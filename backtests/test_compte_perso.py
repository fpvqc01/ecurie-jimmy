# -*- coding: utf-8 -*-
"""COMPTE PERSO (question de Jimmy, 20 aout) : les 5 generations roulees sur
un compte personnel type OANDA -- AUCUNE regle FTMO, aucun challenge a
echouer, seul risque = le capital. Deux variantes par generation :
  - SANS protections (gardien et mode challenge coupes)
  - AVEC le gardien du robot (utile meme en perso : il coupe les tres
    mauvaises journees), mode challenge coupe (inutile hors challenge)
Moteur 1d, 5 ans. Rendement par annee civile + exemple en dollars (5 000 $)."""
import pandas as pd, numpy as np

src = open("scan_strategies.py", encoding="utf-8").read().split("resultats = []")[0]
ns1 = {"__file__": "scan_strategies.py"}; exec(src, ns1)
ns1["RISQUES"]["L4"] = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)

GENS = [("I2+",  False, "R0", 1, -0.035), ("I2++", True, "R0", 3, -0.025),
        ("L3",   False, "R0", 3, -0.025), ("L3+",  True, "R1", 3, -0.025),
        ("L4",   True,  "L4", 3, -0.025)]

series_sans, series_avec = {}, {}
for nom, corr, rset, pyr, garde in GENS:
    series_sans[nom] = ns1["sim_p"](corr, rset, pyr, None, False, garde=-0.99, serie_out=True)
    series_avec[nom] = ns1["sim_p"](corr, rset, pyr, None, False, garde=garde, serie_out=True)
    print("... %s fait" % nom)

def par_annee(serie):
    return {an: ((1 + serie[serie.index.year == an]).prod() - 1) * 100
            for an in sorted({d.year for d in serie.index})}

annees = sorted({d.year for d in series_sans["L4"]["serie"].index})
print()
print("=== COMPTE PERSO SANS PROTECTIONS : RENDEMENT PAR ANNEE (1d) ===")
print("  %-6s | %s" % ("Annee", " | ".join("%-8s" % n for n, *_ in GENS)))
print("  " + "-" * 62)
tab = {n: par_annee(series_sans[n]["serie"]) for n, *_ in GENS}
for an in annees:
    print("  %-6d | %s" % (an, " | ".join("%+7.1f%%" % tab[n].get(an, 0) for n, *_ in GENS)))
print("  " + "-" * 62)
print("  %-6s | %s" % ("CAGR", " | ".join("%+7.1f%%" % series_sans[n]["cagr"] for n, *_ in GENS)))
print("  %-6s | %s" % ("MaxDD", " | ".join("%+7.1f%%" % series_sans[n]["dd"] for n, *_ in GENS)))
print("  (2021 = 4 mois, 2026 = 8 mois)")

print()
print("=== EXEMPLE EN DOLLARS : 5 000 $ DE DEPART ===")
for nom in ("L3+", "L4"):
    for etiquette, series in (("sans protections", series_sans), ("avec le gardien", series_avec)):
        s = series[nom]["serie"]; dd = series[nom]["dd"]
        eq = 5000.0; ligne = []
        for an in annees:
            eq *= (1 + s[s.index.year == an]).prod()
            ligne.append("fin %d : %5.0f $" % (an, eq))
        creux = 5000.0 * (1 + (1 + s).cumprod().div((1 + s).cumprod().cummax()).min() - 1)
        print("%-4s %-16s : %s" % (nom, etiquette, " | ".join(ligne)))
        print("     pire creux depuis un sommet : %.1f%% (ex. %5.0f $ -> %5.0f $)"
              % (dd, 5000.0, 5000.0 * (1 + dd / 100)))
print()
print("Rappel : backtest 2021-2026, frais/swap du moteur, pas les spreads OANDA ;")
print("le passe ne garantit rien. Le pire creux peut arriver DES LE DEPART.")
