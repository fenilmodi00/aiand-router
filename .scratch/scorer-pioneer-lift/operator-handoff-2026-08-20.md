# Operator handoff — scorer/Pioneer status (2026-08-20)

Use this file as the current source of truth for the scorer/Pioneer shadow-serve state.

## Goal status (parity audit)

| Theme | Status |
| --- | --- |
| Diagnose why scorer fails | **Proven** |
| Catalog what won't work | **Proven** (live falsified-path list) |
| Winning strategy + research + debate | **Proven** |
| Router as capable as Fireworks/Pioneer | **Incomplete** — do **not** claim complete |

Full table + falsified catalog: `.scratch/scorer-pioneer-lift/completion-audit-2026-08-20.md`.

- **Serve:** `data/scorer-hard-logistic.json` shadow; ship `rcd=+0.000687`; overlay t=0.15 shadow-only; cascade default-off (0 redirects at ship knobs).
- **Session gold:** local **10/12**; gate `bounded_check_only`; floor n≥300 **disk-blocked** (12 `sweb.eval` preserved; `hello-world` removed ≈0 GB freed).
- **Research vs capability:** strategy done; product parity far.
- **Disk-light parity (no 1TB farm):** `.scratch/scorer-pioneer-lift/disk-light-parity-path-2026-08-20.md` — Modal/sb-cli remote resolve or ephemeral `cache_level=env`+`clean`; do **not** mass-pull on this host.
- **Best next (zero pulls):** stickiness + session_joined sample **landed** (`firerouter-stickiness-2026-08-20.md`, `session-joined-cost-sample-2026-08-20.md`). Re-gate only; unpaid remote-`SWE_EVAL_CMD` spike optional. No smith/gym_alt paid gold. Goal still incomplete.

## Current serve candidate

- **Serve candidate:** `data/scorer-hard-logistic.json`
- **Why this one:** it is the best current shadow artifact on frozen verified replay and is explicitly marked `"serve_candidate": true`.
- **Lightweight verification run today:**
  - `python -m aiand_router.replay_report --gold data/gold-verified.jsonl --artifact data/scorer-hard-logistic.json --models config/models.yaml`
  - Result: `replay_gate_pass=true`, `path=shadow`, `not_spec_floors=true`
  - Key metrics from the current replay:
    - `rank_auc=0.7541887125220459`
    - `brier_skill=0.0006307669657596993`
    - `ece_equal_width=0.006877353719615759`
    - `ece_equal_mass=0.14334260797758666` with `ece_equal_mass_gated=false`
    - `trained.success_rate=0.11235955056179775`
    - `rules.success_rate=0.02247191011235955`
    - `rules_cost_delta=0.0006868617977528091`
    - `savings_vs_most_expensive=0.0008993840449438203`
- **Shadow cost-overlay experiment (not serve):** `data/scorer-hard-logistic-cost-overlay.json` + `config/models.cost-overlay-t015.yaml` (medium threshold **0.15**). Official replay: `rules_cost_delta=-0.000688`, gate pass, AUC same, success 0.090. Clears `rules_cost_delta_not_negative` from `parity_blockers` on n=89 proxy only. Diagnosis: `.scratch/scorer-pioneer-lift/rules-cost-delta-diagnosis-2026-08-20.md`.
- **Fine cost frontier falsified (2026-08-20):** dense medium threshold×max_regret grid found **no** gate-safe unpaid knob that clears `rcd≤0` with succ closer to ship 0.112 than overlay 0.090. Middle band (t≈0.141–0.145, succ 0.101, rcd&lt;0) fails BSS. First safe clear t≈0.148 ≡ succ 0.090. `max_regret` inert; per-effort N/A (replay=`medium`). Keep ship serve; do not add new overlay. Report: `.scratch/scorer-pioneer-lift/fine-cost-frontier-2026-08-20.md`; raw: `data/cost-frontier-fine-2026-08-20.json`.
- **Shadow only:** no path here justifies `TRAINED_PATH=trained`. Keep `path=shadow`.
- **Fireworks-style cascade prototype exists, but is off-path only:** it is disabled by default, only considered when `TRAINED_PATH=off`, and does not change the current Pioneer shadow serve candidate.


## SWE-bench eval unlock (2026-08-20 update)

- Docker Desktop **up**; `swebench==5.0.2` **installed**.
- Wrapper fixed: dataset `SWE-bench/SWE-bench_Verified`; report discovery; Windows UTF-8 + LF bootstrap (CRLF `eval.sh` was a fake fail).
- Image **pulled:** `swebench/sweb.eval.x86_64.django_1776_django-11099:latest` (~4.19 GB local).
- Unpaid gold-patch probe (`data/_gold_django_11099.patch`, never for live turns): **`resolved: true` / `status: ok`**.
- Prompt enrichment + **docker-cp file context** (`src/aiand_router/docker_file_context.py`): copies `likely_target_files` from eval image `/testbed` into edit prompts.
- **Git file-context fallback** (`src/aiand_router/git_file_context.py`): when local `sweb.eval` image is missing, shallow-fetch `repo`@`base_commit` into `data/repo_cache/` for **edit** bytes (`file_context_source=git`). Prefer docker_cp when image exists. **Never gold.** Resolve/`SWE_EVAL_CMD` still image-bound — no new pulls.
- **Live limit-1 filectx smoke:** `data/verified_session_swe_smoke_filectx.jsonl` — `session_gold=true`, rules+trained resolved, `file_context_source=docker_cp`. Spend `15.652567 → 15.653121` (+$0.000554).
- Gate still `bounded_check_only` (n=1 ≪ 300). Serve candidate unchanged. Full runbook: `.scratch/scorer-pioneer-lift/docker-swe-eval-status-2026-08-20.md`.
- Wire: `$env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'` (+ `PYTHONUTF8=1`; gateway `TRAINED_PATH=shadow`).

## What has been disproven / what will not work

- **Do not use the old easy-gold / GBDT path** as the serve path. Earlier replay on `data/scorer.json` failed badly; GBDT worsened Brier/ECE and collapsed toward always-cheapest behavior on verified replay.
- **Do not use silver-regularized Mix1 refits** as the serve path. `data/scorer-hard-logistic-mix1.json` is a regression and is explicitly documented as collapsed transfer.
- **Do not use bilinear artifacts** as the serve path. Unpaid distill advance (2026-08-20): `data/scorer-hard-bilinear-distill48-gymalt.json` beats logistic on BSS/rcd/success but **fails** replay gate (P-spread + ECE_w). Report: `.scratch/scorer-pioneer-lift/bilinear-distill-2026-08-20.md`.
- **Do not scale blind hard-y seed batches** (`seed11`/`seed12`/`seed13`/`seed14`/`seed15`/`seed16`, n400, mix1like, kimi-only-targeted, **order-conservative**) as the next paid move. Those paths failed standalone geometry and/or produced the wrong winner pattern.
- **Order-mix conservative is now a failed paid recipe:** `data/pool-hard-mix-order-conservative.jsonl` passed unpaid preflight (class fractions + projected cost), then seed-16 paid gold **failed standalone geometry** (`y_rate=0.047` below hard band; Flash=Qwen=Pro=0; 26/32 all-fail; 6/32 kimi-only only). Do not re-run that pool.
- **Do not retune on `data/tune.jsonl`** for this effort. That split is the wrong difficulty regime for Pioneer parity.
- **Do not treat `replay_gate_pass=true` as parity.** This artifact is still `not_spec_floors` and still shadow-only.
- **Do not train/calibrate on `data/gold-verified.jsonl`.** Verified remains eval-only.
- **Do not set `TRAINED_PATH=trained`.**
- **Do not treat the cascade prototype as Fireworks parity.** It is a narrow two-model seam, not a measured FireRouter-equivalent product result. Soft-t sweeps unlock redirects without making it FireRouter — keep default-off.
- **Do not expect an unpaid medium-threshold “middle” overlay** that clears `rcd≤0` with success closer to ship 0.112 than t=0.15 — fine frontier falsified (BSS blocks the 0.101 band).
- **Do not expect hash-teacher bilinear distill to jointly beat serve** (gate ∧ rcd≤0 ∧ succ≥serve) under current gold — XOR exhausted; ld18 gate-pass keeps ship rcd.
- **Do not blind-pay gym_alt order-mix / winner-mix pools** after seed2 (32/32 all-fail vs offline projection).

## Fireworks-style binary cascade prototype

- **What it is:** a disabled-by-default binary scorer-backed lane that compares one configured cheap model against one configured strong model. If the cheap model clears the existing effort threshold and stays within the existing max-regret gap of the strong model, the request can redirect to cheap; otherwise it passes through to strong.
- **Where it lives:**
  - config seam in `config/models.yaml` under `cascade_lane`
  - routing logic in `src/aiand_router/scorer.py` via `cascade_lane_config()` and `cascade_select()`
  - path parsing / gating still in `src/aiand_router/scorer.py` through `parse_trained_path()` and `apply_trained_path()`
- **How it is gated right now:**
  - `cascade_lane.enabled: false` in `config/models.yaml`
  - only considered when `TRAINED_PATH=off`
  - ignored for the default `TRAINED_PATH=shadow` Pioneer shadow path
  - ignored for `TRAINED_PATH=trained`
- **Current configured pair:** `cheap_model=deepseek-ai/deepseek-v4-flash`, `strong_model=deepseek-ai/deepseek-v4-pro`
- **Current phase allowlist:** `plan`, `planning`, `edit`, `code_generation`, `code_edit`, `refactoring`, `tool`, `tool_call`, `debug`, `debugging`, `test_failure_analysis`, `security_review`
- **Scoring source:** it reuses the existing scorer artifact and the existing `trained_effort` threshold / `max_regret` knobs. It is not a separate FireRouter-trained classifier.
- **No live impact today:** with the repo default config, the lane is off and the current shadow candidate remains `data/scorer-hard-logistic.json`.

## Test coverage for the cascade seam

- `tests/test_gateway.py::test_disabled_cascade_lane_keeps_rules_pick`
- `tests/test_gateway.py::test_enabled_cascade_lane_redirects_to_cheap_model_on_rules_path`
- `tests/test_gateway.py::test_enabled_cascade_lane_is_ignored_outside_off_path`
- Broader trained/shadow routing behavior still covered in `tests/test_trained_hop.py` and `tests/test_quality_routing.py`

## Why this is still not Fireworks parity

1. **Default-off and off-path only:** FireRouter is a user-facing routing product shape; this seam is disabled and only reachable on `TRAINED_PATH=off`.
2. **Two-model prototype only:** the current seam is one configured cheap model vs one configured strong model, not a demonstrated FireRouter-equivalent routing system.
3. **No FireRouter-style measured eval:** there is no dedicated cost/quality study showing this cascade matches FireRouter behavior or savings on a comparable workload.
4. **Conversation stickiness is separate:** gateway sticky exists (`firerouter-stickiness-2026-08-20.md`); cascade prototype still does not establish FireRouter parity.
5. **Still no promotion evidence:** nothing here changes the core parity blockers around cost vs rules, session-gold promotion, or `TRAINED_PATH=trained`.

## Passing gates vs failing gates

### Passing now

- Frozen verified replay on `data/scorer-hard-logistic.json`: `replay_gate_pass=true`
- Replay outputs still stamp `path=shadow` and `not_spec_floors=true`
- Mix1 hard-gold geometry still verifies as transfer-shaped:
  - `python -m aiand_router.geometry --train data/gold-sparse-hard-mix1.jsonl --eval data/gold-verified.jsonl`
  - Result: `geometry_pass=true`, `spearman_train_eval=0.9486832980505138`, `y_in_hard_band=true`, `holdout_like_order=true`
- Strict standalone merge gate exists in code and is still enforced via `standalone_geometry_pass`

### Still failing / still blocked

- **Pioneer/Fireworks parity is not achieved**
- **A Fireworks-style binary cascade seam now exists, but only as a disabled prototype**
- **`rules_cost_delta < 0` fails on the ship serve knobs** (`+0.000687`); unpaid shadow overlay clears it (`-0.000688`) without replacing serve
- **Equal-mass ECE is not within the nominal bar**, though it is explicitly ungated at this sample size:
  - `ece_equal_mass=0.14334260797758666`
  - `ece_equal_mass_gated=false`
- **No production-style promotion evidence exists**
  - Local filectx merged n=12 / **session_gold 10/12** (`verified_session_filectx_all.jsonl`); still **`bounded_check_only`** (floor n≥300); **disk-blocked** for further images
  - no justification for `TRAINED_PATH=trained`
- **No second fresh geometry-passing hard-gold batch exists**
  - strict standalone merge gate blocks using failing top-ups just because a combined merge would look better

## Exact blockers to Pioneer/Fireworks parity

1. **Cost parity blocker:** ship serve knobs still have `rules_cost_delta > 0` (+0.000687). Unpaid overlay (medium threshold 0.15) clears it on verified proxy but drops success 0.112→0.090 and is **not** promoted to serve. Fine frontier confirms **no unpaid middle** with gate+rcd+better succ (BSS blocks the 0.101 band).
2. **Calibration-at-scale blocker:** equal-width ECE looks good, but equal-mass ECE is still high and currently waived only because selected-hop n is small.
3. **Fresh hard-gold blocker:** there is still no new standalone geometry-passing paid batch beyond Mix1 that would justify scaling or merge growth under the strict merge gate.
4. **Seed-15 / seed-16 blocker:** both paid probes **failed standalone geometry**. Seed-15 (kimi-only-targeted) had wrong winner order at high y; seed-16 (order-conservative) collapsed to kimi-only / all-fail with y below the hard band. Neither unlocks merge, retune, replay comparison, or scale-up.
5. **Promotion blocker:** no path should flip to trained; this remains shadow evidence only, not a production promotion.
6. **Cascade-parity blocker:** the binary cascade seam exists in code, but it is still default-off, off-path-only, and unproven as a FireRouter-equivalent cost/quality result.

## Latest paid evidence: seed-16 failed (order-mix)

- **Pool:** `data/pool-hard-mix-order-conservative.jsonl` (preflight class fractions pass; projected ~$0.66)
- **New gold:** `data/gold-sparse-hard-probe-seed16.jsonl`
- **Spend:** before `14.076110` → after `14.482688` (Δ **+$0.406578**)
- **Standalone geometry result:**
  - `geometry_pass=false`
  - `spearman_train_eval=0.816`
  - `y_rate=0.046875` (`y_in_hard_band=false`)
  - `holdout_like_order=false`
  - per-id: Flash=0, Qwen=0, Kimi=0.1875, Pro=0
- **Winner pattern:** 6/32 kimi-only, **26/32 all-fail**, 0 all-four, 0 qwen-without-flash, 0 flash+qwen+kimi
- **Failure shape:** opposite of seed-15 — too hard / too sparse positives (y below band), not inflated qwen-without-flash. Unpaid class-quota preflight did **not** predict holdout-like order.
- **What did not happen:** no merge, no retune, no replay comparison, no second paid batch.
- **What this disproves:** order-mix conservative (preserving-pattern likelihood + Mix1 class quotas + nm cap 0.85) is **not** a reliable next-paid recipe even when dry-run class fractions pass.

## Prior paid evidence: seed-15 failed

- **New gold:** `data/gold-sparse-hard-probe-seed15.jsonl`
- **Spend update:** `spend_after=14.076110`
- **Standalone geometry:** `geometry_pass=false`, Spearman 0.5, y_rate 0.25, `holdout_like_order=false`
- Disproved `data/pool-hard-mix-kimi-only-targeted.jsonl` as a next-paid source.

## Next-step guidance

1. **Do not run further blind paid probes from order-conservative, kimi-only-targeted, winner-stratified, or mix1like pools.**
2. **Do not merge `data/gold-sparse-hard-probe-seed15.jsonl` or `data/gold-sparse-hard-probe-seed16.jsonl`** into train or retune bases.
3. **Do not retune or replay-compare on top of seed-15/16.** Strict standalone gate already killed those paths.
4. **Keep `data/scorer-hard-logistic.json` as the current shadow serve candidate.**
5. **Smith family is exhausted.** SWE-Gym `gym_alt` first paid probe **gym-alt-seed1** passed standalone geometry (2026-08-20):
   - Gold: `data/gold-sparse-hard-probe-gym-alt-seed1.jsonl` (n=32 prompts / 128 cells)
   - Geometry: `geometry_pass=true`, Spearman 1.0, y 0.125, `holdout_like_order=true`
   - Spend Δ +$0.557 (preflight baseline → post-gold)
   - **Merge + refit attempted:** `data/gold-sparse-hard-mix1-train-gym-alt-merged.jsonl` (n=240) passes combined geometry; `data/scorer-hard-logistic-gym-alt-merged.json` **fails replay** (P-spread 0.084 < 0.10; sole gate failure). Serve candidate unchanged: `data/scorer-hard-logistic.json`.
   - Diagnosis: `.scratch/scorer-pioneer-lift/gym-alt-merge-replay-diagnosis-2026-08-20.md`
   - Preflight helper: `scripts/gym_alt_preflight.py`; report: `.scratch/scorer-pioneer-lift/gym-alt-preflight-2026-08-20.md`.
   - **gym-alt-seed2 paid failed (2026-08-20):** `data/pool-hard-gym-alt-seed2-n40.jsonl` → `data/gold-sparse-hard-probe-gym-alt-seed2.jsonl`. Offline projected ko 0.409 / af 0.505; **actual 32/32 all-fail**. Standalone geometry **fail**: y 0.023, `holdout_like_order=false`. Spend Δ +$0.399. **Do not run further blind gym_alt order-mix probes** — winner-mix projection falsified. Only seed1 geometry-passed; do not merge seed1 without replay-safe strategy. Do not use legacy `pool-hard-gym-alt-n40.jsonl`.
6. **Verified ids scaffold** (`data/verified_ids_scaffold.json`, n=500, `session_gold=false`) is unpaid plumbing only — not session gold, not promotion evidence. Refreshed 2026-08-20.
7. **Promotion readiness scaffolding (2026-08-20 unpaid):** `python scripts/run_promotion_readiness.py` or `lite_runner --promotion-readiness`. Report: `.scratch/scorer-pioneer-lift/promotion-readiness-2026-08-20.md`. Maps runbook §(a) bars; local replay proxy pass but cost `proxy_fail`; session-gold bars `not_started`.
8. **Verified live session runner (2026-08-20):** `verified_runner.py` + `run_verified_session.py` + `eval --gate`. **Live smoke (n=2):** `data/verified_session_smoke.jsonl` (rules-only rows; pre-fix). **Batch (n=10, dual-policy):** `data/verified_session_batch.jsonl` — both `policies.rules` and `policies.trained` (`counterfactual: true` via `x-router-hop-path: trained` on shadow gateway); spend 15.444738→15.650197 (Δ **+$0.205**); rules **0/10**, trained **0/10** resolve; gate **`bounded_check_only`** (n&lt;300 floor). Gateway needs `UPSTREAM_TIMEOUT_S=300` for Kimi counterfactual hops. Full n=500 still requires explicit budget sign-off (~$15+ est. at current per-instance rate).
9. **Verified resolve plumbing fix (2026-08-20 unpaid):** Root cause of 0/10 was not routing — live turns sent only `instance: {id}` and labeled resolve via `_pytest_verify` with **empty `tests`** (always False), while claiming `session_gold=true`. Now loads SWE-bench Verified instance JSON (local dump / `data/dump_cache/swe_verified.jsonl` / unpaid HF `verified_rows.jsonl`) and injects `problem_statement`, hints, repo, FAIL_TO_PASS into flashlight turns (never gold `patch`). Resolve is honest: `harness_proxy` when `tests` present; `session_gold` only via `SWE_EVAL_CMD` docker/eval hook; else `resolved=null` / `label_type=needs_swe_eval` / `session_gold=false`. Offline gold join for unpaid wiring. **Live Verified resolve cannot be non-zero without docker SWE eval.** Scaling n without docker still wastes budget.
10. **SWE_EVAL_CMD thin hook (2026-08-20 unpaid):** `scripts/swe_eval_cmd.py` — dataset `SWE-bench/SWE-bench_Verified`; Windows UTF-8+LF bootstrap; report parsing (summary + per-instance; `error_ids` unlabeled). Gold smoke on django-11099 → `resolved: true`. PowerShell: `$env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'` (+ `PYTHONUTF8=1`). `--mock-resolved` unpaid plumbing only. Docs: `docker-swe-eval-status-2026-08-20.md`, runbook §(a) Step 6.
11. **Docker daemon unlocked on this Windows host (2026-08-20 unpaid):** Docker Desktop started; `docker info` + `hello-world` pass. Hook probe now returns `swebench_package_missing` (not `docker_unavailable`). Verified `--dry-run --limit 1` pass. Paid limit-1 still blocked (no swebench package; spend `$15.65` over `$15` cap). Status + exact PS: `.scratch/scorer-pioneer-lift/docker-swe-eval-status-2026-08-20.md`.

## Exact files to avoid using

Avoid these as serve artifacts or merge bases for parity claims:

- `data/scorer.json` — older failed replay path from the pre-Mix1 logistic/GBDT cycle
- `data/scorer-hard-gbdt.json`
- `data/scorer-hard-gbdt-cal40.json`
- `data/scorer-hard-gbdt-scaled.json`
- `data/scorer-hard-bilinear-probe.json`
- `data/scorer-hard-bilinear.json`
- `data/scorer-hard-bilinear-matched-cal.json`
- `data/scorer-hard-bilinear-hash32.json`
- `data/scorer-hard-bilinear-distill48.json`
- `data/scorer-hard-bilinear-distill48-gymalt.json` — best unpaid bilinear; still not serve
- `data/scorer-hard-logistic-mix1.json`
- `data/scorer-hard-logistic-mix1-merged.json`
- `data/scorer-hard-logistic-nofam.json`
- `data/scorer-hard-logistic-scaled.json`
- `data/gold-sparse-hard-mix1-retune-candidate.jsonl`
- `data/gold-sparse-hard-probe-seed11.jsonl`
- `data/gold-sparse-hard-probe-seed12.jsonl`
- `data/gold-sparse-hard-probe-seed13.jsonl`
- `data/gold-sparse-hard-probe-seed14.jsonl`
- `data/gold-sparse-hard-probe-seed15.jsonl`
- `data/gold-sparse-hard-probe-seed16.jsonl`
- `data/gold-sparse-hard-probe-gym-alt-seed2.jsonl` — order-mix winner-mix preflight passed; paid geometry failed (100% all-fail)
- `data/gold-sparse-hard-mix1-topup32.jsonl`
- `data/gold-sparse-hard-mix1-train-merged.jsonl` unless a future run freshly re-earns standalone and combined geometry
- `data/scorer-hard-logistic-gym-alt-merged.json` — geometry-passing merge refit that **regresses replay P-spread** vs serve candidate
- `data/scorer-hard-logistic-mix1full-gym-alt-merged.json` — counterfactual refit; spread ok but BSS/ECE fail + trained≡Flash

## Notes for the next operator

- The best current shadow artifact is already in place: `data/scorer-hard-logistic.json`.
- Unpaid cost diagnosis (2026-08-20): overspend is systemic Kimi vs rules; shadow overlay t=0.15 clears `rules_cost_delta` without retune — keep as experiment, not serve replacement.
- The Fireworks-style cascade seam is real but intentionally dormant: `config/models.yaml` disables it and the current operator posture does not use it.
- Seed-15 and seed-16 did **not** clear the hard-y blocker; both spent real budget and failed standalone geometry (wrong order / y band).
- The open job is **not** “find any green bit” and is **not** “try another blind paid seed from the same pool families.” Smith is exhausted; gym_alt order-mix seed2 **failed geometry**. **Verified session runner is wired** — next paid step is operator budget reset + gateway smoke (`--limit 2`), not full n=500 blind.
- Keep all paths shadow-only.
- Keep Verified eval-only.
- Keep `TRAINED_PATH` off `trained`.
- **Do not scale Verified session n** until budget is reset and live turns use `SWE_EVAL_CMD` (real swebench, not `--mock-resolved`). Unpaid gold-patch docker smoke on django-11099 now returns `resolved: true`; flashlight alone is still not session gold. Budget must be reset before any paid limit-1.

## Verified filectx batch n=4 (2026-08-20 update)

- **Artifact:** `data/verified_session_filectx_batch.jsonl` (4 local `sweb.eval` django images).
- **Spend:** `15.653121 → 15.662449` (+`0.009328`).
- **session_gold:** 2/4 (11099 docker_cp + 10880 without file bytes); 10914/11066 `needs_swe_eval`.
- **Gate:** `bounded_check_only`; still far from n≥300. Serve candidate **unchanged**; keep `TRAINED_PATH=shadow`.
- **Blocker for scale:** `guess_target_paths` misses → `file_context_source=unavailable` on 3/4 even with local images.
- Report: `.scratch/scorer-pioneer-lift/verified-filectx-batch-2026-08-20.md`.
## Verified filectx scale n=4 (2026-08-20 evening)

- Artifact: `data/verified_session_filectx_n5.jsonl` (n=4; pull-cap limited vs target 5).
- Instances: django__django-11099 (local), 10880/10914/11066 (**pulled**, ~4.18-4.19GB each).
- **session_gold 2/4**; rules+trained both resolved on gold rows; 2x needs_swe_eval.
- Spend delta **+$0.009328** (15.653121 → 15.662449).
- Gate: `bounded_check_only` (n=4 << 300). Serve candidate **unchanged**; keep TRAINED_PATH=shadow for gateway.
- Blockers: floor n; rules_cost_delta>0; BSS/ECE; file_ctx only when paths guessable; do not scale to n=300 this turn without budget/operator plan.
- Next (exact): shadow gateway + SWE_EVAL_CMD + --ids of more local-image django ids (pull <=2-3) then eval --gate on the sessions file.

## Verified filectx pathready batch2 (2026-08-20)

- **Unpaid:** GitHub blob URL path extraction in `guess_target_paths` (django-11066 fixed); curated `data/verified_ids_filectx_pathready.json(l)` (n=4); pulled ≤2 images (12754, 15252).
- **Artifact:** `data/verified_session_filectx_batch2.jsonl`
- **session_gold 2/4**; **docker_cp 4/4** (path-ready curation worked); rules=trained resolve on gold rows; 12754/15252 still `needs_swe_eval` despite file bytes.
- Spend **+$0.018143** (15.662449 → 15.680592).
- Gate: `bounded_check_only`; `do_not_flip_trained_path: true`. Serve candidate **unchanged**.
- Report: `.scratch/scorer-pioneer-lift/verified-filectx-batch2-2026-08-20.md`.
- Next: more pathready local-image ids (pull ≤2) or diagnose apply misses on 12754/15252 before any n-scale.

## Verified filectx batch3 (2026-08-20)

- **Unpaid diagnosis:** 12754/15252 stayed `needs_swe_eval` because extractable patches → SWE_EVAL `resolved:null` (apply/instance error), not empty patch / missing filectx. Note: `filectx-12754-15252-diagnosis-2026-08-20.md`.
- **Ids:** `data/verified_ids_filectx_batch3.jsonl` (n=3 pulls; 0 unused local after exclude prior 6).
- **Artifact:** `data/verified_session_filectx_batch3.jsonl` — session_gold **2/3**; docker_cp **3/3** (14140 labeled fail+fail; 11880 true+true; 11532 unlabeled).
- Spend **+$0.016339** (15.680592 → 15.696931).
- **Cumulative unique session_gold = 5** / 9 filectx ids (≪300).
- Gate: `bounded_check_only`; serve `data/scorer-hard-logistic.json`; gateway `TRAINED_PATH=shadow`.
- Report: `.scratch/scorer-pioneer-lift/verified-filectx-batch3-2026-08-20.md`.

## Promotion evidence consolidation (2026-08-20 night) — DISK-BLOCKED

- **Merged:** `data/verified_session_filectx_all.jsonl` — unique **12** local django images; **`session_gold` 10/12**.
- **Still miss:** 12754, 13512 only — do **not** burn more paid retries without a clear unpaid patch/path fix.
- **`eval --gate`:** `bounded_check_only`; quality 0.80/0.80 on labeled; floor **fail** (12 ≪ 300); live-log BSS/ECE_w fail; `do_not_flip_trained_path: true`.
- **Ship vs cost-overlay re-verify:** ship `rules_cost_delta=+0.000687` (parity blocker remains); overlay t=0.15 `−0.000688`, gate pass, success 0.112→0.090 — **keep overlay shadow-only**; do **not** replace `data/scorer-hard-logistic.json`.
- **Session-joined rcd (sample 2026-08-20):** live `session_joined=true`, `n_joinable_hops=10`, joined `rules_cost_delta≈-0.00162` after shadow restart + local 10880/11880 smokes (plus prior 11099). Detail: `session-joined-cost-sample-2026-08-20.md`. Stickiness: `firerouter-stickiness-2026-08-20.md`. Still `bounded_check_only` (n≪300).
- **Cascade unpaid fixture + knob sweep:** ship knobs → **0 redirects** because Flash P≈0.03 ≪ t=0.10 (`fail_threshold=89`; max_regret inert; Flash>Pro always). Soft in-memory `t=0.035` → **2/70** cheap_redirect; `t≤0.027` → **70/70**. Leave `cascade_lane.enabled: false` (soft-t ≠ FireRouter). Report: `cascade-knob-sweep-2026-08-20.md`.
- **Session-gold scale blocker:** **disk-full / no docker pull**. Next levers are **remote/ephemeral resolve** (`disk-light-parity-path-2026-08-20.md`) and ship-rcd, not more images or cascade promote.
- Readiness: `.scratch/scorer-pioneer-lift/promotion-readiness-2026-08-20.md`.

### Exact next command (zero new images)

```powershell
# Stickiness + session_joined sample done. Re-gate only (no pull):
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_all.jsonl
python -m pytest tests/test_conversation_sticky.py -q
```
