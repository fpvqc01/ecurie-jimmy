# -*- coding: utf-8 -*-
"""LA COURSE A LA VITESSE : quel robot donne un compte finance le plus vite ?

La duree mediane est trompeuse. Un challenge rate coute AUSSI le temps passe
dedans avant de mourir. On classe donc sur le TEMPS ESPERE :
   jours esperes = duree moyenne d un echec x (1/p - 1) + duree d une reussite
   frais esperes = 439 EUR (promo FTMO 100 k) / p

On inclut une combinaison JAMAIS testee : le turbo sur le chassis L11. La
deconcentration du BTC a peut-etre retire la fragilite qui tuait le turbo."""
import os, sys, io
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B

def charge(nom, coupe):
    src = io.open(os.path.join(D, nom), encoding="utf-8").read().split(coupe)[0]
    ns = {"__file__": os.path.join(D, nom), "__name__": "x"}
    exec(src, ns); return ns
R = charge("banc_repli.py", "FEN = (")
C = charge("banc_repli_conditionnel.py", "FEN = R.FEN")
CIBLES, cond = R["CIBLES"], C["repli_conditionnel"]

BASE = dict(B.ALLOC)
def alloc_btc(r):
    a = dict(BASE); lib = a["BTC Cassure"] - r; a["BTC Cassure"] = r
    a["Or"] += lib/2; a["Nasdaq"] += lib/2; return a
BTC115 = alloc_btc(0.0115)

_ch = {}
def chaine(g):
    if g not in _ch: _ch[g] = B.charger(g)
    return _ch[g]

def serie(garde, be, alloc, repli, deb, fin):
    ns0 = chaine(garde)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in alloc: s.risque = alloc[s.nom]
        if be:
            for s in sl:
                if s.nom in B.PYR: B.breakeven(s, be)
        if repli:
            for s in sl:
                if s.nom in CIBLES: cond(s, 1.25, 5, 1.0)
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    return r[0], r[2], r[6].sort_index()

def phase(v, i0, cible, mult, cou):
    eq = 1.0; jt = 0
    for j in range(i0, len(v)):
        m = mult if (cou is None or eq < 1 + cou) else 1.0
        x = v[j] * m
        if x != 0.0: jt += 1
        if x <= -0.05: return 0, j-i0+1
        eq *= (1+x)
        if eq <= 0.90: return 0, j-i0+1
        if eq >= 1 + cible and jt >= 4: return 1, j-i0+1
    return -1, len(v)-i0

def bilan(tj, mult=1.0, cou=None, prix=439):
    v = tj.values; ok = 0; d_ok = []; d_ko = []
    for i0 in range(0, len(v)-60, 3):
        v1, d1 = phase(v, i0, 0.10, mult, cou)
        if v1 == -1: continue
        if v1 == 0: d_ko.append(d1); continue
        v2, d2 = phase(v, i0+d1, 0.05, mult, cou)
        if v2 == -1: continue
        if v2 == 0: d_ko.append(d1+d2); continue
        ok += 1; d_ok.append(d1+d2)
    n = ok + len(d_ko); p = ok/max(n,1)
    med = np.median(d_ok) if d_ok else 0
    moy_ko = np.mean(d_ko) if d_ko else 0
    return dict(p=100*p, med=med, jours=(moy_ko*(1/p-1)+med if p>0 else 9e9),
                frais=(prix/p if p else 9e9))

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))
CH = {"L6":   (0.025,  None, BASE,   False),
      "L6r":  (0.025,  None, BASE,   True),
      "L8":   (0.0175, 0.05, BASE,   False),
      "L8+":  (0.0175, 0.05, BTC115, False),
      "L11":  (0.025,  0.05, BTC115, False),
      "L11r": (0.025,  0.05, BTC115, True)}
S = {(k, e): serie(*CH[k], d, f) for k in CH for e, d, f in FEN}

CAND = [
    ("L6R13",                       "L6",   1.00, None),
    ("L6R13 + repli",               "L6r",  1.00, None),
    ("L6+ turbo x1,33",             "L6",   1.33, 0.04),
    ("L8",                          "L8",   1.00, None),
    ("L8+",                         "L8+",  1.00, None),
    ("L11",                         "L11",  1.00, None),
    ("L11 + repli",                 "L11r", 1.00, None),
    ("L11 + turbo x1,15",           "L11",  1.15, 0.04),
    ("L11 + turbo x1,25",           "L11",  1.25, 0.04),
    ("L11 + turbo x1,33",           "L11",  1.33, 0.04),
    ("L11 + turbo x1,50",           "L11",  1.50, 0.04),
    ("L11 + turbo x1,33 permanent", "L11",  1.33, None),
    ("L11 repli + turbo x1,33",     "L11r", 1.33, 0.04),
]

for e, _, _ in FEN:
    print(); print("=== %s — classement par TEMPS ESPERE jusqu'au compte finance ===" % e.strip())
    print("%-30s | %7s %6s | %9s %8s | %7s" % ("robot", "reuss.", "duree", "JOURS", "FRAIS", "CAGR"))
    print("%-30s | %7s %6s | %9s %8s | %7s" % ("", "", "mediane", "ESPERES", "ESPERES", ""))
    print("-" * 84)
    lignes = []
    for nom, ch, mult, cou in CAND:
        cagr, dd, tj = S[(ch, e)]
        b = bilan(tj, mult, cou)
        lignes.append((b["jours"], nom, b, cagr, dd))
    for jours, nom, b, cagr, dd in sorted(lignes):
        print("%-30s | %6.0f %% %5.0f j | %7.0f j %6.0f EUR | %+6.1f %%"
              % (nom, b["p"], b["med"], b["jours"], b["frais"], cagr))
