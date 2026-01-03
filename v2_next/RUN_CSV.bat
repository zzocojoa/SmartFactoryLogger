@echo off
setlocal

:: --- 1. 환경 설정 ---
set "V2_MODE=CSV"
set "APP_ROOT=%~dp0"
set "BACKEND_DIR=%APP_ROOT%backend"
set "FRONTEND_DIR=%APP_ROOT%frontend"
set "V2_CSV_PATH=..\v1_legacy\logs\Aligned_Results\Factory_Integrated_Log_20251231_000000.csv"

title [SmartFactoryLogger V2] Launcher (CSV REPLAY MODE)

echo ===================================================
echo   Smart Factory Logger V2 - CSV REPLAY MODE
echo   File: %V2_CSV_PATH%
echo ===================================================
echo.

:: --- 2. 백엔드 실행 (Background) ---
echo [1/3] Starting Backend Server...
start "SFL_V2_Backend_CSV" /min cmd /c "cd /d %APP_ROOT% && python -m backend.main"

:: Wait for backend to init
timeout /t 3 >nul

:: --- 3. 프론트엔드 실행 ---
echo [2/3] Starting Frontend Dashboard (Dev Mode)...
cd /d %FRONTEND_DIR%
npm start

echo [3/3] Done.
pause
