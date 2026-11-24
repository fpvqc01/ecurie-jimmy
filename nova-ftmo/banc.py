#!/usr/bin/env python3
"""Banc Nova v3."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from engine import NovaParams, align_markets, challenge_starts, load_h4, run_path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "donnees"


def eval_config(df, params: NovaParams, starts: list[int]) -> dict:
    results = []
    for s in starts:
        sub = df.iloc[s : s + params.max_bars].reset_index(drop=True)
        if len(sub) < 300:
            continue
        results.append(run_path(sub, params))
    n = len(results)
    if not n:
        return {"n": 0}
    passes = [r for r in results if r["status"] == "pass"]
    deads = [r for r in results if r["status"].startswith("dead")]
    pr = len(passes) / n
    med = statistics.median(r["days"] for r in passes) if passes else None
    fail = [r["days"] for r in results if r["status"] != "pass"]
    med_f = statistics.median(fail) if fail else med
    esp = (med + med_f * (1 / pr - 1)) if passes and pr > 0 else None
    return {
        "n": n,
        "pass_rate": round(pr, 4),
        "median_days_pass": med,
        "expected_days": round(esp, 1) if esp else None,
        "dead_rate": round(len(deads) / n, 4),
        "timeout_rate": round(sum(r["status"] == "timeout" for r in results) / n, 4),
        "avg_trades_pass": round(statistics.mean(r["trades"] for r in passes), 1)
        if passes
        else None,
    }


CONFIGS = {
    "nova_v3_D": NovaParams(
        gold_risk=0.010,
        nq_risk=0.008,
        turbo_mult=1.0,
        halt_day=0.024,
        gold_tp_r=2.8,
        nq_tp_r=2.5,
        gold_sl_atr=1.8,
        nq_sl_atr=1.7,
        cooldown_bars=3,
    ),
    "v3_base": NovaParams(),
    "v3_faster": NovaParams(
        gold_risk=0.015, nq_risk=0.011, turbo_mult=1.25, gold_tp_r=2.0, nq_tp_r=1.8
    ),
    "v3_safer": NovaParams(
        gold_risk=0.009,
        nq_risk=0.007,
        turbo_mult=1.0,
        halt_day=0.025,
        gold_tp_r=2.8,
        nq_tp_r=2.5,
    ),
}


def main():
    full = align_markets(load_h4(DATA / "d10h4_gc.csv"), load_h4(DATA / "d10h4_nq.csv"))
    recent = full.loc[full["t"] >= "2021-01-01"].reset_index(drop=True)
    print(f"Barres {len(full)}")
    report = {}
    for wname, wdf in (("2015_2026", full), ("2021_2026", recent)):
        starts = challenge_starts(wdf, step_bars=36)
        print(f"\n=== {wname} starts={len(starts)} ===")
        report[wname] = {}
        for name, p in CONFIGS.items():
            st = eval_config(wdf, p, starts)
            report[wname][name] = st
            print(
                f"{name:14} pass={st['pass_rate']} med={st['median_days_pass']} "
                f"esp={st['expected_days']} dead={st['dead_rate']} to={st['timeout_rate']} "
                f"trades={st['avg_trades_pass']}"
            )
    (ROOT / "resultats_banc.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    # pick best by 10y pass then expected
    rows = []
    for name in CONFIGS:
        a, b = report["2015_2026"][name], report["2021_2026"][name]
        rows.append((a["pass_rate"], -(a["expected_days"] or 9e9), name, a, b))
    rows.sort(reverse=True)
    best = rows[0][2]
    (ROOT / "BEST_CONFIG.txt").write_text(best + "\n", encoding="utf-8")
    print(f"\nRetenue: {best}")
    print(json.dumps(report["2015_2026"][best], indent=2))


if __name__ == "__main__":
    main()
