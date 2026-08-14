from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiand_router.replay_report import (
    assert_not_production_floors,
    main,
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
    return replay_report(GOLD, _artifact(), load_models(cfg), cfg, **kwargs)


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
    report = _report()
    assert isinstance(replay_gate_pass(report), bool)


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
