# scorer-pioneer-lift progress

Started: 2026-08-14
Spec: `.scratch/scorer-pioneer-lift/spec.md`

## Tasks

- Task 1: complete (commits `0911e86` + `4f65b69`, review clean)
  Minors (defer to whole-branch review): AUC imputes 0.5 for unscored ids; Brier drops fallback hops; ECE type-only on fixture; production-floor helper opt-in/conflated; oracle no-pick cost 0; dead hint_bin / double score; try/return vs pytest.raises; `gold_is_holdout` is a constant flag
- Task 2: complete (commits `0911e86..a2adc15` = `436a8bb` + `a2adc15`, review clean)
  Minors (defer to whole-branch review): `featurize` hint_bin name; bias+intercept double-count; feature-index tests; incomplete `calibrator` alias overrides platt; bin head still truncates short `bin_weights`
- Task 3: complete (commits `59aa821` + `1d30631`, review clean)
  Minors (defer): relabel/salvage CLI; GLM reasoning_effort; teacher field on escalate; budget TOCTOU

## Whole-branch

- Task 1: complete (commits `0911e86` + `4f65b69`, review clean)
- Task 2: complete (commits `436a8bb` + `a2adc15`, review clean)
- Task 3: complete (commits `59aa821` + `1d30631`, review clean)
- Spec review: merge-blocking GLM teacher effort, gate vs always-cheapest, AUC 0.5 impute. Report: `whole-branch-spec.md`
- Whole-branch must-fix `8bb2677` re-review clean (GLM effort, gate vs always-cheapest, AUC skip-unscored)
- Finishing: in-scope green after `8bb2677`; **7** `test_gateway.py` `x-router-reason` failures remain.
- Decision: `x-router-reason` is **not** part of the Pioneer-shaped trained contract. Reverted restore (`26718d5` → `1e734c7`). Those 7 gateway failures are **accepted as out of scope** for this spec. See `gateway-reason-dropped.md`.

## Issues (ready-for-agent tickets)

- Issue 01: complete (commits `9c53098`..`5be80c9`, review clean)
  Minors (defer to whole-branch): `--eval` missing-path silent empty collisions; post-filter `sample_stratum` can omit surviving smith when extra fills n; independent margins not joint cells / no occupied floor ≥20; heuristic `hint_bin`; soft tools assert; O(n²) `sample_stratum`; argparse-optional `--smith`/`--eval` (runtime-required)
  ⚠️ dump shapes / `--smith` traj-type: operator-runtime, not a code gap in this ticket
- Issue 02: complete (commits `ab06f39`..`3502973`, review clean)
  Minors (defer): tools stub is a single `read` with empty parameters; no lock that non-`needs_tools` omits tools / that `needs_tools`+`tool_calls` is success; schema does not enforce type/properties; sparse tests assert superset not exact cell set; covering 1 Starlette/httpx warning
- Issue 03: complete (commits `2cc87f5`..`8e12417`, review clean)
  Minors (defer): empty `--exclude` JSONL samples full pool; fit does not refuse overlapping `--gold`/`--cal` files; missing `--cal` path silent fallthrough; `n_cal` overstates when new-ids onboard-only; pooled `p_success` for ids in both splits; dense tag dict duplication; exclude matches `prompt` only; covering 1 warning
  ⚠️ issue-02 y in unchanged `_gold_label`: verified via issue 02 review
- Issue 04: complete (commit `15e629b`, review clean)
  Minors (defer): omit is `if intercepts and i not in intercepts` (weights-only legacy scores ic=0); fit+score omit test would pass without the serve change; hop test does not assert trained-would omits silver-only ids; cal-only table P not Platt; silver second-order Platt a,b via weights; fit JSONL `hint_bin` vs serve predicted bin
  ⚠️ teacher Motif→GLM / parse-fail / opt-in / budget 15: existing `test_train.py` seams present
- Issue 05: complete (commit `40a64cd`, review clean)
  Minors (defer): missing `always_cheapest` key falls back to `always_flash`; cheapest bar compares aggregates not per-prompt picks; no fixture where Flash ≠ cheapest on the integration path; CLI test skips `assert_not_production_floors`; inclusive bar boundaries unpinned; test `POLICIES` omits `always_cheapest`; `gold_is_holdout` constant
  ⚠️ Task-1 report metrics: unchanged replay CLI; verified via Task 1 + this gate delta. 7 `test_gateway.py` `x-router-reason` failures remain out of scope
- Issue 06: complete (commit `cb7a9bf`, review clean — GBDT + post-hoc Platt after operator gate **fail**; replay re-run still fail; shadow + `not_spec_floors`)
  Evidence: `operator-replay-run.md`. Report: `task-06-or-07-report.md`.
  Logistic holdout: AUC 0.295, P-spread 0.188, Brier skill −0.317, ECE 0.154/0.182, trained success ok, cost delta +4.7e-5, ≠ cheapest. After `--gbdt` on sparse-400/dense-100: AUC 0.261, P-spread 0.388, Brier skill −3.80, ECE 0.525, cost delta 0, trained = cheapest. Rec B / live embed closed. 07 not taken.
  **Post-lift diagnosis (NEEDS_CONTEXT):** `gate-fail-diagnosis.md` — gate cannot pass on verified holdout (AUC ceiling ≤0.60 without verified leak; cost_delta&lt;0 impossible). GBDT collapse: length stumps dead on short verified prompts.
  Minors (defer): duplicated `score_eligible` GBDT/logistic branches; fit imports private `_gbdt_z`; GBDT artifacts still write empty `weights: {}`; `load_scorer` does not treat `gbdt` as a load key
- Issue 07: needs-info — **still not taken** after gate-fail diagnosis. Operator gate cannot pass on `data/gold-verified.jsonl` with current sparse/dense labels (AUC ceiling without verified leak ≤0.60; `rules_cost_delta < 0` impossible because rules≡Flash≡cheapest on 89/89). Report: `gate-fail-diagnosis.md`. Hypotheses: `gate-fail-hypotheses.md`.
- Issue 08: complete — unpaid geometry lock. Report: `task-08-plus-report.md`.
- Issue 09: complete — verified-like train/cal pool (`--verified-like`). Same report.
- Issue 10: complete — dual shadow eval (`--cost-gold`). Same report.
- Issue 11: complete — prefer logistic until Spearman > 0. Same report.
- Issue 12: needs-info — paid hard-y probe; recipe in ticket. No invented gold cells.

## Whole-branch (issues 01–06)

- Spec + quality review: **merge-ready** (`1e734c7..cb7a9bf`). Report: `whole-issues-review.md`
- Must-fix before merge: **none**
- Issue 07 correctly not taken (operator gate still fails after GBDT)
- Out of scope: 7 `test_gateway.py` `x-router-reason` failures
- Deferred minors: all can stay (operator footguns / quality nits; see review triage)

## Next path

- Decision: `.scratch/scorer-pioneer-lift/next-path-decision.md` — **Option A** (verified-like train/cal gold + dual shadow eval). Not bar-rewrite, not more easy n, not leak/flip.
- Goal is transfer ranking + hard-cal P(success) + a slice where rules ≠ Flash so cost_delta is real; frozen `gold-verified.jsonl` stays eval-only. Restore logistic until labels transfer; do not serve length-stump GBDT.
- Issue 07 still not taken. Legitimate only after AUC ≥ 0.65 / BSS>0 / ECE on an unused hard holdout **and** a real cost comparison (or an explicit H3 waiver). No `TRAINED_PATH` flip, no fake pass.
- Issue 08: complete — unpaid geometry lock (`python -m aiand_router.geometry`). Spearman/kill/prefer_logistic. Eval not fit y.
- Issue 09: complete — `pool --verified-like` short hard-check train/cal pool, collision-filter vs `--eval`. Not Verified as fit.
- Issue 10: complete — `replay_report --cost-gold` dual eval; `rules_ne_cheapest_rate`; gate still from `--gold`; no fake pass.
- Issue 11: complete — logistic default; GBDT replay note + `--gbdt` help; operator recipe uses `data/scorer-logistic.json` until Spearman > 0.
- Issue 12: needs-info — paid hard-y probe. Recipe in the ticket. Do not invent gold cells. Kill if Spearman still < 0.
- Report: `.scratch/scorer-pioneer-lift/task-08-plus-report.md`
