$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$GuiExe = Join-Path $ProjectRoot ".venv\Scripts\korail-analyzer-gui.exe"

if (-not (Test-Path $GuiExe)) {
    Write-Error "GUI launcher not found. Run: .\.venv\Scripts\python.exe -m pip install -e ."
}

& $GuiExe
