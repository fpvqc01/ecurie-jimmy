# -*- coding: utf-8 -*-
"""BANC L8+ : les deux seuls candidats qui restent debout apres tous les bancs.

  A. FILTRE MARCHE BAISSIER : pas de nouvelle entree quand le Nasdaq est a
     plus de X % sous son sommet (decide avec la veille). Mesure -20 % =
     95 %/89 % de reussite, le meilleur jamais vu, mais +18/+109 jours.
  B. DECONCENTRATION : BTC Cassure fait 74,9 % du rendement ET 9 des 10 pires
     journees. On baisse son risque et on remonte l'or et le Nasdaq, a budget
     de risque total CONSTANT (pour ne pas confondre l'effet avec une simple
     reduction de taille).

On teste A, B, et A+B. Reference = L8 (89 %/205 j, 84 %/228 j)."""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B

NQ = pd.read_csv(os.path.join(D, "d10_nq.csv"), parse_dates=["t"]).set_index("t")
BAISSE = ((NQ["c"] / NQ["c"].cummax()) - 1.0).shift(1)   # decision avec la VEILLE

def sous_sommet(t):
    i = BAISSE.index.searchsorted(pd.Timestamp(t.date()), side="right") - 1
    if i < 0: return 0.0
    v = BAISSE.iloc[i]
    return 0.0 if pd.isna(v) else float(v)

def filtre(s, seuil):
    sig0 = s.signal
    def sig(t):
        return None if sous_sommet(t) <= seuil else sig0(t)
    s.signal = sig
    return s

BASE = dict(B.ALLOC)                       # Or .75 Nasdaq .75 Petrole 1.69 BTCC 1.69 EMA 1.13
BUDGET = sum(BASE.values())

def alloc_btc(r_btc):
    """baisse BTC Cassure a r_btc et redistribue a l'or et au Nasdaq,
    a budget de risque total constant."""
    a = dict(BASE)
    libere = a["BTC Cassure"] - r_btc
    a["BTC Cassure"] = r_btc
    a["Or"] += libere / 2.0
    a["Nasdaq"] += libere / 2.0
    assert abs(sum(a.values()) - BUDGET) < 1e-9
    return a

def mesure(alloc, seuil, deb, fin):
    ns0 = B.charger(0.0175)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in alloc: s.risque = alloc[s.nom]
        for s in sl:
            if s.nom in B.PYR: B.breakeven(s, 0.05)
        if seuil is not None:
            for s in sl: filtre(s, seuil)
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()
    o, m = B.ftmo(tj)
    n5 = int((tj <= -0.05).sum()); n3 = int((tj <= -0.03).sum())
    return r[0], o, m, r[2], n5, n3

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))

VAR = [("REFERENCE L8", BASE, None)]
for rb in (1.35, 1.00, 0.75):
    VAR.append(("B. BTC Cassure %.2f %% (au lieu de 1,69)" % rb, alloc_btc(rb/100), None))
VAR.append(("A. filtre Nasdaq -20 %", BASE, -0.20))
VAR.append(("A+B. filtre -20 % + BTC 1,00 %", alloc_btc(0.0100), -0.20))
VAR.append(("A+B. filtre -20 % + BTC 1,35 %", alloc_btc(0.0135), -0.20))

print("=== BANC L8+ (chassis L8 : gardien -1,75 %, breakeven 5 %, R13) ===")
print("%-38s | %-33s | %s" % ("", "10 ANS", "2021-2026"))
print("%-38s | %7s %8s %6s %7s %5s | %7s %8s %6s %7s"
      % ("variante", "CAGR", "reussite", "duree", "DD", "j<-3%", "CAGR", "reussite", "duree", "DD"))
print("-" * 122)
for nom, alloc, seuil in VAR:
    l = "%-38s |" % nom
    for k, (e, d, f) in enumerate(FEN):
        c, o, m, dd, n5, n3 = mesure(alloc, seuil, d, f)
        if k == 0: l += " %+6.1f %% %6.0f %% %4.0f j %+6.1f %% %4d |" % (c, o, m, dd, n3)
        else:      l += " %+6.1f %% %6.0f %% %4.0f j %+6.1f %%" % (c, o, m, dd)
    print(l)
