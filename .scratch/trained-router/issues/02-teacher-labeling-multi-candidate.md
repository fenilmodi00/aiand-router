# Teacher labeling for multi-candidate success

Type: research
Status: resolved
Blocked by: none
Part of: [Production trained coding router](../map.md)

## Question

How do primary-source LLM routers obtain **multi-candidate success labels**?

Specifically: can a **teacher** chat model label **complexity bins** and **per-model success** without running every candidate? What protocols are documented (RouteLLM, HybridLLM, FrugalGPT, LLMRouter, RouterArena, …)? What leakage or bias to avoid?

Output a labeling recipe an **aiand-deployed** teacher (Flash / Qwen / Pro class) could run **offline**, aligned with our success label: per-request no-escalate (+ valid tools if tools present); session/flashlight outcomes reserved for the promotion gate.

Findings land on branch `research/teacher-labeling` as `.scratch/trained-router/research/teacher-labeling.md`.

## Answer

**Bins: query-only teacher, yes. Per-model success gold: no — run the candidates.** Teacher silver P(success) is a distill prior, not calibration gold. Session/flashlight outcome is promotion-gate only. 3×5 cache is smoke, not a corpus.

Recipe: offline aiand chat (`strict json_schema`) → `complexity_bin` + silver `p_success[eligible]`; stratified real catalog runs → `success_gold` via the gateway escalate/tool-valid predicate; flywheel logs observed hops only (missing ≠ 0). Single teacher or cheap-then-Pro escalate; prefer a teacher outside the measured trio. Do not feed completions into the bin/silver call.

Detail: [`.scratch/trained-router/research/teacher-labeling.md`](../research/teacher-labeling.md) on `research/teacher-labeling` @ `0d9307d`.
