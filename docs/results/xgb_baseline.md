# XGBoost baseline — leakage-safe and LOBO evaluation
Generated 2026-09-17 13:40 UTC by `backend/scripts/evaluate_xgb.py`. Features: band means + ratios/indices + band std + scene QA.

Metrics are in original units (FNU, µg/L, µg/L QSE) unless suffixed `_log` (log1p space). `median_factor_err` = exp(median |log ratio|): 1.5 means the typical prediction is within ×/÷ 1.5.

## Turbidity (FNU)

### Target transform (random split)

| split | held_out | n | r2 | mae | rmse | bias | median_ae | r2_log | rmse_log | median_factor_err | best_iteration |
|---|---|---|---|---|---|---|---|---|---|---|---|
| random | random 20% rows | 1232 | 0.441 | 9.196 | 74.001 | -5.743 | 1.765 | 0.847 | 0.453 | 1.219 | 263.000 |
| random_rawtarget | random 20% rows | 1232 | 0.164 | 19.692 | 90.504 | -2.087 | 12.498 | -0.114 | 1.223 | 2.308 | 16.000 |

### Generalisation designs

| split | held_out | n | r2 | mae | rmse | bias | median_ae | r2_log | rmse_log | median_factor_err | best_iteration |
|---|---|---|---|---|---|---|---|---|---|---|---|
| random | random 20% rows | 1232 | 0.441 | 9.196 | 74.001 | -5.743 | 1.765 | 0.847 | 0.453 | 1.219 | 263.000 |
| site_holdout | 10 held-out sites | 1148 | 0.771 | 9.552 | 34.820 | -4.685 | 3.129 | 0.804 | 0.546 | 1.328 | 645.000 |
| lobo | Trinity | 1809 | 0.466 | 10.462 | 43.791 | -5.250 | 4.497 | 0.446 | 0.537 | 1.232 | 191.000 |
| lobo | Delaware | 1442 | 0.137 | 4.442 | 31.481 | 0.242 | 2.308 | 0.434 | 0.588 | 1.453 | 341.000 |
| lobo | Willamette | 1211 | 0.259 | 4.030 | 5.181 | 3.596 | 3.434 | -1.312 | 0.959 | 2.155 | 83.000 |
| lobo | Illinois | 1084 | 0.161 | 9.817 | 31.149 | -5.259 | 3.553 | 0.504 | 0.638 | 1.382 | 969.000 |
| lobo | Upper Colorado | 614 | 0.325 | 47.654 | 231.496 | -38.936 | 5.085 | 0.866 | 0.516 | 1.291 | 372.000 |
| lobo_pooled | all basins (row-weighted) | 6160 |  | 11.382 | 79.453 |  |  |  |  |  |  |
| lobo_mean | mean over basins (unweighted) | 5 | 0.270 | 15.281 | 68.620 |  |  | 0.188 |  |  |  |

## Chlorophyll-a (µg/L)

### Target transform (random split)

| split | held_out | n | r2 | mae | rmse | bias | median_ae | r2_log | rmse_log | median_factor_err | best_iteration |
|---|---|---|---|---|---|---|---|---|---|---|---|
| random | random 20% rows | 470 | 0.507 | 5.355 | 9.657 | -1.193 | 2.975 | 0.543 | 0.723 | 1.408 | 153.000 |
| random_rawtarget | random 20% rows | 470 | 0.524 | 6.288 | 9.490 | 1.397 | 3.970 | 0.321 | 0.881 | 1.541 | 183.000 |

### Generalisation designs

| split | held_out | n | r2 | mae | rmse | bias | median_ae | r2_log | rmse_log | median_factor_err | best_iteration |
|---|---|---|---|---|---|---|---|---|---|---|---|
| random | random 20% rows | 470 | 0.507 | 5.355 | 9.657 | -1.193 | 2.975 | 0.543 | 0.723 | 1.408 | 153.000 |
| site_holdout | 4 held-out sites | 369 | 0.474 | 6.699 | 9.252 | 2.951 | 4.745 | -0.004 | 1.204 | 2.161 | 1129.000 |
| lobo | Illinois | 1407 | -0.696 | 12.551 | 19.866 | -12.361 | 7.198 | -3.059 | 1.538 | 3.015 | 391.000 |
| lobo | Willamette | 379 | -0.734 | 7.789 | 11.438 | 6.760 | 7.186 | -9.646 | 1.556 | 4.526 | 260.000 |
| lobo | Delaware | 352 | -0.536 | 6.951 | 11.988 | 5.886 | 5.734 | -6.337 | 1.483 | 3.769 | 214.000 |
| lobo | Trinity | 211 | -0.003 | 9.727 | 13.570 | -5.653 | 5.806 | 0.044 | 0.829 | 1.994 | 102.000 |
| lobo_pooled | all basins (row-weighted) | 2349 |  | 10.690 | 17.192 |  |  |  |  |  |  |
| lobo_mean | mean over basins (unweighted) | 4 | -0.492 | 9.254 | 14.216 |  |  | -4.749 |  |  |  |

## CDOM (fDOM proxy) (µg/L QSE)

### Target transform (random split)

| split | held_out | n | r2 | mae | rmse | bias | median_ae | r2_log | rmse_log | median_factor_err | best_iteration |
|---|---|---|---|---|---|---|---|---|---|---|---|
| random | random 20% rows | 104 | 0.691 | 4.423 | 9.559 | -1.827 | 1.491 | 0.811 | 0.378 | 1.136 | 1133.000 |
| random_rawtarget | random 20% rows | 104 | 0.742 | 4.893 | 8.743 | -0.903 | 2.495 | 0.787 | 0.402 | 1.226 | 338.000 |

### Generalisation designs

| split | held_out | n | r2 | mae | rmse | bias | median_ae | r2_log | rmse_log | median_factor_err | best_iteration |
|---|---|---|---|---|---|---|---|---|---|---|---|
| random | random 20% rows | 104 | 0.691 | 4.423 | 9.559 | -1.827 | 1.491 | 0.811 | 0.378 | 1.136 | 1133.000 |
| site_holdout | 2 held-out sites | 268 | -14.522 | 15.480 | 19.148 | 14.029 | 10.667 | -5.811 | 1.166 | 2.023 | 113.000 |
| lobo | Willamette | 379 | -38.766 | 31.879 | 32.362 | 31.879 | 33.708 | -8.268 | 1.817 | 6.119 | 29.000 |
| lobo | Delaware | 82 | -3.463 | 16.647 | 19.128 | -14.815 | 16.892 | -8.915 | 0.745 | 1.863 | 1271.000 |
| lobo | Illinois | 60 | -7.347 | 25.914 | 28.631 | -25.843 | 24.684 | -16.291 | 0.890 | 2.093 | 636.000 |
| lobo_pooled | all basins (row-weighted) | 521 |  | 28.795 | 30.230 |  |  |  |  |  |  |
| lobo_mean | mean over basins (unweighted) | 3 | -16.525 | 24.813 | 26.707 |  |  | -11.158 |  |  |  |

## Reading the table

- **random** is the optimistic ceiling: the model has seen every site during training.
- **site_holdout** removes whole sites; **lobo** removes whole basins — the number that matters for deployment to a new region.
- Negative R² on a LOBO fold means the model does worse than predicting that basin's mean: the held-out basin's conditions are outside what the other basins taught it.
