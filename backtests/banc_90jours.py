# -*- coding: utf-8 -*-
"""OBJECTIF : PASSER LE CHALLENGE EN MOINS DE 90 JOURS (demande Jimmy).

L'ARITHMETIQUE D'ABORD. Le challenge complet demande +10 % puis +5 %, soit
+15,5 % composes. A +29,5 %/an, atteindre +15,5 % demande en moyenne
  ln(1,155) / ln(1,295) x 365 = 204 jours.
C'est l'ancre. Pour le faire en 90 jours il faudrait l'equivalent de
+70 %/an, soit 2,4 fois le rendement actuel.

On mesure donc trois choses :
  1. La DISTRIBUTION des durees, pas seulement la mediane. Quelle part des
     tentatives finit deja en moins de 90 jours aujourd'hui ?
  2. La PHASE 1 SEULE (+10 %), pour chiffrer ce que vaudrait un challenge
     en une seule etape.
  3. La FRONTIERE exacte : quel multiplicateur de mise amene la mediane a
     90 jours, et combien de reussite ca coute."""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B

BASE = dict(B.ALLOC)
def alloc_btc(r):
    a = dict(BASE); lib = a["BTC Cassure"] - r; a["BTC Cassure"] = r
    a["Or"] += lib/2; a["Nasdaq"] += lib/2; return a

def serie(garde, be, alloc, deb, fin):
    ns0 = B.charger(garde)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in alloc: s.risque = alloc[s.nom]
        if be:
            for s in sl:
                if s.nom in B.PYR: B.breakeven(s, be)
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    return r[0], r[2], r[6].sort_index()

def phase(v, i0, cible, g):
    eq = 1.0; jt = 0
    for j in range(i0, len(v)):
        r = v[j] * g
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j-i0+1
        eq *= (1 + r)
        if eq <= 0.90: return 0, j-i0+1
        if eq >= 1 + cible and jt >= 4: return 1, j-i0+1
    return -1, len(v)-i0

def stats(tj, g, une_seule_phase=False):
    v = tj.values; ok = mort = 0; d = []
    for i0 in range(0, len(v)-60, 3):
        v1, d1 = phase(v, i0, 0.10, g)
        if v1 == -1: continue
        if v1 == 0: mort += 1; continue
        if une_seule_phase:
            ok += 1; d.append(d1); continue
        v2, d2 = phase(v, i0+d1, 0.05, g)
        if v2 == -1: continue
        if v2 == 0: mort += 1; continue
        ok += 1; d.append(d1+d2)
    n = ok+mort
    d = np.array(d) if d else np.array([0])
    return dict(reussite=100.0*ok/max(n,1), med=np.median(d),
                p10=np.percentile(d,10), p25=np.percentile(d,25),
                sous90=100.0*(d<90).mean(),
                # part de TOUS les departs qui finissent gagnants en < 90 j
                gagne90=100.0*(d<90).sum()/max(n,1))

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
CONFIGS = (("L6  (gardien 2,50, sans BE)", 0.025,  None, BASE),
           ("L8  (gardien 1,75 + BE)",     0.0175, 0.05, BASE),
           ("L8+ (BTC 1,15 %)",            0.0175, 0.05, alloc_btc(0.0115)))
S = {(n, e): serie(g, b, a, d, f) for n, g, b, a in CONFIGS for e, d, f in FEN}

print("=== 1. LA DISTRIBUTION DES DUREES (mise normale, fermeture a +10 %) ===")
print("   Meme aujourd'hui, une partie des tentatives finit vite.")
print("%-28s | %-42s | %s" % ("", "10 ANS", "2021-2026"))
print("%-28s | %7s %5s %5s %5s %8s | %7s %5s %8s"
      % ("ecurie", "reuss.", "P10", "P25", "med", "<90j*", "reuss.", "med", "<90j*"))
print("-" * 104)
for nom, g0, be, al in CONFIGS:
    l = "%-28s |" % nom
    for k, (e, _, _) in enumerate(FEN):
        r = stats(S[(nom, e)][2], 1.0)
        if k == 0: l += " %6.0f %% %4.0f %4.0f %4.0f %7.0f %% |" % (r["reussite"], r["p10"], r["p25"], r["med"], r["gagne90"])
        else:      l += " %6.0f %% %4.0f %7.0f %%" % (r["reussite"], r["med"], r["gagne90"])
    print(l)
print("   * <90j = part de TOUS les departs qui sont REUSSIS en moins de 90 jours")

print()
print("=== 2. ET SI LE CHALLENGE N'AVAIT QU'UNE SEULE PHASE (+10 %) ? ===")
print("%-28s | %-20s | %s" % ("", "10 ANS", "2021-2026"))
print("%-28s | %8s %5s %7s | %8s %5s %7s" % ("ecurie", "reuss.", "med", "<90j", "reuss.", "med", "<90j"))
print("-" * 82)
for nom, g0, be, al in CONFIGS:
    l = "%-28s |" % nom
    for e, _, _ in FEN:
        r = stats(S[(nom, e)][2], 1.0, une_seule_phase=True)
        l += " %7.0f %% %4.0f %6.0f %% |" % (r["reussite"], r["med"], r["gagne90"])
    print(l)

print()
print("=== 3. LA FRONTIERE : que coute une mediane de 90 jours ? ===")
print("   (on multiplie toutes les mises par g ; chassis L8+, le plus solide)")
print("%-22s | %-26s | %s" % ("", "10 ANS", "2021-2026"))
print("%-22s | %8s %6s %8s | %8s %6s" % ("multiplicateur", "reussite", "med", "<90j", "reussite", "med"))
print("-" * 78)
for g in (1.00, 1.25, 1.50, 1.75, 2.00, 2.50):
    l = "%-22s |" % ("x%.2f" % g)
    for k, (e, _, _) in enumerate(FEN):
        r = stats(S[("L8+ (BTC 1,15 %)", e)][2], g)
        if k == 0: l += " %7.0f %% %5.0f %7.0f %% |" % (r["reussite"], r["med"], r["gagne90"])
        else:      l += " %7.0f %% %5.0f" % (r["reussite"], r["med"])
    print(l)
