# -*- coding: utf-8 -*-
"""L4.3 PROJETE : cadences reelles (EMA H1) + petrole evalue en H4 (la
decouverte du jour). Mode challenge ON et OFF, H4 10 ans.
Comparaison : L4.2 reel actuel (petrole 1x/jour) vs L4.3."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH
BTC_H1 = pd.read_csv(os.path.join(D, "d10h1_btc.csv"), index_col=0,
                     parse_dates=True)[["o","h","l","c"]].astype(float)

for thr_actif in (True, False):
    tag = "ON " if thr_actif else "OFF"
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

    def fabrique(pet_d1):
        def f():
            s = []
            for x in orig():
                if hasattr(x, "pyr_max"): x.pyr_max = 4
                if x.nom == "BTC EMA":
                    x = MH.EmaBTCH4("BTC EMA", BTC_H1, 0.015, 0.0004, -0.000833/4, 1.0,
                                    jimmy=True, retrace=0.25, tpj=2.0)
                elif x.nom == "Petrole" and pet_d1:
                    sig0 = x.signal
                    def sig_d1(t, x=x, sig0=sig0):
                        i = x.idx.get(t)
                        if i is None or not x.NEWDAY[i]: return None
                        return sig0(t)
                    x.signal = sig_d1
                s.append(x)
            return s
        return f

    for nom, pet_d1 in (("L4.2 actuel (petrole 1x/jour)", True),
                        ("L4.3 (petrole evalue en H4)", False)):
        ns["sleeves_l4"] = fabrique(pet_d1)
        c, s, d, m, a1, a2 = ns["sim_h4"](interdit=f_or)
        print("  mode %s %-32s : CAGR %+5.1f%% | REUSSITE %3.0f %% | DD %+6.1f%% | Sharpe %4.2f | %+5.1f/%+5.1f%%"
              % (tag, nom, c, 100-m, d, s, a1, a2))
    print()
