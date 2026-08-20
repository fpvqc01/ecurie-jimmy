# -*- coding: utf-8 -*-
"""Carte du voisinage : or x throttle, les deux moteurs. On cherche un
PLATEAU stable, pas un pic isole (standard de stabilite n.3)."""
import pandas as pd, numpy as np
src = open("valide_l3plus_v2.py", encoding="utf-8").read()
ns = {"__file__": "valide_l3plus_v2.py"}
exec(src.split("VARIANTES =")[0], ns)
sim1d, simh4 = ns["sim1d"], ns["simh4"]

ORS = (0.015, 0.0175, 0.020, 0.0225)
THRS = (0.75, 0.80, 0.85)
print("Grille or x throttle (corr oui, nas 1,5, pet/btc 1,5, pyr 3)")
print("%-22s | %-15s | %-15s" % ("Config", "1d 5 ans", "H4 2 ans"))
print("%-22s | %-6s %-7s | %-6s %-7s" % ("", "CAGR", "Morts", "CAGR", "Morts"))
print("-" * 70)
for o in ORS:
    for t in THRS:
        r1 = sim1d(o, 0.015, 0.015, 0.015, True, t)
        r2 = simh4(o, 0.015, 0.015, 0.015, True, t)
        marq = " <-- L3+ actuel" if (abs(o-0.015) < 1e-9 and t == 0.75) else ""
        print("or %.2f%%  thr %.2f     | %+5.1f%% %5.0f%%  | %+5.1f%% %5.0f%%%s"
              % (o*100, t, r1["cagr"], r1["morts"], r2[0], r2[3], marq))
