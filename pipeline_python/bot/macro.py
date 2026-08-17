"""Couche MACRO : scores par devise a partir des donnees BIS (gratuites, sans cle).

Sources (Banque des Reglements Internationaux, mises a jour en continu) :
  - WS_CBPOL    : taux directeurs officiels des banques centrales
  - WS_LONG_CPI : inflation (variation du CPI sur 12 mois, code unite 771)

Score(devise) = w1 * carry + w2 * momentum de taux + w3 * tendance d'inflation,
chaque composante etant standardisee (z-score) entre les devises, mois par mois.

Biais d'une paire BASE_QUOTE = score(BASE) - score(QUOTE) :
  > +seuil  -> seuls les achats (long) sont autorises
  < -seuil  -> seules les ventes (short) sont autorisees
  sinon     -> pas de trade sur cette paire
"""
from __future__ import annotations

import io

import pandas as pd
import requests

BIS_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS/{flow}/1.0/{key}?format=csv"


def _fetch_bis_monthly(flow: str, key: str) -> pd.Series:
    """Serie mensuelle BIS (index = fin de mois)."""
    r = requests.get(BIS_URL.format(flow=flow, key=key), timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))[["TIME_PERIOD", "OBS_VALUE"]].dropna()
    idx = pd.PeriodIndex(df["TIME_PERIOD"], freq="M").to_timestamp("M")
    s = pd.Series(df["OBS_VALUE"].to_numpy(dtype=float), index=idx)
    return s[~s.index.duplicated(keep="last")].sort_index()


def policy_rate(area: str) -> pd.Series:
    return _fetch_bis_monthly("WS_CBPOL", f"M.{area}")


def inflation_yoy(area: str) -> pd.Series:
    return _fetch_bis_monthly("WS_LONG_CPI", f"M.{area}.771")


def component_panels(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(taux directeurs, inflation YoY) : DataFrames mensuels devises en colonnes.

    Le CPI sort avec ~1-2 mois de retard : on prolonge la derniere valeur
    connue (ffill) pour que les mois recents restent calculables.
    """
    rates, yoys = {}, {}
    for ccy, area in cfg["macro"]["series"].items():
        try:
            rates[ccy] = policy_rate(area)
            yoys[ccy] = inflation_yoy(area)
        except Exception as e:
            print(f"[macro] AVERTISSEMENT: {ccy} (zone {area}) ignoree: {e}")
    if len(rates) < 2:
        raise RuntimeError("Pas assez de devises avec des donnees macro valides.")
    rate_df, yoy_df = pd.DataFrame(rates), pd.DataFrame(yoys)
    idx = rate_df.index.union(yoy_df.index)
    return rate_df.reindex(idx).ffill(), yoy_df.reindex(idx).ffill()


def scores_history(cfg: dict) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Historique mensuel des scores (mois x devises) + composantes brutes."""
    rate_df, yoy_df = component_panels(cfg)
    comps = {
        "carry": rate_df,
        "rate_momentum": rate_df - rate_df.shift(6),
        "inflation_trend": yoy_df - yoy_df.shift(3),
    }
    weights = cfg["macro"]["weights"]
    total = None
    for name, panel in comps.items():
        z = panel.sub(panel.mean(axis=1), axis=0).div(
            panel.std(axis=1).replace(0, 1), axis=0)
        part = z * weights[name]
        total = part if total is None else total + part
    return total, comps


def currency_scores(cfg: dict) -> pd.DataFrame:
    """Photo du dernier mois disponible : devises x [composantes, score]."""
    scores, comps = scores_history(cfg)
    last = scores.dropna(how="all").index[-1]
    out = pd.DataFrame({name: panel.loc[last] for name, panel in comps.items()})
    out["score"] = scores.loc[last]
    return out.dropna(subset=["score"])


# Actifs "risque" cotes contre une devise : leur score macro propre est neutre
# (0), donc leur biais = l'inverse de la force macro de la devise de cotation.
# Ex: XAU_USD -> Fed hawkish (score USD haut) = biais short sur l'or.
RISK_ASSETS = {"XAU", "XAG", "US30", "SPX500", "NAS100", "DE30"}


def pair_bias(pair: str, scores: pd.DataFrame, threshold: float) -> int:
    """+1 = long autorise, -1 = short autorise, 0 = pas de trade."""
    base, quote = pair.split("_")
    if quote not in scores.index:
        return 0
    if base in scores.index:
        base_score = scores.loc[base, "score"]
    elif base in RISK_ASSETS:
        base_score = 0.0
    else:
        return 0
    diff = base_score - scores.loc[quote, "score"]
    if diff > threshold:
        return 1
    if diff < -threshold:
        return -1
    return 0
