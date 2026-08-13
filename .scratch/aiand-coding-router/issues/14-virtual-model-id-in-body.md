# 14 — Completion body keeps the virtual model id

**What to build:** Non-stream chat completions leave `model` as what the client sent (`router/auto`, `aiand-router`, `auto`, or a pin). The routed provider id is only on `X-Router-Model` and in JSONL. Stream passthrough stays unchanged (no rewrite after the client has started reading).

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] `model: router/auto` non-stream response body still has `model: router/auto` (or the requested virtual id)
- [x] `X-Router-Model` and JSONL `selected` still carry the real aiand id (e.g. Qwen on summarize)
- [x] A pinned registry id still round-trips in the body and is forwarded upstream unchanged
- [x] Streamed responses are still SSE passthrough with no second upstream call and no mid-stream escalation
