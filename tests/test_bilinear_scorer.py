"""Bilinear / IRT-lite head: fit → load → score_eligible round-trip."""

from __future__ import annotations

import json
import os
from pathlib import Path

from aiand_router.router import Model
from aiand_router.scorer import (
    featurize_bilinear,
    load_scorer,
    pick_cheapest_above_bar,
    score_eligible,
)
from aiand_router.train import OPT_IN_ENV, main

FLASH = "deepseek-ai/deepseek-v4-flash"
PRO = "deepseek-ai/deepseek-v4-pro"


def _gold_cell(
    prompt: str,
    mid: str,
    success: bool,
    *,
    phase: str = "edit",
    needs_tools: bool = False,
) -> dict:
    return {
        "prompt": prompt,
        "model_id": mid,
        "success": success,
        "success_tier": "verified",
        "unobserved": False,
        "tokens": 80,
        "needs_tools": needs_tools,
        "phase": phase,
        "hint_bin": "standard",
    }


def _fit_bilinear_artifact(tmp_path: Path, gold_rows: list[dict]) -> dict:
    gold = tmp_path / "gold.jsonl"
    gold.write_text("".join(json.dumps(r) + "\n" for r in gold_rows), encoding="utf-8")
    cal = tmp_path / "cal.jsonl"
    cal_rows = []
    for i in range(2):
        cal_rows.append(
            _gold_cell(f"zz cal code {i}: def cal(): pass", FLASH, True, phase="edit")
        )
        cal_rows.append(
            _gold_cell(f"zz cal code {i}: def cal(): pass", PRO, False, phase="edit")
        )
        cal_rows.append(
            _gold_cell(f"zz cal math {i}: 2+2 reply with 4", FLASH, False, phase="summarize")
        )
        cal_rows.append(
            _gold_cell(f"zz cal math {i}: 2+2 reply with 4", PRO, True, phase="summarize")
        )
    cal.write_text("".join(json.dumps(r) + "\n" for r in cal_rows), encoding="utf-8")
    out = tmp_path / "scorer.json"
    assert (
        main(
            ["fit", "--gold", str(gold), "--cal", str(cal), "--out", str(out), "--bilinear"],
            provider=None,
            spend=None,
        )
        == 0
    )
    return json.loads(out.read_text(encoding="utf-8"))


def test_bilinear_fit_round_trip_load_and_score(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    rows = []
    for i in range(12):
        rows.append(_gold_cell(f"code task {i}: def foo(): pass", FLASH, True, phase="edit"))
        rows.append(_gold_cell(f"code task {i}: def foo(): pass", PRO, False, phase="edit"))
    artifact = _fit_bilinear_artifact(tmp_path, rows)
    assert artifact["head"] == "bilinear"
    assert artifact["bilinear"]["query_proj"]
    assert FLASH in artifact["bilinear"]["models"]
    loaded = load_scorer(tmp_path / "scorer.json")
    assert loaded is not None
    _, ps = score_eligible(
        loaded,
        [FLASH, PRO],
        phase="edit",
        needs_tools=False,
        tokens=80,
        text="def bar(): return 1",
    )
    assert FLASH in ps and PRO in ps
    assert ps[FLASH] > ps[PRO]


def test_bilinear_pick_swaps_on_query_model_interaction(tmp_path, monkeypatch):
    """Phase/text cues should flip relative P(success) across models."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    rows = []
    for i in range(12):
        rows.append(
            _gold_cell(
                f"Files: module.py def patch_{i}(): pass",
                FLASH,
                True,
                phase="edit",
            )
        )
        rows.append(
            _gold_cell(
                f"Files: module.py def patch_{i}(): pass",
                PRO,
                False,
                phase="edit",
            )
        )
        rows.append(
            _gold_cell(
                f"What is 2+2? reply with 4 task {i}",
                FLASH,
                False,
                phase="summarize",
            )
        )
        rows.append(
            _gold_cell(
                f"What is 2+2? reply with 4 task {i}",
                PRO,
                True,
                phase="summarize",
            )
        )
    artifact = _fit_bilinear_artifact(tmp_path, rows)
    code_text = "Files: foo.py def broken(): pass"
    math_text = "What is 2+2? reply with the number 4"
    _, ps_code = score_eligible(
        artifact,
        [FLASH, PRO],
        phase="edit",
        tokens=80,
        text=code_text,
    )
    _, ps_math = score_eligible(
        artifact,
        [FLASH, PRO],
        phase="summarize",
        tokens=80,
        text=math_text,
    )
    assert ps_code[FLASH] > ps_code[PRO]
    assert ps_math[PRO] > ps_math[FLASH]
    flash = Model(
        id=FLASH,
        display_name="Flash",
        enabled=True,
        input_per_1m=0.15,
        cached_input_per_1m=0.08,
        output_per_1m=0.25,
        context_window=1_048_576,
        supports_tools=True,
        supports_json=True,
        supports_streaming=True,
        max_output_tokens=16_384,
        aa_index=52,
        aa_source="test",
        measured_on="test",
        measured_success=None,
        latency_ms=0.0,
        health=1.0,
        priors=None,
    )
    pro = Model(
        id=PRO,
        display_name="Pro",
        enabled=True,
        input_per_1m=1.0,
        cached_input_per_1m=0.25,
        output_per_1m=2.5,
        context_window=1_048_576,
        supports_tools=True,
        supports_json=True,
        supports_streaming=True,
        max_output_tokens=16_384,
        aa_index=53,
        aa_source="test",
        measured_on="test",
        measured_success=None,
        latency_ms=0.0,
        health=1.0,
        priors=None,
    )
    pick_code, _ = pick_cheapest_above_bar(
        [flash, pro], ps_code, threshold=0.10, max_regret=0.20
    )
    pick_math, _ = pick_cheapest_above_bar(
        [flash, pro], ps_math, threshold=0.10, max_regret=0.20
    )
    assert pick_code is not None and pick_code.id == FLASH
    assert pick_math is not None and pick_math.id == PRO


def test_hash_text_latent_deterministic_and_unitish():
    from aiand_router.scorer import hash_text_latent

    a = hash_text_latent("Files: foo.py def broken(): pass", 16, seed=17)
    b = hash_text_latent("Files: foo.py def broken(): pass", 16, seed=17)
    c = hash_text_latent("What is 2+2? reply with 4", 16, seed=17)
    assert a == b
    assert len(a) == 16
    assert abs(sum(v * v for v in a) - 1.0) < 1e-6
    assert a != c


def test_bilinear_live_hash_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    rows = []
    for i in range(12):
        rows.append(_gold_cell(f"code task {i}: def foo(): pass", FLASH, True, phase="edit"))
        rows.append(_gold_cell(f"code task {i}: def foo(): pass", PRO, False, phase="edit"))
    gold = tmp_path / "gold.jsonl"
    gold.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    cal = tmp_path / "cal.jsonl"
    cal.write_text(
        "".join(
            json.dumps(_gold_cell(f"zz cal {i}", FLASH, i % 2 == 0, phase="edit")) + "\n"
            for i in range(8)
        ),
        encoding="utf-8",
    )
    out = tmp_path / "scorer.json"
    assert (
        main(
            [
                "fit",
                "--gold",
                str(gold),
                "--cal",
                str(cal),
                "--out",
                str(out),
                "--bilinear",
                "--bilinear-hash-dim",
                "8",
            ],
            provider=None,
            spend=None,
        )
        == 0
    )
    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["bilinear"]["hash_dim"] == 8
    x = featurize_bilinear("edit", False, 80, "standard", text="def bar(): pass", hash_dim=8)
    assert len(artifact["bilinear"]["query_proj"][0]) == len(x)
    loaded = load_scorer(out)
    _, ps = score_eligible(
        loaded,
        [FLASH, PRO],
        phase="edit",
        tokens=80,
        text="def bar(): return 1",
    )
    assert FLASH in ps and PRO in ps


def test_bilinear_distill_serves_without_hash(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    rows = []
    for i in range(12):
        rows.append(
            _gold_cell(f"Files: module.py def patch_{i}(): pass", FLASH, True, phase="edit")
        )
        rows.append(
            _gold_cell(f"Files: module.py def patch_{i}(): pass", PRO, False, phase="edit")
        )
        rows.append(
            _gold_cell(f"What is 2+2? reply with 4 task {i}", FLASH, False, phase="summarize")
        )
        rows.append(
            _gold_cell(f"What is 2+2? reply with 4 task {i}", PRO, True, phase="summarize")
        )
    gold = tmp_path / "gold.jsonl"
    gold.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    cal = tmp_path / "cal.jsonl"
    cal.write_text(
        "".join(
            json.dumps(_gold_cell(f"zz cal distill {i}", FLASH, False, phase="edit")) + "\n"
            for i in range(8)
        ),
        encoding="utf-8",
    )
    out = tmp_path / "scorer.json"
    assert (
        main(
            [
                "fit",
                "--gold",
                str(gold),
                "--cal",
                str(cal),
                "--out",
                str(out),
                "--bilinear",
                "--bilinear-distill-hash-dim",
                "16",
            ],
            provider=None,
            spend=None,
        )
        == 0
    )
    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["bilinear"]["hash_dim"] == 0
    assert artifact["bilinear"]["teacher_hash_dim"] == 16
    assert artifact["bilinear"]["distill"]["mode"] == "hash_teacher_ridge"
    base_x = featurize_bilinear("edit", False, 80, "standard", text="def x(): pass", hash_dim=0)
    assert len(artifact["bilinear"]["query_proj"][0]) == len(base_x)
    _, ps = score_eligible(
        artifact,
        [FLASH, PRO],
        phase="edit",
        tokens=80,
        text="Files: foo.py def broken(): pass",
    )
    assert FLASH in ps and PRO in ps


def test_bilinear_distill_latent_and_ridge_cli(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    rows = []
    for i in range(12):
        rows.append(_gold_cell(f"code task {i}: def foo(): pass", FLASH, True, phase="edit"))
        rows.append(_gold_cell(f"code task {i}: def foo(): pass", PRO, False, phase="edit"))
    gold = tmp_path / "gold.jsonl"
    gold.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    cal = tmp_path / "cal.jsonl"
    cal.write_text(
        "".join(
            json.dumps(_gold_cell(f"zz cal ld {i}", FLASH, i % 2 == 0, phase="edit")) + "\n"
            for i in range(8)
        ),
        encoding="utf-8",
    )
    out = tmp_path / "scorer.json"
    assert (
        main(
            [
                "fit",
                "--gold",
                str(gold),
                "--cal",
                str(cal),
                "--out",
                str(out),
                "--bilinear",
                "--bilinear-distill-hash-dim",
                "16",
                "--bilinear-distill-latent-dim",
                "8",
                "--bilinear-ridge-l2",
                "0.2",
            ],
            provider=None,
            spend=None,
        )
        == 0
    )
    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["bilinear"]["distill"]["latent_dim"] == 8
    assert abs(float(artifact["bilinear"]["distill"]["ridge_l2"]) - 0.2) < 1e-9
    assert len(artifact["bilinear"]["query_proj"]) == 8


def test_fit_bilinear_uses_feature_dim_identity(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    rows = [
        _gold_cell(f"code task {i}: def foo(): pass", FLASH, i == 0, phase="edit")
        for i in range(16)
    ]
    artifact = _fit_bilinear_artifact(tmp_path, rows)
    qp = artifact["bilinear"]["query_proj"]
    x = featurize_bilinear("edit", False, 80, "standard", text="def foo(): pass")
    assert len(qp) == len(x)
    assert all(len(row) == len(x) for row in qp)
    assert all(abs(qp[i][i] - 1.0) < 1e-6 for i in range(len(x)))
    flash_ic = artifact["bilinear"]["models"][FLASH]["intercept"]
    # Frozen at gold logit (1/16 success), not drifted toward 0 by joint GD / n.
    assert flash_ic < -2.0


def test_fit_platt_rejects_inverted_slope():
    from aiand_router.fit import _fit_platt

    # High z, low y (anti-ranked) must not ship a negative Platt a.
    zs = [2.0, 2.1, -2.0, -2.1]
    ys = [0.0, 0.0, 1.0, 1.0]
    a, b = _fit_platt(zs, ys)
    assert a == 1.0 and b == 0.0


def test_featurize_bilinear_includes_phase_family():
    x_edit = featurize_bilinear("edit", False, 100, "standard", text="def x(): pass")
    x_sum = featurize_bilinear("summarize", False, 100, "standard", text="summarize this")
    assert x_edit != x_sum


def test_fit_geometry_gate_blocks_without_override(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    monkeypatch.delenv("GEOMETRY_OVERRIDE", raising=False)
    train = tmp_path / "train.jsonl"
    eval_g = tmp_path / "eval.jsonl"
    # Inverted holdout order -> geometry_pass false
    train.write_text(
        json.dumps(_gold_cell("long", FLASH, True, phase="plan"))
        + "\n"
        + json.dumps(_gold_cell("long", PRO, True, phase="plan"))
        + "\n",
        encoding="utf-8",
    )
    eval_g.write_text(
        json.dumps(_gold_cell("short", FLASH, False, phase="plan"))
        + "\n"
        + json.dumps(_gold_cell("short", PRO, False, phase="plan"))
        + "\n",
        encoding="utf-8",
    )
    gold = tmp_path / "gold.jsonl"
    gold.write_text(json.dumps(_gold_cell("fit row", FLASH, True)) + "\n", encoding="utf-8")
    out = tmp_path / "out.jsonl"
    code = main(
        [
            "fit",
            "--gold",
            str(gold),
            "--out",
            str(out),
            "--geometry-train",
            str(train),
            "--geometry-eval",
            str(eval_g),
        ]
    )
    assert code == 2
    assert not out.exists()
    err = capsys.readouterr().err
    assert "geometry_pass=false" in err


def test_fit_geometry_override_allows_fit(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    monkeypatch.setenv("GEOMETRY_OVERRIDE", "1")
    train = tmp_path / "train.jsonl"
    eval_g = tmp_path / "eval.jsonl"
    train.write_text(
        json.dumps(_gold_cell("long", FLASH, True)) + "\n",
        encoding="utf-8",
    )
    eval_g.write_text(
        json.dumps(_gold_cell("short", FLASH, False)) + "\n",
        encoding="utf-8",
    )
    rows = [_gold_cell(f"train {i}", FLASH, True) for i in range(4)]
    gold = tmp_path / "gold.jsonl"
    gold.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out = tmp_path / "scorer.json"
    code = main(
        [
            "fit",
            "--gold",
            str(gold),
            "--out",
            str(out),
            "--geometry-train",
            str(train),
            "--geometry-eval",
            str(eval_g),
        ]
    )
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data.get("geometry", {}).get("geometry_override") is True
