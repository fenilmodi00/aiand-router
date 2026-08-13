# 10 — Structured JSON is constrained and escalated

**What to build:** When the client asks for JSON / structured output, the gateway only selects models that support it. Malformed JSON (not only bad tool-call JSON) escalates once to a stronger model. Streaming still does not escalate mid-stream. Headers and JSONL record the hop.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] A chat request with JSON / `response_format` does not forward a model with `supports_json: false`
- [x] Invalid JSON content (fake upstream) causes exactly one escalation; `X-Router-Escalated-From` is set
- [x] Invalid tool-call JSON still escalates once (existing behaviour preserved)
- [x] Streamed requests still do not escalate mid-stream
- [x] JSONL records whether structured/tool JSON was valid
