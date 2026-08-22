# -*- coding: utf-8 -*-
"""LES DEUX IDEES DE JIMMY SUR TOUTES LES DERNIERES GENERATIONS.

  A. repli conditionnel : on attend un repli de 1,25 ATR avant d'acheter la
     cassure, SAUF si la tendance est deja forte ((prix-EMA50)/ATR >= 1,0),
     auquel cas on prend la cassure tout de suite.
  B. max 2 unites de pyramide par jour.

Generations : L6R13, L8, L8+, L11. Toutes avec la fermeture a +10 % (R13).
On veut savoir si le gain survit sur les chassis deja deconcentres, ou s'il
faisait double emploi avec la baisse du risque BTC."""
import os, sys, io
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B

def charge(nom, coupe):
    src = io.open(os.path.join(D, nom), encoding="utf-8").read().split(coupe)[0]
    ns = {"__file__": os.path.join(D, nom), "__name__": "x"}
    exec(src, ns); return ns
R = charge("banc_repli.py", "FEN = (")
C = charge("banc_repli_conditionnel.py", "FEN = R.FEN")
CIBLES, max_pyr_jour, cond = R["CIBLES"], R["max_pyr_jour"], C["repli_conditionnel"]

BASE = dict(B.ALLOC)
def alloc_btc(r):
    a = dict(BASE); lib = a["BTC Cassure"] - r; a["BTC Cassure"] = r
    a["Or"] += lib/2; a["Nasdaq"] += lib/2; return a
BTC115 = alloc_btc(0.0115)

_cache = {}
def chaine(garde):
    if garde not in _cache: _cache[garde] = B.charger(garde)
    return _cache[garde]

def mesure(garde, be, alloc, meca, deb, fin):
    ns0 = chaine(garde)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in alloc: s.risque = alloc[s.nom]
        if be:
            for s in sl:
                if s.nom in B.PYR: B.breakeven(s, be)
        if meca: meca(sl)
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()
    o, m = B.ftmo(tj)
    return r[0], o, m, r[2]

GENS = (("L6R13", 0.025,  None, BASE),
        ("L8",    0.0175, 0.05, BASE),
        ("L8+",   0.0175, 0.05, BTC115),
        ("L11",   0.025,  0.05, BTC115))

MECAS = (("reference", None),
         ("+ max 2 pyramidages/jour",
          lambda sl: [max_pyr_jour(s,2) for s in sl if s.nom in CIBLES]),
         ("+ repli 1,25 si force < 1,0",
          lambda sl: [cond(s,1.25,5,1.0) for s in sl if s.nom in CIBLES]),
         ("+ les deux",
          lambda sl: [max_pyr_jour(cond(s,1.25,5,1.0),2) for s in sl if s.nom in CIBLES]))

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))

for nom, garde, be, alloc in GENS:
    print(); print("=== %s ===" % nom)
    print("%-30s | %-30s | %s" % ("", "10 ANS", "2021-2026"))
    print("%-30s | %7s %8s %6s %7s | %8s %6s"
          % ("variante", "CAGR", "reussite", "duree", "DD", "reussite", "duree"))
    print("-" * 92)
    for etq, meca in MECAS:
        l = "%-30s |" % etq
        for k, (e, d0, f0) in enumerate(FEN):
            c, o, m, dd = mesure(garde, be, alloc, meca, d0, f0)
            if k == 0: l += " %+6.1f %% %6.0f %% %4.0f j %+6.1f %% |" % (c, o, m, dd)
            else:      l += " %6.0f %% %4.0f j" % (o, m)
        print(l)
