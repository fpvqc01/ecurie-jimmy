# -*- coding: utf-8 -*-
"""IDEE DE JIMMY (21 aout, version 4 -- la plus precise) :
- ecurie SANS BTC (Or + Petrole + Nasdaq)
- les positions deja ouvertes RESTENT ouvertes (rien n'est ferme de force)
- on bloque UNIQUEMENT les nouvelles entrees les jours feries US tombant
  EN SEMAINE (les fins de semaine ne sont pas touchees)
Variantes (moteur d'origine, 5 ans, I2+ et L3) :
  A. reference sans BTC
  F. pas de nouvelle entree les feries US en semaine (calendrier calcule)
  G. pas de nouvelle entree les jours de semaine ou le Nasdaq n'a pas de
     barre (verite terrain = marche US reellement ferme un jour de semaine)
"""
import os, pandas as pd, numpy as np
from datetime import date, timedelta

d0 = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(d0, "test_marche_us_ferme.py"), encoding="utf-8").read()
exec(src.split("def sim(")[0])

def ferie_semaine(d, variante):
    j = d.date() if hasattr(d, "date") else d
    if variante == "A": return False
    if j.weekday() >= 5: return False              # fins de semaine jamais touchees
    if variante == "F": return j in TOUS           # calendrier calcule
    if variante == "G": return j not in JOURS_US   # verite terrain
    return False

def sim(gen, variante, trace=False):
    pyr = (gen == "L3"); garde = -0.035 if gen == "I2+" else -0.025
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
            tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
    ]
    for s in sleeves:
        if pyr and s.nom == "Petrole":
            s.gerer = gerer_pyr.__get__(s); s.ouvrir = ouvrir_pyr.__get__(s)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    coupes, bloq, entrees = 0, 0, []
    for d in dates:
        for s in sleeves: s.gerer(d)               # positions ouvertes : gestion normale
        jt = sum(s.pnl.get(d, 0) for s in sleeves)
        if jt <= garde:
            f = garde/jt
            for s in sleeves:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            coupes += 1; continue
        if ferie_semaine(d, variante):             # seul le NOUVEAU trade est bloque
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
    "A": "A. reference sans BTC",
    "F": "F. pas d'entree feries US en semaine",
    "G": "G. idem, verite terrain (sans barre)",
}
for gen in ("I2+", "L3"):
    print("=== ECURIE %s SANS BTC, positions conservees (moteur d'origine, 5 ans) ===" % gen)
    print("  %-40s | %-7s | %-6s | %-7s | %-6s | %-6s | %-6s | %s" %
          ("Variante", "CAGR", "Sharpe", "MaxDD", "Trades", "Bloq.", "Morts", "Moities"))
    print("  " + "-"*105)
    for v in ("A", "F", "G"):
        r = sim(gen, v)
        print("  %-40s | %+6.1f%% | %6.2f | %+6.1f%% | %6d | %6d | %5.0f%% | %+5.1f/%+5.1f%%" %
              (NOMS[v], r[0], r[1], r[2], r[3], r[8], r[5], r[6], r[7]))
    print()

# combien de jours chaque filtre bloque, et ou tombent les entrees de la reference
tous_j = sorted(set(gc.index) | set(cl.index) | set(nq.index))
for v in ("F", "G"):
    n = sum(1 for d in tous_j if ferie_semaine(d, v))
    print("filtre %s : %d jours de donnees bloques sur %d" % (v, n, len(tous_j)))
for gen in ("I2+", "L3"):
    e = sim(gen, "A", trace=True)
    for v in ("F", "G"):
        tou = [(d, n) for d, n in e if ferie_semaine(d, v)]
        print("  %s / filtre %s : %d entrees sur %d tombent un ferie US en semaine"
              % (gen, v, len(tou), len(e)))
        for d, n in tou:
            print("      %s (%s)  %s" % (d.date(), SEM[d.weekday()], n))
