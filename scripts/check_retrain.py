#!/usr/bin/env python
"""QA for retrain orchestration (--plan-only dry-run).

Assert-based, stdlib only. Run: python scripts/check_retrain.py

Covers:
  (a) run_plan_only() writes data/scorer.candidate.json that loads via load_scorer.
  (b) data/retrain_report.md exists with expected sections.
  (c) TRAINED_PATH env var is NOT set to 'trained' by the script.
  (d) gate_check verdict line is printed to stdout.
  (e) python -m aiand_router.retrain --plan-only exits 0 as a subprocess.
"""

from __future__ import annotations

import io
import json
import os
import pathlib
import subprocess
import sys
from contextlib import redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data"
CANDIDATE_PATH = DATA / "scorer.candidate.json"
REPORT_PATH = DATA / "retrain_report.md"

VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PY) if VENV_PY.exists() else sys.executable

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


# Clean up any previous artifacts so we test fresh writes
for p in (CANDIDATE_PATH, REPORT_PATH):
    if p.exists():
        p.unlink()

# Save and clear TRAINED_PATH so we can detect if the script sets it
saved_tp = os.environ.pop("TRAINED_PATH", None)

# ---------------------------------------------------------------------------
# Test (a): run_plan_only writes scorer.candidate.json
# ---------------------------------------------------------------------------
print("=== Test (a): run_plan_only writes scorer.candidate.json ===")

from aiand_router.retrain import run_plan_only
from aiand_router.scorer import load_scorer

buf = io.StringIO()
with redirect_stdout(buf):
    run_plan_only()
stdout_a = buf.getvalue()

check("scorer.candidate.json exists", CANDIDATE_PATH.exists())
if CANDIDATE_PATH.exists():
    artifact = load_scorer(CANDIDATE_PATH)
    check("load_scorer returns artifact", artifact is not None)
    if artifact:
        check("artifact has calibrator", "calibrator" in artifact)
        check("artifact has n_gold", "n_gold" in artifact)
        check("artifact has n_cal", "n_cal" in artifact)

# ---------------------------------------------------------------------------
# Test (b): retrain_report.md exists with sections
# ---------------------------------------------------------------------------
print("=== Test (b): retrain_report.md exists with sections ===")
check("retrain_report.md exists", REPORT_PATH.exists())
if REPORT_PATH.exists():
    report = REPORT_PATH.read_text(encoding="utf-8")
    check("has Fit Summary section", "## Fit Summary" in report)
    check("has Calibration Report section", "## Calibration Report" in report)
    check("has Retune Verdict section", "## Retune Verdict" in report)
    check("has Gate-Check Verdict section", "## Gate-Check Verdict" in report)

# ---------------------------------------------------------------------------
# Test (c): TRAINED_PATH not set to 'trained' by the script
# ---------------------------------------------------------------------------
print("=== Test (c): TRAINED_PATH not set to 'trained' ===")
check(
    "TRAINED_PATH not 'trained' after run_plan_only",
    os.environ.get("TRAINED_PATH") != "trained",
    f"(TRAINED_PATH={os.environ.get('TRAINED_PATH')!r})",
)

# Restore TRAINED_PATH
if saved_tp is not None:
    os.environ["TRAINED_PATH"] = saved_tp

# ---------------------------------------------------------------------------
# Test (d): gate_check verdict line printed to stdout
# ---------------------------------------------------------------------------
print("=== Test (d): gate_check verdict line printed ===")
check(
    "stdout has gate_check line",
    "gate_check:" in stdout_a,
    f"(stdout={stdout_a!r})",
)

# ---------------------------------------------------------------------------
# Test (e): python -m aiand_router.retrain --plan-only exits 0
# ---------------------------------------------------------------------------
print("=== Test (e): subprocess module exit 0 ===")
env = dict(os.environ)
env["PYTHONPATH"] = str(ROOT / "src")
env.pop("TRAINED_PATH", None)
proc = subprocess.run(
    [PYTHON, "-m", "aiand_router.retrain", "--plan-only"],
    capture_output=True,
    text=True,
    env=env,
)
check("subprocess exits 0", proc.returncode == 0, f"(rc={proc.returncode}, stderr={proc.stderr[:200]!r})")
check("subprocess stdout has gate_check", "gate_check:" in proc.stdout, f"(stdout={proc.stdout[:200]!r})")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n=== Summary: {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
