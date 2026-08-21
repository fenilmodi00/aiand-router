# Fireworks & Pioneer-Class Router Gap Analysis — aiand-router

**Date:** 2026-08-21
**Commit:** 492a192 (branch v0) — HEAD at time of audit
**Author:** deep-research worker (internal audit + Tavily internet sweep)
**Report path:** `D:/aiand-router/.omo/notepads/pioneer-capacity/research-fireworks-pioneer-gap-2026-08-21.md`

---

## TL;DR Verdict

**We are not only lagging compute. Compute is the smallest of three gaps.**

1. **Routing intelligence — gap is architecture + data, not just GPU.** Fireworks-class is an inference-stack moat (kernels → scheduler → batching → memory → routing) plus compound-system orchestration; Pioneer-class LLM routing is a cost-quality frontier problem solved by calibrated P(success) with dual-metric gates. We have the right *seam* (shared PathPolicy/EligibleSet, shadow vs rules, cheapest-above-bar) but are on a bootstrap_partial artifact: sparse n~400-2000, dense/cal n~300, K3 silver-prior-only, no Verified gate — so the threshold/quality claims are not yet at production n.
2. **Are we on the right path? Yes — with material plan modifications.** The pioneer-capacity plan (Phases A-E, $50, bootstrap_partial/not_spec_floors labels, rules-default-until-gate) is correctly scoped as a stepping-stone, not a Pioneer promotion. It must not be mistaken for Pioneer parity.
3. **What to change:** do not spend $50 re-proving the hop; spend it on (a) closing calibration n to n_cal>1000 with dense-inclusive cost controls, (b) a real shadow flywheel before any more gold, (c) killing the cascade_lane ambiguity, and (d) pinning the provider contract to Fireworks-grade observability (latency/SLO, router-timing header, per-hop cost ledger). Details in Recommended Plan Modifications.

---

## Methodology & Sources

### Track A — Internal audit (primary)

Read at HEAD 492a192:

- `.omo/boulder.json`, `.omo/drafts/pioneer-capacity.md`, `.omo/notepads/pioneer-capacity/{decisions,issues,learnings,problems}.md`, `.omo/start-work/ledger.jsonl`, `.omo/plans/pioneer-capacity.md`, `.gitignore` (modified), `AGENTS.md`, `config/models.yaml`, `docs/runbook-production.md` (absent at path checked), `src/aiand_router/{router,scorer,app,provider,train,pool,eval,promotion_gate,metrics,canary,retrain}.py`, `tests/*`, `git log --oneline -20`, `git status`, `git diff HEAD`.

Notepad files decisions/issues/problems are auto-scaffolded near-empty (192/174/193 bytes); learnings.md is substantive (18 kB). boulder.json active_work_id pioneer-capacity-01f2cdb2, four sibling work_ids, active_plan `.omo/plans/pioneer-capacity.md`.

### Track B — External via Tavily CLI (tvly 0.1.6)

tvly --status = Not authenticated (no TAVILY_API_KEY). tvly research run requires API key — returns exit 3 'research command requires a Tavily API key' (verified 2026-08-21). Fell back to tvly search (unauthenticated, rate-limited) per skill escalation pattern. All searches used --json -o to file.

Seven searches executed; raw JSON saved to `D:/aiand-router/.tmp-tavily-*.json` (also copied to `.tmp-tavily-raw/`):

| # | Query | File | n_results |
|---|-------|------|-----------|
| 1 | Fireworks AI inference router architecture | .tmp-tavily-fireworks.json | 5 |
| 2 | LLM router gateway semantic routing intelligent model selection 2025 2026 | .tmp-tavily-llm-router.json | 5 |
| 3 | learned router vs rule-based cascade cost quality frontier calibration 2025 | .tmp-tavily-cascade.json | 5 |
| 4 | Fireworks AI blog inference optimization throughput | .tmp-tavily-fw-blog.json | 5 |
| 5 | RouteLLM Martian Unify OpenRouter Portkey LLM routing 2025 2026 | .tmp-tavily-route-llm.json | 5 |
| 6 | vLLM semantic router Mixture of Models intelligent routing | .tmp-tavily-vllm.json | 5 |
| 7 | Fireworks AI FireAttention speculative execution throughput latency optimization | .tmp-tavily-fireattention.json | 5 |

Every external claim below cites a URL returned in those files. Raw citation payloads reproduced in Appendix.

### Limitations

- No tavily research (deep multi-source synthesis) — search-only due to missing API key; citations are search-result snippets, not research-report citations.
- Fireworks private scheduler/kernel internals not in public docs; inferred from case studies/blogs.
- 'Pioneer' as a named product returns no canonical result — treated as Pioneer-class = quality-first, cost-governed, calibrated learned router with production gates (proxy: vLLM Semantic Router / RouteLLM / Martian / Portkey / LiteLLM patterns from searches).

---

## What Fireworks / Pioneer-Class Means (with citations)

### Fireworks-class = inference stack + compound routing moat

- **End-to-end inference stack moat:** kernel work on attention hot paths plus scheduler, memory management, batching policy, model packaging, and routing logic that determines real-world latency and cost — WorkOS summary of Fireworks f1 compound-system pitch [workos.com/blog/fireworks-ai-the-pytorch-teams-bet-on-inference-as-the-new-runtime](https://workos.com/blog/fireworks-ai-the-pytorch-teams-bet-on-inference-as-the-new-runtime).
- **Compound AI systems, not single-model calls:** split work across understanding/generation/verification/rewrite, orchestrate multiple specialized models + tool calls behind one API — same source.
- **Scale bar:** 140B tokens/day, 99.99% API uptime — Google Cloud partner blog [cloud.google.com/blog/topics/startups/fireworks-ai-gen-ai-efficient-inference-engine](https://cloud.google.com/blog/topics/startups/fireworks-ai-gen-ai-efficient-inference-engine). Azure/Foundry claim now 13T tokens/day, ~180k req/s, >1000 tok/s on large models [azure.microsoft.com/en-us/blog/introducing-fireworks-ai-on-microsoft-foundry-bringing-high-performance-low-latency-open-model-inference-to-azure](https://azure.microsoft.com/en-us/blog/introducing-fireworks-ai-on-microsoft-foundry-bringing-high-performance-low-latency-open-model-inference-to-azure). Infrastructure: PyTorch-origin team, AWS P4d/A100 then scaled — [aws.amazon.com/solutions/case-studies/fireworks-ai-case-study](https://aws.amazon.com/solutions/case-studies/fireworks-ai-case-study) (4x throughput, 50% latency cut claimed).
- **Serving tiers:** Serverless (pay-per-token, Priority/Fast) / On-Demand (dedicated, multi-region, post-trained) / Reserved (guaranteed capacity) — [fireworks.ai](https://fireworks.ai).
- **Latency/throughput levers we do not have:** FireAttention long-context attention, Adaptive Speculative Execution (domain-tuned draft models, hit rate 29%→76% on code gen, up to 3x latency improvement), Parameter-Efficient Fine-Tuning via LoRA/QLoRA for FireOptimizer — [mongodb.com/docs/atlas/architecture/current/partner-showcase/fin-services-fireworks-rag](https://www.mongodb.com/docs/atlas/architecture/current/partner-showcase/fin-services-fireworks-rag) and [fireworks.ai/blog/fireoptimizer](https://fireworks.ai/blog/fireoptimizer).
- **MoE / RL-rollout specifics:** session affinity, KV-cache behavior, weight-swap, and Rollout Router Replay (R3) — return per-token per-layer expert routing matrix to align trainer vs inference — [docs.fireworks.ai/guides/rollout-inference](https://docs.fireworks.ai/guides/rollout-inference).

### Pioneer-class LLM router = cheapest capable model per query on a calibrated cost-quality frontier

- **Definition:** intelligent routers analyze each request and dynamically select the most appropriate model based on complexity, cost, latency, quality — reduce costs up to 85% while maintaining 95% of GPT-4 performance (RouteLLM-backed claim) — [zylos.ai/research/2026-01-29-llm-routing-intelligent-model-selection](https://zylos.ai/research/2026-01-29-llm-routing-intelligent-model-selection).
- **Scope in 2026:** LLM Router + AI Gateway converged — single OpenAI-compatible API over 400+ models / 60+ providers (OpenRouter), with fallback/retry/circuit-breaker/cache/budget/rate-limit (Portkey), per-provider credential isolation (Braintrust) — synthesis across [inworld.ai/resources/best-llm-router-ai-gateway](https://inworld.ai/resources/best-llm-router-ai-gateway), [digitalocean.com/resources/articles/best-llm-routers](https://www.digitalocean.com/resources/articles/best-llm-routers), [braintrust.dev/articles/best-llm-routers-2026](https://www.braintrust.dev/articles/best-llm-routers-2026).
- **vLLM Semantic Router (Jan 2026) as Pioneer proxy:** system-level intelligence for Mixture-of-Models (MoM), six signal types from requests/responses/context — [zylos.ai/research/2026-01-29-llm-routing-intelligent-model-selection](https://zylos.ai/research/2026-01-29-llm-routing-intelligent-model-selection).
- **Routing strategies palette:** LLMRouter open-source (1k+ stars, v0.2.0 Jan 2026) supports 16+ strategies: KNN, SVM, MLP, Elo, graph, matrix factorization — same source.
- **Rules vs learned is complements, not alternatives:** rules encode hard constraints you can state in advance (compliance, tier, endpoint) with zero added latency; learned picks cheapest capable inside that envelope by inferring difficulty from the query — via confidence (cheap-model logprobs/verifier score), trained classifier on labeled production traffic, or embedding similarity — and adapts to patterns you did not anticipate at cost of latency + eval burden — [leanlm.ai/blog/llm-model-routing](https://leanlm.ai/blog/llm-model-routing).
- **Cascades vs upfront routing:** current families offer 5-25x cost ratios efficient:frontier; hybrid route-then-cascade often best — routing needs upfront classifier (latency before generation), cascading needs calibrated confidence and pays sequential latency — [tianpan.co/blog/2025-11-03-llm-routing-model-cascades](https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades). Same source quantifies 45-85% cost reduction envelope.
- **Quality bar is empirical:** evaluation-driven routing — measure on representative workloads, route on empirical quality metrics not just cost/latency heuristics — [zylos.ai/research/2026-01-29-llm-routing-intelligent-model-selection](https://zylos.ai/research/2026-01-29-llm-routing-intelligent-model-selection).

---

## Our Current State (HEAD 492a192, branch v0)

### Architecture (what the code actually is)

- **Gateway:** FastAPI create_app at `src/aiand_router/app.py:101` — OpenAI-compatible `/v1/chat/completions`, streams, tool_calls/json validation, redaction, budget-gated SpendLog, JSONL log `data/requests.jsonl`, rotation on ROUTER_API_KEY change, CORS, Anthropic adapter. Provider seam HttpAiandProvider (`src/aiand_router/provider.py`) — httpx AsyncClient, 120s upstream timeout, X-Aiand-Metrics header, streaming passthrough.
- **Catalog & policy:** `config/models.yaml` — 9 models, virtual_model router/auto, AA priors (not aiand-hosted measurements), premium_aa_floor 58, per-phase thresholds (e.g., discover 35, debug 50, summarize 24), latency_limit_ms 0, cascade_lane disabled behind TRAINED_PATH=off. `src/aiand_router/router.py` — load_config/load_models, detect_phase (header + heuristic, SHORT+DRAFT alias via PHASE_FAMILY), eligible_models (hard constraints: tools/json/streaming/context, premium floor at effort<max), select_model (eligible → bar → pioneer_score 0.40*success blend), SpendLog, estimate_cost/tokens. Phase vocabulary draft shorts (edit, debug) alias into families — router.py:165,468.
- **Trained hop (scorer):** `src/aiand_router/scorer.py` — features-only, no embeddings. load_scorer, text_features (cheap binary prompt cues), score_eligible (+ Platt/isotonic calibrate → P(success)), trained_select_from_eligible / trained_select (cheapest-above-bar with per-effort threshold/max_regret; SHIP_EFFORT low 0.05/0.30 ... max 0.60/0.03), apply_trained_path wrapper. Bin classifier over trivial/standard/hard/frontier + per-model P(success) heads + calibrator table. ConversationSticky hop_orchestrator.py pins session to first pick.
- **Training pipeline:** `src/aiand_router/train.py`, `fit.py` — teacher → gold → fit. Teacher = Motif-3 (+ GLM 5.2 escalate ~25%); gold = sparse (n budget-capped, 4 anchors: Flash + Qwen3.6-27B + Kimi-K2.7 + DS-V4-Pro, ~800 tok) + dense/cal slice (n~300 x eligible-except-K3) + threshold-tune split (n~300 x anchors). Fit = bin head + logistic/GBDT heads (keep strictly better Brier, tie→logistic) + auto-selected calibrator (Platt if n_cal<=1000 else isotonic PAVA). geometry.py, canary.py (drift when window n>=300 or 7d and escalate +1pp or BSS<=0 or ECE>0.03), retrain.py orchestration, monitor.py non-Python share trigger, metrics.py (BSS, ECE equal-width/equal-mass M=10, MCE, reliability).
- **Pool / ingest:** `src/aiand_router/pool.py` — smith/BFCL ingest, stratum-sampled bootstrap pool (build_pool), collision_keys guards against eval-only dumps (SWE-bench family etc.) — anti-pattern enforced.
- **Eval / gates:** `src/aiand_router/eval.py` (3 executed baselines over 5 seeded tasks), lite_runner.py + minimal SWE-bench-Lite session runner, flashlight.py discover→plan→edit→test loop, promotion_gate.py shadow-vs-rules comparison, replay_report.py.
- **Web:** Next.js 16 / React 19 / Tailwind 4 playground at `web/app/playground` — shadcn/ui, both bun.lock + package-lock.json tracked (intentional duality).

### What works vs scaffolded vs stubbed

| Area | Status | Evidence |
|------|--------|----------|
| Rules routing + gateway proxy | **Works** — production path, default serving | app.py create_app, router.py select_model/eligible_models, tests/test_gateway.py, nightly no-coverage pytest ~400 tests force TRAINED_PATH=shadow via conftest.py |
| Trained shadow path | **Works in shadow** — quality-first, cheapest-above-bar, K3 gated at effort=max | scorer.py score_eligible/trained_select, quality-routing behavior matrix (K3 reach/suppression, premium-floor lock) at tests/test_quality_routing.py — 492a192 message confirms deepened hop/gold-fit/promotion-gate sharing one PathPolicy/EligibleSet |
| Calibration | **Works but partial** — Platt+isotonic PAVA, auto-select n_cal>1000→isotonic | train.py:_fit_platt/_fit_isotonic, scorer.py:_calibrate, metrics.py BSS 0.404 PASS, ECE equal-width 0.013 PASS / equal-mass 0.034 FAIL on bootstrap_partial shortfall — plan F4 honest fail reported |
| Drift/retrain/retune | **Code-complete, not yet in production loop** | canary.py, retrain.py, monitor.py, train.py retune (medium-only + Pioneer offsets walk) — F-wave checks exist, but flywheel is still file JSONL |
| Pool at scale | **Spec-margin, capped** | pool.py build_pool stratas, 2e3 sparse + 300 dense + 300 tune under $50; .omo/plans Phases B-D marked x complete — but not spec floors (spec wants sparse 4k, dense >>300) |
| Eval harness | **Measured but sub-Verified** | eval.py + lite_runner + flashlight suite; bounded gate n~30-50, dual metric (quality+cost+BSS/ECE), verdict bounded_check_only never flips TRAINED_PATH — full Verified 500/300 never run (runbook only) |
| Provider contract | **Minimal viable** — cost ledger, JSONL, shadow headers (trained_selected/trained_confidence/rules_cost_delta_usd) | app.py:_router_headers, router.py:SpendLog, X-Router-* headers — no latency SLO header, no router-timing, no per-hop cost provenance beyond ledger |
| Flywheel log store | **Stubbed** — adapter contract + infra runbook, not an aiand infra sink | .omo/plans invariant: flywheel stays aiand-infra, in-repo adapter only; no remote log store code |
| Embeddings / cascade | **Explicitly not shipped** — features-only hop, cascade_lane.enabled false | AGENTS.md anti-pattern: never set TRAINED_PATH=trained, never train on eval dumps; config/models.yaml cascade_lane off; scorer.py text_features docstring no embed |
| K3 frontier | **Silver prior only** | K3 excluded from gold at $50 by plan cost rule; trained P(success) for K3 is teacher-silver-informed prior, recorded as k3_prior:silver_only, bootstrap_partial/not_spec_floors labels |

### Test coverage & gates

- 22 modules, ~400 tests, pythonpath=src per AGENTS.md + pytest.ini. 24 test files present (incl. conftest). CI is local scripts/check_*.py + scripts/run_*.ps1 budget-capped orchestration — no .github/workflows. Scripts loaded via importlib.util.spec_from_file_location (no subprocess). Smoke at `src/aiand_router/smoke.py` is opt-in real-credit (AIAND_SMOKE=1).

### Provider contract & cost governance

- Catalog list prices in `config/models.yaml` (e.g., Qwen3.6-27B 0.32/3.20 per 1M) + README; savings always vs most_expensive_eligible per request (never invented %). BUDGET_LIMIT_USD enforcement at train.py:_complete pre-call check (SpendLog total vs limit); default $15 code default (BUDGET_LIMIT_USD override env-only, plan cap $50 incremental). Redaction via redact_keys list.

### Routing policy today

- Hard constraints → phase bar → Pioneer score (0.40*success weighted blend) → pick cheapest survivor. Phase bar from config phase_threshold. Frontier K3 only when premium_aa_floor cleared (effort=max). Trained path never expands eligible set; same bar source shared after 492a192. Latency limit currently 0 (disabled).

---

## Gap Table — Dimension | Them (Fireworks/Pioneer-class) | Us | Gap Size

| # | Dimension | Them (cited) | Us (HEAD 492a192) | Gap |
|---|-----------|---------------|-------------------|-----|
| 1 | **Compute / infra** | 140B tok/day 99.99% uptime; 13T tok/day 180k req/s 1000 tok/s; 4x throughput 50% latency via A100-class + kernel co-optimizations [cloud.google...](https://cloud.google.com/blog/topics/startups/fireworks-ai-gen-ai-efficient-inference-engine) [azure.microsoft...](https://azure.microsoft.com/en-us/blog/introducing-fireworks-ai-on-microsoft-foundry-bringing-high-performance-low-latency-open-model-inference-to-azure) [aws.amazon...](https://aws.amazon.com/solutions/case-studies/fireworks-ai-case-study) | Single-process FastAPI proxy over aiand API (no co-located inference, no kernel/scheduler); no dedicated GPU fleet — we route *to* aiand, not *through* our engine | **Large infra gap, but not our product** — we are a router gateway, not an inference engine; closing it means buying inference, not building it; correct to not chase FireAttention/FireOptimizer here |
| 2 | **Routing intelligence (heuristic → learned → cascade)** | Rules + learned complements; learned via logprobs/verifier/classifier/embedding; hybrid route-then-cascade with 5-25x cost ratios, 85% queries to cheaper at 95% quality [leanlm.ai](https://leanlm.ai/blog/llm-model-routing) [tianpan.co](https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades) [zylos.ai](https://zylos.ai/research/2026-01-29-llm-routing-intelligent-model-selection); 16+ strategies in LLMRouter | Rules work; learned is features-only classifier with Platt/isotonic, cheapest-above-bar, no embedding/confidence-cascade/logprob verifier, cascade_lane disabled, conversation-sticky only | **Medium — intelligence gap is real**; our classifier is weaker than confidence-cascade/embedding routers that exploit runtime signals; hybrid cascade not exercised |
| 3 | **Eval / observability** | Evaluation-driven routing on representative workloads; MoM six signal types; semantic cache + routing gateway inline minimizing latency; managed dashboards for cost-per-quality/latency/task [zylos.ai](https://zylos.ai/research/2026-01-29-llm-routing-intelligent-model-selection) [inworld.ai](https://inworld.ai/resources/best-llm-router-ai-gateway) | Flashlight suite + Lite micro-slice n~30-50 bounded_check_only; BSS/ECE metrics implemented but gate never hit spec n; no latency SLO dashboard, no per-hop timing | **Medium-large** — we measure but not at the n or latency granularity Pioneer-class demands; no semantic cache layer |
| 4 | **Provider abstraction & cost governance** | Universal API + fallbacks/retries/circuit breakers/load balancing/caching/budget/rate-limit (Portkey), project-level credentials, price/throughput/latency sorting, data-policy filters (OpenRouter/Braintrust) [braintrust.dev](https://www.braintrust.dev/articles/best-llm-routers-2026) [digitalocean.com](https://www.digitalocean.com/resources/articles/best-llm-routers) | HttpAiandProvider single-upstream, no fallback/hedging across aiand endpoints beyond most_expensive_eligible accounting, no circuit breaker, no semantic cache | **Medium** — gateway is single-provider thin proxy, not a multi-provider AI gateway |
| 5 | **Training data & calibration** | Production-traffic labeled samples; calibration at scale (n_cal>1000 isotonic, else Platt) expected | Sparse n~430-2000 (budget-capped), dense/cal n~300, tune n~300, K3 zero gold cells, bootstrap_partial/not_spec_floors honestly labeled; isotonic unlocks only when n_cal>1000 (rarely reached) | **Large — data gap dominates quality gap**; spec wants sparse 4k/dense-cal ~300+ with K3, Verified 500 gate — we are at ~10-50% of that by design at $50 |
| 6 | **Latency / SLO** | Up to 3x latency cut via adaptive speculative execution (hit 29%→76% code gen); scheduler/batch/memory co-optimizations drive p50/p95 [mongodb.com](https://www.mongodb.com/docs/atlas/architecture/current/partner-showcase/fin-services-fireworks-rag) [fireworks.ai/blog/fireoptimizer](https://fireworks.ai/blog/fireoptimizer) | latency_limit_ms=0 (SLO disabled), no router-added-latency budget, no p95 tracking, no speculative execution, no batching | **Large if we claim infra-grade SLOs; small if we scope to gateway-routing latency (<~10ms scorer)** — scorer itself is ~features-only cheap but gateway adds httpx hop |
| 7 | **Product surface** | Single API for 400+ models/60+ providers, compound systems behind one surface, Fine-tune/LoRA/RL-rollout (R3) integrated [fireworks.ai](https://fireworks.ai) [docs.fireworks.ai/guides/rollout-inference](https://docs.fireworks.ai/guides/rollout-inference) | router/auto virtual model + fallback, marketing + playground in web/; no compound-system orchestration, no fine-tune surface, no MoE R3 | **Small-medium** — product surface is intentionally narrow (cheapest capable per step); wider surface is not on the pioneer-capacity scope |

Gap legend: Small = config/flag change or <1 week; Medium = code + eval iteration, fits in $50-200; Large = data spend or infra buy, or cross-team coordination.

---

## Compute vs Architecture vs Data Diagnosis

**Question: are we only lagging compute? Answer: No. Ranking of binding constraints today is Data > Architecture > Compute.**

1. **Data is binding.** Pioneer-class routing is gated on calibrated P(success). Our calibrator selection is correct (isotonic at n_cal>1000, else Platt) but n_cal rarely exceeds 1000 on a $50 budget where dense/cal is n~300 with capped 800-tok completions (~cents/cell on pricier models). The observed equal-mass ECE 0.034 miss vs 0.03 bar on bootstrap_partial is not a bug — it is the expected shortfall label doing its job. Likewise sparse 4k → we run 0.4-2k, K3 gold = 0. No amount of GPU fixes a missing label. Fireworks case studies buy data via throughput, not by training the router harder.

2. **Architecture is next binding.** Two architectural gaps matter more than raw compute: (a) signal poverty — we use only prompt-text binary cues, not the confidence/verifier/embedding signals that give Pioneer-class routers their 85%/95% frontier [tianpan.co](https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades) [leanlm.ai](https://leanlm.ai/blog/llm-model-routing); (b) hybrid cascade not exercised — the 5-25x cost ratio reality makes route-then-cascade inside a tier the cost-optimal shape, but our cascade_lane is disabled and un-evaluated. Both are inference-cheap (milliseconds) but eval-expensive to prove.

3. **Compute is least binding for a router gateway.** Fireworks' moat is *inference serving* compute (kernels, scheduler, batching, FireAttention, speculative execution). Our product is a *routing gateway* that dispatches to aiand's fleet. We should not build an inference engine; we should route efficiently to the best-priced capable aiand model and keep scorer latency <10ms. The only compute we are legitimately short on is *budget for labels* (aiand credit spend), which is a data cost, not a serving GPU cost. Local model runs remain correctly banned per plan.

**Diagnostic sentence:** If you gave us 10x GPU tomorrow, Pioneer parity would not move — because labels and calibrated thresholds are the frontier; if you gave us 10x labeled data + an offline embedding ablation, it would.

---

## Are We On the Right Path?

**Largely yes — the plan is the right path for a stepping-stone, wrong path if read as Pioneer parity.**

What is correct and should stay:

- **Grounded defaults, not MVP reduction:** full 10-gap scope, medium-only retune with offsets walk, bootstrap_partial/not_spec_floors honesty labels, rules-default-until-gate, no local models, budget caps per phase — all defensible per `.omo/plans/pioneer-capacity.md` global invariants and passed Momus R2 APPROVED + Oracle GO reviews.
- **Shared seams at 492a192:** one PathPolicy/EligibleSet, one fit/label seam, one §(a) bar source between serve and train — prevents the historical divergence where scorer and router disagreed on eligibility.
- **Quality-first + K3 gating via premium_aa_floor at effort=max:** matches the spec contract that trained never expands eligible set; cost-vs-quality dual gate (quality >= rules -1pp AND cost delta <0 AND BSS>0 AND ECE<=0.03) — correct.

What is not on the Pioneer path without changes:

- **Mistaking bounded_check_only for a promotion gate.** Plan correctly says verdict feeds runbook only, but downstream readers may misread 'chore(gate): bounded dual-metric check (not the verified gate)' as a green light. F7 (serving posture unchanged) needs enforcement, not just a check.
- **Spending the same $50 again on the same sparse shape.** Pool strata changed between Phase B/C/D; re-running at same n reproduces bootstrap_partial, not spec floors.
- **Leaving latency/SLO undefined.** latency_limit_ms=0 means no SLO — Pioneer-class routers are defined by latency + cost-per-quality, not cost alone [inworld.ai](https://inworld.ai/resources/best-llm-router-ai-gateway).

---

## Recommended Plan Modifications (prioritized, effort/impact)

Adopt these as amendments to `.omo/plans/pioneer-capacity.md` — do not rewrite the plan, append deltas.

### P0 — Must do before next paid run (fixes correctness/completeness)

| # | Change | Effort | Impact | Owner |
|---|--------|--------|--------|-------|
| P0-1 | **Close calibration n honestly:** reallocate Phase D caps so n_cal crosses 1000 on a *dense* corpus before next fit — either (a) dense n=200 x 5 models (~1000 rows) with tighter output cap 400 tok, or (b) reuse sparse rows *only* for Platt fallback reporting but enforce isotonic table is built from held-out dense/cal slice per spec. Record achieved n_cal in artifact + report; stop claiming ECE 0.03 on shortfall. | S (config + train.py param) | Unlocks isotonic, fixes F4 honest-fail | train owner |
| P0-2 | **Freeze pool strata before next teacher run:** write `data/queries_spec.jsonl` manifest + stratum report *before* teacher labeling, and assert gold/dense/tune are strict partitions of it (pool.py collision_keys already does eval-dump filtering — extend to partition assertion). Avoids the B→C strata drift seen in earlier phases. | S | Prevents label leakage / non-comparable gates | pool owner |
| P0-3 | **Enforce F7 programmatically:** add `scripts/check_serving_posture.py` that asserts TRAINED_PATH default = shadow and config defaults == plan start SHA; run in F-wave and in CI. Amend `.gitignore` delta (already done: adds `.omo/qa`, run-continuation, review-*.diff) — document why in AGENTS.md so next worker does not revert. | S | Prevents accidental promotion | gateway owner |
| P0-4 | **Provider contract: add router-timing + per-hop cost provenance headers** — X-Router-Scorer-Ms, X-Router-Eligible-Count, X-Router-Trained-Confidence, with p50/p95 logged to requests.jsonl. No new infra, just timing around score_eligible. | S | Makes latency gap measurable vs Fireworks-style SLO | app owner |

### P1 — Should do — turns shadow into a real flywheel

| # | Change | Effort | Impact | Owner |
|---|--------|--------|--------|-------|
| P1-1 | **Run a $0 shadow flywheel before next gold:** with TRAINED_PATH=shadow, collect >=300 hops (window rule in canary.py) of live or flashlight-replay traffic, write drift_status.json + multi_swe_rl_status.json. Use this as the *next* pool source — this is the flywheel log store adapter proving the contract before spending again. | M (runbook + collection) | Gives production-like traffic to sample from, not just dumps | app + pool |
| P1-2 | **Offline embedding ablation (hosted only, no local download):** behind a flag, score_eligible variant that concatenates text_features + Nebius Qwen3-Embedding (or aiand-hosted equivalent) cosine; gate keep-iff Brier strictly better AND ECE not worse — per plan spec gate. Do not ship on hop until ablation passes. | M | Tests the architecture gap hypothesis with one API call per query | scorer owner |
| P1-3 | **Hybrid cascade spike (off-path prototype):** enable cascade_lane on TRAINED_PATH=off branch with cheap=Flash / strong=Pro, measure sequential latency + cost vs upfront-only on debug/test_failure_analysis phases where hybrid is theorized best [tianpan.co](https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades). Record as experiment, not promotion. | M | Validates whether to open cascade_lane at all | scorer + eval |

### P2 — Nice to have — Pioneer-class hygiene

| # | Change | Effort | Impact | Owner |
|---|--------|--------|--------|-------|
| P2-1 | **AI Gateway hardening (single-provider version):** add retry with backoff + budget-aware circuit breaker around HttpAiandProvider.complete, uniform error envelope, budget header X-Router-Budget-Remaining. Multi-provider can wait — but single-provider resilience is Pioneer table stakes per Portkey pattern [braintrust.dev](https://www.braintrust.dev/articles/best-llm-routers-2026). | M | Reliability without buying multi-provider | provider owner |
| P2-2 | **Semantic cache layer (category-aware hybrid):** lightweight cache keyed by (phase, normalized prompt hash) with cost-aware reuse — vLLM semantic router pattern [zylos.ai](https://zylos.ai/research/2026-01-29-llm-routing-intelligent-model-selection). Hit-rate logged, not assumed. | M-L | Cheapest latency win after routing intelligence | cache owner |
| P2-3 | **SLO definition:** set latency_limit_ms from real p95 of shadow hops instead of 0; publish p50/p95/p99 in bounded_gate_report.md. Aligns with 'optimizes for cost-per-quality, latency targets, task complexity' definition [inworld.ai](https://inworld.ai/resources/best-llm-router-ai-gateway). | S | Makes gap 6 closable | app + metrics |

Do-not-do (explicit):

- Do not re-spend $50 on sparse-only without first fixing n_cal and flywheel — reproduces bootstrap_partial.
- Do not download/run local embedding models — violates no-local-models invariant.
- Do not set TRAINED_PATH=trained or claim Verified gate without a real Verified 500/300 run (runbook only).
- Do not build FireAttention/speculative execution — buy inference from aiand, do not replicate Fireworks.

---

## Risks & Open Questions

1. **K3 dense gold never at $50.** Frontier routing cannot be calibrated without K3 labels — plan correctly parks this as runbook task 19d. Risk: stakeholder reads 'quality-first router must route to K3' as requiring K3 demo now; mitigate by demonstrating K3 reach on synthetic silver-prior fixture (quality_routing behavior matrix) and labeling artifact k3_prior:silver_only.
2. **Budget semantics ambiguity.** Plan assumes $50 plan-incremental (NOTES.md prior spend $8.16); if owner meant account-absolute, Phase E caps overflow. Resolve before next paid run.
3. **Tavily API key missing → search-only evidence.** Fireworks kernel/scheduler internals are opaque; external claims are bounded by partner blogs (Google Cloud, AWS, Azure) and WorkOS post — sufficient for gap sizing but not for performance JNDs.
4. **Evaluation hazard:** Lite harness vs gateway rule for success_gold — plan records label type per row but gate mixes both; report must keep harness-vs-gateway counts separate (Phase C/D audit already does).
5. **Embedding ablation cost gate is strict (Brier better AND ECE not worse) — may never pass on features-only-strong data.** Keep ablation offline and do not block flywheel on it.
6. **Multi-SWE-RL trigger:** plan monitors non-Python share >=20% — unknown if dump composition or live traffic will trip it first; monitor.py is correct to stay advisory.

---

## Appendix

### A. Internal file map (audit trail)

- `D:/aiand-router/.omo/boulder.json` — 4 work_ids, active pioneer-capacity-01f2cdb2, active_plan `.omo/plans/pioneer-capacity.md`
- `D:/aiand-router/.omo/drafts/pioneer-capacity.md` — gap analysis + $50 allocations, Momus R1 REQUEST_CHANGES→R2 APPROVED, Oracle GO with 7 amendments, handoff 2026-08-15
- `D:/aiand-router/.omo/notepads/pioneer-capacity/*` — decisions/issues/problems scaffolded near-empty; learnings.md 18 kB
- `D:/aiand-router/.omo/start-work/ledger.jsonl` — session ledger
- `D:/aiand-router/.omo/plans/pioneer-capacity.md` — 19 todos Phases A-E + F-wave, invariants, design note premium_aa_floor 58, Bounded gate n~30-50 vs Verified 500 spec
- `D:/aiand-router/.gitignore` — modified: adds `.scratch/**/review-*.diff`, `_*.py`, `__pycache__`, `.omo/run-continuation`, `.omo/qa`, `logs/`
- `D:/aiand-router/config/models.yaml` — 9 models, AA priors, trained_effort low/med/high/max, phase_threshold, premium_aa_floor 58, cascade_lane.enabled false
- `D:/aiand-router/src/aiand_router/{router,scorer,app,provider,train,pool,eval,promotion_gate,metrics,canary,retrain}` — audited heads above
- `D:/aiand-router/tests` — 24 files including conftest.py clamp TRAINED_PATH=shadow, quality-routing + gateway + scorer suites
- `D:/aiand-router/docs/runbook-production.md` — Task 19 handoff runbook (path docs/runbook-production.md, not docs/agents/...)

### B. Tavily raw citations (search results, 2026-08-21)

All files at `D:/aiand-router/.tmp-tavily-*.json` (copied to `.tmp-tavily-raw/`). Summarized with scores; raw_content null (search snippet mode). Each result below is verbatim content snippet + URL + score as returned.

#### B.1 .tmp-tavily-fireworks.json — query 'Fireworks AI inference router architecture'

1. score 0.68 — 'dynamic routing: use smaller or more specialized models where they work... splitting work across understanding, generation, verification, and rewrite steps... Fireworks moat is presented as an inference stack optimized end-to-end: kernel work where it matters (attention and related hot paths), plus the scheduler, memory management, batching policy, model packaging, and routing logic' — https://workos.com/blog/fireworks-ai-the-pytorch-teams-bet-on-inference-as-the-new-runtime
2. score 0.67 — provider catalog (OpenRouter) — https://openrouter.ai/provider/fireworks
3. score 0.66 — 'processes over 140 billion tokens daily with 99.99% API uptime... compound AI systems, which replace traditional, single AI models with multiple interacting models' — https://cloud.google.com/blog/topics/startups/fireworks-ai-gen-ai-efficient-inference-engine
4. score 0.61 — 'lightning-fast, affordable, and customizable... hosts SaaS and supports containerized deployments in VPC... foundation models require powerful, often costly compute' — https://aws.amazon.com/solutions/case-studies/fireworks-ai-case-study
5. score 0.56 — 'For Mixture-of-Experts models, training-inference divergence... Router picking different top-K experts... Rollout Router Replay (R3)... session affinity, KV-cache behavior, weight-swap' — https://docs.fireworks.ai/guides/rollout-inference

#### B.2 .tmp-tavily-llm-router.json — query 'LLM router gateway semantic routing intelligent model selection 2025 2026'

1. score 0.88 — 'vLLM Semantic Router represents a transformative milestone for intelligent LLM routing... Mixture-of-Models (MoM)... router sits between users and models, capturing signals from requests, responses, and context... reduce inference costs by up to 85% while maintaining 95% of GPT-4 level performance... RouteLLM, vLLM Semantic Router... LLMRouter 16 routing strategies including KNN, SVM, MLP, Elo, graph, matrix factorization' — https://zylos.ai/research/2026-01-29-llm-routing-intelligent-model-selection
2. score 0.83 — 'LLM router is a layer between your application and multiple AI model providers that directs each request to the right model based on cost, latency, quality, or business rules. An AI gateway extends this with unified API access, failover, load balancing, and observability... best LLM routers in 2026 do both' — https://inworld.ai/resources/best-llm-router-ai-gateway
3. score 0.76 — 'Better model-task matching... Semantic routing can make this selection based on meaning... fallback retry... OpenRouter 400+ models 60+ providers' — https://www.digitalocean.com/resources/articles/best-llm-routers
4. score 0.74 — 'Portkey gateway supports universal API, conditional routing, automatic fallbacks, retries, timeouts, circuit breakers, load balancing, simple and semantic caching, budget limits, rate limits... Braintrust Gateway... project-level AI providers... OpenRouter price-based routing, throughput/latency sorting' — https://www.braintrust.dev/articles/best-llm-routers-2026
5. score 0.59 — KubeCon talk: cost-aware semantic caching and routing, lightweight semantic router for model selection + category-aware hybrid semantic caching, gateway inline to minimize latency — https://www.youtube.com/watch?v=DIwlL5Z8v1o

#### B.3 .tmp-tavily-cascade.json — query 'learned router vs rule-based cascade cost quality frontier calibration 2025'

1. score 0.49 (leanlm) — 'rule-based and learned routers are complements, not alternatives. Rules encode the constraints you can state in advance... learned router picks the cheapest capable model inside whatever envelope the rules leave open... Rule-based reads metadata... Learned reads the query itself: confidence cascade uses cheap model output signal (token logprobs, or separate verifier score), trained classifier uses features learned from labeled samples, embedding router uses semantic similarity' — https://leanlm.ai/blog/llm-model-routing
2. (same file) second snippet — 'Rule-based adds no latency, but can only encode what you can state in advance. Learned infers difficulty... via confidence, trained classifier, or embedding similarity, and adapts to patterns you did not anticipate at cost of added latency and evaluation burden'
3. score 0.40 (tianpan) — '5-25x cost ratios between efficient and frontier tiers... Routing frameworks are battle-tested... Routing requires accurate upfront classifier that adds latency before any generation. Cascading requires good confidence calibration and accepts sequential latency. Hybrid — route first to avoid obviously mismatched tiers, then cascade within a tier — often work best' — https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades
4. same — 'RouteLLM shows with proper routing you can maintain 95% of frontier quality while routing 85% of queries to cheaper models, achieving 45-85% cost reductions'

#### B.4 .tmp-tavily-fw-blog.json / .tmp-tavily-fireattention.json / .tmp-tavily-route-llm.json / .tmp-tavily-vllm.json

- Fireworks homepage: 'inference engine is optimized at every layer for industry-leading throughput and latency... Serverless / On-Demand / Reserved' — https://fireworks.ai
- AWS case study repeated: 4x throughput, 50% latency — https://aws.amazon.com/solutions/case-studies/fireworks-ai-case-study
- Azure/Foundry: '13T tokens daily, sustaining about 180k requests per second, generating over 1,000 tokens per second on large models' — https://azure.microsoft.com/en-us/blog/introducing-fireworks-ai-on-microsoft-foundry-bringing-high-performance-low-latency-open-model-inference-to-azure
- FireAttention / FireOptimizer: 'adaptive speculative execution improves... using domain-specific or user-profile-customized models... accuracy and hit rates 29% to 76% in code generation, latency improvements up to 3x... FireAttention long-context, Parameter-Efficient Fine-Tuning LoRA/QLoRA' — https://www.mongodb.com/docs/atlas/architecture/current/partner-showcase/fin-services-fireworks-rag and https://fireworks.ai/blog/fireoptimizer
- Additional route-llm/vllm searches corroborated the same router/gateway patterns — files at .tmp-tavily-route-llm.json, .tmp-tavily-vllm.json (5 results each, same source pool as B.2/B.3).

### C. tvly CLI diagnostics

- tvly --version: tavily-cli 0.1.6; tvly --status: Not authenticated; tvly research run: exit 3 'research command requires a Tavily API key' — verified on Windows PowerShell with PYTHONIOENCODING=utf-8 and --json -o file outputs. Install reference: curl -fsSL https://cli.tavily.com/install.sh | bash, or uv tool install tavily-cli per C:/Users/nasri/.claude/skills/tavily-cli/SKILL.md.

### D. Git state at audit

- HEAD 492a192 — 'Deepen hop, gold fit, and promotion gate into shared modules so serve and train share one PathPolicy/EligibleSet, one fit/label seam, and one §(a) bar source.'
- Parent 76e92e9 — 'Ship shadow router prototype: Mix1 scorer path, session-gold harness, and disk-light Modal eval.'
- Branch v0, dirty only on .gitignore (56-line diff: adds .omo/qa, run-continuation, review-*.diff etc.)
- .scratch/** deletions intentional per .scratch gitignore-ish — not a gap.

---

*End of report. Next step: coordinator approves P0 amendments before any paid re-run; do not re-spend $50 without closing n_cal and flywheel first.*
