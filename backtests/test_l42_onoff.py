# -*- coding: utf-8 -*-
"""L4.2 (config DEPLOYEE : or 2,0 + correlation + filtre dollar + pyramide 4)
mode challenge ON vs OFF -- taux de reussite des challenges + rendement
annuel, moteurs H4 et D1, 10 ans."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))

dxy = pd.read_csv(os.path.join(D, "d10_dxy.csv"), index_col=0, parse_dates=True)["c"]
FORT200 = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)

def prepare(fichier, seuil="            sig = s.signal(t)", var_date="t"):
    src = open(os.path.join(D, fichier), encoding="utf-8").read().split("NOMS =")[0].split("CONFIGS =")[0]
    src = src.replace("s.pyr_max = 3", "s.pyr_max = 4")            # pyramide 4
    src = src.replace(seuil,
        "            if s.nom == 'Or' and %s.date() in FORT200: continue   # filtre dollar\n" % var_date
        + seuil)
    ns = {"__file__": os.path.join(D, fichier), "FORT200": FORT200}
    exec(src, ns)
    return ns["sim10"]

sim_h4 = prepare("test_l4_h4_10ans.py", "            sig = s.signal(t)", "t")
sim_d1 = prepare("test_l4_10ans.py",    "            sig = s.signal(d)", "d")

res = {}
res[("H4", "ON")]  = sim_h4("L4")
res[("H4", "OFF")] = sim_h4("L4off")
res[("D1", "ON")]  = sim_d1("L4")
res[("D1", "OFF")] = sim_d1("L4", thr_force=None)

print("=== L4.2 DEPLOYE (or 2,0 + filtre dollar + pyramide 4), 10 ANS ===")
print("  %-22s | %-8s | %-16s | %-7s | %s"
      % ("Config", "CAGR", "REUSSITE challenge", "MaxDD", "Sharpe"))
print("  " + "-" * 72)
for cle, nom in ((("H4","ON"), "H4  mode challenge ON"), (("H4","OFF"), "H4  mode OFF"),
                 (("D1","ON"), "D1  mode challenge ON"), (("D1","OFF"), "D1  mode OFF")):
    r = res[cle]
    print("  %-22s | %+6.1f%% | %9.0f %%       | %+6.1f%% | %5.2f"
          % (nom, r["cagr"], 100 - r["morts"], r["dd"], r.get("sh", r.get("sharpe", 0))))
print()
print("=== RENDEMENT PAR ANNEE ===")
annees = sorted(res[("H4","ON")]["par_an"].keys())
print("  %-6s | %-10s %-10s | %-10s %-10s" % ("Annee", "H4 ON", "H4 OFF", "D1 ON", "D1 OFF"))
print("  " + "-" * 56)
for an in annees:
    print("  %-6d | %+8.1f%% %+8.1f%% | %+8.1f%% %+8.1f%%"
          % (an, res[("H4","ON")]["par_an"].get(an, 0), res[("H4","OFF")]["par_an"].get(an, 0),
             res[("D1","ON")]["par_an"].get(an, 0), res[("D1","OFF")]["par_an"].get(an, 0)))
print("  (2015 = 4 mois, 2026 = 8 mois)")
