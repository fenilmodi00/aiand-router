from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
from aiand_router.router import SpendLog
from aiand_router.train import OPT_IN_ENV, _gold_label, _gold_success, main
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
    queries.write_text(
        json.dumps({"prompt": "rename a variable", "phase": "edit", "needs_tools": True}) + "\n",
        encoding="utf-8",
    )
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
    assert row["phase"] == "edit"
    assert row["needs_tools"] is True
    assert row.get("hint_bin") == "standard"
    assert 0 <= row["p_success"]["deepseek-ai/deepseek-v4-flash"] <= 1
    assert provider.calls[0]["model"] == MOTIF
    assert provider.calls[0]["temperature"] == 0
    assert provider.calls[0]["response_format"]["type"] == "json_schema"
    assert provider.calls[0]["max_completion_tokens"] == 1024
    assert provider.calls[0].get("reasoning_effort") == "low"
    first_spend = spend.total()
    assert first_spend > 0
    assert main(["teacher", "--queries", str(queries), "--out", str(out), "--limit", "1"], **kwargs) == 0
    assert spend.total() == first_spend
    assert provider.calls[0]["model"] != "qwen/qwen3.6-27b"


def test_parse_fail_still_escalates_after_quality_cap(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")
    script = []
    for _ in range(5):
        script.extend([_ok("not json"), _ok("not json"), _label(confidence=0.9)])
    provider = FakeProvider(script)
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(
        "".join(json.dumps({"prompt": f"rename {i}"}) + "\n" for i in range(5)),
        encoding="utf-8",
    )
    out = tmp_path / "silver.jsonl"
    assert (
        main(
            ["teacher", "--queries", str(queries), "--out", str(out), "--limit", "5"],
            provider=provider,
            spend=spend,
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 5
    assert all(not r.get("unlabeled") for r in rows)
    assert sum(1 for c in provider.calls if c["model"] == GLM) == 5


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
    by_id = {c["model"]: c for c in provider.calls}
    assert by_id["deepseek-ai/deepseek-v4-flash"]["max_tokens"] == 512
    assert by_id["deepseek-ai/deepseek-v4-flash"]["reasoning_effort"] == "none"
    assert by_id["qwen/qwen3.6-27b"]["reasoning_effort"] == "none"
    assert by_id["moonshotai/kimi-k2.7-code"]["reasoning_effort"] == "high"
    assert by_id["moonshotai/kimi-k2.7-code"]["max_tokens"] == 1024
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
    assert "deepseek-ai/deepseek-v4-flash" in data["weights"]
    assert "google/gemma-4-31b-it" not in data["weights"]
    assert "platt" in data


def test_gold_timeout_is_unsuccessful_cell_not_crash(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")

    class TimeoutThenOk:
        def __init__(self):
            self.calls = []

        async def complete(self, body):
            self.calls.append(dict(body))
            if len(self.calls) == 1:
                raise httpx.ReadTimeout("slow")
            return _ok("pong")

    provider = TimeoutThenOk()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "add a docstring"}) + "\n", encoding="utf-8")
    gold = tmp_path / "gold.jsonl"
    assert (
        main(
            ["gold", "--queries", str(queries), "--out", str(gold), "--limit", "1"],
            provider=provider,
            spend=spend,
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    rows = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(r["success"] is False for r in rows)
    assert any(r["success"] is True for r in rows)


def test_gold_runs_cells_concurrently(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, "1")

    class Slow:
        def __init__(self):
            self.calls = []
            self.in_flight = 0
            self.max_in_flight = 0

        async def complete(self, body):
            self.calls.append(dict(body))
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            await asyncio.sleep(0.05)
            self.in_flight -= 1
            return _ok("pong")

    provider = Slow()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "add a docstring"}) + "\n", encoding="utf-8")
    gold = tmp_path / "gold.jsonl"
    assert (
        main(
            ["gold", "--queries", str(queries), "--out", str(gold), "--limit", "1"],
            provider=provider,
            spend=spend,
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    assert provider.max_in_flight > 1


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


def test_gold_success_json_and_one_word():
    assert _gold_success({"content": '{"ok": true}'}, "Reply with JSON only.", {}) is True
    assert _gold_success({"content": "not json"}, "Reply with JSON only.", {}) is False
    assert _gold_success({"content": "yes"}, "Reply with the single word yes.", {}) is True
    assert _gold_success({"content": "no"}, "Reply with the single word yes.", {}) is False
    assert _gold_success({"content": ""}, "hello", {"finish_reason": "length"}) is False
    assert _gold_success({"tool_calls": [{"id": "1"}]}, "hello", {}) is True
    assert _gold_success({"content": "receive"}, "Fix the typo 'recieve' to 'receive'.", {}) is True
    assert _gold_success({"content": "recieve"}, "Fix the typo 'recieve' to 'receive'.", {}) is False
    assert _gold_success({"content": '```json\n{"a":1}\n```'}, "Reply with JSON only.", {}) is True
    assert _gold_success({"content": "ok"}, "hello", {}, meta={"tests_passed": False}) is False


def test_gold_success_tiers():
    ok, tier = _gold_label({"content": "4"}, "What is 2+2?", {}, meta={"expected": "4"})
    assert ok and tier == "verified"
    ok, tier = _gold_label({"content": '{"a": 1}'}, "Reply with JSON only.", {})
    assert ok and tier == "proxy"
    ok, tier = _gold_label({"content": "hello world"}, "Say something.", {})
    assert ok and tier == "weak"
    ok, tier = _gold_label(
        {"content": "```python\ndef is_even(n):\n    return n % 2 == 0\n```"},
        "fix",
        {},
        meta={"verify_pytest": True, "module": "parity.py", "tests": "from parity import is_even\n\ndef test_e():\n    assert is_even(2)\n"},
    )
    assert ok and tier == "verified"


def _gold_cell(prompt: str, mid: str, success: bool, *, tier: str = "verified") -> dict:
    return {
        "prompt": prompt,
        "model_id": mid,
        "success": success,
        "success_tier": tier,
        "unobserved": False,
        "tokens": 10,
        "needs_tools": False,
        "phase": "edit",
        "hint_bin": "standard",
    }


def test_fit_calibrates_on_held_out_gold_cal_slice_only(tmp_path, monkeypatch):
    """Platt is fit on held-out gold prompts only — not in-sample on all gold, never silver."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    mid = "deepseek-ai/deepseek-v4-flash"
    gold_rows = [_gold_cell(f"train prompt {i}", mid, True) for i in range(8)]
    gold_rows += [_gold_cell(f"zz cal prompt {i}", mid, False) for i in range(2)]
    gold = tmp_path / "gold.jsonl"
    gold.write_text("".join(json.dumps(r) + "\n" for r in gold_rows), encoding="utf-8")
    # Silver would pull calibrator toward 1.0 if it leaked into Platt.
    silver_rows = [
        {
            "prompt": r["prompt"],
            "complexity_bin": "standard",
            "p_success": {mid: 1.0, "google/gemma-4-31b-it": 0.95},
            "tokens": 10,
            "needs_tools": False,
            "phase": "edit",
            "hint_bin": "standard",
        }
        for r in gold_rows
    ]
    silver = tmp_path / "silver.jsonl"
    silver.write_text("".join(json.dumps(r) + "\n" for r in silver_rows), encoding="utf-8")
    artifact = tmp_path / "scorer.json"
    assert (
        main(
            ["fit", "--gold", str(gold), "--silver", str(silver), "--out", str(artifact)],
            provider=FakeProvider(),
            spend=SpendLog(tmp_path / "spend.txt", 15),
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data["not_spec_floors"] is True
    assert "platt" in data and "a" in data["platt"] and "b" in data["platt"]
    assert "intercepts" in data and mid in data["intercepts"]
    assert "bin_weights" in data and data["bin_weights"]
    assert "google/gemma-4-31b-it" not in data.get("weights", {})
    assert "google/gemma-4-31b-it" not in data.get("p_success", {})
    n_prompts = len({r["prompt"] for r in gold_rows})
    assert data["n_cal"] >= 1
    assert data["n_cal"] < n_prompts
    assert data["n_cal"] < data["n_gold"]


def test_fit_silver_only_regularizes_unobserved_not_observed_gold(tmp_path, monkeypatch):
    """Silver on an observed gold cell must not dilute gold y; missing gold stays missing."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    mid = "deepseek-ai/deepseek-v4-flash"
    gold = tmp_path / "gold.jsonl"
    gold.write_text(json.dumps(_gold_cell("only cell", mid, False)) + "\n", encoding="utf-8")
    silver = tmp_path / "silver.jsonl"
    silver.write_text(
        json.dumps(
            {
                "prompt": "only cell",
                "complexity_bin": "hard",
                "p_success": {mid: 1.0, "google/gemma-4-31b-it": 0.9},
                "tokens": 10,
                "needs_tools": False,
                "phase": "edit",
                "hint_bin": "hard",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    artifact = tmp_path / "scorer.json"
    assert (
        main(
            ["fit", "--gold", str(gold), "--silver", str(silver), "--out", str(artifact)],
            provider=FakeProvider(),
            spend=SpendLog(tmp_path / "spend.txt", 15),
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data["intercepts"][mid] < -2.0
    assert data["p_success"][mid] == 0.0
    assert "google/gemma-4-31b-it" not in data["weights"]
    assert "google/gemma-4-31b-it" not in data["p_success"]


def test_gold_y_verified_beats_nonempty_content():
    """Verified metadata wins over nonempty reply; length+empty is failure."""
    ok, tier = _gold_label(
        {"content": "looks fine"},
        "implement foo",
        {},
        meta={"tests_passed": False},
    )
    assert ok is False and tier == "verified"
    ok, tier = _gold_label(
        {"content": "4"},
        "What is 2+2?",
        {},
        meta={"expected": "5"},
    )
    assert ok is False and tier == "verified"
    assert _gold_success({"content": ""}, "x", {"finish_reason": "length"}) is False
