# Hard-y gold probe: verified-like pool -> sparse gold -> geometry kill/pass.
# Default is dry-run (pool + cost preflight only). Pass -Paid to spend (requires AIAND_TRAIN=1).
param(
    [switch]$Paid,
    [int]$Limit = 40,
    [int]$Seed = 11,
    [string]$Smith = "data/smith-tool-sample.jsonl",
    [string]$Tasks = "data/smith-task-checks.jsonl",
    [string]$Eval = "data/gold-verified.jsonl",
    [string]$Queries = "data/pool-hard-mix-kimi-only-targeted.jsonl",
    [float]$BudgetCap = 15.0,
    [string]$SpendFile = "data/spend.txt",
    [string[]]$ExcludeGold = @(
        "data/gold-sparse-hard-mix1.jsonl",
        "data/gold-sparse-hard-mix1-train.jsonl",
        "data/gold-sparse-hard-mix1-retune.jsonl",
        "data/gold-sparse-hard-mix1-topup32.jsonl",
        "data/gold-sparse-hard-probe-seed11.jsonl",
        "data/gold-sparse-hard-probe-seed12.jsonl",
        "data/gold-sparse-hard-probe-seed13.jsonl",
        "data/gold-sparse-hard-probe-seed14.jsonl"
    ),
    [int]$MinFailToPass = 2,
    [int]$MaxFailToPass = 4,
    [double]$NearMissLo = 0.55,
    [double]$NearMissHi = 0.88
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src"
$Py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

$PoolOut = "data/pool-hard-mix-near_miss_seed$Seed.jsonl"
$GoldOut = "data/gold-sparse-hard-probe-seed$Seed.jsonl"
$LogOut = "data/gold-sparse-hard-probe-seed$Seed.log"

Write-Host "=== hard-y probe (seed=$Seed limit=$Limit paid=$Paid) ==="

# 1) Sample from unpaid mix1like dump pool (default Queries), or rebuild from --smith
#    when -Queries is explicitly empty.
if ($Queries) {
    if (-not (Test-Path $Queries)) {
        Write-Host "refusing: -Queries file not found: $Queries"
        exit 2
    }
    $PoolOut = "data/pool-hard-mix-near_miss_seed$Seed.jsonl"
    Write-Host "sampling Mix1-like n=$Limit seed=$Seed from $Queries -> $PoolOut"
    $excl = @()
    foreach ($g in $ExcludeGold) {
        if (Test-Path $g) { $excl += @("--exclude", $g) }
    }
    & $Py scripts/hard_y_probe.py sample `
        --queries $Queries `
        --out $PoolOut `
        --limit $Limit `
        --seed $Seed `
        --max-fail-to-pass $MaxFailToPass `
        --near-miss-lo $NearMissLo `
        --near-miss-hi $NearMissHi `
        --min-expected-len 24 `
        --max-expected-len 80 `
        --min-fail-to-pass $MinFailToPass `
        @excl
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    & $Py -m aiand_router.train pool `
        --smith $Smith `
        --tasks $Tasks `
        --eval $Eval `
        --out $PoolOut `
        --n $Limit `
        --verified-like `
        --prompt-family flashlight `
        --seed $Seed `
        --verified-like-max-tokens 200 `
        --near-miss-lo $NearMissLo `
        --near-miss-hi $NearMissHi `
        --min-expected-len 24 `
        --max-fail-to-pass $MaxFailToPass
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# 2) Cost preflight (refuse before paid if over cap)
$spendBefore = 0.0
if (Test-Path $SpendFile) {
    $spendBefore = [double](Get-Content $SpendFile -Raw).Trim()
}
$budgetLimit = $spendBefore + $BudgetCap
$env:BUDGET_LIMIT_USD = "$budgetLimit"
Write-Host "spend_before=$spendBefore budget_cap=$BudgetCap budget_limit=$budgetLimit"

& $Py scripts/hard_y_probe.py preflight `
    --pool $PoolOut `
    --eval $Eval `
    --spend $SpendFile `
    --budget-cap $BudgetCap `
    --limit $Limit
if ($LASTEXITCODE -ne 0) {
    Write-Host "refusing: preflight failed (over budget cap)"
    exit $LASTEXITCODE
}

if (-not $Paid) {
    Write-Host "dry-run complete (no gold spend). Re-run with -Paid and `$env:AIAND_TRAIN='1' to label."
    Write-Host "geometry after gold: $Py -m aiand_router.geometry --train $GoldOut --eval $Eval"
    exit 0
}

if ($env:AIAND_TRAIN -ne "1") {
    Write-Host "refusing: set `$env:AIAND_TRAIN='1' for paid gold"
    exit 2
}

if (-not $env:TRAIN_CONCURRENCY) { $env:TRAIN_CONCURRENCY = "10" }

# 3) Paid sparse gold (issue-02 y; cache-first)
& $Py -m aiand_router.train gold `
    --queries $PoolOut `
    --out $GoldOut `
    --limit $Limit `
    2>&1 | Tee-Object -FilePath $LogOut
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 4) Geometry kill/pass (unpaid)
& $Py -m aiand_router.geometry --train $GoldOut --eval $Eval
$geoExit = $LASTEXITCODE

Write-Host ""
Write-Host "=== probe decision ==="
Write-Host "gold: $GoldOut"
Write-Host "If geometry_pass=true, run: .\scripts\run_hard_y_refit.ps1 -TrainGold $GoldOut"
if ($geoExit -ne 0) {
    Write-Host "geometry module returned non-zero; inspect JSON kill/geometry_pass flags above."
}
exit $geoExit
