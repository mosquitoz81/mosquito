@echo off
title Pockie Ninja - Stopping Server
echo ============================================
echo   Pockie Ninja Offline Server - Stopping
echo ============================================
echo.

REM Run the PowerShell script
powershell -ExecutionPolicy Bypass -File "%~dp0stop-local.ps1"

echo.
echo Press any key to close this window...
pause >nul
