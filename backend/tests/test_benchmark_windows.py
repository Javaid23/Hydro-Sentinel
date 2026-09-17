"""Sequence-window construction for the LSTM benchmark (pure numpy; no torch needed)."""

import numpy as np
import pandas as pd

from hydrosentinel.benchmarks.common import MIN_SITE_OBS_SEQ, Scaler, build_windows


def _df(n_a=40, n_b=10):
    t0 = pd.Timestamp("2020-01-01", tz="UTC")
    rows = [{"site_no": "A", "scene_datetime_utc": t0 + pd.Timedelta(days=5 * i)} for i in range(n_a)]
    rows += [{"site_no": "B", "scene_datetime_utc": t0 + pd.Timedelta(days=5 * i)} for i in range(n_b)]
    df = pd.DataFrame(rows).sample(frac=1, random_state=0).reset_index(drop=True)   # shuffled on purpose
    X = np.arange(len(df), dtype=np.float32)[:, None] * np.ones((1, 3), dtype=np.float32)  # row id as feature
    return df, X


def test_windows_are_chronological_within_site_and_left_padded():
    df, X = _df()
    idx = np.arange(len(df))
    S, M, kept = build_windows(df, X, window=4, idx=idx)
    assert set(df.iloc[kept]["site_no"]) == {"A"}                 # B has < MIN_SITE_OBS_SEQ rows
    assert S.shape == (40, 4, 3) and M.shape == (40, 4)
    # the last element of each window is the row itself
    assert np.allclose(S[:, -1, 0], kept)
    # windows only look backwards in time at the same site
    times = df["scene_datetime_utc"].to_numpy()
    for s, r in zip(S, kept):
        prev = s[:-1, 0].astype(int)
        assert all(times[p] <= times[r] for p in prev)
        assert all(df.iloc[p]["site_no"] == "A" for p in prev)
    # earliest observation is fully padded (mask has one real element)
    first = kept[np.argmin(times[kept])]
    m = M[list(kept).index(first)]
    assert m.sum() == 1 and m[-1] == 1


def test_eligibility_is_decided_within_the_given_indices():
    df, X = _df(n_a=40)
    idx = np.flatnonzero(df["site_no"].to_numpy() == "A")[: MIN_SITE_OBS_SEQ - 1]
    S, M, kept = build_windows(df, X, window=3, idx=idx)
    assert len(kept) == 0 and S.shape[0] == 0


def test_scaler_roundtrip():
    X = np.random.default_rng(0).normal(5, 2, size=(100, 4)).astype(np.float32)
    Z = Scaler.fit(X).transform(X)
    assert np.allclose(Z.mean(axis=0), 0, atol=1e-5) and np.allclose(Z.std(axis=0), 1, atol=1e-4)
