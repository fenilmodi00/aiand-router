# Pioneer-grade trained hop

Type: wayfinder:map
Status: resolved

## Destination

The existing FastAPI gateway grows a **trained path** beside rules: complexity bin → calibrated P(success) → cheapest that clears threshold + max_regret. Default serve is `path=shadow`. `$100` buys a labeled **smoke** Scorer (`not_spec_floors`), not Pioneer quality and not the Verified gate.

Spec: [`spec.md`](spec.md). Glossary: [`CONTEXT.md`](../../CONTEXT.md). Production floors stay in [`.scratch/trained-router/spec.md`](../trained-router/spec.md).

## Locked ticket cuts

- Keep **01 / 02 split**. Shadow plumbing first; live pick second. Two agents sequence the gateway, they do not edit it in parallel.
- Do **not** split 02 into pick-vs-scorer_down. One HTTP policy slice.
- **04 waits on 02 and 03.** Fixture load from 01 is the Scorer interface; do not spend gold credits until shadow + trained + scorer_down are green, and silver labels exist.

Seam for 01–02: `POST /v1/chat/completions` on `create_app` + fake aiand upstream. No second HTTP stack.

## Frontier

All tickets resolved. Fit is intercept-only mean gold (`not_spec_floors`); a feature logistic + Platt is the upgrade when smoke n is not enough.

## Tickets

- [01 — Shadow path with fixture Scorer](issues/01-shadow-path-fixture-scorer.md)
- [02 — Live trained pick, effort, scorer_down, named savings](issues/02-trained-pick-effort-scorer-down.md)
- [03 — Opt-in teacher CLI (silver labels)](issues/03-opt-in-teacher-cli.md)
- [04 — Mini gold, Rec A smoke fit, loadable artifact](issues/04-mini-gold-rec-a-fit.md)
- [05 — README trained-path section](issues/05-readme-trained-path.md)
