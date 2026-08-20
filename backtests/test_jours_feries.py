# -*- coding: utf-8 -*-
"""IDEE DE JIMMY (21 aout) : bloquer les entrees les jours FERIES.
Hypothese : liquidite mince = faux signaux et mauvais remplissages ; le BTC
trade 24/7 meme quand les marches americains sont fermes.
Variantes testees sur I2+ et L3 (moteur d'origine, 5 ans) :
  A. reference (aucun blocage)
  B. pas d'entree les jours feries US
  C. B + la veille et le lendemain des feries
  D. pas d'entree pendant la periode des Fetes (24 dec au 2 janv)
  E. C + periode des Fetes
Feries US calcules : Jour de l'An, MLK, Presidents Day, Vendredi saint,
Memorial Day, Juneteenth, 4 juillet, Labor Day, Thanksgiving, Noel."""
import os, pandas as pd, numpy as np
from datetime import date, timedelta

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

# ---------- calendrier des feries americains ----------
def nieme_jour(an, mois, jour_semaine, n):
    d = date(an, mois, 1)
    d += timedelta(days=(jour_semaine - d.weekday()) % 7)
    return d + timedelta(weeks=n-1)

def dernier_jour(an, mois, jour_semaine):
    d = date(an, mois + 1, 1) - timedelta(days=1) if mois < 12 else date(an, 12, 31)
    while d.weekday() != jour_semaine:
        d -= timedelta(days=1)
    return d

def paques(an):
    """algorithme de Meeus/Jones/Butcher"""
    a = an % 19; b = an // 100; c = an % 100
    d = b // 4; e = b % 4; f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19*a + b - d - g + 15) % 30
    i = c // 4; k = c % 4
    l = (32 + 2*e + 2*i - h - k) % 7
    m = (a + 11*h + 22*l) // 451
    mois = (h + l - 7*m + 114) // 31
    jour = ((h + l - 7*m + 114) % 31) + 1
    return date(an, mois, jour)

def feries(an):
    f = set()
    f.add(date(an, 1, 1))                       # Jour de l'An
    f.add(nieme_jour(an, 1, 0, 3))              # MLK (3e lundi janvier)
    f.add(nieme_jour(an, 2, 0, 3))              # Presidents Day
    f.add(paques(an) - timedelta(days=2))       # Vendredi saint
    f.add(dernier_jour(an, 5, 0))               # Memorial Day
    f.add(date(an, 6, 19))                      # Juneteenth
    f.add(date(an, 7, 4))                       # Independence Day
    f.add(nieme_jour(an, 9, 0, 1))              # Labor Day
    f.add(nieme_jour(an, 11, 3, 4))             # Thanksgiving (4e jeudi)
    f.add(date(an, 12, 25))                     # Noel
    return f

TOUS = set()
for an in range(2015, 2028):
    TOUS |= feries(an)

def bloque(d, variante):
    j = d.date() if hasattr(d, "date") else d
    if variante == "A": return False
    if variante in ("B", "C", "E"):
        if j in TOUS: return True
    if variante in ("C", "E"):
        if (j - timedelta(days=1)) in TOUS or (j + timedelta(days=1)) in TOUS: return True
        # la veille/lendemain ouvrable des feries tombant en fin de semaine
        for delta in (2, 3):
            if (j - timedelta(days=delta)) in TOUS and j.weekday() == 0: return True
    if variante in ("D", "E"):
        if (j.month == 12 and j.day >= 24) or (j.month == 1 and j.day <= 2): return True
    return False

# ---------- pyramidage pour L3 ----------
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

def sim(gen, variante):
    pyr = (gen == "L3")
    garde = -0.035 if gen == "I2+" else -0.025
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
        if pyr and s.nom in ("BTC Cassure", "Petrole"):
            s.gerer = gerer_pyr.__get__(s); s.ouvrir = ouvrir_pyr.__get__(s)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    coupes, bloques = 0, 0
    for d in dates:
        for s in sleeves: s.gerer(d)
        jt = sum(s.pnl.get(d, 0) for s in sleeves)
        if jt <= garde:
            f = garde/jt
            for s in sleeves:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            coupes += 1
            continue
        if bloque(d, variante):
            bloques += 1
            continue                      # aucune ENTREE ce jour-la (les sorties restent actives)
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        for s in sleeves:
            if s.pos is not None or ouverts >= 2: continue
            sig = s.signal(d)
            if sig and s.ouvrir(d, **sig): ouverts += 1
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
    return cagr, sh, dd, trades, bloques, c1, c2

NOMS = {
    "A": "A. reference (aucun blocage)",
    "B": "B. pas d'entree les jours feries",
    "C": "C. feries + veille et lendemain",
    "D": "D. periode des Fetes (24 dec - 2 janv)",
    "E": "E. C + periode des Fetes",
}
for gen in ("I2+", "L3"):
    print("=== ECURIE %s (moteur d'origine, 5 ans) ===" % gen)
    print("  %-40s | %-7s | %-6s | %-7s | %-7s | %s" %
          ("Variante", "CAGR", "Sharpe", "MaxDD", "Trades", "Moities"))
    print("  " + "-"*88)
    for v in ("A", "B", "C", "D", "E"):
        r = sim(gen, v)
        print("  %-40s | %+6.1f%% | %6.2f | %+6.1f%% | %7d | %+5.1f/%+5.1f%%" %
              (NOMS[v], r[0], r[1], r[2], r[3], r[5], r[6]))
    print()
