# Motif 3 vs GLM 5.2 (coding)

Researched 2026-08-13. Primary sources + this org’s `GET /v1/models` + two live pings. Not an aiand-hosted quality measurement.

## Org check (this key, 2026-08-13)

`GET https://api.aiand.com/v1/models` lists `motif-technologies/motif-3` (also K3). Org currency is JPY: in 80 / cached 30 / out 320 per 1M ≈ USD catalog $0.50 / $0.20 / $2.00. Context 262144. Capabilities advertised: `chat`, `reasoning` only — **no `tool_calling` flag** — but a live tools ping returned `finish_reason=tool_calls` with valid `ping_tool({"x":1})`. Chat ping 200. Registry: `enabled: true`, `aa_index: 47`, `supports_tools: true`.

Public docs catalog still omits Motif-3; org list is the source of truth.

## What Motif 3 is

- Lab: Motif Technologies (Korea). Official weights: [huggingface.co/Motif-Technologies/Motif-3](https://huggingface.co/Motif-Technologies/Motif-3). Tech report: [arXiv:2608.09119](https://arxiv.org/html/2608.09119). AA page: [artificialanalysis.ai/models/motif-3](https://artificialanalysis.ai/models/motif-3).
- Decoder-only MoE: **314B total / 13.2B active**, 384 routed experts, 8 active per token. MIT license. Text-only. Reasoning model. Context **262K**.
- Architecture: Grouped Differential Latent Attention (GDLA) + modified mHC + Expert-Specific PolyNorm + MTP. Pretrain ~12.5T tokens. Post-train: general SFT → six RL specialist teachers + one SWE SFT teacher → Multi-teacher On-Policy Distillation (MOPD).
- Released ~12 Aug 2026 (AA). Company press same day: AAII 47, 9th globally / 1st Korea / 4th open-weight ([Digital Today](https://www.digitaltoday.co.kr/en/view/92837/motif-motif-3-scores-47-on-aaii-ranks-9th-globally-and-1st-in-south-korea)).

## Independent composite (Artificial Analysis Intelligence Index v4.1.1)

Same 9 evals for both: GDPval-AA v2, τ³-Banking, Terminal-Bench v2.1, SciCode, HLE, GPQA Diamond, CritPt, AA-Omniscience, AA-LCR.

| Model | AA index | Params (active) | Context | Source |
| --- | ---: | --- | ---: | --- |
| Kimi K3 (max) | 60 | 2.8T (104B) | 1M | [AA open-source](https://artificialanalysis.ai/models/open-source) |
| GLM-5.2 (max) | **53** | 753B (40B) | 1M | [AA glm-5-2](https://artificialanalysis.ai/models/glm-5-2) |
| DeepSeek V4 Flash (max) | 52 | 284B (13B) | 1M | same |
| **Motif 3** | **47** | 314B (13.2B) | 262K | [AA motif-3](https://artificialanalysis.ai/models/motif-3) |
| MiniMax-M3 | 45 | 428B (23B) | 1M | same |

Head-to-head AA: GLM-5.2 is **+6** Intelligence Index vs Motif 3, **~4× context**, **~3× active params**. Motif is much smaller at inference. ([AA comparison](https://artificialanalysis.ai/models/comparisons/motif-3-vs-glm-5-2))

AA also flags Motif as **very verbose** on the index run (260M output tokens vs median ~100M; GLM ~140M). That hurts cost/latency even if list price is lower.

## Coding / agent numbers (vendor tables — not the same harness)

**Important:** Motif’s tech report table compares against **GLM-5.1**, not 5.2. “Just behind GLM 5.2” is easy to misread from SWE-bench Verified vs 5.1.

Motif 3 (temp 1.0, top-p 0.95, max seq 262K) vs GLM-5.1, from [arXiv Table 6](https://arxiv.org/html/2608.09119):

| Benchmark | Motif 3 | GLM-5.1 | MiniMax-3 | DS-v4-Pro | Qwen-3.7 Max |
| --- | ---: | ---: | ---: | ---: | ---: |
| SWE-bench Verified | **76.2** | **76.4** | 75.0 | 77.4 | 80.4 |
| Terminal-Bench 2.1 | **74.9** | 61.8 | 65.2 | 64.0 | 75.0 |
| SciCode | 40.6 | 43.8 | 45.4 | 50.0 | 53.5 |
| τ³-Banking | **35.3** | 13.6 | 15.3 | 30.1 | 12.0 |
| ITBench-AA (public*) | **51.5** | 40.3 | — | 38.3 | 42.5 |
| GDPval-AA v2 | 38.7 | 37.8 | 44.4 | 40.2 | 39.0 |

So vs **5.1**: Motif is 0.2 behind on SWE-Verified, **well ahead** on Terminal-Bench and agentic banking/IT. Weakest coding slice is SciCode.

GLM-5.2 vendor card ([HF zai-org/GLM-5.2](https://huggingface.co/zai-org/GLM-5.2), [z.ai blog](https://z.ai/blog/glm-5.2)) — different suite, different harness:

| Benchmark | GLM-5.2 | GLM-5.1 (same card) | Notes |
| --- | ---: | ---: | --- |
| SWE-bench **Pro** | 62.1 | 58.4 | Harder than Verified; Motif does not publish Pro |
| Terminal-Bench 2.1 (Terminus-2) | **81.0** | 63.5 | Motif reports 74.9 on TB 2.1 (harness not identical) |
| TB 2.1 best harness | 82.7 | 69 | Claude Code |
| DeepSWE | 46.2 | 18 | Motif does not publish |
| FrontierSWE | 74.4 | 30.5 | Motif does not publish |
| MCP-Atlas public | 76.8 | 71.8 | |

Apples-to-apples vs **GLM-5.2** on coding: Motif is **behind on Terminal-Bench** (~75 vs ~81 vendor) and does not report SWE-Pro / DeepSWE / FrontierSWE. The “just behind” claim is true for **SWE-Verified vs GLM-5.1** (76.2 vs 76.4), not for GLM-5.2’s coding stack.

Beta vs final: Motif-3-Beta was AAII **44** / Coding Index **62** ([HF Motif-3-Beta](https://huggingface.co/Motif-Technologies/Motif-3-Beta), [temperature2 Motif 3 Beta](https://temperature2.com/models/motif-0714/)). Official Motif 3 is AAII **47**. Do not mix beta rows with final.

## Price / router fit (if it ever lands on the org catalog)

YAML list prices (not confirmed live):

| | Input | Cached | Output | Context | AA (now known) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Flash | 0.15 | 0.08 | 0.25 | 1M | 52 |
| Motif 3 | 0.50 | 0.20 | 2.00 | 262K | **47** |
| Kimi K2.7 Code | 0.75 | 0.20 | 3.50 | 262K | 42 |
| GLM-5.2 | 1.00 | 0.30 | 4.00 | 1M | 53 |

Blended unit cost here (`0.4·in + 0.6·out`): Flash **0.21**, Motif **1.40**, GLM **2.80**. Motif is ~half GLM, ~7× Flash.

If enabled + `aa_index: 47`:

- Clears summarize (24), discover (35), tool (38), edit (40).
- **Fails** plan / debug / security (50) and debug-after-fail (53).
- Default medium/high still picks **Flash** (higher AA, much cheaper). Motif would not displace GLM on plan/debug even if on.
- Useful later only with a **coding-specific prior** (spec already says edit prefers Flash over Kimi Code for the same reason) or if Flash is allow-listed out.

## Public takes (thin — final weights are ~1 day old)

- Company / press: AAII 47, 9th globally, 1st Korea, 4th open-weight; MIT weights + training code ([Digital Today 2026-08-13](https://www.digitaltoday.co.kr/en/view/92837/motif-motif-3-scores-47-on-aaii-ranks-9th-globally-and-1st-in-south-korea)).
- AA: 47 intelligence; **very verbose** (260M index tokens vs ~100M median). Same warning on Beta.
- TechTimes (Beta, 2026-08-04): ~30-person Moreh subsidiary, Dokpamo compute (768 B200s), in-house GDLA+PolyNorm; Beta was research-license; originality claim will be probed; independent validation was mostly AA, not MMLU/HumanEval dumps ([TechTimes](https://www.techtimes.com/articles/322918/20260804/koreas-sovereign-ai-race-isnt-just-giants-motif-reaches-global-top-tier.htm)).
- Practitioners: almost none yet. HF discussions are llama.cpp / install questions, not coding-agent reports. Beta needed `--tool-call-parser motif` / `--reasoning-parser motif` on vLLM; HF `.generate` was broken then fixed. No Reddit/HN coding writeups found.
- Takeaway for this router: price is the win ($0.50/$2 vs GLM $1/$4, ~13B active). Coding benches look close to GLM-5.1, behind GLM-5.2 TB. Default medium still picks **Flash** (AA 52 + cheaper). Motif clears edit/tool (bar 40), not plan/debug (50).

## Do not

- Do not quote Motif SWE-Verified 76.2 as “tied with GLM-5.2”.
- Do not invent an aiand-hosted Motif success rate; AA 47 is a public prior (`measured_on: not_aiand`).
