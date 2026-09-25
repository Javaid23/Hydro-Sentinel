"""
Inspect the raw USGS Sentinel-2 / water-quality matchup CSVs (Matched_WQ_S2_*.csv).

Run BEFORE writing any preprocessing. The release is LONG format: one row per
(Sentinel-2 scene × site × water-quality parameter), with the measured value in
`MeasurementValue` and the constituent identified by `parm_cd` / `parm_nm`.
Reflectance for bands B01–B08, B8A, B11, B12 is repeated on every row.

Reports (to docs/data_inspection.md):
  - exact column list and dtypes (from a small sample read)
  - row counts per file, per parameter, per basin (huc4), per site
  - which parameters are turbidity / chlorophyll-a / CDOM(fDOM), with units
  - date range of scenes and samples, scene-vs-sample time offsets
  - reflectance band value ranges and validity (n_pixels, l2flag, truncated)
  - measurement approval codes (MeasurementCd)

Only the needed columns are loaded (pyarrow engine) so the 1.4 GB pair fits in memory.

Usage:
    python backend/scripts/inspect_data.py [--raw-dir data/raw] [--out docs/data_inspection.md]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 100)

BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"]
BAND_STATS = ["n_pixels", "center", "buf250_mean", "buf250_std", "buf250_med"]

META_COLS = [
    "scene", "source", "Organization", "scene_datetime_UTC", "sample_datetime_UTC",
    "site_no", "station_nm", "parm_cd", "parm_nm", "parm_unit", "Lat", "Long",
    "MeasurementValue", "MeasurementCd", "site_tp_cd", "huc4", "nhd_feature_type",
    "n_l2flag", "l2flag_center", "n_nhd", "n_buf", "n_mask", "truncated",
]
BAND_COLS = [f"{b}_{s}" for b in BANDS for s in BAND_STATS]

# HUC4 → basin name, from the release title. 1204 (San Jacinto / Galveston Bay) holds the
# Lake Houston + Lynchburg Reservoir sites, which USGS groups with the Trinity basin
# (Lynchburg receives Trinity River water via the Coastal Water Authority canal).
HUC4_BASIN = {
    204: "Delaware", 712: "Illinois", 713: "Illinois", 1203: "Trinity", 1204: "Trinity",
    1401: "Upper Colorado", 1402: "Upper Colorado", 1709: "Willamette",
}


def md_table(df: pd.DataFrame, index: bool = True, floatfmt: str = ".4g") -> str:
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else format(v, floatfmt))
        elif pd.api.types.is_integer_dtype(d[c]):
            d[c] = d[c].map(lambda v: f"{v:,}")
    if index:
        d = d.reset_index()
    cols = [str(c) for c in d.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, row in d.iterrows():
        out.append("| " + " | ".join(str(v).replace("|", "\\|") for v in row.values) + " |")
    return "\n".join(out) + "\n"


def load(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for p in paths:
        t0 = time.time()
        df = pd.read_csv(
            p, usecols=META_COLS + BAND_COLS, engine="pyarrow",
            na_values=["NULL", "BLANK", ""],
        )
        df["__file"] = p.name
        print(f"  {p.name}: {len(df):,} rows in {time.time() - t0:.0f}s")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    root = Path(__file__).resolve().parents[2]
    ap.add_argument("--raw-dir", type=Path, default=root / "data" / "raw")
    ap.add_argument("--out", type=Path, default=root / "docs" / "data_inspection.md")
    args = ap.parse_args()

    paths = sorted(args.raw_dir.rglob("Matched_WQ_S2*.csv"))
    if not paths:
        print(f"No Matched_WQ_S2*.csv under {args.raw_dir}. See the Data section of README.md.")
        return 1

    # Exact header from the first file, without loading it
    header = pd.read_csv(paths[0], nrows=0).columns.tolist()
    sample = pd.read_csv(paths[0], nrows=2000, na_values=["NULL", "BLANK", ""])

    print("Loading CSVs (selected columns only) ...")
    df = load(paths)
    L: list[str] = []
    w = L.append

    w("# Raw data inspection report\n")
    w(f"Source: `{args.raw_dir.as_posix()}` — files: " + ", ".join(f"`{p.name}`" for p in paths) + "\n")
    w(f"\nTotal rows (all files): **{len(df):,}** — layout is LONG: one row per scene × site × parameter.\n")
    w("\n## Rows per file\n\n" + md_table(df["__file"].value_counts().rename("rows").to_frame()))

    # ---------------------------------------------------------------- columns
    w(f"\n## Exact columns ({len(header)})\n\n")
    w("| # | column | dtype (sample) | example |\n|---|---|---|---|\n")
    for i, c in enumerate(header):
        s = sample[c]
        ex = str(s.dropna().iloc[0])[:50].replace("|", "\\|") if s.notna().any() else ""
        w(f"| {i} | `{c}` | {s.dtype} | {ex} |\n")

    # ---------------------------------------------------------------- parameters
    w("\n## Water-quality parameters present (`parm_cd`)\n\n")
    parm = (
        df.groupby(["parm_cd", "parm_nm", "parm_unit"], dropna=False)
        .agg(rows=("MeasurementValue", "size"), sites=("site_no", "nunique"),
             value_min=("MeasurementValue", "min"), value_med=("MeasurementValue", "median"),
             value_max=("MeasurementValue", "max"))
        .sort_values("rows", ascending=False)
    )
    w(md_table(parm))

    # ---------------------------------------------------------------- basins
    df["basin"] = df["huc4"].map(HUC4_BASIN).fillna("UNMAPPED huc4=" + df["huc4"].astype(str))
    w("\n## Rows per basin (`huc4`)\n\n")
    basin = (
        df.groupby(["huc4", "basin"])
        .agg(rows=("site_no", "size"), sites=("site_no", "nunique"), scenes=("scene", "nunique"))
        .sort_values("rows", ascending=False)
    )
    w(md_table(basin))
    unmapped = df.loc[~df["huc4"].isin(HUC4_BASIN), "huc4"].dropna().unique()
    if len(unmapped):
        w(f"\n**Unmapped huc4 codes:** {sorted(unmapped.tolist())} — extend `HUC4_BASIN`.\n")

    # rows per basin × parameter
    w("\n## Rows per basin × parameter\n\n")
    bp = df.pivot_table(index="basin", columns="parm_cd", values="site_no", aggfunc="size", fill_value=0)
    w(md_table(bp))

    # ---------------------------------------------------------------- sites
    w("\n## Sites\n\n")
    sites = (
        df.groupby(["site_no", "station_nm", "basin"])
        .agg(rows=("scene", "size"), scenes=("scene", "nunique"), params=("parm_cd", "nunique"),
             first=("sample_datetime_UTC", "min"), last=("sample_datetime_UTC", "max"))
        .sort_values("rows", ascending=False)
    )
    w(f"Distinct sites: **{len(sites)}**\n\n")
    w(md_table(sites))

    # sites × parameter: unique scenes (≈ usable observations per site per target)
    w("\n## Unique scenes per site × parameter (candidate observation counts)\n\n")
    sp = df.pivot_table(index=["basin", "site_no"], columns="parm_cd", values="scene",
                        aggfunc="nunique", fill_value=0)
    w(md_table(sp))
    w("\nSites with ≥30 scenes for a parameter (LSTM eligibility per spec Section 3):\n\n")
    w(md_table((sp >= 30).sum().rename("sites_ge_30").to_frame()))

    # ---------------------------------------------------------------- time
    w("\n## Time coverage\n\n")
    sc = pd.to_datetime(df["scene_datetime_UTC"], errors="coerce", utc=True)
    sm = pd.to_datetime(df["sample_datetime_UTC"], errors="coerce", utc=True)
    w(f"- scene_datetime_UTC: {sc.min()} → {sc.max()} (unparsed: {sc.isna().sum():,})\n")
    w(f"- sample_datetime_UTC: {sm.min()} → {sm.max()} (unparsed: {sm.isna().sum():,})\n")
    off_h = (sm - sc).dt.total_seconds() / 3600
    w("- sample − scene offset (hours): " +
      ", ".join(f"p{int(q*100)}={off_h.quantile(q):.1f}" for q in (0, .05, .25, .5, .75, .95, 1)) + "\n")
    w(f"- |offset| ≤ 3h: {(off_h.abs() <= 3).mean():.1%}, ≤ 12h: {(off_h.abs() <= 12).mean():.1%}, "
      f"≤ 24h: {(off_h.abs() <= 24).mean():.1%}\n")
    w("\n### Scenes per year\n\n" + md_table(sc.dt.year.value_counts().sort_index().rename("rows").to_frame()))
    w("\n### Duplicate (scene, site, parm_cd) rows — multiple samples matched to one overpass\n\n")
    dup = df.duplicated(subset=["scene", "site_no", "parm_cd"], keep=False)
    w(f"{dup.sum():,} rows ({dup.mean():.1%}) share a scene/site/parameter with another row.\n")

    # ---------------------------------------------------------------- QA columns
    w("\n## Measurement approval (`MeasurementCd`)\n\n")
    w(md_table(df["MeasurementCd"].value_counts(dropna=False).rename("rows").to_frame()))
    w("\n## Categorical metadata\n\n")
    for c in ["source", "Organization", "site_tp_cd", "nhd_feature_type", "truncated", "l2flag_center"]:
        w(f"\n`{c}`:\n\n" + md_table(df[c].value_counts(dropna=False).head(15).rename("rows").to_frame()))
    w("\n## Pixel-count / mask columns\n\n")
    w(md_table(df[["n_l2flag", "n_nhd", "n_buf", "n_mask"]].describe(percentiles=[.05, .25, .5, .75, .95]).T))

    # ---------------------------------------------------------------- bands
    w("\n## Reflectance bands\n\n")
    rows = []
    for b in BANDS:
        c = df[f"{b}_buf250_mean"]
        npx = df[f"{b}_n_pixels"]
        rows.append({
            "band": b, "mean_min": c.min(), "mean_p05": c.quantile(.05), "mean_p50": c.median(),
            "mean_p95": c.quantile(.95), "mean_max": c.max(), "missing": int(c.isna().sum()),
            "neg": int((c < 0).sum()), "n_pixels_p50": npx.median(), "n_pixels_0": int((npx == 0).sum()),
        })
    w(md_table(pd.DataFrame(rows).set_index("band")))
    w("\nCenter vs 250 m-buffer-mean correlation per band (are the two aggregations interchangeable?):\n\n")
    corr = {b: df[f"{b}_center"].corr(df[f"{b}_buf250_mean"]) for b in BANDS}
    w(md_table(pd.Series(corr, name="pearson_r").to_frame()))

    # ---------------------------------------------------------------- targets
    w("\n## Target value distributions (per parameter)\n\n")
    for (pc, pn, pu), g in df.groupby(["parm_cd", "parm_nm", "parm_unit"], dropna=False):
        v = pd.to_numeric(g["MeasurementValue"], errors="coerce")
        w(f"\n### `{pc}` — {pn} [{pu}]\n\n")
        d = v.describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).to_frame("value")
        d.loc["missing"] = v.isna().sum()
        d.loc["<= 0"] = (v <= 0).sum()
        w(md_table(d))

    # ---------------------------------------------------------------- head
    w("\n## First 3 rows (selected columns)\n\n```\n")
    w(df[META_COLS].head(3).T.to_string())
    w("\n```\n")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(L), encoding="utf-8")
    print(f"\nReport written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
