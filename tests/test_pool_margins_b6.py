import json
import pathlib
from pathlib import Path

from aiand_router.pool import (
    BIN_FRAC,
    PHASE_FRAC,
    TOOLS_FRAC,
    SPEC_COUNT_BAND,
    SPEC_STRATUM_FLOOR,
    format_coverage_markdown,
    pool_coverage_report,
    validate_spec_margins,
)


def _make_rows(bins, tools, phases):
    """Helper: build synthetic pool rows from parallel lists."""
    rows = []
    for i, (b, t, p) in enumerate(zip(bins, tools, phases)):
        rows.append(
            {
                "id": f"q{i:05d}",
                "instance_id": f"q{i:05d}",
                "prompt": f"prompt {i} {b} {p} {t}",
                "hint_bin": b,
                "needs_tools": t,
                "phase": p,
                "tokens": 100,
                "source": "synthetic",
            }
        )
    return rows


def _balanced_rows(n=4000):
    """Build n rows that pass spec margins by stratified generation."""
    # Use same stratified targets as scripts/build_pool_spec.py: max(20, round(n*fracs))
    rows = []
    idx = 0
    for b, bf in BIN_FRAC.items():
        for p, pf in PHASE_FRAC.items():
            for t, tf in TOOLS_FRAC.items():
                raw = round(n * bf * pf * tf)
                target = max(SPEC_STRATUM_FLOOR, raw)
                for _ in range(target):
                    rows.append({"id": f"q{idx:05d}", "instance_id": f"q{idx:05d}", "prompt": f"prompt {idx} {b} {p} {t}", "hint_bin": b, "needs_tools": t, "phase": p, "tokens": 100, "source": "synthetic"})
                    idx += 1
    # Trim or pad to exactly n while preserving floors (already >= floors)
    if len(rows) > n:
        # Deterministic trim: keep first n (shuffled would be similar, but keep stratified)
        import random as _rng
        _rng.Random(0).shuffle(rows)
        rows = rows[:n]
    elif len(rows) < n:
        while len(rows) < n:
            rows.append({"id": f"q{idx:05d}", "instance_id": f"q{idx:05d}", "prompt": f"prompt {idx}", "hint_bin": "standard", "needs_tools": True, "phase": "edit", "tokens": 100, "source": "synthetic"})
            idx += 1
    return rows


def test_validate_spec_margins_pass_balanced():
    rows = _balanced_rows(7012)
    rep = validate_spec_margins(rows, tolerance=0.03)
    assert rep["overall_ok"], rep["errors"]
    assert rep["count_band"]["ok"]
    assert rep["stratum"]["ok"]


def test_validate_spec_margins_fail_skewed_bin():
    # all trivial -> bin fails
    rows = _make_rows(["trivial"] * 100, [True] * 100, ["edit"] * 100)
    rep = validate_spec_margins(rows, tolerance=0.03)
    assert not rep["overall_ok"]
    assert not rep["bin_ok"]
    assert any("bin" in e for e in rep["errors"])


def test_validate_spec_margins_fail_under_floor():
    # build 48 strata but one stratum has only 5 rows (<20)
    rows = []
    idx = 0
    for b in BIN_FRAC:
        for t in TOOLS_FRAC:
            for p in PHASE_FRAC:
                cnt = 5 if (b == "trivial" and t is True and p == "edit") else 20
                for _ in range(cnt):
                    rows.append(
                        {
                            "id": f"q{idx:05d}",
                            "instance_id": f"q{idx:05d}",
                            "prompt": f"p{idx}",
                            "hint_bin": b,
                            "needs_tools": t,
                            "phase": p,
                            "tokens": 100,
                            "source": "synthetic",
                        }
                    )
                    idx += 1
    rep = validate_spec_margins(rows)
    assert not rep["stratum"]["ok"]
    assert any("stratum" in e for e in rep["errors"])


def test_validate_spec_margins_fail_count_band():
    rows = _make_rows(["standard"] * 100, [True] * 100, ["edit"] * 100)
    rep = validate_spec_margins(rows)
    assert not rep["count_band"]["ok"]
    assert any("count" in e for e in rep["errors"])


def test_real_pool_passes_spec():
    p = Path("data/queries_spec.jsonl")
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    rep = validate_spec_margins(rows)
    assert rep["overall_ok"], rep["errors"]
    assert rep["stratum"]["distinct"] == 48
    assert rep["stratum"]["unoccupied"] == 0
    assert rep["count_band"]["ok"]


def test_pool_coverage_report_manifest_consistency():
    p = Path("data/queries_spec.jsonl")
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    mp = json.loads(Path("data/split_manifest.json").read_text(encoding="utf-8"))
    teacher_n = sum(1 for r in mp["rows"] if r["split"] == "teacher-silver")
    report = pool_coverage_report(rows, manifest_path=Path("data/split_manifest.json"), teacher_silver_n=teacher_n)
    assert report["margins"]["overall_ok"]
    assert report["manifest"]["consistent"]
    assert report["manifest"]["pool_not_in_manifest"] == 0
    assert report["manifest"]["manifest_not_in_pool"] == 0
    assert report["manifest"]["total"] == report["total"] == len(rows)
    assert report["manifest"]["total"] == mp["metadata"]["total"]
    assert report["teacher_cost"]["teacher_silver_n"] == teacher_n
    assert report["teacher_cost"]["cost"] == round(teacher_n * 0.0015, 4)
    assert report["teacher_cost"]["fits_tranche_8"]
    assert report["projected_cost"]["full_pool_cost"] == round(len(rows) * 0.0015, 4)
    md = format_coverage_markdown(report)
    assert "Query Pool Coverage Report" in md
    assert "Bin margins" in md
    assert "Stratum floors" in md
    assert "C1 gate arithmetic" in md
    assert "Manifest consistency" in md


def test_manifest_spend_before_unchanged():
    data = json.loads(Path("data/split_manifest.json").read_text(encoding="utf-8"))
    assert data["metadata"]["spend_before_A"] == 8.16
    assert Path("data/spend.txt").read_text(encoding="utf-8").strip() == "8.16"


def test_topup_split_sizes_gate_reachable():
    data = json.loads(Path("data/split_manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in Path("data/queries_spec.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    from collections import Counter
    cnt = Counter(r["split"] for r in data["rows"])
    assert cnt["promotion-holdout"] == 300
    assert cnt["threshold-tune"] == 300
    assert cnt["dense-cal"] == 300
    # gate-reachable sizing
    assert cnt["teacher-silver"] >= 3800
    assert cnt["sparse-train"] >= 1800
    assert sum(cnt.values()) == len(rows) == data["metadata"]["total"]
    assert len(rows) >= 6500
    # C1/C3 arithmetic: teacher 4000 at 90% yield -> 3600 silver (>3500), sparse 2112 > 2000
    assert cnt["teacher-silver"] * 0.9 >= 3500 or cnt["teacher-silver"] >= 3890
    assert cnt["sparse-train"] >= 2000 or sum(cnt.values()) >= 6800
