#!/usr/bin/env python3
"""Banc ORB session — chasse médiane ≤30–45 j."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from orb_engine import OrbParams, load_bars, run_orb

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def eval_cfg(df, p, starts, horizon):
    results = []
    for s in starts:
        sub = df.iloc[s : s + horizon].reset_index(drop=True)
        if len(sub) < 200:
            continue
        results.append(run_orb(sub, p))
    n = len(results)
    if not n:
        return {"n": 0}
    passes = [r for r in results if r["status"] == "pass"]
    deads = [r for r in results if str(r["status"]).startswith("dead")]
    pr = len(passes) / n
    med = statistics.median(r["days"] for r in passes) if passes else None
    return {
        "n": n,
        "pass_rate": round(pr, 4),
        "median_days_pass": med,
        "pct_pass_le_30d": round(sum(r["days"] <= 30 for r in passes) / n, 4),
        "pct_pass_le_45d": round(sum(r["days"] <= 45 for r in passes) / n, 4),
        "dead_rate": round(len(deads) / n, 4),
        "timeout_rate": round(sum(r["status"] == "timeout" for r in results) / n, 4),
        "avg_trades_pass": round(statistics.mean(r["trades"] for r in passes), 1)
        if passes
        else None,
        "avg_winrate_pass": round(
            statistics.mean(r["winrate"] for r in passes if r["winrate"] is not None), 3
        )
        if passes
        else None,
    }


def main():
    configs = {
        "orb_base": OrbParams(),
        "orb_fast": OrbParams(risk=0.018, tp_r=1.8, range_bars=3, halt_day=0.032),
        "orb_sprint": OrbParams(
            risk=0.025,
            tp_r=1.6,
            range_bars=3,
            sl_buffer_atr=0.15,
            halt_day=0.035,
            max_trades_day=3,
        ),
        "orb_long_only": OrbParams(risk=0.015, tp_r=2.5, range_bars=4, allow_short=False),
        "orb_blitz": OrbParams(
            risk=0.030,
            tp_r=1.5,
            range_bars=2,
            sl_buffer_atr=0.1,
            halt_day=0.038,
            max_trades_day=4,
        ),
    }

    report = {}
    jobs = [
        ("xau_m15", DATA / "xauusd_15m.csv", 36, 1600, 0.00018),
        ("us100_m15", DATA / "us100_15m.csv", 36, 1600, 0.00010),
        ("xau_h1", DATA / "xauusd_60m.csv", 18, 900, 0.00012),
        ("us100_h1", DATA / "us100_60m.csv", 18, 900, 0.00008),
        ("xau_m5", DATA / "xauusd_5m.csv", 80, 4000, 0.00020),
        ("us100_m5", DATA / "us100_5m.csv", 80, 4000, 0.00012),
    ]

    for label, path, step, horizon, spread in jobs:
        df = load_bars(path)
        starts = list(range(80, max(81, len(df) - 40), step))
        print(f"\n=== {label} n={len(df)} starts={len(starts)} ===")
        report[label] = {}
        for name, base in configs.items():
            p = OrbParams(**{**base.__dict__, "spread": spread})
            # M5/M15 range_bars: for H1 use fewer
            if "h1" in label:
                p = OrbParams(**{**p.__dict__, "range_bars": max(1, p.range_bars // 2 or 1)})
            st = eval_cfg(df, p, starts, horizon)
            report[label][name] = st
            print(
                f"{name:14} pass={st.get('pass_rate')} med={st.get('median_days_pass')} "
                f"<=30={st.get('pct_pass_le_30d')} <=45={st.get('pct_pass_le_45d')} "
                f"dead={st.get('dead_rate')} to={st.get('timeout_rate')} wr={st.get('avg_winrate_pass')}"
            )

    flat = []
    for label, m in report.items():
        for name, st in m.items():
            flat.append(
                (
                    st.get("pct_pass_le_30d") or 0,
                    st.get("pass_rate") or 0,
                    -(st.get("dead_rate") or 1),
                    label,
                    name,
                    st,
                )
            )
    flat.sort(reverse=True)
    print("\n=== TOP ≤30j ===")
    for row in flat[:15]:
        print(
            f"{row[3]}/{row[4]} <=30={row[0]} pass={row[1]} dead={-row[2]} med={row[5].get('median_days_pass')}"
        )

    best = flat[0]
    locked = {"market": best[3], "config": best[4], "stats": best[5]}
    (ROOT / "resultats_orb.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "BEST_ORB.json").write_text(json.dumps(locked, indent=2), encoding="utf-8")
    print("\nLOCKED", locked)


if __name__ == "__main__":
    main()
