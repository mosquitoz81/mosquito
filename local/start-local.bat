@echo off
title Pockie Ninja - Starting Server
echo ============================================
echo   Pockie Ninja Offline Server - Starting
echo ============================================
echo.

REM Run the PowerShell script
powershell -ExecutionPolicy Bypass -File "%~dp0start-local.ps1"

echo.
echo Press any key to close this window...
pause >nul
