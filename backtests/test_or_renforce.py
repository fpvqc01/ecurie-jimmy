# -*- coding: utf-8 -*-
"""Synthese : l'or renforce a 3% A L'INTERIEUR de l'ecurie vs or seul vs actuel."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

def sim(nom, or_pct, m_autres, cap):
    sleeves = [
        Fib("Or", gc, or_pct, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0)]
    if m_autres > 0.01:
        sleeves += [
            Donch("Petrole", cl, 0.005*m_autres, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
            Donch("BTC Cassure", btc, 0.005*m_autres, 0.0004, -0.000833, 1.0),
            Fib("Nasdaq", nq, 0.01*m_autres, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5, tpj=1.0,
                lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
            EmaBTC("BTC EMA", btc, 0.005*m_autres, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0)]
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    for date in dates:
        for s in sleeves: s.gerer(date)
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        for s in sleeves:
            if s.pos is not None: continue
            sig = s.signal(date)
            if sig is None: continue
            if cap is not None and ouverts >= cap: continue
            if s.ouvrir(date, **sig): ouverts += 1
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    creux = (eq.min()-1)*100; pire = total.min()*100
    sh = total.mean()/total.std()*np.sqrt(365)
    vals = eq.values; j10 = []
    for i0 in range(0, len(vals)-1, 21):
        ap = np.where(vals[i0:] >= vals[i0]*1.10)[0]
        if len(ap): j10.append(ap[0])
    med = int(np.median(j10)) if j10 else 9999
    viol = "BRISE" if (pire < -5.0 or creux < -10.0) else "ok"
    m1 = len(total)//2
    eq1 = (1+total.iloc[:m1]).cumprod(); eq2 = (1+total.iloc[m1:]).cumprod()
    a1 = (eq1.iloc[-1]**(365.25/m1)-1)*100; a2 = (eq2.iloc[-1]**(365.25/(len(total)-m1))-1)*100
    print(f"{nom:<38} | CAGR {cagr:+5.1f} | creux {creux:+5.1f} | pireJ {pire:+5.2f} | Sh {sh:4.2f} | +10p: {med:>4} j | moities {a1:+5.1f}/{a2:+5.1f} | {viol}")

sim("A. Ecurie actuelle (or 1.5, cap 2)", 0.015, 1.5, 2)
sim("B. Or 3% + autres inchanges, cap 2", 0.03, 1.5, 2)
sim("C. Or 3% + autres reduits x1, cap 2", 0.03, 1.0, 2)
sim("D. Or seul 3% (controle)", 0.03, 0.0, None)
