# -*- coding: utf-8 -*-
"""COMBINAISONS DE MARCHES POUR L4 (21 aout) : les 31 sous-ensembles des 5
manches, config L4 (or 2,0 / autres 1,5, plafond correlation, pyramide 3,
gardien 2,5 %, mode challenge 0,75), evalues sur les DEUX moteurs.
Classement : rendement moyen des 2 moteurs, morts = PIRE cas des 2."""
import pandas as pd, numpy as np, itertools
from moteur_1d import Fib, Donch, EmaBTC, gc, cl, nq, btc, FAM
from moteur_1d import ouvrir_pyr as ouvrir_pyr_1d
import moteur_h4 as MH

src = open("scan_strategies.py", encoding="utf-8").read().split("RISQUES =")[0]
ns1 = {"__file__": "scan_strategies.py"}; exec(src, ns1)
gerer_pyr_max_1d = ns1["gerer_pyr_max"]

src = open("valide_candidats_h4.py", encoding="utf-8").read().split("RISQUES =")[0]
ns2 = {"__file__": "valide_candidats_h4.py"}; exec(src, ns2)
gerer_pyr_max_h4 = ns2["gerer_pyr_max"]

R = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)

def sleeves_1d(noms):
    s = []
    if "Or" in noms:
        s.append(Fib("Or", gc, R["Or"], 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25,
                     tpj=1.5, lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0))
    if "Petrole" in noms:
        s.append(Donch("Petrole", cl, R["Petrole"], 0.00045, +0.000051, 1.4, saison=(1201, 531)))
    if "BTC Cassure" in noms:
        s.append(Donch("BTC Cassure", btc, R["BTC"], 0.0004, -0.000833, 1.0))
    if "Nasdaq" in noms:
        s.append(Fib("Nasdaq", nq, R["Nasdaq"], 0.00003, -0.000213, 1.4, jimmy=True,
                     retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0))
    if "BTC EMA" in noms:
        s.append(EmaBTC("BTC EMA", btc, R["BTC"], 0.0004, -0.000833, 1.0, jimmy=True,
                        retrace=0.25, tpj=2.0))
    for x in s:
        if x.nom in ("BTC Cassure", "Petrole"):
            x.pyr_max = 3
            x.gerer = gerer_pyr_max_1d.__get__(x); x.ouvrir = ouvrir_pyr_1d.__get__(x)
    return s

def sleeves_h4(noms):
    s = []
    if "Or" in noms:
        s.append(MH.FibH4("Or", MH.GC, R["Or"], 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25,
                          tpj=1.5, lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0))
    if "Petrole" in noms:
        s.append(MH.DonchH4("Petrole", MH.CL, R["Petrole"], 0.00045, +0.000051, 1.4, saison=(1201, 531)))
    if "BTC Cassure" in noms:
        s.append(MH.DonchH4("BTC Cassure", MH.BTC, R["BTC"], 0.0004, -0.000833, 1.0))
    if "Nasdaq" in noms:
        s.append(MH.FibH4("Nasdaq", MH.NQ, R["Nasdaq"], 0.00003, -0.000213, 1.4, jimmy=True,
                          retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0))
    if "BTC EMA" in noms:
        s.append(MH.EmaBTCH4("BTC EMA", MH.BTC, R["BTC"], 0.0004, -0.000833, 1.0, jimmy=True,
                             retrace=0.25, tpj=2.0))
    for x in s:
        if x.nom in ("BTC Cassure", "Petrole"):
            x.pyr_max = 3
            x.gerer = gerer_pyr_max_h4.__get__(x); x.ouvrir = MH.ouvrir_pyr.__get__(x)
    return s

def metriques(tj):
    eq = (1+tj).cumprod()
    ans = (tj.index[-1]-tj.index[0]).days/365.25
    cagr = (eq.iloc[-1]**(1/ans)-1)*100
    vals = tj.values; morts = reussis = 0
    for i0 in range(0, len(vals)-40, 21):
        e2 = 1.0
        for jx in range(i0, len(vals)):
            e2 *= (1+vals[jx])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; break
    n = morts+reussis
    m = len(tj)//2
    c1 = ((1+tj[:m]).prod()**(1/max(m/365.25,1e-9))-1)*100
    c2 = ((1+tj[m:]).prod()**(1/max((len(tj)-m)/365.25,1e-9))-1)*100
    return cagr, (morts/n*100 if n else 0), c1, c2

def sim_1d(noms):
    sl = sleeves_1d(noms); garde = -0.025
    dates = sorted(set().union(*[set(s.df.index) for s in sl]))
    equite, histo = 1.0, []
    for d in dates:
        for s in sl: s.gerer(d)
        jt = sum(s.pnl.get(d, 0) for s in sl)
        if jt <= garde:
            f = garde/jt
            for s in sl:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            jt = garde
        equite *= (1+jt); histo.append(equite)
        if jt <= garde: continue
        fc = 0.75 if (len(histo) > 20 and equite < np.mean(histo[-20:])) else 1.0
        ouverts = sum(1 for s in sl if s.pos is not None)
        familles = {FAM[s.nom] for s in sl if s.pos is not None}
        for s in sl:
            if s.pos is not None or ouverts >= 2: continue
            if FAM[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(d)
            if sig is None: continue
            r0 = s.risque; s.risque = r0*fc
            ok = s.ouvrir(d, **sig); s.risque = r0
            if ok: ouverts += 1; familles.add(FAM[s.nom])
    tj = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sl:
        for dt, v in s.pnl.items():
            if dt in tj.index: tj[dt] += v
    return metriques(tj.clip(lower=garde))

def sim_h4(noms):
    sl = sleeves_h4(noms); garde = -0.025
    ts = [t for t in sorted(set().union(*[set(s.index) for s in sl]))
          if t >= pd.Timestamp("2024-08-21")]
    jour_pnl, jour_cour, jour_stop = 0.0, None, False
    eq, eq_jours = 1.0, []
    for t in ts:
        j = t.date()
        if j != jour_cour:
            if jour_cour is not None: eq *= (1+jour_pnl); eq_jours.append(eq)
            jour_cour, jour_pnl, jour_stop = j, 0.0, False
        avant = [s.pnl.get(t, 0) for s in sl]
        for s in sl: s.gerer(t)
        jour_pnl += sum(s.pnl.get(t, 0)-avant[q] for q, s in enumerate(sl))
        if jour_stop: continue
        if jour_pnl <= garde:
            av3 = [s.pnl.get(t, 0) for s in sl]
            for s in sl:
                if s.pos is not None:
                    i = s.idx.get(t)
                    if i is not None: s._clore(t, s.C[i])
                s.attente = None
            jour_pnl += sum(s.pnl.get(t, 0)-av3[q] for q, s in enumerate(sl))
            jour_stop = True; continue
        fc = 0.75 if (len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0
        ouverts = sum(1 for s in sl if s.pos is not None)
        familles = {MH.FAM[s.nom] for s in sl if s.pos is not None}
        for s in sl:
            if s.pos is not None or ouverts >= 2: continue
            if MH.FAM[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(t)
            if sig is None: continue
            r0 = s.risque; s.risque = r0*fc
            av2 = s.pnl.get(t, 0)
            ok = s.ouvrir(t, **sig); s.risque = r0
            if ok:
                jour_pnl += s.pnl.get(t, 0)-av2
                ouverts += 1; familles.add(MH.FAM[s.nom])
    tot = {}
    for s in sl:
        for tt, vv in s.pnl.items():
            jj = tt.date(); tot[jj] = tot.get(jj, 0)+vv
    tous = sorted({t.date() for t in ts})
    tj = pd.Series([tot.get(j, 0.0) for j in tous], index=pd.DatetimeIndex(tous))
    return metriques(tj)

MARCHES = ("Or", "Petrole", "Nasdaq", "BTC Cassure", "BTC EMA")
ABR = {"Or": "OR", "Petrole": "PET", "Nasdaq": "NAS", "BTC Cassure": "BTCc", "BTC EMA": "BTCe"}
res = []
for k in range(1, 6):
    for combo in itertools.combinations(MARCHES, k):
        c1, m1, a1, b1 = sim_1d(combo)
        c2, m2, a2, b2 = sim_h4(combo)
        res.append((combo, c1, m1, c2, m2, a1, b1))

def nom(c): return "+".join(ABR[x] for x in c)
res.sort(key=lambda x: -(x[1]+x[3])/2)
print("=== LES 31 COMBINAISONS L4 (mode challenge actif) ===")
print("%-26s | %-14s | %-14s | %-7s %-5s | %s"
      % ("Combinaison", "1d 5 ans", "H4 2 ans", "MOYEN", "PIRE", "Moities 1d"))
print("%-26s | %-6s %-7s | %-6s %-7s | %-7s %-5s |" % ("", "CAGR", "Morts", "CAGR", "Morts", "CAGR", "morts"))
print("-" * 100)
for combo, c1, m1, c2, m2, a1, b1 in res:
    marq = " <-- L4 complet" if len(combo) == 5 else ""
    print("%-26s | %+5.1f%% %5.0f%%  | %+5.1f%% %5.0f%%  | %+6.1f%% %4.0f%% | %+5.1f/%+5.1f%%%s"
          % (nom(combo), c1, m1, c2, m2, (c1+c2)/2, max(m1, m2), a1, b1, marq))
