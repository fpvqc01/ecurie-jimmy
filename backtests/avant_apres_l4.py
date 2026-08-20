# -*- coding: utf-8 -*-
"""AVANT/APRES : L4.2 (deploye, cadences reelles) vs L4.3-C2 propose
(Cassure H1 + Petrole H4 + EMA D1). Modes ON et OFF, H4 10 ans, par annee."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH
BTC_H1 = pd.read_csv(os.path.join(D, "d10h1_btc.csv"), index_col=0,
                     parse_dates=True)[["o","h","l","c"]].astype(float)

def moteur(thr_actif):
    src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read().split('print()')[0]
    # on recupere aussi la serie journaliere pour le par-annee
    src = src.replace("    return cagr, sh, dd, (morts/n*100 if n else 0), c1, c2",
                      "    return cagr, sh, dd, (morts/n*100 if n else 0), c1, c2, tj")
    if not thr_actif:
        src = src.replace(
            "fc = 0.75 if (len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0",
            "fc = 1.0")
    ns = {"__file__": os.path.join(D, "test_l4_macro.py")}
    exec(src, ns)
    return ns

def fabrique(ns, cadences):
    orig = ns["ORIG_SLEEVES"]
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
    def f():
        s = []
        for x in orig():
            if hasattr(x, "pyr_max"): x.pyr_max = 4
            cad = cadences.get(x.nom, "H4")
            if x.nom.startswith("BTC") and cad == "H1":
                x = btc_h1(x.nom)
            elif cad == "D1":
                x = porte_d1(x)
            s.append(x)
        return s
    return f

AVANT = {"Or": "H4", "Nasdaq": "H4", "BTC Cassure": "H4", "BTC EMA": "H1", "Petrole": "D1"}
APRES = {"Or": "H4", "Nasdaq": "H4", "BTC Cassure": "H1", "BTC EMA": "D1", "Petrole": "H4"}

series = {}
print("%-30s | %-7s | %-9s | %-7s | %s" % ("Config", "CAGR", "REUSSITE", "MaxDD", "Sharpe"))
print("-" * 72)
for mode, thr in (("ON", True), ("OFF", False)):
    ns = moteur(thr)
    ns["ORIG_SLEEVES"] = ns["sleeves_l4"]
    dxy = ns["dxy"]
    FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
    f_or = lambda n, j: n == "Or" and j in FORT
    for nom, cad in (("AVANT (L4.2 actuel)", AVANT), ("APRES (L4.3-C2)", APRES)):
        ns["sleeves_l4"] = fabrique(ns, cad)
        c, s, d, m, a1, a2, tj = ns["sim_h4"](interdit=f_or)
        series[(mode, nom)] = tj
        print("%-6s %-23s | %+6.1f%% | %6.0f %%  | %+6.1f%% | %5.2f"
              % (mode, nom, c, 100-m, d, s))
print()
print("=== PAR ANNEE (mode OFF = celui qui roule sur MT6) ===")
ta, tb = series[("OFF", "AVANT (L4.2 actuel)")], series[("OFF", "APRES (L4.3-C2)")]
print("  %-6s | %-10s | %-10s" % ("Annee", "AVANT", "APRES"))
for an in sorted({d.year for d in ta.index}):
    va = ((1+ta[ta.index.year == an]).prod()-1)*100
    vb = ((1+tb[tb.index.year == an]).prod()-1)*100
    print("  %-6d | %+8.1f%% | %+8.1f%%" % (an, va, vb))
