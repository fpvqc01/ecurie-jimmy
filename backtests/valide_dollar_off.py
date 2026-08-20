# -*- coding: utf-8 -*-
"""Filtre dollar sur L4 en mode challenge OFF (les 2 moteurs, 10 ans)."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))

# ---- H4 : on reprend test_l4_macro et on coupe le throttle ----
src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read()
src = src.split('print()')[0].replace(
    "fc = 0.75 if (len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0",
    "fc = 1.0    # mode challenge OFF")
ns = {"__file__": os.path.join(D, "test_l4_macro.py")}
exec(src, ns)
dxy, sim_h4 = ns["dxy"], ns["sim_h4"]
FORT200 = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
f_or = lambda n, j: n == "Or" and j in FORT200

print("=== L4 MODE CHALLENGE OFF (H4, 10 ans) ===")
for nom, kw in (("reference", dict()), ("+ filtre dollar", dict(interdit=f_or))):
    c, s, d, m, a1, a2 = sim_h4(**kw)
    print("  %-18s : CAGR %+5.1f%% | Sharpe %5.2f | DD %+6.1f%% | morts %3.0f%% | %+5.1f/%+5.1f%%"
          % (nom, c, s, d, m, a1, a2))

# ---- D1 : test_l4_10ans en gen L4off + interdiction or ----
src2 = open(os.path.join(D, "test_l4_10ans.py"), encoding="utf-8").read().split("CONFIGS =")[0]
src2 = src2.replace("            sig = s.signal(d)",
                    "            if INTERDIT and s.nom == 'Or' and d.date() in FORT200: continue\n"
                    "            sig = s.signal(d)")
# gen 'L4' avec throttle force a None
src2 = src2.replace('thr  = 0.75 if gen in ("L3+", "L4") else None', "thr = None")
ns2 = {"__file__": os.path.join(D, "test_l4_10ans.py"), "FORT200": FORT200}
exec(src2, ns2)
print()
print("=== L4 MODE CHALLENGE OFF (D1, 10 ans) ===")
for nom, flag in (("reference", False), ("+ filtre dollar", True)):
    ns2["INTERDIT"] = flag
    r = ns2["sim10"]("L4")
    print("  %-18s : CAGR %+5.1f%% | DD %+6.1f%% | morts %3.0f%% | %+5.1f/%+5.1f%%"
          % (nom, r["cagr"], r["dd"], r["morts"], r["m1"], r["m2"]))
