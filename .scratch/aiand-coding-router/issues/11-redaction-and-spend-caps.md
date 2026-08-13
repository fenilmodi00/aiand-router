# 11 — Configurable redaction and max token/timeout caps

**What to build:** A bad client cannot unbounded-spend with a huge `max_tokens` or an unbounded timeout. Log redaction is configurable. Replay and `/health` still never show provider or router keys.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Request `max_tokens` (or completion max) above the configured cap is rejected before the upstream is called
- [x] Upstream timeout is bounded by configuration; timeout still escalates once when escalation is allowed
- [x] Redaction field list is configurable; replay events omit keys/tokens/secrets
- [x] `/health` still reports spend vs budget and whether the aiand key is set, never the key itself
- [x] Wrong `ROUTER_API_KEY` is still 401 with no upstream call
