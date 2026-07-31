param(
    [string]$Model = "gpt-5.6-terra",
    [switch]$SkipSystemPackages,
    [switch]$RunGui,
    [switch]$RunRootAnalysis
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Get-CommandPath {
    param([string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    return $null
}

function Install-WingetPackage {
    param(
        [string]$Id,
        [string]$Name
    )
    if ($SkipSystemPackages) {
        Write-Warning "$Name is not installed. Skipping system package install."
        return
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Warning "winget is not available. Install $Name manually."
        return
    }
    winget install -e --id $Id --accept-package-agreements --accept-source-agreements
}

function Get-PythonCommand {
    $PythonExe = Get-CommandPath "python"
    if ($PythonExe) {
        return @($PythonExe)
    }
    $PyLauncher = Get-CommandPath "py"
    if ($PyLauncher) {
        return @($PyLauncher, "-3")
    }
    return @()
}

$PythonCommand = Get-PythonCommand
if ($PythonCommand.Count -eq 0) {
    Install-WingetPackage -Id "Python.Python.3.12" -Name "Python 3.12"
    $PythonCommand = Get-PythonCommand
}
if ($PythonCommand.Count -eq 0) {
    throw "Python was not found. Install Python 3.11+ and rerun this script."
}

if (-not (Get-CommandPath "ffmpeg")) {
    Install-WingetPackage -Id "Gyan.FFmpeg" -Name "FFmpeg"
}

$PythonExecutable = $PythonCommand[0]
$PythonArgs = @()
if ($PythonCommand.Count -gt 1) {
    $PythonArgs = $PythonCommand[1..($PythonCommand.Count - 1)]
}

& $PythonExecutable @PythonArgs -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install .

if (-not $env:OPENAI_API_KEY) {
    Write-Warning "OPENAI_API_KEY is not set. Set it in the environment or save it in the app's API settings before analysis."
}

Write-Host ""
Write-Host "Install complete."
Write-Host "Run GUI: .\scripts\run_gui.cmd"
Write-Host "Run root video analysis: .\scripts\analyze_root_videos.cmd"

if ($RunRootAnalysis) {
    & ".\.venv\Scripts\korail-analyzer.exe" analyze-videos "." --out "output\analysis" --interval-sec 10 --model $Model --min-report-risk medium
}

if ($RunGui) {
    & ".\.venv\Scripts\korail-analyzer-gui.exe"
}
