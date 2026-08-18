# -*- coding: utf-8 -*-
"""Entrer DES QUE la nouvelle sort (donnees H1, 2 ans, ~75 annonces US majeures).
Entree a la cloture de la bougie H1 qui contient l'annonce (on a donc vu
~30-60 min de reaction). Deux variantes :
  - MOMENTUM : dans le sens de la bougie d'annonce
  - FADE : contre la bougie d'annonce
Stop 2xATR(H1), TP 3xATR (=1.5R), sortie forcee apres 24 h.
Annonces : NFP (1er vendredi 8h30 NY), CPI (le 12 -> jour ouvrable, 8h30 NY),
FOMC (8/an, ~14h00 NY). Heures converties NY->UTC avec heure d'ete."""
import requests, pandas as pd, numpy as np
from zoneinfo import ZoneInfo

NY, UTC = ZoneInfo("America/New_York"), ZoneInfo("UTC")

def fetch_h1(sym):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"range": "730d", "interval": "1h"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    df = pd.DataFrame({"ts": d["timestamp"], "o": q["open"], "h": q["high"],
                       "l": q["low"], "c": q["close"]}).dropna()
    df["t"] = pd.to_datetime(df["ts"], unit="s", utc=True)
    return df.set_index("t").drop(columns="ts")

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()

def premier_vendredi(an, mois):
    d = pd.Timestamp(an, mois, 1)
    return d + pd.Timedelta(days=(4 - d.dayofweek) % 7)

def jour_ouvrable(d):
    while d.dayofweek >= 5: d += pd.Timedelta(days=1)
    return d

evenements = []
for an in (2024, 2025, 2026):
    for mois in range(1, 13):
        evenements.append((premier_vendredi(an, mois), 8, 30))
        evenements.append((jour_ouvrable(pd.Timestamp(an, mois, 12)), 8, 30))
    for mois, jour in ((1, 28), (3, 18), (5, 6), (6, 17), (7, 29), (9, 16), (11, 4), (12, 16)):
        d = pd.Timestamp(an, mois, jour)
        evenements.append((d + pd.Timedelta(days=(2 - d.dayofweek) % 7), 14, 0))
ev_utc = sorted(pd.Timestamp(d.year, d.month, d.day, hh, mm, tzinfo=NY).astimezone(UTC)
                for d, hh, mm in evenements)

def jour_ouvrable_ts(ts):
    while ts.dayofweek >= 5: ts += pd.Timedelta(days=1)
    return ts

MARCHES = {
    "Or":      ("GC=F",    0.0001,  -0.000273),
    "Nasdaq":  ("NQ=F",    0.00003, -0.000213),
    "Petrole": ("CL=F",    0.00045, +0.000051),
    "BTC":     ("BTC-USD", 0.0004,  -0.000833),
}

def bilan(trades):
    t = np.array(trades)
    if len(t) == 0: return "0 trade"
    pf = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else 99.0
    m1, m2 = t[:len(t)//2].sum(), t[len(t)//2:].sum()
    return f"{len(t):>3} tr | {(t>0).mean()*100:>3.0f}% | total {t.sum():>+6.1f} R | PF {pf:4.2f} | moities {m1:+.1f}/{m2:+.1f}"

def tester(df, frais, swap, mode):
    c, h, l, o = df["c"], df["h"], df["l"], df["o"]
    tr = np.maximum(h - l, np.maximum((h - c.shift()).abs(), (l - c.shift()).abs()))
    atr = wilder(tr, 14)
    idx = df.index
    trades = []
    for ev in ev_utc:
        pos_apres = idx.searchsorted(ev)
        if pos_apres == 0 or pos_apres >= len(idx): continue
        i = pos_apres - 1 if idx[pos_apres - 1] <= ev else pos_apres
        if idx[i] + pd.Timedelta(hours=1) < ev: i = pos_apres
        if i + 26 >= len(idx): continue
        bougie = c.iloc[i] - o.iloc[i]
        if bougie == 0 or np.isnan(bougie): continue
        sens = np.sign(bougie) * (1 if mode == "momentum" else -1)
        e = c.iloc[i]; R = 2 * atr.iloc[i]
        if R <= 0 or np.isnan(R): continue
        stop, tp = e - sens * R, e + sens * 1.5 * R
        fr = 2 * frais * e / R
        res = None
        for j in range(i + 1, min(i + 25, len(idx))):
            if sens > 0:
                if l.iloc[j] <= stop: res = -1.0; break
                if h.iloc[j] >= tp: res = 1.5; break
            else:
                if h.iloc[j] >= stop: res = -1.0; break
                if l.iloc[j] <= tp: res = 1.5; break
        if res is None: res = sens * (c.iloc[j] - e) / R
        trades.append(res - fr + swap * e / R / 24 * (j - i))
    return trades

donnees = {nom: fetch_h1(sym) for nom, (sym, _, _) in MARCHES.items()}
vraies = list(ev_utc)

for etiquette, decalage in (("VRAIES annonces", 0), ("CONTROLE : fausses annonces (+7 jours)", 7)):
    ev_utc = [jour_ouvrable_ts(e + pd.Timedelta(days=decalage)) for e in vraies]
    for mode in (("momentum", "fade") if decalage == 0 else ("fade",)):
        print(f"=== {etiquette} — {mode.upper()} (stop 2xATR, TP 1.5R, max 24 h) ===")
        tous = []
        for nom, (sym, frais, swap) in MARCHES.items():
            t = tester(donnees[nom], frais, swap, mode)
            tous += t
            print(f"  {nom:<8} :", bilan(t))
        print("  PORTEFEUILLE :", bilan(tous))
        print()
