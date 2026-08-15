# Whole-branch must-fix re-review

`1d30631` → `8bb2677`. Verdict against `.scratch/scorer-pioneer-lift/whole-branch-fix-brief.md` and the three must-fix items in `.scratch/scorer-pioneer-lift/whole-branch-spec.md`. Task-scoped gate only — not a re-merge of the full spec. Did not demand can-stay items.

### Spec Compliance

- ✅ Spec compliant on the three must-fixes. Each is present in-diff, wired on the named seam, and locked by a test that would have failed on `1d30631`.
- Owned files only: `src/aiand_router/train.py`, `src/aiand_router/replay_report.py`, `tests/test_train.py`, `tests/test_replay_report.py`. Did not chase stratum sampling, retune, salvage CLI, `gold_is_holdout`, short `bin_weights`, `hint_bin`, gateway `x-router-reason`, or Fowler smells.
- ⚠️ Tests not re-run (implementer: `tests/test_train.py` + `tests/test_replay_report.py` — 29 passed, TDD red/green per finding).

Verification of the three:

1. **GLM teacher `reasoning_effort` — fixed.** `_teacher_call` (`train.py:195-197`) now does `MIN_REASONING_EFFORT.get(model_id)` and writes `reasoning_effort` when the map has a value. GLM escalate is `"none"` (`:60`); Motif stays `"low"` (`:61`). Escalate (`:252-254`) and salvage (`:297-304`) both call `_teacher_call(..., ESCALATE_TEACHER, ...)`, so both paths get the body field. `"none"` is truthy, so `if effort:` does not drop GLM. `tests/test_train.py:108-121` asserts `provider.calls[0]["reasoning_effort"] == MIN_REASONING_EFFORT[ESCALATE_TEACHER]` at the teacher-body seam; the existing Motif test (`:100`) still pins `"low"`.

2. **`replay_gate_pass` vs always-cheapest — fixed.** Gate no longer uses `disagreement_rate > 0` (rules ≠ trained). It requires `report["policies"]["trained"] != report["policies"]["always_flash"]` (`replay_report.py:272`). Identical trained / always-Flash policy stats fail even when rules sometimes pick dear. `disagreement_rate` remains rules≠trained on the report (`:216-217`, `:249`). `tests/test_replay_report.py:135-152` constructs every other bar green, `disagreement_rate=0.4`, and trained stats equal `always_flash`; asserts `False`. That is the `1d30631` hole (implementer red: `assert True is False`).

3. **Rank AUC skip unscored — fixed.** `ps.get(mid, 0.5)` is gone. Loop is `if mid not in ps: continue` then `ps[mid]` (`replay_report.py:229-232`). `ids` is still eligible gold cells (`:219`); `score_eligible` table path omits ids missing from `p_success` (`scorer.py:152-153`), so an omitted gold cell is skipped, not chance-imputed. `tests/test_replay_report.py:155-201` adds eligible `mid/other` gold y=1 with no artifact `p_success` entry: skip → `(0.9,1)` vs `(0.8,0)` → AUC `1.0`; impute `0.5` → also `(0.5,1)` vs `(0.8,0)` → `_rank_auc` `0.5`. Test would fail if 0.5 were imputed.

### Strengths

- **Previous must-fix 1 actually fixed.** Teacher body uses the same `MIN_REASONING_EFFORT` map `_gold_body` already applied (`train.py:327-337`). One-line change at `_teacher_call`; no second HTTP path. Seam test would `KeyError` on the old Motif-only `if model_id == CHEAP_TEACHER` branch.
- **Previous must-fix 2 actually fixed.** Spec Testing Decision “Disagreement > 0 (policy is not identical to always-cheapest-eligible)” is now the gate, not rules≠trained. Report field “rules pick ≠ trained pick” is unchanged. Comparison uses the `always_flash` policy object already in the report (`{success_rate, list_price_cost}`), which is what the brief named. Identical picks ⇒ identical stats ⇒ fail.
- **Previous must-fix 3 actually fixed.** Unscored eligible gold ids no longer pull Mann–Whitney toward 0.5. The new test is a numeric lock, not a type check: `rank_auc == 1.0` vs imputed chance `0.5`.
- Shortest-diff shape: +96/−4, four files, no CLI rewrite, no new dependencies.

### Issues

#### Critical

None.

#### Important

None. All three must-fix items from `whole-branch-spec.md` / `whole-branch-fix-brief.md` are addressed in `8bb2677`.

#### Minor

None in this range that this gate should chase. Can-stay items from the whole-branch spec/standards reviews stay deferred (stratum sampling, retune, extra CLIs, constant `gold_is_holdout`, short `bin_weights`, `hint_bin` naming, TOCTOU, etc.).

Note (not a remaining miss): the gate compares aggregate policy stats, not pick lists. The report does not store picks; identical always-cheapest picks cannot produce different `{success_rate, list_price_cost}`, so the required fail case is covered. A coincidental stats collision (different picks, same rate and cost) would also fail — conservative.

### Assessment

**Task quality: Approved**

The three merge-blocking items are implemented and seam-tested in the owned files. GLM escalate/salvage send published min effort (`"none"`), the replay gate fails trained=always-Flash even when rules disagree, and rank AUC skips unscored ids instead of imputing 0.5. This task gate can close.
