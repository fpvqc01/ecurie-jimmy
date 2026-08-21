# -*- coding: utf-8 -*-
"""UNIVERS OANDA (question de Jimmy, 20 aout) : on ajoute ~20 instruments
CFD offerts chez OANDA au chassis L4 (noyau or 2,0 / petrole 1,5 / US100
1,5, gardien 2,5 %, mode challenge 0,75, max 2 positions, plafond de
correlation metal/indice), puis on ELIMINE les moins profitables et on
refait tourner. Nouveaux marches = cassure Donchian 20/10 pyramidee 3
unites a 1,5 % (le gabarit petrole), LONG seulement, comme les robots.
Moteur 1d, 5 ans Yahoo. Frais/swaps approximatifs par classe d'actif.
Contribution = somme des PnL quotidiens de la manche sur 5 ans (points de
% du compte, apres frais/swap et coupes du gardien)."""
import os, time, requests, pandas as pd, numpy as np
from moteur_1d import Fib, Donch, ouvrir_pyr, gc, cl, nq

src = open("scan_strategies.py", encoding="utf-8").read().split("RISQUES =")[0]
_ns = {"__file__": "scan_strategies.py"}; exec(src, _ns)
gerer_pyr_max = _ns["gerer_pyr_max"]

D = os.path.dirname(os.path.abspath(__file__))

def fetch(sym):
    """Yahoo 5 ans 1d, cache CSV local (oanda_<sym>.csv)."""
    fn = os.path.join(D, "oanda_" + sym.replace("=", "").replace("^", "") + ".csv")
    if os.path.exists(fn):
        return pd.read_csv(fn, index_col=0, parse_dates=True)
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/" + sym,
                     params={"range": "5y", "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    df = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s").normalize(),
                       "o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]}
                      ).dropna().drop_duplicates("t").set_index("t")
    # GARDE-FOU (21 aout 2026) : Yahoo livre des barres incoherentes sur les
    # paires forex "=X" (ouverture/fermeture d'un autre instantane que le
    # haut/bas). On elargit la meche aux valeurs que la source a elle-meme
    # rapportees : on n'invente aucun prix, on rend la barre coherente.
    incoherentes = int(((df.h < df.l) | (df.h < df.o) | (df.h < df.c)
                        | (df.l > df.o) | (df.l > df.c)).sum())
    if incoherentes:
        df["h"] = df[list("ohlc")].max(axis=1)
        df["l"] = df[list("ohlc")].min(axis=1)
        print("  %s : %d barre(s) incoherente(s) reparee(s) a la source" % (sym, incoherentes))
    assert (df[list("ohlc")] > 0).all().all(), "%s : prix <= 0 dans les donnees" % sym
    df.to_csv(fn); time.sleep(0.3)
    return df

# (nom OANDA, symbole Yahoo, famille, frais relatifs, swap/jour)
CANDIDATS = [
    ("EUR_USD", "EURUSD=X", "fx", 0.00010, -0.00005),
    ("GBP_USD", "GBPUSD=X", "fx", 0.00012, -0.00005),
    ("USD_JPY", "USDJPY=X", "fx", 0.00010, -0.00005),
    ("USD_CHF", "USDCHF=X", "fx", 0.00012, -0.00005),
    ("USD_CAD", "USDCAD=X", "fx", 0.00012, -0.00005),
    ("AUD_USD", "AUDUSD=X", "fx", 0.00012, -0.00005),
    ("NZD_USD", "NZDUSD=X", "fx", 0.00015, -0.00005),
    ("EUR_JPY", "EURJPY=X", "fx", 0.00015, -0.00005),
    ("GBP_JPY", "GBPJPY=X", "fx", 0.00020, -0.00005),
    ("EUR_GBP", "EURGBP=X", "fx", 0.00015, -0.00005),
    ("AUD_JPY", "AUDJPY=X", "fx", 0.00020, -0.00005),
    ("EUR_AUD", "EURAUD=X", "fx", 0.00020, -0.00005),
    ("XAG_USD", "SI=F",     "mi", 0.00030, -0.00020),
    ("XCU_USD", "HG=F",     "mi", 0.00040, -0.00020),
    ("BCO_USD", "BZ=F",     "en", 0.00045, +0.00005),
    ("NATGAS",  "NG=F",     "en", 0.00100, -0.00030),
    ("SPX500",  "ES=F",     "mi", 0.00003, -0.00021),
    ("US30",    "YM=F",     "mi", 0.00005, -0.00021),
    ("JP225",   "NKD=F",    "mi", 0.00010, -0.00015),
    ("DE30",    "^GDAXI",   "mi", 0.00010, -0.00015),
]

print("Telechargement Yahoo (cache local)...")
DATA = {}
for nom, sym, fam, frais, swap in CANDIDATS:
    try:
        df = fetch(sym)
        if len(df) < 900:
            print("  %-8s IGNORE (seulement %d jours)" % (nom, len(df))); continue
        DATA[nom] = df
    except Exception as e:
        print("  %-8s IGNORE (%s)" % (nom, type(e).__name__))
print("  %d candidats charges sur %d" % (len(DATA), len(CANDIDATS)))

FAMX = {"Or": "mi", "Nasdaq": "mi", "Petrole": "en"}
FRSW = {}
for nom, sym, fam, frais, swap in CANDIDATS:
    FAMX[nom] = fam; FRSW[nom] = (frais, swap)

def construire(actifs):
    """Noyau L4 OANDA + candidats Donchian pyramides. Ordre = priorite."""
    sl = [Fib("Or", gc, 0.02, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
              lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
          Donch("Petrole", cl, 0.015, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
          Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
              tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0)]
    sl = [s for s in sl if s.nom in actifs]
    for nom in actifs:
        if nom in ("Or", "Petrole", "Nasdaq") or nom not in DATA: continue
        frais, swap = FRSW[nom]
        sl.append(Donch(nom, DATA[nom], 0.015, frais, swap, 1.4))
    for s in sl:
        if isinstance(s, Donch):
            s.pyr_max = 3
            s.gerer = gerer_pyr_max.__get__(s); s.ouvrir = ouvrir_pyr.__get__(s)
    return sl

def metriques(tj):
    eq = (1 + tj).cumprod()
    ans = (tj.index[-1] - tj.index[0]).days / 365.25
    cagr = (eq.iloc[-1] ** (1/ans) - 1) * 100
    dd = ((eq / eq.cummax()) - 1).min() * 100
    vals = tj.values; morts = reussis = 0
    for i0 in range(0, len(vals) - 40, 21):
        e2 = 1.0
        for jx in range(i0, len(vals)):
            e2 *= (1 + vals[jx])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; break
    n = morts + reussis
    return cagr, dd, (morts/n*100 if n else 0)

def sim(actifs):
    sl = construire(actifs)
    garde = -0.025
    dates = sorted(set().union(*[set(s.df.index) for s in sl]))
    equite, histo = 1.0, []
    for d in dates:
        for s in sl: s.gerer(d)
        jt = sum(s.pnl.get(d, 0) for s in sl)
        if jt <= garde:
            f = garde / jt
            for s in sl:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            jt = garde
        equite *= (1 + jt); histo.append(equite)
        if jt <= garde: continue
        fc = 0.75 if (len(histo) > 20 and equite < np.mean(histo[-20:])) else 1.0
        ouverts = sum(1 for s in sl if s.pos is not None)
        familles = {FAMX[s.nom] for s in sl if s.pos is not None}
        for s in sl:
            if s.pos is not None or ouverts >= 2: continue
            if FAMX[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(d)
            if sig is None: continue
            r0 = s.risque; s.risque = r0 * fc
            ok = s.ouvrir(d, **sig); s.risque = r0
            if ok: ouverts += 1; familles.add(FAMX[s.nom])
    tj = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sl:
        for dt, v in s.pnl.items():
            if dt in tj.index: tj[dt] += v
    contrib = {s.nom: (sum(s.pnl.values()) * 100, s.trades) for s in sl}
    return metriques(tj.clip(lower=garde)), contrib

NOYAU = ["Or", "Petrole", "Nasdaq"]
rondes = []
actifs = NOYAU + [n for n in DATA]
for ronde in (1, 2, 3):
    (cagr, dd, morts), contrib = sim(actifs)
    rondes.append((ronde, list(actifs), cagr, dd, morts, contrib))
    print()
    print("=== RONDE %d : %d manches | CAGR %+5.1f%% | MaxDD %+5.1f%% | Morts %2.0f%% ==="
          % (ronde, len(actifs), cagr, dd, morts))
    print("  %-10s %-4s | %-10s | %s" % ("Manche", "fam", "Contribution", "Trades"))
    for nom, (pts, tr) in sorted(contrib.items(), key=lambda x: -x[1][0]):
        print("  %-10s %-4s | %+8.1f pts | %4d" % (nom, FAMX[nom], pts, tr))
    if ronde == 1:
        actifs = [n for n in actifs if contrib.get(n, (0, 0))[0] > 0]
        print("  -> on elimine les contributions negatives ; il reste %d manches" % len(actifs))
    elif ronde == 2:
        actifs = [n for n in actifs if contrib.get(n, (0, 0))[0] >= 2.0]
        print("  -> on garde les contributions >= +2 pts ; il reste %d manches" % len(actifs))

print()
print("=== RESUME DES RONDES (reference : noyau seul or+pet+nas = +11.0%%/an, 11%% morts) ===")
for ronde, act, cagr, dd, morts, _ in rondes:
    print("  Ronde %d (%2d manches) : CAGR %+5.1f%% | MaxDD %+5.1f%% | Morts %2.0f%%"
          % (ronde, len(act), cagr, dd, morts))
print("  Manches finales : " + ", ".join(rondes[-1][1]))
