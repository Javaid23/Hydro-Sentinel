# HydroSentinel

**Observe → Predict → Explain → Assess**

Satellite-based, uncertainty-aware freshwater ecosystem assessment. HydroSentinel estimates
turbidity, chlorophyll-a and CDOM from Sentinel-2 aquatic reflectance, scores how unusual the
current condition is against a site's own history, explains the prediction with SHAP, quantifies
uncertainty with conformal prediction, and turns the result into plain-language decision support.

Three modes: **Historical** (the labelled 2015–2024 matchups), **Live** (the newest usable
Sentinel-2 scene from USGS's daily aquatic-reflectance product, extracted on the fly, with the live
USGS sonde reading beside the prediction), and **Regional demo** (any coordinates in the
conterminous US, explicitly flagged as out-of-region and unvalidated).

Built for the **OneAquaHealth IEEE Global Hackathon 2026** (Resilience Informatics track;
secondary: AI-Supported Assessment).

> The system answers: *"What is the estimated current condition, how unusual is it, and what is
> driving the prediction?"* It does **not** forecast future conditions.

## Layout

```
backend/            FastAPI service + modelling package
  hydrosentinel/    data, features, models, uncertainty, explain, stress, llm
  app/              API (routers, schemas)
  scripts/          inspect_data.py, train.py, evaluate_lobo.py ...
  tests/
frontend/           React dashboard
data/raw/           USGS release CSVs (git-ignored, see docs/DATA.md)
data/processed/     cleaned parquet (git-ignored)
models/             trained artifacts (git-ignored)
docs/               data notes, inspection report, evaluation results
```

## Quick start (backend)

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -r requirements.txt
python scripts/inspect_data.py                   # needs data/raw/*.csv, see docs/DATA.md
```

## Quick start (frontend)

```bash
cd frontend
npm install
cp .env.example .env          # VITE_API_URL=http://localhost:8000
npm run dev                   # http://localhost:5173
```

Run the API first: `cd backend && .venv/Scripts/uvicorn app.main:app --reload --port 8000`
(needs `models/` from `scripts/train.py` and `data/processed/` from `scripts/preprocess.py`).

## Data

USGS matched Sentinel-2 aquatic reflectance + continuous water-quality dataset
(Delaware, Illinois, Trinity, Upper Colorado, Willamette basins, 2015–2024, CC0).
DOI [10.5066/P1A7T4FV](https://doi.org/10.5066/P1A7T4FV). Details in [docs/DATA.md](docs/DATA.md).

## Deployment

- **Backend → Render** (free tier, Docker): [render.yaml](render.yaml) is a blueprint — connect the repo,
  set `GROQ_API_KEY` in the dashboard, and point `HS_CORS_ORIGINS` at the frontend URL.
  Local image: `docker build -f backend/Dockerfile -t hydrosentinel-api . && docker run -p 8000:8000 --env-file backend/.env hydrosentinel-api`
- **Frontend → Vercel**: import the repo with root directory `frontend`, set `VITE_API_URL` to the Render URL.
- Free tiers spin down when idle: hit `/health` once before a demo to avoid a 30–60 s cold start.

## How it works, and how honest it is

Start at [docs/PIPELINE.md](docs/PIPELINE.md) — a step-by-step trace from the USGS release to
the dashboard, with the file that does each step and the document that records what was found.
Headline evaluation results are in [docs/results/model_findings.md](docs/results/model_findings.md);
spec deviations and their reasoning in [docs/decisions.md](docs/decisions.md).

## Status

Hackathon window: 16–30 Sep 2026. See commit history for progress.
