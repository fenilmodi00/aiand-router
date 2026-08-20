#!/usr/bin/env python
"""Unpaid Verified session-gold promotion readiness (runbook §(a)).

Validates the ids scaffold, maps gate bars to checklist status, snapshots local
replay proxy posture, and prints a dual-policy run plan with budget estimates.
No paid HTTP. Does not flip TRAINED_PATH.

PowerShell:
  $env:PYTHONPATH='src'
  python scripts/run_promotion_readiness.py
  python scripts/run_promotion_readiness.py --json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aiand_router.promotion_gate import (  # noqa: E402
    format_promotion_report,
    main as promotion_main,
    promotion_readiness,
)

DEFAULT_SCAFFOLD = ROOT / "data" / "verified_ids_scaffold.json"
DEFAULT_REPORT = (
    ROOT / ".scratch" / "scorer-pioneer-lift" / "promotion-readiness-2026-08-20.md"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scaffold", type=Path, default=DEFAULT_SCAFFOLD)
    parser.add_argument(
        "--artifact",
        default=str(ROOT / "data" / "scorer-hard-logistic.json"),
    )
    parser.add_argument("--models", default=str(ROOT / "config" / "models.yaml"))
    parser.add_argument("--gold", default=str(ROOT / "data" / "gold-verified.jsonl"))
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Write markdown report (default: scratch promotion-readiness doc)",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--stdout-only", action="store_true", help="Skip writing report file")
    args = parser.parse_args(argv)

    if args.stdout_only:
        return promotion_main(
            [
                "--scaffold",
                str(args.scaffold),
                "--artifact",
                args.artifact,
                "--models",
                args.models,
                "--gold",
                args.gold,
                *(["--json"] if args.json else []),
            ]
        )

    report = promotion_readiness(
        scaffold_path=args.scaffold,
        artifact_path=Path(args.artifact),
        models_path=Path(args.models),
        gold_path=Path(args.gold),
    )
    md = format_promotion_report(report)
    if not args.stdout_only:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(md, encoding="utf-8")
        print(f"wrote report {args.report}", flush=True)
    if args.json:
        import json

        slim = dict(report)
        budget = dict(slim.get("budget_estimate") or {})
        budget.pop("per_model_completion_est", None)
        slim["budget_estimate"] = budget
        print(json.dumps(slim, indent=2))
    else:
        print(md)
    return 0 if report.get("scaffold_valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
