"""The /live/* endpoints exercised offline, by seeding the cache and forbidding network calls.

These paths are the ones a visitor actually clicks, but they normally reach out to public imagery
archives, so they went untested. Here the disk cache is pre-populated and both fetchers are
replaced with functions that fail loudly, so a passing test proves the request was served without
touching the network, and a regression that bypasses the cache surfaces as an error rather than a
slow test.
"""

import json as _json
import time as _time

import pandas as pd
import pytest

from hydrosentinel import config as C
from hydrosentinel import live, live_global, livecache

pytestmark = pytest.mark.skipif(
    not (C.MODELS_DIR / "manifest.json").exists() or not (C.DATA_PROCESSED / "observations.parquet").exists(),
    reason="trained artifacts / processed observations not present",
)

LAT, LON = 31.6083, 74.2959          # Ravi at Lahore, outside every training basin
SCENE = "S2C_43RDQ_20260923_0_L2A"


def _observation(scene=SCENE):
    """A realistic extracted observation: plausible harmonised band values and full QA."""
    obs = {
        "scene": scene,
        "scene_datetime_utc": pd.Timestamp("2026-09-23T05:50:26Z"),
        "lat": LAT, "lon": LON, "tile": "T43RDQ", "cloud_cover": 8.0,
        "n_buf": 489, "n_l2flag": 489, "l2flag_center": 1, "n_nhd": 130,
        "n_mask": 130, "truncated": 0, "scl_center": 6, "n_scl_water": 130,
        "n_clipped_negative": 0, "share_clipped": 0.0,
        "harmonisation": {"applied": True, "n_pairs": 15, "n_sites": 5, "factors": {}, "spread": {},
                          "method": "test"},
    }
    values = {"B01": 333, "B02": 459, "B03": 880, "B04": 1116, "B05": 1242,
              "B06": 1333, "B07": 1510, "B08": 1232, "B8A": 1230, "B11": 353, "B12": 332}
    for b in C.BANDS:
        obs[f"{b}_buf250_mean"] = float(values[b])
        obs[f"{b}_buf250_std"] = 40.0
        obs[f"{b}_buf250_med"] = float(values[b])
        obs[f"{b}_center"] = float(values[b])
        obs[f"{b}_n_pixels"] = 130
        obs[f"{b}_n_negative"] = 0
    return obs


def _age_the_entry(cache_dir, hours=30):
    p = next((cache_dir / "live_cache").glob("*.json"))
    blob = _json.loads(p.read_text(encoding="utf-8"))
    blob["fetched_epoch"] = _time.time() - hours * 3600
    p.write_text(_json.dumps(blob), encoding="utf-8")


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """Seed the disk cache and make any network fetch an error."""
    monkeypatch.setattr(livecache, "CACHE_DIR", tmp_path / "live_cache")

    def forbidden(*_a, **_k):
        raise AssertionError("network was used although a fresh cache entry exists")

    monkeypatch.setattr(live, "latest_usable", forbidden)
    monkeypatch.setattr(live_global, "latest_usable", forbidden)
    monkeypatch.setattr(live, "newest_scene_id", forbidden)
    monkeypatch.setattr(live_global, "newest_scene_id", forbidden)
    monkeypatch.setattr(live, "nwis_readings_for_targets", lambda *_a, **_k: {})
    livecache.save(LAT, LON, "global", _observation(),
                   [{"scene": "x", "date": "2026-09-23", "usable": True, "reason": "ok", "n_mask": 130}])
    return tmp_path


@pytest.fixture
def client(offline):
    from fastapi.testclient import TestClient

    from app.main import _live_cache, app
    _live_cache.clear()                     # the in-process layer must not mask the disk cache
    with TestClient(app) as c:
        yield c


def test_cached_coords_request_is_served_without_network(client):
    r = client.get("/live/coords", params={"lat": LAT, "lon": LON, "name": "Ravi at Lahore"})
    assert r.status_code == 200
    j = r.json()
    assert j["cache"]["hit"] is True and j["cache"]["stale"] is False
    assert j["observation"]["scene"] == SCENE
    assert j["mode"] == "live" and j["source_key"] == "global"


def test_out_of_region_response_withholds_what_it_cannot_justify(client):
    j = client.get("/live/coords", params={"lat": LAT, "lon": LON}).json()
    assert j["validation_tier"] == "out_of_region"
    assert j["stress"]["score"] is None, "no local history means no stress score"
    assert j["stress"]["indicators_used"] == []
    for ind in j["indicators"].values():
        assert ind["prediction"] > 0
        assert ind["percentile"] is None and ind["status"] is None
        assert ind["reference_level"] == "none"
        assert ind["confidence"] in {"Low", "Very low"}
        assert ind["interval"]["lower"] <= ind["prediction"] <= ind["interval"]["upper"]


def test_out_of_distribution_check_is_reported(client):
    ood = client.get("/live/coords", params={"lat": LAT, "lon": LON}).json()["ood"]
    assert ood["n_bands"] == len(C.BANDS)
    assert 0 <= ood["n_outside"] <= ood["n_bands"]
    assert ood["verdict"] and ood["reference"]
    assert all(b["direction"] in {"above", "below"} for b in ood["bands"] if b["outside"])


def test_a_stale_entry_is_revalidated_rather_than_refetched(client, offline, monkeypatch):
    """Past the freshness window, one listing call replaces thirteen raster reads."""
    from app.main import _live_cache
    _live_cache.clear()
    _age_the_entry(offline)

    calls = []

    def newest(*_a, **_k):
        calls.append(1)
        return SCENE

    monkeypatch.setattr(live_global, "newest_scene_id", newest)
    j = client.get("/live/coords", params={"lat": LAT, "lon": LON}).json()
    assert calls, "the archive should have been asked whether anything is newer"
    assert j["cache"]["revalidated"] is True and j["cache"]["stale"] is False
    assert j["observation"]["scene"] == SCENE


def test_a_newer_scene_forces_a_real_refetch(client, offline, monkeypatch):
    from app.main import _live_cache
    _live_cache.clear()
    _age_the_entry(offline)
    monkeypatch.setattr(live_global, "newest_scene_id", lambda *_a, **_k: "S2C_43RDQ_20260930_0_L2A")
    # source="auto" tries the CONUS product first; Lahore is outside it
    monkeypatch.setattr(live, "latest_usable", lambda *_a, **_k: (_ for _ in ()).throw(
        LookupError("conterminous United States only")))

    refetched = []

    def fetch(lat, lon, **_k):
        refetched.append((lat, lon))
        return _observation("S2C_43RDQ_20260930_0_L2A"), []

    monkeypatch.setattr(live_global, "latest_usable", fetch)
    j = client.get("/live/coords", params={"lat": LAT, "lon": LON}).json()
    assert refetched, "a newer scene must trigger a real extraction"
    assert j["observation"]["scene"] == "S2C_43RDQ_20260930_0_L2A"


def test_unreachable_archive_falls_back_to_a_flagged_stale_entry(client, offline, monkeypatch):
    from app.main import _live_cache
    _live_cache.clear()
    _age_the_entry(offline)
    monkeypatch.setattr(live_global, "newest_scene_id", lambda *_a, **_k: "S2C_43RDQ_20260930_0_L2A")

    def down(*_a, **_k):
        raise ConnectionError("imagery archive unreachable")

    monkeypatch.setattr(live_global, "latest_usable", down)
    j = client.get("/live/coords", params={"lat": LAT, "lon": LON}).json()
    assert j["cache"]["stale"] is True, "a stale answer must be labelled, not passed off as current"
    assert "unreachable" in (j["cache"]["note"] or "")
    assert j["observation"]["scene"] == SCENE


def test_non_conus_coordinates_never_reach_the_usgs_product(client, monkeypatch):
    """The USGS feed is CONUS-only; asking it for Lahore must raise rather than return nonsense."""
    def no_tile(*_a, **_k):
        raise LookupError("conterminous United States only")

    monkeypatch.setattr(live, "latest_usable", no_tile)
    r = client.get("/live/coords", params={"lat": LAT, "lon": LON, "source": "usgs"})
    assert r.status_code == 404 and "conterminous" in r.json()["detail"]
