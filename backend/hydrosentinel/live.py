"""
Live Sentinel-2 aquatic reflectance → observation row, from USGS's daily-updated ACOLITE-DSF
product on AWS (public bucket, no credentials).

This is the data path for "what does the satellite say *now*": the training release ends in
September 2024, but the same product keeps being produced. Extraction mirrors USGS's matchup
scripts (data/raw/aqr_matchups/scripts/aqr_observations_*.py):

    - 250 m circular buffer on the product's 20 m grid (25 × 25 window) around the point
    - valid pixel = l2_flags == 0  AND  NDWI > 0  AND  inside the circle
      (USGS additionally intersects an NHD water mask we do not have; their NDWI-only variant
       uses this rule — see docs/decisions.md D6)
    - per band: n_pixels, centre value, mean / std / median over valid pixels; negatives → NaN
    - n_mask = valid pixels, n_l2flag = unflagged pixels in the circle, truncated = window
      clipped by the tile edge

Only the window is read from each cloud-optimised GeoTIFF (HTTP range requests), so a scene
costs a few hundred kB, not the ~400 MB of the full tile.

Also provides `nwis_reading()` — the live USGS sonde value nearest an overpass, for honest
side-by-side display at USGS sites.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import httpx
import numpy as np
import pandas as pd

from hydrosentinel import config as C

log = logging.getLogger(__name__)

BUCKET = "usgs-wma-sentinel-2-aqr-acolite-dsf"
REGION = "us-west-2"
PREFIX = "version_01"
HTTP_BASE = f"https://{BUCKET}.s3.{REGION}.amazonaws.com"
BUFFER_M = 250
GRID_M = 20
WINDOW = int(BUFFER_M / GRID_M) * 2 + 1          # 25
NODATA = -32768
NDWI_THRESH = 0.0
SCENE_RE = re.compile(r"(S2[ABC])_MSIAQR_(\d{8}T\d{6})_N\d{4}_R\d{3}_(T\d{2}[A-Z]{3})_\d{8}T\d{6}")


@dataclass(frozen=True)
class Scene:
    scene_id: str
    tile: str
    satellite: str
    datetime_utc: datetime

    def url(self, suffix: str) -> str:
        return f"{HTTP_BASE}/{PREFIX}/{self.tile}/{self.scene_id}_{suffix}.tif"


# ----------------------------------------------------------------------------- tile lookup
def mgrs_tile(lat: float, lon: float) -> str:
    """MGRS 100 km tile id (e.g. T10TER) for a WGS84 point — the product's folder key."""
    import mgrs  # lazy: optional dependency
    m = mgrs.MGRS().toMGRS(lat, lon, MGRSPrecision=0)   # e.g. '10TER'
    return "T" + m


# ----------------------------------------------------------------------------- scene listing
def _list_keys(prefix: str, max_keys: int = 1000) -> list[str]:
    keys: list[str] = []
    token = None
    with httpx.Client(timeout=30) as cli:
        while True:
            params = {"list-type": "2", "prefix": prefix, "max-keys": str(max_keys)}
            if token:
                params["continuation-token"] = token
            r = cli.get(HTTP_BASE + "/", params=params)
            r.raise_for_status()
            keys += re.findall(r"<Key>(.*?)</Key>", r.text)
            m = re.search(r"<NextContinuationToken>(.*?)</NextContinuationToken>", r.text)
            if not m:
                break
            token = m.group(1)
    return keys


@lru_cache(maxsize=64)
def list_scenes(tile: str, year: int) -> list[Scene]:
    """All scenes of a tile in a year (any satellite), newest last. Cached per process."""
    scenes: dict[str, Scene] = {}
    for sat in ("S2A", "S2B", "S2C"):
        for k in _list_keys(f"{PREFIX}/{tile}/{sat}_MSIAQR_{year}"):
            if not k.endswith("_B04.tif"):
                continue
            sid = k.split("/")[-1][: -len("_B04.tif")]
            m = SCENE_RE.match(sid)
            if m:
                dt = datetime.strptime(m.group(2), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                scenes[sid] = Scene(sid, m.group(3), m.group(1), dt)
    return sorted(scenes.values(), key=lambda s: s.datetime_utc)


def recent_scenes(tile: str, n: int = 12, now: datetime | None = None) -> list[Scene]:
    now = now or datetime.now(timezone.utc)
    out = list_scenes(tile, now.year)
    if len(out) < n:
        out = list_scenes(tile, now.year - 1) + out
    return out[-n:]


# ----------------------------------------------------------------------------- extraction
def _circle_mask(n: int, radius_cells: float) -> np.ndarray:
    c = n // 2
    yy, xx = np.mgrid[:n, :n]
    return ((yy - c) ** 2 + (xx - c) ** 2) <= radius_cells ** 2


def _read_window(url: str, lat: float, lon: float) -> tuple[np.ndarray | None, bool, tuple[int, int]]:
    """Read the WINDOW×WINDOW block centred on (lat, lon). Returns (array or None, truncated, centre_rc)."""
    import rasterio
    from rasterio.windows import Window
    from pyproj import Transformer

    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                      GDAL_HTTP_MULTIRANGE="YES", GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES"):
        with rasterio.open(f"/vsicurl/{url}") as ds:
            x, y = Transformer.from_crs("EPSG:4326", ds.crs, always_xy=True).transform(lon, lat)
            row, col = ds.index(x, y)
            half = WINDOW // 2
            r0, c0 = row - half, col - half
            r1, c1 = r0 + WINDOW, c0 + WINDOW
            rr0, cc0 = max(r0, 0), max(c0, 0)
            rr1, cc1 = min(r1, ds.height), min(c1, ds.width)
            if rr1 <= rr0 or cc1 <= cc0:
                return None, True, (half, half)
            block = ds.read(1, window=Window(cc0, rr0, cc1 - cc0, rr1 - rr0)).astype(float)
            truncated = (rr0 != r0) or (cc0 != c0) or (rr1 != r1) or (cc1 != c1)
            # place into a full-size array so the circle mask aligns; pad with NODATA
            full = np.full((WINDOW, WINDOW), float(NODATA))
            full[rr0 - r0: rr0 - r0 + block.shape[0], cc0 - c0: cc0 - c0 + block.shape[1]] = block
            return full, truncated, (half, half)


def extract_observation(scene: Scene, lat: float, lon: float) -> dict:
    """Band/QA columns for one scene at one point, in the training-table layout."""
    circle = _circle_mask(WINDOW, BUFFER_M / GRID_M)
    out: dict = {"scene": scene.scene_id, "scene_datetime_utc": pd.Timestamp(scene.datetime_utc),
                 "lat": lat, "lon": lon, "tile": scene.tile}

    # all 13 rasters are independent HTTP range reads; GDAL releases the GIL, so read them in parallel
    layers = ["l2_flags", "NDWI"] + list(C.BANDS)
    with ThreadPoolExecutor(max_workers=8) as pool:
        reads = dict(zip(layers, pool.map(lambda suf: _read_window(scene.url(suf), lat, lon), layers)))
    l2, trunc_l2, (rc, cc) = reads["l2_flags"]
    ndwi, trunc_n, _ = reads["NDWI"]
    if l2 is None or ndwi is None:
        raise ValueError("point outside tile extent")
    unflagged = (l2 == 0)                                   # USGS: l2_flags == 0 means "no flag"
    water = (ndwi != NODATA) & (ndwi > NDWI_THRESH)         # NDWI is stored ×10⁴; the sign test is scale-free
    valid = unflagged & water & circle
    out.update({
        "n_buf": int(circle.sum()), "n_l2flag": int((unflagged & circle).sum()),
        "l2flag_center": int(unflagged[rc, cc]), "n_nhd": int((water & circle).sum()),
        "n_mask": int(valid.sum()), "truncated": int(trunc_l2 or trunc_n),
    })

    for b in C.BANDS:
        arr, trunc_b, _ = reads[b]
        if arr is None:
            arr = np.full((WINDOW, WINDOW), np.nan)
        out[f"{b}_center"] = float(arr[rc, cc]) if arr[rc, cc] != NODATA else np.nan
        vals = arr.copy()
        vals[(vals <= NODATA) | (vals < 0)] = np.nan          # USGS: negatives → NaN for bands
        vals = vals[valid]
        vals = vals[~np.isnan(vals)]
        out[f"{b}_n_pixels"] = int(len(vals))
        out[f"{b}_buf250_mean"] = float(vals.mean()) if len(vals) else np.nan
        out[f"{b}_buf250_std"] = float(vals.std()) if len(vals) else np.nan
        out[f"{b}_buf250_med"] = float(np.median(vals)) if len(vals) else np.nan
        out["truncated"] = int(out["truncated"] or trunc_b)
    return out


def passes_quality(obs: dict, f: C.MatchupFilter = C.MATCHUP_FILTER) -> tuple[bool, str]:
    """Same pixel-validity rule the training data was filtered with (docs/data_findings.md §4)."""
    npix = min(obs[f"{b}_n_pixels"] for b in f.pixel_check_bands)
    if npix < f.min_pixels:
        return False, f"only {npix} valid water pixels (cloud, glint or no open water)"
    if f.require_not_truncated and obs["truncated"]:
        return False, "buffer clipped by tile edge"
    if any(np.isnan(obs[f"{b}_buf250_mean"]) for b in C.BANDS):
        return False, "a band has no valid pixels"
    return True, "ok"


def latest_usable(lat: float, lon: float, tile: str | None = None, max_scenes: int = 12) -> tuple[dict | None, list[dict]]:
    """Walk back from the newest scene until one passes the quality rule.

    Returns (observation or None, log of scenes tried with their verdicts).
    """
    tile = tile or mgrs_tile(lat, lon)
    tried: list[dict] = []
    scenes = recent_scenes(tile, n=max_scenes)
    if not scenes:
        raise LookupError(f"no scenes for tile {tile}: the USGS aquatic-reflectance product covers the "
                          "conterminous United States only. A non-US site needs a different imagery source "
                          "(e.g. Copernicus Data Space / Earth Engine), which is not wired in.")
    for scene in reversed(scenes):
        try:
            obs = extract_observation(scene, lat, lon)
        except Exception as exc:  # noqa: BLE001 — network / extent problems are per-scene, keep walking
            tried.append({"scene": scene.scene_id, "date": scene.datetime_utc.isoformat(), "usable": False, "reason": str(exc)})
            continue
        ok, why = passes_quality(obs)
        tried.append({"scene": scene.scene_id, "date": scene.datetime_utc.isoformat(), "usable": ok,
                      "reason": why, "n_mask": obs["n_mask"]})
        if ok:
            return obs, tried
    return None, tried


# ----------------------------------------------------------------------------- live ground truth
NWIS_IV = "https://waterservices.usgs.gov/nwis/iv/"


def nwis_reading(site_no: str, parm_cd: int, at: datetime, window_hours: float = 3.0) -> dict | None:
    """Sonde reading nearest `at` (UTC) within ±window_hours, from the USGS instantaneous-values API."""
    start = (at - timedelta(hours=window_hours)).strftime("%Y-%m-%dT%H:%MZ")
    end = (at + timedelta(hours=window_hours)).strftime("%Y-%m-%dT%H:%MZ")
    try:
        with httpx.Client(timeout=20) as cli:
            r = cli.get(NWIS_IV, params={"format": "json", "sites": site_no, "parameterCd": f"{parm_cd:05d}",
                                         "startDT": start, "endDT": end})
            r.raise_for_status()
            series = r.json()["value"]["timeSeries"]
    except Exception as exc:  # noqa: BLE001
        log.warning("NWIS query failed for %s/%s: %s", site_no, parm_cd, exc)
        return None
    best = None
    for s in series:
        for v in s["values"][0]["value"]:
            try:
                val = float(v["value"])
            except ValueError:
                continue
            t = pd.Timestamp(v["dateTime"]).tz_convert("UTC")
            off = abs((t - pd.Timestamp(at)).total_seconds()) / 3600
            if val >= 0 and (best is None or off < best["offset_hours"]):
                best = {"value": val, "datetime_utc": t.isoformat(), "offset_hours": round(off, 2),
                        "qualifiers": v.get("qualifiers", []), "parm_cd": parm_cd}
    return best


def nwis_readings_for_targets(site_no: str, at: datetime) -> dict[str, dict | None]:
    """Nearest live reading per target, trying each of the target's parameter codes in order."""
    out: dict[str, dict | None] = {}
    for key, t in C.TARGETS.items():
        found = None
        for pc in t.parm_codes:
            found = nwis_reading(site_no, pc, at)
            if found:
                break
        out[key] = found
    return out
