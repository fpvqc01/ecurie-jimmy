#!/usr/bin/env python3
"""Télécharge Or/Nasdaq M5/M15/H1 via Yahoo Finance → nova-ftmo/data/."""

from pathlib import Path

import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent / "data"


def flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    df = df.reset_index()
    dtcol = df.columns[0]
    df = df.rename(
        columns={
            dtcol: "t",
            "open": "o",
            "high": "h",
            "low": "l",
            "close": "c",
            "volume": "v",
        }
    )
    df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert(None)
    return df[["t", "o", "h", "l", "c", "v"]].dropna()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("GC=F", "xauusd", "15m", "60d"),
        ("NQ=F", "us100", "15m", "60d"),
        ("GC=F", "xauusd", "5m", "60d"),
        ("NQ=F", "us100", "5m", "60d"),
        ("GC=F", "xauusd", "60m", "730d"),
        ("NQ=F", "us100", "60m", "730d"),
    ]
    for sym, name, interval, period in jobs:
        raw = yf.download(
            sym, interval=interval, period=period, progress=False, auto_adjust=True
        )
        if raw is None or len(raw) == 0:
            print("FAIL", name, interval)
            continue
        flat = flatten(raw)
        path = OUT / f"{name}_{interval}.csv"
        flat.to_csv(path, index=False)
        print("OK", path.name, len(flat), flat["t"].iloc[0], "->", flat["t"].iloc[-1])


if __name__ == "__main__":
    main()
