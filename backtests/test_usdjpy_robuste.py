# -*- coding: utf-8 -*-
"""USDJPY EMA deux sens : parametres voisins + couche macro BIS (biais USD-JPY,
decale 2 mois). Le candidat de reference : EMA 20/50 deux sens, +14.4 R."""
import sys, requests, pandas as pd, numpy as np

sys.path.insert(0, r"C:\Users\jplou\Downloads\oanda-macro-bot")
from bot.config import load_config
from bot.macro import scores_history

cfg = load_config(require_oanda=False)
scores, _ = scores_history(cfg)
scores = scores.shift(2)
biais_m = (scores["USD"] - scores["JPY"]).dropna()

r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/USDJPY=X",
                 params={"range": "10y", "interval": "1d"},
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
r.raise_for_status()
d = r.json()["chart"]["result"][0]
q = d["indicators"]["quote"][0]
df = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s"),
                   "h": q["high"], "l": q["low"], "c": q["close"]}).dropna().set_index("t")
df.index = df.index.normalize()
c, h, l = df["c"], df["h"], df["l"]

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()
tr = np.maximum(h - l, np.maximum((h - c.shift()).abs(), (l - c.shift()).abs()))
atr = wilder(tr, 14)
biais_j = biais_m.reindex(df.index, method="ffill")
FRAIS_RT, SWAP_L, SWAP_S = 0.00006, +0.00005, -0.00010

def bilan(trades):
    t = np.array(trades)
    if len(t) == 0: return "0 trade"
    pf = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else 99.0
    m1, m2 = t[:len(t)//2].sum(), t[len(t)//2:].sum()
    return f"{len(t):>4} tr | {(t>0).mean()*100:>3.0f}% | total {t.sum():>+6.1f} R | PF {pf:4.2f} | moities {m1:+.1f}/{m2:+.1f}"

def ema_2s(rapide=20, lent=50, seuil_macro=None, tp=1.5):
    er = c.ewm(span=rapide, adjust=False).mean(); el = c.ewm(span=lent, adjust=False).mean()
    trades, pos = [], None
    for i in range(lent + 10, len(c)):
        haussier = er.iloc[i] > el.iloc[i]
        if pos:
            R = pos["R"]; fr = FRAIS_RT * pos["e"] / R
            sw = SWAP_L if pos["dir"] == 1 else SWAP_S
            ct = fr - (i - pos["i"]) * 7/5 * sw * pos["e"] / R
            if pos["dir"] == 1:
                if l.iloc[i] <= pos["e"] - R: trades.append(-1.0 - ct); pos = None
                elif h.iloc[i] >= pos["e"] + tp*R: trades.append(tp - ct); pos = None
                elif not haussier: trades.append((c.iloc[i]-pos["e"])/R - ct); pos = None
            else:
                if h.iloc[i] >= pos["e"] + R: trades.append(-1.0 - ct); pos = None
                elif l.iloc[i] <= pos["e"] - tp*R: trades.append(tp - ct); pos = None
                elif haussier: trades.append((pos["e"]-c.iloc[i])/R - ct); pos = None
        if pos is None:
            croise_h = haussier and er.iloc[i-1] <= el.iloc[i-1]
            croise_b = (not haussier) and er.iloc[i-1] >= el.iloc[i-1]
            if seuil_macro is not None:
                b = biais_j.iloc[i]
                if np.isnan(b): continue
                if croise_h and b > seuil_macro: pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=1, i=i)
                elif croise_b and b < -seuil_macro: pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=-1, i=i)
            else:
                if croise_h: pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=1, i=i)
                elif croise_b: pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=-1, i=i)
    return trades

print("--- Parametres voisins (deux sens, reference 20/50 = +14.4 R) ---")
for rp, lt in ((10, 40), (15, 45), (20, 50), (25, 55), (30, 60)):
    print(f"  EMA {rp}/{lt} :", bilan(ema_2s(rp, lt)))
print("\n--- TP voisins (20/50 deux sens, TP en R) ---")
for tpv in (1.0, 1.5, 2.0, 3.0, 99.0):
    et = "sans TP" if tpv == 99.0 else f"TP {tpv:.1f}R"
    print(f"  {et:<8} :", bilan(ema_2s(20, 50, None, tpv)))
print("\n--- Couche macro BIS (filtre directionnel, seuils voisins) ---")
for s in (0.0, 0.25, 0.5, 0.75):
    print(f"  seuil {s:4.2f} :", bilan(ema_2s(20, 50, s)))

