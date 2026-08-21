# Pioneer Training Campaign — Code First, Then Train ($200 cap, $15 checkpoints, ai&-only, RouteLLM-powered)

**Goal:** Deliver a calibrated trained router into this repo — cheapest model that clears a quality bar, K3 included when the task demands it and never when it doesn't — with every $15 spend tranche gated by a named go/no-go check. After the gate passes, wrap steady-state execution in a Cursor `/goal`-style long-lived objective.

**Intent:** CLEAR (outcome defined; only genuine owner-forks would be asked — none survive). Team-mode 5-member hostile roster was UNAVAILABLE (no `team_*` tools); degraded roster `metis + momus + oracle` via native `task` subagents covers the adversarial function.

**Context:** Production spec `.scratch/trained-router/spec.md` parks spec-scale data ops outside this repo; owner has authorized **$200 total ai& credits**, ai&-only provider, no local models. The smoke hop (`.scratch/trained-hop/spec.md`) already works end-to-end. Current ceiling: perfect routing on `data/gold-all.jsonl` (489 prompts, 8 models) = **46.2%** — K3 has zero gold rows. Last refit at n_gold=40 → BSS −0.065 FAIL. This plan restructures the staged $50/$200 proposal into $15-checkpoint tranches so no tranche cannibalizes the next, and borrows the free parts of `lm-sys/RouteLLM` and `Arize/fireworks-cost-benchmark` methodology.

**Design note — K3 reachability (spec-consistent):** `router.py:eligible_models` excludes models at/above `premium_aa_floor` (58) when effort ≠ `max`; K3 (aa 60) is eligible ONLY at `effort=max` on both rules and trained paths. Trained never expands the eligible set.

**Cursor /goal surface:** Operational only — after the plan's final verification wave, the execution session is started under `/goal "Pass the Verified gate within $200"` so the agent holds the objective across tranches, emitting per-checkpoint evidence until the gate passes or budget exhausts. Zero new code for the goal wrapper.

**Decisions (announced in approval brief, locked):**
- D1: EXTEND this repo (`src/aiand_router/`), no new repo.
- D2: `/goal` = operational session wrapper, zero code.
- D3: Hard cap $200, tranches ≤$15 each via `BUDGET_LIMIT_USD` env per run (code default $15 untouched). One concurrent batch is the worst-case overshoot (cents).
- D4: RouteLLM embedding-dependent heads (MF, SW, BERT) deferred behind the EXISTING embed-ablation gate (`docs/runbook-production.md:c` — keep iff Brier strictly better AND ECE not worse). Free borrows land in Phase A.

**Global invariants (worker Must-NOT break):**
1. Rules stay default; trained `live` flips only after a real gate passes. No inventing promotion.
2. Savings only vs `most_expensive_eligible`; never an invented percentage.
3. Every paid phase enforces its cap against `data/spend.txt` BEFORE any ai& call; cumulative cap $200.00. Mechanism: `train.py:_complete` checks `spend.total() >= limit` pre-call. Run each tranche with `BUDGET_LIMIT_USD = spend_file_total_before + tranche_cap`.
4. No local model downloads/runs. Hosted APIs only.
5. `AIAND_BASE_URL` stays on ai& only — no cross-provider row generation under this plan.
6. Artifact metadata: `bootstrap_partial` + `not_spec_floors` until spec floors genuinely met; missing cells stay missing (never impute 0).
7. Every tranche checkpoint is a hard go/no-go: FAIL → stop, diagnose, do not roll into next tranche.
8. LANGUAGE LOCK: All code, docs, JSONL reason codes in English. Honor `CONTEXT.md` vocabulary exactly. Never rename spec terms.

---

## Todos

### Phase A — Code first (credits: $0 — nothing spends until code is clean)

- [x] 1. Strata manifest + spend accounting pre-flight (no credits)
- [ ] 2. Remove distracting / dead code identified in prior gap audits
- [ ] 3. RouteLLM APGR cost-quality curve + noise-regularization borrow (free, code-only)
- [x] 4. Cache-aware cost estimates for multi-turn ranking (Fireworks lesson, free, code-only)
- [ ] 5. Code-phase final verification — tests green, no paid side effects

### Phase B — Teacher silver at scale (cap $15, checkpoint C1)

- [ ] 6. Build production query pool from dumps (~4–5k teacher rows, strata reported)
- [x] 7. Run teacher labeling (Motif-3 → GLM 5.2 escalate ≤25%) → `data/silver.jsonl` + C1 gate

### Phase C — Sparse gold tranche A (cap $15, checkpoint C2)

- [x] 8. Sparse gold — first half n≈1,000 × 4 anchors (Flash + measured trio), no K3 → C2 gate

### Phase D — Sparse gold tranche B (cap $15, checkpoint C3)

- [x] 9. Sparse gold — second half n≈1,000 × 4 anchors → cumulative sparse ~2,000 + C3 gate

### Phase E — Dense/cal expansion (cap $15, checkpoint C4)

- [x] 10. Dense/cal slice n≈300 held-out × eligible-except-K3 + threshold-tune split emission → `data/gold_dense.jsonl` + `data/threshold_tune.jsonl` + C4 gate

### Phase F — Calibration unlock attempt (cap $15, checkpoint C5)

- [x] 11. Dense/cal extension toward n_cal > 1,000 → isotonic unlock if n reached, else honest Platt + C5 gate

### Phase G — K3 onboarding (cap $30 across two $15 tranches, checkpoint C6)

- [x] 12. K3 dense slice part A (~150 rows)
- [x] 13. K3 dense slice part B → K3 n ≥ 300 → re-probe oracle ceiling + C6 gate

### Phase H — Fit → shadow → gates (remaining cap, checkpoints C7/C8)

- [x] 14. Fit scorer (BOTH logistic + GBDT, keep winner on held-out Brier) + calibration on held-out dense only → `data/scorer.json`
- [ ] 15. Retune medium on threshold-tune split; write `trained_effort:` override
- [ ] 16. Shadow run ≥100 hops (flashlight replay + any live traffic), collect `rules_cost_delta_usd` — checkpoint C7 = shadow readiness
- [ ] 17. Bounded gate: Lite micro-slice (n=30–50) + flashlight suite, dual metric — verdict `bounded_check_only`
- [ ] 18. Verified gate: Lite-300 proxy first, then Verified-500 (Docker gate) → promotion decision
- [ ] 19. Handoff artifacts: runbook polish, flywheel log-store contract, K3 onboarding doc, /goal handoff note

---

## Task Details

### Phase A — Code first

**1. Strata manifest + spend accounting pre-flight**
- In `pool.py` / `train.py` add a deterministic split manifest written to `data/split_manifest.json` BEFORE any paid call. Schema (exact fields): `{"prompt_hash": "<sha256[:12]>", "instance_id": "<str|null>", "split": "teacher-silver|sparse-train|dense-cal|threshold-tune|promotion-holdout", "assigned_at": "<iso-date>"}` — one row per pool id, ids keyed by the same `prompt` hash `train.py:_read_queries` uses. Readers (`run_teacher`, `run_gold`) load the manifest and refuse with named error `split_manifest_overlap` when a consumed id is absent or double-assigned. Reuse existing `sample_stratum(seed=0)` machinery; do not invent a new sampler.
- Spend accounting ruling: **`data/spend.txt` stays a single float line — never add comments or headers to it** (`SpendLog.total()` parses one float; any other content parses as 0.0 and silently disables budget enforcement). Record `spend_before_A` in `data/split_manifest.json` metadata block instead; every tranche runs with `BUDGET_LIMIT_USD = spend_before + tranche_cap` where `spend_before` is read from that metadata.
- Verify: `BUDGET_LIMIT_USD` enforcement path is `train.py:_complete` pre-call check — confirm it exists and refuses past limit. No credits spent in this task.
- Commit: `chore(pool): split manifest + spend accounting pre-flight`

**2. Remove distracting / dead code**
- KEEP (load-bearing, do not touch): `pool.py:collision_keys`, all shadow plumbing (`scorer.py:apply_trained_path`, headers), `lite_runner.py`, `eval.py`'s three executed baselines (premium-only, Kimi-only, adaptive), harness helpers (`_pytest_verify`), promotion gate modules.
- REMOVE (candidates, each its own commit): stubbed baseline names in `eval.py` that are not one of the three executed baselines; checked-in synthetic fixtures not referenced by tests; commented-out embed/cascade scaffolding NOT behind the existing `cascade_lane.enabled:false` / embed-ablation gate flags; unused imports flagged by `scripts/check_*.py`.
- QA after each removal: `python -m pytest` green AND `python -m aiand_router.eval --help` still lists exactly premium-only, Kimi-only, adaptive. Zero paid calls.
- Commit(s): `chore(cleanup): remove <what> — <why>` per removal

**3. RouteLLM APGR curve + noise-regularization borrow (free)**
- Borrow A: Port `routellm/evals/evaluate.py` cost-quality curve into `src/aiand_router/eval.py` behind new flag `--apgr` (default off). Adds `APGR = (AUC-router − AUC-weak)/(AUC-strong − AUC-weak)` plus a `strong% → accuracy` plot helper over the existing 3-baselines × 5-seeds loop. No new dependency.
- Borrow B: Port the Gaussian-noise augmentation trick from `routellm/routers/matrix_factorization/train_matrix_factorization.py` as new flag `fit.py --noise-alpha FLOAT` (default 0.0 = off). Pure-Python, no embedding dep.
- Borrow C: Port the quantile `strong_pct → threshold` pattern from `routellm/calibrate_threshold.py` as new flag `train.py retune --init quantile|grid` (default grid = current behavior); quantile initializes the search grid before exhaustive scan.
- Explicitly do NOT port MFModel, SWRankingRouter, or BERTRouter — those need per-request embeddings and are deferred behind the existing embed-ablation gate (`docs/runbook-production.md:c`). Named references for that POST-GATE phase: **`ZhangYiqun018/MTRouter`** (ACL 2026, MIT — history-model joint embeddings for cost-aware multi-turn routing; benchmarked on ScienceWorld/HLE, not coding) and **SWE-Router** (arXiv 2607.00053 — trajectory-conditioned escalate-after-K-cheap-turns). These are the two proven designs for history-conditioned routing — the biggest accuracy lever beyond prompt-only routing. Reference-only until the embed gate passes; never serving scope under this plan.
- QA: `python scripts/check_eval_apgr.py` (new, assert-based): synthetic 2-model win-rate table → APGR ∈ [0,1]; report gains a `cost-quality curve` section only when `--apgr` passed. All three flags default-off. No credits.
- Commit: `feat(eval): APGR curve + routellm-inspired retune init (no embed dep)`

**4. Cache-aware cost estimates for multi-turn ranking (Fireworks lesson)**
- CORRECTED PREMISE: `router.py:estimate_cost` already prefers `cached_input_per_1m` whenever the catalog provides it — unconditionally, even for single-turn requests. The actual gap is turn-count conditionality and auditability, not the absence of cache pricing.
- Change: single-turn requests (`len(messages) <= 1`) price input at list `input_per_1m`; multi-turn requests (`len(messages) > 1`) keep the existing cached-in preference. Add field `est_cache_aware: true|false` to `Decision` + JSONL row + the runbook §b contract field list. Ranking inputs affected: `pioneer_score` cost term, cheapest-effort sort. Post-response logged `cost_usd` stays ACTUAL list-price accounting — estimates rank, billing tells truth.
- QA: unit test with two-model fixture where model A wins on list price but model B wins once cached-in applies — assert multi-turn pick = B, single-turn pick = A, JSONL row carries `est_cache_aware`. Zero credits.
- Commit: `feat(router): turn-aware cache pricing with est_cache_aware audit field`

**5. Code-phase final verification**
- Run full repo checks with `TRAINED_PATH` covering off/shadow/trained fixtures; behavior matrix including K3 reach/suppression + premium-floor lock must pass, plus the new cache-aware flip test from Task 4. `data/spend.txt` unchanged from Phase A entry (prove zero spend). `data/split_manifest.json` disjointness asserted.
- Commit: none — verification only; evidence path `.omo/qa/phase-a-verify.log`

### Phase B — Teacher silver (cap $15, checkpoint C1)

**5. Query pool build (no extra credits beyond the $15 cap)**
- Sample per spec margins: bin 15/40/30/15, tools 75/25, family 30/25/15/15/10/5; occupied-stratum floor ≥ 20 (take-all below). Output `data/queries_spec.jsonl` + coverage report. Sized to the teacher cap: ~4,000–5,000 rows at ~$0.0015/row incl. ≤25% escalate. Must consume only ids assigned to `teacher/silver` in `data/split_manifest.json` from Task 1.
- QA: coverage report shows all target strata with floors; projected teacher cost ≤ $8 within the $15 tranche; manifest sums consistent.
- Commit: `chore(pool): spec-margin query pool with coverage report`

**6. Teacher labeling + C1 gate (cap $15 total for Phase B, stop-on-cap)**
- `AIAND_TRAIN=1 python -m aiand_router.train teacher --queries data/queries_spec.jsonl --out data/silver.jsonl` with `BUDGET_LIMIT_USD = spend_before_B + 15`. Verify before first call: projected cost ≤ remaining cap; abort if `spend.total() + projection > limit`.
- Cheap=Motif-3, escalate=GLM 5.2, temp 0, strict json_schema, label_confidence + AA-disagree rules, cache-first. Unlabeled stays unlabeled.
- **Checkpoint C1 — go/no-go (must pass to enter Phase C):** escalate share ≤ 25%; `silver` row count ≥ 3,500; `geometry_pass` vs `data/gold-verified.jsonl` on a holdout slice (if available) else y_rate in hard band 0.10–0.25. FAIL → diagnose teacher config, do not proceed.
- QA: post-run audit script; spend delta for Phase B ≤ $15.
- Commit: `chore(train): teacher silver (capped $15, C1 gate)`

### Phase C — Sparse gold tranche A (cap $15, checkpoint C2)

**8. Sparse gold first half (cap $15, stop-on-cap)**
- n≈1,000 queries from `data/queries_spec.jsonl` (stratified sample order, cache resume, disjoint from teacher-consumed ids per manifest) × anchors = Flash + Qwen3.6-27B + Kimi-K2.7-Code + DeepSeek-V4-Pro (when eligible per `_gold_ids` filters; ≤4 completions/query). No K3. Short completions (~800 max output tokens). Success gold = gateway rule (no escalate + valid tools/JSON); pytest F2P/P2P harness where a dump provides it (else gateway rule, recorded).
- Output `data/gold_sparse_part_a.jsonl` (merged into `data/gold_sparse.jsonl` on success); per-anchor coverage report; missing cell stays missing.
- **Checkpoint C2:** per ELIGIBLE anchor ≥ 800 rows each, OR cap-stopped with the eligibility filter that caused the shortfall documented per anchor; zero K3 rows; spend delta ≤ $15; harness-vs-gateway label ratio reported. FAIL → adjust sample or cap, do not roll into Phase D.
- Commit: `chore(gold): sparse gold tranche A n≈1000 x 4 anchors (capped $15, no K3)`

### Phase D — Sparse gold tranche B (cap $15, checkpoint C3)

**9. Sparse gold second half (cap $15, stop-on-cap)**
- Second n≈1,000 queries (disjoint from tranche A per manifest) × same 4 anchors, same completion cap, same success rule → merged `data/gold_sparse.jsonl` cumulative sparse ~2,000.
- **Checkpoint C3:** cumulative sparse ≥ 1,800 rows (or honest shortfall with cap accounting); refit trial logistic on sparse-only: held-out Brier < base-rate Brier (any improvement signal, not the final gate); Spearman defined as: anchor win-rate ORDERING on sparse-train half vs sparse-eval half (4 anchors → one rank vector each side, Spearman ρ > 0). FAIL → diagnose sparse composition / anchor eligibility before dense.
- Commit: `chore(gold): sparse gold tranche B n≈1000 x 4 anchors (capped $15, cumulative ~2k)`

### Phase E — Dense/cal expansion (cap $15, checkpoint C4)

**10. Dense/cal slice + threshold-tune emission (cap $15, stop-on-cap)**
- n≈300 held-out-from-sparse queries × every eligible model except K3 → `data/gold_dense.jsonl`. Disjoint from sparse-train, tune split, and any promotion ids per manifest. Short completions (~800 max output tokens per cell).
- SAME task also emits `data/threshold_tune.jsonl`: a further n≈300 manifest-disjoint queries × anchors-only with bootstrap resolve where a harness exists (else gateway rule, recorded) — this is the input Task 15 retune requires; producing it here keeps the disjointness assertion in one place.
- **Checkpoint C4:** full disjoint-set assertion passes across ALL of {sparse-train, dense-cal, threshold-tune, promotion-holdout}; per-model coverage n≥250 OR cap-stopped shortfall recorded with achievable-n arithmetic; ECE equal-width trending down vs last report; spend delta ≤ $15. FAIL → adjust n target within cap, do not proceed to Phase F.
- Commit: `chore(gold): dense calibration slice n≈300 + threshold-tune split (eligible except K3, capped)`

### Phase F — Calibration unlock attempt (cap $15, checkpoint C5)

**11. Dense/cal extension toward n_cal > 1,000 + C5 gate**
- Additional dense rows (held-out, same model set) toward cumulative observed dense cells > 1,000 — the isotonic unlock threshold. Treat n_cal as a CROSS-TRANCHE accumulator: if the $15 cap stops short of 1,000, record achieved n_cal honestly and stay on Platt — never force isotonic on insufficient n. Fit gains explicit flag `fit.py --calibrator auto|platt|isotonic` (default `auto` = count held-out dense rows, pick isotonic iff > 1,000).
- **Checkpoint C5:** if isotonic path taken — dual ECE ≤ 0.03 on a held-out dense slice; if still Platt — equal-width ECE ≤ 0.05 AND the shortfall to 1,000 is quantified in the report (Phase H fit accepts either mode accordingly). FAIL → keep Platt, diagnose dense composition.
- Commit: `feat(train): calibrator auto-select flag + dense extension (capped $15)`

### Phase G — K3 onboarding (cap $30 = 2× $15 tranches, checkpoint C6)

**12. K3 dense slice part A (~150 rows, cap $15)**
- n≈150 held-out queries × K3 only, via a new `train.py gold --include-k3` flag (current `_gold_ids` excludes K3 from dense by default — the flag must bypass that exclusion for this slice ONLY, never for sparse/dense). Respect K3's catalog reasoning-effort default; cost arithmetic uses ACTUAL token caps (`GOLD_REASONING_MAX_TOKENS`, not the 800-tok sparse cap): at $12.50/1M output + $3.00/1M input, $15 buys ≈ 1.1M output tokens ≈ 250–280 rows at ~4k tok/row — set target n=150 to leave input headroom. Disjoint per manifest → `data/gold_k3_part_a.jsonl`.
- QA: K3 row count ≥ 130 OR cap-stopped shortfall with the token-cap arithmetic shown; zero leakage into sparse/dense ids; spend delta ≤ $15.
- Commit: `chore(gold): K3 dense slice part A n≈150 via --include-k3 (capped $15)`

**13. K3 dense slice part B → K3 n ≥ 300 + oracle re-probe + C6 gate (cap $15)**
- Second ~150 K3 rows (disjoint, same flag, same cap) → merged K3 gold `data/gold_k3.jsonl` with K3 n ≥ 300 total.
- Re-run `.scratch/oracle_ceiling_probe.py` on the merged gold (include `gold_sparse + gold_dense + gold_k3`) — the ceiling should clear 50% once K3 is present. Record new ceiling in `data/k3_ceiling_report.md`.
- **Checkpoint C6:** K3 n ≥ 260 (honest floor) and K3 calibrated P(success) ∈ [0,1] for all eligible ids; oracle ceiling > 50% OR diagnose why not (gap = model capability, not router). FAIL → do not proceed to fit without diagnosing K3 label quality.
- Commit: `chore(gold): K3 dense slice part B n≈150 + ceiling re-probe (capped $15, K3 n≥300)`

### Phase H — Fit → shadow → gates (remaining cap ~$65–80, checkpoints C7/C8)

**14. Fit scorer (remaining cap, no per-tranche split — fit itself is free, gold is already bought)**
- Inputs: `gold_sparse + gold_dense + gold_k3 + silver` (silver only on unobserved cells, λ small). Bin head: teacher bins. P(success) heads: fit BOTH logistic and GBDT; keep the one with strictly better Brier on held-out observed gold (tie → logistic, simpler). Calibration corpus = held-out dense/cal slice only; calibrator mode per Task 11's `--calibrator auto` outcome — artifact may be `{"mode":"isotonic","table":[...]}` when n_cal > 1,000 OR `{"mode":"platt","a":...,"b":...}` with equal-width ECE ≤ 0.05 when n_cal ≤ 1,000. Both are acceptable fit outcomes; neither is a task failure.
- Artifact `data/scorer.json` must carry: `bootstrap_partial` / `not_spec_floors` until floors genuinely met, `k3_prior` updated from `silver_only` to `calibrated` after Task 13, calibrator mode, feature list. Never impute 0 for missing cells.
- Also emit APGR cost-quality curve section (from Task 3) into `data/scorer_report.md`.
- QA: `python scripts/check_scorer_fit.py` — artifact loads; `score_eligible` returns p∈[0,1] for all eligible ids incl. K3; bin head emits 4 bins; reliability JSON written; APGR ∈ [0,1]; calibrator mode matches actual n_cal.
- Commit: `feat(scorer): fitted artifact with K3 calibrated + APGR curve`

**15. Retune medium + YAML override**
- CLI `train.py retune --dense data/threshold_tune.jsonl --init grid|quantile` (file produced by Task 10; n≈300 manifest-disjoint; bootstrap resolve where harness exists). Search (threshold, max_regret) grid minimizing list USD subject to escalate-rate ≥ rules − 1pp AND bootstrap-resolve ≥ rules − 1pp. Fit **medium only**; derive low/high/max via Pioneer offsets Δ(−0.05,+0.10)/(+0.10,−0.05)/(+0.50,−0.17), clamp [0,1], walk to restore monotonicity.
- Apply `trained_effort:` to `config/models.yaml`; verify monotonicity; load app with override and assert per-effort headers show fitted numbers.
- QA: medium within constraint or `do-not-promote` verdict recorded; do not invent promotion.
- Commit: `chore(config): retuned trained_effort from tuning split`

**16. Shadow run (≤ $15 from remaining cap, checkpoint C7 = shadow readiness)**
- `TRAINED_PATH=shadow`, serve flashlight task suite plus any live traffic until ≥100 shadow hops; collect `trained_selected`, `trained_confidence`, `rules_cost_delta_usd`. Enforce cap via `BUDGET_LIMIT_USD = spend_before_16 + 15`.
- **Checkpoint C7 (shadow readiness, NOT promotion):** JSONL audit ≥100 rows path=shadow with all contract fields incl. `est_cache_aware`; zero `scorer_down` rows (any such row → diagnose scorer load before gating); `fallback_declined` rate reported (observed, no bar — but a near-100% decline rate is a useless artifact even if clean).
- Commit: `chore(shadow): 100+ shadow hops of fitted artifact (C7 gate)`

**17. Bounded gate (≤ $15, verdict `bounded_check_only`, checkpoint C8a)**
- Via `lite_runner.py`: SWE-bench-Lite micro-slice (n=30 cap, pinned ids from a checked-in id list committed in this task) once as rules, once as trained; plus flashlight suite. Report `data/bounded_gate_report.md`: quality delta vs rules AND cost delta AND calibration (BSS, dual ECE from hops). Verdict formula = quality ≥ rules − 1pp AND cost delta < 0 AND BSS > 0 AND ECE ≤ 0.03. Verdict feeds the runbook only and never flips `TRAINED_PATH`; n below spec floor → verdict line must read `bounded_check_only`.
- **Checkpoint C8a:** report exists with all three metric families; phrase `bounded_check_only` present; no Verified overclaim.
- Commit: `chore(gate): bounded dual-metric check (not the verified gate)`

**18. Verified gate (remaining cap, checkpoint C8b — promotion decision)**
- Per `docs/runbook-production.md:a` — Lite-300 proxy first (cheaper), then Verified-500. Steps: `scripts/gen_verified_queries.py` → `train gold --dense --exclude` on the Verified split → `verified_runner` against gateway in shadow mode. Docker-required for true `session_gold`; WITHOUT Docker, Lite-300 output fails OPEN to `do-not-promote` (never a silent pass). All four bars checked on a frozen promotion split unused for train/cal/retune: quality ≥ rules − 1pp on session gold AND escalate rate; cost delta < 0; BSS > 0; dual ECE ≤ 0.03 (equal-width AND equal-mass M=10); n ≥ 300 session-gold tasks.
- Every bar value in `data/verified_gate_report.md` must be sourced from `data/requests.jsonl` rows with `baseline_model_id` populated — no summary numbers without row provenance.
- On pass → operator flips `TRAINED_PATH=trained` (never the plan worker). On fail → `do-not-promote` with blockers enumerated.
- Commit: `chore(gate): verified promotion gate (Lite-300 proxy + Verified-500 if docker)`

**19. Handoff artifacts**
- Polish `docs/runbook-production.md:a` with the actual Verified commands/costs observed; write flywheel log-store contract (`app.py:_jsonl_row` fields INCLUDING the new `est_cache_aware`, retention-to-next-retrain, redaction) per runbook §b; write K3 onboarding doc (`docs/runbook-production.md:d`); write `/goal` handoff note: objective text `Pass the Verified gate within $200`, per-tranche evidence file list, and stop/continue rules for the Cursor-style wrapper.
- Add a `docs/post-gate-accuracy-roadmap.md` section/note: after Verified passes AND if the embed-ablation gate opens, the next accuracy lever is history-conditioned routing — named proven designs: **MTRouter** (ACL 2026) and **SWE-Router** (arXiv 2607.00053). Reference links only; no implementation scope in this plan.
- QA: every command in the doc exists in the repo; cost formulas reference `config/models.yaml` list prices; final ledger reconciliation holds: sum of tranche deltas == `data/spend.txt` final value − `spend_before_A` from `data/split_manifest.json` metadata.
- Commit: `docs(runbook): handoff — verified gate, flywheel store, K3 onboarding, /goal note`

---

## Dependency Graph

```
Phase A (1→2→3→4→5) — $0, must complete before any spend
    │
    ▼
Phase B (6→7) C1 ──$15──► Phase C (8) C2 ──$15──► Phase D (9) C3
    │                                              │
    └──────────────────────────────────────────────┘
                           │
                           ▼
                    Phase E (10) C4 ──$15──► Phase F (11) C5
                           │                    │
                           └────────────────────┘
                                    │
                                    ▼
                             Phase G (12→13) C6 ──$30──► Phase H (14→15→16→17→18→19) C7/C8
```

No phase after A starts until the prior checkpoint passes. Within Phase H, 13→14→15→16→17 are linear (fit needs gold, retune needs scorer, shadow needs scorer, gates need shadow evidence). Task 18 can overlap 17 once shadow evidence is stable.

## Budget Summary

| Phase | Cap | Cumulative | Evidence at checkpoint |
|-------|-----|------------|------------------------|
| A | $0 | $0 | tests green, manifest disjoint, spend unchanged |
| B | $15 | $15 | C1: silver ≥3,500, escalate ≤25% |
| C | $15 | $30 | C2: sparse tranche A counts |
| D | $15 | $45 | C3: sparse cumulative ~2k, trial Brier signal |
| E | $15 | $60 | C4: dense n≈300, ECE trending |
| F | $15 | $75 | C5: n_cal>1,000 → isotonic |
| G | $30 | $105 | C6: K3 n≥300, ceiling >50% |
| H | ~$80–95 | ≤$200 | C7/C8: shadow ≥100, bounded + verified gates |

Remaining cap after G (~$95) covers H with buffer. Any tranche that cap-stops with honest shortfall records achieved-n; the next tranche's cap is independent (no cannibalization).

---

## Final Verification Wave

- [ ] F1. `python -m pytest` green with `TRAINED_PATH` covering off/shadow/trained fixtures; behavior matrix (K3 reach/suppression, premium-floor lock) passing — evidence: `pytest` log path `.omo/qa/final-pytest.log`
- [ ] F2. `data/spend.txt` end-state ≤ $200.00 total (≤$200 hard cap, ≤$15 per paid tranche) AND ledger reconciliation holds: sum of per-tranche deltas == final `spend.txt` value − `spend_before_A` recorded in `data/split_manifest.json` metadata — evidence: `data/spend.txt` + reconciliation printout
- [ ] F3. `data/split_manifest.json` — all pool ids accounted for, pairwise-disjoint split sets — evidence: manifest + assertion log
- [ ] F4. `data/scorer.json` loads, `score_eligible` returns p∈[0,1] for every eligible model incl. K3, bin head emits 4 bins — evidence: `scripts/check_scorer_fit.py` log
- [ ] F5. Bounded gate report exists with `bounded_check_only` verdict and APGR cost-quality curve section — evidence: `data/bounded_gate_report.md`
- [ ] F6. Verified gate OR Lite-300 proxy gate report exists with all four bars checked and blocker enumeration on fail — evidence: `data/verified_gate_report.md` or `data/lite_gate_report.md`
- [ ] F7. Handoff docs exist and every command in them is runnable in the repo — evidence: `docs/runbook-production.md:a` + `/goal` handoff note

## Must-NOT-Have

- No new repo. No local model downloads/runs. No per-request embedding calls in the serving path before the embed-ablation gate passes. No `TRAINED_PATH=trained` flipped by code — operator only after a real gate passes. No invented savings percentages. No training/calibration/retuning on eval-only dumps (SWE-bench family, Terminal-Bench, Multi-SWE-bench) — `pool.py:collision_keys` enforced. No cross-provider row generation under this plan.

## Handoff — After the Plan

1. Worker runs `$start-work` against this plan; each tranche enforces its $15 cap via `BUDGET_LIMIT_USD` and stops at its checkpoint. FAIL → diagnose, never roll forward.
2. After the final verification wave, the execution session is wrapped as a Cursor `/goal` long-lived objective: `/goal Pass the Verified gate within $200` — the agent holds the objective across tranches, emitting per-checkpoint evidence until the gate passes or budget exhausts.
3. At handoff, offer high-accuracy review (degraded roster: `momus` plan critic + `oracle` independent pass). Full 5-member hostile roster available after enabling `team_mode.enabled=true` and restarting opencode.
