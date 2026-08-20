# -*- coding: utf-8 -*-
"""IDEE DE JIMMY : ajouter le robot TradingView (RSI retour a la moyenne)
sur l'or comme 6e manche de L4 -- comme les deux robots BTC (H1+H4).
Strategie du Pine Script : achat quand RSI(14) < 30 (survente) AVEC filtre
de tendance SMA200 (prix au-dessus), stop 2xATR, TP 3xATR.
Variantes (moteur H4, 10 ans, config L4.2 deployee : pyr4 + filtre dollar) :
  A. L4.2 reference
  B. + Or RSI 1,5 % DANS la famille metal/indice (le plafond arbitre)
  C. + Or RSI 1,5 % HORS famille (les DEUX ors peuvent trader ensemble)
  D. Or RSI seul (que vaut la strategie isolee ?)"""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read()
ns = {"__file__": os.path.join(D, "test_l4_macro.py")}
exec(src.split('print()')[0], ns)
import moteur_h4 as MH
dxy = ns["dxy"]
FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
f_or = lambda n, j: n == "Or" and j in FORT     # filtre dollar sur l'or FIB seulement

class RsiOrH4(MH.SleeveH4):
    """RSI retour a la moyenne du bot TradingView, sur l'or."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.SMA200 = pd.Series(self.DJC).rolling(200).mean().values
    def sortie_cloture(self, v): return False
    def signal(self, t):
        i = self.idx.get(t)
        if i is None: return None
        v = self.prov(i)
        if v is None: return None
        a, rsi = v[0], v[1]
        k = self.KPREV[i]
        if k < 200 or np.isnan(self.SMA200[k]): return None
        c = v[9]
        if c <= self.SMA200[k]: return None        # filtre de tendance du Pine
        if rsi >= 30: return None                  # survente
        return dict(entree=c, stop=c - 2*a, tp=c + 3*a)

def sim(avec_rsi, famille_rsi, seul=False):
    orig = ns["sleeves_l4"]
    def sl():
        s = [] if seul else orig()
        for x in s:
            if hasattr(x, "pyr_max"): x.pyr_max = 4          # pyramide 4 (L4.2)
        if avec_rsi or seul:
            r = RsiOrH4("Or RSI", MH.GC, 0.015, 0.0001, -0.000273, 1.4)
            s.append(r)
        return s
    MH.FAM["Or RSI"] = famille_rsi
    ns["sleeves_l4"] = sl
    try:
        return ns["sim_h4"](interdit=(None if seul else f_or))
    finally:
        ns["sleeves_l4"] = orig

print("=== L4.2 + robot TradingView RSI sur l'or (H4, 10 ans) ===")
print("  %-46s | %-7s | %-6s | %-7s | %s" % ("Variante", "CAGR", "Sharpe", "MaxDD", "Morts"))
print("  " + "-" * 82)
for nom, kw in (
    ("A. L4.2 reference (pyr4 + filtre dollar)", dict(avec_rsi=False, famille_rsi="mi")),
    ("B. + Or RSI dans la famille metal/indice", dict(avec_rsi=True, famille_rsi="mi")),
    ("C. + Or RSI HORS famille (2 ors ensemble)", dict(avec_rsi=True, famille_rsi="rsi")),
    ("D. Or RSI tout seul", dict(avec_rsi=True, famille_rsi="rsi", seul=True)),
):
    c, s, d, m, a1, a2 = sim(**kw)
    print("  %-46s | %+6.1f%% | %6.2f | %+6.1f%% | %4.0f%% | %+5.1f/%+5.1f%%"
          % (nom, c, s, d, m, a1, a2))

# ---- variante E : RSI natif H4 (plus proche du bot TradingView en 1h) ----
class RsiOrH4Natif(MH.SleeveH4):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        c = pd.Series(self.C)
        d = c.diff()
        ag = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        ap = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        self.RSIB = (100 - 100/(1 + ag/ap.replace(0, np.nan))).values
        self.SMAB = c.rolling(200).mean().values
        tr = np.maximum(pd.Series(self.H)-pd.Series(self.L),
             np.maximum((pd.Series(self.H)-c.shift()).abs(), (pd.Series(self.L)-c.shift()).abs()))
        self.ATRB = tr.ewm(alpha=1/14, adjust=False).mean().values
    def sortie_cloture(self, v): return False
    def signal(self, t):
        i = self.idx.get(t)
        if i is None or i < 210: return None
        if self.prov(i) is None: return None
        c = self.C[i]; rsi = self.RSIB[i]; sma = self.SMAB[i]; a = self.ATRB[i]
        if np.isnan(rsi) or np.isnan(sma) or a <= 0: return None
        if c <= sma or rsi >= 30: return None
        return dict(entree=c, stop=c - 2*a, tp=c + 3*a)

def simE(famille_rsi, seul=False):
    orig = ns["sleeves_l4"]
    def sl():
        s = [] if seul else orig()
        for x in s:
            if hasattr(x, "pyr_max"): x.pyr_max = 4
        s.append(RsiOrH4Natif("Or RSI", MH.GC, 0.015, 0.0001, -0.000273, 1.4))
        return s
    MH.FAM["Or RSI"] = famille_rsi
    ns["sleeves_l4"] = sl
    try:
        return ns["sim_h4"](interdit=(None if seul else f_or))
    finally:
        ns["sleeves_l4"] = orig

print()
print("=== variante E : RSI natif H4 (rythme proche du bot TradingView) ===")
for nom, kw in (("E1. + Or RSI H4 dans la famille mi", dict(famille_rsi="mi")),
                ("E2. + Or RSI H4 HORS famille (2 ors)", dict(famille_rsi="rsi")),
                ("E3. Or RSI H4 tout seul", dict(famille_rsi="rsi", seul=True))):
    c, s, d, m, a1, a2 = simE(**kw)
    print("  %-42s | %+6.1f%% | %6.2f | %+6.1f%% | %4.0f%% | %+5.1f/%+5.1f%%"
          % (nom, c, s, d, m, a1, a2))
