# FireRouter conversation stickiness — status (2026-08-20)

**Goal:** FireRouter-style “stick to routed model within a conversation.”  
**Verdict:** **Gateway stickiness present** behind existing session headers. **Not** FireRouter product parity. Do **not** mark Pioneer/Fireworks goal complete.

## What exists

| Piece | Location |
| --- | --- |
| In-process sticky map | `src/aiand_router/app.py` (`route_sticky`, `apply_conversation_sticky`) |
| Conversation id | `x-session-id` / `session_id` / `prompt-cache-key` / `prompt_cache_key` |
| Observability | `X-Router-Conversation-Sticky: 1` + reason code `conversation_sticky` |
| Chat + Anthropic Messages | Both call `apply_conversation_sticky` after route (shadow path intact) |
| Tests | `tests/test_conversation_sticky.py` (**8 passed**) |

## Behavior vs FireRouter docs

| FireRouter claim | AIand today |
| --- | --- |
| Cache routing decision within a conversation | **Yes** — second+ turn with same `(session, effort, allowlist, hop_path)` reuses prior model id |
| Preference changes may take a few turns | **No** — effort / allowlist / hop-path change **immediately** invalidates sticky key (stricter, intentional) |
| Scores each request | **Still scores every turn**, then overrides model on sticky hit (shadow keeps `trained_would`) |
| Managed durable cache | **Process-local only** — lost on gateway restart; unbounded dict (no TTL/LRU) |
| Binary cascade + stickiness as product | Cascade remains **default-off** / `TRAINED_PATH=off` only; stickiness is orthogonal |

## Minimal unpaid change this turn

- Clear `savings_usd` when sticky **overrides** a different fresh pick (avoid lying in `X-Router-Savings-Usd` before post-call recompute).
- Expanded tests: header aliases, Anthropic `/v1/messages`, allowlist + hop-path invalidation, no-session control.

## Live probe (shadow gateway restart)

After restart with `TRAINED_PATH=shadow` (process override; `.env` may still say `trained`):

- Turn 1 `x-session-id=sticky-probe` → `path=shadow`, no sticky header.
- Turn 2 same session → `X-Router-Conversation-Sticky: 1`, same `x-router-model`, `conversation_sticky` in reason codes.

## Remaining FireRouter stickiness gaps (honest)

1. **Not a quality/cost match** — stickiness does not make cascade or scorer FireRouter-class.
2. **No early short-circuit** — full rules/trained score still runs every turn (latency ≠ “cached decision”).
3. **No durable / multi-replica store** — sticky is single-process RAM.
4. **No `x-routing-preference` 1–5 dial** — we use `x-routing-effort` + Pioneer-shaped knobs.
5. **No delayed preference migration** — FireRouter may take a few turns; we invalidate immediately.
6. **Pinned models never enter the sticky map** — correct for pin, different from Firerouter slug primary stickiness.
7. **Shadow vs serve** — sticky forces the **served** model; shadow observability still re-scores.

## Serve recommendation

Keep **`data/scorer-hard-logistic.json`** + **`TRAINED_PATH=shadow`**. Do not flip trained. Stickiness is gateway UX, not a promotion signal.
