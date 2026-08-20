### Spec Compliance

**Mostly matches** Option A unpaid slices 08–11 and the global hard constraints. Geometry lock, `--verified-like` pool, `--cost-gold` dual eval, and logistic-preference notes are present. Verified/Lite/TB stay out of fit; `apply_replay_gate` still always stamps `path=shadow` / `not_spec_floors`; bars are unchanged; issue 07 / `TRAINED_PATH` flip / paid gold (12) are not taken; budget default stays 15; unit tests stay unpaid.

| Slice / constraint | Verdict |
|---|---|
| 08 Geometry: unpaid CLI, per-id rates, Spearman(train, eval), token/`log1p` stats, y-rates, `kill_spearman`, eval not fit y | Met (`geometry.py`; fracs at 4.8 / 4.14, not full histograms) |
| 08 / 11 Prefer logistic while transfer missing | ⚠️ Partial — `prefer_logistic` / `recommended_artifact` tied to `rho < 0` only; path + issue 11 want prefer logistic until `rho > 0` |
| 09 `--verified-like`: short + hard-check metadata, collision vs `--eval`, empty refuse, no `resolved` / no gold cells | Met as filter; hard/frontier preference is weak (see Important) |
| 10 Dual eval: `--gold` gate, `--cost-gold` nested slice, `rules_ne_cheapest_rate`, no bar rewrite | Met |
| 11 Fit default logistic; `--gbdt` help; replay note on `gbdt` artifact; no zoo / no overwrite of `scorer.json` | Met |
| Spec: Verified eval-only; no auto-flip; `not_spec_floors`; `BUDGET_LIMIT_USD` default 15 | Met (untouched defaults; gate still fail-closed) |
| Global: no Verified-as-fit; no 07; no fake pass; no paid gold invent; unit tests never spend | Met |
| Path §6 unpaid order (geometry → pool → dual eval → logistic prefer); paid probe deferred to 12 | Met |

Report claims for seams and constraint holding match the diff. Issue 12 ticket is documentation only (needs-info), not invented cells.

### Strengths

- Unpaid geometry CLI is a clean kill/recommend seam: per-id rates, Spearman, y-rates, length fracs, `eval_is_fit_gold=false`, no `AIAND_TRAIN`, no gate stamp.
- `--verified-like` reuses issue-01 collision-filter and smith-primary rules; copies hard-check keys; refuses empty mix; tests lock long-easy drop, eval collision, no `resolved`/`success` on pool rows.
- Dual eval keeps promotion judgment on `--gold` while exposing H3 via `rules_ne_cheapest_rate` and a fixture where `cost_slice.rules_cost_delta < 0` without rewriting verified bars.
- Logistic preference is documentation + help + replay note, not a second GBDT zoo or a silent `TRAINED_PATH` flip; `apply_replay_gate` still always shadows.

### Issues

#### Critical

None.

#### Important

- **`prefer_logistic` / `recommended_artifact` use `kill` (`rho < 0`), but issue 11 and `next-path-decision.md` §6.1 require logistic until Spearman > 0.** When overlap is too small, rates are constant, or Spearman computes as `0.0`, the CLI recommends `data/scorer.json` and sets `prefer_logistic=false`. Kill of the sparse/dense recipe can stay `rho < 0`; prefer-logistic must stay true unless `rho > 0`.
- **`--verified-like` invents `json_schema: {required: ["status"]}` from any prompt matching `\bjson\b`.** Gold y (`_gold_label`) will treat that as verified-tier and fail almost all coding-agent replies that are not objects with a `status` key. That can drive a low y-rate without verified-like *ranking*, which is the Option A transfer goal this pool exists to feed. Prefer copy/infer of real checks (or a schema with empty `required`) over a fake task contract.
- **After the short+check filter, `mix_sources` still targets issue-01 bin mix (15% trivial / 40% standard), and `infer_bin` maps many ≤62-token prompts to `trivial`.** Issue 09 asks to prefer short + hard/frontier (or JSON/tools-bearing). The “or” saves the letter of the ticket, but the sampler still fights verified-like difficulty instead of up-weighting hard/frontier inside the short set.

#### Minor

- Issue 08 asks for token / `log1p` **histograms**; the CLI prints two diagnostic fractions only (enough for H2, thinner than the brief).
- `--cost-gold` help says “disjoint” but there is no collision-filter vs `--gold` (operator footgun; gate still honest on top-level `--gold`).
- Nested `cost_slice` runs full `apply_replay_gate`, so `cost_slice.replay_gate_pass` can disagree with the top-level flag; top-level gate remains correct.
- Operator recipe (issue 11) retargets `replay_report --artifact`; live hop still defaults to `SCORER_PATH` → `data/scorer.json`. Fine given “do not overwrite,” but the recipe never mentions hop `SCORER_PATH`.
- Geometry has no green-path test for `rho > 0`; `test_replay_gbdt_artifact_prints_prefer_logistic` skips `assert_not_production_floors` (fixture is tiny).

### Assessment

**Task quality:** Needs fixes
**Reasoning:** The unpaid Option A seams are real and hard constraints hold, but prefer-logistic is wired to the kill threshold (`rho < 0`) instead of “until Spearman > 0,” and inferred hard-checks invent a non-task `status` schema that will poison ranking geometry for the hard-y probe. Fix those before treating 08–11 as closed.
