# Demo walkthrough and narration script

Target length: **4 minutes**. The through-line is the spec's flow — Observe → Predict → Explain →
Assess → Act — and the argument is that the system is *honest about what it doesn't know*, which
is what makes the parts it does know usable.

Every number below is real and reproducible; re-check them on the day and swap in the live values.

---

## Before recording

```bash
python backend/scripts/warm_live_cache.py      # ~2-100 min depending on network; do this first
python backend/scripts/warm_live_cache.py --list   # confirm the demo locations are cached
```

Then start both servers and open each tab once so the browser has everything cached:

```
http://localhost:5173/?explain=1               # Historical, explanation pre-generated
http://localhost:5173/?mode=live               # Live
http://localhost:5173/?mode=coords&auto=1      # Regional demo
```

If deployed, hit `/health` once to wake the free-tier backend (30–60 s cold start).

Checklist: browser zoom 100 %, window ≥ 1280 px wide, dark mode matching your preference (the
dashboard supports both), Groq key present so the explanation panel is live.

---

## Scene 0 — Open on the network view (0:00–0:20)

> A water agency runs dozens of monitoring stations. The question each morning is not "what is the
> turbidity at station 14211720" — it is "which of these need someone to look at them today".
>
> HydroSentinel scores every site in the network against its own history in one pass. Forty-nine
> sites, eighteen carrying an elevated indicator, one in higher stress.

*On screen:* the Network overview, then click the top-ranked site to open its detail.

## Scene 1 — The problem (0:00–0:30)

> Freshwater monitoring depends on sensors at fixed points. Between those points, and between
> visits, conditions are unobserved. Satellites cover everything — but a raw reflectance value
> doesn't tell a water manager whether today is unusual, or whether to trust the number.
>
> HydroSentinel turns a Sentinel-2 overpass into an assessment: what the condition is, how unusual
> it is for that specific river, what drove the estimate, and how confident we are.

*On screen:* the dashboard at the Willamette at Portland, Historical mode.

## Scene 2 — Observe and Predict (0:30–1:10)

> This is the Willamette at Portland. For this overpass the models estimate turbidity 1.6 FNU,
> chlorophyll-a 1.7 µg/L, CDOM 10.9. The matched sonde reading that day was 1.4 FNU — shown
> beside the prediction, because the point of a matchup dataset is that you can check.
>
> The models are XGBoost, one per indicator, trained on 9,030 matched observations from five US
> river basins.

*On screen:* indicator cards. Point at the "Matched sonde reading" line.

## Scene 3 — Assess: how unusual is this? (1:10–1:55)

> The score is not a water-quality index. It asks a narrower, answerable question: how unusual is
> this reading *for this river*. Turbidity sits at the 19th percentile of this site's own nine-year
> record — a clear day. Chlorophyll-a at the 67th.
>
> This chart is the site's entire satellite record: nine years, 371 overpasses. Blue dots are sonde
> readings, orange is the model, the shaded band is the site's typical range, and the black line is
> the observation we're assessing.
>
> Crucially, the comparison is always against this site or its basin — never a pool of all five
> basins. A naturally clear river compared against muddy ones would look anomalous just for being
> itself.

*On screen:* scroll to the history chart; switch the tab to Chlorophyll-a to show it works per
indicator.

## Scene 4 — Explain and quantify uncertainty (1:55–2:40)

> Why this number? SHAP attributes the prediction to the satellite features: the red-edge band and
> the red/blue ratio pushed turbidity down. Phrased as contribution, not cause — these are
> reflectance statistics, not pollution sources.
>
> And how certain? Every prediction carries a 90 % conformal interval — turbidity 0.43 to 3.84 FNU,
> and the sonde's 1.4 falls inside it. That coverage is measured, not assumed: it holds at sites in
> the training data, and we measured how much it degrades on unseen basins. That measurement is
> what sets the confidence label.

*On screen:* the Why? and How certain? panels side by side.

## Scene 5 — The honest part (2:40–3:20)

> Here is the result we could have hidden. Under leave-one-basin-out validation, turbidity
> transfers across basins reasonably. Chlorophyll-a does not. CDOM fails outright — R² of minus
> fourteen on unseen sites, because 91 % of its variance is between sites rather than within them.
>
> So every indicator carries a confidence tier derived from that evidence, and we kept CDOM visible
> with a low-confidence label rather than quietly dropping it.
>
> Now the Ravi at Lahore — live Copernicus imagery, a river 11,000 km from any training data. The
> pipeline runs end to end. But there's no local history, so there is no percentile and no stress
> score; and the out-of-distribution check shows several of the eleven bands fall outside anything the
> models saw in training. That's the honest framing: the pipeline works on a new region; the numbers are not
> validated there.

*On screen:* switch to Regional demo, Ravi preset. Show the Local Anomaly Score built from the
location's own archive, and the out-of-distribution panel.

Then scroll back to the Network view's validation chart — three designs, left to right harder — and
let the CDOM bars fall off the bottom. One image carries the whole argument.

## Scene 6 — Act (3:20–3:50)

> Finally, a language model turns the finished assessment into plain language and ranked actions.
> It sits strictly after the pipeline: it receives the numbers as text and cannot generate or alter
> a single one. Note the caveats it's required to state.

*On screen:* click Generate explanation; let the summary and ranked actions render.

## Scene 7 — Close (3:50–4:00)

> HydroSentinel surfaces unusual freshwater conditions from satellite observations, explains what
> drove the estimate, states how uncertain it is, and says plainly where it should not be trusted.
> Everything you saw is traceable from raw USGS data to this screen in the repository.

---

## Numbers to have on hand

| Claim | Value | Source |
|---|---|---|
| Matched observations after filtering | 9,030 (turbidity 6,160 / chl-a 2,349 / CDOM 521) | [data_findings.md](data_findings.md) |
| Raw rows processed | 1,748,467 → 14,665 distinct matchups | [data_findings.md](data_findings.md) |
| Turbidity LOBO | R²_log 0.19 mean, 4 of 5 basins 0.43–0.87 | [results/xgb_baseline.md](results/xgb_baseline.md) |
| CDOM site hold-out | R² −14.5 | [results/model_findings.md](results/model_findings.md) |
| CDOM between-site variance | 91 % | [results/model_findings.md](results/model_findings.md) |
| Conformal coverage, known sites | ≈ 90 % (target 90 %) | [results/uncertainty.md](results/uncertainty.md) |
| Sites / observations served | 49 sites, 6,661 observations | `GET /health` |
| Ravi bands outside training range | 5 of 11 on the 23 Sep 2026 scene — varies by scene, read it off the panel | dashboard OOD panel |
| Tests | 46 | `pytest` |

## Questions judges may ask

**"Why isn't this a forecast?"**
Because nothing in the data supports one. The dataset is matched overpasses and sonde readings,
not a temporal model of what happens next. The early-warning value is that unusual conditions show
up in satellite measurements before a site visit would catch them — not that we predict a future
crisis.

**"Why keep CDOM if it fails validation?"**
It works at the six sites that have fDOM ground truth (random-split R² 0.69) and fails when the
site is unseen. Dropping it would hide a real limitation; keeping it with a measured confidence
tier shows it. The composite score states how many indicators it used.

**"Is the Pakistan demo a real prediction?"**
No, and the interface says so in three places: the mode is labelled unvalidated, no stress score
is computed, and the out-of-distribution panel quantifies how far outside the training range the
inputs sit. It demonstrates that the pipeline generalises operationally, not that the numbers are
accurate there.

**"How do we know none of this is fabricated?"**
`python backend/scripts/audit_provenance.py` — 12 mechanical checks covering the serving path, the
data chain from the raw USGS release, the model artifacts, the imagery sources, and the LLM's
inability to write into the numeric assessment. It is a script rather than a claim so it can be
re-run at any time.

**"What stops the LLM from making things up?"**
It never receives the raw data or the models — only the finished assessment, serialised as text.
Its prompt forbids inventing or restating numbers differently, forbids causal language for SHAP
features, and requires caveats. If it fails or the key is absent, the dashboard still renders every
number; only the prose is missing.

**"What would you do with another two weeks?"**
Lagged reflectance features for turbidity at sites with history (the LSTM benchmark suggests
temporal context helps); more ground truth for CDOM, which is the binding constraint rather than
the model; and a proper cross-calibration study for the Copernicus harmonisation, which currently
rests on 15 same-day pairs.
