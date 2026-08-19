# -*- coding: utf-8 -*-
"""STRESS DU GARDIEN (question de Jimmy, 19 aout) : les tests supposent une
coupure NETTE a -3,5 %/jour. Dans la vraie vie, un ecart de prix (weekend BTC,
choc petrole) peut faire deborder le gardien. Avec le pyramidage les positions
sont 3x plus grosses -> le debordement serait 3x pire.
On mesure :
  A. la perte du jour AVANT gardien (ce que le marche voulait prendre)
  B. combien de jours auraient depasse la vraie limite FTMO de -5 %
  C. le meme test avec un gardien qui deborde de 20 %, 50 %, 100 %
     (glissement/ecart au moment de la coupure)"""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

GARDE = -0.035
LIMITE_FTMO_JOUR = -0.05
LIMITE_FTMO_TOTAL = -0.10

def gerer_pyr(self, date):
    i = self.jour(date)
    if i is None or self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    o = self.df["o"].iloc[i]; a = self.a.iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        # execution realiste du stop : si ecart d'ouverture SOUS le stop, on sort a l'ouverture
        prix_sortie = min(p["s"], o)
        self._clore(date, prix_sortie); self.attente = None; return
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

def serie(unites=1, debordement=0.0):
    """debordement : 0.2 = le gardien laisse passer 20 % de plus que -3,5 %."""
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
    brut, net = [], []
    for date in dates:
        for s in sleeves: s.gerer(date)
        jt = sum(s.pnl.get(date, 0) for s in sleeves)
        brut.append(jt)
        if jt <= GARDE:
            plancher = GARDE * (1 + debordement)      # le gardien deborde
            reel = max(jt, plancher)                  # jamais mieux que le marche
            f = reel / jt
            for s in sleeves:
                if date in s.pnl: s.pnl[date] *= f
                if s.pos is not None:
                    s.pnl[date] = s.pnl.get(date, 0) - s.frais * s.pos["n"]
                s.pos = None; s.attente = None; s.runners = []
            net.append(reel)
            continue
        net.append(jt)
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
    return total, pd.Series(brut, index=idx), pd.Series(net, index=idx)

def analyse(nom, total, brut):
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    pire_reel = total.min()*100
    pire_brut = brut.min()*100
    viol_jour = (total <= LIMITE_FTMO_JOUR).sum()
    creux = (eq.min()-1)*100
    viol_total = 1 if creux <= LIMITE_FTMO_TOTAL*100 else 0
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    print(f"{nom:<44} | {cagr:>+5.1f}% | {sh:>4.2f} | {pire_brut:>+6.2f}% | {pire_reel:>+6.2f}% |"
          f" {viol_jour:>5} | {creux:>+5.1f}% | {'OUI' if viol_total else 'non':>4}")

print("Colonnes : CAGR | Sharpe | pire jour AVANT gardien | pire jour APRES gardien |")
print("           jours au-dela de la limite FTMO -5 % | creux vs depart | violation -10 % ?\n")
print(f"{'Config':<44} | {'CAGR':>6} | {'Sh':>4} | {'BRUT':>7} | {'REEL':>7} | {'>5%':>5} | {'Creux':>6} | {'-10%':>4}")
print("-" * 108)
for nom, u, deb in [
    ("Reference, gardien parfait", 1, 0.0),
    ("Reference, gardien deborde 20 %", 1, 0.2),
    ("Reference, gardien deborde 50 %", 1, 0.5),
    ("Pyramidage 3u, gardien parfait", 3, 0.0),
    ("Pyramidage 3u, gardien deborde 20 %", 3, 0.2),
    ("Pyramidage 3u, gardien deborde 50 %", 3, 0.5),
    ("Pyramidage 3u, gardien deborde 100 % (-7 %)", 3, 1.0),
    ("Pyramidage 4u, gardien deborde 50 %", 4, 0.5),
]:
    total, brut, net = serie(u, deb)
    analyse(nom, total, brut)

print("\n--- Distribution des pires journees BRUTES (avant gardien) ---")
for nom, u in [("Reference", 1), ("Pyramidage 3 unites", 3)]:
    total, brut, net = serie(u, 0.0)
    pires = np.sort(brut.values)[:8] * 100
    print(f"  {nom:<22} : " + ", ".join(f"{x:+.2f}%" for x in pires))
    print(f"    {'':22}   jours sous -3,5 % : {(brut <= -0.035).sum()} | sous -5 % : {(brut <= -0.05).sum()}")
