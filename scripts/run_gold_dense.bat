@echo off
cd /d D:\aiand-router
set AIAND_TRAIN=1
set BUDGET_LIMIT_USD=47.568
set PYTHONPATH=src
D:\aiand-router\.venv\Scripts\python.exe -m aiand_router.train gold --queries data/queries_spec.jsonl --split dense-cal --dense --limit 300 --exclude data/gold_sparse.jsonl --out data/gold_dense.jsonl > data\gold_dense.log 2>&1
