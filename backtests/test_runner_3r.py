# -*- coding: utf-8 -*-
"""Idee de Jimmy (19 aout) : quand un TP ferme un trade, garder un RUNNER
jusqu'a 3R max, stop suiveur toujours en profit, vie limitee a ~24 h
(1 barre journaliere dans le moteur — approximation honnete pour l'EMA H1).
Variantes : 75% TP / 25% runner, et 50/50 ; sur le BTC EMA seul (le robot
a TP 2R vise par l'idee) puis sur les 3 robots a TP (or, nasdaq, btc ema).
La re-entree reste active (le runner s'AJOUTE, il ne remplace rien)."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

def gerer_avec_runner(self, date):
    """Copie de Sleeve.gerer avec runner plafonne 3R + vie max + trail en profit."""
    i = self.jour(date)
    if i is None: return
    if self.runners:
        c_ = self.df["c"].iloc[i]; l_ = self.df["l"].iloc[i]; h_ = self.df["h"].iloc[i]
        a_ = self.a.iloc[i]
        restants = []
        for r in self.runners:
            r["vie"] += 1
            if l_ <= r["trail"]:      # stop suiveur touche (toujours >= prix de TP donc en profit)
                self.pnl[date] = self.pnl.get(date, 0) + r["n"]*(r["trail"]-r["prix"])/r["e0"] - self.frais*r["n"]
            elif h_ >= r["cap"]:      # plafond 3R atteint
                self.pnl[date] = self.pnl.get(date, 0) + r["n"]*(r["cap"]-r["prix"])/r["e0"] - self.frais*r["n"]
            elif r["vie"] >= self.vie_max:   # 24 h ecoulees -> sortie a la cloture
                self.pnl[date] = self.pnl.get(date, 0) + r["n"]*(c_-r["prix"])/r["e0"] - self.frais*r["n"]
            else:
                self.pnl[date] = self.pnl.get(date, 0) + r["n"]*((c_-r["prix"])/r["e0"] + self.swap*self.fs)
                r["prix"] = c_
                r["trail"] = max(r["trail"], c_ - a_)
                restants.append(r)
        self.runners = restants
    if self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        self._clore(date, p["s"]); self.attente = None; return
    if p.get("tp") and h >= p["tp"]:
        tp = p["tp"]
        R = (tp - p["e"]) / self.tpj          # retrouve le R initial en prix
        part = self.part_runner
        self.pnl[date] = self.pnl.get(date, 0) + (1-part)*p["n"]*(tp-p["prix"])/p["e"] - self.frais*(1-part)*p["n"]
        self.runners.append(dict(n=part*p["n"], e0=p["e"], prix=tp,
                                 trail=max(p["e"] + 0.1*R, tp - self.a.iloc[i]),
                                 cap=p["e"] + 3*R, vie=0))
        self.pos = None
        if self.jimmy: self.attente = tp
        return
    if p.get("be") and not p["be_fait"] and h >= p["be"]:
        p["s"] = max(p["s"], p["e"]); p["be_fait"] = True
    if p.get("sortie_cloture") and self.sortie_cloture(i):
        self._clore(date, c); self.attente = None; return
    self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
    p["prix"] = c

def sim(runner_sur=None, part=0.25, vie=1):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    for s in sleeves:
        if runner_sur and s.nom in runner_sur:
            s.part_runner, s.vie_max = part, vie
            s.gerer = gerer_avec_runner.__get__(s)
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

TP3 = ("Or", "Nasdaq", "BTC EMA")
print(f"{'Config':<44} | {'CAGR':>6} | {'Sharpe':>6} | {'PireJ':>6} | {'Moities':>13}")
print("-" * 90)
for nom, kw in [
    ("A. Reference (TP plein, re-entree)", dict()),
    ("B. Runner 25% -> 3R, 24h, BTC EMA seul", dict(runner_sur=("BTC EMA",), part=0.25, vie=1)),
    ("C. Runner 50% -> 3R, 24h, BTC EMA seul", dict(runner_sur=("BTC EMA",), part=0.50, vie=1)),
    ("D. Runner 25% -> 3R, 24h, les 3 robots TP", dict(runner_sur=TP3, part=0.25, vie=1)),
    ("E. Runner 25% -> 3R, 48h, les 3 robots TP", dict(runner_sur=TP3, part=0.25, vie=2)),
    ("F. Runner 50% -> 3R, 48h, les 3 robots TP", dict(runner_sur=TP3, part=0.50, vie=2)),
]:
    r = sim(**kw)
    print(f"{nom:<44} | {r[0]:>+5.1f}% | {r[2]:>6.2f} | {r[1]:>+5.2f}% | {r[3]:>+5.1f}/{r[4]:>+5.1f}%")
