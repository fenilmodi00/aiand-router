@echo off
cd /d D:\aiand-router
set AIAND_TRAIN=1
set BUDGET_LIMIT_USD=47.568
set PYTHONPATH=src
D:\aiand-router\.venv\Scripts\python.exe -m aiand_router.train gold --queries data/queries_spec.jsonl --split threshold-tune --limit 300 --out data/threshold_tune.jsonl > data\threshold_tune.log 2>&1
