# -*- coding: utf-8 -*-
"""Controle d'execution du pyramidage : les unites ajoutees sont remplies au
PIRE de (niveau vise, ouverture du jour) — si le marche a ouvert en ecart
au-dessus du niveau, on paie l'ouverture, pas le niveau. Plus glissement.
Si l'avantage survit a ca, il est reel."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

GARDE = -0.035

def gerer_pyr(self, date):
    i = self.jour(date)
    if i is None or self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    o = self.df["o"].iloc[i]; a = self.a.iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        self._clore(date, p["s"]); self.attente = None; return
    while p["unites"] < self.max_unites and h >= p["prochain"]:
        # EXECUTION REALISTE : si ecart d'ouverture au-dessus du niveau, on paie l'ouverture
        prix_ajout = max(p["prochain"], o) if self.realiste else p["prochain"]
        prix_ajout *= (1 + self.glissement)          # glissement supplementaire
        n_ajout = min(p["n0"], 2.0 - p["n"])
        if n_ajout <= 0: break
        self.pnl[date] = self.pnl.get(date, 0) + n_ajout*(c - prix_ajout)/p["e"] - self.frais*n_ajout
        p["n"] += n_ajout
        p["unites"] += 1
        p["prochain"] = p["prochain"] + self.pas_unite*a
    if p.get("tp") and h >= p["tp"]:
        tp = p["tp"]; self._clore(date, tp)
        if self.jimmy: self.attente = tp
        return
    if p.get("be") and not p["be_fait"] and h >= p["be"]:
        p["s"] = max(p["s"], p["e"]); p["be_fait"] = True
    if p.get("sortie_cloture") and self.sortie_cloture(i):
        self._clore(date, c); self.attente = None; return
    self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
    p["prix"] = c

def ouvrir_pyr(self, date, entree, stop, tp=None, be=None, trail=False, sortie_cloture=False):
    r0p = (entree - stop) / entree
    if r0p <= 0 or r0p > 0.5: return False
    n = min(self.risque / r0p, 2.0)
    self.pnl[date] = self.pnl.get(date, 0) - self.frais * n
    i = self.jour(date); a = self.a.iloc[i]
    self.pos = dict(e=entree, s=stop, tp=tp, n=n, n0=n, be=be, be_fait=False,
                    prix=entree, trail=trail, sortie_cloture=sortie_cloture,
                    unites=1, prochain=entree + self.pas_unite*a)
    self.trades += 1; self.attente = None
    return True

def serie(unites=1, pas=0.5, realiste=True, glissement=0.0, cibles=("BTC Cassure", "Petrole")):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    if unites > 1:
        for s in sleeves:
            if s.nom in cibles:
                s.max_unites, s.pas_unite = unites, pas
                s.realiste, s.glissement = realiste, glissement
                s.gerer = gerer_pyr.__get__(s)
                s.ouvrir = ouvrir_pyr.__get__(s)
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
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    return total, coupes

def stats(total, coupes):
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    vals = total.values; reussis = morts = 0; durees = []
    for i0 in range(0, len(vals)-40, 21):
        eq2 = 1.0
        for j in range(i0, len(vals)):
            eq2 *= (1 + vals[j])
            if eq2 <= 0.92: morts += 1; break
            if eq2 >= 1.10: reussis += 1; durees.append(j-i0); break
    n = reussis + morts
    return cagr, sh, coupes, c1, c2, (morts/n*100 if n else 0), (int(np.median(durees)) if durees else 9999)

print(f"{'Execution des unites ajoutees':<46} | {'CAGR':>6} | {'Sharpe':>6} | {'Coupes':>6} | {'Morts':>6} | {'Duree':>6} | {'Moities':>13}")
print("-" * 118)
for nom, kw in [
    ("Reference (aucun pyramidage)", dict(unites=1)),
    ("3 unites, prix exact (optimiste)", dict(unites=3, realiste=False)),
    ("3 unites, ecart d'ouverture paye", dict(unites=3, realiste=True)),
    ("3 unites, ecart + glissement 0,05 %", dict(unites=3, realiste=True, glissement=0.0005)),
    ("3 unites, ecart + glissement 0,15 %", dict(unites=3, realiste=True, glissement=0.0015)),
    ("2 unites, ecart + glissement 0,05 %", dict(unites=2, realiste=True, glissement=0.0005)),
    ("4 unites, ecart + glissement 0,05 %", dict(unites=4, realiste=True, glissement=0.0005)),
]:
    total, coupes = serie(**kw)
    r = stats(total, coupes)
    print(f"{nom:<46} | {r[0]:>+5.1f}% | {r[1]:>6.2f} | {r[2]:>6} | {r[5]:>5.0f}% | {r[6]:>5} j | {r[3]:>+5.1f}/{r[4]:>+5.1f}%")
