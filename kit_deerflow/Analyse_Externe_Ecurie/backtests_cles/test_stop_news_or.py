# -*- coding: utf-8 -*-
"""Question de Jimmy (19 aout, apres la sortie a -0,78 $ pendant l'annonce) :
le SERRAGE du stop pendant les annonces aide-t-il ou nuit-il au robot or ?
Simulation fib+RSI or sur H1/H4 (2 ans), calendrier reconstruit (NFP/CPI/FOMC).
Variantes de politique pendant la fenetre d'annonce (+-30 min) :
  A. ACTUELLE : breakeven si profit, sinon stop a 0,5xATR (jamais elargi)
  B. AUCUN serrage : stop original conserve
  C. DOUCE : breakeven seulement si profit > 0,5R, sinon 1xATR
  D. BREAKEVEN seulement si profit > 1R (sinon rien)
Mesures : total R, PF, sorties pendant les fenetres, trades.
LIMITE CONNUE : les ecarts/glissements d'annonce ne sont PAS modelises —
le backtest favorise structurellement 'aucun serrage'."""
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
print("Or GC=F : %s -> %s | %d barres H1, %d barres H4" %
      (h1.index[0].date(), h1.index[-1].date(), len(h1), len(h4)))

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()
tr4 = np.maximum(h4["h"]-h4["l"], np.maximum((h4["h"]-h4["c"].shift()).abs(),
                                             (h4["l"]-h4["c"].shift()).abs()))
atr4 = wilder(tr4, 14)
d4 = h4["c"].diff()
rsi4 = 100 - 100/(1 + wilder(d4.clip(lower=0), 14) / wilder(-d4.clip(upper=0), 14).replace(0, np.nan))

# ---- calendrier approximatif ----
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
ev_utc = sorted(pd.Timestamp(x.year, x.month, x.day, hh, mm, tzinfo=NY).astimezone(UTC)
                for x, hh, mm in evts)
ev_arr = pd.DatetimeIndex(ev_utc)

def en_fenetre(t0, t1):
    """la barre H1 [t0,t1) chevauche-t-elle une fenetre evenement +-30 min ?"""
    i = ev_arr.searchsorted(t0 - pd.Timedelta(minutes=90))
    while i < len(ev_arr) and ev_arr[i] <= t1 + pd.Timedelta(minutes=30):
        if t0 < ev_arr[i] + pd.Timedelta(minutes=30) and t1 > ev_arr[i] - pd.Timedelta(minutes=30):
            return True
        i += 1
    return False

FRAIS = 0.0002      # aller-retour ~0,02 %
SWAP_H = 0.000273 / 24

LOOKBACK, FIBLO, FIBHI, RSIPULL, MULT, TPR, RETRACE = 60, 0.2, 0.8, 55, 3.0, 1.5, 0.25

def simuler(politique):
    """politique(profit_R, entree, prix, atr, stop) -> nouveau stop pendant la fenetre"""
    trades, sorties_news = [], 0
    pos, attente, plancher = None, 0.0, 0.0
    h4_idx = h4.index
    for i in range(200, len(h1)):
        t0 = h1.index[i]; t1 = t0 + pd.Timedelta(hours=1)
        o, hh, ll, cc = h1["o"].iloc[i], h1["h"].iloc[i], h1["l"].iloc[i], h1["c"].iloc[i]
        # indicateurs H4 : derniere barre H4 TERMINEE avant t0
        j = h4_idx.searchsorted(t0) - 1
        if j < LOOKBACK + 16: continue
        fen = en_fenetre(t0, t1)
        if pos is not None:
            R = pos["R"]
            # serrage selon la politique (en debut de barre)
            if fen:
                profit_R = (o - pos["e"]) / R
                ns = politique(profit_R, pos["e"], o, atr4.iloc[j], pos["s"])
                if ns is not None and ns > pos["s"]: pos["s"] = ns
            heures = (t0 - pos["t"]).total_seconds() / 3600
            if ll <= pos["s"]:
                res = (pos["s"] - pos["e"]) / R - FRAIS*pos["e"]/R - SWAP_H*heures*pos["e"]/R
                trades.append(res)
                if fen: sorties_news += 1
                if pos["s"] >= pos["tp"] - 1e-9: attente, plancher = pos["tp"], pos["lo"]
                pos = None
                continue
            if hh >= pos["tp"]:
                res = TPR - FRAIS*pos["e"]/R - SWAP_H*heures*pos["e"]/R
                trades.append(res)
                attente, plancher = pos["tp"], pos["lo"]
                pos = None
                continue
            if pos["s"] < pos["e"] and hh >= pos["e"] + R:
                pos["s"] = pos["e"]                       # breakeven +1R (regle de base)
            continue
        # ---- pas de position : signaux sur barre H4 fermee, hors fenetre ----
        if fen: continue
        est_cloture_h4 = (h4_idx[j] + pd.Timedelta(hours=4) <= t0 < h4_idx[j] + pd.Timedelta(hours=5))
        if not est_cloture_h4: continue
        fh = h4["h"].iloc[j-LOOKBACK:j+1]; fl = h4["l"].iloc[j-LOOKBACK:j+1]
        hi_i, lo_i = fh.values.argmax(), fl.values.argmin()
        swing_ok = lo_i < hi_i
        span = fh.iloc[hi_i] - fl.iloc[lo_i]
        cl4 = h4["c"].iloc[j]
        # invalidation de la re-entree
        if attente > 0 and plancher > 0 and cl4 < plancher: attente, plancher = 0.0, 0.0
        a = atr4.iloc[j]
        if a <= 0 or span <= 0: continue
        stopDist = MULT * a
        setup = False
        if swing_ok:
            retr = (fh.iloc[hi_i] - cl4) / span
            if FIBLO <= retr <= FIBHI and rsi4.iloc[j-1] < RSIPULL and rsi4.iloc[j] > rsi4.iloc[j-1]:
                setup = True
        reentree = (attente > 0 and h4["l"].iloc[j] <= attente - RETRACE*a and cl4 > plancher)
        if setup or reentree:
            e = cl4
            pos = dict(e=e, s=e-stopDist, tp=e+TPR*stopDist, R=stopDist, t=t0,
                       lo=fl.iloc[lo_i] if setup else plancher)
            if setup: plancher = fl.iloc[lo_i]
            attente = 0.0
    return trades, sorties_news

POLITIQUES = {
    "A. ACTUELLE (BE si profit, sinon 0,5xATR)":
        lambda pR, e, p, a, s: (e if pR > 0 else p - 0.5*a),
    "B. AUCUN serrage pendant l'annonce":
        lambda pR, e, p, a, s: None,
    "C. DOUCE (BE si +0,5R, sinon 1xATR)":
        lambda pR, e, p, a, s: (e if pR > 0.5 else p - 1.0*a),
    "D. BE seulement si profit > 1R":
        lambda pR, e, p, a, s: (e if pR > 1.0 else None),
}
print()
print("%-44s | %-6s | %-7s | %-4s | %-5s | %s" % ("Politique pendant les annonces", "Trades", "Total R", "PF", "Gagn%", "Sorties en fenetre"))
print("-" * 100)
for nom, pol in POLITIQUES.items():
    t, sn = simuler(pol)
    t = np.array(t)
    pf = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else 99
    print("%-44s | %-6d | %+7.2f | %4.2f | %4.0f%% | %d" %
          (nom, len(t), t.sum(), pf, (t > 0).mean()*100, sn))
