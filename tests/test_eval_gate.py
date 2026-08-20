from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiand_router.eval import promotion_gate_verdict

ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_promotion_gate_verdict_bounded_when_below_floor(tmp_path):
    log = tmp_path / "requests.jsonl"
    sessions = tmp_path / "sessions.jsonl"
    _write_jsonl(
        log,
        [
            {
                "path": "shadow",
                "phase": "edit",
                "selected": "deepseek-ai/deepseek-v4-flash",
                "trained_selected": "moonshotai/kimi-k2.7-code",
                "trained_confidence": 0.72,
                "rules_cost_delta_usd": -0.001,
                "tests_passed": True,
                "cost_usd": 0.0002,
                "tokens_out": 120,
                "status": 200,
            }
        ],
    )
    _write_jsonl(
        sessions,
        [
            {
                "instance_id": "a__b-1",
                "session_gold": True,
                "comparison_mode": "shadow_dual_policy",
                "policies": {
                    "rules": {"resolved": True},
                    "trained": {"resolved": True},
                },
            }
        ],
    )
    report = promotion_gate_verdict(log, session_path=sessions)
    assert report["verdict"] == "bounded_check_only"
    assert report["session_gold"] is True
    assert report["bars"]["cost_rules_delta"]["pass"] is True
    assert report["bars"]["cost_rules_delta"]["session_joined"] is False
    assert "lack session_id" in report["bars"]["cost_rules_delta"]["detail"]
    assert report["bars"]["floor_session_gold_n"]["pass"] is False
    assert report["do_not_flip_trained_path"] is True


def test_promotion_gate_verdict_trained_quality_needs_dual_policy_sessions(tmp_path):
    log = tmp_path / "requests.jsonl"
    sessions = tmp_path / "sessions.jsonl"
    _write_jsonl(log, [])
    _write_jsonl(
        sessions,
        [
            {
                "instance_id": f"a__b-{i}",
                "session_gold": True,
                "policies": {"rules": {"resolved": i % 2 == 0}},
            }
            for i in range(320)
        ],
    )
    report = promotion_gate_verdict(log, session_path=sessions)
    assert report["bars"]["floor_session_gold_n"]["pass"] is True
    assert report["bars"]["quality_session_gold"]["pass"] is None
    assert report["bars"]["quality_session_gold"]["trained_resolve_rate"] is None


def test_promotion_gate_verdict_zero_trained_resolve_rate_is_valid(tmp_path):
    """Dual-policy rows with all trained unresolved → rate 0.0, not null."""
    log = tmp_path / "requests.jsonl"
    sessions = tmp_path / "sessions.jsonl"
    _write_jsonl(log, [])
    _write_jsonl(
        sessions,
        [
            {
                "instance_id": f"a__b-{i}",
                "session_gold": True,
                "comparison_mode": "shadow_dual_policy",
                "policies": {
                    "rules": {"resolved": False},
                    "trained": {"counterfactual": True, "resolved": False},
                },
            }
            for i in range(10)
        ],
    )
    report = promotion_gate_verdict(log, session_path=sessions)
    q = report["bars"]["quality_session_gold"]
    assert q["trained_resolve_rate"] == 0.0
    assert q["rules_resolve_rate"] == 0.0
    assert q["pass"] is True  # 0.0 within 1pp of rules 0.0
    assert "requires dual-policy" not in q["detail"]


def test_promotion_gate_verdict_unlabeled_resolve_is_not_zero(tmp_path):
    """needs_swe_eval (resolved=null) must not look like a measured 0% resolve."""
    log = tmp_path / "requests.jsonl"
    sessions = tmp_path / "sessions.jsonl"
    _write_jsonl(log, [])
    _write_jsonl(
        sessions,
        [
            {
                "instance_id": f"a__b-{i}",
                "session_gold": False,
                "label_type": "needs_swe_eval",
                "comparison_mode": "shadow_dual_policy",
                "policies": {
                    "rules": {"resolved": None, "label_type": "needs_swe_eval"},
                    "trained": {
                        "counterfactual": True,
                        "resolved": None,
                        "label_type": "needs_swe_eval",
                    },
                },
            }
            for i in range(10)
        ],
    )
    report = promotion_gate_verdict(log, session_path=sessions)
    q = report["bars"]["quality_session_gold"]
    assert q["trained_resolve_rate"] is None
    assert q["rules_resolve_rate"] is None
    assert q["pass"] is None
    assert report["session_gold"] is False
    assert report["n_unlabeled_sessions"] == 10
    assert "unlabeled" in q["detail"]


def test_promotion_gate_cost_joins_session_gold_when_session_id_present(tmp_path):
    log = tmp_path / "requests.jsonl"
    sessions = tmp_path / "sessions.jsonl"
    _write_jsonl(
        log,
        [
            {
                "path": "shadow",
                "session_id": "django__django-11099",
                "rules_cost_delta_usd": -0.002,
                "selected": "deepseek-ai/deepseek-v4-flash",
                "status": 200,
                "tokens_out": 10,
            },
            {
                "path": "shadow",
                "session_id": "django__django-11099::cf-trained",
                "rules_cost_delta_usd": -0.004,
                "selected": "moonshotai/kimi-k2.7-code",
                "status": 200,
                "tokens_out": 10,
            },
            {
                "path": "shadow",
                "session_id": "other__unrelated-1",
                "rules_cost_delta_usd": 0.05,
                "selected": "moonshotai/kimi-k2.7-code",
                "status": 200,
                "tokens_out": 10,
            },
            {
                "path": "shadow",
                # historical hop without session_id — excluded from join
                "rules_cost_delta_usd": 0.99,
                "selected": "moonshotai/kimi-k2.7-code",
                "status": 200,
                "tokens_out": 10,
            },
        ],
    )
    _write_jsonl(
        sessions,
        [
            {
                "instance_id": "django__django-11099",
                "session_id": "django__django-11099",
                "session_gold": True,
                "policies": {
                    "rules": {"resolved": True},
                    "trained": {"resolved": True},
                },
            }
        ],
    )
    report = promotion_gate_verdict(log, session_path=sessions)
    cost = report["bars"]["cost_rules_delta"]
    assert cost["session_joined"] is True
    assert cost["n_joinable_hops"] == 2
    assert cost["n_hops_with_session_id"] == 3
    assert cost["rules_cost_delta"] == pytest.approx((-0.002 + -0.004) / 2)
    assert cost["pass"] is True
    assert "session-gold" in cost["detail"]


def test_promotion_gate_cost_honest_when_historical_log_lacks_session_id(tmp_path):
    log = tmp_path / "requests.jsonl"
    sessions = tmp_path / "sessions.jsonl"
    _write_jsonl(
        log,
        [
            {
                "path": "shadow",
                "rules_cost_delta_usd": -0.001,
                "selected": "deepseek-ai/deepseek-v4-flash",
                "status": 200,
                "tokens_out": 10,
            }
        ],
    )
    _write_jsonl(
        sessions,
        [
            {
                "instance_id": "django__django-11099",
                "session_id": "django__django-11099",
                "session_gold": True,
                "policies": {
                    "rules": {"resolved": True},
                    "trained": {"resolved": True},
                },
            }
        ],
    )
    report = promotion_gate_verdict(log, session_path=sessions)
    cost = report["bars"]["cost_rules_delta"]
    assert cost["session_joined"] is False
    assert cost["n_joinable_hops"] == 0
    assert cost["n_hops_with_session_id"] == 0
    assert cost["rules_cost_delta"] == pytest.approx(-0.001)
    assert "lack session_id" in cost["detail"]
    assert "will join" in cost["detail"]


def test_promotion_gate_cost_none_when_session_ids_do_not_join(tmp_path):
    log = tmp_path / "requests.jsonl"
    sessions = tmp_path / "sessions.jsonl"
    _write_jsonl(
        log,
        [
            {
                "path": "shadow",
                "session_id": "other__session-9",
                "rules_cost_delta_usd": -0.001,
                "selected": "deepseek-ai/deepseek-v4-flash",
                "status": 200,
                "tokens_out": 10,
            }
        ],
    )
    _write_jsonl(
        sessions,
        [
            {
                "instance_id": "django__django-11099",
                "session_id": "django__django-11099",
                "session_gold": True,
                "policies": {
                    "rules": {"resolved": True},
                    "trained": {"resolved": True},
                },
            }
        ],
    )
    report = promotion_gate_verdict(log, session_path=sessions)
    cost = report["bars"]["cost_rules_delta"]
    assert cost["session_joined"] is False
    assert cost["n_joinable_hops"] == 0
    assert cost["rules_cost_delta"] is None
    assert cost["pass"] is False
    assert "no request-log hops join" in cost["detail"]
