# -*- coding: utf-8 -*-
"""Contre-verification : L4 + filtre dollar, pyramide 3 vs 4 (H4, 10 ans)."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read()
ns = {"__file__": os.path.join(D, "test_l4_macro.py")}
exec(src.split('print()')[0], ns)
dxy = ns["dxy"]
FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
f_or = lambda n, j: n == "Or" and j in FORT

# pyramide 4 : on patche pyr_max dans la construction des manches
sleeves_l4 = ns["sleeves_l4"]
def sim(pyr_max, interdit):
    orig = sleeves_l4
    def sl4():
        s = orig()
        for x in s:
            if hasattr(x, "pyr_max"): x.pyr_max = pyr_max
        return s
    ns["sleeves_l4"] = sl4
    try:
        return ns["sim_h4"](interdit=interdit)
    finally:
        ns["sleeves_l4"] = orig

for nom, pm, f in (("pyramide 3 + filtre dollar", 3, f_or),
                   ("pyramide 4 + filtre dollar", 4, f_or),
                   ("pyramide 4 sans filtre", 4, None)):
    c, s, d, m, a1, a2 = sim(pm, f)
    print("  %-28s : CAGR %+5.1f%% | Sharpe %5.2f | DD %+6.1f%% | morts %3.0f%% | %+5.1f/%+5.1f%%"
          % (nom, c, s, d, m, a1, a2))
