# -*- coding: utf-8 -*-
"""GRAND RETEST (demande de Jimmy, 19 aout) : toutes les idees recentes
rejouees AVEC le gardien -3,5 %/jour modelise, dans un seul banc d'essai.
Question : est-ce qu'un verdict change une fois la vraie securite simulee ?"""
import os, pandas as pd, numpy as np

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimisation_finale.py"),
           encoding="utf-8").read()
exec(src.split("KW2 =")[0].split('print(f"')[0])

gbp, jpy = fetch("GBPUSD=X"), fetch("USDJPY=X")
GARDE = -0.035

# ---------- classe deux-sens pour USDJPY ----------
class EmaFx2S:
    def __init__(self, nom, df, risque, frais, swap_l, swap_s, fs, tpj=1.5):
        self.nom, self.df, self.risque, self.frais = nom, df, risque, frais
        self.swap_l, self.swap_s, self.fs, self.tpj = swap_l, swap_s, fs, tpj
        self.idx = {d: i for i, d in enumerate(df.index)}
        self.pos, self.pnl, self.trades = None, {}, 0
        self.attente, self.runners = None, []
        self.a = atr_(df)
        self.e20 = df["c"].ewm(span=20, adjust=False).mean()
        self.e50 = df["c"].ewm(span=50, adjust=False).mean()
    def jour(self, date): return self.idx.get(date)
    def _clore(self, date, prix):
        p = self.pos
        self.pnl[date] = self.pnl.get(date, 0) + p["n"]*p["dir"]*(prix-p["prix"])/p["e"] - self.frais*p["n"]
        self.pos = None
    def gerer(self, date):
        i = self.jour(date)
        if i is None or self.pos is None: return
        p = self.pos
        c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
        haussier = self.e20.iloc[i] > self.e50.iloc[i]
        if p["dir"] == 1:
            if l <= p["s"]: self._clore(date, p["s"]); return
            if h >= p["tp"]: self._clore(date, p["tp"]); return
            if not haussier: self._clore(date, c); return
        else:
            if h >= p["s"]: self._clore(date, p["s"]); return
            if l <= p["tp"]: self._clore(date, p["tp"]); return
            if haussier: self._clore(date, c); return
        sw = self.swap_l if p["dir"] == 1 else self.swap_s
        self.pnl[date] = self.pnl.get(date, 0) + p["n"]*(p["dir"]*(c-p["prix"])/p["e"] + sw*self.fs)
        p["prix"] = c
    def signal(self, date):
        i = self.jour(date)
        if i is None or i < 60 or self.pos is not None: return None
        haussier = self.e20.iloc[i] > self.e50.iloc[i]
        ch = haussier and self.e20.iloc[i-1] <= self.e50.iloc[i-1]
        cb = (not haussier) and self.e20.iloc[i-1] >= self.e50.iloc[i-1]
        if not (ch or cb): return None
        c = self.df["c"].iloc[i]; R = 2*self.a.iloc[i]
        if ch: return dict(entree=c, stop=c-R, tp=c+self.tpj*R, dir=1)
        return dict(entree=c, stop=c+R, tp=c-self.tpj*R, dir=-1)
    def ouvrir(self, date, entree, stop, tp, dir):
        r0p = abs(entree - stop) / entree
        if r0p <= 0 or r0p > 0.5: return False
        n = min(self.risque / r0p, 2.0)
        self.pnl[date] = self.pnl.get(date, 0) - self.frais * n
        self.pos = dict(e=entree, s=stop, tp=tp, n=n, dir=dir, prix=entree)
        self.trades += 1
        return True

# ---------- patchs des idees ----------
def gerer_avec_runner(self, date):
    i = self.jour(date)
    if i is None: return
    if self.runners:
        c_ = self.df["c"].iloc[i]; l_ = self.df["l"].iloc[i]; h_ = self.df["h"].iloc[i]
        a_ = self.a.iloc[i]; restants = []
        for r in self.runners:
            r["vie"] += 1
            if l_ <= r["trail"]:
                self.pnl[date] = self.pnl.get(date, 0) + r["n"]*(r["trail"]-r["prix"])/r["e0"] - self.frais*r["n"]
            elif h_ >= r["cap"]:
                self.pnl[date] = self.pnl.get(date, 0) + r["n"]*(r["cap"]-r["prix"])/r["e0"] - self.frais*r["n"]
            elif r["vie"] >= 1:
                self.pnl[date] = self.pnl.get(date, 0) + r["n"]*(c_-r["prix"])/r["e0"] - self.frais*r["n"]
            else:
                self.pnl[date] = self.pnl.get(date, 0) + r["n"]*((c_-r["prix"])/r["e0"] + self.swap*self.fs)
                r["prix"] = c_; r["trail"] = max(r["trail"], c_ - a_); restants.append(r)
        self.runners = restants
    if self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        self._clore(date, p["s"]); self.attente = None; return
    if p.get("tp") and h >= p["tp"]:
        tp = p["tp"]; R = (tp - p["e"]) / self.tpj
        self.pnl[date] = self.pnl.get(date, 0) + 0.75*p["n"]*(tp-p["prix"])/p["e"] - self.frais*0.75*p["n"]
        self.runners.append(dict(n=0.25*p["n"], e0=p["e"], prix=tp,
                                 trail=max(p["e"] + 0.1*R, tp - self.a.iloc[i]),
                                 cap=p["e"] + 3*R, vie=0))
        self.pos = None
        if self.jimmy: self.attente = tp
        return
    if p.get("be") and not p["be_fait"] and h >= p["be"]:
        p["s"] = max(p["s"], p["e"]); p["be_fait"] = True
    if p.get("sortie_cloture") and self.sortie_cloture(i):
        self._clore(date, c); self.attente = None; return
    self.pnl[date] = self.pnl.get(date, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs)
    p["prix"] = c

def gerer_avec_partiel(self, date):
    i = self.jour(date)
    if i is None or self.pos is None: return
    p = self.pos
    c, l, h = self.df["c"].iloc[i], self.df["l"].iloc[i], self.df["h"].iloc[i]
    if p.get("trail"): p["s"] = max(p["s"], self.b10.iloc[i])
    if l <= p["s"]:
        self._clore(date, p["s"]); self.attente = None; return
    if not p.get("partiel_fait"):
        ps = p["e"] * (1 + 0.005 / p["n"])
        if h >= ps:
            self.pnl[date] = self.pnl.get(date, 0) + (1/3)*p["n"]*(ps-p["prix"])/p["e"] - self.frais*p["n"]/3
            p["n"] *= 2/3
            p["partiel_fait"] = True
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

def en_mode_courir(s):
    s.sortie_cloture = (lambda i, s=s: s.e20.iloc[i] <= s.e50.iloc[i])
    original = s.signal
    def signal_sans_tp(date, s=s, original=original):
        sig = original(date)
        if sig is None: return None
        sig["tp"] = None; sig["sortie_cloture"] = True
        return sig
    s.signal = signal_sans_tp
    s.jimmy = False

def en_mode_be_rapide(s, tp_r):
    original = s.signal
    def signal_mod(date, s=s, original=original, tp_r=tp_r):
        sig = original(date)
        if sig is None: return None
        R = sig["entree"] - sig["stop"]
        if R <= 0: return None
        sig["tp"] = sig["entree"] + tp_r * R
        sig["be"] = sig["entree"] + 0.1 * R
        return sig
    s.signal = signal_mod

# ---------- calendrier news (pour la variante news-only) ----------
def premier_vendredi(an, mois):
    d = pd.Timestamp(an, mois, 1)
    return d + pd.Timedelta(days=(4 - d.dayofweek) % 7)
def jour_ouvrable(d):
    while d.dayofweek >= 5: d += pd.Timedelta(days=1)
    return d
evenements = []
for an in range(2021, 2027):
    for mois in range(1, 13):
        evenements.append(premier_vendredi(an, mois))
        evenements.append(jour_ouvrable(pd.Timestamp(an, mois, 12)))
    for mois, jour in ((1, 28), (3, 18), (5, 6), (6, 17), (7, 29), (9, 16), (11, 4), (12, 16)):
        d = pd.Timestamp(an, mois, jour)
        evenements.append(d + pd.Timedelta(days=(2 - d.dayofweek) % 7))
evenements = pd.DatetimeIndex(sorted(set(evenements)))

# ---------- banc d'essai ----------
def sim(variante):
    tp_or, tp_nq, tp_ema = 1.5, 1.0, 2.0
    if variante == "tp25": tp_or = tp_nq = tp_ema = 2.5
    if variante == "tp30": tp_or = tp_nq = tp_ema = 3.0
    cap = {"cap1": 1, "cap3": 3, "sans_cap": 999}.get(variante, 2)
    mult_r = 2.0 if variante == "risque_x2" else 1.0
    r_or = 0.015 if variante == "or_15" else 0.03
    fib_zone = (0.618, 0.886) if variante == "fib_profond" else (0.2, 0.8)
    fib_zone_nq = (0.618, 0.886) if variante == "fib_profond" else (0.1, 0.9)
    jim = variante != "sans_reentree"
    sleeves = [
        Fib("Or", gc, r_or*mult_r, 0.0001, -0.000273, 1.4, jimmy=jim, retrace=0.25, tpj=tp_or,
            lookback=10, fib=fib_zone, pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl, 0.0075*mult_r, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc, 0.0075*mult_r, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq, 0.015*mult_r, 0.00003, -0.000213, 1.4, jimmy=jim,
            retrace=0.5, tpj=tp_nq, lookback=7, fib=fib_zone_nq, pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc, 0.0075*mult_r, 0.0004, -0.000833, 1.0,
               jimmy=(variante != "courir" and jim), retrace=0.25, tpj=tp_ema),
    ]
    if variante == "ema200":
        for s in sleeves:
            s.sma200 = s.df["c"].rolling(200).mean()
            original = s.signal
            def signal_f(date, s=s, original=original):
                sig = original(date)
                if sig is None: return None
                i = s.jour(date)
                if i is None or np.isnan(s.sma200.iloc[i]): return None
                if s.df["c"].iloc[i] <= s.sma200.iloc[i]: return None
                return sig
            s.signal = signal_f
    if variante == "sans_nasdaq":
        sleeves = [s for s in sleeves if s.nom != "Nasdaq"]
    if variante == "gbpusd":
        sleeves.append(EmaBTC("GBPUSD", gbp, 0.0075, 0.00003, -0.000033, 1.4,
                              jimmy=True, retrace=0.25, tpj=1.5))
    if variante == "usdjpy":
        sleeves.append(EmaFx2S("USDJPY", jpy, 0.0075, 0.00003, +0.00005, -0.00010, 1.4))
    TP3 = ("Or", "Nasdaq", "BTC EMA")
    for s in sleeves:
        if variante == "runner" and s.nom in TP3:
            s.gerer = gerer_avec_runner.__get__(s)
        if variante == "partiel" and s.nom in TP3:
            s.gerer = gerer_avec_partiel.__get__(s)
        if variante == "courir" and s.nom in ("Or", "Nasdaq"):
            en_mode_courir(s)
        if variante == "be_rapide" and s.nom in TP3:
            en_mode_be_rapide(s, 2.0)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    permises = None
    if variante == "news_only":
        idx = pd.DatetimeIndex(dates)
        permises = set()
        for ev in evenements:
            apres = idx[idx >= ev]
            for d in apres[:3]: permises.add(d)
    coupes = 0
    for date in dates:
        for s in sleeves: s.gerer(date)
        jour_total = sum(s.pnl.get(date, 0) for s in sleeves)
        if jour_total <= GARDE:
            facteur = GARDE / jour_total
            for s in sleeves:
                if date in s.pnl: s.pnl[date] *= facteur
                if s.pos is not None:
                    s.pnl[date] = s.pnl.get(date, 0) - s.frais * s.pos["n"]
                s.pos = None; s.attente = None; s.runners = []
            coupes += 1
            continue
        if permises is not None and date not in permises: continue
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        for s in sleeves:
            if s.pos is not None: continue
            sig = s.signal(date)
            if sig is None: continue
            if ouverts >= cap: continue
            if s.ouvrir(date, **sig): ouverts += 1
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    eq = (1 + total).cumprod(); annees = len(total)/365.25
    cagr = (eq.iloc[-1]**(1/annees)-1)*100
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+total[m:]).prod()**(1/((len(total)-m)/365.25))-1)*100
    return cagr, sh, coupes, c1, c2

CONFIGS = [
    ("Reference (ecurie actuelle)", "ref"),
    ("Runner 25% -> 3R apres TP", "runner"),
    ("Partielle 1/3 a +500 $", "partiel"),
    ("TP tous a 2.5R", "tp25"),
    ("TP tous a 3R", "tp30"),
    ("Laisser courir (recroise EMA)", "courir"),
    ("BE des profit + TP 2R", "be_rapide"),
    ("Entrees news seulement (0-2 j)", "news_only"),
    ("6e robot GBPUSD", "gbpusd"),
    ("6e robot USDJPY", "usdjpy"),
    ("Sans le Nasdaq", "sans_nasdaq"),
    ("Plafond 1 position", "cap1"),
    ("Plafond 3 positions", "cap3"),
    ("Sans plafond", "sans_cap"),
    ("Risque x2 partout", "risque_x2"),
    ("Or a 1.5% (avant renforcement)", "or_15"),
    ("Fib profond 0.618-0.886", "fib_profond"),
    ("Filtre EMA200 global", "ema200"),
    ("Sans TP ni re-entree (pre-I2)", "sans_reentree"),
]
resultats = []
for nom, v in CONFIGS:
    r = sim(v)
    resultats.append((nom, r))
resultats.sort(key=lambda x: -x[1][0])
print(f"{'Config (gardien -3,5 % partout)':<34} | {'CAGR':>6} | {'Sharpe':>6} | {'Coupes':>6} | {'Moities':>13}")
print("-" * 84)
for nom, r in resultats:
    print(f"{nom:<34} | {r[0]:>+5.1f}% | {r[1]:>6.2f} | {r[2]:>6} | {r[3]:>+5.1f}/{r[4]:>+5.1f}%")
