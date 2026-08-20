"""Unpaid hard-y gold probe helpers: cost projection and geometry preflight.

No aiand credits. Used by scripts/run_hard_y_probe.ps1 before opt-in gold.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from aiand_router.geometry import geometry_report, winner_diagnosis_table  # noqa: E402
from aiand_router.pool import (  # noqa: E402
    GYM_ALT_ORDER_MIX_TARGETS,
    build_order_mix_calibration,
    collect_gym_alt_order_mix_queries,
    collect_kimi_only_targeted_queries,
    collect_mix1like_queries,
    collect_order_mix_conservative_queries,
    collect_winner_stratified_queries,
    collision_keys,
    kimi_only_histogram,
    mix1_kimi_only_pool_rows,
    order_mix_histogram,
    pool_histogram,
    project_order_mix_winner_mix,
    retroactive_order_mix_audit,
    sample_unlabeled,
    winner_stratified_histogram,
    write_pool,
)
from aiand_router.router import estimate_cost, estimate_tokens, load_config, load_models  # noqa: E402
from aiand_router.train import (  # noqa: E402
    GOLD_MAX_TOKENS,
    GOLD_REASONING_MAX_TOKENS,
    MIN_REASONING_EFFORT,
    _gold_ids,
    _messages,
)


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def project_gold_cost(
    queries_path: Path,
    *,
    models_yaml: Path | None = None,
    limit: int = 0,
) -> dict:
    """Upper-bound list-price for sparse gold (Flash + measured trio when eligible)."""
    cfg = load_config(models_yaml or ROOT / "config" / "models.yaml")
    by_id = {m.id: m for m in load_models(cfg)}
    queries = _read_jsonl(queries_path)
    if limit:
        queries = queries[:limit]
    cells = 0
    usd = 0.0
    per_model: dict[str, float] = {}
    for q in queries:
        messages = _messages(q)
        prompt_tokens = estimate_tokens(messages)
        for mid in _gold_ids(q, by_id, dense=False):
            effort = MIN_REASONING_EFFORT.get(mid)
            max_out = (
                GOLD_REASONING_MAX_TOKENS
                if effort and effort != "none"
                else GOLD_MAX_TOKENS
            )
            c = estimate_cost(by_id[mid], prompt_tokens, max_out)
            usd += c
            cells += 1
            per_model[mid] = per_model.get(mid, 0.0) + c
    return {
        "queries": len(queries),
        "cells": cells,
        "projected_usd": round(usd, 4),
        "per_model_usd": {k: round(v, 4) for k, v in sorted(per_model.items())},
    }


def preflight(
    *,
    pool_path: Path,
    train_gold: Path | None,
    eval_gold: Path,
    spend_path: Path,
    budget_cap_usd: float,
    limit: int,
) -> dict:
    proj = project_gold_cost(pool_path, limit=limit)
    spend_before = 0.0
    if spend_path.exists():
        spend_before = float(spend_path.read_text(encoding="utf-8").strip() or "0")
    budget_limit = spend_before + budget_cap_usd
    geo: dict | None = None
    if train_gold and train_gold.exists():
        geo = geometry_report(train_gold, eval_gold)
    return {
        "projected": proj,
        "spend_before_usd": round(spend_before, 6),
        "budget_cap_usd": budget_cap_usd,
        "budget_limit_usd": round(budget_limit, 6),
        "projected_total_usd": round(spend_before + proj["projected_usd"], 6),
        "within_cap": (spend_before + proj["projected_usd"]) <= budget_limit,
        "geometry": geo,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hard-y probe preflight (unpaid)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("project", help="Project sparse gold list-price upper bound")
    p.add_argument("--queries", required=True, help="Pool JSONL from train pool")
    p.add_argument("--limit", type=int, default=0, help="Cap query count (0 = all)")
    p.add_argument("--models", help="models.yaml path")

    pf = sub.add_parser("preflight", help="Cost projection + optional geometry on existing gold")
    pf.add_argument("--pool", required=True)
    pf.add_argument("--eval", default="data/gold-verified.jsonl")
    pf.add_argument("--train-gold", help="Existing sparse gold for geometry (dry-run reuse)")
    pf.add_argument("--spend", default="data/spend.txt")
    pf.add_argument("--budget-cap", type=float, default=15.0)
    pf.add_argument("--limit", type=int, default=40)

    s = sub.add_parser(
        "sample",
        help="Unpaid Mix1-like sample from a pool, excluding already-labeled gold ids/prompts",
    )
    s.add_argument("--queries", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--limit", type=int, default=32)
    s.add_argument("--seed", type=int, default=12)
    s.add_argument("--exclude", action="append", default=[], help="Labeled gold/pool JSONL (repeatable)")
    s.add_argument("--max-fail-to-pass", type=int, default=6)
    s.add_argument("--near-miss-lo", type=float, default=0.55)
    s.add_argument("--near-miss-hi", type=float, default=0.88)
    s.add_argument("--min-expected-len", type=int, default=24)
    s.add_argument("--max-expected-len", type=int, default=80)
    s.add_argument("--min-fail-to-pass", type=int, default=0)

    ml = sub.add_parser(
        "mix1like-pool",
        help="Unpaid Mix1-like query pool from local SWE-smith dumps (no gold spend)",
    )
    ml.add_argument("--smith", default="data/smith-tool.jsonl")
    ml.add_argument("--tasks", default="data/smith-task-checks.jsonl")
    ml.add_argument("--eval", default="data/gold-verified.jsonl")
    ml.add_argument("--out", default="data/pool-hard-mix-mix1like.jsonl")
    ml.add_argument("--mix1", default="data/gold-sparse-hard-mix1.jsonl")
    ml.add_argument("--exclude", action="append", default=[], help="Labeled gold JSONL (repeatable)")
    ml.add_argument("--near-miss-lo", type=float, default=0.55)
    ml.add_argument("--near-miss-hi", type=float, default=0.88)
    ml.add_argument("--min-expected-len", type=int, default=24)
    ml.add_argument("--max-expected-len", type=int, default=80)
    ml.add_argument("--max-fail-to-pass", type=int, default=6)
    ml.add_argument("--min-fail-to-pass", type=int, default=1)
    ml.add_argument("--verified-like-max-tokens", type=int, default=200)

    g = sub.add_parser("geometry-sweep", help="Print geometry table for train files vs eval")
    g.add_argument("--eval", default="data/gold-verified.jsonl")
    g.add_argument("train_files", nargs="+", help="Train gold JSONL paths")

    wd = sub.add_parser(
        "winner-diagnosis",
        help="Winner-pattern table for Mix1 vs seed batches vs verified (unpaid)",
    )
    wd.add_argument("--eval", default="data/gold-verified.jsonl")
    wd.add_argument("--mix1-pool", default="data/pool-hard-mix-near_miss_seed11.jsonl")
    wd.add_argument(
        "gold_files",
        nargs="*",
        default=[
            "data/gold-sparse-hard-mix1.jsonl",
            "data/gold-sparse-hard-mix1-train.jsonl",
            "data/gold-sparse-hard-mix1-topup32.jsonl",
            "data/gold-sparse-hard-probe-seed11.jsonl",
            "data/gold-sparse-hard-probe-seed12.jsonl",
            "data/gold-sparse-hard-probe-seed13.jsonl",
            "data/gold-sparse-hard-probe-seed14.jsonl",
            "data/gold-sparse-hard-probe-seed15.jsonl",
            "data/gold-sparse-hard-probe-seed16.jsonl",
            "data/gold-verified.jsonl",
        ],
    )

    ws = sub.add_parser(
        "winner-stratified-pool",
        help="Unpaid winner-mix stratified pool (F2P 2-4, near-miss 0.55-0.88, Mix1 proxy strata)",
    )
    ws.add_argument("--smith", default="data/smith-tool.jsonl")
    ws.add_argument("--tasks", default="data/smith-task-checks.jsonl")
    ws.add_argument("--eval", default="data/gold-verified.jsonl")
    ws.add_argument("--out", default="data/pool-hard-mix-winner-stratified.jsonl")
    ws.add_argument("--mix1-pool", default="data/pool-hard-mix-near_miss_seed11.jsonl")
    ws.add_argument("--mix1", default="data/gold-sparse-hard-mix1.jsonl")
    ws.add_argument("--exclude", action="append", default=[], help="Labeled gold JSONL (repeatable)")
    ws.add_argument("--near-miss-lo", type=float, default=0.55)
    ws.add_argument("--near-miss-hi", type=float, default=0.88)
    ws.add_argument("--min-expected-len", type=int, default=24)
    ws.add_argument("--max-expected-len", type=int, default=80)
    ws.add_argument("--min-fail-to-pass", type=int, default=2)
    ws.add_argument("--max-fail-to-pass", type=int, default=4)
    ws.add_argument("--verified-like-max-tokens", type=int, default=200)
    ws.add_argument("--seed", type=int, default=0)
    ws.add_argument("--cap", type=int, default=0, help="Max pool rows (0 = all stratified matches)")

    ko = sub.add_parser(
        "kimi-only-pool",
        help="Unpaid Kimi-only-targeted pool from smith (Mix1 Kimi-only proxy traits)",
    )
    ko.add_argument("--smith", default="data/smith-tool.jsonl")
    ko.add_argument("--tasks", default="data/smith-task-checks.jsonl")
    ko.add_argument("--eval", default="data/gold-verified.jsonl")
    ko.add_argument("--out", default="data/pool-hard-mix-kimi-only-targeted.jsonl")
    ko.add_argument("--mix1", default="data/gold-sparse-hard-mix1.jsonl")
    ko.add_argument("--mix1-pool", default="data/pool-hard-mix-near_miss_seed11.jsonl")
    ko.add_argument("--exclude", action="append", default=[], help="Labeled gold JSONL (repeatable)")
    ko.add_argument("--near-miss-lo", type=float, default=0.55)
    ko.add_argument("--near-miss-hi", type=float, default=0.88)
    ko.add_argument("--min-expected-len", type=int, default=24)
    ko.add_argument("--max-expected-len", type=int, default=64)
    ko.add_argument("--min-fail-to-pass", type=int, default=1)
    ko.add_argument("--max-fail-to-pass", type=int, default=4)
    ko.add_argument("--verified-like-max-tokens", type=int, default=200)
    ko.add_argument(
        "--no-mutation-filter",
        action="store_true",
        help="Drop func_pm_* instance_id filter (broader, lower confidence)",
    )

    om = sub.add_parser(
        "order-mix-pool",
        help="Unpaid order-mix conservative pool (good-pattern strata, nm cap 0.82, F2P 2-4)",
    )
    om.add_argument("--smith", default="data/smith-tool.jsonl")
    om.add_argument(
        "--from-pool",
        default="data/pool-hard-mix-mix1like.jsonl",
        help="Re-filter an existing unpaid pool dump; omit or set empty to scan --smith",
    )
    om.add_argument("--tasks", default="data/smith-task-checks.jsonl")
    om.add_argument("--eval", default="data/gold-verified.jsonl")
    om.add_argument("--out", default="data/pool-hard-mix-order-conservative.jsonl")
    om.add_argument("--mix1", default="data/gold-sparse-hard-mix1.jsonl")
    om.add_argument("--mix1-pool", default="data/pool-hard-mix-near_miss_seed11.jsonl")
    om.add_argument("--exclude", action="append", default=[], help="Labeled gold JSONL (repeatable)")
    om.add_argument("--near-miss-lo", type=float, default=0.55)
    om.add_argument("--near-miss-hi", type=float, default=0.85)
    om.add_argument("--min-expected-len", type=int, default=24)
    om.add_argument("--max-expected-len", type=int, default=80)
    om.add_argument("--min-fail-to-pass", type=int, default=1)
    om.add_argument("--max-fail-to-pass", type=int, default=5)
    om.add_argument("--verified-like-max-tokens", type=int, default=200)
    om.add_argument("--seed", type=int, default=0)
    om.add_argument("--sample-n", type=int, default=32, help="Class-quota sample size (0 = full reservoir)")
    om.add_argument("--cap", type=int, default=0, help="Max reservoir rows before sampling (0 = all matches)")
    om.add_argument(
        "--no-mutation-filter",
        action="store_true",
        help="Drop func_pm_* instance_id filter (broader, lower confidence)",
    )

    ga = sub.add_parser(
        "gym-alt-pool",
        help=(
            "Unpaid SWE-Gym gym_alt pool with Mix1 order-mix class quotas "
            "(kimi-heavy bias; no smith mutation markers)"
        ),
    )
    ga.add_argument("--gym-tasks", default="data/dump_cache/swe_gym_tasks.jsonl")
    ga.add_argument(
        "--from-pool",
        default="",
        help="Optional existing gym_alt dry-run pool; empty → build from --gym-tasks",
    )
    ga.add_argument("--eval", default="data/gold-verified.jsonl")
    ga.add_argument("--out", default="data/pool-hard-gym-alt-seed2-n40.jsonl")
    ga.add_argument("--mix1", default="data/gold-sparse-hard-mix1.jsonl")
    ga.add_argument("--mix1-pool", default="data/pool-hard-mix-near_miss_seed11.jsonl")
    ga.add_argument("--exclude", action="append", default=[], help="Labeled gold JSONL (repeatable)")
    ga.add_argument("--near-miss-lo", type=float, default=0.55)
    ga.add_argument("--near-miss-hi", type=float, default=0.85)
    ga.add_argument("--min-expected-len", type=int, default=24)
    ga.add_argument("--max-expected-len", type=int, default=80)
    ga.add_argument("--min-fail-to-pass", type=int, default=1)
    ga.add_argument("--max-fail-to-pass", type=int, default=3)
    ga.add_argument("--verified-like-max-tokens", type=int, default=220)
    ga.add_argument("--seed", type=int, default=18)
    ga.add_argument("--sample-n", type=int, default=40)
    ga.add_argument("--cap", type=int, default=0)

    args = parser.parse_args(argv)
    if args.cmd == "project":
        out = project_gold_cost(
            Path(args.queries),
            models_yaml=Path(args.models) if args.models else None,
            limit=int(args.limit or 0),
        )
        print(json.dumps(out, indent=2))
        return 0
    if args.cmd == "preflight":
        out = preflight(
            pool_path=Path(args.pool),
            train_gold=Path(args.train_gold) if args.train_gold else None,
            eval_gold=Path(args.eval),
            spend_path=Path(args.spend),
            budget_cap_usd=float(args.budget_cap),
            limit=int(args.limit),
        )
        print(json.dumps(out, indent=2))
        if not out["within_cap"]:
            print("refusing: projected spend exceeds budget cap", file=sys.stderr)
            return 2
        if out.get("geometry"):
            geo = out["geometry"]
            print("geometry_pass", geo.get("geometry_pass"), file=sys.stderr)
            print("kill", geo.get("kill"), file=sys.stderr)
        return 0
    if args.cmd == "sample":
        pool = _read_jsonl(Path(args.queries))
        blocked: set[str] = set()
        for ep in args.exclude or []:
            blocked |= collision_keys(_read_jsonl(Path(ep)))
        picked = sample_unlabeled(
            pool,
            n=int(args.limit),
            seed=int(args.seed),
            blocked=blocked,
            max_fail_to_pass=int(args.max_fail_to_pass),
            near_miss_lo=float(args.near_miss_lo),
            near_miss_hi=float(args.near_miss_hi),
            min_expected_len=int(args.min_expected_len),
            max_expected_len=int(args.max_expected_len),
            min_fail_to_pass=int(getattr(args, "min_fail_to_pass", 0) or 0),
        )
        if not picked:
            print("refusing: sample_unlabeled left no queries", file=sys.stderr)
            return 2
        write_pool(picked, Path(args.out))
        print(
            json.dumps(
                {
                    "n": len(picked),
                    "out": args.out,
                    "seed": args.seed,
                    "excluded_keys": len(blocked),
                    "max_fail_to_pass": args.max_fail_to_pass,
                },
                indent=2,
            )
        )
        return 0
    if args.cmd == "mix1like-pool":
        if not args.exclude:
            args.exclude = [
                "data/gold-sparse-hard-mix1.jsonl",
                "data/gold-sparse-hard-mix1-train.jsonl",
                "data/gold-sparse-hard-mix1-retune.jsonl",
                "data/gold-sparse-hard-mix1-topup32.jsonl",
                "data/gold-sparse-hard-probe-seed11.jsonl",
                "data/gold-sparse-hard-probe-seed12.jsonl",
            ]
        smith = Path(args.smith)
        if not smith.exists():
            fallback = ROOT / "data" / "smith-tool-sample.jsonl"
            if fallback.exists():
                print(f"smith missing {smith}; using {fallback}", file=sys.stderr)
                smith = fallback
            else:
                print(f"refusing: smith dump not found: {smith}", file=sys.stderr)
                return 2
        blocked: set[str] = set()
        eval_path = Path(args.eval)
        if eval_path.exists():
            blocked |= collision_keys(_read_jsonl(eval_path))
        for ep in args.exclude or []:
            p = Path(ep)
            if p.exists():
                blocked |= collision_keys(_read_jsonl(p))
        mix1_path = Path(args.mix1)
        mix1_rows = _read_jsonl(mix1_path) if mix1_path.exists() else []
        if mix1_rows:
            blocked |= collision_keys(mix1_rows)
        tasks = Path(args.tasks) if args.tasks else None
        rows = collect_mix1like_queries(
            smith,
            tasks if tasks and tasks.exists() else None,
            blocked=blocked,
            max_tokens=int(args.verified_like_max_tokens),
            min_expected_len=int(args.min_expected_len),
            max_expected_len=int(args.max_expected_len),
            near_miss_lo=float(args.near_miss_lo),
            near_miss_hi=float(args.near_miss_hi),
            max_fail_to_pass=int(args.max_fail_to_pass),
            min_fail_to_pass=int(args.min_fail_to_pass),
        )
        if not rows:
            print("refusing: mix1like pool is empty", file=sys.stderr)
            return 2
        write_pool(rows, Path(args.out))
        hist = pool_histogram(rows, mix1_rows=mix1_rows)
        print(json.dumps({"out": args.out, "smith": str(smith), **hist}, indent=2))
        return 0
    if args.cmd == "geometry-sweep":
        eval_path = Path(args.eval)
        rows = []
        for tf in args.train_files:
            p = Path(tf)
            if not p.exists():
                rows.append({"train": str(p), "error": "missing"})
                continue
            r = geometry_report(p, eval_path)
            rows.append(
                {
                    "train": str(p),
                    "spearman": r.get("spearman_train_eval"),
                    "y_rate": r.get("train", {}).get("y_rate"),
                    "geometry_pass": r.get("geometry_pass"),
                    "kill": r.get("kill"),
                    "holdout_like_order": r.get("holdout_like_order"),
                }
            )
        print(json.dumps(rows, indent=2))
        return 0
    if args.cmd == "winner-diagnosis":
        eval_path = Path(args.eval)
        labels = [
            ("mix1", "data/gold-sparse-hard-mix1.jsonl"),
            ("mix1-train", "data/gold-sparse-hard-mix1-train.jsonl"),
            ("seed11-topup", "data/gold-sparse-hard-mix1-topup32.jsonl"),
            ("seed11-probe", "data/gold-sparse-hard-probe-seed11.jsonl"),
            ("seed12", "data/gold-sparse-hard-probe-seed12.jsonl"),
            ("seed13", "data/gold-sparse-hard-probe-seed13.jsonl"),
            ("seed14", "data/gold-sparse-hard-probe-seed14.jsonl"),
            ("seed15", "data/gold-sparse-hard-probe-seed15.jsonl"),
            ("seed16", "data/gold-sparse-hard-probe-seed16.jsonl"),
            ("verified", "data/gold-verified.jsonl"),
        ]
        slices: list[tuple[str, Path]] = []
        for label, default in labels:
            p = Path(default)
            if p.exists():
                slices.append((label, p))
        for gf in args.gold_files or []:
            p = Path(gf)
            if p.exists() and not any(s[1] == p for s in slices):
                slices.append((p.stem, p))
        table = winner_diagnosis_table(slices, eval_path=eval_path if eval_path.exists() else None)
        print(json.dumps(table, indent=2))
        return 0
    if args.cmd == "winner-stratified-pool":
        if not args.exclude:
            args.exclude = [
                "data/gold-sparse-hard-mix1.jsonl",
                "data/gold-sparse-hard-mix1-train.jsonl",
                "data/gold-sparse-hard-mix1-retune.jsonl",
                "data/gold-sparse-hard-mix1-topup32.jsonl",
                "data/gold-sparse-hard-probe-seed11.jsonl",
                "data/gold-sparse-hard-probe-seed12.jsonl",
                "data/gold-sparse-hard-probe-seed13.jsonl",
            ]
        smith = Path(args.smith)
        if not smith.exists():
            fallback = ROOT / "data" / "smith-tool-sample.jsonl"
            if fallback.exists():
                print(f"smith missing {smith}; using {fallback}", file=sys.stderr)
                smith = fallback
            else:
                print(f"refusing: smith dump not found: {smith}", file=sys.stderr)
                return 2
        blocked: set[str] = set()
        eval_path = Path(args.eval)
        if eval_path.exists():
            blocked |= collision_keys(_read_jsonl(eval_path))
        for ep in args.exclude or []:
            p = Path(ep)
            if p.exists():
                blocked |= collision_keys(_read_jsonl(p))
        mix1_gold = Path(args.mix1)
        if mix1_gold.exists():
            blocked |= collision_keys(_read_jsonl(mix1_gold))
        mix1_pool_path = Path(args.mix1_pool)
        mix1_pool_rows = _read_jsonl(mix1_pool_path) if mix1_pool_path.exists() else []
        if mix1_pool_rows:
            blocked |= collision_keys(mix1_pool_rows)
        tasks = Path(args.tasks) if args.tasks else None
        rows = collect_winner_stratified_queries(
            smith,
            tasks if tasks and tasks.exists() else None,
            blocked=blocked,
            max_tokens=int(args.verified_like_max_tokens),
            min_expected_len=int(args.min_expected_len),
            max_expected_len=int(args.max_expected_len),
            near_miss_lo=float(args.near_miss_lo),
            near_miss_hi=float(args.near_miss_hi),
            min_fail_to_pass=int(args.min_fail_to_pass),
            max_fail_to_pass=int(args.max_fail_to_pass),
            mix1_pool_rows=mix1_pool_rows,
            seed=int(args.seed),
            cap=int(args.cap or 0),
        )
        if not rows:
            print("refusing: winner-stratified pool is empty", file=sys.stderr)
            return 2
        write_pool(rows, Path(args.out))
        hist = winner_stratified_histogram(rows, mix1_rows=mix1_pool_rows)
        print(json.dumps({"out": args.out, "smith": str(smith), **hist}, indent=2))
        return 0
    if args.cmd == "kimi-only-pool":
        if not args.exclude:
            args.exclude = [
                "data/gold-sparse-hard-mix1.jsonl",
                "data/gold-sparse-hard-mix1-train.jsonl",
                "data/gold-sparse-hard-mix1-retune.jsonl",
                "data/gold-sparse-hard-mix1-topup32.jsonl",
                "data/gold-sparse-hard-probe-seed11.jsonl",
                "data/gold-sparse-hard-probe-seed12.jsonl",
                "data/gold-sparse-hard-probe-seed13.jsonl",
                "data/gold-sparse-hard-probe-seed14.jsonl",
            ]
        smith = Path(args.smith)
        if not smith.exists():
            fallback = ROOT / "data" / "smith-tool-sample.jsonl"
            if fallback.exists():
                print(f"smith missing {smith}; using {fallback}", file=sys.stderr)
                smith = fallback
            else:
                print(f"refusing: smith dump not found: {smith}", file=sys.stderr)
                return 2
        blocked: set[str] = set()
        eval_path = Path(args.eval)
        if eval_path.exists():
            blocked |= collision_keys(_read_jsonl(eval_path))
        for ep in args.exclude or []:
            p = Path(ep)
            if p.exists():
                blocked |= collision_keys(_read_jsonl(p))
        mix1_gold = Path(args.mix1)
        if mix1_gold.exists():
            blocked |= collision_keys(_read_jsonl(mix1_gold))
        mix1_pool_path = Path(args.mix1_pool)
        mix1_pool_rows = _read_jsonl(mix1_pool_path) if mix1_pool_path.exists() else []
        mix1_kimi_rows = (
            mix1_kimi_only_pool_rows(_read_jsonl(mix1_gold), mix1_pool_rows)
            if mix1_gold.exists() and mix1_pool_rows
            else []
        )
        tasks = Path(args.tasks) if args.tasks else None
        rows = collect_kimi_only_targeted_queries(
            smith,
            tasks if tasks and tasks.exists() else None,
            blocked=blocked,
            max_tokens=int(args.verified_like_max_tokens),
            near_miss_lo=float(args.near_miss_lo),
            near_miss_hi=float(args.near_miss_hi),
            min_expected_len=int(args.min_expected_len),
            max_expected_len=int(args.max_expected_len),
            min_fail_to_pass=int(args.min_fail_to_pass),
            max_fail_to_pass=int(args.max_fail_to_pass),
            require_mutation=not bool(args.no_mutation_filter),
        )
        if not rows:
            print("refusing: kimi-only-targeted pool is empty", file=sys.stderr)
            return 2
        write_pool(rows, Path(args.out))
        hist = kimi_only_histogram(rows, mix1_kimi_rows=mix1_kimi_rows)
        print(json.dumps({"out": args.out, "smith": str(smith), **hist}, indent=2))
        return 0
    if args.cmd == "order-mix-pool":
        if not args.exclude:
            args.exclude = [
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
            ]
        blocked: set[str] = set()
        eval_path = Path(args.eval)
        if eval_path.exists():
            blocked |= collision_keys(_read_jsonl(eval_path))
        for ep in args.exclude or []:
            p = Path(ep)
            if p.exists():
                blocked |= collision_keys(_read_jsonl(p))
        mix1_gold_path = Path(args.mix1)
        mix1_gold = _read_jsonl(mix1_gold_path) if mix1_gold_path.exists() else []
        if mix1_gold:
            blocked |= collision_keys(mix1_gold)
        mix1_pool_path = Path(args.mix1_pool)
        mix1_pool_rows = _read_jsonl(mix1_pool_path) if mix1_pool_path.exists() else []
        if mix1_pool_rows:
            blocked |= collision_keys(mix1_pool_rows)
        tasks = Path(args.tasks) if args.tasks else None
        from_pool = Path(args.from_pool) if getattr(args, "from_pool", None) else None
        source_rows = None
        if from_pool and from_pool.exists() and str(from_pool) not in ("NONEXISTENT", "-", ""):
            source_rows = _read_jsonl(from_pool)
        smith_path: Path | None = None
        if not source_rows:
            smith_path = Path(args.smith)
            if not smith_path.exists():
                fallback = ROOT / "data" / "smith-tool-sample.jsonl"
                if fallback.exists():
                    print(f"smith missing {smith_path}; using {fallback}", file=sys.stderr)
                    smith_path = fallback
                else:
                    print(f"refusing: smith dump not found: {smith_path}", file=sys.stderr)
                    return 2
        rows = collect_order_mix_conservative_queries(
            smith_path,
            tasks if tasks and tasks.exists() else None,
            source_pool=source_rows,
            blocked=blocked,
            mix1_gold=mix1_gold,
            mix1_pool_rows=mix1_pool_rows,
            max_tokens=int(args.verified_like_max_tokens),
            near_miss_lo=float(args.near_miss_lo),
            near_miss_hi=float(args.near_miss_hi),
            min_expected_len=int(args.min_expected_len),
            max_expected_len=int(args.max_expected_len),
            min_fail_to_pass=int(args.min_fail_to_pass),
            max_fail_to_pass=int(args.max_fail_to_pass),
            require_mutation=not args.no_mutation_filter,
            mutation_waiver_kimi_heavy=True,
            exclude_unknown_class=True,
            seed=int(args.seed),
            cap=int(args.cap),
            sample_n=int(getattr(args, "sample_n", 0) or 0),
        )
        if not rows:
            print("refusing: order-mix conservative pool is empty", file=sys.stderr)
            return 2
        write_pool(rows, Path(args.out))
        hist = order_mix_histogram(
            rows,
            mix1_gold=mix1_gold,
            mix1_pool_rows=mix1_pool_rows,
        )
        src = str(from_pool) if source_rows else str(smith_path)
        print(json.dumps({"out": args.out, "source": src, **hist}, indent=2))
        return 0
    if args.cmd == "gym-alt-pool":
        if not args.exclude:
            args.exclude = [
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
        blocked: set[str] = set()
        eval_path = Path(args.eval)
        if eval_path.exists():
            blocked |= collision_keys(_read_jsonl(eval_path))
        for ep in args.exclude or []:
            p = Path(ep)
            if p.exists():
                blocked |= collision_keys(_read_jsonl(p))
        mix1_gold_path = Path(args.mix1)
        mix1_gold = _read_jsonl(mix1_gold_path) if mix1_gold_path.exists() else []
        if mix1_gold:
            blocked |= collision_keys(mix1_gold)
        mix1_pool_path = Path(args.mix1_pool)
        mix1_pool_rows = _read_jsonl(mix1_pool_path) if mix1_pool_path.exists() else []
        from_pool = Path(args.from_pool) if getattr(args, "from_pool", None) else None
        source_rows = None
        if from_pool and str(from_pool) not in ("", "-", "NONEXISTENT") and from_pool.exists():
            source_rows = _read_jsonl(from_pool)
        gym_tasks = Path(args.gym_tasks) if args.gym_tasks else None
        if not source_rows and (gym_tasks is None or not gym_tasks.exists()):
            print("refusing: need --gym-tasks or --from-pool for gym-alt-pool", file=sys.stderr)
            return 2
        rows = collect_gym_alt_order_mix_queries(
            gym_tasks if not source_rows else None,
            source_pool=source_rows,
            blocked=blocked,
            mix1_gold=mix1_gold,
            mix1_pool_rows=mix1_pool_rows,
            max_tokens=int(args.verified_like_max_tokens),
            near_miss_lo=float(args.near_miss_lo),
            near_miss_hi=float(args.near_miss_hi),
            min_expected_len=int(args.min_expected_len),
            max_expected_len=int(args.max_expected_len),
            min_fail_to_pass=int(args.min_fail_to_pass),
            max_fail_to_pass=int(args.max_fail_to_pass),
            seed=int(args.seed),
            cap=int(args.cap),
            sample_n=int(args.sample_n),
            targets=dict(GYM_ALT_ORDER_MIX_TARGETS),
        )
        if not rows:
            print("refusing: gym_alt order-mix pool is empty", file=sys.stderr)
            return 2
        write_pool(rows, Path(args.out))
        cal = build_order_mix_calibration(mix1_gold, mix1_pool_rows)
        hist = order_mix_histogram(
            rows, mix1_gold=mix1_gold, mix1_pool_rows=mix1_pool_rows
        )
        proj = project_order_mix_winner_mix(rows, cal)
        src = str(from_pool) if source_rows else str(gym_tasks)
        print(
            json.dumps(
                {
                    "out": args.out,
                    "source": src,
                    "targets": dict(GYM_ALT_ORDER_MIX_TARGETS),
                    "projected_winner_mix": proj,
                    **hist,
                },
                indent=2,
            )
        )
        return 0 if proj.get("winner_mix_gate_pass") else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
