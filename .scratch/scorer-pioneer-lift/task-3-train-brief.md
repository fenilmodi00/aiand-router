# Task 3: Train pipeline — success gold, teacher, cal-slice fit

Read first: `.scratch/scorer-pioneer-lift/spec.md` Implementation Decisions + user stories 13–30, 35, 42–45. `CONTEXT.md`.

## Where this fits

Smoke train exists and is WIP. Labels were weak (HTTP 200 / nonempty); Platt was fit on all rows; Motif JSON truncated. Lift **gold y, silver regularizer, teacher parse, fit** so a later replay (Task 1) can see a real policy. Do not flip `TRAINED_PATH`. Do not stamp Verified promotion. Code default `BUDGET_LIMIT_USD` stays **15**.

## Owned files (ONLY these)

- `src/aiand_router/train.py`
- `src/aiand_router/cache.py`
- `tests/test_train.py`

You may **read** `scorer.py` and write artifact keys Task 2 documents (`intercepts`, `bin_weights`, `platt` on cal slice). Do not edit `scorer.py`. Do not add a second HTTP client; keep FakeProvider tests.

Untracked helpers you may include if they already exist and are needed: `datasets/verified-queries.jsonl`, `scripts/gen_verified_queries.py`. Do not ingest SWE-bench Verified/Lite or Terminal-Bench as train dumps. Do not use dump teacher `resolved` as y.

## Implement (TDD)

Existing `tests/test_train.py` must stay green (refuse without opt-in; parse-fail escalates; gold skips K3; `not_spec_floors`; gold success tiers; concurrent gold). Add tests at the train CLI / gold JSONL seam only.

Required:

1. **Gold y order:** verified metadata (`tests_passed`, expected match, JSON/schema validity) → gateway success gold (no escalate, valid tools/JSON if required) → never nonempty content alone when a stronger check exists. `finish_reason=length` with empty content is failure. Missing cells stay missing (unobserved ≠ 0).
2. **Silver** only as regularizer on **unobserved** cells. Never calibrate, gate, or threshold-tune on silver.
3. **Fit:** per-model intercept from gold marginals, then feature correction, then calibrator on a **held-out gold cal slice only** (not in-sample Platt on all zs/ys). Logistic Rec A. No GBDT zoo. No live embed.
4. **Bin head:** fit `bin_weights` from request-observable features (not live `hint_bin`). Train JSONL may still *record* `hint_bin` as a train-only field.
5. Teacher: parse-fail **always** escalates (even after quality cap). Unlabeled stays unlabeled. Prefer `max_completion_tokens` / published `reasoning_effort` so JSON can finish if that is a one-line body change.
6. Sparse gold: Flash + measured trio when eligible. Dense/cal: enabled catalog except K3. **No K3 gold cells.**
7. Artifact remains `not_spec_floors: true`.
8. Cache-first paid calls; cache hits unbilled. Concurrency env-capped (already present — keep).
9. New catalog ids without dense gold stay without a live P(success) intercept invented from silver alone.

Skip (YAGNI this cycle unless already stubbed): offline embed ablation, SWE-smith dump ingest, automatic `path=trained`, Pioneer dashboard, inventing savings %.

Ponytail: extend WIP in `train.py` / `cache.py`; do not rewrite the CLI. Shortest diff that fixes cal-slice Platt and gold-y order.

## Commit

Commit only owned files (plus verified-query dataset/script if you actually use them). Message: why (success gold + cal-slice calibrator so P(success) is not a compressed smoke fit).

## Report

Write `.scratch/scorer-pioneer-lift/task-3-train-report.md`. Return status, commits, test summary, artifact schema emitted for Task 2.
