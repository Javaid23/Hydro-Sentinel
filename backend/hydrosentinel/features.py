"""
Feature engineering: processed matchup table → model feature matrix.

Inputs are the 11 Sentinel-2 band means over a 250 m buffer (as released by USGS, in
scaled reflectance units), their within-buffer standard deviations, and scene-quality
counts. Derived features are band ratios and normalised differences that the aquatic
remote-sensing literature uses for turbidity, chlorophyll and CDOM retrieval. Tree
models can in principle learn ratios from raw bands, but giving them explicitly makes
SHAP output more interpretable ("red/green ratio contributed …").

Nothing in here touches identifiers (site, basin, lat/lon, dates): see config.ID_COLS.
The same function serves training and inference, so it must stay side-effect free.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from hydrosentinel import config as C

_EPS = 1e-6


def _mean(df: pd.DataFrame, band: str) -> pd.Series:
    return df[f"{band}_buf250_mean"].astype(float)


def _nd(a: pd.Series, b: pd.Series) -> pd.Series:
    """Normalised difference (a − b) / (a + b)."""
    return (a - b) / (a + b + _EPS)


# Ratio / index definitions: name → (numerator band, denominator band) or callable.
# Labels are used in SHAP output; keep them short and physically meaningful.
RATIOS: dict[str, tuple[str, str]] = {
    "r_red_green": ("B04", "B03"),      # turbidity / suspended sediment
    "r_red_blue": ("B04", "B02"),       # sediment vs. clear-water blue
    "r_green_blue": ("B03", "B02"),     # CDOM / chlorophyll absorb blue
    "r_rededge1_red": ("B05", "B04"),   # chlorophyll red-edge signal
    "r_nir_red": ("B08", "B04"),        # high-turbidity saturation regime
    "r_nir_green": ("B08", "B03"),
    "r_rededge2_rededge1": ("B06", "B05"),
    "r_swir1_red": ("B11", "B04"),      # residual glint / aerosol indicator
}
INDICES: dict[str, tuple[str, str]] = {
    "ndti": ("B04", "B03"),   # normalised difference turbidity index (red, green)
    "ndci": ("B05", "B04"),   # normalised difference chlorophyll index (red-edge 1, red)
    "ndwi": ("B03", "B08"),   # green vs NIR: water/land mixing sanity signal
}

FEATURE_LABELS: dict[str, str] = {
    **{f"{b}_buf250_mean": f"{b} {C.BAND_LABEL[b]} ({C.BAND_WAVELENGTH_NM[b]} nm) mean" for b in C.BANDS},
    **{f"{b}_buf250_std": f"{b} {C.BAND_LABEL[b]} within-buffer std" for b in C.BANDS},
    "r_red_green": "red / green ratio (B04/B03)",
    "r_red_blue": "red / blue ratio (B04/B02)",
    "r_green_blue": "green / blue ratio (B03/B02)",
    "r_rededge1_red": "red-edge 1 / red ratio (B05/B04)",
    "r_nir_red": "NIR / red ratio (B08/B04)",
    "r_nir_green": "NIR / green ratio (B08/B03)",
    "r_rededge2_rededge1": "red-edge 2 / red-edge 1 ratio (B06/B05)",
    "r_swir1_red": "SWIR 1 / red ratio (B11/B04)",
    "ndti": "NDTI turbidity index (B04−B03)/(B04+B03)",
    "ndci": "NDCI chlorophyll index (B05−B04)/(B05+B04)",
    "ndwi": "NDWI water index (B03−B08)/(B03+B08)",
    "n_mask": "valid water pixels in buffer",
    "n_l2flag": "unflagged pixels in buffer",
    "cv_red": "red band coefficient of variation in buffer",
}


def build_features(df: pd.DataFrame, include_std: bool = True, include_qa: bool = True) -> pd.DataFrame:
    """Return the feature matrix (same row order as `df`). Column order is deterministic."""
    out = pd.DataFrame(index=df.index)

    for b in C.BANDS:
        out[f"{b}_buf250_mean"] = _mean(df, b)

    for name, (num, den) in RATIOS.items():
        out[name] = _mean(df, num) / (_mean(df, den) + _EPS)
    for name, (a, b) in INDICES.items():
        out[name] = _nd(_mean(df, a), _mean(df, b))

    if include_std:
        for b in C.BANDS:
            out[f"{b}_buf250_std"] = df[f"{b}_buf250_std"].astype(float)
        out["cv_red"] = df["B04_buf250_std"].astype(float) / (_mean(df, "B04") + _EPS)

    if include_qa:
        out["n_mask"] = df["n_mask"].astype(float)
        out["n_l2flag"] = df["n_l2flag"].astype(float)

    # Guard: no identifier column can leak in
    leaked = [c for c in out.columns if c in C.ID_COLS]
    assert not leaked, f"identifier columns in feature matrix: {leaked}"
    return out.replace([np.inf, -np.inf], np.nan)


def feature_names(include_std: bool = True, include_qa: bool = True) -> list[str]:
    """Feature column names in the order build_features() emits them (no data needed)."""
    names = [f"{b}_buf250_mean" for b in C.BANDS] + list(RATIOS) + list(INDICES)
    if include_std:
        names += [f"{b}_buf250_std" for b in C.BANDS] + ["cv_red"]
    if include_qa:
        names += ["n_mask", "n_l2flag"]
    return names


def label(feature: str) -> str:
    return FEATURE_LABELS.get(feature, feature)
