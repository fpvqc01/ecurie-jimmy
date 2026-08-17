# -*- coding: utf-8 -*-
"""Cassure de range H4 sur BTC (long-only, style turtle) vs bot actuel (EMA H1).
Entree : cloture H4 au-dessus du plus haut des N bougies precedentes.
Sortie : cloture sous le plus bas des M bougies precedentes.
Frais 0.06%/cote. Donnees : 2 ans de 1h Yahoo (resample H4). Robustesse :
plusieurs (N, M) + resultats par moitie de periode."""
import requests, pandas as pd, numpy as np

FRAIS = 0.0006

r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD",
                 params={"range": "730d", "interval": "1h"},
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
r.raise_for_status()
d = r.json()["chart"]["result"][0]
q = d["indicators"]["quote"][0]
h1 = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s"),
                   "o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]}).dropna().set_index("t")
h4 = h1.resample("4h").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
print(f"Donnees : {h4.index[0].date()} -> {h4.index[-1].date()} ({len(h4)} bougies H4)")

def stats(rs, annees):
    eq = (1 + rs).cumprod()
    tot = (eq.iloc[-1] - 1) * 100
    cagr = (eq.iloc[-1] ** (1/annees) - 1) * 100
    dd = (eq / eq.cummax() - 1).min() * 100
    return tot, cagr, dd

def breakout(df, n_entree, m_sortie, moitie=None):
    haut = df["h"].rolling(n_entree).max().shift(1)
    bas = df["l"].rolling(m_sortie).min().shift(1)
    pos = pd.Series(np.nan, index=df.index)
    pos[df["c"] > haut] = 1.0
    pos[df["c"] < bas] = 0.0
    pos = pos.ffill().fillna(0.0).shift(1).fillna(0.0)
    rend = df["c"].pct_change().fillna(0.0)
    if moitie == 1:
        pos, rend = pos.iloc[:len(pos)//2], rend.iloc[:len(rend)//2]
    elif moitie == 2:
        pos, rend = pos.iloc[len(pos)//2:], rend.iloc[len(rend)//2:]
    frais = pos.diff().abs().fillna(0.0) * FRAIS
    rs = pos * rend - frais
    nb = int((pos.diff().abs() > 0).sum())
    annees = len(rend) * 4 / 24 / 365.25
    return stats(rs, annees), nb

def ema_h1(df, moitie=None):
    e20 = df["c"].ewm(span=20, adjust=False).mean()
    e50 = df["c"].ewm(span=50, adjust=False).mean()
    pos = pd.Series(np.where(e20 > e50, 1.0, 0.0), index=df.index).shift(1).fillna(0.0)
    rend = df["c"].pct_change().fillna(0.0)
    if moitie == 1:
        pos, rend = pos.iloc[:len(pos)//2], rend.iloc[:len(rend)//2]
    elif moitie == 2:
        pos, rend = pos.iloc[len(pos)//2:], rend.iloc[len(rend)//2:]
    frais = pos.diff().abs().fillna(0.0) * FRAIS
    rs = pos * rend - frais
    nb = int((pos.diff().abs() > 0).sum())
    annees = len(rend) / 24 / 365.25
    return stats(rs, annees), nb

print(f"\n{'Strategie':<26} | {'Trades':>6} | {'Total 2 ans':>11} | {'CAGR':>7} | {'Pire DD':>7}")
print("-" * 70)
(s, nb) = ema_h1(h1)
print(f"{'EMA 20/50 H1 (bot actuel)':<26} | {nb:>6} | {s[0]:>+10.1f}% | {s[1]:>+6.1f}% | {s[2]:>6.0f}%")
for (n, m) in [(20, 10), (30, 15), (40, 20), (55, 20)]:
    (s, nb) = breakout(h4, n, m)
    print(f"{f'Cassure H4 {n}/{m}':<26} | {nb:>6} | {s[0]:>+10.1f}% | {s[1]:>+6.1f}% | {s[2]:>6.0f}%")

print("\n--- Stabilite par moitie de periode (1re moitie / 2e moitie, total %) ---")
(s1, _), (s2, _) = ema_h1(h1, 1), ema_h1(h1, 2)
print(f"{'EMA 20/50 H1':<26} : {s1[0]:+.1f}% / {s2[0]:+.1f}%")
for (n, m) in [(20, 10), (30, 15), (40, 20), (55, 20)]:
    (s1, _), (s2, _) = breakout(h4, n, m, 1), breakout(h4, n, m, 2)
    print(f"{f'Cassure H4 {n}/{m}':<26} : {s1[0]:+.1f}% / {s2[0]:+.1f}%")
