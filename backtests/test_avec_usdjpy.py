# -*- coding: utf-8 -*-
"""Config finale (5 robots) AVEC et SANS un 6e robot USDJPY
(EMA 20/50 DEUX SENS, TP 1.5R, stop 2xATR, risque 0.75%).
Premiere classe deux-sens du moteur (le forex se vend aussi).
Frais estimes : 0.003%/cote ; swap achat +0.005%/j, vente -0.010%/j.
5 ans, moities, 12 derniers mois — meme protocole que GBPUSD/Nasdaq."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

jpy = fetch("USDJPY=X")
print(f"USDJPY 5 ans : {jpy.index[0].date()} -> {jpy.index[-1].date()}, {len(jpy)} jours")

class EmaFx2S:
    """EMA 20/50 deux sens avec TP fixe, swap asymetrique (carry)."""
    def __init__(self, nom, df, risque, frais, swap_l, swap_s, fs, tpj=1.5):
        self.nom, self.df, self.risque, self.frais = nom, df, risque, frais
        self.swap_l, self.swap_s, self.fs, self.tpj = swap_l, swap_s, fs, tpj
        self.idx = {d: i for i, d in enumerate(df.index)}
        self.pos, self.pnl, self.trades = None, {}, 0
        self.a = atr_(df)
        self.e20 = df["c"].ewm(span=20, adjust=False).mean()
        self.e50 = df["c"].ewm(span=50, adjust=False).mean()

    def jour(self, date): return self.idx.get(date)

    def _clore(self, date, prix):
        p = self.pos
        self.pnl[date] = self.pnl.get(date, 0) + p["n"]*p["dir"]*(prix-p["prix"])/p["e"] - self.frais*p["n"]
        self.pos = None

    def gerer(self, date):
        i = self.jour(date)
        if i is None or self.pos is None: return
        p = self.pos
        c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
        haussier = self.e20.iloc[i] > self.e50.iloc[i]
        if p["dir"] == 1:
            if l <= p["s"]: self._clore(date, p["s"]); return
            if h >= p["tp"]: self._clore(date, p["tp"]); return
            if not haussier: self._clore(date, c); return
        else:
            if h >= p["s"]: self._clore(date, p["s"]); return
            if l <= p["tp"]: self._clore(date, p["tp"]); return
            if haussier: self._clore(date, c); return
        sw = self.swap_l if p["dir"] == 1 else self.swap_s
        self.pnl[date] = self.pnl.get(date, 0) + p["n"]*(p["dir"]*(c-p["prix"])/p["e"] + sw*self.fs)
        p["prix"] = c

    def signal(self, date):
        i = self.jour(date)
        if i is None or i < 60 or self.pos is not None: return None
        haussier = self.e20.iloc[i] > self.e50.iloc[i]
        croise_h = haussier and self.e20.iloc[i-1] <= self.e50.iloc[i-1]
        croise_b = (not haussier) and self.e20.iloc[i-1] >= self.e50.iloc[i-1]
        if not (croise_h or croise_b): return None
        c = self.df["c"].iloc[i]; R = 2*self.a.iloc[i]
        if croise_h: return dict(entree=c, stop=c-R, tp=c+self.tpj*R, dir=1)
        return dict(entree=c, stop=c+R, tp=c-self.tpj*R, dir=-1)

    def ouvrir(self, date, entree, stop, tp, dir):
        r0p = abs(entree - stop) / entree
        if r0p <= 0 or r0p > 0.5: return False
        n = min(self.risque / r0p, 2.0)
        self.pnl[date] = self.pnl.get(date, 0) - self.frais * n
        self.pos = dict(e=entree, s=stop, tp=tp, n=n, dir=dir, prix=entree)
        self.trades += 1
        return True

def sim(avec_jpy, moitie=None, jours=None):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    if avec_jpy:
        sleeves.append(EmaFx2S("USDJPY EMA", jpy, 0.0075, 0.00003, +0.00005, -0.00010, 1.4))
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
for nom, avec in [("SANS USDJPY (actuel)", False), ("AVEC USDJPY (6 robots)", True)]:
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
