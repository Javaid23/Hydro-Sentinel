"""
Benchmark LSTM, FT-Transformer and XGB+FTT stacking against the XGBoost baseline
(spec Section 3), under the site-holdout and LOBO designs used for the baseline.

Fairness rules
  - identical folds and identical 36-feature input per target
  - standardisation and early-stopping slices fit on the training portion only
  - LSTM is trained/evaluated only at sites with ≥30 observations inside the respective
    portion; XGB is re-scored on that same test subset ("xgb@lstm_rows") so the comparison
    is like-for-like
  - stacking: XGB and FTT are fit on 80 % of the training sites, a Ridge meta-learner on the
    other 20 % (never on rows the base models saw), then everything is scored on the test fold

Writes docs/results/benchmarks.md and .json.

Usage:
    python backend/scripts/evaluate_benchmarks.py [--targets ...] [--skip-lobo] [--window 6]
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
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupShuffleSplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hydrosentinel import config as C  # noqa: E402
from hydrosentinel import data, evaluation as ev, features  # noqa: E402
from hydrosentinel.benchmarks import common as B  # noqa: E402
from hydrosentinel.benchmarks.models import FTTransformer, LSTMRegressor  # noqa: E402
from hydrosentinel.model import TargetModel  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("benchmarks")


def _row(target, model, split, extra=None, **m):
    r = {"target": target, "model": model, "split": split.name, "held_out": split.held_out, **m}
    r.update(extra or {})
    return r


def fit_xgb(X, y, fit_i, val_i) -> TargetModel:
    return TargetModel("t").fit(X.iloc[fit_i], y[fit_i], X.iloc[val_i], y[val_i])


def fit_ftt(Xs, y, fit_i, val_i, seed=C.RANDOM_STATE):
    B.set_seed(seed)
    m = FTTransformer(Xs.shape[1])
    m, ep = B.train_model(m, Xs[fit_i], np.log1p(y[fit_i]), Xs[val_i], np.log1p(y[val_i]),
                          epochs=200, lr=1e-3, batch_size=64, patience=20)
    return m, ep


def evaluate_fold(df, X, y, split: ev.Split, target: str, window: int, do_lstm=True, do_stack=True) -> list[dict]:
    rows = []
    tr, te = split.train_idx, split.test_idx
    df_tr = df.iloc[tr]
    fit_rel, val_rel = ev.site_validation_slice(df_tr)
    fit_i, val_i = tr[fit_rel], tr[val_rel]

    # ---- XGBoost baseline
    t0 = time.time()
    xgb = fit_xgb(X, y, fit_i, val_i)
    p_xgb = xgb.predict(X.iloc[te])
    rows.append(_row(target, "xgboost", split, {"fit_seconds": round(time.time() - t0, 1)}, **ev.regression_metrics(y[te], p_xgb)))

    # ---- standardised features for the neural models (fit on training portion)
    sc = B.Scaler.fit(X.iloc[tr].to_numpy(dtype=np.float32))
    Xs = sc.transform(X.to_numpy(dtype=np.float32)).astype(np.float32)

    # ---- FT-Transformer
    t0 = time.time()
    ftt, ep = fit_ftt(Xs, y, fit_i, val_i)
    p_ftt = np.expm1(B.predict(ftt, Xs[te]))
    rows.append(_row(target, "ft_transformer", split, {"fit_seconds": round(time.time() - t0, 1), "epochs": ep},
                     **ev.regression_metrics(y[te], p_ftt)))

    # ---- LSTM on sequence-eligible rows
    if do_lstm:
        t0 = time.time()
        S_fit, _, k_fit = B.build_windows(df, Xs, window, fit_i)
        S_val, _, k_val = B.build_windows(df, Xs, window, val_i)
        S_te, _, k_te = B.build_windows(df, Xs, window, te)
        if len(k_fit) >= 100 and len(k_val) >= 20 and len(k_te) >= 30:
            B.set_seed()
            lstm = LSTMRegressor(Xs.shape[1])
            lstm, ep = B.train_model(lstm, S_fit, np.log1p(y[k_fit]), S_val, np.log1p(y[k_val]),
                                     epochs=200, lr=1e-3, batch_size=64, patience=20)
            p_lstm = np.expm1(B.predict(lstm, S_te))
            extra = {"fit_seconds": round(time.time() - t0, 1), "epochs": ep, "n_train_seq": int(len(k_fit))}
            rows.append(_row(target, "lstm", split, extra, **ev.regression_metrics(y[k_te], p_lstm)))
            # like-for-like: XGB on exactly the LSTM-eligible test rows
            pos = {r: i for i, r in enumerate(te)}
            sel = np.array([pos[r] for r in k_te])
            rows.append(_row(target, "xgb@lstm_rows", split, {}, **ev.regression_metrics(y[k_te], p_xgb[sel])))
        else:
            rows.append(_row(target, "lstm", split, {"skipped": f"too few sequence-eligible rows (fit={len(k_fit)}, val={len(k_val)}, test={len(k_te)})"}, n=int(len(k_te))))

    # ---- Stacking XGB + FTT with a site-disjoint blend slice
    if do_stack:
        t0 = time.time()
        if df_tr["site_no"].nunique() >= 5:
            gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=C.RANDOM_STATE)
            base_rel, blend_rel = next(gss.split(df_tr, groups=df_tr["site_no"]))
        else:
            rng = np.random.default_rng(C.RANDOM_STATE); perm = rng.permutation(len(tr))
            blend_rel, base_rel = perm[: len(tr) // 5], perm[len(tr) // 5:]
        base_i, blend_i = tr[base_rel], tr[blend_rel]
        b_fit_rel, b_val_rel = ev.site_validation_slice(df.iloc[base_i])
        b_fit, b_val = base_i[b_fit_rel], base_i[b_val_rel]
        xgb_b = fit_xgb(X, y, b_fit, b_val)
        ftt_b, _ = fit_ftt(Xs, y, b_fit, b_val)
        Z_blend = np.column_stack([np.log1p(xgb_b.predict(X.iloc[blend_i])), B.predict(ftt_b, Xs[blend_i])])
        meta = Ridge(alpha=1.0).fit(Z_blend, np.log1p(y[blend_i]))
        Z_te = np.column_stack([np.log1p(xgb_b.predict(X.iloc[te])), B.predict(ftt_b, Xs[te])])
        p_stack = np.expm1(meta.predict(Z_te))
        rows.append(_row(target, "stack_xgb_ftt", split,
                         {"fit_seconds": round(time.time() - t0, 1), "meta_weights": [round(float(w), 3) for w in meta.coef_]},
                         **ev.regression_metrics(y[te], p_stack)))
        # the base XGB trained on the reduced (80 %) site set, for reference
        rows.append(_row(target, "xgb@stack_base", split, {}, **ev.regression_metrics(y[te], xgb_b.predict(X.iloc[te]))))

    for r in rows:
        if "r2" in r:
            log.info("%-14s %-15s %-13s %-16s n=%5d R²=%6.3f MAE=%7.2f R²log=%6.3f", target, r["model"], split.name,
                     split.held_out[:16], r["n"], r["r2"], r["mae"], r["r2_log"])
        else:
            log.info("%-14s %-15s %-13s %-16s %s", target, r["model"], split.name, split.held_out[:16], r.get("skipped"))
    return rows


def write_report(rows: list[dict], out_dir: Path, args) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "benchmarks.json").write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "window": args.window, "results": rows,
    }, indent=2, default=float), encoding="utf-8")
    df = pd.DataFrame(rows)
    md = ["# Model benchmarks — LSTM, FT-Transformer, stacking vs XGBoost\n",
          f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `backend/scripts/evaluate_benchmarks.py` "
          f"(LSTM window = {args.window} observations). Same folds and features as the baseline; see the script "
          "docstring for the fairness rules. Metrics in original units; `r2_log` in log1p space.\n"]
    for t in df["target"].unique():
        md.append(f"\n## {C.TARGETS[t].label}\n")
        for split in ["site_holdout", "lobo"]:
            sub = df[(df["target"] == t) & (df["split"] == split)]
            if sub.empty:
                continue
            md.append(f"\n### {split}\n\n")
            cols = ["model", "held_out", "n", "r2", "mae", "rmse", "r2_log", "median_factor_err", "fit_seconds", "epochs", "skipped"]
            md.append(ev.to_markdown(sub[[c for c in cols if c in sub.columns]].sort_values(["held_out", "model"])))
        # LOBO mean per model
        lob = df[(df["target"] == t) & (df["split"] == "lobo") & df["r2"].notna()]
        if not lob.empty:
            md.append("\n### LOBO mean over basins (unweighted)\n\n")
            md.append(ev.to_markdown(lob.groupby("model")[["r2", "mae", "rmse", "r2_log"]].mean().reset_index()))
    (out_dir / "benchmarks.md").write_text("".join(md), encoding="utf-8")
    log.info("wrote %s", out_dir / "benchmarks.md")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", nargs="+", default=list(C.TARGETS), choices=list(C.TARGETS))
    ap.add_argument("--skip-lobo", action="store_true")
    ap.add_argument("--no-lstm", action="store_true")
    ap.add_argument("--no-stack", action="store_true")
    ap.add_argument("--window", type=int, default=6)
    ap.add_argument("--out-dir", type=Path, default=C.DOCS_DIR / "results")
    args = ap.parse_args()

    rows: list[dict] = []
    for t in args.targets:
        df = data.load_processed(t)
        X = features.build_features(df)
        y = df["value"].to_numpy()
        log.info("=== %s: %d rows", t, len(df))
        splits = [ev.site_holdout(df)] + ([] if args.skip_lobo else list(ev.lobo_folds(df)))
        for s in splits:
            rows.extend(evaluate_fold(df, X, y, s, t, args.window, do_lstm=not args.no_lstm, do_stack=not args.no_stack))
    write_report(rows, args.out_dir, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
