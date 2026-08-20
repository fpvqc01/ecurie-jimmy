# -*- coding: utf-8 -*-
"""TOUS LES BACKTESTS DE LA SEMAINE EN GRAPHIQUE 1D -- meme batterie que le
banc H4 (tests_semaine_h4.py), meme format, moteur journalier.
Deux fenetres : 5 ANS (Yahoo) et 2 ANS (fenetre commune avec le banc H4).
Limite honnete : 'vendredi apres 12h' est impossible en 1d -> on teste la
borne max (tout le vendredi), comme dans les tests originaux."""
import pandas as pd
from moteur_1d import sim, TOUS, JOURS_US

def ligne(nom, r):
    return ("  %-42s | %+6.1f%% | %6.2f | %+6.1f%% | %6d | %5d | %4.0f%% | %+5.1f/%+5.1f%%"
            % (nom, r["cagr"], r["sharpe"], r["dd"], r["trades"], r["coupes"],
               r["morts"], r["m1"], r["m2"]))
ENTETE = ("  %-42s | %-7s | %-6s | %-7s | %-6s | %-5s | %-5s | %s"
          % ("Variante", "CAGR", "Sharpe", "MaxDD", "Trades", "Coupes", "Morts", "Moities"))

GENS = ("I2+", "L3", "I2++", "L3+")
DEB2 = "2024-08-21"

def f_ferie(t): return t.date() in TOUS
def f_us_ferme(t): return t.date() not in JOURS_US
def f_ferie_semaine(t): return t.weekday() < 5 and t.date() in TOUS
def f_ven(t): return t.weekday() == 4
def f_jeu(t): return t.weekday() == 3
def a_ven(t): return t.weekday() == 4      # aplatir a la cloture du vendredi

for titre, deb in (("5 ANS", None), ("2 ANS (fenetre commune H4)", DEB2)):
    print("#" * 100)
    print("# 1. DUEL DES 4 GENERATIONS EN 1D -- %s" % titre)
    print("#" * 100)
    print(ENTETE); print("  " + "-" * 100)
    for g in GENS:
        print(ligne(g, sim(g, debut=deb)))
    print()

print("#" * 100)
print("# 2. FERIES US -- pas de nouvelle entree les feries (1d, 5 ans)")
print("#" * 100)
for g in GENS:
    a = sim(g); b = sim(g, bloque=f_ferie)
    print("  %-5s : ref %+6.1f%%  |  sans feries %+6.1f%%  (delta %+.1f pt)"
          % (g, a["cagr"], b["cagr"], b["cagr"] - a["cagr"]))
print()

print("#" * 100)
print("# 3. MARCHE US FERME (week-ends + feries, verite terrain, 1d, 5 ans)")
print("#" * 100)
for g in GENS:
    a = sim(g); b = sim(g, bloque=f_us_ferme)
    print("  %-5s : ref %+6.1f%%  |  entrees bloquees marche ferme %+6.1f%%  (delta %+.1f pt)"
          % (g, a["cagr"], b["cagr"], b["cagr"] - a["cagr"]))
print()

print("#" * 100)
print("# 4. SANS BTC, feries US en semaine, positions conservees (1d, 5 ans)")
print("#" * 100)
for g in GENS:
    a = sim(g, avec_btc=False); b = sim(g, avec_btc=False, bloque=f_ferie_semaine)
    print("  %-5s : ref sans BTC %+6.1f%%  |  filtre feries %+6.1f%%  (delta %+.1f pt)"
          % (g, a["cagr"], b["cagr"], b["cagr"] - a["cagr"]))
print()

print("#" * 100)
print("# 5. VENDREDI (1d, 5 ans) -- borne max : tout le vendredi (pas de 12h en 1d)")
print("#" * 100)
for g in GENS:
    print("  === %s ===" % g)
    print(ligne("A. reference", sim(g)))
    print(ligne("C. pas d'entree de tout le vendredi", sim(g, bloque=f_ven)))
    print(ligne("D. voisin temoin : pas d'entree le jeudi", sim(g, bloque=f_jeu)))
    print(ligne("E. aplatir a la cloture du vendredi", sim(g, aplatit=a_ven)))
    print()

print("#" * 100)
print("# 6. BTC SEUL, 8 ANS 1D (Binance resample 1d, 2018-2026)")
print("#" * 100)
for g in ("I2+", "L3"):
    print("  === %s (BTC cassure + BTC EMA seulement) ===" % g)
    print(ligne("A. reference 8 ans", sim(g, btc_seul=True, debut="2018-01-01")))
    print(ligne("C. pas d'entree la fin de semaine", sim(g, btc_seul=True, debut="2018-01-01",
                                                         bloque=lambda t: t.weekday() >= 5)))
    print()

print("#" * 100)
print("# 7. COHERENCE -- entrees vendredi / fin de semaine (1d, 5 ans)")
print("#" * 100)
for g in GENS:
    e = sim(g, trace=True)
    ven = [x for x in e if x[0].weekday() == 4]
    print("  %-5s : %d entrees vendredi sur %d" % (g, len(ven), len(e)))
e = sim("L3", btc_seul=True, debut="2018-01-01", trace=True)
we = [x for x in e if x[0].weekday() >= 5]
print("  BTC 8 ans 1d (L3) : %d entrees, %d la fin de semaine" % (len(e), len(we)))
