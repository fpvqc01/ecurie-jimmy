# -*- coding: utf-8 -*-
"""ROBUSTESSE de la trouvaille : L11 + repli conditionnel + turbo.
Le repli corrige exactement ce que le turbo casse (entrer trop haut avec trop
de taille). On verifie que le gain n'est pas un pic isole : balayage du
multiplicateur et du coussin."""
import os, sys, io
import numpy as np
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
V = {"__file__": os.path.join(D, "course_vitesse.py"), "__name__": "x"}
src = io.open(os.path.join(D, "course_vitesse.py"), encoding="utf-8").read().split("CAND = [")[0]
exec(src, V)
S, FEN, bilan = V["S"], V["FEN"], V["bilan"]

print()
print("=== ROBUSTESSE : L11 + repli + turbo (les voisins gagnent-ils ?) ===")
for e, _, _ in FEN:
    print()
    print("--- %s ---" % e.strip())
    print("%-32s | %7s %6s | %9s %8s" % ("reglage du turbo", "reuss.", "duree", "JOURS", "FRAIS"))
    print("-" * 68)
    for mult, cou, etq in ((1.00, None, "sans turbo"),
                           (1.15, 0.04, "x1,15 jusqu'a +4 %"),
                           (1.25, 0.04, "x1,25 jusqu'a +4 %"),
                           (1.33, 0.03, "x1,33 jusqu'a +3 %"),
                           (1.33, 0.04, "x1,33 jusqu'a +4 %"),
                           (1.33, 0.06, "x1,33 jusqu'a +6 %"),
                           (1.33, None, "x1,33 permanent"),
                           (1.50, 0.04, "x1,50 jusqu'a +4 %"),
                           (1.75, 0.04, "x1,75 jusqu'a +4 %")):
        b = bilan(S[("L11r", e)][2], mult, cou)
        print("%-32s | %6.0f %% %5.0f j | %7.0f j %6.0f EUR"
              % (etq, b["p"], b["med"], b["jours"], b["frais"]))
