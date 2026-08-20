from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiand_router.lite_runner import (
    _load_fixture,
    format_comparison_report,
    main,
    summarize_comparison,
)

ROOT = Path(__file__).resolve().parents[1]
CHECKED_IN_COMPARISON = ROOT / "tests" / "fixtures" / "lite_comparison" / "fixture.json"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_lite_runner_legacy_fixture_keeps_single_resolved_shape(tmp_path):
    fixture = [
        {
            "instance_id": "legacy-pass",
            "module": "fix.py",
            "tests": "from fix import fix\n\ndef test_fix():\n    assert fix() == 42\n",
            "patch": "def fix():\n    return 42\n",
        }
    ]
    fixture_path = tmp_path / "fixture.json"
    out_path = tmp_path / "out.jsonl"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    assert main(["--fixture", str(fixture_path), "--out", str(out_path), "--n", "10"]) == 0

    rows = _read_jsonl(out_path)
    assert rows == [
        {
            "instance_id": "legacy-pass",
            "resolved": True,
            "label_type": "harness_proxy",
        }
    ]


def test_lite_runner_comparison_fixture_emits_rules_and_trained_outcomes(tmp_path):
    fixture = [
        {
            "instance_id": "cmp-001",
            "module": "solve.py",
            "tests": "from solve import answer\n\ndef test_answer():\n    assert answer() == 42\n",
            "policies": {
                "rules": {"patch": "def answer():\n    return 0\n"},
                "trained": {"patch": "def answer():\n    return 42\n"},
            },
        }
    ]
    fixture_path = tmp_path / "fixture.json"
    out_path = tmp_path / "out.jsonl"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    assert main(["--fixture", str(fixture_path), "--out", str(out_path), "--n", "10"]) == 0

    rows = _read_jsonl(out_path)
    assert rows == [
        {
            "instance_id": "cmp-001",
            "label_type": "harness_proxy",
            "comparison_mode": "fixture_replay",
            "policies": {
                "rules": {"resolved": False},
                "trained": {"resolved": True},
            },
        }
    ]
    assert "resolved" not in rows[0]


def test_lite_runner_rejects_empty_policy_map(tmp_path):
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps([{"instance_id": "cmp-001", "policies": {}}]), encoding="utf-8")

    with pytest.raises(ValueError, match="empty or invalid policies"):
        _load_fixture(str(fixture_path))


def test_checked_in_comparison_fixture_has_dual_policies():
    rows = _load_fixture(str(CHECKED_IN_COMPARISON))
    assert len(rows) >= 8
    for row in rows:
        policies = row["policies"]
        assert set(policies) >= {"rules", "trained"}
        assert "patch" in policies["rules"]
        assert "patch" in policies["trained"]
        assert row.get("module")
        assert row.get("tests")


def test_checked_in_comparison_fixture_run_and_report(tmp_path):
    out_path = tmp_path / "out.jsonl"
    assert main(["--fixture", str(CHECKED_IN_COMPARISON), "--out", str(out_path), "--n", "50"]) == 0
    rows = _read_jsonl(out_path)
    assert len(rows) == len(_load_fixture(str(CHECKED_IN_COMPARISON)))
    assert all(r.get("comparison_mode") == "fixture_replay" for r in rows)
    assert all(r.get("label_type") == "harness_proxy" for r in rows)

    summary = summarize_comparison(rows)
    assert summary["verdict"] == "bounded_check_only"
    assert summary["production_parity"] is False
    assert summary["session_gold"] is False
    assert summary["n"] == len(rows)
    assert summary["rules_resolved"] + summary["trained_resolved"] >= 1
    # Meaningful divergence: not identical policy outcomes across the slice.
    assert summary["rules_resolved"] != summary["trained_resolved"]
    assert summary["trained_only"] + summary["rules_only"] >= 1

    report = format_comparison_report(summary, fixture_path=str(CHECKED_IN_COMPARISON.as_posix()))
    assert "bounded_check_only" in report
    assert "production_parity=false" in report
    assert "harness-proxy" in report.lower() or "harness_proxy" in report


def test_summarize_comparison_empty():
    summary = summarize_comparison([])
    assert summary["n"] == 0
    assert summary["rules_resolve_rate"] is None
    assert summary["verdict"] == "bounded_check_only"


def test_run_lite_comparison_script_writes_report(tmp_path):
    import importlib.util

    script_path = ROOT / "scripts" / "run_lite_comparison.py"
    spec = importlib.util.spec_from_file_location("run_lite_comparison", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    out = tmp_path / "results.jsonl"
    report = tmp_path / "report.md"
    summary = mod.run(CHECKED_IN_COMPARISON, out, report, n=50)
    assert out.exists()
    assert report.exists()
    assert report.with_suffix(".json").exists()
    text = report.read_text(encoding="utf-8")
    assert "bounded_check_only" in text
    assert summary["n"] >= 8
    assert "TRAINED_PATH" in text


def test_ids_only_verified_scaffold_no_http(tmp_path, monkeypatch):
    from aiand_router import lite_runner

    fake = [f"repo__pkg-{i}" for i in range(12)]

    def _fake_fetch(bench, n=30, cap=None, cache_dir="data/lite_cache"):
        assert bench == "verified"
        return fake[:n]

    monkeypatch.setattr(lite_runner, "fetch_bench_ids", _fake_fetch)
    out = tmp_path / "verified_ids.json"
    assert main(["--ids-only", "--bench", "verified", "--n", "10", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["verdict"] == "ids_scaffold_only"
    assert data["session_gold"] is False
    assert data["production_parity"] is False
    assert data["paid_http_required"] is True
    assert data["n"] == 10
    assert data["instance_ids"] == fake[:10]
