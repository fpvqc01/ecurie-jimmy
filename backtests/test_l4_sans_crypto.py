# -*- coding: utf-8 -*-
"""COMPLEMENT : L4 sans les manches crypto (OR+PETROLE+NASDAQ), config L4
telle quelle (gardien 2,5 % + mode challenge). Les 3 marches existent en
CFD chez OANDA. Comparaison avec or+nasdaq et le L4 complet."""
import pandas as pd, numpy as np

src = open("combo_l4.py", encoding="utf-8").read().split("MARCHES = (")[0]
src = src.replace("return metriques(tj.clip(lower=garde))",
                  "return metriques(tj.clip(lower=garde)) + (tj.clip(lower=garde),)")
src = src.replace("return metriques(tj)", "return metriques(tj) + (tj,)")
ns = {"__file__": "combo_l4.py"}
exec(src, ns)

def maxdd(tj):
    eq = (1 + tj).cumprod()
    return ((eq / eq.cummax()) - 1).min() * 100

print("=== L4 SANS CRYPTO : OR + PETROLE + NASDAQ (config L4 complete) ===")
c1, m1, a1, b1, t1 = ns["sim_1d"](("Or", "Petrole", "Nasdaq"))
c2, m2, a2, b2, t2 = ns["sim_h4"](("Or", "Petrole", "Nasdaq"))
print("1d 5 ans : CAGR %+5.1f%% | MaxDD %+5.1f%% | Morts %2.0f%% | moities %+5.1f/%+5.1f%%"
      % (c1, maxdd(t1), m1, a1, b1))
print("H4 2 ans : CAGR %+5.1f%% | MaxDD %+5.1f%% | Morts %2.0f%%" % (c2, maxdd(t2), m2))
print()
print("Par annee (1d) :")
for an in sorted({d.year for d in t1.index}):
    v = ((1 + t1[t1.index.year == an]).prod() - 1) * 100
    print("  %d : %+6.1f%%" % (an, v))
