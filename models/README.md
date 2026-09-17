# Trained artifacts

Produced by `backend/scripts/train.py` from `data/processed/`; loaded by the API at startup.
Tracked in git (≈2 MB) so the backend deploys straight from the repository.

```
manifest.json            training timestamp, per-target summary
<target>/model.joblib    TargetModel (XGBoost booster + log1p transform + feature names)
<target>/conformal.json  split-conformal calibration (alpha, q_hat in log space, n_calibration)
<target>/reference.joblib site/basin historical reference distributions for percentiles
<target>/global_shap.json mean |SHAP| per feature on the fit set
<target>/metadata.json   training sites/basins, coordinates, feature list, notes
```

Retrain: `python backend/scripts/train.py` (needs `data/processed/*.parquet`).
