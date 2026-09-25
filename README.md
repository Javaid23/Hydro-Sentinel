# HydroSentinel

**Observe → Predict → Explain → Assess**

Satellite-based, uncertainty-aware freshwater ecosystem assessment. HydroSentinel estimates
turbidity, chlorophyll-a and CDOM from Sentinel-2 reflectance, scores how unusual the current
condition is against a site's *own* history, explains the prediction with SHAP, quantifies
uncertainty with conformal prediction, and turns the result into plain-language decision support.

Built for the **OneAquaHealth IEEE Global Hackathon 2026** (Resilience Informatics; secondary:
AI-Supported Assessment).

> The system answers: *"What is the estimated current condition, how unusual is it, and what is
> driving the prediction?"* It does **not** forecast future conditions.

## Four views

| View | What it answers |
|---|---|
| **Network overview** | Which of the 49 monitoring sites need attention right now, ranked, on a map — plus the measured validation evidence behind the numbers |
| **Site detail** | For one overpass: prediction, how unusual it is against that site's own record, what drove it, how certain it is |
| **Live** | The same for the newest usable scene from USGS's daily product, with the live sonde reading beside it |
| **Regional demo** | Any coordinates worldwide, flagged out-of-region, with a Local Anomaly Score built from that location's own archive |

| Mode | Imagery | Ground truth | Validation tier |
|---|---|---|---|
| **Historical** | The labelled USGS matchups, 2015–2024 | Matched sonde reading shown beside each prediction | Site in training data |
| **Live** | Newest usable scene from USGS's daily aquatic-reflectance product (CONUS), extracted on the fly | Live USGS sonde reading at the overpass, fetched from NWIS | Site in training data |
| **Regional demo** | Any coordinates worldwide, via Copernicus Sentinel-2 L2A, harmonised to the training product | None | **Out of region — unvalidated** |

## What the evaluation actually showed

Leave-one-basin-out is the number that matters; the random split is the optimistic ceiling.
Full tables: [docs/results/model_findings.md](docs/results/model_findings.md).

| Target | Random split | Unseen sites | Leave-one-basin-out | Verdict |
|---|---|---|---|---|
| **Turbidity** | R²_log 0.85 | R² 0.77 | 4 of 5 basins R²_log 0.43–0.87 | Works; moderate cross-basin transfer |
| **Chlorophyll-a** | R² 0.51 | R² 0.47 | every fold negative | Within-region only |
| **CDOM (fDOM)** | R² 0.69 | **R² −14.5** | R² −3 to −39 | **Not validated — the model memorises sites** |

The CDOM result is reported rather than hidden: 91 % of its variance is *between* the six sites
that measure it, so a model that looks good on a random split collapses the moment the site is
unseen. Every indicator therefore carries a confidence tier derived from this evidence, not
hand-set ([docs/decisions.md](docs/decisions.md) D3), and the dashboard shows all three alongside
the composite score.

LSTM, FT-Transformer and XGB+LSTM/FTT stacking were benchmarked under the same folds; XGBoost was
retained. The turbidity LSTM was the only close contender and lost on inference requirements, not
on a coin flip — [docs/results/benchmark_findings.md](docs/results/benchmark_findings.md).

## How honesty is enforced, not just claimed

- **Never a pooled reference.** Percentiles are computed against a site's own record, or its
  basin's — never all basins together, which would make a naturally clear river look anomalous.
- **Leakage rule.** The observation being scored is removed from its own reference distribution.
- **Conformal coverage is measured, not assumed.** 90 % intervals hold at known sites; the
  measured shortfall on unseen basins is what sets the lower confidence tiers
  ([docs/results/uncertainty.md](docs/results/uncertainty.md)).
- **Out-of-distribution check.** At any unseen location the dashboard reports how many Sentinel-2
  bands fall outside the 1st–99th percentile of the training data. At the Ravi in Lahore several do,
  so the extrapolation is visible rather than asserted.
- **The LLM cannot touch a number.** It receives the finished assessment as text and returns
  prose; every numeric value on screen comes from the pipeline.
- **No score where none is defensible.** Out of region there is no observed history, so the
  Freshwater Stress Score is not computed. Instead the location's own reference can be built from
  the Sentinel-2 archive and reported separately as a **Local Anomaly Score**, labelled as model
  output rather than measurements ([docs/decisions.md](docs/decisions.md) D8).

## Verify none of it is fabricated

The claim that every number comes from real measurements is checked mechanically, not asserted:

```bash
python backend/scripts/audit_provenance.py
```

It confirms there is no fake/mock/placeholder content in the serving path, that test doubles exist
only under `tests/`, that every processed row traces to the raw USGS release through an audited
filter chain, that the models carry real USGS site numbers, that imagery comes from named public
archives, that the harmonisation factors were measured from real same-day scene pairs, and that
the LLM cannot write into the numeric assessment. Exit code 0 means all checks passed.

## Quick start

```bash
# backend
cd backend
python -m venv .venv && .venv/Scripts/activate      # or source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000                     # http://localhost:8000/docs

# frontend
cd frontend
npm install && cp .env.example .env                  # VITE_API_URL=http://localhost:8000
npm run dev                                          # http://localhost:5173
```

Trained artifacts (`models/`) and processed data (`data/processed/`) are committed, so the API
runs without the 1.4 GB raw release. To rebuild from source data see [docs/PIPELINE.md](docs/PIPELINE.md).

**Before a demo or recording:** `python backend/scripts/warm_live_cache.py` — live extraction is
network-bound (a scene listing plus 13 windowed COG reads) and can take minutes on a poor
connection. Scene pixels never change, so results are cached to disk and reused.

## Layout

```
backend/
  hydrosentinel/    data, features, model, evaluation, uncertainty, explain, stress,
                    live (USGS feed), live_global (Copernicus), livecache, llm, assess
  app/              FastAPI routes and Pydantic schemas
  scripts/          inspect_data, preprocess, evaluate_*, train, warm_live_cache
  tests/            46 tests
frontend/src/       React dashboard (charts.jsx, panels.jsx, App.jsx)
models/             trained artifacts (committed, ~2 MB, so the API deploys from the repo)
data/processed/     cleaned per-target tables + observation index
docs/               PIPELINE.md (end-to-end trace), decisions.md (D1–D8), results/
```

### Model artifacts

Produced by `backend/scripts/train.py` from `data/processed/` and loaded by the API at startup.
Rebuild with `python backend/scripts/train.py`.

| File | Contents |
|---|---|
| `manifest.json` | Training timestamp and per-target summary |
| `training_bands.json` | Per-band training quantiles, used by the out-of-distribution check |
| `harmonisation_l2a.json` | Measured L2A → ACOLITE factors for non-US imagery |
| `<target>/model.joblib` | XGBoost booster plus the log1p transform and feature names |
| `<target>/conformal.json` | Split-conformal calibration: alpha, q̂ in log space, calibration size |
| `<target>/reference.joblib` | Site and basin historical distributions used for percentiles |
| `<target>/global_shap.json` | Mean \|SHAP\| per feature on the fit set |
| `<target>/metadata.json` | Training sites and basins, coordinates, feature list, notes |

## Documentation

| Document | What it answers |
|---|---|
| [docs/PIPELINE.md](docs/PIPELINE.md) | The end-to-end trace: raw data → cleaning → features → training → validation → uncertainty → explanation → score → LLM |
| [docs/decisions.md](docs/decisions.md) | Every deviation from the spec and why (D1–D7) |
| [docs/data_findings.md](docs/data_findings.md) | What the USGS release actually contains and how it was filtered |
| [docs/results/](docs/results/) | Baseline, benchmarks, uncertainty coverage — generated by the evaluation scripts |
| [docs/DEMO.md](docs/DEMO.md) | Demo walkthrough and narration script |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Deploying the backend to Render and the frontend to Vercel |

## Data

USGS matched Sentinel-2 aquatic reflectance + continuous water-quality release (Delaware,
Illinois, Trinity, Upper Colorado, Willamette; 2015–2024; CC0),
DOI [10.5066/P1A7T4FV](https://doi.org/10.5066/P1A7T4FV). Live imagery from USGS's daily
ACOLITE-DSF product and the Copernicus Sentinel-2 L2A archive, both public on AWS.
Details in [docs/DATA.md](docs/DATA.md).
