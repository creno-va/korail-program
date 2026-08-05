@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "ANALYZER=%PROJECT_ROOT%\.venv\Scripts\korail-analyzer.exe"

if not exist "%ANALYZER%" (
  echo Analyzer launcher not found.
  echo Run: powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1
  exit /b 1
)

if "%KORAIL_VISION_MODEL%"=="" set "KORAIL_VISION_MODEL=qwen3-vl:4b"
if "%KORAIL_INTERVAL_SEC%"=="" set "KORAIL_INTERVAL_SEC=15"
if "%KORAIL_MIN_REPORT_RISK%"=="" set "KORAIL_MIN_REPORT_RISK=low"

"%ANALYZER%" analyze-videos "%PROJECT_ROOT%" --out "%PROJECT_ROOT%\output\analysis" --interval-sec "%KORAIL_INTERVAL_SEC%" --model "%KORAIL_VISION_MODEL%" --min-report-risk "%KORAIL_MIN_REPORT_RISK%"
