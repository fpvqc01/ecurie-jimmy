# -*- coding: utf-8 -*-
"""IDEE DE JIMMY (21 aout, version 2) : bloquer les trades quand le MARCHE
AMERICAIN EST FERME -- donc fins de semaine ET jours feries, pas juste les
feries. Seul le BTC peut trader a ces moments-la.
Variantes (moteur d'origine, 5 ans, I2+ et L3) :
  A. reference
  B. pas d'entree la fin de semaine (sam/dim)
  C. pas d'entree fin de semaine + feries (calendrier calcule)
  D. pas d'entree quand le NASDAQ n'a pas de barre  <- verite terrain
  E. D + on ferme les positions BTC avant la fin de semaine (zero exposition
     pendant que le marche US dort)
"""
import os, pandas as pd, numpy as np
from datetime import date, timedelta

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_feries.py"),
          encoding="utf-8").read().split("def bloque")[0])

JOURS_US = set(nq.index.date)          # verite terrain : le Nasdaq a une barre
SEM = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]

def ferme(d, variante):
    j = d.date() if hasattr(d, "date") else d
    if variante == "A": return False
    if variante == "B": return j.weekday() >= 5
    if variante == "C": return j.weekday() >= 5 or j in TOUS
    if variante in ("D", "E"): return j not in JOURS_US
    return False

# ---------- pyramidage (L3) ----------
def gerer_pyr(self, date_):
    i = self.jour(date_)
    if i is None or self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    o = self.df["o"].iloc[i]; a = self.a.iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        self._clore(date_, min(p["s"], o)); self.attente = None; return
    while p["unites"] < 3 and h >= p["prochain"]:
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

def ouvrir_pyr(self, date_, entree, stop, tp=None, be=None, trail=False, sortie_cloture=False):
    r0p = (entree - stop) / entree
    if r0p <= 0 or r0p > 0.5: return False
    n = min(self.risque / r0p, 2.0)
    self.pnl[date_] = self.pnl.get(date_, 0) - self.frais * n
    i = self.jour(date_); a = self.a.iloc[i]
    self.pos = dict(e=entree, s=stop, tp=tp, n=n, n0=n, be=be, be_fait=False,
                    prix=entree, trail=trail, sortie_cloture=sortie_cloture,
                    unites=1, prochain=entree + 0.5*a, dernier=entree)
    self.trades += 1; self.attente = None
    return True

def sim(gen, variante, trace=False):
    pyr = (gen == "L3"); garde = -0.035 if gen == "I2+" else -0.025
    plat = (variante == "E")
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
            tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    for s in sleeves:
        if pyr and s.nom in ("BTC Cassure", "Petrole"):
            s.gerer = gerer_pyr.__get__(s); s.ouvrir = ouvrir_pyr.__get__(s)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    coupes, bloq, entrees = 0, 0, []
    for d in dates:
        for s in sleeves: s.gerer(d)
        # variante E : on aplatit avant la fermeture du marche US
        if plat:
            dem = d + pd.Timedelta(days=1)
            if ferme(dem, "D"):
                for s in sleeves:
                    if s.pos is not None:
                        i = s.jour(d)
                        if i is not None:
                            s._clore(d, s.df["c"].iloc[i])
                        s.attente = None
        jt = sum(s.pnl.get(d, 0) for s in sleeves)
        if jt <= garde:
            f = garde/jt
            for s in sleeves:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            coupes += 1; continue
        if ferme(d, variante):
            bloq += 1; continue
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        for s in sleeves:
            if s.pos is not None or ouverts >= 2: continue
            sig = s.signal(d)
            if sig and s.ouvrir(d, **sig):
                ouverts += 1; entrees.append((d, s.nom))
    if trace: return entrees
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    total = total.clip(lower=garde)
    eq = (1+total).cumprod(); ans = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/ans)-1)*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    dd = ((eq/eq.cummax())-1).min()*100
    trades = sum(s.trades for s in sleeves)
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    vals = total.values; morts = reussis = 0
    for i0 in range(0, len(vals)-40, 21):
        e2 = 1.0
        for j in range(i0, len(vals)):
            e2 *= (1+vals[j])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; break
    n = morts+reussis
    mort = morts/n*100 if n else 0
    return cagr, sh, dd, trades, coupes, mort, c1, c2, bloq

NOMS = {
    "A": "A. reference",
    "B": "B. rien la fin de semaine",
    "C": "C. fin de semaine + feries",
    "D": "D. Nasdaq ferme (verite terrain)",
    "E": "E. D + on aplatit avant la fermeture",
}
for gen in ("I2+", "L3"):
    print("=== ECURIE %s (moteur d'origine, 5 ans) ===" % gen)
    print("  %-38s | %-7s | %-6s | %-7s | %-6s | %-6s | %s" %
          ("Variante", "CAGR", "Sharpe", "MaxDD", "Trades", "Morts", "Moities"))
    print("  " + "-"*95)
    for v in ("A", "B", "C", "D", "E"):
        r = sim(gen, v)
        print("  %-38s | %+6.1f%% | %6.2f | %+6.1f%% | %6d | %5.0f%% | %+5.1f/%+5.1f%%" %
              (NOMS[v], r[0], r[1], r[2], r[3], r[5], r[6], r[7]))
    print()

print("=== JOURS OU LE MARCHE US EST FERME (verite terrain) ===")
tous_j = sorted(set().union(set(btc.index), set(gc.index), set(nq.index), set(cl.index)))
fer_d = [d for d in tous_j if ferme(d, "D")]
print("  %d jours sur %d (%.1f%%) -- dont %d fins de semaine et %d feries en semaine"
      % (len(fer_d), len(tous_j), len(fer_d)/len(tous_j)*100,
         sum(1 for d in fer_d if d.weekday() >= 5),
         sum(1 for d in fer_d if d.weekday() < 5)))
print()
for gen in ("I2+", "L3"):
    e = sim(gen, "A", trace=True)
    tou = [(d, n) for d, n in e if ferme(d, "D")]
    print("  %s : %d entrees sur %d tombent marche US ferme" % (gen, len(tou), len(e)))
    for d, n in tou:
        print("      %s (%s)  %s" % (d.date(), SEM[d.weekday()], n))
