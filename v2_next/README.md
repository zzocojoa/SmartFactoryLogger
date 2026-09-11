# SmartFactoryLogger V2 (v2_next)

릴리스 노트는 [CHANGELOG.md](CHANGELOG.md)를 확인하세요.

## 실행과 종료

개발 실행은 저장소 루트에서 시작합니다. 활성 Python 환경에는
`backend/requirements.txt` 의존성이 설치되어 있어야 합니다.

```powershell
npm start
```

Electron은 현재 Windows x64 검증 대상으로 `44.3.0`에 고정합니다. Node.js
22.12 이상이 필요하며 CI 기준은 22.22.2입니다. Electron 42 이후 `npm ci`는
Electron 바이너리를 내려받지 않으므로, 직접 `dist/electron.exe`를 사용하는
오프라인 검사 전에 설치된 패키지의 다운로드 단계를 실행합니다.

```powershell
node node_modules/electron/install.js
```

일반 `npm start`는 최초 실행 때 자동 준비하며, electron-builder는 별도의
버전 고정 다운로드 경로를 사용합니다. 44는 Windows 32비트(ia32)를 지원하지
않습니다. 의존성 전환 및 로컬 검증은 서버 설치나 운영 수용을 뜻하지 않습니다.

패키지 앱은 창의 X 버튼으로 정상 종료하고 backend와 Electron 프로세스가 모두
종료될 때까지 기다립니다. `taskkill /F`, 작업 관리자 강제 종료,
`Stop-Process -Force`, `SmartFactoryBackend.exe` 직접 종료는 CSV와 fact closeout을
우회하므로 사용하지 않습니다.

개발 터미널에서 시작한 프로세스는 해당 터미널의 `Ctrl+C`로 종료합니다. 포트 충돌이
있으면 소유 프로세스를 먼저 확인하고, 다른 Python 또는 Node 프로세스를 일괄 종료하지
않습니다. lock 파일은 모든 SmartFactoryLogger 프로세스와 health endpoint가 종료된
것을 확인한 뒤 실제 stale lock일 때만 제거합니다.

현재 패키지 빌드는 다음 명령을 사용합니다. 외부·고객 배포 및 정식 상용 운영
배포에는 서명과 exact-commit 검증을 통과한 NSIS installer를 사용합니다.
비공개 개인 사용과 사내 개발·검증용 미서명 설치본은 서로 다른 예외이며,
[Windows Authenticode 서명 운영](docs/V2/05_운영_배포/windows_authenticode_signing.md)의 각 조건을 따릅니다.
조직 관리 장비라도 책임 개발자가 통제하는 제한된 개발·검증 목적에는 서명
구매·등록을 유예할 수 있으나, 정식 운영 승인이나 자동 설치를 뜻하지 않습니다.
kit 외부의 신뢰된 출처에서 확보한 SHA-256, commit-bound release identity,
설치 전 점검과 복구 경로 검증은 미서명 개발본에도 필수입니다.

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

### 프론트엔드 의존성 검증

React 18을 유지하며 Grafana data/runtime/ui는 `12.4.10`, Scenes는 `8.17.0`,
Router는 `7.18.3`, Vitest는 `4.1.11`로 고정합니다. `frontend`에서 `npm ci`를
실행하면 버전 검증형 postinstall이 다음 호환성 조건을 확인합니다.

- 기존 Scenes 그리드: 60열 / 행 높이 20px / 간격 4px.
- Schema 12.4에서 이동한 table 기본값: Scenes의 이전 내부 import를 공개
  `defaultTableOptions`로 연결. ESM/CJS 양쪽을 검사하며 기본값을 새로 만들지 않습니다.
- Grafana UI의 `react-router-dom-v5-compat` 소비는 `Link` 하나로 제한합니다.
  해당 의존성만 **공식 `react-router-dom@7.18.3` npm alias**로 대체하며, Grafana의
  URL 정제·ref·클릭 처리는 수정하지 않습니다. 앱은 shim 없이 Router 공개 API를 씁니다.
- Scenes의 Router `^6.28.0` peer 범위를 넘는 부분은 프로젝트가 책임지는 제한된
  호환 계약입니다. Grafana의 공식 Router 7 지원을 뜻하지 않습니다. 승인된 7개
  ESM/CJS 소비 파일의 해시, 추가 소비 파일, 패키지 버전, 공유 React/Router 실체,
  잠금파일의 공식 tarball·실제 패키지 이름을 검사합니다.

버전·선언·export가 예상과 다르면 설치가 실패합니다. `--ignore-scripts`로 설치한
결과는 패치 완료 상태가 아니며 빌드에 사용하지 않습니다. 업그레이드 시 패치,
실제 Scenes 편집·저장·복원, BrowserRouter/HashRouter 검증을 함께 갱신해야 합니다.

2026-09-11 후속 호환 계층 분리로 프론트엔드 감사의 나머지 moderate 6개 패키지
항목을 제거했습니다. 두 advisory에 걸렸던 Router 6/genuine v5-compat 체인은
잠금파일에 없으며, 공식 alias도 실제 Router 패키지 이름으로 npm 감사 대상입니다.
감사는 시점 기반 결과이지 취약점 부재나 운영 승인을 보장하지 않습니다.

Grafana UI가 선언하지만 사용하지 않는 Router 5는 전역 override하지 않았습니다.
Vite 빌드는 구형 Router 유입, 다른 패키지 실체, CJS/ESM core 혼용을 거부합니다.
업그레이드 시 `verify:router-contract`·실제 Grafana Link·Scenes 라우팅 테스트와
Electron의 편집·저장·복원을 다시 검증해야 합니다. 회귀 시 package/lock, shim,
Vite 설정과 호환 검사 스크립트를 이전 검증 조합으로 함께 되돌리고 `npm ci`합니다.
이는 개발 체크아웃의 복구 경로이며, 서버 롤백을 승인하거나 자동 수행하지 않습니다.

SPOT Temperature v2.5 서버 검증은 다음 문서를 사용합니다.

- [한 번에 실행하는 QA 절차](docs/V2/04_검증/spot_temperature_v25_one_command_qa.md)
- [1.0.13 실장비 서버 검증 결과](docs/04-report/spot-temperature-v2-5-server-validation.md)

현재 API와 v1.0.18 릴리스·운영 경계는 다음 문서에서 확인합니다.

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
