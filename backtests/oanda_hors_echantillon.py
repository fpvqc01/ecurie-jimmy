# -*- coding: utf-8 -*-
"""L'ETUDE OANDA REFAITE PROPREMENT (21 aout 2026).

L'etude d'origine choisit ses gagnants sur les MEMES 5 ans qu'elle mesure :
le CAGR qui passe de +8,5 % a +20,2 % au fil des rondes d'elimination est un
artefact mecanique (on jette les perdants en connaissant l'avenir), pas un
avantage. On refait le meme travail avec une coupure :

  APPRENTISSAGE : premiere moitie -> on choisit les manches
  VERIFICATION  : deuxieme moitie -> on mesure, sans jamais y toucher

Si la selection tient hors echantillon, l'etude vaut quelque chose.
Sinon, c'est du surajustement et il ne faut rien ajouter a l'ecurie."""
import os, sys, io
import pandas as pd, numpy as np
D = r"C:\Users\jplou\Downloads\Ecurie_Jimmy_I2plus_partage\backtests"
os.chdir(D); sys.path.insert(0, D)

src = io.open("test_oanda_univers.py", encoding="utf-8").read()
src = src.split("NOYAU = [")[0]          # tout sauf les rondes d'origine
ns = {"__file__": os.path.join(D, "test_oanda_univers.py"), "__name__": "etude"}
exec(src, ns)
construire, metriques, FAMX, DATA = ns["construire"], ns["metriques"], ns["FAMX"], ns["DATA"]

def sim(actifs, debut=None, fin=None):
    """copie de sim() avec une fenetre de dates"""
    sl = construire(actifs)
    garde = -0.025
    dates = sorted(set().union(*[set(s.df.index) for s in sl]))
    if debut: dates = [d for d in dates if d >= pd.Timestamp(debut)]
    if fin:   dates = [d for d in dates if d <= pd.Timestamp(fin)]
    equite, histo = 1.0, []
    for d in dates:
        for s in sl: s.gerer(d)
        jt = sum(s.pnl.get(d, 0) for s in sl)
        if jt <= garde:
            f = garde / jt
            for s in sl:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            jt = garde
        equite *= (1 + jt); histo.append(equite)
        if jt <= garde: continue
        fc = 0.75 if (len(histo) > 20 and equite < np.mean(histo[-20:])) else 1.0
        ouverts = sum(1 for s in sl if s.pos is not None)
        familles = {FAMX[s.nom] for s in sl if s.pos is not None}
        for s in sl:
            if s.pos is not None or ouverts >= 2: continue
            if FAMX[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(d)
            if sig is None: continue
            r0 = s.risque; s.risque = r0 * fc
            ok = s.ouvrir(d, **sig); s.risque = r0
            if ok: ouverts += 1; familles.add(FAMX[s.nom])
    tj = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sl:
        for dt, v in s.pnl.items():
            if dt in tj.index: tj[dt] += v
    contrib = {s.nom: sum(v for dt, v in s.pnl.items() if dt in tj.index) * 100 for s in sl}
    return metriques(tj.clip(lower=garde)), contrib

NOYAU = ["Or", "Petrole", "Nasdaq"]
TOUS = NOYAU + list(DATA)

# coupure au milieu de l'historique commun
toutes_dates = sorted(set().union(*[set(s.df.index) for s in construire(TOUS)]))
milieu = toutes_dates[len(toutes_dates)//2]
print("Historique : %s -> %s | coupure : %s"
      % (toutes_dates[0].date(), toutes_dates[-1].date(), milieu.date()))
print()

# --- APPRENTISSAGE : on choisit sur la 1re moitie, exactement comme l'etude
print("=== APPRENTISSAGE (1re moitie) : on choisit les manches ===")
actifs = list(TOUS)
for ronde in (1, 2):
    (c, dd, m), contrib = sim(actifs, fin=milieu)
    if ronde == 1:
        actifs = [n for n in actifs if contrib.get(n, 0) > 0]
        print("  ronde 1 : %2d manches -> %2d apres elimination des negatives" % (len(TOUS), len(actifs)))
    else:
        actifs = [n for n in actifs if contrib.get(n, 0) >= 2.0]
        print("  ronde 2 : -> %2d manches gardees (>= +2 pts)" % len(actifs))
CHOISIES = actifs
print("  choix de l'apprentissage : " + ", ".join(CHOISIES))
print()

# --- VERIFICATION : on mesure sur la 2e moitie, jamais vue
print("=== VERIFICATION (2e moitie, jamais utilisee pour choisir) ===")
print("  %-46s | %8s %8s %7s" % ("portefeuille", "CAGR", "MaxDD", "morts"))
print("  " + "-" * 76)
for etq, act in (("noyau seul (or + petrole + Nasdaq)", NOYAU),
                 ("choix de l'apprentissage (%d manches)" % len(CHOISIES), CHOISIES),
                 ("univers complet (%d manches, aucun choix)" % len(TOUS), TOUS)):
    (c, dd, m), _ = sim(act, debut=milieu)
    print("  %-46s | %+7.1f %% %+7.1f %% %6.0f %%" % (etq, c, dd, m))

print()
print("=== RAPPEL : l'etude d'origine, tout en echantillon ===")
for etq, act in (("noyau seul", NOYAU), ("univers complet", TOUS)):
    (c, dd, m), _ = sim(act)
    print("  %-46s | %+7.1f %% %+7.1f %% %6.0f %%" % (etq, c, dd, m))
(c, dd, m), _ = sim(CHOISIES)
print("  %-46s | %+7.1f %% %+7.1f %% %6.0f %%"
      % ("choix de l'apprentissage, mesure en echantillon", c, dd, m))
