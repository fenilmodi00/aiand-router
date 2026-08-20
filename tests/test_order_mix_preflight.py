"""Unpaid order-mix preflight helper tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "order_mix_preflight.py"
SPEC = importlib.util.spec_from_file_location("order_mix_preflight", SCRIPT_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def _build_report(**overrides):
    defaults = dict(
        from_pool=Path("data/pool-hard-mix-mix1like.jsonl"),
        mix1=Path("data/gold-sparse-hard-mix1.jsonl"),
        mix1_pool=Path("data/pool-hard-mix-near_miss_seed11.jsonl"),
        pool_path=Path("data/pool-hard-mix-order-conservative.jsonl"),
        reservoir_path=Path("data/pool-hard-mix-order-conservative-reservoir.jsonl"),
        spend_path=Path("data/spend.txt"),
        budget_cap_usd=15.0,
        seed=16,
        limit=32,
        tolerance_pp=0.10,
        exclude_paths=list(mod.DEFAULT_EXCLUDE),
        write_pool_flag=False,
    )
    defaults.update(overrides)
    return mod.build_report(**defaults)


def test_order_mix_preflight_geometry_predictor_disproven_after_seed16():
    """Class fractions can pass while standalone geometry still fails (seed-16)."""
    report = _build_report()
    assert report["sample_n"] == 32
    assert report["paid_gold_justified"] is True
    predictor = report["preflight_geometry_predictor"]
    assert predictor["valid"] is False
    assert "seed-16" in predictor["reason"]


def test_order_mix_preflight_json_roundtrip():
    report = _build_report()
    blob = json.dumps(report)
    parsed = json.loads(blob)
    assert "dry_run" in parsed
    assert parsed["class_fraction_gate_pass"] is True
    assert parsed["preflight_geometry_predictor"]["valid"] is False
