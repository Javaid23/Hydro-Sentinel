"""Out-of-distribution check: where an observation's bands sit vs the training range."""

import json

import pytest

from hydrosentinel import config as C
from hydrosentinel.assess import AssessmentService

pytestmark = pytest.mark.skipif(not (C.MODELS_DIR / "manifest.json").exists(),
                                reason="trained artifacts not present")


@pytest.fixture(scope="module")
def svc():
    return AssessmentService()


def test_training_reference_covers_every_band(svc):
    assert set(svc.training_bands) == set(C.BANDS)
    for b, r in svc.training_bands.items():
        assert r["p1"] < r["p50"] < r["p99"], b
        assert r["min"] <= r["p1"] and r["p99"] <= r["max"], b


def test_in_range_observation_reports_nothing_outside(svc):
    obs = {f"{b}_buf250_mean": svc.training_bands[b]["p50"] for b in C.BANDS}
    o = svc.ood_check(obs)
    assert o["n_outside"] == 0 and o["share_outside"] == 0
    assert "within the range" in o["verdict"]
    assert len(o["bands"]) == len(C.BANDS)
    for b in o["bands"]:
        assert b["outside"] is False and b["direction"] is None
        assert 0 <= b["position"] <= 100


def test_extreme_values_are_flagged_with_direction(svc):
    high = {f"{b}_buf250_mean": svc.training_bands[b]["p99"] * 5 for b in C.BANDS}
    o = svc.ood_check(high)
    assert o["n_outside"] == len(C.BANDS) and o["share_outside"] == 1.0
    assert all(b["direction"] == "above" for b in o["bands"])
    assert all(b["position"] == 125.0 for b in o["bands"])      # far above: clipped for display

    low = {f"{b}_buf250_mean": max(svc.training_bands[b]["p1"] * 0.05, 0.01) for b in C.BANDS}
    o2 = svc.ood_check(low)
    assert o2["n_outside"] == len(C.BANDS)
    assert all(b["direction"] == "below" for b in o2["bands"])
    # below p1, so negative; the -25 clip only engages for values far below the p1-p99 span
    assert all(-25.0 <= b["position"] < 0 for b in o2["bands"])
    assert min(b["position"] for b in svc.ood_check(
        {f"{b}_buf250_mean": -1e6 for b in C.BANDS})["bands"]) == -25.0


def test_position_is_linear_within_the_training_range(svc):
    mid = {f"{b}_buf250_mean": (svc.training_bands[b]["p1"] + svc.training_bands[b]["p99"]) / 2 for b in C.BANDS}
    o = svc.ood_check(mid)
    for b in o["bands"]:
        assert b["position"] == pytest.approx(50.0, abs=0.2)


def test_missing_bands_are_skipped_not_fatal(svc):
    obs = {f"{b}_buf250_mean": svc.training_bands[b]["p50"] for b in list(C.BANDS)[:4]}
    o = svc.ood_check(obs)
    assert o["n_bands"] == 4 and o["n_outside"] == 0


def test_serialisable(svc):
    obs = {f"{b}_buf250_mean": svc.training_bands[b]["p50"] for b in C.BANDS}
    json.dumps(svc.ood_check(obs))     # must survive the API response encoder
