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

### 현장 HTTP 계측의 독립 주기와 전체 응답 경계

`field_http_sampling.py`는 후속 현장 collector에서 사용할 loopback HTTP 수집 모듈이다.
health2초/data6초/image250ms 각각 단일 worker와 같은 monotonic 원점을 사용한다.
느린 이미지·본문 해석·결과 쓰기가 다른 endpoint의 예정 요청을 직렬로 막지 않는다.
각 worker는 요청을 겹치지 않게 하고 지나간 슬롯을 누락 기록으로 남긴다. 지연 뒤 burst로
과거 슬롯을 메우지 않는다. 첫 요청·최대·분위수·HTTP 실패·timeout·스케줄 지연을 보존한다.

연결·송신·헤더 대기·본문 수신과 JSON/JPEG 해석을 분리한다. socket의 각 blocking read에
단일 요청의 남은 deadline을 적용하여 조금씩 계속 들어오는 헤더/본문도 무한 대기하지 않는다.
전체 본문을 받지 못한 성공 상태 코드, 길이 부족, 잘못된 JSON/JPEG, 크기 상한 초과는 실패다.
부분 본문·원시 헤더·해시·실제 시각을 새 파일로 보존하고 같은 출력 경로를 재사용하지 않는다.
출력/메모리 예산 초과·worker 실패·수동 중단은 불완전 수집으로 기록한다.

이 모듈의 시험은 loopback fixture에서 독립 주기, 느린 헤더/본문의 전체 deadline, 누락 슬롯,
첫 실패 포함 요약, 중단, 파일 충돌과 원문 해시를 확인한다. 제품 실행/종료·장비 요청·설치는 없다.
실제 서버 실행 entrypoint는 아직 제공하지 않는다. 최종 build/프로세스/logger/fingerprint 결합,
보호된 결과 폴더·잠긴 배포 실행, resource/physical disk/web vitals/packet·정상 종료와 합쳐야
전체15분/120분 collector가 된다. HTTP 모듈 성공에도 전체 현장 gate는 NOT_EVALUATED/HOLD다.

요약은 단순한 배열 길이 대신 고유 sequence coverage를 확인한다. NaN/Infinity/음수/bool/null
시간값, 중복·누락 순번은 NOT_MEASURED이며 첫 실패 표본을 삭제하지 않는다. 정상6.2초
fixture의 기본 주기와 느린 이미지에 대한 독립성을 별도로 검사한다. 이 설계의 수집/쓰기
오버헤드는 최종 field collector의 실제 부하 검증에 포함하며 기존 보조 계측 결과로 대체하지 않는다.

### 5.5 프로세스·물리 디스크 및 같은 관찰 시작 시각

`field_resource_sampling.py`는 PID/create-time/exe로 루트를 고정하고 관찰된 자식별 CPU·메모리·
스레드·핸들·I/O를 읽는다. PhysicalDrive는 Windows 원시 DISK_PERFORMANCE와100ns 단위를
보존한다. host 전체 물리 디스크와 프로세스 I/O, RSS 합과 고유 물리 메모리를 구분한다.
구성 변경·읽기 실패·비정상 수치·카운터 감소·누락·중단은 유효 변화량이나 성능 PASS가 아니다.
기본5초·준비120초·관찰300초·최소48표본/240초와 최종 파일 경로240자 예산을 적용한다.
같은 future monotonic origin을 HTTP와 자원 worker에 전달하며 원문에 각자 기록한다.
동기 Windows 조회의 외부 watchdog은 현장 launcher 통합에서 필요하다.

[자원 수집 시험](../../04-report/production-release-risk-validation-resource-collector-20261013.report.md)의
개발 PC420초 관찰에서85/관찰61표본과 두 디스크를 확보했으나 HTTP health1/image17 슬롯이
누락됐다. fetch/해석 반환 후의 지연까지 좁혔으며 정확한 저장/스케줄링 원인은 미확정이다.
HTTP `writes.json`은 원시 파일별 open/write/flush/fsync/close 시간을 보존한다.
계측 추가가 누락 수정 또는 최종 통합/현장 QA 통과를 뜻하지 않는다. native API의 카운터
활성화 효과와 단위·범위·프로세스/장치 식별 한계도 보고서와 결과에 기록한다.

### 5.6 느린 원문 저장과 요청 주기의 분리

HTTP 응답/해석 뒤의 원문·JSON 저장은 하나의 전용 worker로 처리한다. 대기열 기본 한도는
256레코드·직렬화된 metadata+body64MiB이며 저장 중 레코드도 계산한다. 초과 시 수집을 실패로
중단하고 일부 미보존 슬롯을 PASS로 세지 않는다. 전체 body4GiB 예산도 별도로 유지한다.
요청 worker는 비중첩·원래 주기를 유지하며 밀린 요청을 연속 실행하지 않는다.
저장 worker가 body→metadata를 각각 flush/fsync/close한 뒤에만 해당 요청을 persisted로 센다.
수동 중단도 이미 수락한 자료를 배출한 뒤 FAIL을 기록한다. 저장 실패는 생성된 부분 파일의
실제 크기/해시·failed_write 표시와 오류를 보존하고 성공 판정을 차단한다.
대기/최대 적체·제출/저장/폐기 수·배출 시간·파일별 저장 시간을 분리한다. 아직 메모리에 있는
대기 자료는 내구성이 확정되지 않았으며 프로세스 손실 시 완전한 manifest가 성립하지 않는다.
동기 파일/드라이버 호출이 무기한 멈출 경우의 외부 watchdog은 현장 launcher 통합 조건이다.
검증과 실패 기록은 [저장 분리 보고](../../04-report/production-release-risk-validation-persistence-20261013.report.md)에 연결한다.

### 5.7 설치 파일과 관찰된 실행 식별값의 결합

`field_installation_binding.py`는 고정 reference SHA의 후보 payload 전체 기본 스트림과
clean provenance를 확인하고 read-sharing 핸들을 컨텍스트 종료까지 유지한다.
NSIS 추가 파일은 별도 출처의 정확한 크기/SHA가 있어야 허용한다. 경로·reparse·hardlink·
파일 집합·바이트 제한을 적용하며 종료 전 `recheck()`로 이름/ID/해시를 다시 대조한다.
OS의 PID/create-time/exe, main→backend 관계, IPv4/IPv6 listener 소유자를 health GET 앞뒤로
읽고 version/frozen/REAL/build, SPOT/CSV logger UUID를 결합한다. 모호함·권한 오류·
서비스 교체는 FAIL이다. raw body와 HTTP 계측을 보존하며 식별용 첫 GET도 전체 성능 판정에 포함한다.
이 구성요소의 PASS는 표본의 식별 범위이며 서버 전체/실행 메모리/표본 사이 무변경의 증거가 아니다.
최종 fingerprint·authenticated backend generation·watchdog·화면/packet/종료 경계와의
전체 collector 통합은 계속 필요하다. 개발 PC23시험, 실제 추출1814파일 및 기존15표본 파서
검증의 범위는 [식별 결합 보고](../../04-report/production-release-risk-validation-installation-binding-20261014.report.md)에 기록한다.

### 5.8 같은 관찰 구간과 계측 프로세스의 종료 범위

`field_observation.py`는 초기 설치/실행 식별 검사를 통과한 뒤 하나의 future monotonic 원점으로
HTTP·자원·OS 식별 조회를 각각 별도 프로세스에서 실행한다. 첫/마지막 식별용 health GET과
관찰 중 모든 health 본문에 같은 SPOT/logger UUID·build·backend 경로를 요구한다.
원문 manifest의 정확한 파일 집합·크기·SHA를 재검산하고 자원 표본마다 backend 식별값을 확인한다.
작업 종료 전에 설치 payload를 다시 검사한다. 짧은 개발 시험의 자원 범위는 NOT_MEASURED이며
420초 이상 관찰은 기존 준비120초/측정300초 coverage 조건도 만족해야 한다.

Windows 대기 함수 반환 뒤 monotonic deadline을 다시 확인하여 예정 시각 전 요청을 방지한다.
HTTP 요청과 동기 native 조회는 별도 Python 프로세스에 둔다. GIL을 유지한 native 호출350ms의
제어된 재현은 이전 thread 구조의 이미지4슬롯 누락과 새 구조의 누락0을 확인했다.
이 결과를 기존 서버 timeout/drop 또는 주입하지 않은 host 지연의 원인 확정으로 확대하지 않는다.

`field_windows_job.py`는 새 감독 자식의 생성 HANDLE을 이름 없는 Windows Job에 등록한 뒤
실행 gate를 연다. 기존 관찰 대상 앱은 Job에 넣지 않는다. 준비/최종화 예산은 각각 최대180초,
관찰은 최대7200초이며 finalizing 이벤트가 전체 deadline을 연장하지 않는다.
종료·시간 초과·감독 프로세스 손실 때 Job의 계측 자식만 정리하고 실제 앱은 계속 실행한다.
IPC 누락/과대 frame·해시 불일치·원문 손실·첫 health 지연·서비스 교체·중단은 FAIL/HOLD다.
부모의 결과 쓰기까지 감싸는 보호된 외부 launcher, generation/fingerprint, 화면/packet/정상 종료
증거와 실제 서버 설치/복구/15분/120분 QA는 여전히 필요하다. 이 API는 서버 실행 entrypoint가 아니다.

### 5.9 인증된 백엔드 세대의 시작·종료 경계

`field_generation_binding.py`는 잠긴 payload와 main/backend 경로를 확인한 후 OS 식별·listener를
대조한다. 선택한 backend의 환경 API에서 embedded 표시·control token·generation만 사용한다.
환경 사전 전체나 token/request header를 결과로 보존하지 않는다. 환경 조회 앞뒤와 GET 뒤의
OS 식별값을 대조하고 접근 거부·프로세스 변경·누락 값은 실패로 처리한다.
토큰을 보낼 수 있는 곳은 고정 `127.0.0.1:<확인한 포트>/api/control/health`의 GET뿐이다.
기존 전체 요청 deadline과 크기/JSON 제한을 사용하며 redirect는 따라가지 않는다.
응답에 토큰 원문·대소문자 변형·ASCII JSON unicode escape가 있으면 본문/헤더를 보존하지 않고 FAIL이다.
환경 조회 예외는 타입만 기록하여 provider가 포함한 민감 문자열의 전달을 막는다.

실제 후보 소스의 PID·32자리 generation·12자리 session·UTC 시작 시각 계약을 검사한다.
첫 인증 GET과 종료 인증 GET은 각각200ms 조건을 적용하며 같은 identity를 요구한다.
첫 인증 실패는 주기 관찰을 시작하지 않고, 종료 실패는 전체 관찰을 FAIL로 남긴다.
이 검사는 시작·종료 경계 표본이며 모든 중간 순간의 증거는 아니다. 장비 fingerprint/attestation,
보호된 외부 실행기·화면/packet·정상 종료/최종 delta·실제 현장 QA는 별도로 남는다.

### 5.10 최종 설정 기준과 runtime fingerprint의 경계 대조

2026-10-14 사용자 승인에 따라 `sfl-field-configuration-disabled-low-signal-v1` 기준을 추가한다.
기존 v1 기준의 comparator=true 조건은 유지한다. 추가 기준은 승인된 관찰 프로파일 SHA와
시험 순서 승인 SHA `6517011d8f51eb4cff560bf83c8dcbb471bd4add99f21cdac59387d3d1c93685`,
Low Signal off, configured/effective comparator=false를 모두 요구한다. 다른 검사는 동일하다.
기준 JSON의 외부 고정 SHA를 먼저 검증하고, 해당 승인 SHA/전용 schema를 확인한 reader만
검증 범위를 담는 ReferenceSnapshot을 만든다. 장비 HTTP JSON의 추가 필드는 제한 모드를
선택할 수 없다. 이후 runtime·정상 종료 검사는 같은 기준 객체와 정확한 fingerprint를 대조한다.
결과에 DISABLED_LOW_SIGNAL_FIELD_TRIAL·physical NOT_TESTED·formal QA HOLD를 명시하며
수집/데이터 구성요소의 PASS를 정식 QA PASS로 확대하지 않는다. 기본 경로와 거부 검사를
함께 검증하고 설정 도우미의 한정 확인 경로도 같은 승인·미검증 상태에 결합한다.

최종 후보의 실제 attestation에서 작성한 설정 기준 JSON을 외부 SHA로 잠가 읽는다.
기준은 승인된 관찰 프로파일 기록의 SHA와 연결하고, USER_SELF의 최종 fingerprint/설정 SHA,
build·운영자 확인·UTC 시각·readback/comparator 상태를 포함한다. 현재 존재하는 운영본의
fingerprint_mismatch를 고치거나 승인 기록만으로 최종 기준을 자동 생성하지 않는다.
테스트용 기준과 실제 최종 기준은 구분하며 보호된 launcher가 실제 기준 SHA를 고정해야 한다.

`/api/spot/config`의 image 진단에서 제품 소스와 동일한22개 fingerprint 입력을 선택해
canonical JSON SHA256을 재계산한다. 필수 값/타입·프로파일의 소프트웨어 대응 필드·별칭을
검사하고 불일치·미검증·drift·기준 변경은 실패로 남긴다. 원문과 판정 이유를 보존한다.
설정 GET 앞뒤 OS 식별·같은 SPOT 서비스와 관찰 시작/종료의 고정 기준을 결합한다.
초기 실패는 주기 수집 전 중단하고 종료 실패는 관찰 전체를 FAIL로 남긴다.
설정 endpoint의 임의 성능 상한을 새로 만들지 않으며 기존 전체 요청 timeout을 적용한다.
이 검사는 API가 보고한 설정과 attest 정보의 무결성/일치다. 물리 장비 readback·comparator
실증·기준의 실제 승인 확인·정상 종료 metadata와의 최종 대조를 대신하지 않는다.

### 5.11 관찰 종료 health와 정상 종료 sidecar의 연결

관찰 마지막의 검증된 health 원문에서 build·logger UUID·schema·현재 CSV 파일명·마지막
sample 번호를 추출하고 원문 SHA와 함께 `shutdown-expectation.json`으로 보존한다.
필수 값 누락·잘못된 타입·경로·원문 해시 불일치는 관찰 실패다. 후속 보호된 실행기는
성공한 감독 결과와 이 파일의 해시를 연결해야 하며 파일 자체를 현장 승인으로 취급하지 않는다.

`field_shutdown_binding.py`는 이 기대값의 정확한 CSV/sidecar 이름만 읽는다. 최신 시각이나
glob의 첫 파일로 대체하지 않는다. 기본 스트림을 읽기 공유로 잠그고 크기·SHA·파일 식별을
전후 대조하며 pinned 최종 설정 기준도 함께 유지한다. sidecar 양쪽 build/logger, schema,
hardening, finalized=true, reason=shutdown, final sample>=관찰 sample 및 설정 fingerprint/
attestation을 검사한다. `persisted_at`은 마지막 저장 시각으로만 검증하며 종료 시각으로
해석하거나 관찰 이후여야 한다는 조건을 만들지 않는다.

성공 범위는 관찰 기대값과 종료 파일의 식별/설정 연결이다. 정상 종료 실제 수행/프로세스 소멸,
CSV 전체 행·fact/image 연결 검사는 별도다. PASS에도 field/full CSV/normal shutdown gate는
NOT_EVALUATED이고 release는 HOLD다. 앱 종료·설치·설정 변경은 이 모듈에 포함하지 않는다.
최종 caller는 이 결과의 파일 해시와 full validator가 읽은 바이트를 다시 결합해야 한다.

검증은 합성 기준과 native 파일 잠금, 누락/교차 logger·build·파일·sample·schema·미완료 종료,
설정 변조 및 실제 보존 I4/I5 후보 sidecar를 사용한다. 실제 기록의 미검증 attestation은 FAIL로
유지한다. 기존 CSV validator의 opt-in `--require-current-server-promotion-profile`은 특정
과거 운영값(comparator verified=false 포함)의 회귀 조건이다. 최종 QA 실제 호출처럼 일반
CSV 계약을 검사하고 별도의 최종 pinned attestation 조건을 적용하며 과거 상수는 바꾸지 않는다.

### 5.12 전체 CSV 계약과 JPEG 바이트 검사의 별도 실행 파일

기존 `validate_spot_image_files.py`를 후보4cc의 clean source와 잠긴 의존성 환경으로 패키징한다.
제품/설치본과 기존 CSV 검사기 바이트는 변경하지 않는다. frozen 실행의 `__file__` 해시 기록을
유지하기 위해 같은 원본 스크립트를 데이터로 동봉하고, 실행 결과의 tool SHA도 대조한다.
빌드 전후 전체 tracked source·의존성·installer SHA와 새 EXE provenance를 보존한다.

실제 보존 I4/I5 종료 사본의 이미지 subtree와 fact를 전수 검사한다. 외부에서 고정한 원본
목록/크기/SHA를 복사 전후 확인하며 같은 입력으로 Python과 EXE의 요약·판정을 비교한다.
복사본에만 이미지 누락·바이트 변조·fact와 SHA를 맞춘 디코딩 불가 파일·고립 파일·최종
manifest 불일치를 주입한다. 기존 CSV 검사기만 통과하는 이미지 오류와 별도 이미지 검사만
통과하는 manifest 오류를 보존한다. 두 결과를 함께 사용하며 어느 한 검사로 전체 QA를 대신하지 않는다.

이 단계는 도구 준비와 보존된 격리 후보 자료의 검증이다. 전체 운영 데이터/실제 장비/현장
승격 PASS가 아니다. CSV의 부가 fact 경로 소비 범위, 잠긴 입력과 결과/정상 종료의 연결,
보호된 실행기·서버 로컬 전달/실행 및 실제15분/120분 조건은 후속 통합에 남긴다.

구현 확인: portable 이미지 묶음의 서버 로컬 전달/파일 존재는 2026-10-14 r2 영수증으로
확인했다. 서버 로컬 해시·실행 및 보호된 통합 실행기 전달은 아직 미완료다.

### 5.13 CSV 검사기의 모든 데이터 입력 경로 결합

최종 종료 자료에서 선택한 v1/v2/metadata/관찰 fact/이미지 fact/최종 manifest와 선택적
posthoc fact/report를 외부 고정 목록의 SHA·크기에 대조하고 Windows 읽기 공유 핸들로 유지한다.
원본 metadata는 변경하지 않는다. 검사 전용 새 metadata는 posthoc의 fact_path/report_path만
잠긴 사본 경로로 바꾸며 원본·파생본 해시와 정확한 변경 목록을 보존한다. 그 외 모든 필드의
동등성을 확인한다. posthoc CLI override는 SHA/행 수 실패 조건을 완화하므로 사용하지 않는다.

선택적 fact가 외부 목록에 없고 원본 manifest가 row_count=0/sha256=null인 경우에만 부재를
허용한다. 잠긴 일반 파일을 부모로 하는 불가능한 자식 경로로 연결해 검사 중 파일 생성이나
부모 교체가 불가능함을 native Windows에서 검증한다. 값이 없는 fact 파일을 합성하지 않는다.
일치하지 않는 이름·미선언 파일·nonempty manifest·단독 linkage 파일·잘못된 JSON은 거부한다.
기존 CSV 도구가 강제하지 않는 linkage manifest의 report_sha256은 잠긴 report 바이트와 별도로 대조한다.

실제 고정 CSV EXE를 같은 잠금 구간 안에서 실행해 보존 I4/I5 사본, 외부 경로의 오염 파일,
선택적 fact의 올바른/잘못된 행 수·SHA, 최종 manifest 실패를 확인한다. context 종료 오류는
실행 exit0이어도 바이트 결합 PASS가 될 수 없다. 이 모듈은 CSV 입력/소비 경계만 담당한다.
이미지 바이트 검사·정상 종료·attestation·보호된 외부 실행기·최종 현장 QA는 함께 연결해야 한다.
`shutdown_csv_inputs`는 앞서 관찰한 종료 기대값과 고정 설정 기준을 같은 잠긴 원본 metadata에
적용한 뒤에만 명령을 노출한다. 실제 보존 attestation FAIL은 유지하고 합성 기준의 PASS와 구분한다.

### 5.14 종료 사본 CSV·이미지 검사와 자손 종료의 단일 흐름

CSV 입력 context와 동일 image fact를 사용해 전체 선택 이미지 subtree의 고정 목록을 대조하고
각 기본 스트림과 이미지 EXE를 읽기 공유로 잠근다. 이미지 도구의 실행 전후 inventory도
외부 고정 목록과 정확히 대조한다. 새 미선언 파일·누락·경로 교체·출력 불일치는 실패다.
선택 입력의 출처/승인과 서버 전체 snapshot 증명은 외부 실행기의 책임으로 유지한다.

두 고정 EXE는 새 gated worker를 Windows Job에 등록한 뒤 순차 실행한다. 원문 stdout/stderr,
실제 exit와 worker exit, Job 잔존/강제 종료 여부를 보존한다. 시간·출력 예산 초과나 자손 잔존은
FAIL이며 새 검사 자손만 정리한다. CSV·이미지 내용 검사와 두 입력 context 종료를 모두 통과한
뒤에만 선택한 종료 사본 검사 PASS를 기록한다. 실제 종료 기대값/최종 설정을 필수로 받는
상위 API와 데이터 소비 자체의 시험 API를 구분한다. 전체 현장/출시 gate는 계속 HOLD다.

보존 I4/I5 이미지133/199개와 CSV를 함께 실행하고, 누락/변조/고립 이미지·잘못된 manifest,
새 파일·잘못된 도구 출력·worker timeout/자손 잔존/감독자 손실을 검사한다. 기존 앱이나
운영 설정은 변경하지 않는다. 실제 현장 물리 attestation·보호된 launcher 통합은 별도로 남는다.

### 5.15 외부 고정 요청과 보호된 실행 진입점

관찰(900/7200초)과 종료 사본 QA를 명시한 request JSON을 외부 SHA로 고정해 읽는다.
기존 후보/도구 해시·UNSIGNED_INTERNAL 정책을 유지하며 요청 자체를 승인 근거로 해석하지 않는다.
원문 요청·단계 결과·최종 파일 목록/SHA를 새 결과 아래 보존한다. 오류/미완료를 PASS로 만들지 않는다.
frozen 실행은 multiprocessing.freeze_support를 적용하고 기존 Python API와 같은 조건으로 검증한다.

관리자 PS5.1 실행기는 새 결과 자식에만 보호 ACL을 만들고 운영자 읽기 권한을 보장한다.
고정 EXE·요청·동봉 파일을 잠근 뒤, EXE를 suspended 상태로 만들어 이름 없는 Job에 등록하고
나서 실행한다. PyInstaller bootstrap 자식도 포함하며 실제 앱은 Job에 넣지 않는다.
stdout/stderr를 새 파일로 저장하고 시간·출력·잔류 자손·실제 exit를 확인한다. 부모 손실 때도
검사 자손만 정리한다. 기존 부모 ACL·설치·설정·운영 데이터는 변경하지 않는다.
보호된 실행과 각 단계 결과를 실제 관찰→정상 앱 종료→전체 새 사본/QA로 연결하는 현장 절차는
별도 검증 대상이며 물리·UI/packet·승격 조건을 이 진입점의 PASS로 대신하지 않는다.

### 5.16 요청별 health 처리 구간의 선택적 계측

현장203.1356ms 표본은 기존500ms worker 로그에 남지 않으며 executor 대기와 event loop 복귀를
분리할 수 없다. `/health`의 기존 응답 본문·500ms 로그·200ms 실패 기준은 유지한다.
명시적인 로컬 진단 요청에만 `X-SFL-Health-Timing` 응답 헤더를 추가한다.

요청 조건은 `X-SFL-Health-Probe` 하나에 소문자32자리 hex ID, ASGI peer의 literal loopback IP,
Origin/Referer 헤더 부재다. 부적합한 진단 표시는 일반 health로 처리한다. 별도 인증 수단이나
외부 접근 통제를 대신하지 않는다. 전역 상태·파일 기록·장비 제어·추가 worker pool은 만들지 않는다.
요청마다 독립 객체를 쓰고 예외·취소 때 완료 헤더를 만들지 않는다.

예: 확인한 loopback `/health`에 `X-SFL-Health-Probe: 0123456789abcdef0123456789abcdef`를 보낸다.
수집기는 `fetch_sample(port, ENDPOINTS[0], health_probe_id=<새 uuid4 hex>)`로 지정하며,
응답 원문 헤더·본문·해시와 요청 ID를 보존한다. ID 미지정 시 기존 수집 동작을 유지한다.
수집기의 HTTP 성공은 timing 지원·정합성을 뜻하지 않는다. 해석 시 헤더가 정확히 하나인지,
v=1·probe_id 일치·clock·양의 정수 PID/TID·아래 모든 checkpoint의 단조 순서를 별도로 검증해야 한다.
누락되거나 다른 schema/ID인 자료를 시간0으로 채우거나 PASS로 해석하지 않는다.

| checkpoint 차이 | 포함하는 벽시계 구간 |
| --- | --- |
| worker_enter − submitted | executor 제출과 worker 시작 사이; 정확한 queue-only 시간은 아님 |
| plc_done − worker_enter | PLC health 조회 및 진입 계측 |
| runtime_done − plc_done | runtime 정보 조회와 경계 계측 |
| frontend_done − runtime_done | frontend 상태 조회와 경계 계측 |
| worker_exit − frontend_done | 기존 느린 응답 로그·payload 조합 등 나머지 worker 처리 |
| route_resume − worker_exit | worker 반환·future 전달·event loop 복귀 |

헤더는 v/probe_id/pid/loop_tid/worker_tid/clock/checkpoints로 구성하며,
checkpoint 순서는 route_enter, submitted, worker_enter, plc_done, runtime_done,
frontend_done, worker_exit, route_resume다. clock은 Python `perf_counter_ns`이고 단위는 ns다.
route_enter는 진단 요청 조건을 확인한 직후이므로 그 앞의 헤더 검사 시간도 포함하지 않는다.
고정 필드와 검증한 hex ID만 포함한다. 단계 사이 시간에는 OS scheduling·GIL/lock 대기·계측 비용이
포함될 수 있으므로 정확한 CPU 시간이나 특정 원인으로 자동 분류하지 않는다.
route_resume 뒤의 JSON 직렬화·middleware·socket 전송 및 route 진입 전 처리는 포함하지 않는다.
PID/TID만으로 세대를 확정하지 않으며 현장 적용 때 native 생성 식별자와 설치본 identity가 필요하다.
ETW QPC와 직접 같은 수치라고 가정하지 않고 같은 실행의 clock anchor와 trace coverage를 검증한다.

검증은 일반/잘못된/외부/브라우저 표시 요청, 동시 요청, 오류·취소, worker pool 포화,
각 처리 단계와 event loop 복귀 지연을 포함한다. 실제 loopback HTTP 시험은 장비 서비스 lifespan을
끄고 조회값을 격리해 수행한다. 이 변경은 새 제품 소스이며 기존4cc 설치본·고정 도우미를 수정하지 않는다.
실제 장비·frozen 설치본·현장 성능 검증과 배포는 별도이고 출시 HOLD는 유지한다.
