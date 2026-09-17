"""
Assessment service: one Sentinel-2 observation → full structured assessment.

    OBSERVE   bands (+ scene QA) for one overpass at one location
    PREDICT   turbidity / chlorophyll-a / CDOM point estimates
    EXPLAIN   90 % conformal interval + top SHAP contributions per indicator
    ASSESS    site- or basin-relative percentile per indicator → Freshwater Stress Score

Everything numeric is produced here. The LLM layer (llm.py) only receives this dict and
must not alter any value in it.

Confidence tiers (docs/decisions.md D3) are derived from where the observation sits relative
to the training data, never hand-set:
    site_seen       site_no is in the target model's training sites
    basin_seen      basin is in training basins but the site is not
    out_of_region   basin not in training (regional demonstration mode)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from hydrosentinel import config as C
from hydrosentinel import features as F
from hydrosentinel.explain import Explainer
from hydrosentinel.model import TargetModel
from hydrosentinel.stress import ReferenceDistribution, indicator_status, stress_score
from hydrosentinel.uncertainty import ConformalInterval

# Confidence label per (validation tier, target) — from measured LOBO / site-holdout skill and
# conformal coverage (docs/results/model_findings.md, docs/results/uncertainty.md).
CONFIDENCE: dict[str, dict[str, str]] = {
    "site_seen":     {"turbidity": "Moderate", "chlorophyll_a": "Moderate", "cdom": "Moderate"},
    "basin_seen":    {"turbidity": "Moderate", "chlorophyll_a": "Low",      "cdom": "Low"},
    "out_of_region": {"turbidity": "Low",      "chlorophyll_a": "Very low", "cdom": "Very low"},
}
CONFIDENCE_NOTE: dict[str, str] = {
    "site_seen": "This site is in the model's training data; the 90% interval is calibrated for it.",
    "basin_seen": "This basin is in the training data but the site is not; intervals are wider in "
                  "practice than the calibrated 90%.",
    "out_of_region": "This location is outside every training basin. The pipeline runs end-to-end "
                     "but the outputs are unvalidated here and may be out of distribution.",
}


@dataclass
class TargetArtifacts:
    key: str
    model: TargetModel
    conformal: ConformalInterval
    reference: ReferenceDistribution
    explainer: Explainer
    global_shap: list[dict]
    meta: dict

    @classmethod
    def load(cls, tdir: Path) -> "TargetArtifacts":
        meta = json.loads((tdir / "metadata.json").read_text(encoding="utf-8"))
        model = TargetModel.load(tdir / "model.joblib")
        conf = json.loads((tdir / "conformal.json").read_text(encoding="utf-8"))
        conformal = ConformalInterval(model, alpha=conf["alpha"])
        conformal.q_hat_, conformal.n_calibration_ = conf["q_hat_log"], conf["n_calibration"]
        reference = joblib.load(tdir / "reference.joblib")
        global_shap = json.loads((tdir / "global_shap.json").read_text(encoding="utf-8"))
        return cls(key=tdir.name, model=model, conformal=conformal, reference=reference,
                   explainer=Explainer(model), global_shap=global_shap, meta=meta)

    def tier(self, site_no: str | None, basin: str | None) -> str:
        if site_no is not None and str(site_no) in self.meta["training_sites"]:
            return "site_seen"
        if basin is not None and str(basin) in self.meta["training_basins"]:
            return "basin_seen"
        return "out_of_region"


class AssessmentService:
    def __init__(self, models_dir: Path = C.MODELS_DIR):
        self.models_dir = Path(models_dir)
        manifest_path = self.models_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"{manifest_path} not found — run backend/scripts/train.py")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.targets: dict[str, TargetArtifacts] = {
            k: TargetArtifacts.load(self.models_dir / k) for k in self.manifest["targets"]
        }

    # ------------------------------------------------------------------ single observation
    def assess(self, obs: pd.Series | dict, top_k: int = 5) -> dict:
        """obs must carry the band/QA columns; site_no, basin, observed_<target> are optional."""
        row = pd.DataFrame([obs]) if isinstance(obs, dict) else obs.to_frame().T
        X = F.build_features(row)
        site_no = _opt(row, "site_no")
        basin = _opt(row, "basin")

        indicators: dict[str, dict] = {}
        percentiles: dict[str, float | None] = {}
        for key, art in self.targets.items():
            band = art.conformal.predict_interval(X).iloc[0]
            observed = _opt(row, f"observed_{key}")
            observed = None if observed is None or (isinstance(observed, float) and np.isnan(observed)) else float(observed)
            pct = art.reference.percentile(float(band["prediction"]), site_no, basin, exclude_observed=observed)
            tier = art.tier(site_no, basin)
            local = art.explainer.explain_one(X, top_k=top_k)
            percentiles[key] = pct["percentile"]
            indicators[key] = {
                "key": key, "label": art.meta["label"], "unit": art.meta["unit"], "note": art.meta["note"],
                "prediction": round(float(band["prediction"]), 3),
                "interval": {"lower": round(float(band["lower"]), 3), "upper": round(float(band["upper"]), 3),
                             "coverage": art.conformal.coverage_target,
                             "method": "split conformal (log1p residuals)"},
                "observed": observed,
                "percentile": None if pct["percentile"] is None else round(pct["percentile"], 1),
                "reference_level": pct["reference_level"], "n_reference": pct["n_reference"],
                "status": indicator_status(pct["percentile"]),
                "validation_tier": tier, "confidence": CONFIDENCE[tier][key],
                "confidence_note": CONFIDENCE_NOTE[tier],
                "top_contributions": local["top_contributions"],
                "baseline_prediction": round(local["baseline_prediction"], 3),
            }

        score = stress_score(percentiles)
        tiers = {k: v["validation_tier"] for k, v in indicators.items()}
        overall_tier = ("out_of_region" if all(t == "out_of_region" for t in tiers.values())
                        else "site_seen" if all(t == "site_seen" for t in tiers.values()) else "mixed")
        return {
            "observation": {
                "observation_id": _opt(row, "observation_id"), "scene": _opt(row, "scene"),
                "scene_datetime_utc": _iso(_opt(row, "scene_datetime_utc")),
                "site_no": site_no, "station_nm": _opt(row, "station_nm"), "basin": basin,
                "lat": _opt(row, "lat"), "lon": _opt(row, "lon"),
                "n_mask": _opt(row, "n_mask"), "n_l2flag": _opt(row, "n_l2flag"),
            },
            "stress": {**score, "name": "Freshwater Stress Score",
                       "description": "Equal-weight mean of indicator percentiles relative to the site's "
                                      "(or basin's) historical observations, 0–100. Not a validated ecological health index."},
            "indicators": indicators,
            "validation_tier": overall_tier,
            "model_version": self.manifest["trained_utc"],
        }

    # ------------------------------------------------------------------ global explanations
    def global_importance(self, key: str, top_k: int = 10) -> list[dict]:
        return self.targets[key].global_shap[:top_k]

    def describe(self) -> dict:
        return {
            "trained_utc": self.manifest["trained_utc"],
            "targets": {k: {"label": a.meta["label"], "unit": a.meta["unit"], "n_rows": a.meta["n_rows"],
                            "training_basins": a.meta["training_basins"], "n_sites": len(a.meta["training_sites"]),
                            "conformal": a.meta["conformal"]} for k, a in self.targets.items()},
        }


def _opt(row: pd.DataFrame, col: str):
    if col not in row.columns:
        return None
    v = row[col].iloc[0]
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


def _iso(v):
    if v is None:
        return None
    try:
        return pd.Timestamp(v).isoformat()
    except Exception:  # noqa: BLE001
        return str(v)


@lru_cache(maxsize=1)
def get_service(models_dir: str | None = None) -> AssessmentService:
    return AssessmentService(Path(models_dir) if models_dir else C.MODELS_DIR)
