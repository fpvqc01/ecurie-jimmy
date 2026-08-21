# -*- coding: utf-8 -*-
"""BANC D'ESSAI DES SUGGESTIONS DU COMITE EXTERNE No 4 (vitesse) :
simulateur FTMO exact (2 phases) sur config L6 (a x0,75), 10 ans propres.
A. reference L6 x1,0
B. x1,33 permanent (gardien -2,5 % maintenu)
C. DEPART en regime favorable seulement (BTC > EMA200 journaliere)
D. risque degressif : des +4 % dans la phase, mises reduites a 70 %
E. turbo-coussin : x1,33 jusqu'a +4 % de la phase, puis x1,0
F. combo Grok no 1 : x1,33 permanent + depart en regime favorable
G. TP courts or/nasdaq (1,2R / 0,8R) — serie regeneree par le moteur
H. concentration : or/nasdaq/petrole coupes quand BTC > EMA200"""
import os, numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "options_optimisation.py"), encoding="utf-8").read()
src = src.split("OPTIONS = [")[0]
ns0 = {"__file__": os.path.join(D, "options_optimisation.py")}
exec(src, ns0)
ns, fab_option, f_or = ns0["ns"], ns0["fab_option"], ns0["f_or"]
run, fab_l431 = ns0["run"], ns0["fab_l431"]
interne = ns0["ns0"]          # espace de tests_comite_B (charge par options_optimisation)
OR0, NQ0 = interne["OR0"], interne["NQ0"]

ALLOC = {"Or": 0.0075, "Nasdaq": 0.0075, "Petrole": 0.0169,
         "BTC Cassure": 0.0169, "BTC EMA": 0.0113}
def a075(sl):
    for s in sl:
        if s.nom in ALLOC: s.risque = ALLOC[s.nom]

BTC_H1 = interne["BTC_H1"]
btc_j = BTC_H1["c"].resample("1D").last().dropna()
e200 = btc_j.ewm(span=200, adjust=False).mean()
TREND = set(btc_j.index[(btc_j > e200).shift(1).fillna(False)].date)

def serie(post=None, or_params=None, nq_params=None, interdit=None):
    ns["DEBUT"], ns["FIN"] = "2015-08-21", "2026-12-31"
    if or_params or nq_params:
        ns["sleeves_l4"] = fab_l431(or_params=or_params, nq_params=nq_params)
        base = ns["sleeves_l4"]
        def f():
            sl = base()
            a075(sl)
            return sl
        ns["sleeves_l4"] = f
    else:
        ns["sleeves_l4"] = fab_option(post or a075)
    r = ns["sim_h4"](interdit=interdit or f_or)
    return r[0], r[3], r[6].sort_index()

def phase(vals, i0, cible, mult, coussin=None, turbo=None):
    """coussin=(seuil, reduction) : des que eq>=1+seuil, mises x reduction.
    turbo=(seuil,) : mult jusqu'a eq>=1+seuil, puis x1,0."""
    eq = 1.0; jt = 0
    for j in range(i0, len(vals)):
        m = mult
        if turbo and eq >= 1 + turbo[0]: m = 1.0
        if coussin and eq >= 1 + coussin[0]: m = mult * coussin[1]
        r = vals[j] * m
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j - i0 + 1
        eq *= (1 + r)
        if eq <= 0.90: return 0, j - i0 + 1
        if eq >= 1 + cible and jt >= 4: return 1, j - i0 + 1
    return -1, len(vals) - i0

def sim(tj, mult=1.0, coussin=None, turbo=None, dates_depart=None):
    vals = tj.values; dates = tj.index.date
    complets = morts = 0; durees = []
    for i0 in range(0, len(vals) - 60, 3):
        if dates_depart is not None and dates[i0] not in dates_depart: continue
        v1, d1 = phase(vals, i0, 0.10, mult, coussin, turbo)
        if v1 == -1: continue
        if v1 == 0: morts += 1; continue
        v2, d2 = phase(vals, i0 + d1, 0.05, mult, coussin, turbo)
        if v2 == -1: continue
        if v2 == 0: morts += 1; continue
        complets += 1; durees.append(d1 + d2)
    n = complets + morts
    return (100.0 * complets / max(n, 1), np.median(durees) if durees else 0, n)

cagr0, m0, tj0 = serie()
print("serie de reference L6 : CAGR %+.1f %% | reussite fenetres %.0f %%" % (cagr0, 100 - m0))
print()
for nom, kw in (
    ("A. reference L6 x1,0", {}),
    ("B. x1,33 permanent", dict(mult=1.33)),
    ("C. depart si BTC > EMA200 seulement", dict(dates_depart=TREND)),
    ("D. degressif : mises x0,70 des +4 % de phase", dict(coussin=(0.04, 0.70))),
    ("E. turbo-coussin : x1,33 jusqu'a +4 %, puis x1,0", dict(mult=1.33, turbo=(0.04,))),
    ("F. combo Grok 1 : x1,33 + depart en regime", dict(mult=1.33, dates_depart=TREND)),
):
    ok, med, n = sim(tj0, **kw)
    print("%-48s : reussite %3.0f %% | duree mediane %3.0f j | %d departs" % (nom, ok, med, n))

print()
cagrG, mG, tjG = serie(or_params=dict(OR0, tpj=1.2), nq_params=dict(NQ0, tpj=0.8))
ok, med, n = sim(tjG)
print("%-48s : reussite %3.0f %% | duree mediane %3.0f j | CAGR %+.1f %% (vs %+.1f)"
      % ("G. TP courts or 1,2R / nasdaq 0,8R", ok, med, cagrG, cagr0))

f_conc = lambda nom, jour: (nom in ("Or", "Nasdaq", "Petrole") and jour in TREND) or f_or(nom, jour)
cagrH, mH, tjH = serie(interdit=f_conc)
ok, med, n = sim(tjH)
print("%-48s : reussite %3.0f %% | duree mediane %3.0f j | CAGR %+.1f %%"
      % ("H. or/nasdaq/petrole coupes si BTC>e200", ok, med, cagrH))
