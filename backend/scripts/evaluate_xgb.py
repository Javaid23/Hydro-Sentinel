"""
XGBoost baseline: leakage-safe evaluation + leave-one-basin-out (LOBO) for each target.

For every target (turbidity, chlorophyll_a, cdom):
  1. random row split        — optimistic reference (same sites on both sides)
  2. site hold-out           — unseen sites, known basins
  3. LOBO                    — unseen basin, one fold per basin
  4. log vs raw target       — on the random split, to settle the transform choice

Early stopping uses a validation slice carved from the *training* portion by whole sites,
so the stopping rule never sees held-out rows.

Writes docs/results/xgb_baseline.md and docs/results/xgb_baseline.json.

Usage:
    python backend/scripts/evaluate_xgb.py [--targets turbidity chlorophyll_a cdom] [--no-std] [--no-qa]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hydrosentinel import config as C  # noqa: E402
from hydrosentinel import data, evaluation as ev, features  # noqa: E402
from hydrosentinel.model import TargetModel  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("evaluate_xgb")


def fit_eval(df: pd.DataFrame, X: pd.DataFrame, split: ev.Split, target: str, log_target: bool) -> dict:
    """Fit on split.train (with site-wise early-stopping slice), evaluate on split.test."""
    tr, te = split.train_idx, split.test_idx
    df_tr = df.iloc[tr]
    fit_i, val_i = ev.site_validation_slice(df_tr)
    X_tr, y_tr = X.iloc[tr], df_tr["value"].to_numpy()

    t0 = time.time()
    m = TargetModel(target, log_target=log_target)
    m.fit(X_tr.iloc[fit_i], y_tr[fit_i], X_tr.iloc[val_i], y_tr[val_i])
    y_hat = m.predict(X.iloc[te])
    y_te = df.iloc[te]["value"].to_numpy()
    res = ev.regression_metrics(y_te, y_hat)
    res.update({
        "target": target, "split": split.name, "held_out": split.held_out,
        "log_target": log_target, "best_iteration": m.best_iteration_,
        "n_train": int(len(tr)), "fit_seconds": round(time.time() - t0, 1),
    })
    log.info("%-14s %-13s %-22s n=%5d R²=%6.3f MAE=%7.2f RMSE=%7.2f R²log=%6.3f iters=%d",
             target, split.name, split.held_out, res["n"], res["r2"], res["mae"], res["rmse"],
             res["r2_log"], m.best_iteration_)
    return res


def run_target(target: str, include_std: bool, include_qa: bool) -> list[dict]:
    df = data.load_processed(target)
    X = features.build_features(df, include_std=include_std, include_qa=include_qa)
    log.info("=== %s: %d rows, %d features, basins=%s", target, len(df), X.shape[1],
             df["basin"].value_counts().to_dict())
    rows: list[dict] = []

    # 1 + 4. random split, log vs raw
    rs = ev.random_split(df)
    for lt in (True, False):
        r = fit_eval(df, X, rs, target, log_target=lt)
        r["split"] = "random" if lt else "random_rawtarget"
        rows.append(r)

    # 2. site hold-out
    rows.append(fit_eval(df, X, ev.site_holdout(df), target, log_target=True))

    # 3. LOBO
    lobo = [fit_eval(df, X, s, target, log_target=True) for s in ev.lobo_folds(df)]
    rows.extend(lobo)
    if lobo:
        # pooled LOBO metrics: concatenate all held-out predictions (weights basins by size)
        # and the unweighted mean of per-basin R² (treats basins equally)
        pooled = {
            "target": target, "split": "lobo_pooled", "held_out": "all basins (row-weighted)",
            "n": int(sum(r["n"] for r in lobo)),
            "r2": float(np.nan), "mae": float(np.average([r["mae"] for r in lobo], weights=[r["n"] for r in lobo])),
            "rmse": float(np.sqrt(np.average([r["rmse"] ** 2 for r in lobo], weights=[r["n"] for r in lobo]))),
            "r2_log": float(np.nan), "log_target": True,
        }
        mean_r2 = {
            "target": target, "split": "lobo_mean", "held_out": "mean over basins (unweighted)",
            "n": len(lobo), "r2": float(np.mean([r["r2"] for r in lobo])),
            "mae": float(np.mean([r["mae"] for r in lobo])), "rmse": float(np.mean([r["rmse"] for r in lobo])),
            "r2_log": float(np.mean([r["r2_log"] for r in lobo])), "log_target": True,
        }
        rows.extend([pooled, mean_r2])
    return rows


def write_report(rows: list[dict], out_dir: Path, args: argparse.Namespace) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    (out_dir / "xgb_baseline.json").write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "features": {"include_std": not args.no_std, "include_qa": not args.no_qa},
        "results": rows,
    }, indent=2, default=float), encoding="utf-8")

    md = ["# XGBoost baseline — leakage-safe and LOBO evaluation\n",
          f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `backend/scripts/evaluate_xgb.py`. "
          f"Features: band means + ratios/indices"
          + ("" if args.no_std else " + band std") + ("" if args.no_qa else " + scene QA") + ".\n",
          "\nMetrics are in original units (FNU, µg/L, µg/L QSE) unless suffixed `_log` (log1p space). "
          "`median_factor_err` = exp(median |log ratio|): 1.5 means the typical prediction is within ×/÷ 1.5.\n"]
    for target in df["target"].unique():
        t = df[df["target"] == target]
        md.append(f"\n## {C.TARGETS[target].label} ({C.TARGETS[target].unit})\n\n")
        md.append("### Target transform (random split)\n\n")
        md.append(ev.to_markdown(ev.metrics_table(
            t[t["split"].isin(["random", "random_rawtarget"])].to_dict("records")).drop(columns=["target"])))
        md.append("\n### Generalisation designs\n\n")
        md.append(ev.to_markdown(ev.metrics_table(
            t[t["split"].isin(["random", "site_holdout", "lobo", "lobo_pooled", "lobo_mean"])]
            .to_dict("records")).drop(columns=["target"])))
    md.append("\n## Reading the table\n\n"
              "- **random** is the optimistic ceiling: the model has seen every site during training.\n"
              "- **site_holdout** removes whole sites; **lobo** removes whole basins — the number that "
              "matters for deployment to a new region.\n"
              "- Negative R² on a LOBO fold means the model does worse than predicting that basin's mean: "
              "the held-out basin's conditions are outside what the other basins taught it.\n")
    (out_dir / "xgb_baseline.md").write_text("".join(md), encoding="utf-8")
    log.info("wrote %s", out_dir / "xgb_baseline.md")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", nargs="+", default=list(C.TARGETS), choices=list(C.TARGETS))
    ap.add_argument("--no-std", action="store_true", help="drop within-buffer band std features")
    ap.add_argument("--no-qa", action="store_true", help="drop scene-QA count features")
    ap.add_argument("--out-dir", type=Path, default=C.DOCS_DIR / "results")
    args = ap.parse_args()

    rows: list[dict] = []
    for t in args.targets:
        rows.extend(run_target(t, include_std=not args.no_std, include_qa=not args.no_qa))
    write_report(rows, args.out_dir, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
