# AIand Coding Router

OpenAI-compatible proxy that picks an [aiand](https://docs.aiand.com/) model per coding-agent step. Point OpenCode (or anything that speaks `/v1/chat/completions`) at this process and send `model: router/auto`.

See `DESIGN.md` for what we will and will not build. Also: `ARCHITECTURE.md`, `RESEARCH.md`, `SECURITY.md`, `CREDITS.md`. Production trained-router proposal (aiand staff, not this $15 demo): [`.scratch/trained-router/spec.md`](.scratch/trained-router/spec.md).

## How routing works

Hard constraints first (tools / JSON / streaming / context / max output / budget / AA present / optional latency cap). Then predicted success (AA index or measured) must clear the phase bar. K3 stays behind the premium floor unless `x-routing-effort: max`.

After that:

| Effort | Pick |
| --- | --- |
| `low` | cheapest eligible |
| `medium` / `high` (default medium) | highest Pioneer score |
| `max` | strongest AA |

Pioneer score = `0.40·success + 0.20·capability + 0.15·tools + 0.10·latency + 0.10·health − 0.05·cost`. It is in `X-Router-Reason` as `score=`. Max-regret still drops models far behind the best when the phase bar is ≥ 50.

There are **no free models**. Default medium prefers **Flash** (cheapest strong score). Qwen’s output is $3.20/1M, so it is not a cheap-first pick. Use `x-routing-effort: low` to force lowest blended unit cost (still Flash with current prices).

Phases: Draft names are first-class (`planning`, `code_generation`, `security_review`, `final_summary`, …). Flashlight short names (`discover`, `plan`, `edit`, `tool`, `debug`, `summarize`) still work. Missing `x-agent-phase` is normal.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Put your aiand key in `.env` as `AIAND_API_KEY`. Keep `ROUTER_API_KEY` as the key clients send here — never put the aiand key in OpenCode.

Soft budget (`BUDGET_LIMIT_USD`) defaults to **$15**. See `CREDITS.md` for the rehearsal / matrix / reserve split (plan, not a measured live total). Catalog list prices (USD / 1M tokens):

| Model | Input | Cached in | Output | Context |
| --- | ---: | ---: | ---: | ---: |
| `deepseek-ai/deepseek-v4-flash` | $0.15 | $0.08 | $0.25 | 1.0M |
| `google/gemma-4-31b-it` | $0.20 | $0.05 | $0.50 | 262K |
| `openai/gpt-oss-120b` | $0.15 | $0.08 | $0.60 | 131K |
| `qwen/qwen3.6-27b` | $0.32 | $0.20 | $3.20 | 262K |
| `motif-technologies/motif-3` | $0.50 | $0.20 | $2.00 | 262K |
| `moonshotai/kimi-k2.7-code` | $0.75 | $0.20 | $3.50 | 262K |
| `deepseek-ai/deepseek-v4-pro` | $1.00 | $0.25 | $2.50 | 1.0M |
| `zai-org/glm-5.2` | $1.00 | $0.30 | $4.00 | 1.0M |
| `moonshotai/kimi-k3` | $3.00 | $0.50 | $12.50 | 1.0M |

Motif-3 is on this org catalog (AA 47). K3 is listed too; still gated behind `x-routing-effort: max`. Keys: `SECURITY.md`. Optional `LATENCY_LIMIT_MS=0` means no latency hard filter.

```bash
uvicorn aiand_router.app:app --app-dir src --host 127.0.0.1 --port 8000
```

```bash
curl http://127.0.0.1:8000/v1/chat/completions ^
  -H "Authorization: Bearer change-me" ^
  -H "Content-Type: application/json" ^
  -d "{\"model\":\"router/auto\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}]}"
```

Optional headers:

- `x-agent-phase: plan|planning|edit|security_review|debug|summarize|...`
- `x-routing-effort: low|medium|high|max`
- `x-allowed-models: qwen/qwen3.6-27b,moonshotai/kimi-k2.7-code`
- `x-latency-limit: 800` (ms; overrides `LATENCY_LIMIT_MS`)

## OpenCode

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "aiand-router": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "AIand Router",
      "options": {
        "baseURL": "http://127.0.0.1:8000/v1",
        "apiKey": "change-me"
      },
      "models": {
        "router/auto": { "name": "router/auto" }
      }
    }
  }
}
```

The response body keeps `model: router/auto`. The real aiand id is on `X-Router-Model` (plus phase, Pioneer `score=`, threshold, candidates) and in `data/requests.jsonl`.

## Trained path

Default `TRAINED_PATH` is **`shadow`**: the client still gets the rules pick; JSONL and `X-Router-Trained-Would` record what the trained hop would have chosen. Set `TRAINED_PATH=trained` to serve the cheapest eligible model that clears effort threshold and max_regret. `TRAINED_PATH=off` is today’s rules path (learned stub only if `learned_wins.json` says so). Invalid values are treated as shadow.

Scorer weights load from `SCORER_PATH` (default `data/scorer.json`) at process start. Missing or corrupt weights fall back to rules with reason_code `scorer_down` — they do not invent P(success).

There is also a disabled-by-default `cascade_lane` config prototype for `TRAINED_PATH=off` only. It is a binary scorer-backed lane between one configured cheap model and one configured strong model: serve the cheap lane only if it clears the existing effort threshold and stays within the existing max_regret of the strong lane; otherwise pass through to the strong lane. It does not alter the default Pioneer-shaped shadow path.

Opt-in train (not CI; shares `BUDGET_LIMIT_USD`, default **15** in code — set `100` in the environment for the smoke fit):

```bash
set AIAND_TRAIN=1
python -m aiand_router.train teacher --queries queries.jsonl --out data/silver.jsonl
python -m aiand_router.train gold --queries queries.jsonl --out data/gold.jsonl
python -m aiand_router.train fit --gold data/gold.jsonl --silver data/silver.jsonl --out data/scorer.json
```

The `$100` smoke artifact is labeled `not_spec_floors`. It is not Pioneer quality and not the SWE-bench Verified promotion gate. Savings, when logged, are versus `most_expensive_eligible` on that request — never an invented percentage.

## Flashlight demo

A ~200-line client walks discover → plan → edit → test → fix → summarize against this gateway. It reports `{tests_passed, patch_applied}` after the test step so a failing seed can escalate on debug.

```bash
python -m aiand_router.flashlight
```

Then open `http://127.0.0.1:8000/replay`. The page reads the request log (phase, candidates, winner, reason, cost, test outcome). It never renders API keys.

Add `--hard` only after the first seed is green.

AA Intelligence Index scores in the registry are public priors (`measured_on: not_aiand`), not quality measured on aiand. Measured numbers on the replay/eval report come from the request cache/log only.

## Measured comparison

Same five seeded tasks, three executed baselines (premium-only, Kimi-only, adaptive). Other baseline names are stubs and are not run. The command prints costs and models from the request log and will not invent a savings percentage.

```bash
python -m aiand_router.eval
```

Learned routing stays off until `python -m aiand_router.learn` says it beat rules on the held-out slice of that cache.

## Opt-in aiand smoke

Not CI. Spends real credits. One streamed tool-call through this gateway to aiand:

```bash
set AIAND_SMOKE=1
python -m aiand_router.smoke
```

Or curl (gateway already running, `AIAND_API_KEY` in `.env`):

```bash
curl http://127.0.0.1:8000/v1/chat/completions ^
  -H "Authorization: Bearer change-me" ^
  -H "x-agent-phase: discover" ^
  -H "Content-Type: application/json" ^
  -N ^
  -d "{\"model\":\"router/auto\",\"stream\":true,\"messages\":[{\"role\":\"user\",\"content\":\"Call list_files on . then stop.\"}],\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"list_files\",\"parameters\":{\"type\":\"object\",\"properties\":{\"path\":{\"type\":\"string\"}}}}}]}"
```

A good run streams tokens (or a tool call) to the terminal. `data/spend.txt` and `data/requests.jsonl` record it. Do not run this unless you own the credits.
