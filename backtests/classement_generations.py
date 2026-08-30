# -*- coding: utf-8 -*-
# ############################################################### #
# !! FICHIER OBSOLETE - CORRIGE LE 21 AOUT 2026                    #
#                                                                 #
# Son simulateur FTMO contient 3 defauts demontres par le comite : #
#   1. l objectif de phase est valide sur l EQUITE FLOTTANTE alors #
#      que FTMO exige le SOLDE FERME (biais tres optimiste :       #
#      quand l equite touche +10 %%, le solde n est qu a +0,1 a    #
#      +2,3 %%) ;                                                  #
#   2. les challenges non resolus sont JETES du denominateur       #
#      (`if v == -1: continue`) - ce sont les LENTS, et le tri est #
#      ASYMETRIQUE entre variantes (jusqu a 23 %% des departs) ;    #
#   3. les jours de trading comptent les jours ou le P&L bouge au  #
#      lieu des jours ou une position est OUVERTE.                 #
#                                                                 #
# NE PLUS UTILISER POUR PRODUIRE DES CHIFFRES.                     #
# Reference : backtests/SIMULATEUR_FTMO.py                         #
# Classement a jour : backtests/CLASSEMENT_DEFINITIF.py            #
# ############################################################### #

"""CLASSEMENT DE TOUTES LES GENERATIONS DE L'ECURIE — donnees reparees,
meme moteur, meme simulateur FTMO, memes deux fenetres.

Chaque generation tourne avec SA propre configuration (c'est ce qui les
distingue) : I2+ et I2++ n'ont pas les filtres macro, L3/L3+ ont la pyramide,
la famille L6/L8 a les filtres macro et l'allocation a x0,75.

Deux lectures, comme pour le duel :
  A. TEL QUEL   : seul L8 ferme a l'objectif -> les autres sont juges sur le
                  solde REELLEMENT encaisse (regle FTMO exacte).
  B. ARMES EGALES : tout le monde ferme a l'objectif.
"""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import moteur_h4 as MH
import banc_L8 as B
from sim_ferme import instrumenter

# --- instrumenter les manches construites par le moteur brut (vieilles gen.)
_c0 = MH.construire
def construire(*a, **k):
    sl = _c0(*a, **k)
    for s in sl: instrumenter(s)
    MH._dernieres = sl
    return sl
MH.construire = construire

def realise(sl, tj):
    tot = {}
    for s in sl:
        for tt, vv in getattr(s, "pnl_r", {}).items():
            jj = tt.date(); tot[jj] = tot.get(jj, 0) + vv
    return pd.Series([tot.get(j.date(), 0.0) for j in tj.index], index=tj.index)

def phase(vm, vr, i0, cible, mult, turbo, r13):
    eq = bal = 1.0; jt = 0
    for j in range(i0, len(vm)):
        m = 1.0 if (turbo and eq >= 1 + turbo) else mult
        rm, rr = vm[j]*m, vr[j]*m
        if rm != 0.0: jt += 1
        if rm <= -0.05: return 0, j-i0+1
        eq *= (1+rm); bal *= (1+rr)
        if eq <= 0.90: return 0, j-i0+1
        if (eq if r13 else bal) >= 1+cible and jt >= 4: return 1, j-i0+1
    return -1, len(vm)-i0

def ftmo(tj, tjr, mult=1.0, turbo=None, r13=True):
    vm, vr = tj.values, tjr.values
    ok = mort = 0; d = []
    for i0 in range(0, len(vm)-60, 3):
        v1, d1 = phase(vm, vr, i0, 0.10, mult, turbo, r13)
        if v1 == -1: continue
        if v1 == 0: mort += 1; continue
        v2, d2 = phase(vm, vr, i0+d1, 0.05, mult, turbo, r13)
        if v2 == -1: continue
        if v2 == 0: mort += 1; continue
        ok += 1; d.append(d1+d2)
    n = ok+mort
    return 100.0*ok/max(n,1), (np.median(d) if d else 0)

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))

# ---- vieilles generations : moteur brut, chacune sa config
def vieille(gen, deb, fin):
    """le moteur brut renvoie un dictionnaire sans la serie quotidienne :
    on la reconstruit depuis les manches instrumentees (leur pnl reflete
    deja les coupes du gardien, qui ecrit dedans)."""
    r = MH.sim(gen, debut=deb, fin=fin)
    sl = MH._dernieres
    jours = sorted({t.date() for s in sl for t in s.index
                    if t >= pd.Timestamp(deb) and t <= pd.Timestamp(fin)})
    tot = {}
    for s in sl:
        for tt, vv in s.pnl.items():
            jj = tt.date()
            if jj in set(jours) or True: tot[jj] = tot.get(jj, 0) + vv
    tj = pd.Series([tot.get(j, 0.0) for j in jours], index=pd.DatetimeIndex(jours))
    return r["cagr"], r["dd"], tj, realise(sl, tj)

# ---- famille L6/L8 : chaine complete (filtres macro + allocation a x0,75)
def moderne(garde, be, deb, fin):
    ns0 = B.charger(garde)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite = []
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in B.ALLOC: s.risque = B.ALLOC[s.nom]
        if be:
            for s in sl:
                if s.nom in B.PYR: B.breakeven(s, be)
        for s in sl: instrumenter(s)
        boite[:] = sl
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()
    return r[0], r[2], tj, realise(boite, tj)

GEN = [
    ("I2+  (2 manches, gardien 3,5 %)", lambda d, f: vieille("I2+",  d, f), 1.00, None),
    ("I2++ (parite + correlation)",     lambda d, f: vieille("I2++", d, f), 1.00, None),
    ("L3   (pyramide)",                 lambda d, f: vieille("L3",   d, f), 1.00, None),
    ("L3+  (pyr + mode challenge)",     lambda d, f: vieille("L3+",  d, f), 1.00, None),
    ("L6   (macro + alloc a x0,75)",    lambda d, f: moderne(0.025,  None, d, f), 1.00, None),
    ("L6+  (turbo-coussin)",            lambda d, f: moderne(0.025,  None, d, f), 1.33, 0.04),
    ("L6++ (breakeven 5 %)",            lambda d, f: moderne(0.025,  0.05, d, f), 1.00, None),
    ("L8   (gardien 1,75 + BE + R13)",  lambda d, f: moderne(0.0175, 0.05, d, f), 1.00, None),
]

cache = {}
def get(fn, cle, d, f):
    k = (cle, d)
    if k not in cache: cache[k] = fn(d, f)
    return cache[k]

for titre, egales in (("A. TEL QUEL (seule L8 ferme a l'objectif de phase)", False),
                      ("B. A ARMES EGALES (tout le monde ferme a l'objectif)", True)):
    print(); print("=== %s ===" % titre)
    print("%-33s | %-32s | %s" % ("", "10 ANS", "2021-2026"))
    print("%-33s | %8s %8s %6s %7s | %8s %8s %6s %7s"
          % ("generation", "CAGR", "reussite", "duree", "DD", "CAGR", "reussite", "duree", "DD"))
    print("-" * 118)
    for nom, fn, mult, turbo in GEN:
        r13 = True if egales else nom.startswith("L8")
        ligne = "%-33s |" % nom
        for etq, d, f in FEN:
            cagr, dd, tj, tjr = get(fn, nom.split()[0] + str(mult), d, f)
            o, m = ftmo(tj, tjr, mult, turbo, r13)
            ligne += " %+7.1f %% %6.0f %% %4.0f j %+6.1f %% |" % (cagr, o, m, dd)
        print(ligne)
