#!/usr/bin/env python
"""Thin SWE_EVAL_CMD hook for verified_runner true session_gold.

verified_runner sets:
  SWE_EVAL_CMD with {instance_id} and {patch_file} placeholders.

Stdout contract (parsed by aiand_router.verified_runner._run_swe_eval_cmd):
  - last line ``true`` / ``false``, or
  - JSON ``{\"resolved\": true|false}``, or
  - JSON ``{\"resolved\": null, \"status\": \"not_available\"}`` -> unlabeled
    (never treat as measured fail)

Backends (``SWE_EVAL_BACKEND`` or ``--backend``; default ``local``):

  local   — Docker + swebench.harness.run_evaluation (back-compat)
  modal   — same harness with ``--modal true`` (no local image farm)
  sb-cli  — ``sb-cli submit swe-bench_verified test`` (cloud API)

PowerShell (repo root):

  # Default: honest not_available until docker + swebench are ready
  $env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'

  # Modal (no local sweb.eval retention):
  #   pip install modal 'swebench[modal]'; modal token new
  $env:SWE_EVAL_BACKEND='modal'
  $env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'

  # sb-cli (no local images):
  #   pip install sb-cli; sb-cli gen-api-key you@example.com; verify; set SWEBENCH_API_KEY
  $env:SWE_EVAL_BACKEND='sb-cli'
  $env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'

  # Unpaid mock only (never promotion evidence):
  $env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file} --mock-resolved true'

Real local resolve (operator Linux preferred; heavy images):

  1. Docker Engine working: ``docker run hello-world``
  2. ``pip install swebench`` (or clone https://github.com/SWE-bench/SWE-bench)
  3. Re-run with the same SWE_EVAL_CMD - this script invokes
     ``swebench.harness.run_evaluation`` for one instance when
     both docker and the ``swebench`` package are present.
  4. Prefer Ubuntu x86_64. On Windows Docker Desktop this wrapper forces
     UTF-8 + LF newlines when writing eval.sh (otherwise container bash
     sees trailing ``\\r`` and the run is not a real resolve).

Dataset: use ``SWE-bench/SWE-bench_Verified`` (has ``image`` / ``eval_script``).
``princeton-nlp/SWE-bench_Verified`` lacks those fields and breaks make_test_spec.

This repo does not vendor a full docker stack. No fake resolves.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# Official Verified split used by swebench>=5 make_test_spec (image field present).
DEFAULT_DATASET_NAME = "SWE-bench/SWE-bench_Verified"
# Legacy HF id - no image/eval_script; keep only as explicit opt-in for debugging.
LEGACY_DATASET_NAME = "princeton-nlp/SWE-bench_Verified"
MODEL_NAME = "aiand-router"

BACKEND_LOCAL = "local"
BACKEND_MODAL = "modal"
BACKEND_SB_CLI = "sb-cli"
VALID_BACKENDS = (BACKEND_LOCAL, BACKEND_MODAL, BACKEND_SB_CLI)

# sb-cli subset/split for Verified (see https://www.swebench.com/sb-cli/)
SB_CLI_SUBSET = "swe-bench_verified"
SB_CLI_SPLIT = "test"


def _emit(payload: dict[str, Any], *, code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return code


def _not_available(reason: str, **extra: Any) -> int:
    body: dict[str, Any] = {
        "resolved": None,
        "status": "not_available",
        "reason": reason,
    }
    body.update(extra)
    return _emit(body, code=2)


def _normalize_backend(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip().lower().replace("_", "-")
    aliases = {
        "sbcli": BACKEND_SB_CLI,
        "sb-cli": BACKEND_SB_CLI,
        "modal": BACKEND_MODAL,
        "local": BACKEND_LOCAL,
        "docker": BACKEND_LOCAL,
    }
    return aliases.get(value, value)


def resolve_backend(*, cli_backend: str | None = None) -> str:
    """CLI ``--backend`` overrides ``SWE_EVAL_BACKEND``; default ``local``."""
    chosen = _normalize_backend(cli_backend)
    if chosen is None:
        chosen = _normalize_backend(os.getenv("SWE_EVAL_BACKEND"))
    if chosen is None or chosen == "":
        return BACKEND_LOCAL
    return chosen


def _docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        proc = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _swebench_importable() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec("swebench") is not None
    except (ImportError, ValueError):
        return False


def _modal_importable() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec("modal") is not None
    except (ImportError, ValueError):
        return False


def _modal_configured() -> bool:
    """Match swebench.harness.modal_eval.utils.validate_modal_credentials."""
    return (Path.home() / ".modal.toml").is_file()


def _sb_cli_cmd_prefix() -> list[str] | None:
    found = shutil.which("sb-cli")
    if found:
        return [found]
    try:
        import importlib.util

        if importlib.util.find_spec("sb_cli") is not None:
            return [sys.executable, "-m", "sb_cli"]
    except (ImportError, ValueError):
        pass
    return None


def _sb_cli_api_key() -> str | None:
    key = (os.getenv("SWEBENCH_API_KEY") or "").strip()
    return key or None


def _resolved_from_report(data: Any, instance_id: str) -> bool | None:
    """Parse summary or per-instance swebench / sb-cli report JSON.

    Summary (``{model}.{run_id}.json``): top-level ``resolved_ids`` / ``completed_ids``.
    Per-instance (``logs/.../report.json``): ``{instance_id: {resolved: bool}}``.
    sb-cli reports often mirror the same id lists.

    Returns True/False for a completed eval, or None when missing/errored.
    Never map ``error_ids`` to measured fail (that would fake session_gold).
    """
    if not isinstance(data, dict):
        return None

    resolved_ids = data.get("resolved_ids")
    if isinstance(resolved_ids, list):
        if instance_id in resolved_ids:
            return True
        unresolved = set(data.get("unresolved_ids") or [])
        completed = set(data.get("completed_ids") or [])
        if instance_id in unresolved:
            return False
        if instance_id in completed:
            return False
        # Aggregate-only sb-cli reports without id lists stay unlabeled.
        return None

    # Alternate list key sometimes used in cloud reports.
    resolved_alt = data.get("resolved")
    if isinstance(resolved_alt, list):
        if instance_id in resolved_alt:
            return True
        fails = set(data.get("unresolved") or data.get("failed") or [])
        if instance_id in fails:
            return False
        return None

    entry = data.get(instance_id)
    if isinstance(entry, dict) and "resolved" in entry:
        return bool(entry["resolved"])
    return None


def _summary_instance_reason(data: Any, instance_id: str) -> str | None:
    """If summary JSON explains a non-completed instance, return a reason code."""
    if not isinstance(data, dict) or "resolved_ids" not in data:
        return None
    if instance_id in (data.get("error_ids") or []):
        return "swebench_instance_error"
    if instance_id in (data.get("empty_patch_ids") or []):
        return "empty_patch"
    if instance_id in (data.get("incomplete_ids") or []):
        return "swebench_incomplete"
    return None


def _collect_report_paths(work_dir: Path, run_id: str, model_name: str) -> list[Path]:
    """Prefer summary report, then per-instance report.json under logs/."""
    model_key = model_name.replace("/", "__")
    paths: list[Path] = []
    summary = work_dir / f"{model_key}.{run_id}.json"
    if summary.is_file():
        paths.append(summary)
    paths.extend(
        sorted(work_dir.glob(f"logs/run_evaluation/{run_id}/**/report.json"))
    )
    paths.extend(
        p
        for p in sorted(work_dir.glob(f"**/run_evaluation/{run_id}/**/report.json"))
        if p not in paths
    )
    return paths


def _collect_sb_cli_report_paths(output_dir: Path, run_id: str) -> list[Path]:
    """sb-cli writes ``{subset}__{split}__{run_id}.json`` under output_dir."""
    paths: list[Path] = []
    exact = output_dir / f"{SB_CLI_SUBSET}__{SB_CLI_SPLIT}__{run_id}.json"
    if exact.is_file():
        paths.append(exact)
    # overwrite=0 may append -N suffixes
    paths.extend(
        sorted(
            p
            for p in output_dir.glob(f"{SB_CLI_SUBSET}__{SB_CLI_SPLIT}__{run_id}*.json")
            if p not in paths and not p.name.endswith(".response.json")
        )
    )
    paths.extend(
        p
        for p in sorted(output_dir.glob("*.json"))
        if p not in paths and not p.name.endswith(".response.json") and run_id in p.name
    )
    return paths


def _harness_bootstrap_src() -> str:
    """Patch Path.write_text so Windows does not turn eval.sh LF into CRLF."""
    return """\
import pathlib
import runpy
import sys

_orig = pathlib.Path.write_text


def _write_text(self, data, encoding=None, errors=None, newline=None):
    if isinstance(data, str):
        if encoding is None:
            encoding = "utf-8"
        if newline is None:
            newline = "\\n"
    return _orig(self, data, encoding=encoding, errors=errors, newline=newline)


pathlib.Path.write_text = _write_text  # type: ignore[method-assign]
sys.argv = [%ARGS%]
runpy.run_module("swebench.harness.run_evaluation", run_name="__main__")
"""


def _crlf_eval_script_failure(detail: str | None) -> bool:
    if not detail:
        return False
    markers = (
        "pipefail\r",
        "activate\r",
        "/testbed\r",
        "locale-gen\r",
        "invalid option name",
    )
    return any(m in detail for m in markers)


def _instance_log_tail(work_dir: Path, run_id: str, instance_id: str) -> str | None:
    tails: list[str] = []
    for pattern in (
        f"logs/run_evaluation/{run_id}/**/{instance_id}/test_output.txt",
        f"logs/run_evaluation/{run_id}/**/{instance_id}/run_instance.log",
    ):
        for path in work_dir.glob(pattern):
            try:
                tails.append(path.read_text(encoding="utf-8", errors="replace")[-2000:])
            except OSError:
                continue
    if not tails:
        return None
    return "\n".join(tails)[-2500:]


def _remote_run_id(instance_id: str, patch_text: str, *, prefix: str) -> str:
    """Unique run_id so Modal/sb-cli do not reuse a stale cached resolve."""
    digest = hashlib.sha1(
        f"{instance_id}\n{patch_text}".encode("utf-8", errors="replace")
    ).hexdigest()[:10]
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", instance_id)[:48]
    return f"{prefix}_{safe}_{digest}"


def _parse_reports_for_instance(
    report_paths: list[Path],
    instance_id: str,
) -> tuple[bool | None, str | None, str | None, dict[str, Any] | None]:
    """Return (resolved, summary_reason, report_path, summary_data)."""
    summary_reason: str | None = None
    summary_report: str | None = None
    summary_data: dict[str, Any] | None = None
    for report in report_paths:
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        resolved = _resolved_from_report(data, instance_id)
        if resolved is not None:
            return resolved, None, str(report), data if isinstance(data, dict) else None
        if summary_reason is None:
            reason = _summary_instance_reason(data, instance_id)
            if reason is not None:
                summary_reason = reason
                summary_report = str(report)
                summary_data = data if isinstance(data, dict) else None
    return None, summary_reason, summary_report, summary_data


def _run_swebench_one(
    instance_id: str,
    patch_path: Path,
    *,
    run_id: str,
    dataset_name: str,
    modal: bool = False,
) -> int:
    """Best-effort single-instance official harness. Fail closed -> not_available."""
    patch_text = patch_path.read_text(encoding="utf-8")
    if not patch_text.strip():
        return _not_available(
            "empty_patch",
            hint="Official harness skips empty patches; provide a non-empty model_patch",
            instance_id=instance_id,
            backend=BACKEND_MODAL if modal else BACKEND_LOCAL,
        )
    pred = {
        "instance_id": instance_id,
        "model_name_or_path": MODEL_NAME,
        "model_patch": patch_text,
    }
    source = (
        "swebench.harness.run_evaluation[modal]"
        if modal
        else "swebench.harness.run_evaluation"
    )
    with tempfile.TemporaryDirectory(prefix="swe_eval_") as tmp:
        work_dir = Path(tmp)
        preds = work_dir / "preds.jsonl"
        preds.write_text(json.dumps(pred) + "\n", encoding="utf-8", newline="\n")
        report_dir = work_dir / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        harness_args = [
            "swebench.harness.run_evaluation",
            "--dataset_name",
            dataset_name,
            "--predictions_path",
            str(preds),
            "--max_workers",
            "1",
            "--run_id",
            run_id,
            "--instance_ids",
            instance_id,
            "--report_dir",
            str(report_dir),
        ]
        if modal:
            harness_args.extend(["--modal", "true"])
        bootstrap = work_dir / "_harness_bootstrap.py"
        args_literal = ", ".join(json.dumps(a) for a in harness_args)
        bootstrap.write_text(
            _harness_bootstrap_src().replace("%ARGS%", args_literal),
            encoding="utf-8",
            newline="\n",
        )
        cmd = [sys.executable, str(bootstrap)]
        try:
            env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=str(work_dir),
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _not_available(
                "swebench_harness_failed",
                detail=str(exc),
                instance_id=instance_id,
                backend=BACKEND_MODAL if modal else BACKEND_LOCAL,
            )

        report_paths = _collect_report_paths(work_dir, run_id, MODEL_NAME)
        report_paths += list(report_dir.glob("*.json"))
        seen: set[Path] = set()
        unique_paths: list[Path] = []
        for path in report_paths:
            resolved_path = path.resolve()
            if resolved_path in seen:
                continue
            seen.add(resolved_path)
            unique_paths.append(path)

        resolved, summary_reason, summary_report, summary_data = (
            _parse_reports_for_instance(unique_paths, instance_id)
        )
        if resolved is not None:
            log_tail = _instance_log_tail(work_dir, run_id, instance_id)
            if resolved is False and _crlf_eval_script_failure(log_tail):
                return _not_available(
                    "windows_crlf_eval_script",
                    hint=(
                        "Host wrote eval.sh with CRLF; container bash saw \\r. "
                        "Prefer Linux/WSL for SWE_EVAL_CMD if this persists."
                    ),
                    detail=log_tail,
                    instance_id=instance_id,
                    dataset_name=dataset_name,
                    report=summary_report,
                    backend=BACKEND_MODAL if modal else BACKEND_LOCAL,
                )
            return _emit(
                {
                    "resolved": resolved,
                    "status": "ok",
                    "source": source,
                    "backend": BACKEND_MODAL if modal else BACKEND_LOCAL,
                    "instance_id": instance_id,
                    "dataset_name": dataset_name,
                    "report": summary_report
                    or (str(unique_paths[0]) if unique_paths else None),
                },
                code=0,
            )

        log_tail = _instance_log_tail(work_dir, run_id, instance_id)
        detail = log_tail or (proc.stderr or proc.stdout or "").strip()[-2000:] or None
        if _crlf_eval_script_failure(detail):
            return _not_available(
                "windows_crlf_eval_script",
                exit_code=proc.returncode,
                detail=detail,
                instance_id=instance_id,
                dataset_name=dataset_name,
                report=summary_report,
                backend=BACKEND_MODAL if modal else BACKEND_LOCAL,
            )
        if summary_reason is not None:
            extra: dict[str, Any] = {}
            if summary_data:
                reasons = summary_data.get("failure_reasons") or {}
                if instance_id in reasons:
                    extra["failure_reason"] = reasons[instance_id]
            return _not_available(
                summary_reason,
                exit_code=proc.returncode,
                detail=detail,
                instance_id=instance_id,
                dataset_name=dataset_name,
                report=summary_report,
                backend=BACKEND_MODAL if modal else BACKEND_LOCAL,
                **extra,
            )

        return _not_available(
            "swebench_report_missing",
            exit_code=proc.returncode,
            detail=detail,
            instance_id=instance_id,
            dataset_name=dataset_name,
            backend=BACKEND_MODAL if modal else BACKEND_LOCAL,
        )


def _run_sb_cli_one(
    instance_id: str,
    patch_path: Path,
    *,
    run_id: str,
    cmd_prefix: list[str],
) -> int:
    """Submit one prediction via sb-cli; parse report. Fail closed -> not_available."""
    patch_text = patch_path.read_text(encoding="utf-8")
    if not patch_text.strip():
        return _not_available(
            "empty_patch",
            hint="sb-cli skips empty patches; provide a non-empty model_patch",
            instance_id=instance_id,
            backend=BACKEND_SB_CLI,
        )
    preds_obj = {
        instance_id: {
            "model_patch": patch_text,
            "model_name_or_path": MODEL_NAME,
        }
    }
    with tempfile.TemporaryDirectory(prefix="swe_eval_sb_") as tmp:
        work_dir = Path(tmp)
        preds = work_dir / "preds.json"
        preds.write_text(
            json.dumps(preds_obj, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        output_dir = work_dir / "sb-cli-reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            *cmd_prefix,
            "submit",
            SB_CLI_SUBSET,
            SB_CLI_SPLIT,
            "--predictions_path",
            str(preds),
            "--run_id",
            run_id,
            "--instance_ids",
            instance_id,
            "--output_dir",
            str(output_dir),
            "--overwrite",
            "1",
            "--gen_report",
            "1",
        ]
        try:
            env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=str(work_dir),
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _not_available(
                "sb_cli_submit_failed",
                detail=str(exc),
                instance_id=instance_id,
                backend=BACKEND_SB_CLI,
            )

        report_paths = _collect_sb_cli_report_paths(output_dir, run_id)
        resolved, summary_reason, summary_report, summary_data = (
            _parse_reports_for_instance(report_paths, instance_id)
        )
        if resolved is not None:
            return _emit(
                {
                    "resolved": resolved,
                    "status": "ok",
                    "source": "sb-cli submit",
                    "backend": BACKEND_SB_CLI,
                    "instance_id": instance_id,
                    "subset": SB_CLI_SUBSET,
                    "split": SB_CLI_SPLIT,
                    "run_id": run_id,
                    "report": summary_report
                    or (str(report_paths[0]) if report_paths else None),
                },
                code=0,
            )

        detail = (proc.stderr or proc.stdout or "").strip()[-2000:] or None
        if proc.returncode != 0:
            return _not_available(
                "sb_cli_submit_failed",
                exit_code=proc.returncode,
                detail=detail,
                instance_id=instance_id,
                backend=BACKEND_SB_CLI,
                run_id=run_id,
            )
        if summary_reason is not None:
            return _not_available(
                summary_reason,
                exit_code=proc.returncode,
                detail=detail,
                instance_id=instance_id,
                backend=BACKEND_SB_CLI,
                report=summary_report,
                run_id=run_id,
            )
        # Aggregate-only report without per-instance id lists → unlabeled, not fake fail.
        if report_paths and summary_data is not None:
            return _not_available(
                "sb_cli_report_missing_instance",
                hint=(
                    "sb-cli report lacked resolved_ids/unresolved_ids for this "
                    "instance_id; inspect report JSON before claiming session_gold"
                ),
                detail=detail,
                instance_id=instance_id,
                backend=BACKEND_SB_CLI,
                report=str(report_paths[0]),
                run_id=run_id,
            )
        return _not_available(
            "sb_cli_report_missing",
            exit_code=proc.returncode,
            detail=detail,
            instance_id=instance_id,
            backend=BACKEND_SB_CLI,
            run_id=run_id,
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--instance", required=True, help="SWE-bench instance_id")
    p.add_argument("--patch", required=True, type=Path, help="Path to model patch file")
    p.add_argument(
        "--mock-resolved",
        choices=("true", "false"),
        default=None,
        help="Unpaid/test only: emit a fixed bool (not promotion evidence)",
    )
    p.add_argument(
        "--backend",
        choices=VALID_BACKENDS,
        default=None,
        help=(
            "Resolve backend: local|modal|sb-cli "
            "(default: SWE_EVAL_BACKEND or local)"
        ),
    )
    p.add_argument(
        "--run-id",
        default=None,
        help=(
            "Harness/sb-cli run_id. Default local=aiand_swe_eval; "
            "modal/sb-cli auto-hash patch to avoid stale cache."
        ),
    )
    p.add_argument(
        "--dataset-name",
        default=DEFAULT_DATASET_NAME,
        help=(
            f"HF dataset id for harness (default: {DEFAULT_DATASET_NAME}; "
            f"avoid {LEGACY_DATASET_NAME} - missing image field)"
        ),
    )
    args = p.parse_args(argv)

    if not args.patch.is_file():
        return _not_available("patch_missing", patch=str(args.patch))

    if args.mock_resolved is not None:
        resolved = args.mock_resolved == "true"
        return _emit(
            {
                "resolved": resolved,
                "status": "mock",
                "instance_id": args.instance,
                "backend": resolve_backend(cli_backend=args.backend),
                "note": "mock-resolved only; not live SWE-bench docker/cloud eval",
            },
            code=0,
        )

    backend = resolve_backend(cli_backend=args.backend)
    if backend not in VALID_BACKENDS:
        return _not_available(
            "invalid_backend",
            backend=backend,
            hint=f"Set SWE_EVAL_BACKEND or --backend to one of: {', '.join(VALID_BACKENDS)}",
            instance_id=args.instance,
        )

    patch_text = args.patch.read_text(encoding="utf-8")
    if args.run_id:
        run_id = args.run_id
    elif backend == BACKEND_LOCAL:
        run_id = "aiand_swe_eval"
    else:
        run_id = _remote_run_id(args.instance, patch_text, prefix=f"aiand_{backend}")

    if backend == BACKEND_SB_CLI:
        cmd_prefix = _sb_cli_cmd_prefix()
        if cmd_prefix is None:
            return _not_available(
                "sb_cli_missing",
                hint="pip install sb-cli  # then ensure `sb-cli` is on PATH",
                instance_id=args.instance,
                backend=backend,
            )
        if not _sb_cli_api_key():
            return _not_available(
                "sb_cli_not_configured",
                hint=(
                    "Set SWEBENCH_API_KEY after: sb-cli gen-api-key you@example.com "
                    "&& sb-cli verify-api-key <code> "
                    "(docs: https://www.swebench.com/sb-cli/authentication/)"
                ),
                instance_id=args.instance,
                backend=backend,
            )
        return _run_sb_cli_one(
            args.instance,
            args.patch,
            run_id=run_id,
            cmd_prefix=cmd_prefix,
        )

    if backend == BACKEND_MODAL:
        if not _swebench_importable():
            return _not_available(
                "swebench_package_missing",
                hint="pip install 'swebench[modal]' modal",
                instance_id=args.instance,
                backend=backend,
            )
        if not _modal_importable():
            return _not_available(
                "modal_package_missing",
                hint="pip install modal 'swebench[modal]'",
                instance_id=args.instance,
                backend=backend,
            )
        if not _modal_configured():
            return _not_available(
                "modal_not_configured",
                hint=(
                    "Run `modal token new` (writes ~/.modal.toml). "
                    "No local sweb.eval images required."
                ),
                instance_id=args.instance,
                backend=backend,
            )
        return _run_swebench_one(
            args.instance,
            args.patch,
            run_id=run_id,
            dataset_name=args.dataset_name,
            modal=True,
        )

    # local (default)
    if not _docker_ok():
        return _not_available(
            "docker_unavailable",
            hint=(
                "Install Docker Engine and ensure `docker info` works, "
                "or set SWE_EVAL_BACKEND=modal|sb-cli for disk-light remote resolve"
            ),
            instance_id=args.instance,
            backend=backend,
        )
    if not _swebench_importable():
        return _not_available(
            "swebench_package_missing",
            hint="pip install swebench  # or clone SWE-bench/SWE-bench",
            instance_id=args.instance,
            backend=backend,
        )
    return _run_swebench_one(
        args.instance,
        args.patch,
        run_id=run_id,
        dataset_name=args.dataset_name,
        modal=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
