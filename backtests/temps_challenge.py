# -*- coding: utf-8 -*-
"""Temps pour passer les 2 phases FTMO avec la config finale
(or 3%, autres x1.5, cap 2, + couche vol) : medianes et fourchettes."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

sleeves = [
    Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
        lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
    Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
    Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
    Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5, tpj=1.0,
        lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
    EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
]
dates = sorted(set().union(*[s.df.index for s in sleeves]))
for date in dates:
    for s in sleeves: s.gerer(date)
    ouverts = sum(1 for s in sleeves if s.pos is not None)
    for s in sleeves:
        if s.pos is not None: continue
        sig = s.signal(date)
        if sig is None: continue
        if ouverts >= 2: continue
        if s.ouvrir(date, **sig): ouverts += 1
total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
for s in sleeves:
    for dt, v in s.pnl.items():
        if dt in total.index: total[dt] += v

# couche de volatilite (version implementable)
vols = []
for df_ in (btc, gc, nq, cl):
    ret = df_["c"].pct_change()
    vols.append((ret.rolling(20).std() / ret.std()).reindex(total.index).ffill())
vm = pd.concat(vols, axis=1).mean(axis=1).shift(1)
fac = (1.0 / vm).clip(lower=0.5, upper=1.5).fillna(1.0)
r = total * fac
eq = (1 + r).cumprod()
vals = eq.values

def temps_vers(cible):
    jours = []
    rates = 0
    for i0 in range(0, len(vals) - 30, 10):
        ap = np.where(vals[i0:] >= vals[i0] * (1 + cible))[0]
        if len(ap): jours.append(ap[0])
        else: rates += 1
    j = np.array(jours)
    tot = len(jours) + rates
    return (int(np.percentile(j, 25)), int(np.median(j)), int(np.percentile(j, 75)),
            len(jours) * 100 // tot)

for nom, cible in [("PHASE 1 (+10%)", 0.10), ("PHASE 2 (+5%)", 0.05)]:
    p25, med, p75, atteint = temps_vers(cible)
    print(f"{nom} : mediane {med} j | 25% des cas <= {p25} j | 75% des cas <= {p75} j | atteint dans {atteint}% des departs historiques")
annees = len(r) / 365.25
print(f"\n(config finale complete : CAGR simule {((eq.iloc[-1])**(1/annees)-1)*100:+.1f}%/an)")
