#!/usr/bin/env python3
"""Écrit nova_ai_bias.txt pour l'EA (BOTH|LONG|SHORT|OFF).

Usage:
  python3 write_bias.py LONG
  python3 write_bias.py   # calcule un biais simple depuis data H1 Or

Copie ensuite le fichier vers MT5 : Terminal\\MQL5\\Files\\nova_ai_bias.txt
et active UseBiasFile=true dans l'EA.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "nova_ai_bias.txt"


def auto_bias() -> str:
    path = ROOT / "data" / "xauusd_60m.csv"
    if not path.exists():
        return "BOTH"
    df = pd.read_csv(path)
    df["t"] = pd.to_datetime(df["t"])
    df = df.sort_values("t").tail(80)
    c = df["c"].astype(float)
    ema20 = c.ewm(span=20, adjust=False).mean()
    ema50 = c.ewm(span=50, adjust=False).mean()
    if ema20.iloc[-1] > ema50.iloc[-1] and c.iloc[-1] > ema50.iloc[-1]:
        return "LONG"
    if ema20.iloc[-1] < ema50.iloc[-1] and c.iloc[-1] < ema50.iloc[-1]:
        return "SHORT"
    return "BOTH"


def main():
    bias = sys.argv[1].upper() if len(sys.argv) > 1 else auto_bias()
    if bias not in {"BOTH", "LONG", "SHORT", "OFF"}:
        raise SystemExit("bias must be BOTH|LONG|SHORT|OFF")
    OUT.write_text(bias + "\n", encoding="utf-8")
    print(f"Wrote {OUT} -> {bias}")
    print("Copy to MT5 MQL5\\Files\\nova_ai_bias.txt and set UseBiasFile=true")


if __name__ == "__main__":
    main()
