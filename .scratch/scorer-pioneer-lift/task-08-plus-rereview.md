### Spec Compliance

**Matches** Option A unpaid slices 08–11 after the Important fix commit. Prior Important findings are closed in code and covered by focused tests. Global hard constraints still hold: Verified/Lite/TB eval-only; no 07 / `TRAINED_PATH` flip; no fake gate pass; no paid gold invent; unit tests unpaid; issue 12 remains needs-info only.

| Slice / constraint | Verdict |
|---|---|
| 08 Geometry: unpaid CLI, per-id rates, Spearman, token/`log1p` stats, y-rates, `kill_spearman`, eval not fit y | Met |
| 08 / 11 Prefer logistic until Spearman `rho > 0` (kill can stay `rho < 0`) | Met — `prefer_logistic = not (rho > 0)`; kill still `rho < 0`; tests for zero / undefined / positive |
| 09 `--verified-like`: short + hard-check metadata, collision vs `--eval`, empty refuse, no `resolved` / no gold cells | Met |
| 09 No invented `json_schema.required: ["status"]` from `\bjson\b` | Met — inferred schema uses `required: []` |
| 09 Pool not majority-trivial after short+check filter | Met — `trivial` → `hard` remap; test locks `trivial * 2 < len(rows)` |
| 10 Dual eval: `--gold` gate, `--cost-gold` nested slice, `rules_ne_cheapest_rate`, no bar rewrite | Met |
| 11 Fit default logistic; `--gbdt` help; replay note on `gbdt`; no zoo / no overwrite of `scorer.json` | Met |
| Global: no Verified-as-fit; no 07; no fake pass; no paid gold; unit tests never spend | Met |

### Strengths

- Prefer-logistic and kill thresholds are correctly separated; zero / no-overlap Spearman keep logistic recommended without falsely killing the recipe.
- Inferred JSON checks no longer invent a non-task `status` contract; empty `required` matches “parseable JSON ok” and will not poison ranking geometry the way `required: ["status"]` would.
- Verified-like pool remaps post-filter `trivial` bins so `mix_sources` is not majority-trivial on short rename+JSON rows.
- Prior unpaid seams (geometry CLI, dual eval, collision-filter, shadow/`not_spec_floors`) remain intact; Fix section is TDD-evidenced with covering 47 passed.

### Issues

#### Critical

None.

#### Important

None. All three prior Important findings are fixed.

#### Minor

- Issue 08 checklist / Answer still say prefer logistic “while Spearman < 0” / “Spearman < 0 → prefer_logistic”; code and issue 11 correctly require prefer until `rho > 0`. Ticket text drifted.
- Issue 08 still asks for token / `log1p` **histograms**; CLI still prints two diagnostic fractions only (unchanged; enough for H2).
- `--cost-gold` help says “disjoint” but there is still no collision-filter vs `--gold` (operator footgun; top-level gate remains honest).
- Nested `cost_slice` still runs full `apply_replay_gate`, so nested `replay_gate_pass` can disagree with the top-level flag.
- Operator recipe still never mentions hop `SCORER_PATH` (live hop may keep serving `data/scorer.json` while replay uses logistic).
- Remap is blunt (every post-filter `trivial` becomes `hard`) rather than preferentially sampling naturally hard/frontier rows; acceptable for the unpaid seam, but real difficulty still depends on issue-12 gold y.

### Assessment

**Task quality:** Approved
**Reasoning:** The three Important defects (prefer-logistic threshold, fake `status` schema, majority-trivial pool) are fixed with matching tests; unpaid Option A machinery for 08–11 is ready for the paid hard-y probe (issue 12), with only deferred minors left.
