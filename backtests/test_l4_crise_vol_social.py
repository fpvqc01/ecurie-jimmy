# -*- coding: utf-8 -*-
"""LES 3 IDEES DE JIMMY sur L4.3 (moteur H4 realiste, mode ON) :
1. MODE CRISE + SHORTS : regime risk-off detecte par la macro (Nasdaq
   sous sa moyenne 200 j) -> cassures BAISSIERES autorisees (Donchian
   symetrique : entree sous le plus bas 20 j, suiveur plus haut 10 j)
   sur Nasdaq, petrole et BTC pendant le regime seulement.
2. VOLUMES : cassure BTC H1 confirmee par volume (> 1,5 x moyenne 20).
3. SENTIMENT SOCIAL : Fear & Greed crypto -- pas de nouvel achat BTC
   quand la peur est extreme (< 20), teste aussi en contrarien.
Fenetres : 10 ans + 2021-2026."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH

BTC_H1V = pd.read_csv(os.path.join(D, "d10h1v_btc.csv"), index_col=0, parse_dates=True)
BTC_H1 = BTC_H1V[["o","h","l","c"]].astype(float)
VOL = BTC_H1V["v"].astype(float)
VOL_OK = (VOL > VOL.rolling(20).mean().shift(1) * 1.5)
FNG = pd.read_csv(os.path.join(D, "fng.csv"), index_col=0, parse_dates=True)["fng"]
PEUR = set(FNG.index[FNG < 20].date)

def charge(nom):
    return pd.read_csv(os.path.join(D, "d10h4_%s.csv" % nom), index_col=0,
                       parse_dates=True)[["o","h","l","c"]].astype(float)
NQ_J = charge("nq")["c"].resample("1D").last().dropna()
CRISE = set(NQ_J.index[(NQ_J < NQ_J.ewm(span=200, adjust=False).mean()).shift(1).fillna(False)].date)
print("Regime CRISE (Nasdaq < e200, veille) : %d%% du temps" % (100*len(CRISE)/len(NQ_J)))

def moteur():
    src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read().split('print()')[0]
    src = src.replace('if t >= pd.Timestamp("2015-08-21")]',
                      'if t >= pd.Timestamp(DEBUT) and t <= pd.Timestamp(FIN)]')
    ns = {"__file__": os.path.join(D, "test_l4_macro.py"),
          "DEBUT": "2015-08-21", "FIN": "2026-12-31"}
    exec(src, ns)
    ns["ORIG"] = ns["sleeves_l4"]
    return ns

ns = moteur()
dxy = ns["dxy"]
FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
f_or = lambda n, j: n == "Or" and j in FORT
NS2 = {"__file__": os.path.join(D, "valide_candidats_h4.py")}
exec(open(os.path.join(D, "valide_candidats_h4.py"), encoding="utf-8").read()
     .split("RISQUES =")[0], NS2)

def porte_d1(x):
    sig0 = x.signal
    def sig(t, x=x, sig0=sig0):
        i = x.idx.get(t)
        if i is None or not x.NEWDAY[i]: return None
        return sig0(t)
    x.signal = sig
    return x

def cassure_h1(filtre_volume=False, filtre_peur=False, contrarien=False):
    s = MH.DonchH4("BTC Cassure", BTC_H1, 0.015, 0.0004, -0.000833/4, 1.0)
    s.pyr_max = 4
    s.gerer = NS2["gerer_pyr_max"].__get__(s); s.ouvrir = MH.ouvrir_pyr.__get__(s)
    sig0 = s.signal
    def sig(t, s=s, sig0=sig0):
        if filtre_volume:
            ok = VOL_OK.get(t)
            if ok is not True: return None
        if filtre_peur and t.date() in PEUR: return None
        if contrarien and t.date() not in PEUR and FNG.get(pd.Timestamp(t.date()), 50) > 80:
            return None      # contrarien : pas d'achat en euphorie extreme
        return sig0(t)
    s.signal = sig
    return s

# ---- manche SHORT de crise (Donchian symetrique) ----
class DonchShortH4(MH.SleeveH4):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        dj_l = pd.Series(self.DJL); dj_h = pd.Series(self.DJH)
        self.B20J = dj_l.rolling(20).min().values     # canal bas 20 jours
        self.H10J = dj_h.rolling(10).max().values     # suiveur haut 10 jours
    def sortie_cloture(self, v): return False
    def gerer(self, t):
        i = self.idx.get(t)
        if i is None: return
        self._maj_jour(i)
        if self.pos is None: return
        p = self.pos
        c, h = self.C[i], self.H[i]
        k = self.KPREV[i]
        if k >= 0 and not np.isnan(self.H10J[k]) and self.H10J[k] < p["s"]:
            p["s"] = self.H10J[k]                     # suiveur descend
        if h >= p["s"]:                               # stop (short)
            self.pnl[t] = self.pnl.get(t, 0) + p["n"]*(p["prix"]-p["s"])/p["e"] - self.frais*p["n"]
            self.pos = None; return
        if t.date() not in CRISE:                     # fin du regime : on sort
            self.pnl[t] = self.pnl.get(t, 0) + p["n"]*(p["prix"]-c)/p["e"] - self.frais*p["n"]
            self.pos = None; return
        self.pnl[t] = self.pnl.get(t, 0) + p["n"]*((p["prix"]-c)/p["e"])
        p["prix"] = c
    def signal(self, t):
        if t.date() not in CRISE: return None
        i = self.idx.get(t)
        if i is None: return None
        k = self.KPREV[i]
        if k < 25 or np.isnan(self.B20J[k]) or np.isnan(self.H10J[k]): return None
        c = self.C[i]
        if c < self.B20J[k] and self.H10J[k] > c:
            return dict(entree=c, stop=self.H10J[k])
    def ouvrir(self, t, entree, stop):
        r0p = (stop - entree) / entree
        if r0p <= 0 or r0p > 0.5: return False
        n = min(self.risque / r0p, 2.0)
        self.pnl[t] = self.pnl.get(t, 0) - self.frais * n
        self.pos = dict(e=entree, s=stop, n=n, prix=entree)
        self.trades += 1
        return True

def fabrique(courts=False, vol=False, peur=False, contra=False):
    def f():
        s = []
        for x in ns["ORIG"]():
            if hasattr(x, "pyr_max"): x.pyr_max = 4
            if x.nom == "BTC Cassure":
                x = cassure_h1(vol, peur, contra)
            elif x.nom == "BTC EMA":
                x = porte_d1(x)
            s.append(x)
        if courts:
            s.append(DonchShortH4("Short NQ", charge("nq"), 0.01, 0.00003, 0, 1.0))
            s.append(DonchShortH4("Short CL", charge("cl"), 0.01, 0.00045, 0, 1.0))
            s.append(DonchShortH4("Short BTC", BTC_H1, 0.01, 0.0004, 0, 1.0))
            for y in s[-3:]:
                MH.FAM[y.nom] = "short"
        return s
    return f

def run(debut, fin, **kw):
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = fabrique(**kw)
    return ns["sim_h4"](interdit=f_or)

VARS = [("L4.3 reference", {}),
        ("1. + SHORTS en regime de crise", dict(courts=True)),
        ("2. + volume BTC (>1,5x moy 20)", dict(vol=True)),
        ("3a. + peur extreme bloque achats BTC", dict(peur=True)),
        ("3b. + contrarien (pas d'achat en euphorie)", dict(contra=True))]
for etiquette, periode in (("10 ANS", ("2015-08-21", "2026-12-31")),
                           ("2021-2026", ("2021-01-01", "2026-08-20"))):
    print()
    print("=== %s ===" % etiquette)
    for nom, kw in VARS:
        r = run(*periode, **kw)
        print("  %-44s : CAGR %+5.1f%% | reussite %3.0f %% | DD %+6.1f%%"
              % (nom, r[0], 100-r[3], r[2]))
