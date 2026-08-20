"""Unpaid order-mix conservative dry-run preflight (no aiand credits).

Builds or reads the order-conservative pool, samples n=32 with Mix1 class quotas,
reports class-fraction deltas vs Mix1 targets, cost projection, and whether paid
gold is justified. Side-effect free unless --write-pool is set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from aiand_router.pool import (  # noqa: E402
    build_order_mix_calibration,
    collect_order_mix_conservative_queries,
    collision_keys,
    order_mix_bucket_class,
    order_mix_class_fraction_gate,
    order_mix_class_targets,
    order_mix_dry_run_report,
    order_mix_histogram,
    order_mix_reservoir_report,
    write_pool,
)

DEFAULT_POOL = ROOT / "data" / "pool-hard-mix-order-conservative.jsonl"
DEFAULT_RESERVOIR = ROOT / "data" / "pool-hard-mix-order-conservative-reservoir.jsonl"
DEFAULT_MIX1 = ROOT / "data" / "gold-sparse-hard-mix1.jsonl"
DEFAULT_MIX1_POOL = ROOT / "data" / "pool-hard-mix-near_miss_seed11.jsonl"
DEFAULT_FROM_POOL = ROOT / "data" / "pool-hard-mix-mix1like.jsonl"
DEFAULT_SPEND = ROOT / "data" / "spend.txt"
DEFAULT_EXCLUDE = [
    "data/gold-verified.jsonl",
    "data/gold-sparse-hard-mix1.jsonl",
    "data/gold-sparse-hard-mix1-train.jsonl",
    "data/gold-sparse-hard-mix1-retune.jsonl",
    "data/gold-sparse-hard-mix1-topup32.jsonl",
    "data/gold-sparse-hard-probe-seed11.jsonl",
    "data/gold-sparse-hard-probe-seed12.jsonl",
    "data/gold-sparse-hard-probe-seed13.jsonl",
    "data/gold-sparse-hard-probe-seed14.jsonl",
    "data/gold-sparse-hard-probe-seed15.jsonl",
]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _blocked_keys(exclude_paths: list[str]) -> set[str]:
    blocked: set[str] = set()
    for ep in exclude_paths:
        blocked |= collision_keys(_read_jsonl(ROOT / ep))
    return blocked


def paid_probe_command(
    *,
    spend_path: Path,
    budget_cap_usd: float,
    seed: int,
    limit: int,
    pool_path: Path,
) -> str:
    spend_expr = (
        f"([double](Get-Content {spend_path.as_posix()} -Raw).Trim() + {budget_cap_usd:g})"
    )
    return "\n".join(
        [
            '$env:PYTHONPATH = "src"',
            f"$spend = [double](Get-Content {spend_path.as_posix()} -Raw).Trim()",
            f"$env:BUDGET_LIMIT_USD = {spend_expr}",
            '$env:AIAND_TRAIN = "1"',
            '$env:TRAIN_CONCURRENCY = "10"',
            f".\\scripts\\run_hard_y_probe.ps1 -Paid -Seed {seed} -Limit {limit} `",
            f"  -Queries {pool_path.as_posix()} `",
            "  -MinFailToPass 1 -MaxFailToPass 5 -NearMissLo 0.55 -NearMissHi 0.85",
        ]
    )


def build_report(
    *,
    from_pool: Path | None,
    mix1: Path,
    mix1_pool: Path,
    pool_path: Path,
    reservoir_path: Path,
    spend_path: Path,
    budget_cap_usd: float,
    seed: int,
    limit: int,
    tolerance_pp: float,
    exclude_paths: list[str],
    write_pool_flag: bool,
) -> dict[str, object]:
    mix1_gold = _read_jsonl(mix1)
    mix1_pool_rows = _read_jsonl(mix1_pool)
    blocked = _blocked_keys(exclude_paths)
    source_rows = _read_jsonl(from_pool) if from_pool and from_pool.exists() else None
    cal = build_order_mix_calibration(mix1_gold, mix1_pool_rows)
    targets = order_mix_class_targets(mix1_gold, mix1_pool_rows, cal)

    reservoir = collect_order_mix_conservative_queries(
        None,
        None,
        source_pool=source_rows,
        blocked=blocked,
        mix1_gold=mix1_gold,
        mix1_pool_rows=mix1_pool_rows,
        seed=seed,
        sample_n=0,
        mutation_waiver_kimi_heavy=True,
        exclude_unknown_class=True,
    )
    supply = order_mix_reservoir_report(reservoir, cal=cal, targets=targets, sample_n=limit)
    sample = collect_order_mix_conservative_queries(
        None,
        None,
        source_pool=source_rows,
        blocked=blocked,
        mix1_gold=mix1_gold,
        mix1_pool_rows=mix1_pool_rows,
        seed=seed,
        sample_n=limit,
        mutation_waiver_kimi_heavy=True,
        exclude_unknown_class=True,
    )
    dry = order_mix_dry_run_report(
        sample,
        mix1_gold=mix1_gold,
        mix1_pool_rows=mix1_pool_rows,
        tolerance_pp=tolerance_pp,
    )

    spend_usd = None
    spend_error = None
    if spend_path.exists():
        raw = spend_path.read_text(encoding="utf-8").strip()
        try:
            spend_usd = float(raw) if raw else None
        except ValueError:
            spend_error = f"invalid spend value: {raw!r}"

    try:
        from scripts.hard_y_probe import project_gold_cost  # type: ignore
    except Exception:
        sys.path.insert(0, str(ROOT / "scripts"))
        from hard_y_probe import project_gold_cost  # type: ignore

    projected = project_gold_cost(pool_path if pool_path.exists() else reservoir_path, limit=limit)
    budget_limit = (spend_usd or 0.0) + budget_cap_usd
    within_cap = (spend_usd or 0.0) + projected["projected_usd"] <= budget_limit

    class_gate_pass = bool(dry.get("class_fraction_gate_pass"))
    sample_full = len(sample) >= limit
    retro = dry.get("mix1_retroactive") or {}
    retro_ok = (
        retro.get("score_delta") is not None
        and float(retro.get("score_delta") or 0) > 0.5
    )
    paid_justified = class_gate_pass and sample_full and within_cap and retro_ok

    blockers: list[str] = []
    if not sample_full:
        blockers.append(f"sample shortfall: got n={len(sample)} want n={limit}")
    if not class_gate_pass:
        for row in dry.get("per_class") or []:
            if not row.get("within_10pp"):
                blockers.append(
                    f"class {row['class']}: observed {float(row['observed']):.3f} "
                    f"target {float(row['target']):.3f} "
                    f"delta {float(row['delta_pp'])*100:+.1f}pp"
                )
    for cls, short in (supply.get("quota_shortfall") or {}).items():
        if short:
            blockers.append(f"reservoir short on {cls}: need {short} more unlabeled rows")
    if not within_cap:
        blockers.append("projected spend exceeds budget cap")
    if not retro_ok:
        blockers.append("Mix1 retroactive proxy score_delta <= 0.5")
    if spend_error:
        blockers.append(spend_error)

    if write_pool_flag:
        write_pool(reservoir, reservoir_path)
        write_pool(sample, pool_path)

    return {
        "helper_command": ".\\scripts\\order_mix_preflight.py",
        "seed": seed,
        "limit": limit,
        "tolerance_pp": tolerance_pp,
        "pool_path": pool_path.as_posix(),
        "reservoir_path": reservoir_path.as_posix(),
        "reservoir_n": len(reservoir),
        "sample_n": len(sample),
        "supply": supply,
        "dry_run": dry,
        "class_fraction_gate_pass": class_gate_pass,
        "sample_full": sample_full,
        "within_budget_cap": within_cap,
        "mix1_retroactive_ok": retro_ok,
        "paid_gold_justified": paid_justified,
        "blockers": blockers,
        "projected": projected,
        "spend_usd": spend_usd,
        "budget_cap_usd": budget_cap_usd,
        "paid_command": paid_probe_command(
            spend_path=spend_path,
            budget_cap_usd=budget_cap_usd,
            seed=seed,
            limit=limit,
            pool_path=pool_path,
        )
        if paid_justified
        else None,
        "preflight_geometry_predictor": {
            "valid": False,
            "reason": (
                "seed-16 paid falsification: class_fraction_gate_pass and paid_gold_justified "
                "did not predict standalone geometry_pass (y=0.047, holdout_like_order=false)"
            ),
        },
    }


def render_text(report: dict[str, object]) -> str:
    dry = report["dry_run"]
    assert isinstance(dry, dict)
    lines = [
        "# Order-mix conservative dry-run preflight",
        "",
        f"- Pool: `{report['pool_path']}` (sample n={report['sample_n']})",
        f"- Reservoir: `{report['reservoir_path']}` (n={report['reservoir_n']})",
        f"- Class fraction gate (~{float(report['tolerance_pp'])*100:.0f}pp): "
        f"`{str(report['class_fraction_gate_pass']).lower()}`",
        f"- Paid gold justified: `{str(report['paid_gold_justified']).lower()}`",
        "",
        "## Preflight vs geometry (seed-16 falsification)",
        "",
        "Class-quota preflight **does not predict** standalone `geometry_pass`. "
        "Seed-16: preflight pass → paid geometry fail (y below band, 26/32 all-fail). "
        "Do **not** treat `paid_gold_justified=true` as license for more blind paid draws.",
        "",
        "## Class fractions vs Mix1",
        "",
        "| class | observed | target | delta (pp) | within gate |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in dry.get("per_class") or []:
        assert isinstance(row, dict)
        lines.append(
            f"| {row['class']} | {float(row['observed']):.4f} | {float(row['target']):.4f} | "
            f"{float(row['delta_pp'])*100:+.1f} | {row['within_10pp']} |"
        )
    lines.extend(
        [
            "",
            "## Supply",
            "",
            f"- Quota shortfall: `{json.dumps(report.get('supply', {}).get('quota_shortfall', {}))}`",
            f"- Projected gold USD (n={report['limit']}): `{report['projected']['projected_usd']}`",
            f"- Within budget cap: `{report['within_budget_cap']}`",
        ]
    )
    blockers = report.get("blockers") or []
    if blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {b}" for b in blockers)
    paid_cmd = report.get("paid_command")
    if paid_cmd:
        lines.extend(["", "## Paid command (only if gate passed)", "", "```powershell", str(paid_cmd), "```"])
    else:
        lines.extend(["", "## Paid command", "", "_Withheld — dry-run gate did not pass._"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Unpaid order-mix conservative preflight")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report", help="Optional output path for rendered report")
    parser.add_argument("--write-pool", action="store_true", help="Write reservoir + sample pool files")
    parser.add_argument("--from-pool", default=str(DEFAULT_FROM_POOL))
    parser.add_argument("--mix1", default=str(DEFAULT_MIX1))
    parser.add_argument("--mix1-pool", default=str(DEFAULT_MIX1_POOL))
    parser.add_argument("--pool", default=str(DEFAULT_POOL))
    parser.add_argument("--reservoir", default=str(DEFAULT_RESERVOIR))
    parser.add_argument("--spend", default=str(DEFAULT_SPEND))
    parser.add_argument("--budget-cap", type=float, default=15.0)
    parser.add_argument("--seed", type=int, default=16)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--tolerance-pp", type=float, default=0.10)
    args = parser.parse_args(argv)

    from_pool = Path(args.from_pool) if args.from_pool else None
    report = build_report(
        from_pool=from_pool,
        mix1=Path(args.mix1),
        mix1_pool=Path(args.mix1_pool),
        pool_path=Path(args.pool),
        reservoir_path=Path(args.reservoir),
        spend_path=Path(args.spend),
        budget_cap_usd=float(args.budget_cap),
        seed=int(args.seed),
        limit=int(args.limit),
        tolerance_pp=float(args.tolerance_pp),
        exclude_paths=list(DEFAULT_EXCLUDE),
        write_pool_flag=bool(args.write_pool),
    )
    rendered = json.dumps(report, indent=2) if args.json else render_text(report)
    if args.report:
        Path(args.report).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["paid_gold_justified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
