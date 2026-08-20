# -*- coding: utf-8 -*-
"""AVANT/APRES les optimisations du comite : L4.31 vs L4.31 + chandelier
K=4 + espacement 0,75 ATR. Modes ON/OFF, 10 ans + 2021-2026, avec l'effet
sur la queue de risque (somme par jour des risques-au-stop des manches)."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))

SONDE = {}   # t -> risque agrege
def sonde(s):
    gerer0 = s.gerer
    def gerer(t):
        gerer0(t)
        if t.hour == 0 and s.pos is not None:
            p = s.pos
            SONDE[t] = SONDE.get(t, 0.0) + p["n"] * max(p.get("prix", p["e"]) - p["s"], 0) / p["e"]
    s.gerer = gerer
    return s

def moteur(thr):
    src = open(os.path.join(D, "tests_comite_B.py"), encoding="utf-8").read()
    src = src.split("# ============ 5.")[0]
    if not thr:
        src = src.replace(
            'src = src.replace(\'if t >= pd.Timestamp("2015-08-21")]\',',
            'src = src.replace("fc = 0.75 if (len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0", "fc = 1.0")\n'
            'src = src.replace(\'if t >= pd.Timestamp("2015-08-21")]\',')
    ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
    exec(src, ns0)
    return ns0

for mode, thr in (("ON ", True), ("OFF", False)):
    ns0 = moteur(thr)
    chand, esp, run = ns0["chandelier"], ns0["espace"], ns0["run"]
    def avant(s): sonde(s)
    def apres(s): chand(s, 4); esp(s, 0.75); sonde(s)
    for etiquette, per in (("10 ans", ("2015-08-21", "2026-12-31")),
                           ("21-26", ("2021-01-01", "2026-08-20"))):
        for nom, mods in (("AVANT", avant), ("APRES", apres)):
            SONDE.clear()
            r = run(*per, mods=mods)
            rs = pd.Series(list(SONDE.values())) if SONDE else pd.Series([0.0])
            print("mode %s %-7s %-6s : %+5.1f%% | reussite %3.0f%% | DD %+6.1f%% | risque-stop p95 %4.1f%%  max %5.1f%%"
                  % (mode, etiquette, nom, r[0], 100-r[3], r[2],
                     rs.quantile(0.95)*100, rs.max()*100))
    print()
