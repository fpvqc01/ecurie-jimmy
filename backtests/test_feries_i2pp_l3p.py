# -*- coding: utf-8 -*-
"""IDEE DE JIMMY (21 aout, version 5) : le meme test que la v4 mais sur les
NOUVELLES generations I2++ et L3+ :
  - pyramidage (petrole), gardien quotidien 2,5 %
  - plafond de correlation (un seul or/Nasdaq a la fois)
  - parite de risque 1,5 % partout
  - L3+ : + mode challenge (risque x0,75 sous la moyenne 20 jours)
Toujours : SANS BTC (Or + Petrole + Nasdaq), positions conservees, seules
les NOUVELLES entrees bloquees les feries US en semaine.
Variantes : A reference / F calendrier calcule / G verite terrain.
"""
import os, pandas as pd, numpy as np
from datetime import date, timedelta

d0 = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(d0, "test_marche_us_ferme.py"), encoding="utf-8").read()
exec(src.split("def sim(")[0])

FAM = {"Or": "mi", "Nasdaq": "mi", "Petrole": "en"}

def ferie_semaine(d, variante):
    j = d.date() if hasattr(d, "date") else d
    if variante == "A": return False
    if j.weekday() >= 5: return False
    if variante == "F": return j in TOUS
    if variante == "G": return j not in JOURS_US
    return False

def sim(gen, variante, trace=False):
    garde = -0.025                          # gardien 2,5 % des deux generations
    chal = (gen == "L3+")
    sleeves = [
        Fib("Or", gc, 0.015, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.015, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
            tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
    ]
    for s in sleeves:
        if s.nom == "Petrole":
            s.gerer = gerer_pyr.__get__(s); s.ouvrir = ouvrir_pyr.__get__(s)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    equite, histo = 1.0, []
    coupes, bloq, entrees = 0, 0, []
    for d in dates:
        for s in sleeves: s.gerer(d)
        jt = sum(s.pnl.get(d, 0) for s in sleeves)
        if jt <= garde:
            f = garde/jt
            for s in sleeves:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            coupes += 1; jt = garde
        equite *= (1+jt); histo.append(equite)
        if jt <= garde: continue
        if ferie_semaine(d, variante):
            bloq += 1; continue
        fc = 1.0
        if chal and len(histo) > 20 and equite < np.mean(histo[-20:]): fc = 0.75
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        familles = {FAM[s.nom] for s in sleeves if s.pos is not None}
        for s in sleeves:
            if s.pos is not None or ouverts >= 2: continue
            if FAM[s.nom] == "mi" and "mi" in familles: continue   # plafond correlation
            sig = s.signal(d)
            if sig is None: continue
            r0 = s.risque; s.risque = r0 * fc
            ok = s.ouvrir(d, **sig)
            s.risque = r0
            if ok:
                ouverts += 1; familles.add(FAM[s.nom]); entrees.append((d, s.nom))
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
for gen in ("I2++", "L3+"):
    print("=== ECURIE %s SANS BTC, positions conservees (moteur d'origine, 5 ans) ===" % gen)
    print("  %-40s | %-7s | %-6s | %-7s | %-6s | %-6s | %-6s | %s" %
          ("Variante", "CAGR", "Sharpe", "MaxDD", "Trades", "Bloq.", "Morts", "Moities"))
    print("  " + "-"*105)
    for v in ("A", "F", "G"):
        r = sim(gen, v)
        print("  %-40s | %+6.1f%% | %6.2f | %+6.1f%% | %6d | %6d | %5.0f%% | %+5.1f/%+5.1f%%" %
              (NOMS[v], r[0], r[1], r[2], r[3], r[8], r[5], r[6], r[7]))
    print()

for gen in ("I2++", "L3+"):
    e = sim(gen, "A", trace=True)
    for v in ("F", "G"):
        tou = [(d, n) for d, n in e if ferie_semaine(d, v)]
        print("  %s / filtre %s : %d entrees sur %d tombent un ferie US en semaine"
              % (gen, v, len(tou), len(e)))
        for d, n in tou:
            print("      %s (%s)  %s" % (d.date(), SEM[d.weekday()], n))
