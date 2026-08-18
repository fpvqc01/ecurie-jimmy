# -*- coding: utf-8 -*-
"""Criblage USDJPY (10 ans journalier) : familles connues + strategies propres
au carry (tendance longue, retour a la moyenne RSI-2 de Connors).
Frais estimes (A CONFIRMER avec les specs MT5 de Jimmy si un candidat passe) :
spread+commission ~0.006% aller-retour ; swap ACHAT +0.005%/j (carry positif,
on est paye), VENTE -0.010%/j (on paie le differentiel)."""
import requests, pandas as pd, numpy as np

r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/USDJPY=X",
                 params={"range": "10y", "interval": "1d"},
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
r.raise_for_status()
d = r.json()["chart"]["result"][0]
q = d["indicators"]["quote"][0]
df = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s"),
                   "h": q["high"], "l": q["low"], "c": q["close"]}).dropna().set_index("t")
c, h, l = df["c"], df["h"], df["l"]
print(f"USDJPY : {df.index[0].date()} -> {df.index[-1].date()}, {c.iloc[0]:.2f} -> {c.iloc[-1]:.2f}")

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()
tr = np.maximum(h - l, np.maximum((h - c.shift()).abs(), (l - c.shift()).abs()))
atr = wilder(tr, 14)
def rsi(s, n):
    dd = s.diff()
    return 100 - 100/(1 + wilder(dd.clip(lower=0), n) / wilder(-dd.clip(upper=0), n).replace(0, np.nan))
r14, r2 = rsi(c, 14), rsi(c, 2)
sma200 = c.rolling(200).mean()
FRAIS_RT, SWAP_L, SWAP_S = 0.00006, +0.00005, -0.00010

def swap_j(dir_): return SWAP_L if dir_ == 1 else SWAP_S

def bilan(trades):
    t = np.array(trades)
    if len(t) == 0: return "0 trade"
    pf = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else 99.0
    m1, m2 = t[:len(t)//2].sum(), t[len(t)//2:].sum()
    return f"{len(t):>4} tr | {(t>0).mean()*100:>3.0f}% | total {t.sum():>+6.1f} R | PF {pf:4.2f} | moities {m1:+.1f}/{m2:+.1f}"

def cout(pos, i):
    R = pos["R"]; fr = FRAIS_RT * pos["e"] / R
    js = (i - pos["i"]) * 7/5 * (-swap_j(pos["dir"])) * pos["e"] / R
    return fr + js   # swap positif = cout negatif (credit)

def ema_x(sens, rapide=20, lent=50):
    er = c.ewm(span=rapide, adjust=False).mean(); el = c.ewm(span=lent, adjust=False).mean()
    trades, pos = [], None
    for i in range(lent + 10, len(c)):
        haussier = er.iloc[i] > el.iloc[i]
        if pos:
            ct = cout(pos, i)
            if pos["dir"] == 1:
                if l.iloc[i] <= pos["e"] - pos["R"]: trades.append(-1.0 - ct); pos = None
                elif h.iloc[i] >= pos["e"] + 1.5*pos["R"]: trades.append(1.5 - ct); pos = None
                elif not haussier: trades.append((c.iloc[i]-pos["e"])/pos["R"] - ct); pos = None
            else:
                if h.iloc[i] >= pos["e"] + pos["R"]: trades.append(-1.0 - ct); pos = None
                elif l.iloc[i] <= pos["e"] - 1.5*pos["R"]: trades.append(1.5 - ct); pos = None
                elif haussier: trades.append((pos["e"]-c.iloc[i])/pos["R"] - ct); pos = None
        if pos is None:
            croise_h = haussier and er.iloc[i-1] <= el.iloc[i-1]
            croise_b = (not haussier) and er.iloc[i-1] >= el.iloc[i-1]
            if croise_h and sens in ("L", "LS"): pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=1, i=i)
            elif croise_b and sens in ("S", "LS"): pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=-1, i=i)
    return trades

def donch_x(sens, pe=20, ps=10):
    hh = h.rolling(pe).max().shift(1); bb = l.rolling(ps).min().shift(1)
    bl = l.rolling(pe).min().shift(1); hs = h.rolling(ps).max().shift(1)
    trades, pos = [], None
    for i in range(pe + 5, len(c)):
        if pos:
            ct = cout(pos, i)
            if pos["dir"] == 1:
                pos["s"] = max(pos["s"], bb.iloc[i])
                if l.iloc[i] <= pos["s"]: trades.append((pos["s"]-pos["e"])/pos["R"] - ct); pos = None
            else:
                pos["s"] = min(pos["s"], hs.iloc[i])
                if h.iloc[i] >= pos["s"]: trades.append((pos["e"]-pos["s"])/pos["R"] - ct); pos = None
        if pos is None:
            if c.iloc[i] > hh.iloc[i] and sens in ("L", "LS"):
                R = c.iloc[i] - bb.iloc[i]
                if R > 0: pos = dict(e=c.iloc[i], s=bb.iloc[i], R=R, dir=1, i=i)
            elif c.iloc[i] < bl.iloc[i] and sens in ("S", "LS"):
                R = hs.iloc[i] - c.iloc[i]
                if R > 0: pos = dict(e=c.iloc[i], s=hs.iloc[i], R=R, dir=-1, i=i)
    return trades

def fib_x(sens_long=True):
    trades, pos = [], None; lb = 10
    for i in range(210, len(c)):
        if pos:
            ct = cout(pos, i)
            if pos["dir"] == 1:
                if l.iloc[i] <= pos["e"] - pos["R"]: trades.append(-1.0 - ct); pos = None
                elif h.iloc[i] >= pos["e"] + 2*pos["R"]: trades.append(2.0 - ct); pos = None
            else:
                if h.iloc[i] >= pos["e"] + pos["R"]: trades.append(-1.0 - ct); pos = None
                elif l.iloc[i] <= pos["e"] - 2*pos["R"]: trades.append(2.0 - ct); pos = None
        if pos is not None: continue
        wh, wl = h.iloc[i-lb:i], l.iloc[i-lb:i]
        hi_i, lo_i = wh.values.argmax(), wl.values.argmin()
        span = wh.iloc[hi_i] - wl.iloc[lo_i]
        if span <= 0: continue
        if lo_i < hi_i and sens_long:
            retr = (wh.iloc[hi_i] - c.iloc[i]) / span
            if 0.2 <= retr <= 0.8 and r14.iloc[i-1] < 55 and r14.iloc[i] > r14.iloc[i-1]:
                pos = dict(e=c.iloc[i], R=3*atr.iloc[i], dir=1, i=i)
        elif lo_i > hi_i and not sens_long:
            retr = (c.iloc[i] - wl.iloc[lo_i]) / span
            if 0.2 <= retr <= 0.8 and r14.iloc[i-1] > 45 and r14.iloc[i] < r14.iloc[i-1]:
                pos = dict(e=c.iloc[i], R=3*atr.iloc[i], dir=-1, i=i)
    return trades

def rsi2_mr(seuil=10, sortie=60, max_j=7):
    """Connors : achat quand RSI(2) < seuil AU-DESSUS de la SMA200, stop 2xATR,
    sortie RSI(2) > sortie ou apres max_j jours. Achat seul (sens du carry)."""
    trades, pos = [], None
    for i in range(210, len(c)):
        if pos:
            ct = cout(pos, i)
            if l.iloc[i] <= pos["e"] - pos["R"]: trades.append(-1.0 - ct); pos = None
            elif r2.iloc[i] > sortie or (i - pos["i"]) >= max_j:
                trades.append((c.iloc[i]-pos["e"])/pos["R"] - ct); pos = None
        if pos is None and c.iloc[i] > sma200.iloc[i] and r2.iloc[i] < seuil:
            pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=1, i=i)
    return trades

def tendance_carry(n=200):
    """Tenir l'achat tant que cloture > SMA n (encaisse le carry), stop 3xATR suiveur."""
    trades, pos = [], None
    sm = c.rolling(n).mean()
    for i in range(n + 10, len(c)):
        if pos:
            ct = cout(pos, i)
            pos["s"] = max(pos["s"], c.iloc[i] - 3*atr.iloc[i])
            if l.iloc[i] <= pos["s"]: trades.append((pos["s"]-pos["e"])/pos["R"] - ct); pos = None
            elif c.iloc[i] < sm.iloc[i]: trades.append((c.iloc[i]-pos["e"])/pos["R"] - ct); pos = None
        if pos is None and c.iloc[i] > sm.iloc[i] and c.iloc[i-1] <= sm.iloc[i-1]:
            pos = dict(e=c.iloc[i], s=c.iloc[i]-3*atr.iloc[i], R=2*atr.iloc[i], dir=1, i=i)
    return trades

print("\n--- Familles connues ---")
print("  EMA 20/50 achat seul      :", bilan(ema_x("L")))
print("  EMA 20/50 deux sens       :", bilan(ema_x("LS")))
print("  Donchian 20/10 achat seul :", bilan(donch_x("L")))
print("  Donchian 20/10 deux sens  :", bilan(donch_x("LS")))
print("  Donchian 55/20 achat seul :", bilan(donch_x("L", 55, 20)))
print("  fib+RSI achat des replis  :", bilan(fib_x(True)))
print("  fib+RSI vente des rebonds :", bilan(fib_x(False)))
print("\n--- Nouvelles strategies (specifiques carry/USDJPY) ---")
print("  RSI-2 <10 >SMA200 (Connors):", bilan(rsi2_mr()))
print("  RSI-2 voisins <5/s70       :", bilan(rsi2_mr(5, 70)))
print("  RSI-2 voisins <15/s55      :", bilan(rsi2_mr(15, 55)))
print("  Tendance carry SMA200      :", bilan(tendance_carry(200)))
print("  Tendance carry SMA150      :", bilan(tendance_carry(150)))
print("  Tendance carry SMA100      :", bilan(tendance_carry(100)))
