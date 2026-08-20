# -*- coding: utf-8 -*-
"""AVANT/APRES le correctif FibLo/FibHi (20 aout, soir), donnees propres :
AVANT (bogue)   = or et Nasdaq ne peuvent jamais entrer -> ecurie 3/5
MAINTENANT      = config L4+ complete (celle qui a toujours ete backtestee)
Mode challenge ON, 10 ans + 2021-2026."""
import os
D = os.path.dirname(os.path.abspath(__file__))

src = open(os.path.join(D, "tests_comite_B.py"), encoding="utf-8").read()
src = src.split("# ============ 5.")[0]
ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
exec(src, ns0)
ns, fab, f_or = ns0["ns"], ns0["fab_l431"], ns0["f_or"]

def mesure(debut, fin, muets):
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = fab()
    interdit = (lambda n, j: n in ("Or", "Nasdaq") or f_or(n, j)) if muets else f_or
    return ns["sim_h4"](interdit=interdit)

for etiquette, per in (("10 ANS  ", ("2015-08-21", "2026-12-31")),
                       ("2021-26 ", ("2021-01-01", "2026-08-20"))):
    for nom, muets in (("AVANT (bogue, or+Nasdaq muets, 3/5)", True),
                       ("MAINTENANT (corrige, 5/5)         ", False)):
        r = mesure(per[0], per[1], muets)
        print("%s %s : CAGR %+5.1f %% | reussite %3.0f %% | DD %+6.1f %% | Sharpe %.2f"
              % (etiquette, nom, r[0], 100 - r[3], r[2], r[1]))
    print()
