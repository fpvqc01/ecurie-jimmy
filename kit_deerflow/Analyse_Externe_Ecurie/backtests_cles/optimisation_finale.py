# -*- coding: utf-8 -*-
"""GRANDE SYNTHESE : toutes les idees validees de Jimmy, combinees au niveau
du portefeuille (5 ans, mark-to-market quotidien, frais et sizing reels).
  - Mecanisme TP+1R / retracement / re-entree sur les 3 robots de REPLI
    (or 0.25xATR, nasdaq 0.5xATR, BTC EMA 0.25xATR) ; cassures intactes.
  - Plafond global de positions simultanees (priorite : or, petrole, btc brk,
    nasdaq, btc ema).
  - Multiplicateur de risque par trade.
Configs : A actuel | B +TP/reentree | C B+cap2 | D C+x1.5 | E C+x2.
Stabilite par moitie pour la gagnante."""
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
    def __init__(self, nom, df, risque, frais, swap, fs, jimmy=False, retrace=0.25, tpj=1.0, runner75=False):
        self.nom, self.df = nom, df
        self.risque, self.frais, self.swap, self.fs = risque, frais, swap, fs
        self.jimmy, self.retrace, self.tpj = jimmy, retrace, tpj
        self.runner75 = runner75
        self.runners = []   # positions residuelles 25% avec stop suiveur en profit
        self.idx = {d: i for i, d in enumerate(df.index)}
        self.pos, self.pnl, self.trades = None, {}, 0
        self.attente, self.plancher = None, None
        self.a = atr_(df); self.r = rsi_(df["c"])
        self.e20 = df["c"].ewm(span=20, adjust=False).mean()
        self.e50 = df["c"].ewm(span=50, adjust=False).mean()
        self.h20 = df["h"].rolling(20).max().shift(1)
        self.b10 = df["l"].rolling(10).min().shift(1)

    def jour(self, date): return self.idx.get(date)

    def _clore(self, date, prix):
        p = self.pos
        self.pnl[date] = self.pnl.get(date, 0) + p["n"]*(prix-p["prix"])/p["e"] - self.frais*p["n"]
        self.pos = None

    def gerer(self, date):
        i = self.jour(date)
        if i is None: return
        # gestion des runners (independants de la position principale)
        if self.runners:
            c_ = self.df["c"].iloc[i]; l_ = self.df["l"].iloc[i]
            a_ = self.a.iloc[i]
            restants = []
            for r in self.runners:
                if l_ <= r["trail"]:
                    self.pnl[date] = self.pnl.get(date, 0) + r["n"]*(r["trail"]-r["prix"])/r["e"] - self.frais*r["n"]
                else:
                    self.pnl[date] = self.pnl.get(date, 0) + r["n"]*((c_-r["prix"])/r["e"] + self.swap*self.fs)
                    r["prix"] = c_
                    r["trail"] = max(r["trail"], c_ - a_)
                    restants.append(r)
            self.runners = restants
        if self.pos is None: return
        p = self.pos
        c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
        if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
        if l <= p["s"]:
            self._clore(date, p["s"]); self.attente = None; return
        if p.get("tp") and h >= p["tp"]:
            tp = p["tp"]
            if self.runner75:
                # 75% encaisse au TP, 25% devient un runner (stop en profit des le depart)
                self.pnl[date] = self.pnl.get(date, 0) + 0.75*p["n"]*(tp-p["prix"])/p["e"] - self.frais*0.75*p["n"]
                self.runners.append(dict(n=0.25*p["n"], e=p["e"], prix=tp,
                                         trail=max(p["e"], tp - self.a.iloc[i])))
                self.pos = None
            else:
                self._clore(date, tp)
            if self.jimmy: self.attente = tp
            return
        if p.get("be") and not p["be_fait"] and h >= p["be"]:
            p["s"] = max(p["s"], p["e"]); p["be_fait"] = True
        if p.get("sortie_cloture") and self.sortie_cloture(i):
            self._clore(date, c); self.attente = None; return
        self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
        p["prix"] = c

    def ouvrir(self, date, entree, stop, tp=None, be=None, trail=False, sortie_cloture=False):
        r0p = (entree - stop) / entree
        if r0p <= 0 or r0p > 0.5: return False
        n = min(self.risque / r0p, 2.0)
        self.pnl[date] = self.pnl.get(date, 0) - self.frais * n
        self.pos = dict(e=entree, s=stop, tp=tp, n=n, be=be, be_fait=False,
                        prix=entree, trail=trail, sortie_cloture=sortie_cloture)
        self.trades += 1; self.attente = None
        return True

class EmaBTC(Sleeve):
    def sortie_cloture(self, i): return self.e20.iloc[i] <= self.e50.iloc[i]
    def signal(self, date):
        i = self.jour(date)
        if i is None or i < 60: return None
        haussier = self.e20.iloc[i] > self.e50.iloc[i]
        if not haussier: self.attente = None; return None
        c = self.df["c"].iloc[i]; a = self.a.iloc[i]
        R = 2*a
        if self.jimmy:
            tp = c + self.tpj*R
            be = c + R if self.tpj >= 2.0 else None
            if self.e20.iloc[i-1] <= self.e50.iloc[i-1]:
                return dict(entree=c, stop=c-R, tp=tp, be=be, sortie_cloture=True)
            if self.attente is not None and self.df["l"].iloc[i] <= self.attente - self.retrace*a:
                return dict(entree=c, stop=c-R, tp=tp, be=be, sortie_cloture=True)
            return None
        if self.e20.iloc[i-1] <= self.e50.iloc[i-1]:
            return dict(entree=c, stop=c-R, tp=c+3*a, sortie_cloture=True)
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
        self.lb, self.fz, self.pull, self.mult, self.tpr = lookback, fib, pull, mult, tpr
    def sortie_cloture(self, i): return False
    def signal(self, date):
        i = self.jour(date)
        if i is None or i < self.lb + 16: return None
        h, l, c = self.df["h"], self.df["l"], self.df["c"]
        if self.attente is not None and self.plancher is not None and c.iloc[i] < self.plancher:
            self.attente = None
        wh, wl = h.iloc[i-self.lb:i], l.iloc[i-self.lb:i]
        hi_i, lo_i = wh.values.argmax(), wl.values.argmin()
        setup = False
        if lo_i < hi_i:
            span = wh.iloc[hi_i] - wl.iloc[lo_i]
            if span > 0:
                retr = (wh.iloc[hi_i] - c.iloc[i]) / span
                setup = (self.fz[0] <= retr <= self.fz[1]
                         and self.r.iloc[i-1] < self.pull and self.r.iloc[i] > self.r.iloc[i-1])
        R = self.mult * self.a.iloc[i]
        if setup:
            self.plancher = wl.iloc[lo_i]
            if self.jimmy:
                be = c.iloc[i] + R if self.tpj >= 2.0 else None
                return dict(entree=c.iloc[i], stop=c.iloc[i]-R, tp=c.iloc[i]+self.tpj*R, be=be)
            return dict(entree=c.iloc[i], stop=c.iloc[i]-R, tp=c.iloc[i]+self.tpr*R, be=c.iloc[i]+R)
        if (self.jimmy and self.attente is not None and self.plancher is not None
                and l.iloc[i] <= self.attente - self.retrace*self.a.iloc[i]
                and c.iloc[i] > self.plancher):
            be = c.iloc[i] + R if self.tpj >= 2.0 else None
            return dict(entree=c.iloc[i], stop=c.iloc[i]-R, tp=c.iloc[i]+self.tpj*R, be=be)
        return None

def simuler(jim, cap, m, moitie=None, tpj_or=1.0, tpj_nq=1.0, tpj_ema=1.0, runner=False):
    sleeves = [
        Fib("Or", gc, 0.01*m, 0.0001, -0.000273, 1.4, jimmy=jim, retrace=0.25, tpj=tpj_or,
            runner75=runner, lookback=10, fib=(0.2,0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.005*m, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC brk", btc, 0.005*m, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.01*m, 0.00003, -0.000213, 1.4, jimmy=jim, retrace=0.5, tpj=tpj_nq,
            runner75=runner, lookback=7, fib=(0.1,0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC ema", btc, 0.005*m, 0.0004, -0.000833, 1.0, jimmy=jim, retrace=0.25, tpj=tpj_ema,
               runner75=runner),
    ]
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    if moitie == 1: dates = dates[:len(dates)//2]
    if moitie == 2: dates = dates[len(dates)//2:]
    for date in dates:
        for s in sleeves: s.gerer(date)
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        for s in sleeves:
            if s.pos is not None: continue
            sig = s.signal(date)
            if sig is None: continue
            if cap is not None and ouverts >= cap: continue
            if s.ouvrir(date, **sig): ouverts += 1
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
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
    return cagr, dd, pire, sh, med10, nb

print(f"{'Config':<26} | {'CAGR %':>6} | {'Pire DD %':>9} | {'Pire jour %':>11} | {'Sharpe':>6} | {'J->+10%':>7} | {'Trades':>6}")
print("-" * 88)
KW2 = dict(tpj_or=2.0, tpj_nq=1.0, tpj_ema=2.0)   # meilleur reglage par robot
for nom, jim, cap, m, kw in [("A. Actuel", False, None, 1.0, {}),
                              ("G. TP1000 optimal", True, None, 1.0, KW2),
                              ("H. G + cap 2", True, 2, 1.0, KW2),
                              ("I. H + risque x1.5", True, 2, 1.5, KW2),
                              ("Ref: cap2 seul", False, 2, 1.0, {}),
                              ("Ref: cap2 x1.5 seul", False, 2, 1.5, {})]:
    res = simuler(jim, cap, m, **kw)
    print(f"{nom:<26} | {res[0]:>+6.1f} | {res[1]:>9.1f} | {res[2]:>11.2f} | {res[3]:>6.2f} | {res[4]:>7} | {res[5]:>6}")

print("\n--- Stabilite par moitie ---")
for nom, jim, cap, m, kw in [("G", True, None, 1.0, KW2), ("H", True, 2, 1.0, KW2),
                              ("I", True, 2, 1.5, KW2), ("cap2 seul", False, 2, 1.0, {})]:
    r1 = simuler(jim, cap, m, 1, **kw); r2 = simuler(jim, cap, m, 2, **kw)
    print(f"{nom:<10} : moitie 1 CAGR {r1[0]:+.1f}% (DD {r1[1]:.1f}%) | moitie 2 CAGR {r2[0]:+.1f}% (DD {r2[1]:.1f}%)")
