# -*- coding: utf-8 -*-
"""L4 REDUIT A 2 MARCHES : OR + NASDAQ/US100 (question de Jimmy, 20 aout).
Contexte : OANDA Canada n'offre pas de CFD crypto ; or et US100 y sont.
Reutilise les constructeurs de combo_l4.py (config L4 : or 2,0 / nas 1,5,
pyramide s.o. -- les 2 manches sont des replis fib, pas de pyramidage).
Variantes :
  - AVEC protections (gardien 2,5 % + mode challenge 0,75) = L4 tel quel
  - SANS protections (compte perso)
  - AVEC protections mais SANS plafond de correlation : dans L4, or et
    nasdaq sont la meme famille "metal/indice", donc JAMAIS ouverts en
    meme temps -- avec 2 marches seulement, ce plafond ampute beaucoup.
Moteurs 1d 5 ans et H4 2 ans + rendement par annee + exemple 5 000 $."""
import pandas as pd, numpy as np

src = open("combo_l4.py", encoding="utf-8").read().split("MARCHES = (")[0]
src = src.replace("garde = -0.025", "garde = GARDE")
src = src.replace("fc = 0.75 if", "fc = THR if")
src = src.replace('if FAM[s.nom] == "mi" and "mi" in familles: continue',
                  'if CORR and FAM[s.nom] == "mi" and "mi" in familles: continue')
src = src.replace('if MH.FAM[s.nom] == "mi" and "mi" in familles: continue',
                  'if CORR and MH.FAM[s.nom] == "mi" and "mi" in familles: continue')
src = src.replace("return metriques(tj.clip(lower=garde))",
                  "return metriques(tj.clip(lower=garde)) + (tj.clip(lower=garde),)")
src = src.replace("return metriques(tj)", "return metriques(tj) + (tj,)")
ns = {"__file__": "combo_l4.py", "GARDE": -0.025, "THR": 0.75, "CORR": True}
exec(src, ns)

COMBO = ("Or", "Nasdaq")
VARIANTES = [("AVEC protections (= L4)",      -0.025, 0.75, True),
             ("SANS protections",             -0.99,  1.0,  True),
             ("AVEC prot., SANS plafond corr", -0.025, 0.75, False)]

def maxdd(tj):
    eq = (1 + tj).cumprod()
    return ((eq / eq.cummax()) - 1).min() * 100

res = {}
for nom, garde, thr, corr in VARIANTES:
    ns["GARDE"], ns["THR"], ns["CORR"] = garde, thr, corr
    res[nom] = (ns["sim_1d"](COMBO), ns["sim_h4"](COMBO))
    print("... %s fait" % nom)

print()
print("=== L4 OR + NASDAQ (US100) SEULEMENT ===")
print("%-31s | %-22s | %-22s" % ("Variante", "1d 5 ans", "H4 2 ans"))
print("%-31s | %-6s %-7s %-6s | %-6s %-7s %-6s" % ("", "CAGR", "MaxDD", "Morts", "CAGR", "MaxDD", "Morts"))
print("-" * 90)
for nom, *_ in VARIANTES:
    (c1, m1, a1, b1, t1), (c2, m2, a2, b2, t2) = res[nom]
    print("%-31s | %+5.1f%% %+6.1f%% %4.0f%%  | %+5.1f%% %+6.1f%% %4.0f%%"
          % (nom, c1, maxdd(t1), m1, c2, maxdd(t2), m2))
print()
print("Reference L4 COMPLET (5 manches)  | +22.4%  -11.9%    6%  | +27.3%  -13.2%    7%")

print()
print("=== RENDEMENT PAR ANNEE (moteur 1d) ===")
print("  %-6s | %-13s | %-13s | %s" % ("Annee", "AVEC prot.", "SANS prot.", "SANS plafond"))
print("  " + "-" * 54)
t_avec = res["AVEC protections (= L4)"][0][4]
t_sans = res["SANS protections"][0][4]
t_nocorr = res["AVEC prot., SANS plafond corr"][0][4]
for an in sorted({d.year for d in t_avec.index}):
    va = ((1 + t_avec[t_avec.index.year == an]).prod() - 1) * 100
    vs = ((1 + t_sans[t_sans.index.year == an]).prod() - 1) * 100
    vn = ((1 + t_nocorr[t_nocorr.index.year == an]).prod() - 1) * 100
    print("  %-6d | %+10.1f%%  | %+10.1f%%  | %+10.1f%%" % (an, va, vs, vn))
print("  (2021 = 4 mois, 2026 = 8 mois)")

print()
print("=== SANS PROTECTIONS : journees a risque (1d, 5 ans) ===")
print("  pire jour %+.1f%% | jours <-2,5%% : %d | jours <-5%% : %d"
      % (t_sans.min() * 100, (t_sans < -0.025).sum(), (t_sans < -0.05).sum()))

print()
print("=== EXEMPLE : 5 000 $ DE DEPART (moteur 1d) ===")
for nom, *_ in VARIANTES:
    t = res[nom][0][4]
    eq = 5000.0; ligne = []
    for an in sorted({d.year for d in t.index}):
        eq *= (1 + t[t.index.year == an]).prod()
        ligne.append("%d: %5.0f $" % (an, eq))
    print("%-31s : %s" % (nom, " | ".join(ligne)))
