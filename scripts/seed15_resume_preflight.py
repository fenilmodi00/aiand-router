"""Unpaid resume preflight for the seed-15 Kimi-only hard-y probe.

This helper is intentionally side-effect free by default: it reads local state,
prints a readiness report, and never performs paid labeling calls.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - helper still works without dotenv
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEND = ROOT / "data" / "spend.txt"
DEFAULT_POOL = ROOT / "data" / "pool-hard-mix-kimi-only-targeted.jsonl"
DEFAULT_RUNNER = ROOT / "scripts" / "run_hard_y_probe.ps1"
DEFAULT_BUDGET_CAP_USD = 15.0
DEFAULT_SEED = 15
DEFAULT_LIMIT = 32
DEFAULT_MIN_FAIL_TO_PASS = 1
DEFAULT_MAX_FAIL_TO_PASS = 4


def _load_local_env() -> None:
    if load_dotenv is not None:
        load_dotenv()


def _parse_spend(path: Path) -> tuple[float | None, str | None]:
    if not path.exists():
        return None, "missing spend file"
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None, "empty spend file"
    try:
        return float(raw), None
    except ValueError:
        return None, f"invalid spend value: {raw!r}"


def paid_seed15_command(
    *,
    spend_path: Path,
    budget_limit_usd: float | None,
    seed: int,
    limit: int,
    pool_path: Path,
    min_fail_to_pass: int,
    max_fail_to_pass: int,
) -> str:
    budget_expr = (
        f"{budget_limit_usd:.6f}".rstrip("0").rstrip(".")
        if budget_limit_usd is not None
        else f"([double](Get-Content {spend_path.as_posix()} -Raw).Trim() + {DEFAULT_BUDGET_CAP_USD:g})"
    )
    return "\n".join(
        [
            '$env:PYTHONPATH = "src"',
            f"$spend = [double](Get-Content {spend_path.as_posix()} -Raw).Trim()",
            f"$env:BUDGET_LIMIT_USD = {budget_expr}",
            '$env:AIAND_TRAIN = "1"',
            '$env:TRAIN_CONCURRENCY = "10"',
            f".\\scripts\\run_hard_y_probe.ps1 -Paid -Seed {seed} -Limit {limit} `",
            f"  -Queries {pool_path.as_posix()} `",
            f"  -MinFailToPass {min_fail_to_pass} -MaxFailToPass {max_fail_to_pass}",
        ]
    )


def build_report(
    *,
    spend_path: Path = DEFAULT_SPEND,
    pool_path: Path = DEFAULT_POOL,
    runner_path: Path = DEFAULT_RUNNER,
    budget_cap_usd: float = DEFAULT_BUDGET_CAP_USD,
    seed: int = DEFAULT_SEED,
    limit: int = DEFAULT_LIMIT,
    min_fail_to_pass: int = DEFAULT_MIN_FAIL_TO_PASS,
    max_fail_to_pass: int = DEFAULT_MAX_FAIL_TO_PASS,
) -> dict[str, object]:
    _load_local_env()
    spend_usd, spend_error = _parse_spend(spend_path)
    budget_limit_usd = None if spend_usd is None else spend_usd + budget_cap_usd
    aiand_key = os.getenv("AIAND_API_KEY", "")
    python_cmd = str(Path(sys.executable).resolve()) if sys.executable else None
    python_exists = bool(python_cmd and Path(python_cmd).exists())
    powershell_exists = shutil.which("powershell") is not None or shutil.which("pwsh") is not None

    checks = {
        "aiand_api_key_present": bool(aiand_key),
        "spend_file_exists": spend_path.exists(),
        "spend_parse_ok": spend_error is None,
        "pool_file_exists": pool_path.exists(),
        "runner_script_exists": runner_path.exists(),
        "python_available": python_exists,
        "powershell_available": powershell_exists,
    }
    exact_command_runnable = all(checks.values())
    blockers: list[str] = []
    if not checks["aiand_api_key_present"]:
        blockers.append("AIAND_API_KEY is missing")
    if spend_error is not None:
        blockers.append(f"{spend_path.as_posix()}: {spend_error}")
    if not checks["pool_file_exists"]:
        blockers.append(f"required pool file missing: {pool_path.as_posix()}")
    if not checks["runner_script_exists"]:
        blockers.append(f"runner script missing: {runner_path.as_posix()}")
    if not checks["python_available"]:
        blockers.append("python executable not available")
    if not checks["powershell_available"]:
        blockers.append("PowerShell executable not available")

    return {
        "helper_command": ".\\scripts\\preflight_seed15_probe.ps1",
        "seed": seed,
        "limit": limit,
        "min_fail_to_pass": min_fail_to_pass,
        "max_fail_to_pass": max_fail_to_pass,
        "budget_cap_usd": budget_cap_usd,
        "spend_usd": spend_usd,
        "budget_limit_usd": budget_limit_usd,
        "spend_path": spend_path.as_posix(),
        "pool_path": pool_path.as_posix(),
        "runner_path": runner_path.as_posix(),
        "python_executable": python_cmd,
        "checks": checks,
        "exact_seed15_command_runnable": exact_command_runnable,
        "blockers": blockers,
        "paid_seed15_command": paid_seed15_command(
            spend_path=spend_path,
            budget_limit_usd=budget_limit_usd,
            seed=seed,
            limit=limit,
            pool_path=pool_path,
            min_fail_to_pass=min_fail_to_pass,
            max_fail_to_pass=max_fail_to_pass,
        ),
    }


def render_text(report: dict[str, object]) -> str:
    checks = report["checks"]
    assert isinstance(checks, dict)
    blockers = report["blockers"]
    assert isinstance(blockers, list)
    spend = report["spend_usd"]
    spend_text = "unavailable" if spend is None else f"{float(spend):.6f}".rstrip("0").rstrip(".")
    budget = report["budget_limit_usd"]
    budget_text = "unavailable" if budget is None else f"{float(budget):.6f}".rstrip("0").rstrip(".")
    lines = [
        "# Seed-15 resume preflight",
        "",
        f"- Helper command: `{report['helper_command']}`",
        f"- Spend (`{report['spend_path']}`): `{spend_text}` USD",
        f"- Computed `BUDGET_LIMIT_USD`: `{budget_text}`",
        f"- Pool file: `{report['pool_path']}`",
        f"- Runner script: `{report['runner_path']}`",
        f"- Exact seed-15 command runnable: `{str(report['exact_seed15_command_runnable']).lower()}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in checks.items():
        status = "ok" if value else "missing"
        lines.append(f"- `{key}`: `{status}`")
    if blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in blockers)
    lines.extend(["", "## Exact paid command", "", "```powershell", str(report["paid_seed15_command"]), "```"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Unpaid seed-15 resume preflight")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown text")
    parser.add_argument("--report", help="Optional output path for the rendered report")
    parser.add_argument("--spend", default=str(DEFAULT_SPEND))
    parser.add_argument("--pool", default=str(DEFAULT_POOL))
    parser.add_argument("--runner", default=str(DEFAULT_RUNNER))
    args = parser.parse_args(argv)

    report = build_report(
        spend_path=Path(args.spend),
        pool_path=Path(args.pool),
        runner_path=Path(args.runner),
    )
    rendered = json.dumps(report, indent=2) if args.json else render_text(report)
    if args.report:
        Path(args.report).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["exact_seed15_command_runnable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
