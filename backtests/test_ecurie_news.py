# -*- coding: utf-8 -*-
"""L'ecurie si elle ne trade QUE autour des nouvelles economiques US.
Calendrier reconstruit (approximation honnete, 5 ans) :
  - NFP : premier vendredi du mois
  - CPI : le 12 du mois (decale au jour ouvrable suivant)
  - FOMC : 8 reunions/an (dates types : fin jan, mi-mars, debut mai, mi-juin,
    fin juil, mi-sept, debut nov, mi-dec, decalees au mercredi)
Configs : A ecurie normale | B entrees SEULEMENT 0-2 j apres une annonce |
C entrees seulement HORS fenetre (controle) | D fenetre elargie 0-4 j.
Les sorties/stops ne changent jamais — seul le droit d'ENTRER varie."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

# --- calendrier des annonces ---
def premier_vendredi(annee, mois):
    d = pd.Timestamp(annee, mois, 1)
    return d + pd.Timedelta(days=(4 - d.dayofweek) % 7)

def jour_ouvrable(d):
    while d.dayofweek >= 5: d += pd.Timedelta(days=1)
    return d

evenements = []
for an in range(2021, 2027):
    for mois in range(1, 13):
        evenements.append(premier_vendredi(an, mois))            # NFP
        evenements.append(jour_ouvrable(pd.Timestamp(an, mois, 12)))  # CPI
    for mois, jour in ((1, 28), (3, 18), (5, 6), (6, 17), (7, 29), (9, 16), (11, 4), (12, 16)):
        d = pd.Timestamp(an, mois, jour)                         # FOMC
        d = d + pd.Timedelta(days=(2 - d.dayofweek) % 7)         # au mercredi
        evenements.append(d)
evenements = pd.DatetimeIndex(sorted(set(evenements)))
print(f"Calendrier reconstruit : {len(evenements)} annonces sur 2021-2026 (~{len(evenements)//6}/an)")

def dates_permises(dates, fenetre):
    """Jours de marche situes 0..fenetre jours de MARCHE apres une annonce."""
    idx = pd.DatetimeIndex(dates)
    ok = set()
    for ev in evenements:
        apres = idx[idx >= ev]
        for d in apres[:fenetre + 1]: ok.add(d)
    return ok

def sim(filtre=None, fenetre=2, inverse=False):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    permises = dates_permises(dates, fenetre) if filtre else None
    nb_entrees = 0
    for date in dates:
        for s in sleeves: s.gerer(date)
        if filtre:
            dans_fenetre = date in permises
            if (not inverse and not dans_fenetre) or (inverse and dans_fenetre):
                continue
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        for s in sleeves:
            if s.pos is not None: continue
            sig = s.signal(date)
            if sig is None: continue
            if ouverts >= 2: continue
            if s.ouvrir(date, **sig): ouverts += 1; nb_entrees += 1
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    creux = (eq.min()-1)*100; pire = total.min()*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    return cagr, creux, pire, sh, nb_entrees, c1, c2

print(f"\n{'Config':<38} | {'CAGR':>6} | {'Sharpe':>6} | {'Trades':>6} | {'Moities':>13}")
print("-" * 84)
for nom, kw in [
    ("A. Ecurie normale (reference)", dict()),
    ("B. Entrees 0-2 j APRES une annonce", dict(filtre=True, fenetre=2)),
    ("D. Entrees 0-4 j apres une annonce", dict(filtre=True, fenetre=4)),
    ("C. Entrees seulement HORS fenetre 0-2", dict(filtre=True, fenetre=2, inverse=True)),
]:
    r = sim(**kw)
    print(f"{nom:<38} | {r[0]:>+5.1f}% | {r[3]:>6.2f} | {r[4]:>6} | {r[5]:>+5.1f}/{r[6]:>+5.1f}%")
