### Spec Compliance
- ✅ Dense gold runs every enabled catalog id except K3: `_gold_ids(..., dense=True)` lists `models_by_id` enabled ids with `id != K3`, then the same tools filter as sparse (`needs_tools` and not `supports_tools` → omit, not `success=0`). `test_dense_gold_runs_every_eligible_id_except_k3` locks JSONL `dense: true`, `models == eligible`, and K3 absent from rows and `provider.calls`.
- ✅ No K3 gold cells (list-comp + loop; existing `test_dense_gold_excludes_k3` still asserts Gemma in / K3 out).
- ✅ Missing cells stay missing: 429 / budget skip (`_complete` returns status 429) write `unobserved: True` with no `success` field; ineligible ids are never jobs. Dense tagging is applied on that 429 path too.
- ✅ Slice unused for train weights on the `--cal` / `dense: true` seams: intercepts and `_fit_binary_intercept` iterate `train_gold` only; Platt uses `cal_gold`; cal-only ids (Gemma in the lock) get artifact `p_success` and stay out of `weights` / `intercepts` when silver is absent. `not_spec_floors` remains True. Prompt-tail 20% remains only when neither `--cal` nor dense tags are present.
- ✅ Same y seam as issue 02: observed cells still call `_gold_label` (unchanged in this delta). Dump `resolved` is not written on gold rows here.
- ✅ Live gold opt-in (`AIAND_TRAIN`), cache-first `_complete`, code default `BUDGET_LIMIT_USD` `"15"` — unchanged. New tests use FakeProvider (no spend). Artifact not flipped to Verified; `TRAINED_PATH` untouched. No Pioneer dashboard, live embed, Rec B, or K3 cells.
- ⚠️ Issue-02 y semantics (verified metadata first; `needs_tools` + missing `tool_calls` is observed fail; dump `resolved` / query-level `tests_passed` not y) live in unchanged `_gold_label` / `_gold_body`. Cannot re-verify from this delta; dense only reuses the call.
- ❌ Slice is **not** disjoint from sparse train prompts unless the operator passes `--exclude` **and** the leftover after limit is non-empty. The report’s same-pool recipe (`gold` sparse default 400, then `gold --dense --exclude sparse.jsonl` default 100) samples **then** excludes. `sample_stratum(..., seed=0)` makes the dense 100 the prefix of the sparse 400, so `--exclude` drops every dense query and the held-out slice is empty. Platt then hits `len(zs) < 2` → identity `(1.0, 0.0)` and new-id `p_success` is missing. The exclude test uses two hand-written prompts under default limit 100, so it never sees this.

Reported `tests/test_train.py` 31 passed; 7 `test_gateway.py` `x-router-reason` failures treated as out of scope. No focused re-run.

### Strengths
- Small, on-ticket delta: dense JSONL tag, `--exclude`, `fit --cal` / concatenated `dense: true` split. Did not rewrite pool, hop, replay, or issue-02 y.
- Operator-visible locks: catalog completeness vs live `models.yaml`, `dense: true` on cells, `--exclude` prompt set, Flash intercept `_logit(1.0)` from sparse-only, Gemma onboard via `p_success` not weights, concatenated tags beat prompt-tail sort order, `not_spec_floors`.
- Explicit `--cal` uses the **entire** sparse file for train weights (no accidental 20% tail steal) and the cal file for Platt — the right split when the slice is actually populated.
- Honest report concerns on operator-owned `--exclude`, p_success-table onboard, teachers as dense cells, and prompt-tail fallback. The empty-recipe failure was not among them.

### Issues
#### Critical
- **`--exclude` after `_read_queries(limit)` empties the documented dense slice.** `main` takes `DENSE_LIMIT=100` / `SPARSE_LIMIT=400`, stratum-samples with seed 0, then drops prompts in `--exclude`. Same pool + same seed ⇒ dense sample ⊂ sparse sample ⇒ zero queries after exclude. Ticket requirement “slice is disjoint from train sparse gold rows” and “Platt / new-id have measured cells” fail on the recipe the implementer published. Fix: exclude (or hold out) **before** sampling, and fail closed if `--dense --exclude` leaves nothing.

#### Important
- **Disjointness is optional.** Without `--exclude`, same prompts can sit in sparse `--gold` and dense `--cal`. Fit will not use `--cal` rows as train weights, but Flash/trio Platt is then in-sample on those prompts — the failure mode user story 30 exists to prevent. `--exclude` should be required for `--dense`, or fit should refuse overlapping prompt sets.
- **Cal-only ids enter `gold_ids` via `observed = train_gold + cal_gold`.** With `--silver`, the pre-existing silver loop can fill `by_model_x` for those ids (`train_counts==0` → intercept `_logit(0.5)`, weights from silver only). That contradicts this ticket’s “new-id onboard is `p_success`, not weights” and “never … on silver.” This ticket’s recipe omits silver; issue 04 will hit the hole. Guard: skip intercept/weight fit unless `train_counts[mid] > 0`.

#### Minor
- `--cal` path that does not exist (`cal_path.exists()` is false) silently falls through to tags / prompt-tail.
- `n_cal` counts all `cal_gold` rows; Platt skips ids with no weights, so `n_cal` overstates calibrator n when new-ids are onboard-only.
- `p_success` for ids that appear in both splits is the pooled train+cal rate, not cal-only (serve uses weights for those ids; table is fallback).
- 429 vs success row dicts duplicated only to set `dense`. Exclude matching is `r.get("prompt")` only — a queries file with `messages` and no `prompt` would not block. Test docstring mojibake (`ΓÇö`).

### Assessment
**Task quality:** Needs fixes
**Reasoning:** The fit/tag/K3 seams match the ticket when the cal file is hand-built, but the operator path that is supposed to produce a held-out dense slice (`--dense --exclude` on the same pool, default limits) yields no cells, so Platt and new-id onboard have nothing to measure.
