# -*- coding: utf-8 -*-
"""COMPLEMENT au test sans protections : sans le gardien quotidien, combien
de JOURNEES auraient viole la limite de perte quotidienne FTMO (-5 %) ?
Le taux de "morts" du test principal ne simule que la limite TOTALE (-8 %) ;
la limite quotidienne est une 2e facon d'echouer, que seul le gardien coupe.
Moteur 1d, 5 ans, les 5 generations SANS gardien ni mode challenge."""
import pandas as pd, numpy as np

src = open("scan_strategies.py", encoding="utf-8").read().split("resultats = []")[0]
ns1 = {"__file__": "scan_strategies.py"}; exec(src, ns1)
ns1["RISQUES"]["L4"] = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)

GENS = [("I2+",  False, "R0", 1), ("I2++", True, "R0", 3), ("L3", False, "R0", 3),
        ("L3+",  True,  "R1", 3), ("L4",   True, "L4", 3)]

print("=== SANS PROTECTIONS : journees sous les seuils FTMO (1d, 5 ans) ===")
print("%-5s | %-9s | %-12s | %-12s" % ("Gen", "Pire jour", "Jours <-2,5%", "Jours <-5%"))
print("-" * 50)
for nom, corr, rset, pyr in GENS:
    r = ns1["sim_p"](corr, rset, pyr, None, False, garde=-0.99, serie_out=True)
    s = r["serie"]
    print("%-5s | %+7.1f%%  | %10d   | %10d" % (nom, s.min()*100, (s < -0.025).sum(), (s < -0.05).sum()))
print()
print("Rappel : chez FTMO, UNE seule journee sous -5 %% = challenge echoue,")
print("meme si le compte est en profit. C'est le gardien qui empeche ca.")
