# Bootstrap coding-agent datasets

Type: research
Status: resolved
Blocked by: none
Part of: [Production trained coding router](../map.md)

## Question

What **public** coding-agent, SWE, or tool-call datasets could **bootstrap** per-step or per-request outcomes?

For each candidate: official card/paper, license, size, whether it has **per-model** outcomes vs a single trace, whether steps look like coding-agent phases, and whether it can support our success label (no-escalate / tool validity) or only session-level gold.

Primary sources only (dataset cards, papers, official repos). This repo’s 3×5 cache is too small to be the sole corpus; list what could sit beside it.

Findings land on branch `research/bootstrap-datasets` as `.scratch/trained-router/research/bootstrap-datasets.md`.

## Answer

No public dump has named AIand phases or per-catalog no-escalate labels. Bootstrap = parse traces + relabel on aiand, then flywheel. 3×5 stays smoke.

Best beside the cache: **SWE-smith trajectories** (MIT, tool traces + `resolved`); **SWE-Gym / R2E-Gym** OpenHands SFT (Apache-2.0, hundreds–thousands of traces); **SWE-smith / SWE-rebench / Multi-SWE-RL tasks** for relabeling; **BFCL** for tool-JSON. **SWE-bench Verified/Lite** = eval gold only. **Terminal-Bench** = eval gate with **canary: do not train**. RouterBench is per-model but not agentic; RouteLLM/RouterArena are the wrong domain; HumanEval/MBPP/LiveCodeBench/RepoBench are too weak / next-line.

Detail: [`.scratch/trained-router/research/bootstrap-datasets.md`](../research/bootstrap-datasets.md) on `research/bootstrap-datasets` @ `27393a5`. Dump freeze is [Bootstrap dump set](16-bootstrap-dump-set.md).
