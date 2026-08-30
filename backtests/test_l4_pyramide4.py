# -*- coding: utf-8 -*-
"""L4 : pyramide 4 unites vs 3 (les 2 moteurs)."""
import pandas as pd, numpy as np
src = open("scan_strategies.py", encoding="utf-8").read().split("resultats = []")[0]
ns1 = {"__file__": "scan_strategies.py"}; exec(src, ns1)
ns1["RISQUES"]["L4"] = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)
src = open("valide_candidats_h4.py", encoding="utf-8").read().split('print("=== VALIDATION')[0]
ns2 = {"__file__": "valide_candidats_h4.py"}; exec(src, ns2)
ns2["RISQUES"]["L4"] = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)
print("%-24s | %-16s | %-16s" % ("Config", "1d 5 ans", "H4 2 ans"))
print("%-24s | %-7s %-7s | %-7s %-7s" % ("", "CAGR", "Morts", "CAGR", "Morts"))
for nom, pyr in (("L4 pyramide 3 (actuel)", 3), ("L4 pyramide 4", 4), ("L4 pyramide 5", 5)):
    r1 = ns1["sim_p"](True, "L4", pyr, 0.75, False)
    r2 = ns2["sim_p"]("L4", corr=True, throttle=0.75, pyr_max=pyr)
    print("%-24s | %+6.1f%% %5.0f%%  | %+6.1f%% %5.0f%%" % (nom, r1["cagr"], r1["morts"], r2[0], r2[3]))
