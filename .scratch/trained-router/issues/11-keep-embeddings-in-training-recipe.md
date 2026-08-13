# Keep embeddings in the training recipe?

Type: grilling
Status: resolved
Blocked by: 05
Part of: [Production trained coding router](../map.md)

## Question

After the embedding research lands: does the **proposal** keep a training-time embed (prototype: Nebius `Qwen/Qwen3-Embedding-8B`) or go **features-only**?

Not forcing embeddings. Production spec must not hard-require Nebius either way. Only keep them if they help enough to justify the extra pipeline.

HITL — do not resolve without the human.

## Answer

**Proposal keeps an optional embed ablation. Features-only is the default recipe and a valid ship.**

Not required. No Nebius hard-require. No **live embed** ([Tiny local embed on the live hop?](12-tiny-local-embed-on-live-hop.md)).

**Ablation:** same labels + offline-cached query vectors as extra student **train** features vs features-only student. Named embedder: **Qwen3-Embedding-0.6B** local or **8B MRL `dimensions` ≤ 256**. Prototype may also call Nebius `Qwen/Qwen3-Embedding-8B`. Production: OpenAI-compatible / self-host; **unset until the ablation wins**. One pinned English instruct. MiniLM allowed as a substitute, not a second required run. Avengers clustering is not a staffed ablation.

**Keep vectors only if** the held-out **success gold** slice shows the embed student with **strictly better Brier** (not a wash) **and ECE not worse**. Never silver. Dual ECE still reported; [Promotion gate numeric bars](08-promotion-gate-numeric-bars.md) (trained vs rules) is unchanged. Wash → drop embeddings.

**If the ablation wins:** distill into a features-only deployed student. Corollary of never-a-live-embed — do not serve the embed-student as-is.

Rejected: required training embed; features-only freeze with no ablation in the proposal; full 4096-d 8B as the named try; mini promotion-gate between students; clustering-only / dual ablations.

## Comments

- [Qwen3-Embedding-8B as optional training features](05-qwen3-embedding-training-features.md) is resolved. Research rec to grill against: keep **features-only as the default**; try training-time Qwen3 vectors as an **optional ablation** (batch offline; 0.6B or MRL ≤256-d is enough to test; don’t assume 8B wins). [note](../research/qwen3-embedding.md)
- Grill Q1 → B: optional ablation in the proposal; features-only remains the default recipe and a valid ship.
- Round 2 (this session): use-pattern / prototype embedder / spec vs required-ablation / win bar. Live embed already out ([Tiny local embed on the live hop?](12-tiny-local-embed-on-live-hop.md)).
- Grill Q2–Q4 all recs (Brier+ECE bar on success gold; Qwen3 0.6B / MRL ≤256; train features, live hop left to 12). [Tiny local embed on the live hop?](12-tiny-local-embed-on-live-hop.md) closed mid-session → **never a live embed**, so win ⇒ distill into features-only serve.
- Later session confirmed Q2–Q5 recs: distill+clusters *allowed*, 0.6B/MRL first, ablation not required for go/no-go, win bar = promotion-gate vs features-only. Recorded Answer already froze **unstaffed clustering** and **Brier+ECE (not a mini-gate)**. Left as written unless amended.
