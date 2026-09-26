"""Fail the Docker build, rather than the demo, if GDAL cannot actually read a raster.

rasterio ships a bundled GDAL, but that GDAL still loads system libraries at runtime. When one is
missing the import still succeeds and only the *reads* fail, deep inside the per-scene try/except
in `live.latest_usable`. The API then reports "no usable recent scene at this location", which
reads as cloud cover rather than a broken image, and the live mode looks like bad weather
everywhere on earth. That shipped to Render once (missing `libexpat1`).

This runs during the image build, so a missing library is a red build instead of a silent hole in
the demo hours later.

    python backend/scripts/check_gdal.py
"""

from __future__ import annotations

import sys


def main() -> int:
    import numpy as np
    import rasterio
    from rasterio.crs import CRS
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    # PROJ has to open its database to resolve an EPSG code.
    if CRS.from_epsg(4326).to_epsg() != 4326:
        print("FAIL: PROJ could not resolve EPSG:4326", file=sys.stderr)
        return 1

    # Exercise driver registration plus a real write and read-back.
    with MemoryFile() as memfile:
        with memfile.open(driver="GTiff", height=4, width=4, count=1, dtype="uint16",
                          crs="EPSG:4326", transform=from_origin(74.29, 31.61, 1e-4, 1e-4)) as dst:
            dst.write(np.ones((4, 4), dtype="uint16"), 1)
        with memfile.open() as src:
            total = int(src.read(1).sum())
    if total != 16:
        print(f"FAIL: raster read returned {total}, expected 16", file=sys.stderr)
        return 1

    print(f"GDAL ok: rasterio {rasterio.__version__}, GDAL {rasterio.__gdal_version__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
