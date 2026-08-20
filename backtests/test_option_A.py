# -*- coding: utf-8 -*-
"""I2++ et L3+ AVEC l'option A (allocation inverse-volatilite) :
rendement annuel, et validation de A sur ses parametres voisins.
Configurations testees :
  I2++      = pyramidage + gardien 2,5 % + plafond correlation + parite 1,5 %
  I2++ + A  = idem + risque de chaque robot ajuste mensuellement selon sa
              propre volatilite recente (facteur borne)
  L3+       = I2++ + mode challenge (throttle Seykota)
  L3+ + A   = les deux
Validation de A : fenetre de mesure (30/60/90 j) et bornes (0,5-2 / 0,7-1,4)."""
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
                      ).dropna(subset=["h","l","c"]).drop_duplicates("t").set_index("t")
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
    def __init__(self, nom, df, risque, type_, reentree=False, fen_vol=60, **kw):
        self.nom, self.df, self.risque0, self.type, self.kw = nom, df, risque, type_, kw
        self.risque = risque; self.reentree = reentree
        self.frais, self.swap = FRAIS[nom], SWAP[nom]
        self.a = atr_(df); self.r = rsi_(df["c"])
        self.volq = df["c"].pct_change().rolling(fen_vol).std()
        self.hE = df["h"].rolling(kw.get("pe",20)).max().shift(1)
        self.bS = df["l"].rolling(kw.get("ps",10)).min().shift(1)
        self.idx = {d:i for i,d in enumerate(df.index)}
        self.pos=None; self.attente=0.0; self.plancher=0.0
    def jour(self,d): return self.idx.get(d)
    def gerer(self, date):
        i=self.jour(date)
        if i is None or self.pos is None: return 0.0
        p=self.pos; c,h,l=self.df["c"].iloc[i],self.df["h"].iloc[i],self.df["l"].iloc[i]; a=self.a.iloc[i]
        if self.type=="donch":
            p["s"]=max(p["s"], self.bS.iloc[i])
            if p["u"]<3 and a>0 and h>=p["proch"]:
                p["u"]+=1; p["n"]+=p["n0"]; p["proch"]+=0.5*a
                p["turtle"]=max(p.get("turtle",-1e9), h-2.0*a)
            niv=max(p["s"], p.get("turtle",-1e9))
            if l<=niv:
                g=p["n"]*(niv-p["prix"])/p["e"]-self.frais*p["n"]; self.pos=None; return g
            g=p["n"]*((c-p["prix"])/p["e"]+self.swap); p["prix"]=c; return g
        if l<=p["s"]:
            g=p["n"]*(p["s"]-p["prix"])/p["e"]-self.frais*p["n"]; self.pos=None
            self.attente=0.0; self.plancher=0.0; return g
        if h>=p["tp"]:
            g=p["n"]*(p["tp"]-p["prix"])/p["e"]-self.frais*p["n"]
            if self.reentree: self.attente=p["tp"]; self.plancher=p["lo"]
            self.pos=None; return g
        R0=p["e"]-p["s0"]
        if p["s"]<p["e"] and h>=p["e"]+R0: p["s"]=p["e"]
        g=p["n"]*((c-p["prix"])/p["e"]+self.swap); p["prix"]=c; return g
    def signal(self, date):
        i=self.jour(date)
        if i is None or i<130 or self.pos is not None: return None
        c=self.df["c"].iloc[i]; a=self.a.iloc[i]
        if a<=0 or np.isnan(a): return None
        if self.type=="donch":
            if np.isnan(self.hE.iloc[i]) or c<=self.hE.iloc[i]: return None
            s=self.bS.iloc[i]
            if s>=c: return None
            return dict(e=c,s=s,tp=None,a=a,lo=s)
        lb=self.kw["lb"]; fh,fl=self.df["h"].iloc[i-lb:i],self.df["l"].iloc[i-lb:i]
        hi_i,lo_i=fh.values.argmax(),fl.values.argmin(); R=self.kw["mult"]*a
        if self.reentree and self.attente>0 and self.plancher>0:
            if c<self.plancher: self.attente=0.0; self.plancher=0.0
            elif self.df["l"].iloc[i]<=self.attente-0.25*a:
                return dict(e=c,s=c-R,tp=c+self.kw["tpr"]*R,a=a,lo=self.plancher)
        if lo_i>=hi_i: return None
        span=fh.iloc[hi_i]-fl.iloc[lo_i]
        if span<=0: return None
        retr=(fh.iloc[hi_i]-c)/span
        if not (self.kw["flo"]<=retr<=self.kw["fhi"]): return None
        if not (self.r.iloc[i-1]<self.kw["rs"] and self.r.iloc[i]>self.r.iloc[i-1]): return None
        return dict(e=c,s=c-R,tp=c+self.kw["tpr"]*R,a=a,lo=fl.iloc[lo_i])
    def ouvrir(self, sig, facteur=1.0):
        r0=(sig["e"]-sig["s"])/sig["e"]
        if r0<=0 or r0>0.5: return False
        n=min(self.risque*facteur/r0, 2.0)
        self.pos=dict(e=sig["e"],s=sig["s"],s0=sig["s"],tp=sig["tp"] if sig["tp"] else 1e18,
                      n=n,n0=n,prix=sig["e"],u=1,proch=sig["e"]+0.5*sig["a"],turtle=-1e9,lo=sig.get("lo",0))
        self.attente=0.0
        return True

def simuler(option_A=False, challenge=False, fen_vol=60, bornes=(0.5, 2.0)):
    r = 0.015
    manches = [
        Manche("or", M["or"], r, "fib", True, fen_vol, lb=10, flo=0.2, fhi=0.8, rs=55, mult=3.0, tpr=1.5),
        Manche("nasdaq", M["nasdaq"], r, "fib", True, fen_vol, lb=7, flo=0.1, fhi=0.9, rs=60, mult=2.0, tpr=1.0),
        Manche("petrole", M["petrole"], r, "donch", False, fen_vol, pe=20, ps=10),
        Manche("btc", M["btc"], r, "donch", False, fen_vol, pe=55, ps=20),
    ]
    dates = sorted(set().union(*[set(m.df.index) for m in manches]))
    equite, histo, coupes = 1.0, [], 0
    mois = None
    par_annee, eq_debut = {}, {}
    for date in dates:
        if option_A and mois != (date.year, date.month):
            vols = {}
            for m in manches:
                i = m.jour(date)
                v = m.volq.iloc[i] if (i is not None and i > fen_vol) else np.nan
                vols[m.nom] = v if (v and not np.isnan(v) and v > 0) else None
            valides = [v for v in vols.values() if v]
            if valides:
                cible = float(np.median(valides))
                for m in manches:
                    v = vols.get(m.nom)
                    m.risque = m.risque0 * (float(np.clip(cible/v, *bornes)) if v else 1.0)
        mois = (date.year, date.month)
        jt = sum(m.gerer(date) for m in manches)
        if jt <= -0.025:
            jt = -0.025; coupes += 1
            for m in manches: m.pos = None
        an = date.year
        if an not in eq_debut: eq_debut[an] = equite
        equite *= (1+jt); histo.append(equite)
        par_annee[an] = (equite/eq_debut[an]-1)*100
        if jt <= -0.025: continue
        facteur = 1.0
        if challenge and len(histo) > 20 and equite < np.mean(histo[-20:]): facteur = 0.75
        ouverts = sum(1 for m in manches if m.pos is not None)
        fam = {FAM[m.nom] for m in manches if m.pos is not None}
        for m in manches:
            if m.pos is not None or ouverts >= 2: continue
            if FAM[m.nom] == "mi" and "mi" in fam: continue
            s = m.signal(date)
            if s and m.ouvrir(s, facteur): ouverts += 1; fam.add(FAM[m.nom])
    eq = pd.Series(histo, index=pd.DatetimeIndex(dates))
    rend = eq.pct_change().fillna(0)
    an_tot = len(eq)/365.25
    cagr = (eq.iloc[-1]**(1/an_tot)-1)*100
    sh = rend.mean()/rend.std()*np.sqrt(365) if rend.std()>0 else 0
    dd = ((eq/eq.cummax())-1).min()*100
    vals = rend.values; morts = reussis = 0
    for i0 in range(0, len(vals)-40, 21):
        e2 = 1.0
        for j in range(i0, len(vals)):
            e2 *= (1+vals[j])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; break
    n = morts+reussis
    return cagr, sh, dd, coupes, par_annee, (morts/n*100 if n else 0)

CONFIGS = [
    ("I2++",       dict(option_A=False, challenge=False)),
    ("I2++ + A",   dict(option_A=True,  challenge=False)),
    ("L3+",        dict(option_A=False, challenge=True)),
    ("L3+ + A",    dict(option_A=True,  challenge=True)),
]
res = {nom: simuler(**kw) for nom, kw in CONFIGS}
annees = sorted(set().union(*[set(res[n][4].keys()) for n, _ in CONFIGS]))

print("=== RENDEMENT ANNUEL (10 ans, frais et sizing reels, gardiens actifs) ===")
print("  %-6s | %s" % ("Annee", " | ".join("%-9s" % n for n, _ in CONFIGS)))
print("  " + "-"*54)
for a in annees:
    print("  %-6d | %s" % (a, " | ".join("%+8.1f%%" % res[n][4].get(a, 0) for n, _ in CONFIGS)))
print("  " + "-"*54)
print("  %-6s | %s" % ("CAGR", " | ".join("%+8.1f%%" % res[n][0] for n, _ in CONFIGS)))
print("  %-6s | %s" % ("Sharpe", " | ".join("%9.2f" % res[n][1] for n, _ in CONFIGS)))
print("  %-6s | %s" % ("MaxDD", " | ".join("%+8.1f%%" % res[n][2] for n, _ in CONFIGS)))
print("  %-6s | %s" % ("Morts", " | ".join("%8.0f%%" % res[n][5] for n, _ in CONFIGS)))
print("  %-6s | %s" % ("An +", " | ".join("%9s" % ("%d/%d" % (sum(1 for a in annees if res[n][4].get(a,0) > 0), len(annees))) for n, _ in CONFIGS)))

print()
print("=== VALIDATION DE L'OPTION A SUR SES VOISINS (standard 3) ===")
print("  %-34s | %-7s | %-6s | %-7s | %s" % ("Variante de A", "CAGR", "Sharpe", "MaxDD", "Morts"))
print("  " + "-"*70)
for etiq, kw in [
    ("sans A (reference)",            dict(option_A=False)),
    ("A fenetre 60 j, bornes 0,5-2",  dict(option_A=True, fen_vol=60, bornes=(0.5, 2.0))),
    ("A fenetre 30 j, bornes 0,5-2",  dict(option_A=True, fen_vol=30, bornes=(0.5, 2.0))),
    ("A fenetre 90 j, bornes 0,5-2",  dict(option_A=True, fen_vol=90, bornes=(0.5, 2.0))),
    ("A fenetre 60 j, bornes 0,7-1,4",dict(option_A=True, fen_vol=60, bornes=(0.7, 1.4))),
    ("A fenetre 60 j, bornes 0,6-1,6",dict(option_A=True, fen_vol=60, bornes=(0.6, 1.6))),
]:
    r = simuler(**kw)
    print("  %-34s | %+6.1f%% | %6.2f | %+6.1f%% | %4.0f%%" % (etiq, r[0], r[1], r[2], r[5]))
