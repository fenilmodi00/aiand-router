from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiand_router.replay_report import (
    apply_replay_gate,
    assert_not_production_floors,
    main,
    parity_blockers,
    parity_posture,
    replay_gate_pass,
    replay_report,
)
from aiand_router.router import load_models

FIXTURE_DIR = Path(__file__).parent / "fixtures"
GOLD = FIXTURE_DIR / "replay_gold.jsonl"
SCORER = FIXTURE_DIR / "replay_scorer.json"
POLICIES = ("rules", "trained", "oracle", "always_flash", "always_strong")


def _toy_cfg() -> dict:
    return {
        "fallback_model": "cheap/flash",
        "premium_aa_floor": 99,
        "phase_threshold": {
            "summarize": 0,
            "plan": 0,
            "edit": 0,
            "tool": 0,
            "debug": 0,
            "discover": 0,
        },
        "models": [
            {
                "id": "cheap/flash",
                "enabled": True,
                "input_per_1m": 0.1,
                "output_per_1m": 0.1,
                "context_window": 100000,
                "supports_tools": True,
                "aa_index": 40,
                "aa_source": "test",
                "measured_on": "test",
            },
            {
                "id": "dear/strong",
                "enabled": True,
                "input_per_1m": 10,
                "output_per_1m": 10,
                "context_window": 100000,
                "supports_tools": True,
                "aa_index": 55,
                "aa_source": "test",
                "measured_on": "test",
            },
        ],
    }


def _artifact() -> dict:
    return json.loads(SCORER.read_text(encoding="utf-8"))


def _report(**kwargs):
    cfg = _toy_cfg()
    assert_not_production_floors(GOLD, _artifact())
    return replay_report(GOLD, _artifact(), load_models(cfg), cfg, **kwargs)


def _bars_green() -> dict:
    cheapest = {"success_rate": 0.5, "list_price_cost": 0.01}
    trained = {"success_rate": 0.8, "list_price_cost": 0.04}
    return {
        "rank_auc": 0.9,
        "mean_p_spread": 0.2,
        "brier_skill": 0.1,
        "ece_equal_width": 0.01,
        "ece_equal_mass": 0.01,
        "rules_cost_delta": -0.01,
        "rules_ne_cheapest_rate": 1.0,
        "rules_cost_delta_where_rules_ne_cheapest": -0.01,
        "savings_vs_most_expensive": 0.06,
        "policies": {
            "trained": dict(trained),
            "rules": {"success_rate": 0.8, "list_price_cost": 0.05},
            "always_flash": dict(cheapest),
            "always_cheapest": dict(cheapest),
            "always_strong": {"success_rate": 0.8, "list_price_cost": 0.10},
            "always_most_expensive": {"success_rate": 0.5, "list_price_cost": 0.10},
        },
    }


def test_fixture_is_not_production_floors():
    assert_not_production_floors(GOLD, _artifact())


def test_replay_report_policies_success_rate_and_list_price_cost():
    assert_not_production_floors(GOLD, _artifact())
    report = _report()
    # 4×2 gold: p0 both win, p1 strong only, p2 flash only, p3 neither.
    assert report["policies"]["oracle"]["success_rate"] == 3 / 4
    flash = report["policies"]["always_flash"]
    strong = report["policies"]["always_strong"]
    assert flash["success_rate"] == 2 / 4
    assert strong["success_rate"] == 2 / 4
    assert flash["list_price_cost"] < strong["list_price_cost"]
    assert report["rules_cost_delta"] == (
        report["policies"]["trained"]["list_price_cost"]
        - report["policies"]["rules"]["list_price_cost"]
    )
    assert report["savings_vs_most_expensive"] >= 0.0
    assert "always_most_expensive" in report["policies"]
    if report["rules_ne_cheapest_rate"] == 0.0:
        assert report["rules_cost_delta_where_rules_ne_cheapest"] is None
    else:
        assert isinstance(report["rules_cost_delta_where_rules_ne_cheapest"], float)
    for name in POLICIES:
        row = report["policies"][name]
        assert 0.0 <= row["success_rate"] <= 1.0
        assert row["list_price_cost"] >= 0.0


def test_replay_report_disagreement_and_calibration_metrics_defined():
    assert_not_production_floors(GOLD, _artifact())
    report = _report()
    assert report["disagreement_rate"] > 0
    for key in (
        "rank_auc",
        "mean_p_spread",
        "brier",
        "brier_skill",
        "ece_equal_width",
        "ece_equal_mass",
    ):
        assert isinstance(report[key], float)
    # selected-hop y = flash gold cells; p = artifact cheap/flash.
    ys = (1.0, 0.0, 1.0, 0.0)
    p = 0.85
    brier = sum((p - y) ** 2 for y in ys) / len(ys)
    ybar = sum(ys) / len(ys)
    brier_ref = sum((ybar - y) ** 2 for y in ys) / len(ys)
    assert report["brier"] == pytest.approx(brier)
    assert report["brier_skill"] == pytest.approx(1.0 - brier / brier_ref)
    assert report["brier_skill"] != 0.0


def test_cli_gold_is_holdout(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["-h"])
    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out.lower()
    assert "--gold" in help_text
    assert "holdout" in help_text
    assert "train" in help_text or "cal" in help_text
    report = _report()
    assert report["gold_is_holdout"] is True


def test_replay_gate_pass_is_bool_on_toy_fixture():
    assert_not_production_floors(GOLD, _artifact())
    report = _report()
    assert isinstance(replay_gate_pass(report), bool)
    # toy fixture is allowed to fail the bars; do not require AUC ≥ 0.65 here
    assert report["path"] == "shadow"
    assert report["not_spec_floors"] is True


def test_replay_gate_fails_when_trained_is_always_cheapest():
    """Rules≠trained is not enough; trained=always-Flash must fail the gate."""
    cheapest = {"success_rate": 0.5, "list_price_cost": 0.01}
    report = {
        "rank_auc": 0.9,
        "mean_p_spread": 0.2,
        "brier_skill": 0.1,
        "ece_equal_width": 0.01,
        "ece_equal_mass": 0.01,
        "rules_cost_delta": 0.02,
        "rules_ne_cheapest_rate": 1.0,
        "savings_vs_most_expensive": 0.06,
        "disagreement_rate": 0.4,
        "policies": {
            "trained": dict(cheapest),
            "rules": {"success_rate": 0.5, "list_price_cost": 0.05},
            "always_flash": dict(cheapest),
            "always_cheapest": dict(cheapest),
            "always_strong": {"success_rate": 0.7, "list_price_cost": 0.10},
        },
    }
    assert replay_gate_pass(report) is False


def test_replay_gate_fails_always_cheapest_when_strong_is_better_even_if_not_flash():
    cheapest = {"success_rate": 0.5, "list_price_cost": 0.01}
    dear = {"success_rate": 0.8, "list_price_cost": 0.10}
    report = {
        "rank_auc": 0.9,
        "mean_p_spread": 0.2,
        "brier_skill": 0.1,
        "ece_equal_width": 0.01,
        "ece_equal_mass": 0.01,
        "rules_cost_delta": -0.09,
        "rules_ne_cheapest_rate": 1.0,
        "savings_vs_most_expensive": 0.09,
        "disagreement_rate": 0.4,
        "policies": {
            "trained": dict(cheapest),
            "rules": dict(dear),
            "always_flash": dict(dear),
            "always_cheapest": dict(cheapest),
            "always_strong": dict(dear),
        },
    }
    assert replay_gate_pass(report) is False
    """Always-Flash is allowed only when paying up does not buy quality."""
    cheapest = {"success_rate": 0.9, "list_price_cost": 0.01}
    dear = {"success_rate": 0.5, "list_price_cost": 0.10}
    report = {
        "rank_auc": 0.9,
        "mean_p_spread": 0.2,
        "brier_skill": 0.1,
        "ece_equal_width": 0.01,
        "ece_equal_mass": 0.01,
        "rules_cost_delta": -0.01,
        "rules_ne_cheapest_rate": 1.0,
        "savings_vs_most_expensive": 0.09,
        "disagreement_rate": 0.4,
        "policies": {
            "trained": dict(cheapest),
            "rules": dict(dear),
            "always_flash": dict(dear),
            "always_cheapest": dict(cheapest),
            "always_strong": dict(dear),
        },
    }
    assert replay_gate_pass(report) is True


def test_rank_auc_skips_unscored_gold_ids(tmp_path):
    """Unscored eligible ids must not be imputed as 0.5 (that pulls AUC to chance)."""
    cfg = _toy_cfg()
    cfg["models"].append(
        {
            "id": "mid/other",
            "enabled": True,
            "input_per_1m": 1,
            "output_per_1m": 1,
            "context_window": 100000,
            "supports_tools": True,
            "aa_index": 50,
            "aa_source": "test",
            "measured_on": "test",
        }
    )
    gold = tmp_path / "gold.jsonl"
    gold.write_text(
        "".join(
            json.dumps(
                {
                    "prompt": "q",
                    "model_id": mid,
                    "success": ok,
                    "tokens": 100,
                    "needs_tools": False,
                    "phase": "plan",
                }
            )
            + "\n"
            for mid, ok in (
                ("cheap/flash", True),
                ("dear/strong", False),
                ("mid/other", True),
            )
        ),
        encoding="utf-8",
    )
    artifact = {
        "not_spec_floors": True,
        "n_gold": 3,
        "complexity_bin": "standard",
        "p_success": {"cheap/flash": 0.9, "dear/strong": 0.8},
    }
    report = replay_report(gold, artifact, load_models(cfg), cfg)
    # skip mid/other: (0.9, 1) vs (0.8, 0) → 1.0; impute 0.5 → also (0.5, 1) vs (0.8, 0) → 0.5
    assert report["rank_auc"] == 1.0


def test_holdout_ids_restricts_to_unused_split():
    assert_not_production_floors(GOLD, _artifact())
    one = _report(holdout_ids={"p0"})
    all_holdout = _report()
    assert one["n_prompts"] == 1
    assert all_holdout["n_prompts"] > 1


def test_assert_not_production_floors_rejects_verified_n(tmp_path):
    gold = tmp_path / "verified.jsonl"
    gold.write_text(
        "".join(
            json.dumps({"prompt": f"q{i}", "model_id": "cheap/flash", "success": True}) + "\n"
            for i in range(300)
        ),
        encoding="utf-8",
    )
    try:
        assert_not_production_floors(gold, {"not_spec_floors": True, "n_gold": 8})
    except AssertionError:
        return
    raise AssertionError("expected production floors (Verified n≥300) to be rejected")


def test_assert_not_production_floors_rejects_staffed_promotion_stamp():
    try:
        assert_not_production_floors(GOLD, {"not_spec_floors": False, "n_gold": 4000})
    except AssertionError:
        return
    raise AssertionError("expected staffed promotion floors to be rejected")


def test_failing_any_bar_keeps_shadow_and_not_spec_floors():
    """Toy fixture fails the gate; report stays path=shadow and not_spec_floors (no Verified stamp)."""
    assert_not_production_floors(GOLD, _artifact())
    report = _report()
    assert replay_gate_pass(report) is False
    assert report["replay_gate_pass"] is False
    assert report["path"] == "shadow"
    assert report["not_spec_floors"] is True
    assert "savings" not in report


def test_cli_stdout_grepable_shadow_and_not_spec_floors(tmp_path, capsys, monkeypatch):
    import os

    import yaml

    monkeypatch.delenv("TRAINED_PATH", raising=False)
    models = tmp_path / "models.yaml"
    models.write_text(yaml.safe_dump(_toy_cfg()), encoding="utf-8")
    assert main(["--gold", str(GOLD), "--artifact", str(SCORER), "--models", str(models)]) == 0
    out = capsys.readouterr().out
    assert "path=shadow" in out
    assert "not_spec_floors" in out
    assert "replay_gate_pass" in out
    assert os.getenv("TRAINED_PATH") != "trained"


def test_passing_gate_still_keeps_shadow_and_not_spec_floors():
    """This cycle does not auto-flip TRAINED_PATH or stamp Verified."""
    out = apply_replay_gate(_bars_green())
    assert out["replay_gate_pass"] is True
    assert out["path"] == "shadow"
    assert out["not_spec_floors"] is True


@pytest.mark.parametrize(
    "key,value",
    [
        ("rank_auc", 0.64),
        ("mean_p_spread", 0.09),
        ("brier_skill", 0.0),
        ("ece_equal_width", 0.031),
        ("ece_equal_mass", 0.031),
        ("savings_vs_most_expensive", 0.0),
    ],
)
def test_failing_numeric_bar_keeps_shadow_and_not_spec_floors(key, value):
    report = _bars_green()
    report[key] = value
    # Equal-mass ECE is waived only for small-n selected cal; force large-n here.
    if key == "ece_equal_mass":
        report["n_selected"] = 200
        report["n_prompts"] = 200
    out = apply_replay_gate(report)
    assert out["replay_gate_pass"] is False
    assert out["path"] == "shadow"
    assert out["not_spec_floors"] is True


def test_small_n_waives_equal_mass_ece_but_keeps_equal_width():
    report = _bars_green()
    report["ece_equal_mass"] = 0.12
    report["n_selected"] = 72
    report["n_prompts"] = 89
    assert replay_gate_pass(report) is True
    report["ece_equal_width"] = 0.031
    assert replay_gate_pass(report) is False


def test_trained_success_below_rules_minus_1pp_fails_gate():
    report = _bars_green()
    report["policies"]["trained"]["success_rate"] = 0.78
    out = apply_replay_gate(report)
    assert out["replay_gate_pass"] is False
    assert out["path"] == "shadow"
    assert out["not_spec_floors"] is True


def test_replay_report_includes_always_cheapest_policy():
    assert_not_production_floors(GOLD, _artifact())
    row = _report()["policies"]["always_cheapest"]
    assert 0.0 <= row["success_rate"] <= 1.0
    assert row["list_price_cost"] >= 0.0


def test_replay_report_rules_ne_cheapest_rate_on_toy_fixture():
    """Toy catalog: strong wins pioneer_score while Flash is cheapest eligible."""
    assert_not_production_floors(GOLD, _artifact())
    report = _report()
    assert report["rules_ne_cheapest_rate"] == 1.0


def _dual_cfg() -> dict:
    cfg = _toy_cfg()
    cfg["phase_threshold"] = {
        "summarize": 0,
        "plan": 0,
        "edit": 0,
        "tool": 0,
        "debug": 54,
        "discover": 0,
    }
    return cfg


def _gold_rows(prompt: str, phase: str, tokens: int = 20) -> list[dict]:
    return [
        {
            "prompt": prompt,
            "model_id": "cheap/flash",
            "success": True,
            "tokens": tokens,
            "needs_tools": False,
            "phase": phase,
        },
        {
            "prompt": prompt,
            "model_id": "dear/strong",
            "success": True,
            "tokens": tokens,
            "needs_tools": False,
            "phase": phase,
        },
    ]


def test_dual_eval_cost_gold_where_rules_disagree_with_cheapest(tmp_path, capsys, monkeypatch):
    import os

    import yaml

    monkeypatch.delenv("TRAINED_PATH", raising=False)
    eval_gold = tmp_path / "gold-eval.jsonl"
    eval_gold.write_text(
        "".join(json.dumps(r) + "\n" for r in _gold_rows("eval-q", "debug")),
        encoding="utf-8",
    )
    cost_gold = tmp_path / "gold-cost.jsonl"
    cost_gold.write_text(
        "".join(json.dumps(r) + "\n" for r in _gold_rows("cost-q", "summarize")),
        encoding="utf-8",
    )
    models = tmp_path / "models.yaml"
    models.write_text(yaml.safe_dump(_dual_cfg()), encoding="utf-8")
    assert_not_production_floors(eval_gold, _artifact())
    assert_not_production_floors(cost_gold, _artifact())
    assert (
        main(
            [
                "--gold",
                str(eval_gold),
                "--cost-gold",
                str(cost_gold),
                "--artifact",
                str(SCORER),
                "--models",
                str(models),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    report = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert report["rules_ne_cheapest_rate"] == 0.0
    assert report["cost_slice"]["rules_ne_cheapest_rate"] == 1.0
    assert report["cost_slice"]["rules_cost_delta"] < 0
    assert report["cost_slice"]["savings_vs_most_expensive"] > 0
    assert report["savings_vs_most_expensive"] >= 0.0
    assert report["rules_cost_delta_where_rules_ne_cheapest"] is None
    assert report["path"] == "shadow"
    assert report["not_spec_floors"] is True
    assert report["replay_gate_pass"] is False
    assert "path=shadow" in out
    assert os.getenv("TRAINED_PATH") != "trained"


def test_replay_gbdt_artifact_prints_prefer_logistic(tmp_path, capsys, monkeypatch):
    import yaml

    monkeypatch.delenv("TRAINED_PATH", raising=False)
    artifact = dict(_artifact())
    artifact["gbdt"] = {
        "cheap/flash": {
            "intercept": 0.0,
            "trees": [{"feature": 2, "threshold": 4.8, "left": 0.0, "right": 1.0}],
        }
    }
    path = tmp_path / "scorer-gbdt.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    models = tmp_path / "models.yaml"
    models.write_text(yaml.safe_dump(_toy_cfg()), encoding="utf-8")
    assert main(["--gold", str(GOLD), "--artifact", str(path), "--models", str(models)]) == 0
    out = capsys.readouterr().out.lower()
    assert "prefer_logistic" in out
    assert "scorer-logistic" in out or "logistic" in out


def test_replay_gate_passes_when_trained_costs_more_than_rules_but_saves_vs_expensive():
    """Quality-first spend vs rules is not a fail if savings vs most_expensive_eligible > 0."""
    report = _bars_green()
    report["rules_cost_delta"] = 0.000687
    report["rules_cost_delta_where_rules_ne_cheapest"] = 0.000687
    report["rules_ne_cheapest_rate"] = 0.78
    report["savings_vs_most_expensive"] = 0.0009
    assert replay_gate_pass(report) is True


def test_replay_gate_ignores_rules_cost_delta_when_rules_already_cheapest():
    report = _bars_green()
    report["rules_ne_cheapest_rate"] = 0.0
    report["rules_cost_delta"] = 0.0
    report["rules_cost_delta_where_rules_ne_cheapest"] = None
    report["savings_vs_most_expensive"] = 0.002
    assert replay_gate_pass(report) is True


def test_replay_gate_fails_zero_savings_vs_most_expensive():
    report = _bars_green()
    report["rules_cost_delta"] = -0.01
    report["savings_vs_most_expensive"] = 0.0
    assert replay_gate_pass(report) is False


def test_parity_posture_never_claims_production_parity():
    out = apply_replay_gate(_bars_green())
    assert out["local_replay_gate_pass"] is True
    assert out["production_parity"] is False
    assert out["promotion_tier"] == "shadow_local_pass"
    assert "not_spec_floors" in out["parity_blockers"]
    assert "no_session_gold_promotion_gate" in out["parity_blockers"]


def test_parity_posture_lists_rules_cost_delta_when_trained_costs_more():
    report = _bars_green()
    report["rules_cost_delta"] = 0.000687
    out = apply_replay_gate(report)
    assert out["local_replay_gate_pass"] is True
    assert "rules_cost_delta_not_negative" in out["parity_blockers"]


def test_parity_posture_tier_fails_when_local_gate_fails():
    report = _bars_green()
    report["rank_auc"] = 0.64
    out = apply_replay_gate(report)
    assert out["local_replay_gate_pass"] is False
    assert out["promotion_tier"] == "shadow_local_fail"
