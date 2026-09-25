"""API tests. Require trained artifacts (models/) and data/processed/observations.parquet,
which are produced by scripts/train.py and scripts/preprocess.py and are git-ignored — skipped otherwise."""

import pytest

from hydrosentinel import config as C
from hydrosentinel.assess import CONFIDENCE

pytestmark = pytest.mark.skipif(
    not (C.MODELS_DIR / "manifest.json").exists() or not (C.DATA_PROCESSED / "observations.parquet").exists(),
    reason="trained artifacts / processed observations not present",
)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


def test_health_and_sites(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["n_sites"] > 0
    sites = client.get("/sites").json()
    assert sites and {"site_no", "basin", "n_observations", "targets_observed"} <= set(sites[0])
    assert client.get("/sites", params={"basin": "willamette"}).json()


def test_assessment_shape_and_invariants(client):
    site = client.get("/sites", params={"min_observations": 30}).json()[0]["site_no"]
    a = client.get(f"/assessment/{site}").json()
    assert set(a["indicators"]) == set(C.TARGETS)
    for ind in a["indicators"].values():
        assert ind["interval"]["lower"] <= ind["prediction"] <= ind["interval"]["upper"]
        # tiers are per indicator: a site rich in turbidity history may have no chl-a history
        assert ind["validation_tier"] in ("site_seen", "basin_seen")
        assert ind["confidence"] == CONFIDENCE[ind["validation_tier"]][ind["key"]]
        assert len(ind["top_contributions"]) == 5
        if ind["percentile"] is not None:
            assert 0 <= ind["percentile"] <= 100 and ind["status"] in {"Low", "Typical", "Elevated", "High"}
    s = a["stress"]
    assert s["score"] is None or 0 <= s["score"] <= 100
    assert a["llm_explanation"] is None and a["llm_error"] is None   # explain not requested


def test_specific_observation_and_404s(client):
    site = client.get("/sites", params={"min_observations": 30}).json()[0]["site_no"]
    obs = client.get(f"/sites/{site}/observations", params={"limit": 2}).json()
    oid = obs[0]["observation_id"]
    a = client.get(f"/assessment/{site}", params={"observation_id": oid}).json()
    assert a["observation"]["observation_id"] == oid
    assert client.get("/assessment/does-not-exist").status_code == 404
    assert client.get(f"/assessment/{site}", params={"observation_id": "nope"}).status_code == 404
    assert client.get("/models/nope/global-importance").status_code == 404


def test_explain_without_key_degrades_gracefully(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    site = client.get("/sites").json()[0]["site_no"]
    a = client.get(f"/assessment/{site}", params={"explain": "true"}).json()
    assert a["llm_explanation"] is None and "GROQ_API_KEY" in a["llm_error"]
    assert a["stress"] is not None


def test_network_overview_scores_every_site(client):
    n = client.get("/network").json()
    assert n["n_sites"] > 40 and n["n_scored"] <= n["n_sites"]
    assert sum(n["counts"].values()) <= n["n_sites"]

    scored = [s for s in n["sites"] if s["stress_score"] is not None]
    assert scored, "no site could be scored"
    # ranked by stress, unscored sites last
    assert scored == sorted(scored, key=lambda s: -s["stress_score"])
    assert all(s["stress_score"] is not None for s in n["sites"][:len(scored)])

    s = scored[0]
    assert set(s["indicators"]) == set(C.TARGETS)
    assert 0 <= s["stress_score"] <= 100
    assert s["indicators_used"] >= 1
    for ind in s["indicators"].values():
        assert ind["prediction"] > 0
        if ind["percentile"] is not None:
            assert 0 <= ind["percentile"] <= 100
            assert ind["status"] in {"Low", "Typical", "Elevated", "High"}
        else:
            assert ind["status"] is None          # no reference -> no status, never a fabricated one


def test_network_matches_the_single_site_assessment(client):
    """The overview must not disagree with the detail view it links to."""
    n = client.get("/network").json()
    site = next(s for s in n["sites"] if s["stress_score"] is not None)
    detail = client.get(f"/assessment/{site['site_no']}",
                        params={"observation_id": site["observation_id"]}).json()
    assert detail["stress"]["score"] == pytest.approx(site["stress_score"], abs=0.11)
    for key, ind in site["indicators"].items():
        assert detail["indicators"][key]["prediction"] == pytest.approx(ind["prediction"], rel=1e-3)
        if ind["percentile"] is not None:
            assert detail["indicators"][key]["percentile"] == pytest.approx(ind["percentile"], abs=0.11)


def test_network_basin_filter(client):
    all_sites = client.get("/network").json()
    basin = all_sites["sites"][0]["basin"]
    filtered = client.get("/network", params={"basin": basin}).json()
    assert 0 < filtered["n_sites"] <= all_sites["n_sites"]
    assert {s["basin"] for s in filtered["sites"]} == {basin}


def test_validation_reports_the_measured_degradation(client):
    v = client.get("/validation").json()
    assert set(v["targets"]) == set(C.TARGETS)
    t = v["targets"]["turbidity"]["designs"]
    assert {"random", "site_holdout", "lobo"} <= set(t)
    # the honesty claim the dashboard makes: harder designs score worse
    assert t["random"]["r2_log"] > t["lobo"]["r2_log"]
    cd = v["targets"]["cdom"]["designs"]
    assert cd["random"]["r2"] > 0 > cd["site_holdout"]["r2"], "CDOM must show its site-holdout failure"
    assert v["targets"]["cdom"]["verdict"]
    assert t["lobo"]["n_folds"] >= 4 and len(t["lobo"]["folds"]) == t["lobo"]["n_folds"]


def test_expensive_endpoints_are_rate_limited(client):
    """A public endpoint doing minutes of network work must not be freely repeatable."""
    from hydrosentinel import limits
    saved = limits.BASELINE
    limits.BASELINE = limits.RateLimiter(max_calls=2, window_seconds=600, max_concurrent=1, name="baseline build")
    try:
        codes = [client.get("/live/baseline", params={"lat": 0.0, "lon": 0.0}).status_code for _ in range(4)]
        assert 429 in codes, f"never rate limited: {codes}"
        blocked = client.get("/live/baseline", params={"lat": 0.0, "lon": 0.0})
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers
    finally:
        limits.BASELINE = saved


def test_location_label_is_length_capped_by_the_schema(client):
    r = client.get("/live/coords", params={"lat": 45.0, "lon": -122.0, "name": "x" * 500})
    assert r.status_code == 422, "an unbounded free-text field should be rejected at the edge"
