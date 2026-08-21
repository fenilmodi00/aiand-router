"""A3 failing-first tests: APGR math, noise-alpha determinism, retune --init grid equivalence.

All three flags default-off; off == byte-identical outputs.
"""
from __future__ import annotations

import json
import pathlib
import tempfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_apgr_math_borrow_a():
    from aiand_router.eval import apgr

    # router == strong -> 1.0
    assert apgr(auc_router=0.9, auc_weak=0.5, auc_strong=0.9) == pytest.approx(1.0)
    # router == weak -> 0.0
    assert apgr(auc_router=0.5, auc_weak=0.5, auc_strong=0.9) == pytest.approx(0.0)
    # mid-point
    assert apgr(auc_router=0.7, auc_weak=0.5, auc_strong=0.9) == pytest.approx(0.5)
    # range check synthetic 2-model win-rate table -> APGR in [0,1]
    val = apgr(auc_router=0.65, auc_weak=0.5, auc_strong=0.9)
    assert 0.0 <= val <= 1.0
    # div-by-zero guard
    with pytest.raises(ValueError, match=".*strong.*weak.*|.*div.*zero.*|.*undefined.*"):
        apgr(auc_router=0.5, auc_weak=0.5, auc_strong=0.5)


def test_strong_pct_accuracy_curve_helper():
    from aiand_router.eval import strong_pct_accuracy_curve

    pts = [(0.0, 0.5), (0.5, 0.7), (1.0, 0.9)]
    curve = strong_pct_accuracy_curve(pts)
    assert isinstance(curve, list)
    assert len(curve) == 3
    # should be sorted by strong_pct and have keys
    assert curve[0]["strong_pct"] == pytest.approx(0.0)
    assert curve[-1]["strong_pct"] == pytest.approx(1.0)
    assert all("accuracy" in p for p in curve)


def test_report_apgr_flag_off_has_no_curve():
    from aiand_router.eval import report_from_log

    # empty log -> no curve regardless
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "log.jsonl"
        p.write_text("", encoding="utf-8")
        report = report_from_log(p)
        assert "cost_quality_curve" not in report
        # simulate main --apgr adds section only when flag passed
        # report_from_log with apgr=True should gain section
        try:
            report2 = report_from_log(p, apgr=True)
        except TypeError:
            pytest.fail("report_from_log should accept apgr kwarg (Borrow A)")
        assert "cost_quality_curve" in report2


def test_fit_noise_alpha_determinism():
    from aiand_router.fit import fit_scorer

    # minimal gold/silver fixture: 4 prompts x 2 models = 8 rows, enough for cal split
    gold_rows = []
    for i in range(8):
        prompt = f"p{i // 2}"
        mid = "deepseek-ai/deepseek-v4-flash" if i % 2 == 0 else "moonshotai/kimi-k2.7-code"
        gold_rows.append(
            {
                "prompt": prompt,
                "model_id": mid,
                "success": i % 3 != 0,
                "tokens": 500,
                "needs_tools": False,
                "phase": "plan",
            }
        )
    silver_rows = [
        {
            "prompt": "p0",
            "complexity_bin": "standard",
            "p_success": {"deepseek-ai/deepseek-v4-flash": 0.6, "moonshotai/kimi-k2.7-code": 0.4},
            "tokens": 500,
            "needs_tools": False,
            "phase": "plan",
        }
    ]
    with tempfile.TemporaryDirectory() as td:
        tdp = pathlib.Path(td)
        gold_path = tdp / "gold.jsonl"
        silver_path = tdp / "silver.jsonl"
        out1 = tdp / "out1.json"
        out2 = tdp / "out2.json"
        gold_path.write_text("".join(json.dumps(r) + "\n" for r in gold_rows), encoding="utf-8")
        silver_path.write_text("".join(json.dumps(r) + "\n" for r in silver_rows), encoding="utf-8")

        # noise_alpha=0.0 should skip augmentation entirely
        fit_scorer(gold_path, silver_path, out1, noise_alpha=0.0)
        fit_scorer(gold_path, silver_path, out2, noise_alpha=0.0)
        j1 = json.loads(out1.read_text(encoding="utf-8"))
        j2 = json.loads(out2.read_text(encoding="utf-8"))
        assert j1["weights"] == j2["weights"]

        # same seed -> same weights with noise
        out3 = tdp / "out3.json"
        out4 = tdp / "out4.json"
        fit_scorer(gold_path, silver_path, out3, noise_alpha=0.05)
        fit_scorer(gold_path, silver_path, out4, noise_alpha=0.05)
        j3 = json.loads(out3.read_text(encoding="utf-8"))
        j4 = json.loads(out4.read_text(encoding="utf-8"))
        assert j3["weights"] == j4["weights"]
        # noise should change weights vs zero (at least one weight differs)
        assert j1["weights"] != j3["weights"]


def test_retune_init_grid_equivalence():
    from aiand_router.train import run_retune
    import json

    FLASH = "deepseek-ai/deepseek-v4-flash"
    PRO = "deepseek-ai/deepseek-v4-pro"
    GLM = "zai-org/glm-5.2"

    def make_rows(n_queries, rates):
        rows = []
        for i in range(n_queries):
            for mid, rate in rates.items():
                rows.append(
                    {
                        "prompt": f"query {i}",
                        "model_id": mid,
                        "success": i < int(n_queries * rate),
                        "tokens": 500,
                        "needs_tools": False,
                        "phase": "plan",
                    }
                )
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
        assert out_grid_1 == out_grid_2
        # quantile should return valid YAML or do-not-promote without crashing
        out_q = run_retune(dense_path, scorer_path=scorer_path, init="quantile")
        assert isinstance(out_q, str)
        assert out_q == "do-not-promote" or out_q.startswith("trained_effort:")


def _cli_env():
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def test_retune_cli_flag_exists():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "aiand_router.train", "retune", "--help"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=_cli_env(),
        encoding="utf-8",
        errors="replace",
    )
    out = result.stdout + result.stderr
    assert "--init" in out
    assert "quantile" in out
    assert "grid" in out


def test_fit_cli_noise_alpha_flag_exists():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "aiand_router.train", "fit", "--help"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=_cli_env(),
        encoding="utf-8",
        errors="replace",
    )
    out = result.stdout + result.stderr
    assert "--noise-alpha" in out


def test_eval_cli_apgr_flag_exists():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "aiand_router.eval", "--help"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=_cli_env(),
        encoding="utf-8",
        errors="replace",
    )
    out = result.stdout + result.stderr
    assert "--apgr" in out
