# -*- coding: utf-8 -*-
"""Idee de Jimmy (TP +1R -> retracement -> re-entree si regime intact)
appliquee aux 4 autres robots, contre leur version actuelle.
Regime intact = canal de sortie tenu (cassures) / creux du swing tenu (fib).
Frais reels par marche. Comptabilite en R."""
import requests, pandas as pd, numpy as np

def fetch(sym, rng="10y"):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"range": rng, "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    return pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s"),
                         "h": q["high"], "l": q["low"], "c": q["close"]}).dropna().set_index("t")

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()
def atr_(df, n=14):
    tr = np.maximum(df["h"]-df["l"], np.maximum((df["h"]-df["c"].shift()).abs(),
                                                (df["l"]-df["c"].shift()).abs()))
    return wilder(tr, n)
def rsi_(s, n=14):
    d = s.diff()
    return 100 - 100/(1 + wilder(d.clip(lower=0), n) / wilder(-d.clip(upper=0), n).replace(0, np.nan))

def en_saison(date, saison):
    if saison is None: return True
    md = date.month*100 + date.day
    return md >= saison[0] or md <= saison[1]

def brk(df, frais, saison, mode, retrace=0.0):
    """Cassure 20/10. mode='base' (stop suiveur, pas de TP) ou 'jimmy'."""
    c, h, l = df["c"], df["h"], df["l"]
    h20 = h.rolling(20).max().shift(1); b10 = l.rolling(10).min().shift(1)
    a = atr_(df)
    trades, pos, attente = [], None, None
    for i in range(25, len(df)):
        date = df.index[i]
        if pos:
            fr = frais * pos["e"] / pos["R"]
            pos["s"] = max(pos["s"], b10.iloc[i])
            if l.iloc[i] <= pos["s"]:
                trades.append((pos["s"]-pos["e"])/pos["R"] - fr); pos = None; attente = None
            elif mode == "jimmy" and h.iloc[i] >= pos["e"] + pos["R"]:
                trades.append(1.0 - fr); pos = None; attente = c.iloc[i]
            elif c.iloc[i] < b10.iloc[i]:
                trades.append((c.iloc[i]-pos["e"])/pos["R"] - fr); pos = None; attente = None
        if attente is not None and c.iloc[i] < b10.iloc[i]:
            attente = None
        if pos is None and en_saison(date, saison):
            if c.iloc[i] > h20.iloc[i]:
                R = c.iloc[i] - b10.iloc[i]
                if R > 0: pos = dict(e=c.iloc[i], s=b10.iloc[i], R=R); attente = None
            elif (mode == "jimmy" and attente is not None
                  and l.iloc[i] <= attente - retrace*a.iloc[i] and c.iloc[i] > b10.iloc[i]):
                R = c.iloc[i] - b10.iloc[i]
                if R > 0: pos = dict(e=c.iloc[i], s=b10.iloc[i], R=R); attente = None
    return trades

def fib(df, frais, lookback, fz, pull, mult, mode, retrace=0.0):
    c, h, l = df["c"], df["h"], df["l"]
    a = atr_(df); r = rsi_(c)
    trades, pos, attente, plancher = [], None, None, None
    for i in range(lookback+16, len(df)):
        if pos:
            fr = frais * pos["e"] / pos["R"]
            if l.iloc[i] <= pos["s"]:
                trades.append((pos["s"]-pos["e"])/pos["R"] - fr); pos = None
                if mode == "base" or trades[-1] < 0: attente = None
            elif mode == "base":
                if not pos["be"] and h.iloc[i] >= pos["e"] + pos["R"]:
                    pos["s"] = pos["e"]; pos["be"] = True
                if h.iloc[i] >= pos["e"] + 2*pos["R"]:
                    trades.append(2.0 - fr); pos = None
            elif h.iloc[i] >= pos["e"] + pos["R"]:
                trades.append(1.0 - fr); pos = None; attente = c.iloc[i]
        if attente is not None and (plancher is None or c.iloc[i] < plancher):
            attente = None
        setup = False
        if pos is None:
            wh, wl = h.iloc[i-lookback:i], l.iloc[i-lookback:i]
            hi_i, lo_i = wh.values.argmax(), wl.values.argmin()
            if lo_i < hi_i:
                span = wh.iloc[hi_i] - wl.iloc[lo_i]
                if span > 0:
                    retr = (wh.iloc[hi_i] - c.iloc[i]) / span
                    setup = (fz[0] <= retr <= fz[1] and r.iloc[i-1] < pull
                             and r.iloc[i] > r.iloc[i-1])
                    if setup:
                        R = mult * a.iloc[i]
                        pos = dict(e=c.iloc[i], s=c.iloc[i]-R, R=R, be=False)
                        plancher = wl.iloc[lo_i]; attente = None
            if (not setup and mode == "jimmy" and pos is None and attente is not None
                    and l.iloc[i] <= attente - retrace*a.iloc[i]
                    and plancher is not None and c.iloc[i] > plancher):
                R = mult * a.iloc[i]
                pos = dict(e=c.iloc[i], s=c.iloc[i]-R, R=R, be=False); attente = None
    return trades

def bilan(trades):
    t = np.array(trades)
    if len(t) == 0: return "aucun trade"
    pf = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else 99.0
    return f"{len(t):>4} tr | {(t>0).mean()*100:>3.0f}% | {t.sum():>+7.1f} R | PF {pf:4.2f}"

btc, gc, nq, cl = fetch("BTC-USD"), fetch("GC=F"), fetch("NQ=F"), fetch("CL=F")

configs = [
    ("BTC Breakout", lambda m, x: brk(btc, 0.0008, None, m, x)),
    ("Petrole saison", lambda m, x: brk(cl, 0.0009, (1201, 531), m, x)),
    ("Or fib+RSI", lambda m, x: fib(gc, 0.0002, 10, (0.2, 0.8), 55, 3.0, m, x)),
    ("Nasdaq fib+RSI", lambda m, x: fib(nq, 0.0001, 7, (0.1, 0.9), 60, 2.0, m, x)),
]
for nom, fn in configs:
    print(f"=== {nom} ===")
    print(f"  BASE (actuel)        : {bilan(fn('base', 0))}")
    for x in (0.25, 0.5):
        print(f"  JIMMY retrace {x}   : {bilan(fn('jimmy', x))}")
