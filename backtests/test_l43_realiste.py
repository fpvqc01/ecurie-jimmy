# -*- coding: utf-8 -*-
"""REALISME DE L4.3 (demande de Jimmy) :
1. WALK-FORWARD : cadences choisies sur 2015-2020 SEULEMENT, combo fige,
   mesure sur 2021-2026 (jamais vues). Tue ou confirme la selection.
2. STRESS DES COUTS : frais x2 et x3 (spread/glissement pessimistes).
Mode challenge ON, moteur H4."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH
BTC_H1 = pd.read_csv(os.path.join(D, "d10h1_btc.csv"), index_col=0,
                     parse_dates=True)[["o","h","l","c"]].astype(float)

def moteur():
    src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read().split('print()')[0]
    src = src.replace('if t >= pd.Timestamp("2015-08-21")]',
                      'if t >= pd.Timestamp(DEBUT) and t <= pd.Timestamp(FIN)]')
    ns = {"__file__": os.path.join(D, "test_l4_macro.py"),
          "DEBUT": "2015-08-21", "FIN": "2026-12-31"}
    exec(src, ns)
    ns["ORIG"] = ns["sleeves_l4"]
    return ns

ns = moteur()
dxy = ns["dxy"]
FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
f_or = lambda n, j: n == "Or" and j in FORT

def porte_d1(x):
    sig0 = x.signal
    def sig(t, x=x, sig0=sig0):
        i = x.idx.get(t)
        if i is None or not x.NEWDAY[i]: return None
        return sig0(t)
    x.signal = sig
    return x

def btc_h1(nom):
    if nom == "BTC EMA":
        return MH.EmaBTCH4("BTC EMA", BTC_H1, 0.015, 0.0004, -0.000833/4, 1.0,
                           jimmy=True, retrace=0.25, tpj=2.0)
    s = MH.DonchH4("BTC Cassure", BTC_H1, 0.015, 0.0004, -0.000833/4, 1.0)
    ns2 = {"__file__": os.path.join(D, "valide_candidats_h4.py")}
    exec(open(os.path.join(D, "valide_candidats_h4.py"), encoding="utf-8").read()
         .split("RISQUES =")[0], ns2)
    s.pyr_max = 4
    s.gerer = ns2["gerer_pyr_max"].__get__(s); s.ouvrir = MH.ouvrir_pyr.__get__(s)
    return s

def fabrique(cadences, mult_frais=1.0):
    def f():
        s = []
        for x in ns["ORIG"]():
            if hasattr(x, "pyr_max"): x.pyr_max = 4
            cad = cadences.get(x.nom, "H4")
            if x.nom.startswith("BTC") and cad == "H1":
                x = btc_h1(x.nom)
            elif cad == "D1":
                x = porte_d1(x)
            x.frais = x.frais * mult_frais
            s.append(x)
        return s
    return f

def run(cadences, debut, fin, mult_frais=1.0):
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = fabrique(cadences, mult_frais)
    return ns["sim_h4"](interdit=f_or)

BASE = {"Or": "H4", "Nasdaq": "H4", "BTC Cassure": "H4", "BTC EMA": "H1", "Petrole": "D1"}
C2   = {"Or": "H4", "Nasdaq": "H4", "BTC Cassure": "H1", "BTC EMA": "D1", "Petrole": "H4"}

# ---------- 1. WALK-FORWARD ----------
print("### 1. WALK-FORWARD : selection sur 2015-2020, test sur 2021-2026 ###")
print("--- phase de selection (2015-08 -> 2020-12), un robot a la fois ---")
r0 = run(BASE, "2015-08-21", "2020-12-31")
print("  base 2015-2020 : CAGR %+5.1f%%" % r0[0])
choix = {}
for nom, cads in (("Or", ["D1"]), ("Nasdaq", ["D1"]),
                  ("BTC Cassure", ["H1", "D1"]), ("BTC EMA", ["H4", "D1"]),
                  ("Petrole", ["H4"])):
    meilleur, cad_m = r0[0], BASE[nom]
    for cad in cads:
        c = dict(BASE); c[nom] = cad
        r = run(c, "2015-08-21", "2020-12-31")
        print("    %-12s -> %-3s : %+5.1f%%" % (nom, cad, r[0]))
        if r[0] > meilleur + 0.5:
            meilleur, cad_m = r[0], cad
    choix[nom] = cad_m
combo_wf = dict(BASE); combo_wf.update(choix)
print("  combo choisi par 2015-2020 :", {k: v for k, v in choix.items() if v != BASE[k]})
print("--- test HORS ECHANTILLON (2021-01 -> 2026-08), combo FIGE ---")
ra = run(BASE, "2021-01-01", "2026-08-20")
rb = run(combo_wf, "2021-01-01", "2026-08-20")
print("  AVANT (base)  2021-2026 : CAGR %+5.1f%% | reussite %3.0f %% | DD %+6.1f%%" % (ra[0], 100-ra[3], ra[2]))
print("  APRES (combo) 2021-2026 : CAGR %+5.1f%% | reussite %3.0f %% | DD %+6.1f%%" % (rb[0], 100-rb[3], rb[2]))
print()

# ---------- 2. STRESS DES COUTS ----------
print("### 2. STRESS DES COUTS (10 ans, mode ON) ###")
for mult, nom in ((1.0, "frais normaux"), (2.0, "frais x2"), (3.0, "frais x3")):
    ra = run(BASE, "2015-08-21", "2026-12-31", mult)
    rb = run(C2,   "2015-08-21", "2026-12-31", mult)
    print("  %-14s : AVANT %+5.1f%%/%3.0f%%  |  APRES %+5.1f%%/%3.0f%%  (ecart %+.1f pt)"
          % (nom, ra[0], 100-ra[3], rb[0], 100-rb[3], rb[0]-ra[0]))
