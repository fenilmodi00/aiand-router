# Post-probe refit chain after geometry_pass on hard-y sparse gold.
# Refuses fit without geometry pass unless GEOMETRY_OVERRIDE=1.
param(
    [string]$TrainGold = "data/gold-sparse-hard-mix1.jsonl",
    [string]$CalGold = "data/gold-dense-hard-cal-merged.jsonl",
    [string]$Silver = "data/silver.jsonl",
    [string]$Eval = "data/gold-verified.jsonl",
    [string]$TuneGold = "data/gold-sparse-hard-mix-scale23.jsonl",
    [string]$Out = "data/scorer-hard-bilinear.json",
    [switch]$Logistic,
    [switch]$SkipRetune,
    [switch]$SkipShadow
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src"
$Py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

Write-Host "=== hard-y refit chain ==="
Write-Host "train_gold=$TrainGold eval=$Eval cal=$CalGold out=$Out"

# 0) Unpaid geometry gate (must pass before fit)
& $Py -m aiand_router.geometry --train $TrainGold --eval $Eval
$geoJson = & $Py -c @"
import json, sys
from pathlib import Path
from aiand_router.geometry import geometry_report
r = geometry_report(Path(sys.argv[1]), Path(sys.argv[2]))
print(json.dumps({'geometry_pass': r['geometry_pass'], 'kill': r['kill'], 'spearman': r['spearman_train_eval']}))
"@ $TrainGold $Eval
$geo = $geoJson | ConvertFrom-Json
if (-not $geo.geometry_pass) {
    if ($env:GEOMETRY_OVERRIDE -ne "1") {
        Write-Host "refusing refit: geometry_pass=false (set GEOMETRY_OVERRIDE=1 to override)"
        exit 2
    }
    Write-Host "warning: geometry_pass=false but GEOMETRY_OVERRIDE=1"
}

# 1) Fit (bilinear default; logistic with -Logistic)
$fitArgs = @(
    "fit",
    "--gold", $TrainGold,
    "--cal", $CalGold,
    "--silver", $Silver,
    "--out", $Out,
    "--geometry-train", $TrainGold,
    "--geometry-eval", $Eval
)
if (-not $Logistic) {
    $fitArgs += "--bilinear"
}
& $Py -m aiand_router.train @fitArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 2) Retune medium on disjoint cost-gold / tune split
if (-not $SkipRetune -and (Test-Path $TuneGold)) {
    & $Py -m aiand_router.train retune --dense $TuneGold --scorer $Out
}

# 3) Shadow replay (bounded; does not flip TRAINED_PATH)
if (-not $SkipShadow) {
    if (Test-Path "scripts/run_shadow.py") {
        & $Py scripts/run_shadow.py
    }
    & $Py -m aiand_router.replay_report --gold $Eval --artifact $Out --models config/models.yaml
}

Write-Host "refit chain done. TRAINED_PATH unchanged (shadow only)."
Write-Host "Next: bounded gate / operator replay before any live flip."
