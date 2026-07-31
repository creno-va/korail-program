param(
    [string]$Version,
    [switch]$SkipInnoInstall,
    [switch]$SkipPyInstallerInstall,
    [switch]$SkipRuntimeDownloads,
    [string]$InnoSetupVersion = "6.7.1",
    [switch]$BuildAppOnly
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Resolve-InWorkspace {
    param([string]$Path)
    $Root = (Resolve-Path -LiteralPath $ProjectRoot).Path
    $Resolved = if (Test-Path -LiteralPath $Path) {
        (Resolve-Path -LiteralPath $Path).Path
    } else {
        [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $Path))
    }
    if (-not $Resolved.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside workspace: $Resolved"
    }
    return $Resolved
}

function Remove-InWorkspace {
    param([string]$Path)
    $Resolved = Resolve-InWorkspace $Path
    if (Test-Path -LiteralPath $Resolved) {
        Remove-Item -LiteralPath $Resolved -Recurse -Force
    }
}

function Get-ProjectVersion {
    $Pyproject = Get-Content -LiteralPath "pyproject.toml" -Encoding UTF8 -Raw
    if ($Pyproject -match '(?m)^version\s*=\s*"([^"]+)"') {
        return $Matches[1]
    }
    throw "Could not read project version from pyproject.toml"
}

function Find-Iscc {
    $Command = Get-Command iscc -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }
    foreach ($Candidate in @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )) {
        if (Test-Path -LiteralPath $Candidate) {
            return $Candidate
        }
    }
    return $null
}

function Install-PortableInnoSetup {
    param([string]$PackageVersion)

    $ToolsRoot = Resolve-InWorkspace ".tools"
    $PackageRoot = Join-Path $ToolsRoot "Tools.InnoSetup.$PackageVersion"
    $Iscc = Get-ChildItem -LiteralPath $PackageRoot -Recurse -Filter "ISCC.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($Iscc) {
        return $Iscc.FullName
    }

    New-Item -ItemType Directory -Force -Path $ToolsRoot | Out-Null
    $NupkgPath = Join-Path $ToolsRoot "Tools.InnoSetup.$PackageVersion.nupkg"
    $ZipPath = Join-Path $ToolsRoot "Tools.InnoSetup.$PackageVersion.zip"
    $Url = "https://www.nuget.org/api/v2/package/Tools.InnoSetup/$PackageVersion"

    Write-Host "Downloading portable Inno Setup compiler: $Url"
    Invoke-WebRequest -Uri $Url -OutFile $NupkgPath
    Copy-Item -LiteralPath $NupkgPath -Destination $ZipPath -Force

    if (Test-Path -LiteralPath $PackageRoot) {
        Remove-Item -LiteralPath $PackageRoot -Recurse -Force
    }
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $PackageRoot -Force

    $Iscc = Get-ChildItem -LiteralPath $PackageRoot -Recurse -Filter "ISCC.exe" |
        Select-Object -First 1
    if (-not $Iscc) {
        throw "Could not find ISCC.exe in Tools.InnoSetup $PackageVersion"
    }
    return $Iscc.FullName
}

function Install-FfmpegRuntime {
    $VendorBin = Resolve-InWorkspace "packaging\vendor\ffmpeg\bin"
    $FfmpegExe = Join-Path $VendorBin "ffmpeg.exe"
    $FfprobeExe = Join-Path $VendorBin "ffprobe.exe"
    if ((Test-Path -LiteralPath $FfmpegExe) -and (Test-Path -LiteralPath $FfprobeExe)) {
        return $VendorBin
    }

    New-Item -ItemType Directory -Force -Path $VendorBin | Out-Null
    $ToolsRoot = Resolve-InWorkspace ".tools"
    New-Item -ItemType Directory -Force -Path $ToolsRoot | Out-Null
    $ZipPath = Join-Path $ToolsRoot "ffmpeg-release-essentials.zip"
    $ExtractPath = Join-Path $ToolsRoot "ffmpeg-release-essentials"
    $Url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

    Write-Host "Downloading FFmpeg runtime: $Url"
    Invoke-WebRequest -Uri $Url -OutFile $ZipPath
    if (Test-Path -LiteralPath $ExtractPath) {
        Remove-Item -LiteralPath $ExtractPath -Recurse -Force
    }
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractPath -Force

    $ExtractedFfmpeg = Get-ChildItem -LiteralPath $ExtractPath -Recurse -Filter "ffmpeg.exe" |
        Select-Object -First 1
    if (-not $ExtractedFfmpeg) {
        throw "Could not find ffmpeg.exe in downloaded runtime."
    }
    $ExtractedBin = $ExtractedFfmpeg.Directory.FullName
    foreach ($Name in @("ffmpeg.exe", "ffprobe.exe")) {
        $Source = Join-Path $ExtractedBin $Name
        if (-not (Test-Path -LiteralPath $Source)) {
            throw "Could not find $Name in downloaded runtime."
        }
        Copy-Item -LiteralPath $Source -Destination (Join-Path $VendorBin $Name) -Force
    }
    return $VendorBin
}

function Copy-BundledRuntime {
    $RuntimeRoot = Resolve-InWorkspace "dist\KorailAnalyzer\runtime"
    New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

    $FfmpegSource = Resolve-InWorkspace "packaging\vendor\ffmpeg"
    if (-not (Test-Path -LiteralPath (Join-Path $FfmpegSource "bin\ffmpeg.exe"))) {
        throw "FFmpeg runtime is missing. Rerun without -SkipRuntimeDownloads."
    }
    $FfmpegTarget = Join-Path $RuntimeRoot "ffmpeg"
    if (Test-Path -LiteralPath $FfmpegTarget) {
        Remove-Item -LiteralPath $FfmpegTarget -Recurse -Force
    }
    Copy-Item -LiteralPath $FfmpegSource -Destination $FfmpegTarget -Recurse
}

if (-not $Version) {
    $Version = Get-ProjectVersion
}

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

$Python = Resolve-InWorkspace ".venv\Scripts\python.exe"
if (-not $SkipPyInstallerInstall) {
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -e .
    & $Python -m pip install "pyinstaller>=6.11"
}

Remove-InWorkspace "build\korail-analyzer-gui"
Remove-InWorkspace "dist\KorailAnalyzer"
Remove-InWorkspace "dist\installer"

$PyInstaller = Resolve-InWorkspace ".venv\Scripts\pyinstaller.exe"
& $PyInstaller --noconfirm "packaging\pyinstaller\korail-analyzer-gui.spec"

$AppExe = Resolve-InWorkspace "dist\KorailAnalyzer\KorailAnalyzer.exe"
if (-not (Test-Path -LiteralPath $AppExe)) {
    throw "PyInstaller did not create $AppExe"
}

if (-not $SkipRuntimeDownloads) {
    Install-FfmpegRuntime | Out-Null
}
Copy-BundledRuntime

if ($BuildAppOnly) {
    Write-Host "App bundle created: $AppExe"
    exit 0
}

$Iscc = Find-Iscc
if (-not $Iscc -and -not $SkipInnoInstall) {
    $Iscc = Install-PortableInnoSetup -PackageVersion $InnoSetupVersion
}

if (-not $Iscc) {
    throw "Inno Setup compiler was not found. Install Inno Setup 6 or rerun with -BuildAppOnly."
}

$env:KORAIL_APP_VERSION = $Version
& $Iscc "packaging\windows\KorailAnalyzer.iss"

$Installer = Resolve-InWorkspace "dist\installer\KorailAnalyzerSetup-$Version.exe"
if (-not (Test-Path -LiteralPath $Installer)) {
    throw "Installer was not created: $Installer"
}

Write-Host "Installer created: $Installer"
