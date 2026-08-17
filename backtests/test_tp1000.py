# -*- coding: utf-8 -*-
"""TP a 1000$ (=+2R) au lieu de 500$ (=+1R), avec re-entree sur retracement.
Compare pour les 5 robots : BASE (actuel) | JIMMY 1R | JIMMY 2R.
Retracement 0.25xATR (0.5 pour Nasdaq, son gagnant). BE a +1R quand TP=2R.
Comptabilite R, 10 ans, frais reels."""
import requests, pandas as pd, numpy as np

def fetch(sym):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"range": "10y", "interval": "1d"},
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

def brk(df, frais, saison, mode, tpj=1.0, retrace=0.25):
    c, h, l = df["c"], df["h"], df["l"]
    h20 = h.rolling(20).max().shift(1); b10 = l.rolling(10).min().shift(1)
    a = atr_(df)
    trades, pos, attente = [], None, None
    for i in range(25, len(df)):
        if pos:
            fr = frais * pos["e"] / pos["R"]
            pos["s"] = max(pos["s"], b10.iloc[i])
            if l.iloc[i] <= pos["s"]:
                trades.append((pos["s"]-pos["e"])/pos["R"] - fr); pos = None; attente = None
            elif mode == "jimmy" and h.iloc[i] >= pos["e"] + tpj*pos["R"]:
                trades.append(tpj - fr); pos = None; attente = c.iloc[i]
            elif c.iloc[i] < b10.iloc[i]:
                trades.append((c.iloc[i]-pos["e"])/pos["R"] - fr); pos = None; attente = None
        if attente is not None and c.iloc[i] < b10.iloc[i]: attente = None
        if pos is None and en_saison(df.index[i], saison):
            entrer = c.iloc[i] > h20.iloc[i]
            if not entrer and mode == "jimmy" and attente is not None:
                entrer = l.iloc[i] <= attente - retrace*a.iloc[i] and c.iloc[i] > b10.iloc[i]
            if entrer:
                R = c.iloc[i] - b10.iloc[i]
                if R > 0: pos = dict(e=c.iloc[i], s=b10.iloc[i], R=R); attente = None
    return trades

def fib(df, frais, lb, fz, pull, mult, mode, tpj=1.0, retrace=0.25):
    c, h, l = df["c"], df["h"], df["l"]
    a = atr_(df); r = rsi_(c)
    trades, pos, attente, plancher = [], None, None, None
    for i in range(lb+16, len(df)):
        if pos:
            fr = frais * pos["e"] / pos["R"]
            if l.iloc[i] <= pos["s"]:
                res = (pos["s"]-pos["e"])/pos["R"] - fr
                trades.append(res); pos = None
                if res < -0.5: attente = None
            else:
                cible = (2.0 if mode == "base" else tpj)
                if tpj >= 2.0 or mode == "base":
                    if not pos["be"] and h.iloc[i] >= pos["e"] + pos["R"]:
                        pos["s"] = max(pos["s"], pos["e"]); pos["be"] = True
                if pos and h.iloc[i] >= pos["e"] + cible*pos["R"]:
                    trades.append(cible - fr); pos = None
                    if mode == "jimmy": attente = c.iloc[i]
        if attente is not None and (plancher is None or c.iloc[i] < plancher): attente = None
        if pos is not None: continue
        wh, wl = h.iloc[i-lb:i], l.iloc[i-lb:i]
        hi_i, lo_i = wh.values.argmax(), wl.values.argmin()
        setup = False
        if lo_i < hi_i:
            span = wh.iloc[hi_i] - wl.iloc[lo_i]
            if span > 0:
                retr = (wh.iloc[hi_i] - c.iloc[i]) / span
                setup = fz[0] <= retr <= fz[1] and r.iloc[i-1] < pull and r.iloc[i] > r.iloc[i-1]
        if setup:
            R = mult * a.iloc[i]
            pos = dict(e=c.iloc[i], s=c.iloc[i]-R, R=R, be=False)
            plancher = wl.iloc[lo_i]; attente = None
        elif (mode == "jimmy" and attente is not None and plancher is not None
              and l.iloc[i] <= attente - retrace*a.iloc[i] and c.iloc[i] > plancher):
            R = mult * a.iloc[i]
            pos = dict(e=c.iloc[i], s=c.iloc[i]-R, R=R, be=False); attente = None
    return trades

def ema(df, frais, mode, tpj=1.0, retrace=0.25):
    c, h, l = df["c"], df["h"], df["l"]
    e20 = c.ewm(span=20, adjust=False).mean(); e50 = c.ewm(span=50, adjust=False).mean()
    a = atr_(df)
    trades, pos, attente = [], None, None
    for i in range(60, len(df)):
        haussier = e20.iloc[i] > e50.iloc[i]
        if pos:
            R = pos["R"]; fr = frais * pos["e"] / R
            cible = 1.5 if mode == "base" else tpj
            if l.iloc[i] <= pos["e"] - R:
                trades.append(-1.0 - fr); pos = None; attente = None
            elif h.iloc[i] >= pos["e"] + cible*R:
                trades.append(cible - fr); pos = None
                if mode == "jimmy": attente = c.iloc[i]
            elif not haussier:
                trades.append((c.iloc[i]-pos["e"])/R - fr); pos = None; attente = None
        if not haussier: attente = None
        if pos is None and haussier:
            entrer = e20.iloc[i-1] <= e50.iloc[i-1]
            if not entrer and mode == "jimmy" and attente is not None:
                entrer = l.iloc[i] <= attente - retrace*a.iloc[i]
            if entrer:
                pos = dict(e=c.iloc[i], R=2*a.iloc[i]); attente = None
    return trades

def bilan(trades):
    t = np.array(trades)
    if len(t) == 0: return "0 trade"
    pf = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else 99.0
    return f"{len(t):>4} tr | {(t>0).mean()*100:>3.0f}% | {t.sum():>+7.1f} R | PF {pf:4.2f}"

btc, gc, nq, cl = fetch("BTC-USD"), fetch("GC=F"), fetch("NQ=F"), fetch("CL=F")

print("=== BTC EMA ===")
print("  BASE           :", bilan(ema(btc, 0.0008, "base")))
print("  JIMMY 1R (500$):", bilan(ema(btc, 0.0008, "jimmy", 1.0)))
print("  JIMMY 2R (1000$):", bilan(ema(btc, 0.0008, "jimmy", 2.0)))
print("=== Or fib+RSI ===")
print("  BASE           :", bilan(fib(gc, 0.0002, 10, (0.2,0.8), 55, 3.0, "base")))
print("  JIMMY 1R (500$):", bilan(fib(gc, 0.0002, 10, (0.2,0.8), 55, 3.0, "jimmy", 1.0)))
print("  JIMMY 2R (1000$):", bilan(fib(gc, 0.0002, 10, (0.2,0.8), 55, 3.0, "jimmy", 2.0)))
print("=== Nasdaq fib+RSI (retrace 0.5) ===")
print("  BASE           :", bilan(fib(nq, 0.0001, 7, (0.1,0.9), 60, 2.0, "base", retrace=0.5)))
print("  JIMMY 1R (500$):", bilan(fib(nq, 0.0001, 7, (0.1,0.9), 60, 2.0, "jimmy", 1.0, 0.5)))
print("  JIMMY 2R (1000$):", bilan(fib(nq, 0.0001, 7, (0.1,0.9), 60, 2.0, "jimmy", 2.0, 0.5)))
print("=== BTC Breakout ===")
print("  BASE           :", bilan(brk(btc, 0.0008, None, "base")))
print("  JIMMY 2R (1000$):", bilan(brk(btc, 0.0008, None, "jimmy", 2.0)))
print("=== Petrole saisonnier ===")
print("  BASE           :", bilan(brk(cl, 0.0009, (1201,531), "base")))
print("  JIMMY 2R (1000$):", bilan(brk(cl, 0.0009, (1201,531), "jimmy", 2.0)))
