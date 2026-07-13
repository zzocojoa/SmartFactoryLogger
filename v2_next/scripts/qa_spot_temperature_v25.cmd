@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0qa_spot_temperature_v25.ps1" %*
exit /b %ERRORLEVEL%
