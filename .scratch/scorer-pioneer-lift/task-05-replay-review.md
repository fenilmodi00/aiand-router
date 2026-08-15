### Spec Compliance

**Compliant** for this ticket’s gate seam. The diff is the holdout replay gate, not a rewrite of Task 1’s report: `replay_gate_pass` now fails when trained matches always-cheapest-eligible (not only always-Flash); `apply_replay_gate` stamps `path=shadow` and `not_spec_floors=true` whether bars pass or fail; CLI greps those fields; unit tests call `assert_not_production_floors` on the shared `_report()` path and never require the toy fixture to clear AUC ≥ 0.65. Issues 06 and 07 stay out.

| Requirement | Verdict |
|---|---|
| Trained ≠ always-cheapest-eligible (not only always-Flash) | Met (`always_cheapest` policy + gate compare; distinguishing test when Flash ≠ cheapest) |
| Failing any bar keeps `path=shadow` and `not_spec_floors` | Met (`apply_replay_gate`; parametrized numeric misses + toy fixture) |
| Passing still does not auto-flip `TRAINED_PATH` or stamp Verified | Met (pass path still `shadow` / `not_spec_floors=true`; CLI does not set env) |
| Numeric bars in the gate: AUC ≥ 0.65, P-spread ≥ 0.10, Brier skill > 0, dual ECE ≤ 0.03, trained success ≥ rules − 1 pp, rules cost delta < 0 | Met (`replay_gate_pass`; toy is allowed to fail them) |
| Unit tests do not invoke production floors; must not require smoke AUC ≥ 0.65 | Met (`_report()` calls the helper; toy asserts gate False / shadow, never AUC ≥ 0.65) |
| Cost vs rules is `rules_cost_delta`, never savings % | Met in this diff (key unchanged; new test asserts `"savings" not in report`) |
| No Pioneer dashboard, Rec B, live embed, automatic `TRAINED_PATH=trained`; no GBDT (06) or operator flip (07) | Met (not in this diff) |
| Offline replay over frozen `--gold` holdout + artifact + rules; report metrics (policies, disagreement, AUC, P-spread, Brier/ECE) | ⚠️ Cannot verify from this diff (Task 1). This change keeps those keys, adds `always_cheapest`, still has no provider calls. `--gold` help is unchanged context. |
| Tests do not assert sklearn internals; unit tests never spend | Met (synthetic reports + fixture gold; no sklearn, no provider) |

Report concerns 1–4 are accurate, not spec misses: gateway `x-router-reason` failures are out of scope; the toy fixture is supposed to miss bars; `gold_is_holdout` remains a constant with `--gold` as the contract; always-shadow on pass is issue 07.

### Strengths

- The live gap matches the ticket: cheapest-eligible is a real policy (`_pick_cheapest` / `always_cheapest`), and the gate no longer treats “not Flash” as “not cheapest.” The RED case (trained = cheapest, Flash is the dear fallback, other bars green) is locked.
- `apply_replay_gate` is fail-closed on promotion: pass and fail both stamp `path=shadow` and `not_spec_floors=true`. That is the right split from issue 07.
- Tests are pointed rather than a metric dump: parametrized misses for AUC / P-spread / Brier skill / dual ECE / cost delta; a separate −1 pp success case; toy fixture must not satisfy AUC ≥ 0.65; `_report()` now refuses Verified n / staffed stamps.
- Scope stayed inside `replay_report.py` + its tests. CLI gained grepable `path=shadow` without a second HTTP stack or a hop flip.

### Issues

#### Critical

None.

#### Important

None.

#### Minor

- `replay_gate_pass` falls back to `always_flash` when `always_cheapest` is missing. That is the bar this ticket replaced. The CLI path cannot hit it (`replay_report` always writes the key); a saved Task-1 JSON re-gated by hand would silently use Flash again. Fail-closed (missing key → False) would match the ticket better.
- The cheapest bar compares `_policy_stats` dicts (`success_rate` + `list_price_cost`), not per-prompt picks. Identical cheapest picks cannot false-pass. Different picks with the same aggregates would false-fail and stay shadow (safe direction). Spec wording is “policy is not identical.”
- No `replay_report()` fixture where `fallback_model` is not min unit-cost, so `_pick_cheapest` is not differentiated from `_pick_flash` on the integration path. The toy catalog has Flash as cheapest; the distinguishing lock is synthetic dicts only.
- New CLI test invokes `main()` on fixture gold without `assert_not_production_floors`. Shared `GOLD` is tiny and `_report()` would already fail if it grew to Verified n; still a helper skip on a unit-test replay invocation.
- `test_failing_numeric_bar_*` does not pin the inclusive boundaries that should pass (AUC = 0.65, P-spread = 0.10, ECE = 0.03, trained success = rules − 0.01). Misses are clearly on the fail side (0.64, 0.09, 0.031, 0.78 vs 0.80).
- `POLICIES` in the test module still omits `always_cheapest`; coverage for that row is the weaker “rate in [0,1]” test.

### Assessment

**Task quality:** Approved
**Reasoning:** The ticket was the gate, and the gate is in code: trained is judged against always-cheapest-eligible, any miss keeps shadow/`not_spec_floors`, a pass still does not flip or stamp Verified, and CI is not tied to toy AUC ≥ 0.65 or production floors. Residual notes are fallback/proxy/test-gap, not missing bars.
