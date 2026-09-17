"""
Empirical coverage of the 90 % conformal intervals under the three evaluation designs.

Split conformal guarantees coverage only when calibration and scoring rows are exchangeable
(random split at known sites). This script measures what actually happens when the scoring rows
come from unseen sites (site hold-out) or an unseen basin (LOBO), so the confidence tiers in
docs/decisions.md D3 rest on measured numbers.

Writes docs/results/uncertainty.md and .json.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hydrosentinel import config as C  # noqa: E402
from hydrosentinel import data, evaluation as ev, features  # noqa: E402
from hydrosentinel.model import TargetModel  # noqa: E402
from hydrosentinel.uncertainty import ConformalInterval, empirical_coverage, split_calibration  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("evaluate_uncertainty")
ALPHA = 0.10


def coverage_for_split(df: pd.DataFrame, X: pd.DataFrame, split: ev.Split, target: str) -> dict:
    tr, te = split.train_idx, split.test_idx
    # calibration rows come from the TRAINING portion only
    fit_rel, cal_rel = split_calibration(len(tr), frac=0.15, seed=C.RANDOM_STATE)
    fit_idx, cal_idx = tr[fit_rel], tr[cal_rel]
    df_fit = df.iloc[fit_idx]
    in_fit, in_val = ev.site_validation_slice(df_fit)
    y = df["value"].to_numpy()

    m = TargetModel(target).fit(X.iloc[fit_idx].iloc[in_fit], y[fit_idx][in_fit],
                                X.iloc[fit_idx].iloc[in_val], y[fit_idx][in_val])
    iv = ConformalInterval(m, alpha=ALPHA).calibrate(X.iloc[cal_idx], y[cal_idx])
    cov = empirical_coverage(iv, X.iloc[te], y[te])
    res = {"target": target, "split": split.name, "held_out": split.held_out,
           "n_test": cov["n"], "coverage": round(cov["coverage"], 3), "target_coverage": 1 - ALPHA,
           "interval_factor": round(iv.interval_factor, 2), "median_width_factor": round(cov["median_width_factor"], 2)}
    log.info("%-14s %-13s %-22s n=%5d coverage=%.3f (target %.2f) factor=×/÷%.2f",
             target, split.name, split.held_out, cov["n"], cov["coverage"], 1 - ALPHA, iv.interval_factor)
    return res


def main() -> int:
    rows = []
    for target in C.TARGETS:
        df = data.load_processed(target)
        X = features.build_features(df)
        rows.append(coverage_for_split(df, X, ev.random_split(df), target))
        rows.append(coverage_for_split(df, X, ev.site_holdout(df), target))
        rows.extend(coverage_for_split(df, X, s, target) for s in ev.lobo_folds(df))

    out = C.DOCS_DIR / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "uncertainty.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    df = pd.DataFrame(rows)
    md = ["# Conformal interval coverage under each evaluation design\n",
          f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `backend/scripts/evaluate_uncertainty.py`. "
          f"Method: split conformal, absolute residual in log1p space, target coverage {1 - ALPHA:.0%}. "
          "Calibration rows are always drawn from the training portion of the split.\n",
          "\n`interval_factor` is the calibrated multiplicative half-width (prediction ×/÷ factor). "
          "`coverage` is the fraction of held-out observations inside the interval.\n"]
    for t in C.TARGETS:
        md.append(f"\n## {C.TARGETS[t].label}\n\n")
        md.append(ev.to_markdown(df[df["target"] == t].drop(columns=["target"])))
    md.append("\n## Reading the table\n\n"
              "- **random**: coverage ≈ 90 % by construction — the guarantee regime (site_seen tier).\n"
              "- **site_holdout / lobo**: coverage below 90 % means the calibrated band is too narrow for "
              "unseen sites or basins; the shortfall is the quantitative basis for the lower confidence "
              "tiers (basin_seen, out_of_region) in docs/decisions.md D3.\n")
    (out / "uncertainty.md").write_text("".join(md), encoding="utf-8")
    log.info("wrote %s", out / "uncertainty.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
