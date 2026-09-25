"""Disk cache for live extractions: round-trip, freshness window, corruption tolerance."""

import json
import time

import numpy as np
import pandas as pd
import pytest

from hydrosentinel import livecache


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(livecache, "CACHE_DIR", tmp_path / "live_cache")
    return tmp_path / "live_cache"


def _obs():
    return {
        "scene": "S2A_43RDQ_20260918_1_L2A",
        "scene_datetime_utc": pd.Timestamp("2026-09-18T06:00:00Z"),
        "lat": 31.6083, "lon": 74.2959, "n_mask": np.int64(130),
        "B04_buf250_mean": np.float64(1362.0), "B02_buf250_mean": float("nan"),
        "harmonisation": {"applied": True, "n_pairs": 15},
        "_cache": {"should": "not be persisted"},
    }


def test_round_trip_preserves_values_and_types(tmp_cache):
    livecache.save(31.6083, 74.2959, "global", _obs(), [{"scene": "x", "usable": True}])
    obs, tried, stale = livecache.load(31.6083, 74.2959, "global")
    assert obs is not None and not stale
    assert obs["scene"] == "S2A_43RDQ_20260918_1_L2A"
    assert isinstance(obs["scene_datetime_utc"], pd.Timestamp)
    assert obs["scene_datetime_utc"] == pd.Timestamp("2026-09-18T06:00:00Z")
    assert obs["n_mask"] == 130 and isinstance(obs["n_mask"], int)
    assert obs["B04_buf250_mean"] == 1362.0
    assert obs["B02_buf250_mean"] is None          # NaN serialises as null
    assert obs["harmonisation"]["applied"] is True
    assert tried == [{"scene": "x", "usable": True}]
    assert obs["_cache"]["hit"] is True and obs["_cache"]["age_hours"] < 1
    # private keys of the source observation are not persisted
    blob = json.loads(next(tmp_cache.glob("*.json")).read_text(encoding="utf-8"))
    assert "_cache" not in blob["observation"]


def test_miss_returns_none():
    obs, tried, stale = livecache.load(1.0, 2.0, "global")
    assert obs is None and tried is None and stale is False


def test_key_rounds_coordinates_and_separates_sources():
    assert livecache.key(31.60831, 74.29594, "global") == livecache.key(31.60829, 74.29586, "global")
    assert livecache.key(31.6083, 74.2959, "global") != livecache.key(31.6083, 74.2959, "usgs")
    assert livecache.key(-31.6083, -74.2959, "usgs").count("m") >= 2      # no '-' in filenames
    assert "." not in livecache.key(31.6083, 74.2959, "global")


def test_entry_past_the_window_is_flagged_stale(tmp_cache):
    livecache.save(10.0, 20.0, "usgs", _obs(), [])
    p = next(tmp_cache.glob("*.json"))
    blob = json.loads(p.read_text(encoding="utf-8"))
    blob["fetched_epoch"] = time.time() - 30 * 3600          # 30 h ago
    p.write_text(json.dumps(blob), encoding="utf-8")

    obs, _, stale = livecache.load(10.0, 20.0, "usgs")
    assert obs is not None and stale is True                  # still returned, for fallback use
    assert obs["_cache"]["age_hours"] >= 29
    _, _, stale_wide = livecache.load(10.0, 20.0, "usgs", max_age_hours=48)
    assert stale_wide is False


def test_corrupt_entry_is_ignored_not_raised(tmp_cache):
    tmp_cache.mkdir(parents=True, exist_ok=True)
    (tmp_cache / f"{livecache.key(5.0, 6.0, 'global')}.json").write_text("{ not json", encoding="utf-8")
    obs, tried, stale = livecache.load(5.0, 6.0, "global")
    assert obs is None and tried is None


def test_save_is_atomic_and_leaves_no_temp_files(tmp_cache):
    livecache.save(1.0, 2.0, "global", _obs(), [])
    livecache.save(1.0, 2.0, "global", {**_obs(), "scene": "newer"}, [])
    assert list(tmp_cache.glob("*.tmp")) == []
    assert len(list(tmp_cache.glob("*.json"))) == 1           # overwritten in place
    obs, _, _ = livecache.load(1.0, 2.0, "global")
    assert obs["scene"] == "newer"


def test_entries_summary(tmp_cache):
    livecache.save(1.0, 2.0, "global", _obs(), [])
    livecache.save(3.0, 4.0, "usgs", {**_obs(), "scene": "other"}, [])
    rows = livecache.entries()
    assert len(rows) == 2
    assert {r["source"] for r in rows} == {"global", "usgs"}
    assert all(r["scene_datetime_utc"].startswith("2026-09-18") for r in rows)
    assert all(r["age_hours"] < 1 for r in rows)


def test_touch_refreshes_timestamp_without_changing_the_observation(tmp_cache):
    import json as _json
    livecache.save(7.0, 8.0, "usgs", _obs(), [{"scene": "x"}])
    p = next(tmp_cache.glob("*.json"))
    blob = _json.loads(p.read_text(encoding="utf-8"))
    blob["fetched_epoch"] = time.time() - 30 * 3600
    p.write_text(_json.dumps(blob), encoding="utf-8")
    before = _json.loads(p.read_text(encoding="utf-8"))["observation"]

    _, _, stale = livecache.load(7.0, 8.0, "usgs")
    assert stale is True

    assert livecache.touch(7.0, 8.0, "usgs") is True
    after = _json.loads(p.read_text(encoding="utf-8"))
    assert after["observation"] == before          # pixels are immutable; only the timestamp moves
    assert after["revalidated"] == 1
    obs, tried, stale_now = livecache.load(7.0, 8.0, "usgs")
    assert stale_now is False and obs["_cache"]["age_hours"] < 1
    assert tried == [{"scene": "x"}]

    assert livecache.touch(7.0, 8.0, "usgs") is True
    assert _json.loads(p.read_text(encoding="utf-8"))["revalidated"] == 2
    assert list(tmp_cache.glob("*.tmp")) == []


def test_touch_on_missing_entry_is_false():
    assert livecache.touch(99.0, 99.0, "global") is False
