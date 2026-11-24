"""Simulateur FTMO 2-Step minimal (from scratch).

- Objectif de phase jugé sur solde FERMÉ
- Mort journalière : équité vs plancher du jour
- Mort totale : équité vs -10 % du capital initial
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


Phase = Literal["p1", "p2", "funded"]


@dataclass
class FtmoConfig:
    initial: float = 100_000.0
    p1_target: float = 0.10
    p2_target: float = 0.05
    max_day_loss: float = 0.05
    max_total_loss: float = 0.10
    # Coupe-circuits internes (sous les limites FTMO)
    halt_day: float = 0.035
    halt_total: float = 0.08
    min_trading_days: int = 4


@dataclass
class Trade:
    market: str
    entry_i: int
    exit_i: int
    direction: int  # +1 long
    entry: float
    exit: float
    risk_frac: float
    stop: float
    qty: float
    pnl: float


@dataclass
class RunResult:
    status: str  # pass | dead_day | dead_total | timeout
    days: int
    trades: int
    final_balance: float
    phase_reached: str


def _day_key(ts: np.ndarray, i: int) -> str:
    return str(ts[i])[:10]


def simulate_challenge(
    timestamps: np.ndarray,
    equity_curve: np.ndarray,
    balance_curve: np.ndarray,
    trade_count: int,
    cfg: FtmoConfig,
) -> RunResult:
    """equity_curve / balance_curve : indexés comme les barres, base = initial."""
    n = len(equity_curve)
    if n == 0:
        return RunResult("timeout", 0, 0, cfg.initial, "p1")

    day_start_eq = equity_curve[0]
    day_floor = day_start_eq - cfg.max_day_loss * cfg.initial
    halt_day_floor = day_start_eq - cfg.halt_day * cfg.initial
    total_floor = cfg.initial * (1.0 - cfg.max_total_loss)
    halt_total_floor = cfg.initial * (1.0 - cfg.halt_total)

    phase: Phase = "p1"
    phase_start_balance = cfg.initial
    trading_days: set[str] = set()
    last_day = _day_key(timestamps, 0)
    halted_today = False

    for i in range(n):
        d = _day_key(timestamps, i)
        if d != last_day:
            last_day = d
            day_start_eq = equity_curve[i]
            day_floor = day_start_eq - cfg.max_day_loss * cfg.initial
            halt_day_floor = day_start_eq - cfg.halt_day * cfg.initial
            halted_today = False

        eq = equity_curve[i]
        bal = balance_curve[i]
        trading_days.add(d)

        if eq <= total_floor or eq <= halt_total_floor:
            return RunResult(
                "dead_total",
                len(trading_days),
                trade_count,
                float(bal),
                phase,
            )
        if eq <= day_floor:
            return RunResult(
                "dead_day",
                len(trading_days),
                trade_count,
                float(bal),
                phase,
            )
        if eq <= halt_day_floor:
            halted_today = True

        if phase == "p1" and bal >= phase_start_balance * (1.0 + cfg.p1_target):
            if len(trading_days) >= cfg.min_trading_days:
                phase = "p2"
                phase_start_balance = bal
        elif phase == "p2" and bal >= phase_start_balance * (1.0 + cfg.p2_target):
            if len(trading_days) >= cfg.min_trading_days:
                return RunResult(
                    "pass",
                    len(trading_days),
                    trade_count,
                    float(bal),
                    "funded",
                )

        _ = halted_today  # reserved for strategy-side halt hooks

    return RunResult(
        "timeout",
        len(trading_days),
        trade_count,
        float(balance_curve[-1]),
        phase,
    )
