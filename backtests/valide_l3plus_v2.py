# -*- coding: utf-8 -*-
import pandas as pd, numpy as np

# ---- 1d ----
import importlib.util as U
spec = U.spec_from_file_location("scan1d", "scan_strategies.py")
# plutot : re-exec seulement les definitions (le scan complet est long)
src = open("scan_strategies.py", encoding="utf-8").read()
src_defs = src.split("resultats = []")[0]
ns1 = {"__file__": "scan_strategies.py"}
exec(src_defs, ns1)

# risques personnalises
def sim1d(orq, nasq, petq, btcq, corr, thr):
    ns1["RISQUES"]["X"] = dict(Or=orq, Nasdaq=nasq, Petrole=petq, BTC=btcq)
    return ns1["sim_p"](corr, "X", 3, thr, False)

# ---- H4 ----
src = open("valide_candidats_h4.py", encoding="utf-8").read()
src_defs = src.split('print("=== VALIDATION')[0]
ns2 = {"__file__": "valide_candidats_h4.py"}
exec(src_defs, ns2)

def simh4(orq, nasq, petq, btcq, corr, thr):
    ns2["RISQUES"]["X"] = dict(Or=orq, Nasdaq=nasq, Petrole=petq, BTC=btcq)
    return ns2["sim_p"]("X", corr=corr, throttle=thr)

VARIANTES = [
    ("L3+ actuel (or1,5 pet/btc1,5 thr0,75)", (0.015, 0.015, 0.015, 0.015, True, 0.75)),
    ("V1 or 2,0",                             (0.020, 0.015, 0.015, 0.015, True, 0.75)),
    ("V2 throttle 0,85",                      (0.015, 0.015, 0.015, 0.015, True, 0.85)),
    ("V3 or 2,0 + throttle 0,85",             (0.020, 0.015, 0.015, 0.015, True, 0.85)),
    ("V4 or 2,0 pet/btc 1,25",                (0.020, 0.015, 0.0125, 0.0125, True, 0.75)),
    ("V5 tout a 2,0 sauf nas 1,5",            (0.020, 0.015, 0.020, 0.020, True, 0.75)),
    ("V6 or 2,5",                             (0.025, 0.015, 0.015, 0.015, True, 0.75)),
]
print("%-40s | %-16s | %-16s" % ("Variante", "1d 5 ans", "H4 2 ans"))
print("%-40s | %-7s %-7s | %-7s %-7s" % ("", "CAGR", "Morts", "CAGR", "Morts"))
print("-" * 80)
for nom, (o, n, p, b, c, t) in VARIANTES:
    r1 = sim1d(o, n, p, b, c, t)
    r2 = simh4(o, n, p, b, c, t)
    print("%-40s | %+6.1f%% %5.0f%%  | %+6.1f%% %5.0f%%"
          % (nom, r1["cagr"], r1["morts"], r2[0], r2[3]))
