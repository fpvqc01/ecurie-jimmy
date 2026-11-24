#!/usr/bin/env python3
"""Sweep risque / TP / halt pour trouver pass élevé."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from engine import NovaParams, align_markets, challenge_starts, load_h4, run_path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "donnees"


def eval_config(df, params, starts):
    results = []
    for s in starts:
        sub = df.iloc[s : s + 2800].reset_index(drop=True)
        if len(sub) < 250:
            continue
        results.append(run_path(sub, params))
    n = len(results)
    passes = [r for r in results if r["status"] == "pass"]
    deads = [r for r in results if r["status"].startswith("dead")]
    pr = len(passes) / n if n else 0
    med = statistics.median(r["days"] for r in passes) if passes else None
    fail = [r["days"] for r in results if r["status"] != "pass"]
    med_f = statistics.median(fail) if fail else med
    esp = (med + med_f * (1 / pr - 1)) if passes and pr > 0 else None
    return {
        "n": n,
        "pass_rate": round(pr, 4),
        "median_days_pass": med,
        "expected_days": round(esp, 1) if esp else None,
        "dead_rate": round(len(deads) / n, 4) if n else None,
        "timeout_rate": round(sum(r["status"] == "timeout" for r in results) / n, 4)
        if n
        else None,
    }


def main():
    full = align_markets(load_h4(DATA / "d10h4_gc.csv"), load_h4(DATA / "d10h4_nq.csv"))
    recent = full.loc[full["t"] >= "2021-01-01"].reset_index(drop=True)
    starts_full = challenge_starts(full, step_bars=36)
    starts_rec = challenge_starts(recent, step_bars=36)

    grid = []
    for g_risk in (0.008, 0.010, 0.012):
        for n_risk in (0.006, 0.008, 0.010):
            for tp in (1.8, 2.2, 2.6):
                for halt in (0.025, 0.030):
                    for turbo in (1.0, 1.15):
                        grid.append(
                            NovaParams(
                                gold_risk=g_risk,
                                nq_risk=n_risk,
                                gold_tp_r=tp,
                                nq_tp_r=tp - 0.2,
                                turbo_mult=turbo,
                                halt_day=halt,
                                cooldown_bars=4,
                            )
                        )

    rows = []
    print(f"Grid {len(grid)} configs, starts {len(starts_full)}/{len(starts_rec)}")
    for i, p in enumerate(grid):
        a = eval_config(full, p, starts_full)
        # skip expensive recent if clearly dead
        if a["pass_rate"] < 0.35:
            continue
        b = eval_config(recent, p, starts_rec)
        row = {
            "gold_risk": p.gold_risk,
            "nq_risk": p.nq_risk,
            "tp": p.gold_tp_r,
            "halt": p.halt_day,
            "turbo": p.turbo_mult,
            "y10": a,
            "y21": b,
        }
        rows.append(row)
        print(
            f"[{i+1}/{len(grid)}] g={p.gold_risk} n={p.nq_risk} tp={p.gold_tp_r} "
            f"h={p.halt_day} t={p.turbo_mult} | "
            f"10y pass={a['pass_rate']} med={a['median_days_pass']} dead={a['dead_rate']} | "
            f"21 pass={b['pass_rate']} med={b['median_days_pass']}"
        )

    # rank
    def ok(r):
        return r["y10"]["pass_rate"] >= 0.55 and r["y21"]["pass_rate"] >= 0.50

    good = [r for r in rows if ok(r)]
    good.sort(key=lambda r: r["y10"]["expected_days"] or 9e9)
    print(f"\nConfigs passantes (>=55%/50%): {len(good)}")
    for r in good[:10]:
        print(r)

    # fallback: best pass rate
    rows.sort(key=lambda r: (-r["y10"]["pass_rate"], r["y10"]["expected_days"] or 9e9))
    print("\nTop pass rate:")
    for r in rows[:8]:
        print(
            f"g={r['gold_risk']} n={r['nq_risk']} tp={r['tp']} h={r['halt']} t={r['turbo']} "
            f"pass={r['y10']['pass_rate']}/{r['y21']['pass_rate']} "
            f"med={r['y10']['median_days_pass']}/{r['y21']['median_days_pass']} "
            f"dead={r['y10']['dead_rate']}"
        )

    out = {
        "good": good[:20],
        "top_pass": rows[:20],
    }
    (ROOT / "resultats_sweep.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
