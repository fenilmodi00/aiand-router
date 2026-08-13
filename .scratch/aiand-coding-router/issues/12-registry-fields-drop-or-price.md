# 12 — Registry fields that drop or price a model

**What to build:** Model metadata that already belongs in the registry actually affects routing and cost: max output vs request size, streaming support, and cached input price when present. All nine briefed ids still list; Motif-3 stays disabled until the org catalog has it.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Request `max_tokens` above a model’s max output drops that model from auto-select (fallback still applies if the set is empty)
- [x] `stream: true` does not select a model with streaming unsupported
- [x] When cached input price is present, cost accounting / unit-cost blend can use it; when absent, list prices still work
- [x] `/v1/models` still returns `router/auto` plus all nine registry ids
- [x] Motif-3 remains `enabled: false` unless explicitly turned on
