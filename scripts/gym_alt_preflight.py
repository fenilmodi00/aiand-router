"""Unpaid SWE-Gym gym_alt hard-y probe preflight (no aiand credits).

Validates the pre-built gym_alt pool before a small paid geometry probe:
pool exists, collision filters, spend/budget, offline trait histogram vs Mix1.
Side-effect free unless --write-report is set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from aiand_router.pool import (  # noqa: E402
    GYM_ALT_ALL_FAIL_CEILING,
    GYM_ALT_KIMI_ONLY_FLOOR,
    build_order_mix_calibration,
    collision_keys,
    order_mix_histogram,
    pool_histogram,
    project_order_mix_winner_mix,
)

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

DEFAULT_POOL = ROOT / "data" / "pool-hard-gym-alt-seed2-n40.jsonl"
DEFAULT_MIX1_POOL = ROOT / "data" / "pool-hard-mix-near_miss_seed11.jsonl"
DEFAULT_MIX1 = ROOT / "data" / "gold-sparse-hard-mix1.jsonl"
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
    "data/gold-sparse-hard-probe-seed16.jsonl",
    "data/gold-sparse-hard-probe-gym-alt-seed1.jsonl",
]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
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


def _trait_delta(observed: dict[str, Any], reference: dict[str, Any], key: str) -> dict[str, Any]:
    o = (observed.get(key) or {}).get("mean")
    r = (reference.get(key) or {}).get("mean")
    if o is None or r is None:
        return {"observed": o, "reference": r, "delta": None}
    return {"observed": o, "reference": r, "delta": round(float(o) - float(r), 4)}


def paid_probe_command(
    *,
    spend_path: Path,
    budget_cap_usd: float,
    seed_name: str,
    limit: int,
    pool_path: Path,
) -> str:
    spend_expr = (
        f"([double](Get-Content {spend_path.as_posix()} -Raw).Trim() + {budget_cap_usd:g})"
    )
    gold_out = f"data/gold-sparse-hard-probe-{seed_name}.jsonl"
    return "\n".join(
        [
            '$env:PYTHONPATH = "src"',
            f"$spend = [double](Get-Content {spend_path.as_posix()} -Raw).Trim()",
            f"$env:BUDGET_LIMIT_USD = {spend_expr}",
            '$env:AIAND_TRAIN = "1"',
            '$env:TRAIN_CONCURRENCY = "10"',
            f"python -m aiand_router.train gold `",
            f"  --queries {pool_path.as_posix()} `",
            f"  --out {gold_out} `",
            f"  --limit {limit}",
            f"python -m aiand_router.geometry --train {gold_out} --eval data/gold-verified.jsonl",
        ]
    )


def build_report(
    *,
    pool_path: Path,
    mix1_pool_path: Path,
    mix1_gold_path: Path,
    spend_path: Path,
    budget_cap_usd: float,
    seed_name: str,
    limit: int,
    exclude_paths: list[str],
) -> dict[str, Any]:
    if load_dotenv is not None:
        load_dotenv()

    blockers: list[str] = []
    warnings: list[str] = []

    if not pool_path.exists():
        blockers.append(f"missing pool: {pool_path.as_posix()}")
        return {
            "pool_path": pool_path.as_posix(),
            "paid_gold_justified": False,
            "blockers": blockers,
            "warnings": warnings,
        }

    rows = _read_jsonl(pool_path)
    if len(rows) < limit:
        blockers.append(f"pool shortfall: got n={len(rows)} want n>={limit}")

    blocked = _blocked_keys(exclude_paths)
    pool_keys = collision_keys(rows)
    collision_hits = pool_keys & blocked
    if collision_hits:
        blockers.append(f"collision with excluded gold/pools: {len(collision_hits)} keys")

    missing_expected = sum(1 for r in rows if not str(r.get("expected") or "").strip())
    missing_f2p = sum(1 for r in rows if not r.get("FAIL_TO_PASS"))
    wrong_source = sum(1 for r in rows if str(r.get("source") or "") != "swe-gym")
    if missing_expected:
        blockers.append(f"missing expected on {missing_expected}/{len(rows)} rows")
    if missing_f2p:
        blockers.append(f"missing FAIL_TO_PASS on {missing_f2p}/{len(rows)} rows")
    if wrong_source:
        blockers.append(f"non swe-gym source on {wrong_source}/{len(rows)} rows")

    mix1_pool_rows = _read_jsonl(mix1_pool_path)
    hist = pool_histogram(rows, mix1_rows=mix1_pool_rows)
    mix_hist = pool_histogram(mix1_pool_rows[:40], mix1_rows=mix1_pool_rows)

    fam = hist.get("family") or {}
    if fam.get("flashlight", 0) != len(rows):
        blockers.append(f"non-flashlight rows: {len(rows) - int(fam.get('flashlight', 0))}")

    nm_mean = (hist.get("near_miss") or {}).get("mean")
    if nm_mean is None:
        blockers.append("near_miss unavailable on pool")
    elif not (0.50 <= float(nm_mean) <= 0.90):
        blockers.append(f"near_miss mean {nm_mean:.3f} outside build band [0.50, 0.90]")

    bad_elen = sum(
        1
        for r in rows
        if not (24 <= len(str(r.get("expected") or "")) <= 80)
    )
    if bad_elen:
        blockers.append(f"expected_len outside [24, 80] on {bad_elen}/{len(rows)} rows")

    trait_deltas = {
        "fail_to_pass_mean": _trait_delta(hist, mix_hist, "fail_to_pass"),
        "near_miss_mean": _trait_delta(hist, mix_hist, "near_miss"),
        "expected_len_mean": _trait_delta(hist, mix_hist, "expected_len"),
        "prompt_tokens_mean": _trait_delta(hist, mix_hist, "prompt_tokens"),
        "n_f2p_2_4": {
            "observed": hist.get("n_f2p_2_4"),
            "reference": mix_hist.get("n_f2p_2_4"),
        },
    }

    f2p_delta = trait_deltas["fail_to_pass_mean"].get("delta")
    if f2p_delta is not None and float(f2p_delta) < -0.5:
        warnings.append(
            f"F2P mean lighter than Mix1 by {abs(float(f2p_delta)):.2f} "
            "(gym_alt max_f2p=3; winner-pattern risk)"
        )
    tok_delta = trait_deltas["prompt_tokens_mean"].get("delta")
    if tok_delta is not None and float(tok_delta) > 50:
        warnings.append(
            f"prompt_tokens mean +{float(tok_delta):.0f} vs Mix1 (higher list-price / behavior risk)"
        )

    spend_usd = None
    spend_error = None
    if spend_path.exists():
        raw = spend_path.read_text(encoding="utf-8").strip()
        try:
            spend_usd = float(raw) if raw else None
        except ValueError:
            spend_error = f"invalid spend value: {raw!r}"
    else:
        spend_error = "missing spend file"

    try:
        from scripts.hard_y_probe import project_gold_cost  # type: ignore
    except Exception:
        sys.path.insert(0, str(ROOT / "scripts"))
        from hard_y_probe import project_gold_cost  # type: ignore

    projected = project_gold_cost(pool_path, limit=limit)
    budget_limit = (spend_usd or 0.0) + budget_cap_usd
    within_cap = (spend_usd or 0.0) + projected["projected_usd"] <= budget_limit

    if spend_error:
        blockers.append(spend_error)
    if not within_cap:
        blockers.append("projected spend exceeds budget cap")

    api_key_present = bool(os.getenv("AIAND_API_KEY", "").strip())

    mix1_gold_rows = _read_jsonl(mix1_gold_path)
    cal = build_order_mix_calibration(mix1_gold_rows, mix1_pool_rows)
    winner_proj = project_order_mix_winner_mix(
        rows,
        cal,
        kimi_only_floor=GYM_ALT_KIMI_ONLY_FLOOR,
        all_fail_ceiling=GYM_ALT_ALL_FAIL_CEILING,
    )
    om_hist = order_mix_histogram(
        rows, mix1_gold=mix1_gold_rows, mix1_pool_rows=mix1_pool_rows
    )
    class_counts = om_hist.get("order_mix_class") or {}

    if not winner_proj.get("kimi_only_floor_ok"):
        blockers.append(
            f"projected kimi-only {winner_proj.get('kimi-only')} "
            f"< floor {GYM_ALT_KIMI_ONLY_FLOOR}"
        )
    if not winner_proj.get("all_fail_ceiling_ok"):
        blockers.append(
            f"projected all-fail {winner_proj.get('all-fail')} "
            f"> ceiling {GYM_ALT_ALL_FAIL_CEILING}"
        )

    structural_ok = not any(
        b.startswith(
            (
                "missing pool",
                "pool shortfall",
                "collision",
                "missing expected",
                "missing FAIL_TO_PASS",
                "non swe-gym",
                "non-flashlight",
                "near_miss",
                "expected_len",
            )
        )
        for b in blockers
    )
    winner_ok = bool(winner_proj.get("winner_mix_gate_pass"))
    paid_justified = structural_ok and within_cap and spend_error is None and winner_ok

    return {
        "helper_command": ".\\scripts\\gym_alt_preflight.py",
        "seed_name": seed_name,
        "limit": limit,
        "pool_path": pool_path.as_posix(),
        "pool_n": len(rows),
        "collision_hits": len(collision_hits),
        "histogram": hist,
        "mix1_reference_histogram": mix_hist,
        "trait_deltas_vs_mix1": trait_deltas,
        "order_mix_class": class_counts,
        "order_mix_class_frac": om_hist.get("order_mix_class_frac"),
        "projected_winner_mix": winner_proj,
        "projected": projected,
        "spend_usd": spend_usd,
        "budget_cap_usd": budget_cap_usd,
        "within_budget_cap": within_cap,
        "api_key_present": api_key_present,
        "paid_gold_justified": paid_justified,
        "blockers": blockers,
        "trait_warnings": warnings,
        "paid_command": paid_probe_command(
            spend_path=spend_path,
            budget_cap_usd=budget_cap_usd,
            seed_name=seed_name,
            limit=limit,
            pool_path=pool_path,
        )
        if paid_justified
        else None,
        "preflight_geometry_predictor": {
            "valid": False,
            "reason": (
                "Smith seeds 11–16 and seed-16 order-mix preflight falsified offline trait "
                "predictors; gym_alt winner-mix projection is a pool-construction gate only "
                "(kimi-only >=20% / all-fail <=70% from Mix1 buckets). "
                "Only standalone geometry after paid gold is authoritative."
            ),
        },
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "# SWE-Gym gym_alt unpaid preflight",
        "",
        f"- Pool: `{report.get('pool_path')}` (n={report.get('pool_n')})",
        f"- Probe limit: n={report.get('limit')} seed `{report.get('seed_name')}`",
        f"- Collision hits vs excluded gold: `{report.get('collision_hits')}`",
        f"- Paid gold justified: `{str(report.get('paid_gold_justified')).lower()}`",
        f"- API key present: `{str(report.get('api_key_present')).lower()}`",
        "",
        "## Trait histogram vs Mix1 (offline)",
        "",
        "| metric | gym_alt | Mix1 pool | delta |",
        "| --- | --- | --- | --- |",
    ]
    hist = report.get("histogram") or {}
    mix = report.get("mix1_reference_histogram") or {}
    for key, label in (
        ("fail_to_pass", "F2P mean"),
        ("near_miss", "near-miss mean"),
        ("expected_len", "expected len mean"),
        ("prompt_tokens", "prompt tokens mean"),
    ):
        o = (hist.get(key) or {}).get("mean")
        r = (mix.get(key) or {}).get("mean")
        d = (report.get("trait_deltas_vs_mix1") or {}).get(f"{key}_mean", {}).get("delta")
        d_s = f"{float(d):+.3f}" if d is not None else "—"
        o_s = f"{float(o):.3f}" if o is not None else "—"
        r_s = f"{float(r):.3f}" if r is not None else "—"
        lines.append(f"| {label} | {o_s} | {r_s} | {d_s} |")
    lines.extend(
        [
            "",
            f"- n_f2p_2_4: gym_alt `{hist.get('n_f2p_2_4')}` vs Mix1 `{mix.get('n_f2p_2_4')}`",
            "",
            "## Order-mix class + projected winner mix (offline)",
            "",
            f"- Classes: `{report.get('order_mix_class')}`",
            f"- Class frac: `{report.get('order_mix_class_frac')}`",
        ]
    )
    wp = report.get("projected_winner_mix") or {}
    lines.extend(
        [
            f"- Projected kimi-only: `{wp.get('kimi-only')}` "
            f"(floor {wp.get('kimi_only_floor')}; ok=`{wp.get('kimi_only_floor_ok')}`)",
            f"- Projected all-fail: `{wp.get('all-fail')}` "
            f"(ceiling {wp.get('all_fail_ceiling')}; ok=`{wp.get('all_fail_ceiling_ok')}`)",
            f"- Winner-mix gate: `{wp.get('winner_mix_gate_pass')}`",
            "",
            "## Budget",
            "",
            f"- Projected gold USD (n={report.get('limit')}): `{report.get('projected', {}).get('projected_usd')}`",
            f"- Spend file: `{report.get('spend_usd')}`",
            f"- Within budget cap (+{report.get('budget_cap_usd')} USD): `{report.get('within_budget_cap')}`",
        ]
    )
    warnings = report.get("trait_warnings") or []
    if warnings:
        lines.extend(["", "## Trait warnings (non-blocking)", ""])
        lines.extend(f"- {w}" for w in warnings)
    blockers = report.get("blockers") or []
    if blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {b}" for b in blockers)
    pred = report.get("preflight_geometry_predictor") or {}
    lines.extend(
        [
            "",
            "## Geometry predictor",
            "",
            f"- Offline preflight valid: `{pred.get('valid')}`",
            f"- {pred.get('reason')}",
        ]
    )
    paid_cmd = report.get("paid_command")
    if paid_cmd:
        lines.extend(["", "## Paid command (only if justified + key present)", "", "```powershell", str(paid_cmd), "```"])
    else:
        lines.extend(["", "## Paid command", "", "_Withheld — preflight gate did not pass._"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Unpaid gym_alt hard-y probe preflight")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report", help="Optional output path for rendered report")
    parser.add_argument("--pool", default=str(DEFAULT_POOL))
    parser.add_argument("--mix1-pool", default=str(DEFAULT_MIX1_POOL))
    parser.add_argument("--mix1", default=str(DEFAULT_MIX1))
    parser.add_argument("--spend", default=str(DEFAULT_SPEND))
    parser.add_argument("--budget-cap", type=float, default=15.0)
    parser.add_argument("--seed-name", default="gym-alt-seed2")
    parser.add_argument("--limit", type=int, default=32)
    args = parser.parse_args(argv)

    report = build_report(
        pool_path=Path(args.pool),
        mix1_pool_path=Path(args.mix1_pool),
        mix1_gold_path=Path(args.mix1),
        spend_path=Path(args.spend),
        budget_cap_usd=float(args.budget_cap),
        seed_name=str(args.seed_name),
        limit=int(args.limit),
        exclude_paths=list(DEFAULT_EXCLUDE),
    )
    rendered = json.dumps(report, indent=2) if args.json else render_text(report)
    if args.report:
        Path(args.report).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["paid_gold_justified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
