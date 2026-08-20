# -*- coding: utf-8 -*-
"""DUEL DES 4 GENERATIONS (20 aout 2026) : I2+ vs I2++ vs L3 vs L3+
dans le MEME moteur de portefeuille, memes donnees, memes frais reels.

  I2+  = production actuelle : TP/re-entree, plafond 2, vol targeting,
         gardien -3,5 %/jour. Pas de pyramidage.
  I2++ = I2+ + pyramidage Turtle (3 unites, +0,5 ATR, stop 2 ATR sous la
         derniere) sur les 2 cassures + gardien resserre a -2,5 %.
  L3   = identique a I2++ cote strategie (c'est la meme config validee)
         -> sert de controle : les deux doivent donner le meme resultat.
  L3+  = L3 + MODE CHALLENGE (throttle Seykota : risque x0,75 quand
         l'equite passe sous sa moyenne 20 jours).
Mesures : rendement annuel, Sharpe, creux, coupes du gardien, moities,
et surtout SURVIE EN CHALLENGE (fenetres glissantes : +10 % avant -8 %).
"""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

# ---------- pyramidage (code valide, execution realiste) ----------
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
    # stop commun Turtle
    if p["unites"] > 1 and a > 0:
        turtle = p["dernier_prix"] - self.stop_turtle * a
        if turtle > p["s"]: p["s"] = turtle
    self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
    p["prix"] = c

def ouvrir_pyr(self, date, entree, stop, tp=None, be=None, trail=False, sortie_cloture=False):
    r0p = (entree - stop) / entree
    if r0p <= 0 or r0p > 0.5: return False
    n = min(self.risque * self.facteur_challenge / r0p, 2.0)
    self.pnl[date] = self.pnl.get(date, 0) - self.frais * n
    i = self.jour(date); a = self.a.iloc[i]
    self.pos = dict(e=entree, s=stop, tp=tp, n=n, n0=n, be=be, be_fait=False,
                    prix=entree, trail=trail, sortie_cloture=sortie_cloture,
                    unites=1, prochain=entree + self.pas_unite*a, dernier_prix=entree)
    self.trades += 1; self.attente = None
    return True

def sim(generation):
    """I2+ | I2++ | L3 | L3+"""
    pyramidage = generation in ("I2++", "L3", "L3+")
    garde = -0.035 if generation == "I2+" else -0.025
    challenge = (generation == "L3+")

    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    for s in sleeves:
        s.facteur_challenge = 1.0
        if pyramidage and s.nom in ("BTC Cassure", "Petrole"):
            s.max_unites, s.pas_unite, s.stop_turtle = 3, 0.5, 2.0
            s.gerer = gerer_pyr.__get__(s)
            s.ouvrir = ouvrir_pyr.__get__(s)

    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    coupes = 0
    equite = 1.0
    histo = []
    for date in dates:
        for s in sleeves: s.gerer(date)
        jt = sum(s.pnl.get(date, 0) for s in sleeves)
        if jt <= garde:
            f = garde / jt
            for s in sleeves:
                if date in s.pnl: s.pnl[date] *= f
                if s.pos is not None:
                    s.pnl[date] = s.pnl.get(date, 0) - s.frais * s.pos["n"]
                s.pos = None; s.attente = None; s.runners = []
            coupes += 1
            jt = garde
        equite *= (1 + jt); histo.append(equite)
        if jt <= garde: continue
        # mode challenge (Seykota) : risque reduit sous la moyenne 20 jours
        fc = 1.0
        if challenge and len(histo) > 20 and equite < np.mean(histo[-20:]):
            fc = 0.75
        for s in sleeves: s.facteur_challenge = fc
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        for s in sleeves:
            if s.pos is not None: continue
            sig = s.signal(date)
            if sig is None: continue
            if ouverts >= 2: continue
            r0 = s.risque
            if not hasattr(s, "max_unites"): s.risque = r0 * fc   # sleeves sans ouvrir_pyr
            ok = s.ouvrir(date, **sig)
            s.risque = r0
            if ok: ouverts += 1

    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    total = total.clip(lower=garde)
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    creux = (eq.min()-1)*100
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    vals = total.values; reussis = morts = 0; durees = []
    for i0 in range(0, len(vals)-40, 21):
        e2 = 1.0
        for j in range(i0, len(vals)):
            e2 *= (1 + vals[j])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; durees.append(j-i0); break
    n = reussis + morts
    return dict(cagr=cagr, sharpe=sh, creux=creux, coupes=coupes,
                morts=(morts/n*100 if n else 0),
                duree=(int(np.median(durees)) if durees else 9999),
                m1=c1, m2=c2, pire=total.min()*100)

print("%-8s | %-7s | %-6s | %-7s | %-6s | %-6s | %-6s | %s" %
      ("Gen", "CAGR", "Sharpe", "Creux", "Coupes", "Morts", "Duree", "Moities"))
print("-" * 88)
res = {}
for g in ("I2+", "I2++", "L3", "L3+"):
    r = sim(g); res[g] = r
    print("%-8s | %+6.1f%% | %6.2f | %+6.1f%% | %6d | %5.0f%% | %4d j | %+5.1f/%+5.1f%%" %
          (g, r["cagr"], r["sharpe"], r["creux"], r["coupes"], r["morts"], r["duree"], r["m1"], r["m2"]))

print()
print("=== LECTURE DU DUEL ===")
print("  I2++ vs I2+  : %+.1f pt de CAGR | Sharpe %+.2f | morts %+.0f pt | %d j de moins" %
      (res["I2++"]["cagr"]-res["I2+"]["cagr"], res["I2++"]["sharpe"]-res["I2+"]["sharpe"],
       res["I2++"]["morts"]-res["I2+"]["morts"], res["I2+"]["duree"]-res["I2++"]["duree"]))
print("  L3+  vs L3   : %+.1f pt de CAGR | Sharpe %+.2f | morts %+.0f pt | %d j de plus" %
      (res["L3+"]["cagr"]-res["L3"]["cagr"], res["L3+"]["sharpe"]-res["L3"]["sharpe"],
       res["L3+"]["morts"]-res["L3"]["morts"], res["L3+"]["duree"]-res["L3"]["duree"]))
print("  controle I2++ vs L3 (doivent etre proches) : ecart de CAGR %+.2f pt" %
      (res["L3"]["cagr"]-res["I2++"]["cagr"]))
