# -*- coding: utf-8 -*-
"""Correctif au risque decouvert : si on pyramide, on SERRE le gardien quotidien
pour recreer le coussin de securite (rester sous -5 % FTMO meme si le gardien
deborde de 50 %). On teste le gardien a -3,5 % (actuel), -3,0 %, -2,5 %, -2,0 %
avec 2, 3 et 4 unites. Critere de reussite : pire jour BRUT sous 5 %, ou pire
jour reel avec debordement 50 % encore sous -5 %."""
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

def serie(unites, garde):
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
                s.max_unites, s.pas_unite = unites, 0.5
                s.gerer = gerer_pyr.__get__(s)
                s.ouvrir = ouvrir_pyr.__get__(s)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    brut = []
    coupes = 0
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
            coupes += 1
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
    return total, pd.Series(brut, index=idx), coupes

print(f"{'Config':<40} | {'CAGR':>6} | {'Sh':>4} | {'PireBrut':>8} | {'Deb50%':>7} | {'Marge':>6} | {'Morts':>5} | {'Duree':>6}")
print("-" * 104)
for unites in (1, 2, 3, 4):
    for garde in (-0.035, -0.030, -0.025, -0.020):
        if unites == 1 and garde != -0.035: continue
        total, brut, coupes = serie(unites, garde)
        eq = (1 + total).cumprod(); annees = len(total)/365.25
        cagr = (eq.iloc[-1]**(1/annees)-1)*100
        sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
        pire_brut = brut.min()*100
        # pire journee reelle si le gardien deborde de 50 %
        pire_deb = max(brut.min(), garde*1.5)*100
        marge = pire_deb - (-5.0)      # > 0 = il reste de la marge sous la limite FTMO -5 %
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
        nom = f"{unites} unite{'s' if unites>1 else ''}, gardien {garde*100:.1f} %"
        drapeau = "SUR   " if marge > 0 else "BRECHE"
        print(f"{nom:<40} | {cagr:>+5.1f}% | {sh:>4.2f} | {pire_brut:>+7.2f}% | {pire_deb:>+6.2f}% |"
              f" {marge:>+5.2f} {drapeau} | {pct:>4.0f}% | {med:>4} j")
