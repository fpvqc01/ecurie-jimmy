# -*- coding: utf-8 -*-
"""Historique des taux de financement BTCUSDT (Binance perpetuel, 8h)."""
import os, time, requests, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
chemin = os.path.join(D, "funding_btc.csv")
if not os.path.exists(chemin):
    out, start = [], int(pd.Timestamp("2019-09-01").timestamp() * 1000)
    while True:
        r = requests.get("https://fapi.binance.com/fapi/v1/fundingRate",
                         params={"symbol": "BTCUSDT", "startTime": start, "limit": 1000},
                         timeout=60)
        r.raise_for_status()
        k = r.json()
        if not k: break
        out += k
        start = k[-1]["fundingTime"] + 1
        if len(k) < 1000: break
        time.sleep(0.2)
    df = pd.DataFrame(out)
    df["t"] = pd.to_datetime(df["fundingTime"].astype(float), unit="ms")
    df["taux"] = df["fundingRate"].astype(float)
    df[["t", "taux"]].drop_duplicates("t").set_index("t").sort_index().to_csv(chemin)
f = pd.read_csv(chemin, index_col=0, parse_dates=True)
print("funding : %d points, %s -> %s, mediane %.4f %%/8h, >0,05%% : %.0f%% du temps"
      % (len(f), f.index[0].date(), f.index[-1].date(), f["taux"].median()*100,
         (f["taux"] > 0.0005).mean()*100))
