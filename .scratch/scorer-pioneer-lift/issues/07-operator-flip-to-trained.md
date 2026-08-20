# 07 — Operator flip to path=trained

**What to build:** After the replay gate passes, a manual operator switch `TRAINED_PATH=trained` so live hops use the trained router. No automatic flip. JSONL and headers still show path. This does not claim SWE-bench Verified promotion; the production Verified n≥300 gate stays a later staffed bar.

**Blocked by:** 05 — Holdout replay gate (only if the gate passes)

**Status:** needs-info

- [ ] Taken only when the replay gate passes
- [ ] Flip is a manual operator switch of `TRAINED_PATH=trained`
- [ ] No automatic flip
- [ ] JSONL and headers still show path
- [ ] Does not claim SWE-bench Verified promotion
- [ ] Production Verified n≥300 gate remains a later staffed bar

## Comments

Not taken (2026-08-14). Operator replay on `data/gold-verified.jsonl` **failed** (logistic and after the issue-06 GBDT lift). `apply_replay_gate` still never auto-flips (`path=shadow`). Manual `TRAINED_PATH=trained` already exists on the hop. Take this ticket only after a passing operator replay; it still must not claim SWE-bench Verified promotion.

Re-checked after diagnosing the post-GBDT fail (`gate-fail-diagnosis.md`): still **not taken**. Hard blockers — (1) train vs verified model-rate Spearman −0.6 → AUC≥0.65 needs verified leak or new gold; (2) rules≡always-cheapest on this holdout → `rules_cost_delta < 0` unreachable. Do not flip until operator replay is green.
