### Spec Compliance

**Compliant** for this ticket. The one production change matches the live gap: `score_eligible` emits calibrated logistic P(success) only when a gold intercept exists; ids with silver weights and no intercept are omitted (or table-onboarded if they have gold `p_success`). Fit already wrote silver only on unobserved cells, gold intercepts, cal-slice Platt, and `not_spec_floors`; this diff locks that with tests and does not flip `TRAINED_PATH`, add GBDT, or put a teacher/embed on the hop.

| Requirement | Verdict |
|---|---|
| Silver only on unobserved cells; unlabeled ignored; never Platt/gate/threshold on silver | Met (locked by new fit tests; fit loop unchanged) |
| Logistic Rec A: gold intercepts → feature correction → cal-slice calibrator; no GBDT | Met (locked; no `gbdt` / threshold / max_regret in artifact) |
| Live P only for ids with success gold; silver cannot unstick an unseen catalog id | Met (`score_eligible` intercept allowlist + omit test) |
| Cal-only ids onboard via gold table, not silver logistic | Met |
| Rec A at serve: request features + predicted bin; `hint_bin` not required | Met (shadow hop test; live `pick_kwargs` has no `hint_bin`) |
| Artifact `not_spec_floors`; default path stays shadow; no operator flip | Met |
| No live embed, Rec B, Pioneer dashboard, K3 gold, replay gate (05) | Met (not in this diff) |
| Unit tests: FakeProvider, never spend; no sklearn internals | Met (`_fit_platt` is the repo GD helper, not sklearn) |
| Motif cheap → GLM escalate; parse-fail always escalates; quality cap; unlabeled; teacher `max_completion_tokens` + min `reasoning_effort`; opt-in; cache-first; `BUDGET_LIMIT_USD` default 15 | ⚠️ Cannot verify from this diff (unchanged teacher/CLI). Controller: existing `test_train.py` seams — `test_train_refuses_without_opt_in`, `test_parse_fail_still_escalates_after_quality_cap`, `test_teacher_writes_silver_and_uses_motif_then_cache`, `test_teacher_call_sends_min_reasoning_effort_for_glm`; default `BUDGET_LIMIT_USD` is `"15"` in `train.py` / `app.py`. |

Report concerns 1–3 are accurate descriptions, not spec misses: cal-only live P is the gold table (issue 03); silver may move Platt `a`,`b` via weights while Platt **y** stays cal-gold; train JSONL may carry `hint_bin` while serve predicts the bin.

### Strengths

- Serve treats a present `intercepts` map as the allowlist for calibrated logistic P. Missing ids skip `_sigmoid`; `pick_cheapest_above_bar` only considers ids in `p_success`, so omit is “rules-only,” not P=0.
- Cal-only gold still onboards through the table (`i in table` before `continue`), matching issue 03 rather than inventing silver logistic.
- TDD is pointed: RED was `ic=0` → `P=0.5` for a silver-only weight row; GREEN is the omit. Fit tests pin intercepts = gold logit, unlabeled rows do not move weights, Platt reconstruction y is cal-gold, artifact stays `not_spec_floors`.
- Shadow hop loads Rec A and predicts `frontier` from phase/tools/tokens with no `hint_bin` header. Scope stayed inside scorer + tests.

### Issues

#### Critical

None.

#### Important

None.

#### Minor

- The omit is `if intercepts and i not in intercepts`. A weights-only artifact with an empty/missing `intercepts` map still scores logistic at `ic=0`. Fitted Rec A always writes intercepts with weights, so this is legacy-compat, not a fitted-path hole.
- `test_fit_then_score_omits_ids_with_no_success_gold` would already pass without the four-line change: `fit_scorer` skips `mid not in gold_ids`, so silver-only ids never get weights. The dedicated `test_score_eligible_omits_ids_with_silver_weights_but_no_gold_intercept` is the test that actually hits the new branch.
- The hop test locks path=`shadow` and predicted bin; it does not assert `x-router-trained-would` omits a silver-only catalog id. That contract lives on `score_eligible` only.

### Assessment

**Task quality:** Approved
**Reasoning:** Live scoring now refuses calibrated logistic P unless a gold intercept exists, which is the ticket’s serve invariant; silver regularizer, cal-only Platt, `not_spec_floors`, and shadow Rec A are locked without GBDT or a path flip. Residual notes are defense-in-depth and test coverage, not spec failures.
