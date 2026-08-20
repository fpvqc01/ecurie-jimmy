# -*- coding: utf-8 -*-
"""L4.2 AVEC LES UNITES DE TEMPS REELLES DES ROBOTS (demande de Jimmy) :
  - Or, Nasdaq, BTC Cassure : H4 (comme avant)
  - BTC EMA : H1 (96 778 barres, signaux 24x/jour, swap ajuste)
  - Petrole : D1 (signal evalue seulement a la premiere barre du jour)
vs la reference 'tout en H4'. Config L4.2 deployee (pyr4 + filtre dollar),
mode challenge ON et OFF, 10 ans."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH

BTC_H1 = pd.read_csv(os.path.join(D, "d10h1_btc.csv"), index_col=0,
                     parse_dates=True)[["o", "h", "l", "c"]].astype(float)

for thr_actif in (True, False):
    tag = "ON" if thr_actif else "OFF"
    src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read().split('print()')[0]
    if not thr_actif:
        src = src.replace(
            "fc = 0.75 if (len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0",
            "fc = 1.0")
    ns = {"__file__": os.path.join(D, "test_l4_macro.py")}
    exec(src, ns)
    dxy = ns["dxy"]
    FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
    f_or = lambda n, j: n == "Or" and j in FORT
    orig = ns["sleeves_l4"]

    def sl_h4():
        s = orig()
        for x in s:
            if hasattr(x, "pyr_max"): x.pyr_max = 4
        return s

    def sl_reels():
        s = []
        for x in orig():
            if hasattr(x, "pyr_max"): x.pyr_max = 4
            if x.nom == "BTC EMA":
                # H1 : swap divise par 4 (24 barres/jour au lieu de 6)
                y = MH.EmaBTCH4("BTC EMA", BTC_H1, 0.015, 0.0004, -0.000833/4, 1.0,
                                jimmy=True, retrace=0.25, tpj=2.0)
                s.append(y)
            elif x.nom == "Petrole":
                # D1 : signal seulement a la premiere barre H4 du jour
                sig0 = x.signal
                def sig_d1(t, x=x, sig0=sig0):
                    i = x.idx.get(t)
                    if i is None or not x.NEWDAY[i]: return None
                    return sig0(t)
                x.signal = sig_d1
                s.append(x)
            else:
                s.append(x)
        return s

    print("=== MODE CHALLENGE %s (H4/H1/D1 reels vs tout-H4, 10 ans) ===" % tag)
    for nom, fabrique in (("tout en H4 (reference)", sl_h4),
                          ("unites REELLES (EMA H1, petrole D1)", sl_reels)):
        ns["sleeves_l4"] = fabrique
        c, s, d, m, a1, a2 = ns["sim_h4"](interdit=f_or)
        print("  %-38s | %+6.1f%% | Sharpe %5.2f | DD %+6.1f%% | morts %3.0f%% | %+5.1f/%+5.1f%%"
              % (nom, c, s, d, m, a1, a2))
    ns["sleeves_l4"] = orig
    print()
