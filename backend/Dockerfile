# HydroSentinel API. Build context is the repository ROOT, not backend/:
#   docker build -f backend/Dockerfile -t hydrosentinel-api .
#   docker run -p 8000:8000 --env-file backend/.env hydrosentinel-api
#
# rasterio bundles its own GDAL, but that GDAL still links a few system libraries which
# python:3.11-slim does not ship. libexpat1 is the one it needs. Without it every raster read fails
# with "libexpat.so.1: cannot open shared object file", and because each scene is caught per-scene
# that surfaces as "no usable recent scene" at every location — the live mode looks like bad weather
# rather than a broken image. Found only by calling the deployed API; see docs/DEPLOY.md.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends libexpat1 \
 && rm -rf /var/lib/apt/lists/*

# Dependencies first so code edits do not invalidate the (slow) install layer.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Fail the build, not the demo, if GDAL cannot initialise. A missing system library shows up here
# as a build error instead of as an empty dashboard hours later.
COPY backend/scripts/check_gdal.py backend/scripts/check_gdal.py
RUN python backend/scripts/check_gdal.py

COPY backend/app backend/app
COPY backend/hydrosentinel backend/hydrosentinel
COPY models models
COPY data/processed data/processed

# Live extractions are cached here. On a free-tier host the filesystem is ephemeral, so the cache
# is rebuilt after each spin-down — correctness is unaffected, only the first request is slow.
RUN mkdir -p /app/data/live_cache

WORKDIR /app/backend
ENV HS_MODELS_DIR=/app/models     HS_DATA_DIR=/app/data/processed     HS_LIVE_CACHE=/app/data/live_cache     PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3   CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",8000)}/health').read()"

# Single worker: each one loads its own copy of the models (~300 MB resident).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
