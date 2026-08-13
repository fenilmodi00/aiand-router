# Competitor router research: Pioneer Model Router vs Fireworks FireRouter

Primary-source notes for comparing a self-hosted OpenAI-compatible coding router (AIand Coding Router) against two commercial routers.

**Scope:** official docs only. Indexes: [Pioneer llms.txt](https://docs.pioneer.ai/llms.txt), [Fireworks llms.txt](https://docs.fireworks.ai/llms.txt). Fetched 2026-08-13.

**Not used:** blogs, tweets, third-party writeups, inferred internals.

**AIand context (local product, not a competitor claim):** OpenAI-compatible proxy; clients send `model: router/auto`; hard constraints then predicted success vs phase bar; effort `low|medium|high|max`; Pioneer-style score; `x-allowed-models`; response headers `X-Router-Model` / `X-Router-Reason`; OpenCode is the real harness; learned routing stays dark until it beats rules. See repo `README.md` / `.scratch/aiand-coding-router/spec.md`.

---

## How to read this note

Every factual claim below is followed by its exact official URL. If a capability AIand might still need is listed, it is only because the competitor **documents** it — not because we measured it.

**Published quality / savings / SLA numbers:** almost none on either doc site for the routers themselves. That absence is documented explicitly.

---

## Snapshot (for comparison)

| Dimension | Pioneer Model Router | Fireworks FireRouter | AIand Coding Router (ours) |
| --- | --- | --- | --- |
| Positioning | Coding-task router; cheapest model that clears a quality bar | Any LLM workload; cheaper open vs closed-source quality | Coding-agent steps on aiand models |
| Routing mechanism | Trained router: classify complexity → calibrated P(success) per candidate → cheapest that clears threshold + max_regret | Score each request independently; **binary** redirect (open) vs pass-through (closed) | Rules: hard constraints → phase bar → effort pick (cheapest / Pioneer score / strongest AA) |
| Candidate pool | Multi-model (DeepSeek Flash/Pro, GLM 5.2, Claude Sonnet/Opus, GPT-5.5) | Fixed pair: GLM 5.2 ↔ Claude Opus 4.8 | aiand catalog only (Flash, Gemma, GPT-OSS, Qwen, Motif-3, Kimi, DeepSeek Pro, GLM, K3) |
| Policy knobs | threshold, max_regret, fallback, allowed_models, effort presets `low…max` | `x-routing-preference` 1–5 (quality ↔ savings) | `x-routing-effort`, `x-agent-phase`, `x-allowed-models`, `x-latency-limit`, max-regret, budget |
| Wire formats | Native + OpenAI chat/completions/responses + Anthropic messages | Fireworks inference: Chat Completions + Anthropic Messages | OpenAI `/v1/chat/completions` only |
| Virtual model ID | `pioneer/auto` (+ versioned `pioneer/auto_v1.*`, `pioneer/general` in catalog) | `firerouter` / `fireworks/firerouter` / `accounts/fireworks/routers/firerouter` | `router/auto` |
| Observability | Dashboard + `inferences.metadata.model_routing`; `pioneer_routed_model` / `pioneer_savings`; Codex session-savings API | Docs do **not** document selected_model / confidence / savings metadata | `X-Router-*` headers + `data/requests.jsonl` + `/replay` |
| Fallback | Configured fallback if no candidate clears bar **or router unreachable** (no error) | Pass-through fails with provider 401 if Anthropic key missing; no documented “fallback model” | Configured fallback when nothing eligible; one-shot escalate on empty/timeout/429/5xx/bad tool JSON |
| Billing | Pioneer credits (1 credit = $0.01); included credits can be **router-only** | BYOK: Fireworks key pays redirect; Anthropic key pays pass-through; keys not stored | Self-hosted; gateway holds `AIAND_API_KEY`; client sends `ROUTER_API_KEY`; soft USD budget |
| Harnesses | Claude Code, Codex, Cursor (chat only), OpenCode, OpenClaw, Hermes | FireConnect: Claude Code, OpenCode, Codex, Pi, VS Code; Cursor + Deep Agents need workspace BYOK; LiteLLM | OpenCode documented; Cursor not required |
| Maturity | Production product page; “currently works with coding tasks” | **Research preview**; APIs/pair may change | Hackathon / self-hosted |
| Published router evals | **None** on docs | **None** on docs | We refuse invented savings % |

---

## 1. Pioneer Model Router

### 1.1 Product positioning

Pioneer’s platform is broader than the router: fine-tuning, evaluation, and deployment of encoder (GLiNER) and decoder (LLM) models, plus drop-in OpenAI/Anthropic inference. ([https://docs.pioneer.ai/introduction.md](https://docs.pioneer.ai/introduction.md), [https://docs.pioneer.ai/llms.txt](https://docs.pioneer.ai/llms.txt))

The **Model Router** is specifically a coding router:

> “The Pioneer Router picks the cheapest model that meets your quality bar on every **coding** request.” ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

> “Model Routing **currently works with coding tasks**.” ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

Problem framed: agentic coding agents run hundreds to thousands of LLM calls per session; not every call needs a frontier model; autonomous agents have no mechanism to switch models themselves. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

Claude Code docs call it the **Code Router**. ([https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md))

**What they are NOT (implicit / adjacent):** Pioneer is not only a coding router — the company is an SLM fine-tuning + inference platform. The router is one product surface. FAQ still describes Pioneer as making fine-tuning small language models simple. ([https://docs.pioneer.ai/faq.md](https://docs.pioneer.ai/faq.md), [https://docs.pioneer.ai/introduction.md](https://docs.pioneer.ai/introduction.md))

OpenClaw troubleshooting expects catalog IDs matching `pioneer/(auto|auto_v1|general)` and says versioned entries such as `pioneer/auto_v1.1`, `pioneer/auto_v1.2`, and **`pioneer/general`** appear when exposed for the key. That implies a non-`auto` / possibly non-coding router ID exists in the live catalog, but the router concept page still says routing currently works with coding tasks. ([https://docs.pioneer.ai/openclaw.md](https://docs.pioneer.ai/openclaw.md), [https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

### 1.2 How routing actually works

Documented pipeline ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md)):

1. The router is a **low-latency model router trained on coding tasks**.
2. It **reads the messages** in each request.
3. It **classifies task complexity** from the conversation (example: trivial lookup vs multi-file refactor).
4. It produces a **calibrated success probability for each candidate model** on this specific task (score 0–1 = predicted likelihood of succeeding).
5. It **selects the cheapest model whose score clears configured thresholds**.
6. If no candidate clears the bar, **or the router is unreachable** (transport error or timeout), the request **falls back to the configured fallback model without error**. The fallback always runs the full inference path.

This is **multi-candidate scoring**, not a binary open-vs-closed redirect.

**Not documented:** architecture of the classifier (model size, features, whether it is a separate SLM vs embedding vs rules), latency budget in ms, whether scoring is local or a sidecar RPC, whether it is sticky across a conversation.

### 1.3 Candidate model pool

Router page table ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md)):

| Model | Provider |
| --- | --- |
| DeepSeek V4 Flash | DeepSeek |
| DeepSeek V4 Pro | DeepSeek |
| GLM 5.2 | ZhipuAI |
| Claude Sonnet 4.6 | Anthropic |
| GPT-5.5 | OpenAI |
| Claude Opus 4.7 | Anthropic |

> “We are continue adding more coding models to the candidate pool. Check the platform for the most up-to-date list.” ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

Restrict via **Candidate Models** / `allowed_models`. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

**Catalog inconsistency (same doc site, same day):** serverless inference snapshot lists Claude Fable 5 / Haiku 4.5 / Opus 5 / Opus 5 Fast / Sonnet 5, GPT-5.5 + GPT-5.6 Luna/Terra/Sol, DeepSeek V4 Flash 0731, GLM 5.2 / GLM 5.2 Fast, Kimi K2.6 / K2.7 Code / K3 / K3 Fast — not Sonnet 4.6 or Opus 4.7. Changelog deprecates Opus 4.x → Opus 5, Sonnet 4.5/4.6 → Sonnet 5, DeepSeek V4 Pro → DeepSeek V4 Flash, sunset starting **2026-08-14**. ([https://docs.pioneer.ai/concepts/models.md](https://docs.pioneer.ai/concepts/models.md), [https://docs.pioneer.ai/changelog.md](https://docs.pioneer.ai/changelog.md))

Live source of truth: `GET /base-models` and `GET /v1/models`. ([https://docs.pioneer.ai/concepts/models.md](https://docs.pioneer.ai/concepts/models.md), [https://docs.pioneer.ai/concepts/inference.md](https://docs.pioneer.ai/concepts/inference.md))

OpenCode claims a catalog of **70+ models** for `/models`, distinct from the 6-row router candidate table. ([https://docs.pioneer.ai/opencode.md](https://docs.pioneer.ai/opencode.md))

### 1.4 Policy parameters

Documented on the router page. **How a client actually sets them (header vs body vs dashboard) is not shown in the API docs fetched.** ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

**Threshold** — minimum calibrated success probability. Model below this floor is never selected, even if cheapest.

- Lower (e.g. `0.10`) → more aggressive savings.
- Higher (e.g. `0.50`) → only route when confident; fall back more often.

**Max regret** — max allowed probability gap between chosen model and top-scoring candidate. Example: cheapest qualifying scores 0.80, best scores 0.96 → gap 0.16; default `0.15` → move up. “Never pick a model more than X worse than the best available option.”

- Lower → stay closer to top model; fewer savings.
- Higher → accept wider quality gap for lower cost.

**Fallback model** — used when router declines (no candidate cleared threshold) or router service unreachable. Always full inference path. If `allowed_models` is set, fallback is automatically pinned to the **first allowed model** unless specified explicitly.

**allowed_models** — optional allowlist. Use cases: provider-only (e.g. Anthropic-only), drop models that underperform on your codebase, cost caps by excluding expensive candidates.

**Routing effort presets** ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md)):

| Tier | Threshold | Max regret | Candidate pool (as documented) |
| --- | --- | --- | --- |
| `low` | 0.05 | 0.30 | Cheapest models, max savings |
| `medium` | 0.10 | 0.20 | Good quality, good savings |
| `high` | 0.20 | 0.15 | Recommended settings |
| `xhigh` | 0.35 | 0.08 | Prefer stronger models |
| `max` | 0.60 | 0.03 | Best model every time |

Note vs AIand: Pioneer has **`xhigh`** between `high` and `max`; AIand uses `low|medium|high|max` without `xhigh`. Pioneer `high` is labeled “Recommended”; AIand default is `medium`.

### 1.5 Request API

**Auth:** `X-API-Key` or `Authorization: Bearer`. Keys start with `pio_sk_`. No OAuth. ([https://docs.pioneer.ai/authentication.md](https://docs.pioneer.ai/authentication.md), [https://docs.pioneer.ai/api-reference/authentication.md](https://docs.pioneer.ai/api-reference/authentication.md), [https://docs.pioneer.ai/concepts/inference.md](https://docs.pioneer.ai/concepts/inference.md))

**Base URL:** `https://api.pioneer.ai` (native) / `https://api.pioneer.ai/v1` (OpenAI + Anthropic). ([https://docs.pioneer.ai/api-reference/overview.md](https://docs.pioneer.ai/api-reference/overview.md), [https://docs.pioneer.ai/concepts/inference.md](https://docs.pioneer.ai/concepts/inference.md))

**Virtual model:** `pioneer/auto` on Anthropic-compatible requests; Claude Code: `claude --model pioneer/auto`. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

Also accepted as auto-router aliases in harness hooks: `pioneer/auto`, `auto`, `anthropic/pioneer-auto`, `anthropic/pioneer/auto`, and names ending `/pioneer/auto`. ([https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md), [https://docs.pioneer.ai/codex.md](https://docs.pioneer.ai/codex.md))

**Wire formats** ([https://docs.pioneer.ai/concepts/inference.md](https://docs.pioneer.ai/concepts/inference.md), [https://docs.pioneer.ai/api-reference/inference/openai-compatible.md](https://docs.pioneer.ai/api-reference/inference/openai-compatible.md), [https://docs.pioneer.ai/api-reference/inference/anthropic-compatible.md](https://docs.pioneer.ai/api-reference/inference/anthropic-compatible.md)):

| Format | Paths |
| --- | --- |
| Native Pioneer | `POST /inference` |
| OpenAI-compatible | `POST /v1/chat/completions`, `/v1/completions`, `/v1/responses`, `/v1/embeddings`; `GET /v1/models` |
| Anthropic-compatible | `POST /v1/messages` |

Streaming supported on chat-shaped endpoints, not native `/inference`. ([https://docs.pioneer.ai/concepts/inference.md](https://docs.pioneer.ai/concepts/inference.md))

Codex uses **Responses API** (`wire_api = "responses"`) against `https://api.pioneer.ai/v1`. ([https://docs.pioneer.ai/codex.md](https://docs.pioneer.ai/codex.md))

Claude Code uses Anthropic Messages with `ANTHROPIC_BASE_URL=https://api.pioneer.ai` (no `/v1` suffix in the env example). ([https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md))

OpenCode / Hermes / OpenClaw / Cursor use OpenAI-compatible `https://api.pioneer.ai/v1`. ([https://docs.pioneer.ai/opencode.md](https://docs.pioneer.ai/opencode.md), [https://docs.pioneer.ai/hermes.md](https://docs.pioneer.ai/hermes.md), [https://docs.pioneer.ai/openclaw.md](https://docs.pioneer.ai/openclaw.md), [https://docs.pioneer.ai/cursor.md](https://docs.pioneer.ai/cursor.md))

**Prompt caching (relevant to routing cost):** OpenAI/GPT family caches automatically; Claude is opt-in via `cache_control` — Pioneer **forwards as-is and never adds markers**. Cursor autorouter alias **must** be `pioneer/auto-claude-opus-4` so Cursor emits Anthropic `cache_control`; plain `pioneer/auto` silently disables prompt caching. ([https://docs.pioneer.ai/concepts/inference.md](https://docs.pioneer.ai/concepts/inference.md), [https://docs.pioneer.ai/api-reference/prompt-caching.md](https://docs.pioneer.ai/api-reference/prompt-caching.md), [https://docs.pioneer.ai/cursor.md](https://docs.pioneer.ai/cursor.md))

**Persistence:** default stores every inference; `store: false` skips payload storage but still bills. ([https://docs.pioneer.ai/concepts/inference.md](https://docs.pioneer.ai/concepts/inference.md))

### 1.6 Observability

- Routing details stored in **`inferences.metadata.model_routing`**. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
- Dashboard: Router detail page + inference detail view; live monitoring at [https://agent.pioneer.ai/routers](https://agent.pioneer.ai/routers). ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
- **Routing Playground:** paste prompt or conversation; shows selected model, confidence, expected cost savings vs routing everything to fallback. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

Every inference detail `routing` block when request went through the router ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md)):

| Field (docs wording) | Meaning |
| --- | --- |
| selected model | Model that actually ran |
| confidence | Calibrated success probability for the selected model |
| rule | `threshold`, `max_regret`, or `fallback_declined` |
| savings | Cost saved vs routing the same request to the **most expensive candidate** |
| savings fraction | Same, as fraction of most expensive candidate’s cost (0–1) |
| reason_codes | Diagnostic codes from the router’s internal classifiers |

Also logged: expected cost. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

**Response metadata for harnesses:**

- Anthropic-compatible responses include `pioneer_routed_model` and `pioneer_savings` (streaming `message_start` frames and non-streaming bodies). ([https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md))
- `pioneer_savings` = per-1M-token **price difference** vs a frontier reference (default example `claude-opus-4-7`). Stop hook multiplies by actual token usage. On routed-model change (cold prompt cache), cache-write savings are dropped. ([https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md))
- Header/tip: `X-Pioneer-Router-Tip` / `x-pioneer-router-tip` nudges direct (pinned) models toward `pioneer/auto`. ([https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md))
- Codex strips custom fields from on-disk rollout; Pioneer accumulates savings server-side keyed by Codex `prompt_cache_key` (session id). Hook: `GET {base}/codex/session-savings/{session_id}` with Bearer key, 3s timeout. Response fields used: `found`, `savings_usd`, `baseline_model`. ([https://docs.pioneer.ai/codex.md](https://docs.pioneer.ai/codex.md))

Inference history API: `GET /inferences`, `GET /inferences/:id`, `POST /inferences/:id/feedback` (Adaptive Inference — fine-tune loop, not router scoring). Filters include `latency_min` / `latency_max` (ms). ([https://docs.pioneer.ai/api-reference/inference/history.md](https://docs.pioneer.ai/api-reference/inference/history.md), [https://docs.pioneer.ai/concepts/inference.md](https://docs.pioneer.ai/concepts/inference.md))

### 1.7 Fallback / failure behavior

- No candidate clears threshold → fallback model, **without error**. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
- Router unreachable (transport error or timeout) → same fallback, without error. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
- Rule name for decline: `fallback_declined`. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
- Rate limit: chat-shaped endpoints 5,000/min per user; edge 100,000/60s; `429` + `Retry-After`. ([https://docs.pioneer.ai/api-reference/rate-limits.md](https://docs.pioneer.ai/api-reference/rate-limits.md))
- Out of credits: `402` `out_of_credits`. Included plan credits can be **router-only**; calling a model **directly** instead of `pioneer/auto` can return `402` `direct_model_requires_credits`. Monthly overage ceiling: `403` `credit_ceiling_reached`. ([https://docs.pioneer.ai/api-reference/errors.md](https://docs.pioneer.ai/api-reference/errors.md), [https://docs.pioneer.ai/api-reference/rate-limits.md](https://docs.pioneer.ai/api-reference/rate-limits.md))
- Anthropic-compatible only: `529` overloaded when upstream Claude is saturated. ([https://docs.pioneer.ai/api-reference/errors.md](https://docs.pioneer.ai/api-reference/errors.md))
- On-demand cold start: `425 Too Early` + `Retry-After`. ([https://docs.pioneer.ai/api-reference/errors.md](https://docs.pioneer.ai/api-reference/errors.md))
- Status: [https://pioneerai.statuspage.io](https://pioneerai.statuspage.io) / [https://status.pioneer.ai](https://status.pioneer.ai). ([https://docs.pioneer.ai/faq.md](https://docs.pioneer.ai/faq.md), [https://docs.pioneer.ai/api-reference/errors.md](https://docs.pioneer.ai/api-reference/errors.md))

**Not documented for the router:** mid-stream escalate, retry-to-stronger-model, or sticky conversation routing.

### 1.8 Latency characteristics

- Qualitative only: “**low-latency** model router.” ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
- No ms/TTFT/SLA number for the routing step on the docs fetched.
- Prompt caching “cuts cost and latency on repeated prompt prefixes.” ([https://docs.pioneer.ai/concepts/inference.md](https://docs.pioneer.ai/concepts/inference.md))
- Claude cache entries expire after **5 minutes** of inactivity; system prompt often needs **≥4096 tokens** for Anthropic caching. ([https://docs.pioneer.ai/api-reference/prompt-caching.md](https://docs.pioneer.ai/api-reference/prompt-caching.md))
- Encoder models described as fast/CPU; not the coding router. ([https://docs.pioneer.ai/faq.md](https://docs.pioneer.ai/faq.md))

### 1.9 BYOK / billing

**Not BYOK to Anthropic/OpenAI.** You pay Pioneer; Pioneer is a subprocessor consumer of Anthropic, OpenAI, Azure, Modal, etc. ([https://docs.pioneer.ai/trust-safety.md](https://docs.pioneer.ai/trust-safety.md))

Plans ([https://docs.pioneer.ai/pricing.md](https://docs.pioneer.ai/pricing.md)):

- Pro: $20/seat/month, $40/seat/month platform credits.
- Higher Pro-like tier in same page: $50/seat/month, $50 credits, SAML/SSO, inference-tracking opt-out.
- Credit top-ups; org credit hold up to $50,000/month.
- 1 credit = $0.01. ([https://docs.pioneer.ai/api-reference/rate-limits.md](https://docs.pioneer.ai/api-reference/rate-limits.md))

Serverless decoder list prices (snapshot; per 1M tokens) include e.g. Claude Opus 5 $5/$25, Sonnet 5 $2/$10, GPT-5.5 $5/$30, DeepSeek V4 Flash 0731 $0.14/$0.28, GLM 5.2 $1.50/$4.50, Kimi K2.7 Code $0.95/$4.00, Kimi K3 $3/$15. Cache multipliers: Anthropic 0.1× read / 1.25× write; GPT-5 family 0.1× read. Fireworks-served models (DeepSeek, GLM, Kimi) have per-model cache rates. ([https://docs.pioneer.ai/concepts/models.md](https://docs.pioneer.ai/concepts/models.md))

Savings display baseline in harness examples: **claude-opus-4-7**. Example copy: “Pioneer routing saved ~$1.43 this session (vs claude-opus-4-7)” — this is **example UI text**, not a published average. ([https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md), [https://docs.pioneer.ai/codex.md](https://docs.pioneer.ai/codex.md))

Data: by default Pioneer **may train on API data**; Pro/Enterprise can opt out of platform training; task-model Adaptive Inference still uses inference data. Default retention indefinite; `store: false` for ZDR per request. SOC 2 / ISO 27001 **in progress**, first audit expected November 2026. No DPA. ([https://docs.pioneer.ai/trust-safety.md](https://docs.pioneer.ai/trust-safety.md), [https://docs.pioneer.ai/faq.md](https://docs.pioneer.ai/faq.md))

### 1.10 Harness integrations

| Harness | Wire | Router ID | Notes | Source |
| --- | --- | --- | --- | --- |
| Claude Code | Anthropic Messages | `pioneer/auto` | Gateway model discovery; Stop hook for savings; `ANTHROPIC_CUSTOM_MODEL_OPTION` | [claude-code](https://docs.pioneer.ai/claude-code.md) |
| Codex CLI | OpenAI Responses | `pioneer/auto` | `model_catalog_json`; Stop hook hits `/codex/session-savings/{id}` | [codex](https://docs.pioneer.ai/codex.md) |
| Cursor | OpenAI chat (chat/plan panel only) | `pioneer/auto-claude-opus-4` | Composer / Cmd+K / tab **cannot** be routed; alias required for cache markers | [cursor](https://docs.pioneer.ai/cursor.md) |
| OpenCode CLI + Desktop | OpenAI-compatible | Pioneer Auto / `pioneer/auto` | Built-in Pioneer provider; optional Exa web search | [opencode](https://docs.pioneer.ai/opencode.md) |
| OpenClaw | OpenAI completions | `pioneer/auto` default | Custom provider until official; catalog sync via `/v1/models` | [openclaw](https://docs.pioneer.ai/openclaw.md) |
| Hermes Agent | chat_completions | `pioneer/auto` default | One-shot setup filters `anthropic/*` discovery aliases | [hermes](https://docs.pioneer.ai/hermes.md) |

Opus 4.8 integration page defers to Claude Code + `/model`. ([https://docs.pioneer.ai/api-reference/integrating-with-opus-4-8.md](https://docs.pioneer.ai/api-reference/integrating-with-opus-4-8.md))

Agent Skills `SKILL.md` covers Pioneer API for datasets/training/inference — **does not mention the router**. ([https://docs.pioneer.ai/guides/agent-skills.md](https://docs.pioneer.ai/guides/agent-skills.md))

Claude Code `/model` only shows IDs starting with `claude` or `anthropic`; Pioneer publishes aliases like `anthropic/pioneer/gpt-5.4`. Requires `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` and seeded `~/.claude/cache/gateway-models.json`. ([https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md))

### 1.11 Research preview / maturity caveats

No “research preview” label on the router page. Caveats that **are** documented:

- “Currently works with coding tasks.” ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
- Candidate pool still growing; check platform. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
- Large catalog sunset 2026-08-11 deprecate / 2026-08-14 sunset. ([https://docs.pioneer.ai/changelog.md](https://docs.pioneer.ai/changelog.md))
- Compliance program in progress. ([https://docs.pioneer.ai/trust-safety.md](https://docs.pioneer.ai/trust-safety.md))

### 1.12 Published quality metrics / evals / savings

**Router-specific: none.** No SWE-bench, no win-rate, no average % savings, no TTFT overhead.

Related but **not** router evals:

- Fine-tune evaluations report F1 / precision / recall. FAQ: F1 > 0.85 “production-ready for most NER and classification.” ([https://docs.pioneer.ai/faq.md](https://docs.pioneer.ai/faq.md), [https://docs.pioneer.ai/concepts/evaluations.md](https://docs.pioneer.ai/concepts/evaluations.md) via [llms.txt](https://docs.pioneer.ai/llms.txt))
- Adaptive Inference promotes checkpoints when performance improves. ([https://docs.pioneer.ai/introduction.md](https://docs.pioneer.ai/introduction.md))
- Harness savings lines are **per-session measured vs frontier list price**, with example `$1.43`, not a published benchmark. ([https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md))

---

## 2. Fireworks FireRouter

### 2.1 Product positioning

> “Route LLM requests between **closed-source and open models** with FireRouter.” ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))

> “FireRouter is a managed routing service for **any LLM workload**.” ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))

When to use: automatic cost optimization without picking a model per request; want closed-source quality (e.g. Claude Opus) on hard prompts but not every call; many straightforward requests (summaries, formatting, simple Q&A) can use a Fireworks open model; willing to send **both** a Fireworks API key and a provider API key. ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))

FireConnect models page: use `firerouter` when you want to “Auto-route easy work to open models, hard work to Claude Opus 4.8.” ([https://docs.fireworks.ai/ecosystem/fireconnect/models.md](https://docs.fireworks.ai/ecosystem/fireconnect/models.md))

### 2.2 What FireRouter is NOT

Explicit ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md)):

- **Not a deployment router.** Different from [deployment routers](https://docs.fireworks.ai/deployments/routers.md), which load-balance traffic across your own Fireworks deployments (A/B, migration, replica-weighted split).
- **Not request-sticky.** Each request is scored independently.

(There is a nuance: routing **preference** changes can be delayed because FireRouter **caches the routing decision within a conversation**. That is conversation-level cache of the *decision*, not request-sticky targeting. ([https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md)))

FireConnect is a **CLI that rewires harnesses** to Fireworks/FireRouter/Foundry — not the router itself. ([https://docs.fireworks.ai/ecosystem/fireconnect/overview.md](https://docs.fireworks.ai/ecosystem/fireconnect/overview.md))

`fireconnect demo` races Claude Code on Anthropic vs a **fixed** Fireworks challenger (default `glm-5p2-fast`); it is **not** a FireRouter quality eval. ([https://docs.fireworks.ai/ecosystem/fireconnect/demo.md](https://docs.fireworks.ai/ecosystem/fireconnect/demo.md))

### 2.3 Research preview / maturity

> “FireRouter is in **research preview**. APIs, routing behavior, and the models in the routing pair may change. This documentation is updated to reflect the current configuration.” ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))

Fireworks changelog page fetched 2026-08-13 contains **no** `FireRouter` / `firerouter` mention. ([https://docs.fireworks.ai/updates/changelog.md](https://docs.fireworks.ai/updates/changelog.md))

FireConnect FireRouter support: **v0.9.0+**. ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md), [https://docs.fireworks.ai/ecosystem/fireconnect/overview.md](https://docs.fireworks.ai/ecosystem/fireconnect/overview.md))

### 2.4 How routing actually works

Binary two-path router ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md)):

| Path | When | What runs | Billing |
| --- | --- | --- | --- |
| **Redirect** | Simple or low-complexity work | Fireworks open model (e.g. GLM 5.2) | Fireworks API key |
| **Pass-through** | Hard reasoning, judgment, or long context | Closed-source model (e.g. Claude Opus 4.8) | Provider API key (Anthropic) |

> “FireRouter scores each request independently and picks one of two paths.” ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))

> “You do not pick the target model per request; FireRouter decides based on **request complexity**.” ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))

Quickstart verification heuristic: trivial prompt (“rename foo to bar”) → expect fast response on open model; hard reasoning prompt → expect Opus 4.8. ([https://docs.fireworks.ai/ecosystem/firerouter/quickstart.md](https://docs.fireworks.ai/ecosystem/firerouter/quickstart.md))

**Not documented:** classifier vs ML model vs heuristics; score scale; threshold internals behind preference 1–5; whether both candidates are scored or only a complexity score vs a cutoff; multi-candidate ranking.

Conversation cache: “FireRouter caches routing decision within a conversation, so preference changes can take a few turns to take effect without restarting your client.” ([https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md))

### 2.5 Candidate model pool (routing pair)

Current pair ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md)):

| Role | Model |
| --- | --- |
| Pass-through (closed-source) | **Claude Opus 4.8** (`claude-opus-4-8`) |
| Redirect (open) | **GLM 5.2** (`glm-5p2`) |

“These models are subject to change as FireRouter is updated.” Anthropic key required because pass-through target is Opus 4.8. ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md), [https://docs.fireworks.ai/ecosystem/firerouter/authentication.md](https://docs.fireworks.ai/ecosystem/firerouter/authentication.md))

Without an Anthropic key, FireRouter “still redirects to open models but **cannot pass through** to Claude Opus 4.8.” ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))

GLM 5.2 serverless list price (Fireworks, not FireRouter-specific): Standard **$1.40 / $0.14 / $4.40** per 1M (input / cached / output). GLM 5.2 Fast: **$2.10 / $0.21 / $6.60**. ([https://docs.fireworks.ai/serverless/pricing.md](https://docs.fireworks.ai/serverless/pricing.md))

FireConnect default **non-FireRouter** coding catalog is broader (Kimi latest/fast, GLM latest/fast, DeepSeek V4 Flash/Pro, MiniMax, Qwen Plus, Kimi K2.7 Code, etc.) — that is FireConnect model picking, not FireRouter’s pair. ([https://docs.fireworks.ai/ecosystem/fireconnect/models.md](https://docs.fireworks.ai/ecosystem/fireconnect/models.md))

### 2.6 Policy parameters

**Only documented dial:** `x-routing-preference` integer **1–5** (or names). Missing/invalid/out-of-range → **balanced (`3`)**. ([https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md))

| Value | Name | Behavior |
| --- | --- | --- |
| `1` | `max-intelligence` | Strongest bias toward pass-through; quality critical |
| `2` | `more-intelligence` | Favor closed-source on borderline requests |
| `3` | `balanced` | Default; “FireRouter's standard tradeoff” |
| `4` | `more-savings` | Favor open-model redirects on borderline requests |
| `5` | `max-savings` | Strongest bias toward redirect; maximize savings |

When to adjust ([https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md)):

- High-volume simple work → try `4` or `5` (summaries, formatting, straightforward Q&A).
- Quality-critical (security review, complex reasoning, nuanced writing) → try `1` or `2`.
- Evaluating routing → start at `3`, move one step at a time, compare cost and output quality.

**Not documented for FireRouter:** threshold, max_regret, allowed_models, fallback model, effort presets, phase headers.

FireConnect flag `--routing-preference` on `on` for Claude Code, OpenCode, Pi, VS Code. **Codex, Cursor, and Deep Agents do not support `--routing-preference`.** ([https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md), [https://docs.fireworks.ai/ecosystem/fireconnect/cli-reference.md](https://docs.fireworks.ai/ecosystem/fireconnect/cli-reference.md))

LiteLLM: optional header `x-routing-preference: 4`. ([https://docs.fireworks.ai/ecosystem/firerouter/litellm.md](https://docs.fireworks.ai/ecosystem/firerouter/litellm.md))

### 2.7 Request API

**Endpoint:** `https://api.fireworks.ai/inference/v1` ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))

| Wire format | Path |
| --- | --- |
| Chat Completions | `https://api.fireworks.ai/inference/v1/chat/completions` |
| Anthropic Messages | `https://api.fireworks.ai/inference/v1/messages` |

**Model IDs** ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md)):

- `firerouter` (canonical short)
- `fireworks/firerouter`
- `accounts/fireworks/routers/firerouter`

LiteLLM **must** use the full router resource ID in `litellm_params.model`. Short names like `fireworks_ai/firerouter` are rewritten to `accounts/fireworks/models/firerouter`, which FireRouter does **not** recognize. ([https://docs.fireworks.ai/ecosystem/firerouter/litellm.md](https://docs.fireworks.ai/ecosystem/firerouter/litellm.md))

Claude Code manual setup uses `firerouter[1m]` (1M context suffix). ([https://docs.fireworks.ai/ecosystem/firerouter/claude-code.md](https://docs.fireworks.ai/ecosystem/firerouter/claude-code.md))

Anthropic Messages example also sends `anthropic-version: 2023-06-01`. ([https://docs.fireworks.ai/ecosystem/firerouter/quickstart.md](https://docs.fireworks.ai/ecosystem/firerouter/quickstart.md))

### 2.8 Authentication / BYOK / billing

BYOK contract ([https://docs.fireworks.ai/ecosystem/firerouter/authentication.md](https://docs.fireworks.ai/ecosystem/firerouter/authentication.md), [https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md)):

| Key | Header | Used for |
| --- | --- | --- |
| Fireworks `fw_...` | `Authorization: Bearer` or `X-Fireworks-Api-Key` (legacy `X-FireRouter-Fireworks-Key` also accepted) | FireRouter auth + redirected Fireworks inference |
| Anthropic `sk-ant-...` | `x-anthropic-api-key` (also `x-api-key` / Bearer for Anthropic clients) | Claude pass-through |

> “FireRouter **never stores** your provider keys server-side. You send them on each request.” ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))

LiteLLM can pin Anthropic key server-side via `extra_headers` (shared across callers) or leave it to each client. Developers auth to LiteLLM with a virtual key. Requires LiteLLM Proxy **v1.95.0**. ([https://docs.fireworks.ai/ecosystem/firerouter/litellm.md](https://docs.fireworks.ai/ecosystem/firerouter/litellm.md))

Fire Pass (`fpk_...`) is **rejected** for `--model firerouter` on **every** FireConnect harness; use `fw_...`. ([https://docs.fireworks.ai/ecosystem/fireconnect/overview.md](https://docs.fireworks.ai/ecosystem/fireconnect/overview.md), [https://docs.fireworks.ai/ecosystem/fireconnect/models.md](https://docs.fireworks.ai/ecosystem/fireconnect/models.md))

Cursor and Deep Agents need **workspace BYOK** (no local Anthropic key). ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md), [https://docs.fireworks.ai/ecosystem/fireconnect/cursor.md](https://docs.fireworks.ai/ecosystem/fireconnect/cursor.md), [https://docs.fireworks.ai/ecosystem/fireconnect/deepagents.md](https://docs.fireworks.ai/ecosystem/fireconnect/deepagents.md))

Claude Code can use a **Claude subscription** (OAuth) plus Fireworks key in `ANTHROPIC_CUSTOM_HEADERS`, or an Anthropic API key + Fireworks header. ([https://docs.fireworks.ai/ecosystem/firerouter/claude-code.md](https://docs.fireworks.ai/ecosystem/firerouter/claude-code.md))

Fireworks platform ZDR default for open-model inference (not FireRouter-specific). ([https://docs.fireworks.ai/getting-started/glossary.md](https://docs.fireworks.ai/getting-started/glossary.md))

### 2.9 Observability

**FireRouter docs do not document** dashboard fields such as `selected_model`, confidence, rule, savings, or reason_codes.

What exists nearby:

- Fireworks analytics/usage count **server-acknowledged** requests; client-side failures before the server may not show. ([https://docs.fireworks.ai/guides/reliability.md](https://docs.fireworks.ai/guides/reliability.md))
- Dedicated deployment Prometheus metrics (TTFT, TPS, etc.) — not FireRouter. ([https://docs.fireworks.ai/getting-started/glossary.md](https://docs.fireworks.ai/getting-started/glossary.md))
- FireConnect Claude Code: `fireconnect claude usage` / `live` meter estimates **Fireworks spend from session logs** (Claude `/model` picker shows Anthropic list prices, not Fireworks rates). Not FireRouter-specific. ([https://docs.fireworks.ai/ecosystem/fireconnect/claude-code.md](https://docs.fireworks.ai/ecosystem/fireconnect/claude-code.md))
- Quickstart “verify routing” is manual: trivial vs hard prompt. ([https://docs.fireworks.ai/ecosystem/firerouter/quickstart.md](https://docs.fireworks.ai/ecosystem/firerouter/quickstart.md))

### 2.10 Fallback / failure behavior

Documented errors ([https://docs.fireworks.ai/ecosystem/firerouter/authentication.md](https://docs.fireworks.ai/ecosystem/firerouter/authentication.md)):

| Response | Cause |
| --- | --- |
| `401 Missing Fireworks API key` | Fireworks header missing/empty |
| `401 invalid Fireworks API key` | Key rejected |
| Pass-through fails with provider 401 | Anthropic key missing or wrong header |

No documented “if scorer is down, always use Opus” or “always use GLM” fallback analogous to Pioneer’s fallback model.

General Fireworks reliability (platform, not FireRouter-specific): retry 429/500/502/503/504; interactive timeout 30–60s; agentic 5–30 min. ([https://docs.fireworks.ai/guides/reliability.md](https://docs.fireworks.ai/guides/reliability.md))

### 2.11 Latency characteristics

FireRouter-specific:

- Qualitative: trivial prompts → “**fast** response routed to the open model.” ([https://docs.fireworks.ai/ecosystem/firerouter/quickstart.md](https://docs.fireworks.ai/ecosystem/firerouter/quickstart.md))
- No TTFT overhead, no router SLA.

Adjacent Fireworks latency claims (**not** FireRouter):

- Serverless has **no SLA** for latency or availability. Use on-demand or talk to sales. ([https://docs.fireworks.ai/faq-new/deployment-infrastructure/is-latency-guaranteed-for-serverless-models.md](https://docs.fireworks.ai/faq-new/deployment-infrastructure/is-latency-guaranteed-for-serverless-models.md))
- Fast serving path aims for **100+ tok/s**; same model quality, higher $/token. GLM 5.2 Fast ID: `accounts/fireworks/routers/glm-5p2-fast`. ([https://docs.fireworks.ai/serverless/serving-paths.md](https://docs.fireworks.ai/serverless/serving-paths.md), [https://docs.fireworks.ai/ecosystem/fireconnect/models.md](https://docs.fireworks.ai/ecosystem/fireconnect/models.md))
- FireRouter’s documented redirect target is `glm-5p2` (standard GLM 5.2), **not** GLM Fast, unless that changes. ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))
- Glossary: serverless “routed globally … for lowest latency and highest availability.” ([https://docs.fireworks.ai/getting-started/glossary.md](https://docs.fireworks.ai/getting-started/glossary.md))

### 2.12 Harness integrations

**FireConnect** is the recommended path: `fireconnect <harness> on --model firerouter` (v0.9.0+). ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))

Harness support matrix ([https://docs.fireworks.ai/ecosystem/fireconnect/overview.md](https://docs.fireworks.ai/ecosystem/fireconnect/overview.md)):

| Harness | Fireworks gateway | Fire Pass | Microsoft Foundry | FireRouter |
| --- | --- | --- | --- | --- |
| Claude Code | Yes | Yes | No | Yes |
| OpenCode | Yes | Yes | Yes | Yes |
| Codex | Yes | No | Yes | Yes |
| Pi | Yes | Yes | Yes | Yes |
| Cursor | Yes | Yes | Yes | Workspace BYOK |
| VS Code (Copilot Chat) | Yes | Yes | Yes | Yes |
| Deep Agents (`dcode`) | Yes | Yes | Yes | Workspace BYOK |

Notes:

- Fire Pass rejected for FireRouter on every harness. ([https://docs.fireworks.ai/ecosystem/fireconnect/overview.md](https://docs.fireworks.ai/ecosystem/fireconnect/overview.md))
- Claude Code first-connect default **main** is `firerouter` when Claude already has Anthropic auth or workspace BYOK; otherwise `kimi-fast-latest`. Other slots default to GLM Fast / DeepSeek Flash / Kimi Fast — not FireRouter. ([https://docs.fireworks.ai/ecosystem/fireconnect/claude-code.md](https://docs.fireworks.ai/ecosystem/fireconnect/claude-code.md))
- OpenCode: OpenAI-compatible adapter at `https://api.fireworks.ai/inference/v1`. ([https://docs.fireworks.ai/ecosystem/fireconnect/opencode.md](https://docs.fireworks.ai/ecosystem/fireconnect/opencode.md))
- Codex: Responses API (`wire_api = "responses"`); FireRouter BYOK via `ANTHROPIC_API_KEY` or `--anthropic-api-key`; no `--routing-preference`. MiniMax unsupported on Codex Responses path. ([https://docs.fireworks.ai/ecosystem/fireconnect/codex.md](https://docs.fireworks.ai/ecosystem/fireconnect/codex.md))
- Cursor: OpenAI BYOK into `state.vscdb`; **quit IDE** before `on`/`off`; some features may still use Cursor backend; server-side allowlist may block models. ([https://docs.fireworks.ai/ecosystem/fireconnect/cursor.md](https://docs.fireworks.ai/ecosystem/fireconnect/cursor.md))
- VS Code: Copilot **Pro/Enterprise** required; chat-completions custom endpoint. ([https://docs.fireworks.ai/ecosystem/fireconnect/vscode.md](https://docs.fireworks.ai/ecosystem/fireconnect/vscode.md))
- Pi: `~/.pi/agent/settings.json` + `models.json`. ([https://docs.fireworks.ai/ecosystem/fireconnect/pi.md](https://docs.fireworks.ai/ecosystem/fireconnect/pi.md))
- Deep Agents: `~/.deepagents/config.toml`. ([https://docs.fireworks.ai/ecosystem/fireconnect/deepagents.md](https://docs.fireworks.ai/ecosystem/fireconnect/deepagents.md))

**Manual Claude Code** (no FireConnect): edit `~/.claude/settings.json`; `ANTHROPIC_BASE_URL=https://api.fireworks.ai/inference`; `ANTHROPIC_MODEL=firerouter[1m]`; Fireworks key via `ANTHROPIC_CUSTOM_HEADERS`. Also maps other Claude slots to GLM Fast / Kimi / DeepSeek Flash. ([https://docs.fireworks.ai/ecosystem/firerouter/claude-code.md](https://docs.fireworks.ai/ecosystem/firerouter/claude-code.md))

**LiteLLM Proxy** for non-harness apps. ([https://docs.fireworks.ai/ecosystem/firerouter/litellm.md](https://docs.fireworks.ai/ecosystem/firerouter/litellm.md))

FireConnect source: [https://github.com/fw-ai/fireconnect](https://github.com/fw-ai/fireconnect) (official docs link; CLI is OSS, FireRouter service is not). ([https://docs.fireworks.ai/ecosystem/fireconnect/overview.md](https://docs.fireworks.ai/ecosystem/fireconnect/overview.md))

### 2.13 Published quality metrics / evals / savings

**None on FireRouter docs.** No % savings, no quality parity claim vs always-Opus, no eval leaderboard.

`fireconnect demo` measures speed/cost/quality for a **fixed** Fireworks model vs Anthropic Claude Code on toy HTML games; numbers are “measured from the run, not list-price estimates”; explicitly not fabricated if one side fails. Default challenger `glm-5p2-fast`, not `firerouter`. ([https://docs.fireworks.ai/ecosystem/fireconnect/demo.md](https://docs.fireworks.ai/ecosystem/fireconnect/demo.md))

---

## 3. Disambiguation: Fireworks deployment “Routers”

Unrelated product. A **Router** resource splits traffic across **your dedicated deployments** by replica count (weighted-random), for A/B, migration, stable alias. Multi-region deployments only. Model field: `accounts/<ACCOUNT_ID>/routers/<ROUTER_ID>`. ([https://docs.fireworks.ai/deployments/routers.md](https://docs.fireworks.ai/deployments/routers.md))

FireRouter overview explicitly says it is not this. ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))

US-only serverless also uses `accounts/fireworks/routers/...` paths (e.g. `kimi-k3-us`) — geo routers, not FireRouter. ([https://docs.fireworks.ai/ecosystem/fireconnect/models.md](https://docs.fireworks.ai/ecosystem/fireconnect/models.md))

---

## 4. What they implement that AIand might still need

Prioritized by how clearly the docs specify it and how far it is from what we already ship (`router/auto`, phase/effort/allowlist, Pioneer-style score, headers + JSONL replay, OpenCode).

### 4.1 High leverage vs our current gateway

1. **Trained / calibrated per-request P(success) over a multi-model pool** (Pioneer) vs our AA-prior + phase bar. Pioneer’s score is “predicted likelihood of succeeding on this task,” not a static index. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
2. **Explicit `reason` / `rule` enum** (`threshold` | `max_regret` | `fallback_declined`) plus **classifier `reason_codes`**. We expose `X-Router-Reason` with `score=`; they name the policy branch. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
3. **Savings accounting vs a named baseline**, on the response (`pioneer_savings` rate diff) and/or a session endpoint (`/codex/session-savings/{id}`), plus harness Stop hooks. We log cost and refuse an invented %. They still only claim per-request/session vs most expensive candidate or frontier list price — not a published average. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md), [https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md), [https://docs.pioneer.ai/codex.md](https://docs.pioneer.ai/codex.md))
4. **Dashboard + playground** (Pioneer `agent.pioneer.ai/routers`, Routing Playground). We have `/replay` over JSONL. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
5. **Router-unreachable fallback without failing the client** (Pioneer). We escalate on provider failures we can see; we do not document a separate “scorer down → fallback model, 200 OK” path. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
6. **Anthropic Messages + OpenAI Responses** in addition to chat completions (both vendors). OpenCode-only chat completions is a harness gap for Claude Code / Codex. ([https://docs.pioneer.ai/concepts/inference.md](https://docs.pioneer.ai/concepts/inference.md), [https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md), [https://docs.pioneer.ai/codex.md](https://docs.pioneer.ai/codex.md), [https://docs.fireworks.ai/ecosystem/fireconnect/codex.md](https://docs.fireworks.ai/ecosystem/fireconnect/codex.md))
7. **Prompt-cache forwarding / Cursor alias trick** (`pioneer/auto-claude-opus-4` so Cursor emits `cache_control`). Directly affects coding-agent cost. ([https://docs.pioneer.ai/cursor.md](https://docs.pioneer.ai/cursor.md), [https://docs.pioneer.ai/api-reference/prompt-caching.md](https://docs.pioneer.ai/api-reference/prompt-caching.md))
8. **Effort preset `xhigh`** and published numeric threshold/max_regret table (Pioneer). We have effort strings and max-regret but not this exact 5-row calibrated table. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))
9. **FireRouter-style quality↔savings integer dial** (`x-routing-preference` 1–5) as a single header, plus conversation-level decision cache. Different shape from our `x-routing-effort`. ([https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md))
10. **Binary closed-vs-open BYOK pass-through** (FireRouter). Only relevant if we ever mix aiand open models with a frontier BYOK; today we are aiand-only. ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))
11. **One-command harness installer** (FireConnect) vs our README `opencode.json` snippet. Pioneer is closer to us (copy-paste env + hooks) but covers six harnesses. ([https://docs.fireworks.ai/ecosystem/fireconnect/overview.md](https://docs.fireworks.ai/ecosystem/fireconnect/overview.md), [https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md))
12. **LiteLLM proxy recipe** (FireRouter) for teams that already front models with LiteLLM. ([https://docs.fireworks.ai/ecosystem/firerouter/litellm.md](https://docs.fireworks.ai/ecosystem/firerouter/litellm.md))
13. **Versioned virtual model IDs** (`pioneer/auto_v1.1`, `pioneer/auto_v1.2`, `pioneer/general`) so clients can pin router behavior. ([https://docs.pioneer.ai/openclaw.md](https://docs.pioneer.ai/openclaw.md))
14. **Honest maturity label** (FireRouter “research preview”). Useful for how we talk about learned routing staying dark. ([https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md))
15. **Router-only included credits** (Pioneer `direct_model_requires_credits`) — product/billing idea, not a routing algorithm. ([https://docs.pioneer.ai/api-reference/errors.md](https://docs.pioneer.ai/api-reference/errors.md))

### 4.2 Already close / probably skip unless a judge asks

- Multi-candidate cheapest-above-bar + max-regret — we already do a version of this.
- `allowed_models` — we have `x-allowed-models`.
- OpenCode OpenAI-compatible virtual model — we have this.
- Replay/log of winner + reason + cost — we have this.
- Soft spend cap — we have `BUDGET_LIMIT_USD`; Pioneer has plan credits + overage ceiling; Fireworks has account quotas (platform-wide).

### 4.3 Explicit non-goals suggested by their docs

- Do not confuse FireRouter with replica-weighted **deployment routers**. ([https://docs.fireworks.ai/deployments/routers.md](https://docs.fireworks.ai/deployments/routers.md))
- Do not claim Cursor Composer coverage: Pioneer only does chat/plan; FireConnect Cursor is BYOK chat path and may still hit Cursor backend for some features. ([https://docs.pioneer.ai/cursor.md](https://docs.pioneer.ai/cursor.md), [https://docs.fireworks.ai/ecosystem/fireconnect/cursor.md](https://docs.fireworks.ai/ecosystem/fireconnect/cursor.md))
- Do not invent router quality %; **neither vendor publishes one**.

---

## 5. Performance / latency / routing-quality claims (complete list found)

| Claim | Vendor | Kind | URL |
| --- | --- | --- | --- |
| “low-latency model router trained on coding tasks” | Pioneer | Qualitative | [router](https://docs.pioneer.ai/concepts/router.md) |
| Calibrated success probability 0–1 per model | Pioneer | Mechanism, not a measured accuracy | [router](https://docs.pioneer.ai/concepts/router.md) |
| Example savings UI “~$1.43 … vs claude-opus-4-7” | Pioneer | Example copy, not a benchmark | [claude-code](https://docs.pioneer.ai/claude-code.md), [codex](https://docs.pioneer.ai/codex.md) |
| Savings vs most expensive candidate (absolute + 0–1 fraction) | Pioneer | Per-request accounting definition | [router](https://docs.pioneer.ai/concepts/router.md) |
| F1 bands for NER/classification fine-tunes | Pioneer | Unrelated to coding router | [faq](https://docs.pioneer.ai/faq.md) |
| Trivial prompt → fast open-model response; hard prompt → Opus 4.8 | FireRouter | Qualitative verification | [quickstart](https://docs.fireworks.ai/ecosystem/firerouter/quickstart.md) |
| Preference 1–5 biases borderline redirect vs pass-through | FireRouter | Mechanism | [routing-preferences](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md) |
| Fast serving path aims for **100+ tok/s** | Fireworks serverless | Not FireRouter | [serving-paths](https://docs.fireworks.ai/serverless/serving-paths.md), [fireconnect models](https://docs.fireworks.ai/ecosystem/fireconnect/models.md) |
| Serverless: **no SLA** for latency or availability | Fireworks | Platform | [SLA FAQ](https://docs.fireworks.ai/faq-new/deployment-infrastructure/is-latency-guaranteed-for-serverless-models.md) |
| `fireconnect demo` measured speed/cost (fixed model vs Anthropic) | FireConnect | Not FireRouter | [demo](https://docs.fireworks.ai/ecosystem/fireconnect/demo.md) |

**Not found on either official doc site:** SWE-bench / LiveCodeBench / internal win-rate vs always-frontier; average % cost savings; router TTFT overhead; availability SLA for the router service.

---

## 6. Source index (pages fetched)

### Pioneer

- Index: [https://docs.pioneer.ai/llms.txt](https://docs.pioneer.ai/llms.txt)
- Router: [https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md)
- Inference: [https://docs.pioneer.ai/concepts/inference.md](https://docs.pioneer.ai/concepts/inference.md)
- Models / prices: [https://docs.pioneer.ai/concepts/models.md](https://docs.pioneer.ai/concepts/models.md)
- OpenAI API: [https://docs.pioneer.ai/api-reference/inference/openai-compatible.md](https://docs.pioneer.ai/api-reference/inference/openai-compatible.md)
- Anthropic API: [https://docs.pioneer.ai/api-reference/inference/anthropic-compatible.md](https://docs.pioneer.ai/api-reference/inference/anthropic-compatible.md)
- History: [https://docs.pioneer.ai/api-reference/inference/history.md](https://docs.pioneer.ai/api-reference/inference/history.md)
- Auth: [https://docs.pioneer.ai/authentication.md](https://docs.pioneer.ai/authentication.md), [https://docs.pioneer.ai/api-reference/authentication.md](https://docs.pioneer.ai/api-reference/authentication.md)
- Rate limits: [https://docs.pioneer.ai/api-reference/rate-limits.md](https://docs.pioneer.ai/api-reference/rate-limits.md)
- Errors: [https://docs.pioneer.ai/api-reference/errors.md](https://docs.pioneer.ai/api-reference/errors.md)
- Prompt caching: [https://docs.pioneer.ai/api-reference/prompt-caching.md](https://docs.pioneer.ai/api-reference/prompt-caching.md)
- API overview: [https://docs.pioneer.ai/api-reference/overview.md](https://docs.pioneer.ai/api-reference/overview.md)
- Quickstart: [https://docs.pioneer.ai/quickstart.md](https://docs.pioneer.ai/quickstart.md)
- Introduction: [https://docs.pioneer.ai/introduction.md](https://docs.pioneer.ai/introduction.md)
- Pricing: [https://docs.pioneer.ai/pricing.md](https://docs.pioneer.ai/pricing.md)
- FAQ: [https://docs.pioneer.ai/faq.md](https://docs.pioneer.ai/faq.md)
- Changelog: [https://docs.pioneer.ai/changelog.md](https://docs.pioneer.ai/changelog.md)
- Trust & Safety: [https://docs.pioneer.ai/trust-safety.md](https://docs.pioneer.ai/trust-safety.md)
- Agent skills: [https://docs.pioneer.ai/guides/agent-skills.md](https://docs.pioneer.ai/guides/agent-skills.md)
- Claude Code: [https://docs.pioneer.ai/claude-code.md](https://docs.pioneer.ai/claude-code.md)
- Codex: [https://docs.pioneer.ai/codex.md](https://docs.pioneer.ai/codex.md)
- Cursor: [https://docs.pioneer.ai/cursor.md](https://docs.pioneer.ai/cursor.md)
- OpenCode: [https://docs.pioneer.ai/opencode.md](https://docs.pioneer.ai/opencode.md)
- OpenClaw: [https://docs.pioneer.ai/openclaw.md](https://docs.pioneer.ai/openclaw.md)
- Hermes: [https://docs.pioneer.ai/hermes.md](https://docs.pioneer.ai/hermes.md)
- Opus 4.8: [https://docs.pioneer.ai/api-reference/integrating-with-opus-4-8.md](https://docs.pioneer.ai/api-reference/integrating-with-opus-4-8.md)

### Fireworks / FireRouter / FireConnect

- Index: [https://docs.fireworks.ai/llms.txt](https://docs.fireworks.ai/llms.txt)
- FireRouter overview: [https://docs.fireworks.ai/ecosystem/firerouter/overview.md](https://docs.fireworks.ai/ecosystem/firerouter/overview.md)
- Quickstart: [https://docs.fireworks.ai/ecosystem/firerouter/quickstart.md](https://docs.fireworks.ai/ecosystem/firerouter/quickstart.md)
- Authentication: [https://docs.fireworks.ai/ecosystem/firerouter/authentication.md](https://docs.fireworks.ai/ecosystem/firerouter/authentication.md)
- Routing preferences: [https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences.md)
- Claude Code manual: [https://docs.fireworks.ai/ecosystem/firerouter/claude-code.md](https://docs.fireworks.ai/ecosystem/firerouter/claude-code.md)
- LiteLLM: [https://docs.fireworks.ai/ecosystem/firerouter/litellm.md](https://docs.fireworks.ai/ecosystem/firerouter/litellm.md)
- FireConnect overview: [https://docs.fireworks.ai/ecosystem/fireconnect/overview.md](https://docs.fireworks.ai/ecosystem/fireconnect/overview.md)
- Models: [https://docs.fireworks.ai/ecosystem/fireconnect/models.md](https://docs.fireworks.ai/ecosystem/fireconnect/models.md)
- Claude Code: [https://docs.fireworks.ai/ecosystem/fireconnect/claude-code.md](https://docs.fireworks.ai/ecosystem/fireconnect/claude-code.md)
- OpenCode: [https://docs.fireworks.ai/ecosystem/fireconnect/opencode.md](https://docs.fireworks.ai/ecosystem/fireconnect/opencode.md)
- Codex: [https://docs.fireworks.ai/ecosystem/fireconnect/codex.md](https://docs.fireworks.ai/ecosystem/fireconnect/codex.md)
- Pi: [https://docs.fireworks.ai/ecosystem/fireconnect/pi.md](https://docs.fireworks.ai/ecosystem/fireconnect/pi.md)
- Cursor: [https://docs.fireworks.ai/ecosystem/fireconnect/cursor.md](https://docs.fireworks.ai/ecosystem/fireconnect/cursor.md)
- VS Code: [https://docs.fireworks.ai/ecosystem/fireconnect/vscode.md](https://docs.fireworks.ai/ecosystem/fireconnect/vscode.md)
- Deep Agents: [https://docs.fireworks.ai/ecosystem/fireconnect/deepagents.md](https://docs.fireworks.ai/ecosystem/fireconnect/deepagents.md)
- CLI reference: [https://docs.fireworks.ai/ecosystem/fireconnect/cli-reference.md](https://docs.fireworks.ai/ecosystem/fireconnect/cli-reference.md)
- Demo: [https://docs.fireworks.ai/ecosystem/fireconnect/demo.md](https://docs.fireworks.ai/ecosystem/fireconnect/demo.md)
- Deployment routers (not FireRouter): [https://docs.fireworks.ai/deployments/routers.md](https://docs.fireworks.ai/deployments/routers.md)
- Serverless serving paths: [https://docs.fireworks.ai/serverless/serving-paths.md](https://docs.fireworks.ai/serverless/serving-paths.md)
- Serverless pricing: [https://docs.fireworks.ai/serverless/pricing.md](https://docs.fireworks.ai/serverless/pricing.md)
- SLA FAQ: [https://docs.fireworks.ai/faq-new/deployment-infrastructure/is-latency-guaranteed-for-serverless-models.md](https://docs.fireworks.ai/faq-new/deployment-infrastructure/is-latency-guaranteed-for-serverless-models.md)
- Reliability: [https://docs.fireworks.ai/guides/reliability.md](https://docs.fireworks.ai/guides/reliability.md)
- Glossary: [https://docs.fireworks.ai/getting-started/glossary.md](https://docs.fireworks.ai/getting-started/glossary.md)
- Changelog: [https://docs.fireworks.ai/updates/changelog.md](https://docs.fireworks.ai/updates/changelog.md)
