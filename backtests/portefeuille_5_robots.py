# -*- coding: utf-8 -*-
"""PORTEFEUILLE COMBINE des 5 robots — 5 ans, mark-to-market quotidien.
Chaque manche (sleeve) reproduit la logique de son robot en resolution
journaliere, avec la taille de position REELLE (risque fixe par trade,
comme les EA : notional = risque% / distance_stop%), les frais et swaps
exacts du compte FTMO de Jimmy.
Mesures cles pour FTMO : pire journee combinee (limite 5%), pire drawdown
combine (limite 10%), temps median pour +10% (objectif du challenge)."""
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
def atr(df, n=14):
    tr = np.maximum(df["h"]-df["l"], np.maximum((df["h"]-df["c"].shift()).abs(),
                                                (df["l"]-df["c"].shift()).abs()))
    return wilder(tr, n)
def rsi(s, n=14):
    d = s.diff()
    return 100 - 100/(1 + wilder(d.clip(lower=0), n) / wilder(-d.clip(upper=0), n).replace(0, np.nan))

btc, gc, nq, cl = fetch("BTC-USD"), fetch("GC=F"), fetch("NQ=F"), fetch("CL=F")
calendrier = btc.index  # le BTC couvre tous les jours

class Manche:
    """Machine a etats journaliere -> serie de rendements en % du compte."""
    def __init__(self, df, risque, frais_cote, swap_jour, fact_sem):
        self.df, self.risque = df, risque
        self.frais, self.swap, self.fs = frais_cote, swap_jour, fact_sem
        self.ret = pd.Series(0.0, index=df.index)
        self.trades = 0
        self.pos = None  # (entree, stop, tp, notional, be_niveau, be_fait)

    def ouvrir(self, i, entree, stop, tp=None, be=None):
        r0p = (entree - stop) / entree
        if r0p <= 0 or r0p > 0.5: return
        notional = min(self.risque / r0p, 2.0)
        self.ret.iloc[i] -= self.frais * notional
        self.pos = dict(e=entree, s=stop, tp=tp, n=notional, be=be, be_fait=False, prix=entree)
        self.trades += 1

    def fermer(self, i, prix):
        p = self.pos
        self.ret.iloc[i] += p["n"] * (prix - p["prix"]) / p["e"] - self.frais * p["n"]
        self.pos = None

    def marquer(self, i, c_jour, l_jour, h_jour):
        """Mark-to-market + gestion stop/tp/breakeven pour la journee i."""
        p = self.pos
        if p is None: return
        if l_jour <= p["s"]:
            self.fermer(i, p["s"]); return
        if p["tp"] and h_jour >= p["tp"]:
            self.fermer(i, p["tp"]); return
        if p["be"] and not p["be_fait"] and h_jour >= p["be"]:
            p["s"] = max(p["s"], p["e"]); p["be_fait"] = True
        self.ret.iloc[i] += p["n"] * ((c_jour - p["prix"]) / p["e"] + self.swap * self.fs)
        p["prix"] = c_jour

def manche_ema_btc():
    m = Manche(btc, 0.005, 0.0004, -0.000833, 1.0)
    c = btc["c"]; e20 = c.ewm(span=20, adjust=False).mean(); e50 = c.ewm(span=50, adjust=False).mean()
    a = atr(btc)
    for i in range(60, len(btc)):
        m.marquer(i, c.iloc[i], btc["l"].iloc[i], btc["h"].iloc[i])
        haussier = e20.iloc[i] > e50.iloc[i]
        if m.pos and not haussier: m.fermer(i, c.iloc[i])
        elif m.pos is None and haussier and e20.iloc[i-1] <= e50.iloc[i-1]:
            m.ouvrir(i, c.iloc[i], c.iloc[i] - 2*a.iloc[i], c.iloc[i] + 3*a.iloc[i])
    return m

def manche_donchian(df, risque, frais, swap, fs, n_e, n_s, saison=None):
    m = Manche(df, risque, frais, swap, fs)
    c, h, l = df["c"], df["h"], df["l"]
    haut = h.rolling(n_e).max().shift(1); bas = l.rolling(n_s).min().shift(1)
    for i in range(n_e + 2, len(df)):
        if m.pos:
            m.pos["s"] = max(m.pos["s"], bas.iloc[i])   # stop suiveur
        m.marquer(i, c.iloc[i], l.iloc[i], h.iloc[i])
        if m.pos and c.iloc[i] < bas.iloc[i]: m.fermer(i, c.iloc[i])
        ok_saison = True
        if saison is not None:
            md = df.index[i].month * 100 + df.index[i].day
            ok_saison = (md >= saison[0]) or (md <= saison[1])
        if m.pos is None and ok_saison and c.iloc[i] > haut.iloc[i]:
            m.ouvrir(i, c.iloc[i], bas.iloc[i])
    return m

def manche_fib(df, risque, frais, swap, fs, lookback, fib_lo, fib_hi, pull, mult, tpr):
    m = Manche(df, risque, frais, swap, fs)
    c, h, l = df["c"], df["h"], df["l"]
    a = atr(df); r = rsi(c)
    for i in range(lookback + 16, len(df)):
        m.marquer(i, c.iloc[i], l.iloc[i], h.iloc[i])
        if m.pos is not None: continue
        wh, wl = h.iloc[i-lookback:i], l.iloc[i-lookback:i]
        hi_i, lo_i = wh.values.argmax(), wl.values.argmin()
        if lo_i >= hi_i: continue
        span = wh.iloc[hi_i] - wl.iloc[lo_i]
        if span <= 0: continue
        retr = (wh.iloc[hi_i] - c.iloc[i]) / span
        if not (fib_lo <= retr <= fib_hi): continue
        if not (r.iloc[i-1] < pull and r.iloc[i] > r.iloc[i-1]): continue
        R = mult * a.iloc[i]
        m.ouvrir(i, c.iloc[i], c.iloc[i] - R, c.iloc[i] + tpr*R, be=c.iloc[i] + R)
    return m

manches = {
    "BTC EMA (0.5%)":      manche_ema_btc(),
    "BTC Breakout (0.5%)": manche_donchian(btc, 0.005, 0.0004, -0.000833, 1.0, 20, 10),
    "Or fib+RSI (1%)":     manche_fib(gc, 0.01, 0.0001, -0.000273, 1.4, 10, 0.20, 0.80, 55, 3.0, 2.0),
    "Nasdaq fib+RSI (1%)": manche_fib(nq, 0.01, 0.00003, -0.000213, 1.4, 7, 0.10, 0.90, 60, 2.0, 2.0),
    "Petrole saison (0.5%)": manche_donchian(cl, 0.005, 0.00045, +0.000051, 1.4, 20, 10, saison=(1201, 531)),
}

port = pd.DataFrame({n: m.ret.reindex(calendrier).fillna(0.0) for n, m in manches.items()})
total = port.sum(axis=1)
eq = (1 + total).cumprod()
annees = len(total) / 365.25
cagr = (eq.iloc[-1] ** (1/annees) - 1) * 100
dd_serie = eq / eq.cummax() - 1
pire_jour = total.min() * 100
mois = (1 + total).resample("ME").prod() - 1

print("=== PORTEFEUILLE COMBINE (5 robots, 5 ans, frais reels) ===")
print(f"Rendement annuel (CAGR)     : {cagr:+.1f} %")
print(f"Pire drawdown combine       : {dd_serie.min()*100:.1f} %  (coupe-circuit -8%, FTMO -10%)")
print(f"PIRE JOURNEE combinee       : {pire_jour:.2f} %  (coupe-circuit -3.5%, FTMO -5%)")
print(f"Journees sous -3.5%         : {(total < -0.035).sum()}")
print(f"Mois positifs               : {(mois > 0).mean()*100:.0f} %")
sharpe = total.mean() / total.std() * np.sqrt(365) if total.std() > 0 else 0
print(f"Sharpe portefeuille         : {sharpe:.2f}")

# temps pour atteindre +10% (objectif challenge FTMO)
jours_10 = []
vals = eq.values
for i0 in range(0, len(vals) - 1, 21):
    cible = vals[i0] * 1.10
    apres = np.where(vals[i0:] >= cible)[0]
    if len(apres): jours_10.append(apres[0])
if jours_10:
    print(f"Temps pour +10% (objectif)  : mediane {int(np.median(jours_10))} jours, "
          f"atteint dans {len(jours_10)*21*100//len(vals)}% des departs")

print("\n--- Contribution par robot (CAGR de la manche seule) ---")
for n, m in manches.items():
    e = (1 + m.ret).cumprod()
    cg = (e.iloc[-1] ** (1/(len(m.ret)/365.25)) - 1) * 100
    ddm = (e/e.cummax()-1).min() * 100
    print(f"{n:<24} : {cg:+5.1f}%/an | DD {ddm:5.1f}% | {m.trades:>3} trades")

print("\n--- Correlations entre robots (rendements mensuels) ---")
mens = (1 + port).resample("ME").prod() - 1
print(mens.corr().round(2).to_string())
