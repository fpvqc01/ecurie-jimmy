# -*- coding: utf-8 -*-
"""COMPARATIF DES 3 ECURIES L6 (demande Jimmy, 21 aout) :
rendement annuel + taux de reussite du challenge, sur les 2 fenetres.

  L6      = alloc a x0,75 + garde vendredi + EMA 08:00 (EN SERVICE MT6)
  L6+     = L6 + turbo-coussin (x1,33 jusqu'a +4 % de la phase)  (MT5)
  L6++    = L6 + breakeven collectif (seuils 5 % et 6 %)   (en reserve)
  L6++ T  = L6++ avec le turbo REMIS a true (combinaison jamais testee)

Note honnete : le turbo ne s'applique qu'au debut d'une phase (jusqu'au
coussin de +4 %), donc il ne change PAS le rendement annuel long terme —
son effet se mesure dans le simulateur de challenge, pas dans le CAGR.
Simulateur FTMO exact : +10 % puis +5 %, -5 %/jour, -10 % total,
min 4 jours par phase, departs glissants tous les 3 jours."""
import os, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "banc_giveback.py"), encoding="utf-8").read().split("VARIANTES = [")[0]
ns0 = {"__file__": os.path.join(D, "banc_giveback.py")}
exec(src, ns0)
ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab"]
breakeven_collectif, PYR = ns0["breakeven_collectif"], ns0["PYR"]

def phase(vals, i0, cible, mult=1.0, turbo=None):
    eq = 1.0; jt = 0
    for j in range(i0, len(vals)):
        m = mult
        if turbo and eq >= 1 + turbo: m = 1.0
        r = vals[j] * m
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j - i0 + 1
        eq *= (1 + r)
        if eq <= 0.90: return 0, j - i0 + 1
        if eq >= 1 + cible and jt >= 4: return 1, j - i0 + 1
    return -1, len(vals) - i0

def ftmo(tj, mult=1.0, turbo=None):
    vals = tj.values
    complets = morts = p1 = 0; durees = []
    for i0 in range(0, len(vals) - 60, 3):
        v1, d1 = phase(vals, i0, 0.10, mult, turbo)
        if v1 == -1: continue
        if v1 == 0: morts += 1; continue
        p1 += 1
        v2, d2 = phase(vals, i0 + d1, 0.05, mult, turbo)
        if v2 == -1: continue
        if v2 == 0: morts += 1; continue
        complets += 1; durees.append(d1 + d2)
    n = complets + morts
    return (100.0 * complets / max(n, 1), np.median(durees) if durees else 0)

def serie(post, debut, fin):
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = fab(post)
    r = ns["sim_h4"](interdit=f_or)
    return r[0], r[2], r[6].sort_index()

BE5 = lambda sl: [breakeven_collectif(s, 0.05) for s in sl if s.nom in PYR]
BE6 = lambda sl: [breakeven_collectif(s, 0.06) for s in sl if s.nom in PYR]

for etiquette, debut, fin in (("10 ANS (2015-2026)", "2015-08-21", "2026-12-31"),
                              ("2021-2026 (marche recent)", "2021-01-01", "2026-08-20")):
    print()
    print("=== %s ===" % etiquette)
    print("%-34s | %9s | %9s | %7s | %8s" % ("ECURIE", "RENDEMENT", "REUSSITE", "DUREE", "DD max"))
    print("-" * 82)
    cagr0, dd0, tj0 = serie(None, debut, fin)     # base L6
    cagr5, dd5, tj5 = serie(BE5, debut, fin)      # L6++ seuil 5
    cagr6, dd6, tj6 = serie(BE6, debut, fin)      # L6++ seuil 6
    lignes = [
        ("L6  (en service MT6)",            cagr0, dd0, tj0, 1.0,  None),
        ("L6+ turbo (en service MT5)",      cagr0, dd0, tj0, 1.33, 0.04),
        ("L6++ breakeven 5 % (defaut)",     cagr5, dd5, tj5, 1.0,  None),
        ("L6++ breakeven 6 %",              cagr6, dd6, tj6, 1.0,  None),
        ("L6++ 5 % + turbo ON (non teste)", cagr5, dd5, tj5, 1.33, 0.04),
        ("L6++ 6 % + turbo ON (non teste)", cagr6, dd6, tj6, 1.33, 0.04),
    ]
    for nom, cagr, dd, tj, mult, turbo in lignes:
        ok, med = ftmo(tj, mult, turbo)
        etoile = " *" if turbo else "  "
        print("%-34s | %+7.1f %%%s| %7.0f %% | %4.0f j | %+6.1f %%" % (nom, cagr, etoile, ok, med, dd))
    print("  * le turbo n'agit qu'au debut de chaque phase : le rendement annuel affiche est celui de sa base")
