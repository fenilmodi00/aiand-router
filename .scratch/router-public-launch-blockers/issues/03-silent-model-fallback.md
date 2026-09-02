# 03: Unknown model names silently reroute to the cheapest model

**What to build:** Today `model: "gpt-4o"`, `model: ""`, and a missing model field are all silently accepted and served by deepseek-v4-flash as if the user asked for it. A customer integrating against the public API who typos a model name gets answers from a different, cheapest-tier model with zero signal — a trust and billing-fairness problem that looks like bait-and-switch from the outside. After this ticket, unknown model names get an explicit error (404 or 400 naming the model), while valid catalog ids, the documented alias surface, and `auto` keep working.

Decision needed from the team (pick one, implement it, document it in the public API docs): reject unknown ids, or alias a documented allowlist and reject everything else. What must die is the silent fallback. Note "gpt-4o" is a valid OpenAI-family name — check how force-model handling treats wire-family names before choosing the rejection status so Anthropic/OpenAI clients get their native error envelope.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] `model: "gpt-4o"` → explicit error, not a silent completion from another model
- [ ] Empty and missing model handled per the chosen policy, consistently across surfaces
- [ ] Valid catalog ids and `auto` unaffected (spot-check via breaker prompts)
- [ ] Chosen policy documented in the public API docs

## Progress (2026-09-02) — FIXED (policy: reject unknown gpt-*/o*, keep claude-*/gemini-*)
- auto/empty/missing → cluster routing (documented).
- Catalog ids → force + pin (unchanged).
- claude-*/gemini-* → wire-compat passthrough routing (intentional aliasing; installer writes
  these ids into Claude Code's models.json — documented in docs/CONFIGURATION.md).
- Unknown gpt-*/o*/bare names (e.g. gpt-4o) → 400 ForcedModelUnknownError naming the model,
  via the shared rawForceModelFromHeaders path so /v1/route preview and dispatch agree.
- Hazard removed: the old o-prefix check (strings.HasPrefix "o") silently rerouted ANY o-word;
  now all unknown OpenAI-family names 400.
- Verified live: gpt-4o → 400; claude-sonnet-4-6 → 200; zai-org/glm-5.3 → pins.
