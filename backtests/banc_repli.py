# -*- coding: utf-8 -*-
"""BANC « ACHETER LE REPLI » + « MAX 2 PYRAMIDAGES PAR JOUR » (idees de Jimmy).

SON CONSTAT, verifie dans le code : la manche Donchian entre a la CLOTURE
des que le prix depasse le plus-haut 20 jours (`if c > h20: entree=c`).
C'est litteralement acheter le sommet de la cassure. Idem pour les unites de
pyramide, qui s'ajoutent des que le prix monte de 0,5 ATR - plusieurs
peuvent tomber dans la meme journee, toujours plus haut.

MECANISME A - ATTENDRE UN REPLI. Quand le signal se declenche a un prix E,
on n'achete pas. On arme une attente a E - k x ATR et on n'entre que si le
prix redescend jusque-la dans les `fenetre` barres suivantes. Sinon on laisse
passer. Le stop reste celui du signal d'origine : entrer plus bas pour le
meme stop, c'est exactement ce que Jimmy demande.

MECANISME B - MAX N UNITES DE PYRAMIDE PAR JOUR. On plafonne dynamiquement
`pyr_max` a (unites au debut de la journee + N).

Applique aux deux manches qui pyramident et qui achetent la cassure :
BTC Cassure et Petrole. Chassis L6 et L6+ (turbo), tous avec R13."""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B

CIBLES = ("BTC Cassure", "Petrole")

# ---------- A : attendre un repli avant d'acheter ----------
def repli(s, k_atr, fenetre):
    sig0 = s.signal
    s._arme = None
    def sig(t):
        i = s.idx.get(t)
        if i is None: return None
        v = s.prov(i)
        if v is None: return None
        a = v[0]
        if s._arme is not None:
            niveau, reste, base = s._arme
            if s.L[i] <= niveau:                     # le repli s'est produit
                s._arme = None
                d = dict(base); d["entree"] = niveau
                if d["entree"] <= d["stop"]: return None
                return d
            if reste <= 0:
                s._arme = None                       # trop tard, on laisse passer
            else:
                s._arme = (niveau, reste - 1, base)
                return None
        r = sig0(t)
        if r is None or not (a > 0): return None
        s._arme = (r["entree"] - k_atr * a, fenetre, r)
        return None                                  # jamais d'achat au sommet
    s.signal = sig
    return s

# ---------- B : plafond d'unites de pyramide par jour ----------
def max_pyr_jour(s, maxi):
    g0 = s.gerer
    vrai = getattr(s, "pyr_max", 3)
    s._jour = None; s._pid = None; s._u0 = 1
    def g(t):
        p = s.pos
        j = t.date()
        if p is not None:
            if s._jour != j or s._pid is not p:
                s._jour, s._pid, s._u0 = j, p, p.get("unites", 1)
            s.pyr_max = min(vrai, s._u0 + maxi)
        else:
            s.pyr_max = vrai; s._jour = None; s._pid = None
        g0(t)
        s.pyr_max = vrai
    s.gerer = g
    return s

def mesure(garde, meca, mult, cou, deb, fin):
    ns0 = B.charger(garde)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite = []
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in B.ALLOC: s.risque = B.ALLOC[s.nom]
        if meca: meca(sl)
        boite[:] = sl
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()
    v = tj.values; ok = mort = 0; d = []
    for i0 in range(0, len(v)-60, 3):
        e = 1.0; jt = 0; d1 = None; j = i0
        for j in range(i0, len(v)):
            x = v[j] * (mult if (cou is None or e < 1+cou) else 1.0)
            if x != 0.0: jt += 1
            if x <= -0.05: break
            e *= (1+x)
            if e <= 0.90: break
            if e >= 1.10 and jt >= 4: d1 = j-i0+1; break
        if d1 is None:
            if j >= len(v)-1: continue
            mort += 1; continue
        e = 1.0; jt = 0; d2 = None
        for j in range(i0+d1, len(v)):
            x = v[j] * (mult if (cou is None or e < 1+cou) else 1.0)
            if x != 0.0: jt += 1
            if x <= -0.05: break
            e *= (1+x)
            if e <= 0.90: break
            if e >= 1.05 and jt >= 4: d2 = j-(i0+d1)+1; break
        if d2 is None:
            if j >= len(v)-1: continue
            mort += 1; continue
        ok += 1; d.append(d1+d2)
    n = ok+mort
    tr = sum(s.trades for s in boite)
    return tr, r[0], 100.0*ok/max(n,1), (np.median(d) if d else 0), r[2]

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
VAR = [
    ("reference",                       None),
    ("B. max 2 pyramidages / jour",     lambda sl: [max_pyr_jour(s,2) for s in sl if s.nom in CIBLES]),
    ("B. max 1 pyramidage / jour",      lambda sl: [max_pyr_jour(s,1) for s in sl if s.nom in CIBLES]),
    ("A. repli 0,25 ATR (5 barres)",    lambda sl: [repli(s,0.25,5) for s in sl if s.nom in CIBLES]),
    ("A. repli 0,50 ATR (5 barres)",    lambda sl: [repli(s,0.50,5) for s in sl if s.nom in CIBLES]),
    ("A. repli 1,00 ATR (5 barres)",    lambda sl: [repli(s,1.00,5) for s in sl if s.nom in CIBLES]),
    ("A. repli 0,50 ATR (10 barres)",   lambda sl: [repli(s,0.50,10) for s in sl if s.nom in CIBLES]),
    ("A+B repli 0,50 + max 2 / jour",   lambda sl: [max_pyr_jour(repli(s,0.50,5),2) for s in sl if s.nom in CIBLES]),
]

for nom_ch, garde, mult, cou in (("L6  (sans turbo)", 0.025, 1.00, None),
                                 ("L6+ (turbo x1,33)", 0.025, 1.33, 0.04)):
    print(); print("=== %s + fermeture a +10 %% ===" % nom_ch)
    print("%-32s | %-32s | %s" % ("", "10 ANS", "2021-2026"))
    print("%-32s | %6s %7s %8s %6s %7s | %8s %6s"
          % ("mecanisme", "trades", "CAGR", "reussite", "duree", "DD", "reussite", "duree"))
    print("-" * 106)
    for etq, meca in VAR:
        l = "%-32s |" % etq
        for k, (e, d0, f0) in enumerate(FEN):
            tr, cagr, o, m, dd = mesure(garde, meca, mult, cou, d0, f0)
            if k == 0: l += " %6d %+6.1f %% %6.0f %% %4.0f j %+6.1f %% |" % (tr, cagr, o, m, dd)
            else:      l += " %6.0f %% %4.0f j" % (o, m)
        print(l)
