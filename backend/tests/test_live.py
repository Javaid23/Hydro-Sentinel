"""Live extraction logic on synthetic windows (no network): masks, statistics, quality rule, scene parsing."""

from datetime import datetime, timezone

import numpy as np
import pytest

from hydrosentinel import config as C
from hydrosentinel import live


def test_circle_mask_matches_usgs_buffer_geometry():
    m = live._circle_mask(live.WINDOW, live.BUFFER_M / live.GRID_M)
    assert m.shape == (25, 25) and m[12, 12]
    # USGS n_buf in the release is 489 for a full 250 m circle on the 20 m grid
    assert int(m.sum()) == 489
    assert not m[0, 0] and not m[0, 24]


def test_scene_id_parsing_and_urls():
    sid = "S2B_MSIAQR_20260911T190909_N0512_R056_T10TER_20260911T210931"
    m = live.SCENE_RE.match(sid)
    assert m and m.group(1) == "S2B" and m.group(3) == "T10TER"
    sc = live.Scene(sid, "T10TER", "S2B", datetime(2026, 9, 11, 19, 9, 9, tzinfo=timezone.utc))
    assert sc.url("B04").endswith("/version_01/T10TER/" + sid + "_B04.tif")
    assert sc.url("l2_flags").startswith("https://usgs-wma-sentinel-2-aqr-acolite-dsf.s3.us-west-2.amazonaws.com/")


def test_extract_observation_applies_masks_and_stats(monkeypatch):
    """Build synthetic 25×25 layers: flagged ring, dry corner, negative reflectance, one nodata pixel."""
    n = live.WINDOW
    l2 = np.zeros((n, n)); l2[:, :3] = 10000                      # left 3 columns flagged
    ndwi = np.full((n, n), 2000.0); ndwi[:5, :] = -1000            # top 5 rows are land
    bands = {b: np.full((n, n), 300.0 + i * 10) for i, b in enumerate(C.BANDS)}
    bands["B04"][12, 12] = 450.0                                   # centre pixel distinct
    bands["B04"][20, 20] = -5.0                                    # negative → dropped from stats
    bands["B08"][6, 6] = live.NODATA                               # nodata → dropped

    def fake_read(url, lat, lon):
        suf = url.rsplit("_", 1)[-1].replace(".tif", "")
        arr = l2 if suf == "flags" else ndwi if suf == "NDWI" else bands[suf]
        return arr.astype(float), False, (12, 12)

    monkeypatch.setattr(live, "_read_window", fake_read)
    sc = live.Scene("S2A_MSIAQR_20260101T000000_N0512_R001_T10TER_20260101T000000", "T10TER", "S2A",
                    datetime(2026, 1, 1, tzinfo=timezone.utc))
    obs = live.extract_observation(sc, 45.0, -122.0)

    circle = live._circle_mask(n, live.BUFFER_M / live.GRID_M)
    expected_valid = (l2 == 0) & (ndwi > 0) & circle
    assert obs["n_buf"] == 489
    assert obs["n_mask"] == int(expected_valid.sum())
    assert obs["n_l2flag"] == int(((l2 == 0) & circle).sum())
    assert obs["l2flag_center"] == 1 and obs["truncated"] == 0
    assert obs["B04_center"] == 450.0
    assert obs["B04_n_pixels"] == obs["n_mask"] - 1          # the negative pixel is inside the valid area
    assert obs["B08_n_pixels"] == obs["n_mask"] - 1          # the nodata pixel too
    assert obs["B02_n_pixels"] == obs["n_mask"]
    assert obs["B02_buf250_mean"] == pytest.approx(310.0)   # B02 is index 1 in C.BANDS
    assert obs["B02_buf250_std"] == pytest.approx(0.0)
    assert set(C.BAND_MEAN_COLS + C.BAND_STD_COLS + C.BAND_NPIX_COLS + C.SCENE_QA_COLS) <= set(obs)


def test_passes_quality_mirrors_training_filter():
    base = {f"{b}_n_pixels": 50 for b in C.BANDS}
    base.update({f"{b}_buf250_mean": 300.0 for b in C.BANDS})
    base["truncated"] = 0
    assert live.passes_quality(base) == (True, "ok")
    bad = dict(base); bad["B03_n_pixels"] = 2
    assert live.passes_quality(bad)[0] is False and "valid water pixels" in live.passes_quality(bad)[1]
    bad = dict(base); bad["truncated"] = 1
    assert live.passes_quality(bad)[0] is False
    bad = dict(base); bad["B11_buf250_mean"] = float("nan")
    assert live.passes_quality(bad)[0] is False


def test_latest_usable_walks_back_and_reports(monkeypatch):
    scenes = [live.Scene(f"S2A_MSIAQR_2026010{d}T000000_N0512_R001_T10TER_2026010{d}T000000", "T10TER", "S2A",
                         datetime(2026, 1, d, tzinfo=timezone.utc)) for d in (1, 2, 3)]
    monkeypatch.setattr(live, "recent_scenes", lambda tile, n=12, now=None: scenes)
    good = {f"{b}_n_pixels": 40 for b in C.BANDS}; good.update({f"{b}_buf250_mean": 1.0 for b in C.BANDS}); good["truncated"] = 0
    cloudy = dict(good); cloudy.update({f"{b}_n_pixels": 0 for b in C.BANDS})

    def fake_extract(scene, lat, lon):
        if scene.datetime_utc.day == 3:
            return {**cloudy, "n_mask": 0}
        if scene.datetime_utc.day == 2:
            raise ValueError("point outside tile extent")
        return {**good, "n_mask": 40}

    monkeypatch.setattr(live, "extract_observation", fake_extract)
    obs, tried = live.latest_usable(45.0, -122.0, tile="T10TER")
    assert obs is not None and obs["n_mask"] == 40
    assert [t["usable"] for t in tried] == [False, False, True]
    assert "outside" in tried[1]["reason"]


def test_latest_usable_rejects_uncovered_tile(monkeypatch):
    monkeypatch.setattr(live, "recent_scenes", lambda tile, n=12, now=None: [])
    with pytest.raises(LookupError, match="conterminous"):
        live.latest_usable(31.6, 74.3, tile="T43RDQ")
