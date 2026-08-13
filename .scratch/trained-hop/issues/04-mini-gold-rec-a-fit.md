# 04 — Mini gold, Rec A smoke fit, loadable artifact

**What to build:** A trainer, after the HTTP hop is green, can fit a **features-only Rec A Scorer** (logistic or GBDT + Platt; one is enough) from mini **success gold** plus silver regularizer on unobserved cells only. The hop loads that artifact in-process. The file is labeled `not_spec_floors`. Missing gold cells stay missing. No K3 gold cells. No live embed. Stop before the spend file would exceed the configured budget.

Parent: [trained-hop spec](../spec.md). Smoke ceilings: sparse ≤200 queries × Flash + measured trio (short completions); dense/cal ≤100 queries × eligible except K3. This is not the production n=4000 / n≥300 floors and not Verified.

**Blocked by:** 02 — Live trained pick, effort, scorer_down, named savings; 03 — Opt-in teacher CLI (silver labels)

**Status:** resolved

- [ ] Opt-in gold/fit job refuses without the opt-in env (no provider calls, spend unchanged). With opt-in it is cache-first and stops if spend would exceed the configured budget.
- [ ] Sparse gold runs Flash + measured trio only (when eligible). Dense/cal slice runs eligible **except K3**. No K3 gold cells.
- [ ] Student target is gold-where-present + silver regularizer on **unobserved** cells only. Never calibrate on silver. Unobserved ≠ 0.
- [ ] Writes a loadable Scorer artifact labeled `not_spec_floors` (n and dumps below production). Hop does not retrain at request time.
- [ ] Loaded Scorer emits a complexity bin and calibrated P(success) per **eligible** id only. New catalog ids without a dense gold slice stay out of live P(success) (rules-only for that id).
- [ ] `TRAINED_PATH=trained` with this artifact (not only the 01 fixture) serves cheapest-above-bar; scorer-down still applies if the file is corrupt.
- [ ] Default `BUDGET_LIMIT_USD` in code stays 15; smoke at $100 is an operator env, not a code default.
- [ ] No embedding-model forward on the hop. No dump F2P harness, Verified, Terminal-Bench, or K3 gold in this ticket.
