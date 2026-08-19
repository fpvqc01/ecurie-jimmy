# -*- coding: utf-8 -*-
"""Analyse fine du 4 unites (proposition de Jimmy, 19 aout) :
  1. Combien de trades atteignent 2, 3, 4 unites ? (si peu -> resultat fragile)
  2. Risque d'ECART DE PRIX : aucun gardien ne peut arreter un trou de cotation.
     On mesure la perte d'une journee ou le marche ouvre en ecart contre nous,
     selon le nombre d'unites detenues.
  3. Seuil de debordement qui fait sauter la limite FTMO -5 % pour chaque config."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

suivi = []   # (nom_robot, unites_atteintes, resultat_du_trade_en_pct)

def gerer_pyr(self, date):
    i = self.jour(date)
    if i is None or self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    o = self.df["o"].iloc[i]; a = self.a.iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        avant = sum(self.pnl.values())
        self._clore(date, min(p["s"], o))
        suivi.append((self.nom, p["unites"], (sum(self.pnl.values())-avant)*100))
        self.attente = None; return
    while p["unites"] < self.max_unites and h >= p["prochain"]:
        prix_ajout = max(p["prochain"], o)
        n_ajout = min(p["n0"], 2.0 - p["n"])
        if n_ajout <= 0: break
        self.pnl[date] = self.pnl.get(date, 0) + n_ajout*(c - prix_ajout)/p["e"] - self.frais*n_ajout
        p["n"] += n_ajout; p["unites"] += 1
        p["prochain"] = p["prochain"] + self.pas_unite*a
    # exposition du jour : n x variation potentielle (pour l'analyse d'ecart)
    p["expo_max"] = max(p.get("expo_max", 0), p["n"])
    if p.get("tp") and h >= p["tp"]:
        avant = sum(self.pnl.values())
        self._clore(date, p["tp"])
        suivi.append((self.nom, p["unites"], (sum(self.pnl.values())-avant)*100))
        if self.jimmy: self.attente = p
        return
    if p.get("sortie_cloture") and self.sortie_cloture(i):
        avant = sum(self.pnl.values())
        self._clore(date, c)
        suivi.append((self.nom, p["unites"], (sum(self.pnl.values())-avant)*100))
        self.attente = None; return
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
                    unites=1, prochain=entree + self.pas_unite*a, expo_max=n)
    self.trades += 1; self.attente = None
    return True

def serie(unites, garde):
    global suivi
    suivi = []
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    expo = {}
    if unites > 1:
        for s in sleeves:
            if s.nom in ("BTC Cassure", "Petrole"):
                s.max_unites, s.pas_unite = unites, 0.5
                s.gerer = gerer_pyr.__get__(s)
                s.ouvrir = ouvrir_pyr.__get__(s)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    brut = []
    expo_jour = []
    for date in dates:
        for s in sleeves: s.gerer(date)
        jt = sum(s.pnl.get(date, 0) for s in sleeves)
        brut.append(jt)
        # exposition notionnelle totale du jour (pour le risque d'ecart)
        expo_jour.append(sum(s.pos["n"] for s in sleeves if s.pos is not None))
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
    return total, pd.Series(brut, index=idx), pd.Series(expo_jour, index=idx), list(suivi)

print("=== 1. Combien de trades atteignent chaque niveau d'unites ? ===")
for u in (2, 3, 4):
    total, brut, expo, tr = serie(u, -0.025)
    if not tr: continue
    cpt = {}
    gain = {}
    for nom, niv, res in tr:
        cpt[niv] = cpt.get(niv, 0) + 1
        gain[niv] = gain.get(niv, 0) + res
    detail = " | ".join(f"{k} u : {cpt[k]:>2} trades ({gain[k]:+6.1f} %)" for k in sorted(cpt))
    print(f"  max {u} unites -> {detail}")

print("\n=== 2. RISQUE D'ECART (aucun gardien ne peut l'arreter) ===")
print("  Exposition notionnelle maximale detenue, et perte si le marche ouvre")
print("  en ecart de -3 %, -5 % ou -10 % contre nous (choc weekend BTC / guerre) :")
for u in (1, 2, 3, 4):
    total, brut, expo, tr = serie(u, -0.025)
    e = expo.max()
    print(f"  {u} unite{'s' if u>1 else ' '} : expo max {e:>5.2f}x equite | ecart -3 % = {-3*e:>6.2f} %"
          f" | -5 % = {-5*e:>6.2f} % | -10 % = {-10*e:>7.2f} %")

print("\n=== 3. Debordement du gardien qui fait sauter la limite FTMO -5 % ===")
for u, garde in ((1, -0.035), (2, -0.025), (3, -0.025), (4, -0.025), (4, -0.030), (4, -0.035)):
    total, brut, expo, tr = serie(u, garde)
    pb = brut.min()*100
    seuil = (-5.0 / (garde*100) - 1) * 100 if garde else 0
    marge_sans_gardien = pb + 5.0
    print(f"  {u} unite(s), gardien {garde*100:>4.1f} % : pire jour brut {pb:>+6.2f} % |"
          f" tolere un debordement jusqu'a {seuil:>5.0f} % |"
          f" si gardien HORS SERVICE : {'SUR (' if marge_sans_gardien>0 else 'BRECHE ('}{marge_sans_gardien:+.2f} pt)")
