<#
Run the Courier tools supplied in final_cases against a running backend.

Usage from the repository root:
  .\scripts\verify_final_cases.ps1

The backend must already be available at http://127.0.0.1:8000.
#>

param(
    [string]$ApiHost = "127.0.0.1",
    [int]$Port = 8000,
    [int]$BenchmarkCount = 200
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

$root = Split-Path -Parent $PSScriptRoot
$cases = Join-Path $root "final_cases"
$baseUrl = "http://${ApiHost}:$Port"

foreach ($path in @(
    "$cases/run_probe_pack.py",
    "$cases/timing_benchmark.py",
    "$cases/shock_injector.py",
    "$cases/practice_pack/practice_pack.csv",
    "$cases/practice_pack/practice_pack_key.json"
)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing judge material: $path"
    }
}

try {
    Invoke-WebRequest -UseBasicParsing "$baseUrl/openapi.json" | Out-Null
} catch {
    throw "Backend unavailable at $baseUrl. Start it before running this check."
}

function Invoke-JudgeTool([string]$Label, [string[]]$Arguments) {
    Write-Host "`n=== $Label ===" -ForegroundColor Cyan
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

Invoke-JudgeTool "Safety pack + explanations" @(
    "$cases/run_probe_pack.py",
    "--pack", "$cases/practice_pack/practice_pack.csv",
    "--key", "$cases/practice_pack/practice_pack_key.json",
    "--endpoint", "$baseUrl/decide",
    "--explain"
)

Invoke-JudgeTool "Tier 1 timing benchmark" @(
    "$cases/timing_benchmark.py",
    "--host", $ApiHost,
    "--port", "$Port",
    "--count", "$BenchmarkCount"
)

Invoke-JudgeTool "Official surge injector" @(
    "$cases/shock_injector.py",
    "--host", $ApiHost,
    "--port", "$Port",
    "--shock", "surge"
)

Write-Host "`nALL OFFICIAL COURIER CHECKS PASSED" -ForegroundColor Green
