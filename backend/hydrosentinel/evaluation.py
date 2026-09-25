"""
Metrics and leakage-safe data splits.

Three evaluation designs, in increasing strictness:

  random_split      row-level 80/20 — the *optimistic* reference number. Rows from the same
                    site (and often the same week) land on both sides, so this measures
                    interpolation at known sites, not generalisation.
  site_holdout      hold out whole sites (GroupShuffleSplit) — sees new locations within
                    known basins.
  lobo_folds        leave-one-basin-out — the main generalisation test (spec Section 4).

Within any training set, the early-stopping validation slice is carved out of the training
portion only (by whole sites when there are enough of them), so the stopping rule never
sees held-out rows.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit

from hydrosentinel import config as C


# ----------------------------------------------------------------------------- metrics
def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray, log_space_too: bool = True) -> dict[str, float]:
    """R², MAE, RMSE in original units, plus R²/RMSE of log1p values (scale-robust view)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    out = {
        "n": int(len(y_true)),
        "r2": float(r2_score(y_true, y_pred)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "bias": float(np.mean(y_pred - y_true)),
        "median_ae": float(np.median(np.abs(y_pred - y_true))),
    }
    if log_space_too:
        lt, lp = np.log1p(np.clip(y_true, 0, None)), np.log1p(np.clip(y_pred, 0, None))
        out["r2_log"] = float(r2_score(lt, lp))
        out["rmse_log"] = float(np.sqrt(mean_squared_error(lt, lp)))
        # symmetric MAPE-like error in log space, expressed as a factor: exp(median |log ratio|)
        out["median_factor_err"] = float(np.exp(np.median(np.abs(lt - lp))))
    return out


# ----------------------------------------------------------------------------- splits
@dataclass(frozen=True)
class Split:
    name: str
    train_idx: np.ndarray
    test_idx: np.ndarray
    held_out: str = ""     # basin or description


def random_split(df: pd.DataFrame, test_size: float = 0.2, seed: int = C.RANDOM_STATE) -> Split:
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(df))
    n_test = int(round(test_size * len(df)))
    return Split("random", np.sort(idx[n_test:]), np.sort(idx[:n_test]), "random 20% rows")


def site_holdout(df: pd.DataFrame, test_size: float = 0.2, seed: int = C.RANDOM_STATE) -> Split:
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    tr, te = next(gss.split(df, groups=df["site_no"]))
    n_sites = df.iloc[te]["site_no"].nunique()
    return Split("site_holdout", tr, te, f"{n_sites} held-out sites")


def lobo_folds(df: pd.DataFrame, min_test_rows: int = 30) -> Iterator[Split]:
    """Yield one fold per basin present in df (basins with < min_test_rows are skipped, logged)."""
    basins = df["basin"].value_counts()
    for basin, n in basins.items():
        if n < min_test_rows:
            continue
        mask = (df["basin"] == basin).to_numpy()
        yield Split("lobo", np.flatnonzero(~mask), np.flatnonzero(mask), str(basin))


def site_validation_slice(df_train: pd.DataFrame, frac: float = 0.15, min_sites: int = 10,
                          seed: int = C.RANDOM_STATE) -> tuple[np.ndarray, np.ndarray]:
    """Carve a validation slice (for early stopping) out of a training set by whole sites.

    Falls back to a row-level split when there are fewer than `min_sites` sites: with a
    handful of sites a single held-out site is unrepresentative and early stopping then
    halts at iteration 0 (the model collapses to a constant). Either way the slice comes
    from the training portion only, so held-out test rows are never seen.
    """
    n_sites = df_train["site_no"].nunique()
    if n_sites >= min_sites:
        gss = GroupShuffleSplit(n_splits=1, test_size=frac, random_state=seed)
        fit_idx, val_idx = next(gss.split(df_train, groups=df_train["site_no"]))
        return fit_idx, val_idx
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(df_train))
    n_val = max(1, int(round(frac * len(df_train))))
    return idx[n_val:], idx[:n_val]


# ----------------------------------------------------------------------------- reporting
def metrics_table(rows: list[dict]) -> pd.DataFrame:
    """List of {split, held_out, **metrics} → tidy DataFrame with sensible column order."""
    cols = ["target", "split", "held_out", "n", "r2", "mae", "rmse", "bias", "median_ae",
            "r2_log", "rmse_log", "median_factor_err", "best_iteration"]
    df = pd.DataFrame(rows)
    return df[[c for c in cols if c in df.columns]]


def to_markdown(df: pd.DataFrame, floatfmt: str = ".3f") -> str:
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else format(v, floatfmt))
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in d.iterrows():
        lines.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(lines) + "\n"
