# -*- coding: utf-8 -*-
"""BANC D'ESSAI DU GIVE-BACK DES PYRAMIDES (idees du comite externe,
21 aout 2026). Config L6 (allocation a x0,75), donnees propres, mode
challenge, 10 ans. Chaque mecanisme est juge sur les 3 chiffres que
Jimmy veut : RENDEMENT (CAGR), TEMPS (duree mediane du challenge
complet) et REUSSITE (simulateur FTMO exact 2 phases).

Mecanismes testes (appliques aux 2 manches qui pyramident :
BTC Cassure et Petrole) :
  A. reference L6
  B. verrouillage partiel : fermer 1 unite sur 3 des +X % de profit
     (X = 4, 6, 8) — le mecanisme prefere du comite
  C. breakeven collectif : stop remonte au prix d'entree MOYEN des
     unites des que le profit depasse X % (X = 4, 6)
  D. canal de sortie plus court : 5 ou 7 jours au lieu de 10
  E. chandelier ATR K = 3, 4, 5 (re-juge sur la DUREE cette fois)
  F. combo : verrouillage partiel 6 % + canal 7 jours"""
import os, numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "options_optimisation.py"), encoding="utf-8").read()
src = src.split("OPTIONS = [")[0]
ns0 = {"__file__": os.path.join(D, "options_optimisation.py")}
exec(src, ns0)
ns, fab_option, f_or = ns0["ns"], ns0["fab_option"], ns0["f_or"]
interne = ns0["ns0"]
chandelier = interne["chandelier"]

ALLOC = {"Or": 0.0075, "Nasdaq": 0.0075, "Petrole": 0.0169,
         "BTC Cassure": 0.0169, "BTC EMA": 0.0113}
PYR = ("BTC Cassure", "Petrole")

def a075(sl):
    for s in sl:
        if s.nom in ALLOC: s.risque = ALLOC[s.nom]

# ---------- B. verrouillage partiel ----------
def verrou_partiel(s, seuil_pct, fraction=1.0/3.0):
    """des que le profit ouvert depasse seuil_pct, on encaisse une
    fraction de la pile (une seule fois par trade)."""
    gerer0, ouvrir0 = s.gerer, s.ouvrir
    def ouvrir(t, **kw):
        ok = ouvrir0(t, **kw)
        if ok: s._verrou_fait = False
        return ok
    def gerer(t):
        gerer0(t)
        p = s.pos
        if p is None or getattr(s, "_verrou_fait", False): return
        i = s.idx.get(t)
        if i is None: return
        gain = (s.C[i] - p["e"]) / p["e"]
        if gain >= seuil_pct and p["n"] > 0:
            part = p["n"] * fraction
            s.pnl[t] = s.pnl.get(t, 0) - s.frais * part   # sortie de la portion
            p["n"] -= part
            s._verrou_fait = True
    s.ouvrir, s.gerer = ouvrir, gerer
    return s

# ---------- C. breakeven collectif ----------
def breakeven_collectif(s, seuil_pct):
    """des que le profit depasse seuil_pct, le stop ne peut plus
    descendre sous le prix d'entree MOYEN des unites."""
    gerer0 = s.gerer
    def gerer(t):
        gerer0(t)
        p = s.pos
        if p is None: return
        i = s.idx.get(t)
        if i is None: return
        gain = (s.C[i] - p["e"]) / p["e"]
        if gain >= seuil_pct:
            moyen = (p["e"] + p.get("dernier", p["e"])) / 2.0
            if moyen > p["s"]: p["s"] = moyen
    s.gerer = gerer
    return s

# ---------- D. canal de sortie plus court ----------
def canal_court(s, jours):
    import pandas as _pd
    s.B10J = _pd.Series(s.DJL).rolling(jours).min().values
    return s

def fab(post):
    def f():
        sl = ns0["fab_l431"]()()
        a075(sl)
        if post: post(sl)
        return sl
    return f

def serie(post=None):
    ns["DEBUT"], ns["FIN"] = "2015-08-21", "2026-12-31"
    ns["sleeves_l4"] = fab(post)
    r = ns["sim_h4"](interdit=f_or)
    return r[0], r[2], r[6].sort_index()

# ---------- simulateur FTMO exact ----------
def phase(vals, i0, cible):
    eq = 1.0; jt = 0
    for j in range(i0, len(vals)):
        r = vals[j]
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j - i0 + 1
        eq *= (1 + r)
        if eq <= 0.90: return 0, j - i0 + 1
        if eq >= 1 + cible and jt >= 4: return 1, j - i0 + 1
    return -1, len(vals) - i0

def ftmo(tj):
    vals = tj.values
    complets = morts = 0; durees = []
    for i0 in range(0, len(vals) - 60, 3):
        v1, d1 = phase(vals, i0, 0.10)
        if v1 == -1: continue
        if v1 == 0: morts += 1; continue
        v2, d2 = phase(vals, i0 + d1, 0.05)
        if v2 == -1: continue
        if v2 == 0: morts += 1; continue
        complets += 1; durees.append(d1 + d2)
    n = complets + morts
    return 100.0 * complets / max(n, 1), (np.median(durees) if durees else 0)

VARIANTES = [
    ("A. reference L6", None),
    ("B1. verrou partiel 1/3 des +4 %", lambda sl: [verrou_partiel(s, 0.04) for s in sl if s.nom in PYR]),
    ("B2. verrou partiel 1/3 des +6 %", lambda sl: [verrou_partiel(s, 0.06) for s in sl if s.nom in PYR]),
    ("B3. verrou partiel 1/3 des +8 %", lambda sl: [verrou_partiel(s, 0.08) for s in sl if s.nom in PYR]),
    ("C1. breakeven collectif des +4 %", lambda sl: [breakeven_collectif(s, 0.04) for s in sl if s.nom in PYR]),
    ("C2. breakeven collectif des +6 %", lambda sl: [breakeven_collectif(s, 0.06) for s in sl if s.nom in PYR]),
    ("D1. canal de sortie 7 jours", lambda sl: [canal_court(s, 7) for s in sl if s.nom in PYR]),
    ("D2. canal de sortie 5 jours", lambda sl: [canal_court(s, 5) for s in sl if s.nom in PYR]),
    ("E1. chandelier K=5", lambda sl: [chandelier(s, 5) for s in sl if s.nom in PYR]),
    ("E2. chandelier K=4", lambda sl: [chandelier(s, 4) for s in sl if s.nom in PYR]),
    ("E3. chandelier K=3", lambda sl: [chandelier(s, 3) for s in sl if s.nom in PYR]),
    ("F. combo verrou 6 % + canal 7 j",
     lambda sl: [(verrou_partiel(s, 0.06), canal_court(s, 7)) for s in sl if s.nom in PYR]),
]

print("%-36s | %8s | %9s | %8s | %7s" % ("MECANISME", "CAGR", "REUSSITE", "DUREE", "DD"))
print("-" * 82)
for nom, post in VARIANTES:
    cagr, dd, tj = serie(post)
    ok, med = ftmo(tj)
    print("%-36s | %+7.1f %% | %7.0f %% | %5.0f j | %+6.1f %%" % (nom, cagr, ok, med, dd))
