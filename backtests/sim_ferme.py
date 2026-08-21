# -*- coding: utf-8 -*-
"""VERIFICATION DU SIMULATEUR FTMO (point souleve par le comite, 21 aout).

FTMO exige que l'objectif (+10 % puis +5 %) soit atteint POSITIONS FERMEES.
Mon moteur credite le profit FLOTTANT chaque barre (moteur_h4.py ligne 141),
donc le simulateur declarait la phase reussie sur de l'equite flottante.

Ici on separe les deux :
  - equite MARQUEE AU MARCHE  -> regles de PERTE (-5 %/jour, -10 % total).
    C'est correct : FTMO compte bien le flottant pour les pertes.
  - solde FERME (realise)     -> regle d'OBJECTIF (+10 %, +5 %).

Methode : on instrumente chaque manche. Tout ce qui est credite au P&L
entre l'ouverture et la fermeture d'une position appartient a ce trade ;
la somme est portee au jour de la FERMETURE. Exact meme avec pyramide."""
import os, sys, io, numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B

ALLOC, PYR = B.ALLOC, B.PYR

def instrumenter(s):
    """separe le P&L realise du P&L marque au marche"""
    s.pnl_r = {}
    s._cum0 = 0.0
    ouvrir0, clore0 = s.ouvrir, s._clore
    tot = lambda: sum(s.pnl.values())
    def ouvrir(t, *a, **k):
        avant = tot()
        r = ouvrir0(t, *a, **k)
        if s.pos is not None: s._cum0 = avant
        return r
    def _clore(t, prix):
        clore0(t, prix)
        s.pnl_r[t] = s.pnl_r.get(t, 0.0) + (tot() - s._cum0)
    s.ouvrir, s._clore = ouvrir, _clore
    return s

def series(ns0, garde_be, debut, fin):
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite = []
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in ALLOC: s.risque = ALLOC[s.nom]
        if garde_be:
            for s in sl:
                if s.nom in PYR: B.breakeven(s, garde_be)
        for s in sl: instrumenter(s)
        boite[:] = sl
        return sl
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()                       # marque au marche (existant)
    tot = {}
    for s in boite:
        for tt, vv in s.pnl_r.items():
            jj = tt.date(); tot[jj] = tot.get(jj, 0) + vv
    tjr = pd.Series([tot.get(j.date(), 0.0) for j in tj.index], index=tj.index)
    return r[0], r[2], tj, tjr

# ---------- simulateur FTMO : pertes au flottant, objectif au ferme ----------
def phase2(vm, vr, i0, cible):
    eq = 1.0; bal = 1.0; jt = 0
    for j in range(i0, len(vm)):
        rm, rr = vm[j], vr[j]
        if rm != 0.0: jt += 1
        if rm <= -0.05: return 0, j - i0 + 1          # -5 % sur la journee
        eq  *= (1 + rm)
        bal *= (1 + rr)
        if eq <= 0.90: return 0, j - i0 + 1           # -10 % total
        if bal >= 1 + cible and jt >= 4: return 1, j - i0 + 1   # objectif FERME
    return -1, len(vm) - i0

def ftmo2(tj, tjr):
    vm, vr = tj.values, tjr.values
    ok = mort = 0; d = []
    for i0 in range(0, len(vm) - 60, 3):
        v1, d1 = phase2(vm, vr, i0, 0.10)
        if v1 == -1: continue
        if v1 == 0: mort += 1; continue
        v2, d2 = phase2(vm, vr, i0 + d1, 0.05)
        if v2 == -1: continue
        if v2 == 0: mort += 1; continue
        ok += 1; d.append(d1 + d2)
    n = ok + mort
    return 100.0 * ok / max(n, 1), (np.median(d) if d else 0)

if __name__ == "__main__":
    FEN = (("10 ANS ", "2015-08-21", "2026-12-31"),
           ("2021-26", "2021-01-01", "2026-08-20"))
    ns0 = B.charger(0.0175)
    print("=== L8 : ANCIEN simulateur (objectif au FLOTTANT) vs NOUVEAU (au FERME) ===")
    print("%-10s | %8s | %-22s | %-22s" % ("fenetre", "CAGR", "ANCIEN (flottant)", "NOUVEAU (ferme)"))
    print("%-10s | %8s | %9s %11s | %9s %11s" % ("", "", "reussite", "duree", "reussite", "duree"))
    print("-" * 76)
    for nom, deb, f in FEN:
        cagr, dd, tj, tjr = series(ns0, 0.05, deb, f)
        o1, m1 = B.ftmo(tj)
        o2, m2 = ftmo2(tj, tjr)
        print("%-10s | %+7.1f %% | %8.0f %% %8.0f j | %8.0f %% %8.0f j"
              % (nom, cagr, o1, m1, o2, m2))
        ecart = abs(tj.sum() - tjr.sum())
        print("           (controle : somme flottant %.4f vs ferme %.4f, ecart %.4f)"
              % (tj.sum(), tjr.sum(), ecart))
