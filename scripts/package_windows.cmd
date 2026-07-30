@echo off
setlocal

powershell -ExecutionPolicy Bypass -File "%~dp0package_windows.ps1" %*
