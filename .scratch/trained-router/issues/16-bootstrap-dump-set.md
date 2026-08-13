# Bootstrap dump set

Type: grilling
Status: resolved
Blocked by: none
Part of: [Production trained coding router](../map.md)

## Question

Which **public dumps** does the spec ingest for bootstrap vs hold out as **eval-only**?

Research rec to grill against: train/relabel on SWE-smith trajectories (MIT), SWE-Gym / R2E-Gym OpenHands SFT (Apache-2.0), SWE-smith / SWE-rebench / Multi-SWE-RL **tasks**, BFCL for tool-JSON; eval-only SWE-bench Verified/Lite; **do not train** on Terminal-Bench (canary). RouterBench / RouteLLM / RouterArena are the wrong domain for agent traces. No dump has named AIand phases or per-catalog no-escalate labels — bootstrap is parse + relabel, then flywheel.

Detail: [Bootstrap coding-agent datasets](04-bootstrap-coding-agent-datasets.md).

HITL — do not resolve without the human.

## Answer

**Required bootstrap dumps** (parse + relabel; no dump has AIand phases or per-catalog success gold):

- **SWE-smith trajectories**, `tool` split only (MIT). Not the 5k SFT cut, not `xml`/`ticks` (near-duplicate serializations).
- **SWE-smith tasks** (MIT) as the relabel pool.
- **BFCL** (Apache-2.0) for tool-JSON only — never a promotion-gate corpus.

**Allowed, not required:** SWE-Gym OpenHands SFT+verifier and R2E-Gym SFT (Apache **repo**; HF cards undeclared — diligence note in the spec). Skip them if legal review blocks; smith alone still ships.

**Named optional:** SWE-rebench **tasks** (CC-BY-4.0), filter per-instance `license_name`. Scale knob, not a v1 hard-require.

**Eval-only** (never train, calibrator, or threshold/max_regret fit): the whole **SWE-bench family** (full / Lite / Verified / multilingual / multimodal) + **Terminal-Bench** (benchmark do-not-train canary, not a traffic canary). Verified/Lite remain the promotion-gate corpora. Optional diversity eval (e.g. TheAgentCompany) is eval-only if used at all.

**Out:** RouterBench / RouteLLM / RouterArena; HumanEval / MBPP / LiveCodeBench / RepoBench; NVIDIA SWE-Hero/Zero OpenHands dumps; OpenHands feedback; ToolBench. No non-agent router-head prior.

**Hygiene:** drop bootstrap rows whose `instance_id` / problem hash matches the SWE-bench family. This repo’s **3×5** is smoke, disjoint from bootstrap dumps and from the promotion split. Flywheel is not a public dump. **Multi-SWE-RL** is not v1-required (Python-first); revisit if production traffic is multilingual ([Multi-SWE-RL trigger](21-multi-swe-rl-trigger.md)).

Detail: [Bootstrap coding-agent datasets](04-bootstrap-coding-agent-datasets.md) · [note](../research/bootstrap-datasets.md). Sparse-train n / stratum mix → [Sparse-train n and stratum fractions](18-sparse-train-n-and-stratum-fractions.md).

## Comments

- [Promotion gate numeric bars](08-promotion-gate-numeric-bars.md) is resolved. Gate corpora: SWE-bench Verified (500, primary) / Lite (300, proxy until Verified); Terminal-Bench canary only, do not train. This ticket still freezes **train ingest** vs hold-out, not those gate numbers.
- Grill round 1 (all recs): **Q1 D** rec minus Multi-SWE — required SWE-smith traj+tasks+BFCL; gym/r2e allowed with Apache-repo diligence; rebench optional + `license_name` filter; Multi-SWE-RL deferred. **Q2 B** whole SWE-bench family hold-out (full/Lite/Verified/multilingual/multimodal) + TB canary; optional diversity eval never trains. **Q3 A** RouterBench / RouteLLM / RouterArena / HumanEval / MBPP / LCB / RepoBench / NVIDIA OH dumps / OpenHands feedback / ToolBench all out.
- Grill round 2 (all recs): **Q4 C** smith `tool` split only. **Q5 A** gym/r2e optional allowed. **Q6 A** rebench named optional + `license_name`. **Q7 A** SWE-bench family collision filter; 3×5 smoke disjoint; BFCL never a gate corpus.
