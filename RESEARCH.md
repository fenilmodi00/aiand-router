# Research (after the proxy)

Inspiration, not code we copied. Competitor dump: `.scratch/competitor-router-research.md`. Local verdict: `.scratch/router-vs-pioneer-firerouter.md`.

- **Pioneer** — trained coding router: calibrated P(success) per candidate, threshold + max-regret, effort presets including `xhigh`, dashboard metadata (`confidence`, `rule`, `savings`, `reason_codes`), Anthropic + OpenAI Responses, harness hooks. We shipped phase bars + a Pioneer-inspired weighted score + max-regret on AA points, not their trained classifier.
- **FireRouter** — research-preview binary open↔Opus 4.8 BYOK router (`x-routing-preference` 1–5). We hold the aiand key; clients send a router key (no BYOK). Not the same as Fireworks deployment routers.
- **LLMRouter / RouterArena / CrossRouter** — training and leaderboard machinery. Production trained-router proposal (not this demo’s learned stub): [`.scratch/trained-router/spec.md`](.scratch/trained-router/spec.md). LearnedRouter in this repo stays an untrained stub behind the same `Decision` interface until 3×5 beats rules (`DESIGN.md`).
- **vLLM Semantic Router** — full Go/K8s stack. Not used.

Neither Pioneer nor FireRouter publishes router quality evals, TTFT overhead, or an average savings %. AA Intelligence Index scores in the registry are public priors (`measured_on: not_aiand`). They are not aiand-hosted measurements. Do not quote them as provider quality.

Licenses: we did not vendor third-party router code. Ideas only.
