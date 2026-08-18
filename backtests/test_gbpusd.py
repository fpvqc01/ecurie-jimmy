# -*- coding: utf-8 -*-
"""Criblage GBPUSD (10 ans journalier) : nos familles gagnantes, dans les
DEUX sens (le forex n'a pas de biais haussier structurel).
Frais FTMO forex : ~0.012% aller-retour (spread+commission), swap ~0.005%/j."""
import requests, pandas as pd, numpy as np

r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/GBPUSD=X",
                 params={"range": "10y", "interval": "1d"},
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
r.raise_for_status()
d = r.json()["chart"]["result"][0]
q = d["indicators"]["quote"][0]
df = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s"),
                   "h": q["high"], "l": q["low"], "c": q["close"]}).dropna().set_index("t")
c, h, l = df["c"], df["h"], df["l"]
print(f"GBPUSD : {df.index[0].date()} -> {df.index[-1].date()}, {c.iloc[0]:.4f} -> {c.iloc[-1]:.4f}")

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()
tr = np.maximum(h - l, np.maximum((h - c.shift()).abs(), (l - c.shift()).abs()))
atr = wilder(tr, 14)
def rsi(s, n):
    dd = s.diff()
    return 100 - 100/(1 + wilder(dd.clip(lower=0), n) / wilder(-dd.clip(upper=0), n).replace(0, np.nan))
r14 = rsi(c, 14)
FRAIS_RT, SWAP_J = 0.00006, 0.000033  # specs MT5 reelles : ~0.3 pip + 2x2.5$/lot, swap -4.47 pts/j

def bilan(trades):
    t = np.array(trades)
    if len(t) == 0: return "0 trade"
    pf = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else 99.0
    m1, m2 = t[:len(t)//2].sum(), t[len(t)//2:].sum()
    return f"{len(t):>4} tr | {(t>0).mean()*100:>3.0f}% | total {t.sum():>+6.1f} R | PF {pf:4.2f} | moities {m1:+.1f}/{m2:+.1f}"

def ema_2sens(sens):
    e20 = c.ewm(span=20, adjust=False).mean(); e50 = c.ewm(span=50, adjust=False).mean()
    trades, pos = [], None
    for i in range(60, len(c)):
        haussier = e20.iloc[i] > e50.iloc[i]
        if pos:
            R = pos["R"]; fr = FRAIS_RT * pos["e"] / R
            js = (i - pos["i"]) * 7/5 * SWAP_J * pos["e"] / R
            if pos["dir"] == 1:
                if l.iloc[i] <= pos["e"] - R: trades.append(-1.0 - fr - js); pos = None
                elif h.iloc[i] >= pos["e"] + 1.5*R: trades.append(1.5 - fr - js); pos = None
                elif not haussier: trades.append((c.iloc[i]-pos["e"])/R - fr - js); pos = None
            else:
                if h.iloc[i] >= pos["e"] + R: trades.append(-1.0 - fr - js); pos = None
                elif l.iloc[i] <= pos["e"] - 1.5*R: trades.append(1.5 - fr - js); pos = None
                elif haussier: trades.append((pos["e"]-c.iloc[i])/R - fr - js); pos = None
        if pos is None:
            if haussier and e20.iloc[i-1] <= e50.iloc[i-1] and sens in ("L", "LS"):
                pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=1, i=i)
            elif not haussier and e20.iloc[i-1] >= e50.iloc[i-1] and sens in ("S", "LS"):
                pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=-1, i=i)
    return trades

def donch_2sens(sens):
    h20 = h.rolling(20).max().shift(1); b10 = l.rolling(10).min().shift(1)
    b20 = l.rolling(20).min().shift(1); h10 = h.rolling(10).max().shift(1)
    trades, pos = [], None
    for i in range(25, len(c)):
        if pos:
            R = pos["R"]; fr = FRAIS_RT * pos["e"] / R
            js = (i - pos["i"]) * 7/5 * SWAP_J * pos["e"] / R
            if pos["dir"] == 1:
                pos["s"] = max(pos["s"], b10.iloc[i])
                if l.iloc[i] <= pos["s"]: trades.append((pos["s"]-pos["e"])/R - fr - js); pos = None
                elif c.iloc[i] < b10.iloc[i]: trades.append((c.iloc[i]-pos["e"])/R - fr - js); pos = None
            else:
                pos["s"] = min(pos["s"], h10.iloc[i])
                if h.iloc[i] >= pos["s"]: trades.append((pos["e"]-pos["s"])/R - fr - js); pos = None
                elif c.iloc[i] > h10.iloc[i]: trades.append((pos["e"]-c.iloc[i])/R - fr - js); pos = None
        if pos is None:
            if c.iloc[i] > h20.iloc[i] and sens in ("L", "LS"):
                R = c.iloc[i] - b10.iloc[i]
                if R > 0: pos = dict(e=c.iloc[i], s=b10.iloc[i], R=R, dir=1, i=i)
            elif c.iloc[i] < b20.iloc[i] and sens in ("S", "LS"):
                R = h10.iloc[i] - c.iloc[i]
                if R > 0: pos = dict(e=c.iloc[i], s=h10.iloc[i], R=R, dir=-1, i=i)
    return trades

def fib_pullback(sens_long=True):
    trades, pos = [], None
    lb = 10
    for i in range(30, len(c)):
        if pos:
            R = pos["R"]; fr = FRAIS_RT * pos["e"] / R
            js = (i - pos["i"]) * 7/5 * SWAP_J * pos["e"] / R
            if pos["dir"] == 1:
                if l.iloc[i] <= pos["e"] - R: trades.append(-1.0 - fr - js); pos = None
                elif h.iloc[i] >= pos["e"] + 2*R: trades.append(2.0 - fr - js); pos = None
            else:
                if h.iloc[i] >= pos["e"] + R: trades.append(-1.0 - fr - js); pos = None
                elif l.iloc[i] <= pos["e"] - 2*R: trades.append(2.0 - fr - js); pos = None
        if pos is not None: continue
        wh, wl = h.iloc[i-lb:i], l.iloc[i-lb:i]
        hi_i, lo_i = wh.values.argmax(), wl.values.argmin()
        span = wh.iloc[hi_i] - wl.iloc[lo_i]
        if span <= 0: continue
        if lo_i < hi_i and sens_long:   # swing haussier -> achat du repli
            retr = (wh.iloc[hi_i] - c.iloc[i]) / span
            if 0.2 <= retr <= 0.8 and r14.iloc[i-1] < 55 and r14.iloc[i] > r14.iloc[i-1]:
                pos = dict(e=c.iloc[i], R=3*atr.iloc[i], dir=1, i=i)
        elif lo_i > hi_i and not sens_long:  # swing baissier -> vente du rebond
            retr = (c.iloc[i] - wl.iloc[lo_i]) / span
            if 0.2 <= retr <= 0.8 and r14.iloc[i-1] > 45 and r14.iloc[i] < r14.iloc[i-1]:
                pos = dict(e=c.iloc[i], R=3*atr.iloc[i], dir=-1, i=i)
    return trades

print("  EMA 20/50 achat seul       :", bilan(ema_2sens("L")))
print("  EMA 20/50 les deux sens    :", bilan(ema_2sens("LS")))
print("  Donchian 20/10 achat seul  :", bilan(donch_2sens("L")))
print("  Donchian 20/10 deux sens   :", bilan(donch_2sens("LS")))
print("  fib+RSI achat des replis   :", bilan(fib_pullback(True)))
print("  fib+RSI vente des rebonds  :", bilan(fib_pullback(False)))

