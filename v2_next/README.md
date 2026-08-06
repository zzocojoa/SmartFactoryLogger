# SmartFactoryLogger V2 (v2_next)

릴리스 노트는 [CHANGELOG.md](CHANGELOG.md)를 확인하세요.

## 실행과 종료

개발 실행은 저장소 루트에서 시작합니다. 활성 Python 환경에는
`backend/requirements.txt` 의존성이 설치되어 있어야 합니다.

```powershell
npm start
```

패키지 앱은 창의 X 버튼으로 정상 종료하고 backend와 Electron 프로세스가 모두
종료될 때까지 기다립니다. `taskkill /F`, 작업 관리자 강제 종료,
`Stop-Process -Force`, `SmartFactoryBackend.exe` 직접 종료는 CSV와 fact closeout을
우회하므로 사용하지 않습니다.

개발 터미널에서 시작한 프로세스는 해당 터미널의 `Ctrl+C`로 종료합니다. 포트 충돌이
있으면 소유 프로세스를 먼저 확인하고, 다른 Python 또는 Node 프로세스를 일괄 종료하지
않습니다. lock 파일은 모든 SmartFactoryLogger 프로세스와 health endpoint가 종료된
것을 확인한 뒤 실제 stale lock일 때만 제거합니다.

현재 패키지 빌드는 다음 명령을 사용합니다. 외부·고객·상용 서버에는 서명과
exact-commit 검증을 통과한 NSIS installer만 배포합니다. 소유자가 통제하는
비공개 개인 사용 환경의 미서명 예외는 kit 외부의 신뢰된 출처에서 확보한
SHA-256 및 commit-bound release identity 검증을 필수로 적용하며,
[Windows Authenticode 서명 운영](docs/V2/05_운영_배포/windows_authenticode_signing.md)의 유예 조건을 따릅니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1
npm run dist
```

## 검증

브랜치 배포 전 프론트엔드 타입 검사, 린트, 테스트와 백엔드 린트, 타입 검사,
unittest를 한 번에 실행합니다.

```powershell
npm run health
```

SPOT Temperature v2.5 서버 검증은 다음 문서를 사용합니다.

- [한 번에 실행하는 QA 절차](docs/V2/04_검증/spot_temperature_v25_one_command_qa.md)
- [1.0.13 실장비 서버 검증 결과](docs/04-report/spot-temperature-v2-5-server-validation.md)

현재 API와 v1.0.17 운영 경계는 다음 문서에서 확인합니다.

- [Backend API reference](backend/API_DOCUMENTATION.md)
- [SPOT source-port quarantine 설계](docs/02-design/features/spot-tcp-source-port-quarantine-v2.design.md)
- [SPOT source-port field/report 상태](docs/04-report/spot-tcp-source-port-quarantine-v2.report.md)
- [운영·관측성 오류 원인 검증 기록](docs/04-report/runtime-error-root-cause-validation.report.md)
- [Windows Authenticode 서명 운영](docs/V2/05_운영_배포/windows_authenticode_signing.md)
- [배포 체크리스트](docs/V2/DEPLOYMENT_CHECKLIST.md)

## Build commit provenance

PyInstaller backend package는 clean Git HEAD만 build provenance로 포함하며, frozen
runtime은 Git 없이 해당 SHA를 CSV v2 metadata에 기록합니다. Dirty/invalid/no-Git
build 실패 정책과 rollback은
[Packaged Build Commit Provenance](docs/V2/05_운영_배포/build_commit_provenance.md)를
참조하세요.

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
