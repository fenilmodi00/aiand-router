from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seed15_resume_preflight.py"
SPEC = importlib.util.spec_from_file_location("seed15_resume_preflight", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_report_ready_when_inputs_exist(tmp_path, monkeypatch):
    spend = tmp_path / "spend.txt"
    spend.write_text("12.43\n", encoding="utf-8")
    pool = tmp_path / "pool.jsonl"
    pool.write_text('{"prompt":"x"}\n', encoding="utf-8")
    runner = tmp_path / "run_hard_y_probe.ps1"
    runner.write_text("Write-Host ok\n", encoding="utf-8")
    monkeypatch.setenv("AIAND_API_KEY", "test-key")
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "powershell.exe")

    report = MODULE.build_report(spend_path=spend, pool_path=pool, runner_path=runner)

    assert report["spend_usd"] == 12.43
    assert report["budget_limit_usd"] == 27.43
    assert report["exact_seed15_command_runnable"] is True
    assert report["blockers"] == []
    assert "-Seed 15 -Limit 32" in report["paid_seed15_command"]


def test_build_report_blocks_when_key_or_pool_missing(tmp_path, monkeypatch):
    spend = tmp_path / "spend.txt"
    spend.write_text("8.16\n", encoding="utf-8")
    runner = tmp_path / "run_hard_y_probe.ps1"
    runner.write_text("Write-Host ok\n", encoding="utf-8")
    monkeypatch.setenv("AIAND_API_KEY", "")
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "powershell.exe")

    report = MODULE.build_report(
        spend_path=spend,
        pool_path=tmp_path / "missing-pool.jsonl",
        runner_path=runner,
    )

    assert report["budget_limit_usd"] == 23.16
    assert report["exact_seed15_command_runnable"] is False
    assert "AIAND_API_KEY is missing" in report["blockers"]
    assert any("required pool file missing" in item for item in report["blockers"])
