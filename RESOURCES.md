# Trained-hop go-live resources

## Knowledge

- [Spec: Pioneer-grade trained hop](.scratch/trained-hop/spec.md)
  The contract for this cycle: shadow default, `TRAINED_PATH=trained` only after shadow looks sane, `$100` smoke is `not_spec_floors`, not Verified. Use for: any go-live decision on this repo.
- [README — Trained path](README.md#trained-path)
  Operator commands: `TRAINED_PATH`, `SCORER_PATH`, opt-in `AIAND_TRAIN=1` teacher/gold/fit. Use for: the exact CLI to run.
- [Glossary: CONTEXT.md](CONTEXT.md)
  Canonical names (`trained router`, `Scorer`, `scorer_down`, `success gold`, `promotion gate`). Use for: wording in lessons and JSONL greps.
- [Proposal: production trained coding router](.scratch/trained-router/spec.md)
  Staff-grade floors and the real promotion order (train → calibrate → retune → shadow → gate → live). Use for: knowing what this `$100` hop is *not*.
- [FastAPI: Deployment](https://fastapi.tiangolo.com/deployment/)
  What “deploy” means (a stable process users can reach) vs a dev loop. Use for: not confusing `uvicorn` on localhost with a production control plane.
- [Uvicorn](https://www.uvicorn.org/)
  The ASGI server this README already uses. Use for: `--host` / `--port` / `--app-dir`.
- [OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat/create)
  The wire this gateway mimics (`POST /v1/chat/completions`). Use for: client body/headers, not routing policy.
- [JSON Lines](https://jsonlines.org/)
  One JSON value per line. Use for: `queries.jsonl` / silver / gold / request log shape.
- [Research: teacher labeling](.scratch/trained-router/research/teacher-labeling.md)
  Why a chat teacher can label bins from the query (silver) but cannot replace running candidates (gold). Use for: the teacher vs gold distinction.
- [Research: bootstrap datasets](.scratch/trained-router/research/bootstrap-datasets.md)
  Public SWE / router corpora and why Verified/Terminal-Bench stay gates, not this smoke train set. Use for: not copying eval benches into `queries.jsonl`.
- [AIand Chat Completions](https://docs.aiand.com/api/chat-completions/)
  The provider the train CLI actually POSTs to. Use for: teacher/gold are ordinary chat calls, offline, not the live hop.

## Wisdom (Communities)

- [FastAPI GitHub Discussions](https://github.com/fastapi/fastapi/discussions)
  High-signal questions about serving ASGI apps. Use for: process/bind/proxy issues, not routing policy.
- Local: this repo’s `data/requests.jsonl` after a real client hop
  The only place *this* router’s policy is visible. Use for: `path=shadow` vs `path=trained` vs `path=rules`.

## Gaps

- Starter smoke prompts exist at `datasets/smoke-queries.jsonl` (48 rows). Still no production dump at teacher ≤1000 / gold ≤200.
- No production runbook (Nginx, systemd, TLS). Intentionally out of scope for the hop spec.
- Landing-page SWE-Bench “62% cost reduction” / “40–60% token savings” are marketing visuals — no matching measured Verified gate report in this repo to cite as fact.

## Pitch knowledge (Mahakaathan)

- [Lesson: 6-minute technical fluency](lessons/0005-pitch-technical-fluency.html)
  Timed pitch + quiz on safe claims. Use for: rehearsal before judges.
- [Reference: pitch card](reference/pitch-six-minute.html)
  One-page SAFE numbers + code map. Use for: print beside monitor.
- [Deck: hackathon submission](lessons/0004-hackathon-submission.html)
  6-page judging-criteria deck. Use for: slide order, not live ML oversell.
- [ARCHITECTURE.md](ARCHITECTURE.md)
  Gateway diagram. Use for: “where does a request go?”
- [Landing page source](web/app/page.tsx) · [Trained vs rules UI](web/components/TrainedVsRulesSection.tsx)
  What judges see on `:3000/`. Use for: matching demo narration to UI copy — then soften marketing %.
- [data/scorer.json](data/scorer.json) · [data/spend.txt](data/spend.txt) · [data/replay-results.json](data/replay-results.json)
  Artifact floors and spend file. Use for: measured pitch numbers only.
