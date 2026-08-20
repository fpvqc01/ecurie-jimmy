# -*- coding: utf-8 -*-
"""DIAGNOSTIC : ou et pourquoi le systeme perd-il ?
On decompose 10 ans mois par mois : quel robot perd, dans quel regime de
marche, et est-ce que les pertes se ressemblent ?
Mesure du regime : indice de 'hachage' (chop) = combien de marches sont
SANS tendance (|prix - EMA50| < 1 ATR) ce mois-la."""
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

M = {}
for nom, sym in (("or", "GC=F"), ("nasdaq", "NQ=F"), ("petrole", "CL=F"), ("btc", "BTC-USD")):
    M[nom] = fetch(sym)

FRAIS = {"or": 0.0001, "nasdaq": 0.00003, "petrole": 0.00045, "btc": 0.0004}
SWAP = {"or": -0.000273, "nasdaq": -0.000213, "petrole": +0.000051, "btc": -0.000833}
FAMILLE = {"or": "mi", "nasdaq": "mi", "petrole": "en", "btc": "cr"}

class Manche:
    def __init__(self, nom, df, risque, type_, **kw):
        self.nom, self.df, self.risque, self.type, self.kw = nom, df, risque, type_, kw
        self.frais, self.swap = FRAIS[nom], SWAP[nom]
        self.a = atr_(df); self.r = rsi_(df["c"])
        self.e50 = df["c"].ewm(span=50, adjust=False).mean()
        self.hE = df["h"].rolling(kw.get("pe", 20)).max().shift(1)
        self.bS = df["l"].rolling(kw.get("ps", 10)).min().shift(1)
        self.idx = {d: i for i, d in enumerate(df.index)}
        self.pos = None; self.pnl_mois = {}
    def jour(self, d): return self.idx.get(d)
    def _note(self, date, g):
        cle = (date.year, date.month)
        self.pnl_mois[cle] = self.pnl_mois.get(cle, 0) + g
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
                g = p["n"]*(niveau-p["prix"])/p["e"] - self.frais*p["n"]; self.pos = None
                self._note(date, g); return g
            g = p["n"]*((c-p["prix"])/p["e"] + self.swap); p["prix"] = c
            self._note(date, g); return g
        if l <= p["s"]:
            g = p["n"]*(p["s"]-p["prix"])/p["e"] - self.frais*p["n"]; self.pos = None
            self._note(date, g); return g
        if h >= p["tp"]:
            g = p["n"]*(p["tp"]-p["prix"])/p["e"] - self.frais*p["n"]; self.pos = None
            self._note(date, g); return g
        g = p["n"]*((c-p["prix"])/p["e"] + self.swap); p["prix"] = c
        self._note(date, g); return g
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
        span = fh.iloc[hi_i]-fl.iloc[lo_i]
        if span <= 0: return None
        retr = (fh.iloc[hi_i]-c)/span
        if not (self.kw["flo"] <= retr <= self.kw["fhi"]): return None
        if not (self.r.iloc[i-1] < self.kw["rs"] and self.r.iloc[i] > self.r.iloc[i-1]): return None
        R = self.kw["mult"]*a
        return dict(e=c, s=c-R, tp=c+self.kw["tpr"]*R, a=a)
    def ouvrir(self, sig):
        r0 = (sig["e"]-sig["s"])/sig["e"]
        if r0 <= 0 or r0 > 0.5: return False
        n = min(self.risque/r0, 2.0)
        self.pos = dict(e=sig["e"], s=sig["s"], tp=sig["tp"] if sig["tp"] else 1e18,
                        n=n, n0=n, prix=sig["e"], u=1, proch=sig["e"]+0.5*sig["a"], turtle=-1e9)
        return True

manches = [
    Manche("or", M["or"], 0.03, "fib", lb=10, flo=0.2, fhi=0.8, rs=55, mult=3.0, tpr=1.5),
    Manche("nasdaq", M["nasdaq"], 0.015, "fib", lb=7, flo=0.1, fhi=0.9, rs=60, mult=2.0, tpr=1.0),
    Manche("petrole", M["petrole"], 0.0075, "donch", pe=20, ps=10),
    Manche("btc", M["btc"], 0.0075, "donch", pe=55, ps=20),
]
dates = sorted(set().union(*[set(m.df.index) for m in manches]))
equite, mensuel, coupes_mois = 1.0, {}, {}
eq_debut = {}
for date in dates:
    jt = sum(m.gerer(date, True) for m in manches)
    if jt <= -0.025:
        jt = -0.025
        coupes_mois[(date.year, date.month)] = coupes_mois.get((date.year, date.month), 0) + 1
        for m in manches: m.pos = None
    cle = (date.year, date.month)
    if cle not in eq_debut: eq_debut[cle] = equite
    equite *= (1+jt)
    mensuel[cle] = (equite/eq_debut[cle]-1)*100
    if jt <= -0.025: continue
    ouverts = sum(1 for m in manches if m.pos is not None)
    fam = {FAMILLE[m.nom] for m in manches if m.pos is not None}
    for m in manches:
        if m.pos is not None or ouverts >= 2: continue
        if FAMILLE[m.nom] == "mi" and "mi" in fam: continue
        s = m.signal(date)
        if s and m.ouvrir(s): ouverts += 1; fam.add(FAMILLE[m.nom])

# indice de hachage mensuel : combien de marches sans tendance
chop = {}
for cle in mensuel:
    an, mo = cle
    n_sans = 0
    for m in manches:
        sel = m.df[(m.df.index.year == an) & (m.df.index.month == mo)]
        if len(sel) < 5: continue
        i = m.idx.get(sel.index[-1])
        if i is None or i < 60: continue
        ecart = abs(m.df["c"].iloc[i] - m.e50.iloc[i]) / max(m.a.iloc[i], 1e-9)
        if ecart < 1.0: n_sans += 1
    chop[cle] = n_sans

print("=== LES 12 PIRES MOIS (10 ans) ===")
print("  %-9s | %-8s | %-7s | %s" % ("Mois", "Resultat", "Marches sans tendance", "Robot le plus perdant"))
print("  " + "-"*72)
pires = sorted(mensuel.items(), key=lambda x: x[1])[:12]
for cle, v in pires:
    pertes = {m.nom: m.pnl_mois.get(cle, 0)*100 for m in manches}
    pire_robot = min(pertes, key=pertes.get)
    print("  %04d-%02d   | %+7.2f%% | %d/4                   | %s (%+.2f%%)%s" %
          (cle[0], cle[1], v, chop[cle], pire_robot, pertes[pire_robot],
           "  [%d coupe(s)]" % coupes_mois[cle] if cle in coupes_mois else ""))

# correlation hachage <-> resultat
xs = np.array([chop[c] for c in mensuel]); ys = np.array([mensuel[c] for c in mensuel])
print()
print("=== LE HACHAGE EXPLIQUE-T-IL LES PERTES ? ===")
for n in range(5):
    sel = ys[xs == n]
    if len(sel) < 3: continue
    print("  %d marche(s) sans tendance : %3d mois | resultat moyen %+6.2f%% | %2.0f%% de mois positifs" %
          (n, len(sel), sel.mean(), (sel > 0).mean()*100))
print("  correlation hachage/resultat : %.3f" % np.corrcoef(xs, ys)[0, 1])

print()
print("=== CONTRIBUTION TOTALE PAR ROBOT (10 ans) ===")
for m in manches:
    tot = sum(m.pnl_mois.values())*100
    mois_pos = sum(1 for v in m.pnl_mois.values() if v > 0)
    print("  %-8s %+8.1f points | %d mois positifs sur %d" % (m.nom, tot, mois_pos, len(m.pnl_mois)))
