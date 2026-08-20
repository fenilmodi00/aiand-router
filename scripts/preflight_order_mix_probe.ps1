# Unpaid order-mix conservative dry-run preflight (no aiand credits).
param(
    [int]$Seed = 16,
    [int]$Limit = 32,
    [switch]$WritePool,
    [string]$Report = ".scratch/scorer-pioneer-lift/order-mix-preflight-2026-08-20.md"
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src"
$Py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

$argsList = @("scripts/order_mix_preflight.py", "--seed", $Seed, "--limit", $Limit)
if ($WritePool) { $argsList += "--write-pool" }
if ($Report) { $argsList += @("--report", $Report) }

& $Py @argsList
exit $LASTEXITCODE
