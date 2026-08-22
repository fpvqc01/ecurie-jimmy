# -*- coding: utf-8 -*-
"""COMPTE 200 k AVEC LE RISQUE D'UN 100 k (question de Jimmy, 21 aout).

L'idee : prendre un compte FTMO de 200 000 $ mais risquer le meme montant en
DOLLARS que sur un 100 000 $. Le risque par trade passe donc de 1,69 % a
0,845 % du compte, etc.

CE QUE CA FAIT VRAIMENT. Les trois regles FTMO sont en POURCENTAGE du compte :
objectif +10 %, perte max -5 %/jour, perte max -10 % au total. Si on double
le compte sans doubler la mise, tout le rendement en % est divise par deux,
mais l'objectif reste a +10 % et les limites restent a -5 % et -10 %.

C'est donc EXACTEMENT equivalent a garder un compte de 100 k et multiplier
toutes les mises par 0,50. On peut donc le mesurer directement.

On balaye le multiplicateur global g, applique PAR-DESSUS le turbo :
   mise effective = g x (1,33 si la phase est sous +4 %, sinon 1,00)
g = 1,00 -> compte 100 k, mise normale
g = 0,50 -> compte 200 k, meme mise en dollars qu'un 100 k
g = 0,25 -> compte 400 k, meme mise en dollars qu'un 100 k"""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B

def serie(garde, be, deb, fin):
    ns0 = B.charger(garde)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in B.ALLOC: s.risque = B.ALLOC[s.nom]
        if be:
            for s in sl:
                if s.nom in B.PYR: B.breakeven(s, be)
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    return r[0], r[2], r[6].sort_index()

def phase(v, i0, cible, g, turbo):
    eq = 1.0; jt = 0
    for j in range(i0, len(v)):
        m = g * (1.33 if (turbo and eq < 1.04) else 1.0)
        r = v[j] * m
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j-i0+1, "jour"
        eq *= (1 + r)
        if eq <= 0.90: return 0, j-i0+1, "total"
        if eq >= 1 + cible and jt >= 4: return 1, j-i0+1, None
    return -1, len(v)-i0, None

def ftmo(tj, g, turbo):
    v = tj.values; ok = mj = mt = 0; d = []
    for i0 in range(0, len(v)-60, 3):
        v1, d1, c1 = phase(v, i0, 0.10, g, turbo)
        if v1 == -1: continue
        if v1 == 0: mj += (c1=="jour"); mt += (c1=="total"); continue
        v2, d2, c2 = phase(v, i0+d1, 0.05, g, turbo)
        if v2 == -1: continue
        if v2 == 0: mj += (c2=="jour"); mt += (c2=="total"); continue
        ok += 1; d.append(d1+d2)
    n = ok+mj+mt
    return 100.0*ok/max(n,1), (np.median(d) if d else 0), 100.0*mj/max(n,1), 100.0*mt/max(n,1)

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
S = {e: serie(0.025, None, d, f) for e, d, f in FEN}   # chassis L6, celui de L6+

TAILLES = ((1.00, "100 k  (mise normale)"), (0.67, "150 k  (meme $ qu'un 100 k)"),
           (0.50, "200 k  (meme $ qu'un 100 k)"), (0.25, "400 k  (meme $ qu'un 100 k)"))

for turbo, nom in ((True, "L6+ (avec turbo)"), (False, "L6 (sans turbo)")):
    print(); print("=== %s + fermeture a +10 %% ===" % nom)
    print("%-30s | %-28s | %s" % ("", "10 ANS", "2021-2026"))
    print("%-30s | %8s %6s %9s | %8s %6s"
          % ("taille du compte", "reussite", "duree", "mort -5%j", "reussite", "duree"))
    print("-" * 86)
    for g, etq in TAILLES:
        l = "%-30s |" % etq
        for k, (e, _, _) in enumerate(FEN):
            o, m, mj, mt = ftmo(S[e][2], g, turbo)
            if k == 0: l += " %7.0f %% %4.0f j %8.0f %% |" % (o, m, mj)
            else:      l += " %7.0f %% %4.0f j" % (o, m)
        print(l)

# ---- le vrai critere : combien de capital finance par jour d'attente ----
print()
print("=== CE QUI COMPTE VRAIMENT : capital finance par jour de challenge ===")
print("(esperance = taille x taux de reussite, divisee par la duree mediane)")
print("%-30s | %-24s | %s" % ("", "10 ANS", "2021-2026"))
print("%-30s | %10s %11s | %10s %11s"
      % ("scenario", "esperance", "$/jour", "esperance", "$/jour"))
print("-" * 84)
for turbo, nt in ((True, "L6+"), (False, "L6 ")):
    for g, taille in ((1.00, 100), (0.50, 200), (0.25, 400)):
        l = "%-30s |" % ("%s  compte %d k" % (nt, taille))
        for e, _, _ in FEN:
            o, m, mj, mt = ftmo(S[e][2], g, turbo)
            esp = taille * 1000 * o / 100.0
            l += " %9.0f $ %8.0f $ |" % (esp, esp/m if m else 0)
        print(l)
