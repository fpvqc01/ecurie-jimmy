# -*- coding: utf-8 -*-
"""Idee de Jimmy (19 aout, en regardant son graphique or) : stop plus serre
+ position plus grosse (risque constant 3 %). Balayage du multiplicateur ATR
du stop de l'or : 1.25 / 1.5 / 2 / 2.5 / 3 (actuel) / 3.5, plus la variante
« stop au plancher du swing » (sous le dernier support, comme il le ferait).
TP recalcule a 1.5R et breakeven a +1R dans tous les cas (R = distance au stop).
Portefeuille complet, gardien -3.5 %/jour actif."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

GARDE = -0.035

def stop_swing(s):
    """Stop au plus bas des `lookback` dernieres barres (le support)."""
    original = s.signal
    def signal_mod(date, s=s, original=original):
        sig = original(date)
        if sig is None: return None
        i = s.jour(date)
        plancher = s.df["l"].iloc[max(0, i - s.lb):i].min()
        e = sig["entree"]
        if plancher >= e: return None
        R = e - plancher
        sig["stop"] = plancher
        sig["tp"] = e + s.tpj * R
        sig["be"] = e + R
        return sig
    s.signal = signal_mod

def sim(mult_or=3.0, swing=False):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=mult_or, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    if swing: stop_swing(sleeves[0])
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
    or_total = sum(sleeves[0].pnl.values()) * 100
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    return cagr, sh, coupes, sleeves[0].trades, or_total, c1, c2

print(f"{'Stop de l or (risque constant 3%)':<38} | {'CAGR':>6} | {'Sharpe':>6} | {'Coupes':>6} | {'TradesOr':>8} | {'ContribOr':>9} | {'Moities':>13}")
print("-" * 108)
for nom, kw in [
    ("SL 1.25xATR (~le 4300 de Jimmy)", dict(mult_or=1.25)),
    ("SL 1.5xATR", dict(mult_or=1.5)),
    ("SL 2xATR", dict(mult_or=2.0)),
    ("SL 2.5xATR", dict(mult_or=2.5)),
    ("SL 3xATR (ACTUEL)", dict(mult_or=3.0)),
    ("SL 3.5xATR", dict(mult_or=3.5)),
    ("SL au plancher du swing (support)", dict(swing=True)),
]:
    r = sim(**kw)
    print(f"{nom:<38} | {r[0]:>+5.1f}% | {r[1]:>6.2f} | {r[2]:>6} | {r[3]:>8} | {r[4]:>+8.1f} | {r[5]:>+5.1f}/{r[6]:>+5.1f}%")
