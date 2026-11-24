"""Opening Range Breakout — Londres / NY, pour challenge rapide."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class OrbParams:
    # minutes after session open to build range (for M15: 4 bars = 1h)
    range_bars: int = 4
    atr_n: int = 14
    risk: float = 0.012
    sl_buffer_atr: float = 0.2
    tp_r: float = 2.0
    max_trades_day: int = 2
    halt_day: float = 0.030
    initial: float = 100_000.0
    p1_target: float = 0.10
    p2_target: float = 0.05
    flatten_at_phase: bool = True
    # session opens UTC
    london_open: int = 7
    ny_open: int = 13
    session_end: int = 20
    spread: float = 0.00012
    slippage: float = 0.00004
    allow_short: bool = True
    max_bars: int = 80_000


def _atr(h, l, c, n: int) -> np.ndarray:
    prev = np.roll(c, 1)
    prev[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))
    out = np.full_like(tr, np.nan, dtype=float)
    if len(tr) < n:
        return out
    cs = np.cumsum(tr)
    out[n - 1] = cs[n - 1] / n
    for i in range(n, len(tr)):
        out[i] = out[i - 1] + (tr[i] - tr[i - n]) / n
    return out


def load_bars(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["t"] = pd.to_datetime(df["t"])
    return df.sort_values("t").reset_index(drop=True)


@dataclass
class Pos:
    side: int
    entry: float
    stop: float
    tp: float
    qty: float


def run_orb(df: pd.DataFrame, p: OrbParams) -> dict:
    h = df["h"].to_numpy(float)
    l = df["l"].to_numpy(float)
    c = df["c"].to_numpy(float)
    ts = pd.to_datetime(df["t"])
    hours = ts.dt.hour.to_numpy()
    atr = _atr(h, l, c, p.atr_n)

    bal = p.initial
    eq = p.initial
    pos: Pos | None = None
    trades = 0
    wins = 0
    phase = "p1"
    phase_start = p.initial
    day = str(ts.iloc[0])[:10]
    day_start_eq = p.initial
    day_trades = 0
    halted = False
    passed = False
    dead = None
    pass_i = None
    cost = p.spread + p.slippage

    # ORB state per session
    building = False
    range_hi = None
    range_lo = None
    bars_in_range = 0
    armed = False  # ready to break
    taken_session = False

    n = min(len(df), p.max_bars)
    warmup = p.atr_n + 5

    for i in range(n):
        d = str(ts.iloc[i])[:10]
        hh = int(hours[i])
        if d != day:
            day = d
            day_start_eq = eq
            day_trades = 0
            halted = False
            building = False
            armed = False
            taken_session = False
            range_hi = range_lo = None
            bars_in_range = 0

        if pos is not None:
            eq = bal + pos.qty * pos.side * (c[i] - pos.entry)
        else:
            eq = bal

        if eq <= p.initial * 0.90:
            dead = "dead_total"
            break
        if eq <= day_start_eq - 0.05 * p.initial:
            dead = "dead_day"
            break
        if eq <= day_start_eq - p.halt_day * p.initial:
            halted = True
            if pos is not None:
                exit_px = c[i] * (1 - cost if pos.side > 0 else 1 + cost)
                bal += pos.qty * pos.side * (exit_px - pos.entry)
                trades += 1
                pos = None
                eq = bal

        if pos is not None:
            hit_sl = (l[i] <= pos.stop) if pos.side > 0 else (h[i] >= pos.stop)
            hit_tp = (h[i] >= pos.tp) if pos.side > 0 else (l[i] <= pos.tp)
            if hit_sl or hit_tp:
                exit_px = (pos.stop if hit_sl else pos.tp) * (
                    1 - cost if pos.side > 0 else 1 + cost
                )
                pnl = pos.qty * pos.side * (exit_px - pos.entry)
                bal += pnl
                trades += 1
                if pnl > 0:
                    wins += 1
                pos = None
                eq = bal

        if phase == "p1" and bal >= phase_start * (1 + p.p1_target):
            if p.flatten_at_phase and pos is not None:
                exit_px = c[i] * (1 - cost if pos.side > 0 else 1 + cost)
                bal += pos.qty * pos.side * (exit_px - pos.entry)
                trades += 1
                pos = None
                eq = bal
            phase = "p2"
            phase_start = bal
        elif phase == "p2" and bal >= phase_start * (1 + p.p2_target):
            if p.flatten_at_phase and pos is not None:
                exit_px = c[i] * (1 - cost if pos.side > 0 else 1 + cost)
                bal += pos.qty * pos.side * (exit_px - pos.entry)
                trades += 1
                pos = None
                eq = bal
            passed = True
            pass_i = i
            break

        # session lifecycle
        is_open = hh in (p.london_open, p.ny_open)
        if is_open and not building and not armed and not taken_session:
            building = True
            bars_in_range = 0
            range_hi = h[i]
            range_lo = l[i]

        if building:
            range_hi = max(range_hi, h[i])
            range_lo = min(range_lo, l[i])
            bars_in_range += 1
            if bars_in_range >= p.range_bars:
                building = False
                armed = True

        if hh >= p.session_end:
            armed = False
            if pos is not None:
                exit_px = c[i] * (1 - cost if pos.side > 0 else 1 + cost)
                bal += pos.qty * pos.side * (exit_px - pos.entry)
                trades += 1
                pos = None
                eq = bal

        if (
            i < warmup
            or halted
            or pos is not None
            or not armed
            or taken_session
            or day_trades >= p.max_trades_day
        ):
            continue
        if np.isnan(atr[i]) or atr[i] <= 0 or range_hi is None:
            continue

        side = 0
        if c[i] > range_hi:
            side = 1
        elif p.allow_short and c[i] < range_lo:
            side = -1
        if side == 0:
            continue

        # stop beyond other side of range + buffer
        if side > 0:
            stop = range_lo - p.sl_buffer_atr * atr[i]
            entry = c[i] * (1 + cost)
        else:
            stop = range_hi + p.sl_buffer_atr * atr[i]
            entry = c[i] * (1 - cost)
        sl = abs(entry - stop)
        if sl <= 0:
            continue
        qty = (eq * p.risk) / sl
        tp = entry + side * p.tp_r * sl
        pos = Pos(side=side, entry=entry, stop=stop, tp=tp, qty=qty)
        day_trades += 1
        taken_session = True
        armed = False

    days = len({str(t)[:10] for t in ts.iloc[: (pass_i or n - 1) + 1]})
    status = "pass" if passed else (dead or "timeout")
    return {
        "status": status,
        "days": days,
        "trades": trades,
        "winrate": (wins / trades) if trades else None,
        "final_balance": float(bal),
        "phase": "funded" if passed else phase,
    }
