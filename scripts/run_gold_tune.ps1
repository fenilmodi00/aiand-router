$env:PYTHONPATH = "src"
$env:AIAND_TRAIN = "1"
$env:TRAIN_CONCURRENCY = "8"
$env:BUDGET_LIMIT_USD = "15.392172"
& ".venv\Scripts\python.exe" -m aiand_router.train gold --queries data/queries_tune.jsonl --out data/tune.jsonl --limit 300 2>&1 | Tee-Object -FilePath data/tune_run.log
