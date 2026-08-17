# -*- coding: utf-8 -*-
"""Reanalyse de TOUTES les strategies avec les frais reels FTMO releves
dans les specifications MT5 du compte (16 aout 2026) :

BTCUSD  : swap long -30%/an (mode %, 7j/7), commission 0.0325%/cote, spread ~0.015%
XAUUSD  : swap long -93.35 pts = -0.93$/oz/jour (~ -0.0213%/jour, triple mercredi
          -> 7 charges pour 5 jours de marche), commission negligeable, spread 0.40$
US100   : swap long -641.14 pts = -6.41 pts d'indice/jour (~ -0.0213%/jour,
          triple vendredi), commission 0%, spread 1.8 pts

Strategies re-testees sur leurs donnees respectives :
- MacroBot OR et NASDAQ (fib+RSI H4, avec le breakeven +1R maintenant actif)
- BTC : EMA 20/50 H1 et cassure 55/20 H4 (rappel des chiffres deja calcules)
"""
import requests, pandas as pd, numpy as np

def fetch_h4(sym):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"range": "730d", "interval": "1h"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    df = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s"),
                       "o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]}).dropna().set_index("t")
    return df.resample("4h").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False).mean()

def simulate(df, lookback, fib, rsi_pull, atr_mult, tp_r, spread_abs, comm_rt_frac,
             swap_jour_frac, facteur_semaine, breakeven):
    o, h, l, c = df["o"].values, df["h"].values, df["l"].values, df["c"].values
    n = len(df)
    delta = df["c"].diff()
    rsi = (100 - 100/(1 + wilder(delta.clip(lower=0), 14) / wilder(-delta.clip(upper=0), 14).replace(0, np.nan))).values
    tr = np.maximum(df["h"] - df["l"], np.maximum((df["h"] - df["c"].shift()).abs(), (df["l"] - df["c"].shift()).abs()))
    atr = wilder(tr, 14).values
    fib_lo, fib_hi = fib
    trades, i = [], lookback + 15
    while i < n - 2:
        win_h, win_l = h[i-lookback+1:i+1], l[i-lookback+1:i+1]
        hi_i, lo_i = np.argmax(win_h), np.argmin(win_l)
        ok = lo_i < hi_i
        if ok:
            span = win_h[hi_i] - win_l[lo_i]
            retrace = (win_h[hi_i] - c[i]) / span if span > 0 else -1
            ok = (span > 0 and fib_lo <= retrace <= fib_hi
                  and rsi[i-1] < rsi_pull and rsi[i] > rsi[i-1]
                  and not np.isnan(atr[i]) and atr[i] > 0)
        if not ok:
            i += 1; continue
        entree = o[i+1] + spread_abs / 2
        R = atr_mult * atr[i]
        sl, tp, niveau_be = entree - R, entree + tp_r * R, entree + R
        be_actif, sortie, j = False, None, i+1
        for j in range(i+1, n):
            stop = entree if (breakeven and be_actif) else sl
            if l[j] <= stop:
                sortie = 0.0 if (breakeven and be_actif) else -1.0; break
            if h[j] >= tp: sortie = tp_r; break
            if breakeven and not be_actif and h[j] >= niveau_be: be_actif = True
        if sortie is None: break
        bougies_tenues = j - i
        jours = bougies_tenues * 4 / 24 * facteur_semaine
        cout_swap_R = swap_jour_frac * jours * entree / R
        cout_comm_R = comm_rt_frac * entree / R
        trades.append(sortie - cout_swap_R - cout_comm_R)
        i = j + 1
    t = np.array(trades)
    if len(t) == 0: return None
    pf = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else 99.0
    return dict(n=len(t), win=(t > 0).mean()*100, tot=t.sum(), pf=pf)

gc, nq = fetch_h4("GC=F"), fetch_h4("NQ=F")

print("=== MacroBots (fib+RSI H4 + breakeven actif), frais reels FTMO, ~2 ans ===")
for nom, df, args in [
    ("OR     ", gc, dict(lookback=60, fib=(0.20, 0.80), rsi_pull=55.0, atr_mult=3.0, tp_r=2.0,
                         spread_abs=0.40, comm_rt_frac=0.000014, swap_jour_frac=0.000213, facteur_semaine=7/5)),
    ("NASDAQ ", nq, dict(lookback=40, fib=(0.10, 0.90), rsi_pull=60.0, atr_mult=2.0, tp_r=2.0,
                         spread_abs=1.8, comm_rt_frac=0.0, swap_jour_frac=0.000213, facteur_semaine=7/5)),
]:
    sans = simulate(df, breakeven=True, **{**args, "swap_jour_frac": 0.0})
    avec = simulate(df, breakeven=True, **args)
    print(f"{nom} sans swap : {sans['n']} trades, {sans['win']:.0f}% vict., {sans['tot']:+.1f} R, PF {sans['pf']:.2f}")
    print(f"{nom} frais FTMO: {avec['n']} trades, {avec['win']:.0f}% vict., {avec['tot']:+.1f} R, PF {avec['pf']:.2f}"
          f"   (a 1%/trade : {avec['tot']:+.1f}% sur 2 ans)")
