# -*- coding: utf-8 -*-
"""Verification finale du vol targeting avant implementation :
1. Creux depuis le SOLDE DE DEPART (la mesure FTMO) pour chaque version
2. Version IMPLEMENTABLE : facteur calcule depuis la vol des 5 marches
   (ce que le pipeline Python peut faire chaque matin), pas depuis les
   rendements du portefeuille (invisible en production).
   facteur = clip( 1 / vol_relative_moyenne_des_marches , 0.5 .. 1.5 )
   ou vol_relative = vol20j du marche / sa vol mediane 5 ans."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

m = 1.5
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
r = pd.Series(0.0, index=pd.DatetimeIndex(dates))
for s in sleeves:
    for dt, v in s.pnl.items():
        if dt in r.index: r[dt] += v

def stats(rs, nom):
    eq = (1 + rs).cumprod()
    annees = len(rs) / 365.25
    cagr = (eq.iloc[-1] ** (1/annees) - 1) * 100
    dd_pic = (eq/eq.cummax() - 1).min() * 100
    creux = (eq.min() - 1) * 100
    pire = rs.min() * 100
    sh = rs.mean()/rs.std()*np.sqrt(365) if rs.std() > 0 else 0
    vals = eq.values
    j10 = []
    for i0 in range(0, len(vals)-1, 21):
        ap = np.where(vals[i0:] >= vals[i0]*1.10)[0]
        if len(ap): j10.append(ap[0])
    med = int(np.median(j10)) if j10 else -1
    sous8 = int((eq < 0.92).sum())
    print(f"{nom:<42} | CAGR {cagr:+5.1f}% | CREUX depart {creux:+5.1f}% | jours<-8%: {sous8} | "
          f"pire jour {pire:5.2f}% | Sharpe {sh:4.2f} | +10%: {med} j")

stats(r, "I2 actuel (reference)")

# Version theorique (vol du portefeuille)
vol20 = r.rolling(20).std().shift(1)
f_theo = (r.std() / vol20).clip(upper=1.5).fillna(1.0)
stats(r * f_theo, "Overlay THEORIQUE (vol du portefeuille)")

# Version IMPLEMENTABLE (vol des marches, calculable chaque matin en Python)
vols_rel = []
for df_ in (btc, gc, nq, cl):
    ret = df_["c"].pct_change()
    v20 = ret.rolling(20).std()
    vmed = ret.rolling(252 * 5, min_periods=252).std().median()
    vols_rel.append((v20 / ret.std()).reindex(r.index).ffill())
vol_marche = pd.concat(vols_rel, axis=1).mean(axis=1).shift(1)
f_impl = (1.0 / vol_marche).clip(lower=0.5, upper=1.5).fillna(1.0)
stats(r * f_impl, "Overlay IMPLEMENTABLE (vol des 5 marches)")
