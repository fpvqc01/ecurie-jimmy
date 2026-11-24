#!/usr/bin/env python3
"""Génère un dataset ORB labellisé (win/loss) pour le superviseur ML."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from orb_engine import OrbParams, _atr, load_bars

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "ml" / "orb_dataset.csv"


def collect_signals(df: pd.DataFrame, p: OrbParams) -> pd.DataFrame:
    h = df["h"].to_numpy(float)
    l = df["l"].to_numpy(float)
    c = df["c"].to_numpy(float)
    o = df["o"].to_numpy(float)
    ts = pd.to_datetime(df["t"])
    hours = ts.dt.hour.to_numpy()
    atr = _atr(h, l, c, p.atr_n)
    cost = p.spread + p.slippage

    rows = []
    day = str(ts.iloc[0])[:10]
    building = False
    armed = False
    taken = False
    bars_in = 0
    range_hi = range_lo = None

    for i in range(p.atr_n + 5, len(df) - 80):
        d = str(ts.iloc[i])[:10]
        hh = int(hours[i])
        if d != day:
            day = d
            building = armed = taken = False
            bars_in = 0
            range_hi = range_lo = None

        if hh in (p.london_open, p.ny_open) and not building and not armed and not taken:
            building = True
            bars_in = 0
            range_hi, range_lo = h[i], l[i]

        if building:
            range_hi = max(range_hi, h[i])
            range_lo = min(range_lo, l[i])
            bars_in += 1
            if bars_in >= p.range_bars:
                building = False
                armed = True

        if hh >= p.session_end:
            armed = False

        if not armed or taken or np.isnan(atr[i]) or atr[i] <= 0:
            continue

        side = 0
        if c[i] > range_hi:
            side = 1
        elif p.allow_short and c[i] < range_lo:
            side = -1
        if side == 0:
            continue

        entry = c[i] * (1 + cost if side > 0 else 1 - cost)
        stop = (range_lo - p.sl_buffer_atr * atr[i]) if side > 0 else (
            range_hi + p.sl_buffer_atr * atr[i]
        )
        sl = abs(entry - stop)
        if sl <= 0:
            continue
        tp = entry + side * p.tp_r * sl

        # simulate outcome forward
        win = 0
        for j in range(i + 1, min(len(df), i + 200)):
            if side > 0:
                if l[j] <= stop:
                    win = 0
                    break
                if h[j] >= tp:
                    win = 1
                    break
            else:
                if h[j] >= stop:
                    win = 0
                    break
                if l[j] <= tp:
                    win = 1
                    break
            if int(hours[j]) >= p.session_end:
                # close at session end
                px = c[j] * (1 - cost if side > 0 else 1 + cost)
                win = 1 if side * (px - entry) > 0 else 0
                break

        range_w = range_hi - range_lo
        body = abs(c[i] - o[i])
        rows.append(
            {
                "t": ts.iloc[i],
                "hour": hh,
                "side": side,
                "atr": atr[i],
                "range_atr": range_w / atr[i],
                "body_atr": body / atr[i],
                "break_dist_atr": abs(c[i] - (range_hi if side > 0 else range_lo))
                / atr[i],
                "ret_1h": (c[i] / c[max(0, i - 12)] - 1.0) if i >= 12 else 0.0,
                "ret_4h": (c[i] / c[max(0, i - 48)] - 1.0) if i >= 48 else 0.0,
                "win": win,
            }
        )
        taken = True
        armed = False

    return pd.DataFrame(rows)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    p = OrbParams(
        risk=0.018,
        tp_r=1.8,
        range_bars=3,
        spread=0.00020,
        slippage=0.00006,
        halt_day=0.032,
    )
    df = load_bars(DATA / "xauusd_5m.csv")
    ds = collect_signals(df, p)
    ds.to_csv(OUT, index=False)
    rate = float(ds["win"].mean()) if len(ds) else 0
    meta = {"rows": len(ds), "winrate": rate, "path": str(OUT)}
    (OUT.parent / "dataset_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(meta)


if __name__ == "__main__":
    main()
