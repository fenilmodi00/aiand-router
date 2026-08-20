#!/usr/bin/env python
"""Run unpaid dual-policy Lite comparison against the checked-in synthetic fixture.

Produces harness-proxy rules-vs-trained resolve rates. Labeled bounded_check_only;
not session gold and not production parity. No HTTP / no paid API calls.

PowerShell:
  $env:PYTHONPATH='src'
  python scripts/run_lite_comparison.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aiand_router.lite_runner import (  # noqa: E402
    format_comparison_report,
    main as lite_main,
    summarize_comparison,
)

DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "lite_comparison" / "fixture.json"
DEFAULT_OUT = ROOT / "tests" / "fixtures" / "lite_comparison" / "results.jsonl"
DEFAULT_REPORT = ROOT / "tests" / "fixtures" / "lite_comparison" / "report.md"


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def run(
    fixture: Path,
    out: Path,
    report: Path,
    n: int,
) -> dict:
    rc = lite_main(["--fixture", str(fixture), "--out", str(out), "--n", str(n)])
    if rc != 0:
        raise SystemExit(rc)
    rows = _read_jsonl(out)
    summary = summarize_comparison(rows)

    def _rel(path: Path) -> str:
        try:
            return path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return path.as_posix()

    fixture_rel = _rel(fixture)
    summary["fixture"] = fixture_rel
    summary["results"] = _rel(out)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        format_comparison_report(summary, fixture_path=fixture_rel),
        encoding="utf-8",
    )
    summary_path = report.with_suffix(".json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        f"comparison: rules={summary['rules_resolved']}/{summary['n']} "
        f"trained={summary['trained_resolved']}/{summary['n']} "
        f"delta_pp={summary['delta_pp']} verdict={summary['verdict']}"
    )
    print(f"wrote report {report}")
    print(f"wrote summary {summary_path}")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--n", type=int, default=50)
    args = parser.parse_args(argv)
    run(args.fixture, args.out, args.report, args.n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
