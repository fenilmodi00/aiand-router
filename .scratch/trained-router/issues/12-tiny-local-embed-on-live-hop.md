# Tiny local embed on the live hop?

Type: grilling
Status: resolved
Blocked by: 01, 11
Part of: [Production trained coding router](../map.md)

## Question

If training keeps embeddings at all, should the **live hop** ever use a **tiny local** embed (e.g. Qwen3-Embedding-0.6B / MRL ≤256-d, distilled), or stay **features-only** at serve time?

[Qwen3-Embedding-8B as optional training features](05-qwen3-embedding-training-features.md) already ruled out online 8B and a Nebius hard-require. Wait for [Scorer architectures under a 10ms hop](01-scorer-architectures-under-10ms.md) (can a tiny embed fit ~&lt;10ms?) and [Keep embeddings in the training recipe?](11-keep-embeddings-in-training-recipe.md).

HITL — do not resolve without the human.

## Answer

**Never a live embed.** The trained hop is **features-only**: gateway features plus a tiny head (logistic / GBDT / bilinear / MIRT query-latent MLP). MiniLM-class, Qwen3-0.6B, and any sentence-transformer stay off the critical path even if Rec B wins later. A feature→latent MLP is not a live embed.

**Live embed** = embedding-model forward on request text at serve. **Training embed** may still exist offline ([Keep embeddings in the training recipe?](11-keep-embeddings-in-training-recipe.md)). Re-open only if the destination is redrawn after features-only fails promotion — not a spec door.

## Comments

- [Scorer architectures under a 10ms hop](01-scorer-architectures-under-10ms.md) is resolved. Rec A has **no live embed**. Rec B allows MiniLM-class only if measured p50 still &lt;10ms; DeBERTa-large (~36ms) / BERT-base / 8B stay out. Still wait on [Keep embeddings in the training recipe?](11-keep-embeddings-in-training-recipe.md). [note](../research/scorer-architectures.md)
- [Keep embeddings in the training recipe?](11-keep-embeddings-in-training-recipe.md) is resolved: optional offline ablation; win ⇒ distill into this features-only hop.
