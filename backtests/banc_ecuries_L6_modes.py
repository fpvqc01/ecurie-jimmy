# -*- coding: utf-8 -*-
"""COMPARATIF COMPLET DES ECURIES L6 x MODE CHALLENGE ON/OFF
(demande Jimmy, 21 aout). Rendement annuel + reussite du challenge.

Le « mode challenge » = frein d'equite : les mises sont reduites a 75 %
tant que l'equite est sous sa moyenne 20 jours (ligne fc du moteur).
  ON  = protection active (ce qui roule en service)
  OFF = pleine puissance, sans frein

Ecuries : L6 (base), L6+ (turbo-coussin), L6++ (breakeven collectif
5 % et 6 %). Simulateur FTMO exact sur les 2 fenetres."""
import os, io, numpy as np
D = os.path.dirname(os.path.abspath(__file__))

LIGNE_FREIN = "fc = 0.75 if (len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0"

def charger(mode_on):
    """recharge toute la chaine du moteur, avec ou sans le frein d'equite"""
    src = io.open(os.path.join(D, "tests_comite_B.py"), encoding="utf-8").read()
    src = src.split("# ============ 5.")[0]
    if not mode_on:
        src = src.replace(
            "src = src.replace('if t >= pd.Timestamp(\"2015-08-21\")]',",
            'src = src.replace(%r, "fc = 1.0")\n'
            "src = src.replace('if t >= pd.Timestamp(\"2015-08-21\")]'," % LIGNE_FREIN)
    ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
    exec(src, ns0)
    return ns0

ALLOC = {"Or": 0.0075, "Nasdaq": 0.0075, "Petrole": 0.0169,
         "BTC Cassure": 0.0169, "BTC EMA": 0.0113}
PYR = ("BTC Cassure", "Petrole")

def breakeven_collectif(s, seuil):
    gerer0 = s.gerer
    def gerer(t):
        gerer0(t)
        p = s.pos
        if p is None: return
        i = s.idx.get(t)
        if i is None: return
        if (s.C[i] - p["e"]) / p["e"] >= seuil:
            moyen = (p["e"] + p.get("dernier", p["e"])) / 2.0
            if moyen > p["s"]: p["s"] = moyen
    s.gerer = gerer
    return s

def phase(vals, i0, cible, mult=1.0, turbo=None):
    eq = 1.0; jt = 0
    for j in range(i0, len(vals)):
        m = 1.0 if (turbo and eq >= 1 + turbo) else mult
        r = vals[j] * m
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j - i0 + 1
        eq *= (1 + r)
        if eq <= 0.90: return 0, j - i0 + 1
        if eq >= 1 + cible and jt >= 4: return 1, j - i0 + 1
    return -1, len(vals) - i0

def ftmo(tj, mult=1.0, turbo=None):
    vals = tj.values
    complets = morts = 0; durees = []
    for i0 in range(0, len(vals) - 60, 3):
        v1, d1 = phase(vals, i0, 0.10, mult, turbo)
        if v1 == -1: continue
        if v1 == 0: morts += 1; continue
        v2, d2 = phase(vals, i0 + d1, 0.05, mult, turbo)
        if v2 == -1: continue
        if v2 == 0: morts += 1; continue
        complets += 1; durees.append(d1 + d2)
    n = complets + morts
    return 100.0 * complets / max(n, 1), (np.median(durees) if durees else 0)

def mesure(ns0, post, debut, fin):
    ns, f_or, fab_l431 = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    def f():
        sl = fab_l431()()
        for s in sl:
            if s.nom in ALLOC: s.risque = ALLOC[s.nom]
        if post: post(sl)
        return sl
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    return r[0], r[2], r[6].sort_index()

BE5 = lambda sl: [breakeven_collectif(s, 0.05) for s in sl if s.nom in PYR]
BE6 = lambda sl: [breakeven_collectif(s, 0.06) for s in sl if s.nom in PYR]

FENETRES = (("10 ANS (2015-2026)", "2015-08-21", "2026-12-31"),
            ("2021-2026 (marche recent)", "2021-01-01", "2026-08-20"))

for mode_on in (True, False):
    ns0 = charger(mode_on)
    for titre, debut, fin in FENETRES:
        print()
        print("=== MODE CHALLENGE %s | %s ===" % ("ON " if mode_on else "OFF", titre))
        print("%-30s | %9s | %9s | %7s | %8s" % ("ECURIE", "RENDEMENT", "REUSSITE", "DUREE", "DD max"))
        print("-" * 78)
        c0, d0, t0 = mesure(ns0, None, debut, fin)
        c5, d5, t5 = mesure(ns0, BE5, debut, fin)
        c6, d6, t6 = mesure(ns0, BE6, debut, fin)
        for nom, cagr, dd, tj, mult, turbo in (
                ("L6  (base)",              c0, d0, t0, 1.0,  None),
                ("L6+ turbo-coussin",       c0, d0, t0, 1.33, 0.04),
                ("L6++ breakeven 5 %",      c5, d5, t5, 1.0,  None),
                ("L6++ breakeven 6 %",      c6, d6, t6, 1.0,  None),
                ("L6++ 5 % + turbo",        c5, d5, t5, 1.33, 0.04),
        ):
            ok, med = ftmo(tj, mult, turbo)
            print("%-30s | %+7.1f %% | %7.0f %% | %4.0f j | %+6.1f %%" % (nom, cagr, ok, med, dd))
