# Spec: Authorized Fireworks FireRouter Reverse-Engineering & Comparative Open-Weights Router — Intern Research Task

**Status:** draft — ready-for-agent
**Owner:** Research intern (CEO written permission on file)
**Credits:** Fireworks $30 (primary) + Pioneer $20 (comparison), BUDGET_LIMIT_USD-enforced
**Depends on:** pioneer-capacity plan Phase A-E completed (isotonic, metrics, canary, retune, shadow gate) — this plan extends, does not replace

---

## Problem Statement

As a research intern tasked by the CEO with characterizing how Fireworks FireRouter routes open-weights inference, I need a reproducible, authorized method to measure FireRouter's behavior (difficulty routing, cache-aware cost decisions, x-routing-preference) side-by-side with Pioneer Router on the same open-weights provider inference tasks. Today the gateway only speaks aiand catalog models via aiand infra; there is no Fireworks provider adapter, no comparative probe harness, and no shared evaluation that proves "both doing same provider inference of open weights" on identical prompts with budget-capped truth. Without this, the research cannot show where the routers agree, where they diverge, and which wins on quality vs cost vs latency — and the $30 credits cannot be spent in a gate-able way.

## Solution

Extend the existing OpenAI-compatible gateway and trained-router machinery (leave the Pioneer-capacity behavior intact) with a dual-provider comparative layer: add a Fireworks provider adapter behind the same Decision contract, add a budget-capped comparative probe harness that drives both `pioneer/auto`-equivalent and `firerouter` paths through the *same* gateway seam using identical open-weights prompt suites, log both decisions to the same JSONL observability contract, fit a Fireworks-aware scorer calibration from the probe data, and emit a bounded comparative report (savings vs most_expensive_eligible, quality, latency, calibration). The current rules router stays default; the comparative work runs in `shadow` / dry-run posture and never flips `TRAINED_PATH=trained` without the existing promotion gate. CEO permission scope stays in writing; only aggregated curves are publishable.

## User Stories

1. As a research intern, I want to run `firerouter` and `router/auto` against the same prompts through one gateway, so that the comparison is apples-to-apples on provider inference.
2. As a research intern, I want to spend Fireworks $30 and Pioneer $20 without exceeding either cap, so that the task respects the credit limits and stops before overrun.
3. As a research intern, I want every probe hop logged with selected model, calibrated P(success) / confidence, rule (threshold / max_regret / fallback_declined), most_expensive_eligible, savings, and latency, so that cost vs quality is provable.
4. As a research intern, I want to sweep x-routing-preference (max-intelligence ↔ max-savings) and Pioneer effort presets (low/medium/high/max) on the same bucket, so that preference curves are comparable.
5. As a research intern, I want trivial / code_gen / refactor / security_review / long-debug buckets drawn from the existing seeded tasks and stratum-sampled pool, so that difficulty coverage matches the trained-router strata.
6. As a research intern, I want the probe harness to read API keys from env / auth.ini only and never log them, so that credential handling stays safe.
7. As an engineering manager, I want the existing gateway behavior (hard constraints → phase bar → Pioneer-score / trained-select) unchanged when the Fireworks adapter is off, so that current tests stay green.
8. As an evaluator, I want a comparative report that shows savings only vs most_expensive_eligible (never an invented %), plus quality (success gold / session gold) and calibration (BSS, dual ECE), so that "who wins most" is measured not claimed.
9. As a researcher, I want to see FireRouter's documented cache behavior (95%+ hit, half-price cached input) reflected in the cost math, so that Fireworks' compounding advantage is not missed.
10. As a researcher, I want to see Pioneer threshold + max_regret behavior reproduced locally, so that its quality bar is tunable and auditable.
11. As a researcher, I want a fail-closed guarantee (missing Anthropic key → routed request fails, not silent fallback) verified in the harness, so that FireRouter's documented safety is confirmed.
12. As a researcher, I want both routers' pass-through semantics (your Anthropic/OpenAI key forwarded, not stored server-side per docs) left untouched by the probe, so that the experiment does not simulate key storage.
13. As a researcher, I want to fit a Fireworks-aware scorer (same bin head + P(success) heads + isotonic/Platt auto-select) from probe gold, so that a locally-owned model can mimic FireRouter's difficulty decisions.
14. As a researcher, I want the fitted artifact labeled `bootstrap_partial` + `fireworks_probe` + `not_spec_floors` where sparse, so that provenance is explicit.
15. As a researcher, I want to compare on the shared open-weights subset (Kimi K3, GLM-5.2, DeepSeek family) where both providers overlap, so that provider inference differences are isolated.
16. As a researcher, I want to keep the existing premium floor (K3 gated behind effort=max) honored on both paths, so that the locked design choice is not broken.
17. As an operator, I want the drift canary to watch both provider streams (escalate rate, BSS, ECE) over n≥300 / 7 days, so that dataset drift trips retrain planning.
18. As an operator, I want the existing BUDGET_LIMIT_USD pre-call check to gate every paid probe batch, so that one batch cannot consume the next phase's budget.
19. As a compliance reviewer, I want the work to stay inside documented APIs + FireConnect repo (Apache-2.0) + my own credentialed traffic, so that CEO permission scope is not exceeded.
20. As a compliance reviewer, I want the spec to state that publishing raw provider outputs or scorer weights requires separate written approval, so that only aggregated curves are publishable by default.
21. As a future maintainer, I want wiki pages for FireRouter architecture and a Pioneer-vs-Fireworks comparison, so that findings compound.
22. As a future maintainer, I want the comparative probe to run offline / dry (fixture prompts, no credits) and still assert decision shapes, so that CI stays free.
23. As a cost owner, I want the report to price each model from the catalog list prices and log `most_expensive_eligible` per request, so that per-request audit is possible.
24. As a latency owner, I want per-hop latency recorded alongside routing decision, so that Fireworks' direct-infra vs Pioneer proxy latency can be compared.
25. As a harness runner, I want `x-allowed-models` to restrict both routers to the same allow-list in a run, so that pool differences do not confound results.

## Implementation Decisions

- **Reuse the Pioneer-capacity foundation — no rewrite.** Phases A-E (isotonic + Platt auto-select on n_cal, BSS/dual-ECE metrics, drift canary, threshold-tuning-split retune with Pioneer offsets, retrain orchestration, Lite runner) stay as built. This plan adds a provider adapter and a comparative harness; it does not change the rules-pick math or the eligible-set gating.

- **Single high seam for testing: the gateway Decision contract.** All verification drives through the gateway's OpenAI-compatible entry point plus its JSONL row and response headers (`X-Router-*`, `X-Router-Trained-Would`, `Decision.path/rule/reason_codes`, `most_expensive_eligible`). This is the highest seam that already covers rules, trained, shadow, and now Fireworks; no new low seams are introduced. Provider dispatch and scoring stay internal to that seam.

- **Provider adapter is a second backend behind the same eligibility policy.** The gateway gains a provider dispatch that can forward to aiand (existing) or Fireworks serverless (new) based on per-request provider selection, but both share the same hard-constraint filtering, phase detection, and `most_expensive_eligible` definition (list-price unit cost ranking). No catalog-wide price inventing.

- **FireRouter behavioral clone, not weight extraction.** The research reproduces routing *policy* (difficulty score → preference-weighted cheapest-above-bar with cache factor) via a fitted scorer trained on probe gold, using the same features-only + optional training-embed ablation pattern as the Pioneer scorer. No binary dumping, no private artifact scraping; only FireConnect open source and observation via documented endpoints.

- **Comparative probe harness is budget-capped and resumable.** The harness samples from the existing stratum-sampled pool (bin × phase family × tools) and seeded tasks, supports `--provider {aiand,fireworks,both}` and `--preference {low,medium,high,max}` sweeps, checks `data/spend.txt` total + phase projection before each batch (total-only pre-call; worst overshoot is one batch), and resumes from cached JSONL. Output is `data/{pioneer,fireworks}_probes.jsonl` with identical schema; missing cells stay missing.

- **Telemetry contract extension (additive only).** The JSONL row gains two optional fields — `provider: aiand | fireworks` and `routing_preference: max-intelligence | max-savings` plus `cache_hit: bool | null` when Fireworks reports it — alongside the existing `path, rule, p_success, candidates, most_expensive_eligible, savings_usd`. Existing readers ignore new fields.

- **Calibration stays corpus-disciplined.** Fitting uses probe-derived gold; calibration slice is a held-out dense-like subset of probe queries where multiple models were run, disjoint from train and threshold-tuning splits. Auto-select remains `n_cal ≤ 1000 → Platt else isotonic` per the pioneer-capacity decision. SourceRefs updated to include fireworks probe files.

- **Shadow posture for the comparative path.** The gateway serves the rules decision to the client while logging the Fireworks-would-have-picked vs Pioneer-would-have-picked side-by-side (`path=shadow` rows carry both `selected` and `compared_selected`). No live traffic flip without the bounded dual-metric gate (quality ≥ rules −1pp, cost delta <0, BSS>0, ECE≤0.03).

- **Language and domain vocabulary lock.** All code comments, docs, reason codes, and report prose use CONTEXT.md terms exactly (calibrated P(success), complexity bin, phase family, threshold, max regret, shadow, drift canary, success gold, silver P(success), named savings baseline). No renaming.

## Testing Decisions

- **What makes a good test:** assert external Decision behavior through the gateway seam (headers + JSONL row + HTTP 200 with model field preserved), not scorer internals; assert savings only vs most_expensive_eligible logged per request; assert calibration via held-out gold, not training loss; offline fixtures must pass without credits.

- **Modules to test:**
  - Gateway Decision contract + Fireworks adapter dispatch (eligibility, routing, headers, JSONL)
  - Comparative probe harness (stratified sampling, budget cap, resume, dual-provider logging)
  - Calibration metrics (BSS, dual ECE, reliability table) on probe-derived gold
  - Comparative report generation (dual-metric gate, cost vs frontier split)

- **Prior art reused:**
  - `tests/test_gateway.py` — TestClient + FakeProvider pattern for gateway matrix tests
  - `tests/test_bilinear_scorer.py` + `tests/test_geometry.py` — scorer shape + gold-matrix assertions
  - `tests/test_promotion_gate.py` — shadow vs rules cost delta pattern
  - `tests/test_pool.py` — collision filtering + stratum histogram
  - Existing `scripts/check_*.py` assert-based checks (isotonici, metrics, canary, retune)

- **New harness tests (behavior matrix, premium-floor-aware, provider-aware):**
  1. `effort=max` + frontier-bin + Fireworks eligible includes K3 → K3 served only when it alone clears threshold/max_regret; otherwise cheapest survivor within max_regret.
  2. Default effort with K3 in catalog → K3 absent from candidates (premium floor) on both providers.
  3. `x-routing-preference=max-savings` vs `max-intelligence` on same bucket → savings-leaning picks cheaper eligible when within max_regret; intelligence-leaning stays nearer top P(success).
  4. Missing Anthropic key for `firerouter` alias → fail-closed (error, not silent open-model fallback).
  5. Cache-hit probe row → cost math reflects half-price cached input.
  6. Budget cap projection exceeds `BUDGET_LIMIT_USD` → batch refuses before any provider call.

## Out of Scope

- Live `TRAINED_PATH=trained` flip for the comparative artifact — bounded gate only; full Verified (500) gate stays in the handoff runbook.
- K3 dense gold across all probe queries at $30 — cost cap makes this `not_spec_floors`; K3 trained P(success) stays silver-prior where unobserved.
- Local model downloads/runs, live embedding forward on the serve hop, Rec B, `xhigh` rung, or chat-teacher relabeling — all remain out per DESIGN.md and pioneer-capacity invariants.
- Second shadow file, multi-tenant control plane, hosting models on Modal, or inventing a savings % vs anything other than most_expensive_eligible.
- Decompilation, private container/image scraping, credential harvesting, or any undocumented endpoint brute-force — not authorized by CEO scope and not needed for behavioral cloning.
- SWE-bench Verified full gate, flywheel log store on infra, or production embed ablation — documented in the runbook only.

## Further Notes

- **Credits accounting:** treat `data/spend.txt` as the single ledger; run each paid phase with `BUDGET_LIMIT_USD = spend_before + phase_cap` (pioneer $20, fireworks $30 separate caps, plan-incremental; if CEO means account-absolute, state before Phase B). Record ledger deltas per phase.
- **Publishing boundary:** aggregated routing curves (`P(success)` vs actual pass, savings vs most_expensive_eligible, latency distributions) are publishable under the CEO letter; raw per-prompt model outputs, scorer weight tables, and full probe JSONL require explicit additional approval.
- **Already implemented (from pioneer-capacity):** isotonic calibration + auto-select, BSS/dual-ECE metrics, drift canary, retune holdout with Pioneer offsets, retrain orchestration, spec-scale pool ingest with collision filter, Lite runner, budget-gated teacher/sparse-gold/dense/cal flows. This plan composes on top of them.
- **Wiki compounding:** file probe findings to `.opencode/wiki/sources/fireworks-firerouter.md` and comparison to `concepts/routing-comparison.md` with cross-links `[[entities/gateway-app]]`, `[[entities/trained-scorer]]`, `[[concepts/effort-presets]]`.

