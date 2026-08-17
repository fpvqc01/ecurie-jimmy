# -*- coding: utf-8 -*-
"""Backtest de strategies BTC sur 10 ans de donnees journalieres (Yahoo Finance).

Regles anti-triche :
- Les signaux calcules a la cloture du jour J sont appliques au jour J+1 (shift).
- Frais de 0.06 % par changement de position (achat, vente, retournement = 2x).
"""
import json
import requests
import pandas as pd
import numpy as np

FRAIS_PAR_COTE = 0.0006  # 0.06 % par transaction (spread + commission approx.)

# --- 1. Telecharger 10 ans de BTC-USD journalier ---
url = "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD"
params = {"range": "10y", "interval": "1d"}
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
r = requests.get(url, params=params, headers=headers, timeout=30)
r.raise_for_status()
data = r.json()["chart"]["result"][0]

ts = data["timestamp"]
q = data["indicators"]["quote"][0]
df = pd.DataFrame({
    "date": pd.to_datetime(ts, unit="s"),
    "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
}).dropna().set_index("date")

print(f"Donnees : {df.index[0].date()} -> {df.index[-1].date()}  ({len(df)} jours)")
print(f"Prix depart : {df['close'].iloc[0]:,.0f} $ | Prix fin : {df['close'].iloc[-1]:,.0f} $")

close, high, low = df["close"], df["high"], df["low"]
rendements = close.pct_change().fillna(0.0)

# --- 2. Indicateurs ---
ema20 = close.ewm(span=20, adjust=False).mean()
ema50 = close.ewm(span=50, adjust=False).mean()
sma200 = close.rolling(200).mean()

def rsi(serie, periode):
    delta = serie.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/periode, adjust=False).mean()
    perte = (-delta.clip(upper=0)).ewm(alpha=1/periode, adjust=False).mean()
    rs = gain / perte.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

rsi2 = rsi(close, 2)

# Canaux de Donchian (plus haut/plus bas des 20 derniers jours, hors jour courant)
haut20 = high.rolling(20).max().shift(1)
bas20 = low.rolling(20).min().shift(1)
haut55 = high.rolling(55).max().shift(1)
bas55 = low.rolling(55).min().shift(1)

# --- 3. Strategies : chaque fonction retourne la position (1=achat, -1=vente, 0=rien) ---
def pos_buy_hold():
    return pd.Series(1.0, index=close.index)

def pos_ema_cross_long_short():
    return pd.Series(np.where(ema20 > ema50, 1.0, -1.0), index=close.index)

def pos_ema_cross_long_seulement():
    return pd.Series(np.where(ema20 > ema50, 1.0, 0.0), index=close.index)

def pos_sma200():
    return pd.Series(np.where(close > sma200, 1.0, 0.0), index=close.index)

def pos_donchian20():
    # Achat sur cassure du plus haut 20 j ; sortie sur cassure du plus bas 20 j
    pos = pd.Series(np.nan, index=close.index)
    pos[close > haut20] = 1.0
    pos[close < bas20] = 0.0
    return pos.ffill().fillna(0.0)

def pos_donchian55_long_short():
    pos = pd.Series(np.nan, index=close.index)
    pos[close > haut55] = 1.0
    pos[close < bas55] = -1.0
    return pos.ffill().fillna(0.0)

def pos_rsi2_retour_moyenne():
    # Achat quand RSI(2) < 10 en tendance haussiere (prix > SMA200), sortie quand RSI(2) > 60
    pos = pd.Series(np.nan, index=close.index)
    pos[(rsi2 < 10) & (close > sma200)] = 1.0
    pos[rsi2 > 60] = 0.0
    return pos.ffill().fillna(0.0)

strategies = {
    "Buy & hold (reference)": pos_buy_hold,
    "EMA 20/50 achat+vente (bot actuel)": pos_ema_cross_long_short,
    "EMA 20/50 achat seulement": pos_ema_cross_long_seulement,
    "Filtre SMA 200 (achat si prix au-dessus)": pos_sma200,
    "Donchian 20 j (cassures, achat seul.)": pos_donchian20,
    "Donchian 55 j achat+vente": pos_donchian55_long_short,
    "RSI(2) retour a la moyenne": pos_rsi2_retour_moyenne,
}

# --- 4. Moteur de backtest ---
def backtester(position):
    pos_appliquee = position.shift(1).fillna(0.0)          # applique le LENDEMAIN
    frais = pos_appliquee.diff().abs().fillna(0.0) * FRAIS_PAR_COTE
    rend_strat = pos_appliquee * rendements - frais
    equite = (1 + rend_strat).cumprod()

    annees = (close.index[-1] - close.index[0]).days / 365.25
    total = equite.iloc[-1] - 1
    cagr = equite.iloc[-1] ** (1 / annees) - 1
    dd = (equite / equite.cummax() - 1).min()
    vol = rend_strat.std() * np.sqrt(365)
    sharpe = (rend_strat.mean() * 365) / (rend_strat.std() * np.sqrt(365)) if rend_strat.std() > 0 else 0
    pire_jour = rend_strat.min()
    nb_trades = int((pos_appliquee.diff().abs() > 0).sum())
    return {
        "Rendement total": f"{total*100:,.0f} %",
        "Rendement annuel (CAGR)": f"{cagr*100:.1f} %",
        "Pire chute (drawdown)": f"{dd*100:.0f} %",
        "Pire journee": f"{pire_jour*100:.1f} %",
        "Sharpe": f"{sharpe:.2f}",
        "Nb transactions": nb_trades,
    }

resultats = {nom: backtester(fn()) for nom, fn in strategies.items()}
tableau = pd.DataFrame(resultats).T
print()
print(tableau.to_string())

tableau.to_csv(r"C:\Users\jplou\Downloads\backtest_btc_10ans.csv", encoding="utf-8-sig")
print("\nResultats sauvegardes dans Downloads\\backtest_btc_10ans.csv")
