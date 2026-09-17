# Data sources

## Primary training data (P0)

**USGS data release:** *Aquatic reflectance data from Sentinel-2 satellite imagery paired with
continuous water quality measurements across the Delaware, Illinois, Trinity, Upper Colorado, and
Willamette River basins in the United States from July 2015 through September 2024.*
Ball, G.P., and Ducar, S.D., 2025. USGS Idaho Water Science Center. CC0.

- DOI: https://doi.org/10.5066/P1A7T4FV
- ScienceBase item: https://www.sciencebase.gov/catalog/item/664bab7ad34e1955f5a47754
- Landing page: https://www.usgs.gov/data/aquatic-reflectance-data-sentinel-2-satellite-imagery-paired-continuous-water-quality

Files in the release:

| File | Contents |
|---|---|
| `Matched_WQ_S2.zip` | Two CSVs: continuous CDOM, chlorophyll-a and turbidity measurements matched in space and time to Sentinel-2 aquatic-reflectance pixel values (bands 1–8A, 11, 12) |
| `Aquatic_Reflectance_Extraction_Scripts.zip` | Python scripts USGS used to build the matchups (reference only) |

### How to obtain

ScienceBase sits behind a browser bot-check, so download manually:

1. Open the ScienceBase item link above in a browser.
2. Download `Matched_WQ_S2.zip` (and optionally the scripts zip).
3. Unzip into `data/raw/` so the CSVs sit directly at `data/raw/*.csv`.
4. Run the inspection script: `python backend/scripts/inspect_data.py`

`data/raw/` is git-ignored; nothing in the release is modified in place.

## Supplementary (P1, only if schema-compatible)

USGS Sentinel-2 + discrete chlorophyll-a dataset covering Oregon, Ohio and Florida (published Feb 2026).
Used only to add geographic diversity to LOBO evaluation if columns line up with the primary release.

## Live / demo only — never training

USGS Sentinel-2 ACOLITE-DSF Aquatic Reflectance for CONUS (COG rasters, no water-quality labels).
- https://registry.opendata.aws/usgs_aqr/
Used only by the Regional Demonstration Mode (spec Section 18) for on-the-fly band extraction.
