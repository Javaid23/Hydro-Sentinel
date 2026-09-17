# Decision log

Deviations from, or refinements of, the locked specification (CLAUDE.md). Each entry says what was
decided, why, and what it changes. Newest last.

## D1 — huc4 1204 grouped with the Trinity basin (2026-09-17)

The release title lists five basins but the data carries eight HUC4 codes, including 1204
(San Jacinto / Galveston Bay: Lake Houston and Lynchburg Reservoir sites). These receive Trinity
River water and USGS bundles them with Trinity. Kept in the Trinity LOBO group rather than
creating a sixth basin with four sites. Details: [data_findings.md §3](data_findings.md).

## D2 — Chlorophyll-a and CDOM defined by concentration codes only (2026-09-17)

Chl-a uses USGS parameter codes 32316, 32318, 62361 (µg/L); CDOM uses 32295 (fDOM, µg/L QSE).
Relative-fluorescence (RFU) codes are excluded because RFU is sensor-relative, not a concentration.
The CDOM indicator is labelled "CDOM (fDOM proxy)" everywhere. Details: [data_findings.md §2](data_findings.md).

## D3 — Stress score keeps all three indicators, with evidence-based confidence tiers (2026-09-17)

**Evidence.** LOBO evaluation showed turbidity transfers across basins moderately, chlorophyll-a
transfers poorly, and CDOM/fDOM does not transfer at all (91 % of its variance is between the six
sites that have it). Details: [results/model_findings.md](results/model_findings.md).

**Options considered.**
(a) Keep the spec's equal-weight three-indicator composite and attach a per-indicator confidence
    label derived from the validation evidence.
(b) Compute the composite from turbidity + chl-a only and mark CDOM experimental.

**Decision: (a).** Rationale: the system's purpose is to communicate uncertainty rather than hide
it; CDOM retains value at the sites it was trained on (random-split R² 0.69) and the failure is
specifically out-of-site; the spec architecture (three indicators, equal weights, one composite)
is unchanged; and the same mechanism handles the out-of-region demonstration mode where every
indicator is low-confidence. Option (b) would be preferable only if the composite drove automated
actions, which it does not.

**What changes.** Every indicator in the assessment response carries a `validation_tier` and a
`confidence` label derived from it, not hand-set:

| Tier | Condition | Turbidity | Chl-a | CDOM |
|---|---|---|---|---|
| `site_seen` | site present in training data | Moderate | Moderate | Moderate |
| `basin_seen` | basin in training, site not | Moderate | Low | Low |
| `out_of_region` | basin not in training (incl. regional demo) | Low | Very low | Very low |

The 90 % conformal prediction interval is shown alongside as the quantitative statement; the tier
label is the qualitative one. Neither is edited by the LLM layer.

## D4 — Uncertainty method: split conformal prediction in log space (2026-09-17)

Implemented directly (about 40 lines) rather than through `mapie`, so that calibration happens in
the model's log1p space; this yields multiplicative intervals in original units, which suit the
heavy-tailed targets. Coverage is guaranteed only when calibration and scoring data are
exchangeable, i.e. for `site_seen`; empirical coverage on LOBO folds is measured and reported so
the degradation out-of-region is documented rather than assumed.

## D5 — XGBoost remains the served model after the benchmark stage (2026-09-17)

LSTM (site sequences), FT-Transformer and XGB+FTT stacking were evaluated under the baseline's
site-holdout and LOBO folds ([results/benchmark_findings.md](results/benchmark_findings.md)).
The turbidity LSTM was the only competitive alternative (+0.05 R²_log LOBO mean, 3 wins / 1 loss /
1 tie across basins; raw R² 0.90 vs 0.77 on unseen sites). It was not adopted because the margin is
modest and inconsistent, it requires six prior overpasses at the same location (incompatible with
single-observation scoring and the regional demonstration mode), and it would forfeit exact SHAP
and the existing conformal calibration. Recorded as future work: lagged reflectance features for
XGBoost at sites with history.
