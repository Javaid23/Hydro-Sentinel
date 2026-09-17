"""Pydantic response schemas for the HydroSentinel API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal["site_seen", "basin_seen", "out_of_region", "mixed"]


class Contribution(BaseModel):
    feature: str
    label: str
    value: float
    shap_log: float = Field(description="Additive SHAP contribution in log1p space")
    factor: float = Field(description="exp(shap_log): multiplicative effect on the prediction")
    direction: Literal["raised", "lowered"]


class Interval(BaseModel):
    lower: float
    upper: float
    coverage: float = Field(description="Nominal coverage of the conformal interval, e.g. 0.9")
    method: str


class Indicator(BaseModel):
    key: str
    label: str
    unit: str
    note: str = ""
    prediction: float
    interval: Interval
    observed: float | None = Field(None, description="Sonde value matched to this overpass, if any (display only)")
    percentile: float | None = Field(None, description="0–100 relative to the reference distribution")
    reference_level: Literal["site", "basin", "none"]
    n_reference: int
    status: str | None = Field(None, description="Low / Typical / Elevated / High")
    validation_tier: Tier
    confidence: str
    confidence_note: str
    top_contributions: list[Contribution]
    baseline_prediction: float


class Stress(BaseModel):
    name: str
    score: float | None
    label: str | None
    indicators_used: list[str]
    indicators_missing: list[str]
    weights: dict[str, float] | None = None
    description: str


class Observation(BaseModel):
    observation_id: str | None
    scene: str | None
    scene_datetime_utc: str | None
    site_no: str | None
    station_nm: str | None
    basin: str | None
    lat: float | None
    lon: float | None
    n_mask: float | None
    n_l2flag: float | None


class Action(BaseModel):
    rank: int
    action: str
    rationale: str


class LLMExplanation(BaseModel):
    summary: str
    interpretation: str
    actions: list[Action]
    caveats: list[str] = []
    model: str
    generated_utc: str
    disclaimer: str


class Assessment(BaseModel):
    observation: Observation
    stress: Stress
    indicators: dict[str, Indicator]
    validation_tier: Tier
    model_version: str
    llm_explanation: LLMExplanation | None = None
    llm_error: str | None = None


class SiteSummary(BaseModel):
    site_no: str
    station_nm: str
    basin: str
    lat: float
    lon: float
    n_observations: int
    first_observation: str
    latest_observation: str
    targets_observed: list[str]


class ObservationSummary(BaseModel):
    observation_id: str
    scene_datetime_utc: str
    n_mask: float
    observed: dict[str, float | None]


class GlobalImportance(BaseModel):
    target: str
    features: list[dict]


class ModelInfo(BaseModel):
    trained_utc: str
    targets: dict
