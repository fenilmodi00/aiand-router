@echo off
cd /d D:\aiand-router
set AIAND_TRAIN=1
set BUDGET_LIMIT_USD=51.181
set PYTHONPATH=src
D:\aiand-router\.venv\Scripts\python.exe -m aiand_router.train gold --queries data/queries_spec.jsonl --split promotion-holdout --dense --include-k3 --limit 150 --exclude data/gold_sparse.jsonl --out data/gold_k3_part_a.jsonl > data\gold_k3_part_a.log 2>&1
