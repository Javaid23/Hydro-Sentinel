# Benchmark findings — LSTM, FT-Transformer, stacking vs XGBoost (2026-09-17)

Full tables: [benchmarks.md](benchmarks.md) (auto-generated). Design and fairness rules:
`backend/scripts/evaluate_benchmarks.py`. Spec Section 3 timebox: XGBoost full effort, LSTM and
FT-Transformer half a day each, stacking only if both components work. All three ran to completion.

## Set-up

| Model | Input | Trained on |
|---|---|---|
| **XGBoost** (baseline, served) | 36 tabular features of the overpass being scored | all rows |
| **FT-Transformer** | same 36 features, tokenised; 2 encoder layers, 48-d tokens | all rows |
| **LSTM** | the last 6 overpasses at the same site (chronological, backward-looking windows) | only sites with ≥ 30 observations inside the split portion (spec rule); `xgb@lstm_rows` = XGBoost scored on exactly the same test rows |
| **Stack XGB+FTT** | Ridge on log-space predictions of both, fit on a site-disjoint 20 % of the training sites | base models on the other 80 % (`xgb@stack_base` shows the reduced-data XGB alone) |

Same folds as the baseline (site hold-out, leave-one-basin-out), same log1p target, same
early-stopping discipline (validation slice carved from the training portion).

## Turbidity — the only target where the comparison matters

R² in log1p space (scale-robust); raw-unit R² and MAE in [benchmarks.md](benchmarks.md).

| Fold | XGBoost | FT-Transformer | LSTM | XGB on LSTM rows | Stack | XGB stack-base |
|---|---|---|---|---|---|---|
| site hold-out (10 sites) | 0.804 | 0.809 | **0.845** | 0.804 | 0.804 | 0.788 |
| LOBO Trinity | 0.446 | 0.064 | **0.570** | 0.446 | 0.323 | 0.485 |
| LOBO Delaware | **0.434** | 0.365 | 0.369 | 0.423 | 0.288 | 0.430 |
| LOBO Willamette | −1.312 | **−0.650** | −1.079 | −1.312 | −0.840 | −1.189 |
| LOBO Illinois | 0.504 | 0.456 | **0.560** | 0.505 | 0.550 | 0.360 |
| LOBO Upper Colorado | **0.866** | 0.854 | 0.854 | 0.870 | 0.798 | 0.811 |
| **LOBO mean** | 0.188 | 0.218 | **0.255** | 0.186 | 0.224 | 0.179 |

Raw-unit R² on unseen sites: LSTM 0.902 vs XGBoost 0.771 on the same 1,136 rows — the largest
single gap in the study. Under LOBO the raw-unit means are LSTM 0.306, stack 0.308, XGBoost 0.270,
FT-Transformer 0.247.

Reading:
- **Temporal context helps turbidity, modestly.** The LSTM beats XGBoost on 3 of 5 held-out basins
  and on unseen sites within known basins (+0.04 R²_log, +0.13 raw R²). It loses Delaware and ties
  Upper Colorado. The gain is real but not decisive, and it comes with a hard input requirement:
  six prior overpasses at the same location.
- **FT-Transformer ≈ XGBoost** on average (0.218 vs 0.188 LOBO mean) with higher variance per
  basin (collapses on Trinity, best on Willamette). No case for replacing trees with it.
- **Stacking is inconsistent.** It improves on its own reduced-data base (0.224 vs 0.179) and wins
  Illinois and Willamette, but loses Trinity, Delaware and Upper Colorado, and never beats the
  full-data XGBoost by a margin that survives the folds. This mirrors the common finding that
  stacking two models of similar skill on a few thousand rows buys little.
- **Willamette is negative for every model.** The basin's turbidity is uniformly low; every model
  trained on muddier basins over-predicts it. The failure is a domain-shift property of the data,
  not of any architecture — and it is exactly what the site-level reference distributions in the
  stress score are designed to absorb.

## Chlorophyll-a and CDOM

No model generalises across basins for either target (all LOBO R² negative; see
[model_findings.md](model_findings.md) for why — 76 % / 91 % of the variance is between sites).
Two details worth recording:

- On chl-a the LSTM has markedly lower MAE on the Willamette and Delaware folds (3.3 and 3.6 µg/L vs
  7.8 and 7.0 for XGBoost) because it predicts closer to those basins' low levels, but its R² is
  still negative: it is less wrong, not right.
- On the site hold-out XGBoost remains the best chl-a model (R² 0.474 vs 0.348 FTT, 0.251 LSTM).
- The CDOM LSTM could not be trained at all: after the site-wise early-stopping slice, no site in
  the validation portion had 30 observations. The other models fail as the baseline did.

## Decision

**XGBoost stays the served model for all three targets.**

1. The only competitive alternative, the turbidity LSTM, gains ~0.05 R²_log on average with a
   3-win / 1-loss / 1-tie basin record — not the clear empirical win the spec asks for before
   changing the production model.
2. The LSTM needs a site's last six overpasses. The served system must score a *single*
   observation (the API contract, the regional demonstration mode, any new location). Serving the
   LSTM would mean either two code paths or dropping single-overpass scoring.
3. XGBoost keeps exact TreeExplainer SHAP values and the already-calibrated conformal intervals;
   the neural models would need KernelSHAP and re-calibration.
4. The benchmark stage is time-boxed; the remaining effort is better spent on the P0/P1 chain.

**Recorded as future work:** a turbidity model with temporal context (the LSTM here, or simply
lagged reflectance features fed to XGBoost, which would keep the tabular pipeline) for sites with
an observation history. The lagged-feature variant is the cheaper experiment and should be tried
first.

## Compute cost (2-thread CPU, per fold)

XGBoost ≈ 5 s · FT-Transformer ≈ 90–200 s · LSTM ≈ 60–150 s · stack ≈ 150–300 s (two base fits).
Inference cost for all models is negligible relative to network latency.
