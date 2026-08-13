# 02 — Live trained pick, effort, scorer_down, named savings

**What to build:** An operator can set `TRAINED_PATH=trained` and the client is served the **cheapest** eligible model whose calibrated P(success) clears effort **threshold** and **max_regret**. Effort is only `x-routing-effort: low|medium|high|max` (default `medium`; no `xhigh`). If none clear the bar, the configured fallback still returns 200. If the Scorer artifact is missing or corrupt, the hop serves rules with `scorer_down` and no fake confidence. Savings is vs `most_expensive_eligible` only; cost vs rules is `rules_cost_delta_usd`, never named savings.

Parent: [trained-hop spec](../spec.md). Ship defaults: low 0.05/0.30, medium 0.10/0.20, high 0.20/0.15, max 0.60/0.03 — namespaced in `trained_effort`, never rules AA `max_regret: 8`.

**Blocked by:** 01 — Shadow path with fixture Scorer

**Status:** resolved

- [ ] `TRAINED_PATH=trained` + fixture Scorer: served model is the cheapest-above-bar id; JSONL `path=trained`; `X-Router-Reason` absent; `X-Router-Confidence` and `X-Router-Complexity-Bin` present.
- [ ] Trained/shadow headers match the frozen contract: Model, Phase, Effort, Complexity-Bin, Confidence, Rule, Path, Baseline-Model, Savings-Usd (estimate), Reason-Codes, Candidates, Threshold. Shadow still has `X-Router-Trained-Would`.
- [ ] `low` still uses the Scorer (tiny floor, wide regret). `max` is still cheapest-above-bar on the **same eligible set as rules**.
- [ ] Effort header changes threshold / max_regret from `trained_effort` ship defaults.
- [ ] A cheaper model more than max_regret behind the top P(success) is not served (`rule=max_regret`).
- [ ] A model below threshold is not served even if cheapest (`rule=threshold`).
- [ ] None clear the bar: configured fallback, HTTP 200, `rule=fallback_declined`.
- [ ] Missing or corrupt Scorer artifact: `path=rules`, `rule=fallback_declined`, reason_code `scorer_down`, no Confidence, served model is rules/fallback — **not** the learned stub.
- [ ] Tools present → no no-tools model in `candidates` or `p_success` keys. Trained never expands or shrinks hard constraints.
- [ ] Allow-list without K3 → `baseline_model_id` is not K3. Savings vs most expensive **eligible** only.
- [ ] Shadow and trained JSONL rows include `rules_cost_delta_usd` (trained − rules) and do not call it savings.
- [ ] Bloom is off live headers. `learned_wins.json` on does not switch `path=trained` to the highest-AA stub.
