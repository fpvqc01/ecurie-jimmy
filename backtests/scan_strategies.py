# -*- coding: utf-8 -*-
"""SCAN SYSTEMATIQUE (21 aout) : objectif = PLUS de rendement, MOINS de
challenges morts. Chassis L3 (pyramidage + gardien 2,5 %), on balaie :
  - plafond de correlation : oui/non
  - jeu de risques : R0 original (or 3/nas 1,5/pet+btc 0,75)
                     R1 parite plate 1,5 partout
                     R2 or 1,5 / nas 1,5 / pet 1,0 / btc 1,0
                     R3 or 2,0 / nas 1,5 / pet 1,0 / btc 1,0
  - pyramide max : 2 ou 3 unites
  - mode challenge (throttle) : off / x0,75 / x0,50
  - frein de drawdown : off / (risque x0,5 si drawdown depuis sommet > 4 %)
96 configs, moteur 1d 5 ans. Ensuite : frontiere rendement/morts."""
import pandas as pd, numpy as np, itertools
from moteur_1d import (Fib, Donch, EmaBTC, ouvrir_pyr, gc, cl, nq, btc, FAM)

def gerer_pyr_max(self, date_):
    i = self.jour(date_)
    if i is None or self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    o = self.df["o"].iloc[i]; a = self.a.iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        self._clore(date_, min(p["s"], o)); self.attente = None; return
    while p["unites"] < self.pyr_max and h >= p["prochain"]:
        prix = max(p["prochain"], o)
        n_add = min(p["n0"], 2.0 - p["n"])
        if n_add <= 0: break
        self.pnl[date_] = self.pnl.get(date_, 0) + n_add*(c-prix)/p["e"] - self.frais*n_add
        p["n"] += n_add; p["unites"] += 1; p["prochain"] += 0.5*a; p["dernier"] = prix
    if p.get("tp") and h >= p["tp"]:
        tp = p["tp"]; self._clore(date_, tp)
        if self.jimmy: self.attente = tp
        return
    if p.get("be") and not p["be_fait"] and h >= p["be"]:
        p["s"] = max(p["s"], p["e"]); p["be_fait"] = True
    if p.get("sortie_cloture") and self.sortie_cloture(i):
        self._clore(date_, c); self.attente = None; return
    if p["unites"] > 1 and a > 0:
        t = p["dernier"] - 2.0*a
        if t > p["s"]: p["s"] = t
    self.pnl[date_] = self.pnl.get(date_, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
    p["prix"] = c

RISQUES = {
    "R0": dict(Or=0.03,  Nasdaq=0.015, Petrole=0.0075, BTC=0.0075),
    "R1": dict(Or=0.015, Nasdaq=0.015, Petrole=0.015,  BTC=0.015),
    "R2": dict(Or=0.015, Nasdaq=0.015, Petrole=0.01,   BTC=0.01),
    "R3": dict(Or=0.02,  Nasdaq=0.015, Petrole=0.01,   BTC=0.01),
}

def sim_p(corr, rset, pyr_max, throttle, frein, garde=-0.025, serie_out=False):
    R = RISQUES[rset]
    sleeves = [
        Fib("Or", gc, R["Or"], 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, R["Petrole"], 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, R["BTC"], 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, R["Nasdaq"], 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
            tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, R["BTC"], 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    for s in sleeves:
        if s.nom in ("BTC Cassure", "Petrole"):
            s.pyr_max = pyr_max
            s.gerer = gerer_pyr_max.__get__(s); s.ouvrir = ouvrir_pyr.__get__(s)
    dates = sorted(set().union(*[set(s.df.index) for s in sleeves]))
    equite, sommet, histo = 1.0, 1.0, []
    for d in dates:
        for s in sleeves: s.gerer(d)
        jt = sum(s.pnl.get(d, 0) for s in sleeves)
        if jt <= garde:
            f = garde/jt
            for s in sleeves:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            jt = garde
        equite *= (1+jt); histo.append(equite)
        sommet = max(sommet, equite)
        if jt <= garde: continue
        fc = 1.0
        if throttle and len(histo) > 20 and equite < np.mean(histo[-20:]): fc = throttle
        if frein and equite < sommet * (1 - 0.04): fc = min(fc, 0.5)
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        familles = {FAM[s.nom] for s in sleeves if s.pos is not None}
        for s in sleeves:
            if s.pos is not None or ouverts >= 2: continue
            if corr and FAM[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(d)
            if sig is None: continue
            r0 = s.risque; s.risque = r0 * fc
            ok = s.ouvrir(d, **sig)
            s.risque = r0
            if ok: ouverts += 1; familles.add(FAM[s.nom])
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    total = total.clip(lower=garde)
    eq = (1+total).cumprod()
    ans = (total.index[-1] - total.index[0]).days / 365.25
    cagr = (eq.iloc[-1]**(1/ans)-1)*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    dd = ((eq/eq.cummax())-1).min()*100
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    vals = total.values; morts = reussis = 0
    for i0 in range(0, len(vals)-40, 21):
        e2 = 1.0
        for jx in range(i0, len(vals)):
            e2 *= (1+vals[jx])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; break
    n = morts + reussis
    r = dict(cagr=cagr, sharpe=sh, dd=dd, morts=(morts/n*100 if n else 0), m1=c1, m2=c2)
    if serie_out: r["serie"] = total
    return r

resultats = []
for corr, rset, pmax, thr, frein in itertools.product(
        (False, True), ("R0", "R1", "R2", "R3"), (2, 3), (None, 0.75, 0.5), (False, True)):
    r = sim_p(corr, rset, pmax, thr, frein)
    resultats.append((corr, rset, pmax, thr, frein, r))

# references
print("REFERENCES : L3 = corr:N R0 pyr3 thr:N frein:N | L3+ ~ corr:O R1 pyr3 thr0.75")
print()
print("%-5s %-4s %-4s %-5s %-6s | %-7s %-6s %-7s %-5s | %s"
      % ("corr", "risq", "pyr", "thr", "frein", "CAGR", "Sharpe", "MaxDD", "Morts", "Moities"))
print("-" * 85)
# tri : d'abord la frontiere de Pareto (aucune autre config avec cagr>= ET morts<=)
front = []
for x in resultats:
    r = x[5]
    domine = any(y[5]["cagr"] >= r["cagr"] and y[5]["morts"] <= r["morts"]
                 and (y[5]["cagr"] > r["cagr"] or y[5]["morts"] < r["morts"]) for y in resultats)
    if not domine: front.append(x)
front.sort(key=lambda x: -x[5]["cagr"])
print("--- FRONTIERE DE PARETO (aucune config ne fait mieux sur les 2 axes) ---")
for corr, rset, pmax, thr, frein, r in front:
    print("%-5s %-4s %-4d %-5s %-6s | %+6.1f%% %6.2f %+6.1f%% %4.0f%% | %+5.1f/%+5.1f%%"
          % ("oui" if corr else "non", rset, pmax, str(thr), "oui" if frein else "non",
             r["cagr"], r["sharpe"], r["dd"], r["morts"], r["m1"], r["m2"]))
print()
print("--- MEILLEURES PAR OBJECTIF ---")
mieux_l3 = [x for x in resultats if x[5]["cagr"] > 31.1 and x[5]["morts"] < 16]
mieux_l3.sort(key=lambda x: (x[5]["morts"], -x[5]["cagr"]))
print("Configs qui BATTENT L3 sur les DEUX axes (cagr > 31,1 ET morts < 16) : %d" % len(mieux_l3))
for corr, rset, pmax, thr, frein, r in mieux_l3[:10]:
    print("%-5s %-4s %-4d %-5s %-6s | %+6.1f%% %6.2f %+6.1f%% %4.0f%% | %+5.1f/%+5.1f%%"
          % ("oui" if corr else "non", rset, pmax, str(thr), "oui" if frein else "non",
             r["cagr"], r["sharpe"], r["dd"], r["morts"], r["m1"], r["m2"]))
