### Spec Compliance
- ✅ Sparse gold runs Flash + measured trio when eligible: `_gold_ids` starts from `SPARSE_ANCHORS`, then keeps only catalog ids that exist, are enabled, are not K3, and (if `q["needs_tools"]`) `supports_tools`. Default `config/models.yaml` has all four anchors enabled with tools, so a tool-stratum pool row still runs the trio.
- ✅ K3 is never a gold cell (filter in `_gold_ids`; existing `test_gold_sparse_skips_k3_and_fit_writes_not_spec_floors` still asserts it).
- ✅ Ineligible anchors are omitted from jobs (missing, not `success=0`). Budget skip and provider 429 stay `unobserved` without `success` — runner unchanged; this diff adds locks (`test_gold_upstream_429_is_unobserved_not_failure`, existing budget-skip test).
- ✅ Verified JSON/schema on the query runs before the `tool_calls` proxy: invalid JSON → `success=False`, `success_tier=verified` (`test_gold_json_schema_beats_tool_calls_proxy`). `expected` and `verify_pytest` still precede schema (unchanged order).
- ✅ Operator gold JSONL has `success` / `success_tier`; lock also forbids `resolved` / `y` on the k3/floors test.
- ✅ Paid calls cache-first (`_complete` cache hit before spend/provider — unchanged); `test_gold_is_cache_first` locks a second gold run: no new calls, no new spend.
- ✅ Live gold opt-in via `AIAND_TRAIN` — unchanged `test_gold_refuses_without_opt_in`.
- ✅ Code default `BUDGET_LIMIT_USD` stays 15 (`main` `getenv(..., "15")` unchanged; `test_gold_budget_code_default_stays_15` captures `SpendLog` limit with env unset).
- ✅ Concurrent within cap: `Semaphore(_concurrency())` unchanged; test now sets `TRAIN_CONCURRENCY=2` and asserts `1 < max_in_flight <= 2`.
- ✅ Dump `resolved` is not y: pool row `resolved: true` + empty completion → observed `success=False`, no `resolved`/`y` on gold rows.
- ✅ Did not flip `TRAINED_PATH`, did not stamp Verified, did not change Rec A / serve / fit (floors lock still `not_spec_floors`). No Pioneer dashboard, embed, Rec B, K3 cells, or savings %.
- ⚠️ JSON/schema “validity” in this diff is `json.loads` + top-level `required` keys, not a schema library (report concern 1). Empty/`required`-less or non-dict schema → any parseable JSON is verified success.
- ⚠️ `tests_passed`: query-level boolean is still ignored (`test_gold_query_level_tests_passed_is_not_y`). Flashlight path is unchanged `meta["verify_pytest"]`. Aligns with “dump field is not y”; controller should confirm that `verify_pytest` is the intended `tests_passed` seam.
- ⚠️ Cannot verify from this delta (unchanged Task 3 gold): `_gold_body` still has no `tools` array when `needs_tools`; `_gold_label` does not fail tool-required rows that return nonempty text without `tool_calls` (weak success). “No escalate” is not a gold-cell check (teacher-only). `finish_reason=length` + empty content remains failure in unchanged `_gold_label`.

Reported `tests/test_train.py` 25 passed; 7 `test_gateway.py` `x-router-reason` failures treated as out of scope. No warnings were included in the implementer output.

### Strengths
- The issue-02 gap is a small, honest delta: eligibility extracted into `_gold_ids` (sparse and dense share hard constraints), plus one verified-metadata rung. No pool/fit/replay/hop rewrite.
- TDD matches the two new seams (schema beats `tool_calls`; ineligible Kimi skipped on a `needs_tools` row). Locks for cache-first, 429, dump `resolved`, budget 15, and concurrency are operator-visible JSONL / CLI / spend — not sklearn internals.
- Default catalog check: Flash and the measured trio stay eligible on tool rows, so the filter does not silently shrink sparse gold in production yaml.

### Issues
#### Critical
None.

#### Important
None in this delta. Controller follow-ups (unchanged gold y): whether tool-stratum success should require `tool_calls` / a tools array on the gold body, and whether flashlight `verify_pytest` is the full `tests_passed` story.

#### Minor
- Schema check does not enforce `type` / `properties`. No unit test for valid JSON, missing `required` keys, or the `schema` alias — only invalid JSON + `tool_calls`.
- Sparse tests assert a superset (`models >= set(SPARSE_ANCHORS)`, named ids in `called`) and “K3 / ineligible Kimi absent,” not that the cell set equals the eligible sparse anchors. Accidental dense expansion except K3 would still pass.
- `_gold_ids` dense path filters K3 twice (list comp then loop). Harmless.

### Assessment
**Task quality:** Approved
**Reasoning:** The issue-02 delta does what the ticket asked: eligible Flash + trio cells, JSON/schema before the tool-call proxy, and observable locks for cache, 429, dump `resolved`, budget 15, opt-in, and concurrency. Remaining gold-y holes sit in unchanged Task 3 code and should be checked there, not used to reopen this task.
