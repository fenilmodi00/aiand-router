# Named savings baseline

Type: grilling
Status: resolved
Blocked by: none
Part of: [Production trained coding router](../map.md)

## Question

When the spec reports **savings**, what is the **named baseline** every number is versus?

Pioneer uses most-expensive candidate and/or a frontier list price (example: Opus). We have no Opus. Candidates: always-K3, always-fallback, most expensive eligible on that request, or premium-only (Kimi Code / Pro). Must stay measured, never an invented %.

HITL — do not resolve without the human.

## Answer

**Named savings baseline = `most_expensive_eligible`.** Rank this request’s eligible set with the same list-price unit cost the gateway already uses (`0.4·input_or_cached + 0.6·output`). Log `baseline_model_id` every time. Savings = baseline cost − selected cost; ≥ 0 by construction. Never an invented %.

Kimi K3 is today’s catalog ceiling (premium / Fable analog) and will be that id whenever K3 is eligible. Do **not** hard-code K3: allow-list, budget, and effort can drop it; a newer catalog max should become the baseline without a spec edit.

**Not savings:** cost vs the rules router. That is **rules cost delta** — promotion gate and shadow only.

Rejected: `catalog_max` / always-K3 (inflates when K3 was ineligible), always-fallback, always-rules, premium-only (Code/Pro), dual README stamp vs K3. Ex-ante vs ex-post dollars stay on [Observability Decision contract](09-observability-decision-contract.md).

## Comments

- Grill: Q1 → A (`most_expensive_eligible`; K3 is the ceiling when eligible, not a pinned id). Q2 → yes, split savings vs rules cost delta.
