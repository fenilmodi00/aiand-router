import json
import hashlib
import pathlib
import tempfile
from pathlib import Path

import pytest

from aiand_router.pool import (
    MANIFEST_VALID_SPLITS,
    MANIFEST_SPEND_BEFORE_A,
    _prompt_hash,
    build_split_manifest_rows,
    load_split_manifest,
    validate_split_manifest,
    write_split_manifest,
)
from aiand_router.train import (
    _guard_manifest_for_queries,
    _load_manifest_map,
    _prompt_hash as train_hash,
)


def test_prompt_hash_matches_train():
    s = "hello world prompt"
    assert _prompt_hash(s) == train_hash(s) == hashlib.sha256(s.encode()).hexdigest()[:12]


def test_manifest_schema_and_valid_splits():
    p = Path("data/split_manifest.json")
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "metadata" in data and "rows" in data
    rows = data["rows"]
    pool_n = len([l for l in Path("data/queries_spec.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()])
    assert len(rows) == pool_n
    assert len(rows) == data["metadata"]["total"]
    assert 6500 <= len(rows) <= 7500
    for r in rows:
        assert set(r.keys()) == {"prompt_hash", "instance_id", "split", "assigned_at"}
        assert isinstance(r["prompt_hash"], str) and len(r["prompt_hash"]) == 12
        assert r["instance_id"] is None or isinstance(r["instance_id"], str)
        assert r["split"] in MANIFEST_VALID_SPLITS
        assert r["assigned_at"]  # iso-date
    assert MANIFEST_VALID_SPLITS == {
        "teacher-silver",
        "sparse-train",
        "dense-cal",
        "threshold-tune",
        "promotion-holdout",
    }


def test_metadata_spend_before():
    data = json.loads(Path("data/split_manifest.json").read_text(encoding="utf-8"))
    meta = data["metadata"]
    assert meta["spend_before_A"] == 8.16
    assert meta["spend_before_A"] == MANIFEST_SPEND_BEFORE_A
    pool_n = len([l for l in Path("data/queries_spec.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()])
    assert meta["total"] == pool_n
    assert 6500 <= meta["total"] <= 7500
    assert meta["seed"] == 0
    # data/spend.txt stays single float line >= spend_before_A (paid tranches may increase it)
    spend_raw = Path("data/spend.txt").read_text(encoding="utf-8")
    assert spend_raw.strip().replace(".", "", 1).isdigit()
    assert float(spend_raw.strip()) >= 8.16
    assert spend_raw.count("\n") == 1 or spend_raw.strip().count("\n") == 0


def test_deterministic_rerun():
    qs = [json.loads(l) for l in Path("data/queries_spec.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    r1 = build_split_manifest_rows(qs, seed=0, assigned_at="2026-08-21")
    r2 = build_split_manifest_rows(qs, seed=0, assigned_at="2026-08-21")
    assert r1 == r2
    # different seed would differ (not required but sanity)
    # same pool -> same splits (idempotent writer)


def test_absent_id_refusal():
    # query hash not in manifest -> guard raises split_manifest_overlap
    fake = [{"prompt": "this prompt definitely not in pool " + "x" * 100, "instance_id": "q_fake"}]
    with pytest.raises(ValueError, match="split_manifest_overlap"):
        _guard_manifest_for_queries(fake, allowed_splits={"teacher-silver"})
    # also direct map check
    with pytest.raises(ValueError, match="split_manifest_overlap"):
        _guard_manifest_for_queries(fake)


def test_double_assignment_in_manifest():
    # build a manifest with duplicate prompt_hash
    rows = build_split_manifest_rows(
        [json.loads(l) for l in Path("data/queries_spec.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()][:5],
        seed=0,
        assigned_at="2026-08-21",
    )
    dup = rows[0].copy()
    rows.append(dup)
    data = {"metadata": {"spend_before_A": 8.16}, "rows": rows}
    with pytest.raises(ValueError, match="split_manifest_overlap"):
        validate_split_manifest(data)
    # double-assigned query hash within queries list
    p = Path("data/split_manifest.json")
    data_real = json.loads(p.read_text(encoding="utf-8"))
    # pick a real row's prompt
    qs = [json.loads(l) for l in Path("data/queries_spec.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # find a teacher-silver hash
    mp = _load_manifest_map()
    teacher_hash = next(h for h, s in mp.items() if s == "teacher-silver")
    # recover prompt for that hash (find qs that hashes to it)
    target_q = None
    for q in qs:
        if train_hash(q["prompt"]) == teacher_hash:
            target_q = q
            break
    assert target_q is not None
    dup_qs = [target_q, target_q]
    with pytest.raises(ValueError, match="split_manifest_overlap"):
        _guard_manifest_for_queries(dup_qs, allowed_splits={"teacher-silver"})


def test_allowed_split_enforcement():
    qs = [json.loads(l) for l in Path("data/queries_spec.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    mp = _load_manifest_map()
    # find one of each
    teacher_q = next(q for q in qs if mp.get(train_hash(q["prompt"])) == "teacher-silver")
    sparse_q = next(q for q in qs if mp.get(train_hash(q["prompt"])) == "sparse-train")
    # teacher query should pass for teacher, fail for sparse
    _guard_manifest_for_queries([teacher_q], allowed_splits={"teacher-silver"})
    with pytest.raises(ValueError, match="split_manifest_overlap"):
        _guard_manifest_for_queries([teacher_q], allowed_splits={"sparse-train"})
    _guard_manifest_for_queries([sparse_q], allowed_splits={"sparse-train"})
    with pytest.raises(ValueError, match="split_manifest_overlap"):
        _guard_manifest_for_queries([sparse_q], allowed_splits={"teacher-silver"})


def test_baseline_reader_behavior_today():
    # characterization: _load_manifest_map succeeds and returns pool-sized entries, disjoint splits
    mp = _load_manifest_map()
    pool_n = len([l for l in Path("data/queries_spec.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()])
    assert len(mp) == pool_n
    assert 6500 <= len(mp) <= 7500
    # no duplicate hashes (already validated)
    # spends: spend_before from metadata equals file total
    assert len(set(mp.values())) <= 5
