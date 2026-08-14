from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
from aiand_router.router import SpendLog, load_config, load_models
from aiand_router.cache import RequestCache
from aiand_router.train import (
    ESCALATE_TEACHER,
    K3,
    MIN_REASONING_EFFORT,
    OPT_IN_ENV,
    SPARSE_ANCHORS,
    _fit_binary_intercept,
    _fit_platt,
    _gold_label,
    _gold_success,
    _logit,
    _row_x,
    _split_cal_prompts,
    _teacher_call,
    main,
)
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


def test_teacher_call_sends_min_reasoning_effort_for_glm(tmp_path):
    """Escalate/salvage GLM must send published min effort so JSON can finish."""
    provider = FakeProvider([_label()])
    asyncio.run(
        _teacher_call(
            provider,
            ESCALATE_TEACHER,
            [{"role": "user", "content": "x"}],
            cache=RequestCache(tmp_path / "cache"),
            spend=SpendLog(tmp_path / "spend.txt", 15),
            models_by_id={},
        )
    )
    assert provider.calls[0]["reasoning_effort"] == MIN_REASONING_EFFORT[ESCALATE_TEACHER]


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
    assert models >= set(SPARSE_ANCHORS)
    for r in rows:
        assert "success" in r and "success_tier" in r
        assert "resolved" not in r and "y" not in r
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
    monkeypatch.setenv("TRAIN_CONCURRENCY", "2")

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
    assert 1 < provider.max_in_flight <= 2


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
    empty = tmp_path / "none.jsonl"
    empty.write_text("", encoding="utf-8")
    main(
        [
            "gold",
            "--queries",
            str(queries),
            "--out",
            str(gold),
            "--limit",
            "1",
            "--dense",
            "--exclude",
            str(empty),
        ],
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


def test_dense_gold_runs_every_eligible_id_except_k3(tmp_path, monkeypatch):
    """Dense/cal slice runs every enabled catalog id except K3; JSONL marks dense."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "cal slice prompt"}) + "\n", encoding="utf-8")
    gold = tmp_path / "gold.jsonl"
    empty = tmp_path / "none.jsonl"
    empty.write_text("", encoding="utf-8")
    assert (
        main(
            [
                "gold",
                "--queries",
                str(queries),
                "--out",
                str(gold),
                "--limit",
                "1",
                "--dense",
                "--exclude",
                str(empty),
            ],
            provider=provider,
            spend=spend,
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    rows = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    assert all(r.get("dense") is True for r in rows)
    models = {r["model_id"] for r in rows}
    cfg = load_config(Path("config/models.yaml"))
    eligible = {m.id for m in load_models(cfg) if m.enabled and m.id != K3}
    assert models == eligible
    assert K3 not in models
    assert K3 not in {c["model"] for c in provider.calls}
    for r in rows:
        if not r.get("unobserved"):
            assert "success" in r and "success_tier" in r


def test_dense_gold_excludes_sparse_train_prompts(tmp_path, monkeypatch):
    """Dense/cal queries are disjoint from sparse train prompts used for feature fit."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    train_q = tmp_path / "train.jsonl"
    train_q.write_text(json.dumps({"prompt": "sparse train prompt"}) + "\n", encoding="utf-8")
    queries = tmp_path / "q.jsonl"
    queries.write_text(
        json.dumps({"prompt": "sparse train prompt"})
        + "\n"
        + json.dumps({"prompt": "held out cal prompt"})
        + "\n",
        encoding="utf-8",
    )
    gold = tmp_path / "dense.jsonl"
    assert (
        main(
            [
                "gold",
                "--queries",
                str(queries),
                "--out",
                str(gold),
                "--dense",
                "--exclude",
                str(train_q),
            ],
            provider=provider,
            spend=spend,
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    rows = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines() if line.strip()]
    prompts = {r["prompt"] for r in rows}
    assert prompts == {"held out cal prompt"}
    assert "sparse train prompt" not in prompts
    assert all(r.get("dense") is True for r in rows)
    assert K3 not in {r["model_id"] for r in rows}


def test_dense_exclude_before_sample_same_pool_is_nonempty_and_disjoint(tmp_path, monkeypatch):
    """Same pool + same seed: exclude before sample so dense fills n from leftover."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    cache = tmp_path / "cache"
    models = Path("config/models.yaml")
    pool = tmp_path / "pool.jsonl"
    pool.write_text(
        "".join(json.dumps({"prompt": f"pool prompt {i}"}) + "\n" for i in range(6)),
        encoding="utf-8",
    )
    sparse = tmp_path / "sparse.jsonl"
    dense = tmp_path / "dense.jsonl"
    assert (
        main(
            ["gold", "--queries", str(pool), "--out", str(sparse), "--limit", "3"],
            provider=provider,
            spend=spend,
            cache_dir=cache,
            models_path=models,
        )
        == 0
    )
    assert (
        main(
            [
                "gold",
                "--queries",
                str(pool),
                "--out",
                str(dense),
                "--dense",
                "--exclude",
                str(sparse),
                "--limit",
                "2",
            ],
            provider=provider,
            spend=spend,
            cache_dir=cache,
            models_path=models,
        )
        == 0
    )
    sparse_prompts = {json.loads(line)["prompt"] for line in sparse.read_text(encoding="utf-8").splitlines() if line.strip()}
    rows = [json.loads(line) for line in dense.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    dense_prompts = {r["prompt"] for r in rows}
    assert dense_prompts.isdisjoint(sparse_prompts)
    cfg = load_config(models)
    eligible = {m.id for m in load_models(cfg) if m.enabled and m.id != K3}
    assert {r["model_id"] for r in rows} == eligible
    assert K3 not in {r["model_id"] for r in rows}


def test_dense_exclude_empty_leftover_fails_closed(tmp_path, monkeypatch):
    """--dense --exclude with nothing left must not write an empty cal slice."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    pool = tmp_path / "pool.jsonl"
    pool.write_text(
        json.dumps({"prompt": "a"}) + "\n" + json.dumps({"prompt": "b"}) + "\n",
        encoding="utf-8",
    )
    sparse = tmp_path / "sparse.jsonl"
    dense = tmp_path / "dense.jsonl"
    assert (
        main(
            ["gold", "--queries", str(pool), "--out", str(sparse), "--limit", "2"],
            provider=provider,
            spend=spend,
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    code = main(
        [
            "gold",
            "--queries",
            str(pool),
            "--out",
            str(dense),
            "--dense",
            "--exclude",
            str(sparse),
            "--limit",
            "1",
        ],
        provider=provider,
        spend=spend,
        cache_dir=tmp_path / "cache",
        models_path=Path("config/models.yaml"),
    )
    assert code != 0
    assert not dense.exists()


def test_dense_requires_exclude(tmp_path, monkeypatch):
    """--dense without --exclude would let the same prompts sit in sparse gold and cal."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "x"}) + "\n", encoding="utf-8")
    gold = tmp_path / "dense.jsonl"
    code = main(
        ["gold", "--queries", str(queries), "--out", str(gold), "--limit", "1", "--dense"],
        provider=FakeProvider(),
        spend=SpendLog(tmp_path / "spend.txt", 15),
        cache_dir=tmp_path / "cache",
        models_path=Path("config/models.yaml"),
    )
    assert code != 0
    assert not gold.exists()


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
    # Query-level tests_passed is dump metadata, not this candidate's y.
    assert _gold_success({"content": "ok"}, "hello", {}, meta={"tests_passed": False}) is True


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
    # Pin Platt to cal-gold only: would fail if silver (y=1) or train-gold leaked in.
    _, cal_prompts = _split_cal_prompts([r["prompt"] for r in gold_rows])
    cal_gold = [r for r in gold_rows if r["prompt"] in cal_prompts]
    assert cal_gold and all(r["success"] is False for r in cal_gold)
    w = data["weights"][mid]
    ic = data["intercepts"][mid]
    zs, ys = [], []
    for r in cal_gold:
        x = _row_x(r)
        zs.append(ic + sum(w[i] * x[i] for i in range(len(w))))
        ys.append(1.0 if r["success"] else 0.0)
    a, b = _fit_platt(zs, ys)
    assert data["platt"]["a"] == a
    assert data["platt"]["b"] == b


def test_fit_dense_cal_unused_for_train_weights(tmp_path, monkeypatch):
    """Dense/cal JSONL is Platt + new-id onboard only — not train intercepts/weights."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    flash = "deepseek-ai/deepseek-v4-flash"
    gemma = "google/gemma-4-31b-it"
    train_rows = [_gold_cell(f"train prompt {i}", flash, True) for i in range(4)]
    cal_rows = [_gold_cell(f"zz cal prompt {i}", flash, False) for i in range(2)]
    cal_rows += [_gold_cell(r["prompt"], gemma, True) for r in cal_rows[:2]]
    for r in cal_rows:
        r["dense"] = True
    gold = tmp_path / "sparse.jsonl"
    gold.write_text("".join(json.dumps(r) + "\n" for r in train_rows), encoding="utf-8")
    cal = tmp_path / "dense.jsonl"
    cal.write_text("".join(json.dumps(r) + "\n" for r in cal_rows), encoding="utf-8")
    artifact = tmp_path / "scorer.json"
    assert (
        main(
            ["fit", "--gold", str(gold), "--cal", str(cal), "--out", str(artifact)],
            provider=FakeProvider(),
            spend=SpendLog(tmp_path / "spend.txt", 15),
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data["not_spec_floors"] is True
    assert data["intercepts"][flash] == _logit(1.0)
    assert gemma not in data.get("weights", {})
    assert gemma not in data.get("intercepts", {})
    assert data["p_success"][gemma] == 1.0
    assert data["n_cal"] == len(cal_rows)
    w = data["weights"][flash]
    ic = data["intercepts"][flash]
    zs, ys = [], []
    for r in cal_rows:
        if r["model_id"] != flash:
            continue
        x = _row_x(r)
        zs.append(ic + sum(w[i] * x[i] for i in range(len(w))))
        ys.append(1.0 if r["success"] else 0.0)
    a, b = _fit_platt(zs, ys)
    assert data["platt"]["a"] == a
    assert data["platt"]["b"] == b


def test_fit_cal_only_id_with_silver_gets_no_weights(tmp_path, monkeypatch):
    """Cal-only ids onboard via p_success; silver must not invent intercepts/weights."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    flash = "deepseek-ai/deepseek-v4-flash"
    gemma = "google/gemma-4-31b-it"
    train_rows = [_gold_cell(f"train prompt {i}", flash, True) for i in range(4)]
    cal_rows = [_gold_cell(f"zz cal prompt {i}", flash, False) for i in range(2)]
    cal_rows += [_gold_cell(r["prompt"], gemma, True) for r in cal_rows[:2]]
    for r in cal_rows:
        r["dense"] = True
    gold = tmp_path / "sparse.jsonl"
    gold.write_text("".join(json.dumps(r) + "\n" for r in train_rows), encoding="utf-8")
    cal = tmp_path / "dense.jsonl"
    cal.write_text("".join(json.dumps(r) + "\n" for r in cal_rows), encoding="utf-8")
    silver = tmp_path / "silver.jsonl"
    silver.write_text(
        json.dumps(
            {
                "prompt": "silver only",
                "complexity_bin": "standard",
                "p_success": {gemma: 0.9, flash: 0.8},
                "tokens": 10,
                "needs_tools": False,
                "phase": "edit",
                "hint_bin": "standard",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    artifact = tmp_path / "scorer.json"
    assert (
        main(
            [
                "fit",
                "--gold",
                str(gold),
                "--cal",
                str(cal),
                "--silver",
                str(silver),
                "--out",
                str(artifact),
            ],
            provider=FakeProvider(),
            spend=SpendLog(tmp_path / "spend.txt", 15),
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert gemma not in data.get("weights", {})
    assert gemma not in data.get("intercepts", {})
    assert data["p_success"][gemma] == 1.0
    assert flash in data["weights"]


def test_fit_dense_tagged_rows_unused_for_train_weights(tmp_path, monkeypatch):
    """dense=true gold cells stay out of train weights even in a concatenated --gold file."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    flash = "deepseek-ai/deepseek-v4-flash"
    train_rows = [_gold_cell(f"zz train {i}", flash, True) for i in range(8)]
    cal_rows = [_gold_cell(f"aa cal {i}", flash, False) for i in range(2)]
    for r in cal_rows:
        r["dense"] = True
    gold = tmp_path / "gold.jsonl"
    gold.write_text("".join(json.dumps(r) + "\n" for r in train_rows + cal_rows), encoding="utf-8")
    artifact = tmp_path / "scorer.json"
    assert (
        main(
            ["fit", "--gold", str(gold), "--out", str(artifact)],
            provider=FakeProvider(),
            spend=SpendLog(tmp_path / "spend.txt", 15),
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data["intercepts"][flash] == _logit(1.0)
    assert data["n_cal"] == len(cal_rows)


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
        {"content": "4"},
        "What is 2+2?",
        {},
        meta={"expected": "5"},
    )
    assert ok is False and tier == "verified"
    assert _gold_success({"content": ""}, "x", {"finish_reason": "length"}) is False


def test_gold_expected_beats_tool_calls_proxy():
    """Verified expected must win before gateway tool_calls proxy."""
    ok, tier = _gold_label(
        {"content": "wrong", "tool_calls": [{"id": "1"}]},
        "What is 2+2?",
        {},
        meta={"expected": "4"},
    )
    assert ok is False and tier == "verified"


def test_gold_json_schema_beats_tool_calls_proxy():
    """Verified JSON/schema on the query wins before gateway tool_calls proxy."""
    ok, tier = _gold_label(
        {"content": "not json", "tool_calls": [{"id": "1"}]},
        "call a tool",
        {},
        meta={"json_schema": {"type": "object", "required": ["status"]}},
    )
    assert ok is False and tier == "verified"


def test_gold_query_level_tests_passed_is_not_y():
    """Dump/query tests_passed must not stamp the same y on every model."""
    ok, tier = _gold_label(
        {"content": "looks fine"},
        "implement foo",
        {},
        meta={"tests_passed": False},
    )
    assert ok is True and tier == "weak"


def test_gold_needs_tools_sends_tools_array(tmp_path, monkeypatch):
    """needs_tools gold request must include a tools array so the model can emit tool_calls."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(
        json.dumps(
            {
                "prompt": "Use a tool to list files in src.",
                "phase": "tool",
                "hint_bin": "standard",
                "needs_tools": True,
                "source": "swe-smith",
            }
        )
        + "\n",
        encoding="utf-8",
    )
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
    assert provider.calls
    assert all(isinstance(c.get("tools"), list) and c["tools"] for c in provider.calls)


def test_gold_needs_tools_without_tool_calls_is_not_success(tmp_path, monkeypatch):
    """needs_tools + nonempty text + no tool_calls is observed fail, not weak-True."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(
        json.dumps(
            {
                "prompt": "Use a tool to list files in src.",
                "phase": "tool",
                "hint_bin": "standard",
                "needs_tools": True,
                "source": "swe-smith",
            }
        )
        + "\n",
        encoding="utf-8",
    )
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
    observed = [r for r in rows if not r.get("unobserved")]
    assert observed
    assert all(r.get("success") is False for r in observed)
    assert all("success" in r for r in observed)


def test_gold_sparse_skips_ineligible_anchors(tmp_path, monkeypatch):
    """Flash + measured trio run when eligible; ineligible anchors are not gold cells."""
    import yaml

    monkeypatch.setenv(OPT_IN_ENV, "1")
    cfg = yaml.safe_load(Path("config/models.yaml").read_text(encoding="utf-8"))
    for m in cfg["models"]:
        if m["id"] == "moonshotai/kimi-k2.7-code":
            m["supports_tools"] = False
    models_path = tmp_path / "models.yaml"
    models_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(
        json.dumps(
            {
                "prompt": "Use a tool to list files in src.",
                "phase": "tool",
                "hint_bin": "standard",
                "needs_tools": True,
                "source": "swe-smith",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gold = tmp_path / "gold.jsonl"
    assert (
        main(
            ["gold", "--queries", str(queries), "--out", str(gold), "--limit", "1"],
            provider=provider,
            spend=spend,
            cache_dir=tmp_path / "cache",
            models_path=models_path,
        )
        == 0
    )
    called = {c["model"] for c in provider.calls}
    assert "moonshotai/kimi-k2.7-code" not in called
    assert "deepseek-ai/deepseek-v4-flash" in called
    assert "qwen/qwen3.6-27b" in called
    assert "deepseek-ai/deepseek-v4-pro" in called
    assert "moonshotai/kimi-k3" not in called
    rows = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines() if line.strip()]
    models = {r["model_id"] for r in rows}
    assert "moonshotai/kimi-k2.7-code" not in models
    assert "moonshotai/kimi-k3" not in models
    for r in rows:
        if not r.get("unobserved"):
            assert "success" in r and "success_tier" in r


def test_gold_is_cache_first(tmp_path, monkeypatch):
    """Second gold run on the same bodies is cache-first: no new spend, no new provider calls."""
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
    n_calls = len(provider.calls)
    first_spend = spend.total()
    assert n_calls > 0 and first_spend > 0
    assert main(["gold", "--queries", str(queries), "--out", str(gold), "--limit", "1"], **kwargs) == 0
    assert len(provider.calls) == n_calls
    assert spend.total() == first_spend


def test_gold_upstream_429_is_unobserved_not_failure(tmp_path, monkeypatch):
    """Provider 429 is missing, not success=0."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    rate = {"status": 429, "json": {"error": {"message": "rate"}}}
    provider = FakeProvider([rate, rate, rate, rate])
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
    assert rows and all(r.get("unobserved") is True for r in rows)
    assert all("success" not in r for r in rows)


def test_gold_dump_resolved_is_not_y(tmp_path, monkeypatch):
    """Dump teacher resolved on a pool-shaped row is not gold y."""
    monkeypatch.setenv(OPT_IN_ENV, "1")

    class Empty:
        def __init__(self):
            self.calls = []

        async def complete(self, body):
            self.calls.append(dict(body))
            return _ok("")

    provider = Empty()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    queries = tmp_path / "q.jsonl"
    queries.write_text(
        json.dumps(
            {
                "prompt": "add a docstring",
                "phase": "edit",
                "hint_bin": "trivial",
                "needs_tools": False,
                "source": "swe-smith",
                "resolved": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
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
    observed = [r for r in rows if not r.get("unobserved")]
    assert observed and all(r.get("success") is False for r in observed)
    assert all("resolved" not in r and "y" not in r for r in rows)


def test_gold_budget_code_default_stays_15(tmp_path, monkeypatch):
    """Code default BUDGET_LIMIT_USD stays 15 unless the operator raises it."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    monkeypatch.delenv("BUDGET_LIMIT_USD", raising=False)
    captured: dict[str, float] = {}
    real = SpendLog

    def wrap(path, limit):
        captured["limit"] = float(limit)
        return real(tmp_path / "spend.txt", limit)

    monkeypatch.setattr("aiand_router.train.SpendLog", wrap)
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "x"}) + "\n", encoding="utf-8")
    assert (
        main(
            ["gold", "--queries", str(queries), "--out", str(tmp_path / "gold.jsonl"), "--limit", "1"],
            provider=FakeProvider(),
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
        == 0
    )
    assert captured["limit"] == 15.0


def test_gold_budget_skip_is_unobserved_not_failure(tmp_path, monkeypatch):
    """429 / pre-call budget skip stays missing — unobserved ≠ 0."""
    monkeypatch.setenv(OPT_IN_ENV, "1")
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    spend.add(15.0)
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
    assert provider.calls == []
    rows = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines() if line.strip()]
    observed_fails = [r for r in rows if not r.get("unobserved") and r.get("success") is False]
    assert observed_fails == []
    skipped = {mid for mid in SPARSE_ANCHORS}
    observed_ids = {r["model_id"] for r in rows if not r.get("unobserved") and "model_id" in r}
    assert skipped.isdisjoint(observed_ids)
    for r in rows:
        if r.get("unobserved"):
            assert "success" not in r


def test_fit_binary_intercept_freezes_bias_column():
    """Per-model intercept already locks the marginal; do not also learn w[0]."""
    xs = [[1.0, 2.0], [1.0, -1.0], [1.0, 0.5], [1.0, 3.0]]
    ys = [1.0, 0.0, 1.0, 0.0]
    w = _fit_binary_intercept(xs, ys, intercept=_logit(0.5))
    assert w[0] == 0.0
