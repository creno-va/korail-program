param(
    [string]$Model = $env:KORAIL_VISION_MODEL,
    [double]$IntervalSec = 10,
    [string]$MinReportRisk = "medium"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Analyzer = Join-Path $ProjectRoot ".venv\Scripts\korail-analyzer.exe"

if (-not $Model) {
    $Model = "qwen3-vl:8b"
}

if (-not (Test-Path $Analyzer)) {
    Write-Error "Analyzer launcher not found. Run: powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1"
}

& $Analyzer analyze-videos $ProjectRoot --out (Join-Path $ProjectRoot "output\analysis") --interval-sec $IntervalSec --model $Model --min-report-risk $MinReportRisk
