# -*- coding: utf-8 -*-
"""Qui coute : l'EMA en H1 ou le petrole en D1 ? Isolation + PnL par manche."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH
BTC_H1 = pd.read_csv(os.path.join(D, "d10h1_btc.csv"), index_col=0,
                     parse_dates=True)[["o","h","l","c"]].astype(float)
src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read().split('print()')[0]
ns = {"__file__": os.path.join(D, "test_l4_macro.py")}
exec(src, ns)
dxy = ns["dxy"]
FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
f_or = lambda n, j: n == "Or" and j in FORT
orig = ns["sleeves_l4"]

def fabrique(ema_h1, pet_d1):
    def f():
        s = []
        for x in orig():
            if hasattr(x, "pyr_max"): x.pyr_max = 4
            if x.nom == "BTC EMA" and ema_h1:
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

for nom, e, p in (("tout H4", False, False), ("EMA H1 seulement", True, False),
                  ("petrole D1 seulement", False, True), ("les deux (reel)", True, True)):
    ns["sleeves_l4"] = fabrique(e, p)
    c, s, d, m, a1, a2 = ns["sim_h4"](interdit=f_or)
    print("  %-24s : CAGR %+5.1f%% | morts %3.0f%% | DD %+6.1f%% | %+5.1f/%+5.1f%%"
          % (nom, c, m, d, a1, a2))
# PnL par manche pour la config reelle (trace maison via sleeves)
print()
sl = fabrique(True, True)()
ns["sleeves_l4"] = lambda: sl
ns["sim_h4"](interdit=f_or)
print("  PnL cumule par manche (config reelle) :")
for s in sl:
    print("    %-12s : %+7.1f %% (%d trades)" % (s.nom, sum(s.pnl.values())*100, s.trades))
