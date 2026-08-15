"""Retrain orchestration: train -> cal -> retune -> shadow-ready -> gate-check dry-run.

--plan-only: synthetic fixture data, no network, no TRAINED_PATH mutation.
Never sets TRAINED_PATH=trained. Writes data/scorer.candidate.json + data/retrain_report.md.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from .metrics import brier_skill_score, ece_equal_mass, ece_equal_width, reliability
from .scorer import score_eligible
from .train import fit_scorer

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CANDIDATE_PATH = DATA / "scorer.candidate.json"
REPORT_PATH = DATA / "retrain_report.md"

GATE_BSS_MIN = 0.0
GATE_ECE_MAX = 0.03

_FIXTURE_MID = "deepseek-ai/deepseek-v4-flash"


def _has_retune() -> bool:
    """Check if T4's retune function exists in the train module."""
    from . import train

    for name in ("retune_thresholds", "run_retune", "fit_thresholds", "retune"):
        fn = getattr(train, name, None)
        if callable(fn):
            return True
    return False


def _fixture_gold(tmp: Path) -> Path:
    """Create minimal synthetic gold JSONL for dry-run fit."""
    rows: list[dict[str, Any]] = []
    for i in range(30):
        rows.append({
            "prompt": f"train task {i}: implement function foo",
            "model_id": _FIXTURE_MID,
            "success": i % 3 != 0,
            "success_tier": "verified",
            "unobserved": False,
            "tokens": 50 + i,
            "needs_tools": False,
            "phase": "edit",
            "hint_bin": "standard",
            "dense": False,
        })
    for i in range(10):
        rows.append({
            "prompt": f"cal task {i}: fix bug in bar",
            "model_id": _FIXTURE_MID,
            "success": i % 2 == 0,
            "success_tier": "verified",
            "unobserved": False,
            "tokens": 40 + i,
            "needs_tools": False,
            "phase": "edit",
            "hint_bin": "standard",
            "dense": True,
        })
    path = tmp / "gold.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _fixture_silver(tmp: Path) -> Path:
    """Create minimal synthetic silver JSONL for dry-run fit."""
    rows: list[dict[str, Any]] = []
    for i in range(20):
        rows.append({
            "prompt": f"silver task {i}: refactor module",
            "complexity_bin": "standard",
            "p_success": {_FIXTURE_MID: 0.5 + 0.1 * (i % 3)},
            "tokens": 50 + i,
            "needs_tools": False,
            "phase": "edit",
            "hint_bin": "standard",
        })
    path = tmp / "silver.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _cal_rows(artifact: dict[str, Any], gold_path: Path) -> list[tuple[float, float]]:
    """Score each gold row and return (p, y) pairs for calibration metrics."""
    rows: list[tuple[float, float]] = []
    for line in gold_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        mid = r["model_id"]
        _, ps = score_eligible(
            artifact, [mid],
            phase=r.get("phase", "plan"),
            needs_tools=bool(r.get("needs_tools")),
            tokens=int(r.get("tokens", 1)),
            hint_bin=r.get("hint_bin"),
            text=r.get("prompt", ""),
        )
        if mid in ps:
            rows.append((ps[mid], 1.0 if r.get("success") else 0.0))
    return rows


def _write_report(
    artifact: dict[str, Any],
    bss: float,
    ece_w: float,
    ece_m: float,
    mce_val: float,
    retune_available: bool,
    gate_verdict: str,
) -> None:
    """Write data/retrain_report.md."""
    cal_mode = artifact.get("calibrator", {}).get("mode", "unknown")
    lines = [
        "# Retrain Report",
        "",
        "## Fit Summary",
        "",
        f"- n_gold: {artifact.get('n_gold', 0)}",
        f"- n_cal: {artifact.get('n_cal', 0)}",
        f"- n_silver: {artifact.get('n_silver', 0)}",
        f"- calibrator mode: {cal_mode}",
        "",
        "## Calibration Report",
        "",
        f"- Brier skill score: {bss:.6f}",
        f"- ECE (equal-width): {ece_w:.6f}",
        f"- ECE (equal-mass): {ece_m:.6f}",
        f"- MCE: {mce_val:.6f}",
        "",
        "## Retune Verdict",
        "",
        f"- retune: {'available' if retune_available else 'skipped (not available)'}",
        "",
        "## Gate-Check Verdict",
        "",
        f"- gate_check: {gate_verdict}",
        f"- BSS > 0: {'pass' if bss > GATE_BSS_MIN else 'fail'} ({bss:.6f})",
        f"- ECE <= 0.03: {'pass' if ece_w <= GATE_ECE_MAX and ece_m <= GATE_ECE_MAX else 'fail'}"
        f" ({ece_w:.6f} / {ece_m:.6f})",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_plan_only() -> int:
    """Execute: fit -> cal-report -> retune (if available) -> write artifacts -> gate-check."""
    DATA.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        gold_path = _fixture_gold(tmp)
        silver_path = _fixture_silver(tmp)
        fit_out = tmp / "scorer.json"

        # Step 1: fit
        fit_scorer(gold_path, silver_path, fit_out)
        artifact = json.loads(fit_out.read_text(encoding="utf-8"))

        # Step 2: calibration report
        cal_rows = _cal_rows(artifact, gold_path)
        bss = brier_skill_score(cal_rows) if cal_rows else 0.0
        ece_w = ece_equal_width(cal_rows) if cal_rows else 0.0
        ece_m = ece_equal_mass(cal_rows) if cal_rows else 0.0
        rel = reliability(cal_rows) if cal_rows else {}
        mce_val = float(rel.get("mce", 0.0))

        # Step 3: retune (if available)
        retune_available = _has_retune()

        # Step 4: write candidate artifact
        CANDIDATE_PATH.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

        # Step 5: gate-check
        gate_pass = (
            bss > GATE_BSS_MIN
            and ece_w <= GATE_ECE_MAX
            and ece_m <= GATE_ECE_MAX
        )
        gate_verdict = "shadow-ready" if gate_pass else "do-not-promote"

        # Step 6: write report
        _write_report(artifact, bss, ece_w, ece_m, mce_val, retune_available, gate_verdict)

        # Print gate-check verdict line
        print(f"gate_check: {gate_verdict}")

    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    if "--plan-only" in argv:
        return run_plan_only()
    print("usage: python -m aiand_router.retrain --plan-only", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
