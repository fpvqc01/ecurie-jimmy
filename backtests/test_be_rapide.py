# -*- coding: utf-8 -*-
"""Idee de Jimmy (19 aout) : « laisser courir juste quand c'est profitable et
fermer a 50/100/200 % de gain ». Interpretation : breakeven arme des que le
trade est profitable (+0,1R sur barres journalieres), TP a 0,5R / 1R / 2R
(50/100/200 % du montant risque). Gardien -3,5 %/jour modelise partout.
Applique aux 3 robots a TP (or, nasdaq, btc ema), re-entree conservee."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

def en_mode_be_rapide(s, tp_r):
    """Breakeven des +0,1R, TP a tp_r x R (R = distance entree-stop)."""
    original = s.signal
    def signal_mod(date, s=s, original=original, tp_r=tp_r):
        sig = original(date)
        if sig is None: return None
        R = sig["entree"] - sig["stop"]
        if R <= 0: return None
        sig["tp"] = sig["entree"] + tp_r * R
        sig["be"] = sig["entree"] + 0.1 * R
        return sig
    s.signal = signal_mod

GARDE = -0.035

def sim(tp_r=None):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    if tp_r is not None:
        for s in sleeves:
            if s.nom in ("Or", "Nasdaq", "BTC EMA"):
                en_mode_be_rapide(s, tp_r)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    coupes = 0
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
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    pire = total.min()*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    return cagr, pire, sh, coupes, c1, c2

print(f"{'Config (gardien actif)':<46} | {'CAGR':>6} | {'Sharpe':>6} | {'Coupes':>6} | {'Moities':>13}")
print("-" * 92)
for nom, tp_r in [
    ("A. Reference (TP 1.5/1/2, be +1R)", None),
    ("B. BE des profit, TP 0.5R (50% du risque)", 0.5),
    ("C. BE des profit, TP 1R (100% du risque)", 1.0),
    ("D. BE des profit, TP 2R (200% du risque)", 2.0),
]:
    r = sim(tp_r)
    print(f"{nom:<46} | {r[0]:>+5.1f}% | {r[2]:>6.2f} | {r[3]:>6} | {r[4]:>+5.1f}/{r[5]:>+5.1f}%")
