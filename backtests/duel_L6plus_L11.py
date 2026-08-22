# -*- coding: utf-8 -*-
"""DUEL L6+ contre L11 (demande Jimmy, 21 aout).

La duree mediane ne dit pas tout : quand un challenge echoue, on perd AUSSI
le temps passe dedans avant de mourir, plus les frais. On calcule donc le
TEMPS ESPERE JUSQU'AU COMPTE FINANCE, tentatives ratees comprises :

   jours esperes = duree_moyenne_d_un_echec x (1/p - 1) + duree_d_une_reussite
   frais esperes = prix du challenge / p

L6+ est mesure TEL QU'IL TOURNE (sans fermeture a +10 %) et aussi avec, pour
que Jimmy voie les deux."""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B
from sim_ferme import instrumenter

BASE = dict(B.ALLOC)
def alloc_btc(r):
    a = dict(BASE); lib = a["BTC Cassure"] - r; a["BTC Cassure"] = r
    a["Or"] += lib/2; a["Nasdaq"] += lib/2; return a

def serie(garde, be, alloc, deb, fin):
    ns0 = B.charger(garde)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite = []
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in alloc: s.risque = alloc[s.nom]
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

def bilan(tj, tjr, mult, cou, r13, prix=439):
    vm, vr = tj.values, tjr.values
    ok = 0; d_ok = []; d_ko = []
    for i0 in range(0, len(vm)-60, 3):
        v1, d1 = phase(vm, vr, i0, 0.10, mult, cou, r13)
        if v1 == -1: continue
        if v1 == 0: d_ko.append(d1); continue
        v2, d2 = phase(vm, vr, i0+d1, 0.05, mult, cou, r13)
        if v2 == -1: continue
        if v2 == 0: d_ko.append(d1+d2); continue
        ok += 1; d_ok.append(d1+d2)
    n = ok + len(d_ko)
    p = ok/max(n,1)
    med = np.median(d_ok) if d_ok else 0
    moy_ko = np.mean(d_ko) if d_ko else 0
    jours = moy_ko*(1/p - 1) + med if p > 0 else float("inf")
    return dict(p=100*p, med=med, moy_ko=moy_ko, jours=jours,
                tent=1/p if p else 0, frais=prix/p if p else 0)

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
S6  = {e: serie(0.025,  None, BASE,               d, f) for e, d, f in FEN}   # chassis L6+
S11 = {e: serie(0.025,  0.05, alloc_btc(0.0115),  d, f) for e, d, f in FEN}   # chassis L11

CAS = (("L6+  tel qu'il tourne aujourd'hui", S6,  1.33, 0.04, False),
       ("L6+  si on lui ajoutait R13",       S6,  1.33, 0.04, True),
       ("L11",                               S11, 1.00, None, True))

for e, _, _ in FEN:
    print()
    print("=== %s ===" % e.strip())
    print("%-34s | %7s %6s %7s | %8s %9s %8s"
          % ("", "reuss.", "duree", "duree", "tentatives", "JOURS", "FRAIS"))
    print("%-34s | %7s %6s %7s | %8s %9s %8s"
          % ("robot", "", "gagne", "perdu", "moyennes", "ESPERES", "ESPERES"))
    print("-" * 88)
    for nom, S, mult, cou, r13 in CAS:
        cagr, dd, tj, tjr = S[e]
        b = bilan(tj, tjr, mult, cou, r13)
        print("%-34s | %6.0f %% %5.0f j %6.0f j | %7.2f x %7.0f j %7.0f EUR"
              % (nom, b["p"], b["med"], b["moy_ko"], b["tent"], b["jours"], b["frais"]))
    cagr6, dd6 = S6[e][0], S6[e][1]
    cagr11, dd11 = S11[e][0], S11[e][1]
    print("   rendement annuel : L6+ %+.1f %%  L11 %+.1f %%   |   pire creux : L6+ %+.1f %%  L11 %+.1f %%"
          % (cagr6, cagr11, dd6, dd11))
print()
print("(frais : 439 EUR, le prix promo FTMO d'un compte 100 k)")
