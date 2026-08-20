# Spec review: `674e885..1d30631`

Did not demand: Pioneer dashboard, live embed, GBDT zoo, SWE-smith ingest, automatic `TRAINED_PATH=trained`, Verified promotion claim.

## (a) Missing or partial

1. **Stratum sampling.** Spec: “As a trainer, I want stratum sampling (bin × phase family × tools), so that gold is not all trivial edits.” `_read_queries` is first-N. No stratum on the query file.

2. **Retune split.** Spec: “As a trainer, I want medium threshold + max_regret retuned on a split unused for train or calibrator.” Replay hardcodes ship medium (`EFFORT = "medium"`). Story 8 allows keeping 0.10/0.20 until a retune split exists.

3. **GLM teacher effort.** Spec: “Teacher `max_completion_tokens` and minimum published `reasoning_effort` so JSON can finish.” `_teacher_call` sets effort only for Motif; GLM escalate/salvage omit it even though `MIN_REASONING_EFFORT` lists GLM `"none"`.

4. **Tools/JSON-if-required gold.** Spec: “gateway success gold (no escalate, valid tools/JSON if required).” Any `tool_calls` is success; `needs_tools` without calls can still be weak-True on nonempty text.

## (b) Scope creep

- `relabel` / `salvage` CLIs and a second GLM pass after parse-fail already escalates. Spec asked cache-first relabel (story 20) and “parse-fail to always escalate” (story 19), not extra subcommands.
- Optional `hint_bin` on `score_eligible` / `trained_select`. Spec: “Train-only fields (`hint_bin` on JSONL) must not be required at serve.” Live hop does not pass it; the override was not asked.
- Prompt-regex gold (typo/yaml/substring) beyond verified metadata + JSON-if-required.

## (c) Implemented wrong

1. **Gate disagreement.** Spec: “Disagreement > 0 (policy is not identical to always-cheapest-eligible).” `replay_gate_pass` uses rules ≠ trained. Trained=always-Flash can pass if rules sometimes pick dear. (Report field “rules pick ≠ trained pick” is a different line.)

2. **Rank AUC imputes 0.5.** Spec: “rank AUC and mean per-prompt P(success) spread.” `ps.get(mid, 0.5)` for gold cells the scorer omitted.

3. **`gold_is_holdout` is always True.** Spec: “on a **holdout** prompt split unused for train and calibrator.” CLI help warns; the field does not detect mixed gold.

4. **Bin head still truncates.** Spec: “Complexity bin from observable features … and fitted bin head.” `predict_complexity_bin` `_dot`s short `bin_weights`; P(success) weights were length-checked.

## Deferred minors — merge triage

**Must-fix:** GLM teacher `reasoning_effort`; gate vs always-cheapest; AUC skip-unscored.

**Can stay:** stratum sampling (operator JSONL); retune (story 8); Brier/ECE drop fallbacks; ECE type-only on fixture; production-floor helper opt-in; oracle $0; dead `hint_bin` / double score; try/return vs `pytest.raises`; constant `gold_is_holdout` (CLI is the contract); `featurize` hint_bin name; bias+intercept (`w[0]` frozen in `1d30631`); feature-index tests; incomplete `calibrator` alias; short `bin_weights` (new fits emit matching dim); relabel/salvage CLI; teacher field on escalate; budget TOCTOU.
