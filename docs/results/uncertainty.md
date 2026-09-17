# Conformal interval coverage under each evaluation design
Generated 2026-09-17 13:51 UTC by `backend/scripts/evaluate_uncertainty.py`. Method: split conformal, absolute residual in log1p space, target coverage 90%. Calibration rows are always drawn from the training portion of the split.

`interval_factor` is the calibrated multiplicative half-width (prediction ×/÷ factor). `coverage` is the fraction of held-out observations inside the interval.

## Turbidity

| split | held_out | n_test | coverage | target_coverage | interval_factor | median_width_factor |
|---|---|---|---|---|---|---|
| random | random 20% rows | 1232 | 0.875 | 0.900 | 1.780 | 3.700 |
| site_holdout | 10 held-out sites | 1148 | 0.780 | 0.900 | 1.860 | 3.820 |
| lobo | Trinity | 1809 | 0.851 | 0.900 | 1.910 | 3.950 |
| lobo | Delaware | 1442 | 0.719 | 0.900 | 1.810 | 4.270 |
| lobo | Willamette | 1211 | 0.456 | 0.900 | 1.870 | 4.560 |
| lobo | Illinois | 1084 | 0.723 | 0.900 | 1.840 | 3.960 |
| lobo | Upper Colorado | 614 | 0.829 | 0.900 | 1.920 | 3.910 |

## Chlorophyll-a

| split | held_out | n_test | coverage | target_coverage | interval_factor | median_width_factor |
|---|---|---|---|---|---|---|
| random | random 20% rows | 470 | 0.913 | 0.900 | 5.060 | 64.050 |
| site_holdout | 4 held-out sites | 369 | 0.575 | 0.900 | 2.840 | 12.040 |
| lobo | Illinois | 1407 | 0.334 | 0.900 | 2.250 | 15.350 |
| lobo | Willamette | 379 | 0.063 | 0.900 | 2.360 | 7.030 |
| lobo | Delaware | 352 | 0.423 | 0.900 | 3.170 | 16.120 |
| lobo | Trinity | 211 | 0.896 | 0.900 | 3.140 | 13.740 |

## CDOM (fDOM proxy)

| split | held_out | n_test | coverage | target_coverage | interval_factor | median_width_factor |
|---|---|---|---|---|---|---|
| random | random 20% rows | 104 | 0.923 | 0.900 | 1.930 | 4.250 |
| site_holdout | 2 held-out sites | 268 | 0.687 | 0.900 | 3.930 | 17.950 |
| lobo | Willamette | 379 | 0.000 | 0.900 | 1.490 | 2.280 |
| lobo | Delaware | 82 | 0.293 | 0.900 | 1.520 | 2.430 |
| lobo | Illinois | 60 | 0.217 | 0.900 | 1.710 | 3.090 |

## Reading the table

- **random**: coverage ≈ 90 % by construction — the guarantee regime (site_seen tier).
- **site_holdout / lobo**: coverage below 90 % means the calibrated band is too narrow for unseen sites or basins; the shortfall is the quantitative basis for the lower confidence tiers (basin_seen, out_of_region) in docs/decisions.md D3.
