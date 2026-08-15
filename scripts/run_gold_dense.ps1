$env:PYTHONPATH = "src"
$env:AIAND_TRAIN = "1"
$env:TRAIN_CONCURRENCY = "8"
$env:BUDGET_LIMIT_USD = "14.38"
& ".venv\Scripts\python.exe" -m aiand_router.train gold --queries data/queries_spec.jsonl --out data/gold_dense.jsonl --dense --limit 300 --exclude data/gold_sparse.jsonl 2>&1 | Tee-Object -FilePath data/gold_dense_run.log
