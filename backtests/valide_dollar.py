# -*- coding: utf-8 -*-
"""Validation du filtre dollar sur l'or : stabilite aux voisins (EMA 100/
200/300 du DXY) en H4 10 ans, et contre-verification sur le moteur D1 10 ans."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read()
ns = {"__file__": os.path.join(D, "test_l4_macro.py")}
exec(src.split('print()')[0], ns)
dxy, sim_h4 = ns["dxy"], ns["sim_h4"]

print("=== VOISINS : periode de la moyenne du DXY (H4, 10 ans) ===")
for span in (100, 150, 200, 300):
    e = dxy.ewm(span=span, adjust=False).mean()
    FORT = set(dxy.index[(dxy > e)].date)
    f = lambda n, j, F=FORT: n == "Or" and j in F
    c, s, d, m, a1, a2 = sim_h4(interdit=f)
    print("  DXY > e%-3d : CAGR %+5.1f%% | Sharpe %5.2f | morts %3.0f%% | moities %+5.1f/%+5.1f%%"
          % (span, c, s, m, a1, a2))
c, s, d, m, a1, a2 = sim_h4()
print("  reference  : CAGR %+5.1f%% | Sharpe %5.2f | morts %3.0f%% | moities %+5.1f/%+5.1f%%" % (c, s, m, a1, a2))

# ---- contre-verification D1 10 ans ----
print()
print("=== CONTRE-VERIFICATION D1 10 ans ===")
src2 = open(os.path.join(D, "test_l4_10ans.py"), encoding="utf-8").read()
src2 = src2.split("CONFIGS =")[0].replace(
    "        ouverts = sum(1 for s in sl if s.pos is not None)",
    "        ouverts = sum(1 for s in sl if s.pos is not None)")
ns2 = {"__file__": os.path.join(D, "test_l4_10ans.py")}
exec(src2, ns2)
# on injecte le filtre dans le sim D1 : on modifie sim10 pour L4 avec interdiction or
FORT200 = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
src3 = src2.replace("            sig = s.signal(d)",
                    "            if INTERDIT and s.nom == 'Or' and d.date() in FORT200: continue\n"
                    "            sig = s.signal(d)")
ns3 = {"__file__": os.path.join(D, "test_l4_10ans.py"), "FORT200": FORT200}
exec(src3, ns3)
for etiquette, flag in (("L4 reference", False), ("L4 + filtre dollar", True)):
    ns3["INTERDIT"] = flag
    r = ns3["sim10"]("L4")
    print("  %-22s : CAGR %+5.1f%% | morts %3.0f%% | moities %+5.1f/%+5.1f%%"
          % (etiquette, r["cagr"], r["morts"], r["m1"], r["m2"]))
