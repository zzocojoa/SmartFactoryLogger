@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply_spot_temperature_v25_attestation.ps1" %*
exit /b %ERRORLEVEL%
