import json
import hashlib
import pathlib
from pathlib import Path
import pytest

from aiand_router.pool import MANIFEST_VALID_SPLITS
from aiand_router.train import CHEAP_TEACHER, main as train_main, _prompt_hash, _manifest_prompt_of_row
from aiand_router.router import SpendLog
from aiand_router.cache import RequestCache

OPT = "AIAND_TRAIN"


def _hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]


def _label(prompt_hash="ok"):
    import json as _j
    return {
        "status": 200,
        "json": {
            "choices": [{"message": {"content": _j.dumps({"complexity_bin": "standard", "label_confidence": 0.9, "p_success": {"deepseek-ai/deepseek-v4-flash": 0.8}})}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        },
    }


class FakeProvider:
    def __init__(self, script=None):
        self.calls = []
        self.script = list(script or [])
        self._idx = 0

    async def complete(self, body):
        self.calls.append(dict(body))
        if self._idx < len(self.script):
            r = self.script[self._idx]
            self._idx += 1
            return r
        return _label()


def _write_manifest(tmp_path: Path, rows, splits):
    import datetime, json
    out = []
    for r, sp in zip(rows, splits):
        prompt = r["prompt"]
        out.append({"prompt_hash": _hash(prompt), "instance_id": r.get("instance_id"), "split": sp, "assigned_at": "2026-08-21"})
    data = {"metadata": {"spend_before_A": 8.16, "generated_at": "2026-08-21", "total": len(out), "seed": 0}, "rows": out}
    p = tmp_path / "split_manifest.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def test_split_filter_correctness_teacher(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT, "1")
    rows = [
        {"prompt": "prompt teacher 1", "instance_id": "q1", "phase": "edit", "needs_tools": False},
        {"prompt": "prompt teacher 2", "instance_id": "q2", "phase": "edit", "needs_tools": False},
        {"prompt": "prompt sparse 1", "instance_id": "q3", "phase": "edit", "needs_tools": False},
        {"prompt": "prompt sparse 2", "instance_id": "q4", "phase": "edit", "needs_tools": False},
        {"prompt": "prompt dense", "instance_id": "q5", "phase": "edit", "needs_tools": False},
    ]
    splits = ["teacher-silver", "teacher-silver", "sparse-train", "sparse-train", "dense-cal"]
    _write_manifest(tmp_path, rows, splits)
    queries = tmp_path / "queries.jsonl"
    queries.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out = tmp_path / "silver.jsonl"
    provider = FakeProvider([_label() for _ in range(10)])
    spend = SpendLog(tmp_path / "spend.txt", 15)
    code = train_main(
        ["teacher", "--queries", str(queries), "--out", str(out), "--split", "teacher-silver"],
        provider=provider,
        spend=spend,
        cache_dir=tmp_path / "cache",
        models_path=Path("config/models.yaml"),
    )
    assert code == 0
    written = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(written) == 2
    prompts = {r["prompt"] for r in written}
    assert prompts == {"prompt teacher 1", "prompt teacher 2"}


def test_split_gold_filter_correctness(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT, "1")
    rows = [
        {"prompt": "prompt teacher 1", "instance_id": "q1", "phase": "edit", "needs_tools": False},
        {"prompt": "prompt sparse 1", "instance_id": "q2", "phase": "edit", "needs_tools": False},
        {"prompt": "prompt sparse 2", "instance_id": "q3", "phase": "edit", "needs_tools": False},
    ]
    splits = ["teacher-silver", "sparse-train", "sparse-train"]
    _write_manifest(tmp_path, rows, splits)
    queries = tmp_path / "queries.jsonl"
    queries.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out = tmp_path / "gold.jsonl"
    provider = FakeProvider([{"status": 200, "json": {"choices": [{"message": {"content": "hello"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 10}} } for _ in range(10)])
    spend = SpendLog(tmp_path / "spend.txt", 15)

    code = train_main(
        ["gold", "--queries", str(queries), "--out", str(out), "--split", "sparse-train"],
        provider=provider,
        spend=spend,
        cache_dir=tmp_path / "cache",
        models_path=Path("config/models.yaml"),
    )
    assert code == 0
    written = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    prompts = {r["prompt"] for r in written}
    assert prompts == {"prompt sparse 1", "prompt sparse 2"}
    assert len(written) == 8


def test_split_unknown_refusal(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT, "1")
    rows = [{"prompt": "hello", "instance_id": "q1"}]
    _write_manifest(tmp_path, rows, ["teacher-silver"])
    queries = tmp_path / "queries.jsonl"
    queries.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
    out = tmp_path / "silver.jsonl"
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15)
    with pytest.raises(SystemExit) as ei:
        train_main(
            ["teacher", "--queries", str(queries), "--out", str(out), "--split", "bogus-split"],
            provider=provider,
            spend=spend,
            cache_dir=tmp_path / "cache",
            models_path=Path("config/models.yaml"),
        )
    assert ei.value.code == 2


def test_no_flag_backward_compat_ad_hoc(tmp_path, monkeypatch):
    monkeypatch.setenv(OPT, "1")
    queries = tmp_path / "q.jsonl"
    queries.write_text(json.dumps({"prompt": "ad hoc prompt no manifest", "phase": "edit"}) + "\n", encoding="utf-8")
    out = tmp_path / "silver.jsonl"
    provider = FakeProvider([_label()])
    spend = SpendLog(tmp_path / "spend.txt", 15)
    code = train_main(
        ["teacher", "--queries", str(queries), "--out", str(out)],
        provider=provider,
        spend=spend,
        cache_dir=tmp_path / "cache",
        models_path=Path("config/models.yaml"),
    )
    assert code == 0
    assert out.exists()
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row["prompt"] == "ad hoc prompt no manifest"
