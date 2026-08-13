# 04 — Measured comparison

**What to build:** The same five seeded tasks are run three ways — premium-only, Kimi-only, and adaptive `router/auto` — using only the measured trio (Qwen, Kimi K2.7 Code, DeepSeek V4 Pro). Results come from the request cache. The slide can say “on this slice, adaptive cost $Y vs $Z” and must not invent a percentage.

**Blocked by:** 02 — Request cache; 03 — Flashlight run and replay

**Status:** resolved

- [x] A task schema holds at least five seeded tasks and can grow later without a rewrite
- [x] Premium-only pins the strong measured model; Kimi-only pins Kimi K2.7 Code; adaptive uses `router/auto`
- [x] All three baselines run on the same five tasks; duplicate calls hit the cache
- [x] Reported numbers (resolution, cost, latency, models used) are read from cache/log, not typed by hand
- [x] The other five original baseline modes may exist as stubs; they are not executed
- [x] README/replay distinguishes measured numbers from AA priors
