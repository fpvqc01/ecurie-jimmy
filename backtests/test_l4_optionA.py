# -*- coding: utf-8 -*-
"""L4.2 + OPTION A (allocation inverse-volatilite), la decouverte de la
nuit du 19-20 pas encore implementee. Principe : le risque de chaque
manche est module par (vol mediane des marches / vol du marche), borne --
un marche calme recoit plus, un marche agite recoit moins ; la contribution
de risque s'egalise (risk parity dynamique, Bridgewater).
Variantes (H4 10 ans, config L4.2 : pyr4 + filtre dollar) :
  A. reference L4.2
  B. option A bornes 0,5-2,0, fenetre 60 j
  C. voisin bornes 0,75-1,5
  D. voisin fenetre 90 j
Contre-verification D1 10 ans pour la gagnante."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))

def charge(nom):
    return pd.read_csv(os.path.join(D, "d10h4_%s.csv" % nom), index_col=0,
                       parse_dates=True)["c"].resample("1D").last().dropna()
CLOT = {"Or": charge("gc"), "Petrole": charge("cl"), "Nasdaq": charge("nq"),
        "BTC Cassure": charge("btc"), "BTC EMA": charge("btc")}

def table_facteurs(fenetre, lo, hi):
    vols = pd.DataFrame({n: s.pct_change().rolling(fenetre).std() for n, s in CLOT.items()})
    vols = vols.shift(1)                       # seulement l'info d'hier
    cible = vols.median(axis=1)
    fact = (cible.values[:, None] / vols.values)
    fact = pd.DataFrame(np.clip(fact, lo, hi), index=vols.index, columns=vols.columns)
    return {n: fact[n].dropna().to_dict() for n in fact.columns}, fact

# ---- moteur H4 patche : risque module par FACT ----
src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read().split('print()')[0]
src = src.replace("            r0 = s.risque; s.risque = r0*fc",
                  "            r0 = s.risque; s.risque = r0*fc*FACT(s.nom, t)")
ns = {"__file__": os.path.join(D, "test_l4_macro.py"), "FACT": lambda n, t: 1.0}
exec(src, ns)
dxy = ns["dxy"]
FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
f_or = lambda n, j: n == "Or" and j in FORT

orig = ns["sleeves_l4"]
def sl4():
    s = orig()
    for x in s:
        if hasattr(x, "pyr_max"): x.pyr_max = 4
    return s
ns["sleeves_l4"] = sl4

def fact_fn(dico):
    def F(nom, t):
        d = pd.Timestamp(t.date())
        v = dico.get(nom, {}).get(d)
        return float(v) if v is not None and not np.isnan(v) else 1.0
    return F

print("=== L4.2 + OPTION A inverse-volatilite (H4, 10 ans) ===")
print("  %-40s | %-7s | %-6s | %-7s | %-5s | %s" % ("Variante", "CAGR", "Sharpe", "MaxDD", "Morts", "Moities"))
print("  " + "-" * 88)
resultats = {}
for nom, params in (("A. reference L4.2", None),
                    ("B. option A (0,5-2,0 ; 60 j)", (60, 0.5, 2.0)),
                    ("C. voisin bornes 0,75-1,5", (60, 0.75, 1.5)),
                    ("D. voisin fenetre 90 j", (90, 0.5, 2.0))):
    if params is None:
        ns["FACT"] = lambda n, t: 1.0
    else:
        dico, _ = table_facteurs(*params)
        ns["FACT"] = fact_fn(dico)
    c, s, d, m, a1, a2 = ns["sim_h4"](interdit=f_or)
    resultats[nom] = (c, m)
    print("  %-40s | %+6.1f%% | %6.2f | %+6.1f%% | %4.0f%% | %+5.1f/%+5.1f%%"
          % (nom, c, s, d, m, a1, a2))

# ---- contre-verification D1 (variante B) ----
print()
print("=== contre-verification D1 10 ans (option A 0,5-2,0 ; 60 j) ===")
dico, _ = table_facteurs(60, 0.5, 2.0)
FACT_D1 = fact_fn(dico)
src2 = open(os.path.join(D, "test_l4_10ans.py"), encoding="utf-8").read().split("CONFIGS =")[0]
src2 = src2.replace("s.pyr_max = 3", "s.pyr_max = 4")
src2 = src2.replace("            sig = s.signal(d)",
                    "            if s.nom == 'Or' and d.date() in FORT200: continue\n"
                    "            sig = s.signal(d)")
src2 = src2.replace("            r0 = s.risque; s.risque = r0*fc",
                    "            r0 = s.risque; s.risque = r0*fc*FACT_D1(s.nom, d)")
dxy_d = pd.read_csv(os.path.join(D, "d10_dxy.csv"), index_col=0, parse_dates=True)["c"]
FORT200 = set(dxy_d.index[(dxy_d > dxy_d.ewm(span=200, adjust=False).mean())].date)
ns2 = {"__file__": os.path.join(D, "test_l4_10ans.py"), "FORT200": FORT200, "FACT_D1": FACT_D1}
exec(src2, ns2)
r = ns2["sim10"]("L4")
print("  avec option A : CAGR %+5.1f%% | morts %3.0f%% | moities %+5.1f/%+5.1f%%"
      % (r["cagr"], r["morts"], r["m1"], r["m2"]))
ns2["FACT_D1"] = lambda n, d: 1.0
r0 = ns2["sim10"]("L4")
print("  reference     : CAGR %+5.1f%% | morts %3.0f%% | moities %+5.1f/%+5.1f%%"
      % (r0["cagr"], r0["morts"], r0["m1"], r0["m2"]))
