# scripts — CI Gates + Budget-Capped Orchestration

**Generated:** 2026-08-21
**Commit:** 492a192
**Branch:** v0

## OVERVIEW

Local CI replacement: `check_*.py` gates (run without subprocess in tests) + `run_*.ps1` paid orchestration (budget-capped, not time-capped). No `.github/workflows`.

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Pool / ingest gates | `check_pool_spec.py`, `check_ingest_spec.py` | Stratum + collision enforcement |
| Training gates | `check_gold_dense.py`, `check_scorer_fit.py`, `check_teacher.py`, `check_tune.py` | Gold slice + threshold tuning |
| Runtime gates | `check_canary.py`, `check_metrics.py`, `check_monitor.py`, `check_retrain.py` | Canary + budget + retune |
| Paid runs | `run_*.ps1` (budget $15–$30) | Set `BUDGET_LIMIT_USD` + `AIAND_TRAIN=1`, call `python -m aiand_router.train` |
| PowerPoint gen | `gen_hackathon_ppt.py`, `gen_ideathon_ppt.py` | Slide generation, not CI |
| Hooks | `claude_code_hook.sh` | Claude Code stop hook, not CI |

## CONVENTIONS

- Gates expose `build_report() -> dict` for direct import in `tests/test_*_preflight.py` — no subprocess.
- Orchestration is PowerShell (`run_*.ps1`) with hardcoded `BUDGET_LIMIT_USD` (16.585, 14.38, etc.) — cost-capped, operator-owned.
- Tests load scripts via `importlib.util.spec_from_file_location`, not `subprocess.run`.

## ANTI-PATTERNS

- Never run `run_*.ps1` in CI without owning the aiand credits — they spend real money.
- Never add a job that trains on eval-only dumps — `collision_keys` must be checked first.
- Never invent savings % in gate output — always vs `most_expensive_eligible`.
