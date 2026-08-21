# -*- coding: utf-8 -*-
"""L6+ EXACTEMENT TEL QU'IL EST DEPLOYE (turbo x1,33 jusqu'a +4 % de la phase),
AVEC et SANS la fermeture automatique a +10 % de profit du compte.

SANS R13 : l'objectif ne compte que le profit REELLEMENT encaisse (regle FTMO :
           le solde, pas l'equite flottante). C'est l'etat actuel du robot.
AVEC R13 : le robot ferme tout des que le compte touche +10 %, donc le profit
           flottant devient du profit encaisse a l'instant ou il compte.

On note aussi la cause de mort : regle des -5 %/jour ou des -10 % au total."""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B
from sim_ferme import instrumenter

def serie(garde, be, deb, fin):
    ns0 = B.charger(garde)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite = []
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in B.ALLOC: s.risque = B.ALLOC[s.nom]
        if be:
            for s in sl:
                if s.nom in B.PYR: B.breakeven(s, be)
        for s in sl: instrumenter(s)
        boite[:] = sl
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()
    tot = {}
    for s in boite:
        for tt, vv in s.pnl_r.items():
            jj = tt.date(); tot[jj] = tot.get(jj, 0) + vv
    tjr = pd.Series([tot.get(j.date(), 0.0) for j in tj.index], index=tj.index)
    return r[0], r[2], tj, tjr

def phase(vm, vr, i0, cible, mult, coussin, r13):
    eq = bal = 1.0; jt = 0
    for j in range(i0, len(vm)):
        m = mult if (coussin is None or eq < 1 + coussin) else 1.0
        rm, rr = vm[j]*m, vr[j]*m
        if rm != 0.0: jt += 1
        if rm <= -0.05: return 0, j-i0+1, "jour"
        eq *= (1+rm); bal *= (1+rr)
        if eq <= 0.90: return 0, j-i0+1, "total"
        if (eq if r13 else bal) >= 1+cible and jt >= 4: return 1, j-i0+1, None
    return -1, len(vm)-i0, "hors fenetre"

def ftmo(tj, tjr, mult, coussin, r13):
    vm, vr = tj.values, tjr.values
    ok = mj = mt = 0; d = []
    for i0 in range(0, len(vm)-60, 3):
        v1, d1, c1 = phase(vm, vr, i0, 0.10, mult, coussin, r13)
        if v1 == -1: continue
        if v1 == 0:
            mj += (c1 == "jour"); mt += (c1 == "total"); continue
        v2, d2, c2 = phase(vm, vr, i0+d1, 0.05, mult, coussin, r13)
        if v2 == -1: continue
        if v2 == 0:
            mj += (c2 == "jour"); mt += (c2 == "total"); continue
        ok += 1; d.append(d1+d2)
    n = ok+mj+mt
    return 100.0*ok/max(n,1), (np.median(d) if d else 0), 100.0*mj/max(n,1), 100.0*mt/max(n,1)

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
S = {e: serie(0.025, None, d, f) for e, d, f in FEN}   # chassis L6, celui de L6+

print()
print("=== L6+ (turbo x1,33 jusqu'a +4 %) : SANS puis AVEC fermeture a +10 % ===")
print("%-46s | %8s %7s | %9s %9s" % ("", "reussite", "duree", "mort -5%j", "mort -10%"))
print("-" * 84)
for etq, _, _ in FEN:
    cagr, dd, tj, tjr = S[etq]
    print("%s  (rendement %+.1f %%/an, pire creux %+.1f %%)" % (etq.strip(), cagr, dd))
    for nom, mult, cou, r13 in (
            ("  L6+ SANS fermeture a +10 %  (etat actuel)", 1.33, 0.04, False),
            ("  L6+ AVEC fermeture a +10 %", 1.33, 0.04, True),
            ("  -- pour comparer : L6 sans turbo, AVEC", 1.00, None, True),
            ("  -- pour comparer : L8 (autre chassis)",  None, None, None)):
        if mult is None: continue
        o, m, mj, mt = ftmo(tj, tjr, mult, cou, r13)
        print("%-46s | %7.0f %% %5.0f j | %8.0f %% %8.0f %%" % (nom, o, m, mj, mt))
    print()
