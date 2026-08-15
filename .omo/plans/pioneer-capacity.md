# Pioneer Capacity Plan — Trained Router to Pioneer-Parity (Quality-First, $50)

**Goal:** Close the gaps in [.opencode/wiki/concepts/pioneer-gap-analysis.md](.opencode/wiki/concepts/pioneer-gap-analysis.md) so the trained path routes to the cheapest model that clears a *quality* bar — Kimi K3 included when the task demands it, K3 never when it doesn't — with both quality and cost proven on a bounded gate.

**Context:** Production spec `.scratch/trained-router/spec.md` parks spec-scale data ops outside this repo; the owner has authorized executing them here with **$50 total aiand credits**, no local models. The smoke hop (`.scratch/trained-hop/spec.md`) already works end-to-end; this plan raises data scale, adds isotonic calibration, adds drift/retune/retrain machinery, executes teacher + gold at the largest in-budget scale, and ends live-in-shadow with a bounded dual-metric gate.

**Design note — K3 reachability vs the premium floor (spec-consistent):** `router.py:eligible_models` excludes models at/above `premium_aa_floor` (58) when effort ≠ `max`; K3 (aa 60) is therefore eligible ONLY at `effort=max`, on both rules and trained paths (trained never expands the eligible set — trained-hop spec US8/US14). The quality-first mandate is delivered as: at `effort=max` the trained path can and must serve K3 when demanded; below `max`, K3 is absent by the premium floor on BOTH paths, and that gating is part of the locked behavior.

**Global invariants (worker Must-NOT break):**
1. Rules stay default; trained `live` flips only after a real gate passes. No inventing promotion.
2. Savings only vs `most_expensive_eligible`; never an invented percentage.
3. Every paid phase enforces its cap against `data/spend.txt` **before** any aiand call; cumulative plan cap $50.00. Mechanism (only enforcement var is `BUDGET_LIMIT_USD`; `train.py:_complete` checks `spend.total() >= limit` pre-call, returning refusal past the limit, opt-in `_refuse` env gate): run each paid phase with `BUDGET_LIMIT_USD = spend_file_total_before + phase_cap` so no phase cannibalizes the next. Pre-call check is total-only; worst-case overshoot is one concurrent batch (cents at these prices). Prior-spend assumption: `NOTES.md` (2026-08-15) records `data/spend.txt ≈ $8.16`; the plan treats the $50 as **plan-incremental** — F2 audits ledger deltas. If the owner means account-absolute, state it before Phase B.
4. No K3 gold cells at $50; K3 trained-path P(success) is teacher-silver prior only, recorded in the artifact.
5. No local model downloads/runs. Hosted APIs only.
6. No live embed, no Rec B, no `xhigh` rung, no chat teacher on the hop.
7. Artifact metadata: `bootstrap_partial` + `not_spec_floors` labels; missing cells stay missing (never impute 0).
8. LANGUAGE LOCK: All code comments, docs, README/README edits, JSONL reason codes in English. Honor CONTEXT.md vocabulary exactly (complexity bin, calibrated P(success), threshold, max regret, shadow, drift canary, …). Never rename spec terms.

---

## Todos

### Phase A — Code completes (credits: $0)

- [x] 1. Isotonic calibration alongside Platt with spec auto-select
- [x] 2. Calibration gate metrics module (BSS, dual ECE, MCE, reliability data)
- [x] 3. Drift canary module monitoring `data/requests.jsonl`
- [x] 4. Retune-holdout splitting + medium-only (t, r) search with Pioneer offsets
- [x] 5. Retrain orchestration script (train → cal → retune → shadow-ready → gate-check dry-run)
- [x] 6. Multi-SWE-RL non-Python hop monitor
- [x] 7. Quality-first routing acceptance harness (behavior matrix incl. K3 reach/no-K3, premium-floor-aware)
- [x] 8. Spec-scale dump ingest wiring (smith tool split + smith tasks + BFCL, collision-filtered)
- [x] 9. Minimal SWE-bench-Lite session runner (fetch → gateway loop → F2P/P2P resolve)

### Phase B — Teacher at scale (cap $8)

- [x] 10. Build production query pool from dumps (~4–5k teacher rows worth, strata reported)
- [x] 11. Run teacher labeling (Motif-3 → GLM 5.2 escalate ≤25%) → `data/silver.jsonl`

### Phase C — Sparse gold (cap $22)

- [x] 12. Run sparse gold n≈2,000 × 4 anchors (Flash + measured trio), short completions → `data/gold_sparse.jsonl`

### Phase D — Dense/cal + threshold-tune (cap $8)

- [x] 13. Dense/cal slice n≈300 × eligible-except-K3 → `data/gold_dense.jsonl`
- [x] 14. Threshold-tune split n≈300 × anchors with bootstrap resolve → `data/tune.jsonl`

### Phase E — Fit → shadow → bounded gate (cap $4)

- [ ] 15. Fit Scorer (bin head + P(success) heads + auto-selected calibrator) → `data/scorer.json`
- [ ] 16. Retune medium on `data/tune.jsonl`; write `trained_effort:` runtime override
- [ ] 17. Shadow run (≥100 hops or flashlight replay) collecting `rules_cost_delta_usd`
- [ ] 18. Bounded promotion check: flashlight suite + SWE-bench-Lite micro-slice via task-9 runner (n≈30–50), dual metric
- [x] 19. Handoff runbook: full Verified gate, flywheel log store contract, embed-ablation execution, K3 onboarding

---

## Task Details

### Phase A

**1. Isotonic calibration (`train.py`, `scorer.py`, maybe `tests/test_gateway.py`)**
- Add `_fit_isotonic` using Pool Adjacent Violators (PAVA, ~50 lines, pure Python — no sklearn dependency, works offline on Windows). Reference: `src/aiand_router/train.py:_fit_platt` L819–833 for the (z, y) input convention; UCCI findings: isotonic reached ECE 0.03 where temperature scaling reached 0.08.
- Auto-select rule (spec): `n_cal ≤ 1000 → platt`, else `isotonic`. Store in artifact as `calibrator: {"mode": "isotonic", "table": [[z, p], ...]}` or `{"mode": "platt", "a": ..., "b": ...}`.
- Extend `scorer.py:_calibrator_ab` (L141–144) into `_calibrate(artifact, z)` that dispatches on mode; isotonic = monotone step lookup over the stored table.
- QA (agent-run): `python scripts/check_isotonic.py` (new, assert-based): fit on a monotone synthetic set, assert ECE(isotonic) ≤ ECE(platt) on it; artifact round-trip through `load_scorer` + `score_eligible`; `n_cal = 50` forced-Platt path.
- Commit: `feat(train): isotonic calibration with platt fallback per spec n_cal rule`

**2. Calibration gate metrics (`metrics.py` new; reused by eval + canary)**
- Implement: Brier skill score vs base rate, equal-width ECE (M=10), equal-mass ECE (M=10), MCE, optional M=15 report, reliability-table JSON writer. Inputs: rows of (p_success_of_selected, success_gold). Spec bars: BSS > 0, both ECE ≤ 0.03.
- Refs: `.scratch/trained-router/spec.md` §Calibration; `geometry.py` for JSONL loading patterns.
- QA: `python scripts/check_metrics.py` — synthetic perfectly-calibrated data → ECE ≈ 0; constant-prediction data → BSS ≤ 0; mis-calibrated data → ECE > 0.03.
- Commit: `feat(metrics): BSS and dual-ECE gate metrics with reliability data`

**3. Drift canary (`canary.py` new; header hook in `app.py`)**
- Reads `data/requests.jsonl`; window rule: n≥300 hops OR 7 days, whichever later. Trips when: escalate rate >1pp worse than rules rows in window, OR BSS ≤ 0, OR either ECE > 0.03 (metrics from task 2). Writes `data/drift_status.json` `{tripped, reasons[], window}` daily + on demand.
- On trip: new hops get `reason_codes += ["retrain_drift"]` and ops posture = stay rules-default (no live trained flip).
- Refs: spec §Catalog drift and retrain; `app.py:_router_headers` L744–782.
- QA: `python scripts/check_canary.py` — synthetic JSONL with 300 worsening hops → tripped; clean window → not tripped.
- Commit: `feat(canary): drift canary over production JSONL with retrain_drift signaling`

**4. Retune holdout + medium search (`train.py`)**
- CLI `train.py retune --dense data/tune.jsonl`: loads tune split (n≥300, disjoint from sparse-train, dense/cal, 3×5 smoke, and promotion data), searches (threshold, max_regret) on grid minimizing list USD subject to escalate-rate ≥ rules − 1pp AND bootstrap-resolve ≥ rules − 1pp. Fit **medium only**; derive low/high/max via Pioneer offsets Δ(−0.05,+0.10)/(+0.10,−0.05)/(+0.50,−0.17), clamp [0,1], walk to restore t_low ≤ t_med ≤ t_high ≤ t_max and r reversed.
- Emit `trained_effort:` YAML fragment; never edit spec files.
- QA: `python scripts/check_retune.py` — synthetic tune rows where rules misses; assert fitted medium satisfies constraint or script refuses (spec: cannot meet constraint → do not promote path).
- Commit: `feat(train): threshold-tuning-split retune with pioneer offsets and monotonicity walk`

**5. Retrain orchestration (`retrain.py` new)**
- `python -m aiand_router.retrain --plan-only`: executes train → fit → cal-report → retune → writes `data/scorer.candidate.json` + `data/retrain_report.md`. Never sets `TRAINED_PATH=trained`; sets up shadow posture + prints the gate-check verdict line.
- Triggers per spec: new-id onboard flag, drift trip, operator. All dry-runnable.
- QA: run `--plan-only` against fixture rows; assert candidate artifact + report exist and `TRAINED_PATH` untouched.
- Commit: `feat(retrain): orchestration pipeline with shadow-ready candidate artifact`

**6. Multi-SWE-RL monitor (`canary.py` or `monitor.py`)**
- Per-hop language guess from JSONL (file extension in payload, path hints, `lang` tag if present; unknown ≠ non-Python; mixed with a Python source file = Python — spec rule). Non-Python share ≥ 20% over the drift window → `data/multi_swe_rl_status.json` `{recommend_ingest: true}`.
- QA: synthetic hop mix at 25% non-Python trips the recommendation; 10% does not.
- Commit: `feat(monitor): non-python hop share trigger for multi-swe-rl ingestion`

**7. Quality-first routing acceptance harness (`tests/` + `scripts/`) — premium-floor-aware**
- Drive via `create_app` + `TestClient` + FakeProvider per `tests/test_gateway.py` prior art; fixture scorer artifact with explicit per-model p_success values. Assertions:
  1. `effort=max`, frontier-bin fixture, K3 eligible, and only K3's silver prior clears `t_max`/`r_max` → served K3.
  2. `effort=max`, frontier-bin fixture, cheaper survivor ALSO clears `t_max` and sits within `r_max` of K3 → cheapest survivor served (cheapest-above-bar holds on max; no unconditional K3 worship).
  3. Default effort (medium), K3 present in catalog: K3 is absent from `candidates`/`p_success` keys entirely (premium floor gates K3 before the Scorer runs — locks the floor on both paths).
  4. `effort=max`, trivial-bin fixture, K3 and Flash priors both above `t_max`, Flash within `r_max` of K3 → Flash served (never select K3 when not needed).
  5. Cheap model clears threshold within max_regret of top (default effort) → cheapest served (cost discipline).
  6. Nothing clears the bar → `rule=fallback_declined`, fallback model, HTTP 200.
- QA: `pytest tests/` green (use the repo's existing test invocation exactly).
- Commit: `test(routing): quality-first behavior matrix incl K3 reach, K3-suppression, premium-floor lock`

**8. Spec-scale ingest wiring (`pool.py`, config)**
- Bake dump sources into an ingest profile: SWE-smith trajectories `tool` split, SWE-smith tasks, BFCL (≤15% of stratum n), SWE-bench-family + Multi-SWE-bench collision filter mandatory, per-instance license filter for any rebench row.
- `python -m aiand_router.pool ingest --profile spec`: downloads/parses locally (no credits), prints stratum histogram (bin × phase family × tools), collision drop count.
- QA: run ingest dry against a small fixture shard; assert collision filter removes known Verified instance_ids; histogram printed.
- Commit: `feat(pool): spec-scale ingest profile with mandatory collision filtering`

**9. Minimal SWE-bench-Lite session runner (`lite_runner.py` new; reuses train.py harness)**
- Fetch: first-N (default 30, cap 50) instance ids of the public `princeton-nlp/SWE-bench_Lite` split, cached under `data/lite_cache/` (stdlib `urllib` or `httpx` — already a dependency; NO new dependency for this alone). Deterministic seed/order pinned in code.
- Loop: flashlight-style discover→plan→edit→debug turns through the gateway (model `router/auto`), session outcome = F2P/P2P resolve via the existing tempdir pytest harness machinery (`train.py:_pytest_verify` L378–404 pattern) applied to the produced patch. **`resolved` is a lightweight harness-proxy signal, not swebench parity** — both bounded-gate arms share it, so the delta stays apples-to-apples; the real F2P/P2P harness is scoped in the runbook (task 19).
- Offline QA (no credits): fixture upstream serving canned Lite rows; assert runner emits one `{instance_id, resolved}` row per slice instance and respects the N cap.
- Commit: `feat(lite): minimal SWE-bench-lite session runner with resolve harness`

### Phase B

**10. Query pool build (no credits)**
- Sample per spec margins: bin 15/40/30/15, tools 75/25, family 30/25/15/15/10/5; occupied-stratum floor ≥ 20 (take-all below). Output `data/queries_spec.jsonl` + coverage report. Sized to the $8 teacher cap: ~4,000–5,000 rows at ~$0.0015/row incl. ≤25% escalate.
- **Split manifest (before any paid call)**: assign every pool id to exactly one of `sparse-train | dense/cal | tune | promotion-holdout` in `data/split_manifest.json`, computed deterministically (existing `sample_stratum(seed=0)` + `_read_queries(exclude=…)` machinery). Tasks 11–14 read the manifest and only spend within their assigned split.
- QA: coverage report shows all target strata with floors; projected teacher cost ≤ $8; manifest sums to the pool size with pairwise-disjoint split id sets.
- Commit: `chore(pool): spec-margin query pool with stratum coverage report`

**11. Teacher labeling (cap $8, stop-on-cap)**
- `AIAND_TRAIN=1 python -m aiand_router.train teacher --queries data/queries_spec.jsonl --out data/silver.jsonl` (existing CLI). Verify before first call: projected cost ≤ cap (rows × per-row estimate incl. escalate share); abort if spend file + projection would exceed.
- Cheap=Motif-3, escalate=GLM 5.2, temp 0, strict json_schema, label_confidence rule, AA-disagree rule (|p − aa/100| > 0.25), cache-first. Unlabeled stays unlabeled.
- QA: post-run audit script: escalate share ≤ 25%; silver row count; invalid-output count; spend delta ≤ $8.
- Commit: `chore(train): teacher silver at spec-margin scale (cost-capped)`

### Phase C

**12. Sparse gold run (cap $22, stop-on-cap)**
- n≈2,000 queries from `data/queries_spec.jsonl` (sample order stratified, cache resume) × anchors = Flash + Qwen3.6-27B + Kimi-K2.7-Code + DeepSeek-V4-Pro (when eligible; ≤4 completions/query). No K3. Short completions (~800 max output tokens). Success gold = gateway rule (no escalate + valid tools/JSON); pytest F2P/P2P harness where a dump provides it (else gateway rule, recorded).
- Output `data/gold_sparse.jsonl`; per-anchor coverage report; missing cell stays missing.
- QA: audit script asserts per-anchor counts, zero K3 rows, spend delta ≤ $22, harness-vs-gateway label counts reported.
- Commit: `chore(gold): sparse gold n≈2000 x 4 anchors (cost-capped, no K3)`

### Phase D

**13. Dense/cal slice (cap $4, stop-on-cap)**
- n≈300 held-out-from-train queries × every eligible model except K3 → `data/gold_dense.jsonl`. Disjoint from sparse-train, tune split, 3×5 smoke, and any promotion ids. Short completions (~800 max output tokens per cell) so n stays ≥300 within the cap.
- QA: full disjoint-set assertion; per-model coverage **n≥300 OR cap-stopped shortfall recorded** (achieved-n report; artifact keeps `not_spec_floors`) — pre-flight projection sets the target n to the largest value the $4 cap supports (Oracle arithmetic: 800-token output alone across the pricier five models ≈ the per-cell budget at n=300, so achievable n may land 200–280; that is honest shortfall, not a task failure), spend delta ≤ $4.
- Commit: `chore(gold): dense calibration slice n=300 (eligible except k3, capped completions)`

**14. Threshold-tune split (cap $4, stop-on-cap)**
- n≈300 held-out queries × anchors, ~800 max output tokens per cell, bootstrap resolve where harness exists (else gateway success gold, recorded) → `data/tune.jsonl`. Anchors-only is a **budget deviation** from the spec's every-eligible requirement; record it under the `not_spec_floors` label. QA disjointness enumerates the full set: sparse-train, dense/cal, 3×5 smoke, promotion ids.
- QA: full disjoint-set assertion; resolve label type recorded per row; spend delta ≤ $4.
- Commit: `chore(gold): threshold-tuning split n=300 with bootstrap resolve (anchors-only deviation recorded)`

### Phase E

**15. Fit Scorer (`train.py fit`)**
- Inputs: `gold_sparse` + `gold_dense` + `silver`. Gold-where-present + silver regularizer on unobserved cells only (λ small; spec). Bin head: teacher bins. P(success) heads: fit BOTH logistic and GBDT; keep the one with strictly better Brier on held-out observed gold (tie → logistic, simpler). **Calibration corpus = held-out dense/cal slice only** (dense cal observations ≈ 2,400 > 1000 → isotonic path expected per task-1 rule; sparse rows never enter calibration).
- Artifact `data/scorer.json` must carry: `label: bootstrap_partial`, `not_spec_floors`, `k3_prior: silver_only`, calibrator mode, feature list.
- QA: `python scripts/check_scorer_fit.py` — artifact loads; `score_eligible` returns p∈[0,1] for all eligible ids incl. K3; bin head emits one of the 4 bins; reliability JSON from task 2 written.
- Commit: `feat(scorer): fitted bootstrap_partial artifact with isotonic calibration`

**16. Retune medium + YAML override**
- Run task-4 CLI on `data/tune.jsonl`; apply `trained_effort:` to `config/models.yaml` (verify where `effort_knobs` reads `cfg["trained_effort"]` — scorer.py L228–233); verify monotonicity.
- QA: load app with override; per-effort headers show fitted numbers; medium within constraint or `do-not-promote` verdict recorded in report.
- Commit: `chore(config): retuned trained_effort from tuning split`

**17. Shadow run (≤ $2)**
- `TRAINED_PATH=shadow`, serve flashlight task suite plus any live traffic until ≥100 shadow hops; collect `trained_selected`, `trained_confidence`, `rules_cost_delta_usd`.
- QA: JSONL audit: ≥100 rows path=shadow with all contract fields; zero `scorer_down` rows — binary: any `scorer_down` row fails the task and routes to the diagnosing loop before task 18; `fallback_declined`-rate report included (observed, no bar — a fitted artifact that declines nearly everything is useless even if clean).
- Commit: `chore(shadow): 100+ shadow hops of fitted artifact`

**18. Bounded dual-metric gate (≤ $2, label: NOT the Verified gate)**
- Via task-9 runner: SWE-bench-Lite micro-slice (n=30 cap with fixed pinned ids) once as rules, once as trained; plus the repo flashlight suite.
- Report `data/bounded_gate_report.md`: quality (session gold / resolve delta vs rules) AND cost (rules_cost_delta) AND calibration (BSS, dual ECE from hops). Promotion verdict formula = quality ≥ rules − 1pp AND cost delta < 0 AND BSS > 0 AND ECE ≤ 0.03. **The verdict feeds the runbook only and never flips `TRAINED_PATH`**; n below the spec floor → verdict line must read `bounded_check_only`.
- QA: report exists with all three metric families; phrase `bounded_check_only` present; no Verified overclaim.
- Commit: `chore(gate): bounded dual-metric check (not the verified gate)`

**19. Handoff runbook (`docs/runbook-production.md`)**
- Sections: (a) full Verified (500) gate — dataset pin, exact commands, pass bars, cost estimate formula; (b) aiand-infra flywheel log store — JSONL contract fields (from `app.py:_jsonl_row`), retention-to-next-retrain, redaction; (c) embed-ablation execution (Nebius Qwen3-Embedding commands, keep-iff gate: Brier strictly better AND ECE not worse, distill into features-only hop if kept); (d) K3 dense-gold onboarding steps (dense slice incl. K3, n≥300).
- QA: every command in the doc exists in the repo; cost formulas reference README list prices.
- Commit: `docs(runbook): verified gate, flywheel store, embed ablation, k3 onboarding`

**Final verification wave**

- [ ] F1. Repo test suite green with `TRAINED_PATH` covering off/shadow/trained fixtures; behavior matrix (task 7) passing.
- [ ] F2. Spend ledger: `data/spend.txt` end-state ≤ $50.00 total plan spend; per-phase caps audited from ledger deltas.
- [ ] F3. Routing behavior on the fixture harness (task 7): effort=max frontier → K3 when eligible and alone clears; trivial at max → never K3 when a within-regret cheaper survivor exists; default effort → K3 absent from candidates; decline → fallback (evidence: test/JSONL excerpts). On the FITTED artifact, K3-at-max behavior is recorded as-observed (not asserted live: per spec catalog-drift, silver-only ids don't unstick live trained picks until K3 dense gold — task 19d).
- [ ] F4. Calibration report: BSS > 0, equal-width ECE (M=10) ≤ 0.03 and equal-mass ECE ≤ 0.03 on the held-out dense slice; reliability JSON attached.
- [ ] F5. Artifact honesty: `bootstrap_partial` + `not_spec_floors` + `k3_prior: silver_only` labels present; grep proves no invented savings % in README/reports.
- [ ] F6. Runbook completeness: all four sections present, every referenced command exists in-repo.
- [ ] F7. Serving posture unchanged: default `TRAINED_PATH` and config defaults identical to plan start (bounded verdict never flipped live serving).

## Dependency Graph

A1–A9 independent of credits; A8 → B10 (feed pool); B10 → B11; B11 → C12, D13, D14 (silver alongside gold fits); A9 → E18; C12 + D13 → E15; D14 → E16; E15 + E16 → E17; E17 → E18; E18 → E19 (report numbers feed runbook); F-wave last.

## Span of Control

- Read before editing: none (new-module tasks create files; editing tasks were read this session: `train.py`, `scorer.py`, `app.py`, `pool.py`, `geometry.py`).
- No delegate edits to product code beyond task scope; tests via existing `tests/test_gateway.py` seam (FakeProvider + TestClient).
- Paid steps print projected cost + remaining cap before the first call and refuse to exceed.

## Must NOT Have (explicit)

- K3 gold completions at this budget; K3 live promotion claim.
- Verified (500) gate execution; Lite as substitute-after-Verified claims.
- `xhigh` effort rung; raw `x-routing-threshold`/`x-routing-max-regret` headers.
- Live embed on the hop; Rec B; chat model on the serve path; local model downloads.
- Second shadow JSONL file; invented savings %; promoting `bootstrap_partial` past shadow.
- Any relaxed premium floor or special-case that lets K3 through below `effort=max` (floor is locked by task 7 row 3 on both paths).
- Rerouting flops caused by missing fallbacks: decline must always return 200 on the fallback model.

## Review Log

- 2026-08-15 Momus round 1: REQUEST_CHANGES — M1 (K3-reach row contradicted premium floor at non-max effort) fixed via premium-floor-aware matrix (rows 1–4) + design note; M2 (no Lite session runner existed) fixed by adding task 9; MINORs 1–7 fixed (task-10 arithmetic sentence, 800-token caps on tasks 13–14, anchors-only deviation clause + full disjoint-set enumeration on task 14, dense-only calibration corpus parenthetical on task 15, binary scorer_down QA on task 17 / renumbered, trivial/max row with within-regret fixture).
- 2026-08-15 Momus round 2: **APPROVED** — both MAJORs and all 7 MINORs verified fixed; renumbering and cross-refs traced. Two non-blocking advisories applied into task 9 (httpx/urllib wording; harness-proxy fidelity sentence for `resolved`).
- 2026-08-15 Oracle: **GO** conditional on 7 amendments — all applied: cap-stopped dense-n QA (task 13), pre-spend split manifest (task 10), fixture-pinned F3 with as-observed fitted behavior + catalog-drift note, per-phase cap mechanism `BUDGET_LIMIT_USD = total_before + phase_cap` (invariant 3), prior-spend ambiguity note ($8.16 in NOTES.md; plan-incremental assumption, F2 audits deltas), decline-rate report (task 17), verdict-feeds-runbook-only wording + F7 posture check (task 18 / F-wave).
