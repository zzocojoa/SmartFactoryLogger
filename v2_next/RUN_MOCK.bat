@echo off
setlocal

:: --- 1. 환경 설정 ---
set "V2_MODE=MOCK"
set "APP_ROOT=%~dp0"
set "SFL_CONFIG_PATH=%APPDATA%\SmartFactoryLogger\config.ini"

title [SmartFactoryLogger V2] Launcher (MOCK MODE)

echo ===================================================
echo   Smart Factory Logger V2 - MOCK MODE
echo   Root: %APP_ROOT%
echo ===================================================
echo.

:: --- 2. 백엔드 실행 ---
echo [1/2] Starting Backend Server...
start "SFL_V2_Backend_Mock" cmd /k "cd /d %APP_ROOT% && python -m backend.main"

timeout /t 2 >nul

:: --- 3. 프론트엔드 실행 ---
echo [2/2] Starting Frontend...
cd /d %APP_ROOT%frontend
npm start
