### Spec Compliance

**Pass.** The diff is the allowed Rec A lift after a failed replay gate: optional `--gbdt` fits one per-id stump GBDT plus the existing cal-gold Platt, logistic stays the default, Rec B / live embed stay closed, the artifact still stamps `not_spec_floors`, and serve is unchanged (default `TRAINED_PATH` still shadows; `apply_replay_gate` is not touched and still never auto-flips). Clearing the numeric bars is not required; operator evidence shows the re-run still fails and stays `path=shadow`.

Issue 06 checklist vs this change:

| Requirement | Verdict |
|---|---|
| Taken only when the replay gate fails | Met in process (run 1 Brier skill −0.317). CLI does not encode the trigger; operator-owned, as specified. |
| One GBDT + post-hoc calibrator, not a zoo, not also larger n | Met. `fit_scorer(..., gbdt=False)` still trains logistic weights; `--gbdt` trains `gbdt` heads instead, never both populated. No second model class, no Rec B. |
| Rec B closed | Met. No bilinear / MIRT / embed keys; tests assert absence. |
| Live embed closed | Met. Serve path is still `featurize` + trees/Platt. No embedding forward in the hop. |
| Replay re-run after the refit | Met as operator work (`operator-replay-run.md` run 2), not a code change. Still `replay_gate_pass=false`, `path=shadow`, `not_spec_floors=true`. |
| Serve stays shadow | Met. Diff does not change `parse_trained_path` / `TRAINED_PATH`. Hop test asserts `x-router-path == shadow` and rules still dispatched. |
| Artifact stays `not_spec_floors` | Met. Fit still hard-writes `True`; GBDT tests assert it. |

Parent-spec constraints that bind this ticket:

- Logistic Rec A first; GBDT only after Brier skill ≤ 0 (or P-spread too small). Operator ran logistic, Brier skill −0.317, then one GBDT. Code default remains logistic.
- Student target: gold where present + silver on unobserved cells only. Unchanged `by_model_*` construction; GBDT consumes that same `xs`/`ys`. Intercept still from gold marginals (`gold_ys = by_model_y[mid][:n_train]`).
- Never calibrate / gate / threshold-tune on silver. Platt `ys_cal` are cal-gold `success` only. No threshold/max_regret written into the artifact.
- Calibrator on the cal slice only. GBDT `zs_cal` from `_gbdt_z(head, x)` on `cal_gold`.
- No Pioneer dashboard, no K3 gold, no automatic `TRAINED_PATH=trained`, no Verified promotion claim.
- Tests: Train CLI + `FakeProvider`; fit writes `not_spec_floors`; no sklearn; no spend. Assertions are artifact/HTTP/JSONL, not estimator internals.

Issue 07 is correctly not in this diff (`apply_replay_gate` still forces `path=shadow`).

Report claims that hold up in code: `--gbdt`, 24 stdlib stumps, Platt reuse, serve prefers `gbdt` when present, gold-intercept omit still applies, logistic default. Report claims that are operator evidence (not this diff): run 1/2 numbers, clean sparse-400 / dense-100 split, Brier getting worse — consistent with `operator-replay-run.md`; not re-verified here.

### Strengths

- Exclusive head: `if gbdt: gbdt_heads[mid] = _fit_gbdt(...) else: weights[mid] = _fit_binary_intercept(...)`. One Rec A family, not a zoo.
- Serve prefers trees when `artifact["gbdt"]` is a non-empty dict, including when dummy logistic `weights` are also present. `test_score_eligible_uses_gbdt_when_present` proves that (zero weights would yield P=0.5 both ways; tools stump splits across 0.5).
- Gold-intercept omit and table fallback are copied onto the GBDT branch, so new ids without a fitted head still do not get a fake tree score.
- Platt stays the existing `_fit_platt` on cal-gold z; `test_fit_gbdt_platt_on_cal_gold_only` recomputes a,b from cal rows only (train all-success, cal all-fail, silver 1.0) so a silver/train leak would miss.
- Hop test `test_shadow_loads_gbdt_and_does_not_auto_flip` is the right operator observable: path stays shadow, live pick is rules (`cheap/ok`), `trained-would` is GBDT cheapest-above-bar (`mid/ok`) rather than the table’s `dear/ok`, `not_spec_floors` remains.
- Stdlib stumps (skip bias column `j=0`, lr=0.1, 24 trees) match “do not assert sklearn internals” and keep the hop JSON-serializable.
- `--gbdt` is opt-in `store_true`; existing fit tests and the default artifact shape are undisturbed.

### Issues

#### Critical

None.

#### Important

None.

#### Minor

1. **Duplicated `score_eligible` branch.** The GBDT path copies bin prediction, `featurize`, Platt, intercept-omit, and table fallback from the logistic path (~25 lines). Logistic is slightly more defensive (`if not w or len(w) != len(x)`); GBDT does `int(t["feature"])` and will KeyError on a malformed tree. Fine for this ticket; a later edit to omit/table logic can drift.

2. **Train imports a private scorer helper.** `from .scorer import ... _gbdt_z` so fit and serve share z. Small leak of `_` API; acceptable vs duplicating the eight-line walk.

3. **GBDT artifacts still write empty `weights: {}`.** Harmless because serve checks `gbdt` first and `load_scorer` already accepts `p_success`. Slightly noisy for operators grepping the file.

4. **`load_scorer` does not treat `gbdt` as a load key.** It still requires `p_success` or `weights`. Fit always writes `p_success`, so the operator artifact loads. A hand-built trees-only JSON would be rejected — not this ticket’s shape.

### Assessment

**Task quality:** Approved
**Reasoning:** The change is exactly the one allowed lift (stdlib GBDT + cal-slice Platt, logistic default, no Rec B, no issue-07 flip), with tests that pin artifact, serve-shadow, and “prefer trees over weights,” and with operator replay evidence that the re-run stayed shadow / `not_spec_floors`. Remaining notes are duplication and private-import nits, not spec gaps.
