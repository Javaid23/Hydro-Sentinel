"""LLM layer: prompt construction, token-budget retry, error reporting. No network — the client is faked."""

import json
import types

import pytest

from hydrosentinel import llm


def _assessment(score=40.4, percentile=18.8):
    ind = {
        "key": "turbidity", "label": "Turbidity", "unit": "FNU", "note": "",
        "prediction": 1.63, "interval": {"lower": 0.43, "upper": 3.84, "coverage": 0.9, "method": "split conformal"},
        "observed": 1.4, "percentile": percentile, "reference_level": "site", "n_reference": 367,
        "status": "Low", "validation_tier": "site_seen", "confidence": "Moderate",
        "confidence_note": "calibrated", "baseline_prediction": 9.7,
        "top_contributions": [{"label": "B05 red edge 1", "direction": "lowered", "factor": 0.67,
                               "feature": "B05_buf250_mean", "value": 132.0, "shap_log": -0.4}],
    }
    return {
        "observation": {"station_nm": "Test Site", "site_no": "1", "basin": "Willamette",
                        "scene_datetime_utc": "2026-09-11T19:09:09+00:00", "n_mask": 261},
        "stress": {"score": score, "label": "Moderate stress", "indicators_used": ["turbidity"],
                   "indicators_missing": []},
        "indicators": {"turbidity": ind},
        "validation_tier": "site_seen",
    }


VALID = json.dumps({"summary": "s", "interpretation": "i",
                    "actions": [{"rank": 1, "action": "a", "rationale": "r"}], "caveats": ["c"]})


class FakeClient:
    """Records each call and replays a scripted sequence of responses or exceptions."""

    def __init__(self, script):
        self.script, self.calls = list(script), []
        outer = self

        class Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                item = outer.script.pop(0)
                if isinstance(item, Exception):
                    raise item
                return types.SimpleNamespace(
                    choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=item))])

        self.chat = types.SimpleNamespace(completions=Completions())


def _budget_error():
    return Exception("Error code: 400 - {'error': {'code': 'json_validate_failed', "
                     "'failed_generation': 'max completion tokens reached before generating a valid document'}}")


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)


def test_without_a_key_the_layer_is_disabled(no_key):
    out, err = llm.explain(_assessment())
    assert out is None and "GROQ_API_KEY" in err


def test_context_carries_every_number_and_no_invented_ones():
    ctx = llm.render_context(_assessment())
    for token in ("1.63", "0.43", "3.84", "18.8", "40.4", "Moderate", "site_seen", "Test Site", "367"):
        assert token in ctx, token
    assert "lowered the prediction" in ctx          # contribution wording, not causal


def test_context_handles_a_missing_score_and_percentiles():
    a = _assessment(score=None, percentile=None)
    a["stress"].update({"label": None, "indicators_used": [], "indicators_missing": ["turbidity"]})
    a["indicators"]["turbidity"].update({"percentile": None, "status": None})
    ctx = llm.render_context(a)
    assert "percentile: not available" in ctx
    assert "indicators used: none" in ctx


def test_retries_once_with_a_larger_budget_then_succeeds(monkeypatch):
    client = FakeClient([_budget_error(), VALID])
    monkeypatch.setattr(llm, "_client", lambda: client)
    out, err = llm.explain(_assessment())
    assert err is None and out["summary"] == "s"
    assert [c["max_tokens"] for c in client.calls] == [llm.MAX_TOKENS, llm.MAX_TOKENS_RETRY]
    assert out["disclaimer"] == llm.DISCLAIMER and "generated_utc" in out


def test_gives_up_after_the_second_budget_failure_with_an_actionable_message(monkeypatch):
    client = FakeClient([_budget_error(), _budget_error()])
    monkeypatch.setattr(llm, "_client", lambda: client)
    out, err = llm.explain(_assessment())
    assert out is None
    assert "ran out of" in err and "GROQ_MAX_TOKENS" in err
    assert len(client.calls) == 2


def test_other_errors_are_not_retried_and_surface_their_message(monkeypatch):
    client = FakeClient([Exception("Error code: 404 - the model `nope` does not exist")])
    monkeypatch.setattr(llm, "_client", lambda: client)
    out, err = llm.explain(_assessment())
    assert out is None and len(client.calls) == 1
    assert "does not exist" in err                  # the reason, not just the exception class


def test_malformed_reply_is_rejected(monkeypatch):
    monkeypatch.setattr(llm, "_client", lambda: FakeClient(['{"summary": "", "interpretation": ""}']))
    out, err = llm.explain(_assessment())
    assert out is None and err


def test_validate_normalises_actions_and_caveats():
    out = llm._validate({"summary": " s ", "interpretation": "i",
                         "actions": [{"rank": 3, "action": "c"}, {"action": "a"}, {"nope": 1}],
                         "caveats": ["x", "", "  y  "]})
    assert out["summary"] == "s"
    assert [a["rank"] for a in out["actions"]] == [2, 3]     # second entry gets its index as rank
    assert out["caveats"] == ["x", "y"]
