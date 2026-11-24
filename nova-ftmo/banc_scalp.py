#!/usr/bin/env python3
"""Banc Nova Scalp — cible challenge rapide (~30–45 j)."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from scalp_engine import ScalpParams, load_bars, run_scalp

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def eval_path(df, params: ScalpParams, starts: list[int], horizon_bars: int) -> dict:
    results = []
    for s in starts:
        sub = df.iloc[s : s + horizon_bars].reset_index(drop=True)
        if len(sub) < max(params.ema_slow + 50, 200):
            continue
        results.append(run_scalp(sub, params))
    n = len(results)
    if not n:
        return {"n": 0}
    passes = [r for r in results if r["status"] == "pass"]
    deads = [r for r in results if str(r["status"]).startswith("dead")]
    pr = len(passes) / n
    med = statistics.median(r["days"] for r in passes) if passes else None
    fast = sum(1 for r in passes if r["days"] <= 30)
    fast45 = sum(1 for r in passes if r["days"] <= 45)
    fail = [r["days"] for r in results if r["status"] != "pass"]
    med_f = statistics.median(fail) if fail else med
    esp = (med + med_f * (1 / pr - 1)) if passes and pr > 0 else None
    return {
        "n": n,
        "pass_rate": round(pr, 4),
        "median_days_pass": med,
        "pct_pass_le_30d": round(fast / n, 4),
        "pct_pass_le_45d": round(fast45 / n, 4),
        "expected_days": round(esp, 1) if esp else None,
        "dead_rate": round(len(deads) / n, 4),
        "timeout_rate": round(sum(r["status"] == "timeout" for r in results) / n, 4),
        "avg_trades_pass": round(statistics.mean(r["trades"] for r in passes), 1)
        if passes
        else None,
    }


def starts_for(df, step: int, warmup: int = 120) -> list[int]:
    return list(range(warmup, max(warmup + 1, len(df) - 50), step))


CONFIGS = {
    "m15_base": ScalpParams(spread=0.00018, slippage=0.00006, risk=0.006, tp_r=1.4),
    "m15_fast": ScalpParams(
        spread=0.00018,
        slippage=0.00006,
        risk=0.010,
        tp_r=1.2,
        sl_atr=0.9,
        max_trades_day=12,
        halt_day=0.030,
        cooldown_bars=1,
    ),
    "m15_sprint": ScalpParams(
        spread=0.00018,
        slippage=0.00006,
        risk=0.014,
        tp_r=1.15,
        sl_atr=0.85,
        max_trades_day=14,
        halt_day=0.032,
        cooldown_bars=1,
    ),
    "m15_gold_only_agg": ScalpParams(
        spread=0.00018,
        slippage=0.00006,
        risk=0.012,
        tp_r=1.25,
        sl_atr=0.9,
        max_trades_day=10,
        allow_short=True,
        halt_day=0.030,
    ),
    "h1_fast": ScalpParams(
        spread=0.00012,
        slippage=0.00004,
        risk=0.012,
        tp_r=1.5,
        sl_atr=1.2,
        max_trades_day=6,
        ema_slow=40,
        halt_day=0.030,
        cooldown_bars=1,
    ),
    "h1_sprint": ScalpParams(
        spread=0.00012,
        slippage=0.00004,
        risk=0.018,
        tp_r=1.3,
        sl_atr=1.1,
        max_trades_day=8,
        ema_slow=40,
        halt_day=0.032,
        cooldown_bars=1,
    ),
    "h1_blitz": ScalpParams(
        spread=0.00012,
        slippage=0.00004,
        risk=0.022,
        tp_r=1.2,
        sl_atr=1.0,
        max_trades_day=10,
        ema_slow=35,
        halt_day=0.035,
        cooldown_bars=0,
    ),
}


def main():
    report = {}

    # --- M15 gold (~60d) : horizon ~30-45 trading days ≈ 30*26 bars M15/jour ≈ 780 ; use 1200
    gold_m15 = load_bars(DATA / "xauusd_15m.csv")
    nq_m15 = load_bars(DATA / "us100_15m.csv")
    print(f"M15 gold={len(gold_m15)} nq={len(nq_m15)}")

    for label, df, cfgs, step, horizon in [
        (
            "xau_m15",
            gold_m15,
            ["m15_base", "m15_fast", "m15_sprint", "m15_gold_only_agg"],
            48,
            1400,
        ),
        (
            "us100_m15",
            nq_m15,
            ["m15_base", "m15_fast", "m15_sprint"],
            48,
            1400,
        ),
        (
            "xau_h1",
            load_bars(DATA / "xauusd_60m.csv"),
            ["h1_fast", "h1_sprint", "h1_blitz"],
            24,
            800,
        ),
        (
            "us100_h1",
            load_bars(DATA / "us100_60m.csv"),
            ["h1_fast", "h1_sprint", "h1_blitz"],
            24,
            800,
        ),
    ]:
        st = starts_for(df, step=step)
        print(f"\n=== {label} starts={len(st)} horizon_bars={horizon} ===")
        report[label] = {}
        for name in cfgs:
            # Nasdaq spreads un peu meilleurs
            p = CONFIGS[name]
            if "us100" in label:
                p = ScalpParams(**{**p.__dict__, "spread": p.spread * 0.6})
            stats = eval_path(df, p, st, horizon)
            report[label][name] = stats
            print(
                f"{name:18} pass={stats.get('pass_rate')} med={stats.get('median_days_pass')} "
                f"<=30={stats.get('pct_pass_le_30d')} <=45={stats.get('pct_pass_le_45d')} "
                f"dead={stats.get('dead_rate')} to={stats.get('timeout_rate')} "
                f"esp={stats.get('expected_days')}"
            )

    # Ranking: maximize pct_pass_le_45d, then pass_rate, then minimize dead
    flat = []
    for label, cfgs in report.items():
        for name, st in cfgs.items():
            if not st.get("n"):
                continue
            flat.append(
                (
                    st.get("pct_pass_le_30d") or 0,
                    st.get("pct_pass_le_45d") or 0,
                    st.get("pass_rate") or 0,
                    -(st.get("dead_rate") or 1),
                    label,
                    name,
                    st,
                )
            )
    flat.sort(reverse=True)
    print("\n=== TOP pour objectif ~30j (tri ≤30j puis ≤45j puis pass) ===")
    for row in flat[:12]:
        print(
            f"{row[4]}/{row[5]}: <=30={row[0]} <=45={row[1]} pass={row[2]} "
            f"dead={row[6].get('dead_rate')} med={row[6].get('median_days_pass')}"
        )

    best = flat[0]
    locked = {
        "market": best[4],
        "config": best[5],
        "stats": best[6],
        "params": CONFIGS[best[5]].__dict__,
    }
    (ROOT / "resultats_scalp.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "BEST_SCALP.json").write_text(json.dumps(locked, indent=2), encoding="utf-8")
    print(f"\nLOCKED {best[4]}/{best[5]}")
    print(json.dumps(locked, indent=2))


if __name__ == "__main__":
    main()
