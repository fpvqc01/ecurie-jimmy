# -*- coding: utf-8 -*-
"""Telecharge et met en cache les donnees H4 :
  - BTC : Binance klines 4h depuis 2017 (historique complet, gratuit)
  - Or (GC=F), Nasdaq (NQ=F), Petrole (CL=F) : Yahoo 60m -> resample 4h
    (limite Yahoo : 730 jours d'intrajournalier)
Tout en UTC. Ecrit des CSV dans le repertoire du script."""
import os, time, requests, pandas as pd

D = os.path.dirname(os.path.abspath(__file__))

def binance_4h(symbole="BTCUSDT", debut="2017-08-01"):
    out, start = [], int(pd.Timestamp(debut, tz="UTC").timestamp() * 1000)
    while True:
        r = requests.get("https://api.binance.com/api/v3/klines",
                         params={"symbol": symbole, "interval": "4h",
                                 "startTime": start, "limit": 1000}, timeout=60)
        r.raise_for_status()
        k = r.json()
        if not k: break
        out += k
        start = k[-1][0] + 1
        if len(k) < 1000: break
        time.sleep(0.15)
    df = pd.DataFrame(out, columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","x"])
    df = df[["t","o","h","l","c"]].astype(float)
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_localize(None)
    return df.drop_duplicates("t").set_index("t").sort_index()

def yahoo_h4(sym):
    """60m par tranches de 180 jours (max 730 j), resample 4h UTC."""
    fin = int(time.time())
    debut_min = fin - 729*86400
    morceaux = []
    t1 = debut_min
    while t1 < fin:
        t2 = min(t1 + 180*86400, fin)
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                         params={"period1": t1, "period2": t2, "interval": "60m"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        res = r.json()["chart"]["result"][0]
        if "timestamp" in res:
            q = res["indicators"]["quote"][0]
            morceaux.append(pd.DataFrame(
                {"t": pd.to_datetime(res["timestamp"], unit="s"),
                 "o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]}))
        t1 = t2
        time.sleep(0.3)
    df = (pd.concat(morceaux).dropna().drop_duplicates("t").set_index("t").sort_index())
    h4 = pd.DataFrame({"o": df["o"].resample("4h").first(),
                       "h": df["h"].resample("4h").max(),
                       "l": df["l"].resample("4h").min(),
                       "c": df["c"].resample("4h").last()}).dropna()
    return h4

if __name__ == "__main__":
    for nom, fn in (("btc_4h", lambda: binance_4h()),
                    ("gc_4h",  lambda: yahoo_h4("GC=F")),
                    ("nq_4h",  lambda: yahoo_h4("NQ=F")),
                    ("cl_4h",  lambda: yahoo_h4("CL=F"))):
        chemin = os.path.join(D, nom + ".csv")
        if os.path.exists(chemin):
            print(nom, ": deja en cache"); continue
        df = fn()
        df.to_csv(chemin)
        bpj = df.groupby(df.index.date).size()
        print("%s : %d barres, %s -> %s, mediane %d barres/jour"
              % (nom, len(df), df.index[0], df.index[-1], bpj.median()))
