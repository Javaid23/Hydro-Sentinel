"""Location baselines: percentile maths, cache round-trip, and the guard rails on what they claim."""


from datetime import UTC

import numpy as np
import pytest

from hydrosentinel import baseline


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(baseline, "CACHE_DIR", tmp_path / "baseline_cache")
    return tmp_path / "baseline_cache"


def _blob(values=None):
    values = sorted(values if values is not None else [1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 20.0, 50.0])
    return {
        "lat": 25.7, "lon": 32.64, "built_utc": "2026-09-25T12:00:00+00:00",
        "n_scenes": len(values), "n_attempted": len(values) + 3,
        "first_scene": "2025-08-02", "last_scene": "2026-09-21", "lookback_days": 730,
        "source": "Copernicus Sentinel-2 L2A", "kind": "model_predictions",
        "note": "not ground truth",
        "targets": {"turbidity": {
            "label": "Turbidity", "unit": "FNU", "values": values,
            "quantiles": {"p50": float(np.median(values))},
            "series": [], "histogram": {"edges": [], "counts": []},
        }},
    }


def test_cache_round_trip(tmp_cache):
    baseline.save(25.7, 32.64, _blob())
    got = baseline.load(25.7, 32.64)
    assert got["n_scenes"] == 8 and got["kind"] == "model_predictions"
    assert list(tmp_cache.glob("*.tmp")) == []
    assert baseline.load(1.0, 2.0) is None


def test_corrupt_baseline_is_ignored(tmp_cache):
    tmp_cache.mkdir(parents=True, exist_ok=True)
    (tmp_cache / f"{baseline._key(5.0, 6.0)}.json").write_text("{oops", encoding="utf-8")
    assert baseline.load(5.0, 6.0) is None


def test_key_is_filename_safe_and_rounds():
    assert baseline._key(-25.70001, -32.64004) == baseline._key(-25.70002, -32.63996)
    k = baseline._key(-25.7, -32.64)
    assert "-" not in k and "." not in k


def test_percentile_is_mid_rank_and_monotone():
    b = _blob()
    assert baseline.percentile_of(b, "turbidity", 0.1)["percentile"] == 0.0
    assert baseline.percentile_of(b, "turbidity", 1e6)["percentile"] == 100.0
    lo = baseline.percentile_of(b, "turbidity", 2.0)["percentile"]
    hi = baseline.percentile_of(b, "turbidity", 20.0)["percentile"]
    assert lo < hi
    # a value equal to one sample takes the mid-rank of that tie
    eq = baseline.percentile_of(b, "turbidity", 3.0)
    assert eq["percentile"] == round(100 * (2 + 0.5) / 8, 1)     # mid-rank of the tie, to 1 dp
    assert eq["n_reference"] == 8 and eq["unit"] == "FNU"


def test_percentile_of_unknown_target_is_none():
    assert baseline.percentile_of(_blob(), "cdom", 1.0) is None
    assert baseline.percentile_of({"targets": {}}, "turbidity", 1.0) is None


def test_thresholds_are_conservative():
    # a baseline that cannot support a meaningful percentile should not be built
    assert baseline.MIN_SCENES >= 10
    assert baseline.TARGET_SCENES >= baseline.MIN_SCENES
    assert baseline.MAX_ATTEMPTS >= baseline.TARGET_SCENES
    assert baseline.LOOKBACK_DAYS >= 365           # at least a full seasonal cycle


def test_build_refuses_when_too_few_scenes_are_usable(monkeypatch):
    """Cloud rejects most scenes at some locations; the result must be an error, not a thin baseline."""
    from datetime import datetime, timedelta

    from hydrosentinel import live_global as G
    base = datetime(2026, 9, 1, tzinfo=UTC)
    fakes = [_Scene(base - timedelta(days=30 * i)) for i in range(6)]
    monkeypatch.setattr(G, "stac_search", lambda *a, **k: fakes)
    monkeypatch.setattr(baseline, "_extract_one", lambda scene, lat, lon: None)
    with pytest.raises(ValueError, match="usable scenes"):
        baseline.build(25.7, 32.64, service=None)


def test_build_refuses_when_the_archive_has_nothing(monkeypatch):
    from hydrosentinel import live_global as G
    monkeypatch.setattr(G, "stac_search", lambda *a, **k: [])
    with pytest.raises(LookupError, match="no Sentinel-2 scenes"):
        baseline.build(0.0, 0.0, service=None)


def test_entries_summary(tmp_cache):
    baseline.save(25.7, 32.64, _blob())
    baseline.save(31.6, 74.3, _blob([7.0] * 20))
    rows = baseline.entries()
    assert len(rows) == 2
    assert {r["n_scenes"] for r in rows} == {8, 20}
    assert all(r["built_utc"] for r in rows)


def test_note_states_it_is_not_ground_truth():
    """The wording is load-bearing: this reference must never read as measurements."""
    import inspect
    src = inspect.getsource(baseline.build)
    assert "not ground truth" in src
    assert "model_predictions" in src


class _Scene:
    def __init__(self, d):
        self.datetime_utc, self.scene_id = d, str(d.date())


def _archive(n=140, step_days=5):
    from datetime import datetime, timedelta
    now = datetime(2026, 9, 25, tzinfo=UTC)
    return [_Scene(now - timedelta(days=step_days * i)) for i in range(n)]


def test_spread_covers_the_window_not_just_recent_scenes():
    """Taking the newest N would compare one season against itself — the bias this guards against."""
    scenes = _archive()
    full_span = (scenes[0].datetime_utc - scenes[-1].datetime_utc).days
    picked = baseline._spread(scenes, 24)
    span = (max(s.datetime_utc for s in picked) - min(s.datetime_utc for s in picked)).days
    assert len(picked) == 24
    assert span > 0.8 * full_span                      # spans the archive, not the last few weeks

    newest_24 = sorted(scenes, key=lambda s: s.datetime_utc, reverse=True)[:24]
    newest_span = (newest_24[0].datetime_utc - newest_24[-1].datetime_utc).days
    assert span > 4 * newest_span                      # and is far wider than the naive choice


def test_any_prefix_of_the_sample_is_still_spread():
    """Cloud truncates builds early; a prefix must not collapse onto one end of the window."""
    scenes = _archive()
    picked = baseline._spread(scenes, 48)
    for k in (12, 24, 48):
        ds = [s.datetime_utc for s in picked[:k]]
        assert (max(ds) - min(ds)).days > 365, f"prefix of {k} spans under a year"


def test_spread_is_deterministic_and_lossless_for_short_lists():
    scenes = _archive(n=10)
    assert {s.scene_id for s in baseline._spread(scenes, 24)} == {s.scene_id for s in scenes}
    a = [s.scene_id for s in baseline._spread(_archive(), 24)]
    b = [s.scene_id for s in baseline._spread(_archive(), 24)]
    assert a == b


def test_narrow_baselines_are_flagged():
    assert baseline.MIN_SPAN_DAYS >= 300               # must cover most of a year to mean anything
    assert baseline.SEARCH_LIMIT > baseline.MAX_ATTEMPTS
