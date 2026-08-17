# -*- coding: utf-8 -*-
"""Strategies pétrole issues de la recherche (forums + littérature) :
1. SAISONNALITE : accumulation des raffineries avant la 'driving season'.
   Variantes : long 15 fev->31 mai / 1 dec->31 mai / 1 fev->30 juin
2. IBS (Internal Bar Strength) : achat quand close proche du bas du jour
   (IBS<0.2) en tendance (>SMA200), sortie IBS>0.8  [classique des forums]
3. COMBO : cassure Donchian 20/10 permise SEULEMENT en saison favorable
Frais FTMO exacts (spread 0.09% RT, swap long +0.0051%/j credit)."""
import requests, pandas as pd, numpy as np

r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/CL=F",
                 params={"range": "10y", "interval": "1d"},
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
r.raise_for_status()
d = r.json()["chart"]["result"][0]
q = d["indicators"]["quote"][0]
df = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s"),
                   "h": q["high"], "l": q["low"], "c": q["close"]}).dropna().set_index("t")
c = df["c"]

def evaluer(pos):
    pos = pos.shift(1).fillna(0.0)
    rend = c.pct_change().fillna(0.0)
    frais = pos.diff().abs().fillna(0.0) * 0.00045
    swap = pos.clip(lower=0) * 0.000051 * 7/5
    rs = pos * rend + swap - frais
    eq = (1 + rs).cumprod()
    annees = len(rend) / 252
    cagr = (eq.iloc[-1] ** (1/annees) - 1) * 100
    dd = (eq / eq.cummax() - 1).min() * 100
    sh = (rs.mean() * 252) / (rs.std() * np.sqrt(252)) if rs.std() > 0 else 0
    nb = int((pos.diff().abs() > 0).sum())
    # stabilite par moitie
    mid = len(rs)//2
    e1, e2 = (1+rs.iloc[:mid]).cumprod().iloc[-1], (1+rs.iloc[mid:]).cumprod().iloc[-1]
    return f"CAGR {cagr:>+6.1f}% | DD {dd:>4.0f}% | Sharpe {sh:>5.2f} | {nb:>3} tr | moities: {(e1-1)*100:+.0f}%/{(e2-1)*100:+.0f}%"

def saison(debut_m, debut_j, fin_m, fin_j):
    md = df.index.month * 100 + df.index.day
    a, b = debut_m * 100 + debut_j, fin_m * 100 + fin_j
    dedans = (md >= a) & (md <= b) if a < b else (md >= a) | (md <= b)
    return pd.Series(np.where(dedans, 1.0, 0.0), index=c.index)

sma200 = c.rolling(200).mean()
ibs = (c - df["l"]) / (df["h"] - df["l"]).replace(0, np.nan)
p_ibs = pd.Series(np.nan, index=c.index)
p_ibs[(ibs < 0.2) & (c > sma200)] = 1.0
p_ibs[ibs > 0.8] = 0.0
p_ibs = p_ibs.ffill().fillna(0.0)

haut = df["h"].rolling(20).max().shift(1)
bas = df["l"].rolling(10).min().shift(1)
def donch_saison(s):
    p = pd.Series(np.nan, index=c.index)
    p[(c > haut) & (s > 0)] = 1.0
    p[c < bas] = 0.0
    return p.ffill().fillna(0.0)

s1, s2, s3 = saison(2,15,5,31), saison(12,1,5,31), saison(2,1,6,30)
print("1a. Saison 15 fev -> 31 mai        :", evaluer(s1))
print("1b. Saison 1 dec -> 31 mai         :", evaluer(s2))
print("1c. Saison 1 fev -> 30 juin        :", evaluer(s3))
print("2.  IBS<0.2 + tendance             :", evaluer(p_ibs))
print("3a. Donchian 20/10 en saison (dec-mai) :", evaluer(donch_saison(s2)))
print("3b. Donchian 20/10 (reference)     :", evaluer(donch_saison(pd.Series(1.0, index=c.index))))
