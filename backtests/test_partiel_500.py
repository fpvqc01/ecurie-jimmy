# -*- coding: utf-8 -*-
"""Idee de Jimmy (19 aout) : des que le profit ouvert atteint +500 $ (0,5 %
du compte 100k), fermer 1/3 de la position pour securiser, le reste continue
avec les regles normales (stop/TP/trail/re-entree inchanges).
Voisins testes : 1/2 de position, seuils 250/500/1000 $. Une seule fois par trade."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

def gerer_avec_partiel(self, date):
    """Copie de Sleeve.gerer + fermeture partielle a +seuil (une fois par trade)."""
    i = self.jour(date)
    if i is None or self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        self._clore(date, p["s"]); self.attente = None; return
    if not p.get("partiel_fait"):
        ps = p["e"] * (1 + self.seuil_partiel / p["n"])
        if h >= ps:
            frac = self.frac_partiel
            self.pnl[date] = self.pnl.get(date, 0) + frac*p["n"]*(ps-p["prix"])/p["e"] - self.frais*frac*p["n"]
            p["n"] *= (1 - frac)
            p["partiel_fait"] = True
    if p.get("tp") and h >= p["tp"]:
        tp = p["tp"]
        self._clore(date, tp)
        if self.jimmy: self.attente = tp
        return
    if p.get("be") and not p["be_fait"] and h >= p["be"]:
        p["s"] = max(p["s"], p["e"]); p["be_fait"] = True
    if p.get("sortie_cloture") and self.sortie_cloture(i):
        self._clore(date, c); self.attente = None; return
    self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
    p["prix"] = c

def sim(partiel=False, frac=1/3, seuil=0.005):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    if partiel:
        for s in sleeves:
            s.frac_partiel, s.seuil_partiel = frac, seuil
            s.gerer = gerer_avec_partiel.__get__(s)
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
    pire = total.min()*100; creux = (eq.min()-1)*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    return cagr, pire, creux, sh, c1, c2

print(f"{'Config':<42} | {'CAGR':>6} | {'Sharpe':>6} | {'PireJ':>6} | {'Creux':>6} | {'Moities':>13}")
print("-" * 100)
for nom, kw in [
    ("A. Reference (aucune partielle)", dict()),
    ("B. 1/3 ferme a +500 $ (idee de Jimmy)", dict(partiel=True, frac=1/3, seuil=0.005)),
    ("C. 1/2 ferme a +500 $", dict(partiel=True, frac=0.5, seuil=0.005)),
    ("D. 1/3 ferme a +250 $", dict(partiel=True, frac=1/3, seuil=0.0025)),
    ("E. 1/3 ferme a +1000 $", dict(partiel=True, frac=1/3, seuil=0.010)),
]:
    r = sim(**kw)
    print(f"{nom:<42} | {r[0]:>+5.1f}% | {r[3]:>6.2f} | {r[1]:>+5.2f}% | {r[2]:>+5.1f}% | {r[4]:>+5.1f}/{r[5]:>+5.1f}%")
