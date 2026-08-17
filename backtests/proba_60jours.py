# -*- coding: utf-8 -*-
"""Probabilite de passer la phase 1 FTMO (+10%) en 60 jours MAX, selon le
multiplicateur de risque, avec le systeme H2 (TP/reentree + plafond 2).
Fenetres roulantes de 60 jours sur 5 ans. Rupture = perte journaliere > 5%
ou equite sous -10% du depart. Cout moyen = tentatives x ~750$ CAD."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

KW = dict(tpj_or=1.5, tpj_nq=1.0, tpj_ema=2.0)

def serie(m):
    sleeves = [
        Fib("Or", gc, 0.01*m, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.005*m, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC brk", btc, 0.005*m, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.01*m, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5, tpj=1.0,
            lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC ema", btc, 0.005*m, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
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
        for dt, v in s.pnl.items(): total[dt] += v
    return total.values

base = serie(1.0)   # une seule simulation ; les multiplicateurs scalent les rendements
FRAIS = 750
print(f"{'Risque':>8} | {'Passe<=60j':>10} | {'Rupture':>8} | {'Trop lent':>9} | {'Tentatives':>10} | {'Cout moyen':>11}")
print("-" * 70)
for mult in (1.0, 1.5, 2.0, 3.0, 4.0):
    r = base * mult
    n = len(r); passes = ruptures = timeouts = 0
    for i0 in range(0, n - 60, 5):
        eq, issue = 1.0, "timeout"
        for j in range(i0, min(i0 + 60, n)):
            if r[j] < -0.05: issue = "rupture"; break
            eq *= (1 + r[j])
            if eq <= 0.90: issue = "rupture"; break
            if eq >= 1.10: issue = "passe"; break
        if issue == "passe": passes += 1
        elif issue == "rupture": ruptures += 1
        else: timeouts += 1
    tot = passes + ruptures + timeouts
    p = passes / tot
    tent = 1/p if p > 0 else float("inf")
    print(f"x{mult:>6.1f} | {p*100:>9.0f}% | {ruptures/tot*100:>7.0f}% | {timeouts/tot*100:>8.0f}% | {tent:>10.1f} | {tent*FRAIS:>9.0f} $")
