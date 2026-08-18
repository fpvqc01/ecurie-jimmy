# -*- coding: utf-8 -*-
"""Correction demandee par Jimmy (19 aout) : rejouer « laisser courir jusqu'au
recroisement EMA » AVEC le coupe-circuit reel de -3,5 %/jour modelise.
Regle du gardien (comme dans les EA) : si la perte du jour atteint -3,5 %,
tout est ferme, aucune entree avant le lendemain. On suit aussi le nombre
de declenchements et le pire creux (la limite totale FTMO est -10 %, notre
gardien total -8 %).
Approximation honnete : barres journalieres -> on coupe le jour a exactement
-3,5 % (dans la vraie vie il y a du glissement, donc un peu pire)."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

def en_mode_courir(s):
    s.sortie_cloture = (lambda i, s=s: s.e20.iloc[i] <= s.e50.iloc[i])
    original = s.signal
    def signal_sans_tp(date, s=s, original=original):
        sig = original(date)
        if sig is None: return None
        sig["tp"] = None
        sig["sortie_cloture"] = True
        return sig
    s.signal = signal_sans_tp
    s.jimmy = False

GARDE = -0.035

def sim(courir=()):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0,
               jimmy=("BTC EMA" not in courir), retrace=0.25, tpj=2.0),
    ]
    for s in sleeves:
        if s.nom in courir and s.nom != "BTC EMA":
            en_mode_courir(s)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    jours_gardien = 0
    for date in dates:
        for s in sleeves: s.gerer(date)
        jour_total = sum(s.pnl.get(date, 0) for s in sleeves)
        if jour_total <= GARDE:
            facteur = GARDE / jour_total
            for s in sleeves:
                if date in s.pnl: s.pnl[date] *= facteur
                if s.pos is not None:
                    s.pnl[date] = s.pnl.get(date, 0) - s.frais * s.pos["n"]
                s.pos = None; s.attente = None; s.runners = []
            jours_gardien += 1
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
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    pire = total.min()*100
    creux = (eq.min()-1)*100
    dd = ((eq / eq.cummax()).min()-1)*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    return cagr, pire, creux, dd, sh, jours_gardien, c1, c2

print(f"{'Config (gardien -3,5 % ACTIF)':<40} | {'CAGR':>6} | {'Sharpe':>6} | {'PireJ':>6} | {'Creux':>6} | {'MaxDD':>7} | {'Coupes':>6} | {'Moities':>13}")
print("-" * 118)
for nom, courir in [
    ("A. Reference (TP + re-entree)", ()),
    ("C. Or laisse courir", ("Or",)),
    ("E. Les trois laissent courir", ("Or", "Nasdaq", "BTC EMA")),
]:
    r = sim(courir)
    print(f"{nom:<40} | {r[0]:>+5.1f}% | {r[4]:>6.2f} | {r[1]:>+5.2f}% | {r[2]:>+5.1f}% | {r[3]:>+6.1f}% | {r[5]:>6} | {r[6]:>+5.1f}/{r[7]:>+5.1f}%")
