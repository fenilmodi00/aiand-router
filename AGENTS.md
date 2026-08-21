# PROJECT KNOWLEDGE BASE

**Generated:** 2026-08-21
**Commit:** 492a192
**Branch:** v0

## OVERVIEW

OpenAI-compatible gateway that routes each coding-agent step to the cheapest capable aiand model. Python FastAPI proxy (`router/auto`) + Next.js marketing/playground. Hard constraints → phase bar → Pioneer score (or trained threshold) → pick.

## STRUCTURE

```
aiand-router/
├── src/aiand_router/   # gateway, router, scorer, pool, training pipeline
├── web/                # Next.js 16 / React 19 / Tailwind 4 marketing + playground
├── scripts/            # check_*.py CI gates + run_*.ps1 budget-capped orchestration
├── tests/              # pytest suite (22 modules, ~400 tests), fixtures in tests/fixtures/
├── config/             # models.yaml (catalog) + tasks.yaml
├── data/               # JSONL logs, scorer weights (gitignored)
├── demo/seed*          # 5 seeded tasks the flashlight demo solves
├── docs/               # DESIGN.md (locked), ARCHITECTURE.md, RESEARCH.md
└── .scratch/           # working notes (tracked .md only)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Routing policy | `src/aiand_router/router.py` | `select_model`, `eligible_models`, `pioneer_score`, `detect_phase` |
| Gateway / headers | `src/aiand_router/app.py` | FastAPI `create_app`, `X-Router-*`, JSONL, shadow path |
| Trained hop | `src/aiand_router/scorer.py` | `score_eligible`, `trained_select`, `apply_trained_path` |
| Training pipeline | `src/aiand_router/train.py`, `fit.py` | teacher → gold → fit |
| Pool / ingest | `src/aiand_router/pool.py` | bootstrap dump stratum sampling |
| Promotion gate | `src/aiand_router/promotion_gate.py` | shadow vs rules comparison |
| Flashlight demo | `src/aiand_router/flashlight.py` | discover→plan→edit→test loop |
| Eval baseline | `src/aiand_router/eval.py` | 3 executed baselines over 5 seeds |
| Web playground | `web/app/playground/`, `web/components/` | Next.js routes + shadcn/ui |
| Config catalog | `config/models.yaml` | 9 models, AA priors, effort knobs |
| Tests | `tests/` | `conftest.py` forces `TRAINED_PATH=shadow` |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `create_app` | func | `src/aiand_router/app.py:101` | FastAPI factory, all routes |
| `select_model` | func | `src/aiand_router/router.py:398` | Rules pick: eligible → bar → score |
| `eligible_models` | func | `src/aiand_router/router.py:234` | Hard constraints filter |
| `detect_phase` | func | `src/aiand_router/router.py:165` | Header + heuristic phase detection |
| `pioneer_score` | func | `src/aiand_router/router.py:469` | 0.40·success + weighted blend |
| `score_eligible` | func | `src/aiand_router/scorer.py:268` | Trained: featurize + calibrate + P(success) |
| `trained_select` | func | `src/aiand_router/scorer.py:612` | Cheapest above threshold/max_regret |
| `build_pool` | func | `src/aiand_router/pool.py:696` | Stratum-sampled bootstrap pool |
| `SpendLog` | class | `src/aiand_router/router.py:495` | Budget-gated cost tracking |
| `load_config` / `load_models` | func | `src/aiand_router/router.py:127` | YAML catalog loading |

## CONVENTIONS

- `src/` layout, no `pyproject.toml` — `requirements.txt` + `pytest.ini` (`pythonpath=src`, `testpaths=tests`).
- Python 3.14, FastAPI + uvicorn + httpx + pydantic v2 + pyyaml.
- Web: Next.js 16.3, React 19, Tailwind 4, shadcn/ui, both `bun.lock` and `package-lock.json` tracked.
- No CI (`.github/workflows` absent) — CI is `scripts/check_*.py` gates run locally + `scripts/run_*.ps1` budget-capped orchestration.
- Tests use `importlib.util.spec_from_file_location` to load `scripts/*.py` directly (no subprocess).

## ANTI-PATTERNS (THIS PROJECT)

- Never invent savings % — always vs `most_expensive_eligible` logged per request.
- Never train/calibrate/threshold-tune on eval-only dumps (SWE-bench family, Terminal-Bench, Multi-SWE-bench) — `pool.py:collision_keys` enforces.
- Never set `TRAINED_PATH=trained` — promotion-gate/operator-owned only; tests force `shadow` via `conftest.py`.
- Never consult gold patches — file-context helpers (`git_file_context`, `docker_file_context`) never read gold.
- Never change code-default `$15` budget — `BUDGET_LIMIT_USD` override is env-only.
- Never put `AIAND_API_KEY` in `web/.env.local` — stays in Python `src` process only.
- Never use `TRAINED_PATH` from `.env` in tests — `tests/conftest.py` clamps to `shadow`.

## UNIQUE STYLES

- Glossary-precise naming: see `CONTEXT.md` — `success gold` vs `silver P(success)` vs `calibrated P(success)`, `threshold-tuning split` vs `dense gold slice` vs `production retune holdout` are not interchangeable.
- Phase vocabulary: Draft names (`code_generation`, `security_review`) are first-class; flashlight shorts (`edit`, `debug`) alias into the same family via `router.py:detect_phase`.
- `trajectory` is an ordered JSONL replay, not a generic log — ordering + truncation semantics matter (`replay_report.py`).

## COMMANDS

```bash
# Gateway
pip install -r requirements.txt
copy .env.example .env          # set AIAND_API_KEY + ROUTER_API_KEY
uvicorn aiand_router.app:app --app-dir src --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/v1/chat/completions -H "Authorization: Bearer change-me" -d '{"model":"router/auto","messages":[{"role":"user","content":"ping"}]}'

# Tests (no coverage plugin installed)
python -m pytest                # ~400 tests, auto shadow-isolated
python -m aiand_router.smoke    # opt-in, spends real credits (AIAND_SMOKE=1)

# Web
cd web && npm run dev           # Next.js dev
cd web && npm run typecheck && npm run lint && npm run build
```

## NOTES

- `data/requests.jsonl` + `data/spend.txt` are the live log/budget — `app.py:rotate_local_data_if_key_changed` rotates on `ROUTER_API_KEY` change.
- Two web lockfiles (`bun.lock` + `package-lock.json`) — intentional; do not delete one without checking install path.
- `.scratch/*.md` is tracked, `.scratch/*.py|*.json` is gitignored — working notes survive, artifacts do not.
- LSP not installed in this env (42 servers configured, 0 active) — `get_file_skeleton` covers code map.
