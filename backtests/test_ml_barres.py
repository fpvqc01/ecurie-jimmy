# -*- coding: utf-8 -*-
"""ETUDE ML A L'ECHELLE DES BOUGIES (le dernier chapitre honnete du ML).
Au lieu d'apprendre sur 178 trades, on apprend sur ~65 000 bougies.
Trois cibles, chacune avec un usage concret dans l'ecurie :
  CIBLE A — VOLATILITE de demain (regression) : remplacerait la regle
            actuelle du facteurVol. Reference a battre : la persistance
            (« demain = aujourd'hui »), tres dure a battre.
  CIBLE B — DIRECTION du lendemain (classification) : le graal presume,
            historiquement ~51 % = inutile apres frais. On mesure.
  CIBLE C — SURVIE D'UNE CASSURE : quand le prix casse un canal 20,
            tient-il 5 jours au-dessus ? (utile pour filtrer les cassures)
PROTOCOLE : walk-forward annuel strict, standardisation sur le passe
seulement, et TEST DE PERMUTATION (100 melanges) pour chaque cible.
Avec 65 000 exemples, le test a enfin du pouvoir : s'il echoue ici,
la question ML est reglee."""
import requests, pandas as pd, numpy as np

def fetch(sym, rng="10y"):
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/" + sym,
                     params={"range": rng, "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    return pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s").normalize(),
                         "o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]}
                        ).dropna().drop_duplicates("t").set_index("t")

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()

def construire(df, marche):
    """features (connues a la cloture du jour i) + cibles (jour i+1...)"""
    c, h, l, o = df["c"], df["h"], df["l"], df["o"]
    tr = np.maximum(h-l, np.maximum((h-c.shift()).abs(), (l-c.shift()).abs()))
    atr14 = wilder(tr, 14); atr50 = wilder(tr, 50)
    dd = c.diff()
    rsi = 100 - 100/(1 + wilder(dd.clip(lower=0), 14) / wilder(-dd.clip(upper=0), 14).replace(0, np.nan))
    ema20 = c.ewm(span=20, adjust=False).mean()
    ema50 = c.ewm(span=50, adjust=False).mean()
    haut20 = h.rolling(20).max(); bas20 = l.rolling(20).min()
    rend = c.pct_change()
    X = pd.DataFrame({
        "vol_niveau": atr14 / c,
        "vol_regime": atr14 / atr50,
        "rsi": rsi / 100,
        "ecart_ema": (ema20 - ema50) / atr14,
        "pos_prix": (c - ema20) / atr14,
        "pos_canal": (c - bas20) / (haut20 - bas20).replace(0, np.nan),
        "rend1": rend,
        "rend5": c.pct_change(5),
        "rend20": c.pct_change(20),
        "corps": (c - o) / atr14,
        "meche_h": (h - np.maximum(c, o)) / atr14,
        "meche_b": (np.minimum(c, o) - l) / atr14,
        "vol_realisee5": rend.rolling(5).std(),
        "vol_realisee20": rend.rolling(20).std(),
    }, index=df.index)
    # cibles
    cibleA = (tr.shift(-1) / c)                      # amplitude vraie de demain, normalisee
    cibleB = (c.shift(-1) > c).astype(float)         # direction demain
    casse = (c > haut20.shift(1))                    # cassure du canal 20 aujourd'hui
    tient = (c.shift(-5) > c)                        # tient 5 jours plus tard
    cibleC = pd.Series(np.where(casse, tient.astype(float), np.nan), index=df.index)
    ok = X.notna().all(axis=1) & cibleA.notna() & cibleB.notna()
    return X[ok], cibleA[ok], cibleB[ok], cibleC[ok], pd.Series(marche, index=X[ok].index)

print("Telechargement...")
donnees = {m: fetch(s) for m, s in
           (("btc", "BTC-USD"), ("or", "GC=F"), ("nasdaq", "NQ=F"),
            ("petrole", "CL=F"), ("sp500", "ES=F"))}
Xs, As, Bs, Cs, Ms = [], [], [], [], []
for m, df in donnees.items():
    x, a, b, cc, mm = construire(df, m)
    Xs.append(x); As.append(a); Bs.append(b); Cs.append(cc); Ms.append(mm)
X = pd.concat(Xs); A = pd.concat(As); B = pd.concat(Bs); C = pd.concat(Cs); M = pd.concat(Ms)
ordre = np.argsort(X.index.values)
X, A, B, C, M = X.iloc[ordre], A.iloc[ordre], B.iloc[ordre], C.iloc[ordre], M.iloc[ordre]
print("Echantillon : %d bougies, %d features, %s -> %s" %
      (len(X), X.shape[1], X.index[0].date(), X.index[-1].date()))
print("  cassures avec issue connue (cible C) : %d" % C.notna().sum())

# ---------------- modeles maison (numpy) ----------------
def moindres_carres(Xtr, ytr, ridge=1.0):
    Xb = np.hstack([np.ones((len(Xtr), 1)), Xtr])
    A_ = Xb.T @ Xb + ridge * np.eye(Xb.shape[1])
    return np.linalg.solve(A_, Xb.T @ ytr)

def logistique(Xtr, ytr, iters=300, lr=0.5):
    w = np.zeros(Xtr.shape[1] + 1)
    Xb = np.hstack([np.ones((len(Xtr), 1)), Xtr])
    for _ in range(iters):
        p = 1/(1 + np.exp(-np.clip(Xb @ w, -30, 30)))
        w += lr * Xb.T @ (ytr - p) / len(ytr)
    return w

def appliquer(w, Xte, logit=False):
    z = np.hstack([np.ones((len(Xte), 1)), Xte]) @ w
    return 1/(1 + np.exp(-np.clip(z, -30, 30))) if logit else z

def walkforward(Xd, yd, logit, melange=False, graine=0, seuil_tr=2000):
    """entrainement sur les annees precedentes, prediction sur l'annee en cours"""
    idx = Xd.index
    annees = sorted(set(idx.year))
    y = yd.values.copy()
    if melange:
        rng = np.random.default_rng(graine)
        y = rng.permutation(y)
    Xv = Xd.values
    preds, vrais = [], []
    for an in annees:
        tr = np.where(idx.year < an)[0]
        te = np.where(idx.year == an)[0]
        if len(tr) < seuil_tr or len(te) < 20: continue
        mu, sd = Xv[tr].mean(axis=0), Xv[tr].std(axis=0) + 1e-9
        Xtr, Xte = (Xv[tr]-mu)/sd, (Xv[te]-mu)/sd
        w = logistique(Xtr, y[tr]) if logit else moindres_carres(Xtr, y[tr])
        preds.append(appliquer(w, Xte, logit)); vrais.append(y[te])
    if not preds: return None, None
    return np.concatenate(preds), np.concatenate(vrais)

def score(p, v, logit):
    if logit:
        return ((p > 0.5).astype(float) == v).mean()          # exactitude
    ss_res = ((v - p) ** 2).sum(); ss_tot = ((v - v.mean()) ** 2).sum()
    return 1 - ss_res/ss_tot                                   # R2

def etude(nom, Xd, yd, logit, reference=None, n_perm=100, seuil_tr=2000):
    p, v = walkforward(Xd, yd, logit, seuil_tr=seuil_tr)
    if p is None:
        print("  %-40s donnees insuffisantes" % nom); return
    s = score(p, v, logit)
    perms = []
    for k in range(n_perm):
        pp, vv = walkforward(Xd, yd, logit, melange=True, graine=k, seuil_tr=seuil_tr)
        if pp is not None: perms.append(score(pp, vv, logit))
    perms = np.array(perms)
    pval = (perms >= s).mean() * 100
    ref = ("  | reference %.4f" % reference) if reference is not None else ""
    verdict = "SIGNIFICATIF" if pval < 5 else "hasard"
    print("  %-40s %s %.4f%s | hasard moy %.4f | p=%.0f%% -> %s" %
          (nom, "exactitude" if logit else "R2", s, ref, perms.mean(), pval, verdict))
    return s, pval

print()
print("=== CIBLE A : predire la VOLATILITE de demain (usage : facteurVol) ===")
# reference de persistance : la volatilite d'aujourd'hui predit celle de demain
persist = X["vol_niveau"].values
ss_res = ((A.values - persist)**2).sum(); ss_tot = ((A.values - A.values.mean())**2).sum()
print("  reference 'demain = aujourd'hui'         R2 %.4f" % (1 - ss_res/ss_tot))
etude("modele ML (14 features)", X, A, logit=False)

print()
print("=== CIBLE B : predire la DIRECTION de demain ===")
print("  reference 'toujours haussier'            exactitude %.4f" % B.mean())
etude("modele ML (14 features)", X, B, logit=True)

print()
print("=== CIBLE C : une cassure de canal TIENT-ELLE 5 jours ? ===")
mC = C.notna()
print("  reference 'toutes tiennent'              exactitude %.4f" % C[mC].mean())
etude("modele ML sur les cassures", X[mC], C[mC], logit=True, n_perm=100, seuil_tr=300)
