# -*- coding: utf-8 -*-
"""REPRISE DES DEUX RESULTATS OUVERTS DU RAPPORT « CRISES VS CALME ».

Ce rapport a ete ecrit AVANT la reparation des donnees, et il declarait
lui-meme deux reserves majeures :
  - « BTC Cassure tourne en H4 et non en H1, d10h1_btc.csv toujours
    introuvable » -> le fichier existe et est repare : on peut trancher.
  - « le simulateur FTMO garde ses defauts, les reussites sont des bornes
    superieures » -> on a maintenant le simulateur corrige.

On refait donc les deux resultats qui n'ont jamais ete verifies :
  1. CONCENTRATION : BTC Cassure fait-il vraiment 75 % du rendement et
     toutes les journees mortelles ?
  2. FILTRE MARCHE BAISSIER : ne pas ouvrir de nouvelle position quand le
     Nasdaq est a plus de X % sous son sommet (decide avec la veille).
     Le rapport annonce +10 points de reussite sur 10 ans et +16 sur le
     recent, avec un plateau de -12,5 % a -20 %."""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B

NQ = pd.read_csv(os.path.join(D, "d10_nq.csv"), parse_dates=["t"]).set_index("t")
_som = NQ["c"].cummax()
BAISSE = ((NQ["c"] / _som) - 1.0).shift(1)      # .shift(1) = decision avec la VEILLE

def sous_sommet(t):
    """recul du Nasdaq sous son sommet, connu la veille"""
    i = BAISSE.index.searchsorted(pd.Timestamp(t.date()), side="right") - 1
    if i < 0: return 0.0
    v = BAISSE.iloc[i]
    return 0.0 if pd.isna(v) else float(v)

def filtre(s, seuil):
    """bloque les NOUVELLES entrees quand le Nasdaq est trop bas"""
    sig0 = s.signal
    def sig(t):
        if sous_sommet(t) <= seuil: return None
        return sig0(t)
    s.signal = sig
    return s

def mesure(garde, be, seuil, deb, fin, detail=False):
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
        if seuil is not None:
            for s in sl: filtre(s, seuil)
        boite[:] = sl
        return sl
    ns["DEBUT"], ns["FIN"] = deb, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()
    o, m = B.ftmo(tj)
    if not detail: return r[0], o, m, r[2]
    # attribution par manche
    par = {}
    for s in boite:
        d = {}
        for tt, vv in s.pnl.items():
            j = tt.date(); d[j] = d.get(j, 0) + vv
        par[s.nom] = pd.Series(d)
    return r[0], o, m, r[2], tj, par

FEN = (("10 ANS ", "2015-08-21", "2026-12-31"), ("2021-26", "2021-01-01", "2026-08-20"))

# ---------- 1. CONCENTRATION ----------
print("=== 1. CONCENTRATION : qui fait le rendement, qui fait les mauvais jours ===")
print("   (chassis L8, donnees REPAREES, BTC en H1)")
cagr, o, m, dd, tj, par = mesure(0.0175, 0.05, None, "2015-08-21", "2026-12-31", detail=True)
tot = {n: s.sum()*100 for n, s in par.items()}
somme = sum(tot.values())
print("   %-14s | %10s | %6s" % ("manche", "cumul", "part"))
print("   " + "-"*36)
for n, v in sorted(tot.items(), key=lambda x: -x[1]):
    print("   %-14s | %+9.1f %% | %5.1f %%" % (n, v, 100*v/somme if somme else 0))

print()
print("   Les 10 pires journees et leur responsable :")
pires = tj.sort_values().head(10)
print("   %-12s | %8s | %s" % ("date", "total", "manche responsable"))
print("   " + "-"*52)
for d0, v in pires.items():
    j = d0.date()
    coup = max(((n, s.get(j, 0.0)) for n, s in par.items()), key=lambda x: -abs(x[1]))
    print("   %-12s | %+7.2f %% | %s %+.2f %%" % (j, v*100, coup[0], coup[1]*100))
n5 = int((tj <= -0.05).sum()); n3 = int((tj <= -0.03).sum())
print("   journees sous -5 %% : %d   |   sous -3 %% : %d" % (n5, n3))

# ---------- 2. FILTRE MARCHE BAISSIER ----------
print()
print("=== 2. FILTRE MARCHE BAISSIER (pas de nouvelle entree si Nasdaq bas) ===")
print("   (chassis L8 + R13, simulateur corrige, donnees REPAREES)")
print("   %-22s | %-26s | %s" % ("", "10 ANS", "2021-2026"))
print("   %-22s | %7s %8s %6s | %7s %8s %6s"
      % ("seuil", "CAGR", "reussite", "duree", "CAGR", "reussite", "duree"))
print("   " + "-"*76)
for seuil in (None, -0.075, -0.10, -0.125, -0.15, -0.175, -0.20, -0.25):
    etq = "aucun (L8)" if seuil is None else "Nasdaq sous %.1f %%" % (seuil*100)
    l = "   %-22s |" % etq
    for e, d0, f0 in FEN:
        c, o, m, dd = mesure(0.0175, 0.05, seuil, d0, f0)
        l += " %+6.1f %% %6.0f %% %4.0f j |" % (c, o, m)
    print(l)
