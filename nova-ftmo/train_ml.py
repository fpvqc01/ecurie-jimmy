#!/usr/bin/env python3
"""Train un classifieur win/loss ORB → modèle joblib + seuil d'autorisation."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
ML = ROOT / "ml"
DATASET = ML / "orb_dataset.csv"
MODEL = ML / "orb_approver.joblib"
META = ML / "orb_approver_meta.json"

FEATURES = [
    "hour",
    "side",
    "atr",
    "range_atr",
    "body_atr",
    "break_dist_atr",
    "ret_1h",
    "ret_4h",
]


def main():
    if not DATASET.exists():
        raise SystemExit("Run python3 ml_dataset.py first")
    ds = pd.read_csv(DATASET)
    if len(ds) < 30:
        raise SystemExit(f"Dataset too small: {len(ds)} rows — need more history")

    # split chronologique (pas random) — évite le leak temporel
    ds = ds.sort_values("t") if "t" in ds.columns else ds
    X = ds[FEATURES].to_numpy(float)
    y = ds["win"].to_numpy(int)
    cut = max(int(len(ds) * 0.75), 20)
    if cut >= len(ds) - 5:
        Xtr, Xte, ytr, yte = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y if y.sum() > 1 else None
        )
    else:
        Xtr, Xte, ytr, yte = X[:cut], X[cut:], y[:cut], y[cut:]

    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(max_iter=1000, class_weight="balanced"),
            ),
        ]
    )
    pipe.fit(Xtr, ytr)
    proba = pipe.predict_proba(Xte)[:, 1]
    pred = (proba >= 0.55).astype(int)
    try:
        auc = float(roc_auc_score(yte, proba))
    except ValueError:
        auc = None
    report = classification_report(yte, pred, output_dict=True, zero_division=0)

    # seuil : viser précision raisonnable sur classe win
    best_thr, best_f = 0.55, -1.0
    for thr in np.linspace(0.45, 0.75, 13):
        p = (proba >= thr).astype(int)
        if p.sum() == 0:
            continue
        prec = ((p == 1) & (yte == 1)).sum() / max(p.sum(), 1)
        rec = ((p == 1) & (yte == 1)).sum() / max((yte == 1).sum(), 1)
        f = 2 * prec * rec / max(prec + rec, 1e-9)
        if f > best_f:
            best_f, best_thr = f, float(thr)

    joblib.dump({"model": pipe, "features": FEATURES, "threshold": best_thr}, MODEL)
    meta = {
        "rows": int(len(ds)),
        "winrate_base": float(y.mean()),
        "auc": auc,
        "threshold": best_thr,
        "report": report,
        "model": str(MODEL),
    }
    META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
