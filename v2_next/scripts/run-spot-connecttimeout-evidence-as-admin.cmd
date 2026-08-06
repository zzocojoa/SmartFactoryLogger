@echo off
setlocal

rem Historical 2026-07-21 15-minute investigation launcher.
rem Do not substitute this for a current commit-bound canary gate.

if /I "%~1"=="ELEVATED" goto run

set "SFL_EVIDENCE_LAUNCHER=%~f0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Start-Process -FilePath $env:SFL_EVIDENCE_LAUNCHER -Verb RunAs -ArgumentList 'ELEVATED'"
exit /b

:run
cd /d "%~dp0"
title SmartFactoryLogger SPOT Evidence Collection
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0collect-spot-connecttimeout-evidence.ps1" -ObservationMinutes 15
set "collectorExit=%ERRORLEVEL%"

echo.
echo Review the result above. Press any key to close this window.
pause >nul
endlocal & exit /b %collectorExit%
