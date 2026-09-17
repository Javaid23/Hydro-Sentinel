"""
SHAP explanations for a fitted TargetModel (applied to the final validated model only).

TreeExplainer gives exact Shapley values for gradient-boosted trees. Because the model is fit
in log1p space, each SHAP value is an additive contribution in log units. For reporting we
also express it as a multiplicative factor exp(φ): "this feature pushed the prediction ×1.3".

Wording rule (spec Section 9): describe *contribution to the model's prediction*, never cause.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import shap

from hydrosentinel import features as F
from hydrosentinel.model import TargetModel


@dataclass
class Contribution:
    feature: str
    label: str
    value: float          # feature value for this observation
    shap_log: float       # additive contribution in log1p space
    factor: float         # exp(shap_log): multiplicative effect on the prediction
    direction: str        # "raised" | "lowered"

    def to_dict(self) -> dict:
        return {
            "feature": self.feature, "label": self.label, "value": round(float(self.value), 4),
            "shap_log": round(float(self.shap_log), 4), "factor": round(float(self.factor), 3),
            "direction": self.direction,
        }


class Explainer:
    def __init__(self, model: TargetModel, background: pd.DataFrame | None = None):
        assert model.booster_ is not None, "model must be fitted"
        self.model = model
        self.feature_names = list(model.feature_names_)
        # TreeExplainer on the booster itself; background only affects interventional mode.
        self.explainer = shap.TreeExplainer(model.booster_, data=background, feature_perturbation="tree_path_dependent"
                                            if background is None else "interventional")
        self.expected_value_log = float(np.ravel(self.explainer.expected_value)[0])

    # ------------------------------------------------------------------ raw values
    def shap_values(self, X: pd.DataFrame) -> np.ndarray:
        X = X[self.feature_names]
        return np.asarray(self.explainer.shap_values(X))

    # ------------------------------------------------------------------ global
    def global_importance(self, X: pd.DataFrame) -> pd.DataFrame:
        """Mean |SHAP| per feature over X, descending. Columns: feature, label, mean_abs_shap, share."""
        sv = np.abs(self.shap_values(X)).mean(axis=0)
        df = pd.DataFrame({"feature": self.feature_names, "mean_abs_shap": sv})
        df["label"] = df["feature"].map(F.label)
        df["share"] = df["mean_abs_shap"] / df["mean_abs_shap"].sum()
        return df.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)[
            ["feature", "label", "mean_abs_shap", "share"]]

    # ------------------------------------------------------------------ local
    def explain_one(self, x: pd.DataFrame, top_k: int = 5) -> dict:
        """Local explanation for a single-row DataFrame.

        Returns base prediction, the observation's prediction, and the top-k contributions by
        |SHAP| with human labels. All values in the model's original units where relevant.
        """
        assert len(x) == 1, "explain_one takes exactly one row"
        sv = self.shap_values(x)[0]
        order = np.argsort(-np.abs(sv))[:top_k]
        contribs = [
            Contribution(
                feature=self.feature_names[i], label=F.label(self.feature_names[i]),
                value=float(x.iloc[0, x.columns.get_loc(self.feature_names[i])]),
                shap_log=float(sv[i]), factor=float(np.exp(sv[i])),
                direction="raised" if sv[i] > 0 else "lowered",
            )
            for i in order
        ]
        z_hat = self.expected_value_log + float(sv.sum())
        return {
            "baseline_prediction": float(self.model._inv(np.array([self.expected_value_log]))[0]),
            "prediction": float(self.model._inv(np.array([z_hat]))[0]),
            "top_contributions": [c.to_dict() for c in contribs],
            "n_features": len(self.feature_names),
            "residual_others_log": float(sv.sum() - sum(c.shap_log for c in contribs)),
        }


def describe_contribution(c: Contribution | dict, target_label: str) -> str:
    """Plain-language, contribution-not-causation sentence for one SHAP item."""
    d = c if isinstance(c, dict) else c.to_dict()
    pct = abs(d["factor"] - 1) * 100
    return (f"{d['label']} {d['direction']} the predicted {target_label} by about {pct:.0f}% "
            f"relative to the model baseline.")
