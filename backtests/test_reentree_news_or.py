# -*- coding: utf-8 -*-
"""IDEE DE JIMMY (19 aout soir) : quand un stop est touche PENDANT une fenetre
d'annonce, re-analyser apres la fenetre et re-entrer (3e entree) si les
conditions du trade d'origine tiennent toujours.
Conditions de re-entree apres stop-d'annonce (proxy du 'macro encore favorable') :
  - le plancher du swing d'origine n'a pas casse (these intacte)
  - le prix CONFIRME en recuperant au-dessus du prix de sortie (+ marge)
  - dans un delai limite apres la fenetre
Variantes comparees :
  A. actuelle (serrage, pas de re-entree apres stop d'annonce)
  B. aucun serrage (reference du test precedent)
  E1. serrage + re-entree si H1 cloture > prix de sortie (24 h max)
  E2. serrage + re-entree si H1 cloture > sortie + 0,25xATR (24 h max)
  E3. E2 mais delai 48 h
Base : simulateur or fib+RSI signaux H4 / chemin H1, 29 mois, calendrier reconstruit."""
import requests, pandas as pd, numpy as np
from zoneinfo import ZoneInfo

NY, UTC = ZoneInfo("America/New_York"), ZoneInfo("UTC")

r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/GC=F",
                 params={"range": "730d", "interval": "1h"},
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
r.raise_for_status()
d = r.json()["chart"]["result"][0]
q = d["indicators"]["quote"][0]
h1 = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s", utc=True),
                   "o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]}
                  ).dropna().drop_duplicates("t").set_index("t")
h4 = h1.resample("4h").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()
tr4 = np.maximum(h4["h"]-h4["l"], np.maximum((h4["h"]-h4["c"].shift()).abs(),
                                             (h4["l"]-h4["c"].shift()).abs()))
atr4 = wilder(tr4, 14)
d4 = h4["c"].diff()
rsi4 = 100 - 100/(1 + wilder(d4.clip(lower=0), 14) / wilder(-d4.clip(upper=0), 14).replace(0, np.nan))

def premier_vendredi(an, mois):
    x = pd.Timestamp(an, mois, 1)
    return x + pd.Timedelta(days=(4 - x.dayofweek) % 7)
def ouvrable(x):
    while x.dayofweek >= 5: x += pd.Timedelta(days=1)
    return x
evts = []
for an in (2024, 2025, 2026):
    for mois in range(1, 13):
        evts.append((premier_vendredi(an, mois), 8, 30))
        evts.append((ouvrable(pd.Timestamp(an, mois, 12)), 8, 30))
    for mois, jour in ((1,28),(3,18),(5,6),(6,17),(7,29),(9,16),(11,4),(12,16)):
        x = pd.Timestamp(an, mois, jour); x += pd.Timedelta(days=(2 - x.dayofweek) % 7)
        evts.append((x, 14, 0))
ev_arr = pd.DatetimeIndex(sorted(pd.Timestamp(x.year, x.month, x.day, hh, mm, tzinfo=NY).astimezone(UTC)
                                 for x, hh, mm in evts))

def en_fenetre(t0, t1):
    i = ev_arr.searchsorted(t0 - pd.Timedelta(minutes=90))
    while i < len(ev_arr) and ev_arr[i] <= t1 + pd.Timedelta(minutes=30):
        if t0 < ev_arr[i] + pd.Timedelta(minutes=30) and t1 > ev_arr[i] - pd.Timedelta(minutes=30):
            return True
        i += 1
    return False

FRAIS = 0.0002
SWAP_H = 0.000273 / 24
LOOKBACK, FIBLO, FIBHI, RSIPULL, MULT, TPR, RETRACE = 60, 0.2, 0.8, 55, 3.0, 1.5, 0.25

def simuler(serrage=True, rn_marge=None, rn_delai_h=24):
    """rn_marge : None = pas de re-entree apres stop d'annonce ;
       sinon re-entree si cloture H1 > sortie + rn_marge*ATR, hors fenetre,
       plancher intact, dans le delai."""
    trades, sorties_news, reentrees_news, r_reentrees = [], 0, 0, 0.0
    pos, attente, plancher = None, 0.0, 0.0
    rn = None       # dict(sortie, plancher, limite) re-entree d'annonce armee
    h4_idx = h4.index
    for i in range(200, len(h1)):
        t0 = h1.index[i]; t1 = t0 + pd.Timedelta(hours=1)
        o, hh, ll, cc = h1["o"].iloc[i], h1["h"].iloc[i], h1["l"].iloc[i], h1["c"].iloc[i]
        j = h4_idx.searchsorted(t0) - 1
        if j < LOOKBACK + 16: continue
        fen = en_fenetre(t0, t1)
        a = atr4.iloc[j]
        if pos is not None:
            R = pos["R"]
            if fen and serrage:
                profit_R = (o - pos["e"]) / R
                ns = pos["e"] if profit_R > 0 else o - 0.5*a
                if ns > pos["s"]: pos["s"] = ns
            heures = (t0 - pos["t"]).total_seconds() / 3600
            if ll <= pos["s"]:
                res = (pos["s"] - pos["e"]) / R - FRAIS*pos["e"]/R - SWAP_H*heures*pos["e"]/R
                trades.append(res + pos.get("tag", 0)*0)
                if pos.get("rn"): r_reentrees += res
                if fen:
                    sorties_news += 1
                    if rn_marge is not None and plancher > 0:
                        rn = dict(sortie=pos["s"], plancher=plancher,
                                  limite=t0 + pd.Timedelta(hours=rn_delai_h))
                if pos["s"] >= pos["tp"] - 1e-9: attente, plancher = pos["tp"], pos["lo"]
                pos = None
                continue
            if hh >= pos["tp"]:
                res = TPR - FRAIS*pos["e"]/R - SWAP_H*heures*pos["e"]/R
                trades.append(res)
                if pos.get("rn"): r_reentrees += res
                attente, plancher = pos["tp"], pos["lo"]
                pos = None
                continue
            if pos["s"] < pos["e"] and hh >= pos["e"] + R:
                pos["s"] = pos["e"]
            continue
        # ---- RE-ENTREE D'ANNONCE (l'idee de Jimmy) : des que hors fenetre ----
        if rn is not None:
            if t0 > rn["limite"] or h4["c"].iloc[j] < rn["plancher"]:
                rn = None
            elif not fen and cc > rn["sortie"] + (rn_marge or 0)*a and a > 0:
                e = cc
                pos = dict(e=e, s=e-MULT*a, tp=e+TPR*MULT*a, R=MULT*a, t=t0,
                           lo=rn["plancher"], rn=True)
                reentrees_news += 1
                rn = None
                continue
        if fen: continue
        est_cloture_h4 = (h4_idx[j] + pd.Timedelta(hours=4) <= t0 < h4_idx[j] + pd.Timedelta(hours=5))
        if not est_cloture_h4: continue
        fh = h4["h"].iloc[j-LOOKBACK:j+1]; fl = h4["l"].iloc[j-LOOKBACK:j+1]
        hi_i, lo_i = fh.values.argmax(), fl.values.argmin()
        span = fh.iloc[hi_i] - fl.iloc[lo_i]
        cl4 = h4["c"].iloc[j]
        if attente > 0 and plancher > 0 and cl4 < plancher: attente, plancher = 0.0, 0.0
        if a <= 0 or span <= 0: continue
        setup = False
        if lo_i < hi_i:
            retr = (fh.iloc[hi_i] - cl4) / span
            if FIBLO <= retr <= FIBHI and rsi4.iloc[j-1] < RSIPULL and rsi4.iloc[j] > rsi4.iloc[j-1]:
                setup = True
        reentree = (attente > 0 and h4["l"].iloc[j] <= attente - RETRACE*a and cl4 > plancher)
        if setup or reentree:
            e = cl4
            pos = dict(e=e, s=e-MULT*a, tp=e+TPR*MULT*a, R=MULT*a, t=t0,
                       lo=fl.iloc[lo_i] if setup else plancher)
            if setup: plancher = fl.iloc[lo_i]
            attente = 0.0
    return trades, sorties_news, reentrees_news, r_reentrees

print("%-46s | %-6s | %-7s | %-4s | %-14s | %s" %
      ("Variante", "Trades", "Total R", "PF", "Re-entrees news", "R des re-entrees"))
print("-" * 108)
for nom, kw in [
    ("A. Actuelle (serrage, sans 3e entree)", dict(serrage=True)),
    ("B. Aucun serrage (reference)", dict(serrage=False)),
    ("E1. Serrage + 3e entree des confirmation", dict(serrage=True, rn_marge=0.0)),
    ("E2. Serrage + 3e entree a +0,25xATR", dict(serrage=True, rn_marge=0.25)),
    ("E3. E2 avec delai 48 h", dict(serrage=True, rn_marge=0.25, rn_delai_h=48)),
]:
    t, sn, rn_n, rn_r = simuler(**kw)
    t = np.array(t)
    pf = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else 99
    print("%-46s | %-6d | %+7.2f | %4.2f | %-14d | %+.2f R" %
          (nom, len(t), t.sum(), pf, rn_n, rn_r))
