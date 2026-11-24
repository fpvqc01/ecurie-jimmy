"""Nova Scalp Session — M5/M15/H1, sessions Londres+NY, coûts inclus."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ScalpParams:
    ema_fast: int = 20
    ema_slow: int = 50
    atr_n: int = 14
    risk: float = 0.006  # 0.6% / trade
    sl_atr: float = 1.0
    tp_r: float = 1.4
    max_trades_day: int = 8
    cooldown_bars: int = 2
    halt_day: float = 0.028
    initial: float = 100_000.0
    p1_target: float = 0.10
    p2_target: float = 0.05
    flatten_at_phase: bool = True
    # Sessions UTC (approx Londres 7-16, NY 13-20) — overlap inclus
    session1: tuple[int, int] = (7, 16)
    session2: tuple[int, int] = (13, 21)
    # Coûts (fraction prix round-trip approx côté entrée+sortie)
    spread: float = 0.00015  # Or M15 agressif; Nasdaq plus bas en config
    slippage: float = 0.00005
    allow_short: bool = True
    max_bars: int = 50_000


def _ema(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full_like(x, np.nan, dtype=float)
    if len(x) < n:
        return out
    a = 2.0 / (n + 1)
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


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


def in_session(ts: pd.Timestamp, p: ScalpParams) -> bool:
    h = int(ts.hour)
    a, b = p.session1
    c, d = p.session2
    return (a <= h < b) or (c <= h < d)


@dataclass
class Pos:
    side: int  # +1 long / -1 short
    entry: float
    stop: float
    tp: float
    qty: float


def run_scalp(df: pd.DataFrame, p: ScalpParams) -> dict:
    o = df["o"].to_numpy(float)
    h = df["h"].to_numpy(float)
    l = df["l"].to_numpy(float)
    c = df["c"].to_numpy(float)
    ts = pd.to_datetime(df["t"])

    ema_f = _ema(c, p.ema_fast)
    ema_s = _ema(c, p.ema_slow)
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
    last_exit = -10_000
    cost = p.spread + p.slippage

    warmup = max(p.ema_slow, p.atr_n) + 3
    n = min(len(df), p.max_bars)

    for i in range(n):
        d = str(ts.iloc[i])[:10]
        if d != day:
            day = d
            day_start_eq = eq
            day_trades = 0
            halted = False

        if pos is not None:
            mtm = pos.qty * pos.side * (c[i] - pos.entry)
            eq = bal + mtm
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
                # force close on halt
                exit_px = c[i] * (1 - cost if pos.side > 0 else 1 + cost)
                bal += pos.qty * pos.side * (exit_px - pos.entry)
                trades += 1
                last_exit = i
                pos = None
                eq = bal

        # manage open trade
        if pos is not None:
            hit_sl = (l[i] <= pos.stop) if pos.side > 0 else (h[i] >= pos.stop)
            hit_tp = (h[i] >= pos.tp) if pos.side > 0 else (l[i] <= pos.tp)
            exit_px = None
            if hit_sl:
                exit_px = pos.stop * (1 - cost if pos.side > 0 else 1 + cost)
            elif hit_tp:
                exit_px = pos.tp * (1 - cost if pos.side > 0 else 1 + cost)
            if exit_px is not None:
                pnl = pos.qty * pos.side * (exit_px - pos.entry)
                bal += pnl
                trades += 1
                if pnl > 0:
                    wins += 1
                last_exit = i
                pos = None
                eq = bal

        # phase targets
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

        if i < warmup or halted or pos is not None:
            continue
        if day_trades >= p.max_trades_day:
            continue
        if i - last_exit < p.cooldown_bars:
            continue
        if not in_session(ts.iloc[i], p):
            continue
        if np.isnan(ema_f[i]) or np.isnan(ema_s[i]) or np.isnan(atr[i]) or atr[i] <= 0:
            continue

        # Signal: pullback-reprise dans le sens EMA
        long_bias = ema_f[i] > ema_s[i] and c[i] > ema_s[i]
        short_bias = ema_f[i] < ema_s[i] and c[i] < ema_s[i]
        # entrée: close croise ema_fast dans le sens
        long_trig = c[i - 1] <= ema_f[i - 1] and c[i] > ema_f[i] and c[i] > c[i - 1]
        short_trig = c[i - 1] >= ema_f[i - 1] and c[i] < ema_f[i] and c[i] < c[i - 1]

        side = 0
        if long_bias and long_trig:
            side = 1
        elif p.allow_short and short_bias and short_trig:
            side = -1
        if side == 0:
            continue

        sl = p.sl_atr * atr[i]
        entry = c[i] * (1 + cost if side > 0 else 1 - cost)
        risk_cash = eq * p.risk
        qty = risk_cash / sl
        stop = entry - side * sl
        tp = entry + side * p.tp_r * sl
        pos = Pos(side=side, entry=entry, stop=stop, tp=tp, qty=qty)
        day_trades += 1

    days = len({str(t)[:10] for t in ts.iloc[: (pass_i or n - 1) + 1]})
    if passed:
        status = "pass"
    elif dead:
        status = dead
    else:
        status = "timeout"
    return {
        "status": status,
        "days": days,
        "trades": trades,
        "winrate": (wins / trades) if trades else None,
        "final_balance": float(bal),
        "phase": "funded" if passed else phase,
    }
