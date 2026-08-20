# -*- coding: utf-8 -*-
"""DONNEES H4 SUR 10 ANS (21 aout) pour completer le backtest H4 :
  - Or (XAUUSD), Petrole WTI (LIGHTCMDUSD), Nasdaq 100 (USATECHIDXUSD)
    depuis Dukascopy (fichiers publics bi5, H1 par mois, sans compte)
  - BTC : Bitstamp 4h (2015-2017) + Binance 4h (2017-2026, deja en cache)
Le tout resample en H4 UTC, ecrit d10h4_*.csv."""
import os, io, time, lzma, struct, requests, pandas as pd, numpy as np
from datetime import datetime, timezone

D = os.path.dirname(os.path.abspath(__file__))
DEBUT_AN, FIN_AN = 2015, 2026

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Referer": "https://freeserv.dukascopy.com/",
                        "Origin": "https://freeserv.dukascopy.com"})

def duka_mois(instr, an, mois0):
    url = ("https://datafeed.dukascopy.com/datafeed/%s/%04d/%02d/BID_candles_hour_1.bi5"
           % (instr, an, mois0))
    r = None
    for essai in range(8):
        try:
            r = SESSION.get(url, timeout=90)
            if r.status_code == 200: break
            if r.status_code == 404: return None      # mois vraiment absent
        except requests.exceptions.RequestException:
            pass
        time.sleep(5 * (essai + 1))                   # 503/erreur : on laisse refroidir
    if r is None or r.status_code != 200 or len(r.content) == 0:
        return None
    try:
        brut = lzma.decompress(r.content)
    except lzma.LZMAError:
        brut = lzma.decompress(r.content, format=lzma.FORMAT_ALONE)
    n = len(brut) // 24
    base = datetime(an, mois0 + 1, 1, tzinfo=timezone.utc).timestamp()
    lignes = []
    for i in range(n):
        dt_s, o, c, l, h, v = struct.unpack(">IIIIIf", brut[i*24:(i+1)*24])
        lignes.append((base + dt_s, o, h, l, c))
    return lignes

def duka(instr, nom, echelle):
    chemin = os.path.join(D, "d10h4_%s.csv" % nom)
    if os.path.exists(chemin):
        return pd.read_csv(chemin, index_col=0, parse_dates=True)
    tout, rates = [], 0
    for an in range(DEBUT_AN, FIN_AN + 1):
        for m0 in range(12):
            if an == FIN_AN and m0 > 7: break
            lg = duka_mois(instr, an, m0)
            if lg: tout += lg
            else: rates += 1
            time.sleep(1.2)
        print("  %s %d : cumul %d bougies H1 (%d mois manquants)" % (nom, an, len(tout), rates), flush=True)
    if not tout:
        return pd.DataFrame(columns=["o", "h", "l", "c"])
    df = pd.DataFrame(tout, columns=["t", "o", "h", "l", "c"])
    df["t"] = pd.to_datetime(df["t"], unit="s")
    for col in ("o", "h", "l", "c"): df[col] = df[col] / echelle
    df = df[df["c"] > 0].drop_duplicates("t").set_index("t").sort_index()
    h4 = pd.DataFrame({"o": df["o"].resample("4h").first(), "h": df["h"].resample("4h").max(),
                       "l": df["l"].resample("4h").min(),  "c": df["c"].resample("4h").last()}).dropna()
    h4.to_csv(chemin)
    return h4

def bitstamp_h4(debut, fin):
    out, start = [], int(pd.Timestamp(debut).timestamp())
    fin_ts = int(pd.Timestamp(fin).timestamp())
    while start < fin_ts:
        r = requests.get("https://www.bitstamp.net/api/v2/ohlc/btcusd/",
                         params={"step": 14400, "limit": 1000, "start": start}, timeout=60)
        r.raise_for_status()
        k = r.json()["data"]["ohlc"]
        if not k: break
        out += k
        start = int(k[-1]["timestamp"]) + 14400
        time.sleep(0.2)
    df = pd.DataFrame(out)
    df["t"] = pd.to_datetime(df["timestamp"].astype(int), unit="s")
    for col in ("open", "high", "low", "close"): df[col] = df[col].astype(float)
    df = df.rename(columns={"open": "o", "high": "h", "low": "l", "close": "c"})
    return df[["t", "o", "h", "l", "c"]].drop_duplicates("t").set_index("t").sort_index()

if __name__ == "__main__":
    gc = duka("XAUUSD", "gc", 1000.0)
    print("Or Dukascopy H4      : %6d barres, %s -> %s, dernier prix %.0f"
          % (len(gc), gc.index[0].date(), gc.index[-1].date(), gc["c"].iloc[-1]))
    for instr, nom in (("LIGHTCMDUSD", "cl"), ("USATECHIDXUSD", "nq")):
        df = duka(instr, nom, 1000.0)
        if len(df):
            print("%s Dukascopy H4 : %6d barres, %s -> %s, dernier prix %.1f"
                  % (nom, len(df), df.index[0].date(), df.index[-1].date(), df["c"].iloc[-1]))
        else:
            print("%s : VIDE -- instrument ou reseau a verifier" % nom)
    chemin = os.path.join(D, "d10h4_btc.csv")
    if not os.path.exists(chemin):
        b1 = bitstamp_h4("2015-08-01", "2017-09-01")
        b2 = pd.read_csv(os.path.join(D, "btc_4h.csv"), index_col=0, parse_dates=True)
        btc = pd.concat([b1[b1.index < b2.index[0]], b2]).sort_index()
        btc = btc[~btc.index.duplicated()]
        btc.to_csv(chemin)
    btc = pd.read_csv(chemin, index_col=0, parse_dates=True)
    print("BTC Bitstamp+Binance : %6d barres, %s -> %s, dernier prix %.0f"
          % (len(btc), btc.index[0].date(), btc.index[-1].date(), btc["c"].iloc[-1]))
    # controle de coherence vs Yahoo daily (10 ans deja en cache)
    controles = [("gc", gc)] + [(n, duka(i, n, 1000.0)) for i, n in (("LIGHTCMDUSD","cl"),("USATECHIDXUSD","nq"))]
    for nom, df in controles:
        y = pd.read_csv(os.path.join(D, "d10_%s.csv" % nom), index_col=0, parse_dates=True)
        dj = df["c"].resample("1D").last().dropna()
        commun = dj.index.intersection(y.index)
        corr = np.corrcoef(dj.loc[commun], y.loc[commun, "c"])[0, 1]
        ratio = (dj.loc[commun] / y.loc[commun, "c"]).median()
        print("  controle %s : correlation %.4f avec Yahoo, ratio median %.3f (%d jours communs)"
              % (nom, corr, ratio, len(commun)))
