# -*- coding: utf-8 -*-
"""Contre-verification de l'allocation « a x 0,75 » du comite no 3 :
Or 0,75 % / Nasdaq 0,75 % / Petrole 1,69 % / BTC Cassure 1,69 % /
BTC EMA 1,13 % (annonce : +2,9 pts 10 ans, +1,1 pt 21-26, DD egal)."""
import os
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "options_optimisation.py"), encoding="utf-8").read()
src = src.split("OPTIONS = [")[0]
ns0 = {"__file__": os.path.join(D, "options_optimisation.py")}
exec(src, ns0)
ns, fab_option, f_or = ns0["ns"], ns0["fab_option"], ns0["f_or"]

ALLOC = {"Or": 0.0075, "Nasdaq": 0.0075, "Petrole": 0.0169,
         "BTC Cassure": 0.0169, "BTC EMA": 0.0113}
def a075(sl):
    for s in sl:
        if s.nom in ALLOC: s.risque = ALLOC[s.nom]

for etiquette, per in (("10 ANS ", ("2015-08-21", "2026-12-31")),
                       ("2021-26", ("2021-01-01", "2026-08-20"))):
    for nom, post in (("reference L5 ", lambda sl: None), ("alloc a x0,75", a075)):
        ns["DEBUT"], ns["FIN"] = per
        ns["sleeves_l4"] = fab_option(post)
        r = ns["sim_h4"](interdit=f_or)
        print("%s %s : %+5.1f %% | reussite %3.0f %% | DD %+6.1f %% | Sharpe %.2f"
              % (etiquette, nom, r[0], 100 - r[3], r[2], r[1]))
    print()
