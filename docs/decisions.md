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

## D6 — Live mode: on-the-fly extraction from USGS's daily aquatic-reflectance product (2026-09-18)

The labelled release ends September 2024, so the historical dashboard could only score
2015–2024 overpasses. USGS keeps producing the *same* ACOLITE-DSF product daily on a public S3
bucket (`usgs-wma-sentinel-2-aqr-acolite-dsf`, CONUS, 20 m grid, int16 ×10⁴). `hydrosentinel/live.py`
reads only the 25 × 25-pixel window around a point from each band's cloud-optimised GeoTIFF and
rebuilds the training-table columns with USGS's own rules (250 m circle, `l2_flags == 0`,
negatives → NaN, per-band n_pixels / mean / std / median), then applies the same ≥ 5-valid-pixel
quality rule the training data was filtered with, walking back from the newest scene until one
passes.

**Deviation.** USGS additionally intersected an NHD water mask (rasterised resolvable flowlines /
waterbodies) that is not included in the release — only the code that builds it. Live mode uses
`NDWI > 0` from the product's own NDWI layer instead, which is the rule of USGS's alternative
`aqr_observations_NDWI.py` script. Effect: in a narrow river the NDWI mask may admit a few mixed
pixels the NHD mask would have excluded. Live extractions are therefore marked as such in the API
(`mode: "live"`, `extraction_note`).

**Live ground truth.** For USGS sites, the nearest instantaneous sonde reading within ±3 h of the
overpass is fetched from the NWIS IV service and shown beside the prediction (display only; it
never feeds the model). This makes a 2026 prediction checkable on screen.

**Coverage.** The product is conterminous-US only, so the regional demonstration mode works for any
CONUS coordinates (out-of-region tier when outside the five training basins) but not for the Ravi
River at Lahore. A non-US demo would need a Copernicus Data Space / Earth Engine feed and is not
wired in; the UI says so explicitly.

## D7 — Global imagery source for non-US sites, harmonised to the training product (2026-09-18)

The USGS aquatic-reflectance feed (D6) is conterminous-US only, so the Ravi, Chenab and Indus
could not be scored. `hydrosentinel/live_global.py` adds Copernicus Sentinel-2 **L2A** from the
public AWS archive (Earth Search STAC, no credentials, worldwide, scenes within a day of acquisition).

Three things had to be handled honestly:

1. **Different atmospheric correction.** L2A is Sen2Cor (land-oriented); the training data are
   ACOLITE-DSF aquatic reflectance. Measured over the same 250 m of water on the same day at 5
   training sites (15 pairs, `scripts/harmonise_l2a.py`), L2A reads brighter by a median factor of
   1.16–1.37 in the visible, ~1.25 in NIR and ~2.2 in SWIR, with interquartile ranges of roughly
   ±15 %. Live L2A band statistics are divided by these factors before scoring
   (`models/harmonisation_l2a.json`); the API reports the factors and spread. This is a stop-gap
   harmonisation from a small US-only sample, not a validated cross-calibration; the residual
   spread is uncertainty the conformal intervals do not include.
2. **Water masking.** NDWI > 0 (USGS's rule) fails on very turbid rivers under Sen2Cor because NIR
   exceeds green (Ravi at Lahore: SCL marks 169 water pixels, NDWI 3). The global source uses the
   Sen2Cor scene-classification water class OR NDWI > 0; cloud/shadow/snow classes replace
   `l2_flags`.
3. **Offset.** Earth Search COGs already have the BOA offset removed (`earthsearch:boa_offset_applied`),
   despite asset metadata still listing `offset -0.1`. Subtracting it again produced 88 % negative
   pixels at Portland; verified against USGS AQR on the same scene and fixed.

Outputs at these sites are labelled out-of-region, carry no percentile or stress score, and use the
Low / Very low confidence tiers. First results (18 Sep 2026 scenes, late monsoon): turbidity Ravi
≈ 400 FNU, Chenab ≈ 160 FNU, Indus at Sukkur ≈ 210 FNU — plausible in rank and magnitude for the
season, and unverified.

## D8 — Location baselines: a reference built from the archive where no measurements exist (2026-09-25)

Spec Section 6 ranks a prediction against the site's own historical record, falling back to the
basin's. Out of region there is neither, so the dashboard showed predictions with no way to judge
them — the regional demonstration mode's weakest point.

`hydrosentinel/baseline.py` builds the missing reference from the only source available at an
arbitrary coordinate: the Sentinel-2 archive. It extracts ~24 cloud-free scenes at that exact
point, scores each with the same models, and uses those predictions as the distribution.

**Why this is defensible.** The models are likely biased at an out-of-distribution location, but
that bias shifts today's prediction and every historical one alike, so it largely cancels in a
percentile. "Today is turbid for this stretch of the Ravi" survives a systematic error that
"today is 208 FNU" does not.

**Why it is not the stress score, and is never presented as one.** At training sites the reference
is *observed sonde readings*; here it is *model output*. The two are different in kind, so the
result is surfaced as a **Local Anomaly Score** under its own API key (`local_baseline`), on a card
with its own border and wording, always carrying `kind: "model_predictions"` and a note stating it
is not ground truth. It never raises the confidence tier — the models remain unvalidated there.

**Sampling.** The first implementation took the newest usable scenes and, because most scenes at
these sites are cloud-free, stopped after a few weeks of imagery: the Ravi baseline spanned 27 Aug
to 23 Sep, comparing late monsoon against late monsoon. Scenes are now sampled evenly across a
two-year window and then shuffled with a fixed seed, so any prefix — builds are truncated whenever
cloud forces an early stop — remains an unbiased sample of the period. A baseline spanning under
300 days is flagged in the response and on screen as unable to speak to seasonality.

**Cost.** Roughly 4-8 minutes per location (one extraction per scene), then cached. The dashboard
offers a button rather than building automatically, so the cost is a deliberate choice.
