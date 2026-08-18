# -*- coding: utf-8 -*-
"""GBPUSD + couche macro BIS (scores par devise du pipeline oanda-macro-bot).
Biais = score(GBP) - score(USD), decale de 2 mois (retard de publication).
Teste : EMA 20/50 deux sens filtre par le biais, EMA achat seul + biais,
macro seul (position tenue tant que le biais tient), et parametres voisins."""
import sys, requests, pandas as pd, numpy as np

sys.path.insert(0, r"C:\Users\jplou\Downloads\oanda-macro-bot")
from bot.config import load_config
from bot.macro import scores_history

cfg = load_config(require_oanda=False)
scores, _ = scores_history(cfg)
scores = scores.shift(2)  # retard de publication : on ne connait le mois M qu'en M+2
biais_m = (scores["GBP"] - scores["USD"]).dropna()
print(f"Scores BIS : {len(scores)} mois, devises {list(scores.columns)}")
print(f"Biais GBP-USD dispo : {biais_m.index[0].date()} -> {biais_m.index[-1].date()}")

r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/GBPUSD=X",
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
# biais mensuel projete sur chaque jour (valeur du dernier mois connu)
biais_j = biais_m.reindex(df.index, method="ffill")
FRAIS_RT, SWAP_J = 0.00012, 0.00005

def bilan(trades):
    t = np.array(trades)
    if len(t) == 0: return "0 trade"
    pf = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else 99.0
    m1, m2 = t[:len(t)//2].sum(), t[len(t)//2:].sum()
    return f"{len(t):>4} tr | {(t>0).mean()*100:>3.0f}% | total {t.sum():>+6.1f} R | PF {pf:4.2f} | moities {m1:+.1f}/{m2:+.1f}"

def ema_macro(seuil, rapide=20, lent=50, mode="filtre2s"):
    """mode filtre2s : croisement EMA dans le sens du biais macro seulement.
    mode achat : achat seul, autorise si biais > -seuil (pas contre-vent)."""
    er = c.ewm(span=rapide, adjust=False).mean(); el = c.ewm(span=lent, adjust=False).mean()
    trades, pos = [], None
    for i in range(lent + 10, len(c)):
        b = biais_j.iloc[i]
        if np.isnan(b): continue
        haussier = er.iloc[i] > el.iloc[i]
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
            croise_h = haussier and er.iloc[i-1] <= el.iloc[i-1]
            croise_b = (not haussier) and er.iloc[i-1] >= el.iloc[i-1]
            if mode == "filtre2s":
                if croise_h and b > seuil: pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=1, i=i)
                elif croise_b and b < -seuil: pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=-1, i=i)
            else:
                if croise_h and b > -seuil: pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=1, i=i)
    return trades

def macro_seul(seuil):
    """Position tenue tant que le biais depasse le seuil (stop 2xATR suiveur simple)."""
    trades, pos = [], None
    for i in range(20, len(c)):
        b = biais_j.iloc[i]
        if np.isnan(b): continue
        if pos:
            R = pos["R"]; fr = FRAIS_RT * pos["e"] / R
            js = (i - pos["i"]) * 7/5 * SWAP_J * pos["e"] / R
            if pos["dir"] == 1:
                pos["s"] = max(pos["s"], c.iloc[i] - 2*atr.iloc[i])
                if l.iloc[i] <= pos["s"]: trades.append((pos["s"]-pos["e"])/R - fr - js); pos = None
                elif b < seuil: trades.append((c.iloc[i]-pos["e"])/R - fr - js); pos = None
            else:
                pos["s"] = min(pos["s"], c.iloc[i] + 2*atr.iloc[i])
                if h.iloc[i] >= pos["s"]: trades.append((pos["e"]-pos["s"])/R - fr - js); pos = None
                elif b > -seuil: trades.append((pos["e"]-c.iloc[i])/R - fr - js); pos = None
        if pos is None:
            if b > seuil: pos = dict(e=c.iloc[i], s=c.iloc[i]-2*atr.iloc[i], R=2*atr.iloc[i], dir=1, i=i)
            elif b < -seuil: pos = dict(e=c.iloc[i], s=c.iloc[i]+2*atr.iloc[i], R=2*atr.iloc[i], dir=-1, i=i)
    return trades

print("\n--- EMA 20/50 deux sens, filtre par biais macro (seuil = voisins) ---")
for s in (0.25, 0.5, 0.75):
    print(f"  seuil {s:4.2f} :", bilan(ema_macro(s)))
print("\n--- EMA achat seul + biais pas contre-vent ---")
for s in (0.25, 0.5):
    print(f"  seuil {s:4.2f} :", bilan(ema_macro(s, mode="achat")))
print("\n--- Macro seul (tenir tant que le biais tient, stop suiveur 2xATR) ---")
for s in (0.25, 0.5, 0.75):
    print(f"  seuil {s:4.2f} :", bilan(macro_seul(s)))
print("\n--- EMA sans macro, parametres voisins (achat seul, reference +8.6 R) ---")
for rp, lt in ((10, 40), (15, 45), (25, 55), (30, 60)):
    er = c.ewm(span=rp, adjust=False).mean(); el = c.ewm(span=lt, adjust=False).mean()
    trades, pos = [], None
    for i in range(lt + 10, len(c)):
        haussier = er.iloc[i] > el.iloc[i]
        if pos:
            R = pos["R"]; fr = FRAIS_RT * pos["e"] / R
            js = (i - pos["i"]) * 7/5 * SWAP_J * pos["e"] / R
            if l.iloc[i] <= pos["e"] - R: trades.append(-1.0 - fr - js); pos = None
            elif h.iloc[i] >= pos["e"] + 1.5*R: trades.append(1.5 - fr - js); pos = None
            elif not haussier: trades.append((c.iloc[i]-pos["e"])/R - fr - js); pos = None
        if pos is None and haussier and er.iloc[i-1] <= el.iloc[i-1]:
            pos = dict(e=c.iloc[i], R=2*atr.iloc[i], dir=1, i=i)
    print(f"  EMA {rp}/{lt} :", bilan(trades))
