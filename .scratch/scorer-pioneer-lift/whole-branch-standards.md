# Whole-branch Standards (`674e885..1d30631`)

Repo standard: `CONTEXT.md` (glossary only). No `CODING_STANDARDS.md`. Baseline smells are judgement calls. Skip lint/format.

## (a) Documented standard

**No hard glossary hits** for the forbidden pairings: the diff says trained / Scorer / complexity bin / calibrated `p_success` / `rules_cost_delta` / success-gold cells — not “learned router”, Pioneer clone, Pioneer-style score, or named savings vs rules.

**Judgement (language slip)** — `CONTEXT.md` Cheap teacher: *Avoid: Flash (unless the policy actually picks it)*; Named savings baseline: *Avoid: always-fallback*.

```python
def _pick_flash(...):
    fid = cfg.get("fallback_model")
    ...
    return min(eligible, key=lambda m: m.unit_cost) if eligible else None
# ...
"always_flash": _policy_stats(flash_picks, success),
```

`replay_report.py`: `_pick_flash` / `always_flash` pick fallback-or-cheapest, not Flash.

Serve also feeds the **predicted complexity bin** (`CONTEXT.md` Scores: complexity bin) through a parameter named `hint_bin`:

```python
x = featurize(phase, needs_tools, tokens, bin_)
# trained_select(..., hint_bin=hint_bin)
```

## (b) Baseline smells (all judgement)

**Mysterious Name** — `hint_bin` (train JSONL vs serve predicted bin); `not_spec_floors`; nested `one()`.

**Duplicated Code** — `featurize` / `featurize_observable` share bias + tools + log1p + `_token_bins` + family one-hots; `_fit_binary` vs `_fit_binary_intercept` (same GD loop, skip dim 0); teacher salvage row dict vs `run_salvage_silver`; `_row_x` vs `_row_x_observable`.

**Divergent Change** — `train.py` now changes for concurrency/spend lock, gold-y heuristics, pytest verify, intercept + cal-slice Platt, and extra `relabel`/`salvage` CLIs.

**Data Clumps** — `phase`, `needs_tools`, `tokens` (replay also `effort`/`budget`) travel together through `_eligible`, `kw`, `score_eligible`, `trained_select`.

**Speculative Generality** — `_calibrator_ab` accepts `calibrator` or `platt` while fit still writes `platt`; `_query_map` also loads sibling `verified-queries.jsonl`; `relabel`/`salvage` beside in-loop salvage.

**Middle Man** — `_gold_success` only returns `_gold_label(...)[0]`.

**Feature Envy** — `spend._async_lock = asyncio.Lock()` patched onto `SpendLog` from `train.py`.

**Shotgun Surgery** — `hint_bin` threaded through teacher, gold, salvage, fit, scorer, replay, fixtures.
