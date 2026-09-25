"""
Location baselines: a reference distribution built from the satellite archive itself.

The stress score compares a prediction with that site's own historical record (spec Section 6).
At a USGS site that record is *observed sonde readings*. At a new location — the Ravi, the Nile —
there is none, so no percentile can be computed and the dashboard shows no score.

This module builds the missing reference the only way available: extract the same bands at the
same coordinates from past Sentinel-2 scenes, run the same models, and use the resulting
predictions as the distribution.

WHAT THIS IS, AND IS NOT (docs/decisions.md D8)
    It is   an anomaly reference: "today's estimate versus this model's estimates at this exact
            spot across N cloud-free scenes". If the model is biased here — likely, since the
            location is out of distribution — that bias shifts today's prediction and every
            historical one alike, so it largely cancels in a percentile. Relative position is far
            more robust to systematic bias than an absolute value.
    It is   NOT ground truth, and NOT comparable to the observation-based references used at
            training sites. It carries its own label everywhere it is surfaced, and it never
            upgrades the confidence tier: the models remain unvalidated at these locations.

Cost: one extraction per scene (13 windowed COG reads). Scenes are fetched concurrently and the
finished baseline is cached, so a location is slow once and instant afterwards.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from hydrosentinel import config as C
from hydrosentinel import livecache

log = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("HS_BASELINE_CACHE", C.ROOT_DIR / "data" / "baseline_cache"))
MIN_SCENES = 12          # below this a percentile is too coarse to mean anything
TARGET_SCENES = 24       # enough for stable quartiles without a long wait
MAX_ATTEMPTS = 48        # cloud rejects many scenes; cap the work either way
LOOKBACK_DAYS = 730      # two years covers the seasonal cycle at most latitudes
SEARCH_LIMIT = 250       # list the whole window, then sample across it (see _spread)
MIN_SPAN_DAYS = 300      # a baseline narrower than this cannot speak to seasonality
MAX_CLOUD = 40.0
CONCURRENCY = 4          # scenes in flight; each already parallelises its own 13 reads


def _key(lat: float, lon: float) -> str:
    return f"{lat:.4f}_{lon:.4f}".replace("-", "m").replace(".", "p")


def _path(lat: float, lon: float) -> Path:
    return CACHE_DIR / f"{_key(lat, lon)}.json"


def load(lat: float, lon: float) -> dict | None:
    p = _path(lat, lon)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — a corrupt baseline must not break a request
        log.warning("baseline cache unreadable (%s): %s", p.name, exc)
        return None


def save(lat: float, lon: float, blob: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=CACHE_DIR, delete=False, encoding="utf-8", suffix=".tmp") as fh:
        json.dump(blob, fh)
        tmp = Path(fh.name)
    tmp.replace(_path(lat, lon))


def entries() -> list[dict]:
    if not CACHE_DIR.exists():
        return []
    out = []
    for p in sorted(CACHE_DIR.glob("*.json")):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        out.append({"key": p.stem, "lat": b.get("lat"), "lon": b.get("lon"),
                    "n_scenes": b.get("n_scenes"), "built_utc": b.get("built_utc"),
                    "first_scene": b.get("first_scene"), "last_scene": b.get("last_scene")})
    return out


# ----------------------------------------------------------------------------- building
def _spread(scenes: list, n: int, seed: int = C.RANDOM_STATE) -> list:
    """Pick `n` scenes spread across the listing's time range, in a deterministic random order.

    Two biases have to be avoided. Taking the newest N collapses the baseline onto recent weeks:
    at a site where most scenes are cloud-free the build stops after a month of imagery and ends
    up comparing late monsoon against late monsoon. Keeping the spread sample in date order has
    the same effect whenever cloud forces an early stop, because the run is truncated at one end.

    So: sample evenly across the window, then shuffle with a fixed seed. Any prefix is then an
    unbiased sample of the whole period, however many scenes the build gets through.
    """
    if len(scenes) <= n:
        picked = list(scenes)
    else:
        ordered = sorted(scenes, key=lambda s: s.datetime_utc)
        idx = np.unique(np.linspace(0, len(ordered) - 1, n).round().astype(int))
        picked = [ordered[i] for i in idx]
    np.random.default_rng(seed).shuffle(picked)
    return picked


def _extract_one(scene, lat: float, lon: float) -> dict | None:
    """One archive scene → a quality-passing observation, or None. Never raises."""
    from hydrosentinel import live_global as G
    try:
        obs = G.extract_observation(scene, lat, lon)
    except Exception as exc:  # noqa: BLE001 — a single bad scene must not abort the build
        log.debug("baseline scene %s failed: %s", scene.scene_id, exc)
        return None
    ok, _ = G.passes_quality(obs)
    return obs if ok else None


def build(lat: float, lon: float, service, target_scenes: int = TARGET_SCENES,
          max_attempts: int = MAX_ATTEMPTS, progress=None) -> dict:
    """Extract past scenes at (lat, lon), predict each, and summarise the distribution.

    `service` is an AssessmentService — used for its per-target models and the harmonisation
    factors, so the baseline is produced by exactly the same pipeline that scores today's scene.
    """
    from hydrosentinel import features as F
    from hydrosentinel import live_global as G

    t0 = time.time()
    found = G.stac_search(lat, lon, days=LOOKBACK_DAYS, max_cloud=MAX_CLOUD, limit=SEARCH_LIMIT)
    if not found:
        raise LookupError("no Sentinel-2 scenes cover this location in the archive window")
    # Sample across the whole window rather than taking the most recent scenes (see _spread).
    scenes = _spread(found, max_attempts)
    log.info("baseline at %.4f,%.4f: %d scenes in the archive, trying %d spread over %s..%s",
             lat, lon, len(found), len(scenes),
             min(s.datetime_utc for s in found).date(), max(s.datetime_utc for s in found).date())

    harmonisation = G.load_harmonisation()
    observations: list[dict] = []
    attempted = 0
    # Scenes are independent; run a few at a time. Stop as soon as we have enough usable ones.
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for batch_start in range(0, len(scenes), CONCURRENCY):
            batch = scenes[batch_start:batch_start + CONCURRENCY]
            for obs in pool.map(lambda s: _extract_one(s, lat, lon), batch):
                attempted += 1
                if obs is not None:
                    observations.append(G.harmonise(obs, harmonisation))
            if progress:
                progress(len(observations), attempted, len(scenes))
            if len(observations) >= target_scenes:
                break

    if len(observations) < MIN_SCENES:
        raise ValueError(f"only {len(observations)} usable scenes of {attempted} tried "
                         f"(need {MIN_SCENES}); the location may be cloudy, narrow or not open water")

    frame = pd.DataFrame(observations).sort_values("scene_datetime_utc").reset_index(drop=True)
    span_days = int((frame["scene_datetime_utc"].max() - frame["scene_datetime_utc"].min()).days)
    X = F.build_features(frame)

    targets: dict[str, dict] = {}
    for key, art in service.targets.items():
        pred = np.asarray(art.model.predict(X), dtype=float)
        series = [
            {"date": pd.Timestamp(d).isoformat(), "predicted": round(float(v), 3)}
            for d, v in zip(frame["scene_datetime_utc"], pred)
        ]
        q = {f"p{p}": round(float(np.percentile(pred, p)), 3) for p in (5, 10, 25, 50, 75, 90, 95)}
        lo_e, hi_e = max(float(pred.min()), 1e-3), float(pred.max()) * 1.05
        edges = np.geomspace(lo_e, hi_e, 16) if hi_e > lo_e else np.linspace(lo_e, lo_e + 1, 16)
        counts, _ = np.histogram(pred, bins=edges)
        targets[key] = {
            "label": art.meta["label"], "unit": art.meta["unit"],
            "values": [round(float(v), 3) for v in np.sort(pred)],
            "quantiles": q, "series": series,
            "histogram": {"edges": [round(float(e), 4) for e in edges], "counts": [int(c) for c in counts]},
        }

    blob = {
        "lat": lat, "lon": lon,
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_scenes": len(frame), "n_attempted": attempted,
        "first_scene": str(frame["scene_datetime_utc"].min())[:10],
        "last_scene": str(frame["scene_datetime_utc"].max())[:10],
        "lookback_days": LOOKBACK_DAYS,
        "span_days": span_days,
        "covers_seasonal_cycle": span_days >= MIN_SPAN_DAYS,
        "span_warning": (None if span_days >= MIN_SPAN_DAYS else
                         f"These scenes span only {span_days} days, so the reference reflects one part of "
                         f"the year. Today is compared with recent conditions, not the full seasonal range."),
        "source": G.SOURCE_LABEL,
        "kind": "model_predictions",
        "note": ("Reference built from this model's own predictions on past Sentinel-2 scenes at these "
                 "coordinates — not ground truth, and not comparable to the observation-based references "
                 "used at USGS training sites. A percentile against it says how unusual today is for this "
                 "spot; it does not validate the underlying values."),
        "targets": targets,
        "build_seconds": round(time.time() - t0, 1),
    }
    save(lat, lon, blob)
    log.info("built baseline at %.4f,%.4f: %d scenes (%d tried) in %.0fs",
             lat, lon, len(frame), attempted, blob["build_seconds"])
    return blob


# ----------------------------------------------------------------------------- scoring
def percentile_of(blob: dict, target: str, value: float) -> dict | None:
    """Mid-rank percentile of `value` within the baseline's predicted distribution."""
    t = (blob.get("targets") or {}).get(target)
    if not t or not t.get("values"):
        return None
    ref = np.asarray(t["values"], dtype=float)
    less = int(np.searchsorted(ref, value, side="left"))
    equal = int(np.searchsorted(ref, value, side="right")) - less
    pct = 100.0 * (less + 0.5 * equal) / len(ref)
    return {"percentile": round(float(pct), 1), "n_reference": int(len(ref)),
            "quantiles": t["quantiles"], "unit": t["unit"], "label": t["label"]}
