# -*- coding: utf-8 -*-
"""ALTERNATIVE E : selection par ROBUSTESSE plutot que par profit.
Un candidat n'est retenu que si sa contribution marginale au noyau L4.3
est POSITIVE sur DEUX sous-fenetres independantes (2021-2022 ET 2023),
pas juste sur le total. Validation 2024-2026, comme les autres."""
import pandas as pd, numpy as np

src = open("test_l43_alternatives.py", encoding="utf-8").read().split('FIN_SEL, DEBUT_VAL')[0]
ns = {"__file__": "test_l43_alternatives.py"}; exec(src, ns)
sim, DATA = ns["sim"], ns["DATA"]

print("=== SELECTION PAR ROBUSTESSE (positif sur 2021-2022 ET sur 2023) ===")
b1 = sim([], fin="2022-12-31")[0]
b2 = sim([], debut="2023-01-01", fin="2023-12-31")[0]
print("Noyau seul : 2021-2022 %+5.1f%% | 2023 %+5.1f%%" % (b1, b2))
robustes = []
for nom in sorted(DATA):
    d1 = sim([nom], fin="2022-12-31")[0] - b1
    d2 = sim([nom], debut="2023-01-01", fin="2023-12-31")[0] - b2
    if d1 > 0 and d2 > 0:
        robustes.append((nom, d1, d2))
robustes.sort(key=lambda x: -min(x[1], x[2]))
print("Candidats positifs sur LES DEUX sous-fenetres :")
for nom, d1, d2 in robustes:
    print("  %-12s 2021-22 %+5.1f | 2023 %+5.1f pts" % (nom, d1, d2))
SEL = [n for n, _, _ in robustes]

print()
print("=== VALIDATION 2024-2026 ===")
for titre, kw in (("Noyau L4.3 seul (reference)", dict(ajouts=[])),
                  ("E. noyau + robustes (cap 2)", dict(ajouts=SEL)),
                  ("E'. noyau + robustes (cap 3)", dict(ajouts=SEL, cap=3)),
                  ("E''. noyau + robustes 0,75 % cap 3", dict(ajouts=SEL, risque_ajout=0.0075, cap=3))):
    cv, dv, mv = sim(debut="2024-01-01", **kw)
    cp, dp, mp = sim(**kw)
    print("  %-36s | val: %+5.1f%% %+6.1f%% %3.0f%% | 5 ans: %+5.1f%% %+6.1f%% %3.0f%%"
          % (titre, cv, dv, mv, cp, dp, mp))
