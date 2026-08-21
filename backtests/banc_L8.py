# -*- coding: utf-8 -*-
"""BANC L8 — sur DONNEES REPAREES (21 aout 2026).
Teste les correctifs recommandes par le groupe de verification :
  - gardien quotidien resserre (-2,5 % -> -2,0 / -1,75 / -1,5 / -1,25)
  - breakeven collectif (seuls survivants : effet sur le drawdown)
  - combinaisons gardien x breakeven
Config L6 (allocation a x0,75), mode challenge ON, 2 fenetres."""
import os, io, numpy as np
D = os.path.dirname(os.path.abspath(__file__))

LIGNE_GARDE = "sl = sleeves_l4(); garde = -0.025"

def charger(garde_pct):
    """recharge la chaine du moteur avec un gardien quotidien different"""
    src = io.open(os.path.join(D, "tests_comite_B.py"), encoding="utf-8").read()
    src = src.split("# ============ 5.")[0]
    if abs(garde_pct - 0.025) > 1e-9:
        nouveau = "sl = sleeves_l4(); garde = -%.5f" % garde_pct
        src = src.replace(
            "src = src.replace('if t >= pd.Timestamp(\"2015-08-21\")]',",
            'src2 = src.replace(%r, %r)\n'
            "assert src2 != src, 'ANCRE GARDIEN INTROUVABLE'\n"
            "src = src2\n"
            "src = src.replace('if t >= pd.Timestamp(\"2015-08-21\")]'," % (LIGNE_GARDE, nouveau))
    ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
    exec(src, ns0)
    return ns0

ALLOC = {"Or": 0.0075, "Nasdaq": 0.0075, "Petrole": 0.0169,
         "BTC Cassure": 0.0169, "BTC EMA": 0.0113}
PYR = ("BTC Cassure", "Petrole")

def breakeven(s, seuil):
    g0 = s.gerer
    def g(t):
        g0(t)
        p = s.pos
        if p is None: return
        i = s.idx.get(t)
        if i is None: return
        if (s.C[i] - p["e"]) / p["e"] >= seuil:
            m = (p["e"] + p.get("dernier", p["e"])) / 2.0
            if m > p["s"]: p["s"] = m
    s.gerer = g
    return s

def phase(v, i0, cible):
    eq = 1.0; jt = 0
    for j in range(i0, len(v)):
        r = v[j]
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j - i0 + 1
        eq *= (1 + r)
        if eq <= 0.90: return 0, j - i0 + 1
        if eq >= 1 + cible and jt >= 4: return 1, j - i0 + 1
    return -1, len(v) - i0

def ftmo(tj):
    v = tj.values; ok = mort = 0; d = []
    for i0 in range(0, len(v) - 60, 3):
        v1, d1 = phase(v, i0, 0.10)
        if v1 == -1: continue
        if v1 == 0: mort += 1; continue
        v2, d2 = phase(v, i0 + d1, 0.05)
        if v2 == -1: continue
        if v2 == 0: mort += 1; continue
        ok += 1; d.append(d1 + d2)
    n = ok + mort
    return 100.0 * ok / max(n, 1), (np.median(d) if d else 0)

def mesure(ns0, be, debut, fin):
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in ALLOC: s.risque = ALLOC[s.nom]
        if be:
            for s in sl:
                if s.nom in PYR: breakeven(s, be)
        return sl
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    o, m = ftmo(r[6].sort_index())
    return r[0], o, m, r[2]

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))

print("=== BANC L8 : GARDIEN QUOTIDIEN (donnees REPAREES) ===")
print("%-34s | %-30s | %s" % ("", "10 ANS", "2021-2026"))
print("%-34s | %8s %8s %6s %7s | %8s %8s %6s %7s"
      % ("configuration", "CAGR", "reussite", "duree", "DD", "CAGR", "reussite", "duree", "DD"))
print("-" * 118)
for garde in (0.025, 0.020, 0.0175, 0.015, 0.0125):
    ns0 = charger(garde)
    for be, nom_be in ((None, ""), (0.05, " + breakeven 5 %")):
        ligne = "%-34s |" % ("gardien -%.2f %%%s" % (garde * 100, nom_be))
        for _, d, f in FEN:
            c, o, m, dd = mesure(ns0, be, d, f)
            ligne += " %+7.1f %% %6.0f %% %4.0f j %+6.1f %% |" % (c, o, m, dd)
        print(ligne)
