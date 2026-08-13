# Teacher model from aiand catalog

Type: grilling
Status: resolved
Blocked by: 02
Part of: [Production trained coding router](../map.md)

## Question

Which **aiand-deployed** chat model(s) are the spec’s default **teacher** for offline labels, and what is the labeling budget posture?

Credits exist. Teacher is not the live hop. Wait for [Teacher labeling for multi-candidate success](02-teacher-labeling-multi-candidate.md) so the choice matches the protocol (one teacher vs cheap-then-escalate teacher, JSON schema, etc.).

HITL — do not resolve without the human.

## Answer

**Cheap-then-escalate**, catalog-relative **policy + example pins**. Not one global teacher id. Not the live hop. Strict `json_schema`, temperature 0, cache like the gateway. Prices from `GET /v1/models` — do not assume Qwen is free.

**Exclusion:** teacher providers ∉ labs of **measured trio ∪ live fallback**. Today: `qwen`, `moonshotai`, `deepseek-ai`. K3 is not a teacher.

**Cheap teacher:** highest AA among remaining models with `output_per_1m ≤ $2`. Fail a `json_schema` ping → drop that id and rerun.

**Escalate teacher:** highest AA among remaining ≠ cheap teacher. Fallback `zai-org/glm-5.1` if 5.2 is missing.

| Catalog | Cheap teacher | Escalate teacher |
| --- | --- | --- |
| This org (Motif present) | `motif-technologies/motif-3` | `zai-org/glm-5.2` |
| Public catalog, no Motif | `google/gemma-4-31b-it` | `zai-org/glm-5.2` |

**Escalate when:** bin `frontier` always; `hard` only if `label_confidence < 0.60` or AA-disagree (`|p_success − aa_index/100| > 0.25` on any eligible measured-trio ∪ Flash). Soft-cap **≤25%** (keep all frontier; sample extra `hard`). Invalid cheap output: retry once → escalate teacher → else **unlabeled** (missing, not fake bins/silver).

If the teacher advertises `reasoning_effort`, send the minimum (`low` if present). Pairwise judge is not required in v1; if used later, it is the escalate teacher, not a third model.

**Budget:** this repo = teacher **smoke only** (~100 rows to exercise schema + escalate; do not eat the $15 3×5 cap). Spec = **few thousand** query-only rows. Gold-matrix $ stays [Gold matrix sampling](13-gold-matrix-sampling.md).

## Comments

- [Teacher labeling for multi-candidate success](02-teacher-labeling-multi-candidate.md) is resolved. Protocol supports a **single teacher** or **cheap-then-Pro** (Flash/Qwen first, escalate on low `label_confidence` / hard|frontier / silver vs AA disagreement). Strict `json_schema`; temperature 0; cache like the gateway. Prefer a teacher **outside** the measured trio (Qwen / Kimi Code / Pro) to limit family bias. Qwen is listed free to prototype. [note](../research/teacher-labeling.md)
- Grill round 1 (all recs): **C** policy + public-catalog example pins; **cheap-then-escalate**; **C** teacher id ∉ measured trio and ∉ Flash; **B** spec names a production teacher line (few thousand query-only rows, escalate ≤25% planning), this repo smokes only, gold-matrix $ stays ticket 13. Prices from `GET /v1/models` — do not assume Qwen is free.
- Grill round 2 (all recs): cheap picker **B** (highest AA with `output_per_1m ≤ $2`); exclusion **B** (providers of measured trio ∪ live fallback: `qwen`, `moonshotai`, `deepseek-ai`); escalate triggers **B** (always `frontier`; `hard` only if `label_confidence < 0.60` or AA-disagree `> 0.25` on trio∪Flash; soft-cap 25%); invalid output **A** (retry once, then escalate teacher; both fail → unlabeled). Example pins: Motif-3 → GLM 5.2 (this org); Gemma → GLM 5.2 (public, no Motif).
