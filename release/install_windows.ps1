param(
    [string]$Repo = "creno-va/korail-program",
    [string]$Version = "latest",
    [string]$Model = "gpt-5.6-terra",
    [string]$InstallRoot = "$env:LOCALAPPDATA\KorailProgram",
    [switch]$SkipSystemPackages
)

$ErrorActionPreference = "Stop"

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

function Get-ReleaseTag {
    if ($Version -ne "latest") {
        return $Version
    }
    $release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
    return $release.tag_name
}

$Tag = Get-ReleaseTag
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("korail-program-" + [System.Guid]::NewGuid().ToString("N"))
$ZipPath = Join-Path $TempRoot "source.zip"
$ExtractPath = Join-Path $TempRoot "source"
$SourceDir = Join-Path $InstallRoot "source"

New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null

$SourceUrl = "https://github.com/$Repo/archive/refs/tags/$Tag.zip"
Write-Host "Downloading $SourceUrl"
Invoke-WebRequest $SourceUrl -OutFile $ZipPath
Expand-Archive $ZipPath -DestinationPath $ExtractPath -Force
$ExpandedDir = Get-ChildItem -LiteralPath $ExtractPath -Directory | Select-Object -First 1
if (-not $ExpandedDir) {
    throw "Could not find expanded source directory."
}

if (Test-Path $SourceDir) {
    Remove-Item -LiteralPath $SourceDir -Recurse -Force
}
Copy-Item -LiteralPath $ExpandedDir.FullName -Destination $SourceDir -Recurse

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

$VenvPath = Join-Path $InstallRoot ".venv"
& $PythonExecutable @PythonArgs -m venv $VenvPath
& (Join-Path $VenvPath "Scripts\python.exe") -m pip install --upgrade pip
& (Join-Path $VenvPath "Scripts\python.exe") -m pip install $SourceDir

if (-not $env:OPENAI_API_KEY) {
    Write-Warning "OPENAI_API_KEY is not set. Set it in the environment or save it in the app's API settings before analysis."
}

$RunGui = Join-Path $InstallRoot "Run Korail Analyzer.cmd"
$RunAnalysis = Join-Path $InstallRoot "Analyze Videos.cmd"
Set-Content -LiteralPath $RunGui -Encoding ASCII -Value "@echo off`r`n`"$VenvPath\Scripts\korail-analyzer-gui.exe`"`r`n"
Set-Content -LiteralPath $RunAnalysis -Encoding ASCII -Value "@echo off`r`nset INPUT_DIR=%~1`r`nif `"%INPUT_DIR%`"==`"`" set INPUT_DIR=%CD%`r`n`"$VenvPath\Scripts\korail-analyzer.exe`" analyze-videos `"%INPUT_DIR%`" --out `"%CD%\output\analysis`" --model $Model`r`n"

Write-Host ""
Write-Host "Install complete: $InstallRoot"
Write-Host "Run GUI: $RunGui"
Write-Host "Analyze videos: $RunAnalysis"
