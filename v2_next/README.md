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

## React 렌더 계측

대시보드 렌더 commit count와 duration을 비교할 때는 mock 백엔드와 React Profiler
collector를 함께 실행합니다.

```powershell
# 터미널 1: mock API
$env:SF_PROFILER_MOCK_PORT = "8000"
npm run profile:react:mock

# 터미널 2: 프론트엔드
cd frontend
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run start -- --host 127.0.0.1 --port 3000

# 터미널 3: 30초 측정
cd ..
npm run profile:react -- --url http://127.0.0.1:3000/dashboard --label current --duration-ms 30000
```

계측은 `?sfReactProfiler=1` 또는 `localStorage["sf-react-profiler"]="1"`일 때만
활성화됩니다. 측정 결과는 기본적으로 `.gstack/benchmark-reports/` 아래에 저장되며
저장소에는 커밋하지 않습니다.
