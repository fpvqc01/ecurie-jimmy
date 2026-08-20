# -*- coding: utf-8 -*-
"""COMPARAISON POMMES-POMMES : les nouveautes dans le MOTEUR D'ORIGINE,
sur les MEMES 5 ans qui avaient donne +30,7 % a L3.
Le moteur optimisation_finale.py contient tout ce que le moteur simplifie
n'avait pas : les 5 manches (dont BTC EMA), le TP/re-entree partout, le
facteur de volatilite, et les frais detailles.
Configurations comparees :
  I2+   : production actuelle (reference historique +18,0 %)
  L3    : + pyramidage + gardien 2,5 %            (avait donne +30,7 %)
  I2++  : L3 + plafond de correlation + parite de risque 1,5 %
  L3+   : I2++ + mode challenge
"""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

FAM = {"Or": "mi", "Nasdaq": "mi", "Petrole": "en", "BTC Cassure": "cr", "BTC EMA": "cr"}

def gerer_pyr(self, date):
    i = self.jour(date)
    if i is None or self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    o = self.df["o"].iloc[i]; a = self.a.iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        self._clore(date, min(p["s"], o)); self.attente = None; return
    while p["unites"] < 3 and h >= p["prochain"]:
        prix = max(p["prochain"], o)
        n_add = min(p["n0"], 2.0 - p["n"])
        if n_add <= 0: break
        self.pnl[date] = self.pnl.get(date, 0) + n_add*(c-prix)/p["e"] - self.frais*n_add
        p["n"] += n_add; p["unites"] += 1; p["prochain"] += 0.5*a
        p["dernier"] = prix
    if p.get("tp") and h >= p["tp"]:
        tp = p["tp"]; self._clore(date, tp)
        if self.jimmy: self.attente = tp
        return
    if p.get("be") and not p["be_fait"] and h >= p["be"]:
        p["s"] = max(p["s"], p["e"]); p["be_fait"] = True
    if p.get("sortie_cloture") and self.sortie_cloture(i):
        self._clore(date, c); self.attente = None; return
    if p["unites"] > 1 and a > 0:
        t = p["dernier"] - 2.0*a
        if t > p["s"]: p["s"] = t
    self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
    p["prix"] = c

def ouvrir_pyr(self, date, entree, stop, tp=None, be=None, trail=False, sortie_cloture=False):
    r0p = (entree - stop) / entree
    if r0p <= 0 or r0p > 0.5: return False
    n = min(self.risque * self.fc / r0p, 2.0)
    self.pnl[date] = self.pnl.get(date, 0) - self.frais * n
    i = self.jour(date); a = self.a.iloc[i]
    self.pos = dict(e=entree, s=stop, tp=tp, n=n, n0=n, be=be, be_fait=False,
                    prix=entree, trail=trail, sortie_cloture=sortie_cloture,
                    unites=1, prochain=entree + 0.5*a, dernier=entree)
    self.trades += 1; self.attente = None
    return True

def sim(gen):
    pyr = gen in ("L3", "I2++", "L3+")
    garde = -0.035 if gen == "I2+" else -0.025
    corr = gen in ("I2++", "L3+")
    chal = (gen == "L3+")
    parite = gen in ("I2++", "L3+")
    r_or  = 0.015 if parite else 0.03
    r_nas = 0.015
    r_pet = 0.015 if parite else 0.0075
    r_btc = 0.015 if parite else 0.0075
    sleeves = [
        Fib("Or", gc, r_or, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, r_pet, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, r_btc, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, r_nas, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, r_btc, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    for s in sleeves:
        s.fc = 1.0
        if pyr and s.nom in ("BTC Cassure", "Petrole"):
            s.gerer = gerer_pyr.__get__(s); s.ouvrir = ouvrir_pyr.__get__(s)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    equite, histo, coupes = 1.0, [], 0
    par_annee, eq_deb = {}, {}
    for date in dates:
        for s in sleeves: s.gerer(date)
        jt = sum(s.pnl.get(date, 0) for s in sleeves)
        if jt <= garde:
            f = garde/jt
            for s in sleeves:
                if date in s.pnl: s.pnl[date] *= f
                s.pos = None; s.attente = None; s.runners = []
            coupes += 1; jt = garde
        an = date.year
        if an not in eq_deb: eq_deb[an] = equite
        equite *= (1+jt); histo.append(equite)
        par_annee[an] = (equite/eq_deb[an]-1)*100
        if jt <= garde: continue
        fc = 1.0
        if chal and len(histo) > 20 and equite < np.mean(histo[-20:]): fc = 0.75
        for s in sleeves: s.fc = fc
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        familles = {FAM[s.nom] for s in sleeves if s.pos is not None}
        for s in sleeves:
            if s.pos is not None or ouverts >= 2: continue
            if corr and FAM[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(date)
            if sig is None: continue
            r0 = s.risque
            if not hasattr(s, "fc") or not pyr or s.nom not in ("BTC Cassure", "Petrole"):
                s.risque = r0 * fc
            ok = s.ouvrir(date, **sig)
            s.risque = r0
            if ok: ouverts += 1; familles.add(FAM[s.nom])
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    total = total.clip(lower=garde)
    eq = (1+total).cumprod(); ans = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/ans)-1)*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    creux = (eq.min()-1)*100
    dd = ((eq/eq.cummax())-1).min()*100
    vals = total.values; morts = reussis = 0; durees = []
    for i0 in range(0, len(vals)-40, 21):
        e2 = 1.0
        for j in range(i0, len(vals)):
            e2 *= (1+vals[j])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; durees.append(j-i0); break
    n = morts+reussis
    return cagr, sh, dd, coupes, (morts/n*100 if n else 0), (int(np.median(durees)) if durees else 9999), par_annee

GENS = ("I2+", "L3", "I2++", "L3+")
res = {g: sim(g) for g in GENS}

print("=== MOTEUR D'ORIGINE, 5 ANS (le meme qui avait donne +30,7 % a L3) ===")
print("  %-8s | %-8s | %-6s | %-8s | %-6s | %-6s | %s" %
      ("Config", "CAGR", "Sharpe", "MaxDD", "Coupes", "Morts", "Duree challenge"))
print("  " + "-"*76)
for g in GENS:
    r = res[g]
    print("  %-8s | %+7.1f%% | %6.2f | %+7.1f%% | %6d | %5.0f%% | %d j" %
          (g, r[0], r[1], r[2], r[3], r[4], r[5]))

print()
print("=== RENDEMENT ANNUEL (moteur d'origine) ===")
annees = sorted(set().union(*[set(res[g][6].keys()) for g in GENS]))
print("  %-6s | %s" % ("Annee", " | ".join("%-9s" % g for g in GENS)))
print("  " + "-"*54)
for a in annees:
    print("  %-6d | %s" % (a, " | ".join("%+8.1f%%" % res[g][6].get(a, 0) for g in GENS)))
