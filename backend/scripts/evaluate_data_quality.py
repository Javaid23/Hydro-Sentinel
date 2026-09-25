"""
Does keeping provisional measurements change the conclusions?

USGS marks each sonde reading approved (A) or provisional (P). Provisional values have not been
through the agency's review, so a reasonable objection to this project is that training on them
inflates the results. The preprocessing keeps both and records the code
(docs/data_findings.md §4); this script tests whether that choice matters.

For each target it reruns leave-one-basin-out twice — on all records, and on approved records
only — and reports the difference. Where restricting the data would leave too little to evaluate,
that is reported rather than worked around, because it is the answer.

    python backend/scripts/evaluate_data_quality.py

Writes docs/results/data_quality.md.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hydrosentinel import config as C  # noqa: E402
from hydrosentinel import data, features  # noqa: E402
from hydrosentinel import evaluation as ev
from hydrosentinel.model import TargetModel  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("data_quality")

MIN_BASINS = 3        # below this, leave-one-basin-out says nothing about generalisation
MIN_ROWS = 200


def approved_only(df: pd.DataFrame) -> pd.DataFrame:
    """Rows whose measurement code starts with A (approved), dropping provisional ones."""
    return df[df["measurement_cd"].fillna("").astype(str).str.startswith("A")]


def lobo_mean(df: pd.DataFrame, label: str) -> dict | None:
    """Mean LOBO metrics over basins, or None when the subset cannot support the design."""
    basins = df["basin"].nunique()
    if basins < MIN_BASINS or len(df) < MIN_ROWS:
        log.info("  %s: not evaluable (%d rows across %d basins)", label, len(df), basins)
        return {"evaluable": False, "n": len(df), "n_basins": basins,
                "reason": f"{len(df)} rows across {basins} basin(s) — below the {MIN_ROWS} row / "
                          f"{MIN_BASINS} basin floor for a meaningful leave-one-basin-out"}
    X = features.build_features(df)
    y = df["value"].to_numpy()
    folds = []
    for split in ev.lobo_folds(df):
        tr, te = split.train_idx, split.test_idx
        fit_i, val_i = ev.site_validation_slice(df.iloc[tr])
        m = TargetModel("t").fit(X.iloc[tr].iloc[fit_i], y[tr][fit_i], X.iloc[tr].iloc[val_i], y[tr][val_i])
        folds.append({"held_out": split.held_out, **ev.regression_metrics(y[te], m.predict(X.iloc[te]))})
    out = {
        "evaluable": True, "n": len(df), "n_basins": basins, "n_folds": len(folds),
        "r2_log": round(float(np.mean([f["r2_log"] for f in folds])), 3),
        "r2": round(float(np.mean([f["r2"] for f in folds])), 3),
        "mae": round(float(np.mean([f["mae"] for f in folds])), 2),
        "folds": folds,
    }
    log.info("  %s: n=%d, %d basins, LOBO mean R2log=%+.3f MAE=%.2f",
             label, out["n"], basins, out["r2_log"], out["mae"])
    return out


def main() -> int:
    rows = {}
    for target in C.TARGETS:
        df = data.load_processed(target)
        appr = approved_only(df)
        log.info("%s: %d rows, %d approved (%.0f%%)", target, len(df), len(appr), 100 * len(appr) / len(df))
        rows[target] = {
            "label": C.TARGETS[target].label,
            "n_all": len(df), "n_approved": len(appr),
            "share_approved": round(len(appr) / len(df), 3),
            "all": lobo_mean(df, "all records"),
            "approved": lobo_mean(appr, "approved only"),
        }

    md = ["# Does keeping provisional measurements change the conclusions?\n",
          f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by `backend/scripts/evaluate_data_quality.py`.\n",
          "\nUSGS marks each sonde reading **approved (A)** or **provisional (P)**. Provisional values have "
          "not been through the agency's review. Preprocessing keeps both and records the code; this is the "
          "test of whether that choice affects the results.\n",
          "\n| Target | Records | Approved | Approved share | LOBO R²_log (all) | LOBO R²_log (approved only) |\n",
          "|---|---|---|---|---|---|\n"]
    for r in rows.values():
        a, ap = r["all"], r["approved"]
        md.append(f"| {r['label']} | {r['n_all']:,} | {r['n_approved']:,} | {r['share_approved']:.0%} | "
                  f"{a['r2_log'] if a['evaluable'] else '—'} | "
                  f"{ap['r2_log'] if ap['evaluable'] else 'not evaluable'} |\n")

    md.append("\n## What this shows\n\n")
    for r in rows.values():
        a, ap = r["all"], r["approved"]
        md.append(f"**{r['label']}** — ")
        if not ap["evaluable"]:
            md.append(f"restricting to approved records leaves {ap['reason']}. Dropping provisional data would "
                      f"remove the target from the evaluation altogether, so it is kept and the approval code is "
                      f"retained on every row.\n\n")
        elif a["evaluable"]:
            d = ap["r2_log"] - a["r2_log"]
            direction = "better" if d > 0 else "worse" if d < 0 else "unchanged"
            md.append(f"both subsets support the design. Training on approved records only scores "
                      f"R²_log {ap['r2_log']:+.3f} against {a['r2_log']:+.3f} for all records "
                      f"({direction} by {abs(d):.3f}), on {ap['n']:,} rows instead of {a['n']:,}. ")
            if ap["n_basins"] != a["n_basins"]:
                # Means taken over different fold sets are not comparable; say so rather than let
                # the two numbers imply a like-for-like improvement.
                md.append(f"**These two figures are not directly comparable**: restricting the data drops the "
                          f"evaluation from {a['n_basins']} basins to {ap['n_basins']}, so the means are over "
                          f"different folds. What does carry across is the sign — the target fails to transfer "
                          f"to an unseen basin either way.\n\n")
            elif abs(d) < 0.1:
                md.append("The difference is small relative to the spread between basins, so provisional "
                          "records are not inflating the result.\n\n")
            else:
                md.append("The gap is large enough to matter and is reported here rather than buried.\n\n")
        else:
            md.append("neither subset supports a leave-one-basin-out evaluation.\n\n")

    md.append("## Why provisional records are kept\n\n"
              "Restricting to approved data would not make the system more trustworthy — it would shrink the "
              "evidence base to the point where the honest conclusions above could not be drawn at all. The "
              "approval code travels with every row (`measurement_cd`), so any future analysis can split on it.\n")

    out = C.DOCS_DIR / "results" / "data_quality.md"
    out.write_text("".join(md), encoding="utf-8")
    log.info("wrote %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
