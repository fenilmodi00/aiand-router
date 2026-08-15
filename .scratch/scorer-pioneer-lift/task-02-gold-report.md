# Task 02 report: Sparse success-gold run

**Status:** DONE_WITH_CONCERNS  
**Commit:** `ab06f39` — Run sparse success gold so y is gateway-measurable, not dump resolved or nonempty text.

Owned files: `src/aiand_router/train.py`, `tests/test_train.py`. Did not rewrite pool, replay, scorer fit, or hop. Did not re-implement issue 01. Did not flip `TRAINED_PATH`. Artifact still `not_spec_floors` (fit untouched). Code default `BUDGET_LIMIT_USD` stays **15**.

## What shipped

Task 3 already had the gold runner (opt-in, cache-first `_complete`, K3 skip, budget-429 unobserved, expected/pytest before tool_calls, `success` / `success_tier`). Issue 02 filled these gaps:

1. **Eligible sparse anchors only.** `_gold_ids` runs Flash + measured trio when enabled and (if `needs_tools`) `supports_tools`. Disabled / no-tools anchors are not gold cells. K3 never. Dense still = enabled catalog except K3, with the same tools filter.
2. **JSON/schema verified metadata** on the query (`json_schema` or `schema`) is checked before the tool-call proxy. Invalid JSON or missing `required` keys → `success=False`, `success_tier=verified`.
3. **Locks** for ticket seams that already worked: cache-first rerun, upstream 429 unobserved, dump `resolved` is not y, budget default 15, concurrency cap (`TRAIN_CONCURRENCY=2` → max in-flight ≤ 2), operator JSONL has `success` / `success_tier` and never `resolved`/`y`.

Gold still consumes issue-01 pool rows (`prompt`, `phase`, `hint_bin`, `needs_tools`, `source`).

## TDD

### RED → GREEN 1 — JSON/schema beats tool-call proxy

```
python -m pytest tests/test_train.py::test_gold_json_schema_beats_tool_calls_proxy -q --tb=short
```

**RED:** `assert (True is False)` — `_gold_label` returned proxy success because `tool_calls` ran before schema.

**GREEN:** schema parse + `required` keys before `tool_calls`. Test passed.

### RED → GREEN 2 — skip ineligible sparse anchors

```
python -m pytest tests/test_train.py::test_gold_sparse_skips_ineligible_anchors -q --tb=short
```

**RED:** `assert 'moonshotai/kimi-k2.7-code' not in called` failed — Kimi ran even with `supports_tools: false` on a `needs_tools` pool row.

**GREEN:** `_gold_ids` skips that anchor; Flash / Qwen / Pro still run; K3 does not. Test passed.

### Locks (already green; no production change)

| Test | Seam |
|------|------|
| `test_gold_is_cache_first` | second gold run: no new spend, no new provider calls |
| `test_gold_upstream_429_is_unobserved_not_failure` | provider 429 → `unobserved`, no `success` |
| `test_gold_budget_skip_is_unobserved_not_failure` | pre-call budget skip (existing) |
| `test_gold_dump_resolved_is_not_y` | pool row `resolved: true` + empty completion → `success=False`, no `resolved`/`y` on gold |
| `test_gold_budget_code_default_stays_15` | unset `BUDGET_LIMIT_USD` → SpendLog limit 15 |
| `test_gold_runs_cells_concurrently` | `TRAIN_CONCURRENCY=2` → `1 < max_in_flight <= 2` |
| `test_gold_refuses_without_opt_in` | no `AIAND_TRAIN` → exit 2, zero calls |
| `test_gold_sparse_skips_k3_and_fit_writes_not_spec_floors` | all `SPARSE_ANCHORS` in JSONL with `success` / `success_tier` |

Query-level dump `tests_passed` stays **not** y (`test_gold_query_level_tests_passed_is_not_y`). Per-completion pytest (`verify_pytest`) remains the tests_passed path and still runs before tool_calls.

## Tests

```
tests/test_train.py     25 passed
full suite              142 passed, 7 failed
```

The 7 failures are `tests/test_gateway.py` `KeyError: 'x-router-reason'` — out of scope (`gateway-reason-dropped.md`).

## Concerns

1. JSON/schema check is stdlib `json.loads` + `required` keys, not a JSON Schema library (no new deps).
2. Query-level boolean `tests_passed` is still ignored so a dump cannot stamp the same y on every model. Flashlight-style tests use `verify_pytest`.
3. “Eligible” here is hard constraints (enabled + tools), not phase AA bars — those would drop Qwen (AA 38) from most coding phases.
4. Gold body still does not attach a tools array when `needs_tools` is true (pool rows only carry the flag). Tool-valid y then depends on the model emitting `tool_calls` unprompted, or on verified metadata.

Skipped: Pioneer dashboard, live embed, Rec B, fit/replay/hop edits, K3 gold, automatic `TRAINED_PATH=trained`.

## Fix — tool-required gold y (spec gap)

Controller-confirmed miss on unchanged Task 3 gold: `_gold_body` had no `tools` when `needs_tools`; `_gold_label` weak-True on nonempty text without `tool_calls`. Query-level `tests_passed` still not y; JSON/schema still stdlib; eligible still hard constraints.

### TDD RED → GREEN 1 — tools array on needs_tools request

```
python -m pytest tests/test_train.py::test_gold_needs_tools_sends_tools_array -q --tb=short
```

**RED:** `assert all(... c.get("tools") ...)` failed — gold body had no `tools`.

**GREEN:** `_gold_body(..., needs_tools=True)` attaches a one-function tools array. Test passed.

### TDD RED → GREEN 2 — missing tool_calls is not success

```
python -m pytest tests/test_train.py::test_gold_needs_tools_without_tool_calls_is_not_success -q --tb=short
```

**RED:** `assert all(r.get("success") is False ...)` failed — FakeProvider `_ok()` nonempty text labeled weak-True.

**GREEN:** after verified metadata, `needs_tools` and no `tool_calls` → `success=False` (observed, not unobserved). Test passed.

Verified expected / schema / `tests_passed`-is-not-y stayed green.

### Covering

```
python -m pytest tests/test_train.py -q --tb=short
```

```
...........................                                              [100%]
27 passed, 1 warning in 2.61s
```

Warning is existing Starlette/`httpx` TestClient deprecation, not this diff. Concern 4 (no tools array / weak-True on tool-required text) is closed. Did not implement 03–07; did not change Minors.
