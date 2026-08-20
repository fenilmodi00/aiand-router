"""Unpaid gym_alt preflight helper tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "gym_alt_preflight.py"
SPEC = importlib.util.spec_from_file_location("gym_alt_preflight", SCRIPT_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def _build_report(**overrides):
    defaults = dict(
        pool_path=Path("data/pool-hard-gym-alt-seed2-n40.jsonl"),
        mix1_pool_path=Path("data/pool-hard-mix-near_miss_seed11.jsonl"),
        mix1_gold_path=Path("data/gold-sparse-hard-mix1.jsonl"),
        spend_path=Path("data/spend.txt"),
        budget_cap_usd=15.0,
        seed_name="gym-alt-seed2",
        limit=32,
        exclude_paths=list(mod.DEFAULT_EXCLUDE),
    )
    defaults.update(overrides)
    return mod.build_report(**defaults)


def test_gym_alt_preflight_seed2_passes_when_pool_built():
    pool = Path("data/pool-hard-gym-alt-seed2-n40.jsonl")
    if not pool.exists():
        pytest.skip("seed2 pool not built yet")
    report = _build_report()
    assert report["pool_n"] >= 32
    assert report["collision_hits"] == 0
    assert report["within_budget_cap"] is True
    wp = report["projected_winner_mix"]
    assert wp["kimi_only_floor_ok"] is True
    assert wp["all_fail_ceiling_ok"] is True
    assert report["paid_gold_justified"] is True
    assert report["paid_command"] is not None
    assert "gym-alt-seed2" in report["paid_command"]


def test_gym_alt_preflight_blocks_tie_heavy_legacy_n40():
    legacy = Path("data/pool-hard-gym-alt-n40.jsonl")
    if not legacy.exists():
        pytest.skip("legacy gym_alt n40 missing")
    report = _build_report(pool_path=legacy, seed_name="gym-alt-seed1")
    assert report["projected_winner_mix"]["winner_mix_gate_pass"] is False
    assert report["paid_gold_justified"] is False
    assert any("projected" in b for b in report["blockers"])


def test_gym_alt_preflight_geometry_predictor_disclaimed():
    pool = Path("data/pool-hard-gym-alt-seed2-n40.jsonl")
    legacy = Path("data/pool-hard-gym-alt-n40.jsonl")
    path = pool if pool.exists() else legacy
    if not path.exists():
        pytest.skip("no gym_alt pool on disk")
    report = _build_report(pool_path=path)
    predictor = report["preflight_geometry_predictor"]
    assert predictor["valid"] is False
    assert "seed-16" in predictor["reason"] or "Smith seeds" in predictor["reason"]


def test_gym_alt_preflight_blocks_missing_pool(tmp_path):
    report = _build_report(pool_path=tmp_path / "missing.jsonl")
    assert report["paid_gold_justified"] is False
    assert any("missing pool" in b for b in report["blockers"])


def test_gym_alt_preflight_excludes_gym_alt_seed1():
    assert "data/gold-sparse-hard-probe-gym-alt-seed1.jsonl" in mod.DEFAULT_EXCLUDE


def test_gym_alt_preflight_json_roundtrip():
    pool = Path("data/pool-hard-gym-alt-seed2-n40.jsonl")
    legacy = Path("data/pool-hard-gym-alt-n40.jsonl")
    path = pool if pool.exists() else legacy
    if not path.exists():
        pytest.skip("no gym_alt pool on disk")
    report = _build_report(pool_path=path)
    parsed = json.loads(json.dumps(report))
    assert parsed["histogram"]["n"] >= 32
    assert "trait_deltas_vs_mix1" in parsed
    assert "projected_winner_mix" in parsed
