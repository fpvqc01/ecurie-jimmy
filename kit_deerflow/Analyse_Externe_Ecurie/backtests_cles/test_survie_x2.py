# -*- coding: utf-8 -*-
"""Verification de survie du risque x2 (et reference) : simulation de
challenges FTMO par fenetres glissantes. Un challenge demarre chaque ~mois ;
il REUSSIT si +10 % est atteint avant que l'equite touche -8 % vs le depart
(notre gardien total ; la limite FTMO est -10 %), il MEURT sinon.
Gardien -3,5 %/jour actif dans les deux configs."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

GARDE = -0.035

def serie_quotidienne(mult_r):
    sleeves = [
        Fib("Or", gc, 0.03*mult_r, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075*mult_r, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075*mult_r, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015*mult_r, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075*mult_r, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    coupes = 0
    for date in dates:
        for s in sleeves: s.gerer(date)
        jt = sum(s.pnl.get(date, 0) for s in sleeves)
        if jt <= GARDE:
            f = GARDE / jt
            for s in sleeves:
                if date in s.pnl: s.pnl[date] *= f
                if s.pos is not None:
                    s.pnl[date] = s.pnl.get(date, 0) - s.frais * s.pos["n"]
                s.pos = None; s.attente = None; s.runners = []
            coupes += 1
            continue
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
    return total, coupes

for nom, mult in (("Reference (x1)", 1.0), ("Risque x2", 2.0)):
    total, coupes = serie_quotidienne(mult)
    vals = total.values
    reussis = morts = 0; durees = []
    for i0 in range(0, len(vals) - 40, 21):
        eq = 1.0; issue = None
        for j in range(i0, len(vals)):
            eq *= (1 + vals[j])
            if eq <= 0.92: issue = ("mort", j - i0); break
            if eq >= 1.10: issue = ("ok", j - i0); break
        if issue is None: continue
        if issue[0] == "ok": reussis += 1; durees.append(issue[1])
        else: morts += 1
    creux = ((1 + total).cumprod().min() - 1) * 100
    n = reussis + morts
    print(f"{nom} : {n} challenges simules -> {reussis} reussis, {morts} MORTS"
          f" ({morts/n*100:.0f}% d'echec) | duree mediane si reussi {int(np.median(durees))} j"
          f" | creux 5 ans vs depart {creux:+.1f}% | coupes gardien {coupes}")
