"""
Disk cache for live satellite extractions.

Pulling one observation means a scene listing plus 13 windowed COG reads over the public
internet: 20-60 s on a good connection, minutes on a bad one. The result is *immutable* — a
given scene at a given point always yields the same pixels — so it is safe to cache
indefinitely and cheap to keep.

What this is not: it never invents or ages data. Each entry stores the scene id and its
acquisition datetime, and the dashboard always shows those, so a cached answer is
indistinguishable from a fresh one *because it is the same answer*. `fetched_utc` records when
we retrieved it.

Freshness is two-stage, because the expensive part is the pixels, not the listing:

  within `max_age_hours` (default 12 h)   serve the cached entry, no network at all
  past it                                 ask the imagery archive for the newest scene id — one
                                          cheap call. Same id as cached? The pixels cannot have
                                          changed, so reuse them and `touch()` the entry. A newer
                                          scene? Re-extract.
  network unavailable                     serve the cached entry anyway, flagged `stale`

This keeps a refresh at a couple of seconds when nothing new has been acquired, instead of
re-reading 13 windowed rasters to arrive at the same answer.

    backend/scripts/warm_live_cache.py pre-fetches the demo presets before a recording.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from hydrosentinel import config as C

log = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("HS_LIVE_CACHE", C.ROOT_DIR / "data" / "live_cache"))
MAX_AGE_HOURS = float(os.getenv("HS_LIVE_CACHE_HOURS", "12"))


def key(lat: float, lon: float, source: str) -> str:
    """Coordinates rounded to ~11 m so repeat requests for the same point hit the same entry."""
    return f"{source}_{lat:.4f}_{lon:.4f}".replace("-", "m").replace(".", "p")


def _path(k: str) -> Path:
    return CACHE_DIR / f"{k}.json"


def _jsonable(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, (pd.Timestamp, datetime)):
        return pd.Timestamp(v).isoformat()
    if isinstance(v, float) and np.isnan(v):
        return None
    return v


def load(lat: float, lon: float, source: str, max_age_hours: float | None = None) -> tuple[dict | None, list | None, bool]:
    """Return (observation, scenes_tried, stale). `stale` means the entry is older than the
    freshness window — callers may still use it as a network fallback, flagged as such."""
    p = _path(key(lat, lon, source))
    if not p.exists():
        return None, None, False
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — a corrupt entry must never break a request
        log.warning("live cache unreadable (%s): %s", p.name, exc)
        return None, None, False
    age_h = (time.time() - blob.get("fetched_epoch", 0)) / 3600
    obs = blob["observation"]
    obs["scene_datetime_utc"] = pd.Timestamp(obs["scene_datetime_utc"])
    obs["_cache"] = {"hit": True, "fetched_utc": blob.get("fetched_utc"), "age_hours": round(age_h, 1)}
    return obs, blob.get("scenes_tried"), age_h > (max_age_hours if max_age_hours is not None else MAX_AGE_HOURS)


def save(lat: float, lon: float, source: str, obs: dict, scenes_tried: list) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fetched_epoch": time.time(),
        "lat": lat, "lon": lon, "source": source,
        "observation": {k: _jsonable(v) for k, v in obs.items() if not k.startswith("_")},
        "scenes_tried": scenes_tried,
    }
    p = _path(key(lat, lon, source))
    # atomic write: a half-written entry would be read as corrupt on the next request
    with tempfile.NamedTemporaryFile("w", dir=CACHE_DIR, delete=False, encoding="utf-8", suffix=".tmp") as fh:
        json.dump(payload, fh)
        tmp = Path(fh.name)
    tmp.replace(p)
    log.info("cached live observation %s (scene %s)", p.name, obs.get("scene"))


def entries() -> list[dict]:
    """Summary of what is cached — used by scripts/warm_live_cache.py and the /live/cache endpoint."""
    if not CACHE_DIR.exists():
        return []
    out = []
    for p in sorted(CACHE_DIR.glob("*.json")):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        out.append({
            "key": p.stem, "lat": b.get("lat"), "lon": b.get("lon"), "source": b.get("source"),
            "scene": b["observation"].get("scene"), "scene_datetime_utc": b["observation"].get("scene_datetime_utc"),
            "fetched_utc": b.get("fetched_utc"),
            "age_hours": round((time.time() - b.get("fetched_epoch", 0)) / 3600, 1),
        })
    return out


def touch(lat: float, lon: float, source: str) -> bool:
    """Mark an entry as revalidated now, after confirming its scene is still the newest.

    Only the fetch timestamp changes — the observation is untouched, because the pixels of a
    given scene are immutable.
    """
    p = _path(key(lat, lon, source))
    if not p.exists():
        return False
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
        blob["fetched_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        blob["fetched_epoch"] = time.time()
        blob["revalidated"] = blob.get("revalidated", 0) + 1
        with tempfile.NamedTemporaryFile("w", dir=CACHE_DIR, delete=False, encoding="utf-8", suffix=".tmp") as fh:
            json.dump(blob, fh)
            tmp = Path(fh.name)
        tmp.replace(p)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("could not revalidate cache entry %s: %s", p.name, exc)
        return False
