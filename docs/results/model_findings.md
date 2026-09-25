# Model findings — XGBoost baseline (2026-09-17)

Numbers: [xgb_baseline.md](xgb_baseline.md) (auto-generated). Data: [../data_findings.md](../data_findings.md).
Features: 11 band means, 8 band ratios, 3 normalised-difference indices, 11 band stds, red CV, 2 scene-QA counts (36 total).
Target modelled as `log1p(value)`; metrics reported in original units and in log space.

## Headline

| Target | Random split (optimistic) | Site hold-out | LOBO (mean over basins) | Verdict |
|---|---|---|---|---|
| Turbidity | R² 0.44 / R²_log **0.85** | R² **0.77** / R²_log 0.80 | R² 0.27 / R²_log 0.19 (4 of 5 basins ≥ 0.43 in log space) | **Usable; cross-basin transfer is moderate** |
| Chlorophyll-a | R² 0.51 / R²_log 0.54 | R² 0.47 / R²_log 0.00 | R² −0.49 / R²_log −4.7 (all folds negative) | **Within-region only; does not transfer across basins** |
| CDOM (fDOM) | R² 0.69 / R²_log 0.81 | R² **−14.5** | R² −3 to −39 | **Not validated — the model memorises sites** |

## Why the targets differ so much

A variance decomposition of the processed tables explains the pattern:

| Target | Share of log-variance *between* sites | Best within-site Spearman ρ with any feature |
|---|---|---|
| Turbidity | — (within-site signal strong: red / red-edge ρ ≈ 0.7 pooled) | high |
| Chlorophyll-a | 0.76 | 0.28 (NDCI, red-edge/red — physically expected) |
| CDOM (fDOM) | **0.91** | 0.37 (`n_l2flag`, a QA count — not a physical signal) |

- **Turbidity** scatters light; the red and red-edge bands respond directly. The model learns a
  physical relationship that mostly carries across basins.
- **Chlorophyll-a** has a real but weak red-edge signal in these rivers; most variance is "which
  site is this" (Illinois sites sit at 15–35 µg/L, Willamette at ~1). With 4 basins and Illinois
  holding 60 % of rows, holding a basin out removes exactly the level information the model relied on.
- **CDOM/fDOM** absorbs blue light, but at 6 sites and 521 rows the between-site spread (3 → 48
  µg/L QSE) dwarfs any within-site reflectance response. The high random-split R² is site
  memorisation, which the site hold-out (R² = −14.5) exposes immediately. This is a limitation of
  the available ground truth, not something more tuning can fix.

## Fold-level notes (turbidity)

- **Upper Colorado**: R²_log 0.87, but MAE 48 FNU — this basin has the extreme sediment events
  (max 3,510 FNU); the model under-predicts the peaks (bias −39) yet ranks conditions correctly.
- **Willamette**: R²_log −1.3. Willamette turbidity is uniformly low (RMSE only 5 FNU); trained on
  muddier basins the model over-predicts by ~3.6 FNU. Small absolute error, poor R² because the
  basin has almost no variance to explain. This is the classic "clean basin looks anomalous"
  effect that motivates site-level reference distributions in the stress score.
- **Delaware / Illinois**: R²_log 0.43–0.50, median error within ×1.4–1.45.

## Decisions taken

1. **log1p target** for all three targets (raw-target turbidity R²_log −0.11 vs 0.85).
2. **Early-stopping validation slice**: by whole sites when ≥ 10 sites exist in the training
   portion, else by rows. With fewer sites a single held-out site is unrepresentative and
   stopping halted at iteration 0. The slice is always inside the training portion.
3. **Feature set**: keep all 36 for now; ablation (`--no-std`, `--no-qa`) is a follow-up. The
   CDOM `n_l2flag` correlation is a warning that QA counts may act as site proxies — check with SHAP.

## Consequences for the rest of the system (flagged for the spec owner)

Spec Section 6 defines the stress score as an equal-weight mean of three anomalies. Given the
above:

- Turbidity is the only indicator with demonstrated cross-basin skill. Chl-a is defensible for
  sites/basins represented in training. CDOM has no demonstrated skill outside its six sites.
- Options, in order of scientific honesty:
  a. Keep all three in the composite but attach a per-indicator **confidence label** driven by the
     validation evidence (turbidity: Moderate; chl-a: Low outside training basins; CDOM: Low), and
     let conformal intervals be as wide as they need to be.
  b. Compute the composite from turbidity + chl-a only and show CDOM as "experimental".
  The choice changes the dashboard and API contract, so it is a spec-level decision, not made here.
- For the **regional demonstration mode** (spec Section 18), the honest framing is already
  required by the spec; these results make it mandatory for chl-a and CDOM.

## Follow-ups

- LSTM / FT-Transformer / stacking benchmarks: done — [benchmark_findings.md](benchmark_findings.md)
  (XGBoost retained; decision D5).
- SHAP on the final model: done — `models/<target>/global_shap.json`, served per observation.
- Data-quality sensitivity: done — [data_quality.md](data_quality.md) shows the conclusions hold
  when provisional measurements are excluded.
- Not done: hyperparameter search (small grid on depth / learning rate / min_child_weight) and
  feature ablations (`--no-std`, `--no-qa`). Both would tune a result rather than change it; the
  LOBO gap between targets is an order of magnitude larger than either is likely to move.
  Lagged reflectance features for turbidity at sites with history remain the most promising
  experiment, and more chlorophyll-a ground truth the most valuable new data.
