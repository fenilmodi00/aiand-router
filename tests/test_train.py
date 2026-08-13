from __future__ import annotations

import json
import os
from pathlib import Path

from aiand_router.router import SpendLog
from aiand_router.train import OPT_IN_ENV, main
from tests.test_gateway import FakeProvider, _ok

MOTIF = "motif-technologies/motif-3"
GLM = "zai-org/glm-5.2"


def _label(bin: str = "standard", p=None, confidence: float = 0.9) -> dict:
    p = p or {"deepseek-ai/deepseek-v4-flash": 0.8}
    return {
        "status": 200,
        "json": {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "complexity_bin": bin,
                                "label_confidence": confidence,
                                "p_success": p,
                            }
                        ),
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    }


def test_train_refuses_without_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv(OPT_IN_ENV, raising=False)
    provider = FakeProvider([_label()])
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "fix the bug"}) + "\n", encoding="utf-8")
    code = main(
        ["teacher", "--queries", str(queries), "--out", str(tmp_path / "silver.jsonl")],
        provider=provider,
        spend=spend,
    )
    assert code == 2
    assert provider.calls == []
    assert spend.total() == 0
    assert not (tmp_path / "silver.jsonl").exists()


def test_teacher_writes_silver_and_uses_motif_then_cache(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    provider = FakeProvider([_label(), _label()])
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "rename a variable"}) + "\n", encoding="utf-8")
    out = tmp_path / "silver.jsonl"
    kwargs = dict(
        provider=provider,
        spend=spend,
        cache_dir=tmp_path / "cache",
        models_path=Path("config/models.yaml"),
    )
    assert main(["teacher", "--queries", str(queries), "--out", str(out), "--limit", "1"], **kwargs) == 0
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row["complexity_bin"] == "standard"
    assert 0 <= row["p_success"]["deepseek-ai/deepseek-v4-flash"] <= 1
    assert provider.calls[0]["model"] == MOTIF
    assert provider.calls[0]["temperature"] == 0
    assert provider.calls[0]["response_format"]["type"] == "json_schema"
    first_spend = spend.total()
    assert first_spend > 0
    assert main(["teacher", "--queries", str(queries), "--out", str(out), "--limit", "1"], **kwargs) == 0
    assert spend.total() == first_spend
    assert provider.calls[0]["model"] != "qwen/qwen3.6-27b"


def test_invalid_teacher_output_is_unlabeled_not_fake(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    bad = _ok("not json")
    provider = FakeProvider([bad, bad, bad, bad])
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "hard multi-file refactor"}) + "\n", encoding="utf-8")
    out = tmp_path / "silver.jsonl"
    code = main(
        ["teacher", "--queries", str(queries), "--out", str(out), "--limit", "1"],
        provider=provider,
        spend=spend,
        cache_dir=tmp_path / "cache",
    )
    assert code == 0
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row.get("unlabeled") is True
    assert "complexity_bin" not in row or row["complexity_bin"] is None
    assert row.get("p_success") in (None, {})


def test_gold_sparse_skips_k3_and_fit_writes_not_spec_floors(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "add a docstring"}) + "\n", encoding="utf-8")
    gold = tmp_path / "gold.jsonl"
    kwargs = dict(
        provider=provider,
        spend=spend,
        cache_dir=tmp_path / "cache",
        models_path=Path("config/models.yaml"),
    )
    assert main(["gold", "--queries", str(queries), "--out", str(gold), "--limit", "1"], **kwargs) == 0
    rows = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines() if line.strip()]
    models = {r["model_id"] for r in rows}
    assert "moonshotai/kimi-k3" not in models
    assert "deepseek-ai/deepseek-v4-flash" in models
    assert "qwen/qwen3.6-27b" in models
    silver = tmp_path / "silver.jsonl"
    silver.write_text(
        json.dumps(
            {
                "complexity_bin": "trivial",
                "p_success": {
                    "deepseek-ai/deepseek-v4-flash": 0.9,
                    "google/gemma-4-31b-it": 0.4,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    artifact = tmp_path / "scorer.json"
    assert main(["fit", "--gold", str(gold), "--silver", str(silver), "--out", str(artifact)], **kwargs) == 0
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data["not_spec_floors"] is True
    assert "deepseek-ai/deepseek-v4-flash" in data["p_success"]
    assert "google/gemma-4-31b-it" not in data["p_success"]


def test_gold_refuses_without_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv(OPT_IN_ENV, raising=False)
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "x"}) + "\n", encoding="utf-8")
    code = main(
        ["gold", "--queries", str(queries), "--out", str(tmp_path / "gold.jsonl")],
        provider=provider,
        spend=spend,
    )
    assert code == 2
    assert provider.calls == []
    assert spend.total() == 0


def test_dense_gold_excludes_k3(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "x"}) + "\n", encoding="utf-8")
    gold = tmp_path / "gold.jsonl"
    main(
        ["gold", "--queries", str(queries), "--out", str(gold), "--limit", "1", "--dense"],
        provider=provider,
        spend=spend,
        cache_dir=tmp_path / "cache",
        models_path=Path("config/models.yaml"),
    )
    models = {
        json.loads(line)["model_id"]
        for line in gold.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert "moonshotai/kimi-k3" not in models
    assert "google/gemma-4-31b-it" in models
