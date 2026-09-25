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
    bands: dict[str, float | None] | None = None
    band_wavelength_nm: dict[str, int] | None = None
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


class SceneAttempt(BaseModel):
    scene: str
    date: str
    usable: bool
    reason: str
    n_mask: int | None = None


class LiveReading(BaseModel):
    value: float
    datetime_utc: str
    offset_hours: float
    parm_cd: int
    qualifiers: list[str] = []


class Harmonisation(BaseModel):
    applied: bool
    reason: str | None = None
    factors: dict[str, float] | None = None
    spread: dict[str, dict] | None = None
    n_pairs: int | None = None
    n_sites: int | None = None
    method: str | None = None


class CacheInfo(BaseModel):
    hit: bool
    fetched_utc: str | None = None
    age_hours: float | None = None
    stale: bool = False
    revalidated: bool = Field(False, description="Entry was past its freshness window but the archive confirmed no newer scene exists")
    note: str | None = None


class OodBand(BaseModel):
    band: str
    label: str
    wavelength_nm: int
    value: float
    training: dict
    position: float
    outside: bool
    direction: str | None = None


class OodCheck(BaseModel):
    bands: list[OodBand]
    n_bands: int
    n_outside: int
    share_outside: float | None
    verdict: str
    reference: str


class BaselineIndicator(BaseModel):
    label: str
    unit: str
    prediction: float
    percentile: float
    n_reference: int
    quantiles: dict[str, float]
    status: str | None = None


class LocalBaseline(BaseModel):
    available: bool
    reason: str | None = None
    build_url: str | None = None
    name: str | None = None
    description: str | None = None
    kind: str | None = None
    note: str | None = None
    source: str | None = None
    n_scenes: int | None = None
    first_scene: str | None = None
    last_scene: str | None = None
    built_utc: str | None = None
    score: float | None = None
    label: str | None = None
    indicators: dict[str, BaselineIndicator] | None = None
    targets: dict | None = None


class LiveAssessment(Assessment):
    mode: Literal["live"] = "live"
    source: str = "USGS Sentinel-2 ACOLITE-DSF aquatic reflectance (AWS, updated daily)"
    source_key: Literal["usgs", "global"] = "usgs"
    harmonisation: Harmonisation | None = None
    cloud_cover: float | None = None
    cache: CacheInfo | None = Field(None, description="Set when the observation came from the disk cache")
    ood: OodCheck | None = Field(None, description="Where this observation's bands sit vs the training range")
    local_baseline: LocalBaseline | None = Field(
        None, description="Anomaly reference built from the archive at these coordinates, where no "
                          "observation-based reference exists. Model output, not ground truth.")
    scenes_tried: list[SceneAttempt]
    live_readings: dict[str, LiveReading | None] = Field(default_factory=dict,
        description="Nearest USGS sonde reading per target at the overpass time (USGS sites only)")
    extraction_note: str


class HistoryPoint(BaseModel):
    date: str
    observation_id: str
    observed: float | None
    predicted: float
    lower: float
    upper: float


class TargetHistory(BaseModel):
    label: str
    unit: str
    series: list[HistoryPoint]
    reference_level: Literal["site", "basin", "none"]
    n_reference: int
    quantiles: dict[str, float]
    histogram: dict


class SiteHistory(BaseModel):
    site_no: str
    station_nm: str
    basin: str
    n_observations: int
    targets: dict[str, TargetHistory]
    spectrum_median: dict[str, float]
    spectrum_iqr: dict[str, list[float]]
    band_wavelength_nm: dict[str, int]
