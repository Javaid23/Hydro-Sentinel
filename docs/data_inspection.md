# Raw data inspection report
Source: `C:/Users/Lenovo/Desktop/Hydro Sentinel/data/raw` — files: `Matched_WQ_S2_1.csv`, `Matched_WQ_S2_2.csv`

Total rows (all files): **1,748,467** — layout is LONG: one row per scene × site × parameter.

## Rows per file

| __file | rows |
|---|---|
| Matched_WQ_S2_1.csv | 874,234 |
| Matched_WQ_S2_2.csv | 874,233 |

## Exact columns (85)

| # | column | dtype (sample) | example |
|---|---|---|---|
| 0 | `scene` | str | S2B_MSIAQR_20180523T153819_N0206_R011_T18SWJ_20180 |
| 1 | `source` | str | NWIS |
| 2 | `Organization` | str | USGS-NWIS |
| 3 | `scene_datetime_UTC` | str | 2018-05-23 15:38:19+00:00 |
| 4 | `sample_datetime_UTC` | str | 2018-05-23 03:42:00+00:00 |
| 5 | `site_no` | int64 | 140928320 |
| 6 | `SampleID` | float64 |  |
| 7 | `station_nm` | str | Westecunk Crk 3700 ft US of mouth nr West Creek NJ |
| 8 | `parm_cd` | int64 | 63680 |
| 9 | `parm_nm` | str | Turbidity, water, unfiltered, monochrome near infr |
| 10 | `parm_unit` | str | FNU |
| 11 | `loc_web_ds` | float64 |  |
| 12 | `Lat` | float64 | 39.62052778 |
| 13 | `Long` | float64 | -74.2736861 |
| 14 | `MeasurementValue` | float64 | 6.9 |
| 15 | `MeasurementCd` | str | A |
| 16 | `Depth` | float64 |  |
| 17 | `DepthCd` | float64 |  |
| 18 | `DepthPcode` | float64 |  |
| 19 | `DepthUnits` | float64 |  |
| 20 | `site_tp_cd` | str | ST |
| 21 | `huc4` | float64 | 204.0 |
| 22 | `nhd_identifier` | str | [10000200271306] |
| 23 | `nhd_feature_type` | str | Flowline |
| 24 | `n_l2flag` | float64 | 0.0 |
| 25 | `l2flag_center` | float64 | 0.0 |
| 26 | `n_nhd` | float64 | 62.0 |
| 27 | `n_buf` | float64 | 489.0 |
| 28 | `n_mask` | float64 | 0.0 |
| 29 | `truncated` | float64 | 0.0 |
| 30 | `B01_n_pixels` | float64 | 0.0 |
| 31 | `B01_center` | float64 | 5209.0 |
| 32 | `B01_buf250_mean` | float64 | 350.57 |
| 33 | `B01_buf250_std` | float64 | 91.52 |
| 34 | `B01_buf250_med` | float64 | 343.0 |
| 35 | `B02_n_pixels` | float64 | 0.0 |
| 36 | `B02_center` | float64 | 5759.0 |
| 37 | `B02_buf250_mean` | float64 | 326.1 |
| 38 | `B02_buf250_std` | float64 | 117.46 |
| 39 | `B02_buf250_med` | float64 | 291.0 |
| 40 | `B03_n_pixels` | float64 | 0.0 |
| 41 | `B03_center` | float64 | 5839.0 |
| 42 | `B03_buf250_mean` | float64 | 355.77 |
| 43 | `B03_buf250_std` | float64 | 129.35 |
| 44 | `B03_buf250_med` | float64 | 317.5 |
| 45 | `B04_n_pixels` | float64 | 0.0 |
| 46 | `B04_center` | float64 | 5939.0 |
| 47 | `B04_buf250_mean` | float64 | 259.23 |
| 48 | `B04_buf250_std` | float64 | 161.39 |
| 49 | `B04_buf250_med` | float64 | 203.5 |
| 50 | `B05_n_pixels` | float64 | 0.0 |
| 51 | `B05_center` | float64 | 5664.0 |
| 52 | `B05_buf250_mean` | float64 | 299.1 |
| 53 | `B05_buf250_std` | float64 | 167.22 |
| 54 | `B05_buf250_med` | float64 | 266.0 |
| 55 | `B06_n_pixels` | float64 | 0.0 |
| 56 | `B06_center` | float64 | 5995.0 |
| 57 | `B06_buf250_mean` | float64 | 489.93 |
| 58 | `B06_buf250_std` | float64 | 156.29 |
| 59 | `B06_buf250_med` | float64 | 489.5 |
| 60 | `B07_n_pixels` | float64 | 0.0 |
| 61 | `B07_center` | float64 | 6077.0 |
| 62 | `B07_buf250_mean` | float64 | 579.0 |
| 63 | `B07_buf250_std` | float64 | 171.75 |
| 64 | `B07_buf250_med` | float64 | 591.5 |
| 65 | `B08_n_pixels` | float64 | 0.0 |
| 66 | `B08_center` | float64 | 6047.0 |
| 67 | `B08_buf250_mean` | float64 | 513.8 |
| 68 | `B08_buf250_std` | float64 | 152.47 |
| 69 | `B08_buf250_med` | float64 | 460.5 |
| 70 | `B11_n_pixels` | float64 | 0.0 |
| 71 | `B11_center` | float64 | 5576.0 |
| 72 | `B11_buf250_mean` | float64 | 294.33 |
| 73 | `B11_buf250_std` | float64 | 137.24 |
| 74 | `B11_buf250_med` | float64 | 297.0 |
| 75 | `B12_n_pixels` | float64 | 0.0 |
| 76 | `B12_center` | float64 | 4920.0 |
| 77 | `B12_buf250_mean` | float64 | 200.03 |
| 78 | `B12_buf250_std` | float64 | 124.23 |
| 79 | `B12_buf250_med` | float64 | 190.0 |
| 80 | `B8A_n_pixels` | float64 | 0.0 |
| 81 | `B8A_center` | float64 | 6298.0 |
| 82 | `B8A_buf250_mean` | float64 | 559.57 |
| 83 | `B8A_buf250_std` | float64 | 157.8 |
| 84 | `B8A_buf250_med` | float64 | 575.5 |

## Water-quality parameters present (`parm_cd`)

| parm_cd | parm_nm | parm_unit | rows | sites | value_min | value_med | value_max |
|---|---|---|---|---|---|---|---|
| 63680 | Turbidity, water, unfiltered, monochrome near infra-red LED light, 780-900 nm, detection angle 90 +-2.5 degrees, formazin nephelometric units (FNU) | FNU | 959,508 | 57 | 0 | 11.3 | 4000 |
| 32316 | Chlorophyll fluorescence (fChl), water, in situ, concentration estimated from reference material, micrograms per liter as chlorophyll | ug/l | 236,111 | 16 | -2.4 | 9.3 | 638.6 |
| 80297 | Suspended sediment load, water, unfiltered, computed, the product of regression-computed suspended sediment concentration and streamflow, short tons per day | tons/day | 130,941 | 1 | -1000 | 106 | 8150 |
| 32315 | Chlorophyll relative fluorescence (fChl), water, in situ, relative fluorescence units (RFU) | RFU | 101,616 | 17 | -0.03 | 0.81 | 156.3 |
| 99246 | Upper 90 percent prediction limit for SSC by regression (PCODE 99409), milligrams per liter | mg/l | 94,922 | 1 | 0.5 | 5.1 | 82.2 |
| 99409 | Suspended sediment concentration, water, unfiltered, estimated by regression equation, milligrams per liter | mg/l | 94,056 | 1 | 0.1 | 2.7 | 54.7 |
| 32295 | Dissolved organic matter fluorescence (fDOM), water, in situ, concentration estimated from reference material, micrograms per liter as quinine sulfate equivalents (QSE) | ug/l QSE | 74,518 | 8 | 0 | 12.11 | 77.5 |
| 32322 | Dissolved organic matter relative fluorescence (fDOM), water, in situ, relative fluorescence units (RFU) | RFU | 25,766 | 1 | 4.69 | 11.62 | 23.42 |
| 62361 | Chlorophyll, total, water, fluorometric, 650-700 nanometers, in situ sensor, micrograms per liter | ug/l | 13,363 | 2 | 0 | 1.1 | 25 |
| 32320 | Chlorophyll fluorescence (fChl), water, in situ, fluorometric method, excitation at 470 +-15 nm, emission at 685 +-20 nm, relative fluorescence units (RFU) | RFU | 9,419 | 1 | 0.2 | 1 | 8.7 |
| 32318 | Chlorophylls, water, in situ, fluorometric method, excitation at 470 +-15 nm, emission at 685 +-20 nm, micrograms per liter | ug/l | 8,247 | 1 | -0.1 | 1.2 | 54.2 |

## Rows per basin (`huc4`)

| huc4 | basin | rows | sites | scenes |
|---|---|---|---|---|
| 1709.0 | Willamette | 576,345 | 11 | 1,136 |
| 204.0 | Delaware | 280,578 | 16 | 1,121 |
| 1204.0 | UNMAPPED huc4=1204.0 | 247,665 | 4 | 1,045 |
| 1401.0 | Upper Colorado | 204,513 | 10 | 1,231 |
| 713.0 | Illinois | 180,416 | 4 | 887 |
| 712.0 | Illinois | 179,945 | 7 | 721 |
| 1402.0 | Upper Colorado | 49,735 | 4 | 354 |
| 1203.0 | Trinity | 29,270 | 3 | 290 |

**Unmapped huc4 codes:** [1204.0] — extend `HUC4_BASIN`.

## Rows per basin × parameter

| basin | 32295 | 32315 | 32316 | 32318 | 32320 | 32322 | 62361 | 63680 | 80297 | 99246 | 99409 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Delaware | 25,460 | 63,461 | 9,269 | 8,247 | 9,419 | 25,766 | 0 | 138,956 | 0 | 0 | 0 |
| Illinois | 7,236 | 12,115 | 165,258 | 0 | 0 | 0 | 0 | 175,752 | 0 | 0 | 0 |
| Trinity | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 29,270 | 0 | 0 | 0 |
| UNMAPPED huc4=1204.0 | 0 | 0 | 33,908 | 0 | 0 | 0 | 0 | 213,757 | 0 | 0 | 0 |
| Upper Colorado | 61 | 9,598 | 0 | 0 | 0 | 0 | 0 | 244,589 | 0 | 0 | 0 |
| Willamette | 41,761 | 16,442 | 27,676 | 0 | 0 | 0 | 13,363 | 157,184 | 130,941 | 94,922 | 94,056 |

## Sites

Distinct sites: **59**

| site_no | station_nm | basin | rows | scenes | params | first | last |
|---|---|---|---|---|---|---|---|
| 14211720 | WILLAMETTE RIVER AT PORTLAND, OR | Willamette | 354,567 | 437 | 6 | 2015-11-23 07:30:00+00:00 | 2024-09-29 07:00:00+00:00 |
| 1467200 | Delaware River at Penn's Landing, Philadelphia, PA | Delaware | 112,109 | 197 | 5 | 2017-01-26 04:00:00+00:00 | 2024-09-22 00:45:00+00:00 |
| 295826095082200 | Lk Houston S Union Pacific RR Bridge nr Houston,TX | UNMAPPED huc4=1204.0 | 77,477 | 682 | 2 | 2015-08-06 05:15:00+00:00 | 2024-09-30 02:45:00+00:00 |
| 5586300 | ILLINOIS RIVER AT FLORENCE, IL | Illinois | 75,327 | 250 | 3 | 2015-08-03 05:15:00+00:00 | 2024-09-30 03:45:00+00:00 |
| 14211010 | CLACKAMAS RIVER NEAR OREGON CITY, OR | Willamette | 74,939 | 435 | 4 | 2015-11-23 07:30:00+00:00 | 2024-09-29 07:00:00+00:00 |
| 294643095035200 | Lynchburg Res nr CWA Canal Inflow nr Baytown, TX | UNMAPPED huc4=1204.0 | 74,332 | 647 | 2 | 2016-08-20 06:01:00+00:00 | 2024-09-30 02:45:00+00:00 |
| 5553700 | ILLINOIS RIVER AT STARVED ROCK, IL | Illinois | 54,447 | 429 | 2 | 2018-06-13 05:00:00+00:00 | 2024-09-30 03:45:00+00:00 |
| 5537980 | DES PLAINES RIVER AT ROUTE 53 AT JOLIET, IL | Illinois | 52,780 | 199 | 2 | 2017-11-22 05:00:00+00:00 | 2024-09-27 03:30:00+00:00 |
| 295554095093402 | Lk Hou at Jack's Ditch (Site 2) nr Houston, TX | UNMAPPED huc4=1204.0 | 52,429 | 626 | 1 | 2015-08-06 06:00:00+00:00 | 2024-09-30 02:45:00+00:00 |
| 14670261 | Delaware River at Pennypack Woods PA | Delaware | 51,353 | 386 | 2 | 2018-10-03 04:00:00+00:00 | 2024-09-22 00:45:00+00:00 |
| 9088600 | COLORADO RIVER ABOVE DIVIDE CREEK NEAR SILT, CO | Upper Colorado | 47,569 | 173 | 1 | 2022-04-29 06:00:00+00:00 | 2024-09-28 04:40:00+00:00 |
| 14158100 | WILLAMETTE RIVER AT OWOSSO BRIDGE AT EUGENE, OR | Willamette | 44,769 | 482 | 1 | 2015-10-04 07:30:00+00:00 | 2024-09-29 07:00:00+00:00 |
| 300032095080501 | Lk Houston at FM 1960 nr Huffman, TX | UNMAPPED huc4=1204.0 | 43,427 | 515 | 1 | 2018-07-01 05:00:00+00:00 | 2024-09-30 02:45:00+00:00 |
| 5558300 | ILLINOIS RIVER AT HENRY, IL | Illinois | 38,656 | 334 | 2 | 2018-06-15 04:45:00+00:00 | 2024-09-27 03:30:00+00:00 |
| 5538020 | DES PLAINES RIVER IN LOCK CHANNEL AT ROCKDALE, IL | Illinois | 38,294 | 209 | 2 | 2015-09-19 05:00:00+00:00 | 2024-09-27 03:30:00+00:00 |
| 14210000 | CLACKAMAS RIVER AT ESTACADA, OR | Willamette | 37,681 | 436 | 4 | 2015-11-23 07:30:00+00:00 | 2024-09-29 07:00:00+00:00 |
| 5543010 | ILLINOIS RIVER AT SENECA, IL | Illinois | 36,503 | 202 | 2 | 2015-08-10 04:45:00+00:00 | 2024-09-27 03:30:00+00:00 |
| 9071750 | COLORADO RIVER ABOVE GLENWOOD SPRINGS, CO | Upper Colorado | 35,889 | 387 | 2 | 2020-10-31 06:15:00+00:00 | 2024-09-28 04:45:00+00:00 |
| 9144250 | GUNNISON RIVER AT DELTA, CO | Upper Colorado | 31,464 | 337 | 1 | 2021-06-25 06:00:00+00:00 | 2024-09-28 04:45:00+00:00 |
| 9070500 | COLORADO RIVER NEAR DOTSERO, CO | Upper Colorado | 30,091 | 327 | 1 | 2021-04-09 19:15:00+00:00 | 2024-09-28 04:45:00+00:00 |
| 5545750 | FOX RIVER NEAR NEW MUNSTER, WI | Illinois | 24,177 | 160 | 2 | 2022-01-30 05:00:00+00:00 | 2024-09-30 02:45:00+00:00 |
| 5549500 | FOX RIVER NEAR MCHENRY, IL | Illinois | 21,405 | 118 | 2 | 2018-09-13 04:45:00+00:00 | 2024-09-27 03:30:00+00:00 |
| 1463500 | Delaware River at Trenton NJ | Delaware | 21,098 | 551 | 2 | 2015-08-02 04:00:00+00:00 | 2024-09-22 00:00:00+00:00 |
| 9060799 | COLORADO RIVER AT CATAMOUNT BRIDGE, CO | Upper Colorado | 20,428 | 221 | 1 | 2021-07-15 17:45:00+00:00 | 2024-09-28 04:45:00+00:00 |
| 1473500 | Schuylkill River at Norristown, PA | Delaware | 20,421 | 221 | 1 | 2015-08-25 04:30:00+00:00 | 2024-09-22 00:45:00+00:00 |
| 9095500 | COLORADO RIVER NEAR CAMEO, CO. | Upper Colorado | 20,167 | 216 | 1 | 2020-08-27 18:15:00+00:00 | 2024-09-26 05:00:00+00:00 |
| 8062500 | Trinity Rv nr Rosser, TX | Trinity | 18,898 | 218 | 1 | 2015-08-06 05:15:00+00:00 | 2024-09-27 23:15:00+00:00 |
| 1427510 | DELAWARE RIVER AT CALLICOON NY | Delaware | 18,541 | 101 | 2 | 2019-12-22 04:00:00+00:00 | 2024-09-22 01:45:00+00:00 |
| 400853105563701 | WILLOW CREEK RESERVOIR NEAR DAM NEAR GRANBY, CO | Upper Colorado | 18,251 | 64 | 2 | 2022-05-16 06:01:00+00:00 | 2024-09-23 04:46:00+00:00 |
| 444306122144600 | DETROIT LAKE AT LOG BOOM BEHIND DETROIT DAM, OR | Willamette | 17,211 | 74 | 4 | 2022-06-21 10:56:00+00:00 | 2024-09-29 06:56:00+00:00 |
| 1458500 | Delaware River at Frenchtown NJ | Delaware | 17,053 | 234 | 1 | 2015-08-25 04:30:00+00:00 | 2024-09-22 00:45:00+00:00 |
| 9163500 | COLORADO RIVER NEAR COLORADO-UTAH STATE LINE | Upper Colorado | 16,665 | 182 | 1 | 2021-05-29 06:00:00+00:00 | 2024-09-26 05:00:00+00:00 |
| 9152500 | GUNNISON RIVER NEAR GRAND JUNCTION, CO. | Upper Colorado | 15,120 | 163 | 1 | 2021-07-03 06:00:00+00:00 | 2024-09-26 05:00:00+00:00 |
| 441022122193200 | BLUE RIVER LAKE NEAR BLUE RIVER, OR (WQM) | Willamette | 13,701 | 64 | 3 | 2022-05-17 07:56:00+00:00 | 2024-08-15 05:23:00+00:00 |
| 5559900 | ILLINOIS RIVER ABOVE RTE 150 AT PEORIA, IL | Illinois | 11,986 | 68 | 2 | 2023-03-26 04:45:00+00:00 | 2024-09-27 03:30:00+00:00 |
| 453027122400000 | WILLAMETTE RIVER BLW HOLGATE CHANNEL, PORTLAND, OR | Willamette | 11,888 | 66 | 2 | 2023-06-06 20:30:00+00:00 | 2024-09-17 07:00:00+00:00 |
| 14152000 | MIDDLE FORK WILLAMETTE RIVER AT JASPER, OR | Willamette | 9,912 | 109 | 1 | 2015-10-04 07:30:00+00:00 | 2024-09-29 07:00:00+00:00 |
| 1427207 | DELAWARE RIVER AT LORDVILLE NY | Delaware | 8,217 | 91 | 1 | 2021-05-15 04:00:00+00:00 | 2024-09-22 01:45:00+00:00 |
| 9092570 | COLORADO RIVER AT RULISON, CO. | Upper Colorado | 7,641 | 83 | 1 | 2022-06-13 06:00:00+00:00 | 2024-09-26 05:00:00+00:00 |
| 14187500 | SOUTH SANTIAM RIVER AT WATERLOO, OR | Willamette | 7,312 | 78 | 1 | 2023-08-10 07:00:00+00:00 | 2024-09-29 07:00:00+00:00 |
| 1438500 | Delaware River at Montague NJ | Delaware | 7,070 | 158 | 1 | 2019-10-18 04:00:00+00:00 | 2024-09-22 00:30:00+00:00 |
| 401330074001201 | Sunset Lake east of Heck St at Asbury Park NJ | Delaware | 6,952 | 14 | 2 | 2022-08-03 03:50:00+00:00 | 2023-04-03 00:35:00+00:00 |
| 9058000 | COLORADO RIVER NEAR KREMMLING, CO | Upper Colorado | 6,921 | 77 | 1 | 2022-05-06 06:00:00+00:00 | 2024-09-28 04:45:00+00:00 |
| 401349074000601 | Deal lake DS of Park Ave at Asbury Park NJ | Delaware | 6,561 | 14 | 2 | 2022-08-03 03:50:00+00:00 | 2023-04-03 00:35:00+00:00 |
| 423784088133401 | Long Lake at BEN Dock at Long Lake, IL | Illinois | 5,829 | 25 | 2 | 2023-05-20 04:45:00+00:00 | 2024-09-27 03:34:00+00:00 |
| 8067000 | Trinity Rv at Liberty, TX | Trinity | 5,553 | 61 | 1 | 2022-09-10 05:00:00+00:00 | 2024-09-30 02:45:00+00:00 |
| 8067250 | Trinity Rv at IH 10 nr Wallisville, TX | Trinity | 4,819 | 54 | 1 | 2022-11-09 05:00:00+00:00 | 2024-09-30 02:45:00+00:00 |
| 401350073595201 | Deal Lake at Flume House at Asbury Park NJ | Delaware | 4,456 | 9 | 2 | 2022-08-03 03:50:00+00:00 | 2023-04-03 00:35:00+00:00 |
| 442453122394900 | FOSTER LAKE BELOW GEDNEY CREEK, AT FOSTER, OR | Willamette | 3,550 | 38 | 1 | 2023-09-09 07:00:00+00:00 | 2024-09-29 07:00:00+00:00 |
| 401347074003501 | Deal lake at Railroad Bridge at Asbury Park NJ | Delaware | 3,003 | 6 | 2 | 2022-08-03 03:50:00+00:00 | 2022-09-30 00:35:00+00:00 |
| 382852107054801 | BLUE MESA RESERVOIR IN IOLA BASIN NR GUNNISON CO | Upper Colorado | 2,276 | 12 | 2 | 2022-07-30 06:00:00+00:00 | 2022-09-24 04:45:00+00:00 |
| 401352074002701 | Deal Lake 150 ft east of Main St at Interlaken NJ | Delaware | 1,922 | 4 | 2 | 2023-09-12 16:50:00+00:00 | 2023-09-20 01:35:00+00:00 |
| 405610074382301 | Lk Hopatcong 9600 ft NE of dam at Hopatcong NJ | Delaware | 1,318 | 14 | 1 | 2019-07-12 03:45:00+00:00 | 2019-08-30 00:45:00+00:00 |
| 5538010 | DES PLAINES RIVER AT ROCKDALE, IL | Illinois | 957 | 10 | 1 | 2015-09-19 05:00:00+00:00 | 2017-05-22 04:30:00+00:00 |
| 395430106470301 | COLORADO RIVER BELOW ELK CREEK NEAR MCCOY, CO | Upper Colorado | 891 | 12 | 1 | 2021-05-01 06:00:00+00:00 | 2021-07-26 04:45:00+00:00 |
| 382847107120401 | BLUE MESA RES WEST OF DRY GULCH NEAR SAPINERO, CO | Upper Colorado | 875 | 5 | 2 | 2022-09-03 06:00:00+00:00 | 2022-09-24 05:30:00+00:00 |
| 14150000 | MIDDLE FORK WILLAMETTE RIVER NEAR DEXTER, OR | Willamette | 815 | 9 | 1 | 2024-08-09 07:00:00+00:00 | 2024-09-29 07:00:00+00:00 |
| 140928320 | Westecunk Crk 3700 ft US of mouth nr West Creek NJ | Delaware | 384 | 2 | 1 | 2018-05-23 03:42:00+00:00 | 2018-08-22 00:36:00+00:00 |
| 401345074010601 | Deal Lake at Sunset Ave at Asbury Park NJ | Delaware | 120 | 1 | 2 | 2023-09-19 20:40:00+00:00 | 2023-09-20 01:35:00+00:00 |

## Unique scenes per site × parameter (candidate observation counts)

| basin | site_no | 32295 | 32315 | 32316 | 32318 | 32320 | 32322 | 62361 | 63680 | 80297 | 99246 | 99409 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Delaware | 1427207 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 91 | 0 | 0 | 0 |
| Delaware | 1427510 | 0 | 101 | 101 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Delaware | 1438500 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 158 | 0 | 0 | 0 |
| Delaware | 1458500 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 234 | 0 | 0 | 0 |
| Delaware | 1463500 | 0 | 0 | 0 | 353 | 0 | 0 | 0 | 550 | 0 | 0 | 0 |
| Delaware | 1467200 | 97 | 97 | 0 | 0 | 99 | 97 | 0 | 96 | 0 | 0 | 0 |
| Delaware | 1473500 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 221 | 0 | 0 | 0 |
| Delaware | 14670261 | 0 | 183 | 0 | 0 | 0 | 0 | 0 | 386 | 0 | 0 | 0 |
| Delaware | 140928320 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| Delaware | 401330074001201 | 0 | 14 | 0 | 0 | 0 | 0 | 0 | 14 | 0 | 0 | 0 |
| Delaware | 401345074010601 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| Delaware | 401347074003501 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| Delaware | 401349074000601 | 0 | 12 | 0 | 0 | 0 | 0 | 0 | 14 | 0 | 0 | 0 |
| Delaware | 401350073595201 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 9 | 0 | 0 | 0 |
| Delaware | 401352074002701 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| Delaware | 405610074382301 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 14 | 0 | 0 | 0 |
| Illinois | 5537980 | 0 | 0 | 195 | 0 | 0 | 0 | 0 | 199 | 0 | 0 | 0 |
| Illinois | 5538010 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 0 |
| Illinois | 5538020 | 0 | 0 | 207 | 0 | 0 | 0 | 0 | 207 | 0 | 0 | 0 |
| Illinois | 5543010 | 0 | 0 | 202 | 0 | 0 | 0 | 0 | 202 | 0 | 0 | 0 |
| Illinois | 5545750 | 0 | 139 | 0 | 0 | 0 | 0 | 0 | 139 | 0 | 0 | 0 |
| Illinois | 5549500 | 0 | 0 | 118 | 0 | 0 | 0 | 0 | 115 | 0 | 0 | 0 |
| Illinois | 5553700 | 0 | 0 | 429 | 0 | 0 | 0 | 0 | 188 | 0 | 0 | 0 |
| Illinois | 5558300 | 0 | 0 | 326 | 0 | 0 | 0 | 0 | 93 | 0 | 0 | 0 |
| Illinois | 5559900 | 0 | 0 | 68 | 0 | 0 | 0 | 0 | 68 | 0 | 0 | 0 |
| Illinois | 5586300 | 76 | 0 | 245 | 0 | 0 | 0 | 0 | 250 | 0 | 0 | 0 |
| Illinois | 423784088133401 | 0 | 0 | 25 | 0 | 0 | 0 | 0 | 25 | 0 | 0 | 0 |
| Trinity | 8062500 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 218 | 0 | 0 | 0 |
| Trinity | 8067000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 61 | 0 | 0 | 0 |
| Trinity | 8067250 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 54 | 0 | 0 | 0 |
| UNMAPPED huc4=1204.0 | 294643095035200 | 0 | 0 | 158 | 0 | 0 | 0 | 0 | 647 | 0 | 0 | 0 |
| UNMAPPED huc4=1204.0 | 295554095093402 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 626 | 0 | 0 | 0 |
| UNMAPPED huc4=1204.0 | 295826095082200 | 0 | 0 | 208 | 0 | 0 | 0 | 0 | 680 | 0 | 0 | 0 |
| UNMAPPED huc4=1204.0 | 300032095080501 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 515 | 0 | 0 | 0 |
| Upper Colorado | 9058000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 77 | 0 | 0 | 0 |
| Upper Colorado | 9060799 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 221 | 0 | 0 | 0 |
| Upper Colorado | 9070500 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 327 | 0 | 0 | 0 |
| Upper Colorado | 9071750 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 387 | 0 | 0 | 0 |
| Upper Colorado | 9088600 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 173 | 0 | 0 | 0 |
| Upper Colorado | 9092570 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 83 | 0 | 0 | 0 |
| Upper Colorado | 9095500 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 216 | 0 | 0 | 0 |
| Upper Colorado | 9144250 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 337 | 0 | 0 | 0 |
| Upper Colorado | 9152500 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 163 | 0 | 0 | 0 |
| Upper Colorado | 9163500 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 182 | 0 | 0 | 0 |
| Upper Colorado | 382847107120401 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| Upper Colorado | 382852107054801 | 0 | 12 | 0 | 0 | 0 | 0 | 0 | 12 | 0 | 0 | 0 |
| Upper Colorado | 395430106470301 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 0 | 0 | 0 |
| Upper Colorado | 400853105563701 | 0 | 62 | 0 | 0 | 0 | 0 | 0 | 63 | 0 | 0 | 0 |
| Willamette | 14150000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 0 | 0 | 0 |
| Willamette | 14152000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 109 | 0 | 0 | 0 |
| Willamette | 14158100 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 482 | 0 | 0 | 0 |
| Willamette | 14187500 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 78 | 0 | 0 | 0 |
| Willamette | 14210000 | 195 | 43 | 0 | 0 | 0 | 0 | 154 | 435 | 0 | 0 | 0 |
| Willamette | 14211010 | 195 | 43 | 152 | 0 | 0 | 0 | 0 | 435 | 0 | 0 | 0 |
| Willamette | 14211720 | 165 | 0 | 0 | 0 | 0 | 0 | 146 | 434 | 167 | 169 | 167 |
| Willamette | 441022122193200 | 64 | 0 | 64 | 0 | 0 | 0 | 0 | 64 | 0 | 0 | 0 |
| Willamette | 442453122394900 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 38 | 0 | 0 | 0 |
| Willamette | 444306122144600 | 72 | 74 | 72 | 0 | 0 | 0 | 0 | 72 | 0 | 0 | 0 |
| Willamette | 453027122400000 | 0 | 66 | 66 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Sites with ≥30 scenes for a parameter (LSTM eligibility per spec Section 3):

| parm_cd | sites_ge_30 |
|---|---|
| 32295 | 7 |
| 32315 | 9 |
| 32316 | 15 |
| 32318 | 1 |
| 32320 | 1 |
| 32322 | 1 |
| 62361 | 2 |
| 63680 | 43 |
| 80297 | 1 |
| 99246 | 1 |
| 99409 | 1 |

## Time coverage

- scene_datetime_UTC: 2015-08-02 15:51:36+00:00 → 2024-09-29 16:50:19+00:00 (unparsed: 0)
- sample_datetime_UTC: 2015-08-02 04:00:00+00:00 → 2024-09-30 03:45:00+00:00 (unparsed: 0)
- sample − scene offset (hours): p0=-12.0, p5=-10.8, p25=-6.0, p50=-0.1, p75=6.0, p95=10.8, p100=12.0
- |offset| ≤ 3h: 25.0%, ≤ 12h: 100.0%, ≤ 24h: 100.0%

### Scenes per year

| scene_datetime_UTC | rows |
|---|---|
| 2015 | 4,553 |
| 2016 | 17,234 |
| 2017 | 50,972 |
| 2018 | 89,139 |
| 2019 | 100,663 |
| 2020 | 106,451 |
| 2021 | 159,983 |
| 2022 | 398,637 |
| 2023 | 475,307 |
| 2024 | 345,528 |

### Duplicate (scene, site, parm_cd) rows — multiple samples matched to one overpass

1,748,400 rows (100.0%) share a scene/site/parameter with another row.

## Measurement approval (`MeasurementCd`)

| MeasurementCd | rows |
|---|---|
| A | 1,043,939 |
| P | 688,228 |
| A, R | 14,477 |
| P, e | 863 |
| A, > | 330 |
| A, < | 276 |
| A, e | 144 |
| P, > | 103 |
| A, [4] | 101 |
| P, < | 6 |

## Categorical metadata


`source`:

| source | rows |
|---|---|
| NWIS | 1,748,467 |

`Organization`:

| Organization | rows |
|---|---|
| USGS-NWIS | 1,748,467 |

`site_tp_cd`:

| site_tp_cd | rows |
|---|---|
| ST | 1,055,391 |
| ST-TS | 359,386 |
| LK | 333,690 |

`nhd_feature_type`:

| nhd_feature_type | rows |
|---|---|
| Flowline | 1,402,791 |
| Waterbody | 345,676 |

`truncated`:

| truncated | rows |
|---|---|
| 0.0 | 1,733,954 |
| 1.0 | 14,513 |

`l2flag_center`:

| l2flag_center | rows |
|---|---|
| 0.0 | 1,181,829 |
| 1.0 | 566,638 |

## Pixel-count / mask columns

| index | count | mean | std | min | 5% | 25% | 50% | 75% | 95% | max |
|---|---|---|---|---|---|---|---|---|---|---|
| n_l2flag | 1.748e+06 | 167.8 | 148.5 | 0 | 0 | 22 | 137 | 300 | 452 | 489 |
| n_nhd | 1.748e+06 | 188.5 | 149.6 | 1 | 2 | 28 | 218 | 286 | 489 | 489 |
| n_buf | 1.748e+06 | 488.6 | 4.536 | 439 | 489 | 489 | 489 | 489 | 489 | 489 |
| n_mask | 1.748e+06 | 130.1 | 140 | 0 | 0 | 1 | 70 | 255 | 417 | 489 |

## Reflectance bands

| band | mean_min | mean_p05 | mean_p50 | mean_p95 | mean_max | missing | neg | n_pixels_p50 | n_pixels_0 |
|---|---|---|---|---|---|---|---|---|---|
| B01 | 3.65 | 108.5 | 274.1 | 625.9 | 2858 | 373,721 | 0 | 70 | 373,721 |
| B02 | 6.44 | 130 | 283.9 | 649.3 | 2830 | 372,188 | 0 | 70 | 372,188 |
| B03 | 16 | 192.3 | 381.5 | 926.6 | 2757 | 372,188 | 0 | 70 | 372,188 |
| B04 | 5.39 | 115.2 | 298.1 | 929 | 2863 | 372,188 | 0 | 70 | 372,188 |
| B05 | 12.99 | 126.3 | 329 | 941.1 | 3236 | 372,188 | 0 | 70 | 372,188 |
| B06 | 5 | 114.1 | 263.5 | 691.6 | 3153 | 372,764 | 0 | 69 | 372,764 |
| B07 | 3.25 | 119.2 | 287 | 759.7 | 2770 | 373,109 | 0 | 70 | 373,109 |
| B08 | 1 | 97.15 | 238 | 679.2 | 2815 | 373,004 | 0 | 70 | 373,004 |
| B8A | 3 | 85.03 | 232.4 | 665.8 | 2800 | 373,958 | 0 | 69 | 373,958 |
| B11 | 0 | 36.6 | 136.7 | 400 | 501.5 | 393,918 | 0 | 47 | 393,918 |
| B12 | 0 | 28.54 | 103.4 | 331.3 | 1123 | 376,284 | 0 | 52 | 376,284 |

Center vs 250 m-buffer-mean correlation per band (are the two aggregations interchangeable?):

| index | pearson_r |
|---|---|
| B01 | 0.6818 |
| B02 | 0.406 |
| B03 | 0.3611 |
| B04 | 0.3525 |
| B05 | 0.4139 |
| B06 | 0.3635 |
| B07 | 0.4017 |
| B08 | 0.3276 |
| B8A | 0.4026 |
| B11 | 0.3771 |
| B12 | 0.3715 |

## Target value distributions (per parameter)


### `32295` — Dissolved organic matter fluorescence (fDOM), water, in situ, concentration estimated from reference material, micrograms per liter as quinine sulfate equivalents (QSE) [ug/l QSE]

| index | value |
|---|---|
| count | 7.452e+04 |
| mean | 20.97 |
| std | 17.54 |
| min | 0 |
| 1% | 1.52 |
| 5% | 2.99 |
| 25% | 5.22 |
| 50% | 12.11 |
| 75% | 35.54 |
| 95% | 52.69 |
| 99% | 66.02 |
| max | 77.5 |
| missing | 0 |
| <= 0 | 61 |

### `32315` — Chlorophyll relative fluorescence (fChl), water, in situ, relative fluorescence units (RFU) [RFU]

| index | value |
|---|---|
| count | 1.016e+05 |
| mean | 2.715 |
| std | 6.641 |
| min | -0.03 |
| 1% | 0.05 |
| 5% | 0.15 |
| 25% | 0.44 |
| 50% | 0.81 |
| 75% | 1.92 |
| 95% | 11.3 |
| 99% | 37.7 |
| max | 156.3 |
| missing | 0 |
| <= 0 | 256 |

### `32316` — Chlorophyll fluorescence (fChl), water, in situ, concentration estimated from reference material, micrograms per liter as chlorophyll [ug/l]

| index | value |
|---|---|
| count | 2.361e+05 |
| mean | 14.53 |
| std | 17.12 |
| min | -2.4 |
| 1% | 0.1 |
| 5% | 0.48 |
| 25% | 3.9 |
| 50% | 9.3 |
| 75% | 20.3 |
| 95% | 43.7 |
| 99% | 70.5 |
| max | 638.6 |
| missing | 0 |
| <= 0 | 1043 |

### `32318` — Chlorophylls, water, in situ, fluorometric method, excitation at 470 +-15 nm, emission at 685 +-20 nm, micrograms per liter [ug/l]

| index | value |
|---|---|
| count | 8247 |
| mean | 1.829 |
| std | 2.408 |
| min | -0.1 |
| 1% | 0 |
| 5% | 0.2 |
| 25% | 0.6 |
| 50% | 1.2 |
| 75% | 2.3 |
| 95% | 4.7 |
| 99% | 11 |
| max | 54.2 |
| missing | 0 |
| <= 0 | 93 |

### `32320` — Chlorophyll fluorescence (fChl), water, in situ, fluorometric method, excitation at 470 +-15 nm, emission at 685 +-20 nm, relative fluorescence units (RFU) [RFU]

| index | value |
|---|---|
| count | 9419 |
| mean | 1.261 |
| std | 0.7799 |
| min | 0.2 |
| 1% | 0.3 |
| 5% | 0.5 |
| 25% | 0.8 |
| 50% | 1 |
| 75% | 1.5 |
| 95% | 2.8 |
| 99% | 4.1 |
| max | 8.7 |
| missing | 0 |
| <= 0 | 0 |

### `32322` — Dissolved organic matter relative fluorescence (fDOM), water, in situ, relative fluorescence units (RFU) [RFU]

| index | value |
|---|---|
| count | 2.577e+04 |
| mean | 12.02 |
| std | 3.163 |
| min | 4.69 |
| 1% | 5.4 |
| 5% | 7.26 |
| 25% | 9.9 |
| 50% | 11.62 |
| 75% | 13.61 |
| 95% | 18.1 |
| 99% | 22.52 |
| max | 23.42 |
| missing | 0 |
| <= 0 | 0 |

### `62361` — Chlorophyll, total, water, fluorometric, 650-700 nanometers, in situ sensor, micrograms per liter [ug/l]

| index | value |
|---|---|
| count | 1.336e+04 |
| mean | 1.486 |
| std | 1.284 |
| min | -0 |
| 1% | 0.1 |
| 5% | 0.2 |
| 25% | 0.7 |
| 50% | 1.1 |
| 75% | 1.9 |
| 95% | 4 |
| 99% | 6.2 |
| max | 25 |
| missing | 0 |
| <= 0 | 78 |

### `63680` — Turbidity, water, unfiltered, monochrome near infra-red LED light, 780-900 nm, detection angle 90 +-2.5 degrees, formazin nephelometric units (FNU) [FNU]

| index | value |
|---|---|
| count | 9.595e+05 |
| mean | 31.52 |
| std | 130.2 |
| min | 0 |
| 1% | 0.4 |
| 5% | 1 |
| 25% | 4.1 |
| 50% | 11.3 |
| 75% | 27.4 |
| 95% | 95 |
| 99% | 315 |
| max | 4000 |
| missing | 0 |
| <= 0 | 519 |

### `80297` — Suspended sediment load, water, unfiltered, computed, the product of regression-computed suspended sediment concentration and streamflow, short tons per day [tons/day]

| index | value |
|---|---|
| count | 1.309e+05 |
| mean | 346.6 |
| std | 832.7 |
| min | -1000 |
| 1% | -329 |
| 5% | -98.8 |
| 25% | 16.8 |
| 50% | 106 |
| 75% | 265 |
| 95% | 1950 |
| 99% | 4170 |
| max | 8150 |
| missing | 0 |
| <= 0 | 1.771e+04 |

### `99246` — Upper 90 percent prediction limit for SSC by regression (PCODE 99409), milligrams per liter [mg/l]

| index | value |
|---|---|
| count | 9.492e+04 |
| mean | 6.382 |
| std | 8.119 |
| min | 0.5 |
| 1% | 0.5 |
| 5% | 0.6 |
| 25% | 0.8 |
| 50% | 5.1 |
| 75% | 8.6 |
| 95% | 21.3 |
| 99% | 37 |
| max | 82.2 |
| missing | 0 |
| <= 0 | 0 |

### `99409` — Suspended sediment concentration, water, unfiltered, estimated by regression equation, milligrams per liter [mg/l]

| index | value |
|---|---|
| count | 9.406e+04 |
| mean | 3.629 |
| std | 4.931 |
| min | 0.1 |
| 1% | 0.2 |
| 5% | 0.3 |
| 25% | 0.5 |
| 50% | 2.7 |
| 75% | 4.7 |
| 95% | 12.8 |
| 99% | 23 |
| max | 54.7 |
| missing | 0 |
| <= 0 | 0 |

## First 3 rows (selected columns)

```
                                                                                                                                                                       0                                                                                                                                                    1                                                                                                                                                    2
scene                                                                                                       S2B_MSIAQR_20180523T153819_N0206_R011_T18SWJ_20180523T205444                                                                                         S2B_MSIAQR_20180523T153819_N0206_R011_T18SWJ_20180523T205444                                                                                         S2B_MSIAQR_20180523T153819_N0206_R011_T18SWJ_20180523T205444
source                                                                                                                                                              NWIS                                                                                                                                                 NWIS                                                                                                                                                 NWIS
Organization                                                                                                                                                   USGS-NWIS                                                                                                                                            USGS-NWIS                                                                                                                                            USGS-NWIS
scene_datetime_UTC                                                                                                                             2018-05-23 15:38:19+00:00                                                                                                                            2018-05-23 15:38:19+00:00                                                                                                                            2018-05-23 15:38:19+00:00
sample_datetime_UTC                                                                                                                            2018-05-23 03:42:00+00:00                                                                                                                            2018-05-23 03:48:00+00:00                                                                                                                            2018-05-23 03:54:00+00:00
site_no                                                                                                                                                        140928320                                                                                                                                            140928320                                                                                                                                            140928320
station_nm                                                                                                            Westecunk Crk 3700 ft US of mouth nr West Creek NJ                                                                                                   Westecunk Crk 3700 ft US of mouth nr West Creek NJ                                                                                                   Westecunk Crk 3700 ft US of mouth nr West Creek NJ
parm_cd                                                                                                                                                            63680                                                                                                                                                63680                                                                                                                                                63680
parm_nm              Turbidity, water, unfiltered, monochrome near infra-red LED light, 780-900 nm, detection angle 90 +-2.5 degrees, formazin nephelometric units (FNU)  Turbidity, water, unfiltered, monochrome near infra-red LED light, 780-900 nm, detection angle 90 +-2.5 degrees, formazin nephelometric units (FNU)  Turbidity, water, unfiltered, monochrome near infra-red LED light, 780-900 nm, detection angle 90 +-2.5 degrees, formazin nephelometric units (FNU)
parm_unit                                                                                                                                                            FNU                                                                                                                                                  FNU                                                                                                                                                  FNU
Lat                                                                                                                                                            39.620528                                                                                                                                            39.620528                                                                                                                                            39.620528
Long                                                                                                                                                          -74.273686                                                                                                                                           -74.273686                                                                                                                                           -74.273686
MeasurementValue                                                                                                                                                     6.9                                                                                                                                                  6.7                                                                                                                                                  6.5
MeasurementCd                                                                                                                                                          A                                                                                                                                                    A                                                                                                                                                    A
site_tp_cd                                                                                                                                                            ST                                                                                                                                                   ST                                                                                                                                                   ST
huc4                                                                                                                                                               204.0                                                                                                                                                204.0                                                                                                                                                204.0
nhd_feature_type                                                                                                                                                Flowline                                                                                                                                             Flowline                                                                                                                                             Flowline
n_l2flag                                                                                                                                                             0.0                                                                                                                                                  0.0                                                                                                                                                  0.0
l2flag_center                                                                                                                                                        0.0                                                                                                                                                  0.0                                                                                                                                                  0.0
n_nhd                                                                                                                                                               62.0                                                                                                                                                 62.0                                                                                                                                                 62.0
n_buf                                                                                                                                                              489.0                                                                                                                                                489.0                                                                                                                                                489.0
n_mask                                                                                                                                                               0.0                                                                                                                                                  0.0                                                                                                                                                  0.0
truncated                                                                                                                                                            0.0                                                                                                                                                  0.0                                                                                                                                                  0.0
```
