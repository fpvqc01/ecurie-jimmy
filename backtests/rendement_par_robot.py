# -*- coding: utf-8 -*-
"""Contribution de chaque robot sur 5 ans (config finale I2+ : cap 2, x1.5)
+ ligne totale avec la couche de volatilite."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

m = 1.5
sleeves = [
    Fib("Or", gc, 0.01*m, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
        lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
    Donch("Petrole", cl, 0.005*m, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
    Donch("BTC Cassure", btc, 0.005*m, 0.0004, -0.000833, 1.0),
    Fib("Nasdaq", nq, 0.01*m, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5, tpj=1.0,
        lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
    EmaBTC("BTC EMA", btc, 0.005*m, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
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
annees = len(dates) / 365.25
print(f"=== Contribution par robot — 5 ans (aout 2021 -> aout 2026), frais reels ===\n")
print(f"{'Robot':<14} | {'Total 5 ans':>11} | {'Par annee':>9} | {'Trades':>6} | {'Gagnants':>8} | {'Meilleure annee':>15}")
print("-" * 82)
resultats = []
for s in sleeves:
    serie = pd.Series(0.0, index=total.index)
    for dt, v in s.pnl.items():
        if dt in total.index:
            total[dt] += v; serie[dt] += v
    cum = (1 + serie).cumprod()
    tot = (cum.iloc[-1] - 1) * 100
    par_an = ((cum.iloc[-1]) ** (1/annees) - 1) * 100
    par_annee = (1 + serie).groupby(serie.index.year).prod() - 1
    meilleure = par_annee.idxmax()
    resultats.append((s.nom, tot, par_an, s.trades, meilleure, par_annee.max()*100))
for nom, tot, par_an, tr, ma, mv in sorted(resultats, key=lambda x: -x[1]):
    print(f"{nom:<14} | {tot:>+10.1f}% | {par_an:>+8.1f}% | {tr:>6} | {'':>8} | {ma} ({mv:+.1f}%)")

eq = (1 + total).cumprod()
print(f"\nPortefeuille (moteur seul)     : total {(eq.iloc[-1]-1)*100:+.1f}% | {((eq.iloc[-1])**(1/annees)-1)*100:+.1f}%/an")
vol20 = total.rolling(20).std().shift(1)
f_impl_vols = []
for df_ in (btc, gc, nq, cl):
    ret = df_["c"].pct_change()
    f_impl_vols.append((ret.rolling(20).std() / ret.std()).reindex(total.index).ffill())
vm = pd.concat(f_impl_vols, axis=1).mean(axis=1).shift(1)
fac = (1.0 / vm).clip(lower=0.5, upper=1.5).fillna(1.0)
eqv = (1 + total * fac).cumprod()
print(f"Portefeuille + couche vol (I2+): total {(eqv.iloc[-1]-1)*100:+.1f}% | {((eqv.iloc[-1])**(1/annees)-1)*100:+.1f}%/an")
