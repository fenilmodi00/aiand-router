# Pioneer-like Scorer and train pipeline

Status: ready-for-agent

Glossary: [`CONTEXT.md`](../../CONTEXT.md). Hop contract (already shipped, shadow default): [`.scratch/trained-hop/spec.md`](../trained-hop/spec.md). Production floors this cycle may approach but must not claim: [`.scratch/trained-router/spec.md`](../trained-router/spec.md).

This spec is for **lifting the smoke Scorer** (`not_spec_floors`) until trained routing is Pioneer-shaped in **behavior and measured bars**, not a Pioneer product clone.

## Problem Statement

I already have a live OpenAI-compatible gateway. Rules pick a model. A trained path exists in **shadow**: complexity bin, calibrated P(success) per eligible id, cheapest that clears threshold and max_regret. I fitted a smoke Scorer from teacher silver + mini gold. It loads. It is not good enough to flip `TRAINED_PATH=trained`.

What I see today: holdout rank AUC around **0.55**, predicted P(success) compressed into a narrow band (~0.22–0.30), Platt collapsing scores, and either **zero disagreement** with rules (always Flash) or **disagreement that loses** (trained slightly worse success / higher cost than rules). Teacher JSON often truncates. Gold was mostly “got a reply,” not task success. Features are phase / tools / tokens / a hint bin the live hop does not observe. Credits are no longer the blocker.

I want the **train pipeline and Scorer** improved until trained is a Pioneer-like router: calibrated per-candidate P(success) that actually separates models, cheapest-above-bar that beats rules on quality and cost in shadow, then an explicit promotion decision. I must not invent a savings percentage, clone Pioneer’s dashboard, put a chat teacher or embed on the live hop, or treat SWE-bench Verified as a train dump.

## Solution

Keep the shipped hop. Improve **labels, features, fit, calibration, and the replay gate** until shadow shows a real trained policy.

Hard constraints still build the **eligible set**. The **Scorer** stays Rec A (in-process, features-only at serve, logistic or GBDT + post-hoc calibrator). Complexity bin is predicted from request-observable features. P(success) is calibrated on **success gold**, never on silver. Pick stays cheapest-above-bar at effort threshold and max_regret.

**Gold y** becomes gateway-observable success (no escalate, valid tools/JSON if required) plus **verified** checks when the query carries them (expected substring, JSON schema, flashlight `tests_passed`). Unobserved stays missing, not 0. Silver is a regularizer on unobserved cells only.

**Data** grows along published recipes: run candidates for gold (not teacher-only); ingest allowed bootstrap dumps (SWE-smith `tool` traj as primary; BFCL capped) as query pools; keep Verified / Terminal-Bench eval-only. Teacher stays cheap-then-escalate, parse-reliable, cache-first. Optional **offline** embedding ablation may train a student; if it wins Brier without hurting ECE, distill into the features-only hop. No live embed. No live chat teacher.

**Serve stays shadow** until a frozen promotion-style replay says trained is non-inferior on quality, strictly cheaper vs rules, and calibrated (Brier skill > 0, dual ECE ≤ 0.03) with P-spread large enough that cheapest-above-bar is not Flash-on-every-row. Flipping to `path=trained` remains an operator switch, not this spec’s automatic last step.

Credits are sufficient; stop for quality bars and cache, not for a $15 default.

## User Stories

1. As a coding-agent user, I want `model: router/auto` unchanged, so that pipeline work does not break clients.
2. As a coding-agent user, I want streaming, tools, and missing phase to keep working, so that trained quality work is not a protocol change.
3. As a coding-agent user, I want pinned catalog ids to still bypass auto-select, so that eval baselines stay honest.
4. As the router, I want hard constraints before any Scorer, so that trained only scores the same eligible set as rules.
5. As the router, I want a predicted complexity bin `trivial|standard|hard|frontier` from request-observable features only, so that live hops never look up train-query hint bins.
6. As the router, I want calibrated P(success) per eligible id, so that cheapest-above-bar is a quality floor, not an arbitrary 0–1 score.
7. As the router, I want predicted P(success) to **spread** across models on the same query, so that Flash is not always the unique survivor above threshold.
8. As the router, I want effort `low|medium|high|max` to keep ship knobs (0.05/0.30, 0.10/0.20, 0.20/0.15, 0.60/0.03) until a retune split exists, so that I do not copy Pioneer `xhigh`.
9. As the router, I want scorer-down to stay rules with `scorer_down` and no fake confidence, so that a bad refit cannot invent P(success).
10. As an operator, I want default `TRAINED_PATH=shadow`, so that live traffic stays on rules while the Scorer is lifted.
11. As an operator, I want JSONL and headers to show rules pick vs trained-would, so that I can watch disagreement before any flip.
12. As an operator, I want `TRAINED_PATH=trained` to remain a manual switch after the replay gate, so that a better fit cannot silently go live.
13. As a trainer, I want gold y to be **success gold**, so that “HTTP 200 + nonempty text” is not treated as task success.
14. As a trainer, I want verified queries (`expected`, JSON, `tests_passed`) to override weak proxies, so that hard fails stay hard fails.
15. As a trainer, I want missing gold cells to stay unobserved, so that unobserved ≠ 0.
16. As a trainer, I want silver only on unobserved cells, so that I never calibrate or threshold-tune on teacher guesses.
17. As a trainer, I want teacher output to parse as strict JSON most of the time, so that unlabeled rows are rare rather than the majority.
18. As a trainer, I want Motif (cheap teacher) not to spend the token budget on reasoning whitespace, so that GLM escalate is for uncertainty, not parse failure.
19. As a trainer, I want parse-fail to always escalate, so that the 25% quality cap is not eaten by truncated Motif JSON.
20. As a trainer, I want cache-first paid calls, so that refits and relabels are free on the same bodies.
21. As a trainer, I want concurrent gold/teacher within a concurrency cap, so that larger n finishes in hours not days.
22. As a trainer, I want sparse gold on Flash + measured trio, so that train n can grow without a full catalog × query matrix.
23. As a trainer, I want a dense/cal slice on eligible except K3, so that Platt/isotonic and new-id P(success) have measured cells.
24. As a trainer, I want no K3 gold cells in this cycle, so that $12.50/1M output cannot dominate spend without a max-effort question.
25. As a trainer, I want bootstrap queries from allowed dumps (SWE-smith `tool` traj primary; BFCL ≤ 15% of n), so that prompts look like coding-agent steps, not only synthetic JSONL.
26. As a trainer, I want dump teacher `resolved` **not** used as y, so that catalog P(success) is measured on aiand completions.
27. As a trainer, I want SWE-bench Verified/Lite and Terminal-Bench kept eval-only, so that promotion corpora never leak into fit.
28. As a trainer, I want stratum sampling (bin × phase family × tools), so that gold is not all trivial edits.
29. As a trainer, I want per-model intercepts from gold marginals plus query features, so that base rates (Qwen vs Kimi) are not flattened by Platt.
30. As a trainer, I want a post-hoc calibrator fit **only** on a held-out gold cal slice, so that in-sample Platt cannot hide miscalibration.
31. As a trainer, I want logistic Rec A first, and GBDT + calibrator only if logistic fails the replay bars, so that we do not jump to Rec B.
32. As a trainer, I want an optional **offline** embed ablation (named small encoder, MRL cap), so that we can test Brier lift without a live embed.
33. As a trainer, I want embed vectors dropped unless held-out Brier is strictly better and ECE is not worse, so that unused vectors do not rot in the artifact.
34. As a trainer, I want a win from embeddings distilled into features-only weights, so that serve stays <10ms in-process.
35. As a trainer, I want the artifact still labeled `not_spec_floors` until production n and dumps are met, so that smoke n cannot be sold as Verified.
36. As a trainer, I want a replay report: rules vs trained vs oracle vs always-cheapest vs always-strong, so that I see success rate, list-price cost, disagreement, AUC, Brier, ECE, and P-spread on one page.
37. As a trainer, I want holdout AUC clearly above chance and P-spread large enough that medium threshold does not admit every model, so that cheapest-above-bar can differ from rules.
38. As a trainer, I want Brier skill > 0 vs a constant base-rate predictor, so that a calibrated-but-useless constant scorer cannot pass.
39. As a trainer, I want equal-width and equal-mass ECE ≤ 0.03 on selected-hop P(success), so that threshold 0.10 means about 10% observed success.
40. As a trainer, I want trained holdout **session or per-request success ≥ rules − 1 pp** and **rules cost delta < 0**, so that disagreement is not a quality regression.
41. As a trainer, I want medium threshold + max_regret retuned on a split unused for train or calibrator, so that we do not fit knobs on the same gold we score.
42. As a credit owner, I want budget env-driven with a high operator cap this cycle, so that quality work is not stopped at the code default $15.
43. As a credit owner, I want spend logged and cache hits unbilled, so that I can see dollars vs replay lift.
44. As a credit owner, I want named savings still vs `most_expensive_eligible` only, so that cost vs rules is never called savings.
45. As an operator, I want new catalog ids without a dense gold slice to stay rules-only for live P(success), so that silver cannot unstick an unseen model.
46. As an operator, I want the hop to predict complexity bin without `hint_bin` in the HTTP request, so that OpenCode clients do not send train labels.
47. As a judge, I want JSONL I can grep for `path=shadow` vs `path=trained` vs `path=rules`, so that policy is visible without a dashboard.
48. As a future owner, I want production n=4000 sparse / n≥300 retune / Verified gate to remain the staffed bar, so that this lift cycle cannot claim that gate passed.

## Implementation Decisions

- One product: the existing gateway. No second server. No agent loop in this spec. Flashlight may **label** verified gold; it is not a new product.
- Rec A only at serve: request-observable features + predicted bin + per-survivor logistic **or** GBDT + post-hoc calibrator. Rec B (bilinear / MIRT / live embed) stays closed.
- Live hop: no chat teacher, no embedding forward. Complexity bin from observable features (phase family, tools, tokens, and fitted bin head). Train-only fields (`hint_bin` on JSONL) must not be required at serve.
- Gold y, in order: verified metadata (`tests_passed`, expected match, JSON/schema validity) → gateway success gold (no escalate, valid tools/JSON if required) → never “nonempty content” alone when a stronger check exists. `finish_reason=length` with empty content is failure.
- Sparse gold: Flash + measured trio when eligible. Dense/cal: enabled catalog except K3. Missing cells stay missing.
- Silver: Motif cheap → GLM escalate; parse-fail always escalates; quality escalate still capped; unlabeled stays unlabeled. Teacher `max_completion_tokens` and minimum published `reasoning_effort` so JSON can finish.
- Student target: gold where present + silver regularizer on unobserved cells only. Never calibrate, gate, or threshold-tune on silver.
- Fit: per-model intercept from gold marginals, then feature correction, then calibrator on the **cal slice only**. If logistic holdout Brier skill ≤ 0 or P-spread stays too small for cheapest-above-bar to move, one GBDT + calibrator is allowed. Not both as a zoo.
- Optional offline embed ablation vs features-only; keep vectors iff held-out success-gold Brier strictly better and ECE not worse; if win, distill into features-only artifact.
- Bootstrap ingest: SWE-smith `tool` trajectories as primary query pool (collision-filtered); BFCL ≤ 15% of train n for tool-JSON strata; SWE-Gym / R2E allowed as extra pool. Do not train on Verified, Lite, or Terminal-Bench.
- Dump `resolved` is not success gold. Success gold requires an aiand candidate run (or cache of that run) plus the y definition above.
- Artifact remains `not_spec_floors` until production floors in the trained-router spec are actually met. This cycle may exceed smoke n; it still must not stamp Verified promotion.
- Replay is the quality gate for this cycle (see Testing). Promotion to `path=trained` is still operator-owned after that gate.
- Budget: operator env may be large; code default `BUDGET_LIMIT_USD` stays 15. Cache-first. Concurrency env-capped. Stop on quality bars, not an invented credit scare.
- Observability unchanged: shadow headers + JSONL Decision contract. No Pioneer dashboard, playground, `xhigh`, or invented savings %.

Research this spec is allowed to implement (product docs and papers; Pioneer **internals unpublished**):

- Pioneer **product** shape: complexity class → calibrated P(success) → cheapest above threshold + max_regret; effort retunes those knobs. ([Pioneer Router concepts](https://docs.pioneer.ai/concepts/router))
- Dense multi-candidate gold is built by **running the pool**, not by a query-only teacher (LLMRouter, RouterBench, HybridLLM). Teacher/silver is a prior on unobserved cells only.
- RouteLLM: binary strong-vs-weak from preferences; N-way catalog P(success) is not their v1. Do not copy pairwise win as our y.
- Zooter distills a **response** RM after all candidates ran — not a substitute for gold, and not our live hop.
- Calibration: predicted rates must match observed rates; AUC alone is insufficient when the policy is a numeric threshold. Use Brier + reliability + ECE; Platt if cal n is small, isotonic if large. A constant base-rate predictor is calibrated and useless — require Brier skill > 0. (Guo et al. ICML 2017; Niculescu-Mizil & Caruana 2005; Kumar, Liang & Ma NeurIPS 2019.)
- Scrouting (2026): a **text** head that spreads P(success) widely is what makes cheapest-above-bar move; a compressed head (sd ~0.07, all mass above θ) collapses to the cheapest fixer. Our smoke fit matches that failure. Lift must widen support, not only add features that Platt then flattens.
- SWE-Router (2026): partial-trajectory routing is stronger for multi-turn SWE — **out of scope** for this in-process hop (no live agent value head).
- Azure Model Router: documented as a lightweight non-LLM scorer at negligible latency — compatible with Rec A; internals not copyable.
- SWE-smith / SWE-Gym / R2E: trajectory + resolve dumps for **query pools**; labels for our catalog still need aiand gold cells.
- learning-to-route / kNN over past tasks: interesting, but a live embed or growing vector store is not this hop. Offline kNN ablation only if it stays off the request path.

## Testing Decisions

A good test asserts what an operator or client can observe: HTTP path/headers, JSONL fields, gold cell `success` / `success_tier`, replay numbers, and that refused train jobs do not call the provider. Tests do not assert sklearn internals, YAML parse details, or httpx call shapes.

**Single new seam for this spec: an offline replay report** over a frozen gold JSONL + current Scorer artifact + rules picker. Same inputs, no live aiand required. The report must include, on a **holdout** prompt split unused for train and calibrator:

- rules vs trained vs oracle (cheapest gold-success) vs always-Flash vs always-strong: success rate and list-price cost
- disagreement rate (rules pick ≠ trained pick)
- rank AUC and mean per-prompt P(success) spread
- Brier and Brier skill vs constant base rate; equal-width ECE (M=10) and equal-mass ECE on **selected-hop** P(success)
- assertion helpers: fail CI if replay is invoked in unit tests against **production** floors; unit tests may use a tiny fixture gold file

That is the quality seam. It extends the existing replay helper; do not add a second HTTP stack.

**Existing seams stay green (do not replace them):**

- `POST /v1/chat/completions` on `create_app` + fake aiand upstream: shadow / trained / scorer_down / effort knobs (already the hop suite)
- Train CLI + fake provider: refuse without opt-in; teacher parse-fail escalates; gold skips K3; fit writes `not_spec_floors`; gold success tiers; live bin prediction without train `hint_bin`

**Live aiand** (teacher/gold/verified pytest) is opt-in, not CI. Replay and hop tests never spend.

**Numeric bars for “good enough to consider trained”** (this cycle’s replay gate, not the staffed Verified gate):

- Holdout rank AUC ≥ 0.65
- Mean per-prompt P-spread ≥ 0.10
- Brier skill > 0; dual ECE ≤ 0.03 on selected-hop P(success)
- Trained holdout success ≥ rules − 1 pp; rules cost delta < 0
- Disagreement > 0 (policy is not identical to always-cheapest-eligible)

Failing any bar → stay `path=shadow`, keep `not_spec_floors`. Passing this replay gate still does **not** claim SWE-bench Verified promotion.

Prior art: hop tests with FakeProvider; train tests with opt-in env; replay script over gold JSONL.

## Out of Scope

- Pioneer clone: dashboard, Routing Playground, session-savings API, Anthropic Messages, OpenAI Responses, `auto_v*`, FireConnect, `xhigh`, BYOK, `x-routing-preference`
- Replacing the rules router
- Live chat LLM as the hop; live embed; Rec B as the shipped hop; Nebius hard-require
- SWE-Router-style mid-trajectory value heads
- Training on SWE-bench Verified/Lite or Terminal-Bench
- Using dump teacher `resolved` as success gold
- K3 gold cells; inventing a savings %
- Automatic `TRAINED_PATH=trained` without an operator flip
- Claiming the production Verified promotion gate from this cycle
- Multi-tenant aiand control plane, Nginx/Gunicorn production topology
- Flashlight/OpenCode as products (labeling harness only)

## Further Notes

Smoke measurements that motivated this spec (operator session, not a promotion run): silver parse yield started ~35% labeled; Motif `finish_reason=length` on teacher JSON; gold `max_tokens=64` burned on reasoning; after pipeline fixes, holdout AUC ~0.55, P-spread ~0.02–0.07, rules and trained either identical (Flash) or trained slightly worse. Verified-query gold (89 prompts) made y stricter but did not clear AUC 0.65.

Production numeric bars (Verified n≥300, 1 pp quality, cost delta < 0, BSS > 0, ECE ≤ 0.03) stay in the trained-router promotion ticket. This spec’s replay gate is the **local** bar for “shadow looks like a real router.”

Credits: operator said they are sufficient. Still cache-first, still opt-in env, still do not change the code default budget of 15.
