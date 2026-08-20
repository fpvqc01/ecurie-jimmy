# -*- coding: utf-8 -*-
"""Pourquoi L3 fait +12,5 % en H4 contre +33,8 % en journalier sur LA MEME
fenetre de 2 ans ? Decomposition par manche : trades, PnL cumule, coupes."""
import os, pandas as pd, numpy as np
import moteur_h4 as M

def detail_h4(gen):
    sleeves = M.construire(gen)
    garde = -0.035 if gen == "I2+" else -0.025
    corr = gen in ("I2++", "L3+")
    ts = [t for t in sorted(set().union(*[set(s.index) for s in sleeves])) if t >= pd.Timestamp('2024-08-21')]
    jour_pnl, jour_cour, jour_stop, coupes = 0.0, None, False, 0
    for t in ts:
        j = t.date()
        if j != jour_cour: jour_cour, jour_pnl, jour_stop = j, 0.0, False
        avant = [s.pnl.get(t, 0) for s in sleeves]
        for s in sleeves: s.gerer(t)
        jour_pnl += sum(s.pnl.get(t, 0) - avant[q] for q, s in enumerate(sleeves))
        if jour_stop: continue
        if jour_pnl <= garde:
            av3 = [s.pnl.get(t, 0) for s in sleeves]
            for s in sleeves:
                if s.pos is not None:
                    i = s.idx.get(t)
                    if i is not None: s._clore(t, s.C[i])
                s.attente = None
            jour_pnl += sum(s.pnl.get(t, 0) - av3[q] for q, s in enumerate(sleeves))
            jour_stop = True; coupes += 1; continue
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        familles = {M.FAM[s.nom] for s in sleeves if s.pos is not None}
        for s in sleeves:
            if s.pos is not None or ouverts >= 2: continue
            if corr and M.FAM[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(t)
            if sig is None: continue
            av2 = s.pnl.get(t, 0)
            if s.ouvrir(t, **sig):
                jour_pnl += s.pnl.get(t, 0) - av2
                ouverts += 1; familles.add(M.FAM[s.nom])
    print("  H4 / %s : %d coupes de gardien" % (gen, coupes))
    for s in sleeves:
        print("    %-12s : %3d trades, PnL cumule %+7.1f %%" % (s.nom, s.trades, sum(s.pnl.values())*100))

# meme decomposition avec le moteur JOURNALIER sur la meme fenetre
d0 = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(d0, "test_vendredi.py"), encoding="utf-8").read().split("NOMS =")[0]
src = src.replace("dates = sorted(set().union(*[s.df.index for s in sleeves]))",
                  "dates = [d for d in sorted(set().union(*[s.df.index for s in sleeves]))"
                  " if d >= pd.Timestamp('2024-08-21')]")
src = src.replace("    if trace: return entrees",
                  "    if trace:\n"
                  "        print('  JOURNALIER / %s : %d coupes' % (gen, coupes))\n"
                  "        for s in sleeves:\n"
                  "            print('    %-12s : %3d trades, PnL cumule %+7.1f %%' % (s.nom, s.trades, sum(s.pnl.values())*100))\n"
                  "        return entrees")
ns = {"__file__": os.path.join(d0, "test_vendredi.py")}
exec(src, ns)
for gen in ("L3", "I2+"):
    ns["sim"](gen, "A", trace=True)
    detail_h4(gen)
    print()
