# -*- coding: utf-8 -*-
"""TOURNOI DES VERSIONS L4 (demande de Jimmy) : chaque etage empile,
moteur H4 realiste (cadences reelles), 10 ans + hors echantillon 2021-2026,
modes ON et OFF.
  L4.0 : or 2,0 + correlation + parite, pyramide 3, sans filtre dollar
  L4.1 : + filtre dollar
  L4.2 : + pyramide 4              <- DEPLOYE sur MT6 (mode OFF)
  L4.3 : + cadences (Cassure H1, Petrole H4, EMA D1)"""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH
BTC_H1 = pd.read_csv(os.path.join(D, "d10h1_btc.csv"), index_col=0,
                     parse_dates=True)[["o","h","l","c"]].astype(float)

def moteur(thr_actif):
    src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read().split('print()')[0]
    src = src.replace('if t >= pd.Timestamp("2015-08-21")]',
                      'if t >= pd.Timestamp(DEBUT) and t <= pd.Timestamp(FIN)]')
    if not thr_actif:
        src = src.replace(
            "fc = 0.75 if (len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0",
            "fc = 1.0")
    ns = {"__file__": os.path.join(D, "test_l4_macro.py"),
          "DEBUT": "2015-08-21", "FIN": "2026-12-31"}
    exec(src, ns)
    ns["ORIG"] = ns["sleeves_l4"]
    return ns

def porte_d1(x):
    sig0 = x.signal
    def sig(t, x=x, sig0=sig0):
        i = x.idx.get(t)
        if i is None or not x.NEWDAY[i]: return None
        return sig0(t)
    x.signal = sig
    return x

NS2 = {"__file__": os.path.join(D, "valide_candidats_h4.py")}
exec(open(os.path.join(D, "valide_candidats_h4.py"), encoding="utf-8").read()
     .split("RISQUES =")[0], NS2)

def btc_h1(nom, pyr_max):
    if nom == "BTC EMA":
        return MH.EmaBTCH4("BTC EMA", BTC_H1, 0.015, 0.0004, -0.000833/4, 1.0,
                           jimmy=True, retrace=0.25, tpj=2.0)
    s = MH.DonchH4("BTC Cassure", BTC_H1, 0.015, 0.0004, -0.000833/4, 1.0)
    s.pyr_max = pyr_max
    s.gerer = NS2["gerer_pyr_max"].__get__(s); s.ouvrir = MH.ouvrir_pyr.__get__(s)
    return s

def fabrique(ns, cadences, pyr_max):
    def f():
        s = []
        for x in ns["ORIG"]():
            if hasattr(x, "pyr_max"): x.pyr_max = pyr_max
            cad = cadences.get(x.nom, "H4")
            if x.nom.startswith("BTC") and cad == "H1":
                x = btc_h1(x.nom, pyr_max)
            elif cad == "D1":
                x = porte_d1(x)
            s.append(x)
        return s
    return f

REEL = {"Or": "H4", "Nasdaq": "H4", "BTC Cassure": "H4", "BTC EMA": "H1", "Petrole": "D1"}
C2   = {"Or": "H4", "Nasdaq": "H4", "BTC Cassure": "H1", "BTC EMA": "D1", "Petrole": "H4"}
VERSIONS = [
    ("L4.0 (base, pyr3, sans filtre)", REEL, 3, False),
    ("L4.1 (+ filtre dollar)",         REEL, 3, True),
    ("L4.2 (+ pyramide 4) [DEPLOYE]",  REEL, 4, True),
    ("L4.3 (+ cadences optimisees)",   C2,   4, True),
]

for mode, thr in (("ON", True), ("OFF", False)):
    ns = moteur(thr)
    dxy = ns["dxy"]
    FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
    f_or = lambda n, j: n == "Or" and j in FORT
    print("=== MODE CHALLENGE %s ===" % mode)
    print("  %-34s | %-19s | %-19s" % ("Version", "10 ANS", "2021-2026 (difficile)"))
    print("  %-34s | %-7s %-9s | %-7s %-9s" % ("", "CAGR", "Reussite", "CAGR", "Reussite"))
    print("  " + "-" * 78)
    for nom, cad, pyr, filtre in VERSIONS:
        ns["sleeves_l4"] = fabrique(ns, cad, pyr)
        ns["DEBUT"], ns["FIN"] = "2015-08-21", "2026-12-31"
        r10 = ns["sim_h4"](interdit=(f_or if filtre else None))
        ns["sleeves_l4"] = fabrique(ns, cad, pyr)
        ns["DEBUT"], ns["FIN"] = "2021-01-01", "2026-08-20"
        r5 = ns["sim_h4"](interdit=(f_or if filtre else None))
        print("  %-34s | %+6.1f%% %5.0f %%   | %+6.1f%% %5.0f %%"
              % (nom, r10[0], 100-r10[3], r5[0], 100-r5[3]))
    print()
