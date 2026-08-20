from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiand_router.promotion_gate import (
    VERIFIED_PRIMARY_N,
    build_gate_checklist,
    format_promotion_report,
    load_ids_scaffold,
    promotion_readiness,
    validate_ids_scaffold,
)

ROOT = Path(__file__).resolve().parents[1]
CHECKED_IN_SCAFFOLD = ROOT / "data" / "verified_ids_scaffold.json"


def _minimal_scaffold(n: int = 500) -> dict:
    ids = [f"repo__pkg-{i}" for i in range(n)]
    return {
        "verdict": "ids_scaffold_only",
        "bench": "verified",
        "n": n,
        "session_gold": False,
        "production_parity": False,
        "paid_http_required": True,
        "instance_ids": ids,
    }


def test_validate_ids_scaffold_accepts_checked_in_shape():
    if not CHECKED_IN_SCAFFOLD.exists():
        pytest.skip("checked-in scaffold missing")
    scaffold = load_ids_scaffold(CHECKED_IN_SCAFFOLD)
    errors = validate_ids_scaffold(scaffold)
    assert errors == []
    assert scaffold["n"] >= 300
    assert scaffold["session_gold"] is False


def test_validate_ids_scaffold_rejects_bad_verdict():
    scaffold = _minimal_scaffold(10)
    scaffold["verdict"] = "bounded_check_only"
    errors = validate_ids_scaffold(scaffold)
    assert any("verdict" in e for e in errors)


def test_validate_ids_scaffold_rejects_session_gold_true():
    scaffold = _minimal_scaffold(10)
    scaffold["session_gold"] = True
    errors = validate_ids_scaffold(scaffold)
    assert any("session_gold" in e for e in errors)


def test_validate_ids_scaffold_rejects_below_floor():
    scaffold = _minimal_scaffold(50)
    errors = validate_ids_scaffold(scaffold)
    assert any("below session-gold floor" in e for e in errors)


def test_gate_checklist_marks_session_quality_not_started():
    scaffold = _minimal_scaffold()
    rows = build_gate_checklist(scaffold=scaffold, scaffold_errors=[])
    by_id = {r["id"]: r for r in rows}
    assert by_id["quality_session_gold"]["status"] == "not_started"
    assert by_id["floor_session_gold_n"]["status"] in {
        "scaffold_only",
        "scaffold_only_remote_ready",
        "scaffold_only_remote_auth_pending",
    }


def test_resolve_backend_posture_distinguishes_floor_paths():
    from aiand_router.promotion_gate import resolve_backend_posture

    posture = resolve_backend_posture()
    assert "local_image_farm" in posture["floor_paths"]
    assert "remote_eval" in posture["floor_paths"]
    assert posture["floor_paths"]["local_image_farm"]["scale_ready_on_this_host"] is False
    assert posture["local"]["floor_path"] == "local_image_farm"
    # Modal may or may not be auth'd; structure must be honest either way.
    assert "configured" in posture["modal"]
    assert "configured" in posture["sb_cli"]
    assert isinstance(posture["remote_eval_ready"], bool)


def test_floor_bar_embeds_local_vs_remote_paths():
    scaffold = _minimal_scaffold()
    posture = {
        "remote_eval_ready": False,
        "floor_paths": {
            "local_image_farm": {
                "scale_ready_on_this_host": False,
                "blocker": "disk_blocked_no_mass_pull",
            },
            "remote_eval": {
                "scale_ready_on_this_host": False,
                "blocker": "auth_pending_modal_or_sb_cli",
            },
        },
    }
    live = {"n_session_gold": 10, "floor_n": 300, "below_floor": True}
    rows = build_gate_checklist(
        scaffold=scaffold,
        scaffold_errors=[],
        resolve_posture=posture,
        live_sessions=live,
    )
    floor = {r["id"]: r for r in rows}["floor_session_gold_n"]
    assert floor["status"] == "scaffold_only_remote_auth_pending"
    assert "local_image_farm" in floor["detail"]
    assert "remote_eval" in floor["detail"]
    assert floor["floor_paths"]["local_image_farm"]["blocker"] == "disk_blocked_no_mass_pull"


def test_gate_checklist_cost_proxy_from_local_snapshot():
    scaffold = _minimal_scaffold()
    local = {"rules_cost_delta": 0.001, "n_prompts": 89}
    rows = build_gate_checklist(scaffold=scaffold, scaffold_errors=[], local=local)
    by_id = {r["id"]: r for r in rows}
    assert by_id["cost_rules_delta"]["status"] == "proxy_fail"


def test_promotion_readiness_report_honesty(tmp_path):
    scaffold_path = tmp_path / "scaffold.json"
    scaffold_path.write_text(json.dumps(_minimal_scaffold()), encoding="utf-8")
    report = promotion_readiness(
        scaffold_path=scaffold_path,
        artifact_path=ROOT / "data" / "scorer-hard-logistic.json",
        gold_path=ROOT / "data" / "gold-verified.jsonl",
    )
    assert report["verdict"] == "promotion_readiness_unpaid"
    assert report["session_gold"] is False
    assert report["production_parity"] is False
    assert report["prototype_ready"] is True
    assert report["do_not_flip_trained_path"] is True
    assert report["scaffold_valid"] is True
    assert report["local_replay"] is not None
    assert report["resolve_backend"]["floor_paths"]["remote_eval"]
    assert report["budget_estimate"]["n_instances"] == VERIFIED_PRIMARY_N
    md = format_promotion_report(report)
    assert "Does **not** flip `TRAINED_PATH=trained`" in md
    assert "local_image_farm" in md
    assert "remote_eval" in md
    assert "bounded_check_only" in md or "run_lite_comparison" in md
    assert any(gap for gap in report["code_gaps"] if "remote_eval" in gap or "session-gold" in gap)


def test_lite_runner_promotion_readiness_flag(tmp_path, monkeypatch):
    from aiand_router import lite_runner

    scaffold = _minimal_scaffold(10)
    out = tmp_path / "scaffold.json"
    out.write_text(json.dumps(scaffold), encoding="utf-8")
    calls: list[list[str]] = []

    def _fake_promotion_main(argv):
        calls.append(list(argv))
        return 0

    import aiand_router.promotion_gate as promotion_gate

    monkeypatch.setattr(promotion_gate, "main", _fake_promotion_main)
    rc = lite_runner.main(["--promotion-readiness", "--out", str(out)])
    assert rc == 0
    assert calls and str(out) in calls[0]


def test_run_promotion_readiness_script(tmp_path):
    import importlib.util

    script_path = ROOT / "scripts" / "run_promotion_readiness.py"
    spec = importlib.util.spec_from_file_location("run_promotion_readiness", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    scaffold = tmp_path / "scaffold.json"
    scaffold.write_text(json.dumps(_minimal_scaffold()), encoding="utf-8")
    report_path = tmp_path / "report.md"
    rc = mod.main(
        [
            "--scaffold",
            str(scaffold),
            "--report",
            str(report_path),
            "--stdout-only",
        ]
    )
    assert rc == 0
    assert report_path.exists() is False  # stdout-only skips default write
