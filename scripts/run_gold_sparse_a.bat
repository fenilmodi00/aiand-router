@echo off
set AIAND_TRAIN=1
set BUDGET_LIMIT_USD=38.021
set PYTHONPATH=src
D:\aiand-router\.venv\Scripts\python.exe -m aiand_router.train gold --queries data/queries_spec.jsonl --split sparse-train --limit 1000 --out data/gold_sparse_part_a.jsonl > data\gold_sparse_part_a.log 2>&1
