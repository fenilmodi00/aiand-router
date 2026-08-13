# Scorer architectures under a ~10ms hop

**Branch:** `research/scorer-architectures`  
**Question:** Which published router or classifier architectures can emit **calibrated per-candidate P(success)** for coding (or general LLM routing) while serving **in-process at about &lt;10ms** added latency?  
**Fetched:** 2026-08-13. Primary sources only (papers, official docs, first-party model cards). Indexes such as `.scratch/competitor-router-research.md` were used to find URLs, not as evidence.

**AIand constraints (product, not a published claim):** hard constraints still build the eligible set; the scorer only ranks/scores survivors; live hop must not call an aiand chat model (teacher-only, offline); an 8B remote embed is not the default live hop; embeddings may be training-time only; destination is a proposal-grade spec, not an implementation.

## How to read this note

- **Documented** = the owning paper or first-party doc states it.
- **Inferred** = a consequence of documented numbers (e.g. converting published throughput to per-request ms) or a gap (architecture not published). Inferred lines are labeled.
- Pioneer’s **product contract** (complexity class → calibrated P(success) → cheapest above threshold + max_regret) is first-party. Pioneer’s **scorer architecture is not documented**. Do not invent it. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

Almost no published router is both (a) coding-agent specific and (b) measured at &lt;10ms in-process with calibrated multi-candidate P(success). The useful literature is **general LLM routing** plus **calibration** plus **tiny encoder speed**. Coding-specific evidence is thin and called out.

---

## 1. Target output shape (what “P(success)” means)

### 1.1 Pioneer product contract (documented behavior, undocumented internals)

Pioneer’s Model Router is a **coding** router: “picks the cheapest model that meets your quality bar on every **coding** request.” “Model Routing **currently works with coding tasks**.” It is a “low-latency model router trained on coding tasks.” ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

Documented pipeline ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md)):

1. Read the messages.
2. Classify task complexity from the conversation (example: trivial lookup vs multi-file refactor).
3. Produce a **calibrated success probability for each candidate model** on this task (score 0–1 = predicted likelihood of succeeding).
4. Select the **cheapest** model whose score clears configured **threshold** and **max_regret**.
5. If no candidate clears the bar, **or the router is unreachable**, fall back without error.

Effort presets retune threshold + max_regret only (`low`…`max`, plus Pioneer-only `xhigh`). Observability includes confidence (= winner P(success)), rule (`threshold` | `max_regret` | `fallback_declined`), and reason codes. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

**Not documented:** model size, features vs embed vs SLM, in-process vs sidecar RPC, calibration method (Platt / isotonic / temperature / IRT), latency in milliseconds. **Inferred:** any claim that Pioneer is “DeBERTa / MF / IRT / 8B embed” is invention. Stop.

### 1.2 Azure Model Router (lightweight ML, not an LLM; architecture still opaque)

Microsoft documents Model Router as “a purpose-built, trained machine-learning model,” “a **lightweight ML model** designed to predict which model performs best for a given prompt at **minimal latency**,” and explicitly “**not an LLM itself**.” Training data includes “question answering, **code generation**, mathematical reasoning,” summarization, conversations, and agentic/tool-calling workloads. The hop “adds minimal overhead — a negligible fraction of the LLM inference time.” Modes are Balanced / Cost / Quality. ([https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works))

**Not documented:** parameter count, encoder vs feature model, whether scores are calibrated posteriors, ms overhead. **Inferred:** Azure’s published shape (tiny non-LLM scorer + difficulty-aware pick + no chat-LLM hop) is compatible with aiand’s hop constraints; their internals still cannot be copied.

### 1.3 Academic definition of per-candidate P(success)

Shnitzer et al. formalize routing as **one binary correctness predictor per LLM**: \(g_m(x)\) estimates \(P(y(x,m)=1\mid x)\), trained with binary cross-entropy; \(y\) is whether model \(m\) was “correct enough” on input \(x\). Test time calls only the chosen LLM, plus “one call to some general embedding function.” ([https://arxiv.org/abs/2309.15789](https://arxiv.org/abs/2309.15789))

IRT-Router models \(P(\text{LLM } M_j \text{ succeeds on query } q_i)\) with Item Response Theory (logistic MIRT or neural NIRT), then combines that predicted performance with cost. ([https://arxiv.org/abs/2506.01048](https://arxiv.org/abs/2506.01048), ACL 2025: [https://aclanthology.org/2025.acl-long.761/](https://aclanthology.org/2025.acl-long.761/))

EmbedLLM’s decoder outputs a **correctness score** \(s_{m,q}=\sigma(p_1-p_0)\): “predicted probability of the model \(m\) correctly answering question \(q\).” Routing uses that probability plus a threshold. ([https://arxiv.org/abs/2410.02223](https://arxiv.org/abs/2410.02223))

RouteLLM parameterizes a **win probability** \(P_\theta(\text{win}_{\mathcal{M}_\text{strong}}\mid q)\) and thresholds it; evaluation is **binary** strong vs weak, not N-way P(success). They note N-way as future work. ([https://arxiv.org/abs/2406.18665](https://arxiv.org/abs/2406.18665))

HybridLLM trains a BERT-style encoder to estimate \(\Pr[q(S(x))\ge q(L(x))]\) (small model quality ≥ large), then thresholds. Binary, not per-candidate catalog scoring. ([https://arxiv.org/abs/2404.14618](https://arxiv.org/abs/2404.14618), ICLR 2024)

**Documented vs inferred:** “0–1 score” ≠ “calibrated P(success).” Pioneer *claims* calibration; RouteLLM/HybridLLM/RouterBench scores are typically used as ranking/threshold signals. Calibration as a *method* is documented in Guo et al. (temperature scaling) and Platt (sigmoid mapping), not in Pioneer’s docs. ([http://proceedings.mlr.press/v70/guo17a/guo17a.pdf](http://proceedings.mlr.press/v70/guo17a/guo17a.pdf), [https://arxiv.org/abs/1706.04599](https://arxiv.org/abs/1706.04599); Platt 1999, *Advances in Large Margin Classifiers*)

---

## 2. Published architecture families

LLMRouter’s survey paper is useful as a **taxonomy owned by the library authors**, not as latency evidence. A router is \(E_q\) (context encoder) + \(E_m\) (model encoder) + scoring \(g\) + decision \(d\) + learning signal. Families: embedding similarity (\(k\)NN), bilinear/MF, classification head, GNN message passing, next-token LM router, cascade accept/escalate. ([https://arxiv.org/html/2608.06867v1](https://arxiv.org/html/2608.06867v1); first-party site [https://ulab-uiuc.github.io/LLMRouter/](https://ulab-uiuc.github.io/LLMRouter/))

| Family | What it emits | Multi-candidate P(success)? | Live hop (documented) | ~&lt;10ms in-process? |
| --- | --- | --- | --- | --- |
| Feature / tiny head (Shnitzer \(g_m\), RouterBench MLP) | \(P(\text{correct}\mid x,m)\) or regression score | **Yes** if one head per model or bilinear over model factors | Sentence embed + \(k\)NN/MLP, or MLP on features | **Yes if no large live embed**; MLP/logistic alone is trivial. Embed hop depends on encoder size (see §3). |
| Matrix factorization / EmbedLLM bilinear | BT win score or sigmoid correctness | RouteLLM: **binary** pair. EmbedLLM: **yes**, 112 models | RouteLLM MF: OpenAI `text-embedding-3-small` + tiny projection. EmbedLLM: `all-mpnet-base-v2` + Hadamard + linear | MF **head** is tiny. **Live embed** may fail 10ms if remote/8B/BERT-base. |
| IRT / MIRT-BERT | Explicit \(P(\text{correct})\) via logistic IRT | **Yes** (20 LLMs in paper) | Query embed (e.g. BERT) + tiny IRT layers; optional \(k\)NN warmup | IRT math is cheap. **BERT embed** likely fails 10ms CPU (see DistilBERT §3). RouterArena reports MIRT-BERT latency on the order of **~14 ms** (see §3). |
| BERT / DeBERTa classifier (HybridLLM, RouteLLM BERT) | Sigmoid score / win probability | HybridLLM/RouteLLM BERT: **binary** | Full encoder forward (DeBERTa-v3-large 300M; BERT-base) | **Fails as published:** HybridLLM router **36 ms**. DistilBERT STS-B CPU pass is still hundreds of ms/example. |
| Causal LLM-as-router (RouteLLM Llama-3-8B; LLMRouter CausalLM / Router-R1) | Next-token class / verbalized pick | Usually 2-way or argmax over named models | Autoregressive 8B (or similar) | **Fails** latency + aiand “no chat model on live hop.” |
| Cascade + post-hoc scorer (FrugalGPT, AutoMix) | Quality score **after generation** | Sequential, not a single pre-hop P vector | Must call at least one chat LLM, then DistilBERT/self-verify | **Fails** hop constraint and latency. |
| Semantic Router (Aurelio) | Cosine similarity to **utterances / routes** | **No** P(success) per catalog model | Bi-encoder + similarity | Wrong output shape. Encoder may be remote OpenAI/Cohere or local HF. ([https://docs.aurelio.ai/semantic-router/user-guide/concepts/overview](https://docs.aurelio.ai/semantic-router/user-guide/concepts/overview)) |
| GraphRouter | Edge logits / “probability distribution of the selected LLM” | Softmax over models, not necessarily calibrated P(success) | BERT/PLM init + GNN; GPT-4o used offline for task/LLM descriptions | No &lt;10ms measurement. BERT init likely similar cost to HybridLLM encoder. ([https://arxiv.org/abs/2410.03834](https://arxiv.org/abs/2410.03834)) |

---

## 3. Latency: documented numbers vs the 10 ms bar

### 3.1 Documented router latency / throughput

**HybridLLM (ICLR 2024).** DeBERTa-v3-large (300M) router, same backbone for deterministic / probabilistic / transformed scores. Average latency **0.036 ± 0.002 s (36 ms)** vs Flan-T5-800M 0.46 s, Llama-2-7B 7.99 s, Llama-2-13B 14.61 s. Authors call router cost “negligible compared to autoregressive decoding.” **Relative to LLM decode, yes. Relative to a 10 ms hop, no.** ([https://arxiv.org/abs/2404.14618](https://arxiv.org/abs/2404.14618))

**RouteLLM.** Table 7 reports **throughput**, not p50 latency, on Chatbot Arena conversations. GPU routers on GCP `g2-standard-4` (1× NVIDIA L4); SW ranking on CPU `n2-standard-8`. ([https://arxiv.org/abs/2406.18665](https://arxiv.org/abs/2406.18665))

| Router | Cost / million requests | Requests / second | VM |
| --- | --- | --- | --- |
| SW Ranking | $37.36 | **2.9** | CPU n2-standard-8 |
| Matrix Factorization | $1.42 | **155.16** | L4 GPU |
| BERT | $3.19 | **69.62** | L4 GPU |
| Causal LLM | $5.23 | **42.46** | L4 GPU |

SW ranking and MF **embed the query with OpenAI `text-embedding-3-small`**. Causal LLM is Llama-3-8B next-token classification. ([https://arxiv.org/abs/2406.18665](https://arxiv.org/abs/2406.18665))

**Inferred (not stated as ms):** \(1000/155 \approx 6.4\) ms/req (MF), \(1000/70 \approx 14\) ms (BERT), \(1000/42 \approx 24\) ms (causal 8B), \(1000/2.9 \approx 345\) ms (SW). Throughput ≠ single-request latency if batched. Even as a lower bound, **SW ranking with a remote embed fails 10 ms**; **causal 8B fails**; **BERT-base on L4 is at best borderline**; **MF head + GPU embed is the only RouteLLM shape that *might* clear 10 ms**, and only if the embed is local/tiny—not a remote API and not 8B.

**EmbedLLM.** On 1× A100 80GB, MF router takes **3.80 s to route 3,000 questions** (50 trials), “basically free compared to downstream model inference.” Vs RouteLLM causal LLM “&lt;50 requests per second,” EmbedLLM “more than **750** model selections” from a **112**-model pool; training uses &lt;1 GB GPU vs “60× cheaper than fine-tuning Llama-3-8B.” ([https://arxiv.org/abs/2410.02223](https://arxiv.org/abs/2410.02223))

**Inferred:** \(3800/3000 \approx 1.3\) ms per question **for the MF head after question embeddings exist**. Question text is pre-embedded with sentence-transformers **`all-mpnet-base-v2`** (\(d=768\)). If that encoder is on the live hop, add its latency. The 1.3 ms figure is **not** an 8B embed hop.

**RouterArena.** Routing latency is a first-class metric: additional TTFT / E2E when the router sits on the critical path; some routers introduce “non-negligible overhead that may even compromise SLOs.” Figure 9 plots latency on a **0–600 ms** axis. In the extracted comparison, **MIRT-BERT ≈ 13.7** and **K-means ≈ 11.3** sit on that latency axis (units: ms). Commercial / large routers reach hundreds of ms. ([https://arxiv.org/abs/2510.00202](https://arxiv.org/abs/2510.00202))

**Inferred:** published multi-candidate IRT-BERT serving is **around the 10 ms line, slightly over**, not comfortably under. Treat 13.7 ms as “does not clear a hard 10 ms bar” unless aiand measures a smaller student.

**Azure / Pioneer.** “Minimal overhead” / “low-latency” only. **No ms.** ([https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works), [https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

### 3.2 Encoder size vs 10 ms (primary speed tables)

**DistilBERT (Sanh et al.).** 66M params vs BERT-base 110M; **60% faster**, 97% of BERT GLUE. Table 3: full STS-B dev pass, CPU Xeon E5-2690 v3 @ 2.9 GHz, batch size 1: BERT-base **668 s**, DistilBERT **410 s**. ([https://arxiv.org/abs/1910.01108](https://arxiv.org/abs/1910.01108))

STS-B dev has on the order of \(10^3\) examples. **Inferred:** DistilBERT is still **hundreds of ms per example** on that CPU setup—not a 10 ms hop. Distillation helps vs BERT; it does **not** by itself satisfy aiand’s budget on CPU.

**Sentence-Transformers (first-party).** `all-MiniLM-L6-v2` is **5× faster** than `all-mpnet-base-v2` while remaining “good quality.” ([https://www.sbert.net/docs/sentence_transformer/pretrained_models.html](https://www.sbert.net/docs/sentence_transformer/pretrained_models.html)) MiniLM-class semantic-search models report **~18,000 GPU / ~750 CPU queries per second** (`multi-qa-MiniLM-L6-*`, `msmarco-MiniLM-L6-cos-v5`); mpnet/BERT-base class is **~4,000 GPU / ~170 CPU q/s**. ([https://www.sbert.net/docs/sentence_transformer/pretrained_models.html](https://www.sbert.net/docs/sentence_transformer/pretrained_models.html))

**Inferred:** \(1000/750 \approx 1.3\) ms/query CPU for MiniLM **if** 1/throughput ≈ latency. That is the only widely published **tiny local embed** in the same order of magnitude as 10 ms. `all-mpnet-base-v2` (~5× slower) is **inferred ~6–7 ms CPU** at the same conversion—borderline, hardware-dependent. Do not treat throughput tables as a measured p50 for long coding-agent transcripts (MiniLM usable length is short; `all-MiniLM-L6-v2` is trained around 256 word pieces on the MiniLM line—confirm on the model card before using on full OpenCode histories).

**Qwen3-Embedding (first-party card + tech report).** Series sizes **0.6B / 4B / 8B**; 8B has **36 layers**, context **32k**, embedding dim **up to 4096** (MRL 32–4096). Intended tasks include retrieval, **classification**, clustering, **code retrieval**. No router-hop ms published. ([https://huggingface.co/Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B), [https://arxiv.org/abs/2506.05176](https://arxiv.org/abs/2506.05176))

**Inferred:** an **8B, 36-layer** embed as the default **live** hop cannot be assumed to fit ~10 ms in-process (and a **remote** 8B hop adds RTT). Compatible with aiand as **training-time features only**. The **0.6B** sibling is still ~25× MiniLM-L6 (22.7M) and is not a documented &lt;10 ms hop.

### 3.3 Shapes that fail the bar (for aiand)

| Shape | Why it fails | Source |
| --- | --- | --- |
| **Chat-LLM-as-router** (Llama-3-8B classifier, Router-R1, any aiand catalog chat model) | Autoregressive hop; RouteLLM causal LLM 42 rps on L4; violates “teacher only.” | [https://arxiv.org/abs/2406.18665](https://arxiv.org/abs/2406.18665), [https://arxiv.org/html/2608.06867v1](https://arxiv.org/html/2608.06867v1) |
| **Online 8B embed** (Qwen3-Embedding-8B or similar remote) | 8B/36L foundation embed; no published &lt;10 ms hop; remote RTT. | [https://huggingface.co/Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B) |
| **RouteLLM SW ranking + `text-embedding-3-small`** | 2.9 rps on CPU VM; remote embed. | [https://arxiv.org/abs/2406.18665](https://arxiv.org/abs/2406.18665) |
| **HybridLLM DeBERTa-v3-large** | **36 ms documented.** | [https://arxiv.org/abs/2404.14618](https://arxiv.org/abs/2404.14618) |
| **BERT-base / DistilBERT as the live encoder on CPU** | DistilBERT STS-B CPU: 410 s full pass; inferred hundreds of ms/example. RouteLLM BERT 70 rps on L4 is at best ~14 ms inferred. | [https://arxiv.org/abs/1910.01108](https://arxiv.org/abs/1910.01108), [https://arxiv.org/abs/2406.18665](https://arxiv.org/abs/2406.18665) |
| **FrugalGPT cascade** | Router + DistilBERT **generation scorer** after calling LLM APIs; stop/escalate loop. Live hop includes chat models. | [https://arxiv.org/abs/2305.05176](https://arxiv.org/abs/2305.05176), TMLR PDF [https://lingjiaochen.com/papers/2024_FrugalGPT_TMLR.pdf](https://lingjiaochen.com/papers/2024_FrugalGPT_TMLR.pdf) |
| **AutoMix** | Generate with small LM → few-shot self-verification → POMDP escalate. Live hop includes LM generation. | [https://arxiv.org/abs/2310.12963](https://arxiv.org/abs/2310.12963) |
| **Semantic Router as P(success) scorer** | Similarity to utterances, not per-candidate success probability. | [https://docs.aurelio.ai/semantic-router/user-guide/concepts/overview](https://docs.aurelio.ai/semantic-router/user-guide/concepts/overview) |

RouterBench itself **does not report router latency**; it flags latency as future work. ([https://arxiv.org/abs/2403.12031](https://arxiv.org/abs/2403.12031))

---

## 4. Calibration (what literature actually specifies)

**Definition.** Guo et al.: confidence calibration means probability estimates that match true correctness likelihood; they evaluate ECE / reliability diagrams / NLL. Modern nets are often overconfident. **Temperature scaling** (single scalar \(T\) on logits, then softmax) is “a single-parameter variant of Platt Scaling” and “surprisingly effective.” It does not change argmax accuracy. ([https://arxiv.org/abs/1706.04599](https://arxiv.org/abs/1706.04599), ICML 2017 PDF [http://proceedings.mlr.press/v70/guo17a/guo17a.pdf](http://proceedings.mlr.press/v70/guo17a/guo17a.pdf))

**Platt scaling.** Fit a sigmoid on classifier scores to get \(P(\text{class}\mid\text{input})\). Post-hoc; does not retrain the base model. (Platt, 1999, *Probabilistic Outputs for Support Vector Machines…*, Advances in Large Margin Classifiers)

**HybridLLM** explicitly designs router score as an estimate of \(\Pr[H(x)\ge 0]\) and uses a small **calibration set** (500 validation samples) to pick the **operating threshold**, not to publish ECE. ([https://arxiv.org/abs/2404.14618](https://arxiv.org/abs/2404.14618))

**IRT-Router** outputs a **logistic probability of success** by construction (MIRT). That is a calibrated *functional form*, not a reported ECE on coding-agent escalate labels. ([https://arxiv.org/abs/2506.01048](https://arxiv.org/abs/2506.01048))

**Pioneer** says “calibrated success probability” and uses it as a **thresholdable** quantity. **Method not documented.** ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

**Inferred for the spec:** any student that emits logits or raw GBDT margins should add a **documented** post-hoc map (temperature or Platt) and gate promotion on ECE/Brier—not only cheaper picks. That evaluation ticket is separate (`issues/03-calibration-for-router-p-success.md`); this note only records that calibration is a **post-processor**, not a reason to pick a huge live encoder.

---

## 5. Coding-specific evidence (thin)

| Source | Coding relevance | Architecture useful for aiand? |
| --- | --- | --- |
| Pioneer docs | **Coding-only** product; complexity + per-model P(success) + cheapest-above-bar. | Policy/contract **yes**. Internals **no**. |
| Azure Model Router | Training includes **code generation** and agentic tool-calling. | Lightweight non-LLM hop **yes**. Internals **no**. |
| RouterBench | Dataset includes **MBPP** among tasks; KNN/MLP predictive routers. | MLP/KNN **shape** yes. No &lt;10 ms. ([https://arxiv.org/abs/2403.12031](https://arxiv.org/abs/2403.12031)) |
| IRT-Router | **HumanEval** used as **OOD** test set. | Multi-candidate logistic P(success) **yes**. BERT embed hop risky. ([https://arxiv.org/abs/2506.01048](https://arxiv.org/abs/2506.01048)) |
| Qwen3-Embedding | MTEB **Code** retrieval; classification listed as a downstream task. | **Training-time** features **yes**. Live 8B **no**. ([https://arxiv.org/abs/2506.05176](https://arxiv.org/abs/2506.05176)) |
| RouteLLM / HybridLLM / FrugalGPT | General QA / MT-Bench / MixInstruct, not coding-agent sessions. | Architecture lessons only. |
| Semantic Router | Intent/utterance routing, not catalog P(success). | Not the scorer. |

**Inferred:** a coding-agent scorer will be **trained on aiand teacher labels + flywheel JSONL**, not downloaded as a published coding-router checkpoint. Published papers justify the **shape**, not a ready student.

---

## 6. Recommendations (proposal-grade; do not implement here)

Two shapes are compatible with: eligible-set already filtered; in-process ~&lt;10 ms; no live aiand chat model; no default online 8B embed; embeddings optional at **train** time; emit per-survivor P(success) for threshold + max_regret.

### Recommendation A (default) — Feature model + per-candidate calibrated heads

**What to copy (documented):** Shnitzer’s reduction of routing to **binary correctness predictors** \(g_m(x)\approx P(\text{success}\mid x,m)\); RouterBench’s **MLP (1–2×100 ReLU) or \(k\)NN** predicting performance per model; Pioneer/Azure **policy** (cheapest above bar / difficulty-aware pick among a subset). ([https://arxiv.org/abs/2309.15789](https://arxiv.org/abs/2309.15789), [https://arxiv.org/abs/2403.12031](https://arxiv.org/abs/2403.12031), [https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md))

**Live hop:** only cheap request/catalog features already available in the gateway (token estimate, tools present, phase hint, allowlist, latency cap, prior AA / measured success, price, context window, tool-capable flag) plus an optional **tiny discrete complexity bin** (Pioneer documents complexity classification; the map wants explicit bins). A logistic or GBDT head **per eligible model** (or one shared trunk + model-id embedding table) + **temperature/Platt** on a held-out set (Guo / Platt).

**Why it clears 10 ms:** no transformer forward, no remote embed, no chat LLM. Classical ML on tens of features is microseconds–low milliseconds on CPU. **Inferred**, but the alternative published encoder hops are measured **above** 10 ms (HybridLLM 36 ms; DistilBERT CPU hundreds of ms/example).

**Training-time embeds (optional, not on the hop):** Qwen3-Embedding-8B / MiniLM / teacher embeddings as **offline features or distillation targets** only—consistent with the Qwen3 card (classification / code retrieval) and with “embeddings may be training-only.” ([https://huggingface.co/Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B))

**Risk (documented in Shnitzer):** correctness predictors can be weak OOD (their HELM \(g_m\) accuracy ≈ 0.59); they recommend a small in-domain labeled set. Aiand’s flywheel + flashlight outcomes are that in-domain set. ([https://arxiv.org/abs/2309.15789](https://arxiv.org/abs/2309.15789))

### Recommendation B (if features alone underfit) — Tiny bilinear / MIRT head, embeddings **offline or MiniLM-class only**

**What to copy:** RouteLLM **matrix factorization** (query vector × model vector → BT win score); EmbedLLM **Hadamard + linear → sigmoid correctness** over many models, with **frozen model embeddings**; IRT-Router **MIRT logistic** \(P(\text{success})\) after a query embedding. ([https://arxiv.org/abs/2406.18665](https://arxiv.org/abs/2406.18665), [https://arxiv.org/abs/2410.02223](https://arxiv.org/abs/2410.02223), [https://arxiv.org/abs/2506.01048](https://arxiv.org/abs/2506.01048))

**Live hop options that can still hit ~10 ms:**

1. **No live embed:** map the same cheap features as Rec A into a small query latent (\(d\sim 32\)–\(128\)) via a tiny MLP; keep **model factors frozen**; score \( \sigma(v_m \odot v_q) \) or MIRT logistic. EmbedLLM/RouteLLM MF math without the heavy encoder. EmbedLLM’s **1.3 ms / query on A100 for the MF head** supports the head itself. ([https://arxiv.org/abs/2410.02223](https://arxiv.org/abs/2410.02223))
2. **Distilled local MiniLM-class embed only if measured p50 still &lt;10 ms** on representative coding transcripts. Sentence-Transformers publishes MiniLM at ~750 CPU q/s vs mpnet ~170. **Do not** default to BERT-base, DeBERTa-large, `text-embedding-3-small` remote, or Qwen3-8B online. ([https://www.sbert.net/docs/sentence_transformer/pretrained_models.html](https://www.sbert.net/docs/sentence_transformer/pretrained_models.html))

**Do not copy as the live hop:** HybridLLM DeBERTa-v3-large (36 ms); RouteLLM Llama-3-8B; FrugalGPT DistilBERT-after-generation; GraphRouter BERT+GNN; Semantic Router utterance index.

**Calibration:** bilinear/IRT logits still need Guo/Platt (or report ECE of the IRT logistic) before treating scores as Pioneer-style thresholdable P(success).

### Complexity bin

Pioneer documents **complexity classification plus** per-model P(success). Azure documents **difficulty-aware** routing. Neither publishes the bin taxonomy. **Inferred for the spec:** a tiny multiclass head sharing Rec A features (or Rec B query latent) is enough; bins are an input to \(g_m\), not a substitute for per-candidate P(success). Taxonomy is a separate ticket (`issues/07-complexity-bin-taxonomy.md`).

---

## 7. What the spec should say vs leave open

**Say (supported by primary sources):**

- Scorer is a **predictive** router: pick among the **already eligible** set without generating from candidates (RouterBench predictive vs cascade; Shnitzer vs LLM-blender/FrugalGPT).
- Output is **per-survivor P(success)**, then **cheapest clearing threshold + max_regret** (Pioneer contract; HybridLLM/Azure show threshold/mode as the quality–cost knob).
- Live hop is a **non-LLM** student (Azure wording; RouteLLM/EmbedLLM show 8B causal routers are the slow/expensive ones).
- **Teacher** chat models and **large embeds** are offline (FrugalGPT/AutoMix fail if pulled onto the hop; Qwen3-8B is a training feature candidate only).
- Calibration is **explicit post-processing** (Guo / Platt), not “sigmoid ≈ calibrated.”

**Leave open (not documented for coding-agent 10 ms):**

- Exact feature list / whether MiniLM ever joins the live hop (measure; don’t assume).
- Whether Rec A alone beats rules on flashlight/OpenCode labels.
- Numeric ECE bars (calibration ticket).
- Pioneer/Azure internals.

---

## 8. Source list (primary)

| ID | Work | URL |
| --- | --- | --- |
| Pioneer Router | First-party coding router concepts | https://docs.pioneer.ai/concepts/router.md |
| Azure Model Router | First-party “how it works” | https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works |
| RouteLLM | Ong et al., arXiv:2406.18665 | https://arxiv.org/abs/2406.18665 |
| HybridLLM | Ding et al., ICLR 2024, arXiv:2404.14618 | https://arxiv.org/abs/2404.14618 |
| FrugalGPT | Chen, Zaharia, Zou, arXiv:2305.05176 / TMLR PDF | https://arxiv.org/abs/2305.05176 |
| RouterBench | Hu et al., arXiv:2403.12031 | https://arxiv.org/abs/2403.12031 |
| Shnitzer et al. | arXiv:2309.15789 | https://arxiv.org/abs/2309.15789 |
| EmbedLLM | Zhuang et al., ICLR 2025, arXiv:2410.02223 | https://arxiv.org/abs/2410.02223 |
| IRT-Router | Song et al., ACL 2025, arXiv:2506.01048 | https://arxiv.org/abs/2506.01048 |
| GraphRouter | Feng et al., arXiv:2410.03834 | https://arxiv.org/abs/2410.03834 |
| AutoMix | Aggarwal et al., arXiv:2310.12963 | https://arxiv.org/abs/2310.12963 |
| LLMRouter | arXiv:2608.06867 + official docs | https://arxiv.org/html/2608.06867v1 |
| RouterArena | Lu et al., arXiv:2510.00202 | https://arxiv.org/abs/2510.00202 |
| Semantic Router | Aurelio first-party overview | https://docs.aurelio.ai/semantic-router/user-guide/concepts/overview |
| DistilBERT | Sanh et al., arXiv:1910.01108 | https://arxiv.org/abs/1910.01108 |
| Qwen3-Embedding | Card + arXiv:2506.05176 | https://huggingface.co/Qwen/Qwen3-Embedding-8B |
| Sentence-Transformers | Official pretrained model table | https://www.sbert.net/docs/sentence_transformer/pretrained_models.html |
| Guo et al. | ICML 2017 calibration / temperature scaling | https://arxiv.org/abs/1706.04599 |
| Platt 1999 | Probabilistic outputs / sigmoid scaling | Advances in Large Margin Classifiers (Platt scaling) |

**Not used as evidence:** blogs, tweets, LMSYS blog (index only), third-party writeups of Pioneer/FireRouter internals, DeepWiki summaries.
