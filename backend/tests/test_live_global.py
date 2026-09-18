"""Global (Sentinel-2 L2A) source: masks, offset handling, harmonisation — on synthetic windows, no network."""

from datetime import datetime, timezone

import numpy as np
import pytest

from hydrosentinel import config as C
from hydrosentinel import live_global as G


def _scene(offset_applied=True):
    assets = {"scl": "https://x/scl.tif", **{a: f"https://x/{a}.tif" for a in G.ASSET_FOR_BAND.values()}}
    return G.GlobalScene("S2A_43RDQ_20260918_1_L2A", "T43RDQ", "S2A", datetime(2026, 9, 18, tzinfo=timezone.utc),
                         8.0, assets, offset_applied)


def _fake_reads(scl, bands_by_asset):
    def fake(url, lat, lon):
        key = url.rsplit("/", 1)[-1].replace(".tif", "")
        arr = scl if key == "scl" else bands_by_asset[key]
        return arr.astype(float), False, (12, 12)
    return fake


def test_scl_water_or_ndwi_and_cloud_flags(monkeypatch):
    n = G.WINDOW
    scl = np.full((n, n), 5.0)                 # bare soil everywhere...
    scl[8:17, :] = 6                            # ...a horizontal band of SCL water
    scl[:, 20:] = 9                             # cloud on the right
    green = np.full((n, n), 300.0); nir = np.full((n, n), 500.0)   # NDWI < 0 everywhere (turbid-river case)
    nir[0:3, :] = 100.0                                            # NDWI > 0 in the top rows (but they are soil per SCL)
    bands = {a: np.full((n, n), 400.0) for a in G.ASSET_FOR_BAND.values()}
    bands["green"], bands["nir"] = green, nir
    monkeypatch.setattr(G, "_read_window_resampled", _fake_reads(scl, bands))
    obs = G.extract_observation(_scene(), 31.6, 74.3)
    circle = G._circle_mask(n, G.BUFFER_M / G.GRID_M)
    unflagged = scl != 9
    water = (scl == 6) | (((green - nir) / (green + nir)) > 0)
    assert obs["n_mask"] == int((unflagged & water & circle).sum())
    assert obs["n_scl_water"] == int(((scl == 6) & circle).sum())
    assert obs["n_l2flag"] == int((unflagged & circle).sum())
    assert obs["l2flag_center"] == 1 and obs["scl_center"] == 6
    assert obs["B04_buf250_mean"] == pytest.approx(400.0)
    assert obs["share_clipped"] == 0


def test_offset_only_subtracted_when_not_already_applied(monkeypatch):
    n = G.WINDOW
    scl = np.full((n, n), 6.0)
    bands = {a: np.full((n, n), 1300.0) for a in G.ASSET_FOR_BAND.values()}
    monkeypatch.setattr(G, "_read_window_resampled", _fake_reads(scl, bands))
    applied = G.extract_observation(_scene(offset_applied=True), 0, 0)
    raw = G.extract_observation(_scene(offset_applied=False), 0, 0)
    assert applied["B04_buf250_mean"] == pytest.approx(1300.0)       # Earth Search COGs: already offset-corrected
    assert raw["B04_buf250_mean"] == pytest.approx(300.0)            # raw baseline >= 04.00: subtract 1000


def test_negative_values_are_clipped_and_counted(monkeypatch):
    n = G.WINDOW
    scl = np.full((n, n), 6.0)
    bands = {a: np.full((n, n), 200.0) for a in G.ASSET_FOR_BAND.values()}
    bands["blue"][:, :12] = -50.0                                     # negative blue on the left half
    monkeypatch.setattr(G, "_read_window_resampled", _fake_reads(scl, bands))
    obs = G.extract_observation(_scene(), 0, 0)
    assert obs["B02_n_negative"] > 0 and obs["n_clipped_negative"] == obs["B02_n_negative"]
    assert 0 < obs["share_clipped"] < 1
    assert obs["B02_buf250_mean"] >= 0                               # clipped, not NaN: the pixel count is kept
    assert obs["B02_n_pixels"] == obs["n_mask"]


def test_harmonise_divides_band_stats_only():
    obs = {f"{b}_buf250_mean": 400.0 for b in C.BANDS}
    obs.update({f"{b}_buf250_std": 40.0 for b in C.BANDS})
    obs.update({f"{b}_buf250_med": 390.0 for b in C.BANDS})
    obs.update({f"{b}_center": 410.0 for b in C.BANDS})
    obs.update({f"{b}_n_pixels": 100 for b in C.BANDS})
    obs["n_mask"] = 100
    h = {"factors": {b: 2.0 for b in C.BANDS}, "spread": {}, "n_pairs": 9, "n_sites": 3, "method": "test"}
    out = G.harmonise(obs, h)
    assert out["B04_buf250_mean"] == 200.0 and out["B04_buf250_std"] == 20.0 and out["B04_center"] == 205.0
    assert out["B04_n_pixels"] == 100 and out["n_mask"] == 100
    assert out["harmonisation"]["applied"] and out["harmonisation"]["n_pairs"] == 9
    assert obs["B04_buf250_mean"] == 400.0                           # input not mutated
    none = G.harmonise(obs, None)
    assert none["harmonisation"]["applied"] is False and none["B04_buf250_mean"] == 400.0
