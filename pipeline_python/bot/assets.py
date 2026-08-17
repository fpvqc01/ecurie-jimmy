"""Strategies macro dediees aux actifs non-forex (or, indices).

Chaque actif a une regle de biais macro basee sur les donnees BIS US :
  - gold_real_rates : l'or est long tant que les taux reels US (taux Fed -
    inflation) ne montent pas nettement sur 3 mois. Moteur macro classique
    de l'or : taux reels en baisse = or soutenu.
  - nasdaq_fed : le Nasdaq est long tant que la Fed n'est pas en serrage
    brutal (hausse des taux > 0.5 point sur 6 mois). Achat de replis en
    regime monetaire neutre ou accommodant.

Les biais sont mensuels et decales de 2 mois (delai de publication du CPI).
Regles long-only : en regime defavorable l'actif est simplement evite.
"""
from __future__ import annotations

import pandas as pd

from .macro import component_panels


def _shifted(bias: pd.Series) -> pd.Series:
    return bias.shift(2).fillna(0).astype(int)


def _gold_real_rates(rate_df: pd.DataFrame, yoy_df: pd.DataFrame) -> pd.Series:
    real = rate_df["USD"] - yoy_df["USD"]
    d3 = real - real.shift(3)
    return _shifted((d3 < 0.25).astype(int))


def _nasdaq_fed(rate_df: pd.DataFrame, yoy_df: pd.DataFrame) -> pd.Series:
    mom6 = rate_df["USD"] - rate_df["USD"].shift(6)
    return _shifted((mom6 <= 0.5).astype(int))


BIAS_RULES = {
    "gold_real_rates": _gold_real_rates,
    "nasdaq_fed": _nasdaq_fed,
}


def asset_bias_series(rule: str, rate_df: pd.DataFrame, yoy_df: pd.DataFrame) -> pd.Series:
    if rule not in BIAS_RULES:
        raise ValueError(f"regle de biais inconnue: {rule}")
    return BIAS_RULES[rule](rate_df, yoy_df)


def asset_timing(cfg: dict, acfg: dict) -> dict:
    """Timing de l'actif = timing global surcharge par la section de l'actif."""
    merged = {**cfg["timing"], **acfg.get("timing", {})}
    merged["granularity"] = acfg.get("granularity", merged["granularity"])
    merged["candle_count"] = acfg.get("candle_count", merged["candle_count"])
    return merged


def all_asset_biases(cfg: dict) -> dict[str, tuple[int, pd.Series]]:
    """{instrument: (biais courant, serie mensuelle)} pour cfg['assets']."""
    assets = cfg.get("assets") or {}
    if not assets:
        return {}
    rate_df, yoy_df = component_panels(cfg)
    out = {}
    for inst, acfg in assets.items():
        serie = asset_bias_series(acfg["bias"], rate_df, yoy_df)
        out[inst] = (int(serie.iloc[-1]), serie)
    return out
