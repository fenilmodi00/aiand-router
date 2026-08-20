#!/usr/bin/env python
"""Unit tests for scripts/swe_eval_cmd.py (no docker required)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "swe_eval_cmd.py"


def _load_mod():
    spec = importlib.util.spec_from_file_location("swe_eval_cmd", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(*extra: str, patch_text: str = "diff --git a/f b/f\n") -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".patch", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(patch_text)
        patch_path = handle.name
    try:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--instance",
                "django__django-11099",
                "--patch",
                patch_path,
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        Path(patch_path).unlink(missing_ok=True)


def test_default_dataset_is_swebench_org_verified():
    mod = _load_mod()
    assert mod.DEFAULT_DATASET_NAME == "SWE-bench/SWE-bench_Verified"
    assert "princeton-nlp" not in mod.DEFAULT_DATASET_NAME


def test_help_lists_correct_dataset():
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert proc.returncode == 0
    help_text = (proc.stdout + proc.stderr).replace("\n", " ")
    assert "SWE-bench_Verified" in help_text
    assert "--dataset-name" in help_text
    # Default must not advertise the legacy princeton-nlp id as primary.
    assert "default: SWE-bench/SWE-bench_Verified" in help_text or (
        "SWE-bench/" in help_text and "SWE-bench_Verified" in help_text
    )


def test_resolved_from_summary_report():
    mod = _load_mod()
    summary = {
        "resolved_ids": ["django__django-11099"],
        "completed_ids": ["django__django-11099"],
        "unresolved_ids": [],
    }
    assert mod._resolved_from_report(summary, "django__django-11099") is True
    summary_fail = {
        "resolved_ids": [],
        "completed_ids": ["django__django-11099"],
        "unresolved_ids": ["django__django-11099"],
    }
    assert mod._resolved_from_report(summary_fail, "django__django-11099") is False
    # error_ids must stay unlabeled (not fake measured fail)
    summary_err = {
        "resolved_ids": [],
        "completed_ids": [],
        "unresolved_ids": [],
        "error_ids": ["django__django-11099"],
    }
    assert mod._resolved_from_report(summary_err, "django__django-11099") is None
    assert (
        mod._summary_instance_reason(summary_err, "django__django-11099")
        == "swebench_instance_error"
    )


def test_resolved_from_per_instance_report():
    mod = _load_mod()
    per = {"django__django-11099": {"resolved": True, "patch_exists": True}}
    assert mod._resolved_from_report(per, "django__django-11099") is True
    per_fail = {"django__django-11099": {"resolved": False}}
    assert mod._resolved_from_report(per_fail, "django__django-11099") is False
    assert mod._resolved_from_report({}, "django__django-11099") is None


def test_collect_report_paths_prefers_summary(tmp_path: Path):
    mod = _load_mod()
    run_id = "aiand_swe_eval"
    summary = tmp_path / f"aiand-router.{run_id}.json"
    summary.write_text("{}", encoding="utf-8")
    inst = (
        tmp_path
        / "logs"
        / "run_evaluation"
        / run_id
        / "aiand-router"
        / "django__django-11099"
        / "report.json"
    )
    inst.parent.mkdir(parents=True)
    inst.write_text("{}", encoding="utf-8")
    paths = mod._collect_report_paths(tmp_path, run_id, "aiand-router")
    assert paths[0] == summary
    assert inst in paths


def test_mock_resolved_true():
    proc = _run("--mock-resolved", "true")
    assert proc.returncode == 0
    obj = json.loads(proc.stdout.strip())
    assert obj["resolved"] is True
    assert obj["status"] == "mock"


def test_mock_resolved_false():
    proc = _run("--mock-resolved", "false")
    assert proc.returncode == 0
    obj = json.loads(proc.stdout.strip())
    assert obj["resolved"] is False
    assert obj["status"] == "mock"


def test_crlf_eval_script_detection():
    mod = _load_mod()
    assert mod._crlf_eval_script_failure("set: pipefail\r: invalid option name")
    assert mod._crlf_eval_script_failure("cd: $'/testbed\r': No such file")
    assert not mod._crlf_eval_script_failure("ModuleNotFoundError: No module named django")


def test_harness_bootstrap_forces_lf_and_utf8():
    mod = _load_mod()
    src = mod._harness_bootstrap_src().replace(
        "%ARGS%", '"swebench.harness.run_evaluation", "--run_id", "x"'
    )
    assert 'newline = "\\n"' in src
    assert 'encoding = "utf-8"' in src
    assert "runpy.run_module" in src


def test_empty_patch_is_not_available_when_ready(monkeypatch, capsys):
    """Empty patch must not fake-resolve; short-circuit before harness when docker+pkg ok."""
    mod = _load_mod()
    monkeypatch.setattr(mod, "_docker_ok", lambda: True)
    monkeypatch.setattr(mod, "_swebench_importable", lambda: True)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".patch", delete=False, encoding="utf-8"
    ) as handle:
        handle.write("")
        patch_path = Path(handle.name)
    try:
        code = mod.main(
            ["--instance", "django__django-11099", "--patch", str(patch_path)]
        )
    finally:
        patch_path.unlink(missing_ok=True)
    assert code == 2
    obj = json.loads(capsys.readouterr().out.strip())
    assert obj["reason"] == "empty_patch"


def test_default_emits_not_available_without_swebench(monkeypatch, capsys):
    """Force missing package so this stays a fast unpaid unit test (no live harness)."""
    mod = _load_mod()
    monkeypatch.setattr(mod, "_docker_ok", lambda: True)
    monkeypatch.setattr(mod, "_swebench_importable", lambda: False)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".patch", delete=False, encoding="utf-8"
    ) as handle:
        handle.write("diff --git a/f b/f\n")
        patch_path = Path(handle.name)
    try:
        code = mod.main(
            ["--instance", "django__django-11099", "--patch", str(patch_path)]
        )
    finally:
        patch_path.unlink(missing_ok=True)
    assert code == 2
    obj = json.loads(capsys.readouterr().out.strip())
    assert obj["resolved"] is None
    assert obj["status"] == "not_available"
    assert obj["reason"] == "swebench_package_missing"


def test_resolve_backend_default_local(monkeypatch):
    mod = _load_mod()
    monkeypatch.delenv("SWE_EVAL_BACKEND", raising=False)
    assert mod.resolve_backend() == "local"


def test_resolve_backend_from_env(monkeypatch):
    mod = _load_mod()
    monkeypatch.setenv("SWE_EVAL_BACKEND", "modal")
    assert mod.resolve_backend() == "modal"
    monkeypatch.setenv("SWE_EVAL_BACKEND", "sb_cli")
    assert mod.resolve_backend() == "sb-cli"


def test_resolve_backend_cli_overrides_env(monkeypatch):
    mod = _load_mod()
    monkeypatch.setenv("SWE_EVAL_BACKEND", "modal")
    assert mod.resolve_backend(cli_backend="sb-cli") == "sb-cli"


def test_invalid_backend_not_available(monkeypatch, capsys):
    mod = _load_mod()
    monkeypatch.setenv("SWE_EVAL_BACKEND", "spaceship")
    with tempfile.NamedTemporaryFile(
        "w", suffix=".patch", delete=False, encoding="utf-8"
    ) as handle:
        handle.write("diff --git a/f b/f\n")
        patch_path = Path(handle.name)
    try:
        code = mod.main(
            ["--instance", "django__django-11099", "--patch", str(patch_path)]
        )
    finally:
        patch_path.unlink(missing_ok=True)
    assert code == 2
    obj = json.loads(capsys.readouterr().out.strip())
    assert obj["reason"] == "invalid_backend"
    assert obj["resolved"] is None


def test_modal_not_configured_is_honest(monkeypatch, capsys):
    mod = _load_mod()
    monkeypatch.setattr(mod, "_swebench_importable", lambda: True)
    monkeypatch.setattr(mod, "_modal_importable", lambda: True)
    monkeypatch.setattr(mod, "_modal_configured", lambda: False)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".patch", delete=False, encoding="utf-8"
    ) as handle:
        handle.write("diff --git a/f b/f\n")
        patch_path = Path(handle.name)
    try:
        code = mod.main(
            [
                "--backend",
                "modal",
                "--instance",
                "django__django-11099",
                "--patch",
                str(patch_path),
            ]
        )
    finally:
        patch_path.unlink(missing_ok=True)
    assert code == 2
    obj = json.loads(capsys.readouterr().out.strip())
    assert obj["resolved"] is None
    assert obj["reason"] == "modal_not_configured"
    assert obj["backend"] == "modal"


def test_sb_cli_missing_api_key_is_honest(monkeypatch, capsys):
    mod = _load_mod()
    monkeypatch.setattr(mod, "_sb_cli_cmd_prefix", lambda: ["sb-cli"])
    monkeypatch.delenv("SWEBENCH_API_KEY", raising=False)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".patch", delete=False, encoding="utf-8"
    ) as handle:
        handle.write("diff --git a/f b/f\n")
        patch_path = Path(handle.name)
    try:
        code = mod.main(
            [
                "--backend",
                "sb-cli",
                "--instance",
                "django__django-11099",
                "--patch",
                str(patch_path),
            ]
        )
    finally:
        patch_path.unlink(missing_ok=True)
    assert code == 2
    obj = json.loads(capsys.readouterr().out.strip())
    assert obj["resolved"] is None
    assert obj["reason"] == "sb_cli_not_configured"


def test_sb_cli_missing_binary_is_honest(monkeypatch, capsys):
    mod = _load_mod()
    monkeypatch.setattr(mod, "_sb_cli_cmd_prefix", lambda: None)
    monkeypatch.setenv("SWEBENCH_API_KEY", "fake-key")
    with tempfile.NamedTemporaryFile(
        "w", suffix=".patch", delete=False, encoding="utf-8"
    ) as handle:
        handle.write("diff --git a/f b/f\n")
        patch_path = Path(handle.name)
    try:
        code = mod.main(
            [
                "--backend",
                "sb-cli",
                "--instance",
                "django__django-11099",
                "--patch",
                str(patch_path),
            ]
        )
    finally:
        patch_path.unlink(missing_ok=True)
    assert code == 2
    obj = json.loads(capsys.readouterr().out.strip())
    assert obj["reason"] == "sb_cli_missing"


def test_modal_mock_remote_success(monkeypatch, capsys):
    mod = _load_mod()
    monkeypatch.setattr(mod, "_swebench_importable", lambda: True)
    monkeypatch.setattr(mod, "_modal_importable", lambda: True)
    monkeypatch.setattr(mod, "_modal_configured", lambda: True)

    def fake_run(instance_id, patch_path, *, run_id, dataset_name, modal=False):
        assert modal is True
        assert instance_id == "django__django-11099"
        return mod._emit(
            {
                "resolved": True,
                "status": "ok",
                "source": "swebench.harness.run_evaluation[modal]",
                "backend": "modal",
                "instance_id": instance_id,
            },
            code=0,
        )

    monkeypatch.setattr(mod, "_run_swebench_one", fake_run)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".patch", delete=False, encoding="utf-8"
    ) as handle:
        handle.write("diff --git a/f b/f\n")
        patch_path = Path(handle.name)
    try:
        code = mod.main(
            [
                "--backend",
                "modal",
                "--instance",
                "django__django-11099",
                "--patch",
                str(patch_path),
            ]
        )
    finally:
        patch_path.unlink(missing_ok=True)
    assert code == 0
    obj = json.loads(capsys.readouterr().out.strip())
    assert obj["resolved"] is True
    assert obj["backend"] == "modal"


def test_sb_cli_mock_remote_fail(monkeypatch, capsys):
    mod = _load_mod()
    monkeypatch.setattr(mod, "_sb_cli_cmd_prefix", lambda: ["sb-cli"])
    monkeypatch.setenv("SWEBENCH_API_KEY", "fake-key")

    def fake_sb(instance_id, patch_path, *, run_id, cmd_prefix):
        return mod._emit(
            {
                "resolved": False,
                "status": "ok",
                "source": "sb-cli submit",
                "backend": "sb-cli",
                "instance_id": instance_id,
            },
            code=0,
        )

    monkeypatch.setattr(mod, "_run_sb_cli_one", fake_sb)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".patch", delete=False, encoding="utf-8"
    ) as handle:
        handle.write("diff --git a/f b/f\n")
        patch_path = Path(handle.name)
    try:
        code = mod.main(
            [
                "--backend",
                "sb-cli",
                "--instance",
                "django__django-11099",
                "--patch",
                str(patch_path),
            ]
        )
    finally:
        patch_path.unlink(missing_ok=True)
    assert code == 0
    obj = json.loads(capsys.readouterr().out.strip())
    assert obj["resolved"] is False
    assert obj["backend"] == "sb-cli"


def test_collect_sb_cli_report_paths(tmp_path: Path):
    mod = _load_mod()
    run_id = "aiand_sb-cli_django__django-11099_abc"
    exact = tmp_path / f"swe-bench_verified__test__{run_id}.json"
    exact.write_text("{}", encoding="utf-8")
    paths = mod._collect_sb_cli_report_paths(tmp_path, run_id)
    assert exact in paths


def test_remote_run_id_stable_for_same_patch():
    mod = _load_mod()
    a = mod._remote_run_id("django__django-11099", "diff --git a/f b/f\n", prefix="aiand_modal")
    b = mod._remote_run_id("django__django-11099", "diff --git a/f b/f\n", prefix="aiand_modal")
    c = mod._remote_run_id("django__django-11099", "diff --git a/g b/g\n", prefix="aiand_modal")
    assert a == b
    assert a != c
    assert a.startswith("aiand_modal_")
