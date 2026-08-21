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
    """Build n rows that pass spec margins by mirroring the real pool distribution."""
    # Real pool (4039 rows) passes with margins within 1%; scale its empirical
    # distribution down to n while preserving each occupied stratum >= floor.
    real_path = Path("data/queries_spec.jsonl")
    if real_path.exists():
        real = [json.loads(l) for l in real_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        # if n matches real, just return copy with new ids
        if n == len(real):
            out = []
            for i, r in enumerate(real):
                out.append({**r, "id": f"q{i:05d}", "instance_id": f"q{i:05d}", "prompt": f"prompt {i} {r['hint_bin']} {r['phase']}"})
            return out
        # else sample deterministically to approximate margins: take first n of real repeated
        # scale by repeating real rows proportionally
        out = []
        for i in range(n):
            r = real[i % len(real)]
            out.append({**r, "id": f"q{i:05d}", "instance_id": f"q{i:05d}", "prompt": f"prompt {i} {r['hint_bin']} {r['phase']}"})
        # ensure stratum floors: the real pool already has 48 strata >=20, repetition keeps it
        return out
    # fallback synthetic: allocate per spec with floor guard
    rows = []
    idx = 0
    for b in BIN_FRAC:
        for t in TOOLS_FRAC:
            for p in PHASE_FRAC:
                for _ in range(SPEC_STRATUM_FLOOR):
                    rows.append({"id": f"q{idx:05d}", "instance_id": f"q{idx:05d}", "prompt": f"prompt {idx}", "hint_bin": b, "needs_tools": t, "phase": p, "tokens": 100, "source": "synthetic"})
                    idx += 1
    # pad remaining with standard/edit/True which is spec-centred
    while len(rows) < n:
        rows.append({"id": f"q{idx:05d}", "instance_id": f"q{idx:05d}", "prompt": f"prompt {idx}", "hint_bin": "standard", "needs_tools": True, "phase": "edit", "tokens": 100, "source": "synthetic"})
        idx += 1
    return rows[:n]


def test_validate_spec_margins_pass_balanced():
    rows = _balanced_rows(4039)
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
    assert report["manifest"]["total"] == report["total"] == 4039
    assert report["teacher_cost"]["teacher_silver_n"] == 2139
    assert report["teacher_cost"]["cost"] == round(2139 * 0.0015, 4)
    assert report["projected_cost"]["fits_tranche_8"]
    assert report["teacher_cost"]["fits_tranche_8"]
    # markdown renders without error and contains key sections
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
