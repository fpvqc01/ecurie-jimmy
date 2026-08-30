# -*- coding: utf-8 -*-
"""RAFFINEMENT du gagnant de test_challenge_rapide.py : le profil COUSSIN
(risque proportionnel a la distance du plancher FTMO -10 %).
m = clip(BASE * (equite - 0.90) / 0.10, PLANCHER_M, CAP)
On balaie BASE et CAP, plus 2 combos coussin+palier (protection pres de la
cible). Cap maximal 1,8 : un jour de base -2,5 % (gardien) donne -4,5 %,
il reste 0,5 point de marge avant la limite FTMO de -5 %/jour."""
import numpy as np, pandas as pd

src = open("scan_strategies.py", encoding="utf-8").read().split("resultats = []")[0]
ns = {"__file__": "scan_strategies.py"}
exec(src, ns)
ns["RISQUES"]["L4"] = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)
serie = ns["sim_p"](True, "L4", 3, 0.75, False, serie_out=True)["serie"]
r_base = serie.to_numpy(); n = len(r_base)

PERTE_JOUR, PERTE_TOT = -0.05, 0.90
FRAIS = 750
MAX_JOURS = 500

def coussin(base, cap, plancher=0.5):
    def m(e, cible):
        return float(np.clip(base * (e - PERTE_TOT) / 0.10, plancher, cap))
    return m

def coussin_palier(base, cap):
    c = coussin(base, cap)
    def m(e, cible):
        prog = (e - 1.0) / cible
        v = c(e, cible)
        if prog >= 0.8: return min(v, 0.75)
        if prog >= 0.5: return min(v, 1.25)
        return v
    return m

PROFILS = [
    ("coussin 1,5 cap 1,8",        coussin(1.5, 1.8)),
    ("coussin 1,8 cap 1,8",        coussin(1.8, 1.8)),
    ("coussin 2,0 cap 1,8",        coussin(2.0, 1.8)),
    ("coussin 2,5 cap 1,8",        coussin(2.5, 1.8)),
    ("coussin 2,0 plancher 0,25",  coussin(2.0, 1.8, 0.25)),
    ("coussin 2,0 + palier",       coussin_palier(2.0, 1.8)),
    ("coussin 2,5 + palier",       coussin_palier(2.5, 1.8)),
]

def jouer_phase(rendement_suivant, profil, cible):
    e = 1.0
    for j in range(1, MAX_JOURS + 1):
        r1 = rendement_suivant()
        if r1 is None: return None, j
        r = profil(e, cible) * r1
        if r <= PERTE_JOUR: return False, j
        e *= (1 + r)
        if e <= PERTE_TOT: return False, j
        if e - 1.0 >= cible: return True, j
    return False, MAX_JOURS

print("=" * 86)
print("1) REJEU HISTORIQUE (un depart tous les 5 jours)")
print("=" * 86)
entete = (f"{'Profil':<28} | {'Finance':>8} | {'Brule':>6} | "
          f"{'Jours P1 med':>12} | {'Jours P1+P2 med':>15}")
print(entete); print("-" * len(entete))
for nom, profil in PROFILS:
    fin_ok = brule = 0; jp1, jtot = [], []
    for i0 in range(0, n - 60, 5):
        pos = [i0]
        def suivant():
            if pos[0] >= n: return None
            v = r_base[pos[0]]; pos[0] += 1
            return v
        v1, j1 = jouer_phase(suivant, profil, 0.10)
        if v1 is None: continue
        if v1 is False: brule += 1; continue
        v2, j2 = jouer_phase(suivant, profil, 0.05)
        if v2 is False: brule += 1
        elif v2 is True:
            fin_ok += 1; jp1.append(j1); jtot.append(j1 + j2)
    tot = fin_ok + brule
    if tot == 0: continue
    print(f"{nom:<28} | {fin_ok/tot*100:>7.1f}% | {brule/tot*100:>5.1f}% | "
          f"{np.median(jp1) if jp1 else float('nan'):>12.0f} | "
          f"{np.median(jtot) if jtot else float('nan'):>15.0f}")

print()
print("=" * 86)
print("2) MONTE-CARLO (blocs 10 jours, 2 000 carrieres, retente jusqu'au financement)")
print("=" * 86)
rng = np.random.default_rng(42)
def flux_blocs():
    etat = {"i": 0, "restant": 0}
    def suivant():
        if etat["restant"] <= 0:
            etat["i"] = int(rng.integers(0, n))
            etat["restant"] = int(rng.geometric(1 / 10))
        v = r_base[etat["i"] % n]
        etat["i"] += 1; etat["restant"] -= 1
        return v
    return suivant

entete = (f"{'Profil':<28} | {'Finance/essai':>13} | {'Tentatives':>10} | "
          f"{'Jours tot med':>13} | {'Cout moyen':>10}")
print(entete); print("-" * len(entete))
for nom, profil in PROFILS:
    reussites_1er = 0; tentatives_l, jours_l, couts = [], [], []
    for _ in range(2000):
        jours = 0; t = 0; ok = False
        while t < 10 and not ok:
            t += 1
            suivant = flux_blocs()
            v1, j1 = jouer_phase(suivant, profil, 0.10)
            jours += j1
            if v1:
                v2, j2 = jouer_phase(suivant, profil, 0.05)
                jours += j2
                if v2: ok = True
        if ok:
            if t == 1: reussites_1er += 1
            tentatives_l.append(t); jours_l.append(jours); couts.append(t * FRAIS)
    if not tentatives_l: continue
    print(f"{nom:<28} | {reussites_1er/2000*100:>12.1f}% | "
          f"{np.mean(tentatives_l):>10.2f} | {np.median(jours_l):>13.0f} | "
          f"{np.mean(couts):>8.0f} $")
print("\n(References test_challenge_rapide.py : x1,0 constant = 80,6 % / 259 j / 936 $ ;")
print(" coussin 1,5 cap 1,9 = 79,3 % / 215 j / 954 $.)")
