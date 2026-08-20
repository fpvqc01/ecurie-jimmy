# -*- coding: utf-8 -*-
"""VALIDATION SEVERE de l'avantage ML du meta-etiquetage.
Le gain brut etait +0,7 R sur 70 signaux : reel ou hasard ?
  TEST 1 — PERMUTATION : on melange les etiquettes (y) 200 fois et on refait
    tout le walk-forward. Si l'avantage vrai n'est pas dans le top 5 % des
    avantages obtenus au hasard, il n'est pas significatif.
  TEST 2 — STABILITE ANNEE PAR ANNEE : le sizing ML bat-il la base
    regulierement, ou grace a une seule annee chanceuse ?
  TEST 3 — QUELS FEATURES comptent (poids moyens du modele) ?"""
import requests, pandas as pd, numpy as np, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_ml_metalabel.py"),
           encoding="utf-8").read()
# on reutilise tout le code de generation jusqu'a la construction de signaux
exec(src.split("# ------------------------------------------------------------------\n# Regression")[0]
     .replace('print("Telechargement des 4 marches...")', 'pass'))

F = np.array([s[2] for s in signaux])
R = np.array([s[3] for s in signaux])
dates = [s[0] for s in signaux]
annees = sorted(set(d.year for d in dates))
premiere = annees[0] + 4

def logistique(X, y, iters=400, lr=0.1):
    w = np.zeros(X.shape[1] + 1)
    Xb = np.hstack([np.ones((len(X), 1)), X])
    for _ in range(iters):
        p = 1/(1 + np.exp(-Xb @ w))
        w += lr * Xb.T @ (y - p) / len(y)
    return w

def predire(w, X):
    return 1/(1 + np.exp(-np.hstack([np.ones((len(X), 1)), X]) @ w))

def walkforward(Y, retour_details=False):
    base, ml, poids, par_an = [], [], [], {}
    for an in annees:
        if an < premiere: continue
        tr = [i for i, d in enumerate(dates) if d.year < an]
        te = [i for i, d in enumerate(dates) if d.year == an]
        if len(tr) < 100 or not te: continue
        mu, sd = F[tr].mean(axis=0), F[tr].std(axis=0) + 1e-9
        Xtr = (F[tr] - mu) / sd
        w = logistique(Xtr, Y[tr])
        poids.append(w)
        ptr = predire(w, Xtr)
        tb, th = np.percentile(ptr, 33), np.percentile(ptr, 66)
        pte = predire(w, (F[te] - mu) / sd)
        b_an, m_an = 0.0, 0.0
        tailles = []
        for k, i in enumerate(te):
            t = 0.5 if pte[k] < tb else (1.5 if pte[k] > th else 1.0)
            tailles.append(t)
            base.append(R[i]); ml.append(R[i] * t)
            b_an += R[i]; m_an += R[i] * t
        moy = np.mean(tailles) if tailles else 1.0
        par_an[an] = (b_an, m_an / moy if moy else 0.0, len(te))
    base, ml = np.array(base), np.array(ml)
    # normalisation de l'exposition totale pour comparer a risque egal
    ml_norm = ml.sum() / (ml.sum()/base.sum() if base.sum() else 1)  # placeholder
    return base, ml, poids, par_an

Y_vrai = (R > 0).astype(float)
base, ml, poids, par_an = walkforward(Y_vrai)
# avantage a exposition egale : on normalise par la taille moyenne
tailles_moy = ml.sum() / base.sum() if base.sum() else 1
avantage_vrai = ml.sum() / (np.abs(ml).sum() / np.abs(base).sum()) - base.sum()

print("=== TEST 2 : STABILITE ANNEE PAR ANNEE (a exposition normalisee) ===")
print("  %-6s | %-9s | %-9s | %-8s | %s" % ("Annee", "base R", "ML R", "ecart", "signaux"))
print("  " + "-"*54)
gagne = 0
for an, (b, m, k) in sorted(par_an.items()):
    ec = m - b
    if ec > 0.01: gagne += 1
    print("  %-6d | %+8.2f | %+8.2f | %+7.2f | %d" % (an, b, m, ec, k))
print("  -> le ML bat la base dans %d annees sur %d" % (gagne, len(par_an)))

print()
print("=== TEST 1 : PERMUTATION (200 melanges des etiquettes) ===")
rng = np.random.default_rng(7)
avantages = []
for it in range(200):
    Yp = rng.permutation(Y_vrai)
    b, m, _, _ = walkforward(Yp)
    expo = np.abs(m).sum() / max(np.abs(b).sum(), 1e-9)
    avantages.append(m.sum()/expo - b.sum())
avantages = np.array(avantages)
expo_v = np.abs(ml).sum() / max(np.abs(base).sum(), 1e-9)
av_v = ml.sum()/expo_v - base.sum()
pct = (avantages >= av_v).mean() * 100
print("  avantage REEL (exposition egale) : %+.2f R" % av_v)
print("  hasard : moyenne %+.2f R | ecart-type %.2f | max %+.2f R" %
      (avantages.mean(), avantages.std(), avantages.max()))
print("  p-value approximative : %.1f %%  (%s)" %
      (pct, "SIGNIFICATIF" if pct < 5 else "NON SIGNIFICATIF — indistinguable du hasard"))

print()
print("=== TEST 3 : ce que le modele a appris (poids moyens standardises) ===")
noms = ["vol niveau", "vol regime", "force tendance", "RSI",
        "etirement 20j", "momentum 20j", "famille repli", "famille cassure"]
W = np.mean(np.array(poids), axis=0)
ordre = np.argsort(-np.abs(W[1:]))
for k in ordre:
    print("  %-16s %+0.3f" % (noms[k], W[1+k]))
