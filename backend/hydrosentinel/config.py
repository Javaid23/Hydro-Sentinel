"""
Central configuration: paths, dataset schema decisions, target definitions.

Every schema constant here was confirmed against the raw USGS release by
`scripts/inspect_data.py`; the reasoning is in docs/data_findings.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ----------------------------------------------------------------------------- paths
BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
DATA_RAW = ROOT_DIR / "data" / "raw"
DATA_PROCESSED = ROOT_DIR / "data" / "processed"
MODELS_DIR = ROOT_DIR / "models"
DOCS_DIR = ROOT_DIR / "docs"

RANDOM_STATE = 42

# ----------------------------------------------------------------------------- raw schema
RAW_GLOB = "Matched_WQ_S2*.csv"
RAW_NA_VALUES = ["NULL", "BLANK", ""]

BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"]

# Sentinel-2 MSI band centres (nm), useful for labelling SHAP output.
BAND_WAVELENGTH_NM = {
    "B01": 443, "B02": 490, "B03": 560, "B04": 665, "B05": 705, "B06": 740,
    "B07": 783, "B08": 842, "B8A": 865, "B11": 1610, "B12": 2190,
}
BAND_LABEL = {
    "B01": "coastal aerosol", "B02": "blue", "B03": "green", "B04": "red",
    "B05": "red edge 1", "B06": "red edge 2", "B07": "red edge 3", "B08": "NIR",
    "B8A": "narrow NIR", "B11": "SWIR 1", "B12": "SWIR 2",
}

# huc4 → basin. 1204 (San Jacinto) is grouped with Trinity — see docs/data_findings.md §3.
HUC4_BASIN: dict[int, str] = {
    204: "Delaware",
    712: "Illinois", 713: "Illinois",
    1203: "Trinity", 1204: "Trinity",
    1401: "Upper Colorado", 1402: "Upper Colorado",
    1709: "Willamette",
}
BASINS = sorted(set(HUC4_BASIN.values()))


# ----------------------------------------------------------------------------- targets
@dataclass(frozen=True)
class Target:
    key: str                      # column / file name, e.g. "turbidity"
    label: str                    # human label for UI
    unit: str
    parm_codes: tuple[int, ...]   # USGS parameter codes pooled into this target
    note: str = ""


TARGETS: dict[str, Target] = {
    "turbidity": Target(
        key="turbidity", label="Turbidity", unit="FNU", parm_codes=(63680,),
    ),
    "chlorophyll_a": Target(
        key="chlorophyll_a", label="Chlorophyll-a", unit="µg/L",
        parm_codes=(32316, 32318, 62361),
        note="In-situ fluorometric estimates in µg/L. RFU codes (32315, 32320) are excluded: "
             "relative fluorescence is sensor-specific and not a concentration.",
    ),
    "cdom": Target(
        key="cdom", label="CDOM (fDOM proxy)", unit="µg/L QSE", parm_codes=(32295,),
        note="Fluorescent dissolved organic matter (fDOM) as quinine-sulfate equivalents; the "
             "in-situ proxy for CDOM. RFU code 32322 excluded (one site, not a concentration).",
    ),
}
PARM_TO_TARGET: dict[int, str] = {pc: t.key for t in TARGETS.values() for pc in t.parm_codes}


# ----------------------------------------------------------------------------- matchup filters
@dataclass(frozen=True)
class MatchupFilter:
    """Filters applied when collapsing the long release to one row per overpass × site × target."""
    max_offset_hours: float = 3.0            # |sample time − scene time|
    min_pixels: int = 5                      # min valid pixels on each of PIXEL_CHECK_BANDS
    pixel_check_bands: tuple[str, ...] = ("B02", "B03", "B04", "B08")
    require_not_truncated: bool = True
    drop_remark_codes: tuple[str, ...] = ("<", ">", "e")   # censored / estimated readings
    require_positive: bool = True


MATCHUP_FILTER = MatchupFilter()

# ----------------------------------------------------------------------------- feature columns
BAND_MEAN_COLS = [f"{b}_buf250_mean" for b in BANDS]
BAND_STD_COLS = [f"{b}_buf250_std" for b in BANDS]
BAND_NPIX_COLS = [f"{b}_n_pixels" for b in BANDS]
SCENE_QA_COLS = ["n_mask", "n_l2flag", "l2flag_center"]

# Columns kept in the processed tables that must NEVER be used as model features
# (location/time identifiers that would let a model memorise sites and defeat LOBO).
ID_COLS = [
    "scene", "site_no", "station_nm", "basin", "huc4", "lat", "lon", "site_tp_cd",
    "nhd_feature_type", "scene_datetime_utc", "sample_datetime_utc", "offset_hours",
    "parm_cd", "measurement_cd",
]


@dataclass
class Settings:
    """Runtime settings for the API; env-overridable via pydantic-settings in app/."""
    models_dir: Path = field(default=MODELS_DIR)
    data_dir: Path = field(default=DATA_PROCESSED)
