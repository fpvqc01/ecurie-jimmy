# -*- coding: utf-8 -*-
"""QUESTION DE JIMMY (20 aout) : « ajouter l'apprentissage automatique de
chaque robot ? » — version concrete et testable : un robot APPRENANT qui
re-optimise ses parametres sur ses donnees recentes (walk-forward), contre
le robot FIXE aux parametres du plateau valide.
  Experience 1 (BTC, EMA) : tous les 6 mois, l'apprenant choisit le meilleur
    couple EMA (parmi 25 combinaisons) des 24 derniers mois, et le trade
    pendant les 6 mois suivants. Variante 'apprenant rapide' : re-choix
    mensuel sur les 6 derniers mois.
  Experience 2 (Or, fib+RSI) : l'apprenant re-choisit son TP (1R/1.5R/2R/3R)
    et son seuil RSI (50/55/60) tous les 6 mois de la meme facon.
Le robot fixe utilise les parametres valides (EMA 20/50 ; TP 1,5R RSI 55).
Verdict par le total R sur ~8 ans HORS periode d'apprentissage initiale."""
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

btc = fetch("BTC-USD")
gc = fetch("GC=F")

# ------------------------------------------------------------------
# Experience 1 : EMA sur BTC
# ------------------------------------------------------------------
def trades_ema(df, rapide, lent, i0, i1):
    """R des trades EMA long-only (TP 1.5R, stop 2xATR) entre i0 et i1."""
    c, h, l = df["c"], df["h"], df["l"]
    er = c.ewm(span=rapide, adjust=False).mean()
    el = c.ewm(span=lent, adjust=False).mean()
    tr = np.maximum(h-l, np.maximum((h-c.shift()).abs(), (l-c.shift()).abs()))
    atr = wilder(tr, 14)
    out, pos = [], None
    for i in range(max(i0, lent+10), i1):
        haussier = er.iloc[i] > el.iloc[i]
        if pos:
            R = pos["R"]
            if l.iloc[i] <= pos["e"] - R: out.append(-1.0); pos = None
            elif h.iloc[i] >= pos["e"] + 1.5*R: out.append(1.5); pos = None
            elif not haussier: out.append((c.iloc[i]-pos["e"])/R); pos = None
        if pos is None and haussier and er.iloc[i-1] <= el.iloc[i-1]:
            pos = dict(e=c.iloc[i], R=2*atr.iloc[i])
    return out

GRILLE_EMA = [(r, s) for r in (10, 15, 20, 25, 30) for s in (40, 45, 50, 55, 60)]

def apprenant_ema(df, fenetre_j, pas_j):
    """walk-forward : re-choisit le meilleur couple EMA chaque `pas_j` jours
    sur les `fenetre_j` jours precedents."""
    n = len(df)
    total, changements, courant = [], 0, (20, 50)
    i = fenetre_j
    while i < n:
        fin_app = i
        deb_app = max(0, i - fenetre_j)
        meilleur, meilleur_r = courant, -1e9
        for (r, s) in GRILLE_EMA:
            somme = sum(trades_ema(df, r, s, deb_app, fin_app))
            if somme > meilleur_r:
                meilleur_r, meilleur = somme, (r, s)
        if meilleur != courant: changements += 1
        courant = meilleur
        total += trades_ema(df, courant[0], courant[1], i, min(i + pas_j, n))
        i += pas_j
    return total, changements

print("=== EXPERIENCE 1 : BTC, robot EMA (meme periode d'evaluation) ===")
depart = 504    # 2 ans d'echauffement pour tous
fixe = trades_ema(btc, 20, 50, depart, len(btc))
print("  FIXE (EMA 20/50 du plateau)         : %3d trades | total %+7.1f R" % (len(fixe), sum(fixe)))
for nom, fen, pas in (("APPRENANT 6 mois (fenetre 24 m)", 504, 126),
                      ("APPRENANT RAPIDE mensuel (fen. 6 m)", 126, 21)):
    t, ch = apprenant_ema(btc, fen, pas)
    print("  %-36s: %3d trades | total %+7.1f R | %d changements de parametres" % (nom, len(t), sum(t), ch))

# ------------------------------------------------------------------
# Experience 2 : fib+RSI sur l'or (apprend TP et seuil RSI)
# ------------------------------------------------------------------
def trades_fib(df, tp_r, rsi_seuil, i0, i1):
    c, h, l = df["c"], df["h"], df["l"]
    tr = np.maximum(h-l, np.maximum((h-c.shift()).abs(), (l-c.shift()).abs()))
    atr = wilder(tr, 14)
    dd = c.diff()
    r14 = 100 - 100/(1 + wilder(dd.clip(lower=0), 14) / wilder(-dd.clip(upper=0), 14).replace(0, np.nan))
    out, pos = [], None
    lb = 10
    for i in range(max(i0, 30), i1):
        if pos:
            R = pos["R"]
            if l.iloc[i] <= pos["e"] - R: out.append(-1.0); pos = None
            elif h.iloc[i] >= pos["e"] + tp_r*R: out.append(tp_r); pos = None
            continue
        fh, fl = h.iloc[i-lb:i], l.iloc[i-lb:i]
        hi_i, lo_i = fh.values.argmax(), fl.values.argmin()
        if lo_i >= hi_i: continue
        span = fh.iloc[hi_i] - fl.iloc[lo_i]
        if span <= 0: continue
        retr = (fh.iloc[hi_i] - c.iloc[i]) / span
        if not (0.2 <= retr <= 0.8): continue
        if not (r14.iloc[i-1] < rsi_seuil and r14.iloc[i] > r14.iloc[i-1]): continue
        pos = dict(e=c.iloc[i], R=3*atr.iloc[i])
    return out

GRILLE_FIB = [(tp, rs) for tp in (1.0, 1.5, 2.0, 3.0) for rs in (50, 55, 60)]

def apprenant_fib(df, fenetre_j, pas_j):
    n = len(df)
    total, changements, courant = [], 0, (1.5, 55)
    i = fenetre_j
    while i < n:
        meilleur, meilleur_r = courant, -1e9
        for (tp, rs) in GRILLE_FIB:
            somme = sum(trades_fib(df, tp, rs, max(0, i-fenetre_j), i))
            if somme > meilleur_r:
                meilleur_r, meilleur = somme, (tp, rs)
        if meilleur != courant: changements += 1
        courant = meilleur
        total += trades_fib(df, courant[0], courant[1], i, min(i + pas_j, n))
        i += pas_j
    return total, changements

print()
print("=== EXPERIENCE 2 : OR, robot fib+RSI (apprend TP et seuil RSI) ===")
fixe2 = trades_fib(gc, 1.5, 55, depart, len(gc))
print("  FIXE (TP 1,5R / RSI 55 valides)     : %3d trades | total %+7.1f R" % (len(fixe2), sum(fixe2)))
for nom, fen, pas in (("APPRENANT 6 mois (fenetre 24 m)", 504, 126),
                      ("APPRENANT RAPIDE mensuel (fen. 6 m)", 126, 21)):
    t, ch = apprenant_fib(gc, fen, pas)
    print("  %-36s: %3d trades | total %+7.1f R | %d changements de parametres" % (nom, len(t), sum(t), ch))
