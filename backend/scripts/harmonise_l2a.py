"""
Empirical harmonisation of Sentinel-2 L2A (Sen2Cor) to USGS ACOLITE-DSF aquatic reflectance.

The regional demonstration mode outside the US has to use L2A surface reflectance, but the models
were trained on ACOLITE aquatic reflectance. Over water the two differ systematically. This script
measures the per-band ratio L2A / AQR at training sites on days where BOTH products have a usable
scene, and writes the median ratio and its spread to models/harmonisation_l2a.json. live_global.py
divides L2A band means by these factors before scoring, and the API reports the spread so the
extra uncertainty is visible rather than hidden.

This is a stop-gap for a demonstration mode, not a validated cross-calibration: n is small, the
sites are all US rivers, and the ratio is expected to vary with water type, aerosol and glint.

Usage:
    python backend/scripts/harmonise_l2a.py [--days 120] [--max-pairs-per-site 4]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hydrosentinel import config as C  # noqa: E402
from hydrosentinel import live  # noqa: E402
from hydrosentinel import live_global as G

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("harmonise")

# One well-observed site per basin (site_no → name); coordinates come from the model metadata.
SITES = {
    "14211720": "Willamette River at Portland, OR",
    "1463500": "Delaware River at Trenton, NJ",
    "5586300": "Illinois River at Florence, IL",
    "295826095082200": "Lake Houston nr Houston, TX",
    "9163500": "Colorado River nr Colorado-Utah state line",
}


def site_coords() -> dict[str, tuple[float, float]]:
    meta = json.loads((C.MODELS_DIR / "turbidity" / "metadata.json").read_text(encoding="utf-8"))
    return {s: tuple(meta["site_coords"][s]) for s in SITES if s in meta["site_coords"]}


def pairs_for_site(site: str, lat: float, lon: float, days: int, max_pairs: int) -> list[dict]:
    tile = live.mgrs_tile(lat, lon)
    now = datetime.now(UTC)
    aqr = {s.datetime_utc.strftime("%Y%m%d"): s for s in live.list_scenes(tile, now.year)
           if s.datetime_utc >= now - timedelta(days=days)}
    l2a = {s.datetime_utc.strftime("%Y%m%d"): s for s in G.stac_search(lat, lon, days=days, max_cloud=80, limit=60)
           if s.tile == tile}
    common = sorted(set(aqr) & set(l2a), reverse=True)
    log.info("%s (%s): %d AQR, %d L2A scenes, %d same-day pairs", SITES[site], tile, len(aqr), len(l2a), len(common))
    out = []
    for day in common:
        try:
            a = live.extract_observation(aqr[day], lat, lon)
            b = G.extract_observation(l2a[day], lat, lon)
        except Exception as exc:  # noqa: BLE001
            log.info("  %s: extraction failed (%s)", day, exc)
            continue
        ok_a, why_a = live.passes_quality(a)
        ok_b, why_b = live.passes_quality(b)
        if not (ok_a and ok_b):
            log.info("  %s: skipped (AQR %s / L2A %s)", day, why_a, why_b)
            continue
        ratios = {band: b[f"{band}_buf250_mean"] / a[f"{band}_buf250_mean"] for band in C.BANDS
                  if a[f"{band}_buf250_mean"] > 0}
        out.append({"site_no": site, "site": SITES[site], "date": day, "aqr_scene": aqr[day].scene_id,
                    "l2a_scene": l2a[day].scene_id, "n_mask_aqr": a["n_mask"], "n_mask_l2a": b["n_mask"],
                    "aqr": {band: round(a[f"{band}_buf250_mean"], 1) for band in C.BANDS},
                    "l2a": {band: round(b[f"{band}_buf250_mean"], 1) for band in C.BANDS},
                    "ratio": {k: round(v, 3) for k, v in ratios.items()}})
        log.info("  %s: pair ok — red ratio %.2f, NIR ratio %.2f", day, ratios.get("B04", np.nan), ratios.get("B08", np.nan))
        if len(out) >= max_pairs:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--max-pairs-per-site", type=int, default=4)
    ap.add_argument("--out", type=Path, default=C.MODELS_DIR / "harmonisation_l2a.json")
    args = ap.parse_args()

    pairs: list[dict] = []
    for site, (lat, lon) in site_coords().items():
        pairs += pairs_for_site(site, lat, lon, args.days, args.max_pairs_per_site)

    if len(pairs) < 3:
        log.error("only %d pairs — not enough to harmonise", len(pairs))
        return 1
    factors, spread = {}, {}
    for band in C.BANDS:
        r = np.array([p["ratio"][band] for p in pairs if band in p["ratio"]])
        factors[band] = round(float(np.median(r)), 3)
        q1, q3 = np.percentile(r, [25, 75])
        spread[band] = {"iqr_low": round(float(q1), 3), "iqr_high": round(float(q3), 3),
                        "min": round(float(r.min()), 3), "max": round(float(r.max()), 3), "n": int(len(r))}
    result = {
        "method": "median per-band ratio L2A(Sen2Cor, Earth Search) / USGS ACOLITE-DSF AQR over the same 250 m water "
                  "buffer on the same day; live_global divides L2A band means by these factors before scoring",
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_pairs": len(pairs), "n_sites": len({p["site_no"] for p in pairs}),
        "factors": factors, "spread": spread, "pairs": pairs,
    }
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    log.info("wrote %s (%d pairs, %d sites)", args.out, len(pairs), result["n_sites"])
    print("\nband  factor   IQR")
    for band in C.BANDS:
        sp = spread[band]
        print(f"{band:5s} {factors[band]:6.2f}   {sp['iqr_low']:.2f}–{sp['iqr_high']:.2f}  (n={sp['n']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
