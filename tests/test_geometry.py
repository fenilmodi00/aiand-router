from __future__ import annotations

import json
import os
from pathlib import Path

from aiand_router.geometry import main


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
    assert report["prefer_logistic"] is True
    assert report["train"]["y_rate"] == 4 / 6
    assert report["eval"]["y_rate"] == 2 / 6
    assert report["train"]["frac_log1p_gt_4_8"] == 1.0
    assert report["eval"]["frac_log1p_le_4_14"] == 1.0
    assert report["eval_is_fit_gold"] is False
    assert "replay_gate_pass" not in report
    assert os.getenv("TRAINED_PATH") != "trained"


def test_geometry_cli_help_says_eval_only(capsys):
    try:
        main(["-h"])
    except SystemExit as e:
        assert e.code == 0
    help_text = capsys.readouterr().out.lower()
    assert "--eval" in help_text
    assert "eval-only" in help_text or "not fit" in help_text
    assert "spearman" in help_text
