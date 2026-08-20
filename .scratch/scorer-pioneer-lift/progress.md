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
- Issue 12: complete — paid hard-y probe. Spearman 0.0, y_rate 0.0 (27 observed / 88), `kill_spearman` false. **Fail-pass / do not scale.** Issue 07 not taken. Reports: `issue-12-probe-run.md`, `task-12-probe-report.md`.

## Whole-branch (issues 01–06)

- Spec + quality review: **merge-ready** (`1e734c7..cb7a9bf`). Report: `whole-issues-review.md`
- Must-fix before merge: **none**
- Issue 07 correctly not taken (operator gate still fails after GBDT)
- Out of scope: 7 `test_gateway.py` `x-router-reason` failures
- Deferred minors: all can stay (operator footguns / quality nits; see review triage)

## Next path

- Next cycle spec: `.scratch/scorer-hard-transfer/spec.md` (ready-for-agent; real credits OK).
- Decision: `.scratch/scorer-pioneer-lift/next-path-decision.md` — **Option A** (verified-like train/cal gold + dual shadow eval). Not bar-rewrite, not more easy n, not leak/flip.
- Goal is transfer ranking + hard-cal P(success) + a slice where rules ≠ Flash so cost_delta is real; frozen `gold-verified.jsonl` stays eval-only. Restore logistic until labels transfer; do not serve length-stump GBDT.
- Issue 07 still not taken. Legitimate only after AUC ≥ 0.65 / BSS>0 / ECE on an unused hard holdout **and** a real cost comparison (or an explicit H3 waiver). No `TRAINED_PATH` flip, no fake pass.
- Issue 08: complete (`c3732e8`..`c0b0e0a`, review clean) — unpaid geometry lock (`python -m aiand_router.geometry`). Spearman/kill/prefer_logistic until rho > 0. Eval not fit y.
- Issue 09: complete (same range, review clean) — `pool --verified-like`; no fake `status` schema; trivial→hard remap; collision-filter vs `--eval`. Not Verified as fit.
- Issue 10: complete (same range, review clean) — `replay_report --cost-gold` dual eval; `rules_ne_cheapest_rate`; gate still from `--gold`; no fake pass.
- Issue 11: complete (same range, review clean) — logistic default; GBDT replay note + `--gbdt` help; prefer logistic until Spearman > 0.
- Issue 12: complete — hard-y probe ran (`datasets/train-queries.jsonl` as `--smith`; no HF SWE-smith dump). Spearman **0.0**, train y_rate **0.0**, `kill_spearman` false, `prefer_logistic` true. **Do not scale** (failed pass; not the ~0.39 easy-y kill). No dense/fit/`--cost-gold`. Issue 07 still not taken. Spend delta ≈ 0.023; 61/88 budget-unobserved (operator `.env` cap; code default 15 unchanged).
- Issue 13 / scale: **not taken**.
- **Mix1 hard-y (2026-08-20):** `data/gold-sparse-hard-mix1.jsonl` passes standalone geometry (Spearman 0.949, y 0.181, order true). `data/scorer-hard-logistic.json` passes frozen verified replay (`replay_gate_pass=true`) but **not** production parity (`rules_cost_delta>0`, n=89, `not_spec_floors`).
- **Seeds 11–16:** all fail standalone geometry. Seed-16 (order-conservative): unpaid class-quota preflight passed; paid geometry failed (y 0.047, 26/32 all-fail). **Preflight does not predict geometry.** Spend ~$14.48. Do not spend on order-conservative / kimi-only / winner-strat / mix1like pools.
- **Unpaid next (2026-08-20):** SWE-Gym `gym_alt` pool family wired; dry-run pools ready; ranking in `unpaid-next-path-2026-08-20.md`.
- **gym-alt-seed1 paid (2026-08-20):** preflight pass → n=32 gold → **standalone geometry pass** (Spearman 1.0, y 0.125, order true). Spend Δ +$0.557. Report: `gym-alt-preflight-2026-08-20.md`.
- **gym-alt merge refit (2026-08-20):** combined merge `mix1-train+gym-alt` n=240 geometry pass → refit `scorer-hard-logistic-gym-alt-merged.json` **replay fail** (P-spread 0.084 < 0.10; sole gate). Counterfactual full-Mix1+gym-alt refit also fails (BSS/ECE, trained≡Flash). Diagnosis: `gym-alt-merge-replay-diagnosis-2026-08-20.md`. Serve candidate unchanged.
- **gym-alt seed2 (2026-08-20):** order-mix sampling fix + winner-mix preflight gate. Pool: `data/pool-hard-gym-alt-seed2-n40.jsonl`. Offline projected ko **0.409** / af **0.505** → paid n=32 gold **failed standalone geometry** (y **0.023**, Spearman 0.816, `holdout_like_order=false`; **32/32 all-fail** actual vs 50% projected). Spend Δ +$0.399. **Winner-mix offline projection falsified** (same class as seed-16 preflight falsification). No merge/refit. Report: `gym-alt-seed2-preflight-2026-08-20.md`.
- **rules_cost_delta diagnosis (2026-08-20 unpaid):** ship overspend is systemic (72/89 hops Kimi vs rules Pro/Flash). Shadow overlay `threshold=0.15` clears rcd to **-0.000688** with gate still pass (AUC same; BSS ~flat; success 0.112→0.090). Artifacts: `config/models.cost-overlay-t015.yaml`, `data/scorer-hard-logistic-cost-overlay.json`. Serve candidate **unchanged**. Report: `rules-cost-delta-diagnosis-2026-08-20.md`.
- **Promotion readiness scaffolding (2026-08-20 unpaid):** `src/aiand_router/promotion_gate.py`, `scripts/run_promotion_readiness.py`, `lite_runner --promotion-readiness`. Report: `.scratch/scorer-pioneer-lift/promotion-readiness-2026-08-20.md`. Tests: `tests/test_promotion_gate.py` (9 passed).
- **Verified session runner (2026-08-20):** plumbing + **live smoke n=2** (`verified_session_smoke.jsonl`, rules-only pre-fix) + **batch n=10 dual-policy** (`data/verified_session_batch.jsonl`). Dual-policy fix: gateway `x-router-hop-path` header + counterfactual trained edit/debug pass (shadow gateway unchanged). Spend 15.444738→15.650197 (Δ +$0.205); rules 0/10, trained 0/10 resolve; `eval --gate` → `bounded_check_only`. Tests: `test_verified_runner.py` (9), `test_trained_hop.py` (hop-path override).
- **Verified instance context + honest resolve (2026-08-20 unpaid):** diagnosed 0/10 as empty flashlight context + `_pytest_verify` without tests (fake fails + false `session_gold`). Wired instance dump/HF load, problem_statement/FAIL_TO_PASS context, `needs_swe_eval`/`harness_proxy`/`offline_gold`/`SWE_EVAL_CMD` labels; eval unlabeled ≠ 0.0. Tests: `test_verified_runner.py` + `test_eval_gate.py` (30 passed with lite). **Live Verified resolve still needs docker.** Serve candidate unchanged.
- **SWE_EVAL_CMD thin hook (2026-08-20 unpaid):** `scripts/swe_eval_cmd.py` — PowerShell env documented; default `not_available` (no fake fail); `--mock-resolved` for unpaid tests; optional `swebench.harness.run_evaluation` when Docker + package present. Parser fix: `resolved:null` stays unlabeled. Serve candidate unchanged.
- **SWE_EVAL_BACKEND remote resolve (2026-08-20 unpaid):** `local|modal|sb-cli` behind same `SWE_EVAL_CMD` contract. Modal = harness `--modal true`; sb-cli = `submit swe-bench_verified test`. Honest `modal_not_configured` / `sb_cli_not_configured|missing` without auth. Tests: `tests/test_swe_eval_cmd.py` 22 passed. Docs: disk-light / unpaid-next / docker-swe-eval-status. No docker pull. Serve unchanged.
- **Option A bilinear distill (2026-08-20 unpaid):** `--bilinear-hash-dim` / `--bilinear-distill-hash-dim` (hash teacher → ridge student, no live neural embed). Best cost/BSS: `data/scorer-hard-bilinear-distill48-gymalt.json` (AUC 0.747, BSS +0.058, rcd −0.000278, succ 0.124) still **gate fail**. **Gate recovery:** `--bilinear-distill-latent-dim 18` → `data/scorer-hard-bilinear-distill48-ld18-gymalt.json` (gate true, AUC 0.791, BSS +0.032, ECE 0.022, spread 0.106; rcd still +0.000687). Do **not** replace serve. Reports: `bilinear-distill-2026-08-20.md`, `distill-gate-recovery-2026-08-20.md`. Tests: `test_bilinear_scorer.py` 11 passed.
- **Option B cost frontier (2026-08-20):** no unpaid threshold between 0.10 and 0.15 clears `rcd≤0` with less succ loss than t=0.15 overlay (0.112→0.090). t=0.12/0.13 gate-pass but rcd still &gt;0.
- **Fine cost frontier (2026-08-20):** denser grid falsifies intermediate overlay. t≈0.141–0.145 clears rcd at succ 0.101 but **BSS fails**; first gate-safe clear t≈0.148 at succ 0.090. max_regret inert; per-effort N/A. Report: `fine-cost-frontier-2026-08-20.md`.
- **Cascade knob sweep (2026-08-20 unpaid):** 0 redirects at ship knobs = **threshold** (Flash P≈0.03 ≪ 0.10), not max_regret/phases/pair order. Soft in-memory `t=0.035` → 2/70; `t≤0.027` → 70/70. Keep `cascade_lane.enabled: false`. Report: `cascade-knob-sweep-2026-08-20.md`.
- **Docker unlock (2026-08-20 unpaid):** Docker Desktop started on this Windows host; `docker info` + `hello-world` pass. `swe_eval_cmd` probe → `swebench_package_missing` (not `docker_unavailable`). Verified `--dry-run --limit 1` pass. Paid limit-1 **not** run (no swebench; spend `$15.65`/`$15` blocked). Report: `docker-swe-eval-status-2026-08-20.md`. Cascade unpaid deferred. Serve candidate unchanged.
- Post-mortem: `.scratch/scorer-pioneer-lift/mix1-vs-seeds-postmortem-2026-08-20.md`.
- Minors (defer): issue-08 ticket text still says Spearman < 0; token histograms thinner than brief; `--cost-gold` no collision vs `--gold`; nested cost_slice gate; hop `SCORER_PATH` recipe; blunt trivial→hard remap; inferred `json_schema` from the word `json`
- Report: `.scratch/scorer-pioneer-lift/task-12-probe-report.md` / `issue-12-probe-run.md` / `task-08-plus-report.md`

- **Live Verified SWE_EVAL_CMD smoke (2026-08-20):** limit-1 on `django__django-11099` with shadow gateway + true `SWE_EVAL_CMD`. Spend `15.650197 → 15.651332` (delta `~.001`). Session `label_type=needs_swe_eval` / `session_gold=false` (hook ran; model text not a valid unified diff → harness `not_available`). `eval --gate` → `bounded_check_only`. Serve candidate unchanged. Docs: `docker-swe-eval-status-2026-08-20.md`.
- **Verified patch-format fix + re-smoke (2026-08-20):** `_VERIFIED_TURNS` ask for ````diff` unified patches; `extract_unified_diff` + skip-docker on python-only. Unpaid tests green. Re-smoke limit-1: spend `15.651332 → 15.651502` (+$0.00017); model returned real unified diff; docker **Patch Apply Failed** → still `needs_swe_eval` (model quality, not format). Serve candidate unchanged.
- **Docker-cp file context + true session_gold smoke (2026-08-20):** `docker_file_context.py` (`docker create`+`cp` of `likely_target_files` from eval image into edit prompts). Unpaid: 42 tests + real validators.py cp. Paid limit-1 filectx smoke: spend `15.652567 → 15.653121` (+$0.000554); `has_file_contents=true`, `file_context_source=docker_cp`, **`session_gold=true`** (rules+trained resolved). Serve candidate **unchanged**. Docs: `docker-swe-eval-status-2026-08-20.md`.

- **Verified filectx dual-policy batch n=4 (2026-08-20):** local images only; spend +$0.009328 (15.653→15.662); session_gold 2/4; `eval --gate` → `bounded_check_only`. Artifact `data/verified_session_filectx_batch.jsonl`. Serve candidate unchanged. Report: `verified-filectx-batch-2026-08-20.md`.
- **Verified filectx scale n=4 (2026-08-20):** ids prefer local images; pulled 3 django eval images (~4.18-4.19GB). Out data/verified_session_filectx_n5.jsonl. session_gold **2/4**; spend 15.653121→15.662449 (+$0.009328). Gate bounded_check_only. Serve candidate unchanged. Do **not** run n=300/500 this turn.
- **Verified filectx pathready batch2 n=4 (2026-08-20):** GitHub-blob path-guess fix; curated `data/verified_ids_filectx_pathready.jsonl`; pulled ≤2 images (12754/15252). Out `data/verified_session_filectx_batch2.jsonl`. session_gold **2/4**; docker_cp **4/4**; spend 15.662449→15.680592 (+$0.018143). Gate `bounded_check_only`. Serve candidate unchanged (gateway shadow). Report: `verified-filectx-batch2-2026-08-20.md`.
- **Verified filectx batch3 n=3 (2026-08-20):** Unpaid diagnose 12754/15252 = apply/harness `resolved:null` (not empty patch; docker_cp OK). Curated `data/verified_ids_filectx_batch3.jsonl` (exclude prior 6; 0 unused local → pull ≤3: 14140/11532/11880). Out `data/verified_session_filectx_batch3.jsonl`. session_gold **2/3**; docker_cp **3/3**; spend 15.680592→15.696931 (+$0.016339). **Cumulative unique session_gold = 5** (of 9 filectx ids). Gate `bounded_check_only`. Serve unchanged; gateway shadow. Report: `verified-filectx-batch3-2026-08-20.md`; diagnosis `filectx-12754-15252-diagnosis-2026-08-20.md`.
- **Verified filectx batch4 LOCAL-ONLY (2026-08-20):** Disk stop — **no more docker pulls**. Unpaid: F2P-ranked path guess + plausible filter, max 4 files, copied-path edit prompts, `swe_eval_reason` on session rows. Paid n=3 on already-local 13512/13786/14011 (no new pull after stop). session_gold **1/3**; spend 15.696931→15.713667 (+$0.016736). **Cumulative unique session_gold = 6 / 12**. Gate `bounded_check_only`. Serve unchanged. Inventory: `local-sweb-eval-inventory-2026-08-20.md`; report: `verified-filectx-batch4-2026-08-20.md`. **0 unused local images left.**
- **Verified filectx batch5 harden retest LOCAL-ONLY (2026-08-20):** Unpaid: `normalize_unified_diff`, primary-over-test path ranking + legacy F2P, `DEFAULT_MAX_FILES=2`, stricter edit/debug prompts (no gold injection). Paid dual-policy n=5 local misses (14011/10914/15252/13512/12754) — **no pull**. session_gold **2/5** (14011 labeled fail, 15252 resolve true). Spend 15.713667→15.742347 (+$0.028680). **Cumulative unique session_gold = 8 / 12**. Still miss: 10914/11532/12754/13512. Gate `bounded_check_only`. Serve unchanged (`TRAINED_PATH=shadow`). Report: `verified-filectx-batch5-2026-08-20.md`.
- **Verified filectx batch6 miss retest LOCAL-ONLY (2026-08-20):** Unpaid: debug turn gets truncated ``swe_eval_detail``. Paid n=4 remaining local misses (10914/11532/12754/13512) - **no pull**. session_gold **2/4** (10914+11532 resolve). Spend 15.742347→15.757069 (+$0.014722). **Cumulative unique session_gold = 10 / 12**. Still miss: 12754/13512. Gate ``bounded_check_only``. Serve unchanged (``TRAINED_PATH=shadow``). Local-12 largely exhausted for useful retries. Report: ``verified-filectx-batch6-2026-08-20.md``.
- **Promotion consolidation unpaid (2026-08-20 night):** Merged `verified_session_filectx_all.jsonl` gate re-run → `bounded_check_only` (10/12 session_gold; resolve 0.80/0.80; floor 12≪300). Ship vs overlay re-verify: ship rcd **+0.000687**, overlay **−0.000688** (keep shadow-only). Cascade fixture n=89 edit: **0** cheap redirects. **Session-gold scale disk-blocked** — next levers cost/cascade/hard-gold, not pulls. Docs: `promotion-readiness-2026-08-20.md`, `operator-handoff`, `unpaid-next-path`, `completion-audit`.
- **Git file-context fallback unpaid (2026-08-20 night):** `git_file_context.py` + `resolve_target_file_contents` prefers local `docker_cp`, else shallow `repo`@`base_commit` into `data/repo_cache/` (blob cache; never gold). Unpaid: 16 filectx + 45 verified tests pass; live git CLI `file_context_source=git` for django-11099 validators (685B, `$` anchors). **Edit context unblocked without pulls; resolve still image-bound.** Serve/`TRAINED_PATH` unchanged. Docs: `docker-swe-eval-status-2026-08-20.md`.
- **FireRouter stickiness + session_joined sample (2026-08-20):** Expanded sticky tests (8 pass); savings cleared on sticky model override. Live sticky on shadow gateway. Paid ≤2 local gold (10880/11880, no pull): spend 15.758→15.767 (+$0.009). Gate `session_joined=true`, `n_joinable_hops=10`, joined rcd **−0.00162**, still `bounded_check_only`. Serve unchanged. Docs: `firerouter-stickiness-2026-08-20.md`, `session-joined-cost-sample-2026-08-20.md`. **Goal not complete.**

