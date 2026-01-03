@echo off
setlocal

echo [Deploy] Starting Smart Factory Logger V2...

:: 1. Build Frontend
echo [Deploy] Building Frontend (React/Vite)...
cd frontend
call npm install
call npm run build
if %errorlevel% neq 0 (
    echo [Error] Frontend build failed!
    pause
    exit /b %errorlevel%
)
cd ..

:: 2. Start Backend (FastAPI with Static Files)
echo [Deploy] Starting Backend Server...
echo [Info] Server will be available at http://localhost:8000
echo [Info] API Docs at http://localhost:8000/docs
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1

endlocal
