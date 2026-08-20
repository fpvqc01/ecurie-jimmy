# -*- coding: utf-8 -*-
"""CADENCE D'EVALUATION DE CHAQUE ROBOT (demande de Jimmy) : autour de la
base REALISTE (Or H4, Nasdaq H4, Cassure H4, EMA H1, Petrole D1), on change
UN robot a la fois. Mode challenge ON, moteur H4, 10 ans.
Cadences possibles : D1 (une decision/jour), H4, H1 (BTC seulement --
donnees H1 disponibles). Les indicateurs restent JOURNALIERS partout ;
seule la frequence de decision change (comme dans les vrais robots)."""
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

def porte_d1(x):
    sig0 = x.signal
    def sig(t, x=x, sig0=sig0):
        i = x.idx.get(t)
        if i is None or not x.NEWDAY[i]: return None
        return sig0(t)
    x.signal = sig
    return x

def btc_h1(nom):
    if nom == "BTC EMA":
        return MH.EmaBTCH4("BTC EMA", BTC_H1, 0.015, 0.0004, -0.000833/4, 1.0,
                           jimmy=True, retrace=0.25, tpj=2.0)
    s = MH.DonchH4("BTC Cassure", BTC_H1, 0.015, 0.0004, -0.000833/4, 1.0)
    ns2 = {"__file__": os.path.join(D, "valide_candidats_h4.py")}
    exec(open(os.path.join(D, "valide_candidats_h4.py"), encoding="utf-8").read()
         .split("RISQUES =")[0], ns2)
    s.pyr_max = 4
    s.gerer = ns2["gerer_pyr_max"].__get__(s); s.ouvrir = MH.ouvrir_pyr.__get__(s)
    return s

# base realiste : cadences des vrais robots
BASE = {"Or": "H4", "Nasdaq": "H4", "BTC Cassure": "H4", "BTC EMA": "H1", "Petrole": "D1"}

def fabrique(cadences):
    def f():
        s = []
        for x in orig():
            if hasattr(x, "pyr_max"): x.pyr_max = 4
            cad = cadences.get(x.nom, "H4")
            if x.nom.startswith("BTC") and cad == "H1":
                x = btc_h1(x.nom)
            elif cad == "D1":
                x = porte_d1(x)
            # cad H4 = defaut du moteur
            s.append(x)
        return s
    return f

def run(cadences):
    ns["sleeves_l4"] = fabrique(cadences)
    return ns["sim_h4"](interdit=f_or)

print("%-46s | %-7s | %-9s | %-7s | %s" % ("Variante (un robot change a la fois)", "CAGR", "REUSSITE", "MaxDD", "Moities"))
print("-" * 96)
variantes = [("BASE realiste (robots actuels)", dict(BASE))]
for nom, cads in (("Or", ["D1"]), ("Nasdaq", ["D1"]),
                  ("BTC Cassure", ["H1", "D1"]), ("BTC EMA", ["H4", "D1"]),
                  ("Petrole", ["H4"])):
    for cad in cads:
        c = dict(BASE); c[nom] = cad
        variantes.append(("%s -> %s" % (nom, cad), c))
res = {}
for nom, cads in variantes:
    r = run(cads)
    res[nom] = r
    print("%-46s | %+6.1f%% | %6.0f %%  | %+6.1f%% | %+5.1f/%+5.1f%%"
          % (nom, r[0], 100-r[3], r[2], r[4], r[5]))

# combinaison des ameliorations trouvees (celles qui battent la base)
base_c = res["BASE realiste (robots actuels)"][0]
gagnants = {n.split(" -> ")[0]: n.split(" -> ")[1] for n, r in res.items()
            if " -> " in n and r[0] > base_c + 0.5}
combo = dict(BASE); combo.update(gagnants)
r = run(combo)
print("-" * 96)
print("%-46s | %+6.1f%% | %6.0f %%  | %+6.1f%% | %+5.1f/%+5.1f%%"
      % ("COMBO des gagnants : " + str(gagnants), r[0], 100-r[3], r[2], r[4], r[5]))

print()
print("=== combos prudents (sans le Nasdaq->D1 qui degrade la reussite) ===")
for nom, chg in (("C1 : Cassure H1 + Petrole H4", {"BTC Cassure": "H1", "Petrole": "H4"}),
                 ("C2 : C1 + EMA D1", {"BTC Cassure": "H1", "Petrole": "H4", "BTC EMA": "D1"}),
                 ("C3 : C2 + Nasdaq D1 (combo complet)", {"BTC Cassure": "H1", "Petrole": "H4", "BTC EMA": "D1", "Nasdaq": "D1"})):
    c = dict(BASE); c.update(chg)
    r = run(c)
    print("%-42s | %+6.1f%% | %6.0f %%  | %+6.1f%% | %+5.1f/%+5.1f%%"
          % (nom, r[0], 100-r[3], r[2], r[4], r[5]))
