# Whole-branch review: scorer-pioneer-lift issues 01–06

**Base:** `1e734c73c6ab835e139bb556271dbbd2f897636a`
**Head:** `cb7a9bff01bf9b548d8b539e7aaef0363d596203`
**Diff:** `.scratch/scorer-pioneer-lift/review-whole-issues-1e734c7..cb7a9bf.diff` (9 files, +2227/−51)
**Issue 07:** not taken (gate still fails). **Out of scope:** 7 `test_gateway.py` `x-router-reason` failures (`gateway-reason-dropped.md`).

---

### Spec Compliance (branch)

Issues 01–06 match the spec’s pipeline, not a Pioneer clone and not a production Verified promotion.

| Issue | Spec ask | What landed |
|---|---|---|
| 01 | Stratum pool (bin × phase family × tools); SWE-smith primary; BFCL ≤ 15%; gym/R2E extra; Verified/Lite/TB out; collision-filter; dump `resolved` unused as y | `train pool` writes that JSONL; `--eval` required; FAIL_TO_PASS / TB canary dropped; teacher/gold `--limit` uses the same sampler |
| 02 | Sparse gold = Flash + measured trio when eligible; no K3; unobserved stays missing; verified metadata overrides weak proxies; cache-first; opt-in; budget default 15 | `_gold_ids` / `_gold_label`; 429 and budget skip are unobserved; schema + `needs_tools` without `tool_calls` is fail; dump `resolved` never written |
| 03 | Dense/cal: every enabled id except K3; disjoint from sparse train; unused for train weights | `--dense --exclude`; `fit --gold/--cal` (or `dense: true` tags); intercepts/weights on train rows; Platt + new-id table on cal |
| 04 | Silver on unobserved cells only; logistic Rec A; predicted bin; no live P from silver-alone ids; `not_spec_floors`; shadow; no GBDT in this ticket | Omit in `score_eligible` when intercepts exist and id is missing; hop predicts bin without HTTP `hint_bin`; `--gbdt` absent until 06 |
| 05 | Offline holdout replay; rules/trained/oracle/always-Flash/always-strong + always-cheapest; bars operator-side; fail → shadow + `not_spec_floors`; unit tests must not hit production floors | `always_cheapest` policy; `replay_gate_pass` vs cheapest not only Flash; `apply_replay_gate` never auto-flips and never stamps Verified; toy fixture allowed to fail bars |
| 06 | If gate fails: one larger n **or** one GBDT + post-hoc calibrator; Rec B / live embed closed; re-run replay; stay shadow | Operator logistic fail (AUC 0.295, Brier skill −0.317) → `fit --gbdt` on sparse-400/dense-100; re-run still fail; no Rec B |

**Global constraints (held):**

- Default hop is shadow (`parse_trained_path` → `"shadow"`). `apply_replay_gate` sets `path=shadow` even when bars would pass. No `TRAINED_PATH=trained` flip in this range.
- Fit always writes `"not_spec_floors": True`. Gate report does too. No Verified / production-floor stamp.
- No Rec B, live embed, Pioneer dashboard, or savings-% field on the replay report.
- Silver is a regularizer on unobserved cells; Platt y is cal-gold `success`. Dump `resolved` is not y (pool omits it; gold ignores it).
- `BUDGET_LIMIT_USD` code default stays `"15"`. Pool is unpaid. Gold/replay/hop tests use FakeProvider / fixtures; they do not spend.

**Issue 07 correctly not taken.** Operator evidence (`operator-replay-run.md`): after GBDT, AUC 0.261, Brier skill −3.80, dual ECE 0.525, cost delta 0, trained = always-cheapest. Spec: failing any bar → stay shadow. Manual flip remains existing env; this branch does not add an auto-flip.

**Known out of scope:** 7 `test_gateway.py` `x-router-reason` failures. Pioneer-shaped trained contract is bin + calibrated P(success) + cheapest-above-bar, not Decision reason strings.

#### Findings

**Critical:** none.

**Important:** none that break the live hop or the gate contract. Operator footguns (missing `--eval` file, missing `--cal` path, overlapping `--gold`/`--cal`, empty `--exclude`) can poison a *future* fit; they do not flip serve. See triage.

**Minor (spec / test seams, not missing features):**

- Stratum mix is independent margins (bin + phase + tools scores), not joint cells with a floor. Spec story 28 is “not all trivial edits”; tests lock that, not a full factorial.
- `replay_gate_pass` compares trained vs always-cheapest **aggregate** `{success_rate, list_price_cost}`, not per-prompt pick identity. Spec bar is “policy is not identical to always-cheapest-eligible.”
- `gold_is_holdout` is still a constant `True`; the contract is CLI `--gold` as holdout, not a mix detector.
- Optional embed ablation (stories 32–34) and medium retune split (story 41) were not taken. Story 8 allows keeping ship knobs 0.10/0.20 until a retune split exists.

**Scope creep:** none that violates Out of Scope. `pool` CLI, `--exclude`/`--cal`, `--gbdt`, and `always_cheapest` are the issue tickets. Relabel/salvage CLIs predate this range.

---

### Standards / quality

Repo standard is `CONTEXT.md` (glossary). No `CODING_STANDARDS.md`. Smell baseline is judgement; skip format/lint.

**Documented standard:** the diff speaks trained / Scorer / complexity bin / calibrated `p_success` / `rules_cost_delta` / success-gold cells. It does not call the hop a “learned router,” clone Pioneer, or name cost-vs-rules as savings. Replay adds `always_cheapest` beside `always_flash` (fallback-or-cheapest), which is the glossary-safer baseline for the gate bar.

**Tests match the spec’s testing decisions:** they assert JSONL `success` / `success_tier`, hop `path=shadow` / `x-router-trained-would`, gate fields, refuse-without-opt-in, and “toy fixture may fail bars.” They do not assert sklearn internals.

#### Findings

**Critical:** none.

**Important (judgement, not merge-blocking):**

- **Duplicated Code** — `score_eligible` GBDT and logistic branches copy bin prediction, Platt `a,b`, intercept omit, and table fallback. A later omit-rule change can drift. Same shape in gold 429 vs success row dicts (`dense` tag duplicated).
- **Mysterious Name** — serve still threads the predicted complexity bin through a parameter named `hint_bin` (`score_eligible`, replay gold items). Glossary: complexity bin ≠ train JSONL `hint_bin`. Live hop does not require the HTTP field.

**Minor:**

- **Divergent Change** — `train.py` still owns pool dispatch, gold y, silver regularizer, logistic, GBDT, Platt, and CLI refuse. `pool.py` extraction helped ingest; fit still lives here.
- **Feature Envy / coupling** — `train.fit_scorer` imports private `scorer._gbdt_z`. GBDT artifacts still write empty `weights: {}`; `load_scorer` keys on `p_success` or `weights`, not `gbdt`. Fit always writes `p_success`, so current artifacts load.
- **Speculative Generality** — `_calibrator_ab` still accepts `calibrator` or `platt` while fit writes `platt`. Pre-existing alias; this range did not add a second calibrator zoo.
- Stdlib stump GBDT (24 trees, skip bias dim) is the spec’s Rec A lift, not an extra library.

---

### Deferred minors triage (must-fix before merge vs can stay)

Nothing below puts live traffic on `path=trained` or stamps Verified. **Must-fix before merge: none.**

**Can stay** (issue 01–06 ledger):

| Item | Why it can stay |
|---|---|
| `--eval` missing-path → empty collisions | CLI still requires `--eval`; eval-named paths are ingest-blocked; operator-runtime |
| `sample_stratum` can drop smith when extra fills n | Smith-primary when `len(smith) ≥ n`; tiny-smith path is tested for “any smith” but not guaranteed by the sampler |
| Independent margins / no occupied floor ≥20 | Mix is not all-trivial; joint design not required to merge a shadow Scorer |
| Heuristic `hint_bin` on pool rows | Train-only; serve predicts the bin |
| Soft tools assert; O(n²) sampler; argparse-optional `--smith` | Runtime refuse covers gym-only; n=4000 is fine |
| Tools stub is a single `read`; schema ignores type/properties | Labeling harness, not the product hop |
| Sparse tests assert superset of anchors | Eligible-set filter is the spec |
| Empty `--exclude` samples full leftover pool | `--dense` still requires `--exclude`; disjointness is locked when exclude is real sparse gold |
| Fit does not refuse overlapping `--gold`/`--cal`; missing `--cal` path fallthrough | Operator used sparse-400 / dense-100 / verified holdout; artifact stays `not_spec_floors` |
| `n_cal` / pooled table `p_success`; dense tag duplication; exclude matches `prompt` only | Reporting / onboard table, not live flip |
| Intercept omit `if intercepts and i not in intercepts`; fit+score test would pass without serve change | Omit is in `score_eligible`; hop GBDT/Rec A tests lock shadow |
| Cal-only table P is not Platt; silver second-order on Platt a,b via weights | Spec allows silver regularizer; Platt *y* is still cal gold |
| Fit JSONL `hint_bin` vs serve predicted bin | Spec: serve must not require train `hint_bin` |
| Cheapest bar is aggregate stats; no Flash≠cheapest fixture on the integration path; CLI test skips `assert_not_production_floors`; inclusive boundaries unpinned; `POLICIES` omit; `gold_is_holdout` constant | Gate is operator-side; toy fixture is allowed to fail; CLI uses the tiny fixture gold |
| Duplicated `score_eligible` GBDT/logistic; private `_gbdt_z`; empty `weights: {}`; `load_scorer` ignores `gbdt` as a key | Fit writes `p_success`; hop test loads GBDT and stays shadow |

**Can stay** (pre-issue Task 1–3 leftovers still on the tree; AUC 0.5 impute / GLM teacher effort / gate-vs-cheapest were already must-fix in `8bb2677`, before this range):

Brier dropping fallback hops; ECE type-only on the toy fixture; production-floor helper opt-in/conflated; oracle no-pick cost 0; dead `hint_bin` / double score; `try/return` vs `pytest.raises`; `featurize` `hint_bin` name; feature-index tests; incomplete `calibrator` alias; short `bin_weights` truncate; relabel/salvage CLI; teacher field on escalate; budget TOCTOU.

**Do not treat as merge blockers:** operator replay failing the numeric bars; GBDT making Brier/ECE worse. Spec trigger was “logistic fails → one GBDT lift,” then stay shadow. Issue 07 is needs-info until a later gate passes.

---

### Assessment

**Merge readiness:** Ready

**Reasoning:** Issues 01–06 ship the stratum pool, success-gold y, dense/cal split, silver-regularized Rec A, holdout replay gate, and one GBDT lift without opening Rec B, live embed, or an auto-flip. Serve stays shadow by default; artifacts and gate reports stay `not_spec_floors`; silver is not Platt/gate/threshold y; dump `resolved` is not y; budget default 15; unit tests do not spend. Operator holdout still fails the local bars, so issue 07 was correctly left untaken. Remaining ledger items are operator footguns and quality nits, not live-path defects. The 7 `x-router-reason` gateway failures stay accepted out of scope.
