# -*- coding: utf-8 -*-
"""Config finale (5 robots) AVEC et SANS un 6e robot GBPUSD
(EMA 20/50 achat seul, TP 1.5R + re-entree, risque 0.75%, frais forex FTMO).
5 ans, moities, 12 derniers mois â€” meme protocole que le test Nasdaq."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

gbp = fetch("GBPUSD=X")
print(f"GBPUSD 5 ans : {gbp.index[0].date()} -> {gbp.index[-1].date()}, {len(gbp)} jours")

def sim(avec_gbp, moitie=None, jours=None):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    if avec_gbp:
        sleeves.append(EmaBTC("GBPUSD EMA", gbp, 0.0075, 0.00003, -0.000033, 1.4,
                              jimmy=True, retrace=0.25, tpj=1.5))
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    if moitie == 1: dates = dates[:len(dates)//2]
    if moitie == 2: dates = dates[len(dates)//2:]
    if jours: dates = dates[-jours:]
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
    detail = {}
    for s in sleeves:
        detail[s.nom] = sum(s.pnl.values()) * 100
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    creux = (eq.min()-1)*100; pire = total.min()*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    return cagr, creux, pire, sh, detail

print(f"\n{'Config':<24} | {'CAGR':>6} | {'Creux':>6} | {'PireJ':>6} | {'Sharpe':>6}")
print("-" * 62)
for nom, avec in [("SANS GBPUSD (actuel)", False), ("AVEC GBPUSD (6 robots)", True)]:
    r = sim(avec)
    print(f"{nom:<24} | {r[0]:>+5.1f}% | {r[1]:>+5.1f}% | {r[2]:>+5.2f}% | {r[3]:>6.2f}")
    if avec:
        print("  contributions (points de % cumules sur 5 ans) :")
        for k, v in r[4].items(): print(f"    {k:<12} {v:+7.1f}")
print("\n--- Moities (5 ans) ---")
for nom, avec in [("SANS", False), ("AVEC", True)]:
    r1 = sim(avec, moitie=1); r2 = sim(avec, moitie=2)
    print(f"{nom} : {r1[0]:+.1f}% / {r2[0]:+.1f}%")
print("\n--- 12 derniers mois ---")
for nom, avec in [("SANS", False), ("AVEC", True)]:
    r = sim(avec, jours=365)
    print(f"{nom} : {r[0]:+.1f}% | Sharpe {r[3]:.2f}")

