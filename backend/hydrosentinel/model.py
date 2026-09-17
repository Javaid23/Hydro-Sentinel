"""
XGBoost regressor for one water-quality target, with an optional log1p target transform.

The wrapper exposes a plain sklearn-style fit/predict on ORIGINAL units so that every
caller (evaluation, conformal, SHAP, API) sees the same thing, while the underlying
booster is trained in log space where the targets are roughly symmetric.

    model = TargetModel("turbidity").fit(X_train, y_train, X_val, y_val)
    y_hat = model.predict(X_new)               # FNU, not log
    model.booster_                              # raw xgboost.XGBRegressor for SHAP
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from hydrosentinel import config as C

# Conservative defaults for a few thousand rows; tuned per target later if warranted.
DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 2000,          # upper bound; early stopping picks the real number
    "learning_rate": 0.03,
    "max_depth": 5,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "objective": "reg:squarederror",
    "tree_method": "hist",
    "random_state": C.RANDOM_STATE,
    "n_jobs": -1,
}


@dataclass
class TargetModel:
    target: str
    log_target: bool = True
    params: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_PARAMS))
    early_stopping_rounds: int = 100
    booster_: xgb.XGBRegressor | None = None
    feature_names_: list[str] | None = None
    best_iteration_: int | None = None

    # ----------------------------------------------------------------- transforms
    def _fwd(self, y: np.ndarray) -> np.ndarray:
        return np.log1p(y) if self.log_target else np.asarray(y, dtype=float)

    def _inv(self, z: np.ndarray) -> np.ndarray:
        return np.expm1(z) if self.log_target else z

    # ----------------------------------------------------------------- fit / predict
    def fit(self, X: pd.DataFrame, y: np.ndarray,
            X_val: pd.DataFrame | None = None, y_val: np.ndarray | None = None) -> "TargetModel":
        """Fit on (X, y). If a validation set is given, use early stopping on it."""
        params = dict(self.params)
        fit_kwargs: dict[str, Any] = {}
        if X_val is not None and y_val is not None:
            params["early_stopping_rounds"] = self.early_stopping_rounds
            fit_kwargs["eval_set"] = [(X_val, self._fwd(np.asarray(y_val)))]
            fit_kwargs["verbose"] = False
        self.booster_ = xgb.XGBRegressor(**params)
        self.booster_.fit(X, self._fwd(np.asarray(y)), **fit_kwargs)
        self.feature_names_ = list(X.columns)
        bi = getattr(self.booster_, "best_iteration", None)
        self.best_iteration_ = int(bi) if bi is not None else int(params["n_estimators"])
        return self

    def refit_fixed(self, X: pd.DataFrame, y: np.ndarray, n_estimators: int) -> "TargetModel":
        """Refit on all data with a fixed tree count (used after early stopping chose one)."""
        params = dict(self.params, n_estimators=int(n_estimators))
        self.booster_ = xgb.XGBRegressor(**params)
        self.booster_.fit(X, self._fwd(np.asarray(y)))
        self.feature_names_ = list(X.columns)
        self.best_iteration_ = int(n_estimators)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predictions in original units (e.g. FNU, µg/L)."""
        return self._inv(self.predict_transformed(X))

    def predict_transformed(self, X: pd.DataFrame) -> np.ndarray:
        """Predictions in model space (log1p units if log_target). Used by conformal wrapper."""
        assert self.booster_ is not None, "model not fitted"
        X = X[self.feature_names_]
        return self.booster_.predict(X)

    # ----------------------------------------------------------------- persistence
    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return path

    @staticmethod
    def load(path: Path) -> "TargetModel":
        return joblib.load(path)
