# Scorer architectures under a 10ms hop

Type: research
Status: resolved
Blocked by: none
Part of: [Production trained coding router](../map.md)

## Question

Which **published** router or classifier architectures can emit **calibrated per-candidate P(success)** for coding (or general LLM routing) while serving **in-process at about &lt;10ms** added latency?

Constraints for this effort: hard constraints still build the eligible set; live hop must not call an aiand chat model; an 8B remote embed is not the default hop; embeddings may be training-only.

What is documented vs inferred? Which shapes fail the latency bar (chat-LLM-as-router, online 8B embed)? Recommend one or two shapes compatible with those constraints (feature model, tiny head, distilled embed, …), citing primary sources only.

Findings land on branch `research/scorer-architectures` as `.scratch/trained-router/research/scorer-architectures.md`.

## Answer

Calibrated per-candidate P(success) at ~&lt;10ms is a **feature / tiny-head** scorer, not a chat LLM or online 8B embed. Pioneer/Azure document the product hop, not internals. HybridLLM DeBERTa ~36ms, DistilBERT-on-CPU, RouterArena MIRT-BERT ~14ms, and remote embed ranking fail a hard 10ms bar as published. Sigmoid ≠ calibrated; Platt/temperature are the documented post-hoc maps.

**Rec A (default):** feature model + per-survivor logistic/GBDT + Platt/temperature; embeddings teacher-only at train time. **Rec B:** tiny bilinear/MIRT; live MiniLM-class only if measured p50 &lt;10ms.

Detail: [`.scratch/trained-router/research/scorer-architectures.md`](../research/scorer-architectures.md) on `research/scorer-architectures` @ `bb02699`. Shape freeze is [Scorer shape Rec A vs Rec B](15-scorer-shape-rec-a-vs-b.md).
