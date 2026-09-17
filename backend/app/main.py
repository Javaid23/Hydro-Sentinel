"""
HydroSentinel API.

    GET /health
    GET /models                                   model + calibration metadata
    GET /models/{target}/global-importance        global SHAP importance
    GET /sites                                    monitoring sites with observation counts
    GET /sites/{site_id}/observations             available Sentinel-2 observations for a site
    GET /assessment/{site_id}                     full assessment for the latest (or chosen) observation
        ?observation_id=...   score a specific overpass
        ?explain=true         add the LLM explanation (Groq); numeric output is identical either way

One call to /assessment renders the whole dashboard view.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app import schemas
from hydrosentinel import config as C
from hydrosentinel import data, llm
from hydrosentinel.assess import AssessmentService

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
log = logging.getLogger("api")

MODELS_DIR = Path(os.getenv("HS_MODELS_DIR", C.MODELS_DIR))
DATA_DIR = Path(os.getenv("HS_DATA_DIR", C.DATA_PROCESSED))
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
    key = (observation_id, result["model_version"])
    if key not in _explanations:
        _explanations[key] = llm.explain(result)
    return _explanations[key]
