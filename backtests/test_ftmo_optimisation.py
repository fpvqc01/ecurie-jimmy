# -*- coding: utf-8 -*-
"""OPTIMISATION POUR LES CHALLENGES FTMO (demande de Jimmy, 20 aout).
Objectif : maximiser le taux de reussite du challenge (+10 % avant -8 %)
et la vitesse pour passer -- pas le CAGR. Chez FTMO la crypto est offerte,
donc la base est le L4 COMPLET (5 manches). Variantes testees :
  - ajouter les 4 candidats recurrents des tests OANDA (USD_JPY, AUD_JPY,
    Brent, JP225 -- tous offerts chez FTMO), a 1,5 %% ou 0,75 %%, cap 2/3
  - mode challenge plus agressif (throttle 0,5)
  - frein de drawdown (risque x0,5 si DD > 4 %%)
  - risque global x0,75 / x1,25
Challenges simules : fenetres glissantes demarrant tous les 21 jours ;
mortes si equite <= 0,92, reussies si >= 1,10 (duree notee). Gardien
-2,5 %% toujours actif (tient la limite quotidienne FTMO -5 %%).
Moteur 1d 5 ans + fenetre de validation 2024-2026."""
import os, pandas as pd, numpy as np
from moteur_1d import Fib, Donch, EmaBTC, ouvrir_pyr, gc, cl, nq, btc

src = open("scan_strategies.py", encoding="utf-8").read().split("RISQUES =")[0]
_ns = {"__file__": "scan_strategies.py"}; exec(src, _ns)
gerer_pyr_max = _ns["gerer_pyr_max"]

D = os.path.dirname(os.path.abspath(__file__))
def charger(sym):
    fn = os.path.join(D, "oanda_" + sym + ".csv")
    return pd.read_csv(fn, index_col=0, parse_dates=True)

CAND = {"USD_JPY": ("USDJPYX", "fx", 0.00010, -0.00005),
        "AUD_JPY": ("AUDJPYX", "fx", 0.00020, -0.00005),
        "BCO_USD": ("BZF",     "en", 0.00045, +0.00005),
        "JP225":   ("NKDF",    "mi", 0.00010, -0.00015)}
FAMX = {"Or": "mi", "Nasdaq": "mi", "Petrole": "en", "BTC Cassure": "cr", "BTC EMA": "cr"}
for n, (s, f, fr, sw) in CAND.items(): FAMX[n] = f

def construire(ajouts=(), risque_ajout=0.015, mult_risque=1.0):
    m = mult_risque
    sl = [Fib("Or", gc, 0.02*m, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
              lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
          Donch("Petrole", cl, 0.015*m, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
          Donch("BTC Cassure", btc, 0.015*m, 0.0004, -0.000833, 1.0),
          Fib("Nasdaq", nq, 0.015*m, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
              tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
          EmaBTC("BTC EMA", btc, 0.015*m, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0)]
    for nom in ajouts:
        sym, fam, frais, swap = CAND[nom]
        sl.append(Donch(nom, charger(sym), risque_ajout*m, frais, swap, 1.4))
    for s in sl:
        if s.nom in ("BTC Cassure", "Petrole") or s.nom in CAND:
            s.pyr_max = 3
            s.gerer = gerer_pyr_max.__get__(s); s.ouvrir = ouvrir_pyr.__get__(s)
    return sl

def sim(ajouts=(), cap=2, risque_ajout=0.015, mult_risque=1.0, throttle=0.75,
        frein=False, debut=None, fin=None):
    sl = construire(ajouts, risque_ajout, mult_risque)
    garde = -0.025
    dates = sorted(set().union(*[set(s.df.index) for s in sl]))
    if debut: dates = [x for x in dates if x >= pd.Timestamp(debut)]
    if fin: dates = [x for x in dates if x <= pd.Timestamp(fin)]
    equite, sommet, histo = 1.0, 1.0, []
    for d in dates:
        for s in sl: s.gerer(d)
        jt = sum(s.pnl.get(d, 0) for s in sl)
        if jt <= garde:
            f = garde / jt
            for s in sl:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            jt = garde
        equite *= (1 + jt); histo.append(equite); sommet = max(sommet, equite)
        if jt <= garde: continue
        fc = 1.0
        if throttle and len(histo) > 20 and equite < np.mean(histo[-20:]): fc = throttle
        if frein and equite < sommet * 0.96: fc = min(fc, 0.5)
        ouverts = sum(1 for s in sl if s.pos is not None)
        familles = {FAMX[s.nom] for s in sl if s.pos is not None}
        for s in sl:
            if s.pos is not None or ouverts >= cap: continue
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
    return tj.clip(lower=garde)

def stats_challenge(tj):
    """morts %, mediane de duree des reussites (jours calendrier ~ barres), CAGR"""
    vals = tj.values; morts = 0; durees = []
    for i0 in range(0, len(vals) - 40, 21):
        e2 = 1.0
        for jx in range(i0, len(vals)):
            e2 *= (1 + vals[jx])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: durees.append(jx - i0); break
    n = morts + len(durees)
    eq = (1 + tj).cumprod()
    ans = (tj.index[-1] - tj.index[0]).days / 365.25
    cagr = (eq.iloc[-1] ** (1/ans) - 1) * 100
    dd = ((eq / eq.cummax()) - 1).min() * 100
    return (morts/n*100 if n else 0), (np.median(durees) if durees else float("nan")), cagr, dd

C4 = ("USD_JPY", "AUD_JPY", "BCO_USD", "JP225")
CONFIGS = [
    ("L4 complet (reference)",              dict()),
    ("L4 + 4 cand. 1,5% cap 2",             dict(ajouts=C4)),
    ("L4 + 4 cand. 1,5% cap 3",             dict(ajouts=C4, cap=3)),
    ("L4 + 4 cand. 0,75% cap 3",            dict(ajouts=C4, risque_ajout=0.0075, cap=3)),
    ("L4 throttle 0,5",                     dict(throttle=0.5)),
    ("L4 + frein DD 4%",                    dict(frein=True)),
    ("L4 risque x0,75",                     dict(mult_risque=0.75)),
    ("L4 risque x1,25",                     dict(mult_risque=1.25)),
    ("L4 + 4 cand. 0,75% cap 3, thr 0,5",   dict(ajouts=C4, risque_ajout=0.0075, cap=3, throttle=0.5)),
]

print("=== OPTIMISATION CHALLENGE FTMO (moteur 1d) ===")
print("%-36s | %-26s | %-20s" % ("Config", "PLEINE PERIODE 2021-2026", "VALIDATION 2024-2026"))
print("%-36s | %-6s %-8s %-8s | %-6s %-8s" % ("", "Echecs", "MedJours", "CAGR", "Echecs", "MedJours"))
print("-" * 100)
for nom, kw in CONFIGS:
    m1, d1, c1, dd1 = stats_challenge(sim(**kw))
    m2, d2, c2, dd2 = stats_challenge(sim(debut="2024-01-01", **kw))
    print("%-36s | %5.0f%% %6.0f j  %+6.1f%%  | %5.0f%% %6.0f j"
          % (nom, m1, d1, c1, m2, d2))
print()
print("Echecs = %% de challenges glissants touchant -8 %% avant +10 %%.")
print("MedJours = duree mediane (jours de bourse) pour atteindre +10 %%.")
print("Gardien -2,5 %% actif partout (tient la limite quotidienne FTMO).")
