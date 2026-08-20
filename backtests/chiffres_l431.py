# -*- coding: utf-8 -*-
"""L4.31 (tampon 0,25) vs L4.3 : ON et OFF, 10 ans + 2021-2026."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH
BTC_H1 = pd.read_csv(os.path.join(D, "d10h1_btc.csv"), index_col=0,
                     parse_dates=True)[["o","h","l","c"]].astype(float)

for mode, thr in (("ON", True), ("OFF", False)):
    src = open(os.path.join(D, "test_l43_realiste.py"), encoding="utf-8").read().split("BASE =")[0]
    if not thr:
        src = src.replace('src = src.replace(\'if t >= pd.Timestamp("2015-08-21")]\',',
                          'src = src.replace("fc = 0.75 if (len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0", "fc = 1.0")\n    src = src.replace(\'if t >= pd.Timestamp("2015-08-21")]\',')
    ns0 = {"__file__": os.path.join(D, "test_l43_realiste.py")}
    exec(src, ns0)
    ns, fabrique = ns0["ns"], ns0["fabrique"]
    dxy = ns["dxy"]
    FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
    f_or = lambda n, j: n == "Or" and j in FORT
    C2 = {"Or": "H4", "Nasdaq": "H4", "BTC Cassure": "H1", "BTC EMA": "D1", "Petrole": "H4"}
    def tampon(s, pct=0.0025):
        sig0 = s.signal
        def sig(t, s=s, sig0=sig0):
            r = sig0(t)
            if r is None: return None
            k = s.KPREV[s.idx.get(t)]
            if r["entree"] <= s.H20J[k] * (1 + pct): return None
            return r
        s.signal = sig
        return s
    def var(avec):
        base = fabrique(C2)
        def f():
            sl = base()
            if avec:
                for s in sl:
                    if s.nom in ("BTC Cassure", "Petrole"): tampon(s)
            return sl
        return f
    for nomv, avec in (("L4.3 (avant)", False), ("L4.31 (maintenant)", True)):
        ligne = "  mode %-3s %-20s" % (mode, nomv)
        for et, per in (("10 ans", ("2015-08-21", "2026-12-31")),
                        ("21-26", ("2021-01-01", "2026-08-20"))):
            ns["DEBUT"], ns["FIN"] = per
            ns["sleeves_l4"] = var(avec)
            r = ns["sim_h4"](interdit=f_or)
            ligne += " | %s : %+5.1f%% / %3.0f%%" % (et, r[0], 100-r[3])
        print(ligne)
