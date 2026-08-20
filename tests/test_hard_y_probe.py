"""End-to-end hard-y probe pipeline tests (unpaid fixtures only)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aiand_router.geometry import FLASH, KIMI, PRO, QWEN, geometry_report, main as geometry_main
from aiand_router.train import GEOMETRY_OVERRIDE_ENV, OPT_IN_ENV, main as train_main

FIXTURE = Path(__file__).parent / "fixtures" / "hard_y_probe"
TRAIN_FIX = FIXTURE / "gold-sparse-hard-fixture.jsonl"
EVAL_FIX = FIXTURE / "gold-verified-fixture.jsonl"


def _write_holdout_like_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Synthetic verified-like cells: short tokens, hard-band y, holdout order."""
    patterns = [
        {FLASH: False, QWEN: False, KIMI: True, PRO: False},
        {FLASH: False, QWEN: False, KIMI: True, PRO: False},
        {FLASH: True, QWEN: False, KIMI: False, PRO: False},
        {FLASH: False, QWEN: True, KIMI: False, PRO: False},
        {FLASH: False, QWEN: False, KIMI: False, PRO: False},
    ]
    train_rows: list[dict] = []
    eval_rows: list[dict] = []
    for i, oc in enumerate(patterns):
        for mid, ok in oc.items():
            train_rows.append(
                {
                    "prompt": f"Fix snippet {i}: broken python",
                    "model_id": mid,
                    "success": ok,
                    "success_tier": "verified",
                    "tokens": 40 + i,
                    "needs_tools": False,
                    "phase": "edit",
                    "hint_bin": "hard",
                    "expected": "return x + 1",
                }
            )
        for mid, ok in oc.items():
            eval_rows.append(
                {
                    "prompt": f"Holdout {i}: repair",
                    "model_id": mid,
                    "success": ok,
                    "tokens": 35 + i,
                    "needs_tools": False,
                    "phase": "edit",
                }
            )
    train = tmp_path / "train.jsonl"
    ev = tmp_path / "eval.jsonl"
    train.write_text("".join(json.dumps(r) + "\n" for r in train_rows), encoding="utf-8")
    ev.write_text("".join(json.dumps(r) + "\n" for r in eval_rows), encoding="utf-8")
    return train, ev


def test_fixture_files_geometry_pass():
    report = geometry_report(TRAIN_FIX, EVAL_FIX)
    assert report["geometry_pass"] is True
    assert report["spearman_train_eval"] > 0
    assert report["holdout_like_order"] is True
    assert 0.07 <= report["train"]["y_rate"] <= 0.22


def test_probe_recipe_synthetic_geometry_pass(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("AIAND_TRAIN", raising=False)
    train, ev = _write_holdout_like_fixture(tmp_path)
    assert geometry_main(["--train", str(train), "--eval", str(ev)]) == 0
    out = capsys.readouterr().out
    report = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert report["geometry_pass"] is True


def test_fit_bilinear_with_geometry_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    monkeypatch.delenv(GEOMETRY_OVERRIDE_ENV, raising=False)
    gold = tmp_path / "fit-gold.jsonl"
    rows = []
    for i in range(12):
        rows.append(
            {
                "prompt": f"train task {i}",
                "model_id": FLASH,
                "success": i % 3 != 0,
                "tokens": 45,
                "needs_tools": False,
                "phase": "edit",
                "hint_bin": "hard",
            }
        )
    gold.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out = tmp_path / "scorer.json"
    code = train_main(
        [
            "fit",
            "--gold",
            str(gold),
            "--out",
            str(out),
            "--bilinear",
            "--geometry-train",
            str(TRAIN_FIX),
            "--geometry-eval",
            str(EVAL_FIX),
        ]
    )
    assert code == 0
    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact.get("head") == "bilinear"
    assert artifact.get("geometry", {}).get("geometry_pass") is True


def test_hard_y_probe_project_unpaid():
    import subprocess
    import sys

    pool = Path("data/pool-hard-mix-near_miss_seed11.jsonl")
    if not pool.exists():
        pytest.skip("operator pool not present")
    proc = subprocess.run(
        [sys.executable, "scripts/hard_y_probe.py", "project", "--queries", str(pool), "--limit", "40"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["cells"] == 40 * 4
    assert 0 < data["projected_usd"] < 15


def test_hard_y_probe_sample_excludes_labeled(tmp_path):
    import subprocess
    import sys

    pool = tmp_path / "pool.jsonl"
    labeled = tmp_path / "gold.jsonl"
    out = tmp_path / "sampled.jsonl"
    pool.write_text(
        json.dumps({"prompt": "keep me", "instance_id": "keep-1", "expected": "return x + 1"})
        + "\n"
        + json.dumps({"prompt": "drop me", "instance_id": "drop-1", "expected": "return x + 1"})
        + "\n",
        encoding="utf-8",
    )
    labeled.write_text(
        json.dumps({"prompt": "drop me", "instance_id": "drop-1", "model_id": "x", "success": False})
        + "\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/hard_y_probe.py",
            "sample",
            "--queries",
            str(pool),
            "--out",
            str(out),
            "--limit",
            "8",
            "--seed",
            "12",
            "--exclude",
            str(labeled),
            "--near-miss-lo",
            "0",
            "--near-miss-hi",
            "1",
            "--min-expected-len",
            "0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [r["instance_id"] for r in rows] == ["keep-1"]
