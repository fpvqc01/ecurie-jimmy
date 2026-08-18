# -*- coding: utf-8 -*-
"""Idee de Jimmy (19 aout) : laisser courir les trades TANT QUE l'EMA 20/50
ne recroise pas — aucun TP. Le stop initial et le breakeven restent.
  - BTC EMA : jimmy=False (plus de TP ni re-entree, sortie = recroisement, deja code)
  - Or / Nasdaq : TP retire, sortie ajoutee quand EMA20 <= EMA50 (journalier)
Variantes robot par robot puis toutes ensemble."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

def en_mode_courir(s):
    """Retire le TP du sleeve et ajoute la sortie sur recroisement EMA20/50."""
    s.sortie_cloture = (lambda i, s=s: s.e20.iloc[i] <= s.e50.iloc[i])
    original = s.signal
    def signal_sans_tp(date, s=s, original=original):
        sig = original(date)
        if sig is None: return None
        sig["tp"] = None
        sig["sortie_cloture"] = True
        return sig
    s.signal = signal_sans_tp
    s.jimmy = False   # plus de re-entree (il n'y a plus de TP pour l'armer)

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

print(f"{'Config':<44} | {'CAGR':>6} | {'Sharpe':>6} | {'PireJ':>6} | {'Moities':>13}")
print("-" * 94)
for nom, courir in [
    ("A. Reference (TP + re-entree)", ()),
    ("B. BTC EMA laisse courir (sortie recroise)", ("BTC EMA",)),
    ("C. Or laisse courir", ("Or",)),
    ("D. Nasdaq laisse courir", ("Nasdaq",)),
    ("E. Les trois laissent courir", ("Or", "Nasdaq", "BTC EMA")),
]:
    r = sim(courir)
    print(f"{nom:<44} | {r[0]:>+5.1f}% | {r[2]:>6.2f} | {r[1]:>+5.2f}% | {r[3]:>+5.1f}/{r[4]:>+5.1f}%")
