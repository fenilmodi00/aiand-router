# Research (after the proxy)

Inspiration, not code we copied:

- **Pioneer** — quality threshold / max-regret / predicted success. We shipped a phase bar + cheapest eligible AA prior, not Pioneer’s score formula or max-regret.
- **FireRouter** — OpenAI-compatible gateway, streaming, tools, provider pass-through. We hold the provider key; clients send a router key (no BYOK).
- **LLMRouter / RouterArena / CrossRouter** — training and leaderboard machinery. Out of scope until a 3×5 cache beats rules. LearnedRouter is an untrained stub behind the same `Decision` interface.
- **vLLM Semantic Router** — full Go/K8s stack. Not used.

AA Intelligence Index scores in the registry are public priors (`measured_on: not_aiand`). They are not aiand-hosted measurements. Do not quote them as provider quality.

Licenses: we did not vendor third-party router code. Ideas only.
