# -*- coding: utf-8 -*-
"""LES 5 GENERATIONS SANS LES PROTECTIONS FTMO (demande de Jimmy, 20 aout).
On coupe les 2 coupe-circuits concus pour FTMO :
  - le GARDIEN QUOTIDIEN (-2,5 %, -3,5 % pour I2+) : jamais declenche
  - le MODE CHALLENGE (throttle x0,75 en drawdown) : desactive
On GARDE la strategie propre a chaque generation (pyramidage, plafond de
correlation, jeu de risques) -- c'est le robot, pas une protection FTMO.
I2+ est approxime dans le moteur parametrique par pyramide max = 1.
Moteurs : 1d 5 ans (Yahoo) et H4 2 ans (fenetre commune).
Morts = %% de challenges FTMO simules (fenetres glissantes) qui touchent
-8 %% avant +10 %%."""
import pandas as pd, numpy as np

SANS_GARDE = -0.99   # seuil jamais atteint = gardien coupe

# --- moteur 1d parametrique (celui du scan de 96 configs) ---
src = open("scan_strategies.py", encoding="utf-8").read().split("resultats = []")[0]
ns1 = {"__file__": "scan_strategies.py"}; exec(src, ns1)
ns1["RISQUES"]["L4"] = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)

# --- moteur H4 parametrique, gardien rendu parametrable ---
src = open("valide_candidats_h4.py", encoding="utf-8").read().split('print("=== VALIDATION')[0]
assert "garde = -0.025" in src
src = src.replace("garde = -0.025", "garde = GARDE")
ns2 = {"__file__": "valide_candidats_h4.py", "GARDE": -0.025}; exec(src, ns2)
ns2["RISQUES"]["R0"] = dict(ns2["RISQUES"]["L3"])
ns2["RISQUES"]["R1"] = dict(ns2["RISQUES"]["C1"])
ns2["RISQUES"]["L4"] = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)

#        nom     corr   risques pyr  throttle  gardien nominal
GENS = [("I2+",  False, "R0",   1,   None,     -0.035),
        ("I2++", True,  "R0",   3,   None,     -0.025),
        ("L3",   False, "R0",   3,   None,     -0.025),
        ("L3+",  True,  "R1",   3,   0.75,     -0.025),
        ("L4",   True,  "L4",   3,   0.75,     -0.025)]

res = {}
for nom, corr, rset, pyr, thr, garde in GENS:
    a1 = ns1["sim_p"](corr, rset, pyr, thr, False, garde=garde)
    s1 = ns1["sim_p"](corr, rset, pyr, None, False, garde=SANS_GARDE)
    ns2["GARDE"] = garde
    a2 = ns2["sim_p"](rset, corr=corr, throttle=thr, pyr_max=pyr)
    ns2["GARDE"] = SANS_GARDE
    s2 = ns2["sim_p"](rset, corr=corr, throttle=None, pyr_max=pyr)
    res[nom] = (a1, s1, a2, s2)
    print("... %s fait" % nom)

print()
print("=== MOTEUR 1d, 5 ANS ===")
print("%-5s | %-24s | %-24s" % ("Gen", "AVEC protections", "SANS protections"))
print("%-5s | %-7s %-7s %-6s | %-7s %-7s %-6s" % ("", "CAGR", "MaxDD", "Morts", "CAGR", "MaxDD", "Morts"))
print("-" * 62)
for nom, _, _, _, _, _ in GENS:
    a, s = res[nom][0], res[nom][1]
    print("%-5s | %+6.1f%% %+6.1f%% %4.0f%%  | %+6.1f%% %+6.1f%% %4.0f%%"
          % (nom, a["cagr"], a["dd"], a["morts"], s["cagr"], s["dd"], s["morts"]))

print()
print("=== MOTEUR H4, 2 ANS (fenetre commune) ===")
print("%-5s | %-24s | %-24s" % ("Gen", "AVEC protections", "SANS protections"))
print("%-5s | %-7s %-7s %-6s | %-7s %-7s %-6s" % ("", "CAGR", "MaxDD", "Morts", "CAGR", "MaxDD", "Morts"))
print("-" * 62)
for nom, _, _, _, _, _ in GENS:
    a, s = res[nom][2], res[nom][3]
    print("%-5s | %+6.1f%% %+6.1f%% %4.0f%%  | %+6.1f%% %+6.1f%% %4.0f%%"
          % (nom, a[0], a[2], a[3], s[0], s[2], s[3]))

print()
print("Rappel : AVEC = gardien quotidien + mode challenge (L3+/L4) actifs,")
print("SANS = aucun coupe-circuit ; strategie et sizing identiques par ailleurs.")
