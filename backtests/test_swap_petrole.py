# -*- coding: utf-8 -*-
"""Point B de l'expert forex : le swap 'bonus' du petrole peut s'inverser
en contango. Test : swap +0,005 %/j (actuel) vs 0 vs -0,03 %/j (contango
severe type 2020). Donnees propres, L4+ mode ON, 10 ans."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "tests_comite_B.py"), encoding="utf-8").read().split("# ============ 5.")[0]
ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
exec(src, ns0)
run, fab_l431, ns = ns0["run"], ns0["fab_l431"], ns0["ns"]

def fab_swap(swap_pet):
    base = fab_l431()
    def f():
        sl = base()
        for s in sl:
            if s.nom == "Petrole": s.swap = swap_pet
        return sl
    return f

for nom, sw in (("swap actuel (+1,9 %/an bonus)", +0.000051),
                ("swap neutre (0)", 0.0),
                ("contango severe (-0,03 %/jour)", -0.0003)):
    ns["DEBUT"], ns["FIN"] = "2015-08-21", "2026-12-31"
    ns["sleeves_l4"] = fab_swap(sw)
    r = ns["sim_h4"](interdit=None)
    print("  %-32s : CAGR %+5.1f%% | reussite %3.0f%% | DD %+6.1f%%" % (nom, r[0], 100-r[3], r[2]))
