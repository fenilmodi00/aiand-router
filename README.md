# AIand Coding Router

OpenAI-compatible proxy that picks an [aiand](https://docs.aiand.com/) model per coding-agent step. Point OpenCode (or anything that speaks `/v1/chat/completions`) at this process and send `model: router/auto`.

See `DESIGN.md` for what we will and will not build. Also: `ARCHITECTURE.md`, `RESEARCH.md`, `SECURITY.md`, `CREDITS.md`.

## How routing works

Hard constraints first (tools / JSON / streaming / context / max output / budget / AA present / Motif-3 off / optional latency cap). Then predicted success (AA index or measured) must clear the phase bar. K3 stays behind the premium floor unless `x-routing-effort: max`.

After that:

| Effort | Pick |
| --- | --- |
| `low` | cheapest eligible |
| `medium` / `high` (default medium) | highest Pioneer score |
| `max` | strongest AA |

Pioneer score = `0.40·success + 0.20·capability + 0.15·tools + 0.10·latency + 0.10·health − 0.05·cost`. It is in `X-Router-Reason` as `score=`. Max-regret still drops models far behind the best when the phase bar is ≥ 50.

Default medium therefore prefers **Flash** on summarize/discover, not free Qwen. Use `x-routing-effort: low` for cheap-first.

Phases: Draft names are first-class (`planning`, `code_generation`, `security_review`, `final_summary`, …). Flashlight short names (`discover`, `plan`, `edit`, `tool`, `debug`, `summarize`) still work. Missing `x-agent-phase` is normal.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Put your aiand key in `.env` as `AIAND_API_KEY`. Keep `ROUTER_API_KEY` as the key clients send here — never put the aiand key in OpenCode.

Soft budget (`BUDGET_LIMIT_USD`) defaults to **$15**. See `CREDITS.md` for the rehearsal / matrix / reserve split (plan, not a measured live total). Qwen is $0 on the catalog but is not the default adaptive pick. Do not press max-effort until you have confirmed K3 on your org catalog ($3 / $12.50 per 1M). Keys: `SECURITY.md`. Optional `LATENCY_LIMIT_MS=0` means no latency hard filter.

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
