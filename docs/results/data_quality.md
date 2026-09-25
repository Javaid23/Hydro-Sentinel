# Does keeping provisional measurements change the conclusions?
Generated 2026-09-25 16:37 UTC by `backend/scripts/evaluate_data_quality.py`.

USGS marks each sonde reading **approved (A)** or **provisional (P)**. Provisional values have not been through the agency's review. Preprocessing keeps both and records the code; this is the test of whether that choice affects the results.

| Target | Records | Approved | Approved share | LOBO R²_log (all) | LOBO R²_log (approved only) |
|---|---|---|---|---|---|
| Turbidity | 6,160 | 5,403 | 88% | 0.188 | 0.249 |
| Chlorophyll-a | 2,349 | 1,747 | 74% | -4.749 | -2.883 |
| CDOM (fDOM proxy) | 521 | 60 | 12% | -11.158 | not evaluable |

## What this shows

**Turbidity** — both subsets support the design. Training on approved records only scores R²_log +0.249 against +0.188 for all records (better by 0.061), on 5,403 rows instead of 6,160. The difference is small relative to the spread between basins, so provisional records are not inflating the result.

**Chlorophyll-a** — both subsets support the design. Training on approved records only scores R²_log -2.883 against -4.749 for all records (better by 1.866), on 1,747 rows instead of 2,349. **These two figures are not directly comparable**: restricting the data drops the evaluation from 4 basins to 3, so the means are over different folds. What does carry across is the sign — the target fails to transfer to an unseen basin either way.

**CDOM (fDOM proxy)** — restricting to approved records leaves 60 rows across 1 basin(s) — below the 200 row / 3 basin floor for a meaningful leave-one-basin-out. Dropping provisional data would remove the target from the evaluation altogether, so it is kept and the approval code is retained on every row.

## Why provisional records are kept

Restricting to approved data would not make the system more trustworthy — it would shrink the evidence base to the point where the honest conclusions above could not be drawn at all. The approval code travels with every row (`measurement_cd`), so any future analysis can split on it.
