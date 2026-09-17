# Model benchmarks — LSTM, FT-Transformer, stacking vs XGBoost
Generated 2026-09-17 18:44 UTC by `backend/scripts/evaluate_benchmarks.py` (LSTM window = 6 observations). Same folds and features as the baseline; see the script docstring for the fairness rules. Metrics in original units; `r2_log` in log1p space.

## Turbidity

### site_holdout

| model | held_out | n | r2 | mae | rmse | r2_log | median_factor_err | fit_seconds | epochs | skipped |
|---|---|---|---|---|---|---|---|---|---|---|
| ft_transformer | 10 held-out sites | 1148 | 0.684 | 9.664 | 40.889 | 0.809 | 1.320 | 215.900 | 13.000 | nan |
| lstm | 10 held-out sites | 1136 | 0.902 | 8.833 | 22.848 | 0.845 | 1.351 | 33.200 | 22.000 | nan |
| stack_xgb_ftt | 10 held-out sites | 1148 | 0.687 | 9.785 | 40.705 | 0.804 | 1.315 | 212.500 |  | nan |
| xgb@lstm_rows | 10 held-out sites | 1136 | 0.771 | 9.628 | 35.002 | 0.804 | 1.328 |  |  | nan |
| xgb@stack_base | 10 held-out sites | 1148 | 0.632 | 9.969 | 44.143 | 0.788 | 1.330 |  |  | nan |
| xgboost | 10 held-out sites | 1148 | 0.771 | 9.552 | 34.820 | 0.804 | 1.328 | 7.400 |  | nan |

### lobo

| model | held_out | n | r2 | mae | rmse | r2_log | median_factor_err | fit_seconds | epochs | skipped |
|---|---|---|---|---|---|---|---|---|---|---|
| ft_transformer | Delaware | 1442 | 0.128 | 4.774 | 31.649 | 0.365 | 1.473 | 162.700 | 9.000 | nan |
| lstm | Delaware | 1400 | 0.052 | 5.489 | 33.481 | 0.369 | 1.474 | 32.100 | 25.000 | nan |
| stack_xgb_ftt | Delaware | 1442 | 0.124 | 5.290 | 31.722 | 0.288 | 1.597 | 240.800 |  | nan |
| xgb@lstm_rows | Delaware | 1400 | 0.137 | 4.507 | 31.945 | 0.423 | 1.469 |  |  | nan |
| xgb@stack_base | Delaware | 1442 | 0.135 | 4.482 | 31.512 | 0.430 | 1.455 |  |  | nan |
| xgboost | Delaware | 1442 | 0.137 | 4.442 | 31.481 | 0.434 | 1.453 | 3.900 |  | nan |
| ft_transformer | Illinois | 1084 | -0.173 | 11.143 | 36.840 | 0.456 | 1.395 | 347.500 | 37.000 | nan |
| lstm | Illinois | 1050 | 0.430 | 9.804 | 26.015 | 0.560 | 1.455 | 57.100 | 56.000 | nan |
| stack_xgb_ftt | Illinois | 1084 | 0.501 | 9.287 | 24.014 | 0.550 | 1.378 | 122.900 |  | nan |
| xgb@lstm_rows | Illinois | 1050 | 0.158 | 9.972 | 31.616 | 0.505 | 1.379 |  |  | nan |
| xgb@stack_base | Illinois | 1084 | 0.390 | 10.858 | 26.566 | 0.360 | 1.516 |  |  | nan |
| xgboost | Illinois | 1084 | 0.161 | 9.817 | 31.149 | 0.504 | 1.382 | 9.600 |  | nan |
| ft_transformer | Trinity | 1809 | 0.490 | 12.574 | 42.816 | 0.064 | 1.422 | 176.300 | 13.000 | nan |
| lstm | Trinity | 1809 | 0.458 | 10.667 | 44.121 | 0.570 | 1.292 | 22.900 | 13.000 | nan |
| stack_xgb_ftt | Trinity | 1809 | 0.429 | 11.322 | 45.277 | 0.323 | 1.281 | 193.200 |  | nan |
| xgb@lstm_rows | Trinity | 1809 | 0.466 | 10.462 | 43.791 | 0.446 | 1.232 |  |  | nan |
| xgb@stack_base | Trinity | 1809 | 0.433 | 10.745 | 45.127 | 0.485 | 1.225 |  |  | nan |
| xgboost | Trinity | 1809 | 0.466 | 10.462 | 43.791 | 0.446 | 1.232 | 2.700 |  | nan |
| ft_transformer | Upper Colorado | 614 | 0.328 | 46.833 | 231.032 | 0.854 | 1.334 | 342.900 | 31.000 | nan |
| lstm | Upper Colorado | 604 | 0.288 | 47.858 | 239.680 | 0.854 | 1.292 | 31.900 | 19.000 | nan |
| stack_xgb_ftt | Upper Colorado | 614 | 0.097 | 56.912 | 267.814 | 0.798 | 1.266 | 294.900 |  | nan |
| xgb@lstm_rows | Upper Colorado | 604 | 0.324 | 48.348 | 233.402 | 0.870 | 1.285 |  |  | nan |
| xgb@stack_base | Upper Colorado | 614 | 0.119 | 55.232 | 264.511 | 0.811 | 1.274 |  |  | nan |
| xgboost | Upper Colorado | 614 | 0.325 | 47.654 | 231.496 | 0.866 | 1.291 | 5.100 |  | nan |
| ft_transformer | Willamette | 1211 | 0.462 | 2.844 | 4.417 | -0.650 | 1.683 | 164.100 | 8.000 | nan |
| lstm | Willamette | 1211 | 0.300 | 3.555 | 5.036 | -1.079 | 1.814 | 24.200 | 13.000 | nan |
| stack_xgb_ftt | Willamette | 1211 | 0.389 | 3.206 | 4.706 | -0.840 | 1.760 | 136.600 |  | nan |
| xgb@lstm_rows | Willamette | 1211 | 0.259 | 4.030 | 5.181 | -1.312 | 2.155 |  |  | nan |
| xgb@stack_base | Willamette | 1211 | 0.210 | 3.801 | 5.349 | -1.189 | 1.963 |  |  | nan |
| xgboost | Willamette | 1211 | 0.259 | 4.030 | 5.181 | -1.312 | 2.155 | 1.800 |  | nan |

### LOBO mean over basins (unweighted)

| model | r2 | mae | rmse | r2_log |
|---|---|---|---|---|
| ft_transformer | 0.247 | 15.634 | 69.351 | 0.218 |
| lstm | 0.305 | 15.474 | 69.667 | 0.255 |
| stack_xgb_ftt | 0.308 | 17.203 | 74.707 | 0.224 |
| xgb@lstm_rows | 0.269 | 15.464 | 69.187 | 0.187 |
| xgb@stack_base | 0.258 | 17.024 | 74.613 | 0.179 |
| xgboost | 0.270 | 15.281 | 68.620 | 0.188 |

## Chlorophyll-a

### site_holdout

| model | held_out | n | r2 | mae | rmse | r2_log | median_factor_err | fit_seconds | epochs | skipped |
|---|---|---|---|---|---|---|---|---|---|---|
| ft_transformer | 4 held-out sites | 369 | 0.348 | 6.836 | 10.306 | -0.025 | 1.938 | 70.600 | 13.000 | nan |
| lstm | 4 held-out sites | 369 | 0.251 | 7.230 | 11.049 | -0.097 | 1.672 | 16.100 | 40.000 | nan |
| stack_xgb_ftt | 4 held-out sites | 369 | 0.337 | 6.902 | 10.393 | -0.033 | 1.820 | 74.900 |  | nan |
| xgb@lstm_rows | 4 held-out sites | 369 | 0.474 | 6.699 | 9.252 | -0.004 | 2.161 |  |  | nan |
| xgb@stack_base | 4 held-out sites | 369 | 0.475 | 7.065 | 9.244 | -0.150 | 2.623 |  |  | nan |
| xgboost | 4 held-out sites | 369 | 0.474 | 6.699 | 9.252 | -0.004 | 2.161 | 9.400 |  | nan |

### lobo

| model | held_out | n | r2 | mae | rmse | r2_log | median_factor_err | fit_seconds | epochs | skipped |
|---|---|---|---|---|---|---|---|---|---|---|
| ft_transformer | Delaware | 352 | -0.571 | 5.216 | 12.124 | -4.101 | 2.124 | 69.500 | 10.000 | nan |
| lstm | Delaware | 352 | -0.095 | 3.562 | 10.123 | -2.472 | 2.039 | 6.500 | 2.000 | nan |
| stack_xgb_ftt | Delaware | 352 | 0.004 | 1.785 | 9.656 | -0.251 | 1.570 | 53.300 |  | nan |
| xgb@lstm_rows | Delaware | 352 | -0.536 | 6.951 | 11.988 | -6.337 | 3.769 |  |  | nan |
| xgb@stack_base | Delaware | 352 | -0.597 | 6.376 | 12.226 | -5.615 | 2.912 |  |  | nan |
| xgboost | Delaware | 352 | -0.536 | 6.951 | 11.988 | -6.337 | 3.769 | 2.600 |  | nan |
| ft_transformer | Illinois | 1407 | -0.633 | 12.035 | 19.493 | -3.095 | 2.721 | 30.400 | 9.000 | nan |
| lstm | Illinois | 1385 | -0.615 | 11.746 | 17.872 | -2.576 | 2.944 | 5.000 | 15.000 | nan |
| stack_xgb_ftt | Illinois | 1407 | -0.853 | 14.094 | 20.766 | -4.597 | 4.952 | 26.400 |  | nan |
| xgb@lstm_rows | Illinois | 1385 | -0.761 | 12.128 | 18.658 | -3.048 | 2.977 |  |  | nan |
| xgb@stack_base | Illinois | 1407 | -0.647 | 12.032 | 19.574 | -2.798 | 2.777 |  |  | nan |
| xgboost | Illinois | 1407 | -0.696 | 12.551 | 19.866 | -3.059 | 3.015 | 3.100 |  | nan |
| ft_transformer | Trinity | 211 | 0.140 | 9.093 | 12.568 | -0.016 | 1.921 | 80.900 | 12.000 | nan |
| lstm | Trinity | 211 | -0.042 | 11.652 | 13.831 | -0.374 | 2.374 | 7.100 | 2.000 | nan |
| stack_xgb_ftt | Trinity | 211 | -0.764 | 12.311 | 17.995 | -1.562 | 3.109 | 61.500 |  | nan |
| xgb@lstm_rows | Trinity | 211 | -0.003 | 9.727 | 13.570 | 0.044 | 1.994 |  |  | nan |
| xgb@stack_base | Trinity | 211 | 0.154 | 8.642 | 12.460 | 0.169 | 1.742 |  |  | nan |
| xgboost | Trinity | 211 | -0.003 | 9.727 | 13.570 | 0.044 | 1.994 | 1.700 |  | nan |
| ft_transformer | Willamette | 379 | -0.441 | 6.315 | 10.426 | -7.575 | 3.674 | 43.200 | 1.000 | nan |
| lstm | Willamette | 379 | -0.136 | 3.264 | 9.258 | -3.376 | 1.980 | 6.500 | 4.000 | nan |
| stack_xgb_ftt | Willamette | 379 | -0.621 | 7.448 | 11.056 | -9.375 | 4.453 | 65.000 |  | nan |
| xgb@lstm_rows | Willamette | 379 | -0.734 | 7.789 | 11.438 | -9.646 | 4.526 |  |  | nan |
| xgb@stack_base | Willamette | 379 | -1.140 | 9.232 | 12.706 | -11.641 | 5.050 |  |  | nan |
| xgboost | Willamette | 379 | -0.734 | 7.789 | 11.438 | -9.646 | 4.526 | 2.700 |  | nan |

### LOBO mean over basins (unweighted)

| model | r2 | mae | rmse | r2_log |
|---|---|---|---|---|
| ft_transformer | -0.376 | 8.165 | 13.653 | -3.697 |
| lstm | -0.222 | 7.556 | 12.771 | -2.200 |
| stack_xgb_ftt | -0.559 | 8.910 | 14.868 | -3.946 |
| xgb@lstm_rows | -0.508 | 9.149 | 13.914 | -4.747 |
| xgb@stack_base | -0.557 | 9.070 | 14.242 | -4.971 |
| xgboost | -0.492 | 9.254 | 14.216 | -4.749 |

## CDOM (fDOM proxy)

### site_holdout

| model | held_out | n | r2 | mae | rmse | r2_log | median_factor_err | fit_seconds | epochs | skipped |
|---|---|---|---|---|---|---|---|---|---|---|
| ft_transformer | 2 held-out sites | 268 | -14.217 | 16.088 | 18.959 | -5.025 | 2.700 | 18.300 | 25.000 | nan |
| lstm | 2 held-out sites | 268 |  |  |  |  |  |  |  | too few sequence-eligible rows (fit=215, val=0, test=268) |
| stack_xgb_ftt | 2 held-out sites | 268 | -9.590 | 13.639 | 15.815 | -4.203 | 2.511 | 15.900 |  | nan |
| xgb@stack_base | 2 held-out sites | 268 | -10.900 | 13.895 | 16.765 | -4.904 | 2.008 |  |  | nan |
| xgboost | 2 held-out sites | 268 | -14.522 | 15.480 | 19.148 | -5.811 | 2.023 | 1.100 |  | nan |

### lobo

| model | held_out | n | r2 | mae | rmse | r2_log | median_factor_err | fit_seconds | epochs | skipped |
|---|---|---|---|---|---|---|---|---|---|---|
| ft_transformer | Delaware | 82 | -3.912 | 17.506 | 20.066 | -9.311 | 1.817 | 23.700 | 23.000 | nan |
| lstm | Delaware | 82 |  |  |  |  |  |  |  | too few sequence-eligible rows (fit=373, val=0, test=82) |
| stack_xgb_ftt | Delaware | 82 | -4.717 | 19.704 | 21.648 | -10.305 | 2.146 | 10.500 |  | nan |
| xgb@stack_base | Delaware | 82 | -7.371 | 24.631 | 26.196 | -23.661 | 3.109 |  |  | nan |
| xgboost | Delaware | 82 | -3.463 | 16.647 | 19.128 | -8.915 | 1.863 | 7.600 |  | nan |
| ft_transformer | Illinois | 60 | -9.752 | 29.393 | 32.495 | -29.973 | 3.054 | 16.700 | 8.000 | nan |
| lstm | Illinois | 60 |  |  |  |  |  |  |  | too few sequence-eligible rows (fit=392, val=0, test=60) |
| stack_xgb_ftt | Illinois | 60 | -13.084 | 35.844 | 37.191 | -36.052 | 3.587 | 21.600 |  | nan |
| xgb@stack_base | Illinois | 60 | -5.878 | 23.479 | 25.989 | -12.736 | 1.806 |  |  | nan |
| xgboost | Illinois | 60 | -7.347 | 25.914 | 28.631 | -16.291 | 2.093 | 4.500 |  | nan |
| ft_transformer | Willamette | 379 | -44.756 | 34.302 | 34.714 | -8.825 | 6.199 | 5.000 | 7.000 | nan |
| lstm | Willamette | 379 |  |  |  |  |  |  |  | too few sequence-eligible rows (fit=121, val=0, test=379) |
| stack_xgb_ftt | Willamette | 379 | -33.918 | 29.899 | 30.326 | -7.773 | 5.796 | 5.400 |  | nan |
| xgb@stack_base | Willamette | 379 | -42.308 | 33.369 | 33.773 | -8.585 | 6.185 |  |  | nan |
| xgboost | Willamette | 379 | -38.766 | 31.879 | 32.362 | -8.268 | 6.119 | 0.400 |  | nan |

### LOBO mean over basins (unweighted)

| model | r2 | mae | rmse | r2_log |
|---|---|---|---|---|
| ft_transformer | -19.473 | 27.067 | 29.092 | -16.036 |
| stack_xgb_ftt | -17.240 | 28.482 | 29.722 | -18.043 |
| xgb@stack_base | -18.519 | 27.160 | 28.653 | -14.994 |
| xgboost | -16.525 | 24.813 | 26.707 | -11.158 |
