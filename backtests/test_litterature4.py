# -*- coding: utf-8 -*-
"""LITTERATURE 4e TOURNEE (livres + Reddit/forums/YouTube) sur L4.3.
Idees candidates issues de la recherche du 20 aout :
  B. Turtle Systeme 2 : canal d'entree 55 JOURS (consensus moderne :
     moins de faux signaux) -- cassure BTC + petrole ; sortie 10 j gardee
  C. voisin canal 40 j (stabilite)
  D. tampon anti-faux-signal : entree seulement si le declencheur depasse
     le canal de 0,1 % (D1) / 0,2 % (D2)
  E. time-stop : fermer un trade non profitable apres 10 jours
  F. filtre FUNDING BTC : pas d'achat quand le financement perpetuel
     moyen 3 j > 0,05 %/8h (longs surpeuples) -- donnees Binance 2019+
  G. cassure BTC seulement si BTC > sa propre moyenne 200 j
Moteur H4 realiste, config L4.3 (C2), mode ON, 10 ans + 2021-2026."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH

src = open(os.path.join(D, "test_l43_realiste.py"), encoding="utf-8").read()
src = src.split("BASE =")[0]
ns0 = {"__file__": os.path.join(D, "test_l43_realiste.py")}
exec(src, ns0)
ns, fabrique, f_or = ns0["ns"], ns0["fabrique"], None
dxy = ns["dxy"]
FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
f_or = lambda n, j: n == "Or" and j in FORT
C2 = {"Or": "H4", "Nasdaq": "H4", "BTC Cassure": "H1", "BTC EMA": "D1", "Petrole": "H4"}
BTC_H1 = ns0["BTC_H1"]

fund = pd.read_csv(os.path.join(D, "funding_btc.csv"), index_col=0, parse_dates=True)["taux"]
fund_j = fund.resample("1D").mean().rolling(3).mean().shift(1)
SURCHAUFFE = set(fund_j.index[fund_j > 0.0005].date)
btc_j = BTC_H1["c"].resample("1D").last().dropna()
BTC_E200 = set(btc_j.index[(btc_j > btc_j.ewm(span=200, adjust=False).mean()).shift(1).fillna(False)].date)

def canal(s, n_entree):
    s.H20J = pd.Series(s.DJH).rolling(n_entree).max().values
    return s

def tampon(s, pct):
    sig0 = s.signal
    def sig(t, s=s, sig0=sig0, pct=pct):
        r = sig0(t)
        if r is None: return None
        i = s.idx.get(t)
        k = s.KPREV[i]
        if r["entree"] <= s.H20J[k] * (1 + pct): return None
        return r
    s.signal = sig
    return s

def filtre_dates(s, exclues):
    sig0 = s.signal
    def sig(t, s=s, sig0=sig0):
        if t.date() in exclues: return None
        return sig0(t)
    s.signal = sig
    return s

def time_stop(s, jours=10):
    ouvrir0, gerer0 = s.ouvrir, s.gerer
    def ouvrir(t, **kw):
        ok = ouvrir0(t, **kw)
        if ok: s._t_in, s._px_in = t, kw.get("entree", 0)
        return ok
    def gerer(t):
        gerer0(t)
        if s.pos is not None and hasattr(s, "_t_in") and (t - s._t_in).days >= jours:
            i = s.idx.get(t)
            if i is not None and s.C[i] <= s._px_in:
                s._clore(t, s.C[i]); s.attente = None
    s.ouvrir, s.gerer = ouvrir, gerer
    return s

def variante(mod):
    base = fabrique(C2)
    def f():
        sl = base()
        for s in sl:
            mod(s)
        return sl
    return f

MODS = [
    ("A. L4.3 reference", lambda s: s),
    ("B. canal d'entree 55 j (S2 Turtle)", lambda s: canal(s, 55) if s.nom in ("BTC Cassure", "Petrole") else s),
    ("C. voisin canal 40 j", lambda s: canal(s, 40) if s.nom in ("BTC Cassure", "Petrole") else s),
    ("D1. tampon 0,1 % au-dela du canal", lambda s: tampon(s, 0.001) if s.nom in ("BTC Cassure", "Petrole") else s),
    ("D2. tampon 0,2 %", lambda s: tampon(s, 0.002) if s.nom in ("BTC Cassure", "Petrole") else s),
    ("E. time-stop 10 j si non profitable", lambda s: time_stop(s, 10) if s.nom in ("BTC Cassure", "Petrole") else s),
    ("F. funding >0,05%%/8h bloque achats BTC", lambda s: filtre_dates(s, SURCHAUFFE) if s.nom.startswith("BTC") else s),
    ("G. cassure BTC si BTC > e200 propre", lambda s: filtre_dates(s, {d for d in btc_j.index.date} - BTC_E200) if s.nom == "BTC Cassure" else s),
]
for etiquette, periode in (("10 ANS", ("2015-08-21", "2026-12-31")),
                           ("2021-2026", ("2021-01-01", "2026-08-20"))):
    print()
    print("=== %s (L4.3, mode ON) ===" % etiquette)
    for nom, mod in MODS:
        ns["DEBUT"], ns["FIN"] = periode
        ns["sleeves_l4"] = variante(mod)
        r = ns["sim_h4"](interdit=f_or)
        print("  %-42s : CAGR %+5.1f%% | reussite %3.0f %% | DD %+6.1f%%"
              % (nom, r[0], 100-r[3], r[2]))

print()
print("=== VOISINS DU TAMPON (0,10 -> 0,30 %) ===")
for pct in (0.001, 0.0015, 0.002, 0.0025, 0.003):
    mod = lambda s, p=pct: tampon(s, p) if s.nom in ("BTC Cassure", "Petrole") else s
    ligne = "  tampon %.2f %%" % (pct*100)
    for etiquette, periode in (("10a", ("2015-08-21", "2026-12-31")),
                               ("21-26", ("2021-01-01", "2026-08-20"))):
        ns["DEBUT"], ns["FIN"] = periode
        ns["sleeves_l4"] = variante(mod)
        r = ns["sim_h4"](interdit=f_or)
        ligne += " | %s : %+5.1f%% / %3.0f%%" % (etiquette, r[0], 100-r[3])
    print(ligne)
