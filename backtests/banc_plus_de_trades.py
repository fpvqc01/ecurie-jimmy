# -*- coding: utf-8 -*-
"""PLUS DE COUPS, PAS PLUS DE RISQUE (objectif 90 jours, 21 aout).

Constat : sur 90 jours l'ecurie n'ouvre que 7 positions. Faire +15,5 % avec
7 tirages demande 2-3 trades enormes. Augmenter la MISE a ete teste dix fois
et detruit la reussite. La seule autre voie est d'augmenter le NOMBRE DE COUPS.

On raccourcit le CANAL D'ENTREE (le plus-haut 20 jours qui declenche la
cassure) a 15, 10 et 7 jours. Plus il est court, plus le robot entre souvent.
Attention : c'est l'entree, PAS la sortie - le canal de sortie 7 jours a deja
ete teste et rejete (69 % de reussite sur 2021-2026).

On mesure le nombre de trades, la reussite, la duree mediane, et surtout la
part des departs REUSSIS en moins de 90 jours."""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B

BASE = dict(B.ALLOC)
def alloc_btc(r):
    a = dict(BASE); lib = a["BTC Cassure"] - r; a["BTC Cassure"] = r
    a["Or"] += lib/2; a["Nasdaq"] += lib/2; return a

def canal_entree(s, jours):
    """raccourcit le plus-haut glissant qui declenche l'entree"""
    s.H20J = pd.Series(s.DJH).rolling(jours).max().values
    return s

def mesure(alloc, jours, deb, fin):
    ns0 = B.charger(0.0175)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite = []
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in alloc: s.risque = alloc[s.nom]
        for s in sl:
            if s.nom in B.PYR: B.breakeven(s, 0.05)
        if jours:
            for s in sl:
                if hasattr(s, "DJH"): canal_entree(s, jours)
        boite[:] = sl
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()
    v = tj.values; ok = mort = 0; d = []
    for i0 in range(0, len(v)-60, 3):
        e = 1.0; jt = 0; d1 = None
        for j in range(i0, len(v)):
            x = v[j]
            if x != 0.0: jt += 1
            if x <= -0.05: break
            e *= (1+x)
            if e <= 0.90: break
            if e >= 1.10 and jt >= 4: d1 = j-i0+1; break
        if d1 is None:
            if j >= len(v)-1: continue
            mort += 1; continue
        e = 1.0; jt = 0; d2 = None
        for j in range(i0+d1, len(v)):
            x = v[j]
            if x != 0.0: jt += 1
            if x <= -0.05: break
            e *= (1+x)
            if e <= 0.90: break
            if e >= 1.05 and jt >= 4: d2 = j-(i0+d1)+1; break
        if d2 is None:
            if j >= len(v)-1: continue
            mort += 1; continue
        ok += 1; d.append(d1+d2)
    n = ok+mort
    d = np.array(d) if d else np.array([0])
    trades = sum(s.trades for s in boite)
    return trades, 100.0*ok/max(n,1), np.median(d), 100.0*(d<90).sum()/max(n,1), r[0], r[2]

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
AL = alloc_btc(0.0115)     # chassis L8+

print("=== CANAL D'ENTREE RACCOURCI (chassis L8+, plus de coups a mise egale) ===")
print("%-24s | %-40s | %s" % ("", "10 ANS", "2021-2026"))
print("%-24s | %6s %7s %7s %5s %7s | %7s %5s %7s"
      % ("canal d'entree", "trades", "CAGR", "reuss.", "med", "<90j", "reuss.", "med", "<90j"))
print("-" * 104)
for jours, etq in ((None, "20 jours (actuel)"), (15, "15 jours"), (10, "10 jours"), (7, "7 jours")):
    l = "%-24s |" % etq
    for k, (e, d0, f0) in enumerate(FEN):
        tr, o, m, s90, cagr, dd = mesure(AL, jours, d0, f0)
        if k == 0: l += " %6d %+6.1f %% %6.0f %% %4.0f %6.0f %% |" % (tr, cagr, o, m, s90)
        else:      l += " %6.0f %% %4.0f %6.0f %%" % (o, m, s90)
    print(l)
