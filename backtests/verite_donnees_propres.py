# -*- coding: utf-8 -*-
"""LA VERITE SUR DONNEES PROPRES (barres week-end purgees) :
chiffres de reference L4.3x + simulateur FTMO exact, ON et OFF."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))

for mode, thr in (("ON ", True), ("OFF", False)):
    src = open(os.path.join(D, "tests_comite_B.py"), encoding="utf-8").read()
    src = src.split("# ============ 5.")[0]
    if not thr:
        src = src.replace(
            'src = src.replace(\'if t >= pd.Timestamp("2015-08-21")]\',',
            'src = src.replace("fc = 0.75 if (len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0", "fc = 1.0")\n'
            'src = src.replace(\'if t >= pd.Timestamp("2015-08-21")]\',')
    ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
    exec(src, ns0)
    run = ns0["run"]
    for et, per in (("10 ans", ("2015-08-21", "2026-12-31")),
                    ("21-26", ("2021-01-01", "2026-08-20"))):
        r = run(*per)
        print("mode %s %-7s : CAGR %+5.1f%% | reussite %3.0f%% | DD %+6.1f%% | Sharpe %4.2f | %+5.1f/%+5.1f%%"
              % (mode, et, r[0], 100-r[3], r[2], r[1], r[4], r[5]))
    if thr:
        # simulateur FTMO exact sur la serie 10 ans mode ON
        r = run("2015-08-21", "2026-12-31")
        tj = r[6]; vals = tj.values
        def phase(i0, cible):
            eq = 1.0; jours = 0
            for i in range(i0, len(vals)):
                x = vals[i]
                if abs(x) > 1e-9: jours += 1
                if x <= -0.05: return (False, i)
                eq *= (1 + x)
                if eq <= 0.90: return (False, i)
                if eq >= 1.0 + cible and jours >= 4: return (True, i)
            return (None, len(vals)-1)
        p1 = tout = n = 0
        for i0 in range(0, len(vals) - 90, 5):
            ok1, i1 = phase(i0, 0.10)
            if ok1 is None: break
            n += 1
            if not ok1: continue
            p1 += 1
            ok2, _ = phase(i1 + 1, 0.05)
            if ok2 or ok2 is None: tout += 1
        print("   SIMULATEUR FTMO EXACT (donnees propres) : phase 1 = %.0f %%, complet = %.0f %% (%d departs)"
              % (100*p1/n, 100*tout/n, n))
