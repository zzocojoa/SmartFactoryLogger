# 프로덕션 출시 리스크: 설계와 구현 착수

작성일: 2026-10-10. 기준: `codex/production-release-risk-validation-20261010`,
`eb9af6f1398d588733f3f1884411e2612496d267`.
계획: [기준 플랜](../../01-plan/features/production-release-risk-validation-codex-production-release-risk-validation-20261010.plan.md).

정책 갱신: 2026-10-12 사용자는 인증서 없이 앞으로도 미서명으로 운영하도록 지시했다.
현재 대상은 최종 clean commit의 미서명 내부 운영 NSIS 설치본이다. 인증서/서명 담당자·서명 환경·
서명자·유효 서명·타임스탬프 요구를 제거하고 `NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY`로 기록한다.
실제 installer/앱은 `NotSigned`로 확인하며 서명 PASS를 만들지 않는다. 아래 R1~R5 기술 조건과
R6의 출처/무결성·설치/복구·현장 QA 조건은 유지한다. 과거 서명 조사·봉인 증거는 당시 기록이다.

## 1. 아키텍처와 확인된 상태

Electron이 FastAPI backend의 시작·정상 종료를 관리하고 React 화면이 HTTP API를 조회한다.
backend는 PLC·SPOT 수집, 온도 상태/설정 provenance, CSV logger,
observation/image fact와 종료 증거를 연결한다. SPOT 이미지 저장은 bounded queue와
단일 writer thread를 사용한다. 현재 후보는 정확한 clean commit/버전·태그에서 미서명으로 빌드하고
payload 출처·manifest/provenance·SHA256과 실제 `NotSigned` 상태를 검사한다.
기존 서명 workflow/검사기는 별도 서명 경로로 보존하며 이번 운영 후보의 실행 gate에서 제외한다.

착수 시 HEAD/master/origin/master는 모두 위 기준 commit이다. 기존 변경은 계획 문서와
PDCA 상태이며 제품 코드는 기준과 동일하다. 실제 운영본은 `541d701d…` / `08C061EE…`,
교체 전 이전본은 `4c97d4a…` / `D453C1D1…`이다. 소스 기준과 운영 설치본을 혼용하지 않는다.

원본 적용 후 검토에는 최초 timeout 원인 `UNCONFIRMED`, 첫 health `223.4887ms`,
과거 image drop 15건이 남아 있다. 최근 누락 0건·설정 보존·미서명 내부 승인은
R1~R6의 완료 증거가 아니다.

## 2. 여섯 항목의 책임과 완료 기준

사용자는 유지보수를 아무 때나 수행해도 된다고 승인했다. 실명 담당자·검토자와 승인 장비 프로파일은
Codex가 서버 기록에서 직접 확인한다. 2026-10-12 서버 연결이 복구돼 과거 Operator1 기록과 현재 fingerprint mismatch를 확인했다.
당시 아래 역할의 실제 지정과 승인 실장비 프로파일·최종 attestation은 미완료였다.

2026-10-12 후속 직접 답변 “모두 본인”으로 장비·운영 확인, QA, 릴리즈 판단 담당자를
모두 사용자 본인으로 확정했다. 위 문장의 역할 미지정은 당시 상태이며 현재 승인 실장비
프로파일·최종 attestation과 기술 QA는 계속 미완료다. Codex는 개발·회수·검증 실행을 담당한다.

| ID | 담당 역할 | 조치 사항 | 검증 방법 | 완료 기준 |
|---|---|---|---|---|
| R1 최초 timeout | Backend 엔지니어 / QA | 원본 요청 순서·서비스 세대·시간선 복원. 연결/응답/본문/JSON/서버 처리·잠금/파일 I/O 분리. 인과가 입증된 병목 수정 | 격리 환경의 작은/실제 규모 fact, 느린 디스크, 초기화 중 동시 health. 수정 전 실패/후 통과·계측 유무 비교 | 원본 사건과 일치하는 인과 증거 및 첫 요청 포함 재발 0. 부족하면 UNCONFIRMED/HOLD |
| R2 전체 성능 | 성능 QA / Backend·Frontend | 조건/도구 고정, 초기 시작 격리 10회·현장 3회, 1/3탭, 동시 저장, 전체 API·화면·자원 수집 | health 2초 주기 비중첩, first/max/p50/p95/p99/timeout/error. 자원 warmup120초·5초·300초·선호60/최소48표본·최소240초. 새 미서명 개선 후보 15분/120분 | 각 client health≤200ms·timeout0·시작≤30초·전체 필수 계약/측정 누락0. 50ms 경고 별도, 223.4887ms 보존 |
| R3 장비 설정 | 장비/운영 담당 / 설정 엔지니어·QA | 승인 모델·모드·범위·방사율·LowSignal·comparator·통신 프로파일과 실제 화면/readback/파일 대조. 최종 build attestation | 임계값 미만/동일/초과, build·fingerprint·config_drift·runtime·동일 세대 종료 sidecar. not_supported는 실제 운영자 확인 | 필수 불일치/미확인0·drift0·동일 fingerprint·운영자 확인. fingerprint만으로 실장비 적합성을 선언하지 않음 |
| R4 전수 데이터 | 데이터 무결성 QA / 수집 엔지니어·운영 | 전체 과거/현재 CSV·metadata·fact·manifest·이미지·영수증 목록/해시와 일관된 사본 확보. 스키마별 검사와 전체 이미지 해시/디코딩·역참조·종료 delta | 기존 CSV validator 전체 규칙 + 이미지 실물 검사. streaming/index와 작은 동일 입력 대조, 시작/종료 목록·해시 비교 | 검사/분류100%·수량/바이트 정산·미분류0. 후보 손상/설명 없는 누락/불일치/미완료 종료0. 과거 실패 처리 결정 별도 |
| R5 과거 drop15 | SPOT 엔지니어 / 데이터 책임자·QA | 이전 build의 동일 drop 경로 대조, 크기 초과/큐 포화/worker 실패/정책 제외/retention 구분. 카운터·fact·로그·event 시간선 정산 | 격리 크기 경계/큐 포화/느린 저장/디스크 부족/권한 거부/정상 종료 drain. 원인별 회귀·새 정상 운전 | 과거15건의 원인·영향·복구 가능성·처리 결정 증거, 예방 회귀 통과·새 drop/저장 실패0·정상 종료. 과거 증거 부족이면 HOLD |
| R6 미서명 패키지/정식 QA | 릴리즈 책임자 / 보안·QA·운영 | 사용자 미서명 정책·버전/태그 재확인, 최종 clean commit 고정·미서명 빌드·전체 NSIS payload 추출, 동일 설치본으로 신규/업그레이드/재시작/복구/현장 QA | installer/Electron NotSigned, 요구 서명 판정 NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY, commit/tag/SHA256/payload/provenance. health/build/관련 도구 회귀 및 FINAL PASS·validator0·동일 세대 정상 종료 | 정확한 최종 미서명 설치본의 필수 소스/패키지/설치/복구/설정/성능/데이터/현장 QA 모두 통과. 인증서 부재는 HOLD 사유에서 제거, 미서명 운영 승인은 기술 QA를 대체하지 않음 |

기존 성능 계약은 health 50ms 경고/200ms 실패, data 100/500ms,
SPOT 이미지 500ms 경고(실패 상한 미정), LCP 2500/4000ms, CLS 0.1/0.25다.
이번 계획의 각 client health≤200ms 조건과 기존 server 관측 계약을 구분한다.

## 3. 이번 로컬 구현의 입출력과 실패 조건

### 3.1 R1: writer 생성 잠금 분리

수정 전 확인된 코드 경로: `_get_spot_image_capture_writer` → constructor →
`_initialize_manifest_state` → 전체 fact 해시 + CSV 행 수 계산이
`_spot_image_capture_lock` 안에서 실행된다. 같은 잠금을 producer·종료 snapshot도 쓴다.
과거 서버 사건과의 인과는 아직 입증되지 않았지만, 느린 constructor가 종료 조회를
막는 현상은 격리 회귀로 증명할 수 있다.

- writer의 생성/재사용/설정 signature는 별도 `_spot_image_capture_writer_lock`으로 직렬화한다.
- 기존 상태 잠금은 counter·queue outcome·shutdown baseline의 atomic transition을 유지한다.
- 상태 잠금을 writer/file 잠금과 중첩하지 않는다. constructor·fact I/O·join을 상태 잠금 안에 넣지 않는다.
- constructor가 멈춰 있어도 memory-only shutdown snapshot을 읽을 수 있어야 한다.
- hash/row 검사·dedupe·manifest fail-closed·설정 경로 변경 계약을 유지한다.
- 이 수정만으로 최초 `/api/spot/config`의 동기 fact scan이나 200ms 성능이 해결됐다고 하지 않는다.

2026-10-12 추가 보완은 설정 조회에만 대기 없는 manifest snapshot을 사용한다.
서버에서 회수한 fact의 4,091,827행 prefix가 과거 metadata의 SHA256과 정확히 일치했고,
격리 HTTP 시험에서 같은 입력으로 첫 5초 timeout과 약 20초 초기화를 재현했다.
이는 원본 서버 사건의 인과를 확정하는 로그와 구분한다.

- `/api/spot/config`는 writer를 생성하지 않으며 생성 중인 writer/file 잠금을 기다리지 않는다.
- 미생성·생성 중·다른 경로·파일 잠금 사용 중이면 `fact_row_count=null`, `fact_sha256=null`,
  `fact_manifest_state_ready=false`로 미확인을 명시한다. 미확인을 0행/PASS로 해석하지 않는다.
- 이미 준비된 같은 설정의 writer는 파일 잠금을 즉시 얻을 때만 행 수·digest를 한 snapshot으로 읽는다.
  외부 크기 변경/읽기 오류는 digest를 미확인으로 만들고 기존 fail-closed 상태를 유지한다.
- 시작 metadata, worker, 종료 manifest의 기존 대기/전수 검사 경로는 유지한다.
  새 background initializer·hash 생략·retention 변경을 추가하지 않는다.
- 실제 HTTP 초기/초기화 중/완료 후의 제한된 세 표본은 전체 R2 성능 계약이나 서버 현장 PASS가 아니다.

### 3.2 R5: 원인별 drop 계수

- 기존 `dropped_count`와 별도로 `dropped_oversize_count`, `dropped_queue_full_count`를 추가한다.
- 각각 실제 크기 초과/QueueFull 분기에만 계수하고 health와 종료 snapshot에 노출한다.
- 정상 정책 제외·interval 제외·worker failure는 drop으로 계수하지 않는다.
- 정상 종료나 성공 저장은 과거 계수를 초기화하지 않는다. test reset만 기존 격리 방식으로 초기화한다.
- 기존 CSV/fact/manifest 스키마는 변경하지 않는다. 새 필드는 과거15건의 원인 소급 분류가 아니다.

### 3.3 R2: client 응답 시간과 관측 요약

- `Invoke-ReadOnlyEndpoint`에서 `Stopwatch`로 요청 시작부터 전체 본문 수신/오류 본문 처리까지 측정한다.
- 성공·HTTP 실패·timeout 모두 `client_elapsed_ms`를 raw envelope/raw index에 보존한다.
- JSON parsing·서버 내부 시간은 포함된 것으로 주장하지 않는다. 연결/TTFB 세분화는 후속 계측이다.
- health 원시 표본을 첫 값·최대·nearest-rank p50/p95/p99, error/timeout/미측정/200ms 초과 건수로 요약한다.
- 첫 실패를 제외하지 않고 필수 시간 누락/비정상 값은 NOT_MEASURED, HTTP 실패/시간 초과는 FAIL로 남긴다.
- 이 요약은 수집된 요청의 관측 판정이다. 기존 수집기의 주기/다중 endpoint 순서는 유지하며,
  정식 R2의 전용 2초 sampler·시작/화면/자원·15/120분 gate를 대체하지 않는다.
- sanitized image 상태에도 새 원인별 계수를 전달하고 CI QA selftest에 수집기를 등록한다.

### 3.4 R4: 선택 fact와 이미지 사본 실물 검사

- `scripts/validate_spot_image_files.py`는 선택 fact를 CSV streaming으로 읽고 이미지 SHA256/크기,
  모든 프레임의 디코딩, 기록된 MIME/치수를 확인한다. 기존 CSV 스키마 검사와 함께 사용한다.
- SQLite 인덱스로 ID/경로 중복과 전체 이미지 역참조를 확인한다. Windows 대소문자 별칭은 동일 파일로 정산한다.
- 이미지 폴더 전후 목록/stat/SHA256 및 fact 전후 identity/hash를 보존한다. 변경·누락·고아·불명 파일은 실패다.
- 경로 이탈·ADS·symlink/reparse를 거부하고 입력 밖의 새 결과 폴더만 허용한다. 기존 출력이나 원본을 덮어쓰지 않는다.
- `scope=copied_image_subtree_and_selected_fact`, `full_data_gate=NOT_EVALUATED`를 항상 기록한다.
  전체 snapshot 일관성·모든 CSV/metadata/manifest/영수증·시작/종료 delta의 R4 완료 판정은 별도다.
- 회귀 파일 `backend/tests/test_spot_image_file_validation.py`는 Windows 대소문자·해시/크기·디코딩·
  경로·누락·역참조·입력 보존·출력 재사용을 검사한다. 제품의 기존 저장/보존 스키마는 변경하지 않는다.

## 4. 검증 순서와 작업 경계

각 결함은 실패 회귀 1개 → 수정 → 해당 회귀 통과로 진행한다.
추가 경계: 동시 writer 요청 단일 생성, 생성 실패 후 재시도, 실제 fact 해시/행 수,
크기 상한 동일/초과·큐 포화·정책 제외, 정상 drain/과거 실패 보존,
첫 지연/200ms 경계/오류/timeout/누락·비정상 timing/본문 수신 계측.

최종 상태에서 관련 backend 모듈 검사, PowerShell 수집기 selftest,
`npm run health`, `npm --prefix frontend run build` 및 `git diff --check`를 실행하고
원시 출력과 종료 코드를 보존한다. 패키지/실장비/성능을 로컬 단위검사의 통과로 대체하지 않는다.

이번 착수는 로컬 소스·도구·문서 수정이다. 원본 증거·운영 설치본·장비 설정·서명 비밀·
기존 workflow 승인·rollback 기준은 유지한다. 유지보수 시간은 언제든 가능 승인을 적용한다. 현장 진입은 책임자/승인 프로파일과
정확한 후보 설치본이 준비된 후 기준 계획의 단계 순서를 따른다.

## 5. 후속 PDCA와 증거 양식

| 단계 | 실행 | 산출물과 종료 gate |
|---|---|---|
| Plan | 여섯 책임자/검토자·승인 프로파일·전체 데이터 범위·유지보수 시간 확정 | 원본 실패/운영본/복구 설치본 출처와 범위 고정 |
| Do | 이번 회귀/수정 + 원본 시간선 분석, 전체 사본 확보, R3/R4 도구 보완, 격리 장애 재현 | 수정 전후 증거·전수 입력 manifest·설정 attestation. 원인 미확정은 HOLD |
| Check 후보 | 최종 소스 검사 → 버전/태그 확인 → 정확한 clean commit의 미서명 빌드 → payload/출처/해시·NotSigned → 격리 설치/복구 | 동일 installer SHA256에 결합한 소스·패키지·설치·복구 결과 |
| Check 현장 | 조건/백업 확인 → 정상 종료·승인 설치/설정 → QA → 초기15분/canary120분 → 전체 새 데이터+delta | 동일 build/logger/fingerprint·성능·CSV/이미지·정상 종료, 여섯 DoD 통과 |
| Act | 실패 보완/영향 검사 재실행, QA/릴리즈 결정, 승격·적용 확인 후 기준 갱신 | 새 build/installer를 다음 rollback으로 등록. 이전본·실패 증거 보존 |

서버 자료는 실제 Desktop/SmartFactory의 새 실행 폴더와
`Z:/SmartFactory/YYYYMMDD/{send,return,records}`를 사용한다. Codex가 공유 전송과
Chrome 원격 데스크톱의 서버 최종 폴더 복사·절대경로/파일 확인까지 맡는다.
공유 업로드만으로 전달 완료라고 하지 않는다. 실제 서버 결함 주입/강제 종료/삭제/자동 rollback은 실행하지 않는다.

실행별 기록 예:

```text
run_id / 역할 담당자·검토자 / 승인 범위·유지보수 시간:
source commit / tool SHA256 / installer SHA256·NotSigned·태그 / 미서명 정책 근거:
signature_requirement: NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY
입력 목록 SHA256 / 전체 파일·행·이미지·바이트 수 / 관측 조건:
service/logger 세대 / config fingerprint / 정상 종료 receipt:
R1~R6 각각: FACT 또는 INFERENCE / evidence 경로·해시 / PASS·FAIL·HOLD:
실행 명령 / stdout·stderr / exit_code / 미실행·미측정:
다음 조치 / 재개 조건 / 이전→새 rollback 기준과 적용 확인:
```

## 2026-10-13 이미지 저장 실패 로그의 식별 정보 보완

서버 cold 사본의 stderr에는 PID 12156 구간의 저장 실패 경고 16줄이 있지만
개별 시각·예외 종류·capture ID가 없다. 기존 Oct8 기록도 같은 경고를 확인했다.
이번 16개 orphan JPEG와 fact 시간 간격 대조는 관련성을 보강하며 실제 예외 원인은
여전히 미확정이다. 현재 코드에서도 `extra.error_type`이 기본 로그 형식에서 누락되므로
확인된 보완 범위는 실패 로그의 추적 가능성이다.

1. 기본 `StreamHandler`에서 실제 fact append 실패 후 다음 capture 성공을 재현한다.
2. 기존 경고 본문에 JSON으로 실패 시각, capture 시각/ID/SHA256/크기, service ID,
   실패 누계, writer 초기화/저장 단계, 예외 종류와 숫자 errno/winerror를 남긴다.
   원본 예외 문자열·URL·경로·이미지 본문·관측 스냅샷은 포함하지 않는다.
3. 큐 완료와 실패 누계의 원자성, 후속 capture 처리, 실패가 있는 정상 종료의 FAIL을
   유지한다. 잘못된 capture 시각 때문에 진단 기록이나 다음 처리가 중단되지 않아야 한다.
4. 수정 전 실패/수정 후 성공, 관련 회귀와 최종 `npm run health`를 실제 exit와 기록한다.

통과 기준은 회복 후에도 로그 하나로 실패한 고립 이미지 바이트를 식별할 수 있는 것이다.
저장 방식·자동 복구·서버 설치는 이 변경에 포함하지 않는다. R5 원인 판정은 HOLD다.

## 2026-10-13 현장 준비 패키지의 식별 계약

후보1.0.28/4cc7393e/8821746b와 현재 롤백541d701d/08C061EE를 동일 묶음에 보존한다.
`scripts/field-v1028/verify-field-package.ps1`은 외부 고정 manifest SHA와 전체 선언 파일의
잠긴 read handle로 정확한 목록·크기·SHA·미서명 상태·기존 payload/backend/QA 출처를 검사한다.
파일 경로와 실제 reparse, 변조된 버전/출처 및 승인 주장도 거부해야 한다.
성공 범위는 전달 패키지 확인이며 installed tree/현장 QA와 분리한다. 성공 시에도
설치·canary·승격 false/HOLD다. 자동 설치·HTTP·프로세스/설정 변경은 포함하지 않는다.
같은 잠긴 도구 바이트를 실행하는 launcher와 전체 현장 수집·판정은 후속 단계다.
정상2·부정16 실행과 서버 최종 경로/파일 존재 근거는
[패키지 보고](../../04-report/production-release-risk-validation-field-package-20261013.report.md)에 기록한다.

### 같은 잠금 바이트 실행과 결과 보존

`invoke-field-package-read.ps1`은 전달 검증기56144abd와 manifest58012882를 고정한다.
관리자 네이티브 PS5.1에서 새 결과 자식 폴더만 만들고 부모/패키지/운영본은 변경하지 않는다.
외부 고정 SHA의 bootstrap이 컨트롤러를 잠가 읽고, 컨트롤러의 새 자식 프로세스도 검증기를
잠금→길이/SHA 확인→동일 스트림 UTF-8 해석→ScriptBlock 실행 순서로 처리한다.
해시 뒤 `-File`로 경로를 다시 열어 실행하지 않는다. 부모와 자식의 입력 경로를 검사한다.
결과 ACL은 Administrators/SYSTEM 쓰기와 운영자 읽기이며 기존 경로·reparse·240자 초과를 거부한다.
stdout/stderr/구조화 결과/manifest를 새 파일로 쓰고 결과 경로·manifest SHA를 콘솔에 출력한다.
120초 상한은 이 도우미가 직접 만든 검증 자식에만 적용하며 앱 프로세스는 제어하지 않는다.
검증 기준: 정확한 바이트 실행, 변조/경로 거부, 실행 중 쓰기·삭제 잠금, 실패/timeout의 HOLD,
결과 원문·해시·새 경로/ACL·재실행 보존, 비관리자 무변경 거부다. 개발 PC 권한 치환 fixture와
실제 관리자 서버 실행을 구분하며, 후자가 끝나기 전 서버 hash 검증 완료로 표시하지 않는다.
