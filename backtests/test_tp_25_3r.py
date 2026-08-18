# -*- coding: utf-8 -*-
"""Idee de Jimmy (19 aout) : TP a 2.5R ou 3R au lieu des TP actuels
(or 1.5R, nasdaq 1R, BTC EMA 2R). La re-entree reste active partout.
Balayage : chaque robot individuellement puis tous ensemble."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

def sim(tp_or=1.5, tp_nq=1.0, tp_ema=2.0):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=tp_or,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=tp_nq, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=tp_ema),
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
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    pire = total.min()*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    return cagr, pire, sh, c1, c2

print(f"{'Config (TP or/nasdaq/btc-ema)':<42} | {'CAGR':>6} | {'Sharpe':>6} | {'PireJ':>6} | {'Moities':>13}")
print("-" * 92)
for nom, kw in [
    ("A. Reference 1.5 / 1.0 / 2.0", dict()),
    ("B. Or a 2.5R", dict(tp_or=2.5)),
    ("C. Or a 3.0R", dict(tp_or=3.0)),
    ("D. Nasdaq a 2.5R", dict(tp_nq=2.5)),
    ("E. BTC EMA a 2.5R", dict(tp_ema=2.5)),
    ("F. BTC EMA a 3.0R", dict(tp_ema=3.0)),
    ("G. Tous a 2.5R", dict(tp_or=2.5, tp_nq=2.5, tp_ema=2.5)),
    ("H. Tous a 3.0R", dict(tp_or=3.0, tp_nq=3.0, tp_ema=3.0)),
]:
    r = sim(**kw)
    print(f"{nom:<42} | {r[0]:>+5.1f}% | {r[2]:>6.2f} | {r[1]:>+5.2f}% | {r[3]:>+5.1f}/{r[4]:>+5.1f}%")
