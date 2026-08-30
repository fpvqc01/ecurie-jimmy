# -*- coding: utf-8 -*-
"""Volumes BTC H1 (Binance/Bitstamp) + Fear & Greed crypto historique."""
import os, time, requests, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))

# --- volumes H1 : on refait le fetch en gardant la colonne volume ---
chemin = os.path.join(D, "d10h1v_btc.csv")
if not os.path.exists(chemin):
    out, start = [], int(pd.Timestamp("2017-08-17").timestamp() * 1000)
    while True:
        r = requests.get("https://api.binance.com/api/v3/klines",
                         params={"symbol": "BTCUSDT", "interval": "1h",
                                 "startTime": start, "limit": 1000}, timeout=60)
        r.raise_for_status()
        k = r.json()
        if not k: break
        out += k
        start = k[-1][0] + 1
        if len(k) < 1000: break
        time.sleep(0.12)
    # CORRIGE le 21 aout 2026 : Binance renvoie [t, open, HIGH, LOW, close, vol].
    # L ancien "tochlv" mettait le BAS dans la colonne h et la CLOTURE dans l
    # -> c est le bogue qui avait corrompu 81 %% des barres H1 du BTC.
    df = pd.DataFrame(out, columns=list("tohlcv") + ["ct","qv","n","tb","tq","x"])
    df = df[["t","o","h","l","c","v"]].astype(float)
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_localize(None)
    b2 = df.drop_duplicates("t").set_index("t").sort_index()
    # bitstamp 2015-2017 avec volume
    out2, start = [], int(pd.Timestamp("2015-08-01").timestamp())
    fin_ts = int(pd.Timestamp("2017-08-18").timestamp())
    while start < fin_ts:
        r = requests.get("https://www.bitstamp.net/api/v2/ohlc/btcusd/",
                         params={"step": 3600, "limit": 1000, "start": start}, timeout=60)
        r.raise_for_status()
        k = r.json()["data"]["ohlc"]
        if not k: break
        out2 += k
        start = int(k[-1]["timestamp"]) + 3600
        time.sleep(0.2)
    b1 = pd.DataFrame(out2)
    b1["t"] = pd.to_datetime(b1["timestamp"].astype(int), unit="s")
    for c in ("open","high","low","close","volume"): b1[c] = b1[c].astype(float)
    b1 = b1.rename(columns={"open":"o","high":"h","low":"l","close":"c","volume":"v"})
    b1 = b1[["t","o","h","l","c","v"]].drop_duplicates("t").set_index("t").sort_index()
    btc = pd.concat([b1[b1.index < b2.index[0]], b2]).sort_index()
    btc = btc[~btc.index.duplicated()]
    btc.to_csv(chemin)
print("BTC H1+volume :", len(pd.read_csv(chemin)), "barres")

# --- Fear & Greed historique (alternative.me, gratuit, depuis 2018) ---
chemin2 = os.path.join(D, "fng.csv")
if not os.path.exists(chemin2):
    r = requests.get("https://api.alternative.me/fng/", params={"limit": 0}, timeout=60)
    r.raise_for_status()
    d = r.json()["data"]
    df = pd.DataFrame([(pd.to_datetime(int(x["timestamp"]), unit="s").normalize(),
                        int(x["value"])) for x in d], columns=["t", "fng"])
    df.drop_duplicates("t").set_index("t").sort_index().to_csv(chemin2)
f = pd.read_csv(chemin2, index_col=0, parse_dates=True)
print("Fear&Greed : %d jours, %s -> %s" % (len(f), f.index[0].date(), f.index[-1].date()))
