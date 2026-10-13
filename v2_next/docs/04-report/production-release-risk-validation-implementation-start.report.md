# 프로덕션 출시 리스크 검토·코드 개선 착수 보고

작성일: 2026-10-10. 상태: 초기 로컬 수정·소스 검증 확인 / R1~R6 정식 출시 HOLD.

## 1. 범위와 기준

사용자가 요청한 플랜 검토, 여섯 미결 항목의 역할/조치/검증/완료 기준,
실제 코드 수정과 수정안, 안전한 배포·관리 PDCA 로드맵을 정리했다.
여섯 항목의 현장 DoD가 충족됐다는 보고는 아니다.

- 브랜치: `codex/production-release-risk-validation-20261010`.
- 착수 시 HEAD·로컬 master·origin/master 추적 ref:
  `eb9af6f1398d588733f3f1884411e2612496d267`. 새 원격 최신성 확인/merge/push는 수행하지 않았다.
- 착수 전 변경은 사용자 요청으로 저장된 계획 문서와 PDCA 상태였다. 이를 보존했다.
- 이번 변경은 commit 전 작업 트리에 있다. HEAD SHA는 수정된 바이트의 build identity가 아니다.
- root/frontend 표시 버전은 `1.0.26`을 유지했다. `1.0.27`은 최종 후보 준비 시 재확인할 계획값이다.
- 현재 운영본·다음 rollback 기준 `541d701d…/08C061EE…`과 교체 전 이전본
  `4c97d4a…/D453C1D1…`은 갱신하지 않았다.

Electron → FastAPI → PLC/SPOT 수집 → CSV/observation/image fact →
manifest/정상 종료 증거의 연결을 유지했다. React/API·서명 NSIS workflow는 기존 경로를 따른다.
전체 책임·검증 매트릭스, 입출력/실패 조건은
[설계 문서](../02-design/features/production-release-risk-validation.design.md)에 있다.

## 2. R1~R6 판단과 다음 조치

| ID | 담당 역할 | 이번 확인·조치 | 남은 검증·완료 조건 | 판정 |
|---|---|---|---|---|
| R1 | Backend 엔지니어·QA | constructor의 전체 fact I/O가 상태 잠금을 점유하는 격리 재현. writer 잠금을 분리해 memory-only 종료 조회 회귀 통과 | 과거 요청/세대/원본 시간선·구간 계측·실제 규모/느린 디스크 인과 확인, 첫 요청 포함 timeout 재발0. `/api/spot/config`의 동기 fact scan은 남음 | 로컬 잠금 결함 수정 / 과거 원인 UNCONFIRMED |
| R2 | 성능 QA·Backend·Frontend | raw client timing/first/max/p50/p95/p99/오류/timeout/누락/경고 판정 추가. 첫 실패를 포함하는 localhost 검증 | 초기10회/현장3회·1/3탭·2초 health 비중첩·각≤200ms/timeout0·시작≤30초·전체 API/화면/자원 계약·15분/120분·누락0 | 관측 도구 보완 / 정식 성능 미측정 |
| R3 | 장비/운영 담당·설정 엔지니어·QA | 기존 attestation/fingerprint/drift/comparator/readback 경로와 실제 확인 필요성 설계 | 승인 프로파일의 필수 필드 대조·미만/동일/초과·운영자 확인·동일 build/fingerprint/runtime/정상 종료. 불일치/미확인0 | HOLD |
| R4 | 데이터 무결성 QA·운영·수집 엔지니어 | 기존 validator는 fact 파일 해시/행/안전한 경로를 검사하며 이미지 개별 바이트/전체 디코딩을 증명하지 못함을 확인 | 전체 과거/현재 자료의 고정 목록/일관된 사본, 스키마별 CSV 규칙·이미지 해시/전체 디코딩/역참조·종료 delta. 검사/분류100%·미분류0·과거 처리 결정 | HOLD |
| R5 | SPOT 엔지니어·데이터 책임자·QA | `4c97d4a…`에도 크기 초과/QueueFull 경로가 존재. 현재 원인별 drop 계수 추가, 정책 off/간격 제외·worker 실패·종료 보존 구분 | 과거15건의 개별 또는 시간구간 정산·원인/영향/복구/처리 결정, 디스크 부족/권한/느린 저장 등 격리 재현·예방 회귀, 새 정상 운전 drop/실패0 | 관측 개선 / 과거 원인 UNCONFIRMED |
| R6 | 릴리즈·보안·QA·운영 | existing workflow의 exact default-branch SHA/tag·Node22.22.2/Python3.12.6·hash lock·서명/출처 계약 확인. local QA 실행 | 최종 서명 installer/Electron Valid·기대 signer/timestamp·payload/provenance/SHA 대조, 동일 설치본 신규/upgrade/restart/rollback/현장 QA·FINAL PASS/validator0/동일 세대 종료 | HOLD |

실명 담당자·검토자·승인 장비 프로파일·유지보수 시간은 미지정이다.
원본 첫 health `223.4887ms`, 과거 drop15, 최초 timeout `UNCONFIRMED` 기록을 유지했다.
이번 mock 수치나 현재 counter로 과거 사건을 소급 분류하지 않는다.

## 3. 기준 브랜치 대비 실제 수정안

### 3.1 writer I/O와 상태 잠금 분리 — 적용

`backend/FacilityData/drivers/spot_api.py`:

```diff
 _spot_image_capture_lock = threading.Lock()
+_spot_image_capture_writer_lock = threading.Lock()

 def _get_spot_image_capture_writer() -> SpotImageCaptureWriter:
-    with _spot_image_capture_lock:
+    with _spot_image_capture_writer_lock:
         # Existing constructor, config signature and writer reuse remain here.
```

test reset도 writer 참조는 writer lock, counter는 state lock으로 분리한다.
두 잠금을 중첩하지 않는다. 행 수/해시 검사·dedupe·manifest fail-closed는 유지한다.
초기 API latency를 완전히 해결했다고 주장하지 않는다.

### 3.2 drop 원인 계수 — 적용

같은 파일의 기존 실제 분기에만 다음 계수를 추가했다.

```python
if len(image_bytes) > max_bytes:
    with _spot_image_capture_lock:
        _spot_image_capture_dropped_count += 1
        _spot_image_capture_dropped_oversize_count += 1
    return

try:
    _SPOT_IMAGE_CAPTURE_QUEUE.put_nowait(event)
except queue.Full:
    _spot_image_capture_dropped_count += 1
    _spot_image_capture_dropped_queue_full_count += 1
    return
```

health와 종료 snapshot의 `dropped_oversize_count`/`dropped_queue_full_count`,
sanitized 수집 결과에 이를 노출한다. 기존 총 drop·worker failure·정책·보존 기간·CSV 스키마는 유지한다.

### 3.3 client 응답 시간 — 적용

`scripts/collect_operational_observability.ps1`의 성공 경로 핵심:

```powershell
$requestTimer = [System.Diagnostics.Stopwatch]::StartNew()
$response = Invoke-WebRequest -Uri $Uri -Method Get -TimeoutSec $Timeout -UseBasicParsing
$body = [string]$response.Content
$requestTimer.Stop()
# Existing envelope receives this field (other existing fields omitted here):
return [ordered]@{
  client_elapsed_ms = $requestTimer.Elapsed.TotalMilliseconds
}
```

실제 함수는 시작 UTC, 오류 본문 읽기 이후 시간, timeout 여부도 반환한다.
raw envelope/raw index에 원시 값을 남기며 반올림으로 200ms 초과를 숨기지 않는다.
요약은 다음 계약이다.

```text
scope: observed_client_health_requests_only
full_performance_gate: NOT_EVALUATED
FAIL: HTTP 오류 또는 timeout 또는 어느 표본이든 >200ms
NOT_MEASURED: 계획 표본 누락/중복, null/음수/NaN/무한대/비숫자 timing
PASS: 수집된 health 표본 범위만 정상·유효·모두 ≤200ms
```

첫 요청·오류 요청을 포함하며 50ms 초과 경고를 별도 기록한다.
JSON parsing/연결/TTFB 구간 분리와 전용 2초 sampler는 후속 작업이다.
`scripts/run_qa_selftests.cjs`에 수집기 selftest를 등록했다.

### 3.4 R3/R4/R6 후속 코드·도구 방향

- R3: 기존 attestation/one-command QA를 재사용하되 도구의 증명 필드 밖에 있는
  승인 모델·모드·범위·방사율·통신 조건은 승인 프로파일/실장비 확인 증거로 대조한다.
  알 수 없는 값을 기본값으로 채우거나 fingerprint를 실장비 확인으로 대신하지 않는다.
- R4: 기존 CSV validator에 대한 별도 전수 검사 도우미를 설계한다. 고정 inventory의
  파일 SHA256/size·스키마·row/sequence/TTL/최종 sequence를 유지하고, 이미지마다
  streaming SHA256 → Pillow 구조 확인 → 재열기/전체 `load()` → fact 크기/해시/치수
  대조 → 파일→fact 역참조를 수행한다. 검사 전후 목록/해시 변경은 불완전으로 처리한다.
  경로 경계/reparse·전체 입력 delta·retention 증거를 함께 검사하며 기존 과거 스키마 규칙을 보존한다.
- R6: 서명 workflow를 대체하지 않는다. 필요한 소스/lock 수정 검토 후 clean 최종 commit,
  root/frontend/backend 버전, 원격 tag 충돌을 재확인한 뒤 동일 설치본에 모든 결과를 결합한다.

## 4. 검증과 한계

원시 증거 폴더:
`C:/Users/user/Desktop/SmartFactory/RISK_20261010_f70608b7`.

| 실제 실행 | 결과 | 증명 범위 |
|---|---|---|
| R1 focused unittest 수정 전/후 | exit1 → exit0 | 느린 fact 초기화 중 종료 snapshot이 상태 잠금에 막히는 격리 결함 |
| R5 크기 초과 unittest 수정 전/후 | exit1 → exit0 | 새 원인별 계수 누락→관측 가능 |
| writer 동시 생성/실패 재시도/큐·크기·정상 종료 4회귀 | 4 tests, exit0 | 단일 writer·크기 동일 허용·큐/drop 정산·정책 제외·종료 counter 보존 |
| 수집기 timing/summary selftest 수정 전/후 | 각각 exit1 → exit0 | 첫 지연/200ms 경계/HTTP 오류/timeout/누락/비정상 timing/비밀정보 제외 |
| 실제 collector localhost smoke 3시나리오 | exit0, 검사 PASS | 250ms 첫 지연·timeout·HTTP500을 모두 관측 FAIL로 보존. raw timing·12개 raw hash/회차·sanitized drop 연결 |
| 최초 `npm run health` | exit1, dependency tests 2/14 PASS | 설치된 npm 의존성이 lock보다 이전 버전. 실패 원본 보존 |
| `npm ci`, `npm --prefix frontend ci` | 각각 exit0 | 기존 lock대로 복원·frontend postinstall 호환 검사 통과. lock 수정 없음 |
| 복원 후 `npm run health` | exit0 | dependency14·Electron94·frontend Node9/Vitest434 통과, frontend type/lint·backend ruff/mypy(9 files) 통과, backend901(900 통과/1 skip), QA6 selftest 통과 |
| `npm --prefix frontend run build` | exit0, 25.04초 | 4577 modules, production React/Router graph 계약 통과, startup splash 복사. Zod PURE 주석 경고 2건 |
| skip 확인 focused `unittest -v` | exit0, 1 skip | private F01 fixture 미지정으로 해당 사례가 실행되지 않았음을 확인 |
| Markdown fence/local link 검사·`git diff --check` | exit0 | 새/갱신 문서 구조와 로컬 링크·diff 공백 확인 |
| `npm audit --json` / frontend audit | 각각 exit1 | root high1/moderate8, frontend high6/moderate2 패키지 항목. 아래 한계 참조 |

localhost smoke 최초 시도는 PS7에서 상속된 PSModulePath 때문에 Windows PS5의
`Get-FileHash`를 찾지 못해 실패했다. 원본을 보존하고 기존 CI runner와 같이 child env에서
PSModulePath를 제거한 새 실행으로 3시나리오를 검증했다. 제품/현장 PASS로 바꾸지 않았다.

backend skip 사례는
`FactPollingTests.test_f01_raw_inputs_poll_publish_csv_continue_during_fact_initialization`이며,
`TEMPERATURE_GOAL_PACKAGE`의 private F01 fixture가 지정되지 않았기 때문이다.
이를 실행한 것으로 표시하지 않는다. full log의 negative CSV validator 결과·격리 오류
로그와 runner 실패를 구분했고, 최종 unittest의 failure/error는 0이다.
Starlette/httpx deprecation warning과 build의 Zod PURE annotation 경고는 남아 있다.

감사에서는 root의 electron-builder → @electron/get → got/cacheable-request →
`http-cache-semantics@4.2.0` 경로와 `sprintf-js` 계열, frontend의 Tailwind/glob/braces·
source-map-js 계열 항목이 보고됐다. tree별 패키지 항목 수는 독립 advisory 수가 아니며,
출시 payload/runtime의 실제 영향은 아직 판정하지 않았다. 강제 audit fix/메이저 upgrade는 실행하지 않았다.
성공한 health가 있더라도 감사 미해결을 숨기지 않는다. 보안 담당의 영향 판단/보완 검증을 R6 후보 검토에 연결한다.

서버 원본 전수 확보·실장비 attestation·최종 서명 빌드·installer 실물/설치/복구·
현장 15/120분·같은 세대 종료 검증은 수행하지 않았다. 로컬 시험으로 이 gate를 PASS 처리하지 않는다.

## 5. 안전한 배포·관리 PDCA 로드맵

1. **Plan:** 여섯 역할의 실명 담당자/검토자, 승인 장비 프로파일, 전체 과거/현재 데이터 목록,
   유지보수 시간을 확정한다. 원본 timeout/drop15의 시간선과 운영/복귀 설치본 해시를 보존한다.
   새 npm 감사 항목의 실제 payload 영향·보완 범위를 검토해 기존 계획의 R6에 증거를 연결한다.
2. **Do:** 이번 로컬 회귀를 유지하면서 실제 규모 fact 초기화·동시 health를 계측하고 확인된
   원인만 수정한다. 전체 일관된 사본의 CSV/이미지 전수 도우미, 승인 프로파일 대조,
   디스크/권한/큐 장애의 격리 재현을 완료한다. 원인 부족은 HOLD로 남긴다.
3. **Check:** clean 최종 source·버전/tag를 확인하고 protected default branch의 정확한 SHA로
   서명 설치본을 만든다. 같은 installer의 payload/signature/provenance/SHA·신규 설치/upgrade/
   restart/이전본 복구를 검증한다. 현장은 백업·정상 종료·승인 적용·attestation/QA 후
   초기15분·canary120분, 전체 API/화면/자원 계약과 CSV/이미지+종료 delta·동일 세대 종료를 검사한다.
   health 2초 비중첩·첫 요청 포함 각≤200ms/timeout0·필수 NOT_MEASURED0 등 여섯 DoD를 확인한다.
4. **Act:** 실패 원인을 보완하고 영향받은 검사만 재실행한다. QA/릴리즈 책임자의 결정을
   기록하고 운영 승격·실제 적용 확인이 끝난 새 build/installer를 다음 rollback 기준으로 갱신한다.
   이전본·실패 자료를 보존하며 운영 중 성능/큐/drop/저장 실패/drift/종료 증거를 계속 점검한다.
   유지보수·복구는 실제 상태와 승인 범위/설정·데이터 호환성을 확인해 수행한다.

서버 전달은 실제 Desktop/SmartFactory의 실행별 새 폴더와
`Z:/SmartFactory/YYYYMMDD/send|return|records`를 사용하고, Codex가 Chrome 원격 데스크톱을
통한 서버 최종 폴더 복사·절대경로/파일 확인까지 맡는다. 공유 업로드만으로 전달 완료라고 하지 않는다.
현재 동일 미서명 운영본에 새 후보용 120분 시험·재빌드·재승인을 자동 추가하지 않는다.

운영 증거 양식은 [설계 문서 §5](../02-design/features/production-release-risk-validation.design.md#5-후속-pdca와-증거-양식)를 사용한다.
이번 로컬 Act 교훈은 상태 조회의 메모리-only 주석을 실제 잠금 경계로 검증하고,
lock/installed mismatch를 먼저 확인하며, 수집 exit0와 성능 PASS를 분리하는 것이다.
