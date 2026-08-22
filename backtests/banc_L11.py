# -*- coding: utf-8 -*-
"""BANC L11 : le breakeven collectif peut-il remplacer le frein d'equite ?

Decouvert au banc des six versions L6 : « L6++ sans challenge » (breakeven
ON, frein d'equite OFF) faisait 87 %/178 j et 86 %/209 j avec +33,3 %/an,
au lieu de 85 %/199 j et 79 %/206 j avec +29,5 %/an pour L6++ mode ON.
Hypothese : les deux mecanismes protegent du meme risque, en garder deux
coute du rendement pour rien.

On verifie sur le chassis L8+ (deconcentration BTC a 1,15 %, breakeven 5 %),
en croisant mode challenge ON/OFF et gardien 1,75/2,50 %.
Reference L8+ = mode ON, gardien 1,75 : 99 %/238 j et 97 %/298 j."""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_ecuries_L6_modes as BM
import banc_L8 as B
import io as _io

BASE = dict(B.ALLOC)
def alloc_btc(r):
    a = dict(BASE); lib = a["BTC Cassure"] - r; a["BTC Cassure"] = r
    a["Or"] += lib/2; a["Nasdaq"] += lib/2; return a
AL = alloc_btc(0.0115)

def charger(mode_on, garde):
    """chaine complete : mode challenge ON/OFF ET gardien au choix"""
    src = _io.open(os.path.join(D, "tests_comite_B.py"), encoding="utf-8").read()
    src = src.split("# ============ 5.")[0]
    remp = []
    if not mode_on:
        remp.append((BM.LIGNE_FREIN, "fc = 1.0"))
    if abs(garde - 0.025) > 1e-9:
        remp.append(("sl = sleeves_l4(); garde = -0.025",
                     "sl = sleeves_l4(); garde = -%.5f" % garde))
    if remp:
        code = "".join("src2 = src.replace(%r, %r)\nassert src2 != src, 'ANCRE %d'\nsrc = src2\n"
                       % (a, b, i) for i, (a, b) in enumerate(remp))
        src = src.replace("src = src.replace('if t >= pd.Timestamp(\"2015-08-21\")]',",
                          code + "src = src.replace('if t >= pd.Timestamp(\"2015-08-21\")]',")
    ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
    exec(src, ns0)
    return ns0

def mesure(mode_on, garde, deb, fin):
    ns0 = charger(mode_on, garde)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in AL: s.risque = AL[s.nom]
        for s in sl:
            if s.nom in B.PYR: B.breakeven(s, 0.05)
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()
    o, m = B.ftmo(tj)
    n3 = int((tj <= -0.03).sum())
    return r[0], o, m, r[2], n3

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
print("=== BANC L11 (chassis L8+ : BTC 1,15 %, breakeven 5 %, R13) ===")
print("%-34s | %-33s | %s" % ("", "10 ANS", "2021-2026"))
print("%-34s | %7s %8s %6s %7s %5s | %7s %8s %6s"
      % ("configuration", "CAGR", "reussite", "duree", "DD", "j<-3%", "CAGR", "reussite", "duree"))
print("-" * 112)
for mode_on in (True, False):
    for garde in (0.0175, 0.025):
        etq = "frein equite %s | gardien %.2f %%" % ("ON " if mode_on else "OFF", garde*100)
        l = "%-34s |" % etq
        for k, (e, d, f) in enumerate(FEN):
            c, o, m, dd, n3 = mesure(mode_on, garde, d, f)
            if k == 0: l += " %+6.1f %% %6.0f %% %4.0f j %+6.1f %% %4d |" % (c, o, m, dd, n3)
            else:      l += " %+6.1f %% %6.0f %% %4.0f j" % (c, o, m)
        print(l)
