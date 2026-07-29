@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo Virtual environment not found.
  echo Run: python -m venv .venv
  exit /b 1
)

"%PYTHON%" -m unittest discover -s tests
