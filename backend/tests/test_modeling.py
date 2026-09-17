"""Tests for features, TargetModel and evaluation splits on a small synthetic table."""

import numpy as np
import pandas as pd
import pytest

from hydrosentinel import config as C
from hydrosentinel import evaluation as ev
from hydrosentinel import features
from hydrosentinel.model import TargetModel


@pytest.fixture(scope="module")
def table() -> pd.DataFrame:
    """Synthetic processed-style table: 4 basins × 3 sites × 40 rows; target driven by red/green."""
    rng = np.random.default_rng(0)
    rows = []
    for basin in ["A", "B", "C", "D"]:
        for s in range(3):
            for _ in range(40):
                r = {"basin": basin, "site_no": f"{basin}{s}", "n_mask": 100.0, "n_l2flag": 80.0}
                base = rng.uniform(100, 600)
                for b in C.BANDS:
                    r[f"{b}_buf250_mean"] = base * rng.uniform(0.7, 1.3)
                    r[f"{b}_buf250_std"] = rng.uniform(5, 30)
                red_green = r["B04_buf250_mean"] / r["B03_buf250_mean"]
                r["value"] = float(np.expm1(2.0 + 2.5 * np.log(red_green) + rng.normal(0, 0.15)))
                rows.append(r)
    return pd.DataFrame(rows)


def test_feature_matrix_shape_and_names(table):
    X = features.build_features(table)
    assert list(X.columns) == features.feature_names()
    assert X.shape == (len(table), 36)
    assert not X.isna().any().any()
    assert not any(c in X.columns for c in C.ID_COLS)
    X2 = features.build_features(table, include_std=False, include_qa=False)
    assert list(X2.columns) == features.feature_names(include_std=False, include_qa=False)
    assert X2.shape[1] == 11 + len(features.RATIOS) + len(features.INDICES)


def test_ratio_and_index_values(table):
    X = features.build_features(table)
    r = table["B04_buf250_mean"] / table["B03_buf250_mean"]
    assert np.allclose(X["r_red_green"], r, rtol=1e-5)
    nd = (table["B05_buf250_mean"] - table["B04_buf250_mean"]) / (table["B05_buf250_mean"] + table["B04_buf250_mean"])
    assert np.allclose(X["ndci"], nd, atol=1e-6)
    assert X["ndwi"].between(-1, 1).all()


def test_target_model_learns_and_roundtrips_log(table, tmp_path):
    X = features.build_features(table)
    y = table["value"].to_numpy()
    split = ev.random_split(table)
    m = TargetModel("turbidity").fit(X.iloc[split.train_idx], y[split.train_idx],
                                     X.iloc[split.test_idx], y[split.test_idx])
    pred = m.predict(X.iloc[split.test_idx])
    assert (pred > 0).all()
    assert ev.regression_metrics(y[split.test_idx], pred)["r2_log"] > 0.8
    assert np.allclose(np.log1p(pred), m.predict_transformed(X.iloc[split.test_idx]), atol=1e-4)
    # persistence
    p = m.save(tmp_path / "m.joblib")
    m2 = TargetModel.load(p)
    assert np.allclose(m2.predict(X.iloc[:5]), pred[:0].tolist() + list(m.predict(X.iloc[:5])))
    assert m2.feature_names_ == list(X.columns)


def test_splits_are_disjoint_and_leakage_safe(table):
    rs = ev.random_split(table)
    assert set(rs.train_idx).isdisjoint(rs.test_idx)
    assert len(rs.train_idx) + len(rs.test_idx) == len(table)

    sh = ev.site_holdout(table)
    tr_sites = set(table.iloc[sh.train_idx]["site_no"])
    te_sites = set(table.iloc[sh.test_idx]["site_no"])
    assert tr_sites.isdisjoint(te_sites)

    folds = list(ev.lobo_folds(table))
    assert {f.held_out for f in folds} == set(table["basin"])
    for f in folds:
        assert set(table.iloc[f.test_idx]["basin"]) == {f.held_out}
        assert f.held_out not in set(table.iloc[f.train_idx]["basin"])


def test_validation_slice_by_site_when_enough_sites(table):
    fit_i, val_i = ev.site_validation_slice(table, min_sites=10)
    assert set(table.iloc[fit_i]["site_no"]).isdisjoint(table.iloc[val_i]["site_no"])
    small = table[table["site_no"].isin(["A0", "A1", "B0"])].reset_index(drop=True)
    fit_i, val_i = ev.site_validation_slice(small, min_sites=10)   # falls back to rows
    assert len(fit_i) + len(val_i) == len(small) and len(val_i) > 0


def test_metrics_keys():
    m = ev.regression_metrics(np.array([1.0, 2.0, 4.0]), np.array([1.1, 1.9, 4.2]))
    assert {"n", "r2", "mae", "rmse", "bias", "median_ae", "r2_log", "rmse_log", "median_factor_err"} <= set(m)
    assert m["n"] == 3 and m["median_factor_err"] >= 1.0
