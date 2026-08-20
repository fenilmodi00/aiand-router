"""Unpaid offline winner-pattern trait analysis (no API)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from aiand_router.geometry import (
    HOLDOUT_ORDER_IDS,
    classify_winner_pattern,
    group_gold_by_prompt,
    holdout_like_order,
    per_id_rates,
    y_rate,
)
from aiand_router.pool import (
    _nm_bin,
    load_task_checks,
    apply_task_checks,
    matches_kimi_only_mutation,
    observable_proxies,
    proxy_stratum,
)

ROOT = Path(__file__).resolve().parents[2]

SLICES = [
    ("mix1", ROOT / "data/gold-sparse-hard-mix1.jsonl"),
    ("seed11", ROOT / "data/gold-sparse-hard-probe-seed11.jsonl"),
    ("seed12", ROOT / "data/gold-sparse-hard-probe-seed12.jsonl"),
    ("seed13", ROOT / "data/gold-sparse-hard-probe-seed13.jsonl"),
    ("seed14", ROOT / "data/gold-sparse-hard-probe-seed14.jsonl"),
    ("seed15", ROOT / "data/gold-sparse-hard-probe-seed15.jsonl"),
    ("verified", ROOT / "data/gold-verified.jsonl"),
]

POOL_FILES = [
    ROOT / "data/pool-hard-mix-near_miss_seed11.jsonl",
    ROOT / "data/pool-hard-mix-winner-stratified.jsonl",
    ROOT / "data/pool-hard-mix-kimi-only-targeted.jsonl",
]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_pool_index() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for pf in POOL_FILES:
        if not pf.exists():
            continue
        for row in load_jsonl(pf):
            out[str(row.get("prompt") or "")] = row
    return out


def enrich_row(prompt: str, gold_row: dict, pool: dict[str, dict], tasks: dict) -> dict:
    row = dict(pool.get(prompt) or {})
    if not row:
        row = {
            "prompt": prompt,
            "expected": gold_row.get("expected", ""),
            "instance_id": gold_row.get("instance_id", ""),
        }
    apply_task_checks([row], tasks)
    return row


def pattern_fractions(rows: list[dict]) -> dict[str, float]:
    counts = Counter()
    by = group_gold_by_prompt(rows)
    n = 0
    for oc in by.values():
        if not all(mid in oc for mid in HOLDOUT_ORDER_IDS):
            continue
        pat = classify_winner_pattern({mid: oc[mid] for mid in HOLDOUT_ORDER_IDS})
        counts[pat] += 1
        n += 1
    return {k: round(v / n, 4) if n else 0.0 for k, v in sorted(counts.items())}


def main() -> None:
    pool = build_pool_index()
    tasks = load_task_checks(ROOT / "data/smith-task-checks.jsonl")

    print("=== Mix1 pattern × observable proxies (pool-joined) ===")
    mix1 = load_jsonl(SLICES[0][1])
    by = group_gold_by_prompt(mix1)
    pattern_rows: dict[str, list[dict]] = defaultdict(list)
    for prompt, oc in by.items():
        if not all(mid in oc for mid in HOLDOUT_ORDER_IDS):
            continue
        pat = classify_winner_pattern({mid: oc[mid] for mid in HOLDOUT_ORDER_IDS})
        gr = next(r for r in mix1 if r["prompt"] == prompt)
        row = enrich_row(prompt, gr, pool, tasks)
        pattern_rows[pat].append(row)

    for pat, rs in sorted(pattern_rows.items()):
        f2p = Counter(observable_proxies(r)["fail_to_pass"] for r in rs)
        nm = [observable_proxies(r)["near_miss"] for r in rs]
        nm = [x for x in nm if isinstance(x, float)]
        el = [observable_proxies(r)["expected_len"] for r in rs]
        strata = Counter(proxy_stratum(r) for r in rs)
        mut = sum(matches_kimi_only_mutation(str(r.get("instance_id") or "")) for r in rs)
        print(
            f"{pat:20s} n={len(rs):2d} f2p={dict(f2p)} "
            f"nm={sum(nm)/len(nm):.3f} el={sum(el)/len(el):.1f} mut={mut} strata={dict(strata)}"
        )

    print("\n=== Slice summary (pool-joined proxies + pattern rates) ===")
    table = []
    for label, path in SLICES:
        if not path.exists():
            continue
        rows = load_jsonl(path)
        by = group_gold_by_prompt(rows)
        patterns = Counter()
        joined = 0
        f2p: list[int] = []
        nm: list[float] = []
        el: list[int] = []
        strata: Counter[str] = Counter()
        mut = 0
        nm_bins: Counter[str] = Counter()
        for prompt, oc in by.items():
            if not all(mid in oc for mid in HOLDOUT_ORDER_IDS):
                continue
            pat = classify_winner_pattern({mid: oc[mid] for mid in HOLDOUT_ORDER_IDS})
            patterns[pat] += 1
            gr = next(r for r in rows if r["prompt"] == prompt)
            row = enrich_row(prompt, gr, pool, tasks)
            if prompt in pool:
                joined += 1
            px = observable_proxies(row)
            f2p.append(int(px["fail_to_pass"]))
            if isinstance(px["near_miss"], float):
                nm.append(px["near_miss"])
                nb = _nm_bin(px["near_miss"])
                if nb:
                    nm_bins[nb] += 1
            el.append(int(px["expected_len"]))
            s = proxy_stratum(row)
            if s:
                strata[s] += 1
            if matches_kimi_only_mutation(str(row.get("instance_id") or "")):
                mut += 1
        n = sum(patterns.values())
        rates = per_id_rates(rows)
        table.append(
            {
                "label": label,
                "n": n,
                "joined": joined,
                "y": round(y_rate(rows), 4),
                "order": holdout_like_order(rates),
                "kimi_only_frac": round(patterns.get("kimi-only", 0) / n, 4) if n else 0,
                "all_fail_frac": round(patterns.get("all-fail", 0) / n, 4) if n else 0,
                "qwf_frac": round(patterns.get("qwen-without-flash", 0) / n, 4) if n else 0,
                "all_four_frac": round(patterns.get("all-four", 0) / n, 4) if n else 0,
                "fqk_frac": round(patterns.get("flash+qwen+kimi", 0) / n, 4) if n else 0,
                "f2p_mean": round(sum(f2p) / len(f2p), 3) if f2p else None,
                "f2p_p90": sorted(f2p)[int(0.9 * (len(f2p) - 1))] if f2p else None,
                "nm_mean": round(sum(nm) / len(nm), 3) if nm else None,
                "elen_mean": round(sum(el) / len(el), 1) if el else None,
                "mut_frac": round(mut / n, 4) if n else 0,
                "nm_hi_frac": round(nm_bins.get("nm_hi", 0) / n, 4) if n else 0,
            }
        )

    print(json.dumps(table, indent=2))

    # Mix1 good-pattern envelope vs seed-15 bad patterns
    print("\n=== Mix1 order-preserving patterns vs order-breaking (observable) ===")
    good_pats = {"kimi-only", "all-fail", "flash+qwen+kimi"}
    bad_pats = {"qwen-without-flash", "all-four", "flash+pro", "other"}
    good_nm: list[float] = []
    bad_nm: list[float] = []
    good_f2p: list[int] = []
    bad_f2p: list[int] = []
    for pat, rs in pattern_rows.items():
        for r in rs:
            px = observable_proxies(r)
            if isinstance(px["near_miss"], float):
                (good_nm if pat in good_pats else bad_nm).append(px["near_miss"])
            (good_f2p if pat in good_pats else bad_f2p).append(int(px["fail_to_pass"]))
    print(f"good nm mean={sum(good_nm)/len(good_nm):.3f} bad nm mean={sum(bad_nm)/len(bad_nm):.3f}")
    print(f"good f2p {Counter(good_f2p)} bad f2p {Counter(bad_f2p)}")


if __name__ == "__main__":
    main()
