# Hard-transfer Scorer gold (verified-like ranking)

Status: ready-for-agent

Glossary: [`CONTEXT.md`](../../CONTEXT.md). Prior cycle (pipeline + failed probe — do **not** treat as this cycle’s “done”): [`.scratch/scorer-pioneer-lift/spec.md`](../scorer-pioneer-lift/spec.md). Decision that chose this path: [`.scratch/scorer-pioneer-lift/next-path-decision.md`](../scorer-pioneer-lift/next-path-decision.md). Probe fail that motivates real smith + budget: [`.scratch/scorer-pioneer-lift/issues/12-hard-y-probe-gold.md`](../scorer-pioneer-lift/issues/12-hard-y-probe-gold.md). Hop contract (shadow default): [`.scratch/trained-hop/spec.md`](../trained-hop/spec.md). Production floors this cycle may approach but must not claim: [`.scratch/trained-router/spec.md`](../trained-router/spec.md).

This spec is the **next** lift: make train/cal **success gold** transfer to frozen verified eval (Spearman > 0), refit a logistic Scorer, and clear an offline replay gate on a **cost-meaningful** holdout — then only an operator may flip `TRAINED_PATH=trained`. It does **not** claim SWE-bench Verified promotion.

## Problem Statement

I already have the Pioneer-shaped hop in **shadow**: complexity bin, calibrated P(success) per eligible id, cheapest-above-bar. The pioneer-lift cycle shipped pool / gold / fit / geometry / dual-replay machinery and a GBDT lift attempt. The operator replay gate on frozen verified success gold is still **red**. Ranking on train gold is anti-correlated or empty vs holdout (sparse↔verified model-rate Spearman was −0.6; the hard-y probe then hit Spearman **0** and train y_rate **0**). Dense-cal y ≈ 39% cannot calibrate for verified y ≈ 7%. On the frozen verified file, rules pick Flash on every row and Flash is global cheapest, so `rules_cost_delta < 0` is structurally impossible. Length-stump GBDT collapses on short verified prompts; logistic is less broken but still fails the gate.

The last paid probe used a synthetic / thin pool (`train-queries` as `--smith`), not real SWE-smith `tool` trajectories, and many cells stayed budget-unobserved. Credits are available this cycle; the code default budget stays 15 and the operator env may be large. Cache-first. I am ready to spend for **real** coding-agent queries and hard checks — not to invent a green gate, leak Verified into fit, or auto-flip trained.

I want the Scorer to behave like a Pioneer-like router on **hard** work: model order that matches verified holdout, calibrated P(success) that separates survivors, cheapest-above-bar that can beat rules on quality and on cost where cost is a real test — then a **manual** promotion decision. I must not train on Verified/Lite/Terminal-Bench, use dump `resolved` as y, calibrate on silver, open Rec B / live embed, or claim production Verified floors.

## Solution

Keep the shipped hop and pioneer-lift CLIs. Rebuild **labels and fit inputs**, not the HTTP stack.

1. **Real coding-agent query pools** — SWE-smith `tool` trajectories as the primary bootstrap dump; BFCL capped; collision-filter vs frozen eval. Prefer verified-like difficulty (short, hard/frontier, tools/JSON, attachable `expected` / schema / flashlight checks on **bootstrap** rows). Do not use the frozen Verified dump as the train pool.
2. **Paid sparse (+ hard dense/cal) success gold** — Flash + measured trio for sparse; dense except K3 for cal/onboard; issue-02 y (verified metadata overrides weak proxies; dump `resolved` never y). Difficulty and model ranking must look like holdout (~0.07–0.22 overall y, not dense-easy ~0.39). Cache-first; `AIAND_TRAIN=1`; operator budget may be large; stop on quality bars, not an invented credit scare.
3. **Geometry pass** — unpaid Spearman of per-model success rates vs frozen verified eval must be **> 0** with holdout-like order (Kimi ≫ Flash ≈ Qwen ≫ Pro). Eval never enters fit, cal, or threshold-tune. Kill and stop scaling if Spearman stays ≤ 0 or y stays empty/easy-wrong.
4. **Logistic refit** — prefer logistic Rec A until transfer exists; no GBDT-on-length zoo. Platt/isotonic only on the hard dense-cal slice. Silver only on unobserved cells — never Platt/gate/threshold y.
5. **Replay gate green** on a holdout where cost vs rules is meaningful (`rules_ne_cheapest` possible) — dual offline report: frozen verified (or same-kind eval) for transfer metrics, plus a disjoint bootstrap cost slice. Bars: rank AUC, P-spread, Brier skill > 0, dual ECE, quality ≥ rules − 1 pp, rules cost delta < 0 on the cost-meaningful slice, disagreement > 0. Unit tests never assert production floors.
6. **Only then** manual `TRAINED_PATH=trained` — still shadow by default; `apply_replay_gate` never auto-flips; artifact stays `not_spec_floors` until production floors are actually met; **not** a Verified promotion claim.

Ideal quality gate for this cycle: geometry Spearman > 0 **and** replay gate green on a cost-meaningful holdout (offline once gold exists). No new HTTP stack.

## User Stories

1. As a coding-agent user, I want `model: router/auto` unchanged, so that gold/fit work does not break clients.
2. As a coding-agent user, I want streaming, tools, and missing phase to keep working, so that this cycle is not a protocol change.
3. As a coding-agent user, I want pinned catalog ids to still bypass auto-select, so that eval baselines stay honest.
4. As the router, I want hard constraints before any Scorer, so that trained only scores the same eligible set as rules.
5. As the router, I want a predicted complexity bin `trivial|standard|hard|frontier` from request-observable features only, so that live hops never look up train-query hint bins.
6. As the router, I want calibrated P(success) per eligible id, so that cheapest-above-bar is a quality floor, not an arbitrary score.
7. As the router, I want predicted P(success) to spread across models on hard queries, so that Flash is not always the unique survivor above threshold.
8. As the router, I want effort `low|medium|high|max` knobs unchanged until a retune split exists, so that I do not copy Pioneer `xhigh`.
9. As the router, I want scorer-down to stay rules with `scorer_down` and no fake confidence, so that a bad refit cannot invent P(success).
10. As an operator, I want default `TRAINED_PATH=shadow`, so that live traffic stays on rules while transfer gold is built.
11. As an operator, I want JSONL and headers to show rules pick vs trained-would, so that I can watch disagreement before any flip.
12. As an operator, I want `TRAINED_PATH=trained` to remain a **manual** switch only after a green replay gate, so that a better fit cannot silently go live.
13. As an operator, I want `apply_replay_gate` never to auto-flip path, so that gate machinery cannot promote itself.
14. As a trainer, I want the primary train/cal query pool from SWE-smith `tool` trajectories, so that prompts look like coding-agent steps, not only synthetic train-queries.
15. As a trainer, I want BFCL at most a small share of pool n (≤ 15%), so that tool-JSON strata exist without dominating.
16. As a trainer, I want pool collision-filter against frozen eval dumps, so that Verified/Lite/Terminal-Bench prompts never enter fit gold by accident.
17. As a trainer, I want `--verified-like` (or equivalent) sampling that prefers short + hard/frontier + tools/JSON rows, so that train difficulty matches holdout shape.
18. As a trainer, I want hard-check metadata (`expected`, JSON schema, flashlight `tests`) attached on **bootstrap** rows when present or safely inferable, so that success gold is not “got a reply.”
19. As a trainer, I want dump teacher `resolved` **never** used as y, so that catalog P(success) is measured on aiand completions.
20. As a trainer, I want SWE-bench Verified, Lite, and Terminal-Bench kept **eval-only**, so that promotion corpora never leak into fit, cal, or threshold-tune.
21. As a trainer, I want frozen verified success-gold JSONL unused as fit y, so that transfer is earned, not leaked.
22. As a trainer, I want sparse success gold on Flash + measured trio when eligible, so that train n can grow without a full matrix.
23. As a trainer, I want a dense/cal slice on eligible except K3, disjoint from sparse, so that Platt and new-id P(success) have measured cells.
24. As a trainer, I want no K3 gold cells this cycle, so that expensive output does not dominate spend without a max-effort question.
25. As a trainer, I want gold y to prefer verified metadata over weak proxies, so that hard fails stay hard fails.
26. As a trainer, I want missing gold cells to stay unobserved, so that unobserved ≠ 0 and budget-skipped rows are not fake fails.
27. As a trainer, I want overall train/cal y-rate in a hard band (~0.07–0.22), not dense-easy (~0.39), so that calibration matches verified difficulty.
28. As a trainer, I want per-model train success rates to correlate with frozen verified rates (Spearman > 0), so that ranking can transfer.
29. As a trainer, I want holdout-like model order on train gold (Kimi > Flash ≈ Qwen > Pro), so that cheapest-above-bar can prefer survivors that actually win on hard work.
30. As a trainer, I want an unpaid geometry report before scaling spend, so that I kill anti-correlated or empty-y recipes early.
31. As a trainer, I want a kill if Spearman ≤ 0 or y stays empty / easy-wrong, so that I do not buy more of the wrong ranking.
32. As a trainer, I want silver only on unobserved cells, so that I never calibrate, gate, or threshold-tune on teacher guesses.
33. As a trainer, I want teacher Motif→GLM escalate with parse-fail always escalating, so that unlabeled rows stay rare.
34. As a trainer, I want cache-first paid calls, so that refits and relabels are free on the same bodies.
35. As a trainer, I want concurrent gold within a concurrency cap, so that larger n finishes in hours not days.
36. As a trainer, I want logistic Rec A as the default fit until Spearman > 0 and transfer improves, so that I do not serve a length-stump GBDT zoo.
37. As a trainer, I want GBDT only as an explicit opt-in after logistic still fails *with* transferring labels, so that trees must split on more than `log1p(tokens)`.
38. As a trainer, I want a post-hoc calibrator fit **only** on the hard dense-cal slice, so that easy-cal Platt cannot hide miscalibration.
39. As a trainer, I want per-model intercepts from gold marginals plus query features, so that base rates are not flattened into always-Flash.
40. As a trainer, I want the artifact labeled `not_spec_floors` until production floors are actually met, so that this cycle cannot be sold as Verified promotion.
41. As a trainer, I want a dual offline replay: primary `--gold` for transfer metrics and `--cost-gold` for cost vs rules, so that H3 (rules≡cheapest) cannot fake a cost pass on the wrong file.
42. As a trainer, I want the cost slice to have non-trivial `rules_ne_cheapest_rate`, so that `rules_cost_delta < 0` is a real test.
43. As a trainer, I want holdout rank AUC clearly above chance and P-spread large enough that medium threshold does not admit every model, so that cheapest-above-bar can differ from rules.
44. As a trainer, I want Brier skill > 0 vs a constant base-rate predictor, so that a calibrated-but-useless constant Scorer cannot pass.
45. As a trainer, I want equal-width and equal-mass ECE ≤ 0.03 on selected-hop P(success), so that threshold 0.10 means about 10% observed success.
46. As a trainer, I want trained holdout success ≥ rules − 1 pp on the transfer eval, so that disagreement is not a quality regression.
47. As a trainer, I want rules cost delta < 0 on the cost-meaningful slice, so that trained can demonstrate cheaper-than-rules where rules sometimes pick non-cheapest.
48. As a trainer, I want disagreement > 0 vs always-cheapest-eligible, so that the policy is not identical to always-Flash.
49. As a trainer, I want medium threshold + max_regret retuned only on a split unused for train or calibrator, so that knobs are not fit on the same gold we score.
50. As a credit owner, I want to spend real credits this cycle for smith-backed hard gold, so that the probe is not starved by a thin synthetic pool or an invented scare.
51. As a credit owner, I want code default `BUDGET_LIMIT_USD` to stay 15 while operator env may be large, so that CI/smoke stays cheap and operators can scale.
52. As a credit owner, I want spend logged and cache hits unbilled, so that I can see dollars vs geometry and replay lift.
53. As a credit owner, I want work to stop on quality bars (Spearman, replay), not at an arbitrary dollar cutoff invented by the agent, so that transfer is the goal.
54. As a credit owner, I want named savings still vs `most_expensive_eligible` only, so that cost vs rules is never called savings.
55. As an operator, I want new catalog ids without a dense gold slice to stay rules-only for live P(success), so that silver cannot unstick an unseen model.
56. As an operator, I want the hop to predict complexity bin without `hint_bin` in the HTTP request, so that OpenCode clients do not send train labels.
57. As a judge, I want JSONL I can grep for `path=shadow` vs `path=trained` vs `path=rules`, so that policy is visible without a dashboard.
58. As a judge, I want geometry and replay reports to print kill/pass flags an operator can trust, so that scale-or-stop is not a vibes call.
59. As a future owner, I want production n=4000 sparse / n≥300 retune / Verified gate to remain the staffed bar, so that this hard-transfer cycle cannot claim that gate passed.
60. As a future owner, I want Rec B, live embed, and Pioneer dashboard work to stay closed, so that this cycle stays Rec A features-only at serve.
61. As a developer, I want unit tests on train/pool/gold/fit to use FakeProvider, so that CI never spends.
62. As a developer, I want live gold opt-in via `AIAND_TRAIN=1` only, so that accidental paid runs are hard.
63. As a developer, I want geometry tests to assert Spearman vs frozen verified eval without writing fit gold from that eval, so that the seam matches the product rule.
64. As a developer, I want replay unit tests to use tiny fixtures and never production floor helpers as pass criteria, so that CI does not encode Verified promotion.
65. As a developer, I want HTTP hop tests on `create_app` + FakeProvider to stay default shadow, so that trained is only exercised when an operator points `TRAINED_PATH=trained` after a green gate.
66. As a developer, I want no second HTTP stack for this cycle, so that quality work stays offline CLIs + existing hop.
67. As an operator, I want issue-07-style flip to stay illegitimate until geometry and cost-meaningful replay are green, so that we do not ship inverted ranking.
68. As an operator, I want a documented H3-style cost waiver only as a footnote on files where rules≡cheapest **after** transfer exists — never as the first move or a substitute for a cost-meaningful slice.
69. As a trainer, I want stratum sampling (bin × phase family × tools) on the smith pool, so that gold is not all trivial edits.
70. As a trainer, I want optional SWE-Gym / R2E as extra pool sources, so that I can fill hard strata without touching eval-only dumps.
71. As a trainer, I want `finish_reason=length` with empty content treated as failure, so that truncated “success” does not inflate y.
72. As a trainer, I want tools/JSON validity required when the query demands them, so that gateway success gold matches coding-agent reality.
73. As a trainer, I want sparse and dense outputs tagged so fit can refuse overlapping train/cal when configured, so that cal is held out.
74. As a trainer, I want geometry to compare train rates to eval rates by catalog id, so that Spearman is model-order transfer, not prompt overlap.
75. As an operator, I want shadow to keep serving the less-broken logistic artifact while labels transfer, so that length-stump GBDT does not stay the live shadow Scorer by default.
76. As a judge, I want oracle vs rules vs trained vs always-cheapest vs always-strong on one replay page, so that quality headroom and cost are visible together.
77. As a trainer, I want probe-then-scale: small paid sparse → geometry → only then dense/cal + fit + cost-gold, so that failed geometry does not burn a full matrix.
78. As a credit owner, I want budget-unobserved cells to remain missing (not imputed fail), so that a capped run does not invent y_rate 0 as “all models fail.”
79. As an operator, I want promotion language to say “shadow looks like a real router,” not “Verified promoted,” so that stakeholders are not misled.
80. As a future owner, I want this feature directory separate from pioneer-lift, so that the next cycle’s tickets do not overwrite prior evidence.

## Implementation Decisions

- One product: the existing gateway. No second server. No agent loop. Flashlight may label verified-style checks on bootstrap rows; it is not a new product.
- Rec A only at serve: request-observable features + predicted complexity bin + per-survivor **logistic** (default) or, only after transfer, an explicit GBDT + post-hoc calibrator. Rec B (bilinear / MIRT / live embed) stays closed. No live chat teacher. No live embed.
- Prefer logistic until geometry Spearman > 0 and replay moves; do not keep a length-stump GBDT as the shadow artifact while every split is `log1p(tokens)` dead on short prompts.
- Query pool module / train CLI: SWE-smith `tool` traj primary; BFCL ≤ 15% of n; optional SWE-Gym/R2E; `--verified-like` (or equivalent) for short/hard/tools/JSON; collision-filter vs `--eval`; refuse empty mix. Never ingest Verified/Lite/Terminal-Bench as train pool.
- Hard-check metadata on bootstrap rows: copy or attach `expected` / JSON schema / flashlight tests when present; do not invent fake `status` schemas that force universal fail; dump `resolved` is never written as success gold.
- Gold / fit CLI: sparse = Flash + measured trio; dense/cal = eligible except K3; y order = verified metadata → gateway success gold → never nonempty-alone when a stronger check exists; missing stays missing; silver regularizer on unobserved only.
- Geometry CLI: Spearman (and related rate tables) of train success-gold model rates vs frozen verified eval; print kill/pass; eval path never feeds fit/cal/threshold. Geometry is unpaid.
- Fit: per-model intercepts from gold marginals, feature correction, calibrator on **hard cal only**. Artifact `not_spec_floors` until production floors met.
- Offline replay report: dual `--gold` + `--cost-gold`; primary gate metrics from `--gold`; cost slice must expose `rules_ne_cheapest` (or equivalent) so cost_delta is meaningful; never encode production Verified floors in unit tests.
- Serve: default shadow; manual `TRAINED_PATH=trained` only after green gate; `apply_replay_gate` non-auto; scorer-down → rules.
- Budget: code default `BUDGET_LIMIT_USD` stays 15; operator env may be large this cycle; cache-first; concurrency env-capped; stop on Spearman/replay bars, not an invented credit scare.
- Named savings vs `most_expensive_eligible` only; rules cost delta is rules cost delta — never call it savings.
- Observability unchanged: shadow headers + JSONL Decision contract. No Pioneer dashboard, playground, `xhigh`, or invented savings %.
- Prior pioneer-lift machinery is assumed available; this cycle’s job is **real smith-backed hard gold + transfer + logistic refit + cost-meaningful gate**, not re-deriving the hop.

Research this spec may lean on (product docs and papers; Pioneer **internals unpublished**):

- Pioneer product shape: complexity class → calibrated P(success) → cheapest above threshold + max_regret.
- Dense multi-candidate gold by running the pool (LLMRouter / RouterBench / HybridLLM); silver is a prior on unobserved cells only.
- Calibration requires Brier skill > 0 and reliability/ECE — a constant base-rate predictor is calibrated and useless.
- Scrouting (2026): compressed P(success) collapses cheapest-above-bar to the cheapest fixer; lift must widen support on hard work.
- SWE-smith / SWE-Gym / R2E: trajectory dumps for **query pools**; labels still need aiand success gold.
- Gate-fail diagnosis (prior cycle): AUC ceiling without verified leak when train ranking anti-correlates; cost_delta impossible when rules≡cheapest on the eval file — fix labels and add a cost-meaningful eval slice, do not leak or vanity-waive first.

## Testing Decisions

A good test asserts what an operator or client can observe: CLI exit/flags, geometry Spearman/kill, gold cell `success` / `success_tier`, replay numbers, HTTP path/headers, and that refused train jobs do not call the provider. Tests do not assert sklearn internals, YAML parse details, or httpx call shapes.

**Confirmed seams (use these exactly):**

1. **Train / pool / gold / fit CLI** — FakeProvider in unit tests; live gold opt-in `AIAND_TRAIN=1`.
2. **Geometry CLI** — Spearman vs frozen verified eval; eval never fit gold.
3. **Offline replay report** — dual `--gold` + `--cost-gold`; bars; never production floors in unit tests.
4. **HTTP hop (`create_app` + FakeProvider)** — default shadow; manual `TRAINED_PATH=trained` only after green gate.

**Ideal quality gate (operator / offline once gold exists):** geometry Spearman > 0 **and** replay gate green on a cost-meaningful holdout. No new HTTP stack.

**Numeric bars for “good enough to consider trained”** (local replay gate, not staffed Verified promotion):

- Geometry: Spearman(train model rates, frozen verified rates) > 0 with holdout-like order
- Holdout rank AUC ≥ 0.65
- Mean per-prompt P-spread ≥ 0.10
- Brier skill > 0; equal-width ECE ≤ 0.03 on selected-hop P(success)
- Equal-mass ECE ≤ 0.03 when `n_selected ≥ 150`; below that, equal-mass is reported but not gated (small-n noise floor; see issue 06)
- Trained success ≥ rules − 1 pp on transfer eval
- Rules cost delta < 0 on the cost-meaningful `--cost-gold` slice (`rules_ne_cheapest` possible)
- Disagreement > 0 (policy ≠ always-cheapest-eligible)

Failing any bar → stay `path=shadow`, keep `not_spec_floors`. Passing still does **not** claim SWE-bench Verified promotion.

Prior art: pioneer-lift train/pool/geometry/replay tests; hop suite with FakeProvider; opt-in live gold under `AIAND_TRAIN`.

## Out of Scope

- Pioneer clone: dashboard, Routing Playground, session-savings API, Anthropic Messages, OpenAI Responses, `auto_v*`, FireConnect, `xhigh`, BYOK, `x-routing-preference`
- Replacing the rules router
- Live chat LLM as the hop; live embed; Rec B as the shipped hop; Nebius hard-require
- SWE-Router-style mid-trajectory value heads
- Training, calibrating, or threshold-tuning on SWE-bench Verified/Lite or Terminal-Bench (including frozen verified success gold as fit y)
- Using dump teacher `resolved` as success gold
- Silver as Platt / gate / threshold y
- K3 gold cells; inventing a savings %
- Automatic `TRAINED_PATH=trained` / auto `apply_replay_gate` flip
- Claiming production Verified promotion or production floors from this cycle
- Gate vanity as the path: lowering AUC floors, rewriting `cost_delta ≤ 0` as the whole plan, catalog/rules edits to manufacture savings
- Scaling the easy sparse/dense recipe while Spearman ≤ 0
- GBDT-on-length zoo as the default shadow Scorer before transfer
- New HTTP stack / second gateway
- Multi-tenant aiand control plane, Nginx/Gunicorn production topology
- Flashlight/OpenCode as products (labeling harness only)
- Creating implementation tickets in this turn (`/to-tickets` is separate)

## Further Notes

Prior cycle (pioneer-lift) delivered pool/gold/fit/geometry/dual-replay and a failed hard-y probe: Spearman **0.0**, train y_rate **0.0**, `--smith` was synthetic `train-queries`, many cells budget-unobserved. Decision doc chose **Option A**: verified-like train/cal gold + dual shadow eval — not bar rewrite, not more easy n, not leak/flip.

This cycle’s success is transfer + a real cost comparison, then optional manual flip — not “gate green by definition.” Frozen verified remains eval-only; a bootstrap cost slice is where `rules_cost_delta < 0` can be earned. A narrow H3 waiver (cost_delta when rules≡cheapest) may be documented later as a reporting footnote only after transfer exists — never as the opening move.

Credits: user confirmed real spend is OK this cycle. Code default budget stays 15; operator env may be large. Cache-first. Stop on quality bars.

Issue-tracker home for follow-on tickets: `.scratch/scorer-hard-transfer/issues/` (create via `/to-tickets`, not this spec turn).
