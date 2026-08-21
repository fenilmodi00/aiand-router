# Issues

## 2026-08-21 A4 turn-aware cache pricing
- [watch] Single-turn medium-effort edit/codegen picks flipped Pro -> Flash on the real catalog (margin 0.0002). Intended per plan (ranking consumes turn-aware estimates), but if edit quality regresses, revisit the -0.05 cost weight in pioneer_score before reverting cache pricing.
- [contract] `est_cache_aware` is absent from JSONL rows for client-pinned hops (no stamp_baseline call). Phase H presence audit must tolerate missing field on pinned rows.
- [scope] Shadow/trained ranking (scorer.pick_cheapest_above_bar) still ranks by legacy cached-preferred Model.unit_cost; only rules-path ranking is turn-aware. Unifying later means threading multi_turn through scorer.py (out of A4 scope).

## 2026-08-21 FIX collision refusal
- Commit 80f4128: per-primary-source survival restored (regressed in 76e92e9 per worker comment).
- ACCEPTED GAP: --queries pointing outside data/ without sibling split_manifest.json -> warn-only disjointness. All paid tranches MUST use data/-colocated query files.
- train.py manifest validation still duplicates pool.py validate_split_manifest (~40 lines) - candidate consolidation, low priority.

