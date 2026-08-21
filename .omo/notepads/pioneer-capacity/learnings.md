# Learnings — pioneer-capacity

Conventions, patterns, and successful approaches discovered during work on this plan.

_Auto-scaffolded by /start-work. Append new entries below - never overwrite._

---

# pioneer-capacity learnings

## 2026-08-15 - Wave 1 dispatch

- `.env` in this repo actively sets `TRAINED_PATH` (uncommented, =trained). App/tests load .env, so bare `pytest tests/` shows ~31 failures (signature: `os.getenv("TRAINED_PATH")=="trained"`, x-router-path trained vs expected shadow). Pre-existing env condition, not a code regression. Verifier (bg_d5f99cd8) confirming via temp-worktree-at-HEAD experiment. For F1, run the suite with the env var explicitly overridden; never edit user .env. (quirk store backend down - Ollama 11434 refused; recorded here instead.)
- Wave-1 lane T6 (monitor) completed its session WITHOUT writing files - exploration-only output, no monitor.py/check_monitor.py/t6 log. Lesson: for low-tier lanes, put the file-deliverable requirement first in the prompt. Respawned as bg_45758d29 with tightened prompt.
- Wave-1 QA artifacts all present and passing: t1 (17/17, ECE iso 0.0287 vs platt 0.0809), t2 (7/7), t8 (collision_dropped=2, license_dropped=1, malformed=1), t9 (fixture 3 rows, prompt-injection sandbox proof).
- Parallel lanes in one git tree: file-isolated waves work; verification of a wave must happen before the next wave edits shared files (train.py). Sequenced: verify+commit Wave 1, then dispatch Wave 2.
- Spend baseline at session start: data/spend.txt = 8.157082. Phase caps relative to the value at phase start (BUDGET_LIMIT_USD = spend_before + phase_cap).

## 2026-08-15 - T5 retrain orchestration

- T5 retrain orchestration complete: `src/aiand_router/retrain.py` + `scripts/check_retrain.py`, 14/14 QA pass.
- `fit_scorer` is callable directly without AIAND_TRAIN — it's a plain function, not gated by `_refuse()`. Only `main()` enforces the opt-in. retrain.py imports and calls `fit_scorer` directly, no subprocess, no env var needed.
- T4 (retune) has NOT landed yet — no `retune` subcommand in train.py's `main()`. retrain.py checks at runtime via `_has_retune()` (looks for callable `retune_thresholds`/`run_retune`/`fit_thresholds`/`retune` attrs on the train module). When T4 lands, the retune step will auto-activate; until then it's noted as "skipped (not available)" in the report.
- Gate-check on synthetic fixture data correctly returns `do-not-promote` (BSS=-0.065, ECE=0.123) — the synthetic data is too small/random for good calibration. This is the expected dry-run behavior: the gate works by refusing to promote a poorly-calibrated scorer.
- retrain.py never loads `.env` (no `dotenv.load_dotenv()` in `__main__`), so TRAINED_PATH stays unset when run as `python -m aiand_router.retrain --plan-only`. The check script verifies this by popping TRAINED_PATH before calling `run_plan_only()` and asserting it's not 'trained' afterward.
- Calibration metrics computed by scoring each gold row through `score_eligible` to get calibrated p_success, then pairing (p, y) into metrics rows. Uses all gold rows (train+cal) — acceptable for dry-run gate-check; real promotion gate uses the dense gold slice only.
- `python -m aiand_router.retrain` needs `PYTHONPATH=src` (or `--app-dir src` style) since the package isn't pip-installed in the venv.

## [2026-08-15] T7: Quality-first routing acceptance harness
- Created `tests/test_quality_routing.py` with 6 behavior assertions covering the trained-path routing matrix.
- All 6 tests pass in 1.08s with `TRAINED_PATH=shadow` override.
- Key findings:
  - At `effort=max`, the premium floor check is skipped (`effort == 'max'` in `eligible_models`), but the AA quality threshold is `max(phase_bar, premium_aa_floor)`. With the default config (`premium_aa_floor=58`), only K3 (aa=60) is eligible at max. A custom config with `premium_aa_floor=50` is needed to get Flash (aa=52) eligible at max.
  - The raw `p_success` path in `score_eligible` (no `weights`/`gbdt` keys) uses values directly without calibration — simplest way to control which models clear the threshold in tests.
  - `pick_cheapest_above_bar` sorts survivors by `(unit_cost, -p_success)` — cheapest first. This is the cost discipline mechanism: even at `effort=max`, if a cheaper model clears threshold and is within `max_regret` of the top, it wins.
  - The `trained_effort` knobs from config: `max: {threshold: 0.60, max_regret: 0.03}`, `medium: {threshold: 0.10, max_regret: 0.20}`.
  - `monkeypatch.delenv('TRAINED_PATH')` + `monkeypatch.delenv('SCORER_PATH')` in each test prevents .env interference. Explicit `trained_path='trained'` and `scorer_path=fixture` params to `create_app` override any env vars.
  - `X-Router-Candidates` header contains comma-separated eligible model IDs — useful for verifying premium floor gating (K3 absent at medium effort).

## [2026-08-15] T3: Drift canary module

- Created `src/aiand_router/canary.py` (175 pure LOC), `scripts/check_canary.py` (9/9 QA pass), edited `app.py` `_router_headers` (4 lines: import + 3-line guard).
- Canary imports `brier_skill_score`, `ece_equal_width`, `ece_equal_mass` from T2's `metrics.py` — no new dependencies, stdlib + existing module only.
- Window rule: n>=300 rows AND 7 days (both must be met). Window = max(last_300, last_7d) by row count. "last 7 days" is relative to newest row timestamp, not wall clock — deterministic.
- Trip conditions: (1) trained escalate rate > rules + 1pp, (2) BSS <= 0, (3) either ECE > 0.03. Escalate = presence of `escalated_from` field in JSONL row. Success gold = 0 if escalated OR tool_valid=False OR json_valid=False OR status>=400; 1 otherwise; None (skip) if status missing.
- `is_tripped()` uses mtime-based cache so the app hot path (`_router_headers`) doesn't re-read the file on every hop. Returns False when `data/drift_status.json` doesn't exist — the `_router_headers` edit is a no-op in tests.
- `data/drift_status.json` output is deterministic: `{tripped, reasons[], window: {n_rows, n_days}}` — no timestamps from `datetime.now()`, all time data comes from the JSONL rows.
- On trip: `retrain_drift` added to `decision.reason_codes` in `_router_headers`; ops posture stays rules-default (no live trained flip). The reason code propagates to JSONL via `_jsonl_row` since `_router_headers` is called before `_jsonl_row` in both code paths.
- Synthetic test data lesson: discrete p values (0.9, 0.3) with only 150 rows don't calibrate well in equal-mass bins (ECE=0.06). Need continuous p ~ U(0,1) with ~3000+ trained rows for ECE <= 0.03 in the healthy case. The `check_metrics.py` script uses 20000 rows for the same reason.
- Pre-existing test failures (31) are from `.env` setting `TRAINED_PATH=trained` — not caused by canary changes. Verified `is_tripped()` returns False when no `drift_status.json` exists.

## [2026-08-15] T4: Retune-holdout splitting + medium-only (t, r) search

- T4 retune complete: `run_retune()` in train.py + `scripts/check_retune.py`, 39/39 QA pass.
- `retune` subcommand bypasses `AIAND_TRAIN` gate (same as `pool`) — it's a pure offline computation (reads JSONL + scorer, does math, prints YAML). No API calls, no spending.
- Constraint semantics: `escalate_rate = 1 - resolve_rate` where resolve = trained-picked model succeeded (NOT counting rules fallback). When trained declines (fallback_declined), it's an escalate regardless of rules fallback outcome. This makes `do-not-promote` achievable: if the scorer can't predict which models succeed, no (t, r) gets resolve_rate within 1pp of rules.
- `threshold=1.0` (always decline) gives resolve_rate=0, which fails the constraint when rules_resolve_rate > 0.01. This is the key difference from counting rules-fallback as resolve — it would make do-not-promote impossible.
- Grid: threshold [0, 1] step 0.01 (101 values) × max_regret [0, 0.2] step 0.01 (21 values) = 2121 combos. Pre-computing `score_eligible` per query (outside the grid loop) is essential — the grid only calls `pick_cheapest_above_bar` which is O(n_eligible).
- Pioneer offsets: dt(-0.05,+0.10)/(+0.10,-0.05)/(+0.50,-0.17) from medium. Clamp [0,1] then walk: `t_low=min(t_low,t_med)`, `t_high=max(t_high,t_med)`, `t_max=max(t_max,t_high)`, reversed for r. Single-pass suffices since t_med/r_med are fixed.
- `eligible_models` with `budget_usd=1e18` avoids budget-based filtering. `spend_usd=0.0` ensures no models are excluded by remaining budget.
- `run_retune` returns the YAML string (or "do-not-promote"); the CLI wrapper does `print(result, end="")` to avoid double newlines.
- T5 retrain's `_has_retune()` will now find `run_retune` — the retune step in retrain.py should auto-activate.



## [2026-08-15] T10: Spec-scale query pool + split manifest

- Created `scripts/build_pool_spec.py` (generator) and `scripts/check_pool_spec.py` (QA gate). No src/ edits, no aiand credits, no network.
- `data/queries.jsonl` does not exist — the existing pool files (`pool-hard.jsonl` etc.) are all `hard`-bin flashlight prompts, not diverse enough for spec margins. Generated synthetic coding-agent prompts instead.
- Query format matches `pool.py`'s `_query()` output: `prompt`, `phase` (family), `hint_bin`, `needs_tools`, `source`, `instance_id`, plus `id` and `tokens` (computed via `len(json.dumps(messages)) // 4`, same as `router.estimate_tokens`).
- Stratum target formula: `max(20, round(n * bin_frac * phase_frac * tools_frac))` per (bin, phase, tools) cell. Floor 20 applied to all 48 strata. Total = 4,039 (within 4,000-5,000 spec band).
- Margins hit within +/-1pp: bin 15.3/39.6/29.8/15.3, tools 74.3/25.7, phase 29.7/24.8/14.9/14.9/10.2/5.7. All within the +/-5pp spec tolerance.
- Split assignment: deterministic `random.Random(0).shuffle(queries)` then slice — promotion-holdout (300), tune (300), dense/cal (300), sparse-train (3,139). Manifest stores split->[id] lists; pairwise disjoint by construction.
- Teacher cost projection: 4,039 rows x avg 54 tokens x per-row $ .000425 (Flash cheap + 25% Pro escalate) = $1.72, well under $8 cap.
- TDD: wrote `check_pool_spec.py` first, ran it (FAIL: pool not found), then built the generator, ran it, re-ran the checker (PASS: all checks green).
- QA log saved to `.omo/qa/t10-pool-spec.log`.

## [2026-08-15] T15: Scorer metadata + reliability metrics

- Added 3 metadata fields to `data/scorer.json`: `label: "bootstrap_partial"`, `k3_prior: "silver_only"`, `features: [16 feature names]` matching the `featurize()` function in `scorer.py`.
- Feature names derived from `featurize()`: bias, needs_tools, log_tokens, 4 token-bin one-hots, 4 hint-bin one-hots, 5 text-feature binaries = 16 total, matching the 16-element `weights` arrays.
- Created `scripts/compute_reliability.py` — loads gold_dense.jsonl, scores each observed row through `score_eligible`, pairs (p_success, success_gold), computes BSS/ECE/MCE/reliability table via `metrics.py`.
- Reliability on 1127 observed gold_dense rows: BSS=0.404, ECE equal-width=0.013, ECE equal-mass=0.034, MCE=0.030. The equal-mass ECE (0.034) slightly exceeds the 0.03 promotion-gate bar — expected for a bootstrap_partial artifact.
- `check_scorer_fit.py` still passes 11/11 after adding metadata fields (no existing keys modified).
- `data/reliability.json` output: `{bss, ece_equal_width, ece_equal_mass, mce, reliability_table, n_rows}`.

## [2026-08-15] T19: Production handoff runbook

- T19 runbook complete: `docs/runbook-production.md` + `scripts/check_runbook.py`, 6/6 QA pass.
- Four sections: (a) Full Verified(500) promotion gate, (b) aiand-infra flywheel log store, (c) embed ablation execution, (d) K3 dense-gold onboarding.
- JSONL contract fields documented from `app.py:_jsonl_row` (base + conditional + call-site extras). `ts` added by `append_jsonl` in `router.py:455`. No API keys in any field — verified by reading `_jsonl_row` and all three call sites (L453, L522, L687).
- Commands referenced in the runbook, all verified to exist: `scripts/gen_verified_queries.py`, `aiand_router.train` (subcommands: teacher, gold, fit, retune), `aiand_router.retrain` (--plan-only), `aiand_router.lite_runner`, `aiand_router.eval`, `scripts/check_canary.py`.
- `check_runbook.py` regex extracts `python -m <module>` and `python scripts/<file>.py` lines from markdown, resolves each to a file under `src/` or repo root, asserts all exist. 6 unique commands verified.
- Cost formulas reference README list prices: Flash $0.15/$0.25, Qwen 3.6 27B $0.32/$3.20, Motif-3 $0.50/$2.00, K2.7 Code $0.75/$3.50, DS V4 Pro $1.00/$2.50, GLM 5.2 $1.00/$4.00, K3 $3.00/$12.50.
- K3 onboarding cost estimate: n=300 x ~$0.0145/completion = ~$4.35 (K3 is the most expensive model at $12.50/1M output).
- Verified gate cost estimate: 500 x 4 models x ~$0.0014 avg = ~$2.80 (measured trio + Flash); 500 x 7 models x ~$0.0024 avg = ~$8.40 (full eligible set).
- `lite_runner.py` has a hard CAP=50 on instance count — the runbook notes this is the bounded check (task 18), distinct from the full Verified(500) promotion gate. The runbook references a future `verified_runner` for the full gate.
- `gen_verified_queries.py` emits `datasets/verified-queries.jsonl` with checkable outcomes (expected substrings, pytest verify, JSON validity) — used as the Verified query set for gold runs.
- `train.py` CLI subcommands: `pool`, `teacher`, `gold` (with `--dense`/`--exclude`), `fit` (with `--gbdt`), `relabel`, `salvage`, `retune` (with `--dense`/`--scorer`/`--models`). `pool` and `retune` bypass the `AIAND_TRAIN` gate (offline computations).
- `retrain.py --plan-only` runs fit -> cal-report -> retune (if available) -> write `data/scorer.candidate.json` + `data/retrain_report.md` -> gate-check. Never sets `TRAINED_PATH=trained`.
- `canary.py` drift canary: window = n>=300 AND 7 days (both must be met). Trip conditions: escalate rate >1pp worse than rules, BSS<=0, either ECE>0.03. On trip: `path=rules`, reason_code `retrain_drift`.

## [2026-08-15] T16: Retune medium on data/tune.jsonl

- Ran `python -m aiand_router.train retune --dense data/tune.jsonl --scorer data/scorer.json` with `PYTHONPATH=src` and `AIAND_TRAIN=1`.
- Retune succeeded (not "do-not-promote"). Fitted values:
  - low: {threshold: 0.78, max_regret: 0.23}
  - medium: {threshold: 0.83, max_regret: 0.13}
  - high: {threshold: 0.93, max_regret: 0.08}
  - max: {threshold: 1.00, max_regret: 0.00}
- Monotonicity verified: t_low(0.78) ≤ t_med(0.83) ≤ t_high(0.93) ≤ t_max(1.00), r_low(0.23) ≥ r_med(0.13) ≥ r_high(0.08) ≥ r_max(0.00).
- Applied to `config/models.yaml` with comment `# retuned from data/tune.jsonl (task 16)`.
- Raw output saved to `data/retune_result.txt`.
- `scripts/check_retune.py` passes 39/39.
- The retuned thresholds are much higher than the defaults (0.78 vs 0.05 for low) — the scorer is conservative, requiring high confidence before picking a trained model over the rules fallback. max_regret values are also tighter (0.23 vs 0.30 for low). This reflects the bootstrap_partial scorer's calibration: it only clears the bar when it's confident.

## [2026-08-15] T17: Shadow run (≥100 hops collecting rules_cost_delta_usd)

- Created `scripts/run_shadow.py` — self-contained script that starts uvicorn programmatically in a background thread, sends 160 requests (semaphore=5), stops the server, and audits the JSONL. No subprocess management.
- **CRITICAL gotcha**: `.env` sets `SCORER_PATH=data/scorer-hard-logistic.json` (a hard-bin-only scorer with very negative intercepts). This scorer produces p_success values of 0.02–0.14 for all models, far below the retuned thresholds (0.78+). Every row was `fallback_declined` with `trained_confidence=None`. The fix: override `SCORER_PATH` to `data/scorer.json` (the task 15 artifact) via `os.environ` BEFORE any `aiand_router` imports. `load_dotenv()` does NOT override existing env vars, so setting it early sticks.
- **CRITICAL gotcha**: `.env` also sets `TRAINED_PATH=trained` (uncommented). Must override with `os.environ["TRAINED_PATH"] = "shadow"` BEFORE imports. Same `load_dotenv()` non-override behavior.
- `uvicorn.Config` does NOT accept `app_dir` as a kwarg — that's a `uvicorn.run()` parameter. Use `sys.path.insert(0, str(ROOT / "src"))` instead to make `aiand_router` importable.
- The gateway's `rotate_local_data_if_key_changed` archives `requests.jsonl` and `spend.txt` only when `AIAND_API_KEY` fingerprint changes. Since the key didn't change, no archiving occurred. The `restore_if_archived` defensive check is a no-op in practice.
- Shadow run results (160 requests, all cache hits from prior traffic): 160 `path=shadow` rows, 0 `scorer_down`, 120 rows with all three fields (`trained_selected` + `trained_confidence` + `rules_cost_delta_usd`), 40 `fallback_declined` (max effort, threshold=1.0, expected). Spend delta: $0.0 (cache hits). `rules_cost_delta_usd` mean: -0.003 (trained picks are cheaper than rules picks).
- The 40 fallback_declined rows (25% = max effort) still have `trained_selected` and `rules_cost_delta_usd` but NOT `trained_confidence` (None in the fallback path of `trained_select`). This is by design: `fallback_decision` doesn't set `confidence`, so `apply_trained_path("shadow", ...)` copies None into `rules.trained_confidence`, and `_jsonl_row` omits None fields.
- For low/medium/high efforts, the scorer correctly predicts high p_success for Flash (0.95+), which clears the retuned thresholds (0.78/0.83/0.93). The trained path picks Flash (cheapest above bar) and logs `trained_confidence` ≈ 0.95.
- `predict_complexity_bin` with the `scorer.json` bin_weights predicts "hard" for short plan-phase prompts (log1p(10)≈2.4, token_bin < 128, phase=plan). This is expected — the bin head learned that short prompts in plan phase tend to be hard.
- Audit output: `data/shadow_audit.json` with fields: `spend_before`, `spend_after`, `spend_delta`, `new_rows_total`, `shadow_rows`, `scorer_down_rows`, `rows_with_all_fields`, `fallback_declined_rows`, `fallback_declined_rate`, `rules_cost_delta_usd` (count/min/max/mean), `pass`.
