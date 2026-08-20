from __future__ import annotations

from aiand_router.scorer import BINS, FAMILIES, featurize


def test_featurize_dim_and_hint_bin_one_hot():
    x = featurize("edit", True, 600, "hard", text="Reply with JSON only: {\"id\": 1}")
    # bias + needs_tools + log1p + 4 token bins + 4 hint bins + text_features
    from aiand_router.scorer import text_features

    assert len(x) == 3 + 4 + len(BINS) + len(text_features(""))
    assert x[0] == 1.0
    assert x[1] == 1.0
    hint_start = 3 + 4
    assert x[hint_start + list(BINS).index("hard")] == 1.0
    assert sum(x[hint_start : hint_start + len(BINS)]) == 1.0
    # phase one-hots are not in the P(success) vector
    assert len(x) == hint_start + len(BINS) + len(text_features(""))


def test_featurize_observable_omits_hint_bin():
    from aiand_router.scorer import featurize_observable

    x = featurize_observable("edit", True, 600)
    assert len(x) == 3 + 4 + len(FAMILIES)


def test_text_features_vary_within_short_prompts():
    from aiand_router.scorer import text_features

    a = text_features("Reply with the single word alpha.")
    b = text_features("Files: reverse.py: def reverse(s): return s")
    assert a != b
    assert a[2] == 1.0  # reply with
    assert b[0] == 1.0  # code cue


def _full_dim() -> int:
    from aiand_router.scorer import text_features

    return 3 + 4 + len(BINS) + len(text_features(""))


def _obs_dim() -> int:
    return 3 + 4 + len(FAMILIES)


def test_predict_complexity_bin_and_intercepts():
    from aiand_router.scorer import featurize_observable, predict_complexity_bin, score_eligible

    obs = featurize_observable("plan", False, 100)
    full = featurize("plan", False, 100, "trivial")
    artifact = {
        "weights": {"m/a": full},
        "intercepts": {"m/a": 0.5},
        "bin_weights": {
            "trivial": [2.0] + [0.0] * (len(obs) - 1),
            "standard": [0.0] * len(obs),
            "hard": [0.0] * len(obs),
            "frontier": [0.0] * len(obs),
        },
        "platt": {"a": 1.0, "b": 0.0},
    }
    assert predict_complexity_bin(artifact, phase="plan", needs_tools=False, tokens=100) == "trivial"
    _, ps = score_eligible(artifact, ["m/a"], phase="plan", needs_tools=False, tokens=100)
    assert 0.0 < ps["m/a"] < 1.0


def test_featurize_token_bins():
    assert featurize("plan", False, 50)[3] == 1.0  # 0-128
    assert featurize("plan", False, 200)[4] == 1.0  # 128-512
    assert featurize("plan", False, 1000)[5] == 1.0  # 512-2k
    assert featurize("plan", False, 3000)[6] == 1.0  # 2k+


def test_featurize_unknown_hint_defaults_standard():
    x = featurize("plan", False, 100, "nope")
    hint_start = 3 + 4
    assert x[hint_start + list(BINS).index("standard")] == 1.0


def _zeros(n: int) -> list[float]:
    return [0.0] * n


def test_intercepts_change_p_success():
    from aiand_router.scorer import score_eligible

    zeros = _zeros(_full_dim())
    base = {"weights": {"m/a": zeros}, "platt": {"a": 1.0, "b": 0.0}}
    _, low = score_eligible(
        {**base, "intercepts": {"m/a": -1.0}},
        ["m/a"],
        phase="plan",
        needs_tools=False,
        tokens=100,
    )
    _, high = score_eligible(
        {**base, "intercepts": {"m/a": 1.0}},
        ["m/a"],
        phase="plan",
        needs_tools=False,
        tokens=100,
    )
    _, missing = score_eligible(base, ["m/a"], phase="plan", needs_tools=False, tokens=100)
    assert high["m/a"] > missing["m/a"] > low["m/a"]


def test_score_eligible_omits_ids_with_silver_weights_but_no_gold_intercept():
    """Ids without success gold get no live calibrated P(success) from silver alone."""
    from aiand_router.scorer import score_eligible

    zeros = _zeros(_full_dim())
    artifact = {
        "weights": {"m/gold": zeros, "m/silver": zeros},
        "intercepts": {"m/gold": 0.5},
        "p_success": {"m/gold": 0.8},
        "platt": {"a": 1.0, "b": 0.0},
    }
    _, ps = score_eligible(
        artifact, ["m/gold", "m/silver"], phase="plan", needs_tools=False, tokens=100
    )
    assert "m/gold" in ps
    assert "m/silver" not in ps


def test_score_eligible_uses_predicted_bin_when_hint_bin_is_none():
    from aiand_router.scorer import predict_complexity_bin, score_eligible

    obs = _zeros(_obs_dim())
    w = _zeros(_full_dim())
    w[3 + 4 + list(BINS).index("frontier")] = 4.0
    artifact = {
        "weights": {"m/a": w},
        "intercepts": {"m/a": 0.0},
        "complexity_bin": "standard",
        "bin_weights": {
            "trivial": _zeros(_obs_dim()),
            "standard": _zeros(_obs_dim()),
            "hard": _zeros(_obs_dim()),
            "frontier": [8.0] + obs[1:],
        },
        "platt": {"a": 1.0, "b": 0.0},
    }
    predicted = predict_complexity_bin(artifact, phase="plan", needs_tools=False, tokens=100)
    assert predicted == "frontier"
    bin_, ps = score_eligible(
        artifact, ["m/a"], phase="plan", needs_tools=False, tokens=100, hint_bin=None
    )
    assert bin_ == "frontier"
    assert ps["m/a"] > 0.8
    forced, ps_forced = score_eligible(
        artifact, ["m/a"], phase="plan", needs_tools=False, tokens=100, hint_bin="trivial"
    )
    assert forced == "trivial"
    assert ps_forced["m/a"] < 0.6


def test_p_spread_not_collapsed_by_identity_platt():
    from aiand_router.scorer import score_eligible

    zeros = _zeros(_full_dim())
    artifact = {
        "weights": {"m/cheap": zeros, "m/dear": zeros},
        "intercepts": {"m/cheap": -2.0, "m/dear": 2.0},
        "platt": {"a": 1.0, "b": 0.0},
    }
    _, ps = score_eligible(
        artifact, ["m/cheap", "m/dear"], phase="plan", needs_tools=False, tokens=80
    )
    spread = max(ps.values()) - min(ps.values())
    assert spread >= 0.10
    assert ps["m/dear"] > ps["m/cheap"]


def test_calibrator_key_applies_after_intercepts():
    from aiand_router.scorer import score_eligible

    zeros = _zeros(_full_dim())
    artifact = {
        "weights": {"m/a": zeros},
        "intercepts": {"m/a": 0.0},
        "calibrator": {"kind": "platt", "a": 2.0, "b": -1.0},
    }
    _, ps = score_eligible(artifact, ["m/a"], phase="plan", needs_tools=False, tokens=100)
    # z = 0 + 0; sigmoid(2*0 + -1) ≈ 0.269, not identity sigmoid(0)=0.5
    assert abs(ps["m/a"] - 0.268941) < 0.01


def test_old_weights_platt_artifact_scores_without_intercepts():
    from aiand_router.scorer import score_eligible

    zeros = _zeros(_full_dim())
    zeros[0] = 0.5
    artifact = {"weights": {"m/a": zeros}, "platt": {"a": 1.0, "b": 0.0}}
    _, ps = score_eligible(artifact, ["m/a"], phase="plan", needs_tools=False, tokens=100)
    assert 0.0 < ps["m/a"] < 1.0


def test_score_eligible_short_weights_use_table_p_not_truncated_dot():
    from aiand_router.scorer import score_eligible

    table_p = 0.42
    # Pre-17-dim layout (bias + tools + log1p + families). Truncated w·x → ~1.0.
    short = [10.0] * (3 + len(FAMILIES))
    artifact = {
        "weights": {"m/a": short, "m/b": short},
        "p_success": {"m/a": table_p},
        "platt": {"a": 1.0, "b": 0.0},
    }
    _, ps = score_eligible(artifact, ["m/a", "m/b"], phase="plan", needs_tools=False, tokens=100)
    assert ps == {"m/a": table_p}


def test_old_p_success_table_artifact_still_works():
    from aiand_router.scorer import score_eligible

    artifact = {
        "not_spec_floors": True,
        "complexity_bin": "hard",
        "p_success": {"m/a": 0.8, "m/b": 0.2},
    }
    bin_, ps = score_eligible(artifact, ["m/a", "m/b", "m/c"], phase="edit", tokens=10)
    assert bin_ == "hard"
    assert ps == {"m/a": 0.8, "m/b": 0.2}


def test_score_eligible_does_not_overwrite_not_spec_floors():
    from aiand_router.scorer import score_eligible

    artifact = {
        "not_spec_floors": True,
        "weights": {"m/a": _zeros(_full_dim())},
        "intercepts": {"m/a": 0.2},
        "platt": {"a": 1.0, "b": 0.0},
    }
    score_eligible(artifact, ["m/a"], phase="plan", needs_tools=False, tokens=100)
    assert artifact["not_spec_floors"] is True


def test_ship_effort_knobs_match_spec_and_have_no_xhigh():
    from aiand_router.scorer import SHIP_EFFORT, effort_knobs

    assert SHIP_EFFORT == {
        "low": {"threshold": 0.05, "max_regret": 0.30},
        "medium": {"threshold": 0.10, "max_regret": 0.20},
        "high": {"threshold": 0.20, "max_regret": 0.15},
        "max": {"threshold": 0.60, "max_regret": 0.03},
    }
    assert "xhigh" not in SHIP_EFFORT
    assert effort_knobs({}, "medium") == (0.10, 0.20)


def test_load_scorer_corrupt_is_none_and_scorer_down_does_not_invent_p(tmp_path):
    from aiand_router.router import Decision, Model
    from aiand_router.scorer import apply_trained_path, load_scorer

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_scorer(bad) is None
    model = Model(
        id="cheap/ok",
        display_name="cheap",
        enabled=True,
        input_per_1m=0.1,
        output_per_1m=0.1,
        context_window=1000,
        supports_tools=True,
        supports_json=True,
        supports_streaming=True,
        max_output_tokens=None,
        cached_input_per_1m=None,
        aa_index=50,
        aa_source="test",
        measured_on="test",
        measured_success=None,
        latency_ms=0,
        health=1,
        priors=None,
    )
    rules = Decision(model=model, phase="plan", threshold=0, reason="rules", candidates=["cheap/ok"])
    rules.confidence = 0.99
    out = apply_trained_path("trained", rules, None, tokens=10)
    assert out.confidence is None
    assert out.complexity_bin is None
    assert "scorer_down" in (out.reason_codes or [])
    assert out.p_success is None


def test_score_eligible_uses_gbdt_when_present():
    """GBDT artifact scores from trees + Platt, not the logistic weights path."""
    from aiand_router.scorer import score_eligible

    zeros = _zeros(_full_dim())
    artifact = {
        "not_spec_floors": True,
        "weights": {"m/a": zeros},
        "intercepts": {"m/a": 0.0},
        "gbdt": {
            "m/a": {
                "intercept": 0.0,
                "trees": [{"feature": 1, "threshold": 0.5, "left": -2.0, "right": 2.0}],
            }
        },
        "platt": {"a": 1.0, "b": 0.0},
    }
    _, no_tools = score_eligible(artifact, ["m/a"], phase="plan", needs_tools=False, tokens=100)
    _, with_tools = score_eligible(artifact, ["m/a"], phase="plan", needs_tools=True, tokens=100)
    assert no_tools["m/a"] < 0.5 < with_tools["m/a"]
    assert artifact["not_spec_floors"] is True
