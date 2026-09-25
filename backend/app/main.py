"""
HydroSentinel API.

    GET /health
    GET /models                                   model + calibration metadata
    GET /models/{target}/global-importance        global SHAP importance
    GET /network                                  every site scored on its latest observation,
                                                  ranked — the "what needs attention" view
    GET /validation                                 how the models performed under each split design
    GET /sites                                    monitoring sites with observation counts
    GET /sites/{site_id}/observations             available Sentinel-2 observations for a site
    GET /assessment/{site_id}                     full assessment for the latest (or chosen) observation
        ?observation_id=...   score a specific overpass
        ?explain=true         add the LLM explanation (Groq); numeric output is identical either way
    GET /live/{site_id}                           LIVE: newest usable Sentinel-2 scene from USGS's daily
                                                  product, extracted on the fly, + live sonde readings
    GET /live/coords?lat=&lon=                    LIVE at any coordinates (regional demonstration mode;
                                                  out-of-region, unvalidated)
    GET /live/cache                               what live extractions are cached on disk
    GET /live/baseline?lat=&lon=                  build (or fetch) a location's own reference
                                                  distribution from the Sentinel-2 archive

Live extractions are cached to disk (hydrosentinel/livecache.py): a scene's pixels never change,
so a cached answer is the same answer. Pre-fetch demo locations with scripts/warm_live_cache.py.

One call to /assessment renders the whole dashboard view.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from app import schemas
from hydrosentinel import (
    baseline,
    data,
    features,
    limits,
    live,
    live_global,
    livecache,
    llm,
    netguard,
    stress,
)
from hydrosentinel import config as C
from hydrosentinel.assess import AssessmentService

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
log = logging.getLogger("api")

MODELS_DIR = Path(os.getenv("HS_MODELS_DIR", C.MODELS_DIR))
DATA_DIR = Path(os.getenv("HS_DATA_DIR", C.DATA_PROCESSED))
VALIDATION_VERDICT = {
    "turbidity": "Transfers across basins reasonably; the strongest of the three.",
    "chlorophyll_a": "Usable within regions it has seen; does not transfer to an unseen basin.",
    "cdom": "Fails on unseen sites — 91% of its variance is between sites, not within them.",
}

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("HS_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")]


class State:
    service: AssessmentService
    observations: pd.DataFrame
    sites: pd.DataFrame


state = State()


def _site_table(obs: pd.DataFrame) -> pd.DataFrame:
    g = obs.groupby("site_no")
    sites = g.agg(station_nm=("station_nm", "first"), basin=("basin", "first"), lat=("lat", "first"),
                  lon=("lon", "first"), n_observations=("scene", "size"),
                  first_observation=("scene_datetime_utc", "min"), latest_observation=("scene_datetime_utc", "max"))
    for k in C.TARGETS:
        sites[f"has_{k}"] = g[f"observed_{k}"].apply(lambda s: bool(s.notna().any()))
    return sites.reset_index()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.service = AssessmentService(MODELS_DIR)
    state.observations = data.load_observations(DATA_DIR)
    state.sites = _site_table(state.observations)
    log.info("loaded %d observations at %d sites; models trained %s",
             len(state.observations), len(state.sites), state.service.manifest["trained_utc"])
    yield


app = FastAPI(title="HydroSentinel API", version="0.1.0", lifespan=lifespan,
              description="Observe → Predict → Explain → Assess. Current-condition freshwater assessment from Sentinel-2.")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok", "model_version": state.service.manifest["trained_utc"],
            "n_sites": int(len(state.sites)), "n_observations": int(len(state.observations))}


@app.get("/models", response_model=schemas.ModelInfo)
def models():
    return state.service.describe()


@app.get("/models/{target}/global-importance", response_model=schemas.GlobalImportance)
def global_importance(target: str, top_k: int = Query(10, ge=1, le=36)):
    if target not in state.service.targets:
        raise HTTPException(404, f"unknown target {target}; choose from {list(state.service.targets)}")
    return {"target": target, "features": state.service.global_importance(target, top_k)}


@app.get("/sites", response_model=list[schemas.SiteSummary])
def sites(basin: str | None = None, min_observations: int = Query(0, ge=0)):
    s = state.sites
    if basin:
        s = s[s["basin"].str.lower() == basin.lower()]
    s = s[s["n_observations"] >= min_observations]
    return [
        schemas.SiteSummary(
            site_no=r.site_no, station_nm=r.station_nm, basin=r.basin, lat=float(r.lat), lon=float(r.lon),
            n_observations=int(r.n_observations),
            first_observation=pd.Timestamp(r.first_observation).isoformat(),
            latest_observation=pd.Timestamp(r.latest_observation).isoformat(),
            targets_observed=[k for k in C.TARGETS if getattr(r, f"has_{k}")],
        )
        for r in s.sort_values(["basin", "station_nm"]).itertuples()
    ]


def _guard(request: Request, limiter: limits.RateLimiter, wait: float = 0.0):
    """Apply the rate and concurrency limits for an expensive operation.

    Returns a context manager holding a concurrency slot; raises 429 when the caller has used up
    its allowance or every slot is busy.
    """
    caller = request.client.host if request.client else "unknown"
    try:
        limiter.check(caller)
    except limits.RateLimited as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": str(exc.retry_after)}) from exc
    holder = limits.slot(limiter, wait)
    if not holder.__enter__():
        raise HTTPException(429, f"{limiter.name} capacity in use ({limiter.max_concurrent} at a time); retry shortly",
                            headers={"Retry-After": "20"})
    return holder


def _nn(v):
    """NaN -> None. Columns that mix strings with missing values come back from pandas as NaN,
    which is not JSON and not what the schema declares."""
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    return v


_network_cache: dict | None = None


@app.get("/network", response_model=schemas.NetworkOverview)
def network(basin: str | None = None):
    """Every monitoring site scored on its most recent archived observation, ranked by stress.

    This is a screening view: one pass over the network to see which sites are unusual relative to
    their own records, rather than clicking through them one at a time. Each site's assessment uses
    the same models, references and leave-one-out rule as the detail view; only SHAP is omitted.
    """
    global _network_cache
    if _network_cache is None:
        obs = state.observations
        latest = obs.loc[obs.groupby("site_no")["scene_datetime_utc"].idxmax()].reset_index(drop=True)
        scored = state.service.score_many(latest)

        sites = []
        for (_, meta), (_, row) in zip(latest.iterrows(), scored.iterrows(), strict=True):
            indicators = {
                k: {"prediction": float(row[f"{k}_prediction"]), "percentile": _nn(row[f"{k}_percentile"]),
                    "status": _nn(row[f"{k}_status"]), "reference_level": str(row[f"{k}_reference_level"]),
                    "observed": _nn(row[f"{k}_observed"]), "unit": C.TARGETS[k].unit,
                    "label": C.TARGETS[k].label}
                for k in C.TARGETS
            }
            sites.append({
                "site_no": str(meta["site_no"]), "station_nm": str(meta["station_nm"]),
                "basin": str(meta["basin"]), "lat": float(meta["lat"]), "lon": float(meta["lon"]),
                "observation_id": str(meta["observation_id"]),
                "scene_datetime_utc": pd.Timestamp(meta["scene_datetime_utc"]).isoformat(),
                "stress_score": _nn(row["stress_score"]), "stress_label": _nn(row["stress_label"]),
                "indicators_used": int(row["indicators_used"]),
                "n_observations": int((obs["site_no"] == meta["site_no"]).sum()),
                "indicators": indicators,
            })
        sites.sort(key=lambda s: (s["stress_score"] is None, -(s["stress_score"] or 0)))
        dates = [s["scene_datetime_utc"] for s in sites]
        _network_cache = {
            "sites": sites,
            "n_sites": len(sites),
            "n_scored": sum(s["stress_score"] is not None for s in sites),
            "counts": {label: sum(s["stress_label"] == label for s in sites)
                       for _, label in stress.STRESS_STATUS},
            "elevated": [s["site_no"] for s in sites
                         if any((i["status"] in ("Elevated", "High")) for i in s["indicators"].values())],
            "latest_observation": max(dates) if dates else None,
            "oldest_observation": min(dates) if dates else None,
            "note": ("Each site is scored on its most recent observation in the labelled archive "
                     "(2015-2024), not on imagery from today. Use Live mode for a current scene."),
        }
    out = dict(_network_cache)
    if basin:
        keep = [s for s in out["sites"] if s["basin"].lower() == basin.lower()]
        out = {**out, "sites": keep, "n_sites": len(keep),
               "n_scored": sum(s["stress_score"] is not None for s in keep)}
    return out


@app.get("/validation", response_model=schemas.ValidationSummary)
def validation():
    """Measured model performance under each split design — the evidence behind the confidence tiers.

    Read from the generated evaluation report so the dashboard cannot state anything the scripts
    did not produce.
    """
    path = MODELS_DIR / "xgb_baseline.json"
    if not path.exists():
        raise HTTPException(503, "evaluation results not generated; run scripts/evaluate_xgb.py")
    rows = json.loads(path.read_text(encoding="utf-8"))["results"]
    designs = {"random": "Random split", "site_holdout": "Unseen sites", "lobo": "Unseen basin"}
    targets = {}
    for key in C.TARGETS:
        per_design = {}
        for split, label in designs.items():
            matching = [r for r in rows if r["target"] == key and r["split"] == split]
            if not matching:
                continue
            per_design[split] = {
                "label": label,
                "r2": round(float(np.mean([r["r2"] for r in matching])), 3),
                "r2_log": round(float(np.mean([r["r2_log"] for r in matching])), 3),
                "mae": round(float(np.mean([r["mae"] for r in matching])), 2),
                "n_folds": len(matching),
                "folds": [{"held_out": r["held_out"], "r2": round(float(r["r2"]), 3),
                           "r2_log": round(float(r["r2_log"]), 3)} for r in matching],
            }
        targets[key] = {"label": C.TARGETS[key].label, "unit": C.TARGETS[key].unit,
                        "designs": per_design,
                        "verdict": VALIDATION_VERDICT.get(key, "")}
    return {
        "targets": targets,
        "explanation": ("A random split lets the model see every site during training, so it measures "
                        "interpolation, not generalisation. Holding out whole sites, then whole basins, "
                        "is what the deployed confidence tiers are based on."),
        "source": "models/xgb_baseline.json, generated by backend/scripts/evaluate_xgb.py",
    }


def _site_obs(site_id: str) -> pd.DataFrame:
    o = state.observations[state.observations["site_no"] == site_id]
    if o.empty:
        raise HTTPException(404, f"unknown site {site_id}")
    return o.sort_values("scene_datetime_utc")


@app.get("/sites/{site_id}/observations", response_model=list[schemas.ObservationSummary])
def site_observations(site_id: str, limit: int = Query(50, ge=1, le=1000)):
    o = _site_obs(site_id).tail(limit)
    return [
        schemas.ObservationSummary(
            observation_id=r.observation_id, scene_datetime_utc=pd.Timestamp(r.scene_datetime_utc).isoformat(),
            n_mask=float(r.n_mask),
            observed={k: (None if np.isnan(getattr(r, f"observed_{k}")) else float(getattr(r, f"observed_{k}")))
                      for k in C.TARGETS},
        )
        for r in o.itertuples()
    ]


_history_cache: dict[str, dict] = {}


@app.get("/sites/{site_id}/history", response_model=schemas.SiteHistory)
def site_history(site_id: str):
    """Everything the history / distribution charts need for one site:
    per target — observed & model-predicted series over all overpasses, the site (or basin)
    reference quantiles, a histogram of the reference distribution — plus the site's median
    spectrum. Predictions here are batch point estimates (no SHAP), cached per site."""
    if site_id in _history_cache:
        return _history_cache[site_id]
    o = _site_obs(site_id)
    X = features.build_features(o)
    basin = str(o["basin"].iloc[0])
    targets = {}
    for key, art in state.service.targets.items():
        pred = art.model.predict(X)
        band = art.conformal.predict_interval(X)
        obs_col = o[f"observed_{key}"]
        series = [
            {"date": pd.Timestamp(d).isoformat(), "observation_id": oid,
             "observed": None if np.isnan(v) else round(float(v), 3),
             "predicted": round(float(p), 3), "lower": round(float(lo), 3), "upper": round(float(hi), 3)}
            for d, oid, v, p, lo, hi in zip(o["scene_datetime_utc"], o["observation_id"], obs_col, pred,
                                            band["lower"], band["upper"])
        ]
        ref, level = art.reference.reference_for(site_id, basin)
        if ref is not None and len(ref):
            q = {f"p{int(p)}": round(float(np.percentile(ref, p)), 3) for p in (5, 10, 25, 50, 75, 90, 95)}
            # log-spaced bins suit the heavy-tailed targets; edges in original units
            lo_e, hi_e = max(float(ref.min()), 1e-3), float(ref.max()) * 1.05
            edges = np.geomspace(lo_e, hi_e, 21)
            counts, _ = np.histogram(ref, bins=edges)
            hist = {"edges": [round(float(e), 4) for e in edges], "counts": [int(c) for c in counts]}
        else:
            q, hist = {}, {"edges": [], "counts": []}
        targets[key] = {"label": art.meta["label"], "unit": art.meta["unit"], "series": series,
                        "reference_level": level, "n_reference": int(len(ref)) if ref is not None else 0,
                        "quantiles": q, "histogram": hist}
    spectrum = {b: round(float(o[f"{b}_buf250_mean"].median()), 2) for b in C.BANDS}
    spectrum_iqr = {
        b: [round(float(o[f"{b}_buf250_mean"].quantile(.25)), 2),
            round(float(o[f"{b}_buf250_mean"].quantile(.75)), 2)]
        for b in C.BANDS
    }
    out = {"site_no": site_id, "station_nm": str(o["station_nm"].iloc[0]), "basin": basin,
           "n_observations": int(len(o)), "targets": targets,
           "spectrum_median": spectrum, "spectrum_iqr": spectrum_iqr, "band_wavelength_nm": C.BAND_WAVELENGTH_NM}
    _history_cache[site_id] = out
    return out


@app.get("/assessment/{site_id}", response_model=schemas.Assessment, response_model_exclude_none=False)
def assessment(site_id: str, observation_id: str | None = None, explain: bool = False,
               top_k: int = Query(5, ge=1, le=10)):
    o = _site_obs(site_id)
    if observation_id:
        o = o[o["observation_id"] == observation_id]
        if o.empty:
            raise HTTPException(404, f"observation {observation_id} not found at site {site_id}")
    row = o.iloc[-1]
    result = state.service.assess(row, top_k=top_k)
    if explain:
        result["llm_explanation"], result["llm_error"] = _cached_explanation(row["observation_id"], result)
    return result


_explanations: dict[tuple[str, str], tuple[dict | None, str | None]] = {}


def _cached_explanation(observation_id: str, result: dict) -> tuple[dict | None, str | None]:
    """Cache successful explanations per observation; failures are retried on the next request."""
    key = (observation_id, result["model_version"])
    if key not in _explanations:
        out, err = llm.explain(result)
        if err is not None:
            return None, err
        _explanations[key] = (out, None)
    return _explanations[key]


# ----------------------------------------------------------------------------- live mode
EXTRACTION_NOTE = ("Bands extracted on the fly from the newest usable scene: 250 m buffer on the 20 m grid, "
                   "valid = unflagged (l2_flags==0) AND water (NDWI>0). Training data used an additional NHD "
                   "water mask; see docs/decisions.md D6.")

_live_cache: dict[str, dict] = {}


def _attach_baseline(result: dict, lat: float, lon: float) -> dict | None:
    """Where today's predictions sit in this location's own satellite record, if one is built.

    Only used where no observation-based reference exists (out of region). It is reported under
    its own key with its own wording — it never becomes `stress`, and never raises the confidence
    tier, because the models are still unvalidated here.
    """
    if all(i.get("percentile") is not None for i in result["indicators"].values()):
        return None                      # a real, observation-based reference already applies
    blob = baseline.load(lat, lon)
    if not blob:
        return {"available": False, "reason": "not built for this location yet",
                "build_url": f"/live/baseline?lat={lat}&lon={lon}"}
    indicators, pcts = {}, {}
    for key, ind in result["indicators"].items():
        got = baseline.percentile_of(blob, key, ind["prediction"])
        if not got:
            continue
        pcts[key] = got["percentile"]
        indicators[key] = {**got, "status": stress.indicator_status(got["percentile"]),
                           "prediction": ind["prediction"]}
    if not indicators:
        return {"available": False, "reason": "baseline has no usable targets"}
    score = stress.stress_score(pcts)
    return {
        "available": True,
        "name": "Local Anomaly Score",
        "description": ("How unusual today's estimates are compared with this model's own estimates at "
                        "these coordinates across the archive. Not the Freshwater Stress Score: the "
                        "reference is model output, not measurements."),
        "kind": blob["kind"], "note": blob["note"], "source": blob["source"],
        "n_scenes": blob["n_scenes"], "first_scene": blob["first_scene"], "last_scene": blob["last_scene"],
        "built_utc": blob["built_utc"],
        "span_days": blob.get("span_days"), "covers_seasonal_cycle": blob.get("covers_seasonal_cycle"),
        "span_warning": blob.get("span_warning"),
        "score": score["score"], "label": score["label"],
        "indicators": indicators,
        "targets": {k: {"histogram": v["histogram"], "series": v["series"]} for k, v in blob["targets"].items()},
    }


def _stale_fallback(lat: float, lon: float, source: str, note: str) -> tuple[dict, list, str, dict] | None:
    """The last successfully extracted scene here, flagged stale, or None if nothing is cached.

    Used whenever a live fetch cannot produce a current observation. A stale real measurement that
    says it is stale is more useful than an error; what it must never do is look current.
    """
    for src in (("usgs", "global") if source == "auto" else (source,)):
        cached, tried, _ = livecache.load(lat, lon, src)
        if cached is not None:
            info = cached.pop("_cache")
            log.info("serving stale cache (%s, %.1f h old) at %.4f,%.4f: %s",
                     src, info["age_hours"], lat, lon, note)
            return cached, tried or [], src, {**info, "stale": True, "note": note}
    return None


def _fetch_live(lat: float, lon: float, source: str) -> tuple[dict, list, str, dict | None]:
    """Get one live observation, preferring a fresh disk-cached copy.

    Order: fresh cache -> network -> stale cache (flagged). Returns
    (observation, scenes_tried, source_key, cache_info-or-None).
    """
    for src in (("usgs", "global") if source == "auto" else (source,)):
        obs, tried, stale = livecache.load(lat, lon, src)
        if obs is None:
            continue
        info = obs.pop("_cache")
        if not stale:
            log.info("live cache hit (%s, %.1f h old) at %.4f,%.4f", src, info["age_hours"], lat, lon)
            return obs, tried or [], src, {**info, "stale": False}
        # Past the freshness window: one listing call is far cheaper than re-reading 13 rasters.
        try:
            newest = (live.newest_scene_id(lat, lon) if src == "usgs" else live_global.newest_scene_id(lat, lon))
        except Exception as exc:  # noqa: BLE001 — fall through to a full fetch, which handles failure
            log.info("could not revalidate %s cache at %.4f,%.4f: %s", src, lat, lon, exc)
            newest = None
        if newest and newest == obs.get("scene"):
            livecache.touch(lat, lon, src)
            log.info("live cache revalidated (%s): %s is still the newest scene", src, newest)
            return obs, tried or [], src, {**info, "stale": False, "revalidated": True}

    used, obs, tried = None, None, []
    try:
        if source in ("auto", "usgs"):
            try:
                obs, tried = live.latest_usable(lat, lon)
                used = "usgs"
            except LookupError as exc:
                if source == "usgs":
                    raise HTTPException(404, str(exc)) from exc
        if obs is None and source in ("auto", "global"):
            obs, tried_g = live_global.latest_usable(lat, lon)
            tried = tried + tried_g
            used = "global"
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — network failures fall back to a stale copy if we have one
        log.warning("live extraction failed at %.4f,%.4f: %s", lat, lon, exc)
        fallback = _stale_fallback(lat, lon, source,
                                   "imagery service was unreachable; showing the last successfully "
                                   "retrieved scene for this location")
        if fallback is not None:
            return fallback
        raise HTTPException(503, f"imagery service unreachable or failed ({type(exc).__name__}); retry shortly") from exc

    if obs is None:
        # The archive answered, but nothing it offered was usable — cloud, glint or no open water.
        # That is routine, so a previously extracted scene is better than an error, provided it is
        # labelled stale rather than passed off as current.
        fallback = _stale_fallback(lat, lon, source,
                                   "no usable scene in the latest overpasses (cloud, glint or no open "
                                   "water); showing the last successfully retrieved scene for this location")
        if fallback is not None:
            return fallback
        raise HTTPException(503, f"no usable recent scene at this location (cloud/glint/no open water in the last "
                                 f"{len(tried)} overpasses): " + "; ".join(f"{t['date'][:10]} {t['reason']}" for t in tried))
    livecache.save(lat, lon, used, obs, tried)
    return obs, tried, used, None


def _live_assess(lat: float, lon: float, site_no: str | None, station_nm: str | None, basin: str | None,
                 explain: bool, top_k: int, cache_key: str, source: str = "auto") -> dict:
    """source: 'usgs' (CONUS aquatic reflectance), 'global' (Sentinel-2 L2A, harmonised), or 'auto' = usgs then global."""
    cache_key = f"{cache_key}|{source}"
    if cache_key in _live_cache:
        result = dict(_live_cache[cache_key])
    else:
        obs, tried, used, cached = _fetch_live(lat, lon, source)
        obs.update({"site_no": site_no, "station_nm": station_nm, "basin": basin,
                    "observation_id": f"live_{site_no or 'coords'}_{obs['scene_datetime_utc']:%Y%m%dT%H%M%S}"})
        readings = live.nwis_readings_for_targets(site_no, obs["scene_datetime_utc"]) if site_no else {}
        # matched live readings are display-only; they also drive the leave-one-out rule if the
        # value happened to be in the reference (it never is for post-2024 scenes)
        for k, r in readings.items():
            obs[f"observed_{k}"] = r["value"] if r else np.nan
        result = state.service.assess(pd.Series(obs), top_k=top_k)
        result.update({
            "mode": "live", "scenes_tried": tried, "live_readings": readings,
            "source": ("USGS Sentinel-2 ACOLITE-DSF aquatic reflectance (AWS, updated daily)" if used == "usgs"
                       else live_global.SOURCE_LABEL),
            "source_key": used,
            "extraction_note": EXTRACTION_NOTE if used == "usgs" else live_global.EXTRACTION_NOTE,
            "harmonisation": obs.get("harmonisation"),
            "cloud_cover": obs.get("cloud_cover"),
            "cache": cached,
            "ood": state.service.ood_check(pd.Series(obs)),
        })
        result["local_baseline"] = _attach_baseline(result, lat, lon)
        _live_cache[cache_key] = dict(result)
    if explain:
        result["llm_explanation"], result["llm_error"] = _cached_explanation(result["observation"]["observation_id"], result)
    return result


@app.get("/live/cache")
def live_cache_status():
    """What live extractions are cached on disk (scene id, acquisition time, when fetched)."""
    return {"cache_dir": str(livecache.CACHE_DIR), "max_age_hours": livecache.MAX_AGE_HOURS,
            "entries": livecache.entries()}


@app.get("/live/baseline")
def live_baseline(request: Request, lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
                  rebuild: bool = False, scenes: int = Query(baseline.TARGET_SCENES, ge=12, le=40)):
    """Build (or return) this location's own reference distribution from the Sentinel-2 archive.

    Slow the first time — it extracts and scores past scenes — then cached. Used where no
    observation-based reference exists; see hydrosentinel/baseline.py for what it does and does
    not claim.
    """
    if not rebuild:
        blob = baseline.load(lat, lon)
        if blob:
            return {**blob, "cached": True,
                    "targets": {k: {kk: vv for kk, vv in v.items() if kk != "values"}
                                for k, v in blob["targets"].items()}}
    holder = _guard(request, limits.BASELINE)
    try:
        blob = baseline.build(lat, lon, state.service, target_scenes=scenes)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.warning("baseline build failed at %.4f,%.4f: %s", lat, lon, exc)
        raise HTTPException(503, f"could not build a baseline ({type(exc).__name__}); retry shortly") from exc
    finally:
        holder.__exit__(None, None, None)
    return {**blob, "cached": False,
            "targets": {k: {kk: vv for kk, vv in v.items() if kk != "values"} for k, v in blob["targets"].items()}}


@app.get("/live/baselines")
def live_baselines():
    """Which locations have a baseline built."""
    return {"cache_dir": str(baseline.CACHE_DIR), "entries": baseline.entries()}


@app.get("/live/coords", response_model=schemas.LiveAssessment)
def live_coords(request: Request, lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
                name: str | None = Query(None, max_length=200), explain: bool = False,
                top_k: int = Query(5, ge=1, le=10),
                source: str = Query("auto", pattern="^(auto|usgs|global)$")):
    """Regional demonstration mode: any coordinates, no site history → out_of_region tier, no percentiles.
    Inside the conterminous US the USGS aquatic-reflectance product is used; elsewhere (or with
    source=global) Sentinel-2 L2A is harmonised to it."""
    key = f"coords:{lat:.4f},{lon:.4f}"
    label = netguard.safe_label(name, f"{lat:.4f}, {lon:.4f}")
    holder = _guard(request, limits.LIVE)
    try:
        return _live_assess(lat, lon, None, label, None, explain, top_k, key, source)
    finally:
        holder.__exit__(None, None, None)


@app.get("/live/{site_id}", response_model=schemas.LiveAssessment)
def live_site(request: Request, site_id: str, explain: bool = False, top_k: int = Query(5, ge=1, le=10)):
    """Live assessment at a training-data site: newest usable scene + the site's own reference history."""
    s = state.sites[state.sites["site_no"] == site_id]
    if s.empty:
        raise HTTPException(404, f"unknown site {site_id}")
    r = s.iloc[0]
    holder = _guard(request, limits.LIVE)
    try:
        return _live_assess(float(r.lat), float(r.lon), site_id, r.station_nm, r.basin, explain, top_k,
                            f"site:{site_id}")
    finally:
        holder.__exit__(None, None, None)
