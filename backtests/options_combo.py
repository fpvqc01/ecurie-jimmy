# -*- coding: utf-8 -*-
"""Combo des 2 options quasi gratuites : C (petrole sans ajout vendredi)
+ F (EMA D1 decision 08:00). Contre reference, 2 fenetres, mode ON."""
import os
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "options_optimisation.py"), encoding="utf-8").read()
src = src.split("OPTIONS = [")[0]
ns0 = {"__file__": os.path.join(D, "options_optimisation.py")}
exec(src, ns0)
ns, fab_option, f_or = ns0["ns"], ns0["fab_option"], ns0["f_or"]
pas_ajout_vendredi, ema_8h = ns0["pas_ajout_vendredi"], ns0["ema_8h"]

def combo(sl):
    for s in sl:
        if s.nom == "Petrole": pas_ajout_vendredi(s)
        if s.nom == "BTC EMA": ema_8h(s)

for etiquette, per in (("10 ANS ", ("2015-08-21", "2026-12-31")),
                       ("2021-26", ("2021-01-01", "2026-08-20"))):
    for nom, post in (("reference L4+", lambda sl: None), ("combo C+F    ", combo)):
        ns["DEBUT"], ns["FIN"] = per
        ns["sleeves_l4"] = fab_option(post)
        r = ns["sim_h4"](interdit=f_or)
        print("%s %s : %+5.1f %% | reussite %3.0f %% | DD %+6.1f %% | Sharpe %.2f"
              % (etiquette, nom, r[0], 100 - r[3], r[2], r[1]))
    print()
