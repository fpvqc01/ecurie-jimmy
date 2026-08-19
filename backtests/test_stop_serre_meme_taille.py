# -*- coding: utf-8 -*-
"""Idee de Jimmy (19 aout, v2) : rapprocher le stop de l'or SANS grossir la
position. Taille = celle du 3xATR actuel ; TP et breakeven inchanges ;
seul le stop se rapproche (m x ATR). Le risque par trade baisse donc a
3% x m/3 (ex. m=1.25 -> ~1.25%). Portefeuille complet, gardien actif."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

GARDE = -0.035

def stop_rapproche(s, m):
    """Stop a m x ATR mais taille du 3xATR : risque efficace = 3% x m/3."""
    s.risque = 0.03 * m / 3.0          # compense le sizing de ouvrir()
    original = s.signal
    def signal_mod(date, s=s, original=original, m=m):
        sig = original(date)           # mult=3 -> stop3, tp 1.5R(3ATR), be +1R(3ATR)
        if sig is None: return None
        i = s.jour(date)
        a = s.a.iloc[i]
        sig["stop"] = sig["entree"] - m * a   # on rapproche SEULEMENT le stop
        return sig
    s.signal = signal_mod

def sim(m=None):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    if m is not None: stop_rapproche(sleeves[0], m)
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
    pire = total.min()*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    mm = len(total)//2
    c1 = ((1+total[:mm]).prod()**(1/(mm/365.25))-1)*100
    c2 = ((1+total[mm:]).prod()**(1/((len(total)-mm)/365.25))-1)*100
    return cagr, sh, pire, sleeves[0].trades, or_total, c1, c2

print(f"{'Stop or, MEME taille de position':<38} | {'CAGR':>6} | {'Sharpe':>6} | {'PireJ':>6} | {'TradesOr':>8} | {'ContribOr':>9} | {'Moities':>13}")
print("-" * 110)
for nom, m in [
    ("SL 1.25xATR, risque efficace ~1.25%", 1.25),
    ("SL 1.5xATR, risque efficace 1.5%", 1.5),
    ("SL 2xATR, risque efficace 2%", 2.0),
    ("SL 2.5xATR, risque efficace 2.5%", 2.5),
    ("SL 3xATR, risque 3% (ACTUEL)", None),
]:
    r = sim(m)
    print(f"{nom:<38} | {r[0]:>+5.1f}% | {r[1]:>6.2f} | {r[2]:>+5.2f}% | {r[3]:>8} | {r[4]:>+8.1f} | {r[5]:>+5.1f}/{r[6]:>+5.1f}%")
