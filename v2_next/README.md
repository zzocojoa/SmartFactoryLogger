# SmartFactoryLogger V2 (v2_next)

cd frontend; npm start

cd backend; python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# 1. JSON 마이그레이션 + 서버 시작 (권장)

.\SmartFactory_v1.0.4.exe --migrate-json

# 2. 마이그레이션만 실행 (GUI 없이)

.\SmartFactory_v1.0.4.exe --migrate-only

# 3. 일반 실행 (마이그레이션 없이)

.\SmartFactory_v1.0.4.exe

# 권장 워크플로우 (한 번에 실행)

## 1. 기존 프로세스 모두 종료

taskkill /F /IM python.exe 2>$null

Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force;
Write-Host "모든 Node 프로세스 종료됨"

## 2. Lock 파일 삭제

Remove-Item -Path "$env:APPDATA\SmartFactoryLogger\sfl_v2.lock" -ErrorAction
SilentlyContinue

## 3. 백엔드 재시작

python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload

## 4. EXE 빌드

powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1
