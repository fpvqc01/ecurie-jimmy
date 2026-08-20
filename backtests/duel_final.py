# -*- coding: utf-8 -*-
"""DUEL FINAL DES 4 ECURIES — rendement annuel, annee par annee.
  I2+  : production actuelle (gardien -3,5 %, pas de pyramidage)
  L3   : + pyramidage Turtle + gardien -2,5 %  (= I2++ d'origine)
  I2++ : L3 + PLAFOND DE CORRELATION (un seul metal/indice a la fois)
  L3+  : I2++ + MODE CHALLENGE (throttle Seykota x0,75 en drawdown)
10 ans de donnees (2016-2026), sizing reel, frais reels, gardiens actifs."""
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

print("Telechargement 10 ans...")
M = {}
for nom, sym in (("or", "GC=F"), ("nasdaq", "NQ=F"), ("petrole", "CL=F"), ("btc", "BTC-USD")):
    M[nom] = fetch(sym)
    print("  %-8s %d jours (%s -> %s)" % (nom, len(M[nom]), M[nom].index[0].date(), M[nom].index[-1].date()))

FAMILLE = {"or": "metal_indice", "nasdaq": "metal_indice", "petrole": "energie", "btc": "crypto"}
FRAIS = {"or": 0.0001, "nasdaq": 0.00003, "petrole": 0.00045, "btc": 0.0004}
SWAP = {"or": -0.000273, "nasdaq": -0.000213, "petrole": +0.000051, "btc": -0.000833}

class Manche:
    def __init__(self, nom, df, risque, type_, **kw):
        self.nom, self.df, self.risque, self.type, self.kw = nom, df, risque, type_, kw
        self.frais, self.swap = FRAIS[nom], SWAP[nom]
        self.a = atr_(df); self.r = rsi_(df["c"])
        self.hE = df["h"].rolling(kw.get("pe", 20)).max().shift(1)
        self.bS = df["l"].rolling(kw.get("ps", 10)).min().shift(1)
        self.idx = {d: i for i, d in enumerate(df.index)}
        self.pos = None; self.trades = 0
    def jour(self, d): return self.idx.get(d)
    def gerer(self, date, pyramide):
        i = self.jour(date)
        if i is None or self.pos is None: return 0.0
        p = self.pos
        c, h, l = self.df["c"].iloc[i], self.df["h"].iloc[i], self.df["l"].iloc[i]
        a = self.a.iloc[i]
        if self.type == "donch":
            p["s"] = max(p["s"], self.bS.iloc[i])
            if pyramide and p["u"] < 3 and a > 0 and h >= p["proch"]:
                p["u"] += 1; p["n"] += p["n0"]; p["proch"] += 0.5*a
                p["turtle"] = max(p.get("turtle", -1e9), h - 2.0*a)
            niveau = max(p["s"], p.get("turtle", -1e9))
            if l <= niveau:
                g = p["n"]*(niveau-p["prix"])/p["e"] - self.frais*p["n"]; self.pos = None; return g
            g = p["n"]*((c-p["prix"])/p["e"] + self.swap); p["prix"] = c; return g
        if l <= p["s"]:
            g = p["n"]*(p["s"]-p["prix"])/p["e"] - self.frais*p["n"]; self.pos = None; return g
        if h >= p["tp"]:
            g = p["n"]*(p["tp"]-p["prix"])/p["e"] - self.frais*p["n"]; self.pos = None; return g
        g = p["n"]*((c-p["prix"])/p["e"] + self.swap); p["prix"] = c; return g
    def signal(self, date):
        i = self.jour(date)
        if i is None or i < 130 or self.pos is not None: return None
        c = self.df["c"].iloc[i]; a = self.a.iloc[i]
        if a <= 0 or np.isnan(a): return None
        if self.type == "donch":
            if np.isnan(self.hE.iloc[i]) or c <= self.hE.iloc[i]: return None
            s = self.bS.iloc[i]
            if s >= c: return None
            return dict(e=c, s=s, tp=None, a=a)
        lb = self.kw["lb"]
        fh, fl = self.df["h"].iloc[i-lb:i], self.df["l"].iloc[i-lb:i]
        hi_i, lo_i = fh.values.argmax(), fl.values.argmin()
        if lo_i >= hi_i: return None
        span = fh.iloc[hi_i] - fl.iloc[lo_i]
        if span <= 0: return None
        retr = (fh.iloc[hi_i]-c)/span
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
        self.trades += 1
        return True

def simuler(gen):
    pyramide = gen in ("L3", "I2++", "L3+")
    garde = -0.035 if gen == "I2+" else -0.025
    correlation = gen in ("I2++", "L3+")
    challenge = (gen == "L3+")
    manches = [
        Manche("or", M["or"], 0.03, "fib", lb=10, flo=0.2, fhi=0.8, rs=55, mult=3.0, tpr=1.5),
        Manche("nasdaq", M["nasdaq"], 0.015, "fib", lb=7, flo=0.1, fhi=0.9, rs=60, mult=2.0, tpr=1.0),
        Manche("petrole", M["petrole"], 0.0075, "donch", pe=20, ps=10),
        Manche("btc", M["btc"], 0.0075, "donch", pe=55, ps=20),
    ]
    dates = sorted(set().union(*[set(m.df.index) for m in manches]))
    equite, histo, coupes = 1.0, [], 0
    par_annee = {}
    eq_debut_annee = {}
    for date in dates:
        jt = sum(m.gerer(date, pyramide) for m in manches)
        if jt <= garde:
            jt = garde; coupes += 1
            for m in manches: m.pos = None
        an = date.year
        if an not in eq_debut_annee: eq_debut_annee[an] = equite
        equite *= (1+jt); histo.append(equite)
        par_annee[an] = (equite/eq_debut_annee[an] - 1)*100
        if jt <= garde: continue
        facteur = 1.0
        if challenge and len(histo) > 20 and equite < np.mean(histo[-20:]): facteur = 0.75
        ouverts = sum(1 for m in manches if m.pos is not None)
        familles = {FAMILLE[m.nom] for m in manches if m.pos is not None}
        for m in manches:
            if m.pos is not None or ouverts >= 2: continue
            if correlation and FAMILLE[m.nom] == "metal_indice" and "metal_indice" in familles: continue
            s = m.signal(date)
            if s and m.ouvrir(s, facteur):
                ouverts += 1; familles.add(FAMILLE[m.nom])
    eq = pd.Series(histo, index=pd.DatetimeIndex(dates))
    rend = eq.pct_change().fillna(0)
    annees = len(eq)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    sharpe = rend.mean()/rend.std()*np.sqrt(365) if rend.std() > 0 else 0
    dd = ((eq/eq.cummax())-1).min()*100
    return cagr, sharpe, dd, coupes, par_annee, sum(m.trades for m in manches)

GENS = ("I2+", "L3", "I2++", "L3+")
res = {g: simuler(g) for g in GENS}

print()
print("=== RENDEMENT ANNUEL PAR ECURIE (10 ans, sizing et frais reels) ===")
annees = sorted(set().union(*[set(res[g][4].keys()) for g in GENS]))
print("  %-6s | %s" % ("Annee", " | ".join("%-8s" % g for g in GENS)))
print("  " + "-"*52)
for an in annees:
    ligne = " | ".join("%+7.1f%%" % res[g][4].get(an, 0) for g in GENS)
    print("  %-6d | %s" % (an, ligne))
print("  " + "-"*52)
print("  %-6s | %s" % ("CAGR", " | ".join("%+7.1f%%" % res[g][0] for g in GENS)))
print("  %-6s | %s" % ("Sharpe", " | ".join("%8.2f" % res[g][1] for g in GENS)))
print("  %-6s | %s" % ("MaxDD", " | ".join("%+7.1f%%" % res[g][2] for g in GENS)))
print("  %-6s | %s" % ("Coupes", " | ".join("%8d" % res[g][3] for g in GENS)))
print("  %-6s | %s" % ("Trades", " | ".join("%8d" % res[g][5] for g in GENS)))
print()
print("  Annees positives : " + " | ".join(
    "%s %d/%d" % (g, sum(1 for a in annees if res[g][4].get(a, 0) > 0), len(annees)) for g in GENS))
