# -*- coding: utf-8 -*-
"""L4 avec PLUS de risque sur l'or : echelle complete 1,5 -> 3,0 %.
Config fixe = L4 (corr, nas 1,5, pet/btc 1,5, pyramide 3, gardien 2,5 %,
mode challenge 0,75). Les 2 moteurs."""
import pandas as pd, numpy as np
src = open("valide_l3plus_v2.py", encoding="utf-8").read()
ns = {"__file__": "valide_l3plus_v2.py"}
exec(src.split("VARIANTES =")[0], ns)
sim1d, simh4 = ns["sim1d"], ns["simh4"]

print("Echelle du risque OR (config L4, mode challenge actif)")
print("%-12s | %-22s | %-22s | %-8s %s" % ("Or %", "1d 5 ans", "H4 2 ans", "MOYEN", "PIRE"))
print("%-12s | %-6s %-6s %-7s | %-6s %-6s %-7s |" % ("", "CAGR", "MaxDD", "Morts", "CAGR", "MaxDD", "Morts"))
print("-" * 92)
for o in (0.015, 0.020, 0.0225, 0.025, 0.0275, 0.030):
    r1 = sim1d(o, 0.015, 0.015, 0.015, True, 0.75)
    r2 = simh4(o, 0.015, 0.015, 0.015, True, 0.75)
    marq = "  <-- L4 actuel" if abs(o-0.020) < 1e-9 else ""
    print("or %.2f %%    | %+5.1f%% %+6.1f%% %5.0f%%  | %+5.1f%% %+6.1f%% %5.0f%%  | %+6.1f%% %4.0f%%%s"
          % (o*100, r1["cagr"], r1["dd"], r1["morts"], r2[0], r2[2], r2[3],
             (r1["cagr"]+r2[0])/2, max(r1["morts"], r2[3]), marq))
