# -*- coding: utf-8 -*-
"""L4.3 CONTRE TOUTES LES ECURIES (moteur H4 realiste, 10 ans + 2021-2026).
Chaque generation avec SA config exacte et les cadences REELLES des robots
(EMA H1, petrole D1) ; L4.3 avec ses cadences optimisees (Cassure H1,
Petrole H4, EMA D1). Filtre dollar : L4.x seulement."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH
BTC_H1 = pd.read_csv(os.path.join(D, "d10h1_btc.csv"), index_col=0,
                     parse_dates=True)[["o","h","l","c"]].astype(float)
dxy = pd.read_csv(os.path.join(D, "d10_dxy.csv"), index_col=0, parse_dates=True)["c"]
FORT200 = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)

src = open(os.path.join(D, "test_l4_h4_10ans.py"), encoding="utf-8").read().split("NOMS =")[0]
src = src.replace("s.pyr_max = 3", "s.pyr_max = PYRMAX")
src = src.replace('if t >= pd.Timestamp("2015-08-21")]',
                  'if t >= pd.Timestamp(DEBUT) and t <= pd.Timestamp(FIN)]')
src = src.replace("    sl = sleeves(gen)", "    sl = ADAPT(sleeves(gen))")
src = src.replace("            sig = s.signal(t)",
                  "            if FILTRE_OR and s.nom == 'Or' and t.date() in FORT200: continue\n"
                  "            sig = s.signal(t)")
ns = {"__file__": os.path.join(D, "test_l4_h4_10ans.py"), "PYRMAX": 3,
      "DEBUT": "2015-08-21", "FIN": "2026-12-31", "FILTRE_OR": False,
      "FORT200": FORT200, "ADAPT": lambda sl: sl}
exec(src, ns)

NS2 = {"__file__": os.path.join(D, "valide_candidats_h4.py")}
exec(open(os.path.join(D, "valide_candidats_h4.py"), encoding="utf-8").read()
     .split("RISQUES =")[0], NS2)

def porte_d1(x):
    sig0 = x.signal
    def sig(t, x=x, sig0=sig0):
        i = x.idx.get(t)
        if i is None or not x.NEWDAY[i]: return None
        return sig0(t)
    x.signal = sig
    return x

def adapt_fab(cadences):
    def adapt(sl):
        out = []
        for x in sl:
            cad = cadences.get(x.nom, "H4")
            if x.nom == "BTC EMA" and cad == "H1":
                x = MH.EmaBTCH4("BTC EMA", BTC_H1, x.risque, 0.0004, -0.000833/4, 1.0,
                                jimmy=True, retrace=0.25, tpj=2.0)
            elif x.nom == "BTC Cassure" and cad == "H1":
                pyr = hasattr(x, "pyr_max")
                y = MH.DonchH4("BTC Cassure", BTC_H1, x.risque, 0.0004, -0.000833/4, 1.0)
                if pyr:
                    y.pyr_max = x.pyr_max
                    y.gerer = NS2["gerer_pyr_max"].__get__(y); y.ouvrir = MH.ouvrir_pyr.__get__(y)
                x = y
            elif cad == "D1":
                x = porte_d1(x)
            out.append(x)
        return out
    return adapt

REEL = {"BTC EMA": "H1", "Petrole": "D1"}                      # cadences des vrais robots
C2   = {"BTC Cassure": "H1", "BTC EMA": "D1", "Petrole": "H4"} # L4.3

ECURIES = [
    ("I2+  (MT5 FTMO)",        "I2+",   3, False, REEL),
    ("L3   (MT4 FTMO)",        "L3",    3, False, REEL),
    ("L3+  (jamais deployee)", "L3+",   3, False, REEL),
    ("L4.2 (MT6, mode ON)",    "L4",    4, True,  REEL),
    ("L4.2 (MT6, mode OFF)",   "L4off", 4, True,  REEL),
    ("L4.3 (mode ON)",         "L4",    4, True,  C2),
    ("L4.3 (mode OFF)",        "L4off", 4, True,  C2),
]
print("%-24s | %-19s | %-19s" % ("Ecurie", "10 ANS", "2021-2026 (difficile)"))
print("%-24s | %-7s %-9s | %-7s %-9s" % ("", "CAGR", "Reussite", "CAGR", "Reussite"))
print("-" * 78)
for nom, gen, pyrmax, filtre, cad in ECURIES:
    ns["PYRMAX"], ns["FILTRE_OR"], ns["ADAPT"] = pyrmax, filtre, adapt_fab(cad)
    ns["DEBUT"], ns["FIN"] = "2015-08-21", "2026-12-31"
    r10 = ns["sim10"](gen)
    ns["DEBUT"], ns["FIN"] = "2021-01-01", "2026-08-20"
    r5 = ns["sim10"](gen)
    print("%-24s | %+6.1f%% %5.0f %%   | %+6.1f%% %5.0f %%"
          % (nom, r10["cagr"], 100-r10["morts"], r5["cagr"], 100-r5["morts"]))
