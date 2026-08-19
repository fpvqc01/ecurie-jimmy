# -*- coding: utf-8 -*-
"""IDEES DE LA LITTERATURE jamais testees sur l'ecurie (19 aout 2026).
Sources : Hurst/Ooi/Pedersen « A Century of Evidence on Trend-Following »
(AQR, ensemble de horizons), Moskowitz/Ooi/Pedersen « Time Series Momentum »
(filtre 12 mois), Dennis/Eckhardt (regles des Turtles : pyramidage a 0,5N,
plafonds par marche correle, portfolio heat).
Toutes testees au niveau du PORTEFEUILLE avec gardien -3,5 %/jour actif."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

GARDE = -0.035

# ---------- Idee 1 : filtre time-series momentum 12 mois (Moskowitz et al.) ----------
def filtre_tsmom(s, mois=12):
    n = int(mois * 21)
    original = s.signal
    def signal_mod(date, s=s, original=original, n=n):
        sig = original(date)
        if sig is None: return None
        i = s.jour(date)
        if i is None or i < n: return None
        if s.df["c"].iloc[i] <= s.df["c"].iloc[i-n]: return None   # tendance 12 m negative
        return sig
    s.signal = signal_mod

# ---------- Idee 2 : pyramidage Turtle (ajout d'unites a +0,5 ATR) ----------
def gerer_avec_pyramide(self, date):
    i = self.jour(date)
    if i is None or self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    a = self.a.iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        self._clore(date, p["s"]); self.attente = None; return
    # --- ajout d'unites facon Turtle : chaque +0,5 ATR au-dessus du dernier ajout
    while p["unites"] < self.max_unites and h >= p["prochain"]:
        prix_ajout = p["prochain"]
        n_ajout = min(p["n0"], 2.0 - p["n"])
        if n_ajout <= 0: break
        self.pnl[date] = self.pnl.get(date, 0) + n_ajout*(c - prix_ajout)/p["e"] - self.frais*n_ajout
        p["n"] += n_ajout
        p["unites"] += 1
        p["prochain"] = prix_ajout + 0.5*a
    if p.get("tp") and h >= p["tp"]:
        tp = p["tp"]; self._clore(date, tp)
        if self.jimmy: self.attente = tp
        return
    if p.get("be") and not p["be_fait"] and h >= p["be"]:
        p["s"] = max(p["s"], p["e"]); p["be_fait"] = True
    if p.get("sortie_cloture") and self.sortie_cloture(i):
        self._clore(date, c); self.attente = None; return
    self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
    p["prix"] = c

def ouvrir_avec_pyramide(self, date, entree, stop, tp=None, be=None, trail=False, sortie_cloture=False):
    r0p = (entree - stop) / entree
    if r0p <= 0 or r0p > 0.5: return False
    n = min(self.risque / r0p, 2.0)
    self.pnl[date] = self.pnl.get(date, 0) - self.frais * n
    i = self.jour(date); a = self.a.iloc[i]
    self.pos = dict(e=entree, s=stop, tp=tp, n=n, n0=n, be=be, be_fait=False,
                    prix=entree, trail=trail, sortie_cloture=sortie_cloture,
                    unites=1, prochain=entree + 0.5*a)
    self.trades += 1; self.attente = None
    return True

# ---------- moteur commun ----------
def sim(variante="ref"):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    sous_jacent = {"Or": "XAU", "Petrole": "OIL", "BTC Cassure": "BTC",
                   "Nasdaq": "NQ", "BTC EMA": "BTC"}

    if variante == "tsmom":
        for s in sleeves: filtre_tsmom(s, 12)
    if variante == "tsmom6":
        for s in sleeves: filtre_tsmom(s, 6)
    if variante in ("pyramide", "pyramide3"):
        for s in sleeves:
            if s.nom in ("BTC Cassure", "Petrole"):
                s.max_unites = 2 if variante == "pyramide" else 3
                s.gerer = gerer_avec_pyramide.__get__(s)
                s.ouvrir = ouvrir_avec_pyramide.__get__(s)

    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    coupes = 0
    for date in dates:
        for s in sleeves: s.gerer(date)
        jt = sum(s.pnl.get(date, 0) for s in sleeves)
        if jt <= GARDE:
            f = GARDE / jt
            for s in sleeves:
                if date in s.pnl: s.pnl[date] *= f
                if s.pos is not None:
                    s.pnl[date] = s.pnl.get(date, 0) - s.frais * s.pos["n"]
                s.pos = None; s.attente = None; s.runners = []
            coupes += 1
            continue
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        occupes = {sous_jacent[s.nom] for s in sleeves if s.pos is not None}
        for s in sleeves:
            if s.pos is not None: continue
            sig = s.signal(date)
            if sig is None: continue
            if ouverts >= 2: continue
            if variante == "correlation" and sous_jacent[s.nom] in occupes: continue
            if s.ouvrir(date, **sig):
                ouverts += 1; occupes.add(sous_jacent[s.nom])
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    pire = total.min()*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    return cagr, sh, pire, coupes, c1, c2

print(f"{'Idee de la litterature (gardien actif)':<44} | {'CAGR':>6} | {'Sharpe':>6} | {'PireJ':>6} | {'Coupes':>6} | {'Moities':>13}")
print("-" * 104)
for nom, v in [
    ("Reference (ecurie actuelle)", "ref"),
    ("Filtre TSMOM 12 mois (Moskowitz+)", "tsmom"),
    ("Filtre TSMOM 6 mois", "tsmom6"),
    ("Pyramidage Turtle 2 unites (+0,5 ATR)", "pyramide"),
    ("Pyramidage Turtle 3 unites", "pyramide3"),
    ("Plafond par sous-jacent (1 BTC max)", "correlation"),
]:
    r = sim(v)
    print(f"{nom:<44} | {r[0]:>+5.1f}% | {r[1]:>6.2f} | {r[2]:>+5.2f}% | {r[3]:>6} | {r[4]:>+5.1f}/{r[5]:>+5.1f}%")
