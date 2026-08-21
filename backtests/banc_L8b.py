# -*- coding: utf-8 -*-
"""BANC L8 partie B : PLAFOND DE NOTIONNEL (donnees reparees).
Le moteur plafonne deja a 2,0x l'equite par manche (moteur_h4.py:147).
L'expert levier recommande 0,8x sur BTC, 0,6x petrole, 1,25x portefeuille.
Ici on teste le plafond PAR MANCHE : 2,0 (actuel) / 1,25 / 1,0 / 0,8,
combine au meilleur gardien du banc A (-1,75 %) et au breakeven 5 %."""
import os, io, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = io.open(os.path.join(D, "banc_L8.py"), encoding="utf-8").read().split("FEN = (")[0]
ns0 = {"__file__": os.path.join(D, "banc_L8.py")}
exec(src, ns0)
charger, mesure, breakeven, ALLOC, PYR = (ns0["charger"], ns0["mesure"],
                                          ns0["breakeven"], ns0["ALLOC"], ns0["PYR"])
ftmo = ns0["ftmo"]

def plafonner(s, cap):
    """bride le notionnel de la manche : n <= cap x equite"""
    ouvrir0, gerer0 = s.ouvrir, s.gerer
    def ouvrir(t, **kw):
        ok = ouvrir0(t, **kw)
        if ok and s.pos is not None and s.pos["n"] > cap:
            s.pos["n"] = cap
            if "n0" in s.pos: s.pos["n0"] = min(s.pos["n0"], cap)
        return ok
    def gerer(t):
        gerer0(t)
        p = s.pos
        if p is not None and p["n"] > cap:
            s.pnl[t] = s.pnl.get(t, 0) - s.frais * (p["n"] - cap)
            p["n"] = cap
    s.ouvrir, s.gerer = ouvrir, gerer
    return s

def mesure2(ns0_, be, cap, debut, fin):
    ns, f_or, fab = ns0_["ns"], ns0_["f_or"], ns0_["fab_l431"]
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in ALLOC: s.risque = ALLOC[s.nom]
            if cap: plafonner(s, cap)
            if be and s.nom in PYR: breakeven(s, be)
        return sl
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    o, m = ftmo(r[6].sort_index())
    return r[0], o, m, r[2]

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
print("=== PLAFOND DE NOTIONNEL x gardien -1,75 % x breakeven 5 % ===")
print("%-32s | %-31s | %s" % ("", "10 ANS", "2021-2026"))
print("%-32s | %8s %8s %6s %7s | %8s %8s %6s %7s"
      % ("plafond par manche", "CAGR", "reussite", "duree", "DD", "CAGR", "reussite", "duree", "DD"))
print("-" * 118)
ns175 = charger(0.0175)
for cap, nom in ((None, "2,00x (actuel du moteur)"), (1.25, "1,25x"), (1.00, "1,00x"), (0.80, "0,80x")):
    ligne = "%-32s |" % nom
    for _, d, f in FEN:
        c, o, m, dd = mesure2(ns175, 0.05, cap, d, f)
        ligne += " %+7.1f %% %6.0f %% %4.0f j %+6.1f %% |" % (c, o, m, dd)
    print(ligne)
