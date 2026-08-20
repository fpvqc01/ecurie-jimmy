# -*- coding: utf-8 -*-
"""BACKTEST L4 (or 2,0 / nas 1,5 / pet-btc 1,5, plafond correlation, pyr 3,
gardien 2,5 %) : AVEC mode challenge (throttle 0,75) vs SANS.
Rendement annuel + taux de challenges echoues, moteurs 1d (5 ans) et H4 (2 ans)."""
import pandas as pd, numpy as np

# --- moteur 1d parametrique (du scan) ---
src = open("scan_strategies.py", encoding="utf-8").read().split("resultats = []")[0]
ns1 = {"__file__": "scan_strategies.py"}; exec(src, ns1)
ns1["RISQUES"]["L4"] = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)

# --- moteur H4 parametrique ---
src = open("valide_candidats_h4.py", encoding="utf-8").read().split('print("=== VALIDATION')[0]
ns2 = {"__file__": "valide_candidats_h4.py"}; exec(src, ns2)
ns2["RISQUES"]["L4"] = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)

print("=== L4 : RESUME (les 2 moteurs) ===")
print("%-28s | %-16s | %-16s" % ("Config", "1d 5 ans", "H4 2 ans"))
print("%-28s | %-7s %-8s | %-7s %-8s" % ("", "CAGR", "Echecs", "CAGR", "Echecs"))
print("-" * 78)
res = {}
for nom, thr in (("L4 AVEC mode challenge", 0.75), ("L4 SANS mode challenge", None)):
    r1 = ns1["sim_p"](True, "L4", 3, thr, False, serie_out=True)
    r2 = ns2["sim_p"]("L4", corr=True, throttle=thr)
    res[nom] = (r1, r2)
    print("%-28s | %+6.1f%% %6.0f%%  | %+6.1f%% %6.0f%%"
          % (nom, r1["cagr"], r1["morts"], r2[0], r2[3]))
print()
print("=== L4 : RENDEMENT PAR ANNEE (moteur 1d) ===")
s_avec = res["L4 AVEC mode challenge"][0]["serie"]
s_sans = res["L4 SANS mode challenge"][0]["serie"]
print("  %-6s | %-12s | %s" % ("Annee", "AVEC mode ch.", "SANS mode ch."))
print("  " + "-" * 42)
for an in sorted({d.year for d in s_avec.index}):
    va = ((1 + s_avec[s_avec.index.year == an]).prod() - 1) * 100
    vs = ((1 + s_sans[s_sans.index.year == an]).prod() - 1) * 100
    print("  %-6d | %+10.1f%%  | %+10.1f%%" % (an, va, vs))
print("  (2021 = 4 mois, 2026 = 8 mois)")
print()
print("=== references pour situer ===")
for nom, (c1, m1, c2, m2) in (("L3 (ton MT4)", (31.1, 16, 14.9, 38)),
                               ("L3+ (or 1,5)", (21.6, 6, 23.6, 4)),
                               ("I2+ (ton MT5)", (17.7, 14, 15.8, 22))):
    print("  %-14s : 1d %+5.1f%% / %2.0f%% echecs | H4 %+5.1f%% / %2.0f%% echecs" % (nom, c1, m1, c2, m2))
