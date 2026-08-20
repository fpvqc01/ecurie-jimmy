# -*- coding: utf-8 -*-
"""TOUS LES BACKTESTS DE LA SEMAINE, REFAITS EN H4 (21 aout 2026).
Fenetres : ecurie complete = 2 ans (limite Yahoo intrajournalier) ;
BTC seul = 8 ans H4 (Binance 2017-2026).
12h Montreal = 16h UTC (EDT). Barres H4 UTC : 0,4,8,12,16,20."""
import pandas as pd, numpy as np
from datetime import timedelta
from moteur_h4 import (sim as _sim, ligne, ENTETE, FERIES, GC, NQ, CL, BTC)
def sim(*a, **k):
    k.setdefault('debut', '2024-08-21')   # fenetre commune : sans ca, l'union
    return _sim(*a, **k)                  # des index melangeait 9 ans de BTC

GENS = ("I2+", "L3", "I2++", "L3+")
JOURS_US = set(NQ.index.date)

# ---- moteur JOURNALIER restreint a la meme fenetre de 2 ans (validation) ----
import os
_d0 = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_d0, "test_vendredi.py"), encoding="utf-8").read().split("NOMS =")[0]
_src = _src.replace("dates = sorted(set().union(*[s.df.index for s in sleeves]))",
                    "dates = [d for d in sorted(set().union(*[s.df.index for s in sleeves]))"
                    " if d >= pd.Timestamp('2024-08-21')]")
_ns = {"__file__": os.path.join(_d0, "test_vendredi.py")}
exec(_src, _ns)
sim_jour = _ns["sim"]

def f_ferie(t):            # ferie US (nouvelles entrees bloquees)
    return t.date() in FERIES
def f_us_ferme(t):         # marche US ferme (week-end + feries), verite terrain
    return t.date() not in JOURS_US
def f_ferie_semaine(t):    # ferie US en semaine seulement
    return t.weekday() < 5 and t.date() in FERIES
def f_ven(t):              # tout le vendredi
    return t.weekday() == 4
def f_ven_apres12(t):      # vendredi apres 12h Montreal (16h UTC) -- LA regle exacte
    return t.weekday() == 4 and t.hour >= 16
def f_jeu(t):              # voisin temoin
    return t.weekday() == 3
def a_ven_soir(t):         # aplatir a la derniere barre du vendredi (20h UTC)
    return t.weekday() == 4 and t.hour == 20

print("#" * 100)
print("# 0. VALIDATION -- moteur JOURNALIER, meme fenetre 2 ans (2024-08-21 ->)")
print("#" * 100)
for g in GENS:
    r = sim_jour(g, "A")
    print("  %-5s (journalier 2 ans) : CAGR %+6.1f%% | Sharpe %5.2f | DD %+6.1f%% | %d trades"
          % (g, r[0], r[1], r[2], r[3]))
print()

print("#" * 100)
print("# 1. DUEL DES 4 GENERATIONS EN H4 -- ecurie complete, 2 ans")
print("#" * 100)
print(ENTETE); print("  " + "-" * 100)
for g in GENS:
    print(ligne(g, sim(g)))
print()

print("#" * 100)
print("# 2. FERIES US -- pas de nouvelle entree les feries (4 generations)")
print("#" * 100)
for g in GENS:
    a = sim(g); b = sim(g, bloque=f_ferie)
    print("  %-5s : ref %+6.1f%%  |  sans feries %+6.1f%%  (delta %+.1f pt)"
          % (g, a["cagr"], b["cagr"], b["cagr"] - a["cagr"]))
print()

print("#" * 100)
print("# 3. MARCHE US FERME (week-ends + feries, verite terrain)")
print("#" * 100)
for g in GENS:
    a = sim(g); b = sim(g, bloque=f_us_ferme)
    print("  %-5s : ref %+6.1f%%  |  entrees bloquees marche ferme %+6.1f%%  (delta %+.1f pt)"
          % (g, a["cagr"], b["cagr"], b["cagr"] - a["cagr"]))
print()

print("#" * 100)
print("# 4. SANS BTC, feries US en semaine, positions conservees")
print("#" * 100)
for g in GENS:
    a = sim(g, avec_btc=False); b = sim(g, avec_btc=False, bloque=f_ferie_semaine)
    print("  %-5s : ref sans BTC %+6.1f%%  |  filtre feries %+6.1f%%  (delta %+.1f pt)"
          % (g, a["cagr"], b["cagr"], b["cagr"] - a["cagr"]))
print()

print("#" * 100)
print("# 5. VENDREDI -- enfin le VRAI test 'apres 12h' (12h Montreal = 16h UTC)")
print("#" * 100)
for g in GENS:
    print("  === %s ===" % g)
    print(ligne("A. reference", sim(g)))
    print(ligne("B. pas d'entree vendredi apres 12h", sim(g, bloque=f_ven_apres12)))
    print(ligne("C. pas d'entree de tout le vendredi", sim(g, bloque=f_ven)))
    print(ligne("D. voisin temoin : pas d'entree le jeudi", sim(g, bloque=f_jeu)))
    print(ligne("E. aplatir tout le vendredi 20h", sim(g, aplatit=a_ven_soir)))
    print()

print("#" * 100)
print("# 6. BTC SEUL, 8 ANS H4 (Binance 2017-2026) -- pyramidage + vendredi")
print("#" * 100)
for g in ("I2+", "L3"):
    print("  === %s (BTC cassure + BTC EMA seulement) ===" % g)
    print(ligne("A. reference 8 ans", sim(g, btc_seul=True, debut="2018-01-01")))
    print(ligne("B. pas d'entree vendredi apres 12h", sim(g, btc_seul=True, debut="2018-01-01", bloque=f_ven_apres12)))
    print(ligne("C. pas d'entree la fin de semaine", sim(g, btc_seul=True, debut="2018-01-01",
                                                         bloque=lambda t: t.weekday() >= 5)))
    print()

print("#" * 100)
print("# 7. CONTROLE DE COHERENCE -- entrees vendredi apres 12h dans la reference")
print("#" * 100)
for g in GENS:
    e = sim(g, trace=True)
    v12 = [(t, n) for t, n in e if f_ven_apres12(t)]
    print("  %-5s : %d entrees sur %d apres vendredi 12h" % (g, len(v12), len(e)))
e = sim("L3", btc_seul=True, debut="2018-01-01", trace=True)
v12 = [(t, n) for t, n in e if f_ven_apres12(t)]
we = [(t, n) for t, n in e if t.weekday() >= 5]
print("  BTC 8 ans (L3) : %d entrees, %d le vendredi apres 12h, %d la fin de semaine"
      % (len(e), len(v12), len(we)))
