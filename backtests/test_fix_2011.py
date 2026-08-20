# -*- coding: utf-8 -*-
"""LA CRISE QUI TUE : 2011 (dette europeenne) declenche le gardien total.
Diagnostic + recherche d'un correctif qui sauve 2011 SANS abimer le reste.
Candidats testes :
  A. reference (rien)
  B. MODE CHALLENGE Seykota (risque x0,75 sous la moyenne 20 j)
  C. or a 2 % au lieu de 3 %
  D. throttle plus severe x0,5
  E. plafond de correlation : 1 seul robot 'metal/indice' a la fois
  F. B + C combines
Chaque candidat est juge sur : 2011 (survie), les 6 autres crises, ET le
rendement 10 ans normal (pour verifier qu'on ne casse pas la poule aux oeufs)."""
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
    df["o"] = df["o"].fillna(df["c"])
    return df

def fetch(sym, depuis="2000-01-01"):
    morceaux, cur, fin = [], pd.Timestamp(depuis), pd.Timestamp.today()
    while cur < fin:
        suiv = min(cur + pd.DateOffset(years=10), fin)
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

M = {}
for nom, sym in (("or", "GC=F"), ("nasdaq", "^IXIC"), ("petrole", "CL=F"), ("btc", "BTC-USD")):
    M[nom] = fetch(sym)

FAMILLE = {"or": "metal", "nasdaq": "indice", "petrole": "energie", "btc": "crypto"}

class Manche:
    def __init__(self, nom, df, risque, type_, **kw):
        self.nom, self.df, self.risque, self.type, self.kw = nom, df, risque, type_, kw
        self.a = atr_(df); self.r = rsi_(df["c"])
        self.h20 = df["h"].rolling(kw.get("pe", 20)).max().shift(1)
        self.b10 = df["l"].rolling(kw.get("ps", 10)).min().shift(1)
        self.idx = {d: i for i, d in enumerate(df.index)}
        self.pos = None
    def jour(self, d): return self.idx.get(d)
    def gerer(self, date, pyramide):
        i = self.jour(date)
        if i is None or self.pos is None: return 0.0
        p = self.pos
        c, h, l = self.df["c"].iloc[i], self.df["h"].iloc[i], self.df["l"].iloc[i]
        a = self.a.iloc[i]
        if self.type == "donch":
            p["s"] = max(p["s"], self.b10.iloc[i])
            if pyramide and p["u"] < 3 and a > 0 and h >= p["proch"]:
                p["u"] += 1; p["n"] += p["n0"]; p["proch"] += 0.5*a; p["turtle"] = h - 2.0*a
            niveau = max(p["s"], p.get("turtle", -1e9))
            if l <= niveau:
                g = p["n"]*(niveau-p["prix"])/p["e"]; self.pos = None; return g
            g = p["n"]*(c-p["prix"])/p["e"]; p["prix"] = c; return g
        if l <= p["s"]:
            g = p["n"]*(p["s"]-p["prix"])/p["e"]; self.pos = None; return g
        if h >= p["tp"]:
            g = p["n"]*(p["tp"]-p["prix"])/p["e"]; self.pos = None; return g
        g = p["n"]*(c-p["prix"])/p["e"]; p["prix"] = c; return g
    def signal(self, date):
        i = self.jour(date)
        if i is None or i < 130 or self.pos is not None: return None
        c = self.df["c"].iloc[i]; a = self.a.iloc[i]
        if a <= 0 or np.isnan(a): return None
        if self.type == "donch":
            if np.isnan(self.h20.iloc[i]) or c <= self.h20.iloc[i]: return None
            s = self.b10.iloc[i]
            if s >= c: return None
            return dict(e=c, s=s, tp=None, a=a)
        lb = self.kw["lb"]
        fh, fl = self.df["h"].iloc[i-lb:i], self.df["l"].iloc[i-lb:i]
        hi_i, lo_i = fh.values.argmax(), fl.values.argmin()
        if lo_i >= hi_i: return None
        span = fh.iloc[hi_i] - fl.iloc[lo_i]
        if span <= 0: return None
        retr = (fh.iloc[hi_i] - c)/span
        if not (self.kw["flo"] <= retr <= self.kw["fhi"]): return None
        if not (self.r.iloc[i-1] < self.kw["rs"] and self.r.iloc[i] > self.r.iloc[i-1]): return None
        R = self.kw["mult"]*a
        return dict(e=c, s=c-R, tp=c+self.kw["tpr"]*R, a=a)
    def ouvrir(self, sig, facteur):
        r0 = (sig["e"]-sig["s"])/sig["e"]
        if r0 <= 0 or r0 > 0.5: return False
        n = min(self.risque*facteur/r0, 2.0)
        self.pos = dict(e=sig["e"], s=sig["s"], tp=sig["tp"] if sig["tp"] else 1e18,
                        n=n, n0=n, prix=sig["e"], u=1, proch=sig["e"]+0.5*sig["a"], turtle=-1e9)
        return True

def rejouer(d0, d1, variante, garde_j=-0.025, garde_tot=-0.08):
    r_or = 0.02 if variante in ("C", "F") else 0.03
    manches = [
        Manche("or", M["or"], r_or, "fib", lb=10, flo=0.2, fhi=0.8, rs=55, mult=3.0, tpr=1.5),
        Manche("nasdaq", M["nasdaq"], 0.015, "fib", lb=7, flo=0.1, fhi=0.9, rs=60, mult=2.0, tpr=1.0),
        Manche("petrole", M["petrole"], 0.0075, "donch", pe=20, ps=10),
        Manche("btc", M["btc"], 0.0075, "donch", pe=55, ps=20),
    ]
    dates = sorted(set().union(*[set(m.df.index) for m in manches]))
    dates = [d for d in dates if d0 <= d <= d1]
    equite, pire, coupes, halt = 1.0, 0.0, 0, False
    histo = []
    for date in dates:
        if halt: break
        jt = sum(m.gerer(date, True) for m in manches)
        if jt <= garde_j:
            jt = garde_j; coupes += 1
            for m in manches: m.pos = None
        equite *= (1+jt); histo.append(equite)
        pire = min(pire, equite-1)
        if equite-1 <= garde_tot: halt = True; break
        if jt <= garde_j: continue
        facteur = 1.0
        if variante in ("B", "F") and len(histo) > 20 and equite < np.mean(histo[-20:]): facteur = 0.75
        if variante == "D" and len(histo) > 20 and equite < np.mean(histo[-20:]): facteur = 0.5
        ouverts = sum(1 for m in manches if m.pos is not None)
        familles = {FAMILLE[m.nom] for m in manches if m.pos is not None}
        for m in manches:
            if m.pos is not None or ouverts >= 2: continue
            if variante == "E" and FAMILLE[m.nom] in ("metal", "indice") and \
               familles & {"metal", "indice"}: continue
            s = m.signal(date)
            if s and m.ouvrir(s, facteur):
                ouverts += 1; familles.add(FAMILLE[m.nom])
    return (equite-1)*100, pire*100, coupes, halt

CRISES = [("techno 2000-02","2000-03-01","2002-10-31"), ("2008","2007-10-01","2009-04-01"),
          ("dette 2011","2011-05-01","2011-12-31"), ("petrole 14-16","2014-06-01","2016-03-01"),
          ("2018","2018-09-01","2019-01-31"), ("COVID","2020-02-01","2020-06-30"),
          ("inflation 2022","2022-01-01","2022-12-31")]
NOMS = {"A":"A. reference", "B":"B. mode challenge x0,75", "C":"C. or a 2 %",
        "D":"D. throttle x0,5", "E":"E. cap correlation metal/indice", "F":"F. B + C"}

print("=== RECHERCHE D'UN CORRECTIF POUR 2011 ===")
print("%-32s | %-24s | %-9s | %s" % ("Variante", "2011", "crises +", "10 ans (2016-2026)"))
print("-" * 92)
for v in ("A", "B", "C", "D", "E", "F"):
    r2011 = rejouer(pd.Timestamp("2011-05-01"), pd.Timestamp("2011-12-31"), v)
    positives = 0
    for nom, a, b in CRISES:
        rr = rejouer(pd.Timestamp(a), pd.Timestamp(b), v)
        if rr[0] > 0: positives += 1
    long = rejouer(pd.Timestamp("2016-08-01"), pd.Timestamp("2026-08-01"), v)
    annees = 10.0
    cagr = ((1+long[0]/100)**(1/annees)-1)*100
    print("%-32s | %+6.1f%% creux %+5.1f%% %-4s | %d/7      | %+5.1f%%/an (creux %+.1f%%)" %
          (NOMS[v], r2011[0], r2011[1], "HALT" if r2011[3] else "ok", positives, cagr, long[1]))
