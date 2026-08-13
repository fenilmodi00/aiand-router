# Mission: Live trained hop

**Status (2026-08-13): smoke Scorer fit is undone.** `GET /v1/models` works; `POST /v1/chat/completions` returns 404 `model_not_found` for every catalog id (Flash, Motif, GLM, …). Spend stayed $0. Rules path is still the live pick. Resume teacher → gold → fit when a playground completion returns 200. Query file: `datasets/train-queries.jsonl`.

## Why
I already have an OpenAI-compatible coding router. I want coding-agent clients (OpenCode and anything that speaks `/v1/chat/completions`) to point at this process with `model: router/auto` and get real routed completions — first on the rules path, then on a Pioneer-shaped trained path once a Scorer exists and shadow looks sane. Success is a live hop I can use, not a second product and not a Pioneer clone.

## Success looks like
- Start this gateway locally and have a client complete a `router/auto` request through it
- Read `X-Router-Path` / `data/requests.jsonl` and know whether that hop was `rules`, `shadow`, or `trained`
- Fit a `not_spec_floors` Scorer (opt-in, budget-capped) and watch shadow before flipping `TRAINED_PATH=trained`
- Keep the rules path as fallback; never treat smoke weights as the Verified promotion gate

## Constraints
- Windows / PowerShell
- About $100 of aiand credits for a smoke fit — not production gold-matrix floors
- Default code budget stays $15; smoke at $100 is an operator env, not a code default
- Clients must keep talking to `/v1/chat/completions`; no new protocol

## Out of scope
- Flashlight agents, OpenCode snippets, playgrounds, Pioneer dashboard clone
- Production floors: n=4000 sparse, n≥300 retune, SWE-bench Verified, Terminal-Bench
- Operating multi-tenant aiand infra, Nginx/Gunicorn production topology
- Invented savings percentages
