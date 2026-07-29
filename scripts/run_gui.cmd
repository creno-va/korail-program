@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "GUI_EXE=%PROJECT_ROOT%\.venv\Scripts\korail-analyzer-gui.exe"

if not exist "%GUI_EXE%" (
  echo GUI launcher not found.
  echo Run: .venv\Scripts\python.exe -m pip install -e .
  exit /b 1
)

"%GUI_EXE%"
