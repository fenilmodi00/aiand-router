# Complexity bin taxonomy

Type: grilling
Status: resolved
Blocked by: 02
Part of: [Production trained coding router](../map.md)

## Question

What **discrete complexity bins** does the spec freeze (count, names, boundaries)?

Standing preference is explicit bins (e.g. trivial / standard / hard / frontier) plus per-model P(success). Bins become `reason_codes`. The pick still uses P(success) + cost, not the bin alone.

Wait for [Teacher labeling for multi-candidate success](02-teacher-labeling-multi-candidate.md): only bins a teacher can label reliably belong in the spec.

HITL — do not resolve without the human.

## Answer

Freeze **four query-only bins**: `trivial | standard | hard | frontier`. Canonical glossary term: **Complexity bin** (not “complexity class”).

| Bin | Boundary (messages + tool schemas + optional phase hint only) |
| --- | --- |
| `trivial` | One-shot lookup / rename / format / comment / docstring; no repo reasoning. |
| `standard` | Localized implement / fix / test / tool call with a clear spec; one area of the code. |
| `hard` | Multi-file, ambiguous spec, debug-after-fail, security review, cross-cutting plan. Cheap models often fail. |
| `frontier` | Catalog-ceiling or still-may-fail: novel algorithm, huge ambiguous repo, SWE-Verified-class, adversarial. Not a model id — K3 is only today’s ceiling. |

Label never uses “how many models would succeed” (that’s the measured matrix). Same **phase** can sit in different bins (`edit`+rename vs `edit`+lock-free paper). No fifth `debug_fail` bin.

**Bin does not pick.** Feature + `reason_codes` + train/eval stratum only. Threshold + max_regret stay **effort-only**; bin does not gate the eligible set.

**Bloom** (`bloom_level`) is optional on the **offline teacher row only** — not a live reason_code, not in Decision headers.

Rejected: 3-bin merge, Bloom-6 as live enum, binary easy/hard, bin-retuned threshold.

## Comments

- [Teacher labeling for multi-candidate success](02-teacher-labeling-multi-candidate.md) is resolved. Teacher can label bins query-only (RouterArena Bloom-style). Recipe uses `trivial|standard|hard|frontier` plus optional Bloom as examples only — this ticket still freezes names/boundaries. Prefer bins a cheap teacher can label reliably; empirical difficulty still needs a measured matrix. [note](../research/teacher-labeling.md)
- Grill: Q1–Q3 all take the recs (four bins + those boundaries; observational only; Bloom teacher-only).
