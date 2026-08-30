# -*- coding: utf-8 -*-
"""Chargeur du moteur avec, en plus de regle_siege.charger3, le levier A4 :
UN SEUL ROBOT DE L'ECURIE PAR SYMBOLE.

BTC Cassure et BTC EMA tradent tous deux BTCUSD. Le plafond de 2 piles compte
des SIEGES, pas des sous-jacents : les deux peuvent donc etre longs BTC en
meme temps, ce qui double l'exposition sur le seul marche qui porte deja
75 % du rendement et 9 des 10 pires journees.
"""
import io
import os
import sys

import regle_siege as RS

SYMB = {"BTC Cassure": "BTC", "BTC EMA": "BTC",
        "Or": "XAU", "Nasdaq": "NQ", "Petrole": "CL"}

# on greffe le test A4 juste apres le test de heat, dans le meme bloc d'entree
A_ENTREE_NEW = RS.N_ENTREE
N_ENTREE_A4 = RS.N_ENTREE + """
            if UN_PAR_SYMBOLE and any(
                    o.pos is not None and o.nom != s.nom
                    and SYMB.get(o.nom) == SYMB.get(s.nom) for o in sl):
                continue"""


def charger4(garde=0.025, cap=2, libere=False, heatmax=9.9, mode="total",
             invisibles=(), cap_mi=True, un_par_symbole=False):
    if not un_par_symbole:
        return RS.charger3(garde, cap, libere, heatmax, mode, invisibles, cap_mi)

    # meme construction que charger3, avec l'ancre d'entree enrichie
    src = io.open(os.path.join(RS.BT, "tests_comite_B.py"),
                  encoding="utf-8").read().split("# ============ 5.")[0]
    rem = [(RS.A_OUVERTS, RS.N_OUVERTS),
           (RS.A_ENTREE, N_ENTREE_A4),
           (RS.A_INCR, RS.N_INCR)]
    if abs(garde - 0.025) > 1e-9:
        rem.append((RS.A_GARDE, "sl = sleeves_l4(); garde = -%.5f" % garde))
    if not cap_mi:
        rem.append((RS.A_CORR, "if False: continue   # plafond de correlation MORT"))
    bloc = ""
    for a, b in rem:
        bloc += ("src2 = src.replace(%r, %r)\n"
                 "assert src2 != src, 'ANCRE INTROUVABLE %s'\nsrc = src2\n"
                 % (a, b, a.strip()[:28]))
    src = src.replace("src = src.replace('if t >= pd.Timestamp(\"2015-08-21\")]',",
                      bloc + "src = src.replace('if t >= pd.Timestamp(\"2015-08-21\")]',")
    ns0 = {"__file__": os.path.join(RS.BT, "tests_comite_B.py")}
    s = sys.stdout
    sys.stdout = io.StringIO()
    exec(src, ns0)
    sys.stdout = s
    ns0["ns"]["CAPPOS"] = cap
    ns0["ns"]["LIBERE"] = libere
    ns0["ns"]["HEATMAX"] = heatmax
    ns0["ns"]["MODE_HEAT"] = mode
    ns0["ns"]["INVISIBLES"] = set(invisibles)
    ns0["ns"]["UN_PAR_SYMBOLE"] = True
    ns0["ns"]["SYMB"] = SYMB
    return ns0
