#!/usr/bin/env python3
"""Superviseur ML : lit un signal pending de l'EA, écrit AUTHORIZE/DENY.

Architecture:
  EA  →  MQL5/Files/nova_pending.json
  CE SCRIPT lit le pending, score ML, écrit nova_auth.txt = YES|NO

Usage (sur le PC Windows où tourne MT5):
  python supervisor.py --mt5-files "C:\\Users\\...\\MQL5\\Files" --loop

Sans --loop : une seule décision.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parent
ML = ROOT / "ml"
MODEL_PATH = ML / "orb_approver.joblib"


def decide(pending: dict, bundle: dict) -> tuple[str, float]:
    feats = bundle["features"]
    thr = float(bundle["threshold"])
    model = bundle["model"]
    x = np.array([[float(pending.get(f, 0.0)) for f in feats]], dtype=float)
    proba = float(model.predict_proba(x)[0, 1])
    return ("YES" if proba >= thr else "NO"), proba


def once(files_dir: Path, bundle: dict) -> bool:
    pending_path = files_dir / "nova_pending.json"
    auth_path = files_dir / "nova_auth.txt"
    if not pending_path.exists():
        return False
    try:
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if pending.get("status") != "WAIT":
        return False
    # already answered?
    if auth_path.exists():
        # allow overwrite for new signal id
        pass
    decision, proba = decide(pending, bundle)
    auth_path.write_text(f"{decision},{proba:.4f},{pending.get('id','')}\n", encoding="utf-8")
    # mark pending consumed
    pending["status"] = "DONE"
    pending["decision"] = decision
    pending["proba"] = proba
    pending_path.write_text(json.dumps(pending), encoding="utf-8")
    print(f"auth={decision} proba={proba:.3f} id={pending.get('id')}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mt5-files",
        required=True,
        help=r"Chemin MQL5\Files du terminal FTMO",
    )
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()

    if not MODEL_PATH.exists():
        raise SystemExit("Missing model. Run: python ml_dataset.py && python train_ml.py")
    bundle = joblib.load(MODEL_PATH)
    files_dir = Path(args.mt5_files)
    files_dir.mkdir(parents=True, exist_ok=True)

    print(f"Supervisor watching {files_dir}")
    if not args.loop:
        once(files_dir, bundle)
        return
    while True:
        once(files_dir, bundle)
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
