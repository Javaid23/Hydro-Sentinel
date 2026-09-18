# HydroSentinel — end-to-end trace

How a Sentinel-2 observation becomes an assessment, in the order the work was done, with the file
that does each step and the document that records what was found. Every numeric output the
dashboard shows is produced by steps 1–9; step 10 only puts words around them.

| # | Step | Code | Evidence / decisions |
|---|---|---|---|
| 1 | **Where the data came from** — USGS matched Sentinel-2 aquatic reflectance + continuous water-quality release (5 basins, 2015–2024, CC0) | [`docs/DATA.md`](DATA.md) | DOI 10.5066/P1A7T4FV |
| 2 | **What it actually contains** — long-format, 1.75 M rows, 85 columns, 11 parameter codes | [`backend/scripts/inspect_data.py`](../backend/scripts/inspect_data.py) | [`data_inspection.md`](data_inspection.md) (generated), [`data_findings.md`](data_findings.md) |
| 3 | **How it was cleaned** — nearest sonde reading per overpass, ≤ 3 h, ≥ 5 valid pixels, no censored codes, all bands present → 9,030 matchups | [`backend/hydrosentinel/data.py`](../backend/hydrosentinel/data.py), [`scripts/preprocess.py`](../backend/scripts/preprocess.py) | [`preprocess_summary.md`](preprocess_summary.md) (rows dropped per rule), [`decisions.md`](decisions.md) D1–D2 |
| 4 | **Which targets** — turbidity `63680`; chl-a `32316/32318/62361` (µg/L); CDOM as fDOM `32295` (µg/L QSE). RFU codes excluded | [`backend/hydrosentinel/config.py`](../backend/hydrosentinel/config.py) | [`data_findings.md §2`](data_findings.md) |
| 5 | **How features were built** — 11 band means, 8 ratios, 3 indices, 11 band stds, red CV, 2 scene-QA counts. No location/time identifiers | [`backend/hydrosentinel/features.py`](../backend/hydrosentinel/features.py) | [`data_findings.md §6`](data_findings.md) |
| 6 | **How models were trained** — XGBoost per target, log1p target, early stopping on a site-wise slice of the training portion | [`backend/hydrosentinel/model.py`](../backend/hydrosentinel/model.py) | [`results/model_findings.md`](results/model_findings.md) |
| 7 | **How generalisation was tested** — random split (optimistic), site hold-out, leave-one-basin-out | [`backend/hydrosentinel/evaluation.py`](../backend/hydrosentinel/evaluation.py), [`scripts/evaluate_xgb.py`](../backend/scripts/evaluate_xgb.py) | [`results/xgb_baseline.md`](results/xgb_baseline.md), [`results/model_findings.md`](results/model_findings.md) |
| 7b | **Alternative models** — LSTM (≥ 30-obs sites), FT-Transformer, XGB+FTT stacking, same folds | [`backend/hydrosentinel/benchmarks/`](../backend/hydrosentinel/benchmarks/), [`scripts/evaluate_benchmarks.py`](../backend/scripts/evaluate_benchmarks.py) | [`results/benchmarks.md`](results/benchmarks.md) |
| 8 | **How uncertainty was calculated** — split conformal, absolute residuals in log1p space, 90 %; coverage measured under every split design | [`backend/hydrosentinel/uncertainty.py`](../backend/hydrosentinel/uncertainty.py), [`scripts/evaluate_uncertainty.py`](../backend/scripts/evaluate_uncertainty.py) | [`results/uncertainty.md`](results/uncertainty.md), [`decisions.md`](decisions.md) D4 |
| 9 | **How predictions were explained** — SHAP TreeExplainer on the final model; global mean-|SHAP| and per-observation top-k, phrased as contribution | [`backend/hydrosentinel/explain.py`](../backend/hydrosentinel/explain.py) | `models/<target>/global_shap.json` |
| 10 | **How the stress indicator was calculated** — percentile of each prediction vs the site's own history (≥ 30 obs) else the basin's; never a global pool; leave-one-out for the scored observation; equal-weight mean → 0–100 | [`backend/hydrosentinel/stress.py`](../backend/hydrosentinel/stress.py) | [`decisions.md`](decisions.md) D3 (confidence tiers) |
| 11 | **Production artifacts** — retrain on pooled data, calibrate, bundle | [`backend/scripts/train.py`](../backend/scripts/train.py) | [`models/README.md`](../models/README.md), `models/manifest.json` |
| 12 | **Assembly** — one observation → predictions + intervals + SHAP + percentiles + score + confidence tiers | [`backend/hydrosentinel/assess.py`](../backend/hydrosentinel/assess.py) | — |
| 13 | **How the LLM uses those outputs** — receives the assessment dict as text, returns summary / interpretation / ranked actions / caveats; cannot change a number; failures degrade to "explanation unavailable" | [`backend/hydrosentinel/llm.py`](../backend/hydrosentinel/llm.py) | prompt rules in the file |
| 13b | **Live data path** — newest usable scene from USGS's daily product, windowed COG reads, USGS's masking rules, live NWIS sonde reading for comparison | [`backend/hydrosentinel/live.py`](../backend/hydrosentinel/live.py) | [`decisions.md`](decisions.md) D6 |
| 14 | **API** — `GET /assessment/{site_id}` returns everything for one dashboard view | [`backend/app/main.py`](../backend/app/main.py), [`schemas.py`](../backend/app/schemas.py) | `/docs` (OpenAPI) |
| 15 | **Dashboard** — score → indicators → why → how certain → what it means → actions | [`frontend/src/`](../frontend/src/) | — |

## Reproduce

```bash
# 0. data: unzip Matched_WQ_S2.zip into data/raw/ (docs/DATA.md)
cd backend && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
python scripts/inspect_data.py            # docs/data_inspection.md
python scripts/preprocess.py              # data/processed/*.parquet, docs/preprocess_summary.md
python scripts/evaluate_xgb.py            # docs/results/xgb_baseline.md
python scripts/evaluate_uncertainty.py    # docs/results/uncertainty.md
python scripts/evaluate_benchmarks.py     # docs/results/benchmarks.md   (needs torch)
python scripts/train.py                   # models/
pytest                                    # 20 tests
uvicorn app.main:app --reload             # http://localhost:8000/docs
```

Seeds are fixed (`config.RANDOM_STATE = 42`); numbers in the docs were produced on 2026-09-17.

## What the system does not do

- It does not forecast. Every output describes the overpass being scored.
- It does not claim validated skill outside the five training basins; see the confidence tiers.
- The stress score is an anomaly indicator relative to a site's own record, not an ecological
  health index, and its weights are not learned.
