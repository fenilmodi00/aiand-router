# Scorer shape Rec A vs Rec B

Type: grilling
Status: resolved
Blocked by: none
Part of: [Production trained coding router](../map.md)

## Question

Which live-hop scorer does the spec freeze?

- **Rec A (research default):** feature model + per-survivor logistic/GBDT + Platt/temperature. No live embed or chat.
- **Rec B:** tiny bilinear / MIRT head on features (query latent from a tiny MLP, frozen model factors). **No live embed** — [Tiny local embed on the live hop?](12-tiny-local-embed-on-live-hop.md) closed MiniLM-class / 0.6B on the hop. Never 8B / BERT-base / DeBERTa-large online.

Chat-LLM-as-router and online 8B embed already fail the hop bar. Detail: [Scorer architectures under a 10ms hop](01-scorer-architectures-under-10ms.md).

HITL — do not resolve without the human.

## Answer

**Rec A only.** Spec freeze is the **Scorer**: in-process, features-only, gateway features already on the hop + predicted complexity bin + per-survivor logistic **or** GBDT (implementer/eval choice) + Platt/temperature. Score survivors only. Independent heads vs shared trunk + model-id is unpinned. Exact feature columns are training/eval, not a production freeze.

**Rec B is not a spec door** (bilinear / MIRT / feature→latent MLP as the shipped hop). Reopen only if Rec A fails the promotion gate — same pattern as [Tiny local embed on the live hop?](12-tiny-local-embed-on-live-hop.md). No live embed, no chat teacher.

Glossary: **Scorer**. Research: [Scorer architectures under a 10ms hop](01-scorer-architectures-under-10ms.md) · [note](../research/scorer-architectures.md)

## Comments

- [Tiny local embed on the live hop?](12-tiny-local-embed-on-live-hop.md) resolved: never a live embed. Rec B option 2 (MiniLM on the hop) is out; Rec B remains bilinear/MIRT **without** an embedder.
- [Keep embeddings in the training recipe?](11-keep-embeddings-in-training-recipe.md) resolved: optional offline vectors; if they win, distill into whichever head this ticket freezes. Does not pick Rec A vs Rec B.
- Grill Q1 → A: Rec A only; Rec B not a spec door (reopen only if Rec A fails promotion).
- Grill Q2–Q5 all recs: logistic or GBDT unpinned; head sharing unpinned; feature-column list envelope-only; glossary **Scorer**.
- [Student training target](14-student-training-target.md) resolved: Rec A (the frozen Scorer) trains P(success) with gold + query-only silver regularizer (unobserved only).
