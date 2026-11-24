"""Moteur Nova v3 : tendance EMA + entrée croisement, TP/SL ATR, Or+Nasdaq."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class NovaParams:
    gold_ema_fast: int = 20
    gold_ema_slow: int = 100
    gold_atr: int = 14
    gold_risk: float = 0.012
    gold_sl_atr: float = 1.7
    gold_tp_r: float = 2.4

    nq_ema_fast: int = 20
    nq_ema_slow: int = 100
    nq_atr: int = 14
    nq_risk: float = 0.009
    nq_sl_atr: float = 1.6
    nq_tp_r: float = 2.2

    max_positions: int = 2
    turbo_mult: float = 1.15
    turbo_until: float = 0.04

    gold_spread: float = 0.00012
    nq_spread: float = 0.00008
    gold_swap_year: float = -0.078
    nq_swap_year: float = -0.078

    flatten_at_phase: bool = True
    p1_target: float = 0.10
    p2_target: float = 0.05
    halt_day: float = 0.028
    initial: float = 100_000.0
    cooldown_bars: int = 2
    max_bars: int = 4500  # ~750 jours H4


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


def _ema(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full_like(x, np.nan, dtype=float)
    if len(x) < n:
        return out
    alpha = 2.0 / (n + 1)
    out[n - 1] = np.mean(x[:n])
    for i in range(n, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out


def load_h4(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["t"] = pd.to_datetime(df["t"])
    return df.sort_values("t").reset_index(drop=True)


def align_markets(gold: pd.DataFrame, nq: pd.DataFrame) -> pd.DataFrame:
    g = gold.rename(columns={"o": "g_o", "h": "g_h", "l": "g_l", "c": "g_c"})
    q = nq.rename(columns={"o": "q_o", "h": "q_h", "l": "q_l", "c": "q_c"})
    return pd.merge(g, q, on="t", how="inner").reset_index(drop=True)


@dataclass
class Pos:
    market: str
    entry: float
    stop: float
    tp: float
    qty: float


def run_path(df: pd.DataFrame, p: NovaParams) -> dict:
    g_c = df["g_c"].to_numpy(float)
    g_h = df["g_h"].to_numpy(float)
    g_l = df["g_l"].to_numpy(float)
    q_c = df["q_c"].to_numpy(float)
    q_h = df["q_h"].to_numpy(float)
    q_l = df["q_l"].to_numpy(float)
    ts = df["t"].to_numpy()

    g_atr = _atr(g_h, g_l, g_c, p.gold_atr)
    q_atr = _atr(q_h, q_l, q_c, p.nq_atr)
    g_ef = _ema(g_c, p.gold_ema_fast)
    g_es = _ema(g_c, p.gold_ema_slow)
    q_ef = _ema(q_c, p.nq_ema_fast)
    q_es = _ema(q_c, p.nq_ema_slow)

    bal = p.initial
    eq = p.initial
    positions: list[Pos] = []
    trades = 0
    phase = "p1"
    phase_start = p.initial
    day = str(ts[0])[:10]
    day_start_eq = p.initial
    halted = False
    passed = False
    dead = None
    pass_i = None
    last_exit = {"gold": -10_000, "nq": -10_000}

    swap_g = p.gold_swap_year / (365.0 * 6.0)
    swap_q = p.nq_swap_year / (365.0 * 6.0)
    warmup = max(p.gold_ema_slow, p.nq_ema_slow, p.gold_atr, p.nq_atr) + 2
    n = min(len(df), p.max_bars)

    for i in range(n):
        d = str(ts[i])[:10]
        if d != day:
            day = d
            day_start_eq = eq
            halted = False

        mtm = sum(
            pos.qty * ((g_c[i] if pos.market == "gold" else q_c[i]) - pos.entry)
            for pos in positions
        )
        eq = bal + mtm

        if eq <= p.initial * 0.90:
            dead = "dead_total"
            break
        if eq <= day_start_eq - 0.05 * p.initial:
            dead = "dead_day"
            break
        if eq <= day_start_eq - p.halt_day * p.initial:
            halted = True

        still: list[Pos] = []
        for pos in positions:
            lo = g_l[i] if pos.market == "gold" else q_l[i]
            hi = g_h[i] if pos.market == "gold" else q_h[i]
            spr = p.gold_spread if pos.market == "gold" else p.nq_spread
            exit_px = None
            if lo <= pos.stop:
                exit_px = min(pos.stop, hi) * (1.0 - spr)
            elif hi >= pos.tp:
                exit_px = max(pos.tp, lo) * (1.0 - spr)
            if exit_px is not None:
                bal += pos.qty * (exit_px - pos.entry)
                trades += 1
                last_exit[pos.market] = i
            else:
                px = g_c[i] if pos.market == "gold" else q_c[i]
                bal += abs(pos.qty * px) * (
                    swap_g if pos.market == "gold" else swap_q
                )
                still.append(pos)
        positions = still
        mtm = sum(
            pos.qty * ((g_c[i] if pos.market == "gold" else q_c[i]) - pos.entry)
            for pos in positions
        )
        eq = bal + mtm

        if phase == "p1" and bal >= phase_start * (1.0 + p.p1_target):
            if p.flatten_at_phase and positions:
                for pos in positions:
                    px = g_c[i] if pos.market == "gold" else q_c[i]
                    spr = p.gold_spread if pos.market == "gold" else p.nq_spread
                    bal += pos.qty * (px * (1.0 - spr) - pos.entry)
                    trades += 1
                    last_exit[pos.market] = i
                positions = []
                eq = bal
            phase = "p2"
            phase_start = bal
        elif phase == "p2" and bal >= phase_start * (1.0 + p.p2_target):
            if p.flatten_at_phase and positions:
                for pos in positions:
                    px = g_c[i] if pos.market == "gold" else q_c[i]
                    spr = p.gold_spread if pos.market == "gold" else p.nq_spread
                    bal += pos.qty * (px * (1.0 - spr) - pos.entry)
                    trades += 1
                positions = []
                eq = bal
            passed = True
            pass_i = i
            break

        if i < warmup or halted:
            continue

        gain = (eq - p.initial) / p.initial
        mult = p.turbo_mult if gain < p.turbo_until else 1.0

        def try_enter(market: str):
            if len(positions) >= p.max_positions:
                return
            if any(pos.market == market for pos in positions):
                return
            if i - last_exit[market] < p.cooldown_bars:
                return
            if i < 2:
                return

            if market == "gold":
                risk = p.gold_risk * mult
                if risk <= 0:
                    return
                if any(np.isnan([g_ef[i], g_es[i], g_atr[i], g_ef[i - 1]])):
                    return
                # Prix croise au-dessus de l'EMA rapide, régime EMA lente haussier
                cross = g_c[i - 1] <= g_ef[i - 1] and g_c[i] > g_ef[i]
                regime = g_c[i] > g_es[i] and g_ef[i] > g_es[i]
                if not (cross and regime):
                    return
                atr = g_atr[i]
                sl = p.gold_sl_atr * atr
                entry = g_c[i] * (1.0 + p.gold_spread)
                tp_r = p.gold_tp_r
            else:
                risk = p.nq_risk * mult
                if risk <= 0:
                    return
                if any(np.isnan([q_ef[i], q_es[i], q_atr[i], q_ef[i - 1]])):
                    return
                cross = q_c[i - 1] <= q_ef[i - 1] and q_c[i] > q_ef[i]
                regime = q_c[i] > q_es[i] and q_ef[i] > q_es[i]
                if not (cross and regime):
                    return
                atr = q_atr[i]
                sl = p.nq_sl_atr * atr
                entry = q_c[i] * (1.0 + p.nq_spread)
                tp_r = p.nq_tp_r

            if sl <= 0:
                return
            qty = (eq * risk) / sl
            positions.append(
                Pos(market=market, entry=entry, stop=entry - sl, tp=entry + tp_r * sl, qty=qty)
            )

        try_enter("gold")
        try_enter("nq")

    days = len({str(t)[:10] for t in ts[: (pass_i or n - 1) + 1]})
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
        "final_balance": float(bal),
        "phase": "funded" if passed else phase,
    }


def challenge_starts(df: pd.DataFrame, step_bars: int = 18) -> list[int]:
    warmup = 140
    return list(range(warmup, max(warmup + 1, len(df) - 500), step_bars))
