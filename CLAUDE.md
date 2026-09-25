# HydroSentinel — Project Specification for Claude Code

**Tagline:** Observe → Predict → Explain → Assess

**Context:** Built for the OneAquaHealth IEEE Global Hackathon 2026 (Sep 16–30). Primary track: Resilience Informatics. Secondary track: AI-Supported Assessment.

This file is the locked specification. Do not deviate from the boundaries below without flagging the change explicitly. Where the actual dataset schema forces a decision this file didn't anticipate, make the narrowest decision needed and note it — don't improvise broader architecture changes.

---

## 0. Build status

Everything under P0 and P1 (Section 21) is built, tested and documented. Start here:

| Question | Where |
|---|---|
| How does raw data become an assessment? | [docs/PIPELINE.md](docs/PIPELINE.md) — the end-to-end trace |
| Where did this deviate from the spec, and why? | [docs/decisions.md](docs/decisions.md) — D1 to D10, each with its evidence |
| Did the models actually work? | [docs/results/model_findings.md](docs/results/model_findings.md) |
| Is any of it fabricated? | `python backend/scripts/audit_provenance.py` — mechanical checks, run it |

**Ten decisions are recorded against this spec.** Three are worth knowing before reading further,
because they change what the code does relative to what is written below:

- **D4** — conformal prediction was implemented directly rather than via `mapie`, so calibration
  happens in the model's own log1p space (Section 8 still governs *what* is required).
- **D7** — the regional demonstration layer is no longer limited to the USGS conterminous-US
  product. Outside it, Copernicus Sentinel-2 L2A is used and harmonised to the training product by
  measured per-band factors. Section 18's labelling rules apply unchanged.
- **D8** — where no observed history exists, a reference can be built from that location's own
  satellite archive and reported as a **Local Anomaly Score**. It is never the Freshwater Stress
  Score of Section 6, never raises the confidence tier, and always states that its reference is
  model output rather than measurements.

Three capabilities were added that this spec did not anticipate. None relaxes a boundary:

- **Network overview** — every monitoring site scored on its latest observation, ranked and mapped.
  Uses the same models, references and leave-one-out rule as the single-site view; only SHAP is
  omitted, because a ranked list does not need per-observation attribution.
- **Out-of-distribution check** — Section 18 requires saying that inputs at an unseen site may fall
  outside the trained range. This measures it: each band is placed against the 1st–99th percentile
  of the training data, and the count outside is shown.
- **Live extraction cache** — a scene's pixels are immutable, so extractions are cached to disk and
  revalidated with a cheap scene listing. No effect on what is reported; the scene id and
  acquisition time are always shown.

---

## 1. Project Objective

HydroSentinel is a satellite-based, uncertainty-aware freshwater ecosystem assessment system.

It uses matched Sentinel-2 aquatic reflectance and ground-truth water-quality observations to estimate:

- Turbidity
- Chlorophyll-a
- CDOM

The system determines how unusual the current predicted condition is relative to historical observations, explains the prediction using SHAP, quantifies uncertainty, and provides a human-readable interpretation and recommended actions.

**The core claim is current-condition assessment, not future forecasting.**

Do not claim HydroSentinel provides a 7-day forecast unless a separate validated forecasting experiment is later developed and explicitly labeled as such.

---

## 2. Dataset

**Primary training data:** USGS matched Sentinel-2 aquatic reflectance + water quality dataset. Delaware, Illinois, Trinity, Upper Colorado, and Willamette River basins. July 2015–September 2024. CC0. DOI 10.5066/P1A7T4FV.

**Supplementary (if schema-compatible):** USGS Sentinel-2 + discrete chlorophyll-a dataset covering Oregon, Ohio, and Florida (published Feb 2026). Use for additional geographic diversity in leave-one-basin-out (LOBO) evaluation if column structure is compatible with the primary dataset.

**Live/demo data only, not training:** USGS's dynamically-updated Sentinel-2 ACOLITE-DSF aquatic reflectance product (conterminous US, raster COG tiles, no water-quality labels). Use only for the regional demonstration layer (Section 18), which requires on-the-fly band extraction at chosen coordinates, not a CSV load.

**Rule:** Do not assume column names beyond what's documented. Inspect the actual CSVs first (data inspection script) before writing the preprocessing pipeline. Report back: which file contains observations, exact column names, row counts per basin/site, available Sentinel-2 bands, exact names for turbidity/chlorophyll-a/CDOM columns.

---

## 3. Model Benchmark

XGBoost is the mandatory baseline. Compare:

1. **XGBoost** — mandatory, full implementation and validation
2. **LSTM** — only for sites with ≥30 chronologically ordered observations. If a site doesn't meet this, exclude it from LSTM training rather than forcing a sequence model on insufficient data.
3. **XGBoost + LSTM stacking** — only if both components are already working reliably.
4. **FT-Transformer or TabTransformer** — experimental benchmark, not a requirement for the final system.

Do not assume which model wins. Select empirically.

**Timebox: 2 days maximum for this entire benchmark stage.**
- XGBoost: full effort, no cap
- LSTM: half-day implementation attempt
- FT-Transformer/TabTransformer: half-day implementation attempt
- Stacking: only if components already work cleanly

If a model can't be implemented reliably within its timebox: document the attempt, mark it as deprioritized, move on. Do not let benchmark experimentation consume time budgeted for SHAP, uncertainty, LLM integration, or the dashboard.

---

## 4. Geographic Generalization

Random train/test splits pooling all basins together are NOT sufficient for the main generalization evaluation.

**Use leave-one-basin-out (LOBO) validation:**

```
Train: Basins 2,3,4,5 → Test: Basin 1
Train: Basins 1,3,4,5 → Test: Basin 2
Train: Basins 1,2,4,5 → Test: Basin 3
Train: Basins 1,2,3,5 → Test: Basin 4
Train: Basins 1,2,3,4 → Test: Basin 5
```

Report R², MAE, RMSE per held-out basin. Also record model complexity/inference cost where practical.

**LOBO is for validation only, not deployment.** After model selection and validation are complete:

```
LOBO evaluation → Choose model → Validate generalization
        ↓
Retrain selected model on full pooled dataset
        ↓
Production model
```

When later scoring a genuinely unseen external location (e.g. a Pakistani river site), be transparent in the UI that this is out-of-region inference, not validated performance in that region.

---

## 5. Prediction Layer

```
Sentinel-2 Reflectance
        ↓
Validated ML Model
        ↓
┌───────────────┐
│ Turbidity     │
│ Chlorophyll-a │
│ CDOM          │
└───────────────┘
```

Each target modeled independently. Do not create a combined target before individual predictions are reliable.

---

## 6. Stress/Risk Score

Convert each predicted indicator into an empirical percentile/anomaly relative to its historical reference distribution.

**Reference distribution hierarchy (important):**
- If a monitoring site has sufficient historical observations, compute percentiles relative to that **site's own** historical distribution.
- If site-level history is insufficient, fall back to the **basin-level** historical distribution.
- **Never** pool observations from all five basins into a single global reference distribution — a naturally different basin would look artificially anomalous just for being itself.

**Leakage rule:** The reference distribution must be fit using training/reference data only. Neither the observation being scored nor any held-out test observation may be used to construct the reference distribution it's being compared against.

**Composite score (initial/MVP version):** equal weighting, no learned second-stage model.

```
Stress Score = 1/3 Turbidity anomaly + 1/3 Chlorophyll-a anomaly + 1/3 CDOM anomaly
```

Scale to 0–100.

**Do not:**
- Train a second-stage learned risk model for the MVP
- Invent scientifically unsupported weights
- Describe this as a "validated ecological health index" — use "Freshwater Stress Score" or "Ecosystem Stress Indicator" instead

Keep individual indicators visible alongside the composite score, not just the single number.

---

## 7. Scientific Interpretation Rules

Avoid causal overclaims. Not:

> "High chlorophyll-a means the ecosystem is unhealthy."

Instead:

> "Elevated chlorophyll-a is contributing to the current stress score because its predicted level is unusually high relative to the historical reference distribution. It should be interpreted alongside turbidity and CDOM."

Keep prediction, anomaly, and interpretation as distinct concepts. Don't turn correlation into causation.

---

## 8. Uncertainty

First-class output, not an afterthought.

**Do not** just take the standard deviation of a few model predictions and call it uncertainty.

Use a defensible method:
- Conformal prediction, preferred if implementation is manageable in the timebox
- Properly designed bootstrap/ensemble uncertainty as fallback if conformal prediction can't be completed reliably

Target output shape:

```
Predicted turbidity: 14.2
Prediction interval: 11.8–17.1
Confidence: Moderate
```

Confidence terminology must be tied to whichever method is actually used, not invented independently.

---

## 9. Explainability (SHAP)

Apply SHAP to the **final validated model only**, not an early experiment.

Show both:
- Global feature importance (which Sentinel-2 bands matter overall)
- Local explanation (why this specific prediction)

Phrase findings as contribution, not causation:

> "This feature contributed strongly to the model's prediction."

Not:

> "This feature caused the change."

---

## 10. LLM Layer

The LLM sits strictly **after** the scientific/modeling pipeline.

**It must never generate or modify:** predictions, uncertainty values, stress scores, or SHAP values.

**Input to the LLM (structured):**
```
predictions (turbidity, chlorophyll-a, CDOM)
historical percentiles
stress score
uncertainty interval
top SHAP features
indicator status
```

**Output from the LLM:**
- Plain-language explanation
- Concise interpretation
- Ranked potential actions

The LLM is an explanation and decision-support interface, not a scientific prediction engine. Do not let it access or modify the pipeline's numeric outputs.

---

## 11. Core User Flow

```
OBSERVE   → Sentinel-2 observation
PREDICT   → Turbidity / Chlorophyll-a / CDOM
EXPLAIN   → SHAP + uncertainty
ASSESS    → Freshwater Stress Score
ACT       → LLM-generated interpretation + recommended actions
```

---

## 12. Tech Stack

**Backend:** Python, FastAPI, Pydantic for request/response schemas. XGBoost for models. SHAP for explainability. Split conformal prediction implemented directly (see D4 — `mapie` was the original suggestion, but calibrating in the model's own log1p space is ~40 lines and yields multiplicative intervals that suit these heavy-tailed targets). Model artifacts bundled into the backend's Docker image — no separate model registry needed at this size.

**LLM layer:** Groq API (fast inference, generous free tier). Use a current Groq-hosted model (e.g. a Llama or similar instruct model available on Groq) for the explanation/recommendation layer described in Section 10. Groq's low latency is a genuine advantage for a live demo, the explanation should feel near-instant after the score renders.

**Frontend:** React. Plain React with fetch calls to the backend is sufficient — no need for Next.js or server-side rendering for this dashboard.

**Why this stack over Streamlit (the default choice in most reference repos):** separates concerns cleanly, plays to existing production experience (FastAPI + React already used in prior work), and is a genuine differentiator given the hackathon's judging criteria explicitly include architecture and UX.

---

## 13. Backend API Shape (guidance, not final contract)

A single endpoint like `GET /assessment/{site_id}` should return one structured JSON response containing:

```
stress_score
indicator_percentiles (turbidity, chlorophyll-a, CDOM)
predictions (raw values)
uncertainty_intervals
shap_top_features
llm_explanation
recommended_actions
```

This keeps the frontend simple — one call renders the whole dashboard view.

---

## 14. Dashboard (React)

Prioritize clarity over feature count. Main screen shows, in this order:

1. **Current Assessment** — Freshwater Stress Score, e.g. "78 / 100 — Higher Stress"
2. **Indicator breakdown** — Turbidity / Chlorophyll-a / CDOM with percentile and status (Elevated/High/Moderate)
3. **Why?** — SHAP top contributors
4. **How certain?** — prediction intervals / uncertainty, confidence label
5. **What does this mean?** — LLM-generated plain-language explanation
6. **Recommended actions** — small ranked list

---

## 15. Deployment

- **Frontend:** Vercel or Netlify, deployed from GitHub, free tier.
- **Backend:** Render or Fly.io, both have real free tiers with no billing account required. Render is the simpler setup (point it at the GitHub repo, auto-builds and deploys). Tradeoff: free-tier services on both spin down after a period of inactivity, so the first request after idling has a cold-start delay of roughly 30-60 seconds.
- **Before recording the demo video:** hit the deployed backend once to warm it up, avoid a cold-start delay on camera.

---

## 16. Forecasting Boundary — DO NOT VIOLATE

The MVP does **not** forecast into the future. Do not build:

- "7-Day Forecast" panels
- "X% probability in N days" claims
- Future prediction graphs

...unless a separate, validated temporal forecasting experiment is completed and explicitly labeled as experimental/future work.

The system answers: **"What is the estimated current condition, how unusual is it, and what is driving the prediction?"** — nothing more.

---

## 17. Climate Scenario Boundary

Do not include a "+2°C climate scenario" slider or similar in the core MVP. This would require climate/weather predictors and a validated relationship between those variables and the targets, which this dataset doesn't establish.

If implemented later, it must be explicitly labeled **"Experimental What-If Scenario"** and never presented as validated climate prediction.

---

## 18. Regional Demonstration Layer (Pakistan or other non-US sites)

If live Sentinel-2 imagery from a non-training region (e.g. Pakistan) is added:

- Keep it clearly separated from the USGS-trained evaluation pipeline (a distinct mode, not blended into the main dashboard).
- Label it explicitly: **"Regional Demonstration Mode — using live Sentinel-2 imagery"**.
- Never label it or imply: **"Validated [Region] water-quality prediction"** — the model has not been validated there unless real regional ground-truth data is later used to test it.
- Data source for this mode is a live reflectance product requiring band extraction at chosen coordinates — a genuinely different data path than the CSV-based training pipeline. Inside the conterminous US that is USGS's ACOLITE-DSF product (the same processing as the training data); elsewhere it is Copernicus Sentinel-2 L2A, harmonised to it by measured per-band factors (D7). The harmonisation is a stop-gap from 15 same-day pairs at US sites, not a validated cross-calibration, and the interface says so.

**Demo sites:** Ravi River Bridge, Lahore (31.6083°N, 74.2959°E) is wired in and verified against live imagery, along with thirteen other rivers across Pakistan, South and East Asia, Africa, Europe and the Americas. Every preset was checked for open water in the 250 m buffer before being added; candidates that landed off-water (Jhelum at Jhelum, Indus at Attock, Tigris at Baghdad, Niger at Niamey, Amazon at Manaus) were dropped rather than shipped broken.

**Why the output here is not just unlabeled but genuinely uncertain, state this in any demo narration or written docs:** the model is trained exclusively on US river basins. A Pakistani urban river like the Ravi differs in typical sediment load, pollutant profile, and water chemistry, meaning the input values it sees may fall outside the range the model ever learned from (out-of-distribution inputs). There is also no local ground truth to check the prediction against. The honest framing is "the pipeline runs end-to-end on a new region," not "this is an accurate reading of the Ravi River."

---

## 19. Citizen Photo Verification

Stretch goal only. Priority order: core ML prediction → SHAP → uncertainty → stress score → LLM explanation → dashboard → citizen-photo verification. Do not let this feature compress time budgeted for anything earlier in that list.

---

## 20. Hackathon Positioning

**Primary track:** Resilience Informatics (predictive dashboards, alerts, resilience tools — HydroSentinel's core fit).

**Secondary track:** AI-Supported Assessment (explainable AI, human-in-the-loop — the SHAP + uncertainty + LLM layer).

**Framing for judges:**

> HydroSentinel surfaces unusual freshwater conditions from satellite observations, explains what is driving the prediction, communicates uncertainty, and translates results into understandable decision support.

**Early-warning argument (since there's no forecast):**

> Unusual conditions can become visible in satellite-derived measurements before they are obvious through manual inspection or before a situation becomes severe. HydroSentinel surfaces those signals early enough to support investigation and action.

Do not claim the system predicts a future crisis. The evidence doesn't support that claim.

---

## 21. Implementation Priority

**P0 — Must work:**
- USGS data ingestion + inspection
- Preprocessing
- XGBoost baseline
- Leakage-safe evaluation
- LOBO evaluation
- SHAP
- Uncertainty
- Composite stress score
- FastAPI backend serving the assessment endpoint
- React dashboard covering Section 14's core screens

**P1 — Important:**
- LSTM experiment
- Tabular transformer experiment
- Stacking experiment
- LLM explanation layer
- Ranked recommendations
- Visual polish

**P2 — Stretch:**
- Live regional demonstration mode (Pakistan or other) — **built**, worldwide (D7)
- Citizen-photo verification — not built, deliberately: it would consume time without adding
  evidence, and reads as an unvalidated bolt-on next to the validated pipeline
- Experimental "what-if" scenario analysis — not built; see Section 17, the data does not support it
- OneAquaHealth ecosystem integration (Citizen Science App, etc.) — not built

**Never let P2 work compromise P0.**

**Status:** P0 and P1 complete. The remaining task is deployment (Render + Vercel);
[docs/DEPLOY.md](docs/DEPLOY.md) covers it.

---

## 22. Engineering Principle

Build a clean, independent HydroSentinel codebase. Any external repos consulted are conceptual guidance only, not copy-paste sources; respect their licenses. The final repo should let another researcher trace, in order: where the data came from → how it was cleaned → how features were selected → how models were trained → how geographic generalization was tested → how uncertainty was calculated → how predictions were explained → how the stress indicator was calculated → how the LLM uses those outputs.

**Favor scientific honesty, reproducibility, and a working end-to-end demo over feature quantity.**

---

## 23. Timeline Note

Hackathon runs Sep 16–30, 2026. Per the rules, the actual implementation must be developed during this window — pre-hackathon work was limited to dataset inspection and design (this spec). Commit history should reflect genuine, incremental work across the window, not a single large commit appearing at the end.
