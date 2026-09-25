"""Unit tests for the raw → matchup pipeline on a tiny synthetic frame (no raw data needed)."""

import pandas as pd
import pytest

from hydrosentinel import config as C
from hydrosentinel import data


def _raw_frame() -> pd.DataFrame:
    """Two overpasses at one site; each matched to several sonde readings, plus edge cases."""
    scene_t = pd.Timestamp("2022-06-01 16:00:00+00:00")
    rows = []

    def add(scene, offset_h, parm, value, cd="A", npix=100, trunc=0, huc4=204, b01=250.0):
        r = {
            "scene": scene, "scene_datetime_UTC": str(scene_t),
            "sample_datetime_UTC": str(scene_t + pd.Timedelta(hours=offset_h)),
            "site_no": "0001", "station_nm": "Test", "parm_cd": parm, "Lat": 40.0, "Long": -75.0,
            "MeasurementValue": value, "MeasurementCd": cd, "site_tp_cd": "ST", "huc4": huc4,
            "nhd_feature_type": "Flowline", "n_l2flag": 50, "l2flag_center": 1, "n_mask": 80, "truncated": trunc,
        }
        for b in C.BANDS:
            r[f"{b}_buf250_mean"] = b01 if b == "B01" else 300.0
            r[f"{b}_buf250_std"] = 10.0
            r[f"{b}_n_pixels"] = npix
        rows.append(r)

    # scene A: turbidity readings at −2h, +0.25h (nearest), +5h
    add("A", -2.0, 63680, 10.0)
    add("A", 0.25, 63680, 12.0)
    add("A", 5.0, 63680, 30.0)
    # scene A: chlorophyll (µg/L) nearest is a censored '<' reading → should be dropped
    add("A", 0.1, 32316, 1.0, cd="A, <")
    # scene A: RFU chlorophyll must be ignored entirely
    add("A", 0.1, 32315, 5.0)
    # scene B: turbidity but only 2 valid pixels → dropped by pixel filter
    add("B", 0.0, 63680, 8.0, npix=2)
    # scene C: fDOM with nearest reading at 4h (outside 3h) → dropped by offset rule
    add("C", 4.0, 32295, 15.0)
    # scene D: fDOM, fine, but non-positive value → dropped
    add("D", 0.0, 32295, 0.0)
    # scene E: fDOM, fine, but missing B01 mean → dropped by 'all band means present'
    add("E", 0.0, 32295, 20.0, b01=float("nan"))
    # scene F: good fDOM
    add("F", -0.5, 32295, 22.0, cd="P")
    return pd.DataFrame(rows)


def test_standardise_maps_basin_and_target():
    df = data._standardise(_raw_frame())
    assert set(df["basin"].unique()) == {"Delaware"}
    assert df.loc[df["parm_cd"] == 63680, "target"].iloc[0] == "turbidity"
    assert df.loc[df["parm_cd"] == 32315, "target"].isna().all()  # RFU has no target


def test_standardise_rejects_unknown_huc4():
    raw = _raw_frame()
    raw.loc[0, "huc4"] = 9999
    with pytest.raises(ValueError, match="huc4"):
        data._standardise(raw)


def test_collapse_keeps_nearest_reading():
    df = data._standardise(_raw_frame())
    df = df[df["target"].notna()]
    out = data.collapse_matchups(df)
    a_turb = out[(out["scene"] == "A") & (out["target"] == "turbidity")]
    assert len(a_turb) == 1
    assert a_turb["value"].iloc[0] == 12.0
    assert abs(a_turb["offset_hours"].iloc[0] - 0.25) < 1e-9


def test_filters_drop_each_edge_case():
    df = data._standardise(_raw_frame())
    df = df[df["target"].notna()]
    kept, audit = data.apply_filters(data.collapse_matchups(df))
    kept_scenes = set(zip(kept["scene"], kept["target"]))
    assert kept_scenes == {("A", "turbidity"), ("F", "cdom")}
    dropped = dict(zip(audit["rule"], audit["dropped"]))
    assert dropped["|offset| <= 3.0 h"] == 1                       # scene C
    assert dropped["min n_pixels >= 5 on B02/B03/B04/B08"] == 1    # scene B
    assert dropped["no remark code in ('<', '>', 'e')"] == 1       # scene A chl
    assert dropped["value > 0"] == 1                               # scene D
    assert dropped["all band means present"] == 1                  # scene E


def test_split_targets_layout():
    df = data._standardise(_raw_frame())
    df = df[df["target"].notna()]
    kept, _ = data.apply_filters(data.collapse_matchups(df))
    tables = data.split_targets(kept)
    assert set(tables) == set(C.TARGETS)
    assert len(tables["turbidity"]) == 1 and len(tables["cdom"]) == 1 and len(tables["chlorophyll_a"]) == 0
    for t in tables.values():
        assert all(c in t.columns for c in C.BAND_MEAN_COLS + ["value", "basin", "site_no"])
        assert not any(c in t.columns for c in ("target",))
