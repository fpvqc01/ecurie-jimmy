# -*- coding: utf-8 -*-
"""DUEL HONNETE L6 / L6+ / L6++ / L8 — donnees REPAREES, meme simulateur.

Jimmy conteste : « L6+ a de meilleurs resultats, l'optimisation n'a rien
apporte ? » Ses chiffres L6+ (78 %/109 j) venaient des donnees corrompues.
On remesure tout le monde cote a cote, avec DEUX lectures :

  A. TEL QUEL : chaque ecurie comme elle existe aujourd'hui. L6/L6+/L6++
     n'ont PAS la fermeture a l'objectif (R13) -> objectif juge sur le solde
     FERME. L8 l'a -> objectif juge a l'equite de cloture.
  B. A ARMES EGALES : tout le monde avec R13. Isole le changement de
     strategie du gain apporte par la fonction."""
import os, sys, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B
from sim_ferme import instrumenter
import pandas as pd

ALLOC, PYR = B.ALLOC, B.PYR

def series(ns0, be, debut, fin):
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite = []
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in ALLOC: s.risque = ALLOC[s.nom]
        if be:
            for s in sl:
                if s.nom in PYR: B.breakeven(s, be)
        for s in sl: instrumenter(s)
        boite[:] = sl
        return sl
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()
    tot = {}
    for s in boite:
        for tt, vv in s.pnl_r.items():
            jj = tt.date(); tot[jj] = tot.get(jj, 0) + vv
    tjr = pd.Series([tot.get(j.date(), 0.0) for j in tj.index], index=tj.index)
    return r[0], r[2], tj, tjr

def phase(vm, vr, i0, cible, mult, turbo, r13):
    """r13=True : le robot ferme tout a l'objectif -> l'equite vaut le solde.
       r13=False : l'objectif ne compte que le profit REELLEMENT encaisse."""
    eq = 1.0; bal = 1.0; jt = 0
    for j in range(i0, len(vm)):
        m = 1.0 if (turbo and eq >= 1 + turbo) else mult
        rm, rr = vm[j] * m, vr[j] * m
        if rm != 0.0: jt += 1
        if rm <= -0.05: return 0, j - i0 + 1
        eq *= (1 + rm); bal *= (1 + rr)
        if eq <= 0.90: return 0, j - i0 + 1
        atteint = eq if r13 else bal
        if atteint >= 1 + cible and jt >= 4: return 1, j - i0 + 1
    return -1, len(vm) - i0

def ftmo(tj, tjr, mult=1.0, turbo=None, r13=True):
    vm, vr = tj.values, tjr.values
    ok = mort = 0; d = []
    for i0 in range(0, len(vm) - 60, 3):
        v1, d1 = phase(vm, vr, i0, 0.10, mult, turbo, r13)
        if v1 == -1: continue
        if v1 == 0: mort += 1; continue
        v2, d2 = phase(vm, vr, i0 + d1, 0.05, mult, turbo, r13)
        if v2 == -1: continue
        if v2 == 0: mort += 1; continue
        ok += 1; d.append(d1 + d2)
    n = ok + mort
    return 100.0 * ok / max(n, 1), (np.median(d) if d else 0)

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"),
       ("2021-26", "2021-01-01", "2026-08-20"))

# ecurie -> (gardien, breakeven, multiplicateur, turbo)
ECURIES = [
    ("L6  (base)",             0.025,  None, 1.00, None),
    ("L6+ (turbo-coussin)",    0.025,  None, 1.33, 0.04),
    ("L6++ (breakeven 5 %)",   0.025,  0.05, 1.00, None),
    ("L8  (gardien 1,75 + BE)", 0.0175, 0.05, 1.00, None),
]

cache = {}
def get(garde, be, deb, fin):
    k = (garde, be, deb)
    if k not in cache:
        cache[k] = series(B.charger(garde), be, deb, fin)
    return cache[k]

for titre, r13_pour_tous in (("A. TEL QUEL (seule L8 ferme a l'objectif)", False),
                             ("B. A ARMES EGALES (tout le monde ferme a l'objectif)", True)):
    print()
    print("=== %s ===" % titre)
    print("%-24s | %-32s | %s" % ("", "10 ANS", "2021-2026"))
    print("%-24s | %8s %8s %6s %7s | %8s %8s %6s %7s"
          % ("ecurie", "CAGR", "reussite", "duree", "DD", "CAGR", "reussite", "duree", "DD"))
    print("-" * 108)
    for nom, garde, be, mult, turbo in ECURIES:
        r13 = True if r13_pour_tous else nom.startswith("L8")
        ligne = "%-24s |" % nom
        for etq, deb, fin in FEN:
            cagr, dd, tj, tjr = get(garde, be, deb, fin)
            o, m = ftmo(tj, tjr, mult, turbo, r13)
            ligne += " %+7.1f %% %6.0f %% %4.0f j %+6.1f %% |" % (cagr, o, m, dd)
        print(ligne)
