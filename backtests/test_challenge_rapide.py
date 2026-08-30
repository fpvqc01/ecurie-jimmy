# -*- coding: utf-8 -*-
"""OBJECTIF JIMMY (20 aout) : etre finance PLUS VITE sans augmenter le risque
de bruler le compte. On garde la strategie L4 telle quelle et on ne touche
qu'au PROFIL DE RISQUE pendant le challenge (multiplicateur applique jour
par jour selon la progression vers la cible).

Profils testes (m = multiplicateur du risque de base L4 mode challenge) :
  constant xM     : meme risque du debut a la fin (reference + versions gonflees)
  palier 1.5->0.5 : x1,5 au depart, x1,0 a mi-chemin de la cible, x0,5 pres
                    de la cible (on protege les gains quand la job est presque faite)
  coussin (CPPI)  : m proportionnel a la distance du plancher -10 % ;
                    accelere quand on est en avance, freine en creux
  maison x1->x1.75: prudent (x1) jusqu'a +3 % de coussin, puis x1,75
                    (on joue avec l'argent de la maison)
  frein 1.5/0.75  : x1,5 tant qu'on est au-dessus du depart, x0,75 en creux

Regles FTMO : P1 +10 %, P2 +5 %, perte jour -5 %, perte totale -10 %,
pas de limite de temps. Le gardien L4 plafonne un jour de base a -2,5 % :
a x2,0 un tel jour touche EXACTEMENT -5 % -> x2 est un mur, pas une option.

Deux verdicts par profil :
  1. REJEU HISTORIQUE : un challenge demarre tous les 5 jours sur les 5 ans
     reels (P1 puis P2 enchaines sur la vraie sequence).
  2. MONTE-CARLO par blocs de 10 jours consecutifs (2 000 carrieres par
     profil) : on retente apres chaque echec jusqu'au financement (max 10
     tentatives) -> tentatives moyennes, jours totaux, cout a 750 $/essai.
"""
import numpy as np, pandas as pd

# --- serie quotidienne L4 (mode challenge actif, throttle 0,75) ---
src = open("scan_strategies.py", encoding="utf-8").read().split("resultats = []")[0]
ns = {"__file__": "scan_strategies.py"}
exec(src, ns)
ns["RISQUES"]["L4"] = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)
serie = ns["sim_p"](True, "L4", 3, 0.75, False, serie_out=True)["serie"]
r_base = serie.to_numpy()
n = len(r_base)
annees = (serie.index[-1] - serie.index[0]).days / 365.25
cagr = ((1 + r_base).prod() ** (1 / annees) - 1) * 100
print(f"Serie L4 mode challenge : {n} jours ({annees:.1f} ans), CAGR {cagr:+.1f} %/an a x1\n")

PERTE_JOUR, PERTE_TOT = -0.05, 0.90
FRAIS = 750
MAX_JOURS = 500          # aucun challenge FTMO n'a de limite; garde-fou de calcul


def m_constant(k):
    return lambda e, cible: k

def m_palier(e, cible):
    prog = (e - 1.0) / cible
    if prog >= 0.8: return 0.5
    if prog >= 0.5: return 1.0
    return 1.5

def m_coussin(e, cible):
    # distance au plancher FTMO -10 % ; 1,5x quand le coussin est intact
    return float(np.clip(1.5 * (e - PERTE_TOT) / 0.10, 0.5, 1.9))

def m_maison(e, cible):
    return 1.75 if e >= 1.03 else 1.0

def m_frein(e, cible):
    return 1.5 if e >= 1.0 else 0.75

PROFILS = [
    ("constant x1,0 (reference)", m_constant(1.0)),
    ("constant x1,25",            m_constant(1.25)),
    ("constant x1,5",             m_constant(1.5)),
    ("constant x1,75",            m_constant(1.75)),
    ("constant x2,0 (le mur)",    m_constant(2.0)),
    ("palier 1,5 -> 1,0 -> 0,5",  m_palier),
    ("coussin (CPPI, max 1,9)",   m_coussin),
    ("maison 1,0 -> 1,75 a +3%",  m_maison),
    ("frein 1,5 / 0,75 en creux", m_frein),
]


def jouer_phase(rendement_suivant, profil, cible):
    """Deroule une phase. Retourne (verdict, jours) :
    verdict True=cible atteinte, False=brule, None=plus de donnees."""
    e = 1.0
    for j in range(1, MAX_JOURS + 1):
        r1 = rendement_suivant()
        if r1 is None:
            return None, j
        r = profil(e, cible) * r1
        if r <= PERTE_JOUR:
            return False, j
        e *= (1 + r)
        if e <= PERTE_TOT:
            return False, j
        if e - 1.0 >= cible:
            return True, j
    return False, MAX_JOURS   # trop lent = on compte comme un echec de carriere


# ------------------------------------------------------------------
# 1) REJEU HISTORIQUE : depart tous les 5 jours, P1 puis P2 enchaines
# ------------------------------------------------------------------
print("=" * 86)
print("1) REJEU HISTORIQUE (vraie sequence 5 ans, un depart tous les 5 jours)")
print("=" * 86)
entete = (f"{'Profil':<28} | {'Finance':>8} | {'Brule':>6} | "
          f"{'Jours P1 med':>12} | {'Jours P1+P2 med':>15}")
print(entete); print("-" * len(entete))
for nom, profil in PROFILS:
    fin_ok = brule = encours = 0
    jp1, jtot = [], []
    for i0 in range(0, n - 60, 5):
        pos = [i0]
        def suivant():
            if pos[0] >= n: return None
            v = r_base[pos[0]]; pos[0] += 1
            return v
        v1, j1 = jouer_phase(suivant, profil, 0.10)
        if v1 is None: encours += 1; continue
        if v1 is False: brule += 1; continue
        v2, j2 = jouer_phase(suivant, profil, 0.05)
        if v2 is None: encours += 1
        elif v2 is False: brule += 1
        else:
            fin_ok += 1; jp1.append(j1); jtot.append(j1 + j2)
    tot = fin_ok + brule
    if tot == 0: continue
    print(f"{nom:<28} | {fin_ok/tot*100:>7.1f}% | {brule/tot*100:>5.1f}% | "
          f"{np.median(jp1) if jp1 else float('nan'):>12.0f} | "
          f"{np.median(jtot) if jtot else float('nan'):>15.0f}")
print(f"\n(Departs sans verdict avant la fin des donnees : ignores. "
      f"'Brule' = -5 %/jour ou -10 % total en P1 ou P2.)")

# ------------------------------------------------------------------
# 2) MONTE-CARLO carrieres : blocs de 10 jours, retente apres echec
# ------------------------------------------------------------------
print()
print("=" * 86)
print("2) MONTE-CARLO (blocs de 10 jours consecutifs, 2 000 carrieres/profil,")
print("   on retente apres chaque compte brule, maximum 10 tentatives)")
print("=" * 86)
rng = np.random.default_rng(42)
N_CARRIERES = 2000
BLOC = 10

def flux_blocs():
    etat = {"i": rng.integers(0, n), "restant": 0}
    def suivant():
        if etat["restant"] <= 0:
            etat["i"] = int(rng.integers(0, n))
            etat["restant"] = int(rng.geometric(1 / BLOC))
        v = r_base[etat["i"] % n]
        etat["i"] += 1; etat["restant"] -= 1
        return v
    return suivant

entete = (f"{'Profil':<28} | {'Finance/essai':>13} | {'Tentatives':>10} | "
          f"{'Jours tot med':>13} | {'Cout moyen':>10}")
print(entete); print("-" * len(entete))
resume = []
for nom, profil in PROFILS:
    reussites_1er = 0; tentatives_l, jours_l, couts = [], [], []
    for _ in range(N_CARRIERES):
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
    p1essai = reussites_1er / N_CARRIERES * 100
    resume.append((nom, p1essai, np.mean(tentatives_l),
                   np.median(jours_l), np.mean(couts)))
    print(f"{nom:<28} | {p1essai:>12.1f}% | {np.mean(tentatives_l):>10.2f} | "
          f"{np.median(jours_l):>13.0f} | {np.mean(couts):>8.0f} $")

print("\nLecture : 'Finance/essai' = chance de passer P1+P2 du premier coup.")
print("'Jours tot med' = jours de calendrier medians avant d'etre finance,")
print("reprises comprises. Cout a 750 $/tentative (FTMO rembourse le premier")
print("essai reussi au 1er retrait -> soustraire 750 $ du cout affiche).")
print("Rappel : le gardien plafonne un jour de base a -2,5 % ; tout profil")
print("qui depasse x1,9 peut toucher la limite FTMO de -5 %/jour en un seul jour.")
