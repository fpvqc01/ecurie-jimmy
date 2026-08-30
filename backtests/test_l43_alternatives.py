# -*- coding: utf-8 -*-
"""ALTERNATIVES POUR AJOUTER DES PAIRES A "L4.3" (noyau or+petrole+US100),
demande de Jimmy, 20 aout. Le test precedent (ajout massif + elimination)
a echoue en validation. Ici, 4 methodes structurees, toutes jugees sur
2024-2026 apres selection sur 2021-2023 :
  A. ajout UN-A-UN (contribution marginale au noyau, pas de cohue)
  B. comme A mais CAP DE POSITIONS 2 -> 3 (faire de la place)
  C. candidats SHORT sur le forex (cassure baissiere via serie inversee)
  D. satellites a RISQUE REDUIT 0,75 % (complement, pas dominant)
Moteur 1d, 5 ans Yahoo (caches oanda_*.csv de test_oanda_univers.py)."""
import os, pandas as pd, numpy as np
from moteur_1d import Fib, Donch, ouvrir_pyr, gc, cl, nq

src = open("scan_strategies.py", encoding="utf-8").read().split("RISQUES =")[0]
_ns = {"__file__": "scan_strategies.py"}; exec(src, _ns)
gerer_pyr_max = _ns["gerer_pyr_max"]

D = os.path.dirname(os.path.abspath(__file__))
src = open("test_oanda_univers.py", encoding="utf-8").read()
CANDIDATS = eval(src.split("CANDIDATS = ")[1].split("]")[0] + "]")

def charger(sym):
    fn = os.path.join(D, "oanda_" + sym.replace("=", "").replace("^", "") + ".csv")
    return pd.read_csv(fn, index_col=0, parse_dates=True) if os.path.exists(fn) else None

DATA, FAMX, FRSW = {}, {"Or": "mi", "Nasdaq": "mi", "Petrole": "en"}, {}
for nom, sym, fam, frais, swap in CANDIDATS:
    df = charger(sym)
    if df is None or len(df) < 900: continue
    DATA[nom] = df; FAMX[nom] = fam; FRSW[nom] = (frais, swap)
    if fam == "fx":                       # version short : serie inversee
        inv = pd.DataFrame({"o": 1/df["o"], "h": 1/df["l"], "l": 1/df["h"], "c": 1/df["c"]})
        DATA[nom + "_S"] = inv; FAMX[nom + "_S"] = "fx"; FRSW[nom + "_S"] = (frais, swap)

def construire(ajouts, risque_ajout=0.015):
    sl = [Fib("Or", gc, 0.02, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
              lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
          Donch("Petrole", cl, 0.015, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
          Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
              tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0)]
    for nom in ajouts:
        frais, swap = FRSW[nom]
        sl.append(Donch(nom, DATA[nom], risque_ajout, frais, swap, 1.4))
    for s in sl:
        if isinstance(s, Donch):
            s.pyr_max = 3
            s.gerer = gerer_pyr_max.__get__(s); s.ouvrir = ouvrir_pyr.__get__(s)
    return sl

def metriques(tj):
    eq = (1 + tj).cumprod()
    ans = (tj.index[-1] - tj.index[0]).days / 365.25
    cagr = (eq.iloc[-1] ** (1/ans) - 1) * 100
    dd = ((eq / eq.cummax()) - 1).min() * 100
    vals = tj.values; morts = reussis = 0
    for i0 in range(0, len(vals) - 40, 21):
        e2 = 1.0
        for jx in range(i0, len(vals)):
            e2 *= (1 + vals[jx])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; break
    n = morts + reussis
    return cagr, dd, (morts/n*100 if n else 0)

def sim(ajouts, cap=2, risque_ajout=0.015, debut=None, fin=None):
    sl = construire(ajouts, risque_ajout)
    garde = -0.025
    dates = sorted(set().union(*[set(s.df.index) for s in sl]))
    if debut: dates = [x for x in dates if x >= pd.Timestamp(debut)]
    if fin: dates = [x for x in dates if x <= pd.Timestamp(fin)]
    equite, histo = 1.0, []
    for d in dates:
        for s in sl: s.gerer(d)
        jt = sum(s.pnl.get(d, 0) for s in sl)
        if jt <= garde:
            f = garde / jt
            for s in sl:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            jt = garde
        equite *= (1 + jt); histo.append(equite)
        if jt <= garde: continue
        fc = 0.75 if (len(histo) > 20 and equite < np.mean(histo[-20:])) else 1.0
        ouverts = sum(1 for s in sl if s.pos is not None)
        familles = {FAMX[s.nom] for s in sl if s.pos is not None}
        for s in sl:
            if s.pos is not None or ouverts >= cap: continue
            if FAMX[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(d)
            if sig is None: continue
            r0 = s.risque; s.risque = r0 * fc
            ok = s.ouvrir(d, **sig); s.risque = r0
            if ok: ouverts += 1; familles.add(FAMX[s.nom])
    tj = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sl:
        for dt, v in s.pnl.items():
            if dt in tj.index: tj[dt] += v
    return metriques(tj.clip(lower=garde))

FIN_SEL, DEBUT_VAL = "2023-12-31", "2024-01-01"

print("=== PHASE 1 : CONTRIBUTION MARGINALE UN-A-UN (selection 2021-2023) ===")
base_sel = sim([], fin=FIN_SEL)[0]
print("Noyau seul 2021-2023 : %+5.1f%%" % base_sel)
deltas = []
for nom in sorted(DATA):
    c = sim([nom], fin=FIN_SEL)[0]
    deltas.append((nom, c - base_sel))
deltas.sort(key=lambda x: -x[1])
print("Top 10 (delta CAGR vs noyau, _S = version short) :")
for nom, dl in deltas[:10]:
    print("  %-12s %+5.1f pts" % (nom, dl))
print("Pires 3 :")
for nom, dl in deltas[-3:]:
    print("  %-12s %+5.1f pts" % (nom, dl))

TOP3 = [n for n, _ in deltas[:3]]
TOP5 = [n for n, _ in deltas[:5]]
print()
print("Retenus par la selection : TOP3 = %s | TOP5 = %s" % (TOP3, TOP5))

print()
print("=== PHASE 2 : VALIDATION 2024-2026 (jamais vu) + pleine periode ===")
TESTS = [("Noyau L4.3 seul (reference)",        dict(ajouts=[])),
         ("A. noyau + TOP3 (cap 2)",            dict(ajouts=TOP3)),
         ("A'. noyau + TOP5 (cap 2)",           dict(ajouts=TOP5)),
         ("B. noyau + TOP3, cap 3",             dict(ajouts=TOP3, cap=3)),
         ("B'. noyau + TOP5, cap 3",            dict(ajouts=TOP5, cap=3)),
         ("D. noyau + TOP3 a 0,75 %, cap 2",    dict(ajouts=TOP3, risque_ajout=0.0075)),
         ("D'. noyau + TOP3 a 0,75 %, cap 3",   dict(ajouts=TOP3, risque_ajout=0.0075, cap=3))]
print("%-34s | %-24s | %-24s" % ("Alternative", "VALIDATION 2024-2026", "Pleine periode 2021-2026"))
print("%-34s | %-6s %-7s %-6s | %-6s %-7s %-6s" % ("", "CAGR", "MaxDD", "Morts", "CAGR", "MaxDD", "Morts"))
print("-" * 95)
for nom, kw in TESTS:
    cv, dv, mv = sim(debut=DEBUT_VAL, **kw)
    cp, dp, mp = sim(**kw)
    print("%-34s | %+5.1f%% %+6.1f%% %4.0f%%  | %+5.1f%% %+6.1f%% %4.0f%%"
          % (nom, cv, dv, mv, cp, dp, mp))
