# -*- coding: utf-8 -*-
# ############################################################### #
# !! FICHIER OBSOLETE - CORRIGE LE 21 AOUT 2026                    #
#                                                                 #
# Son simulateur FTMO contient 3 defauts demontres par le comite : #
#   1. l objectif de phase est valide sur l EQUITE FLOTTANTE alors #
#      que FTMO exige le SOLDE FERME (biais tres optimiste :       #
#      quand l equite touche +10 %%, le solde n est qu a +0,1 a    #
#      +2,3 %%) ;                                                  #
#   2. les challenges non resolus sont JETES du denominateur       #
#      (`if v == -1: continue`) - ce sont les LENTS, et le tri est #
#      ASYMETRIQUE entre variantes (jusqu a 23 %% des departs) ;    #
#   3. les jours de trading comptent les jours ou le P&L bouge au  #
#      lieu des jours ou une position est OUVERTE.                 #
#                                                                 #
# NE PLUS UTILISER POUR PRODUIRE DES CHIFFRES.                     #
# Reference : backtests/SIMULATEUR_FTMO.py                         #
# Classement a jour : backtests/CLASSEMENT_DEFINITIF.py            #
# ############################################################### #

"""SIMULATEUR FTMO EXACT sur L6 (allocation a x0,75) vs L5 :
phase 1 : +10 % ; phase 2 : +5 % ; regles communes : -5 %/jour sur
l'equite de debut de jour, -10 % sous le capital initial de la phase,
minimum 4 jours de trading par phase. Departs glissants tous les 3
jours de bourse, 10 ans de donnees propres, mode challenge ON."""
import os, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "options_optimisation.py"), encoding="utf-8").read()
src = src.split("OPTIONS = [")[0]
ns0 = {"__file__": os.path.join(D, "options_optimisation.py")}
exec(src, ns0)
ns, fab_option, f_or = ns0["ns"], ns0["fab_option"], ns0["f_or"]

ALLOC = {"Or": 0.0075, "Nasdaq": 0.0075, "Petrole": 0.0169,
         "BTC Cassure": 0.0169, "BTC EMA": 0.0113}
def a075(sl):
    for s in sl:
        if s.nom in ALLOC: s.risque = ALLOC[s.nom]

def phase(vals, i0, cible):
    """retourne (verdict, jours utilises) ; verdict 1=reussi 0=mort -1=fin de donnees"""
    eq = 1.0; jours_trade = 0
    for j in range(i0, len(vals)):
        r = vals[j]
        if r != 0.0: jours_trade += 1
        if r <= -0.05: return 0, j - i0 + 1          # -5 % du debut de jour
        eq *= (1 + r)
        if eq <= 0.90: return 0, j - i0 + 1           # -10 % total
        if eq >= 1 + cible and jours_trade >= 4:
            return 1, j - i0 + 1
    return -1, len(vals) - i0

for nom, post in (("L5 (allocation actuelle av. bascule)", lambda sl: None),
                  ("L6 (allocation a x0,75)            ", a075)):
    ns["DEBUT"], ns["FIN"] = "2015-08-21", "2026-12-31"
    ns["sleeves_l4"] = fab_option(post)
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()
    vals = tj.values
    p1 = complets = morts1 = morts2 = tronques = 0
    durees = []
    for i0 in range(0, len(vals) - 60, 3):
        v1, d1 = phase(vals, i0, 0.10)
        if v1 == -1: tronques += 1; continue
        if v1 == 0: morts1 += 1; continue
        p1 += 1
        v2, d2 = phase(vals, i0 + d1, 0.05)
        if v2 == -1: tronques += 1; continue
        if v2 == 0: morts2 += 1; continue
        complets += 1; durees.append(d1 + d2)
    n1 = p1 + morts1                      # departs juges en phase 1
    n = complets + morts1 + morts2        # departs juges au complet
    print("%s : %d departs juges" % (nom, n))
    print("   phase 1 reussie : %.0f %% (%d/%d) | CHALLENGE COMPLET (2 phases) : %.0f %% (%d/%d)"
          % (100.0 * p1 / max(n1, 1), p1, n1, 100.0 * complets / max(n, 1), complets, n))
    print("   duree mediane du challenge complet : %.0f jours de bourse" % (np.median(durees) if durees else 0))
    print("   (CAGR %+.1f %% | reussite fenetres %.0f %% | DD %+.1f %%)" % (r[0], 100 - r[3], r[2]))
    print()
