"""
Freshwater Stress Score: empirical percentiles against historical reference distributions.

Reference hierarchy (spec Section 6):
    site   — if the site has ≥ MIN_SITE_OBS historical observations, use its own distribution
    basin  — otherwise fall back to the basin's pooled distribution
    none   — basin unknown / out of region: no percentile can be computed
Never a global all-basin pool: a naturally clear or naturally turbid basin would look anomalous
simply for being itself.

Leakage rule: the reference is built from training/reference rows only. When the observation
being scored is itself part of the reference table, its own value is removed before ranking
(leave-one-out), so no observation is compared against a distribution that contains it.

Composite (MVP): equal-weight mean of the available indicator percentiles, scaled 0–100.
No learned weights. Individual indicators stay visible; the composite is a "Freshwater Stress
Score", not a validated ecological health index.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MIN_SITE_OBS = 30

# Percentile bands for a single indicator
INDICATOR_STATUS = [(25, "Low"), (75, "Typical"), (90, "Elevated"), (100.01, "High")]
# Composite bands
STRESS_STATUS = [(40, "Lower stress"), (70, "Moderate stress"), (100.01, "Higher stress")]


def _band(value: float, bands: list[tuple[float, str]]) -> str:
    for upper, name in bands:
        if value < upper:
            return name
    return bands[-1][1]


@dataclass
class ReferenceDistribution:
    """Historical observed values per site and per basin for one target."""
    target: str
    min_site_obs: int = MIN_SITE_OBS
    site_values: dict[str, np.ndarray] = field(default_factory=dict)
    basin_values: dict[str, np.ndarray] = field(default_factory=dict)
    site_basin: dict[str, str] = field(default_factory=dict)

    @classmethod
    def fit(cls, df: pd.DataFrame, target: str, min_site_obs: int = MIN_SITE_OBS) -> "ReferenceDistribution":
        """df: processed rows used as reference (training data only). Needs site_no, basin, value."""
        rd = cls(target=target, min_site_obs=min_site_obs)
        for site, g in df.groupby("site_no"):
            rd.site_values[str(site)] = np.sort(g["value"].to_numpy(dtype=float))
            rd.site_basin[str(site)] = str(g["basin"].iloc[0])
        for basin, g in df.groupby("basin"):
            rd.basin_values[str(basin)] = np.sort(g["value"].to_numpy(dtype=float))
        return rd

    def reference_for(self, site_no: str | None, basin: str | None) -> tuple[np.ndarray | None, str]:
        """Return (sorted reference values, level) with level ∈ {'site', 'basin', 'none'}."""
        if site_no is not None and str(site_no) in self.site_values:
            v = self.site_values[str(site_no)]
            if len(v) >= self.min_site_obs:
                return v, "site"
            basin = basin or self.site_basin.get(str(site_no))
        if basin is not None and str(basin) in self.basin_values:
            return self.basin_values[str(basin)], "basin"
        return None, "none"

    def percentile(self, value: float, site_no: str | None, basin: str | None,
                   exclude_observed: float | None = None) -> dict:
        """Empirical percentile (0–100) of `value` within the reference.

        exclude_observed: if the scored observation's own ground-truth value is in the reference,
        pass it here so one matching entry is removed first (leave-one-out).
        """
        ref, level = self.reference_for(site_no, basin)
        if ref is None:
            return {"percentile": None, "reference_level": "none", "n_reference": 0}
        if exclude_observed is not None:
            i = np.searchsorted(ref, exclude_observed)
            if i < len(ref) and np.isclose(ref[i], exclude_observed):
                ref = np.delete(ref, i)
        if len(ref) == 0:
            return {"percentile": None, "reference_level": "none", "n_reference": 0}
        # mid-rank percentile: (#less + 0.5 * #equal) / n
        less = np.searchsorted(ref, value, side="left")
        equal = np.searchsorted(ref, value, side="right") - less
        pct = 100.0 * (less + 0.5 * equal) / len(ref)
        return {"percentile": float(pct), "reference_level": level, "n_reference": int(len(ref))}

    def summary(self) -> dict:
        return {
            "target": self.target, "min_site_obs": self.min_site_obs,
            "sites": {s: int(len(v)) for s, v in self.site_values.items()},
            "basins": {b: int(len(v)) for b, v in self.basin_values.items()},
        }


def indicator_status(percentile: float | None) -> str | None:
    return None if percentile is None else _band(percentile, INDICATOR_STATUS)


def stress_score(percentiles: dict[str, float | None]) -> dict:
    """Equal-weight mean of available indicator percentiles → 0–100 score + label.

    Indicators without a percentile are excluded and listed, so the caller can show that the
    composite is based on fewer than three inputs.
    """
    used = {k: v for k, v in percentiles.items() if v is not None}
    if not used:
        return {"score": None, "label": None, "indicators_used": [], "indicators_missing": list(percentiles)}
    score = float(np.mean(list(used.values())))
    return {
        "score": round(score, 1),
        "label": _band(score, STRESS_STATUS),
        "indicators_used": sorted(used),
        "indicators_missing": sorted(k for k in percentiles if k not in used),
        "weights": {k: round(1.0 / len(used), 3) for k in used},
    }
