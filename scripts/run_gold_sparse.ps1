$env:PYTHONPATH = "src"
$env:AIAND_TRAIN = "1"
$env:TRAIN_CONCURRENCY = "8"
$env:BUDGET_LIMIT_USD = "30.7149276733398"
& ".venv\Scripts\python.exe" -m aiand_router.train gold --queries data/queries_spec.jsonl --out data/gold_sparse.jsonl --limit 2000 2>&1 | Tee-Object -FilePath data/gold_sparse_run.log

