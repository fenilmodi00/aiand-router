# 01: Multi-turn conversations return 400 on every surface (assistant-role output_text bug)

**What to build:** Any chat request that includes conversation history (an assistant-role message) currently fails on every inbound surface — OpenAI chat completions, Anthropic messages, and Anthropic passthrough all return `400 "The inference backend rejected this request as invalid."` (long prefixes hit a 503 failover variant). Users of every multi-turn client — chat UIs, agents, Claude Code sessions — cannot hold a conversation through the router at all. After this ticket, a two-turn conversation (`user → assistant → user`) completes on all surfaces with a correct final answer, in both streaming and non-streaming modes.

Root cause (isolated on the live beta via wire-shape matrix): the OpenAI-compat chat→Responses translator emits assistant history as easy-input items whose content parts carry type `output_text`. The upstream accepts `output_text` only inside fully-typed `{"type":"message"}` items; in easy-input position it requires `input_text` parts. Fix the part-type emission for assistant easy-input items (or emit fully-typed message items). Two companion updates keep the fix honest: a unit test currently asserts the broken `output_text` shape and must be flipped to the correct expectation, and the smoke suite has zero cassettes containing assistant-role traffic — add a multi-turn scenario so this class is caught before prod next time.

QA evidence: reproducible 4/4 with short and long payloads, on `auto` and explicit model ids, all three surfaces; direct upstream probes show string-content → 200, easy-input + `input_text` → 200, easy-input + `output_text` (router's shape) → 400, typed message + `output_text` → 200. This is the launch blocker: it also unblocks conversation-append cache testing and every agentic client.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Two-turn conversation returns 200 with a correct answer on `/v1/chat/completions`
- [ ] Two-turn conversation returns 200 on `/v1/messages` (Anthropic surface)
- [ ] Streaming variant of both works end to end (`[DONE]` / message_stop)
- [ ] Unit test asserting assistant easy-input part type updated to the accepted shape
- [ ] New smoke scenario/cassette with assistant-role history exercising real upstream
- [ ] Verified on the live beta endpoint with the probe matrix above (all shapes that failed now pass)

## Progress (2026-09-02) — FIXED
writeResponsesContentMessage now emits input_text for every easy-input text part regardless of
role (single choke point covering both the Anthropic→Responses and chat→Responses paths);
assistant non-text parts still dropped. Unit tests flipped/added (responses_from_openai_chat_test.go,
responses_outbound_test.go); new smoke scenario smoke/multiturn_test.go (non-stream + stream)
with cassette generator entries (gencassettes) and a committed cassette.
Verified LIVE on a local ORT router against the real aiand upstream: two-turn conversation
returns 200 with the correct answer on /v1/chat/completions AND /v1/messages, streaming variant
emits banana + [DONE]. All four wire-shape probes from the QA matrix now accepted upstream.
