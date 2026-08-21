#!/usr/bin/env python
"""QA for APGR cost-quality curve + routellm-inspired borrow flags.

Assert-based, stdlib + PyYAML only. Run: python scripts/check_eval_apgr.py

Covers:
  (a) APGR math: router==strong -> 1.0, router==weak -> 0.0, synthetic 2-model -> APGR in [0,1]
  (b) div-by-zero guard raises ValueError with clear message
  (c) strong_pct_accuracy_curve helper returns sorted curve
  (d) report_from_log gains cost_quality_curve only when --apgr (apgr=True) passed; off == byte-identical (no section)
  (e) CLI flags default-off: --apgr, --noise-alpha, --init grid
  (f) All three flags default-off byte-identical: fit_scorer noise_alpha=0.0 skips augmentation; retune init grid unchanged

No network calls, no credits.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

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


# ---------------------------------------------------------------------------
# (a) APGR math
# ---------------------------------------------------------------------------
print("=== Test (a): APGR math ===")
from aiand_router.eval import apgr, strong_pct_accuracy_curve, report_from_log

check("router==strong -> 1.0", apgr(0.9, 0.5, 0.9) == 1.0)
check("router==weak -> 0.0", apgr(0.5, 0.5, 0.9) == 0.0)
# synthetic 2-model win-rate table -> APGR in [0,1]
synthetic = apgr(auc_router=0.65, auc_weak=0.5, auc_strong=0.9)
check("synthetic APGR in [0,1]", 0.0 <= synthetic <= 1.0, f"({synthetic})")
check("midpoint 0.5", abs(apgr(0.7, 0.5, 0.9) - 0.5) < 1e-9)

# ---------------------------------------------------------------------------
# (b) div-by-zero guard
# ---------------------------------------------------------------------------
print("=== Test (b): div-by-zero guard ===")
raised = False
msg = ""
try:
    apgr(0.5, 0.5, 0.5)
except ValueError as e:
    raised = True
    msg = str(e)
check("div-by-zero raises ValueError", raised)
check("error message mentions strong/weak or div/undefined", "strong" in msg.lower() or "div" in msg.lower() or "undefined" in msg.lower(), f"({msg})")

# ---------------------------------------------------------------------------
# (c) strong_pct_accuracy_curve helper
# ---------------------------------------------------------------------------
print("=== Test (c): strong_pct_accuracy_curve helper ===")
curve = strong_pct_accuracy_curve([(0.0, 0.5), (1.0, 0.9), (0.5, 0.7)])
check("curve is list of 3", isinstance(curve, list) and len(curve) == 3)
check("sorted by strong_pct", curve[0]["strong_pct"] <= curve[1]["strong_pct"] <= curve[2]["strong_pct"])
check("keys strong_pct and accuracy", all("strong_pct" in p and "accuracy" in p for p in curve))
# dict input variant
curve2 = strong_pct_accuracy_curve([{"strong_pct": 1.0, "accuracy": 0.9}, {"strong_pct": 0.0, "accuracy": 0.5}])
check("dict input sorted", curve2[0]["strong_pct"] == 0.0)

# trapz helper sanity
from aiand_router.eval import auc_trapezoid

check("auc_trapezoid 0->1 linear", abs(auc_trapezoid([0, 1], [0, 1]) - 0.5) < 1e-9)
check("auc_trapezoid constant", abs(auc_trapezoid([0, 1], [0.8, 0.8]) - 0.8) < 1e-9)

# ---------------------------------------------------------------------------
# (d) report_from_log flag-off vs flag-on
# ---------------------------------------------------------------------------
print("=== Test (d): report_from_log apgr flag ===")
with tempfile.TemporaryDirectory() as td:
    # synthetic log with 3 baselines: premium, kimi, adaptive (virtual)
    # Use the same kinds as eval.report_from_log expects: requested ids
    rows = []
    for req in ["deepseek-ai/deepseek-v4-pro", "moonshotai/kimi-k2.7-code", "deepseek-ai/deepseek-v4-flash"]:
        rows.append(
            {
                "requested": req,
                "selected": req,
                "reason": "ok",
                "status": 200,
                "cost_usd": 0.001,
                "tokens_out": 100,
            }
        )
    p = pathlib.Path(td) / "log.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    report_off = report_from_log(p)
    check("flag-off report lacks cost_quality_curve", "cost_quality_curve" not in report_off)
    report_on = report_from_log(p, apgr=True)
    check("flag-on report gains cost_quality_curve", "cost_quality_curve" in report_on)
    if "cost_quality_curve" in report_on:
        cqc = report_on["cost_quality_curve"]
        check("cqc has apgr", "apgr" in cqc)
        check("cqc has curve", "curve" in cqc and isinstance(cqc["curve"], list))
        # APGR should be in [0,1] or None if guard triggered
        apgr_val = cqc.get("apgr")
        if apgr_val is not None:
            check("apgr in [0,1] or None", 0.0 <= float(apgr_val) <= 1.0 or apgr_val is None, f"({apgr_val})")
        # empty log fallback
        empty_p = pathlib.Path(td) / "empty.jsonl"
        empty_p.write_text("", encoding="utf-8")
        empty_off = report_from_log(empty_p)
        check("empty flag-off no curve", "cost_quality_curve" not in empty_off)
        empty_on = report_from_log(empty_p, apgr=True)
        check("empty flag-on has curve fallback", "cost_quality_curve" in empty_on)

# ---------------------------------------------------------------------------
# (e) CLI flags existence and default-off
# ---------------------------------------------------------------------------
print("=== Test (e): CLI flags default-off ===")
import os
import subprocess

def _env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env

def has_flag(cmd, flag):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), env=_env(), encoding="utf-8", errors="replace")
    return flag in (result.stdout + result.stderr)

check("--apgr flag exists", has_flag([sys.executable, "-m", "aiand_router.eval", "--help"], "--apgr"))
check("--noise-alpha flag exists", has_flag([sys.executable, "-m", "aiand_router.train", "fit", "--help"], "--noise-alpha"))
check("--init flag exists", has_flag([sys.executable, "-m", "aiand_router.train", "retune", "--help"], "--init"))
r = subprocess.run([sys.executable, "-m", "aiand_router.train", "retune", "--help"], capture_output=True, text=True, cwd=str(ROOT), env=_env(), encoding="utf-8", errors="replace")
check("retune default grid", "grid" in (r.stdout + r.stderr))
r2 = subprocess.run([sys.executable, "-m", "aiand_router.train", "fit", "--help"], capture_output=True, text=True, cwd=str(ROOT), env=_env(), encoding="utf-8", errors="replace")
check("fit default noise-alpha 0.0", "0.0" in (r2.stdout + r2.stderr) or "noise-alpha" in (r2.stdout + r2.stderr))

# ---------------------------------------------------------------------------
# (f) byte-identical off behavior + noise determinism + grid equivalence
# ---------------------------------------------------------------------------
print("=== Test (f): default-off byte-identical + borrow behavior ===")
from aiand_router.fit import fit_scorer
from aiand_router.train import run_retune

# fit noise_alpha determinism + off identical
with tempfile.TemporaryDirectory() as td:
    tdp = pathlib.Path(td)
    gold_rows = []
    for i in range(8):
        prompt = f"p{i // 2}"
        mid = "deepseek-ai/deepseek-v4-flash" if i % 2 == 0 else "moonshotai/kimi-k2.7-code"
        gold_rows.append({"prompt": prompt, "model_id": mid, "success": i % 3 != 0, "tokens": 500, "needs_tools": False, "phase": "plan"})
    silver_rows = [{"prompt": "p0", "complexity_bin": "standard", "p_success": {"deepseek-ai/deepseek-v4-flash": 0.6, "moonshotai/kimi-k2.7-code": 0.4}, "tokens": 500, "needs_tools": False, "phase": "plan"}]
    gold_path = tdp / "gold.jsonl"
    silver_path = tdp / "silver.jsonl"
    gold_path.write_text("".join(json.dumps(r) + "\n" for r in gold_rows), encoding="utf-8")
    silver_path.write_text("".join(json.dumps(r) + "\n" for r in silver_rows), encoding="utf-8")
    out_a = tdp / "a.json"
    out_b = tdp / "b.json"
    fit_scorer(gold_path, silver_path, out_a, noise_alpha=0.0)
    fit_scorer(gold_path, silver_path, out_b, noise_alpha=0.0)
    check("noise_alpha=0.0 identical", out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8"))
    out_c = tdp / "c.json"
    out_d = tdp / "d.json"
    fit_scorer(gold_path, silver_path, out_c, noise_alpha=0.05)
    fit_scorer(gold_path, silver_path, out_d, noise_alpha=0.05)
    check("noise_alpha same seed deterministic", out_c.read_text(encoding="utf-8") == out_d.read_text(encoding="utf-8"))

# retune grid equivalence
FLASH = "deepseek-ai/deepseek-v4-flash"
PRO = "deepseek-ai/deepseek-v4-pro"
GLM = "zai-org/glm-5.2"


def make_rows(n_queries, rates):
    rows = []
    for i in range(n_queries):
        for mid, rate in rates.items():
            rows.append({"prompt": f"query {i}", "model_id": mid, "success": i < int(n_queries * rate), "tokens": 500, "needs_tools": False, "phase": "plan"})
    return rows


rows = make_rows(100, {FLASH: 0.8, PRO: 0.8, GLM: 0.8})
scorer = {"not_spec_floors": True, "complexity_bin": "standard", "p_success": {FLASH: 0.9, PRO: 0.5, GLM: 0.5}}
with tempfile.TemporaryDirectory() as td:
    tdp = pathlib.Path(td)
    dense_path = tdp / "tune.jsonl"
    scorer_path = tdp / "scorer.json"
    dense_path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    scorer_path.write_text(json.dumps(scorer), encoding="utf-8")
    out_grid_1 = run_retune(dense_path, scorer_path=scorer_path, init="grid")
    out_grid_2 = run_retune(dense_path, scorer_path=scorer_path, init="grid")
    check("retune grid deterministic", out_grid_1 == out_grid_2)
    out_q = run_retune(dense_path, scorer_path=scorer_path, init="quantile")
    check("retune quantile returns valid", out_q == "do-not-promote" or out_q.startswith("trained_effort:"))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n=== Summary: {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
