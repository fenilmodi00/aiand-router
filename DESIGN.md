# AIand Coding Router — locked design

Grilled from `Draft_agnet.md`. This file wins when the draft disagrees.

## Product

OpenAI-compatible gateway. Clients send `model: router/auto`. The router picks an aiand model per request.

The product is the router. A thin flashlight agent is a demo client, not the deliverable. OpenCode is the real-harness proof. Cursor is out.

## Settled decisions

| Item | Choice |
| --- | --- |
| Win | Live demo + tiny cached comparison (3 models × ~5 tasks) |
| Audience | Hackathon judges / aiand |
| Credits | ~$5 rehearsal, ~$10 matrix, ~$15 reserve. Soft `BUDGET_LIMIT_USD` in the gateway |
| Who spends | One person. Every paid call uses the request cache |
| Models | All 9 in the registry. Policy is not “highest AA” |
| Index | Artificial Analysis Intelligence Index as prior. Label `source: artificial_analysis`, `measured_on: not_aiand`. Overwrite only where the 3×5 cache has data |
| Policy | Phase sets a quality bar. Cheapest eligible model whose index ≥ bar. K3 only if bar is high or `x-routing-effort: max` |
| Client model | `router/auto`. Optional `x-allowed-models`, `x-routing-effort`, `x-agent-phase` |
| Auth | Gateway holds `AIAND_API_KEY`. Clients send `ROUTER_API_KEY` |
| Phases | `discover`, `plan`, `edit`, `tool`, `debug`, `summarize` |
| Third-party | Missing phase is normal. Heuristics from tools / messages |
| Escalate | Empty, timeout, rate limit, invalid tool JSON. Flashlight may POST structured test outcome |
| Dashboard | One HTML page over JSONL (later) |
| Measured trio | `qwen/qwen3.6-27b`, `moonshotai/kimi-k2.7-code`, `deepseek-ai/deepseek-v4-pro` |
| Learned router | Module may exist. Stays dark unless the 3×5 cache beats rules |
| Eval now | 5 seeded tasks, 3 executed baselines (premium / Kimi-only / adaptive) |
| Eval later | 50–100 tasks, more baselines — after the replay exists |
| Cut | Cursor, K8s, Semantic Router, docker-compose, Modal |

## Do not do first

Learned training pipeline, 50–100 SWE tasks, 8 executed baselines, hosting models on Modal, inventing a savings %.

## Build order

1. This gateway: `/v1/chat/completions` + streaming + tools + registry + rules
2. One streamed tool-call smoke test against aiand
3. Flashlight agent + OpenCode snippet
4. 3×5 cache + replay page
5. LearnedRouter only if the cache beats rules
