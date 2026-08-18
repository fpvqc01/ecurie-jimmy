# -*- coding: utf-8 -*-
"""Ecurie Jimmy vs « proxy Simons » : les strategies de style Renaissance
documentees publiquement (stat-arb / retour a la moyenne 1-5 jours, paires),
implementees a l'echelle retail sur les marches de Jimmy avec les frais FTMO reels.
NB : la vraie strategie Medallion est secrete — ceci teste la FAMILLE de
strategies, pas le fonds. Sizing identique aux robots : risque 0.75% par
trade (2xATR), mark-to-market quotidien.
Frais par cote (etablis dans le projet) : BTC 0.04%+swap -0.083%/j,
or 0.01%+swap -0.027%/j, nasdaq 0.003%+swap -0.021%/j, petrole 0.045%+swap +0.005%/j,
argent 0.07%+swap -0.027%/j."""
import requests, pandas as pd, numpy as np

def fetch(sym, rng="10y"):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"range": rng, "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    return pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s").normalize(),
                         "h": q["high"], "l": q["low"], "c": q["close"]}
                        ).dropna().drop_duplicates("t").set_index("t")

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()
def atrp(df, n=14):
    tr = np.maximum(df["h"]-df["l"], np.maximum((df["h"]-df["c"].shift()).abs(),
                                                (df["l"]-df["c"].shift()).abs()))
    return (wilder(tr, n) / df["c"])

MARCHES = {
    "BTC":     ("BTC-USD", 0.0004,  -0.000833),
    "Or":      ("GC=F",    0.0001,  -0.000273),
    "Nasdaq":  ("NQ=F",    0.00003, -0.000213),
    "Petrole": ("CL=F",    0.00045, +0.000051),
}
data = {k: (fetch(sym), frais, swap) for k, (sym, frais, swap) in MARCHES.items()}

def bilan(rends):
    """rends = liste de rendements de trade en % d'equite (sizing 0.75%/2ATR)."""
    t = np.array(rends)
    if len(t) == 0: return "0 trade"
    pf = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else 99.0
    m1, m2 = t[:len(t)//2].sum()*100, t[len(t)//2:].sum()*100
    return (f"{len(t):>5} tr | {(t>0).mean()*100:>3.0f}% | net {t.sum()*100:>+7.1f}% equite"
            f" | PF {pf:4.2f} | moities {m1:+.1f}/{m2:+.1f}")

RISQUE = 0.0075

def mr_zscore(df, frais, swap, fenetre=20, seuil=2.0, tenue=1, deux_sens=True):
    """Retour a la moyenne : z-score du rendement 1 jour ; achat si z<-seuil,
    vente si z>+seuil ; sortie apres `tenue` jours. Style stat-arb classique."""
    c = df["c"]; r1 = c.pct_change()
    z = (r1 - r1.rolling(fenetre).mean()) / r1.rolling(fenetre).std()
    ap = atrp(df); rends = []
    i = fenetre + 2
    while i < len(c) - tenue:
        notional = min(RISQUE / (2*ap.iloc[i]), 2.0)
        if z.iloc[i] < -seuil:
            brut = (c.iloc[i+tenue]/c.iloc[i] - 1)
            rends.append(notional * (brut - 2*frais + swap*tenue)); i += tenue
        elif deux_sens and z.iloc[i] > seuil:
            brut = -(c.iloc[i+tenue]/c.iloc[i] - 1)
            rends.append(notional * (brut - 2*frais + swap*tenue)); i += tenue
        i += 1
    return rends

def mr_5jours(df, frais, swap, seuil=1.5, tenue=3):
    """Renversement 5 jours : z-score du rendement 5 j, achat de la faiblesse."""
    c = df["c"]; r5 = c.pct_change(5)
    z = (r5 - r5.rolling(60).mean()) / r5.rolling(60).std()
    ap = atrp(df); rends = []
    i = 65
    while i < len(c) - tenue:
        notional = min(RISQUE / (2*ap.iloc[i]), 2.0)
        if z.iloc[i] < -seuil:
            brut = (c.iloc[i+tenue]/c.iloc[i] - 1)
            rends.append(notional * (brut - 2*frais + swap*tenue)); i += tenue
        elif z.iloc[i] > seuil:
            brut = -(c.iloc[i+tenue]/c.iloc[i] - 1)
            rends.append(notional * (brut - 2*frais + swap*tenue)); i += tenue
        i += 1
    return rends

print("=== Proxy Simons 1 : stat-arb z-score 1 jour (achat faiblesse / vente force) ===")
tous1 = []
for nom, (df, frais, swap) in data.items():
    r = mr_zscore(df, frais, swap)
    tous1 += r
    print(f"  {nom:<8} :", bilan(r))
print("  PORTEFEUILLE :", bilan(tous1))

print("\n=== Proxy Simons 2 : renversement 5 jours (tenue 3 j) ===")
tous2 = []
for nom, (df, frais, swap) in data.items():
    r = mr_5jours(df, frais, swap)
    tous2 += r
    print(f"  {nom:<8} :", bilan(r))
print("  PORTEFEUILLE :", bilan(tous2))

print("\n=== Proxy Simons 3 : paire or/argent (z-score du ratio, 20 j) ===")
si = fetch("SI=F")
gc = data["Or"][0]
idx = gc.index.intersection(si.index)
ratio = np.log(gc.loc[idx, "c"] / si.loc[idx, "c"])
z = (ratio - ratio.rolling(20).mean()) / ratio.rolling(20).std()
apg, aps = atrp(gc).reindex(idx), atrp(si).reindex(idx)
rends = []
i = 25
vals = ratio.values
while i < len(idx) - 3:
    if abs(z.iloc[i]) > 2.0:
        sens = -np.sign(z.iloc[i])   # ratio trop haut -> vendre or / acheter argent
        brut = sens * (vals[i+3] - vals[i])   # variation du log-ratio
        notional = min(RISQUE / (2*apg.iloc[i]), 2.0)
        # frais des DEUX jambes : or (0.0001) + argent (0.0007) par cote, swaps 3 j
        rends.append(notional * (brut - 2*(0.0001+0.0007) + (-0.000273-0.000273)*3))
        i += 3
    i += 1
print("  Or/Argent :", bilan(rends))

print("\n=== Reference : l'ecurie de Jimmy (5 ans, meme moteur) ===")
print("  CAGR +18.1%/an | Sharpe 1.38 | pire jour -4.02% | creux -6.1%")
print("  (proxys Simons ci-dessus : totaux sur 10 ans, diviser par ~10 pour l'annuel)")
