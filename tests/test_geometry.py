from __future__ import annotations

import json
import os
from pathlib import Path

from aiand_router.geometry import (
    FLASH,
    KIMI,
    PRO,
    QWEN,
    main,
)


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _cells(prompt: str, tokens: int, outcomes: dict[str, bool], *, phase: str = "plan") -> list[dict]:
    return [
        {
            "prompt": prompt,
            "model_id": mid,
            "success": ok,
            "tokens": tokens,
            "needs_tools": False,
            "phase": phase,
        }
        for mid, ok in outcomes.items()
    ]


def _unobserved(prompt: str, mid: str, tokens: int = 20) -> dict:
    return {
        "prompt": prompt,
        "model_id": mid,
        "unobserved": True,
        "tokens": tokens,
        "needs_tools": False,
        "phase": "plan",
    }


def test_geometry_cli_prints_spearman_and_kill_without_opt_in(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("AIAND_TRAIN", raising=False)
    train = _write_jsonl(
        tmp_path / "gold-sparse.jsonl",
        _cells("long train", 400, {"cheap/flash": True, "mid/kimi": False, "dear/pro": True})
        + _cells("long train 2", 400, {"cheap/flash": True, "mid/kimi": False, "dear/pro": True}),
    )
    cal = _write_jsonl(
        tmp_path / "gold-dense.jsonl",
        _cells("easy cal", 300, {"cheap/flash": True, "mid/kimi": True, "dear/pro": True}),
    )
    eval_gold = _write_jsonl(
        tmp_path / "gold-verified.jsonl",
        _cells("short eval", 20, {"cheap/flash": False, "mid/kimi": True, "dear/pro": False})
        + _cells("short eval 2", 20, {"cheap/flash": False, "mid/kimi": True, "dear/pro": False}),
    )
    code = main(
        [
            "--train",
            str(train),
            "--cal",
            str(cal),
            "--eval",
            str(eval_gold),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    report = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert report["train"]["per_id"]["cheap/flash"] == 1.0
    assert report["train"]["per_id"]["mid/kimi"] == 0.0
    assert report["eval"]["per_id"]["cheap/flash"] == 0.0
    assert report["eval"]["per_id"]["mid/kimi"] == 1.0
    assert report["spearman_train_eval"] == -1.0
    assert report["kill_spearman"] is True
    assert report["kill"] is True
    assert report["geometry_pass"] is False
    assert report["prefer_logistic"] is True
    assert report["train"]["y_rate"] == 4 / 6
    assert report["eval"]["y_rate"] == 2 / 6
    assert report["train"]["frac_log1p_gt_4_8"] == 1.0
    assert report["eval"]["frac_log1p_le_4_14"] == 1.0
    assert report["eval_is_fit_gold"] is False
    assert "replay_gate_pass" not in report
    assert os.getenv("TRAINED_PATH") != "trained"
    assert os.getenv("AIAND_TRAIN") is None


def test_geometry_zero_spearman_kills(tmp_path, capsys, monkeypatch):
    """Spearman == 0 must kill (failed hard-y probe left kill_spearman false)."""
    monkeypatch.delenv("AIAND_TRAIN", raising=False)
    same = {"cheap/flash": True, "mid/kimi": True, "dear/pro": True}
    train = _write_jsonl(tmp_path / "gold-sparse.jsonl", _cells("a", 20, same) + _cells("b", 20, same))
    eval_gold = _write_jsonl(tmp_path / "gold-verified.jsonl", _cells("c", 20, same) + _cells("d", 20, same))
    assert main(["--train", str(train), "--eval", str(eval_gold)]) == 0
    out = capsys.readouterr().out
    report = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert report["spearman_train_eval"] == 0.0
    assert report["kill_spearman"] is True
    assert report["kill"] is True
    assert report["geometry_pass"] is False
    assert report["prefer_logistic"] is True
    assert report["recommended_artifact"] == "data/scorer-logistic.json"


def test_geometry_undefined_spearman_kills(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("AIAND_TRAIN", raising=False)
    train = _write_jsonl(
        tmp_path / "gold-sparse.jsonl",
        _cells("a", 20, {"cheap/flash": True, "mid/kimi": False}),
    )
    eval_gold = _write_jsonl(
        tmp_path / "gold-verified.jsonl",
        _cells("c", 20, {"dear/pro": False, "other/qwen": True}),
    )
    assert main(["--train", str(train), "--eval", str(eval_gold)]) == 0
    out = capsys.readouterr().out
    report = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert report["spearman_train_eval"] == 0.0
    assert report["kill_spearman"] is True
    assert report["prefer_logistic"] is True
    assert report["recommended_artifact"] == "data/scorer-logistic.json"


def test_geometry_empty_y_kills_even_with_unobserved(tmp_path, capsys, monkeypatch):
    """All observed fails → y_rate 0 kill; unobserved must not count as fails."""
    monkeypatch.delenv("AIAND_TRAIN", raising=False)
    train_rows = (
        _cells(
            "hard",
            20,
            {FLASH: False, QWEN: False, KIMI: False, PRO: False},
        )
        + [_unobserved("hard", FLASH), _unobserved("hard", KIMI)]
    )
    train = _write_jsonl(tmp_path / "gold-sparse.jsonl", train_rows)
    eval_gold = _write_jsonl(
        tmp_path / "gold-verified.jsonl",
        _cells(
            "eval",
            20,
            {FLASH: False, QWEN: False, KIMI: True, PRO: False},
        ),
    )
    assert main(["--train", str(train), "--eval", str(eval_gold)]) == 0
    out = capsys.readouterr().out
    report = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert report["train"]["y_rate"] == 0.0
    assert report["train"]["observed_n"] == 4
    assert report["train"]["unobserved_n"] == 2
    assert report["kill_y_empty"] is True
    assert report["kill"] is True
    assert report["geometry_pass"] is False


def test_geometry_dense_easy_y_kills(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("AIAND_TRAIN", raising=False)
    # 8/20 = 0.4 ≈ dense-easy ~0.39 (closer to 0.39 than hard-band mid)
    outcomes = [
        {FLASH: True, QWEN: True, KIMI: False, PRO: False},
        {FLASH: True, QWEN: True, KIMI: False, PRO: False},
        {FLASH: True, QWEN: True, KIMI: False, PRO: False},
        {FLASH: True, QWEN: True, KIMI: False, PRO: False},
        {FLASH: False, QWEN: False, KIMI: False, PRO: False},
    ]
    train_rows: list[dict] = []
    for i, oc in enumerate(outcomes):
        train_rows.extend(_cells(f"easy {i}", 300, oc))
    train = _write_jsonl(tmp_path / "gold-sparse.jsonl", train_rows)
    eval_gold = _write_jsonl(
        tmp_path / "gold-verified.jsonl",
        _cells("e", 20, {FLASH: False, QWEN: False, KIMI: True, PRO: False})
        + _cells("f", 20, {FLASH: False, QWEN: False, KIMI: True, PRO: False}),
    )
    assert main(["--train", str(train), "--eval", str(eval_gold)]) == 0
    out = capsys.readouterr().out
    report = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert abs(report["train"]["y_rate"] - 0.39) < 0.02
    assert report["kill_y_easy"] is True
    assert report["kill"] is True
    assert report["y_in_hard_band"] is False
    assert report["geometry_pass"] is False


def test_geometry_pass_hard_band_holdout_order(tmp_path, capsys, monkeypatch):
    """Pass: Spearman > 0, y in ~0.07–0.22, Kimi ≫ Flash ≈ Qwen ≫ Pro."""
    monkeypatch.delenv("AIAND_TRAIN", raising=False)
    # 20 cells: 3 successes → y_rate 0.15. Rates: Kimi 2/5, Flash=Qwen 0.5/5? need Flash≈Qwen > Pro
    # Per id over 5 prompts: Flash 1/5=0.2, Qwen 1/5=0.2, Kimi 2/5=0.4, Pro 0/5=0 → y=4/20=0.2
    train_rows: list[dict] = []
    patterns = [
        {FLASH: False, QWEN: False, KIMI: True, PRO: False},
        {FLASH: False, QWEN: False, KIMI: True, PRO: False},
        {FLASH: True, QWEN: False, KIMI: False, PRO: False},
        {FLASH: False, QWEN: True, KIMI: False, PRO: False},
        {FLASH: False, QWEN: False, KIMI: False, PRO: False},
    ]
    for i, oc in enumerate(patterns):
        train_rows.extend(_cells(f"t{i}", 20, oc))
    train = _write_jsonl(tmp_path / "gold-sparse.jsonl", train_rows)
    # Matching holdout order on eval → Spearman > 0
    eval_rows: list[dict] = []
    for i, oc in enumerate(patterns):
        eval_rows.extend(_cells(f"e{i}", 20, oc))
    eval_gold = _write_jsonl(tmp_path / "gold-verified.jsonl", eval_rows)
    assert main(["--train", str(train), "--eval", str(eval_gold)]) == 0
    out = capsys.readouterr().out
    report = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert report["spearman_train_eval"] > 0
    assert report["train"]["y_rate"] == 0.2
    assert report["y_in_hard_band"] is True
    assert report["holdout_like_order"] is True
    assert report["kill_spearman"] is False
    assert report["kill_y_empty"] is False
    assert report["kill_y_easy"] is False
    assert report["kill"] is False
    assert report["geometry_pass"] is True
    assert report["prefer_logistic"] is False
    assert report["recommended_artifact"] == "data/scorer.json"
    assert report["eval_is_fit_gold"] is False


def test_geometry_y_rate_ignores_unobserved(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("AIAND_TRAIN", raising=False)
    # 1 success / 2 observed = 0.5; many unobserved must not dilute to "all fail"
    train = _write_jsonl(
        tmp_path / "gold-sparse.jsonl",
        _cells("a", 20, {FLASH: True, QWEN: False})
        + [_unobserved("a", KIMI), _unobserved("a", PRO), _unobserved("b", FLASH)],
    )
    eval_gold = _write_jsonl(
        tmp_path / "gold-verified.jsonl",
        _cells("c", 20, {FLASH: True, QWEN: False}),
    )
    assert main(["--train", str(train), "--eval", str(eval_gold)]) == 0
    out = capsys.readouterr().out
    report = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert report["train"]["y_rate"] == 0.5
    assert report["train"]["observed_n"] == 2
    assert report["train"]["unobserved_n"] == 3
    assert "kill" in out
    assert "geometry_pass" in out


def test_geometry_positive_spearman_allows_scorer_json(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("AIAND_TRAIN", raising=False)
    order = {"cheap/flash": False, "mid/kimi": True, "dear/pro": False}
    train = _write_jsonl(tmp_path / "gold-sparse.jsonl", _cells("a", 20, order) + _cells("b", 20, order))
    eval_gold = _write_jsonl(tmp_path / "gold-verified.jsonl", _cells("c", 20, order) + _cells("d", 20, order))
    assert main(["--train", str(train), "--eval", str(eval_gold)]) == 0
    out = capsys.readouterr().out
    report = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert report["spearman_train_eval"] > 0
    assert report["kill_spearman"] is False
    assert report["prefer_logistic"] is False
    assert report["recommended_artifact"] == "data/scorer.json"
    # Fake ids → not holdout-like order → no geometry_pass
    assert report["holdout_like_order"] is False
    assert report["geometry_pass"] is False


def test_geometry_cli_help_says_eval_only(capsys):
    try:
        main(["-h"])
    except SystemExit as e:
        assert e.code == 0
    help_text = capsys.readouterr().out.lower()
    assert "--eval" in help_text
    assert "eval-only" in help_text or "not fit" in help_text
    assert "spearman" in help_text
    assert "kill" in help_text
