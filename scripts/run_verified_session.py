#!/usr/bin/env python
"""Run Verified session-gold shadow sessions (runbook §(a)).

Unpaid plumbing (instance context + honest labels):
  $env:PYTHONPATH='src'
  python scripts/run_verified_session.py --dry-run --limit 5 --no-fetch `
    --instances tests/fixtures/verified_instances/instances.jsonl
  python scripts/run_verified_session.py --offline-gold tests/fixtures/verified_instances/offline_gold.jsonl `
    --instances tests/fixtures/verified_instances/instances.jsonl --limit 2 `
    --out data/verified_offline_gold_smoke.jsonl --no-fetch

PowerShell paid smoke (operator budget + gateway; resolve still null without docker):
  $env:PYTHONPATH='src'
  # Terminal 1 — shadow gateway:
  $env:TRAINED_PATH='shadow'
  $env:SCORER_PATH='data/scorer-hard-logistic.json'
  $env:UPSTREAM_TIMEOUT_S='300'
  uvicorn aiand_router.app:app --app-dir src --host 127.0.0.1 --port 8000
  # Terminal 2 — unpaid plan:
  python scripts/run_verified_session.py --dry-run --limit 500
  # Terminal 2 — paid smoke (limit 1–2 ONLY after budget headroom; spend is ~$15.65):
  python scripts/run_verified_session.py --limit 1 --out data/verified_session_smoke.jsonl
  # Expect: problem_statement in hops when instances dump/HF cache is present;
  # resolved=null, label_type=needs_swe_eval, session_gold=false without SWE_EVAL_CMD.

  # True session gold — thin hook (default local = honest not_available until swebench+docker):
  $env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'
  # Disk-light remote: $env:SWE_EVAL_BACKEND='modal'  # or 'sb-cli' + SWEBENCH_API_KEY
  # Unpaid mock only (never promotion evidence):
  # $env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file} --mock-resolved true'
  # Real local resolve: install Docker + `pip install swebench`, then use the default SWE_EVAL_CMD above.

  # Gate check:
  python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_smoke.jsonl
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aiand_router.verified_runner import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
