"""
Pre-fetch live satellite observations for the demo locations so the dashboard responds instantly.

Live extraction is network-bound (a scene listing plus 13 windowed COG reads): 20-60 s on a good
connection, minutes on a bad one. A scene's pixels never change, so the result is cached to disk
(hydrosentinel/livecache.py) and reused. Run this before recording a demo or presenting.

    python backend/scripts/warm_live_cache.py                 # the dashboard presets + top US sites
    python backend/scripts/warm_live_cache.py --force         # refetch even if a fresh entry exists
    python backend/scripts/warm_live_cache.py --list          # show what is cached, fetch nothing
    python backend/scripts/warm_live_cache.py --coords 31.6083 74.2959 --name "Ravi"

Failures are reported and skipped — a location with no cloud-free scene right now is not an error.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hydrosentinel import config as C  # noqa: E402
from hydrosentinel import live, live_global, livecache  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("warm")

# Mirrors the dashboard's Regional-demo presets (frontend/src/App.jsx). Keep the two in step.
PRESETS: list[tuple[str, float, float]] = [
    ("Ravi River at Ravi Road Bridge, Lahore", 31.6083, 74.2959),
    ("Chenab River at Head Marala", 32.6720, 74.4640),
    ("Kabul River at Nowshera", 34.0050, 71.9830),
    ("Sutlej River at Head Islam", 29.8290, 72.5480),
    ("Indus River at Sukkur Barrage", 27.6820, 68.8480),
    ("Indus River at Kotri Barrage", 25.4460, 68.3090),
    ("Ganges at Varanasi", 25.3050, 83.0200),
    ("Brahmaputra at Guwahati", 26.1900, 91.7400),
    ("Mekong at Phnom Penh", 11.5650, 104.9350),
    ("Nile at Luxor", 25.7000, 32.6400),
    ("Danube at Budapest", 47.4980, 19.0470),
    ("Rhine at Cologne", 50.9400, 6.9640),
    ("Thames at Gravesend", 51.4480, 0.3660),
    ("Mississippi River at St. Louis, MO", 38.6270, -90.1794),
]

# US monitoring sites worth warming for the Live tab (busiest, all three targets observed).
US_SITES = ["14211720", "14211010", "1463500", "5586300", "295826095082200"]


def site_coords() -> dict[str, tuple[str, float, float]]:
    meta = json.loads((C.MODELS_DIR / "turbidity" / "metadata.json").read_text(encoding="utf-8"))
    return {s: (meta["site_names"].get(s, s), *meta["site_coords"][s]) for s in US_SITES if s in meta["site_coords"]}


def warm(name: str, lat: float, lon: float, force: bool) -> dict:
    """Fetch and cache one location, preferring the USGS product where it has coverage."""
    t0 = time.time()
    for src in ("usgs", "global"):
        if not force:
            obs, _, stale = livecache.load(lat, lon, src)
            if obs is not None and not stale:
                return {"name": name, "status": "already fresh", "source": src,
                        "scene": obs.get("scene"), "seconds": 0.0}
    try:
        try:
            obs, tried = live.latest_usable(lat, lon)
            used = "usgs"
        except LookupError:            # outside the conterminous-US product
            obs, tried = live_global.latest_usable(lat, lon)
            used = "global"
        if obs is None:
            reasons = "; ".join(f"{t['date'][:10]} {t['reason'][:40]}" for t in (tried or [])[:3])
            return {"name": name, "status": "no usable scene", "detail": reasons, "seconds": round(time.time() - t0, 1)}
        livecache.save(lat, lon, used, obs, tried)
        return {"name": name, "status": "fetched", "source": used, "scene": obs.get("scene"),
                "scene_date": str(obs["scene_datetime_utc"])[:10], "n_mask": obs.get("n_mask"),
                "seconds": round(time.time() - t0, 1)}
    except Exception as exc:  # noqa: BLE001 — one bad location must not stop the warm-up
        return {"name": name, "status": "failed", "detail": f"{type(exc).__name__}: {exc}"[:120],
                "seconds": round(time.time() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="refetch even when a fresh entry exists")
    ap.add_argument("--list", action="store_true", help="show the cache and exit")
    ap.add_argument("--presets-only", action="store_true", help="skip the US monitoring sites")
    ap.add_argument("--coords", nargs=2, type=float, metavar=("LAT", "LON"), help="warm one location instead")
    ap.add_argument("--name", default="ad-hoc location")
    args = ap.parse_args()

    if args.list:
        rows = livecache.entries()
        print(f"{len(rows)} cached entries in {livecache.CACHE_DIR}\n")
        for e in rows:
            print(f"  {e['source']:6s} {e['lat']:>9.4f},{e['lon']:>9.4f}  scene {e['scene_datetime_utc'][:10]}  "
                  f"fetched {e['age_hours']:.1f} h ago")
        return 0

    targets = ([(args.name, *args.coords)] if args.coords
               else list(PRESETS) + ([] if args.presets_only else [(n, la, lo) for n, la, lo in site_coords().values()]))

    log.info("warming %d locations (cache: %s)", len(targets), livecache.CACHE_DIR)
    results = []
    for i, (name, lat, lon) in enumerate(targets, 1):
        log.info("[%d/%d] %s", i, len(targets), name)
        r = warm(name, lat, lon, args.force)
        results.append(r)
        log.info("      %s%s (%.0fs)", r["status"], f" — {r.get('scene_date') or r.get('detail', '')}" if r.get("scene_date") or r.get("detail") else "", r["seconds"])

    ok = [r for r in results if r["status"] in ("fetched", "already fresh")]
    print(f"\n{len(ok)}/{len(results)} locations ready")
    for r in results:
        if r["status"] not in ("fetched", "already fresh"):
            print(f"  NOT READY  {r['name']}: {r['status']} — {r.get('detail', '')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
