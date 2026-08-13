# Architecture

The product is an OpenAI-compatible **gateway**. Coding agents change `baseURL` and send `model: router/auto`. A thin flashlight client is a demo, not the product.

```
OpenCode / flashlight / eval
        │  Bearer ROUTER_API_KEY
        ▼
FastAPI  /v1/chat/completions  /v1/models  /health  /replay
        │  detect phase → hard constraints → pick cheapest above bar
        │  (or pin a registry id for baselines)
        ▼
aiand  Authorization: AIAND_API_KEY
```

Per-step routing uses six phases: `discover`, `plan`, `edit`, `tool`, `debug`, `summarize`. Draft names (`planning`, `code_generation`, …) alias onto those six. Missing `x-agent-phase` is normal; heuristics fill in.

Rules selection: filter enabled / allow-list / tools / JSON / streaming / context / max output / budget / AA present / premium floor, then cheapest blended `$/1M`. Learned selection shares that eligible set and stays dark unless a cache comparison says it won.

Tests drive the ASGI app with a fake aiand upstream. CI never calls the provider. Opt-in smoke (`AIAND_SMOKE=1`) is the only live path.

Replay is one HTML page over `data/requests.jsonl`. Spend is a process-local file gated by `BUDGET_LIMIT_USD`.
