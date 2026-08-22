# -*- coding: utf-8 -*-
"""ROBUSTESSE du repli conditionnel : les voisins gagnent-ils aussi ?
Regle : on attend un repli de k ATR avant d'acheter la cassure, SAUF si la
tendance est deja forte, c'est-a-dire (prix - EMA50)/ATR >= seuil.
On charge les fonctions des bancs SANS reexecuter leurs tableaux."""
import os, sys, io
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)

def charge(nom, coupe):
    src = io.open(os.path.join(D, nom), encoding="utf-8").read().split(coupe)[0]
    ns = {"__file__": os.path.join(D, nom), "__name__": "x"}
    exec(src, ns)
    return ns

R = charge("banc_repli.py", "FEN = (")
C = charge("banc_repli_conditionnel.py", "FEN = R.FEN")
FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
CIBLES, mesure = R["CIBLES"], R["mesure"]
cond = C["repli_conditionnel"]

print("=== ROBUSTESSE DU REPLI CONDITIONNEL (chassis L6 + R13) ===")
print("   on attend un repli de k ATR, SAUF si (prix - EMA50)/ATR >= seuil")
print("%-32s | %-30s | %s" % ("", "10 ANS", "2021-2026"))
print("%-32s | %7s %8s %6s %7s | %8s %6s"
      % ("configuration", "CAGR", "reussite", "duree", "DD", "reussite", "duree"))
print("-" * 94)
l = "%-32s |" % "reference (achat de la cassure)"
for idx, (e, d0, f0) in enumerate(FEN):
    tr, cagr, o, m, dd = mesure(0.025, None, 1.00, None, d0, f0)
    l += (" %+6.1f %% %6.0f %% %4.0f j %+6.1f %% |" if idx == 0 else " %6.0f %% %4.0f j") % (
        (cagr, o, m, dd) if idx == 0 else (o, m))
print(l)
for k in (0.75, 1.00, 1.25):
    for seuil in (0.5, 1.0, 1.5):
        meca = (lambda kk, zz: (lambda sl: [cond(s, kk, 5, zz) for s in sl if s.nom in CIBLES]))(k, seuil)
        l = "%-32s |" % ("k = %.2f ATR / force >= %.1f" % (k, seuil))
        for idx, (e, d0, f0) in enumerate(FEN):
            tr, cagr, o, m, dd = mesure(0.025, meca, 1.00, None, d0, f0)
            if idx == 0: l += " %+6.1f %% %6.0f %% %4.0f j %+6.1f %% |" % (cagr, o, m, dd)
            else:        l += " %6.0f %% %4.0f j" % (o, m)
        print(l)
