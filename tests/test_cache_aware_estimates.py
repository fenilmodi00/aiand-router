"""Turn-aware cache pricing estimates (Fireworks lesson).

Single-turn hops price input at list `input_per_1m`; multi-turn hops keep the
cached-in preference when the catalog provides it. `est_cache_aware` records
whether cached-in pricing was applied in the routing estimate. Post-response
`cost_usd` billing is untouched (actual list-price accounting).
"""

from __future__ import annotations

import yaml

from aiand_router.app import _jsonl_row
from aiand_router.router import estimate_cost, load_models, select_model

# Model A wins on list price; model B wins once cached-in applies.
CFG = """
fallback_model: test/a
max_regret: 0
phase_threshold: {summarize: 0}
models:
  - id: test/a
    enabled: true
    input_per_1m: 1.00
    cached_input_per_1m: 0.90
    output_per_1m: 1.00
    context_window: 1048576
    supports_tools: true
    supports_json: true
    supports_streaming: true
    max_output_tokens: 16384
    aa_index: 50
    aa_source: test
    measured_on: test
  - id: test/b
    enabled: true
    input_per_1m: 1.10
    cached_input_per_1m: 0.10
    output_per_1m: 1.00
    context_window: 1048576
    supports_tools: true
    supports_json: true
    supports_streaming: true
    max_output_tokens: 16384
    aa_index: 50
    aa_source: test
    measured_on: test
"""


def _model(model_id: str):
    cfg = yaml.safe_load(CFG)
    return {m.id: m for m in load_models(cfg)}[model_id]


def _pick(effort: str, *, multi_turn: bool):
    cfg = yaml.safe_load(CFG)
    models = load_models(cfg)
    return select_model(
        cfg,
        models,
        phase="summarize",
        needs_tools=False,
        tokens=1000,
        effort=effort,
        allowed=None,
        spend_usd=0.0,
        budget_usd=15.0,
        multi_turn=multi_turn,
    )


def test_estimate_cost_defaults_to_cached_preference():
    """Characterization: legacy callers keep cached-in pricing unchanged."""
    a = _model("test/a")
    assert estimate_cost(a, 1_000_000, 1_000_000) == 0.90 + 1.00


def test_single_turn_pays_list_price_multi_turn_uses_cached():
    b = _model("test/b")
    assert estimate_cost(b, 1_000_000, 0, multi_turn=False) == 1.10
    assert estimate_cost(b, 1_000_000, 0, multi_turn=True) == 0.10


def test_low_effort_flip_between_turn_counts():
    single = _pick("low", multi_turn=False)
    multi = _pick("low", multi_turn=True)
    assert single.model.id == "test/a"
    assert multi.model.id == "test/b"


def test_medium_effort_pioneer_cost_term_flips():
    assert _pick("medium", multi_turn=False).model.id == "test/a"
    assert _pick("medium", multi_turn=True).model.id == "test/b"


def test_jsonl_row_carries_est_cache_aware():
    row_single = _jsonl_row(_pick("low", multi_turn=False), requested="router/auto")
    row_multi = _jsonl_row(_pick("low", multi_turn=True), requested="router/auto")
    assert row_single["est_cache_aware"] is False
    assert row_multi["est_cache_aware"] is True
