"""
Global Sentinel-2 source: L2A surface reflectance from the public AWS archive via the Earth Search
STAC API — worldwide, no credentials. Used where USGS's CONUS aquatic-reflectance product has no
coverage (e.g. the Ravi, Chenab and Indus rivers).

CAVEAT, surfaced in the API as `source` / `extraction_note` (docs/decisions.md D7): Sen2Cor is a
land-oriented atmospheric correction, while the training data are ACOLITE-DSF *aquatic*
reflectance. Over water the two differ systematically (sun-glint and aerosol handling), so the
model input is shifted relative to what it learned from — on top of the location being out of
region. The dashboard states this every time this source is used.

Extraction mirrors live.extract_observation() so the output columns are identical:
    - all assets resampled onto the 20 m, 25 × 25 window (10 m bands averaged 2×2, 60 m nearest)
    - "unflagged" = Sen2Cor scene-classification (SCL) not in {nodata, saturated, cloud shadow,
      cloud, cirrus, snow}   — the l2_flags == 0 analogue
    - water = Sen2Cor SCL water class OR NDWI > 0. NDWI alone fails on very turbid rivers under
      Sen2Cor (NIR exceeds green, e.g. the Ravi at Lahore: SCL marks 169 water pixels, NDWI 3)
    - reflectance in the USGS ×10⁴ convention (Earth Search COGs already have the BOA offset
      removed; see L2A_OFFSET_DN). Any negative values are clipped to 0 and counted
      (`n_clipped_negative`, `share_clipped`) so a shift from training inputs stays visible
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
import pandas as pd

from hydrosentinel import config as C
from hydrosentinel.live import BUFFER_M, GRID_M, NDWI_THRESH, WINDOW, _circle_mask, passes_quality
from hydrosentinel.netguard import BlockedURL, allowed_url

STAC_SEARCH = "https://earth-search.aws.element84.com/v1/search"
STAC_COLLECTION = "sentinel-2-l2a"
SOURCE_LABEL = "Copernicus Sentinel-2 L2A (Sen2Cor surface reflectance) via AWS Earth Search"
EXTRACTION_NOTE = ("Bands extracted on the fly from Sentinel-2 L2A: 250 m buffer on a 20 m grid, valid = not cloud/shadow/snow "
                   "per the Sen2Cor scene classification AND water (SCL water class or NDWI>0). This is Sen2Cor land-oriented "
                   "surface reflectance, not the ACOLITE aquatic reflectance the models were trained on; band values are "
                   "divided by empirical L2A/ACOLITE factors measured at US training sites (docs/decisions.md D7), which "
                   "adds uncertainty the intervals do not capture.")

# training band → Earth Search asset key
ASSET_FOR_BAND = {"B01": "coastal", "B02": "blue", "B03": "green", "B04": "red", "B05": "rededge1",
                  "B06": "rededge2", "B07": "rededge3", "B08": "nir", "B8A": "nir08", "B11": "swir16", "B12": "swir22"}
SCL_FLAGGED = {0, 1, 3, 8, 9, 10, 11}      # nodata, saturated, cloud shadow, cloud med/high, cirrus, snow
SCL_WATER = 6
log = logging.getLogger(__name__)

L2A_OFFSET_DN = 1000                        # BOA_ADD_OFFSET (baseline >= 04.00): reflectance = (DN - 1000) * 1e-4.
                                            # Earth Search COGs carry `earthsearch:boa_offset_applied: true`, meaning the
                                            # offset has ALREADY been removed (DN = reflectance * 1e4 directly), despite
                                            # the asset metadata still listing offset -0.1. Verified 2026-09-18 at
                                            # Portland: water red DN 293 (= 0.029) vs USGS AQR 0.020; subtracting again
                                            # would give -0.07. So we subtract only when the flag is False.


@dataclass(frozen=True)
class GlobalScene:
    scene_id: str
    tile: str
    satellite: str
    datetime_utc: datetime
    cloud_cover: float
    assets: dict
    offset_applied: bool


def stac_search(lat: float, lon: float, days: int = 60, max_cloud: float = 60.0, limit: int = 12) -> list[GlobalScene]:
    """Recent L2A scenes covering the point, newest first."""
    now = datetime.now(UTC)
    body = {
        "collections": [STAC_COLLECTION],
        "intersects": {"type": "Point", "coordinates": [lon, lat]},
        "datetime": f"{(now - timedelta(days=days)):%Y-%m-%dT%H:%M:%SZ}/{now:%Y-%m-%dT%H:%M:%SZ}",
        "query": {"eo:cloud_cover": {"lt": max_cloud}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        "limit": limit,
    }
    with httpx.Client(timeout=60) as cli:
        r = cli.post(STAC_SEARCH, json=body)
        r.raise_for_status()
        feats = r.json().get("features", [])
    out = []
    for f in feats:
        p, a = f["properties"], f["assets"]
        if not all(k in a for k in list(ASSET_FOR_BAND.values()) + ["scl"]):
            continue
        # Asset hrefs are supplied by a third party. Check every one against the imagery
        # allowlist here, so a compromised or spoofed catalogue cannot steer GDAL elsewhere.
        try:
            assets = {k: allowed_url(v["href"]) for k, v in a.items() if isinstance(v.get("href"), str)}
        except BlockedURL as exc:
            log.warning("skipping scene %s: %s", f.get("id"), exc)
            continue
        if not all(k in assets for k in list(ASSET_FOR_BAND.values()) + ["scl"]):
            continue
        out.append(GlobalScene(
            scene_id=str(f["id"]), tile=str(p.get("grid:code", "")).replace("MGRS-", "T"),
            satellite=str(p.get("platform", "")).replace("sentinel-", "S").upper()[:3],
            datetime_utc=pd.Timestamp(p["datetime"]).tz_convert("UTC").to_pydatetime(),
            cloud_cover=float(p.get("eo:cloud_cover", float("nan"))),
            assets=assets,
            offset_applied=bool(p.get("earthsearch:boa_offset_applied", p.get("s2:boa_offset_applied", True))),
        ))
    return out


def _read_window_resampled(url: str, lat: float, lon: float) -> tuple[np.ndarray | None, bool, tuple[int, int]]:
    """Read the block around the point and resample it onto the 20 m WINDOW grid
    (10 m assets averaged, 60 m nearest), so every band lands on the same 25 x 25 grid."""
    import rasterio
    from pyproj import Transformer
    from rasterio.enums import Resampling
    from rasterio.windows import Window

    url = allowed_url(url)          # never hand GDAL an address we did not expect
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        with rasterio.open(f"/vsicurl/{url}") as ds:
            x, y = Transformer.from_crs("EPSG:4326", ds.crs, always_xy=True).transform(lon, lat)
            res = ds.res[0]
            scale = GRID_M / res                       # native pixels per 20 m cell: 2, 1 or 1/3
            size = max(1, int(round(WINDOW * scale)))
            row, col = ds.index(x, y)
            r0, c0 = int(round(row - size / 2)), int(round(col - size / 2))
            r1, c1 = r0 + size, c0 + size
            rr0, cc0, rr1, cc1 = max(r0, 0), max(c0, 0), min(r1, ds.height), min(c1, ds.width)
            if rr1 <= rr0 or cc1 <= cc0:
                return None, True, (WINDOW // 2, WINDOW // 2)
            truncated = (rr0, cc0, rr1, cc1) != (r0, c0, r1, c1)
            resampling = Resampling.average if res < GRID_M else Resampling.nearest
            block = ds.read(1, window=Window(cc0, rr0, cc1 - cc0, rr1 - rr0), out_shape=(WINDOW, WINDOW),
                            resampling=resampling).astype(float)
            return block, truncated, (WINDOW // 2, WINDOW // 2)


def extract_observation(scene: GlobalScene, lat: float, lon: float) -> dict:
    circle = _circle_mask(WINDOW, BUFFER_M / GRID_M)
    out: dict = {"scene": scene.scene_id, "scene_datetime_utc": pd.Timestamp(scene.datetime_utc),
                 "lat": lat, "lon": lon, "tile": scene.tile, "cloud_cover": scene.cloud_cover}
    layers = {"scl": scene.assets["scl"], **{b: scene.assets[ASSET_FOR_BAND[b]] for b in C.BANDS}}
    with ThreadPoolExecutor(max_workers=8) as pool:
        reads = dict(zip(layers, pool.map(lambda u: _read_window_resampled(u, lat, lon), layers.values())))
    scl, trunc, (rc, cc) = reads["scl"]
    if scl is None:
        raise ValueError("point outside scene extent")
    scl_i = np.rint(scl)                                   # categorical; nearest-neighbour resampled
    unflagged = ~np.isin(scl_i, list(SCL_FLAGGED))

    bands: dict[str, np.ndarray] = {}
    for b in C.BANDS:
        arr, tb, _ = reads[b]
        trunc = trunc or tb
        if arr is None:
            bands[b] = np.full((WINDOW, WINDOW), np.nan)
            continue
        v = arr.copy()
        v[v == 0] = np.nan                                  # L2A nodata
        if not scene.offset_applied:
            v = v - L2A_OFFSET_DN                           # raw baseline >= 04.00 DN -> reflectance x 1e4
        bands[b] = v

    g, n = bands["B03"], bands["B08"]
    ndwi = (g - n) / (g + n + 1e-6)
    water = (scl_i == SCL_WATER) | (np.isfinite(ndwi) & (ndwi > NDWI_THRESH))
    valid = unflagged & water & circle
    out.update({
        "n_buf": int(circle.sum()), "n_l2flag": int((unflagged & circle).sum()),
        "l2flag_center": int(unflagged[rc, cc]), "n_nhd": int((water & circle).sum()),
        "n_mask": int(valid.sum()), "truncated": int(trunc),
        "scl_center": int(scl_i[rc, cc]), "n_scl_water": int(((scl_i == SCL_WATER) & circle).sum()),
    })
    n_clipped = 0
    n_total = 0
    for b in C.BANDS:
        arr = bands[b]
        out[f"{b}_center"] = float(arr[rc, cc]) if np.isfinite(arr[rc, cc]) else np.nan
        vals = arr[valid]
        vals = vals[~np.isnan(vals)]
        neg = int((vals < 0).sum())
        n_clipped += neg
        n_total += len(vals)
        out[f"{b}_n_negative"] = neg
        vals = np.clip(vals, 0, None)                       # Sen2Cor negatives -> 0 (counted above)
        out[f"{b}_n_pixels"] = int(len(vals))
        out[f"{b}_buf250_mean"] = float(vals.mean()) if len(vals) else np.nan
        out[f"{b}_buf250_std"] = float(vals.std()) if len(vals) else np.nan
        out[f"{b}_buf250_med"] = float(np.median(vals)) if len(vals) else np.nan
    out["n_clipped_negative"] = n_clipped
    out["share_clipped"] = round(n_clipped / n_total, 3) if n_total else None
    return out


def latest_usable(lat: float, lon: float, max_scenes: int = 12) -> tuple[dict | None, list[dict]]:
    tried: list[dict] = []
    for scene in stac_search(lat, lon, limit=max_scenes):
        try:
            obs = extract_observation(scene, lat, lon)
        except Exception as exc:  # noqa: BLE001 - per-scene problems: keep walking back
            tried.append({"scene": scene.scene_id, "date": scene.datetime_utc.isoformat(), "usable": False, "reason": str(exc)})
            continue
        ok, why = passes_quality(obs)
        tried.append({"scene": scene.scene_id, "date": scene.datetime_utc.isoformat(), "usable": ok, "reason": why,
                      "n_mask": obs["n_mask"]})
        if ok:
            return harmonise(obs, load_harmonisation()), tried
    return None, tried


# ----------------------------------------------------------------------------- harmonisation
HARMONISATION_PATH = C.MODELS_DIR / "harmonisation_l2a.json"


def load_harmonisation(path=HARMONISATION_PATH) -> dict | None:
    """Per-band L2A/AQR factors from scripts/harmonise_l2a.py, or None if the study has not been run."""
    import json
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def harmonise(obs: dict, h: dict | None) -> dict:
    """Divide L2A band statistics by the empirical L2A/AQR factor so the model sees ACOLITE-like inputs.

    Means, medians, centre values and stds are all scaled (std scales with the mean). Pixel counts
    and masks are untouched. The observation records what was applied and the factor spread so the
    API can report it.
    """
    out = dict(obs)
    if not h:
        out["harmonisation"] = {"applied": False, "reason": "no harmonisation study on disk"}
        return out
    for b in C.BANDS:
        f = h["factors"].get(b)
        if not f or f <= 0:
            continue
        for stat in ("buf250_mean", "buf250_std", "buf250_med", "center"):
            k = f"{b}_{stat}"
            if k in out and out[k] is not None and np.isfinite(out[k]):
                out[k] = out[k] / f
    out["harmonisation"] = {
        "applied": True, "factors": h["factors"], "spread": h["spread"],
        "n_pairs": h["n_pairs"], "n_sites": h["n_sites"], "method": h["method"],
    }
    return out


def newest_scene_id(lat: float, lon: float) -> str | None:
    """Id of the most recent L2A scene covering the point — STAC listing only, no pixel reads."""
    scenes = stac_search(lat, lon, limit=1)
    return scenes[0].scene_id if scenes else None
