# -*- coding: utf-8 -*-
"""Portefeuille des 5 robots avec PLAFOND global de positions simultanees.
Compare : illimite (actuel) vs max 2 vs max 1.
Un robot ne peut ouvrir que si le nombre de positions ouvertes < plafond.
Ordre de priorite en cas de signaux le meme jour : or, petrole, BTC brk,
Nasdaq, BTC ema (du plus fort au plus faible historiquement)."""
import requests, pandas as pd, numpy as np

def fetch(sym):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"range": "5y", "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    return pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s").normalize(),
                         "o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]}
                        ).dropna().drop_duplicates("t").set_index("t")

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()
def atr_(df, n=14):
    tr = np.maximum(df["h"]-df["l"], np.maximum((df["h"]-df["c"].shift()).abs(),
                                                (df["l"]-df["c"].shift()).abs()))
    return wilder(tr, n)
def rsi_(s, n=14):
    d = s.diff()
    return 100 - 100/(1 + wilder(d.clip(lower=0), n) / wilder(-d.clip(upper=0), n).replace(0, np.nan))

btc, gc, nq, cl = fetch("BTC-USD"), fetch("GC=F"), fetch("NQ=F"), fetch("CL=F")

class Sleeve:
    def __init__(self, nom, df, risque, frais, swap, fs):
        self.nom, self.df = nom, df
        self.risque, self.frais, self.swap, self.fs = risque, frais, swap, fs
        self.idx = {d: i for i, d in enumerate(df.index)}
        self.pos = None
        self.pnl = {}
        self.trades = 0
        self.a = atr_(df); self.r = rsi_(df["c"])
        self.e20 = df["c"].ewm(span=20, adjust=False).mean()
        self.e50 = df["c"].ewm(span=50, adjust=False).mean()
        self.h20 = df["h"].rolling(20).max().shift(1)
        self.b10 = df["l"].rolling(10).min().shift(1)

    def jour(self, date):
        return self.idx.get(date)

    def gerer(self, date):
        """Mark-to-market + sorties. Retourne rien; libere le slot si sortie."""
        i = self.jour(date)
        if i is None or self.pos is None: return
        p = self.pos
        c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
        if p.get("trail"):
            p["s"] = max(p["s"], self.b10.iloc[i])
        if l <= p["s"]:
            self.pnl[date] = self.pnl.get(date, 0) + p["n"]*(p["s"]-p["prix"])/p["e"] - self.frais*p["n"]
            self.pos = None; return
        if p.get("tp") and h >= p["tp"]:
            self.pnl[date] = self.pnl.get(date, 0) + p["n"]*(p["tp"]-p["prix"])/p["e"] - self.frais*p["n"]
            self.pos = None; return
        if p.get("be") and not p["be_fait"] and h >= p["be"]:
            p["s"] = max(p["s"], p["e"]); p["be_fait"] = True
        if p.get("sortie_cloture") and self.sortie_cloture(i):
            self.pnl[date] = self.pnl.get(date, 0) + p["n"]*(c-p["prix"])/p["e"] - self.frais*p["n"]
            self.pos = None; return
        self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
        p["prix"] = c

    def ouvrir(self, date, entree, stop, tp=None, be=None, trail=False, sortie_cloture=False):
        r0p = (entree - stop) / entree
        if r0p <= 0 or r0p > 0.5: return False
        n = min(self.risque / r0p, 2.0)
        self.pnl[date] = self.pnl.get(date, 0) - self.frais * n
        self.pos = dict(e=entree, s=stop, tp=tp, n=n, be=be, be_fait=False,
                        prix=entree, trail=trail, sortie_cloture=sortie_cloture)
        self.trades += 1
        return True

class EmaBTC(Sleeve):
    def sortie_cloture(self, i): return self.e20.iloc[i] <= self.e50.iloc[i]
    def signal(self, date):
        i = self.jour(date)
        if i is None or i < 60: return None
        if self.e20.iloc[i] > self.e50.iloc[i] and self.e20.iloc[i-1] <= self.e50.iloc[i-1]:
            c = self.df["c"].iloc[i]
            return dict(entree=c, stop=c-2*self.a.iloc[i], tp=c+3*self.a.iloc[i], sortie_cloture=True)
        return None

class Donch(Sleeve):
    def __init__(self, *a, saison=None, **k):
        super().__init__(*a, **k); self.saison = saison
    def sortie_cloture(self, i): return self.df["c"].iloc[i] < self.b10.iloc[i]
    def signal(self, date):
        i = self.jour(date)
        if i is None or i < 25: return None
        if self.saison:
            md = date.month*100 + date.day
            if not (md >= self.saison[0] or md <= self.saison[1]): return None
        c = self.df["c"].iloc[i]
        if c > self.h20.iloc[i]:
            return dict(entree=c, stop=self.b10.iloc[i], trail=True, sortie_cloture=True)
        return None

class Fib(Sleeve):
    def __init__(self, *a, lookback=10, fib=(0.2,0.8), pull=55, mult=3.0, tpr=2.0, **k):
        super().__init__(*a, **k)
        self.lb, self.fib, self.pull, self.mult, self.tpr = lookback, fib, pull, mult, tpr
    def sortie_cloture(self, i): return False
    def signal(self, date):
        i = self.jour(date)
        if i is None or i < self.lb + 16: return None
        h, l, c = self.df["h"], self.df["l"], self.df["c"]
        wh, wl = h.iloc[i-self.lb:i], l.iloc[i-self.lb:i]
        hi_i, lo_i = wh.values.argmax(), wl.values.argmin()
        if lo_i >= hi_i: return None
        span = wh.iloc[hi_i] - wl.iloc[lo_i]
        if span <= 0: return None
        retr = (wh.iloc[hi_i] - c.iloc[i]) / span
        if not (self.fib[0] <= retr <= self.fib[1]): return None
        if not (self.r.iloc[i-1] < self.pull and self.r.iloc[i] > self.r.iloc[i-1]): return None
        R = self.mult * self.a.iloc[i]
        return dict(entree=c.iloc[i], stop=c.iloc[i]-R, tp=c.iloc[i]+self.tpr*R, be=c.iloc[i]+R)

def simuler(cap, m=1.0):
    sleeves = [
        Fib("Or", gc, 0.01*m, 0.0001, -0.000273, 1.4, lookback=10, fib=(0.2,0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.005*m, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC brk", btc, 0.005*m, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.01*m, 0.00003, -0.000213, 1.4, lookback=7, fib=(0.1,0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC ema", btc, 0.005*m, 0.0004, -0.000833, 1.0),
    ]
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    bloques = 0
    for date in dates:
        for s in sleeves:
            s.gerer(date)
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        for s in sleeves:
            if s.pos is not None: continue
            sig = s.signal(date)
            if sig is None: continue
            if cap is not None and ouverts >= cap:
                bloques += 1; continue
            if s.ouvrir(date, **sig):
                ouverts += 1
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for d, v in s.pnl.items(): total[d] += v
    eq = (1 + total).cumprod()
    annees = len(total) / 365.25
    cagr = (eq.iloc[-1] ** (1/annees) - 1) * 100
    dd = (eq/eq.cummax()-1).min() * 100
    pire = total.min() * 100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    vals = eq.values
    j10 = []
    for i0 in range(0, len(vals)-1, 21):
        ap = np.where(vals[i0:] >= vals[i0]*1.10)[0]
        if len(ap): j10.append(ap[0])
    med10 = int(np.median(j10)) if j10 else -1
    nb = sum(s.trades for s in sleeves)
    return cagr, dd, pire, sh, med10, nb, bloques

print(f"{'Configuration':<22} | {'CAGR %':>6} | {'Pire DD %':>9} | {'Pire jour %':>11} | {'Sharpe':>6} | {'Jours->+10%':>11} | {'Bloqués':>7}")
print("-" * 96)
for cap, m, nom in [(None, 1.0, "Illimité, risque x1"), (2, 1.0, "Max 2, risque x1"),
                    (1, 1.0, "Max 1, risque x1"), (2, 1.5, "Max 2, risque x1.5"),
                    (2, 2.0, "Max 2, risque x2"), (1, 2.0, "Max 1, risque x2"),
                    (1, 3.0, "Max 1, risque x3")]:
    cagr, dd, pire, sh, med10, nb, bl = simuler(cap, m)
    print(f"{nom:<22} | {cagr:>+6.1f} | {dd:>9.1f} | {pire:>11.2f} | {sh:>6.2f} | {med10:>11} | {bl:>7}")
