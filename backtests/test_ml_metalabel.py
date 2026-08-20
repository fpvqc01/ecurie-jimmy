# -*- coding: utf-8 -*-
"""ETUDE ML — META-ETIQUETAGE (Lopez de Prado) sur les signaux de l'ecurie.
PRINCIPE : le ML ne choisit PAS les trades. Les strategies validees generent
leurs signaux comme d'habitude ; le modele apprend seulement, a partir du
CONTEXTE de chaque signal (volatilite, tendance, etirement, RSI...), la
probabilite qu'il reussisse — puis module la TAILLE (0,5x / 1x / 1,5x).
PROTOCOLE HONNETE :
  - ~10 ans de signaux des 5 manches (or fib, nasdaq fib, btc ema,
    btc donchian, petrole donchian saisonnier) -> echantillon groupe
  - regression logistique maison (numpy), features standardisees
  - WALK-FORWARD STRICT : entrainement sur le passe seulement,
    re-entrainement annuel, prediction sur l'annee suivante
  - verdict : total R pondere vs total R de base, moities, et test
    du 'skip' (ignorer le pire decile) ; peu importe la beaute du modele,
    seuls les standards comptent."""
import requests, pandas as pd, numpy as np

def fetch(sym, rng="10y"):
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/" + sym,
                     params={"range": rng, "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    return pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s").normalize(),
                         "h": q["high"], "l": q["low"], "c": q["close"]}
                        ).dropna().drop_duplicates("t").set_index("t")

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()

def indicateurs(df):
    c, h, l = df["c"], df["h"], df["l"]
    tr = np.maximum(h-l, np.maximum((h-c.shift()).abs(), (l-c.shift()).abs()))
    out = {}
    out["atr14"] = wilder(tr, 14)
    out["atr100"] = wilder(tr, 100)
    dd = c.diff()
    out["rsi14"] = 100 - 100/(1 + wilder(dd.clip(lower=0), 14) / wilder(-dd.clip(upper=0), 14).replace(0, np.nan))
    out["ema50"] = c.ewm(span=50, adjust=False).mean()
    out["min20"] = l.rolling(20).min()
    out["ret20"] = c.pct_change(20)
    return out

def features_a(df, ind, i, type_strat):
    """vecteur de contexte au moment du signal (bougies fermees seulement)"""
    c = df["c"].iloc[i]
    a = ind["atr14"].iloc[i]
    if a <= 0 or np.isnan(a): return None
    f = [
        a / c * 100,                                    # niveau de volatilite (%)
        ind["atr14"].iloc[i] / max(ind["atr100"].iloc[i], 1e-9),   # regime de vol
        (c - ind["ema50"].iloc[i]) / a,                 # force de tendance (en ATR)
        ind["rsi14"].iloc[i] / 100.0,                   # RSI
        (c - ind["min20"].iloc[i]) / a,                 # etirement depuis le creux 20j
        ind["ret20"].iloc[i] * 100,                     # momentum 20 jours (%)
        1.0 if type_strat == "repli" else 0.0,          # famille repli
        1.0 if type_strat == "cassure" else 0.0,        # famille cassure (ema = 0/0)
    ]
    if any(np.isnan(x) for x in f): return None
    return f

# ------------------------------------------------------------------
# Generateurs de signaux (identiques aux etudes precedentes)
# ------------------------------------------------------------------
def sig_fib(df, ind, lookback, fiblo, fibhi, rsis, mult, tpr):
    c, h, l = df["c"], df["h"], df["l"]
    out, pos = [], None
    for i in range(max(120, lookback+2), len(df)):
        if pos:
            R = pos["R"]
            if l.iloc[i] <= pos["e"] - R: out.append((pos["i"], pos["f"], -1.0)); pos = None
            elif h.iloc[i] >= pos["e"] + tpr*R: out.append((pos["i"], pos["f"], tpr)); pos = None
            continue
        fh, fl = h.iloc[i-lookback:i], l.iloc[i-lookback:i]
        hi_i, lo_i = fh.values.argmax(), fl.values.argmin()
        if lo_i >= hi_i: continue
        span = fh.iloc[hi_i] - fl.iloc[lo_i]
        if span <= 0: continue
        retr = (fh.iloc[hi_i] - c.iloc[i]) / span
        if not (fiblo <= retr <= fibhi): continue
        r14 = ind["rsi14"]
        if not (r14.iloc[i-1] < rsis and r14.iloc[i] > r14.iloc[i-1]): continue
        f = features_a(df, ind, i, "repli")
        if f is None: continue
        pos = dict(e=c.iloc[i], R=mult*ind["atr14"].iloc[i], i=df.index[i], f=f)
    return out

def sig_ema(df, ind):
    c, h, l = df["c"], df["h"], df["l"]
    er = c.ewm(span=20, adjust=False).mean(); el = c.ewm(span=50, adjust=False).mean()
    out, pos = [], None
    for i in range(120, len(df)):
        haussier = er.iloc[i] > el.iloc[i]
        if pos:
            R = pos["R"]
            if l.iloc[i] <= pos["e"] - R: out.append((pos["i"], pos["f"], -1.0)); pos = None
            elif h.iloc[i] >= pos["e"] + 2.0*R: out.append((pos["i"], pos["f"], 2.0)); pos = None
            elif not haussier: out.append((pos["i"], pos["f"], (c.iloc[i]-pos["e"])/R)); pos = None
        if pos is None and haussier and er.iloc[i-1] <= el.iloc[i-1]:
            f = features_a(df, ind, i, "ema")
            if f is None: continue
            pos = dict(e=c.iloc[i], R=2*ind["atr14"].iloc[i], i=df.index[i], f=f)
    return out

def sig_donch(df, ind, pe, ps, saison=None):
    c, h, l = df["c"], df["h"], df["l"]
    hh = h.rolling(pe).max().shift(1); bb = l.rolling(ps).min().shift(1)
    out, pos = [], None
    for i in range(max(120, pe+2), len(df)):
        if pos:
            pos["s"] = max(pos["s"], bb.iloc[i])
            R = pos["R"]
            if l.iloc[i] <= pos["s"]:
                out.append((pos["i"], pos["f"], (pos["s"]-pos["e"])/R)); pos = None
            continue
        if saison is not None:
            m = df.index[i].month
            ok = (m >= saison[0] or m <= saison[1])
            if not ok: continue
        if c.iloc[i] > hh.iloc[i]:
            R = c.iloc[i] - bb.iloc[i]
            if R <= 0: continue
            f = features_a(df, ind, i, "cassure")
            if f is None: continue
            pos = dict(e=c.iloc[i], s=bb.iloc[i], R=R, i=df.index[i], f=f)
    return out

# ------------------------------------------------------------------
print("Telechargement des 4 marches...")
btc, gc, nq, cl = fetch("BTC-USD"), fetch("GC=F"), fetch("NQ=F"), fetch("CL=F")
signaux = []
for nom, s in [
    ("or", sig_fib(gc, indicateurs(gc), 10, 0.2, 0.8, 55, 3.0, 1.5)),
    ("nasdaq", sig_fib(nq, indicateurs(nq), 7, 0.1, 0.9, 60, 2.0, 1.0)),
    ("btc_ema", sig_ema(btc, indicateurs(btc))),
    ("btc_cassure", sig_donch(btc, indicateurs(btc), 55, 20)),
    ("petrole", sig_donch(cl, indicateurs(cl), 20, 10, saison=(12, 5))),
]:
    for (date, f, r) in s:
        signaux.append((date, nom, f, r))
signaux.sort(key=lambda x: x[0])
print("Echantillon : %d signaux sur %s -> %s" %
      (len(signaux), signaux[0][0].date(), signaux[-1][0].date()))
gagnants = sum(1 for s in signaux if s[3] > 0)
print("Taux de reussite de base : %.0f %% | R total de base : %+.1f" %
      (100*gagnants/len(signaux), sum(s[3] for s in signaux)))

# ------------------------------------------------------------------
# Regression logistique maison + walk-forward annuel
# ------------------------------------------------------------------
def logistique(X, y, iters=400, lr=0.1):
    w = np.zeros(X.shape[1] + 1)
    Xb = np.hstack([np.ones((len(X), 1)), X])
    for _ in range(iters):
        p = 1/(1 + np.exp(-Xb @ w))
        w += lr * Xb.T @ (y - p) / len(y)
    return w

def predire(w, X):
    Xb = np.hstack([np.ones((len(X), 1)), X])
    return 1/(1 + np.exp(-Xb @ w))

dates = [s[0] for s in signaux]
F = np.array([s[2] for s in signaux])
R = np.array([s[3] for s in signaux])
Y = (R > 0).astype(float)
annees = sorted(set(d.year for d in dates))
premiere_annee_test = annees[0] + 4      # 4 ans d'entrainement minimum

base_R, ml_R, skip_R = [], [], []
tailles_utilisees = []
for an in annees:
    if an < premiere_annee_test: continue
    train = [i for i, d in enumerate(dates) if d.year < an]
    test = [i for i, d in enumerate(dates) if d.year == an]
    if len(train) < 100 or not test: continue
    mu, sd = F[train].mean(axis=0), F[train].std(axis=0) + 1e-9
    Xtr = (F[train] - mu) / sd
    w = logistique(Xtr, Y[train])
    p_tr = predire(w, Xtr)
    t_bas, t_haut = np.percentile(p_tr, 33), np.percentile(p_tr, 66)
    t_skip = np.percentile(p_tr, 10)
    Xte = (F[test] - mu) / sd
    p_te = predire(w, Xte)
    for k, i in enumerate(test):
        base_R.append(R[i])
        taille = 0.5 if p_te[k] < t_bas else (1.5 if p_te[k] > t_haut else 1.0)
        tailles_utilisees.append(taille)
        ml_R.append(R[i] * taille)
        skip_R.append(0.0 if p_te[k] < t_skip else R[i])

base_R, ml_R, skip_R = map(np.array, (base_R, ml_R, skip_R))
n = len(base_R); m = n // 2
def ligne(nom, arr, div=1.0):
    tot = arr.sum() / div
    m1, m2 = arr[:m].sum() / div, arr[m:].sum() / div
    pf = arr[arr > 0].sum() / abs(arr[arr < 0].sum()) if (arr < 0).any() else 99
    print("  %-34s total %+7.1f R | PF %4.2f | moities %+6.1f / %+6.1f" % (nom, tot, pf, m1, m2))

print()
print("=== VERDICT WALK-FORWARD (%d signaux hors entrainement) ===" % n)
ligne("BASE (tous les signaux, taille 1)", base_R)
ligne("ML sizing 0,5/1/1,5 (normalise)", ml_R, np.mean(tailles_utilisees))
ligne("ML skip du pire decile", skip_R)
print()
print("  repartition des tailles ML : 0,5x=%d | 1x=%d | 1,5x=%d" %
      (sum(1 for t in tailles_utilisees if t == 0.5),
       sum(1 for t in tailles_utilisees if t == 1.0),
       sum(1 for t in tailles_utilisees if t == 1.5)))
# le modele a-t-il un vrai pouvoir discriminant ?
haut = ml_R[np.array(tailles_utilisees) == 1.5]
bas = ml_R[np.array(tailles_utilisees) == 0.5]
if len(haut) and len(bas):
    print("  R moyen des signaux juges FORTS : %+.3f | juges FAIBLES : %+.3f  (ecart = pouvoir predictif)" %
          ((haut/1.5).mean(), (bas/0.5).mean()))
