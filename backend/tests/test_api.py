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
