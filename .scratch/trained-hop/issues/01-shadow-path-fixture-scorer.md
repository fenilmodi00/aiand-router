# 01 — Shadow path with fixture Scorer

**What to build:** A coding-agent client keeps talking to `router/auto` exactly as today. Default `TRAINED_PATH=shadow` still **serves the rules pick** (streaming, tools, missing phase, pinned ids unchanged). The same JSONL row and response headers also record what the trained router **would** have picked from a fixture Scorer. `TRAINED_PATH=off` is today’s rules headers. Invalid path value is shadow. The learned stub cannot silently replace this path.

Parent: [trained-hop spec](../spec.md). Decision contract is the spec’s `Decision` shape (from the observability prototype).

**Blocked by:** None — can start immediately.

**Status:** resolved

- [ ] Default (unset) `TRAINED_PATH` is `shadow`. Invalid value is `shadow`.
- [ ] `TRAINED_PATH=shadow`: HTTP 200; served `model` / `X-Router-Model` is the **rules** pick; fake provider is called with that rules id, not the trained would-be id.
- [ ] Same hop: JSONL `path=shadow`, `selected` = rules id, `trained_selected` present; header `X-Router-Path: shadow` and `X-Router-Trained-Would` = trained would-be id.
- [ ] `TRAINED_PATH=off`: identical to today’s rules headers (`X-Router-Reason` still present); trained fields not required.
- [ ] A pinned real model id still bypasses auto-select.
- [ ] Missing `x-agent-phase`, streaming, and tools still work (no protocol break).
- [ ] `learned_wins.json` on does **not** switch shadow to the highest-AA learned stub.
- [ ] Fixture Scorer artifact is injectable on the app; missing this ticket’s fixture is not yet `scorer_down` (that is 02) — 01 may assume a fixture is present.
- [ ] JSONL redaction still strips secrets.
- [ ] Rules path may leave new Decision fields empty and keep prose `X-Router-Reason`.
