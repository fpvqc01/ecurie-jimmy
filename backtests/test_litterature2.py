# -*- coding: utf-8 -*-
"""LITTERATURE, 2e TOURNEE (20 aout 2026) — 4 ecoles jamais testees :
  A. THROTTLE D'EQUITE (Seykota/Basso, Market Wizards) : risque des nouvelles
     entrees reduit de moitie quand l'equite du portefeuille est sous sa
     propre moyenne 20 jours. « Trade smaller when losing. »
  B. FILTRE ADX (Wilder 1978, New Concepts) : les cassures ne s'ouvrent que
     si ADX(14) confirme une force de tendance (seuils 20 et 25).
  C. SORTIE TEMPORELLE (Kaufman, Trading Systems and Methods) : une cassure
     qui n'a pas atteint +0,5R apres N barres est fermee (N = 10 et 15).
  D. TOURNANT DU MOIS (McConnell & Xu 2008) : mini-manche US100 longue du
     dernier jour du mois + 3 premiers jours (anomalie documentee).
Tout au niveau PORTEFEUILLE, gardien -2,5 %/jour actif, frais reels."""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

GARDE = -0.025

# ---------- indicateur ADX(14) de Wilder ----------
def adx14(df):
    h, l, c = df["h"], df["l"], df["c"]
    up, dn = h.diff(), -l.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    moins_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum(h - l, np.maximum((h - c.shift()).abs(), (l - c.shift()).abs()))
    atr = tr.ewm(alpha=1/14, adjust=False).mean()
    pdi = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr
    mdi = 100 * pd.Series(moins_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/14, adjust=False).mean()

# ---------- C : gerer() de cassure avec sortie temporelle ----------
def gerer_temps(self, date):
    i = self.jour(date)
    if i is None or self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    p["vie"] = p.get("vie", 0) + 1
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        self._clore(date, p["s"]); self.attente = None; return
    # sortie temporelle Kaufman : pas +0,5R apres N barres -> dehors
    R0 = p.get("R0", 0)
    if R0 > 0 and p["vie"] >= self.duree_max and (c - p["e"]) < 0.5 * R0:
        self._clore(date, c); self.attente = None; return
    if p.get("sortie_cloture") and self.sortie_cloture(i):
        self._clore(date, c); self.attente = None; return
    self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
    p["prix"] = c

# ---------- D : mini-manche tournant du mois sur US100 ----------
class TournantDuMois:
    def __init__(self, df, risque, frais, swap, fs):
        self.nom, self.df = "TdM Nasdaq", df
        self.risque, self.frais, self.swap, self.fs = risque, frais, swap, fs
        self.idx = {d: i for i, d in enumerate(df.index)}
        self.pos, self.pnl, self.trades = None, {}, 0
        self.attente, self.runners = None, []
        self.a = atr_(df)
        # dernier jour de bourse de chaque mois
        s = pd.Series(df.index, index=df.index)
        self.dernier_jour = set(s.groupby([df.index.year, df.index.month]).max())
    def jour(self, date): return self.idx.get(date)
    def gerer(self, date):
        i = self.jour(date)
        if i is None or self.pos is None: return
        p = self.pos
        c, l = self.df["c"].iloc[i], self.df["l"].iloc[i]
        p["vie"] += 1
        if l <= p["s"]:
            self.pnl[date] = self.pnl.get(date, 0) + p["n"]*(p["s"]-p["prix"])/p["e"] - self.frais*p["n"]
            self.pos = None; return
        if p["vie"] >= 4:      # sortie apres 4 jours de bourse
            self.pnl[date] = self.pnl.get(date, 0) + p["n"]*(c-p["prix"])/p["e"] - self.frais*p["n"]
            self.pos = None; return
        self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
        p["prix"] = c
    def signal(self, date):
        i = self.jour(date)
        if i is None or i < 20 or self.pos is not None: return None
        if date not in self.dernier_jour: return None
        c = self.df["c"].iloc[i]; R = 2*self.a.iloc[i]
        if R <= 0: return None
        return dict(entree=c, stop=c-R)
    def ouvrir(self, date, entree, stop):
        r0p = (entree - stop) / entree
        if r0p <= 0 or r0p > 0.5: return False
        n = min(self.risque / r0p, 2.0)
        self.pnl[date] = self.pnl.get(date, 0) - self.frais * n
        self.pos = dict(e=entree, s=stop, n=n, prix=entree, vie=0)
        self.trades += 1
        return True

def sim(variante="ref", param=None):
    sleeves = [
        Fib("Or", gc, 0.03, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
            retrace=0.5, tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    if variante == "adx":
        for s in sleeves:
            if s.nom in ("BTC Cassure", "Petrole"):
                s.adx = adx14(s.df)
                original = s.signal
                def signal_f(date, s=s, original=original):
                    sig = original(date)
                    if sig is None: return None
                    i = s.jour(date)
                    if np.isnan(s.adx.iloc[i]) or s.adx.iloc[i] < param: return None
                    return sig
                s.signal = signal_f
    if variante == "temps":
        for s in sleeves:
            if s.nom in ("BTC Cassure", "Petrole"):
                s.duree_max = param
                s.gerer = gerer_temps.__get__(s)
                original_ouvrir = s.ouvrir
                def ouvrir_f(date, entree, stop, s=s, orig=original_ouvrir, **kw):
                    ok = orig(date, entree, stop, **kw)
                    if ok: s.pos["R0"] = entree - stop; s.pos["vie"] = 0
                    return ok
                s.ouvrir = ouvrir_f
    if variante == "tdm":
        sleeves.append(TournantDuMois(nq, 0.0075, 0.00003, -0.000213, 1.4))

    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    coupes = 0
    equite = 1.0
    histo = []          # rendements quotidiens pour la moyenne 20 j
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
            jt = GARDE
        equite *= (1 + jt)
        histo.append(equite)
        if jt <= GARDE: continue
        # ---- A : throttle d'equite (Seykota) ----
        facteur_risque = 1.0
        if variante == "throttle" and len(histo) > 20:
            sma20 = np.mean(histo[-20:])
            if equite < sma20: facteur_risque = param
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        for s in sleeves:
            if s.pos is not None: continue
            sig = s.signal(date)
            if sig is None: continue
            if ouverts >= 2: continue
            r_avant = s.risque
            s.risque = r_avant * facteur_risque
            ok = s.ouvrir(date, **sig)
            s.risque = r_avant
            if ok: ouverts += 1
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    total = total.clip(lower=GARDE)
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
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
    return cagr, sh, coupes, (morts/n*100 if n else 0), (int(np.median(durees)) if durees else 9999), c1, c2

print("%-46s | %-6s | %-6s | %-6s | %-5s | %-6s | %s" %
      ("Idee (source)", "CAGR", "Sharpe", "Coupes", "Morts", "Duree", "Moities"))
print("-" * 110)
for nom, v, p in [
    ("REFERENCE (ecurie actuelle)", "ref", None),
    ("A. Throttle equite x0.5 (Seykota)", "throttle", 0.5),
    ("A'. Throttle x0.75 (voisin)", "throttle", 0.75),
    ("B. Filtre ADX>20 sur cassures (Wilder)", "adx", 20),
    ("B'. Filtre ADX>25 (voisin)", "adx", 25),
    ("C. Sortie temporelle 10 barres (Kaufman)", "temps", 10),
    ("C'. Sortie temporelle 15 barres (voisin)", "temps", 15),
    ("D. Tournant du mois US100 (McConnell&Xu)", "tdm", None),
]:
    r = sim(v, p)
    print("%-46s | %+5.1f%% | %6.2f | %6d | %4.0f%% | %4d j | %+5.1f/%+5.1f%%" %
          (nom, r[0], r[1], r[2], r[3], r[4], r[5], r[6]))
