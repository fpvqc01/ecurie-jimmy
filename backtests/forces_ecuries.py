# -*- coding: utf-8 -*-
"""Contribution par manche de chaque ecurie (moteur realiste, 10 ans)."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "duel_final_l43.py"), encoding="utf-8").read()
src = src.split("ECURIES =")[0]
ns = {"__file__": os.path.join(D, "duel_final_l43.py")}
exec(src, ns)
I = ns["ns"]   # espace interne de duel_final (sim10, ADAPT...)

capture = {}
def adapt_capture(cadences):
    base = ns["adapt_fab"](cadences)
    def a(sl):
        out = base(sl)
        capture["sl"] = out
        return out
    return a

REEL, C2 = ns["REEL"], ns["C2"]
for nom, gen, pyrmax, filtre, cad in (
        ("I2+", "I2+", 3, False, REEL), ("L3", "L3", 3, False, REEL),
        ("L3+", "L3+", 3, False, REEL), ("L4.2 ON", "L4", 4, True, REEL),
        ("L4.3 ON", "L4", 4, True, C2)):
    I["PYRMAX"], I["FILTRE_OR"], I["ADAPT"] = pyrmax, filtre, adapt_capture(cad)
    I["DEBUT"], I["FIN"] = "2015-08-21", "2026-12-31"
    r = I["sim10"](gen)
    print("== %-8s (CAGR %+.1f%%) :" % (nom, r["cagr"]))
    for s in capture["sl"]:
        print("     %-12s : %+7.1f %% cumule | %3d trades" % (s.nom, sum(s.pnl.values())*100, s.trades))
