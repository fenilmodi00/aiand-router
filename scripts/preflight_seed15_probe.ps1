param(
    [switch]$Json,
    [string]$Report
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = if (Test-Path "$root\.venv\Scripts\python.exe") {
    "$root\.venv\Scripts\python.exe"
} else {
    "python"
}

$args = @("$root\scripts\seed15_resume_preflight.py")
if ($Json) {
    $args += "--json"
}
if ($Report) {
    $args += @("--report", $Report)
}

& $py @args
exit $LASTEXITCODE
