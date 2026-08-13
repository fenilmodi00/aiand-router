# 03 — Opt-in teacher CLI (silver labels)

**What to build:** A trainer can mint **complexity bins** and **silver P(success)** query-only, offline, without touching the live hop. Cheap teacher then escalate (this org: Motif → GLM), temperature 0, strict json_schema, cache-first, catalog-relative exclusions (providers of measured trio ∪ live fallback). Pytest and a forgotten process cannot spend: the job refuses unless an explicit opt-in env is set. Unlabeled stays unlabeled.

Parent: [trained-hop spec](../spec.md). Ceiling for this `$100` cycle: ≤1000 teacher rows. Soft-cap escalate ≤25%. Live chat teacher is out.

**Blocked by:** None — can start immediately (parallel with 01).

**Status:** resolved

- [ ] Without the opt-in env, the CLI refuses, the fake provider is not called, and spend does not move.
- [ ] With opt-in + fake provider: writes parseable teacher rows (bin in `trivial|standard|hard|frontier` + silver P(success) per eligible id). Invalid cheap output retries once, then escalate, else unlabeled — never fake bins/silver.
- [ ] Paid calls hit the request cache; reruns do not spend again.
- [ ] Shares the existing spend file and budget limiter. Does not change default `BUDGET_LIMIT_USD` in code from 15.
- [ ] Teacher set excludes providers of the measured trio ∪ live fallback. Escalate teacher is GLM; cheap teacher is Motif.
- [ ] Bloom, if present, stays on the offline teacher row only — not a live Decision field.
- [ ] Default run size is capped at ~800–1000 query-only rows (ceiling, not a production floor).
