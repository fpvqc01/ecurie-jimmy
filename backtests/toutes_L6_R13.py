# -*- coding: utf-8 -*-
"""TOUTES LES VERSIONS L6 AVEC LA FERMETURE A +10 % DU COMPTE (demande Jimmy).

Regle 1 « seulement des achats » : DEJA en place. Verifie dans le code, il
n'existe aucun ordre de vente dans aucun robot (7 trade.Buy, 0 trade.Sell) et
le moteur de backtest calcule (prix courant - prix d'entree), donc long.
Rien a changer, rien a tester : c'est deja le cas.

Regle 2 « fermeture de toutes les positions a +10 % de profit du compte » :
c'est R13. On la mesure ici sur les SIX versions L6 existantes dans MT6 :
  Jimmy L6, L6+, L6++  et leurs trois variantes « sans challenge »
soit 3 mecanismes x 2 modes.

SANS R13 : l'objectif ne compte que le profit REELLEMENT encaisse (regle FTMO
           exacte, c'est l'etat actuel des robots).
AVEC R13 : le robot ferme tout des que le compte touche +10 %."""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_ecuries_L6_modes as BM
import banc_L8 as B
from sim_ferme import instrumenter

def serie(mode_on, be, deb, fin):
    ns0 = BM.charger(mode_on)
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
S = {}
for mo in (True, False):
    for be in (None, 0.05):
        for e, d, f in FEN:
            S[(mo, be, e)] = serie(mo, be, d, f)

# (nom du dossier MT6, mode challenge, breakeven, multiplicateur, coussin turbo)
VERSIONS = [
    ("Jimmy L6",                    True,  None, 1.00, None),
    ("Jimmy L6+",                   True,  None, 1.33, 0.04),
    ("Jimmy L6++",                  True,  0.05, 1.00, None),
    ("Jimmy L6 sans challenge",     False, None, 1.00, None),
    ("Jimmy L6+ sans challenge",    False, None, 1.33, 0.04),
    ("Jimmy L6++ sans challenge",   False, 0.05, 1.00, None),
]

for r13, titre in ((False, "SANS fermeture a +10 % — l'etat actuel de tes robots"),
                   (True,  "AVEC fermeture a +10 % du compte")):
    print(); print("=== %s ===" % titre)
    print("%-28s | %-26s | %s" % ("", "10 ANS", "2021-2026"))
    print("%-28s | %7s %8s %6s | %7s %8s %6s"
          % ("version", "CAGR", "reussite", "duree", "CAGR", "reussite", "duree"))
    print("-" * 84)
    for nom, mo, be, mult, cou in VERSIONS:
        l = "%-28s |" % nom
        for e, _, _ in FEN:
            cagr, dd, tj, tjr = S[(mo, be, e)]
            o, m = ftmo(tj, tjr, mult, cou, r13)
            l += " %+6.1f %% %6.0f %% %4.0f j |" % (cagr, o, m)
        print(l)
