# Task 2 re-review: Scorer serve lift

Base `0911e86` → head `a2adc15` (`436a8bb` + weight-length fix). Verdict against `.scratch/scorer-pioneer-lift/task-2-scorer-brief.md`, the follow-up `.scratch/scorer-pioneer-lift/task-2-fix-brief.md`, and spec stories 5–9, 29–31, 35, 46.

### Spec Compliance

**Met.** Relative to `0911e86..a2adc15`, serve-side Rec A matches the task brief and binding constraints: complexity bin from request-observable features (`featurize_observable` + `predict_complexity_bin`), optional `hint_bin` not required at serve (`None` → predicted bin), per-model intercepts (missing → 0) then `w·x` then post-hoc calibrator, P-spread possible under identity Platt, old `p_success` / matching-length weights+platt paths preserved, effort knobs unchanged with no `xhigh`, scorer-down left to `apply_trained_path` without invented confidence, `not_spec_floors` unread-for-write, no GBDT/live embed, owned files only, tests stay on public scorer behavior.

The previous Important is closed in this range: `score_eligible` rejects `len(w) != len(x)` before `_dot` and falls back to that id’s `p_success` or omits the id. No fake P(success).

### Strengths

- Correct split between observable bin head (`src/aiand_router/scorer.py:59-68`, `:89-101`) and full `featurize` with predicted-bin one-hots (`:71-86`, `:138`) — scoring bin weights no longer share the P(success) vector.
- Intercept path is the minimal formula the brief asked for: `sigmoid(a * (ic + w·x) + b)` at `:149-151`, with `_calibrator_ab` (`:114-117`) accepting `calibrator` or `platt`.
- Compatibility for hop fixtures is real: table fallback (`:153-158`) and missing-intercept weights (`:140`, exercised in `tests/test_scorer.py:155-163`). Matching-length old weights+platt still score; short weights no longer pretend to.
- **Previous Important actually fixed.** `score_eligible` (`:145-148`) gates `if not w or len(w) != len(x)` before `_dot`. Table hit → that id’s `p_success`; miss → omit (same as missing weights). `tests/test_scorer.py:166-178` (`test_score_eligible_short_weights_use_table_p_not_truncated_dot`) locks the public seam: 9-dim `weights` plus table `0.42` yield `{m/a: 0.42}`, not truncated-dot ~1.0; sibling id without a table entry is omitted. Implementer reported red then green; this re-review did not re-run the suite.
- Contract tests cover the brief’s gaps: intercepts move P (`:70-91`), predicted bin when `hint_bin is None` (`:94-124`), P-spread ≥ 0.10 (`:127-142`), calibrator after intercepts (`:145-153`), `not_spec_floors` untouched (`:194-204`), knobs / no `xhigh` (`:207-220`), scorer-down (`:223-253`).
- Short, numpy-free diff confined to the two owned files.

### Issues

#### Critical

None.

#### Important

None. The prior stale-short-weights finding (`_dot` truncation mis-scoring 9-dim `weights` on 17-dim `x`) is addressed by `a2adc15`.

#### Minor

1. **`featurize(..., hint_bin=...)` name vs serve semantics.** At hop, the fourth argument is the *predicted* (or override) bin (`src/aiand_router/scorer.py:138`), not a train-only hint. Easy to misread next to `score_eligible(..., hint_bin=None)` (`:127`). Rename or document as `complexity_bin` / `bin_` at the public boundary.
2. **Bias term + intercepts both live in the schema.** Feature vector always includes bias `1.0` (`:80`), and intercepts add another constant (`:149-151`). Correct if Task 3 fits accordingly; the report’s “dim includes bias” note should explicitly say whether `w[0]` is fixed at 0 when intercepts are present, or Task 3 will double-count base rate.
3. **Layout / index assertions in unit tests.** `tests/test_scorer.py:6-14`, `:45-49`, `:59-61` lock feature indices. Allowed as public `featurize` contract for Task 3, but tighter than “P(success) / bin labels / pick inputs” only — fine if treated as the serve↔fit schema lock.
4. **`calibrator` with only one of `a`/`b` overrides `platt` entirely** (`src/aiand_router/scorer.py:116-117`). Incomplete alias objects default the missing coeff to identity (`1` or `0`) rather than merging with `platt`. Document for Task 3 or merge keys.
5. **`_dot` still truncates; only the P(success) caller length-checks.** `src/aiand_router/scorer.py:109-111` vs `:145`. `predict_complexity_bin` (`:101`) can still align a short `bin_weights` vector onto the 13-dim observable layout. Old artifacts typically omit `bin_weights` and fall back to `complexity_bin` (`:97-99`), so this is not the transitional P-table footgun. Task 3 should emit dim-13 bin heads; a length check there can wait for whole-branch review.

### Assessment

**Task quality: Approved**

Requirements are implemented and tested at the public scorer API. The Important weight-length footgun is fixed in-diff: wrong-length `weights` no longer silently mis-score, and the new test pins table fallback vs omit. Remaining items are Minors (naming, bias+intercept schema, test tightness, calibrator alias, residual `_dot` on the bin head). This task gate can close; defer Minors to whole-branch review.
