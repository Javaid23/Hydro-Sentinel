"""
Split conformal prediction intervals for a fitted TargetModel.

Method (absolute-residual split conformal, Lei et al. 2018 / Angelopoulos & Bates 2021):

    1. Fit the point model on the training portion.
    2. On a disjoint calibration set, compute nonconformity scores
           s_i = | z_i − ẑ_i |          (z = log1p(y): the model's own space)
    3. q̂ = the ⌈(n+1)(1−α)⌉/n empirical quantile of {s_i}.
    4. For a new x: interval = [ ẑ(x) − q̂ , ẑ(x) + q̂ ] in log space,
       mapped back with expm1 → a multiplicative band in original units.

Guarantee: P(y ∈ interval) ≥ 1 − α for scoring data exchangeable with the calibration set
(known sites). Out of region the guarantee does not hold; `empirical_coverage()` measures what
actually happens on held-out basins so it can be reported instead of assumed.

Working in log space is deliberate: residuals of these skewed targets scale with the level, so
a constant additive band in FNU or µg/L would be far too wide at low values and too narrow at
high ones. A constant band in log space is a constant *factor*, which matches the error structure
(see `median_factor_err` in evaluation).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from hydrosentinel.model import TargetModel


@dataclass
class ConformalInterval:
    """Calibrated interval generator wrapping a fitted TargetModel."""
    model: TargetModel
    alpha: float = 0.10                      # 90 % intervals
    q_hat_: float | None = None
    n_calibration_: int = 0
    calibration_scores_: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)

    def calibrate(self, X_cal: pd.DataFrame, y_cal: np.ndarray) -> ConformalInterval:
        z = self.model._fwd(np.asarray(y_cal, dtype=float))
        z_hat = self.model.predict_transformed(X_cal)
        scores = np.abs(z - z_hat)
        n = len(scores)
        if n < 20:
            raise ValueError(f"calibration set too small for α={self.alpha}: n={n}")
        # finite-sample corrected quantile level, capped at 1
        level = min(1.0, np.ceil((n + 1) * (1 - self.alpha)) / n)
        self.q_hat_ = float(np.quantile(scores, level, method="higher"))
        self.n_calibration_ = int(n)
        self.calibration_scores_ = scores
        return self

    def predict_interval(self, X: pd.DataFrame) -> pd.DataFrame:
        """Columns: prediction, lower, upper (original units), width_factor (= upper/lower)."""
        assert self.q_hat_ is not None, "call calibrate() first"
        z_hat = self.model.predict_transformed(X)
        lo = self.model._inv(z_hat - self.q_hat_)
        hi = self.model._inv(z_hat + self.q_hat_)
        pred = self.model._inv(z_hat)
        lo = np.clip(lo, 0.0, None)
        return pd.DataFrame({
            "prediction": pred, "lower": lo, "upper": hi,
            "width_factor": (hi + 1e-9) / (lo + 1e-9),
        }, index=X.index)

    @property
    def coverage_target(self) -> float:
        return 1.0 - self.alpha

    @property
    def interval_factor(self) -> float:
        """Approximate multiplicative half-width: prediction × / ÷ this. Exact in log1p space;
        in original units it is a constant factor only for values well above 1."""
        assert self.q_hat_ is not None
        return float(np.exp(self.q_hat_)) if self.model.log_target else float("nan")

    def to_dict(self) -> dict:
        return {
            "method": "split conformal, absolute residual in log1p space",
            "alpha": self.alpha, "coverage_target": self.coverage_target,
            "q_hat_log": self.q_hat_, "interval_factor": self.interval_factor,
            "n_calibration": self.n_calibration_,
        }


def empirical_coverage(iv: ConformalInterval, X: pd.DataFrame, y: np.ndarray) -> dict[str, float]:
    """Fraction of y inside the interval, plus median relative width — for reporting on held-out data."""
    band = iv.predict_interval(X)
    y = np.asarray(y, dtype=float)
    inside = (y >= band["lower"].to_numpy()) & (y <= band["upper"].to_numpy())
    return {
        "coverage": float(inside.mean()),
        "target": iv.coverage_target,
        "n": int(len(y)),
        "median_width_factor": float(band["width_factor"].median()),
    }


def split_calibration(n_rows: int, frac: float = 0.15, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Random row indices (fit_idx, cal_idx). Rows are exchangeable at known sites, which is the regime
    in which the coverage guarantee is claimed."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n_rows)
    n_cal = max(20, int(round(frac * n_rows)))
    return np.sort(idx[n_cal:]), np.sort(idx[:n_cal])
