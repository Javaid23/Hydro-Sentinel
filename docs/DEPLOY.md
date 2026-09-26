# Deployment

Backend to **Render** (Docker, free tier), frontend to **Vercel** (free tier). Both deploy from
the GitHub repository; nothing needs to be uploaded by hand because the trained artifacts
(`models/`, ~2 MB) and processed data (`data/processed/`, ~3 MB) are committed.

Budget 20–30 minutes end to end, most of it waiting for the first Docker build.

---

## 1. Backend → Render

1. **New → Web Service**, connect the GitHub repo, pick branch `main`.
2. Render reads [`render.yaml`](../render.yaml) and pre-fills: runtime **Docker**, dockerfile
   `./backend/Dockerfile`, context `.`, plan **Free**, health check `/health`.
   If it doesn't, set those four by hand — note the build context is the repository root, not
   `backend/`.
3. Add the secret under **Environment**:

   | Key | Value |
   |---|---|
   | `GROQ_API_KEY` | your key — never commit it |
   | `GROQ_MODEL` | `openai/gpt-oss-120b` (already in `render.yaml`) |
   | `HS_CORS_ORIGINS` | the Vercel URL from step 2, plus `http://localhost:5173` |

4. Deploy. The first build takes ~5–10 minutes (rasterio, xgboost and shap are large wheels).
5. Verify:

   ```bash
   curl https://<your-service>.onrender.com/health
   # {"status":"ok","model_version":"...","n_sites":49,"n_observations":6661}
   ```

## 2. Frontend → Vercel

1. **Add New → Project**, import the repo.
2. Set **Root Directory** to `frontend` (otherwise Vercel builds the repository root and fails).
   Framework preset: Vite. Build command and output directory come from
   [`frontend/vercel.json`](../frontend/vercel.json).
3. Environment variable:

   | Key | Value |
   |---|---|
   | `VITE_API_URL` | `https://<your-service>.onrender.com` — no trailing slash |

4. Deploy, then go back to Render and put the Vercel URL into `HS_CORS_ORIGINS`. The browser
   blocks the API call without it, and the error looks like a dead backend rather than a CORS
   problem — check this first if the deployed dashboard shows "Cannot reach the API".

---

## What to expect on the free tier

| | Behaviour |
|---|---|
| **Cold start** | The service spins down after ~15 minutes idle. The next request waits 30–60 s while the container starts and loads the models. Hit `/health` before any demo. |
| **Memory** | Measured 324 MB peak locally against Render's 512 MB limit. One uvicorn worker only — each worker loads its own copy of the models. |
| **Live extraction** | 20–60 s for a location that isn't cached, longer on a poor connection. Results are cached to disk, but the free-tier filesystem is ephemeral, so the cache empties on each spin-down. |
| **Warming the deployed cache** | Request the demo locations once after a deploy: `curl "https://<service>/live/coords?lat=31.6083&lon=74.2959"` for each preset, or check `GET /live/cache` to see what's already there. |

## Troubleshooting

**Build fails on the `COPY models models` line** — the build context is wrong. It must be the
repository root (`dockerContext: .` in `render.yaml`), not `backend/`.

**`/health` returns 503 or the service restarts in a loop** — almost always memory. Confirm the
start command has `--workers 1`; a second worker doubles the ~300 MB model footprint and exceeds
the free tier.

**Dashboard says "Cannot reach the API"** — check `HS_CORS_ORIGINS` includes the exact Vercel
origin (scheme included, no trailing slash), then that `VITE_API_URL` on Vercel points at the
Render URL. Vercel bakes the variable in at build time, so change it *and redeploy*.

**Explanations say "GROQ_API_KEY not set"** — the key is missing on Render. Every numeric part of
the dashboard still works; only the prose panel is affected.

**Every live location says "no usable recent scene"** — if this happens at *every* site rather than
one, it is not weather. rasterio's bundled GDAL loads system libraries at runtime that
`python:3.11-slim` does not ship; when one is missing the import still succeeds and only the reads
fail, and because each scene is caught individually the API reports it as cloud cover. The image
installs `libexpat1` for this reason, and `backend/scripts/check_gdal.py` runs during the build so a
missing library fails the build instead. If it recurs, read the full 503 detail — it carries the
per-scene reason, which names the missing library.

**First live request times out** — the imagery archives are public but occasionally slow. The
dashboard shows a Retry button for this case; the request is also cached once it succeeds.

## Alternative: run the container locally

```bash
docker build -f backend/Dockerfile -t hydrosentinel-api .
docker run -p 8000:8000 --env-file backend/.env hydrosentinel-api
```

Useful for reproducing a Render build failure without waiting on their queue.
