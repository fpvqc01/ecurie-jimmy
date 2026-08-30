# -*- coding: utf-8 -*-
"""BANC R2 + RECHERCHE DE VITESSE — 22 aout 2026, simulateur v2.

Deux questions, un seul banc :

  1) VALIDER A4 (un seul robot de l'ecurie par symbole). C'est un correctif de
     RISQUE, mais il change le comportement : il faut le mesurer avant de le
     deployer, pas seulement le coder.

  2) CHERCHER LA VITESSE. Objectif de Jimmy : 60 jours. On mesure la frontiere
     reelle en balayant les seuls leviers qui n'ont pas ete rejetes :
     multiplicateur de risque, regle siege/risque, allocation deconcentree,
     et la sensibilite a la regle des 4 jours de trading.

Metrique de decision (validee par le comite) : DUREE MEDIANE a reussite
>= 85 %. On surveille en second : <=60j, esperance, creux.
"""
import io
import json
import os
import sys
import time

BT = r"C:\Users\jplou\Downloads\Ecurie_Jimmy_I2plus_partage\backtests"
sys.path.insert(0, BT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_o = sys.stdout
sys.stdout = io.StringIO()
import CLASSEMENT_DEFINITIF as CD          # noqa: E402
sys.stdout = _o
import SIM_FTMO_V2 as V2                   # noqa: E402
from serie_flottant import series_flot     # noqa: E402
from regle_a4 import charger4              # noqa: E402

EMP = CD.rediriger_vers_donnees()
DEB, FIN, PISTE = "2021-01-01", "2026-08-20", 730

FTMO2 = dict(cibles=(0.10, 0.05), perte_jour=0.05, perte_totale=0.10, jours_min=4)
FTMO2_J0 = dict(cibles=(0.10, 0.05), perte_jour=0.05, perte_totale=0.10, jours_min=0)
FLEX1 = dict(cibles=(0.10,), perte_jour=0.04, perte_totale=0.12, jours_min=0)

ALLOC_R1 = {"Or": 0.0075, "Nasdaq": 0.0075, "Petrole": 0.0169,
            "BTC Cassure": 0.0169, "BTC EMA": 0.0113}
ALLOC_DEC = {"Or": 0.0102, "Nasdaq": 0.0102, "Petrole": 0.0169,
             "BTC Cassure": 0.0115, "BTC EMA": 0.0113}


def mult(a, k):
    return {n: v * k for n, v in a.items()}


_CACHE = {}


def serie(alloc, k=1.0, cap=2, libere=False, heatmax=9.9, mode="total",
          a4=False):
    cle = (tuple(sorted(alloc.items())), k, cap, libere, heatmax, mode, a4)
    if cle in _CACHE:
        return _CACHE[cle]
    t0 = time.time()
    s = sys.stdout
    sys.stdout = io.StringIO()
    cagr, dd, tj, tjr, tjo, tjf = series_flot(
        charger4(0.025, cap, libere, heatmax, mode, (), True, a4),
        0.05, DEB, FIN, alloc=mult(alloc, k))
    sys.stdout = s
    r = (cagr, dd, tj.values.astype(float), tjo.values.astype(float),
         tjf.values.astype(float))
    _CACHE[cle] = r
    print("   . serie calculee en %4.0f s  (CAGR %+5.1f%%, creux %5.1f%%)"
          % (time.time() - t0, cagr, dd), file=sys.stderr)
    return r


CONFIGS = [
    # etiquette                                    alloc      k     cap lib heat  mode    a4
    ("R1 reference (telle que compilee)",          ALLOC_R1, 1.00,  2, False, 9.9, "total", False),
    ("R2 = R1 + A4 (un robot par symbole)",        ALLOC_R1, 1.00,  2, False, 9.9, "total", True),
    ("R1 + allocation deconcentree (L11)",         ALLOC_DEC, 1.00, 2, False, 9.9, "total", False),
    ("R2 deconcentree (alloc L11 + A4)",           ALLOC_DEC, 1.00, 2, False, 9.9, "total", True),
    ("R1 + regle siege/risque 2,5 %",              ALLOC_R1, 1.00, 99, True, 0.025, "capital", False),
    ("R1 risque x1,15",                            ALLOC_R1, 1.15,  2, False, 9.9, "total", False),
    ("R1 risque x1,33",                            ALLOC_R1, 1.33,  2, False, 9.9, "total", False),
    ("R1 risque x1,33 + regle siege 2,5 %",        ALLOC_R1, 1.33, 99, True, 0.025, "capital", False),
    ("R2 deconcentree x1,33",                      ALLOC_DEC, 1.33, 2, False, 9.9, "total", True),
    ("R2 deconcentree x1,33 + siege 3,0 %",        ALLOC_DEC, 1.33, 99, True, 0.030, "capital", True),
]

ENTETE = ("%-42s %6s %5s %5s %6s %6s %6s | %6s %7s"
          % ("configuration", "reuss", "med", "p10", "<=45j", "<=60j", "esp",
             "CAGR", "creux"))


def ligne(nom, s, prod):
    cagr, dd, vm, vo, vf = s
    r = V2.simuler(vm, vf, vo, piste_min=PISTE, r13=True, regle="ftmo",
                   gardien=0.010, **prod)
    print("%-42s %5.1f%% %4.0fj %4.0fj %5.1f%% %5.1f%% %5.0fj | %+5.1f%% %6.1f%%"
          % (nom, r["reussite"], r["duree_med"], r["duree_p10"], r["p45"],
             r["p60"], r["esperance"], cagr, dd))
    return dict(nom=nom, reussite=r["reussite"], med=r["duree_med"],
                p10=r["duree_p10"], p45=r["p45"], p60=r["p60"],
                esp=r["esperance"], cagr=cagr, dd=dd)


print(EMP)
print("Fenetre %s -> %s | simulateur v2 | departs a plat | R13 actif" % (DEB, FIN))

S = {}
for etq, al, k, cap, lib, hm, md, a4 in CONFIGS:
    print("Calcul : " + etq, file=sys.stderr)
    S[etq] = serie(al, k, cap, lib, hm, md, a4)

sortie = {}
for titre, prod in (("FTMO 2-Step (10 % + 5 %) — le produit Swing achetable", FTMO2),
                    ("FTMO 2-Step SANS la regle des 4 jours (sensibilite)", FTMO2_J0),
                    ("PRODUIT 1 PHASE (+10 %, mort -12 %) — autre firme", FLEX1)):
    print()
    print("=" * 118)
    print(titre)
    print("=" * 118)
    print(ENTETE)
    print("-" * 118)
    sortie[titre] = [ligne(etq, S[etq], prod) for etq, *_ in CONFIGS]

with open("resultats_banc_R2.json", "w", encoding="utf-8") as f:
    json.dump(sortie, f, indent=1, ensure_ascii=False)
print()
print("resultats_banc_R2.json ecrit")
