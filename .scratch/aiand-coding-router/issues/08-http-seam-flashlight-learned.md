# 08 — Flashlight and learned tests stay on the HTTP seam

**What to build:** Flashlight phase walk and “learned stays dark” are proven the way OpenCode would talk to the gateway: chat completions plus headers and JSONL. Tests do not import private flashlight runners or call selection directly.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Discover → plan → edit → test outcome → debug → summarize is observable via HTTP + JSONL/`X-Router-*` (stronger model after test fail still holds)
- [x] After comparison says rules win, `POST /v1/chat/completions` with summarize still uses rules (not learned) and the fake upstream is called with that model
- [x] Comparison CLI may still run as a process; gateway tests do not call `select_model` / `learned_select` / private flashlight helpers
- [x] Fake upstream only; no live aiand in CI
