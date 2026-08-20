# 08 — Manual flip to path=trained

**What to build:** Operator-owned TRAINED_PATH=trained after a green cost-meaningful replay. Language is “shadow looks like a real router,” not “Verified promoted.” Production n=4000 / n≥300 Verified gate stays a later staffed bar. JSONL/headers still show path. apply_replay_gate never auto-flips.

**Blocked by:** 06 — Dual replay (only if the gate passes; 07 if it was taken and then passed)

**Status:** **done** — operator flip applied locally after issue 06 `replay_gate_pass=true`. Artifact stays `not_spec_floors` (not a Verified promotion claim).

- [x] Taken only after 06 (and 07 if used) is green on transfer and cost-meaningful cost_delta
- [x] Flip is manual; apply_replay_gate never auto-flips — **operator action done** (local `.env`; code default still shadow if unset)
- [x] Artifact may stay not_spec_floors; no SWE-bench Verified promotion claim
- [x] Clients unchanged: model router/auto, streaming/tools/missing phase, pinned catalog ids still bypass auto-select

## Flip command (PowerShell — run only when ready to serve trained)

```
# After replay_gate_pass=true on dual report; still shadow by default until this env is set:
$env:TRAINED_PATH="trained"
$env:SCORER_PATH="data/scorer-hard-logistic.json"
# Confirm JSONL/headers show path=trained; apply_replay_gate must never set this itself.
# Revert: $env:TRAINED_PATH="shadow"  (or unset)
```

Do **not** claim production Verified floors. Language: shadow/trained hop looks like a real router on the local dual holdout.

## Answer

**Where set**
- Local gitignored `.env`: `TRAINED_PATH=trained`, `SCORER_PATH=data/scorer-hard-logistic.json` (runtime via `load_dotenv()` in `app.py`).
- Documented in `.env.example` (same keys, no secrets) and `NOTES.md`.
- `apply_replay_gate` still always stamps `path=shadow` / `not_spec_floors=true` — never writes these env vars.

**Smoke (FakeProvider, unpaid)**
- `load_scorer(data/scorer-hard-logistic.json)` → ok (`n_cal=664`, `not_spec_floors=true`).
- `create_app(..., trained_path=trained, scorer_path=hard artifact, config/models.yaml)` → HTTP 200, `x-router-path=trained`, JSONL `path=trained`, served `moonshotai/kimi-k2.7-code`.
- Env-driven `create_app` (no explicit path args, after `load_dotenv`) → also `x-router-path=trained`.

**Operator start next time**
1. Ensure `.env` has the two lines above (or set the PowerShell env for the session).
2. Start the gateway as usual (`python -m aiand_router` / project runbook); dotenv loads trained + hard logistic artifact.
3. Grep JSONL / headers for `path=trained`. Revert with `TRAINED_PATH=shadow` (or unset).

**Caveats**
- Artifact `not_spec_floors=true` — not a SWE-bench Verified promotion; production n=4000 / n≥300 staffed bar remains later.
- Dual-replay green used small-n equal-mass ECE waiver (`n_selected=72 < 150`); equal-width ECE gated; no H3 cost waiver.
- Code default remains `shadow` if env unset; CI / other machines stay shadow unless they copy the flip.
