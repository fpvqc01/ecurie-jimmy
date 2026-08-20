# -*- coding: utf-8 -*-
"""Isolation : le gain de la variante C vient-il du vendredi ou du dimanche ?
D = dimanche seulement. E/F = voisins (jeudi seul, lundi seul) pour le
standard de stabilite : si bloquer n'importe quel jour "aide", c'est du bruit."""
import os, pandas as pd, numpy as np
from datetime import date, timedelta
d0 = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(d0, "test_vendredi.py"), encoding="utf-8").read()
exec(src.split("NOMS =")[0].replace(
    'if variante == "C": return w == 4 or w == 6',
    'if variante == "C": return w == 4 or w == 6\n'
    '    if variante == "D": return w == 6\n'
    '    if variante == "E": return w == 3\n'
    '    if variante == "F": return w == 0'))
NOMS = {"A": "A. reference", "D": "D. dimanche seulement",
        "E": "E. voisin: jeudi seulement", "F": "F. voisin: lundi seulement"}
for gen in ("I2+", "L3", "I2++", "L3+"):
    print("=== %s ===" % gen)
    for v in ("A", "D", "E", "F"):
        r = sim(gen, v)
        print("  %-28s | %+6.1f%% | Sharpe %5.2f | DD %+6.1f%% | morts %3.0f%% | %+5.1f/%+5.1f%%" %
              (NOMS[v], r[0], r[1], r[2], r[5], r[6], r[7]))
    print()
