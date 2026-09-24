"""
Train the production models on the full pooled dataset and bundle all artifacts.

LOBO (scripts/evaluate_xgb.py) is validation only. This script produces what the API serves:

For each target:
  1. rows → fit portion (85 %) + calibration portion (15 %), random by row
  2. XGBoost fit on the fit portion with early stopping on a site-wise slice of it
  3. split-conformal calibration (90 %) on the calibration portion
  4. global SHAP importance on the fit portion
  5. site/basin reference distributions from all rows (leave-one-out applied at scoring time)
  6. artifacts → models/<target>/  and models/manifest.json

Usage:
    python backend/scripts/train.py [--targets ...] [--alpha 0.1]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hydrosentinel import config as C  # noqa: E402
from hydrosentinel import data, evaluation as ev, features  # noqa: E402
from hydrosentinel.explain import Explainer  # noqa: E402
from hydrosentinel.model import TargetModel  # noqa: E402
from hydrosentinel.stress import ReferenceDistribution  # noqa: E402
from hydrosentinel.uncertainty import ConformalInterval, empirical_coverage, split_calibration  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("train")


def train_target(target: str, alpha: float, out_dir: Path) -> dict:
    df = data.load_processed(target)
    X = features.build_features(df)
    y = df["value"].to_numpy()

    fit_idx, cal_idx = split_calibration(len(df), frac=0.15, seed=C.RANDOM_STATE)
    df_fit = df.iloc[fit_idx]
    inner_fit, inner_val = ev.site_validation_slice(df_fit)
    X_fit, y_fit = X.iloc[fit_idx], y[fit_idx]

    model = TargetModel(target).fit(X_fit.iloc[inner_fit], y_fit[inner_fit], X_fit.iloc[inner_val], y_fit[inner_val])
    log.info("%s: fit on %d rows (val %d), best_iteration=%d", target, len(inner_fit), len(inner_val), model.best_iteration_)

    # Refit on the whole fit portion with the chosen tree count so no rows are wasted
    model.refit_fixed(X_fit, y_fit, n_estimators=max(model.best_iteration_ + 1, 50))

    conformal = ConformalInterval(model, alpha=alpha).calibrate(X.iloc[cal_idx], y[cal_idx])
    cov = empirical_coverage(conformal, X.iloc[cal_idx], y[cal_idx])   # sanity: ≈ 1-α by construction
    log.info("%s: conformal factor ×/÷ %.2f on %d calibration rows (in-sample coverage %.2f)",
             target, conformal.interval_factor, conformal.n_calibration_, cov["coverage"])

    explainer = Explainer(model)
    global_imp = explainer.global_importance(X_fit)
    log.info("%s: top SHAP features: %s", target, ", ".join(global_imp["feature"].head(5)))

    reference = ReferenceDistribution.fit(df, target)

    # ------------------------------------------------------------------ persist
    tdir = out_dir / target
    tdir.mkdir(parents=True, exist_ok=True)
    model.save(tdir / "model.joblib")
    joblib.dump(reference, tdir / "reference.joblib")
    (tdir / "conformal.json").write_text(json.dumps(conformal.to_dict(), indent=2), encoding="utf-8")
    global_imp.to_json(tdir / "global_shap.json", orient="records", indent=2)

    meta = {
        "target": target, "label": C.TARGETS[target].label, "unit": C.TARGETS[target].unit,
        "note": C.TARGETS[target].note,
        "n_rows": int(len(df)), "n_fit": int(len(fit_idx)), "n_calibration": int(len(cal_idx)),
        "n_estimators": model.best_iteration_, "log_target": model.log_target,
        "feature_names": model.feature_names_,
        "training_sites": sorted(df["site_no"].unique().tolist()),
        "training_basins": sorted(df["basin"].unique().tolist()),
        "site_basin": df.drop_duplicates("site_no").set_index("site_no")["basin"].to_dict(),
        "site_names": df.drop_duplicates("site_no").set_index("site_no")["station_nm"].to_dict(),
        "site_coords": {s: [float(r.lat), float(r.lon)] for s, r in
                        df.drop_duplicates("site_no").set_index("site_no")[["lat", "lon"]].iterrows()},
        "reference": reference.summary(),
        "conformal": conformal.to_dict(),
        "trained_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (tdir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", nargs="+", default=list(C.TARGETS), choices=list(C.TARGETS))
    ap.add_argument("--alpha", type=float, default=0.10, help="1 − coverage for conformal intervals")
    ap.add_argument("--out-dir", type=Path, default=C.MODELS_DIR)
    args = ap.parse_args()

    manifest = {"trained_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "alpha": args.alpha, "targets": {}}
    for t in args.targets:
        meta = train_target(t, args.alpha, args.out_dir)
        manifest["targets"][t] = {k: meta[k] for k in
                                  ("label", "unit", "n_rows", "n_estimators", "training_basins", "conformal")}
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Per-band training distribution, used by the out-of-distribution check for unseen locations.
    # Built from the largest target's table (turbidity) — the broadest sample of training inputs.
    ref_df = data.load_processed("turbidity")
    bands_ref = {}
    for b in C.BANDS:
        col = ref_df[f"{b}_buf250_mean"].dropna()
        bands_ref[b] = {k: round(float(v), 2) for k, v in {
            "p1": col.quantile(0.01), "p25": col.quantile(0.25), "p50": col.median(),
            "p75": col.quantile(0.75), "p99": col.quantile(0.99), "min": col.min(), "max": col.max(),
        }.items()}
    (args.out_dir / "training_bands.json").write_text(json.dumps(bands_ref, indent=2), encoding="utf-8")
    log.info("wrote %s (%d bands from %d turbidity observations)", args.out_dir / "training_bands.json",
             len(bands_ref), len(ref_df))
    log.info("wrote %s", args.out_dir / "manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
