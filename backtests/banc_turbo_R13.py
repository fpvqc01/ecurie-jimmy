# -*- coding: utf-8 -*-
"""BANC TURBO + FERMETURE A L'OBJECTIF (R13) — 21 aout 2026.

Le turbo-coussin est le SEUL levier connu qui coupe la duree de moitie
(118 j contre 205). Son defaut : 75 % de reussite sur 10 ans, 69 % sur
2021-2026. Question de Jimmy : est-ce qu'on peut le dompter ?

On balaye multiplicateur x coussin sur DEUX chassis :
  - chassis L6 (gardien -2,5 %, sans breakeven) : celui de L6+ aujourd'hui
  - chassis L8 (gardien -1,75 % + breakeven 5 %) : le meilleur creux

Tous avec R13 (fermeture a l'objectif). On note aussi COMMENT ca meurt :
par la regle des -5 %/jour ou par celle des -10 % au total. C'est la
difference entre un reglage trop agressif et un chassis trop fragile."""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B

def serie(garde, be, deb, fin):
    ns0 = B.charger(garde)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in B.ALLOC: s.risque = B.ALLOC[s.nom]
        if be:
            for s in sl:
                if s.nom in B.PYR: B.breakeven(s, be)
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    return r[0], r[2], r[6].sort_index()

def phase(v, i0, cible, mult, coussin):
    """turbo : on trade a `mult` tant que la phase n'a pas atteint `coussin`,
    puis on revient a x1. Retourne (issue, jours, cause)."""
    eq = 1.0; jt = 0; pire = 1.0
    for j in range(i0, len(v)):
        m = mult if (coussin is None or eq < 1 + coussin) else 1.0
        r = v[j] * m
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j-i0+1, "jour", pire
        eq *= (1 + r); pire = min(pire, eq)
        if eq <= 0.90: return 0, j-i0+1, "total", pire
        if eq >= 1 + cible and jt >= 4: return 1, j-i0+1, None, pire
    return -1, len(v)-i0, None, pire

def ftmo(tj, mult, coussin):
    v = tj.values
    ok = 0; mj = mt = 0; d = []; pires = []
    for i0 in range(0, len(v)-60, 3):
        v1, d1, c1, p1 = phase(v, i0, 0.10, mult, coussin)
        if v1 == -1: continue
        if v1 == 0:
            (mj := mj + 1) if c1 == "jour" else (mt := mt + 1); continue
        v2, d2, c2, p2 = phase(v, i0+d1, 0.05, mult, coussin)
        if v2 == -1: continue
        if v2 == 0:
            (mj := mj + 1) if c2 == "jour" else (mt := mt + 1); continue
        ok += 1; d.append(d1+d2); pires.append(min(p1, p2))
    n = ok + mj + mt
    return (100.0*ok/max(n,1), (np.median(d) if d else 0),
            100.0*mj/max(n,1), 100.0*mt/max(n,1),
            (100*(min(pires)-1) if pires else 0))

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
CHASSIS = (("chassis L6  (gardien -2,50 %, sans breakeven)", 0.025, None),
           ("chassis L8  (gardien -1,75 % + breakeven 5 %)", 0.0175, 0.05))
MULTS   = (1.00, 1.15, 1.25, 1.33, 1.50)
COUSSINS = (0.02, 0.03, 0.04, 0.06, None)   # None = turbo permanent

for titre, garde, be in CHASSIS:
    S = {etq: serie(garde, be, d, f) for etq, d, f in FEN}
    print(); print("=== %s ===" % titre)
    print("(rendement de base %+.1f %% sur 10 ans, creux %+.1f %%)"
          % (S["10 ANS "][0], S["10 ANS "][1]))
    print("%-30s | %-26s | %s" % ("", "10 ANS", "2021-2026"))
    print("%-30s | %8s %6s %9s | %8s %6s" % ("reglage", "reussite", "duree", "mort -5%j", "reussite", "duree"))
    print("-" * 88)
    for mult in MULTS:
        for cou in COUSSINS:
            if mult == 1.00 and cou is not None: continue      # sans turbo : un seul cas
            etq = ("sans turbo (reference)" if mult == 1.00 else
                   "x%.2f %s" % (mult, "permanent" if cou is None else "jusqu'a +%.0f %%" % (cou*100)))
            l = "%-30s |" % etq
            for k, (etqf, _, _) in enumerate(FEN):
                o, m, mj, mt, pire = ftmo(S[etqf][2], mult, cou)
                if k == 0: l += " %7.0f %% %4.0f j %8.0f %% |" % (o, m, mj)
                else:      l += " %7.0f %% %4.0f j" % (o, m)
            print(l)
