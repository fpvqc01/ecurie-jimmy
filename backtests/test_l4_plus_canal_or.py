# -*- coding: utf-8 -*-
"""L4 + LA STRATEGIE DU ROBOT POWERSHELL SUR L'OR (gold-news-bot) :
cassure du canal 20 en H4, sortie suiveuse (plus bas 10 barres H4),
validee 2006-2026 a ~3-4 %/an avec 0,5 %/trade.
Variantes (les 2 moteurs) :
  A. L4 reference (5 manches)
  B. L4 + canal or a 0,5 % (le reglage du bot OANDA)
  C. L4 + canal or a 1,0 %
  D. L4 ou le canal REMPLACE l'or fib (canal a 2,0 %)
Le canal est dans la famille metal/indice : le plafond de correlation
s'applique (jamais deux positions or en meme temps).
En H4 : canal exact (20 barres H4). En 1d : approximation (canal 4 jours,
sortie 2 jours) -- a lire comme indicatif seulement."""
import pandas as pd, numpy as np
from moteur_1d import Fib, gc
import moteur_h4 as MH
Sleeve = Fib.__mro__[1]      # classe de base du moteur 1d (non exportee)

src = open("combo_l4.py", encoding="utf-8").read().split("MARCHES =")[0]
ns = {"__file__": "combo_l4.py"}; exec(src, ns)
sleeves_1d, sleeves_h4 = ns["sleeves_1d"], ns["sleeves_h4"]
FAM_1D, FAM_H4 = dict(ns["FAM"]), dict(MH.FAM)
FAM_1D["Or Canal"] = "mi"; FAM_H4["Or Canal"] = "mi"
metriques = ns["metriques"]

# ---- canal H4 exact (le vrai bot) ----
class CanalOrH4(MH.SleeveH4):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        H = pd.Series(self.H); L = pd.Series(self.L)
        self.H20B = H.rolling(20).max().shift(1).values   # canal 20 barres H4
        self.L10B = L.rolling(10).min().shift(1).values   # sortie suiveuse 10 barres
    def sortie_cloture(self, v): return False
    def gerer(self, t):
        i = self.idx.get(t)
        if i is None: return
        self._maj_jour(i)
        if self.pos is None: return
        p = self.pos
        l = self.L[i]; c = self.C[i]
        b = self.L10B[i]
        if not np.isnan(b) and b > p["s"]: p["s"] = b        # suiveur
        if l <= p["s"]:
            self._clore(t, p["s"]); return
        self.pnl[t] = self.pnl.get(t, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs/MH.BPJ)
        p["prix"] = c
    def signal(self, t):
        i = self.idx.get(t)
        if i is None or i < 25: return None
        h20 = self.H20B[i]; b10 = self.L10B[i]
        if np.isnan(h20) or np.isnan(b10): return None
        c = self.C[i]
        if c > h20 and b10 < c:
            return dict(entree=c, stop=b10)
        return None

# ---- approximation 1d (canal 4 jours, sortie 2 jours) ----
class CanalOr1d(Sleeve):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.h4j = self.df["h"].rolling(4).max().shift(1)
        self.b2j = self.df["l"].rolling(2).min().shift(1)
    def sortie_cloture(self, i): return False
    def gerer(self, date):
        i = self.jour(date)
        if i is None or self.pos is None: return
        p = self.pos
        c, l = self.df["c"].iloc[i], self.df["l"].iloc[i]
        b = self.b2j.iloc[i]
        if not np.isnan(b) and b > p["s"]: p["s"] = b
        if l <= p["s"]:
            self._clore(date, p["s"]); return
        self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
        p["prix"] = c
    def signal(self, date):
        i = self.jour(date)
        if i is None or i < 6: return None
        h, b = self.h4j.iloc[i], self.b2j.iloc[i]
        if np.isnan(h) or np.isnan(b): return None
        c = self.df["c"].iloc[i]
        if c > h and b < c:
            return dict(entree=c, stop=b)
        return None

BASE = ("Or", "Petrole", "Nasdaq", "BTC Cassure", "BTC EMA")

def sim_generic(sl, fam, h4):
    garde = -0.025
    if h4:
        ts = [t for t in sorted(set().union(*[set(s.index) for s in sl]))
              if t >= pd.Timestamp("2024-08-21")]
    else:
        ts = sorted(set().union(*[set(s.df.index) for s in sl]))
    jour_pnl, jour_cour, jour_stop = 0.0, None, False
    eq, eq_jours, histo, equite = 1.0, [], [], 1.0
    for t in ts:
        if h4:
            j = t.date()
            if j != jour_cour:
                if jour_cour is not None: eq *= (1+jour_pnl); eq_jours.append(eq)
                jour_cour, jour_pnl, jour_stop = j, 0.0, False
            avant = [s.pnl.get(t, 0) for s in sl]
        for s in sl: s.gerer(t)
        if h4:
            jour_pnl += sum(s.pnl.get(t, 0)-avant[q] for q, s in enumerate(sl))
            if jour_stop: continue
            if jour_pnl <= garde:
                av3 = [s.pnl.get(t, 0) for s in sl]
                for s in sl:
                    if s.pos is not None:
                        i = s.idx.get(t)
                        if i is not None: s._clore(t, s.C[i])
                    s.attente = None
                jour_pnl += sum(s.pnl.get(t, 0)-av3[q] for q, s in enumerate(sl))
                jour_stop = True; continue
            fc = 0.75 if (len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0
        else:
            jt = sum(s.pnl.get(t, 0) for s in sl)
            if jt <= garde:
                f = garde/jt
                for s in sl:
                    if t in s.pnl: s.pnl[t] *= f
                    s.pos = None; s.attente = None
                    if hasattr(s, "runners"): s.runners = []
                jt = garde
            equite *= (1+jt); histo.append(equite)
            if jt <= garde: continue
            fc = 0.75 if (len(histo) > 20 and equite < np.mean(histo[-20:])) else 1.0
        ouverts = sum(1 for s in sl if s.pos is not None)
        familles = {fam[s.nom] for s in sl if s.pos is not None}
        for s in sl:
            if s.pos is not None or ouverts >= 2: continue
            if fam[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(t)
            if sig is None: continue
            r0 = s.risque; s.risque = r0*fc
            av2 = s.pnl.get(t, 0)
            ok = s.ouvrir(t, **sig); s.risque = r0
            if ok:
                if h4: jour_pnl += s.pnl.get(t, 0)-av2
                ouverts += 1; familles.add(fam[s.nom])
    tot = {}
    for s in sl:
        for tt, vv in s.pnl.items():
            jj = tt.date() if h4 else tt
            tot[jj] = tot.get(jj, 0)+vv
    if h4:
        tous = sorted({t.date() for t in ts})
        tj = pd.Series([tot.get(j, 0.0) for j in tous], index=pd.DatetimeIndex(tous))
    else:
        tj = pd.Series(0.0, index=pd.DatetimeIndex(ts))
        for k2, v in tot.items():
            if k2 in tj.index: tj[k2] += v
        tj = tj.clip(lower=garde)
    return metriques(tj)

def variante(nom_v, risque_canal, remplace):
    marches = tuple(m for m in BASE if not (remplace and m == "Or"))
    # 1d
    sl1 = sleeves_1d(marches)
    if risque_canal:
        sl1.append(CanalOr1d("Or Canal", gc, risque_canal, 0.0001, -0.000273, 1.4))
    r1 = sim_generic(sl1, FAM_1D, h4=False)
    # H4
    sl2 = sleeves_h4(marches)
    if risque_canal:
        sl2.append(CanalOrH4("Or Canal", MH.GC, risque_canal, 0.0001, -0.000273, 1.4))
    r2 = sim_generic(sl2, FAM_H4, h4=True)
    print("%-38s | %+5.1f%% %5.0f%%  | %+5.1f%% %5.0f%%  | %+6.1f%% %4.0f%%"
          % (nom_v, r1[0], r1[1], r2[0], r2[1], (r1[0]+r2[0])/2, max(r1[1], r2[1])))

print("%-38s | %-14s | %-14s | %-7s %s" % ("Variante", "1d 5 ans*", "H4 2 ans", "MOYEN", "PIRE"))
print("%-38s | %-6s %-7s | %-6s %-7s |" % ("", "CAGR", "Morts", "CAGR", "Morts"))
print("-" * 96)
variante("A. L4 reference (5 manches)", None, False)
variante("B. L4 + canal or 0,5 % (reglage bot)", 0.005, False)
variante("C. L4 + canal or 1,0 %", 0.010, False)
variante("D. canal 2,0 % REMPLACE l'or fib", 0.020, True)
print()
print("* 1d = approximation du canal (4 jours) ; le H4 est le canal exact du bot.")
# le canal seul, H4, pour verifier qu'on retrouve l'ordre de grandeur du bot (~3-4 %/an)
sl = [CanalOrH4("Or Canal", MH.GC, 0.005, 0.0001, -0.000273, 1.4)]
r = sim_generic(sl, FAM_H4, h4=True)
print("Canal or SEUL a 0,5 %% (H4 2 ans) : %+.1f %%/an -- attendu ~3-4 %% (2006-2026)" % r[0])
