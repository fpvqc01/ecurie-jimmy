# -*- coding: utf-8 -*-
"""LA VRAIE REGLE DES TURTLES (intuition de Jimmy, 19 aout) : quand on ajoute
une unite, le stop de TOUTE la position remonte a k x ATR sous la DERNIERE
unite achetee. Le stop monte donc avec la pyramide -> la perte totale reste
plafonnee meme avec 4 unites.
Mon test precedent gardait le stop du canal Donchian (loin en dessous) : c'est
ce qui creait la journee brute a -7,74 %.
On balaye k = 1,0 / 1,5 / 2,0 / 2,5 ATR et le canal seul (reference), pour
3 et 4 unites, avec gardien -2,5 % et -3,0 %."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

def gerer_pyr(self, date):
    i = self.jour(date)
    if i is None or self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    o = self.df["o"].iloc[i]; a = self.a.iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        self._clore(date, min(p["s"], o)); self.attente = None; return
    while p["unites"] < self.max_unites and h >= p["prochain"]:
        prix_ajout = max(p["prochain"], o)
        n_ajout = min(p["n0"], 2.0 - p["n"])
        if n_ajout <= 0: break
        self.pnl[date] = self.pnl.get(date, 0) + n_ajout*(c - prix_ajout)/p["e"] - self.frais*n_ajout
        p["n"] += n_ajout; p["unites"] += 1
        p["prochain"] = p["prochain"] + self.pas_unite*a
        # === REGLE TURTLE : le stop remonte sous la derniere unite ===
        if self.k_stop is not None:
            p["s"] = max(p["s"], prix_ajout - self.k_stop * a)
    if p.get("tp") and h >= p["tp"]:
        tp = p["tp"]; self._clore(date, tp)
        if self.jimmy: self.attente = tp
        return
    if p.get("sortie_cloture") and self.sortie_cloture(i):
        self._clore(date, c); self.attente = None; return
    self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
    p["prix"] = c

def ouvrir_pyr(self, date, entree, stop, tp=None, be=None, trail=False, sortie_cloture=False):
    r0p = (entree - stop) / entree
    if r0p <= 0 or r0p > 0.5: return False
    n = min(self.risque / r0p, 2.0)
    self.pnl[date] = self.pnl.get(date, 0) - self.frais * n
    i = self.jour(date); a = self.a.iloc[i]
    self.pos = dict(e=entree, s=stop, tp=tp, n=n, n0=n, be=be, be_fait=False,
                    prix=entree, trail=trail, sortie_cloture=sortie_cloture,
                    unites=1, prochain=entree + self.pas_unite*a)
    self.trades += 1; self.attente = None
    return True

def serie(unites, garde, k_stop):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    if unites > 1:
        for s in sleeves:
            if s.nom in ("BTC Cassure", "Petrole"):
                s.max_unites, s.pas_unite, s.k_stop = unites, 0.5, k_stop
                s.gerer = gerer_pyr.__get__(s)
                s.ouvrir = ouvrir_pyr.__get__(s)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    brut = []
    for date in dates:
        for s in sleeves: s.gerer(date)
        jt = sum(s.pnl.get(date, 0) for s in sleeves)
        brut.append(jt)
        if jt <= garde:
            f = garde / jt
            for s in sleeves:
                if date in s.pnl: s.pnl[date] *= f
                if s.pos is not None:
                    s.pnl[date] = s.pnl.get(date, 0) - s.frais * s.pos["n"]
                s.pos = None; s.attente = None; s.runners = []
            continue
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        for s in sleeves:
            if s.pos is not None: continue
            sig = s.signal(date)
            if sig is None: continue
            if ouverts >= 2: continue
            if s.ouvrir(date, **sig): ouverts += 1
    idx = pd.DatetimeIndex(dates)
    total = pd.Series(0.0, index=idx)
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    return total, pd.Series(brut, index=idx)

def bilan(nom, total, brut, garde):
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    pb = brut.min()*100
    sans_gardien = pb + 5.0            # > 0 = survit meme si le gardien plante
    deb50 = max(brut.min(), garde*1.5)*100
    vals = total.values; reussis = morts = 0; durees = []
    for i0 in range(0, len(vals)-40, 21):
        e2 = 1.0
        for j in range(i0, len(vals)):
            e2 *= (1 + vals[j])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; durees.append(j-i0); break
    n = reussis + morts
    pct = morts/n*100 if n else 0
    med = int(np.median(durees)) if durees else 9999
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    flag = "SUR   " if sans_gardien > 0 else "depend"
    print(f"{nom:<42} | {cagr:>+5.1f}% | {sh:>4.2f} | {pb:>+6.2f}% | {sans_gardien:>+5.2f} {flag} |"
          f" {pct:>4.0f}% | {med:>4} j | {c1:>+5.1f}/{c2:>+5.1f}%")

print("Colonnes : CAGR | Sharpe | pire jour BRUT | marge si le gardien PLANTE | morts | duree | moities\n")
print(f"{'Config':<42} | {'CAGR':>6} | {'Sh':>4} | {'Brut':>7} | {'Sans gardien':>13} | {'Morts':>5} | {'Duree':>6} | {'Moities':>13}")
print("-" * 122)
bilan("Reference actuelle (aucun pyramidage)", *serie(1, -0.035, None), -0.035)
print("-" * 122)
for u in (3, 4):
    for k in (None, 2.5, 2.0, 1.5, 1.0):
        for g in (-0.025, -0.030):
            etiq = "canal seul (ancien test)" if k is None else f"stop a {k} ATR sous la derniere unite"
            nom = f"{u} u, {etiq}, gardien {g*100:.1f}%"
            bilan(nom, *serie(u, g, k), g)
    print("-" * 122)
