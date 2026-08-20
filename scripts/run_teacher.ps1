$env:PYTHONPATH = "src"
$env:AIAND_TRAIN = "1"
$env:TRAIN_CONCURRENCY = "8"
$env:BUDGET_LIMIT_USD = "16.585"
& ".venv\Scripts\python.exe" -m aiand_router.train teacher --queries data/queries_spec.jsonl --out data/silver.jsonl 2>&1 | Tee-Object -FilePath data/teacher_run.log
