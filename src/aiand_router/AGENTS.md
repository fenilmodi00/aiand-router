# src/aiand_router — Gateway Core

**Generated:** 2026-08-21
**Commit:** 492a192
**Branch:** v0

## OVERVIEW

FastAPI proxy + routing policy + trained scorer. One `src/` package holds the entire backend — no sub-packages.

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Gateway, headers, JSONL | `app.py` | `create_app` (L101), `_router_headers`, `_jsonl_row` |
| Rules router | `router.py` | `select_model`, `eligible_models`, `pioneer_score`, `detect_phase` |
| Trained scorer | `scorer.py` | `score_eligible`, `trained_select`, `apply_trained_path`, `featurize` |
| Pool / ingest | `pool.py` | `build_pool`, `collision_keys`, `ingest_spec` — 83 functions, largest module |
| Promotion gate | `promotion_gate.py` | Shadow vs rules comparison, §(a) bar source |
| Training fit | `fit.py` / `train.py` | GBDT + isotonic fit, teacher → gold → fit |
| Geometry / eval | `geometry.py` / `eval.py` | 3×5 cache analysis, 3 executed baselines |
| Flashlight demo | `flashlight.py` | ~200-line discover→summarize loop |
| File contexts | `git_file_context.py`, `docker_file_context.py` | Never read gold patches |
| Replay console | `replay_report.py`, `replay.html` | `data/requests.jsonl` → HTML |

## CONVENTIONS

- Single package `aiand_router` under `src/`; imported as `aiand_router.*` via `pytest.ini: pythonpath=src`.
- No `pyproject.toml` — deps in `requirements.txt`, all config is YAML (`config/models.yaml`) + env.
- `router.py` is the policy authority; `scorer.py` shares its `EligibleSet` via `build_eligible_set` — never duplicate eligibility.

## ANTI-PATTERNS

- Never duplicate `eligible_models` logic in `scorer.py` — use `build_eligible_set` from `router.py`.
- Never read gold in `git_file_context` / `docker_file_context` / `pool.ingest_path`.
- Never invent `P(success)` when `load_scorer` fails — fall back to rules (`scorer_down`).
- Never call aiand directly from `router.py` — `provider.py` owns auth (`AIAND_API_KEY`).
