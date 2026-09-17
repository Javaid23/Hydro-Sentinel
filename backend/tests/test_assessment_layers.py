"""Tests for conformal intervals, SHAP explainer and stress-score reference distributions."""

import numpy as np
import pandas as pd
import pytest

from hydrosentinel import config as C
from hydrosentinel import features
from hydrosentinel.explain import Explainer, describe_contribution
from hydrosentinel.model import TargetModel
from hydrosentinel.stress import ReferenceDistribution, indicator_status, stress_score
from hydrosentinel.uncertainty import ConformalInterval, empirical_coverage, split_calibration


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(1)
    rows = []
    for basin in ["A", "B", "C"]:
        for s in range(4):
            for _ in range(60):
                r = {"basin": basin, "site_no": f"{basin}{s}", "n_mask": 100.0, "n_l2flag": 80.0}
                base = rng.uniform(100, 600)
                for b in C.BANDS:
                    r[f"{b}_buf250_mean"] = base * rng.uniform(0.7, 1.3)
                    r[f"{b}_buf250_std"] = rng.uniform(5, 30)
                rg = r["B04_buf250_mean"] / r["B03_buf250_mean"]
                r["value"] = float(np.expm1(2.0 + 2.5 * np.log(rg) + rng.normal(0, 0.2)))
                rows.append(r)
    df = pd.DataFrame(rows)
    X = features.build_features(df)
    y = df["value"].to_numpy()
    fit_idx, cal_idx = split_calibration(len(df), frac=0.2, seed=0)
    m = TargetModel("turbidity").fit(X.iloc[fit_idx], y[fit_idx])
    return df, X, y, m, fit_idx, cal_idx


def test_conformal_coverage_on_exchangeable_data(fitted):
    df, X, y, m, fit_idx, cal_idx = fitted
    half = len(cal_idx) // 2
    iv = ConformalInterval(m, alpha=0.1).calibrate(X.iloc[cal_idx[:half]], y[cal_idx[:half]])
    assert iv.q_hat_ > 0 and iv.interval_factor > 1
    cov = empirical_coverage(iv, X.iloc[cal_idx[half:]], y[cal_idx[half:]])
    assert 0.8 <= cov["coverage"] <= 1.0          # ≈ 0.9 with sampling noise
    band = iv.predict_interval(X.iloc[:10])
    assert (band["lower"] <= band["prediction"]).all() and (band["prediction"] <= band["upper"]).all()
    # exact in log1p space; only approximately a constant factor in original units (values >> 1)
    assert np.allclose(np.log1p(band["upper"]) - np.log1p(band["lower"]), 2 * iv.q_hat_, atol=1e-4)


def test_conformal_rejects_tiny_calibration(fitted):
    _, X, y, m, _, cal_idx = fitted
    with pytest.raises(ValueError):
        ConformalInterval(m).calibrate(X.iloc[cal_idx[:5]], y[cal_idx[:5]])


def test_shap_global_and_local(fitted):
    df, X, y, m, fit_idx, _ = fitted
    ex = Explainer(m)
    imp = ex.global_importance(X.iloc[fit_idx])
    assert list(imp.columns) == ["feature", "label", "mean_abs_shap", "share"]
    assert abs(imp["share"].sum() - 1) < 1e-6
    # the synthetic target is driven by red/green, so a red/green-type feature should rank near the top
    assert any(f in imp["feature"].head(4).tolist() for f in ("r_red_green", "ndti", "B04_buf250_mean", "B03_buf250_mean"))

    loc = ex.explain_one(X.iloc[[0]], top_k=3)
    assert len(loc["top_contributions"]) == 3
    assert loc["prediction"] == pytest.approx(m.predict(X.iloc[[0]])[0], rel=1e-3)
    c = loc["top_contributions"][0]
    assert c["direction"] in ("raised", "lowered")
    assert (c["factor"] > 1) == (c["direction"] == "raised")
    sentence = describe_contribution(c, "turbidity")
    assert "contribut" not in sentence or "cause" not in sentence
    assert c["label"] in sentence


def test_reference_distribution_hierarchy_and_loo(fitted):
    df, *_ = fitted
    rd = ReferenceDistribution.fit(df, "turbidity", min_site_obs=30)
    # site with enough obs → site level
    r = rd.percentile(df["value"].median(), site_no="A0", basin="A")
    assert r["reference_level"] == "site" and r["n_reference"] == 60 and 0 <= r["percentile"] <= 100
    # unknown site in a known basin → basin level
    r = rd.percentile(10.0, site_no="ZZ", basin="B")
    assert r["reference_level"] == "basin" and r["n_reference"] == 240
    # unknown basin → none
    r = rd.percentile(10.0, site_no="ZZ", basin="Q")
    assert r["reference_level"] == "none" and r["percentile"] is None
    # site below threshold falls back to its basin
    rd2 = ReferenceDistribution.fit(df, "turbidity", min_site_obs=100)
    assert rd2.percentile(10.0, site_no="A0", basin=None)["reference_level"] == "basin"
    # leave-one-out removes exactly one matching value
    v = float(df.loc[df["site_no"] == "A0", "value"].iloc[0])
    assert rd.percentile(v, "A0", "A", exclude_observed=v)["n_reference"] == 59
    # monotone
    assert rd.percentile(1e-3, "A0", "A")["percentile"] < rd.percentile(1e6, "A0", "A")["percentile"]


def test_stress_score_composition():
    s = stress_score({"turbidity": 90.0, "chlorophyll_a": 60.0, "cdom": 30.0})
    assert s["score"] == 60.0 and s["label"] == "Moderate stress"
    assert s["weights"] == {"turbidity": 0.333, "chlorophyll_a": 0.333, "cdom": 0.333}
    s = stress_score({"turbidity": 95.0, "chlorophyll_a": None, "cdom": None})
    assert s["score"] == 95.0 and s["label"] == "Higher stress"
    assert s["indicators_used"] == ["turbidity"] and set(s["indicators_missing"]) == {"chlorophyll_a", "cdom"}
    assert stress_score({"turbidity": None})["score"] is None
    assert indicator_status(10) == "Low" and indicator_status(50) == "Typical"
    assert indicator_status(80) == "Elevated" and indicator_status(95) == "High"
    assert indicator_status(None) is None
