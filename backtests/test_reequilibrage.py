# -*- coding: utf-8 -*-
"""LA PISTE LA PLUS PROMETTEUSE : le robot OR porte 3 % de risque (le double
des autres) et contribue ZERO sur 10 ans, tout en causant 11 des 12 pires
mois. Le BTC et le petrole portent le systeme avec 0,75 %.
MAIS attention : le moteur de ce test n'a PAS le TP/re-entree, qui est
justement le mecanisme cle du robot or. On teste donc les DEUX questions :
  Q1. L'or AVEC re-entree est-il rentable sur 10 ans ? (le moteur 5 ans
      disait +58,5 points ; a verifier sur 10 ans)
  Q2. Quel niveau de risque pour l'or ? (3 % / 2 % / 1,5 % / 1 %)
  Q3. Et si on rebalancait vers les robots qui gagnent (BTC, petrole) ?"""
import os, time, requests, pandas as pd, numpy as np

def _tranche(sym, p1, p2):
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/" + sym,
                     params={"period1": p1, "period2": p2, "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    if "timestamp" not in d: return None
    q = d["indicators"]["quote"][0]
    df = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s").normalize(),
                       "o": q.get("open"), "h": q["high"], "l": q["low"], "c": q["close"]}
                      ).dropna(subset=["h", "l", "c"]).drop_duplicates("t").set_index("t")
    df["o"] = df["o"].fillna(df["c"]); return df

def fetch(sym, depuis="2016-01-01"):
    morceaux, cur, fin = [], pd.Timestamp(depuis), pd.Timestamp.today()
    while cur < fin:
        suiv = min(cur + pd.DateOffset(years=5), fin)
        try:
            d = _tranche(sym, int(cur.timestamp()), int(suiv.timestamp()))
            if d is not None and len(d): morceaux.append(d)
        except Exception: pass
        cur = suiv; time.sleep(0.15)
    out = pd.concat(morceaux)
    return out[~out.index.duplicated(keep="first")].sort_index()

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()
def atr_(df, n=14):
    tr = np.maximum(df["h"]-df["l"], np.maximum((df["h"]-df["c"].shift()).abs(),
                                                (df["l"]-df["c"].shift()).abs()))
    return wilder(tr, n)
def rsi_(s, n=14):
    d = s.diff()
    return 100 - 100/(1 + wilder(d.clip(lower=0), n) / wilder(-d.clip(upper=0), n).replace(0, np.nan))

M = {n: fetch(s) for n, s in (("or","GC=F"), ("nasdaq","NQ=F"), ("petrole","CL=F"), ("btc","BTC-USD"))}
FRAIS = {"or":0.0001, "nasdaq":0.00003, "petrole":0.00045, "btc":0.0004}
SWAP = {"or":-0.000273, "nasdaq":-0.000213, "petrole":+0.000051, "btc":-0.000833}
FAM = {"or":"mi", "nasdaq":"mi", "petrole":"en", "btc":"cr"}

class Manche:
    def __init__(self, nom, df, risque, type_, reentree=False, **kw):
        self.nom, self.df, self.risque, self.type, self.kw = nom, df, risque, type_, kw
        self.reentree = reentree
        self.frais, self.swap = FRAIS[nom], SWAP[nom]
        self.a = atr_(df); self.r = rsi_(df["c"])
        self.hE = df["h"].rolling(kw.get("pe",20)).max().shift(1)
        self.bS = df["l"].rolling(kw.get("ps",10)).min().shift(1)
        self.idx = {d:i for i,d in enumerate(df.index)}
        self.pos = None; self.attente = 0.0; self.plancher = 0.0; self.total = 0.0
    def jour(self,d): return self.idx.get(d)
    def gerer(self, date, pyramide):
        i = self.jour(date)
        if i is None or self.pos is None: return 0.0
        p = self.pos
        c,h,l = self.df["c"].iloc[i], self.df["h"].iloc[i], self.df["l"].iloc[i]
        a = self.a.iloc[i]
        if self.type=="donch":
            p["s"] = max(p["s"], self.bS.iloc[i])
            if pyramide and p["u"]<3 and a>0 and h>=p["proch"]:
                p["u"]+=1; p["n"]+=p["n0"]; p["proch"]+=0.5*a
                p["turtle"] = max(p.get("turtle",-1e9), h-2.0*a)
            niv = max(p["s"], p.get("turtle",-1e9))
            if l<=niv:
                g = p["n"]*(niv-p["prix"])/p["e"] - self.frais*p["n"]; self.pos=None
                self.total+=g; return g
            g = p["n"]*((c-p["prix"])/p["e"] + self.swap); p["prix"]=c
            self.total+=g; return g
        if l<=p["s"]:
            g = p["n"]*(p["s"]-p["prix"])/p["e"] - self.frais*p["n"]; self.pos=None
            self.attente=0.0; self.plancher=0.0; self.total+=g; return g
        if h>=p["tp"]:
            g = p["n"]*(p["tp"]-p["prix"])/p["e"] - self.frais*p["n"]
            if self.reentree: self.attente = p["tp"]; self.plancher = p["lo"]
            self.pos=None; self.total+=g; return g
        # breakeven +1R
        R0 = p["e"]-p["s0"]
        if p["s"] < p["e"] and h >= p["e"]+R0: p["s"] = p["e"]
        g = p["n"]*((c-p["prix"])/p["e"] + self.swap); p["prix"]=c
        self.total+=g; return g
    def signal(self, date):
        i = self.jour(date)
        if i is None or i<130 or self.pos is not None: return None
        c = self.df["c"].iloc[i]; a = self.a.iloc[i]
        if a<=0 or np.isnan(a): return None
        if self.type=="donch":
            if np.isnan(self.hE.iloc[i]) or c<=self.hE.iloc[i]: return None
            s = self.bS.iloc[i]
            if s>=c: return None
            return dict(e=c, s=s, tp=None, a=a, lo=s)
        lb = self.kw["lb"]
        fh, fl = self.df["h"].iloc[i-lb:i], self.df["l"].iloc[i-lb:i]
        hi_i, lo_i = fh.values.argmax(), fl.values.argmin()
        R = self.kw["mult"]*a
        # re-entree apres TP : repli de 0,25 ATR, plancher intact
        if self.reentree and self.attente>0 and self.plancher>0:
            if c < self.plancher: self.attente=0.0; self.plancher=0.0
            elif self.df["l"].iloc[i] <= self.attente - 0.25*a:
                return dict(e=c, s=c-R, tp=c+self.kw["tpr"]*R, a=a, lo=self.plancher)
        if lo_i>=hi_i: return None
        span = fh.iloc[hi_i]-fl.iloc[lo_i]
        if span<=0: return None
        retr = (fh.iloc[hi_i]-c)/span
        if not (self.kw["flo"]<=retr<=self.kw["fhi"]): return None
        if not (self.r.iloc[i-1]<self.kw["rs"] and self.r.iloc[i]>self.r.iloc[i-1]): return None
        return dict(e=c, s=c-R, tp=c+self.kw["tpr"]*R, a=a, lo=fl.iloc[lo_i])
    def ouvrir(self, sig):
        r0 = (sig["e"]-sig["s"])/sig["e"]
        if r0<=0 or r0>0.5: return False
        n = min(self.risque/r0, 2.0)
        self.pos = dict(e=sig["e"], s=sig["s"], s0=sig["s"], tp=sig["tp"] if sig["tp"] else 1e18,
                        n=n, n0=n, prix=sig["e"], u=1, proch=sig["e"]+0.5*sig["a"],
                        turtle=-1e9, lo=sig.get("lo", 0))
        self.attente = 0.0
        return True

def simuler(r_or=0.03, r_nas=0.015, r_pet=0.0075, r_btc=0.0075, reentree=True):
    manches = [
        Manche("or", M["or"], r_or, "fib", reentree, lb=10, flo=0.2, fhi=0.8, rs=55, mult=3.0, tpr=1.5),
        Manche("nasdaq", M["nasdaq"], r_nas, "fib", reentree, lb=7, flo=0.1, fhi=0.9, rs=60, mult=2.0, tpr=1.0),
        Manche("petrole", M["petrole"], r_pet, "donch", pe=20, ps=10),
        Manche("btc", M["btc"], r_btc, "donch", pe=55, ps=20),
    ]
    dates = sorted(set().union(*[set(m.df.index) for m in manches]))
    equite, histo, coupes = 1.0, [], 0
    for date in dates:
        jt = sum(m.gerer(date, True) for m in manches)
        if jt <= -0.025:
            jt = -0.025; coupes += 1
            for m in manches: m.pos = None
        equite *= (1+jt); histo.append(equite)
        if jt <= -0.025: continue
        ouverts = sum(1 for m in manches if m.pos is not None)
        fam = {FAM[m.nom] for m in manches if m.pos is not None}
        for m in manches:
            if m.pos is not None or ouverts>=2: continue
            if FAM[m.nom]=="mi" and "mi" in fam: continue
            s = m.signal(date)
            if s and m.ouvrir(s): ouverts+=1; fam.add(FAM[m.nom])
    eq = pd.Series(histo, index=pd.DatetimeIndex(dates))
    rend = eq.pct_change().fillna(0)
    an = len(eq)/365.25
    cagr = (eq.iloc[-1]**(1/an)-1)*100
    sh = rend.mean()/rend.std()*np.sqrt(365) if rend.std()>0 else 0
    dd = ((eq/eq.cummax())-1).min()*100
    m2 = len(rend)//2
    c1 = ((1+rend[:m2]).prod()**(1/(m2/365.25))-1)*100
    c2 = ((1+rend[m2:]).prod()**(1/((len(rend)-m2)/365.25))-1)*100
    contrib = {m.nom: m.total*100 for m in manches}
    return cagr, sh, dd, coupes, c1, c2, contrib

print("=== Q1 : LA RE-ENTREE SAUVE-T-ELLE LE ROBOT OR ? (10 ans) ===")
for re_, etiq in ((False, "SANS re-entree"), (True, "AVEC re-entree")):
    r = simuler(reentree=re_)
    print("  %-16s CAGR %+5.1f%% | Sharpe %4.2f | DD %+6.1f%% | or %+6.1f pts | nasdaq %+5.1f" %
          (etiq, r[0], r[1], r[2], r[6]["or"], r[6]["nasdaq"]))

print()
print("=== Q2 : QUEL RISQUE POUR L'OR ? (avec re-entree) ===")
print("  %-12s | %-7s | %-6s | %-7s | %-8s | %s" % ("Risque or", "CAGR", "Sharpe", "MaxDD", "Coupes", "Moities"))
print("  " + "-"*70)
for r_or in (0.03, 0.025, 0.02, 0.015, 0.01):
    r = simuler(r_or=r_or)
    print("  %-12s | %+6.1f%% | %6.2f | %+6.1f%% | %8d | %+5.1f/%+5.1f%%" %
          ("%.1f %%" % (r_or*100), r[0], r[1], r[2], r[3], r[4], r[5]))

print()
print("=== Q3 : REEQUILIBRER VERS LES ROBOTS QUI GAGNENT ===")
configs = [
    ("actuel (3/1,5/0,75/0,75)", dict()),
    ("or 1,5 % (reduit)", dict(r_or=0.015)),
    ("or 1,5 + BTC/petrole 1,25 %", dict(r_or=0.015, r_pet=0.0125, r_btc=0.0125)),
    ("or 1 + BTC/petrole 1,5 %", dict(r_or=0.01, r_pet=0.015, r_btc=0.015)),
    ("egalise a 1,5 % partout", dict(r_or=0.015, r_nas=0.015, r_pet=0.015, r_btc=0.015)),
]
print("  %-30s | %-7s | %-6s | %-7s | %s" % ("Configuration", "CAGR", "Sharpe", "MaxDD", "Moities"))
print("  " + "-"*76)
for nom, kw in configs:
    r = simuler(**kw)
    print("  %-30s | %+6.1f%% | %6.2f | %+6.1f%% | %+5.1f/%+5.1f%%" %
          (nom, r[0], r[1], r[2], r[4], r[5]))
