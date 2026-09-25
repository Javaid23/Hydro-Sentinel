"""
Raw USGS release → clean per-target matchup tables.

Pipeline (each step documented in docs/data_findings.md §4):

    load_raw()            read only needed columns from Matched_WQ_S2_*.csv
    collapse_matchups()   one row per (scene, site, target): the sonde reading nearest the overpass
    apply_filters()       time offset, valid pixels, truncation, remark codes, positive values
    split_targets()       {target_key: DataFrame} with a common column layout

The processed tables keep identifier columns (site, basin, time) so that LOBO
splits and site-level reference distributions can be built downstream, but the
feature-engineering step must only consume band / QA columns (see config.ID_COLS).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

from hydrosentinel import config as C

log = logging.getLogger(__name__)

_RAW_META = [
    "scene", "scene_datetime_UTC", "sample_datetime_UTC", "site_no", "station_nm",
    "parm_cd", "Lat", "Long", "MeasurementValue", "MeasurementCd", "site_tp_cd",
    "huc4", "nhd_feature_type", "n_l2flag", "l2flag_center", "n_mask", "truncated",
]
_RAW_BANDS = C.BAND_MEAN_COLS + C.BAND_STD_COLS + C.BAND_NPIX_COLS


def load_raw(raw_dir: Path = C.DATA_RAW) -> pd.DataFrame:
    """Read the release CSVs (selected columns only) and restrict to target parameter codes."""
    paths = sorted(raw_dir.rglob(C.RAW_GLOB))
    if not paths:
        raise FileNotFoundError(f"No {C.RAW_GLOB} under {raw_dir}; see docs/DATA.md")
    frames = []
    for p in paths:
        t0 = time.time()
        df = pd.read_csv(p, usecols=_RAW_META + _RAW_BANDS, engine="pyarrow",
                         na_values=C.RAW_NA_VALUES, dtype={"site_no": str})
        df = df[df["parm_cd"].isin(C.PARM_TO_TARGET)]
        log.info("%s: %s rows kept of target parameters (%.0fs)", p.name, f"{len(df):,}", time.time() - t0)
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    return _standardise(raw)


def _standardise(df: pd.DataFrame) -> pd.DataFrame:
    """Rename to snake_case, parse times, attach basin and target keys."""
    df = df.rename(columns={
        "scene_datetime_UTC": "scene_datetime_utc",
        "sample_datetime_UTC": "sample_datetime_utc",
        "Lat": "lat", "Long": "lon",
        "MeasurementValue": "value", "MeasurementCd": "measurement_cd",
    })
    df["scene_datetime_utc"] = pd.to_datetime(df["scene_datetime_utc"], utc=True)
    df["sample_datetime_utc"] = pd.to_datetime(df["sample_datetime_utc"], utc=True)
    df["offset_hours"] = (df["sample_datetime_utc"] - df["scene_datetime_utc"]).dt.total_seconds() / 3600
    df["huc4"] = df["huc4"].astype("Int64")
    df["basin"] = df["huc4"].map(C.HUC4_BASIN)
    unmapped = df.loc[df["basin"].isna(), "huc4"].dropna().unique().tolist()
    if unmapped:
        raise ValueError(f"huc4 codes without a basin mapping: {unmapped}; extend config.HUC4_BASIN")
    df["target"] = df["parm_cd"].map(C.PARM_TO_TARGET)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["measurement_cd"] = df["measurement_cd"].astype("string")
    return df


def collapse_matchups(df: pd.DataFrame) -> pd.DataFrame:
    """Keep, per (scene, site, target), the sonde reading closest in time to the overpass."""
    df = df[df["value"].notna()]
    idx = df.groupby(["scene", "site_no", "target"], sort=False)["offset_hours"].apply(
        lambda s: s.abs().idxmin()
    )
    out = df.loc[idx.values].reset_index(drop=True)
    log.info("collapsed %s rows → %s distinct scene×site×target matchups", f"{len(df):,}", f"{len(out):,}")
    return out


def apply_filters(df: pd.DataFrame, f: C.MatchupFilter = C.MATCHUP_FILTER) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply matchup quality filters. Returns (kept, audit) where audit counts rows dropped per rule."""
    n0 = len(df)
    audit = []

    def step(name: str, mask: pd.Series) -> None:
        nonlocal df
        dropped = int((~mask).sum())
        audit.append({"rule": name, "dropped": dropped, "remaining": int(mask.sum())})
        df = df[mask]

    step(f"|offset| <= {f.max_offset_hours} h", df["offset_hours"].abs() <= f.max_offset_hours)
    npix = df[[f"{b}_n_pixels" for b in f.pixel_check_bands]].min(axis=1)
    step(f"min n_pixels >= {f.min_pixels} on {'/'.join(f.pixel_check_bands)}", npix >= f.min_pixels)
    if f.require_not_truncated:
        step("not truncated at scene edge", df["truncated"] == 0)
    if f.drop_remark_codes:
        pat = "|".join(map(__import__("re").escape, f.drop_remark_codes))
        step(f"no remark code in {f.drop_remark_codes}", ~df["measurement_cd"].fillna("").str.contains(pat))
    if f.require_positive:
        step("value > 0", df["value"] > 0)
    # Band means must be present for every band we model on
    step("all band means present", df[C.BAND_MEAN_COLS].notna().all(axis=1))

    audit_df = pd.DataFrame(audit)
    log.info("filters: %s → %s rows\n%s", f"{n0:,}", f"{len(df):,}", audit_df.to_string(index=False))
    return df.reset_index(drop=True), audit_df


_OUT_COLS = (
    ["scene", "site_no", "station_nm", "basin", "huc4", "lat", "lon", "site_tp_cd", "nhd_feature_type",
     "scene_datetime_utc", "sample_datetime_utc", "offset_hours", "parm_cd", "measurement_cd", "value"]
    + C.BAND_MEAN_COLS + C.BAND_STD_COLS + C.BAND_NPIX_COLS + C.SCENE_QA_COLS
)


def split_targets(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """One tidy table per target, sorted by site then time (needed for sequence models later)."""
    out = {}
    for key in C.TARGETS:
        t = df[df["target"] == key][_OUT_COLS].sort_values(["site_no", "scene_datetime_utc"])
        out[key] = t.reset_index(drop=True)
    return out


def summarise(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Rows per basin × target, plus sites with ≥30 observations — the numbers quoted in docs."""
    rows = []
    for key, t in tables.items():
        per_basin = t.groupby("basin").size()
        sites_ge30 = int((t.groupby("site_no").size() >= 30).sum())
        rows.append({"target": key, **per_basin.to_dict(), "total": len(t),
                     "sites": t["site_no"].nunique(), "sites_ge_30": sites_ge30})
    return pd.DataFrame(rows).set_index("target").fillna(0).astype(int)


def load_processed(key: str, processed_dir: Path = C.DATA_PROCESSED) -> pd.DataFrame:
    """Read a processed per-target table written by scripts/preprocess.py."""
    p = processed_dir / f"{key}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"{p} not found — run backend/scripts/preprocess.py first")
    return pd.read_parquet(p)


# ----------------------------------------------------------------------------- observation index
_OBS_KEY = ["scene", "site_no"]
_OBS_META = ["station_nm", "basin", "huc4", "lat", "lon", "site_tp_cd", "nhd_feature_type", "scene_datetime_utc"]


def build_observation_index(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per (scene, site) across all target tables, with bands/QA and observed values.

    The three targets are measured at different sites and overpasses, but every model can be
    applied to any Sentinel-2 observation. This table is what the API scores: bands + QA for the
    features, and `observed_<target>` (NaN when that target was not measured) for display and
    for the leave-one-out reference-distribution rule.
    """
    band_cols = C.BAND_MEAN_COLS + C.BAND_STD_COLS + C.BAND_NPIX_COLS + C.SCENE_QA_COLS
    parts = []
    for key, t in tables.items():
        p = t[_OBS_KEY + _OBS_META + band_cols + ["value"]].rename(columns={"value": f"observed_{key}"})
        parts.append(p)
    obs = pd.concat(parts, ignore_index=True)
    agg = {c: "first" for c in _OBS_META + band_cols}
    agg.update({f"observed_{k}": "first" for k in tables})
    obs = obs.groupby(_OBS_KEY, as_index=False).agg(agg)
    obs["observation_id"] = obs["site_no"] + "_" + obs["scene_datetime_utc"].dt.strftime("%Y%m%dT%H%M%S")
    obs = obs.sort_values(["site_no", "scene_datetime_utc"]).reset_index(drop=True)
    return obs


def load_observations(processed_dir: Path = C.DATA_PROCESSED) -> pd.DataFrame:
    p = processed_dir / "observations.parquet"
    if not p.exists():
        raise FileNotFoundError(f"{p} not found — run backend/scripts/preprocess.py first")
    return pd.read_parquet(p)
