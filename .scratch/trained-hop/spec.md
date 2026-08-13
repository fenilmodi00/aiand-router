# Pioneer-grade trained hop

Status: ready-for-agent

This is the **implementation spec** for this gateway. The production proposal (floors, dumps, Verified gate) stays [`.scratch/trained-router/spec.md`](../trained-router/spec.md). Glossary: [`CONTEXT.md`](../../CONTEXT.md).

## Problem Statement

I have an OpenAI-compatible coding router that already picks an aiand model with **rules** (phase bars + Pioneer-style score). I want the **router itself** to be Pioneer-grade: complexity bin, calibrated P(success) per eligible model, cheapest that clears threshold and max_regret, effort presets, and honest observability.

I do **not** want to build agents, flashlight, or OpenCode in this cycle. Clients that already speak `/v1/chat/completions` should get the trained policy later by pointing at this process. I have about **$100** of aiand credits for a **smoke fit** of the Scorer — not the production gold-matrix floors. I must not invent a savings percentage, clone Pioneer’s dashboard/playground, or replace the rules path (it stays fallback).

Today `learn.py` is an untrained highest-AA stub behind a 3×5 flag. That is not the trained router.

## Solution

The gateway grows a **trained path** beside rules.

Hard constraints still produce the **eligible set**. A **Scorer** (Rec A: features-only logistic or GBDT + Platt) emits a complexity bin and calibrated P(success) per survivor. The pick is the **cheapest** survivor that clears effort **threshold** and **max_regret**. Else decline to the configured fallback, `path=rules`.

**Default serve is `path=shadow`:** the client still gets the **rules** pick; the JSONL row and headers also record what trained would have picked. `path=trained` (live trained pick) is an explicit operator switch after shadow looks sane — not automatic promotion, and not the Verified production gate.

A small **offline** train CLI (opt-in, cached, budget-capped) can fit a smoke Scorer from teacher silver + mini gold on Flash + measured trio. Weights load in-process. No live embed. No chat teacher on the hop. Agents stay out.

## User Stories

1. As a coding-agent user, I want `model: router/auto` to keep working, so that I do not change my client when the trained hop lands.
2. As a coding-agent user, I want streaming and tools to keep working, so that the trained hop is not a protocol break.
3. As a coding-agent user, I want missing `x-agent-phase` to stay normal, so that third-party clients still route.
4. As a coding-agent user, I want `x-routing-effort: low|medium|high|max` to be the only effort wire, so that I do not send raw threshold numbers.
5. As a coding-agent user, I want default effort to be `medium`, so that I match Pioneer-named presets without copying Pioneer-high onto our medium.
6. As a coding-agent user, I do not want `xhigh`, so that we do not ship a Pioneer-only rung.
7. As a coding-agent user, I want a pinned real model id to still bypass auto-select, so that eval baselines keep working.
8. As the router, I want hard constraints to run before any Scorer, so that trained only scores/picks among the same survivors as rules.
9. As the router, I want the Scorer to emit `trivial|standard|hard|frontier`, so that complexity is a feature and reason_code, not the pick.
10. As the router, I want the Scorer to emit calibrated P(success) per eligible id, so that the pick is cheapest-above-bar, not max weighted score.
11. As the router, I want ship-default threshold/max_regret per effort (low 0.05/0.30, medium 0.10/0.20, high 0.20/0.15, max 0.60/0.03), so that an unfitted hop still has Pioneer-shaped knobs.
12. As the router, I want those knobs in `trained_effort` YAML (or equivalent), namespaced away from rules `max_regret: 8`, so that AA points are never reused as probabilities.
13. As the router, I want `low` to still use the Scorer, so that low is a tiny floor and wide regret, not scorer-off.
14. As the router, I want `max` to stay cheapest-above-bar on the same eligible set as rules, so that the premium floor still lets K3 in without a special-case strongest-on-max.
15. As the router, I want decline (`rule=fallback_declined`) to use the configured fallback model, so that an empty bar still returns 200.
16. As the router, I want scorer-down to serve rules, `path=rules`, `rule=fallback_declined`, reason_code `scorer_down`, and no fake confidence, so that a missing artifact cannot invent P(success).
17. As the gateway, I want default `TRAINED_PATH=shadow`, so that live traffic stays on rules until I flip it.
18. As the gateway, I want shadow headers `X-Router-Path: shadow`, `X-Router-Model` = rules pick, and `X-Router-Trained-Would` = trained pick, so that a client can see both without a second request.
19. As the gateway, I want one JSONL row per hop with `path`, `selected` (served), `trained_selected`, `trained_confidence`, `p_success`, `complexity_bin`, `rule`, `reason_codes`, `threshold`, `max_regret`, `baseline_model_id`, estimated then realized `savings_usd`, and `rules_cost_delta_usd` (trained − rules, not called savings), so that shadow and live share one log.
20. As the gateway, I want trained-path response headers: Model, Phase, Effort, Complexity-Bin, Confidence, Rule, Path, Baseline-Model, Savings-Usd (estimate), Reason-Codes, Candidates, Threshold — and no prose `X-Router-Reason` on the trained path, so that the contract matches the frozen observability prototype.
21. As the gateway, I want the rules path to keep `X-Router-Reason`, so that the existing demo does not regress.
22. As a credit owner, I want savings vs `most_expensive_eligible` only, so that I never stamp an invented %.
23. As a credit owner, I want K3 to be the baseline id only when it is eligible, so that allow-list/budget/effort cannot inflate savings.
24. As a credit owner, I want `BUDGET_LIMIT_USD` to stay env-driven (default 15; I set 100 for smoke), so that a forgotten process cannot spend the wallet.
25. As a credit owner, I want every paid teacher or gold call to hit the request cache, so that reruns are free.
26. As a credit owner, I want paid train jobs to refuse unless an explicit opt-in env is set, so that pytest cannot call aiand.
27. As a credit owner, I want no K3 cells in the $100 gold smoke, so that $12.50/1M output cannot eat the budget.
28. As a trainer, I want a teacher CLI (Motif cheap → GLM escalate, catalog-relative exclusions), so that I can mint bins + silver P(success) query-only.
29. As a trainer, I want teacher temperature 0 and strict json_schema, so that labels are parseable.
30. As a trainer, I want ~800–1000 teacher rows as the $100 default, so that silver exists without eating gold spend.
31. As a trainer, I want a mini sparse gold of ~150–200 queries × Flash + measured trio (short completions), so that success gold exists without n=4000.
32. As a trainer, I want a mini dense/cal slice of ~80–100 queries × eligible except K3, so that Platt can fit without claiming n≥300.
33. As a trainer, I want gold-where-present + silver regularizer on unobserved cells only, so that we do not train Zooter or calibrate on silver.
34. As a trainer, I want missing cells to stay missing, so that unobserved ≠ 0.
35. As a trainer, I want the fitted Scorer written as a loadable artifact, so that the hop does not retrain at request time.
36. As a trainer, I want the artifact labeled `not_spec_floors` (n and dumps below production), so that I cannot confuse smoke weights with a promoted model.
37. As a trainer, I want logistic **or** GBDT plus Platt in-process, so that Rec A is the hop (implementer choice, one is enough for v1).
38. As a trainer, I want no embedding-model forward on the hop and no required Nebius, so that serve stays features-only.
39. As a trainer, I want Bloom off live headers, so that teacher-only Bloom cannot leak into Decision.
40. As an operator, I want `TRAINED_PATH=trained` to serve the trained pick, so that I can try Pioneer-shaped routing after watching shadow.
41. As an operator, I want `TRAINED_PATH=off` to be today’s rules (and the old learned stub only if its 3×5 flag is on), so that I can disable trained without deleting artifacts.
42. As an operator, I want the learned highest-AA stub **not** to be the trained router, so that 3×5 `learned_wins` cannot silently replace Rec A.
43. As an operator, I want new catalog ids without a dense gold slice to stay rules-only for live P(success), so that silver cannot unstick an unseen model.
44. As an operator, I want scorer latency to stay in-process and aim at ~&lt;10ms added, so that the hop is a classifier not a chat call.
45. As a README reader, I want a short “trained path” section: shadow default, how to set path, how to run opt-in train, and that $100 smoke is not Verified promotion, so that I do not claim Pioneer quality I did not measure.
46. As a judge, I want JSONL I can grep for `path=shadow` vs `path=trained` vs `path=rules`, so that I can see the policy without a dashboard.
47. As a future owner, I want production dump ingest, n=4000 sparse, n≥300 retune, and Verified gate to remain documented in the proposal spec, so that this cycle does not pretend to staff that.

## Implementation Decisions

- One product: the existing FastAPI OpenAI-compatible gateway. No second server. No agent loop in this spec.
- `TRAINED_PATH` env (or equivalent config): `off` | `shadow` (default) | `trained`. Invalid value → `shadow`.
- Eligible set is `eligible_models` as today. Trained never expands or shrinks hard constraints.
- Scorer is Rec A only: gateway features + predicted bin + per-survivor logistic **or** GBDT + Platt. v1 may ship logistic-only. Score survivors only.
- Pick: cheapest unit-cost survivor with P(success) ≥ threshold and (top P(success) − P(success)) ≤ max_regret. Else fallback_declined.
- Ship defaults from the effort table above. Runtime `trained_effort:` may override after a retune; this $100 cycle may keep ship defaults (mini split is not the spec threshold-tuning split).
- Extend the Decision record to carry: path, rule, complexity_bin, confidence, p_success map, max_regret, reason_codes, baseline_model_id, savings estimate, trained_selected (shadow). Rules path may leave new fields empty and keep prose reason.
- Headers: trained/shadow as frozen observability contract; rules keep `X-Router-Reason`.
- JSONL: same file `data/requests.jsonl` (prototype flywheel log). No second shadow file. Ex-ante savings on headers; realized dollars when usage lands.
- Savings = baseline cost − selected cost vs `most_expensive_eligible`. `rules_cost_delta_usd` is trained − rules, shadow/trained rows only, never named savings.
- Learned stub (`learned_select` + `learned_wins.json`) stays the 3×5 experiment. Trained hop does not read that flag.
- Scorer artifact on disk; missing or corrupt → scorer_down behavior. Load once at process start (or mtime reload is optional, not required).
- Train CLI is offline, cache-first, refuses without opt-in env (same spirit as `AIAND_SMOKE=1`). Shares spend file and budget limiter.
- Teacher: cheap-then-escalate, exclude providers of measured trio ∪ live fallback; this org pins Motif → GLM. Soft-cap escalate ≤25%. Unlabeled ≠ fake.
- $100 smoke sizes are ceilings, not production floors: teacher ≤1000 rows, sparse gold ≤200 × Flash+trio, dense/cal ≤100 × eligible except K3. Stop if spend file would exceed the configured budget.
- Do not run dump F2P harness, Verified, Terminal-Bench, or K3 gold in this spec.
- Do not change default `BUDGET_LIMIT_USD` in code from 15; document setting 100 for smoke.
- Provider adapter stays injectable so tests never call aiand.

Decision shape (contract; from the observability prototype, not a demo):

```
Decision:
  model                 # served pick
  phase, effort
  path                  # rules | trained | shadow
  rule                  # threshold | max_regret | fallback_declined
  complexity_bin        # trivial|standard|hard|frontier | omit if scorer_down
  confidence            # winner P(success) | omit if scorer_down
  p_success             # id → float, eligible only
  threshold, max_regret # trained knobs (probabilities)
  reason_codes[]
  candidates[]          # eligible ids
  baseline_model_id
  trained_selected      # shadow only
```

## Testing Decisions

A good test asserts what a client can observe: HTTP status, served `model` / `X-Router-Model`, trained/shadow headers, JSONL fields, whether the fake provider was called, and that spend does not move when the job is refused. Tests do not assert sklearn internals, YAML parse details, or httpx call shapes.

**Single seam: the ASGI app with a fake aiand upstream** (same as today’s gateway suite). Inject the provider, spend log, JSONL path, cache dir, scorer artifact path, and `TRAINED_PATH`. Drive `POST /v1/chat/completions`.

Cover on that seam:

- `TRAINED_PATH=shadow`: served model is the rules pick; JSONL `path=shadow`; `trained_selected` present; `X-Router-Trained-Would` set; provider called with the **rules** id
- `TRAINED_PATH=trained` with a fixture Scorer: served model is the cheapest-above-bar id; `path=trained`; `X-Router-Reason` absent; Confidence and Complexity-Bin present
- scorer artifact missing: `path=rules`, reason_code `scorer_down`, no Confidence, served model is rules/fallback — not the learned stub
- `TRAINED_PATH=off`: identical to today’s rules headers (Reason still present); no trained fields required
- max_regret: a cheaper model more than max_regret behind the top scorer is not served
- threshold: a model below threshold is not served even if cheapest
- fallback_declined when none clear the bar: fallback model, `rule=fallback_declined`
- eligible set: tools present → no no-tools model in `candidates` / `p_success` keys
- effort header `low|medium|high|max` changes threshold/max_regret from `trained_effort`
- savings vs most expensive **eligible** (allow-list without K3 → baseline is not K3)
- `learned_wins.json` on must not switch shadow/trained to highest-AA stub
- train CLI without opt-in env: no provider calls
- JSONL redaction still strips secrets

Prior art: `tests/test_gateway.py` (`FakeProvider`, `TestClient`, JSONL assertions). Add cases there or a sibling test module that still uses `create_app` + `FakeProvider` — do not add a second HTTP stack.

Live aiand (teacher/gold) is not CI. Opt-in smoke only, credit owner present.

If this seam does not match what you want (for example unit-test the Scorer pick with no HTTP), say so before `/implement`. The rest of the spec does not depend on a different seam.

## Out of Scope

- Flashlight agent, OpenCode snippets, playground, replay-page redesign
- Pioneer clone: dashboard, Routing Playground, session-savings API, Anthropic Messages, OpenAI Responses, `auto_v*`, FireConnect, `xhigh`, BYOK, `x-routing-preference`
- Replacing the rules router
- Live chat LLM as the hop; live embed; Rec B; Nebius hard-require
- Production floors: smith ingest at spec n, sparse 4000, dense/retune n≥300, bootstrap resolve harness, SWE-bench Verified/Lite, Terminal-Bench, Multi-SWE-RL
- K3 gold cells; spending past `BUDGET_LIMIT_USD`
- Promoting smoke weights as if the Verified gate passed
- Operating aiand multi-tenant infra; production flywheel object store
- Invented savings %

## Further Notes

Production algorithm, dumps, promotion bars, retrain cadence, and flywheel store: [`.scratch/trained-router/spec.md`](../trained-router/spec.md). Do not relitigate those floors here.

`$100` buys a **labeled smoke Scorer**, not Pioneer’s unpublished training set. README must say weights are `not_spec_floors`.

Build order for the implementing agent: fake-provider tests for shadow/trained/scorer_down → Scorer + pick + headers/JSONL → opt-in teacher/gold CLI → fit artifact → load on hop. Do not spend credits until the HTTP seam is green.
