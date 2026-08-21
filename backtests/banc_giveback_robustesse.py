# -*- coding: utf-8 -*-
"""ROBUSTESSE du gagnant du banc give-back : le breakeven collectif.
Un seul bon chiffre ne prouve rien (souvenir de l'option A rejetee pour
« pic isole »). On verifie : (1) le PLATEAU des seuils voisins 5/6/7/9 %
sur 10 ans ; (2) la tenue sur 2021-2026 ; (3) le meme test pour le canal
7 jours (le plus rapide du banc) pour voir s'il tient sur la periode
recente."""
import os, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "banc_giveback.py"), encoding="utf-8").read()
src = src.split("VARIANTES = [")[0]
ns0 = {"__file__": os.path.join(D, "banc_giveback.py")}
exec(src, ns0)
ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab"]
breakeven_collectif, canal_court, PYR = ns0["breakeven_collectif"], ns0["canal_court"], ns0["PYR"]
ftmo = ns0["ftmo"]

def mesure(post, debut, fin):
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = fab(post)
    r = ns["sim_h4"](interdit=f_or)
    ok, med = ftmo(r[6].sort_index())
    return r[0], ok, med, r[2]

PERIODES = (("10 ans ", "2015-08-21", "2026-12-31"),
            ("2021-26", "2021-01-01", "2026-08-20"))

print("=== PLATEAU DU BREAKEVEN COLLECTIF (seuil de declenchement) ===")
print("%-28s | %-32s | %s" % ("", "10 ANS", "2021-2026"))
print("%-28s | %8s %8s %7s | %8s %8s %7s" % ("seuil", "CAGR", "reussite", "duree", "CAGR", "reussite", "duree"))
print("-" * 92)
for etiquette, post in (
        ("reference (aucun)", None),
        ("breakeven des +5 %", lambda sl: [breakeven_collectif(s, 0.05) for s in sl if s.nom in PYR]),
        ("breakeven des +6 %", lambda sl: [breakeven_collectif(s, 0.06) for s in sl if s.nom in PYR]),
        ("breakeven des +7 %", lambda sl: [breakeven_collectif(s, 0.07) for s in sl if s.nom in PYR]),
        ("breakeven des +9 %", lambda sl: [breakeven_collectif(s, 0.09) for s in sl if s.nom in PYR]),
        ("canal de sortie 7 jours", lambda sl: [canal_court(s, 7) for s in sl if s.nom in PYR]),
):
    ligne = "%-28s |" % etiquette
    for _, d, f in PERIODES:
        cagr, ok, med, dd = mesure(post, d, f)
        ligne += " %+7.1f %% %6.0f %% %4.0f j |" % (cagr, ok, med)
    print(ligne)
