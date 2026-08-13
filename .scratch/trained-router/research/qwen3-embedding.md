# Qwen3-Embedding-8B as optional training features

**Question:** Can Qwen3-Embedding-8B (and the Qwen3-Embedding series) plus published embedding-based routers support using these vectors as **training features** for model routing?

**Scope:** primary sources only — Qwen official paper/model card/GitHub, Nebius Token Factory docs + catalog, aiand docs, published router papers. Not third-party magazines.

**Fetched:** 2026-08-13.

**Constraints (from ticket / map):** online 8B embed on every `router/auto` request is **out** unless a measured p50 still fits ~&lt;10ms (assume it does not until a primary source or measurement says otherwise). Prototype access: Nebius Token Factory `Qwen/Qwen3-Embedding-8B`. Production spec must **not** hard-require Nebius. aiand has no embedding catalog. Embeddings stay optional: keep them only if they help training.

---

## Recommendation

**Try training-time embeddings as an optional ablation. Do not use 8B online. Do not hard-require Nebius. Keep features-only as the default recipe until the ablation wins.**

| Decision | Verdict |
| --- | --- |
| Online 8B embed on every `router/auto` hop | **Don't try.** No primary source or measurement shows p50 &lt;10ms. Remote Token Factory RTT alone cannot meet that bar. |
| Qwen3-Embedding vectors as **offline training features** | **Try**, vs a features-only baseline. Published routers do this. Qwen3 is trained for classification + code retrieval. Apache 2.0 weights exist independently of Nebius. |
| Hard-require Nebius in the production spec | **Don't.** aiand has no embedding catalog; prototype may call Token Factory; production must self-host or call any external embed API. |
| Assume 8B specifically beats a tiny embed / features-only | **Don't assume.** LLMRouterBench finds backbone embed quality has little effect on routing accuracy. |

---

## 1. Qwen3-Embedding series (official)

### 1.1 Intended tasks

Qwen positions the series as text embedding and ranking models for **text retrieval, code retrieval, text classification, text clustering, and bitext mining**. Not LLM routing. ([https://huggingface.co/Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B), [https://github.com/QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding), [https://arxiv.org/abs/2506.05176](https://arxiv.org/abs/2506.05176))

Paper abstract: SOTA on MTEB multilingual embedding plus retrieval tasks including **code retrieval, cross-lingual retrieval, and multilingual retrieval**. Apache 2.0. Sizes **0.6B / 4B / 8B** for both embedding and reranking. ([https://arxiv.org/html/2506.05176](https://arxiv.org/html/2506.05176))

Training data for embeddings is organized so models apply to **retrieval, STS, classification, and clustering**. Synthetic pre-training explicitly includes classification pairs. Supervised fine-tune data includes **CodeSearchNet**. ([https://arxiv.org/html/2506.05176](https://arxiv.org/html/2506.05176) §§2, A.1, Table 6)

**Routing:** the Qwen3 Embedding paper, HF card, blog, and GitHub README do **not** evaluate LLM model routing. Classification on MTEB ≠ calibrated P(success) over an aiand catalog.

### 1.2 Dims, context, architecture

| Model | Params | Layers | Sequence length (Qwen) | Native dim | MRL | Instruction-aware |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Qwen3-Embedding-0.6B | 0.6B | 28 | 32K | 1024 | yes | yes |
| Qwen3-Embedding-4B | 4B | 36 | 32K | 2560 | yes | yes |
| Qwen3-Embedding-8B | 8B | 36 | 32K | 4096 | yes | yes |

Sources: HF card, GitHub README, paper Table 1. ([https://huggingface.co/Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B), [https://github.com/QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding), [https://arxiv.org/html/2506.05176](https://arxiv.org/html/2506.05176))

**8B specifics (HF card):**

- Model type: text embedding
- Languages: 100+, including programming languages
- Context length: **32k**
- Embedding dimension: **up to 4096**; user-defined output dims **32 to 4096** (MRL)
- Pooling: last-token / `[EOS]` hidden state, then L2 normalize
- Instruction format: `Instruct: {task}\nQuery:{query}` on the query side; documents uninstructed. Instruct typically +1–5% vs no instruct; write instruct in English.

Official blog repeats the same table and MRL / instruction notes. ([https://qwenlm.github.io/blog/qwen3-embedding/](https://qwenlm.github.io/blog/qwen3-embedding/))

**Nebius catalog discrepancy:** Token Factory lists Qwen3-Embedding-8B context window as **41K tokens**, type `embedding`, id `Qwen/Qwen3-Embedding-8B`. Qwen’s own card/paper say **32k**. Do not silently reconcile; treat 32k as the model limit unless Nebius documents a different tokenizer/window. ([https://tokenfactory.nebius.com/model-catalog.md](https://tokenfactory.nebius.com/model-catalog.md))

### 1.3 Classification and code retrieval (published numbers)

MTEB Multilingual, 8B (paper Table 2 / HF card, leaderboard snapshot ~June 2025):

- Mean (task) **70.58**, mean (type) **61.69**
- Classification **74.00**, clustering **57.65**, retrieval **70.88**, STS **81.08**

MTEB English v2, 8B: mean (task) **75.22**; classification **90.43**.

MTEB Code: **0.6B = 75.41**, **4B = 80.06**, **8B = 80.68** (beats Gemini Embedding 74.66 on that table). ([https://arxiv.org/html/2506.05176](https://arxiv.org/html/2506.05176) Tables 2–3)

Classification + code retrieval are the closest official downstream tasks to “embed a coding-agent conversation and use the vector as a feature.” They are still retrieval/classification benchmarks, not routers.

### 1.4 Latency — no &lt;10ms claim

HF card points to blog/GitHub for “hardware requirements and inference performance.” Neither the paper, HF card, GitHub README, nor official blog publishes a p50 &lt;10ms for 8B embed. ([https://huggingface.co/Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B), [https://github.com/QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding), [https://arxiv.org/html/2506.05176](https://arxiv.org/html/2506.05176))

Official usage paths are Sentence-Transformers, Transformers, vLLM `task="embed"`, and Hugging Face TEI (GPU or CPU Docker). Those are batch/server embedders, not a &lt;10ms in-process hop. ([https://huggingface.co/Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B))

**Therefore:** keep the ticket assumption — online 8B embed does **not** fit ~&lt;10ms until measured. Nebius marketing “sub-second” (if encountered) is not &lt;10ms and is not cited here as a Token Factory docs fact.

---

## 2. Nebius Token Factory (official)

Index: [https://docs.tokenfactory.nebius.com/llms.txt](https://docs.tokenfactory.nebius.com/llms.txt)

### 2.1 Model id for prototype

Public catalog row:

> Qwen3-Embedding-8B | Qwen | embedding | 8 | 41 | eu-north1 | `Qwen/Qwen3-Embedding-8B`: input_price_per_million_tokens=**0.01**, output_price_per_million_tokens=**0**

([https://tokenfactory.nebius.com/model-catalog.md](https://tokenfactory.nebius.com/model-catalog.md))

JSON `/api/public/models_info` is the authoritative machine-readable catalog; the Markdown view is for reading. Same page.

`GET /v1/models` lists available models (OpenAI-compatible). ([https://docs.tokenfactory.nebius.com/api-reference/models/list-models.md](https://docs.tokenfactory.nebius.com/api-reference/models/list-models.md))

### 2.2 Embeddings API shape

OpenAI-compatible inference. Base URL `https://api.tokenfactory.nebius.com/v1/`. Auth: `Authorization: Bearer $NEBIUS_API_KEY`. ([https://docs.tokenfactory.nebius.com/api-reference/introduction.md](https://docs.tokenfactory.nebius.com/api-reference/introduction.md))

**Example** (`POST /v1/embeddings`) uses `BAAI/bge-en-icl` as the documented sample model, not Qwen3. Same wire shape applies; swap `model`. ([https://docs.tokenfactory.nebius.com/api-reference/examples/create-embeddings.md](https://docs.tokenfactory.nebius.com/api-reference/examples/create-embeddings.md))

```python
from openai import OpenAI
client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ["NEBIUS_API_KEY"],
)
client.embeddings.create(
    model="BAAI/bge-en-icl",  # prototype: Qwen/Qwen3-Embedding-8B
    input="Wake up, Neo...",
    encoding_format="float",
)
```

cURL: `POST https://api.tokenfactory.nebius.com/v1/embeddings` with JSON `{model, input, encoding_format}`.

Example response: `{object: "list", data: [{object: "embedding", embedding: [...floats...], index: 0}], model, usage: {prompt_tokens, total_tokens}}`. Sample notes **1536 floats** for `BAAI/bge-en-icl`. Qwen3-Embedding-8B native dim is **4096** unless `dimensions` is set.

**OpenAPI request (`EmbeddingRequest`)** — required: `model`, `input`. Optional: `encoding_format` (`float` | `base64`, default float), `user`, `service_tier` (`auto` | `default` | `flex` | …), **`dimensions`** (integer; examples **4096**, **8192**). `input` may be string, token ids, or batches thereof. ([https://docs.tokenfactory.nebius.com/api-reference/inference/create-embeddings.md](https://docs.tokenfactory.nebius.com/api-reference/inference/create-embeddings.md))

`dimensions` on Token Factory aligns with Qwen MRL (truncate toward 32–4096). Do not pass 8192 for Qwen3-Embedding-8B; that example is schema-generic.

LangChain Token Factory docs default embeddings to `BAAI/bge-en-icl`, confirming embeddings are a first-class Token Factory surface, not chat-only. ([https://docs.tokenfactory.nebius.com/integrations/frameworks/langchain](https://docs.tokenfactory.nebius.com/integrations/frameworks/langchain))

**No Token Factory doc in llms.txt claims p50 &lt;10ms for Qwen3-Embedding-8B.**

### 2.3 Production must not hard-require Nebius

Qwen3-Embedding-8B weights are Apache 2.0 on Hugging Face / ModelScope. Prototype can call Token Factory; production can run local TEI/vLLM/sentence-transformers or any other OpenAI-compatible embed API. ([https://huggingface.co/Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B), [https://qwenlm.github.io/blog/qwen3-embedding/](https://qwenlm.github.io/blog/qwen3-embedding/))

---

## 3. aiand has no embedding catalog

RAG cookbook: Approach A = stuff corpus into a chat model; Approach B = **embed locally** with `sentence-transformers` (`BAAI/bge-small-en-v1.5`); scaling note: “if running embeddings locally isn’t a fit, call **any external embeddings API**.” No aiand embed model id. ([https://docs.aiand.com/cookbook/rag/](https://docs.aiand.com/cookbook/rag/))

LlamaIndex integration: “Bring your own embeddings — **ai& doesn't expose an embeddings endpoint**.” ([https://docs.aiand.com/integrations/llamaindex/](https://docs.aiand.com/integrations/llamaindex/))

Model catalog is chat/completion models (`GET /v1/models`); no embedding rows. ([https://docs.aiand.com/models/catalog/](https://docs.aiand.com/models/catalog/))

**Implication:** a production trained-router spec that requires an aiand-hosted embed would invent a product surface aiand does not document. Training-time embed must stay optional and provider-pluggable.

---

## 4. Published embedding-based routers

These papers support **using query (and sometimes model) embeddings as router features**. None use Qwen3-Embedding. None require an 8B online hop.

### 4.1 RouteLLM (Ong et al., 2024)

[https://arxiv.org/abs/2406.18665](https://arxiv.org/abs/2406.18665) / [HTML](https://arxiv.org/html/2406.18665v4)

Learns routers that pick strong vs weak LLM from preference data.

- **Matrix factorization** and **similarity-weighted ranking:** query embedded with OpenAI **`text-embedding-3-small`**. MF scores via bilinear model+query embeddings (Hadamard + projection).
- **BERT classifier:** fine-tunes BERT_BASE on the query text (CLS → logistic). No frozen giant embed at serve.
- **Causal LLM router:** full FT of a small causal LM.

Table 7 overhead (Chatbot Arena sample; embedding cost included where routers need it): MF **155 req/s**, BERT **70 req/s**, causal LLM **42 req/s**, SW ranking **2.9 req/s**. That is still far from a documented &lt;10ms p50 for an **8B** embedder; MF speed assumes embeddings already available or a small commercial embed API, not Qwen3-8B.

**Support for training features:** yes — frozen query embeddings are first-class training (and inference) features for MF / SW ranking.

### 4.2 EmbedLLM (Zhuang et al., ICLR 2025)

[https://arxiv.org/abs/2410.02223](https://arxiv.org/abs/2410.02223) (ICLR 2025 PDF: [https://proceedings.iclr.cc/paper_files/paper/2025/file/bf5e4b85d203481d6e37bd32d9600162-Paper-Conference.pdf](https://proceedings.iclr.cc/paper_files/paper/2025/file/bf5e4b85d203481d6e37bd32d9600162-Paper-Conference.pdf))

Learns **compact embeddings of LLMs**, plus query embeddings, then a linear decoder predicts correctness → routing.

- Questions pre-embedded with sentence-transformer **`all-mpnet-base-v2`**, then projected.
- Router: Hadamard product of model embed × query embed → linear classifier. Multi-candidate P(correct)-style scores.
- Latency quoted: **3.80 s / 3000 questions** on A100 ≈ **~1.3 ms / query for the router head**, explicitly compared to RouteLLM’s causal LLM router. That figure is **not** embedding generation time.

**Support for training features:** yes — query vectors + learned model vectors are the training representation. The published query embedder is a small ST model, not 8B.

### 4.3 GraphRouter (Feng et al., 2024)

[https://arxiv.org/abs/2410.03834](https://arxiv.org/abs/2410.03834)

Heterogeneous graph: task / query / LLM nodes; route = edge prediction.

- Query and task text initialized with a moderate PLM (**BERT**-style mean pooling). LLM nodes from prompted capability+cost descriptions, same PLM.
- GNN then predicts performance/cost.

**Support for training features:** yes — query embeddings initialize graph nodes. Live hop still needs whatever PLM produced those features unless distilled.

### 4.4 HybridLLM (Ding et al., ICLR 2024)

[https://arxiv.org/abs/2404.14618](https://arxiv.org/abs/2404.14618)

Binary small-vs-large router: **DeBERTa-v3-large** (BERT-style encoder) predicts an ease score; threshold routes. Single forward pass; authors treat router cost as negligible vs autoregressive LLM decode. **No separate frozen embedding model.**

**Support for “embeddings as features”:** weak / adjacent. It is a tiny encoder classifier on raw text — the features-only / tiny-head alternative, not a frozen 8B vector pipeline.

### 4.5 LLMRouterBench (ACL Findings 2026)

[https://aclanthology.org/2026.findings-acl.1881.pdf](https://aclanthology.org/2026.findings-acl.1881.pdf)

Unified re-eval of EmbedLLM, GraphRouter, Avengers, RouteLLM, HybridLLM, etc.

> “Embedding models have little influence on routing performance.”

Table 6 (performance-oriented, embedding-dependent methods):

| Embedder | GraphRouter | EmbedLLM | Avengers |
| --- | ---: | ---: | ---: |
| nli-bert-base | 69.60 | 70.55 | 70.43 |
| all-MiniLM-L6-v2 (22.7M) | 68.05 | 70.95 | 71.03 |
| gte-Qwen2-7B-instruct | 70.29 | 71.24 | 71.94 |

Swapping a 7B Qwen2 embedder for MiniLM does **not** move routing accuracy much. Authors: embedding quality is likely not the bottleneck; mechanism + recall of rare specialists matter more.

Avengers: **clustering-based** routing using embeddings, **no neural training**, still competitive with EmbedLLM/GraphRouter. That is an offline-embed use (cluster complexity / domain), not an 8B live hop.

**Implication for 8B:** published evidence does **not** say Qwen3-Embedding-8B will beat MiniLM or Qwen3-Embedding-0.6B as a routing feature. Try 8B if cheap offline; also try 0.6B / tiny ST. Do not bet the recipe on 8B quality.

### 4.6 Pioneer (competitor docs — not an embedding claim)

Pioneer documents a trained coding router (complexity class → calibrated P(success) → cheapest above bar) but **does not document** whether the classifier uses embeddings. ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md); see repo `.scratch/competitor-router-research.md`). Do not infer Pioneer internals.

---

## 5. Training-time vs live hop

| Pattern | Train | Live `&lt;10ms` hop | Fits aiand constraints? |
| --- | --- | --- | --- |
| A. Frozen 8B embed → tiny head | 8B vectors + labels | **Needs 8B (or same) embed every request** | **No** (online 8B out) |
| B. Offline 8B (or 0.6B) embed → distill into tiny text/feature student | Embed + teacher labels offline | Student only (features / tiny BERT) | **Yes** if ablation wins |
| C. Offline embed for clustering / pseudo-bins (Avengers-style), student is features-only | Embed offline | No embed | **Yes** |
| D. Features-only (phase, tokens, tools, message stats, …) | No embed | No embed | **Yes** (default until B/C win) |
| E. Tiny local embed (MiniLM / Qwen3-0.6B) at train **and** serve | Small embed | Small embed, **only if measured &lt;10ms** | Maybe later; map still unspecified |

MRL (dims 32–4096) helps B/C/E: store/train on 64–256-d prefixes instead of 4096-d. ([https://huggingface.co/Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B))

Instruction-aware queries: if used, pin one English instruct string for “coding-agent routing / complexity” and keep it identical at train and any future serve embed.

---

## 6. What this does *not* prove

- That Qwen3-Embedding-8B improves **calibrated P(success)** on aiand coding-agent logs. No such experiment exists in the cited sources.
- That 8B beats 0.6B or MiniLM for routing. LLMRouterBench suggests it may not.
- That Token Factory p50 is &lt;10ms. Not documented.
- That production aiand will host embeddings. Official docs say the opposite.

---

## 7. Practical prototype note (not a production requirement)

If running the ablation:

1. Features-only baseline scorer.
2. Same labels + Qwen3 vectors (start **0.6B local** or Nebius **`Qwen/Qwen3-Embedding-8B`** with `dimensions` ≤ 256). Instruct string fixed. Batch offline only.
3. Keep embeddings if validation calibration / promotion-gate metrics beat (1) by enough to justify the extra pipeline. Else drop.

Provider seam: OpenAI-compatible `embeddings.create`; `model` and `base_url` configurable. Default production: unset / unused.

---

## Sources

### Qwen (first party)

- [https://arxiv.org/abs/2506.05176](https://arxiv.org/abs/2506.05176) — Zhang et al., *Qwen3 Embedding: Advancing Text Embedding and Reranking Through Foundation Models*
- [https://arxiv.org/html/2506.05176](https://arxiv.org/html/2506.05176) — HTML full text (tables, architecture, MTEB Code)
- [https://huggingface.co/Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B) — model card
- [https://github.com/QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding) — official repo / README
- [https://qwenlm.github.io/blog/qwen3-embedding/](https://qwenlm.github.io/blog/qwen3-embedding/) — Qwen blog

### Nebius Token Factory (first party)

- [https://docs.tokenfactory.nebius.com/llms.txt](https://docs.tokenfactory.nebius.com/llms.txt)
- [https://tokenfactory.nebius.com/model-catalog.md](https://tokenfactory.nebius.com/model-catalog.md)
- [https://docs.tokenfactory.nebius.com/api-reference/introduction.md](https://docs.tokenfactory.nebius.com/api-reference/introduction.md)
- [https://docs.tokenfactory.nebius.com/api-reference/examples/create-embeddings.md](https://docs.tokenfactory.nebius.com/api-reference/examples/create-embeddings.md)
- [https://docs.tokenfactory.nebius.com/api-reference/inference/create-embeddings.md](https://docs.tokenfactory.nebius.com/api-reference/inference/create-embeddings.md)
- [https://docs.tokenfactory.nebius.com/api-reference/models/list-models.md](https://docs.tokenfactory.nebius.com/api-reference/models/list-models.md)
- [https://docs.tokenfactory.nebius.com/integrations/frameworks/langchain](https://docs.tokenfactory.nebius.com/integrations/frameworks/langchain)

### aiand (first party)

- [https://docs.aiand.com/cookbook/rag/](https://docs.aiand.com/cookbook/rag/)
- [https://docs.aiand.com/integrations/llamaindex/](https://docs.aiand.com/integrations/llamaindex/)
- [https://docs.aiand.com/models/catalog/](https://docs.aiand.com/models/catalog/)

### Embedding-based / related router papers

- RouteLLM — [https://arxiv.org/abs/2406.18665](https://arxiv.org/abs/2406.18665)
- EmbedLLM — [https://arxiv.org/abs/2410.02223](https://arxiv.org/abs/2410.02223); ICLR 2025 PDF above
- GraphRouter — [https://arxiv.org/abs/2410.03834](https://arxiv.org/abs/2410.03834)
- HybridLLM — [https://arxiv.org/abs/2404.14618](https://arxiv.org/abs/2404.14618)
- LLMRouterBench — [https://aclanthology.org/2026.findings-acl.1881.pdf](https://aclanthology.org/2026.findings-acl.1881.pdf)
