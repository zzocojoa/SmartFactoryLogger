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

## 로컬 검증 파일 관리

개발 PC의 단일 관리본은 `verification-files.local.json`이다. 저장 로직의 소스 위치와
해시, 발견 경로, 보존 분류, 연결 폴더/접근 실패, 삭제 전 파일 해시 및 삭제 이력을
기록한다. 로컬 경로가 포함되므로 Git에 커밋하거나 외부에 공유하지 않는다.

```powershell
node scripts/manage-verification-files.cjs scan
```

위 명령은 기존 삭제 이력을 보존하면서 목록만 갱신한다. 삭제·이동·앱 실행은 하지
않으며, 전체 디스크나 원격 서버의 모든 파일을 찾았다는 뜻은 아니다. 임의의 출력
경로 override는 별도 확인이 필요하다. 실제 설정/CSV/이미지/설치 폴더는 정리 대상이
아니고, 과거 해시 결합 도우미의 저장 경로도 변경하지 않는다.

삭제 실행기는 `scripts/remove-reviewed-verification-files.ps1`이며 **개발 PC의
PowerShell 7 전용**이다. 검토된 좁은 허용 경로, 관리본 SHA256, 계획 ID가 모두 필요하고
기본적인 경로·내용·사용 상태 검사를 통과해야 한다. 먼저 `-WhatIf`로 점검한다.
새 폴더는 이름이 임시 파일처럼 보여도 자동 삭제하지 않는다. 삭제한 캐시/테스트
바이너리는 재생성이 필요하며, 중복은 관리본에 기록한 `retained_copy`로 복구한다.

개발 PC에서 서버로부터 받은 `Desktop/test` 증거의 통합 위치는
`artifacts/server-evidence/desktop-test`이다. 원본 내용/해시/시각/접근 권한을 보존하고,
이전 경로와 새 경로의 대응 및 이관 상태는 같은 관리본의 `migrations`에 기록한다.
이 위치와 관리본은 Git에서 제외한다. 과거 보고서와 증거 내부의 경로는 역사적 기록이므로
수정하지 않는다. 서버의 `C:\ProgramData\SFLOps`나 운영 데이터는 이 로컬 이관과 별개다.

이관 실행기 `scripts/migrate-desktop-test.ps1`은 고정된 컬렉션 경로만 취급하며 관리본의
계획 ID와 외부 SHA256을 요구한다. 전체 복사·검증과 경로 대응 저장이 완료된 뒤에만
기존 파일을 제거한다. 중단 상태는 자동 재시도하지 않고 두 위치를 보존하여 조사한다.
이관 후 `node scripts/manage-verification-files.cjs scan`과 `verify`를 차례로 실행한다.
검증기에서 최신 서버 결과는 완료된 이관 경로를 사용하며, 중간 상태에서는 실행을 막는다.

`Desktop/SmartFactory`의 과거 전송본은 같은 부모의 `desktop-smartfactory`에 보관한다.
실행기는 `-Collection desktop-smartfactory`로 이 고정된 이관만 선택할 수 있다.
검토된 압축 해제 중복은 보존 ZIP의 전체 해시와 내부 항목의 길이/해시가 모두 일치할
때만 제거한다. 관리본에 원래 경로, ZIP 경로/내부 항목, 시각/ACL을 남겨 복구에 사용한다.
`verify`는 해당 ZIP 항목도 다시 검사한다. 빌드/임시 폴더의 동일 파일만으로는 보존을
대체하지 않으며, 과거 도우미는 경로를 바꾸지 않은 열람용 기록이므로 직접 실행하지 않는다.

`Desktop/SmartFactoryLogger_Release`는 `desktop-release` 컬렉션으로 통합한다.
`-Collection desktop-release`는 이 고정된 경로만 처리한다. 배포 릴리스·현장 도구 묶음과
직계 운영 도우미는 그대로 보존한다. 그 외 같은 파일명/길이/SHA256의 반복 파일은
통합 폴더 내 실제 보존 파일을 직접 가리키는 `retained_file`로 기록하고 중복만 제거한다.
중복끼리의 연쇄 참조와 외부 임시/빌드 파일에 의존하는 복구는 허용하지 않는다.
이 보관본은 로컬 PowerShell 7용이며, 정리된 staging/압축 해제 트리는 실행 가능한
설치본이 아니다. 복원이 필요하면 관리본의 원래 경로/권한/시각을 따라 별도로 복원한다.
긴 `spot_connecttimeout_field_kit_077b6b1c_rebuilt_20260727` 상위 폴더만
`kit-077b6b1`로 짧게 보관하며 파일 이름/내용과 내부 상대 구조는 유지한다.
원래 이름은 같은 관리본의 디렉터리/파일 경로 대응에 남긴다.

`SmartFactoryLogger_Transfer_0695a0f_20260806` 및 `_R2`, `_R3` 전송본은
같은 보관 루트의 `transfer-0695a0f-r1`, `-r2`, `-r3`로 각각 대응한다.
서로 다른 ZIP 개정본과 `SUPERSEDED_*_DO_NOT_USE.txt`는 함께 보존한다.
`prepare-transfer-batches`는 세 고정 경로의 계획만 만들며, 실행은 컬렉션별로 순차 수행한다.
다음 컬렉션 실행에는 직전 실행 후 갱신된 관리본 SHA256이 필요하다. 이관 완료는 과거
설치 도우미를 실행하거나 구형 ZIP을 다시 배포해도 된다는 승인이 아니다.

`node scripts/manage-verification-files.cjs audit-build-checkout`은 개발 PC의 고정된
`SmartFactoryLogger_Builds/spot-tcp-connection-reuse-remediation_bfd9be7/source`만
읽어 과거 소스, Git 메타데이터, 의존성/캐시, 빌드 결과와 테스트 증거를 분류한다.
결과는 같은 관리본의 `audits`에 추가하며 `scan` 이후에도 유지한다. 감사 목록은
기본 스캔에서 제외된 체크아웃의 보충 기록이므로 기본 파일 합계에 중복 합산하지 않는다.
Git 명령은 선택적 인덱스 쓰기와 fsmonitor를 끈 읽기 전용 조회만 사용하고, 설정 내용이나
remote URL은 출력하지 않는다. 생성 로직의 소스 위치/해시와 보존 패키지의 해시를 기록한다.
`CANDIDATE_*`는 삭제 승인이 아니다. 의존성 재설치 가능성, 바이트 단위 재현성, 실제 사용
상태와 삭제 직전 파일별 해시/ACL/ADS는 별도 확인해야 한다. `.git` 및 추적 소스는 보존한다.

`scripts/review-build-cache.ps1 -ExpectedIndexSha256 <관리본 SHA256>`은 위 감사의
캐시·중간 빌드 102개만 읽어 파일별 해시/권한/시각/ADS, Python 원본 소스, 생성 로직과
관찰 가능한 프로세스·서비스·작업·바로가기 참조를 점검한다. 빌드 경고, 모듈 참조 보고서,
TOC 7개는 보존하고 나머지 95개의 삭제 후보 목록을 같은 `audits`에 기록한다.
기본 검토 모드는 삭제/이동하지 않는다. 별도 승인된 고정 검토 ID의 95개만 처리하는
`-RemoveReviewed` 모드는 먼저 `-WhatIf`로 재검증하고, 같은 관리본 SHA256으로 실행한다.
삭제 전 해시/권한/ADS·소스/설치본 보존·사용 참조를 재확인하고 상태를 먼저 기록한다.
빈 디렉터리는 삭제하지 않는다. 중간 실패는 `PARTIAL_STOPPED`로 보존하며 자동 재시도하지
않는다. `scan`은 미완료 삭제 상태를 거부하고, `verify`는 완료 후 95개 부재 및 보존한
7개 진단 파일과 Python 원본의 해시를 다시 확인한다. 감사 원본은 당시의 기록으로 남고
실제 삭제 결과는 그 검토 기록의 `cleanup` 및 공통 `history`에 추가된다.
Windows 파일 시각의 64비트 ticks는 JSON 숫자 정밀도 손실을 막기 위해 문자열로 기록한다.
과거 숫자 기록은 남아 있는 binary64 정밀도에서만 비교하고, 내용/권한/ADS가 일치한 경우
현재의 정확한 문자열 시각을 별도 실행 기록에 남겨 삭제 직전 다시 확인한다.
캐시 재생성이나 재빌드가 원래 바이트까지 복원함을 보장하지 않는다. 전역 열린 핸들과
모든 셸의 작업 디렉터리는 이 점검만으로 증명하지 못한다.

`node scripts/manage-verification-files.cjs audit-build-dependencies`는 같은 구형 빌드
체크아웃의 네 의존성 폴더만 읽고 결과를 관리본 `audits`에 추가한다. Node 잠금파일과
설치 버전, 의도된 Grafana 설치 후 패치, Python 배포판의 버전/RECORD 해시, Playwright
브라우저 개정 번호를 확인한다. 과거 코드나 설치 스크립트를 실행하지 않고 네트워크도
사용하지 않는다. 설치 파일, 설정, 브라우저를 변경하거나 삭제하지 않는다.
잠금파일 일치만으로 전체 파일 무변경을 보장하지 않으며 Python RECORD도 독립적인
신뢰 근거가 아니다. 버전 미고정 요구사항, 패키지 원본/브라우저 다운로드의 가용성,
새 경로에서의 실제 재설치는 별도 검증이 필요하다. 이 감사는 삭제 승인이 아니다.

`scripts/rehearse-build-dependencies.cjs`는 별도 승인된 개발 PC 재설치 검증용이다.
`prepare`는 `.tmp/dep-<GUID>` 하나에 입력 복사본·캐시·wheel·로그를 모으고 관리본에
실행 경로를 먼저 등록한다. `node`, `frontend`, `python`, `node-scripts`,
`frontend-scripts`, `browsers`, `compare`를 같은 실행 ID로 **순차** 수행한다.
진행 중이거나 이미 시도한 단계는 재실행하지 않는다. 실패 로그와 원본은 보존한다.
Node는 `npm ci --ignore-scripts` 후 검토한 설치 스크립트만 별도로 실행하고, Python은
기록된 41개 버전의 wheel만 내려받아 해시 고정·오프라인 설치 및 `pip check`를 수행한다.
사용자 인증 설정/환경변수는 설치 자식 프로세스에 전달하지 않는다. 이것은 별도 경로
검증이지 OS 보안 샌드박스는 아니다. 구형 의존성의 보안성 또는 운영 적합성을 인증하지 않는다.
`compare`는 기존 파일과 재설치 파일의 해시를 관리본에 기록하고, 경로가 포함된 Python
실행기/가상환경 설정·bytecode·설치 메타데이터와 그 외 차이를 구분한다. 원본·검증용
설치본 모두 자동 삭제하지 않는다. 앱 실행·전체 빌드·서버 설치·의존성 업그레이드도 하지 않는다.
해석되지 않은 차이는 원래 비교 기록을 덮어쓰지 않고 `gap_review`에 별도로 검토한다.
이번 실행의 Python 실행기 21개는 PE stub/내장 진입점 코드가 일치하는지 확인했고,
Vitest 과거 결과 1개는 원본 바이트·SHA256을 관리본에 base64로 보존했다. 과거 결과를
현재 재설치 환경에서 테스트를 다시 통과한 증거로 사용하지 않는다. `cache`는 내려받은
npm 원본과 wheel의 해시를 확인하여 같은 실행 기록에 추가한다. 브라우저 다운로드 ZIP은
보관하지 않았으며 npm의 완전 오프라인 재설치는 별도로 실행하지 않았다.

`node scripts/plan-dependency-cleanup.cjs`는 재설치 차이 검토가 끝난 고정 실행에 대해
**삭제 없이 목록만 확정**한다. 구형 체크아웃의 의존성 네 폴더와 검증용 Node 두 폴더,
Python 가상환경, Node compile cache만 후보로 삼고, 파일별 SHA256과 정확한 시각 문자열을
같은 관리본의 `audits`에 기록한다. 원본 Git/추적 소스/배포 패키지는 남긴다.
복원용 npm·Electron 다운로드 캐시, wheel, 새 브라우저 트리, 입력과 로그는 전부 보존하며
별도 이관 전까지 `.tmp/dep-<GUID>`에 남아 있어도 **일반 임시 파일로 삭제하지 않는다**.
과거 Vitest 결과는 관리본에 보존된 원본 바이트/해시를 재확인한다.
`read-dependency-use.ps1`은 읽을 수 있는 프로세스·서비스·예약 작업·바로가기 참조를
요약하고, 참조가 있으면 계획을 보류한다. 참조 0건도 전체 열린 핸들이 없다는 증명은 아니다.
이 계획은 기존 삭제 실행기의 입력이 아니며, 별도 승인과 삭제 직전 경로/해시/권한/ADS/
사용 상태 재검증 및 파일별 삭제 기록 없이는 실행할 수 없다. 새 브라우저 복원본의
물리적 통합 이관과 전체 오프라인 재설치·앱 빌드 검증은 이 단계에 포함하지 않는다.

승인된 고정 계획의 실행기는 `scripts/remove-dependency-cleanup.ps1`이다.
현재 관리본의 외부 SHA256을 주고 `-WhatIf`를 먼저 실행한 다음 같은 해시로 실행한다.
후보 파일을 `FileShare.None`으로 열어 내용·시각·ACL·추가 스트림을 확인하고 유지하며,
복원 파일은 별도 읽기 핸들로 보존한다. 디렉터리의 추가 스트림도 검사한다.
다른 설치/패키지 관리/정리 명령을 동시에 실행하지 않는다. 관찰 불가능한 프로세스 정보나
전역 셸 작업 경로까지 미사용을 입증하는 검사는 아니며 파일 핸들을 닫고 제거하는 사이의
짧은 경합도 완전히 제거하지 않는다. 신뢰되지 않은 쓰기 권한이나 실제 잠금 충돌은 중단한다.
`cleanup.file_states`와 `directory_states`는 관리본 안의 고정 길이 기록이다.
`P`는 대기, `R`은 디스크에 기록한 삭제 요청, `D`는 삭제 후 부재 확인이다.
각 변경을 flush한 뒤 진행하며 중단 시 `R`은 실제 삭제 여부가 불확실하므로 수동 확인한다.
파일 뒤에는 기록된 빈 디렉터리만 `LiteralPath`로 비재귀 삭제한다. 권한 변경·강제 프로세스
종료·자동 재시도는 하지 않는다. `scan`과 `verify`는 미완료 cleanup을 거부한다.
완료 후 `scan`은 복원 자료를 `PROTECT_DEPENDENCY_RECOVERY`로 유지하고 `verify`는
삭제 부재·보존 해시·항목별 완료 기록을 재검증한다. 구형 환경 재사용은 보존 자료로
별도 재설치가 필요하고, 생성 파일의 과거 바이트까지 되돌리는 복원은 보장하지 않는다.
`record-dependency-acl-hold <관리본 SHA256>`는 삭제 전 권한 중단 결과와 8개 루트의
현재 ACL, 모든 후보의 존재를 같은 관리본에 기록하는 읽기 전용 감사다. ACL은 변경하지
않는다. 미해결 `HOLD_ACL_TRUST_UNRESOLVED`가 있으면 삭제 실행기는 재실행을 거부하며,
계정 출처 확인이나 별도 승인된 제한적 ACL 조정 없이 허용 SID를 넓혀 통과시키지 않는다.

`repair-dependency-acl.ps1`은 별도 승인된 재설치 검증 폴더 네 개에만 적용한다.
82,283개 경로별 원래 ACL을 관리본의 SDDL 풀과 매핑으로 먼저 저장하고, 루트 DACL만
4회 수정한다. 소유자·그룹, 상위 폴더, 복원 자료와 구형 소스의 권한은 변경하지 않는다.
전체 자식 상속·경계 ACL 및 74,664개 파일의 해시·수정/생성 시각을 재검증한 뒤 기존 HOLD를
해결 감사에 연결한다. 실패 시 자동 복원/재실행/삭제 없이 멈추며, 미완료 감사가 있으면
다른 관리본 갱신도 차단한다. 변경 전 ACL 복원은 별도 검토가 필요하다. 이 실행은 단일
작업자와 동시 패키지 작업 없음이 전제이며 상위 폴더 교체에 대한 보안 샌드박스가 아니다.

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
