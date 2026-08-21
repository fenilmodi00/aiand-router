---
slug: pioneer-capacity
goal: Reach Pioneer-router capacity per .opencode/wiki/concepts/pioneer-gap-analysis.md
intent: clear
review_required: true
status: complete
created: 2026-08-15
---

# Draft — pioneer-capacity

## Grounded context (explored this session, verified against source)

Codebase: `D:\aiand-router`, Python FastAPI gateway (`src/aiand_router/`): router.py (rules path + Decision contract), scorer.py (trained path: bin classifier, GBDT/logistic heads + Platt, effort presets, cheapest-above-bar), train.py (teacher/gold/fit/salvage/relabel, Platt only), pool.py (smith/BFCL ingest, strata), geometry.py, eval.py, learn.py (dark stub), app.py (FastAPI, headers, JSONL, shadow). Two specs: `.scratch/trained-hop/spec.md` (implementable hop, $100 smoke, done) and `.scratch/trained-router/spec.md` (production proposal-go/no-go; explicitly "proposal-grade … This repo does not run it" for spec-scale data ops; flywheel store = aiand infra).

Gap analysis (wiki page, this session): 10 gaps. P0: production data scale (sparse n=4000, dense n≥300, threshold-tune n≥300), isotonic calibration (Platt-only today), promotion gate (SWE-bench Verified 500 / Lite 300 never run). P1: drift canary (no code), production retune holdout, flywheel log store (aiand infra). P2: retrain automation, embed ablation (spec-optional, keep-iff Brier better + ECE not worse). P3: Multi-SWE-RL trigger, bootstrap dumps at scale.

## Adopted defaults (defensible, recorded, not asked)

- Full scope = all 10 gaps (ulw-plan invariant: no MVP reduction invented by me).
- Promotion gate at **medium effort only** (spec-fixed).
- Isotonic calibration implemented as the n>1000 path per spec; Platt kept for small-n (spec-fixed).
- Embed ablation included as an OFFLINE experiment with spec keep/discard gate; features-only stays the shipped hop; no production embed hard-require (spec-fixed).
- Multi-SWE-RL: implement monitor; ingestion conditional on the ≥20% non-Python trigger (spec-fixed).
- Trained hop stays behind rules fallback; rules remain default until gate passes (spec-fixed, no-go item).
- No live embed, no chat teacher on the hop, Rec B not reopened (spec no-go).

## Owner-decision forks (survive exploration — must ask)

1. **Scope boundary for out-of-repo items**: flywheel log store + Verified-gate execution are aiand-infra / spend operations the production spec parks outside this repo. Choice: (a) plan is code-complete for everything this repo owns + runbook/handoff tasks for infra-side items (owner executes spend), or (b) this session plans the actual paid data-ops runs here too.
2. **Paid-operation budget ceiling** (irreversible spend): spec band for full matrix + Verified gate ≈ low-hundreds to low-thousands USD; current repo cap is $15 code default ($100 smoke env override). Needs an explicit number the plan may target.

## Approved scope inputs (user answers, 2026-08-15)

- Scope boundary: EXECUTE paid data ops from this repo (overrides spec's out-of-repo parking; flywheel log store stays aiand-infra runbook + in-repo adapter contract).
- Budget ceiling: **$50 aiand API credits**, hard cap, stop-on-cap per stage.
- Constraint: **no local model downloads/runs** — embed ablation is hosted-API-only (e.g. Nebius Qwen3-Embedding), execution credit-gated, default deferred behind P0/P1.
- User note: Pioneer-parity must not cost Pioneer-internal money; features-only hop validated.

## Budget allocation model (from README list prices, plan-parameter, verify at fit time)

Teacher ≈ $0.0015/row (Motif-3, escalate ≤25% on GLM 5.2) → ~4–5k rows ≈ $5–8.
Sparse gold per query ≈ $0.01 (4 anchors: Flash + Qwen3.6-27B + Kimi-K2.7 + DS-V4-Pro, ~800 output tok) → n≈2,000 ≈ $20.
Dense/cal slice n≈300 × eligible-except-K3 ≈ $4; threshold-tune split n≈300 × anchors ≈ $4.
n_cal > 1000 → isotonic unlocks per spec.
Verified 500-session gate exceeds budget → bounded promotion check (flashlight suite + Lite micro-slice n≈30–50, explicitly NOT the gate) + full-gate runbook with exact cost/commands.
Caps: teacher $8, sparse gold $22, dense+retune $8, fit/shadow/bounded-check $4, reserve $8 = $50.

## User requirement added at approval (2026-08-15, with Momus review request)

- **Quality-first router**: must route to Kimi K3 when the task demands it (frontier bin / effort `max` / when only K3 clears the bar) — never cheap-only. When it does not need K3, it must never select it.
- **Dual metric gate**: bounded gate must report quality vs rules AND cost delta together; neither alone promotes.
- Plan written under inferred approval (user invoked the plan critic — an artifact is required); review_required=true (Momus per user; Oracle second half of dual review per contract).
- K3 truth at $50: no K3 gold cells (spec-cost rule stands); K3 trained-path P(success) is silver-informed prior; premium floor + effort `max` guarantee K3 reachability; dense-gold-with-K3 is a runbook item.

## Review receipts

- Momus R1: REQUEST_CHANGES → M1/M2 + 7 MINORs fixed. R2: **APPROVED**, 2 advisories applied.
- Oracle: **GO**, 7 conditional amendments applied (cap-stopped dense-n QA, split manifest, fixture F3, per-phase cap mechanism, prior-spend note, decline-rate report, verdict-never-flips + F7).
- Receipts recorded in plan `## Review Log`. Plan final: `.omo/plans/pioneer-capacity.md`. Handed off 2026-08-15.
