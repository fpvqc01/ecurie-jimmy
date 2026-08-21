# -*- coding: utf-8 -*-
"""Pourquoi ca semblait plus vite avant : duree de la PHASE 1 seule
(l'ancien chiffre cite ~80 jours) vs les 2 phases, donnees propres,
et comparaison avec les donnees SALES (barres week-end) qui gonflaient
la vitesse. Config L6 (a x0,75)."""
import os, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "options_optimisation.py"), encoding="utf-8").read()
src = src.split("OPTIONS = [")[0]
ns0 = {"__file__": os.path.join(D, "options_optimisation.py")}
exec(src, ns0)
ns, fab_option, f_or = ns0["ns"], ns0["fab_option"], ns0["f_or"]
ALLOC = {"Or": 0.0075, "Nasdaq": 0.0075, "Petrole": 0.0169,
         "BTC Cassure": 0.0169, "BTC EMA": 0.0113}
def a075(sl):
    for s in sl:
        if s.nom in ALLOC: s.risque = ALLOC[s.nom]

def phase(vals, i0, cible):
    eq = 1.0; jt = 0
    for j in range(i0, len(vals)):
        r = vals[j]
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j - i0 + 1
        eq *= (1 + r)
        if eq <= 0.90: return 0, j - i0 + 1
        if eq >= 1 + cible and jt >= 4: return 1, j - i0 + 1
    return -1, len(vals) - i0

def stats(vals, mult=1.0):
    v = vals * mult
    d1s, d2s, dtot, m = [], [], [], 0
    for i0 in range(0, len(v) - 60, 3):
        v1, d1 = phase(v, i0, 0.10)
        if v1 == -1: continue
        if v1 == 0: m += 1; continue
        d1s.append(d1)
        v2, d2 = phase(v, i0 + d1, 0.05)
        if v2 == -1: continue
        if v2 == 0: m += 1; continue
        d2s.append(d2); dtot.append(d1 + d2)
    n = len(dtot) + m
    return (100.0 * len(dtot) / max(n, 1), np.median(d1s) if d1s else 0,
            np.median(d2s) if d2s else 0, np.median(dtot) if dtot else 0)

ns["DEBUT"], ns["FIN"] = "2015-08-21", "2026-12-31"
ns["sleeves_l4"] = fab_option(a075)
r = ns["sim_h4"](interdit=f_or)
vals = r[6].sort_index().values

for nom, mult in (("L6 risque normal (x1,0)", 1.0),
                  ("L6 accelere (x1,33, gardien fixe simule)", 1.33)):
    ok, d1, d2, dt = stats(vals, mult)
    print("%-42s : reussite %3.0f %% | phase 1 mediane %3.0f j | phase 2 %3.0f j | TOTAL %3.0f j"
          % (nom, ok, d1, d2, dt))
