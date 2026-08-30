# -*- coding: utf-8 -*-
"""VALIDATION HORS ECHANTILLON de la selection OANDA : on refait la
selection (elimination des moins profitables) en n'utilisant QUE
2021-2023, puis on evalue le portefeuille retenu sur 2024-2026 (jamais vu).
Compare : selection 2021-2023, noyau seul, selection pleine periode
(test_oanda_univers.py, biaisee par construction), et les 23 manches."""
import pandas as pd, numpy as np

src = open("test_oanda_univers.py", encoding="utf-8").read().split("NOYAU =")[0]
src = src.replace("def sim(actifs):", "def sim(actifs, debut=None, fin=None):")
src = src.replace("    dates = sorted(set().union(*[set(s.df.index) for s in sl]))\n",
                  "    dates = sorted(set().union(*[set(s.df.index) for s in sl]))\n"
                  "    if debut: dates = [x for x in dates if x >= pd.Timestamp(debut)]\n"
                  "    if fin: dates = [x for x in dates if x <= pd.Timestamp(fin)]\n")
ns = {"__file__": "test_oanda_univers.py"}; exec(src, ns)
sim, DATA = ns["sim"], ns["DATA"]

NOYAU = ["Or", "Petrole", "Nasdaq"]
TOUT = NOYAU + [n for n in DATA]
FIN_SEL, DEBUT_VAL = "2023-12-31", "2024-01-01"

print("=== SELECTION SUR 2021-2023 SEULEMENT ===")
(c, d, m), contrib = sim(TOUT, fin=FIN_SEL)
print("Ronde 1 (23 manches, 2021-2023) : CAGR %+5.1f%% -- eliminations :" % c)
garder = [n for n in TOUT if contrib.get(n, (0, 0))[0] > 0]
print("  contributions negatives sorties : %s"
      % ", ".join(n for n in TOUT if n not in garder))
(c, d, m), contrib = sim(garder, fin=FIN_SEL)
sel = [n for n in garder if contrib.get(n, (0, 0))[0] >= 1.0]
print("Ronde 2 (%d manches) : CAGR %+5.1f%% -- on garde >= +1 pt : %s"
      % (len(garder), c, ", ".join(sel)))

print()
print("=== EVALUATION SUR 2024-2026 (JAMAIS VU PAR LA SELECTION) ===")
FINAL_INSAMPLE = ["Or", "Petrole", "EUR_USD", "USD_JPY", "AUD_JPY", "BCO_USD", "NATGAS", "JP225"]
for nom, actifs in (("Selection 2021-2023 (honnete)", sel),
                    ("Noyau or+pet+nas", NOYAU),
                    ("Selection pleine periode (biaisee)", FINAL_INSAMPLE),
                    ("Les 23 manches", TOUT)):
    (c, d, m), _ = sim(actifs, debut=DEBUT_VAL)
    print("  %-36s (%2d manches) : CAGR %+5.1f%% | MaxDD %+5.1f%% | Morts %2.0f%%"
          % (nom, len(actifs), c, d, m))

print()
print("=== PORTEFEUILLE FINAL 8 MANCHES : PAR ANNEE (pleine periode) ===")
(c, d, m), contrib = sim(FINAL_INSAMPLE)
sl_dates = None
# rendement par annee : on refait la serie via sim en fenetres annuelles
for an in range(2021, 2027):
    (ca, dd_, mo), _ = sim(FINAL_INSAMPLE, debut="%d-01-01" % an, fin="%d-12-31" % an)
    # ca est annualise ; pour une fenetre partielle c'est approximatif
    print("  %d : %+6.1f%% (annualise)" % (an, ca))
print("  Pleine periode : CAGR %+5.1f%% | MaxDD %+5.1f%% | Morts %2.0f%%" % (c, d, m))
