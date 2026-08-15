#!/usr/bin/env python
"""QA gate for the spec-scale query pool (T10).

Asserts:
  (a) data/queries_spec.jsonl exists and has 4,000-5,000 rows
  (b) every occupied stratum (bin x phase family x tools) has >= 20 rows
  (c) projected teacher cost <= $8 (rows x per-row estimate incl. <=25% escalate)
  (d) split_manifest.json sums to pool size
  (e) split id sets are pairwise disjoint
  (f) each row has required fields: prompt, phase, needs_tools, hint_bin, tokens

Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "data" / "queries_spec.jsonl"
MANIFEST = ROOT / "data" / "split_manifest.json"

BIN_FRAC = {"trivial": 0.15, "standard": 0.40, "hard": 0.30, "frontier": 0.15}
PHASE_FRAC = {
    "edit": 0.30,
    "tool": 0.25,
    "plan": 0.15,
    "debug": 0.15,
    "discover": 0.10,
    "summarize": 0.05,
}
TOOLS_FRAC = {True: 0.75, False: 0.25}
REQUIRED_FIELDS = ("prompt", "phase", "needs_tools", "hint_bin", "tokens")
STRATUM_FLOOR = 20

# Teacher cost projection (catalog list prices, USD / 1M tokens)
CHEAP_IN = 0.15   # Flash input
CHEAP_OUT = 0.25  # Flash output
ESC_IN = 1.00     # Pro input
ESC_OUT = 2.50    # Pro output
AVG_IN_TOK = 500
AVG_OUT_TOK = 300
ESCALATE_SHARE = 0.25
COST_CAP = 8.0

SPLITS = ("sparse-train", "dense/cal", "tune", "promotion-holdout")


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _family(phase: str) -> str:
    return PHASE_FRAC.get(phase, phase) if phase in PHASE_FRAC else phase


def check_pool_size(rows: list[dict]) -> list[str]:
    errs = []
    n = len(rows)
    if n < 4000:
        errs.append(f"pool too small: {n} < 4000")
    if n > 5000:
        errs.append(f"pool too large: {n} > 5000")
    return errs


def check_required_fields(rows: list[dict]) -> list[str]:
    errs = []
    for i, r in enumerate(rows):
        missing = [f for f in REQUIRED_FIELDS if f not in r]
        if missing:
            errs.append(f"row {i}: missing fields {missing}")
            if len(errs) > 5:
                errs.append("... (truncated)")
                break
    return errs


def check_strata(rows: list[dict]) -> tuple[list[str], str]:
    """Check occupied strata have >= floor rows. Return (errors, histogram_text)."""
    hist: Counter[tuple[str, str, bool]] = Counter()
    for r in rows:
        b = str(r.get("hint_bin") or "standard")
        p = str(r.get("phase") or "plan")
        t = bool(r.get("needs_tools"))
        hist[(b, p, t)] += 1

    lines = ["stratum_histogram:"]
    errs = []
    for b in BIN_FRAC:
        for p in PHASE_FRAC:
            for t in (True, False):
                n = hist.get((b, p, t), 0)
                if n:
                    lines.append(f"  bin={b} phase={p} tools={t}: {n}")
                    if n < STRATUM_FLOOR:
                        errs.append(
                            f"stratum bin={b} phase={p} tools={t} has {n} < {STRATUM_FLOOR}"
                        )
    return errs, "\n".join(lines)


def check_margins(rows: list[dict]) -> list[str]:
    """Check bin/tools/phase margins are within +-5pp of spec."""
    errs = []
    n = len(rows)
    if not n:
        return ["empty pool"]

    bin_c = Counter(str(r.get("hint_bin") or "standard") for r in rows)
    phase_c = Counter(str(r.get("phase") or "plan") for r in rows)
    tool_c = Counter(bool(r.get("needs_tools")) for r in rows)

    for b, frac in BIN_FRAC.items():
        actual = bin_c.get(b, 0) / n
        target = frac
        if abs(actual - target) > 0.06:
            errs.append(f"bin {b}: {actual:.1%} vs target {target:.1%} (delta > 6pp)")

    for p, frac in PHASE_FRAC.items():
        actual = phase_c.get(p, 0) / n
        target = frac
        if abs(actual - target) > 0.06:
            errs.append(f"phase {p}: {actual:.1%} vs target {target:.1%} (delta > 6pp)")

    for t, frac in TOOLS_FRAC.items():
        actual = tool_c.get(t, 0) / n
        target = frac
        if abs(actual - target) > 0.06:
            errs.append(f"tools={t}: {actual:.1%} vs target {target:.1%} (delta > 6pp)")

    return errs


def check_cost(rows: list[dict]) -> tuple[list[str], str]:
    """Project teacher cost. Return (errors, cost_text)."""
    n = len(rows)
    avg_tokens = sum(int(r.get("tokens", 0)) for r in rows) / n if n else 0
    in_tok = max(AVG_IN_TOK, int(avg_tokens))
    out_tok = AVG_OUT_TOK
    cheap = (in_tok * CHEAP_IN + out_tok * CHEAP_OUT) / 1e6
    esc = (in_tok * ESC_IN + out_tok * ESC_OUT) / 1e6
    per_row = (1 - ESCALATE_SHARE) * cheap + ESCALATE_SHARE * esc
    total = n * per_row
    text = (
        f"teacher_cost_projection: rows={n} avg_tokens={avg_tokens:.0f} "
        f"per_row=${per_row:.6f} escalate_share={ESCALATE_SHARE:.0%} "
        f"total=${total:.2f} cap=${COST_CAP:.2f}"
    )
    errs = []
    if total > COST_CAP:
        errs.append(f"projected teacher cost ${total:.2f} > ${COST_CAP:.2f}")
    return errs, text


def check_manifest(rows: list[dict]) -> tuple[list[str], str]:
    """Check manifest sums to pool, splits disjoint, every id assigned."""
    errs = []
    if not MANIFEST.exists():
        return [f"manifest not found: {MANIFEST}"], ""

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    splits = manifest.get("splits", {})
    text_parts = ["split_manifest:"]

    pool_ids = set()
    for r in rows:
        rid = str(r.get("id") or r.get("instance_id") or "")
        if rid:
            pool_ids.add(rid)

    all_assigned: set[str] = set()
    split_sets: dict[str, set[str]] = {}
    for sp in SPLITS:
        ids = set(splits.get(sp, []))
        split_sets[sp] = ids
        text_parts.append(f"  {sp}: {len(ids)}")
        overlap = all_assigned & ids
        if overlap:
            errs.append(f"split {sp} overlaps prior splits: {len(overlap)} ids")
        all_assigned |= ids

    total_assigned = sum(len(s) for s in split_sets.values())
    text = "\n".join(text_parts)

    if total_assigned != len(rows):
        errs.append(f"manifest total {total_assigned} != pool size {len(rows)}")

    unassigned = pool_ids - all_assigned
    if unassigned:
        errs.append(f"{len(unassigned)} pool ids not in any split")

    extra = all_assigned - pool_ids
    if extra:
        errs.append(f"{len(extra)} manifest ids not in pool")

    return errs, text


def main() -> int:
    all_errs: list[str] = []
    info_lines: list[str] = []

    if not POOL.exists():
        print(f"FAIL: pool not found: {POOL}", file=sys.stderr)
        return 1

    rows = _read_jsonl(POOL)
    info_lines.append(f"pool_rows: {len(rows)}")

    all_errs += check_pool_size(rows)
    all_errs += check_required_fields(rows)

    strata_errs, hist = check_strata(rows)
    all_errs += strata_errs
    info_lines.append(hist)

    margin_errs = check_margins(rows)
    all_errs += margin_errs

    cost_errs, cost_text = check_cost(rows)
    all_errs += cost_errs
    info_lines.append(cost_text)

    manifest_errs, manifest_text = check_manifest(rows)
    all_errs += manifest_errs
    info_lines.append(manifest_text)

    for line in info_lines:
        print(line)

    if all_errs:
        print(f"\nFAIL: {len(all_errs)} error(s):", file=sys.stderr)
        for e in all_errs:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("\nPASS: all checks green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
