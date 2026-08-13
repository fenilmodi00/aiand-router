# Qwen3-Embedding-8B as optional training features

Type: research
Status: resolved
Blocked by: none
Part of: [Production trained coding router](../map.md)

## Question

Does **Qwen3-Embedding-8B** (model card / paper) and any **published embedding-based router** support using these vectors as **training features** for model routing?

Online 8B embed on every `router/auto` request is **out** unless a measured p50 still fits a ~&lt;10ms hop (assume it does not until proven). Prototype access is Nebius Token Factory `Qwen/Qwen3-Embedding-8B`; production spec must **not** hard-require Nebius.

Document: dims, context, intended tasks, any classification/routing use, Nebius API shape from **official** Token Factory docs, and whether training-time embeddings are worth trying vs features-only.

Findings land on branch `research/qwen3-embedding` as `.scratch/trained-router/research/qwen3-embedding.md`.

## Answer

**Try training-time embeddings as an optional ablation. Do not use 8B online. Do not hard-require Nebius. Keep features-only as the default until the ablation wins.**

Qwen3-Embedding-8B is 4096-d / 32k ctx, built for retrieval, classification, and code retrieval — not LLM routing. Published routers (RouteLLM MF, EmbedLLM, GraphRouter) do use query embeddings as train/serve features; LLMRouterBench finds embedder quality barely moves routing accuracy. No primary source shows p50 &lt;10ms for 8B, so online 8B stays out. Prototype may call Nebius `POST /v1/embeddings`; production can self-host Apache 2.0 weights (0.6B/4B/8B) or any external API.

Detail: [`.scratch/trained-router/research/qwen3-embedding.md`](../research/qwen3-embedding.md) on `research/qwen3-embedding` @ `b0ef675`.
