@echo off
setlocal

set "SOURCE_DIR=Z:\v2_next"
set "DEST_DIR=%~dp0"

echo ===================================================
echo   Smart Factory Logger V2 - UPDATER
echo   Source: %SOURCE_DIR%
echo   Dest:   %DEST_DIR%
echo ===================================================
echo.

if not exist "%SOURCE_DIR%" (
    echo [ERROR] Source directory not found (Z: drive disconnected?)
    pause
    exit /b 1
)

echo [1/2] Updating Backend...
robocopy "%SOURCE_DIR%\backend" "%DEST_DIR%backend" /E /XO /XN /XC /MT:32 /R:2 /W:1 /XD __pycache__ /XF *.pyc config.ini

echo [2/2] Updating Frontend (Source Only)...
robocopy "%SOURCE_DIR%\frontend" "%DEST_DIR%frontend" /E /XO /XN /XC /MT:32 /R:2 /W:1 /XD node_modules build .git /XF *.log

echo.
echo [SUCCESS] Update Completed.
pause
