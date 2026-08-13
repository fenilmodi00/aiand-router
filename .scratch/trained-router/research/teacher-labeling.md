# Teacher labeling for multi-candidate success

Primary-source notes for how published LLM routers obtain **complexity bins** and **per-candidate success** labels, and a recipe an **aiand-deployed teacher** can run **offline**.

**Fetched:** 2026-08-13. **Not used:** blogs, tweets, third-party writeups.

**Local product context (not a competitor claim):** trained-router destination is complexity class → calibrated P(success) per eligible candidate → cheapest that clears threshold + max_regret. Teacher is an aiand chat model used offline only; it is not the live hop. Per-request success = no escalate (+ valid tools if tools present). Promotion-gate gold = harness/flashlight task outcome when present. See `CONTEXT.md`, `.scratch/trained-router/map.md`.

---

## How to read this note

Every factual claim about an external system is followed by the owning source. Local gateway/success-label facts cite this repo. Absence of documentation is stated as absence.

**Bins in the recipe below are examples the standing preference already uses** (`trivial / standard / hard / frontier`). Ticket 07 freezes names/boundaries later; this note only says which bin *kinds* a teacher can label.

---

## Direct answer

| Question | Answer from primary sources |
| --- | --- |
| Can a teacher chat model label **complexity bins** without running candidates? | **Yes.** RouterArena annotates Bloom cognitive level from the query alone with DeepSeek-V3.1 LLM-as-judge. ([https://arxiv.org/html/2510.00202v2](https://arxiv.org/html/2510.00202v2); ICLR version: [https://proceedings.iclr.cc/paper_files/paper/2026/file/4987bb24bc53c198785922d1bd9e18cf-Paper-Conference.pdf](https://proceedings.iclr.cc/paper_files/paper/2026/file/4987bb24bc53c198785922d1bd9e18cf-Paper-Conference.pdf)) |
| Can a teacher label **per-model success** without running every candidate? | **Not as gold.** Dense multi-candidate success matrices are built by **running the pool** (LLMRouter, RouterBench, HybridLLM, Zooter). A teacher/judge/RM can score **after responses exist**, or emit **silver** P(success) from the query alone (that *is* the routing problem). Pairwise preference (Arena / GPT-4 judge) needs **two** responses, not N. |
| Is teacher-from-query P(success) documented as a substitute for running models? | Documented only as a **student/router**, not as offline gold. RouteLLM’s causal-LLM classifier predicts strong-vs-weak win from the query; Zooter **distills** RM scores into a query-only router after first running all candidates. ([https://arxiv.org/html/2406.18665v4](https://arxiv.org/html/2406.18665v4), [https://aclanthology.org/2024.naacl-long.109/](https://aclanthology.org/2024.naacl-long.109/)) |

Pioneer’s product docs describe a coding router that classifies complexity and emits calibrated P(success) per candidate. They **do not** document how those labels were collected. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

---

## Local success label (this repo)

**Per-request training / calibration label** (gateway-observable):

- Escalate once (unless `effort=low`) on empty message, timeout/408, 429, 5xx, other 4xx, invalid tool-call JSON, or invalid JSON content when structured output was requested. Streaming does not escalate mid-stream. (`src/aiand_router/app.py` `_should_escalate`; `.scratch/aiand-coding-router/spec.md`)
- `tool_calls_valid`: every `tool_calls[].function.arguments` must parse as JSON. No tool calls → valid. (`src/aiand_router/router.py`)
- Success for P(success) training: **no escalate** and **tool_valid if tools were present**. Session/test outcome is **not** this label. (`CONTEXT.md`, map Notes)

**Promotion-gate gold** (session-level, when present):

- Flashlight POSTs `{tests_passed, patch_applied}` to `/v1/router/outcome` after pytest. OpenCode is the real harness; flashlight is the demo client. (`src/aiand_router/flashlight.py`, `ARCHITECTURE.md`, map Notes)
- Do not train per-request P(success) on session gold. Do not use a teacher as promotion-gate gold.

**3×5 cache is too small alone:** spec is 3 measured models × ~5 seeded tasks for demo baselines, not a training corpus. (`.scratch/aiand-coding-router/spec.md` items 52, 58, 109)

**Teacher hop:** offline `POST https://api.aiand.com/v1/chat/completions` (OpenAI-compatible; structured outputs via `response_format` json_object or strict json_schema). ([https://docs.aiand.com/api/chat-completions/](https://docs.aiand.com/api/chat-completions/), [https://docs.aiand.com/capabilities/structured-outputs/](https://docs.aiand.com/capabilities/structured-outputs/)) Teacher is **not** the live routing hop. (`CONTEXT.md`)

Catalog classes named in the ticket (org source of truth remains `GET /v1/models`): Flash `deepseek-ai/deepseek-v4-flash`; Qwen `qwen/qwen3.6-27b`; Pro `deepseek-ai/deepseek-v4-pro`. ([https://docs.aiand.com/models/catalog/](https://docs.aiand.com/models/catalog/), `config/models.yaml`)

---

## Protocol catalog

| System | What is labeled | How labels are obtained | Run every candidate? | Teacher/judge role |
| --- | --- | --- | --- | --- |
| **RouteLLM** | Binary P(strong beats weak) | (1) Chatbot Arena human pairwise votes, models tiered, **responses dropped** from student features; (2) MMLU gold: run Ms+Mw vs answer key; (3) GPT-4 judge on ~120k open-ended pairs (~$700), reuse Nectar GPT-4 responses + Mixtral gens | No for Arena; **yes for the pair** on gold/judge | GPT-4 as **pairwise judge after both answers**, plus optional causal-LLM **student** |
| **HybridLLM** | Easy vs hard = small-model quality gap vs large | MixInstruct queries; **10 responses from all LLMs** on 10k train examples; BARTScore quality gap; DeBERTa router | **Yes** (train matrix + 10 samples) | No chat teacher; BARTScore instead of GPT-ranking (cost) |
| **FrugalGPT** | Post-answer correctness score + cascade stop | Run APIs on 50% train split; DistilBERT scorer on **query+response → correct vs gold**; cascade at inference | Train: **yes** (for scorer); inference: cheap-first until score clears | DistilBERT scorer, not a chat teacher; stop judger is a threshold |
| **LLMRouter / xRouteBench** | Dense query×model perf + cost | Automated pipeline: dispatch **every** candidate (18 in the paper), task metric + token cost | **Yes** (supervision construction) | Optional LLM-judge metric column |
| **RouterArena** | Bloom cognitive level + empirical difficulty + per-model correctness | LLM-as-judge (DeepSeek-V3.1) for Bloom **from query**; empirical difficulty = fraction of **42 models** correct; eval runs selected model (prefix cache) | Bloom: **no**; empirical difficulty / oracle metrics: **yes** | Teacher for **bins/coverage only** |
| **RouterBench** | Precomputed q(o), c(o) per model | 405,467 inference outcomes, 11 models × 8 datasets × 64 tasks | **Yes** (offline matrix) | None for labeling; oracle = cheapest correct |
| **Zooter** | Per-model RM reward → distilled router | Infer **all** candidates; QwenRM scalar rewards; tag-based denoise; distill to DeBERTa router | **Yes** at label time; **no** at inference | RM teacher on **responses**, not query-only gold |
| **AutoMix** | Accept vs escalate after a small-model answer | Few-shot **self-verify** the small LM’s output; POMDP meta-router | At least the small model; larger only if rejected | Self-verifier, not a separate offline teacher |

Pioneer: complexity class + calibrated P(success) per candidate is the **serving** story; labeling protocol is unpublished. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

---

### RouteLLM (Ong et al., 2024)

Paper: [https://arxiv.org/abs/2406.18665](https://arxiv.org/abs/2406.18665) / [v4 HTML](https://arxiv.org/html/2406.18665v4). Code: [https://github.com/lm-sys/RouteLLM](https://github.com/lm-sys/RouteLLM). Judge dataset card: [https://huggingface.co/datasets/routellm/gpt4_judge_battles](https://huggingface.co/datasets/routellm/gpt4_judge_battles) (Apache-2.0; ~109k rows; schema `prompt`, `response_a/b`, `winner_*`; card README empty, schema is first-party).

**Setup:** binary route between strong (e.g. GPT-4) and weak (e.g. Mixtral-8x7B). Student predicts \(P(\mathrm{win}_s \mid q)\); threshold \(\alpha\) trades cost vs quality. ([v4 §2–3](https://arxiv.org/html/2406.18665v4))

**Label sources:**

1. **Arena human preference.** ~80k battles → prune short prompts → ~65k comparisons / 64 models. Cluster into 10 leaderboard tiers; top-2 = strong, tier 3 = weak. Pairwise labels are sparse (<0.1% for a given pair). **“Crucially, we exclude model responses and retain only the winner identities in training.”** ([v4 §4.1](https://arxiv.org/html/2406.18665v4))
2. **Golden-labeled augmentation.** MMLU validation (~1500): run \(M_s\) and \(M_w\), compare to the answer key → win/tie/loss. Needed because Arena-only routers fail OOD on MMLU. ([v4 §4.1.1, §5.1](https://arxiv.org/html/2406.18665v4))
3. **LLM-judge augmentation.** Generate both responses (reuse Nectar GPT-4 answers as \(M_s\), generate Mixtral as \(M_w\)), then GPT-4 pairwise judge. ~120k samples, ~$700. Debias using MT-Bench judge practices (Zheng et al. 2023). ([v4 §4.1.1](https://arxiv.org/html/2406.18665v4); dataset [gpt4_judge_battles](https://huggingface.co/datasets/routellm/gpt4_judge_battles))

**Eval leakage control:** cross-contamination check between train and MMLU / MT-Bench / GSM8K; report uncontaminated results. ([v4 §5](https://arxiv.org/html/2406.18665v4))

**Implication for us:** a teacher **can** produce pairwise preference **after two candidate completions**, and a student can learn from query + winner only. A teacher **cannot** mint a trustworthy N-way success matrix from the query alone; that is what RouteLLM’s router is trained to approximate, and they still needed gold/judge augmentation for OOD.

---

### HybridLLM (Ding et al., ICLR 2024)

Paper: [https://arxiv.org/abs/2404.14618](https://arxiv.org/abs/2404.14618) / [v1 HTML](https://arxiv.org/html/2404.14618v1). MSR page: [https://www.microsoft.com/en-us/research/publication/hybrid-llm-cost-efficient-and-quality-aware-query-routing/](https://www.microsoft.com/en-us/research/publication/hybrid-llm-cost-efficient-and-quality-aware-query-routing/).

**“Easy” is not intrinsic difficulty.** Easy = small-model BARTScore is close to (or better than) the large model. Quality gap \(H(x)=q(S(x))-q(L(x))\) is a random variable (non-deterministic gens). ([v1 §2–3](https://arxiv.org/html/2404.14618v1))

**Labels require both models’ outputs.** They sample 10k MixInstruct train queries and **generate 10 responses from all LLMs under consideration**, then train DeBERTa-v3-large to predict the gap. They prefer BARTScore over GPT-ranking because GPT-ranking is expensive and cannot break ties. ([v1 §2, §4](https://arxiv.org/html/2404.14618v1))

**Implication:** HybridLLM’s difficulty label **is** per-pair success gap, and they **run the candidates** (with multi-sample) to get it. BARTScore is not our escalate/tool-valid label and is a poor proxy for coding-agent tool JSON.

---

### FrugalGPT (Chen, Zaharia, Zou; TMLR / arXiv 2305.05176)

Paper: [https://arxiv.org/abs/2305.05176](https://arxiv.org/abs/2305.05176); author PDF: [https://lingjiaochen.com/papers/2024_FrugalGPT_TMLR.pdf](https://lingjiaochen.com/papers/2024_FrugalGPT_TMLR.pdf).

**Serving vs labeling.** At inference: query-agnostic cascade (router permutation + DistilBERT generation scorer + threshold stop judger). Stop if \(g_i(q,a)>\tau_i\), else next LLM. ([TMLR §4](https://lingjiaochen.com/papers/2024_FrugalGPT_TMLR.pdf))

**How the scorer is trained:** for each LLM, DistilBERT input = **query appended with that service’s response**; label = **whether the response is correct** (task gold). 50/50 train/test split per dataset. They explicitly say pre-query quality estimation is hard for generative APIs, which is why they use a **post-query** scorer. ([TMLR §4, related work](https://lingjiaochen.com/papers/2024_FrugalGPT_TMLR.pdf))

**Implication:** FrugalGPT does **not** label success without running the model. The cheap model at inference is a scorer on an already-generated answer (same family as our escalate-after-empty/bad-JSON, not a pre-hop teacher). MPI tables need a full pairwise correctness matrix on the train split.

---

### LLMRouter / xRouteBench (Feng et al., 2026)

Paper: [https://arxiv.org/html/2608.06867v1](https://arxiv.org/html/2608.06867v1). First-party docs: [https://ulab-uiuc.github.io/LLMRouter/](https://ulab-uiuc.github.io/LLMRouter/), [data and metrics](https://ulab-uiuc.github.io/LLMRouter/learn/data-and-metrics/), [training and evaluation](https://ulab-uiuc.github.io/LLMRouter/learn/training-and-evaluation/). Repo: [https://github.com/ulab-uiuc/LLMRouter](https://github.com/ulab-uiuc/LLMRouter).

**Explicit claim:** constructing routing supervision “require[s] running every candidate model on every benchmark query and scoring each response with task-specific metrics.” Pipeline: query curation → **dispatch each query to every candidate** (18 models in the paper) → metric + token cost → dense query–model matrix used as both train labels and test bed. ([paper §1–3](https://arxiv.org/html/2608.06867v1))

**Supervision families they document** ([data and metrics](https://ulab-uiuc.github.io/LLMRouter/learn/data-and-metrics/)):

1. Classification: `best_model(q) = argmax_m Score(m,q)`
2. Pairwise preferences (Elo / matrix factorization)
3. Top-k vs last-k contrastive (e.g. RouterDC)
4. Binary gating: “is the small model good enough?” (HybridLLM / AutoMix style)

Optional `llm_judge` column in the weighted score. Offline eval uses `--route-only` against the precomputed matrix so provider noise does not confound router comparison. ([training and evaluation](https://ulab-uiuc.github.io/LLMRouter/learn/training-and-evaluation/))

**Implication:** this is the canonical **N-way gold** protocol. Teacher-only P(success) is not how LLMRouter builds supervision.

---

### RouterArena (Lu et al.; arXiv 2510.00202 / ICLR 2026)

arXiv HTML: [https://arxiv.org/html/2510.00202v2](https://arxiv.org/html/2510.00202v2). ICLR PDF: [https://proceedings.iclr.cc/paper_files/paper/2026/file/4987bb24bc53c198785922d1bd9e18cf-Paper-Conference.pdf](https://proceedings.iclr.cc/paper_files/paper/2026/file/4987bb24bc53c198785922d1bd9e18cf-Paper-Conference.pdf). Code: [https://github.com/RouteWorks/RouterArena](https://github.com/RouteWorks/RouterArena).

**Two difficulty notions (do not collapse them):**

| Version | Bloom LLM-as-judge | “True” difficulty |
| --- | --- | --- |
| arXiv v2 HTML | DeepSeek-V3.1 labels Bloom; remember/understand → easy, apply → medium, analyze/evaluate → difficult; drop create (open-ended, not reliably evaluable) | Same Bloom bins used as difficulty |
| ICLR 2026 | Same judge for **cognitive coverage only**; human check: 54.9% exact / 76.7% ±1 Bloom agreement on 450 stratified queries | **Empirical:** run 42 models; hard ≤4/42 correct, medium 5–19, easy ≥20 |

Cite both; prefer ICLR for evaluation difficulty. Oracle / optimal-selection metrics still need per-model correctness (they run inference themselves and **prefix-cache** overlapping pools). ([ICLR §3, §C.1, ethics](https://proceedings.iclr.cc/paper_files/paper/2026/file/4987bb24bc53c198785922d1bd9e18cf-Paper-Conference.pdf))

**Implication:** a teacher **can** label discrete complexity/cognitive bins from the conversation **without** candidate runs. Those bins are **coverage / features / reason_codes**, not a substitute for per-model success. Empirical difficulty ≈ “how many catalog models would succeed” — which **is** a multi-candidate success matrix.

---

### RouterBench (Hu et al., 2024)

Paper: [https://arxiv.org/abs/2403.12031](https://arxiv.org/abs/2403.12031) / [v1 HTML](https://arxiv.org/html/2403.12031v1). Data/code: [https://github.com/withmartian/routerbench](https://github.com/withmartian/routerbench).

405,467 pre-generated inference outcomes (11 models, 8 datasets, 64 tasks: reasoning, knowledge, conversation, math, coding, RAG). Quality \(q(o_i^j)\) and cost \(c(o_i^j)\) stored so routers can be trained/tested **without further inference**. Oracle = best-performing LLM, cheapest on ties. ([v1 §4](https://arxiv.org/html/2403.12031v1))

**Implication:** same family as LLMRouter’s matrix. Coding subset exists but labels are benchmark metrics, not escalate/tool-valid.

---

### Adjacent primary protocols (cited by the above)

**Zooter / “Routing to the Expert”** (Lu et al., NAACL 2024): infer **all** candidates on the train set → QwenRM scalar rewards → tag-based denoise → distill into a query-only DeBERTa router. Inference then calls one expert. RM ranking is weak on MMLU/GSM8K/HumanEval. ([https://aclanthology.org/2024.naacl-long.109/](https://aclanthology.org/2024.naacl-long.109/), [arXiv 2311.08692](https://arxiv.org/abs/2311.08692)). RouteLLM warns QwenRM labels “can inherit biases from their training data.” ([RouteLLM v4 related work](https://arxiv.org/html/2406.18665v4))

**AutoMix** (Aggarwal et al., NeurIPS 2024 / arXiv 2310.12963): small LM answers → few-shot **self-verification** on that answer → POMDP/threshold decides escalate. Not a pre-hop teacher; needs at least one completion. Self-verify is noisy by design. ([https://arxiv.org/abs/2310.12963](https://arxiv.org/abs/2310.12963), [https://automix-llm.github.io/automix/](https://automix-llm.github.io/automix/))

**LLM-Blender MixInstruct** (Jiang et al. 2023): source of HybridLLM’s queries/responses; GPT-ranking is the expensive alternative HybridLLM declined. Cited via HybridLLM / RouteLLM.

---

## Leakage and bias to avoid

Drawn only from the sources above plus this repo’s label split.

1. **Response leakage into the student.** RouteLLM drops candidate responses from router training and keeps winner ids only. Feeding completions (or escalate traces) into the live scorer would also blow the <10ms hop. ([RouteLLM v4 §4.1](https://arxiv.org/html/2406.18665v4); map: live hop in-process)

2. **Train/eval contamination.** RouteLLM decontaminates public benchmarks. Do not train on promotion-gate flashlight/OpenCode tasks or the 3×5 eval slice. ([RouteLLM v4 §5](https://arxiv.org/html/2406.18665v4); spec item 58)

3. **Judge position / verbosity bias.** RouteLLM explicitly de-biases GPT-4 pairwise judgements using Zheng et al. 2023 (MT-Bench) practices: swap order, etc. ([RouteLLM v4 §4.1.1 fn. 4](https://arxiv.org/html/2406.18665v4))

4. **Reward-model / teacher-family bias.** Zooter RM labels inherit RM training bias; RouteLLM prefers human prefs for that reason. A Qwen teacher scoring Qwen candidates (or Flash scoring Flash) will overstate same-family P(success). ([RouteLLM related work](https://arxiv.org/html/2406.18665v4); [Zooter](https://aclanthology.org/2024.naacl-long.109/))

5. **Wrong metric as “success.”** BARTScore (HybridLLM), Arena win, DistilBERT-vs-gold (FrugalGPT), RM scalar (Zooter) ≠ **no-escalate + valid tools**. Using them as P(success) gold would train the wrong head. HybridLLM also notes GPT-ranking cannot distinguish same-rank examples. ([HybridLLM §2](https://arxiv.org/html/2404.14618v1))

6. **Bloom bin ≠ empirical difficulty ≠ phase.** RouterArena ICLR: Bloom is coverage; difficulty is model-accuracy fraction. Our **phase** is an agent step name, not complexity. (`CONTEXT.md`; [RouterArena ICLR §3](https://proceedings.iclr.cc/paper_files/paper/2026/file/4987bb24bc53c198785922d1bd9e18cf-Paper-Conference.pdf))

7. **Session gold ≠ per-request label.** Flashlight `tests_passed` / OpenCode task outcome is promotion-gate only. A cheap discover hop can “succeed” (no escalate) in a session that later fails tests.

8. **Production missingness.** Flywheel JSONL only observes the **selected** model (and maybe one escalate). Treating unobserved candidates as failures is selection bias. LLMRouter/RouterBench gold is a **full matrix**; production is a bandit. New catalog models stay unlabeled until a matrix/explore pass (map Notes).

9. **Open-ended / create tasks.** RouterArena drops Bloom “create” because they cannot be reliably auto-evaluated. Coding edits without a harness are in this bucket — hence promotion-gate harness, not teacher prose quality. ([arXiv v2 §3](https://arxiv.org/html/2510.00202v2))

10. **Teacher in the eligible set.** If the teacher id is also a live candidate, query-only P(success) labels are not independent of the pool. Keep teacher **offline-only**; do not route live traffic through it. (`CONTEXT.md`)

11. **FrugalGPT distribution shift.** Scorer trained on one label mix degrades under shifted test labels; they still evaluate it. Recalibrate when flywheel mix ≠ bootstrap mix. ([FrugalGPT TMLR §5](https://lingjiaochen.com/papers/2024_FrugalGPT_TMLR.pdf))

12. **Sparsity / tiering.** Arena-style pairwise is too sparse for N-way without tiering or augmentation. ([RouteLLM v4 §4.1](https://arxiv.org/html/2406.18665v4))

---

## Proposed offline labeling recipe (aiand teacher)

Aligns with published protocols: **RouterArena-style teacher bins** + **LLMRouter/RouterBench-style measured success on a subset** + **RouteLLM-style query-only student features** + **production flywheel for the observed hop**. Teacher never serves `router/auto`.

### Label schema (two heads, three gold tiers)

| Field | Producer | Use |
| --- | --- | --- |
| `complexity_bin` | Teacher, query-only (messages + tool schemas + optional `x-agent-phase`) | Feature / `reason_codes`. Example enum: `trivial \| standard \| hard \| frontier` (not frozen; ticket 07). |
| `p_success_silver[model_id]` | Teacher, query-only, eligible ids only | Distillation prior / warm start. **Not** calibration gold. |
| `success_gold[model_id]` | **Run that candidate** on aiand; apply gateway predicate | Train + calibrate P(success). Missing = unobserved, not 0. |
| `session_gold` | Flashlight/OpenCode outcome when present | **Promotion gate only.** |

Gateway predicate for `success_gold` (must match live escalate):

```
success = (status not in {408,429} and status < 500 and status < 400
           and choices non-empty
           and (content or tool_calls)
           and tool_calls_valid(message)
           and (json_content_valid(message) if client asked for JSON))
```

(`src/aiand_router/app.py` `_should_escalate`, `tool_calls_valid`, `json_content_valid`)

### Teacher API (offline only)

- Base: `https://api.aiand.com/v1/chat/completions` with org key. ([https://docs.aiand.com/api/chat-completions/](https://docs.aiand.com/api/chat-completions/))
- `response_format`: strict `json_schema` (`additionalProperties: false`, all fields required; nullable via `["string","null"]`). ([https://docs.aiand.com/capabilities/structured-outputs/](https://docs.aiand.com/capabilities/structured-outputs/))
- Temperature 0. Cache by request identity (prompt + teacher id + schema + temperature + max tokens) — same keying as the gateway request cache. (spec item 52)
- **Do not** send candidate completions into the bin/`p_success_silver` call (RouteLLM response-exclusion).

Suggested strict schema (illustrative):

```json
{
  "complexity_bin": "trivial|standard|hard|frontier",
  "bloom_level": "remember|understand|apply|analyze|evaluate|create|null",
  "p_success": { "<eligible model id>": 0.0 },
  "tools_required": true,
  "label_confidence": 0.0
}
```

`p_success` keys = **eligible set after hard constraints**, not the full catalog. (map: trained only scores survivors)

### Teacher posture (Flash / Qwen / Pro) — protocol, not a pick

Ticket 10 chooses the default teacher. This recipe supports either:

- **Single teacher:** one catalog chat model labels bins + silver P(success) for every bootstrap row.
- **Cheap-then-escalate teacher (FrugalGPT/AutoMix-shaped, offline only):** Flash or Qwen labels all rows; if `label_confidence` is low, bin is `hard|frontier`, or silver P(success) disagrees with AA prior by a large margin, re-label with Pro. Still not the live hop.

Prefer a teacher **outside** the measured-trio / live default cheap models when labeling those models’ silver P(success) (family bias). Catalog prices: Qwen listed free to prototype; Flash $0.15/$0.25; Pro $1.00/$2.50 per 1M. ([https://docs.aiand.com/models/catalog/](https://docs.aiand.com/models/catalog/))

Pairwise judge variant (RouteLLM \(D_{judge}\)): only after **two** candidate completions exist; swap order once; store `winner` not prose. Use for OOD/open-ended hops where escalate/tool-valid is uninformative (e.g. summarize with no tools). Do not replace `success_gold` on tool hops.

### Stage A — Bootstrap (assume 3×5 is a smoke cache, not the corpus)

1. **Queries:** public coding-agent / SWE / tool-call traces (ticket 04) + synthetic conversations spanning phases (`discover…summarize`) and the four complexity bins. Dedup against flashlight seeds and any held-out gate set.
2. **Teacher pass (no candidate runs):** bin + silver `p_success` for each eligible id. Target: thousands of rows, not 15. RouterArena used ~8.4k eval queries; RouteLLM judge set ~120k — we need enough per bin×phase to train a tiny student, not Arena scale on day one.
3. **Measured matrix (sparse, not full N×Q):** following LLMRouter/RouterBench/HybridLLM, **run real aiand candidates** on a stratified subsample:
   - Stratify by `complexity_bin`, phase, tools-present vs not.
   - Always include the measured trio (Qwen 3.6 27B, Kimi K2.7 Code, DeepSeek V4 Pro) plus Flash (fallback/cheap) where eligible. (spec item 109)
   - For each cell: one greedy-ish completion (`temperature` matching prod), record status/empty/tool_valid/json_valid/tokens/cost → `success_gold`.
   - Budget posture: full matrix is the gold standard (LLMRouter 18-way; RouterArena 42-way for difficulty). If credits cannot cover N×Q, cover **cheap + one mid + one premium** per stratum (RouteLLM pair + FrugalGPT L=3), never a single model.
4. **Fit student** on query features (+ optional embed, ticket 05/11) → bin head + per-eligible P(success). Supervise P(success) with `success_gold` where present; silver teacher probs only as a regularizer/distillation target (Zooter-style), never as the calibration set.
5. **Calibrate** P(success) on a held-out **measured** slice only (ticket 03). Teacher silver is not a reliability diagram.

### Stage B — Production flywheel

1. Serve **rules** (then shadow trained). Log JSONL: selected, eligible candidates, escalate-from, status, `tool_valid`, `json_valid`, phase, effort. (`src/aiand_router/app.py` row)
2. Convert each logged hop to `success_gold[selected]` (and `success_gold[escalated_to]` if a second hop ran). **Leave other ids unobserved.**
3. Periodically: teacher-bin unlabeled new traffic (query-only); **explore / shadow-execute** a small random or uncertainty slice across 2–3 candidates to refresh the matrix (new catalog models stay rules-only until labeled — map Notes).
4. Retrain + recalibrate; promotion gate still uses harness/flashlight **session** outcome + escalate rate + ECE, not teacher agreement.

### What the teacher must not do

- Live `router/auto` hop.
- Promotion-gate grading.
- Invent `success_gold` for models that were not run.
- See future turns, pytest output, or escalate result when labeling complexity.
- Use Arena/BART/RM scores as drop-in P(success) without mapping through the gateway predicate.

### Minimal viable first spend

1. Teacher-bin + silver P(success) on a few thousand bootstrap prompts (Qwen/Flash class).
2. Measured `success_gold` on ~hundreds of stratified hops × 3–5 catalog models (reuse gateway cache).
3. Keep 3×5 cache as **demo/eval smoke**, disjoint from train.
4. Turn on flywheel logging before any trained pick.

---

## What this note does not freeze

- Exact bin names/boundaries → ticket 07 (HITL).
- Default teacher id / budget → ticket 10 (HITL; wait on this recipe).
- Student architecture → ticket 01.
- Numeric threshold / max_regret / ECE bars → tickets 03, 08.
- Public dataset list → ticket 04.

---

## Sources (owning)

- RouteLLM: [arXiv 2406.18665](https://arxiv.org/abs/2406.18665), [v4 HTML](https://arxiv.org/html/2406.18665v4), [lm-sys/RouteLLM](https://github.com/lm-sys/RouteLLM), [routellm/gpt4_judge_battles](https://huggingface.co/datasets/routellm/gpt4_judge_battles)
- HybridLLM: [arXiv 2404.14618](https://arxiv.org/abs/2404.14618), [v1 HTML](https://arxiv.org/html/2404.14618v1), [MSR publication page](https://www.microsoft.com/en-us/research/publication/hybrid-llm-cost-efficient-and-quality-aware-query-routing/)
- FrugalGPT: [arXiv 2305.05176](https://arxiv.org/abs/2305.05176), [TMLR PDF](https://lingjiaochen.com/papers/2024_FrugalGPT_TMLR.pdf)
- LLMRouter: [arXiv 2608.06867](https://arxiv.org/html/2608.06867v1), [docs: data/metrics](https://ulab-uiuc.github.io/LLMRouter/learn/data-and-metrics/), [docs: train/eval](https://ulab-uiuc.github.io/LLMRouter/learn/training-and-evaluation/), [ulab-uiuc/LLMRouter](https://github.com/ulab-uiuc/LLMRouter)
- RouterArena: [arXiv 2510.00202v2](https://arxiv.org/html/2510.00202v2), [ICLR 2026 PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/4987bb24bc53c198785922d1bd9e18cf-Paper-Conference.pdf), [RouteWorks/RouterArena](https://github.com/RouteWorks/RouterArena)
- RouterBench: [arXiv 2403.12031](https://arxiv.org/abs/2403.12031), [v1 HTML](https://arxiv.org/html/2403.12031v1)
- Zooter: [NAACL 2024](https://aclanthology.org/2024.naacl-long.109/), [arXiv 2311.08692](https://arxiv.org/abs/2311.08692)
- AutoMix: [arXiv 2310.12963](https://arxiv.org/abs/2310.12963), [project page](https://automix-llm.github.io/automix/)
- Pioneer (serving only, no label protocol): [https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md)
- aiand API: [chat completions](https://docs.aiand.com/api/chat-completions/), [structured outputs](https://docs.aiand.com/capabilities/structured-outputs/), [catalog](https://docs.aiand.com/models/catalog/)
- This repo: `CONTEXT.md`, `.scratch/trained-router/map.md`, `.scratch/aiand-coding-router/spec.md`, `src/aiand_router/app.py`, `src/aiand_router/router.py`, `src/aiand_router/flashlight.py`, `config/models.yaml`
