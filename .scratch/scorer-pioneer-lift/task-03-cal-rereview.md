### Spec Compliance
- ✅ Confirmed gap closed: `--exclude` runs **before** `sample_stratum`. `_read_queries` filters the pool, then samples leftover. Same-pool recipe (sparse `--limit 3`, dense `--exclude` sparse `--limit 2`) is nonempty and disjoint — `test_dense_exclude_before_sample_same_pool_is_nonempty_and_disjoint`. Reported RED was `cells=0` on sample-then-exclude.
- ✅ Confirmed gap closed: `--dense` without `--exclude` returns 2 and writes nothing — `test_dense_requires_exclude`. In-sample Platt from overlapping same-pool dense is no longer the default CLI path.
- ✅ Confirmed gap closed: leftover-empty after `--dense --exclude` returns 2 and does not create `--out` — `test_dense_exclude_empty_leftover_fails_closed`.
- ✅ Confirmed gap closed: `n_train == 0` skips intercepts/weights. Cal-only Gemma plus silver `p_success` 0.9 stays out of `weights` / `intercepts`; onboard is cal gold `p_success` 1.0 — `test_fit_cal_only_id_with_silver_gets_no_weights`.
- ✅ Dense gold runs every enabled catalog id except K3 (`_gold_ids(..., dense=True)` + tools filter). JSONL marks `dense: true` on 429 and observed paths. Locks: `test_dense_gold_runs_every_eligible_id_except_k3`, `test_dense_gold_excludes_k3`.
- ✅ Missing cells stay missing: 429 / budget skip (`_complete` status 429) write `unobserved: True` with no `success`. Ineligible ids are never jobs.
- ✅ Slice unused for train weights: `--cal` and concatenated `dense: true` feed Platt / new-id `p_success` only; intercepts from sparse train (`_logit(1.0)` lock). Prompt-tail 20% remains only when neither `--cal` nor dense tags are present. Artifact still `not_spec_floors`.
- ✅ Same y seam as issue 02: observed cells still call `_gold_label` (not in this delta). Dump `resolved` is not written on gold rows here.
- ✅ Live gold opt-in (`AIAND_TRAIN`), cache-first `_complete`, code default `BUDGET_LIMIT_USD` `"15"` — unchanged. New tests use FakeProvider. No `TRAINED_PATH` flip, Pioneer dashboard, live embed, Rec B, or K3 cells.
- ⚠️ Issue-02 y semantics still live in unchanged `_gold_label` / `_gold_body`. Cannot re-verify from this delta; dense only reuses the call.
- ⚠️ Reported covering run: `35 passed, 1 warning in 3.66s`. Implementer attributes the warning to Starlette/`httpx` TestClient deprecation, not this delta. This re-review did not re-run the suite.

### Strengths
- The three first-review blockers are local patches on the named seams: exclude-then-sample in `_read_queries`, `--dense` refuse + empty-leftover refuse in `main`, `n_train == 0` in the intercept loop. Pool, hop, replay, and issue-02 y were left alone.
- TDD matches the gaps (RED: empty same-pool dense; RED: empty leftover exit 0; RED: `--dense` without `--exclude`; RED: Gemma in `weights` from silver). Covering tests go through Train CLI + FakeProvider and assert JSONL prompts, catalog ids, and artifact `weights` / `p_success` / `not_spec_floors`.
- Explicit `--cal` still uses the entire sparse file for train weights (no accidental 20% tail steal). Concatenated `dense: true` still beats prompt-tail sort order.
- Report Fix section matches the diff; minors were explicitly left untouched.

### Issues
#### Critical
None.

#### Important
None. The first-review Critical (sample-then-exclude empties the same-pool slice) and Importants (optional `--exclude`; cal-only ids taking silver weights) are fixed in this head.

#### Minor
- `--dense --exclude` with an empty JSONL is allowed and then samples the full pool (K3 tests rely on this). Fit still does not refuse overlapping `--gold` / `--cal` prompt sets, so a same-file `--cal` or an empty exclude plus two runs of one pool can still put Platt in-sample.
- `--cal` path that does not exist (`cal_path.exists()` is false) or is all-unobserved still silently falls through to tags / prompt-tail (first-review minor, unchanged).
- `n_cal` counts all `cal_gold` rows; Platt skips ids with no weights, so `n_cal` overstates calibrator n when new-ids are onboard-only (unchanged).
- `p_success` for ids in both splits is the pooled train+cal rate, not cal-only (serve uses weights for those ids; table is fallback; unchanged).
- 429 vs success row dicts still duplicated only to set `dense`. Exclude matching builds `blocked` from `r.get("prompt")` only — a queries file with `messages` and no `prompt` would not block; `_read_queries` compares `_prompt_of(_messages(q))`. The documented recipe excludes sparse **gold** JSONL, which has `prompt`.
- Covering output includes 1 warning. Not explained by this diff’s imports; treat as noise unless a later train-test run shows it is new.

### Assessment
**Task quality:** Approved
**Reasoning:** The operator path that is supposed to produce a held-out dense slice now excludes before sampling, refuses `--dense` without `--exclude`, fails closed on empty leftover, and will not fit silver weights for cal-only ids. Remaining notes are the untouched first-review polish plus an empty-exclude hatch, not reopeners.
