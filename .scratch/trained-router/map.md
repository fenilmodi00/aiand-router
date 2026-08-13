# Production trained coding router

Type: wayfinder:map
Status: resolved

## Destination

A **proposal-grade spec + go/no-go** the aiand team can staff and implement: an **aiand-owned trained router** over the **aiand catalog only**. Path: complexity bin → calibrated P(success) per eligible candidate → cheapest that clears threshold + max_regret. **Rules stay default + scorer-down / decline fallback.** Trained is **shadow then promote**. This repo is the reference prototype, not their multi-tenant control plane.

Artifact: [`spec.md`](spec.md) (GO to staff shadow→promote Rec A; NO-GO to replace rules / clone Pioneer / full-train from this repo).

## Notes

Domain: coding-agent model routing. Glossary: [`CONTEXT.md`](../../CONTEXT.md). Current rules path: `DESIGN.md`, `src/aiand_router/router.py`. Competitor dump: [`.scratch/competitor-router-research.md`](../competitor-router-research.md). Local verdict: [`.scratch/router-vs-pioneer-firerouter.md`](../router-vs-pioneer-firerouter.md).

Skills every session: `/wayfinder`, `/grilling`, `/domain-modeling`, `/research`. Do not implement the trained path in a charting or ticket session unless the ticket type is `task`/`prototype` and the map Notes say otherwise. Default remains **plan, don't do**.

Standing preferences (grilled):

- Algorithm + production envelope only (labels, calibration, fallback, observability, promotion, catalog drift). Not a Pioneer product clone.
- Same eligible set as rules; trained only scores/picks among survivors.
- Phase stays an optional hint; complexity is predicted; rules fallback still uses phase bars.
- Success label: per-request no-escalate (+ valid tools if tools present); promotion-gate gold is harness/flashlight outcome when present.
- Data: bootstrap (public/synthetic + this repo’s JSONL) **and** a production flywheel.
- Promotion: non-inferior quality, lower cost, trustworthy calibration. No invented savings %.
- Shadow required before any live trained pick.
- Live hop: in-process, ~&lt;10ms. Teacher is offline only. **No live embed**. **Scorer** is Rec A (gateway features + logistic/GBDT + Platt/temperature). Rec B (bilinear/MIRT) is not a spec door.
- Effort headers stay `low|medium|high|max` and only retune threshold + max_regret: v1 on the **threshold-tuning split**; later full retrains on a **production retune holdout**. \(t,r\) freeze between retrains. Trained pick is cheapest-above-bar, not max weighted score. No `xhigh` unless the team asks.
- Retrain: event + operator (new-id onboard, **drift canary**, or operator). No calendar/volume. Re-shadow + Verified re-gate. Drift trip → `path=rules` (`retrain_drift`) until replacement gates; operator/new-id keep previous trained.
- Observability: confidence (= winner P(success)), rule (`threshold` | `max_regret` | `fallback_declined`), reason_codes, savings vs a **named** baseline. No dashboard/playground requirement.
- New catalog models stay rules-only / prior-only until a **dense gold slice** including that id reaches n≥300. Teacher silver may train the student head; it does not unstick live trained pick.
- Student P(success): gold where present + query-only silver regularizer on unobserved cells only. Never calibrate, gate, or threshold-tune on silver. λ is a train hyperparam. Retrain batch includes a teacher pass.
- Complexity is explicit **discrete bins** plus per-model P(success).
- Training recipe: **features-only default** (valid ship). Optional offline **embed ablation** (named: Qwen3-0.6B or 8B MRL ≤256; Nebius 8B ok in prototype). Keep vectors iff held-out success-gold Brier strictly better and ECE not worse; if win, distill into the features-only hop. No Nebius hard-require. No live embed.
- Credits: enough aiand spend to run a teacher offline. Teacher is cheap-then-escalate, catalog-relative (exclude providers of measured trio ∪ live fallback). Example pins: Motif→GLM / Gemma→GLM. Prototype smokes teacher labels; spec few thousand query-only rows.

## Decisions so far

- [Qwen3-Embedding-8B as optional training features](issues/05-qwen3-embedding-training-features.md) — try training-time embeddings as an ablation; features-only default; no online 8B; no Nebius hard-require. [note](research/qwen3-embedding.md)
- [Teacher labeling for multi-candidate success](issues/02-teacher-labeling-multi-candidate.md) — teacher labels bins + silver P(success) query-only; success gold requires running candidates; 3×5 is smoke. [note](research/teacher-labeling.md)
- [Scorer architectures under a 10ms hop](issues/01-scorer-architectures-under-10ms.md) — live hop is feature/tiny-head, not chat LLM or online 8B. Shape freeze: [Scorer shape Rec A vs Rec B](issues/15-scorer-shape-rec-a-vs-b.md). [note](research/scorer-architectures.md)
- [Calibration for router P(success)](issues/03-calibration-for-router-p-success.md) — reliability + ECE + Brier; Pioneer method unpublished; gate needs Brier skill \(>0\) + dual ECE. [note](research/calibration.md)
- [Bootstrap coding-agent datasets](issues/04-bootstrap-coding-agent-datasets.md) — parse+relabel SWE-smith / SWE-Gym / R2E-Gym / BFCL; Terminal-Bench eval-only canary. [note](research/bootstrap-datasets.md)
- [Named savings baseline](issues/06-named-savings-baseline.md) — `most_expensive_eligible` (today usually K3); rules cost delta is not savings.
- [Complexity bin taxonomy](issues/07-complexity-bin-taxonomy.md) — `trivial` / `standard` / `hard` / `frontier`; reason_code/stratum only; Bloom teacher-only.
- [Promotion gate numeric bars](issues/08-promotion-gate-numeric-bars.md) — 1 pp non-inferior quality, rules cost delta < 0, BSS \(>0\), ECE \(\le 0.03\); Verified/Lite, TB canary.
- [Observability Decision contract](issues/09-observability-decision-contract.md) — slim `X-Router-*` ex-ante + JSONL ex-post; full `p_success`; shadow on the same row. [proto](prototypes/observability-decision-contract.html)
- [Tiny local embed on the live hop?](issues/12-tiny-local-embed-on-live-hop.md) — never a live embed; features-only hop (tiny MLP/GBDT/bilinear ok); MiniLM/0.6B off the path. Training embeds still optional offline.
- [Keep embeddings in the training recipe?](issues/11-keep-embeddings-in-training-recipe.md) — optional offline ablation vs features-only default; keep iff better Brier + ECE not worse; Qwen3 0.6B/MRL≤256; win ⇒ distill (no live embed). [note](research/qwen3-embedding.md)
- [Teacher model from aiand catalog](issues/10-teacher-model-from-aiand-catalog.md) — cheap-then-escalate, catalog-relative; exclude `qwen`/`moonshotai`/`deepseek-ai`; Motif→GLM (this org) / Gemma→GLM (public); spec few thousand query-only rows, this repo smokes ~100.
- [Scorer shape Rec A vs Rec B](issues/15-scorer-shape-rec-a-vs-b.md) — Rec A (**Scorer**: features + logistic/GBDT + Platt); Rec B not a spec door. [note](research/scorer-architectures.md)
- [Student training target](issues/14-student-training-target.md) — gold + query-only silver regularizer (unobserved only); not Zooter; never calibrate on silver; new ids wait for dense gold slice.
- [Gold matrix sampling](issues/13-gold-matrix-sampling.md) — hybrid: dense held-out n≥300 × eligible (cal + onboard); sparse train thousands × Flash+trio; flywheel observed+explore; missing ≠ 0.
- [Bootstrap dump set](issues/16-bootstrap-dump-set.md) — required smith `tool` traj + smith tasks + BFCL; gym/r2e allowed; rebench optional; SWE-bench family + TB eval-only; no RouterBench-class. [note](research/bootstrap-datasets.md)
- [Effort tier threshold and max_regret](issues/17-effort-tier-threshold-max-regret.md) — Pioneer-named ship defaults; retune medium before shadow; gate at medium; effort header only.
- [Sparse-train n and stratum fractions](issues/18-sparse-train-n-and-stratum-fractions.md) — n=4000 (floor ≥3000); phase-family strata; bin/tools/phase margins + occ. floor 20; BFCL ≤15%; optional K3 probe ≤5%.
- [Threshold-tuning split](issues/19-threshold-tuning-split.md) — third bootstrap dense n≥300; retune y = success gold + bootstrap resolve; not Verified/Lite; disjoint from cal/train/promotion.
- [Retrain cadence and threshold refit](issues/20-retrain-cadence-and-threshold-refit.md) — event+operator; freeze \(t,r\) until full retrain; production retune holdout n≥300; drift canary; re-shadow+re-gate; drift→rules.
- [Multi-SWE-RL trigger](issues/21-multi-swe-rl-trigger.md) — ≥20% non-Python in canary window → Multi-SWE-RL on next retrain; bench eval-only; diligence gate.
- [Flywheel log store](issues/22-flywheel-log-store.md) — JSONL-compatible append log on aiand infra; same Decision row; keep until next retrain+gate; this repo is prototype only.

## Not yet specified

(none)

## Out of scope

- Full Pioneer clone: dashboard, Routing Playground, session-savings API, Anthropic Messages, OpenAI Responses, versioned `auto_v*`, FireConnect-style installer, six-harness matrix, router-only credits.
- FireRouter BYOK / `x-routing-preference` 1–5 / Opus pass-through.
- Cursor, K8s, Modal-hosting the catalog, inventing a savings %.
- Replacing the rules router (it stays fallback).
- Live aiand chat model as the routing hop.
- Hard-requiring Nebius (or any third-party embed) in the production spec.
- Operating aiand’s multi-tenant production infra from this repo.
