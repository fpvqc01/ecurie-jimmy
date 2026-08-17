# -*- coding: utf-8 -*-
"""Question de Jimmy : moins de robots mais plus de risque et pas de blocage
= plus de gains ? Configs testees (5 ans, frais reels, SANS plafond pour les
sous-ensembles) : or seul, or+petrole, or+petrole+nasdaq, a divers risques,
contre l'ecurie complete (5 robots, plafond 2, x1.5)."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

def flotte(noms, m):
    tous = {
        "Or": lambda: Fib("Or", gc, 0.01*m, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
                          lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        "Petrole": lambda: Donch("Petrole", cl, 0.005*m, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        "BTC Cassure": lambda: Donch("BTC Cassure", btc, 0.005*m, 0.0004, -0.000833, 1.0),
        "Nasdaq": lambda: Fib("Nasdaq", nq, 0.01*m, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5, tpj=1.0,
                              lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        "BTC EMA": lambda: EmaBTC("BTC EMA", btc, 0.005*m, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    }
    return [tous[n]() for n in noms]

def simuler_libre(noms, m, cap):
    sleeves = flotte(noms, m)
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
    eq = (1 + total).cumprod()
    annees = len(total) / 365.25
    cagr = (eq.iloc[-1] ** (1/annees) - 1) * 100
    creux = (eq.min() - 1) * 100
    pire = total.min() * 100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    vals = eq.values
    j10 = []
    for i0 in range(0, len(vals)-1, 21):
        ap = np.where(vals[i0:] >= vals[i0]*1.10)[0]
        if len(ap): j10.append(ap[0])
    med = int(np.median(j10)) if j10 else 9999
    viol = "❌FTMO" if (pire < -5.0 or creux < -10.0) else "ok"
    return cagr, creux, pire, sh, med, viol

print(f"{'Config':<40} | {'CAGR':>6} | {'Creux':>6} | {'PireJ':>6} | {'Sharpe':>6} | {'+10%':>5} | {'Regles':>6}")
print("-" * 92)
tests = [
    ("ECURIE 5 robots, cap 2, x1.5 (actuel)", ["Or","Petrole","BTC Cassure","Nasdaq","BTC EMA"], 1.5, 2),
    ("Or SEUL, risque 1.5%", ["Or"], 1.5, None),
    ("Or SEUL, risque 3%", ["Or"], 3.0, None),
    ("Or SEUL, risque 4.5%", ["Or"], 4.5, None),
    ("Or+Petrole, sans cap, risque x1.5", ["Or","Petrole"], 1.5, None),
    ("Or+Petrole, sans cap, risque x3", ["Or","Petrole"], 3.0, None),
    ("Or+Petrole+Nasdaq, sans cap, x1.5", ["Or","Petrole","Nasdaq"], 1.5, None),
    ("Or+Petrole+Nasdaq, sans cap, x2.25", ["Or","Petrole","Nasdaq"], 2.25, None),
]
for nom, robots, m, cap in tests:
    r = simuler_libre(robots, m, cap)
    print(f"{nom:<40} | {r[0]:>+5.1f}% | {r[1]:>+5.1f}% | {r[2]:>+5.2f}% | {r[3]:>6.2f} | {r[4]:>5} | {r[5]:>6}")
