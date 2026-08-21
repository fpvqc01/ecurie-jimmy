# -*- coding: utf-8 -*-
"""BTC en H1 sur 10 ans : Bitstamp (2015-2017) + Binance (2017-2026)."""
import os, time, requests, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
chemin = os.path.join(D, "d10h1_btc.csv")
if os.path.exists(chemin):
    print("deja en cache"); raise SystemExit

def binance(interval, debut):
    out, start = [], int(pd.Timestamp(debut).timestamp() * 1000)
    while True:
        r = requests.get("https://api.binance.com/api/v3/klines",
                         params={"symbol": "BTCUSDT", "interval": interval,
                                 "startTime": start, "limit": 1000}, timeout=60)
        r.raise_for_status()
        k = r.json()
        if not k: break
        out += k
        start = k[-1][0] + 1
        if len(k) < 1000: break
        time.sleep(0.12)
    df = pd.DataFrame(out, columns=list("tohlcv") + ["ct","qv","n","tb","tq","x"])
    df = df[["t","o","h","l","c"]].astype(float)
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_localize(None)
    return df.drop_duplicates("t").set_index("t").sort_index()

def bitstamp(debut, fin):
    out, start = [], int(pd.Timestamp(debut).timestamp())
    fin_ts = int(pd.Timestamp(fin).timestamp())
    while start < fin_ts:
        r = requests.get("https://www.bitstamp.net/api/v2/ohlc/btcusd/",
                         params={"step": 3600, "limit": 1000, "start": start}, timeout=60)
        r.raise_for_status()
        k = r.json()["data"]["ohlc"]
        if not k: break
        out += k
        start = int(k[-1]["timestamp"]) + 3600
        time.sleep(0.2)
    df = pd.DataFrame(out)
    df["t"] = pd.to_datetime(df["timestamp"].astype(int), unit="s")
    for col in ("open","high","low","close"): df[col] = df[col].astype(float)
    df = df.rename(columns={"open":"o","high":"h","low":"l","close":"c"})
    return df[["t","o","h","l","c"]].drop_duplicates("t").set_index("t").sort_index()

b2 = binance("1h", "2017-08-17")
b1 = bitstamp("2015-08-01", "2017-08-18")
btc = pd.concat([b1[b1.index < b2.index[0]], b2]).sort_index()
btc = btc[~btc.index.duplicated()]
btc.to_csv(chemin)
print("BTC H1 : %d barres, %s -> %s" % (len(btc), btc.index[0], btc.index[-1]))


# --- controle de coherence ajoute le 21 aout 2026 ---
# apres tout telechargement, verifier que les bougies ont du sens :
#   assert (df["h"] >= df[["o","c"]].max(axis=1)).all()
#   assert (df["l"] <= df[["o","c"]].min(axis=1)).all()
