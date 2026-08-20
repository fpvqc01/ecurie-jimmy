# -*- coding: utf-8 -*-
"""DEUX ETUDES (20 aout 2026) :
  1. DUEL des generations sur 10 ANS (au lieu de 5) — stabilite sur deux
     moities de 5 ans.
  2. EPREUVE DES CRISES : les strategies de l'ecurie appliquees aux
     periodes de crise reelles, sur le maximum d'historique disponible
     par marche (l'or et les indices remontent loin ; le BTC non).
     Marches de substitution pour l'histoire longue :
       ^GSPC (S&P 500, depuis 1927)  -> proxy du robot Nasdaq (fib+RSI)
       GC=F / ^XAU                    -> or
       CL=F (petrole depuis 1983)     -> petrole
     Crises testees : 1929, 1987, 2000-2002, 2008, 2011, 2015, 2018,
     COVID 2020, 2022 inflation — celles couvertes par les donnees.
NOTE HONNETE : le BTC n'existe pas avant 2014 ; aucune strategie BTC ne
peut etre testee sur les crises anciennes."""
import os, requests, pandas as pd, numpy as np

import time
def _tranche(sym, p1, p2):
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/" + sym,
                     params={"period1": p1, "period2": p2, "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    if "timestamp" not in d: return None
    q = d["indicators"]["quote"][0]
    df = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s").normalize(),
                       "o": q.get("open"), "h": q["high"], "l": q["low"], "c": q["close"]}
                      ).dropna(subset=["h", "l", "c"]).drop_duplicates("t").set_index("t")
    df["o"] = df["o"].fillna(df["c"])
    return df

def fetch(sym, rng="max"):
    """Yahoo renvoie du mensuel sur range=max : on demande des tranches de
    10 ans en period1/period2 pour obtenir du VRAI journalier."""
    morceaux = []
    debut = pd.Timestamp("1927-01-01")
    fin = pd.Timestamp.today()
    cur = debut
    while cur < fin:
        suivant = min(cur + pd.DateOffset(years=10), fin)
        try:
            d = _tranche(sym, int(cur.timestamp()), int(suivant.timestamp()))
            if d is not None and len(d): morceaux.append(d)
        except Exception:
            pass
        cur = suivant
        time.sleep(0.2)
    if not morceaux: raise RuntimeError("aucune donnee")
    out = pd.concat(morceaux)
    return out[~out.index.duplicated(keep="first")].sort_index()

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()

def indicateurs(df):
    c, h, l = df["c"], df["h"], df["l"]
    tr = np.maximum(h-l, np.maximum((h-c.shift()).abs(), (l-c.shift()).abs()))
    dd = c.diff()
    return dict(
        atr=wilder(tr, 14),
        rsi=100 - 100/(1 + wilder(dd.clip(lower=0), 14) / wilder(-dd.clip(upper=0), 14).replace(0, np.nan)),
        e20=c.ewm(span=20, adjust=False).mean(),
        e50=c.ewm(span=50, adjust=False).mean(),
    )

def strat_fib(df, ind, i0, i1, lookback=10, fiblo=0.2, fibhi=0.8, rsis=55, mult=3.0, tpr=1.5):
    """repli fibonacci + RSI (robots or / nasdaq), retourne les R"""
    c, h, l = df["c"], df["h"], df["l"]
    out, pos = [], None
    for i in range(max(i0, 120), i1):
        if pos:
            R = pos["R"]
            if l.iloc[i] <= pos["e"] - R: out.append(-1.0); pos = None
            elif h.iloc[i] >= pos["e"] + tpr*R: out.append(tpr); pos = None
            continue
        fh, fl = h.iloc[i-lookback:i], l.iloc[i-lookback:i]
        hi_i, lo_i = fh.values.argmax(), fl.values.argmin()
        if lo_i >= hi_i: continue
        span = fh.iloc[hi_i] - fl.iloc[lo_i]
        if span <= 0: continue
        retr = (fh.iloc[hi_i] - c.iloc[i]) / span
        if not (fiblo <= retr <= fibhi): continue
        if not (ind["rsi"].iloc[i-1] < rsis and ind["rsi"].iloc[i] > ind["rsi"].iloc[i-1]): continue
        R = mult * ind["atr"].iloc[i]
        if R <= 0 or np.isnan(R): continue
        pos = dict(e=c.iloc[i], R=R)
    return out

def strat_donch(df, ind, i0, i1, pe=20, ps=10, pyramide=False):
    """cassure Donchian avec stop suiveur, option pyramidage 3 unites"""
    c, h, l = df["c"], df["h"], df["l"]
    hh = h.rolling(pe).max().shift(1); bb = l.rolling(ps).min().shift(1)
    out, pos = [], None
    for i in range(max(i0, 120), i1):
        if pos:
            a = ind["atr"].iloc[i]
            pos["s"] = max(pos["s"], bb.iloc[i])
            if pyramide and pos["u"] < 3 and a > 0 and h.iloc[i] >= pos["prochain"]:
                pos["u"] += 1
                pos["n"] += 1
                pos["prochain"] += 0.5 * a
                pos["turtle"] = max(pos["turtle"], max(pos["prochain"] - 0.5*a, 0) - 2.0*a)
            niveau = max(pos["s"], pos["turtle"]) if pyramide else pos["s"]
            if l.iloc[i] <= niveau:
                out.append(pos["n"] * (niveau - pos["e"]) / pos["R"]); pos = None
            continue
        if c.iloc[i] > hh.iloc[i]:
            R = c.iloc[i] - bb.iloc[i]
            a = ind["atr"].iloc[i]
            if R <= 0 or np.isnan(a) or a <= 0: continue
            pos = dict(e=c.iloc[i], s=bb.iloc[i], R=R, n=1, u=1,
                       prochain=c.iloc[i] + 0.5*a, turtle=-1e9)
    return out

def bilan(R):
    R = np.array(R)
    if len(R) == 0: return "aucun trade"
    pf = R[R > 0].sum() / abs(R[R < 0].sum()) if (R < 0).any() else 99
    return "%3d tr | %+7.1f R | PF %5.2f | %3.0f%% gagn." % (len(R), R.sum(), pf, (R > 0).mean()*100)

# =========================================================
print("=== TELECHARGEMENT (historique maximal) ===")
marches = {}
for nom, sym in (("S&P 500", "^GSPC"), ("Or", "GC=F"), ("Nasdaq", "^IXIC"),
                 ("Petrole", "CL=F"), ("BTC", "BTC-USD")):
    try:
        df = fetch(sym)
        marches[nom] = df
        print("  %-10s %s -> %s  (%d jours, %.0f ans)" %
              (nom, df.index[0].date(), df.index[-1].date(), len(df),
               (df.index[-1]-df.index[0]).days/365.25))
    except Exception as e:
        print("  %-10s echec : %s" % (nom, e))

# =========================================================
CRISES = [
    ("Krach de 1929 + Depression", "1929-09-01", "1932-07-01"),
    ("Choc petrolier 1973-74",     "1973-10-01", "1975-01-01"),
    ("Lundi noir 1987",            "1987-08-01", "1988-02-01"),
    ("Bulle techno 2000-2002",     "2000-03-01", "2002-10-31"),
    ("Crise financiere 2008",      "2007-10-01", "2009-04-01"),
    ("Crise de la dette 2011",     "2011-05-01", "2011-12-31"),
    ("Krach petrolier 2014-16",    "2014-06-01", "2016-03-01"),
    ("Correction 2018",            "2018-09-01", "2019-01-31"),
    ("COVID 2020",                 "2020-02-01", "2020-05-01"),
    ("Inflation / taux 2022",      "2022-01-01", "2022-12-31"),
    ("Krach crypto 2022",          "2021-11-01", "2022-12-31"),
]

print()
print("=== EPREUVE DES CRISES (strategies de l'ecurie, R par crise) ===")
print("%-28s | %-10s | %s" % ("Crise", "Marche", "Resultat de la strategie"))
print("-" * 92)
total_par_crise = {}
for nom_crise, deb, fin in CRISES:
    d0, d1 = pd.Timestamp(deb), pd.Timestamp(fin)
    lignes = []
    for nom_m, df in marches.items():
        if df.index[0] > d0 or df.index[-1] < d1: continue
        sous = df[(df.index >= d0 - pd.Timedelta(days=200)) & (df.index <= d1)]
        if len(sous) < 200: continue
        ind = indicateurs(sous)
        i0 = sous.index.searchsorted(d0)
        if nom_m in ("S&P 500", "Nasdaq"):
            R = strat_fib(sous, ind, i0, len(sous), lookback=7, fiblo=0.1, fibhi=0.9,
                          rsis=60, mult=2.0, tpr=1.0)
            etiq = "fib+RSI (nasdaq)"
        elif nom_m == "Or":
            R = strat_fib(sous, ind, i0, len(sous))
            etiq = "fib+RSI (or)"
        else:
            R = strat_donch(sous, ind, i0, len(sous), 20, 10, pyramide=True)
            etiq = "cassure + pyramide"
        if not R: continue
        lignes.append((nom_m, etiq, R))
    if not lignes:
        print("%-28s | %s" % (nom_crise, "pas de donnees disponibles"))
        continue
    tot = []
    for nom_m, etiq, R in lignes:
        print("%-28s | %-10s | %-20s %s" % (nom_crise, nom_m, etiq, bilan(R)))
        tot += R
    total_par_crise[nom_crise] = np.array(tot)
    print("%-28s | %-10s | %s" % ("", "TOTAL", bilan(tot)))
    print("-" * 92)

print()
print("=== BILAN GLOBAL DES CRISES ===")
gagnantes = sum(1 for r in total_par_crise.values() if r.sum() > 0)
print("  crises testees : %d | positives : %d | negatives : %d" %
      (len(total_par_crise), gagnantes, len(total_par_crise)-gagnantes))
tous = np.concatenate(list(total_par_crise.values())) if total_par_crise else np.array([])
if len(tous):
    print("  toutes crises confondues : %s" % bilan(tous))
