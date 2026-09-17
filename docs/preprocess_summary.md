# Preprocessing summary
Generated 2026-09-17T13:21:48+00:00 by `backend/scripts/preprocess.py`.

Raw rows with a target parameter code: **1,291,747** → distinct scene×site×target matchups (nearest sonde reading per overpass): **14,665**.

## Rows dropped per filter rule

| rule | dropped | remaining |
|---|---|---|
| |offset| <= 3.0 h | 197 | 14,468 |
| min n_pixels >= 5 on B02/B03/B04/B08 | 5,154 | 9,314 |
| not truncated at scene edge | 0 | 9,314 |
| no remark code in ('<', '>', 'e') | 21 | 9,293 |
| value > 0 | 22 | 9,271 |
| all band means present | 241 | 9,030 |

## Usable observations per basin × target

| target | Delaware | Illinois | Trinity | Upper Colorado | Willamette | total | sites | sites_ge_30 |
|---|---|---|---|---|---|---|---|---|
| turbidity | 1,442 | 1,084 | 1,809 | 614 | 1,211 | 6,160 | 47 | 36 |
| chlorophyll_a | 352 | 1,407 | 211 | 0 | 379 | 2,349 | 18 | 17 |
| cdom | 82 | 60 | 0 | 0 | 379 | 521 | 6 | 6 |

Decisions behind each rule: [data_findings.md](data_findings.md).
