# -*- coding: utf-8 -*-
"""MATRICE COMPLETE (demande Jimmy, 21 aout) : TURBO x MODE CHALLENGE,
avec et sans fermeture automatique a +10 % de profit du compte.

  turbo          = mises x1,33 tant que la phase n'a pas atteint +4 %
  mode challenge = frein d'equite : mises reduites a 75 % quand l'equite
                   passe sous sa moyenne des 20 derniers jours
  fermeture +10 %= le robot ferme tout des que le compte touche +10 %
                   (R13). Sans elle, l'objectif ne compte que le profit
                   REELLEMENT encaisse, comme l'exige FTMO.

Chassis L6 (gardien -2,50 %, allocation a x0,75), donnees reparees."""
import os, sys, io
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_ecuries_L6_modes as BM
import banc_L8 as B
from sim_ferme import instrumenter

def serie(mode_on, deb, fin):
    ns0 = BM.charger(mode_on)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite = []
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in B.ALLOC: s.risque = B.ALLOC[s.nom]
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

def phase(vm, vr, i0, cible, mult, cou, r13):
    eq = bal = 1.0; jt = 0
    for j in range(i0, len(vm)):
        m = mult if (cou is None or eq < 1 + cou) else 1.0
        rm, rr = vm[j]*m, vr[j]*m
        if rm != 0.0: jt += 1
        if rm <= -0.05: return 0, j-i0+1
        eq *= (1+rm); bal *= (1+rr)
        if eq <= 0.90: return 0, j-i0+1
        if (eq if r13 else bal) >= 1+cible and jt >= 4: return 1, j-i0+1
    return -1, len(vm)-i0

def ftmo(tj, tjr, mult, cou, r13):
    vm, vr = tj.values, tjr.values
    ok = mort = 0; d = []
    for i0 in range(0, len(vm)-60, 3):
        v1, d1 = phase(vm, vr, i0, 0.10, mult, cou, r13)
        if v1 == -1: continue
        if v1 == 0: mort += 1; continue
        v2, d2 = phase(vm, vr, i0+d1, 0.05, mult, cou, r13)
        if v2 == -1: continue
        if v2 == 0: mort += 1; continue
        ok += 1; d.append(d1+d2)
    n = ok+mort
    return 100.0*ok/max(n,1), (np.median(d) if d else 0)

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
S = {(mo, e): serie(mo, d, f) for mo in (True, False) for e, d, f in FEN}

for r13, titre in ((False, "SANS fermeture a +10 % (etat actuel des robots)"),
                   (True,  "AVEC fermeture a +10 % (R13)")):
    print(); print("=== %s ===" % titre)
    print("%-38s | %-26s | %s" % ("", "10 ANS", "2021-2026"))
    print("%-38s | %7s %8s %7s | %7s %8s"
          % ("configuration", "CAGR", "reussite", "duree", "CAGR", "reussite"))
    print("-" * 92)
    for mode_on in (True, False):
        for turbo, nt in ((None, "sans turbo"), ((1.33, 0.04), "TURBO x1,33 jusqu'a +4 %")):
            mult, cou = (1.0, None) if turbo is None else turbo
            etq = "mode challenge %s | %s" % ("ON " if mode_on else "OFF", nt)
            l = "%-38s |" % etq
            for k, (e, _, _) in enumerate(FEN):
                cagr, dd, tj, tjr = S[(mode_on, e)]
                o, m = ftmo(tj, tjr, mult, cou, r13)
                if k == 0: l += " %+6.1f %% %6.0f %% %4.0f j |" % (cagr, o, m)
                else:      l += " %+6.1f %% %6.0f %% %4.0f j" % (cagr, o, m)
            print(l)
