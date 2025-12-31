@echo off
setlocal

:: --- 1. 환경 설정 ---
set "V2_MODE=REAL"
set "APP_ROOT=%~dp0"
set "BACKEND_DIR=%APP_ROOT%backend"
set "FRONTEND_DIR=%APP_ROOT%frontend"
set "CONFIG_PATH=%APPDATA%\SmartFactoryLogger\config.ini"
set "SFL_CONFIG_PATH=%CONFIG_PATH%"

title [SmartFactoryLogger V2] Launcher (REAL MODE)

echo ===================================================
echo   Smart Factory Logger V2 - REAL MODE
echo   Device: %COMPUTERNAME%
echo   Root: %APP_ROOT%
echo ===================================================
echo.

:: --- 2. 백엔드 실행 (Background) ---
echo [1/3] Starting Backend Server...
start "SFL_V2_Backend" /min cmd /c "cd /d %APP_ROOT% && python -m backend.main"

:: Wait for backend to init (Simple delay)
timeout /t 3 >nul

:: --- 3. 프론트엔드 실행 ---
echo [2/3] Starting Frontend Dashboard...
cd /d %FRONTEND_DIR%

:: Check if build exists (Prodcution) or run dev (Dev)
if exist "build\index.html" (
    echo    Found production build. Serving...
    :: Use 'serve' if installed, otherwise fallback to npm start
    :: For now, assuming npm start for flexibility as per README
    npm start
) else (
    echo    Starting Development Server...
    npm start
)

echo [3/3] Done.
pause
