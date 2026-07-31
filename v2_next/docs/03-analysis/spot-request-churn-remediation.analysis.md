# Gap Analysis: spot-request-churn-remediation

> **Historical snapshot — superseded.** This document records the failed
> pre-quarantine candidate and its rollback decision. The final production
> operating baseline is the
> `575e869b63d3052156624886fe0358fb39d6c98a`
> `FIELD_CANARY_PASS / PHYSICAL_PATH_PARTIAL` package. A later adversarial
> failure-path delta is `FIELD_REVALIDATION_REQUIRED` as recorded in
> `docs/04-report/spot-tcp-source-port-quarantine-v2.report.md`.
>
> Date: 2026-07-27 | Design: `docs/02-design/features/spot-request-churn-remediation.design.md`
> Failed package baseline: `45263ff46ce184ef0cb63f1cec7658f929167b2e` | Act iteration: 3 | Analysis iteration: 4
> Verdict: **Field Act local Check passed / actual-server recheck required / rollback remains active**

---

## Match Rate: 100% (design-code/local)

## Field Promotion Gate: RECHECK REQUIRED

## Summary

설계의 로컬 검증 항목 50개 전부가 구현 및 검증 증거와 일치한다.

Frontend는 SPOT image 정상 표시가 끝난 뒤 설정된 1~10초 cadence로 다음 요청을
예약한다. 정상 timer, 기존 500/1000/2000ms retry, manual refresh, visibility 복귀 및
unmount lifecycle은 중복 실행되지 않는다.

Backend는 기존 `httpx.AsyncClient`, payload validation, timeout 및
`_spot_device_request_lock`을 유지하면서 process-local JPEG cache와 shared refresh
task를 사용한다. Act에서 mypy narrowing을 명시하고, 실제 shared task를 기다리지 않은
second cache check caller를 waiter 집계에서 제외했다. 또한 refresh 실패 뒤 다음
shared refresh의 복구와 완료 task 정리 중 replacement task 보존을 자동 테스트로
고정했다.

실제 HTTP/1.0 + Content-Length + server close loopback에서 cold caller 20개와 만료 후
caller 20개는 각각 upstream 요청 1개로 병합됐고, fresh caller 100개는 추가 upstream
요청 없이 cache에서 처리됐다. 전체 로컬 quality gate와 회귀 테스트가 통과했으므로
clean package 생성과 실제 서버 Check까지 진행했다.

그러나 실제 운영 `refresh_interval=1.0s`를 변경하지 않은 15분 smoke에서 image
upstream, 전체 SPOT 신규 연결률, baseline 대비 감소율 및 60초 미만 동일 4-tuple
재사용 gate를 충족하지 못했다. 로컬 구현 일치율과 별개로 field promotion은
실패이며, 120분 canary를 진행하지 않고 검증된 rollback 설치본으로 복귀해야 한다.

## Actual-server 15-minute smoke

### Evidence identity

- Run: `runtime_validation_20260725_003551`
- Observation: `2026-07-25 00:37:05~00:52:07 +09:00`, `902.502s`
- Candidate backend SHA-256:
  `9A9F1A50028BA126ADAF6B9CC232DABA7875111D7C6584B0B38ED63183E316BB`
- Candidate policy: `spot-image-demand-shaping-v1`
- Official sanitized ZIP SHA-256:
  `4875C983A288F60D7E8805D63D023AFAA0727D883956730F615E001795756C9B`
- Supplied raw-private ZIP SHA-256:
  `ECC7BC20D2F34C78EA5519FDDB161B1315AA6F44E53DFE063B3CA632B4697EA4`
- Independent manifest verification:
  outer raw `626/626`, app raw `590/590`, missing `0`, mismatch `0`
- Collector result: `PARTIAL`, exit code `2`, reason
  `switch-evidence-unavailable`

`PARTIAL`은 관리형 스위치 시작/종료 counter 부재만 의미한다. 제품·TCP promotion
gate 계산에 필요한 packet, app, ping 및 server NIC 자료는 완전하게 보존됐다.

### Gate calculation

60초 p95는 관측 시작 시각에 정렬한 15개 fixed window와 1초 간격 rolling window
843개를 모두 계산했다. 두 방식의 p95 결과는 동일했다.

| Gate | Required | Observed | Verdict |
|---|---:|---:|---|
| image upstream 60초 p95 | `<=0.5/s` | `0.9667/s` | **FAIL** |
| 전체 SPOT 신규 TCP 60초 p95 | `<=6/s` | `10.9667/s` | **FAIL** |
| baseline `37.674/s` 대비 감소 | `>=80%` | `70.92%` | **FAIL** |
| 동일 4-tuple 5초 미만 재사용 | `0` | `0` | PASS |
| 동일 4-tuple 60초 미만 재사용 | `0` | `723` | **FAIL** |
| SPOT SYN 무응답/재전송/RST/handshake 실패 | `0` | `0` | PASS |
| SPOT 5xx/ConnectTimeout/upstream failure | `0` | `0` | PASS |
| temperature/diagnostic/control HTTP 회귀 | `0` | `0` | PASS |
| ping loss | `0` | `0/1,104` | PASS |
| server NIC error/discard 증가 | `0` | `0` | PASS |

관측 구간의 SPOT 신규 연결 9,888건은 image 868건(`0.9618/s`),
temperature 902건(`0.9994/s`), control 902건(`0.9994/s`),
diagnostic 7,216건(`7.9956/s`)이었다. 전체 평균은 `10.9562/s`다.

애플리케이션 counter의 894.688초 delta는 downstream `905`, upstream `860`,
cache hit `31`, coalesced waiter `14`, refresh success `860`, refresh failure `0`,
failure `0`이었다. 실제 upstream 억제율은 `4.97%`에 그쳤다. 180개 진단 sample
모두 policy가 일치하고 image status는 `ok`였으며 요청 수락 중이었다.

전체 보존 capture에서는 SPOT 연결 시도 12,309건 모두 SYN-ACK과 handshake가
완료됐고 HTTP status 200, HTTP/1.0, Content-Length, body complete, server FIN으로
종료됐다. SPOT 전용 연결 실패, handshake 후 무응답, response 전 reset,
SYN retransmission은 모두 0이다.

오류 큐는 시작과 종료 모두 기존 `plc_driver diagnostics_age_ms=''` 1항목,
repeat 43으로 동일했다. 신규 `spot_image` 오류는 없다. RSS는 869.695초 동안
684,343,296 bytes에서 716,824,576 bytes로 증가했지만 memory leak suspect는
0건이고 CSV queue/drop 상태도 정상 범위였다.

별도 관측으로 SPOT config attestation의 `config_drift_detected=true`가 180/180
sample에서 유지됐다. 운영 `config.ini` SHA-256은 설치 전후 동일하므로 이번
후보 설치로 생긴 설정 파일 변경 근거는 없으며, 이 attestation mismatch는 별도
운영 이슈로 추적한다.

### Field decision

통신 실패가 재발하지 않은 점만으로 promotion할 수 없다. 네 개 hard gate가
초과됐으므로 이 package는 field Check 실패로 기록한다. 관리형 스위치 자료 부재는
물리 원인 세분화만 제한하며 위 제품 gate 실패를 무효화하지 않는다.

### Rollback closure

- Rollback verification: `2026-07-27 08:25:07 +09:00`
- Candidate 정상 종료: 제품 process `5 -> 0`, 약 `2분 36초`, 강제 종료 없음
- Rollback installer exit code: `0`
- Installed rollback backend SHA-256:
  `F1A65AC7E2C27FC049398EA0AF2A6DAA775A081DE0311E42A3EAA87CE4A15A54`
- Operating config SHA-256:
  `3E839DE1523906344BEA1087BE74F89E7C8DBC1A2F6258A32C3953E304B48704`
  (설치 전과 동일)
- Runtime: backend process `1`, Electron process `4`, health HTTP `200`,
  image status `ok`
- Current HTTP window: error `0`, 5xx `0`, p95 `52.637ms`
- Current operational UI: EX·LS recovered, SPOT normal, CSV queue/drop 정상,
  memory leak suspect/warning/error `0`
- Evidence:
  `server_check_after_rollback_20260727_082507.json` (private server evidence)

오류 큐 `7`항목과 repeat `187`, 누적 HTTP 5xx `1`은 지우지 않은 v1.0.16의
운영 이력이다. 마지막 source는 `spot_image`이며 현재 60초 HTTP window에는
error와 5xx가 없고 SPOT image status도 `ok`다. 따라서 이 누적 이력은 rollback
실패로 판정하지 않지만, v1.0.16의 기존 간헐적 SPOT 오류가 해소됐다는 의미도
아니다. 오류 큐는 증거 보존을 위해 clear하지 않는다.

검증된 rollback identity와 운영 설정 복원은 완료됐다. 실패한 candidate는 더 이상
배포 상태가 아니며, 새 Act와 그 후속 15분 smoke가 승인·통과하기 전까지 package와
120분 canary를 차단한다.

## Field Act iteration 3

실패 원인은 image 단독이 아니라 diagnostic 8-field fan-out을 포함한 전체 SPOT
background request budget이었다. 이번 Act는 제품의 공식 HTTP 경로와
`_spot_device_request_lock`을 유지하면서 다음 최소 변경만 적용했다.

- backend image upstream 최소 간격을 `3.0s`로 고정했다.
- diagnostic 8-field sweep를 startup에서 즉시 한 번 실행한 뒤 최소 `10.0s`
  간격으로 제한했다.
- 실행 중인 diagnostic sweep와 10초 이내 poll은 새 task를 만들지 않고 기존
  snapshot을 사용한다.
- diagnostic 정상 decimation을 stale로 오인하지 않도록 max age를 최소 `20.0s`로
  맞췄다.
- image, temperature, internal temperature, diagnostics의 계산 상한과 합계,
  정책 버전, sweep 실행·억제·upstream 누계를 `/api/spot/config` diagnostics에
  additive field로 노출했다.

운영 `refresh_interval=1.0s`에서 계산된 background 상한은 image `0.333/s`,
temperature `1.0/s`, internal temperature `1.0/s`, diagnostics `0.8/s`, 합계
`3.133/s`다. 내부 poll 하한 `0.5s`에서도 합계 `5.133/s`로 field gate
`6/s` 아래다. 이 값은 로컬 정책 상한이며 실제 신규 TCP 연결률을 증명하지 않으므로
clean package와 실제 서버 15분 smoke를 별도 Check로 수행해야 한다.

DB, CSV, config 및 image fact schema는 변경하지 않았다. source port, IP, URL,
payload 또는 absolute path를 새 diagnostics field에 노출하지 않는다. 현재 서버는
계속 검증된 rollback v1.0.16이며 이 Act source는 배포되지 않았다.

## Match Calculation

| 영역 | 전체 | 일치 | 판정 |
|---|---:|---:|---|
| Frontend policy 및 lifecycle | 18 | 18 | 일치 |
| Backend cache 및 concurrency | 20 | 20 | 일치 |
| API, observability 및 security | 8 | 8 | 일치 |
| Local quality 및 protocol gate | 4 | 4 | 일치 |
| Field Act background budget | 10 | 10 | 일치 |
| **합계** | **60** | **60** | **100%** |

## Implemented Items

- [x] 최초 image 요청은 즉시 수행하고 정상 표시 완료 뒤에만 다음 timer를 예약한다.
- [x] `refresh_interval`의 invalid 값은 3초, finite 값은 1~10초로 정규화한다.
- [x] 정상 timer, 자동 retry 및 manual refresh가 동시에 실행되지 않는다.
- [x] hidden 화면과 unmount에서 정상 timer를 해제하고 visible 복귀 시 한 번 재개한다.
- [x] Blob URL, 마지막 정상 frame, payload validation 및 기존 오류 계약을 유지한다.
- [x] cache entry는 JPEG 한 장과 epoch, monotonic, upstream latency만 process memory에 보유한다.
- [x] monotonic strict TTL 경계와 clock anomaly safe miss를 구현했다.
- [x] cold/expired concurrent caller는 하나의 shielded shared refresh task를 사용한다.
- [x] caller cancellation이 shared refresh를 취소하지 않으며 shutdown은 bounded하다.
- [x] refresh 실패 시 expired cache를 HTTP 200 stale fallback으로 사용하지 않는다.
- [x] refresh 실패 뒤 다음 shared refresh가 성공하고 cache를 교체한다.
- [x] 완료 task 정리 중 새 replacement task reference를 지우지 않는다.
- [x] lock 내부 second cache check hit는 cache hit로만 집계하고 waiter로 집계하지 않는다.
- [x] upstream 성공 한 번당 image capture enqueue도 한 번만 수행한다.
- [x] `X-Spot-Image-Age-Ms`와 source/captured-at/upstream-latency 계약을 제공한다.
- [x] downstream/upstream/cache/leader/waiter/success/failure/cache-age 누계를 제공한다.
- [x] query parameter를 통한 TTL, upstream URL, force refresh 및 source port 주입을 추가하지 않았다.
- [x] raw socket, source-port allocator, custom HTTP parser 및 Windows network 변경을 추가하지 않았다.
- [x] DB, CSV, config 및 image fact schema migration이 없다.
- [x] HTTP/1.0 + Content-Length + server close loopback에서 freshness window당 upstream 1회를 확인했다.
- [x] Ruff, mypy, Electron, Frontend, Backend 및 QA self-test 전체 gate가 통과했다.
- [x] image upstream 보호 간격을 strict `3.0s` 경계로 고정했다.
- [x] diagnostic sweep를 startup 즉시 실행한 뒤 strict `10.0s` 시작 간격으로 제한했다.
- [x] 느린 diagnostic sweep 실행 중에는 새 sweep가 겹치지 않는다.
- [x] diagnostic max age를 effective sweep 간격의 2배 이상으로 맞췄다.
- [x] 가장 빠른 `0.5s` poll에서도 계산된 background 상한이 `5.133333/s`다.
- [x] 요청 budget 및 diagnostic sweep 누계를 additive diagnostics로 제공한다.
- [x] Act 변경에 schema, 설정 migration, raw socket 또는 네트워크 설정 변경이 없다.

## Resolved Blocking Items

- [x] **BLOCK-01 — mypy:** fresh cache 분기에서 `cache_entry is not None`을 명시하여
      `_SpotImageCacheEntry`로 narrowing했다.
- [x] **BLOCK-02 — recovery test:** 실패한 refresh 뒤 다음 shared refresh가 성공하고
      cache와 failure 상태를 복구하는 테스트를 추가했다.
- [x] **BLOCK-03 — task race test:** 완료 refresh cleanup이 새 replacement task를
      제거하지 않는 테스트를 추가했다.
- [x] **BLOCK-04 — waiter counter:** second cache check hit에서 waiter 증가를 제거하고
      cache hit만 증가하는 테스트를 추가했다.

## Changed Items (Deviations from Design)

- [x] exact HTTP/1.0 close 조건은 repository unit test가 아니라 Check 시점의 body-free
      loopback으로 검증했다. cache/single-flight 동시성 동작은 repository 자동 테스트로
      고정되어 있다.
- [x] Act worktree의 `backend/.venv`에 repository 고정
      `requirements-dev.txt`를 설치하고 해당 interpreter로 Ruff, mypy 및 backend
      tests를 실행했다. 제품 dependency 및 repository 파일은 이 준비 과정에서
      변경되지 않았다.

## Validation Evidence

- Implementation commit: `4e3719e feat(spot): shape image request demand`
- Act source changes: `spot_api.py` narrowing 및 waiter 의미 수정
- Act tests: recovery, second-cache-check counter, replacement-task race 3건 추가
- Electron startup/lifecycle: 38 tests PASS
- Frontend: typecheck PASS, ESLint PASS, 33 files / 250 tests PASS
- Frontend production build: PASS, 4,532 modules
- Backend Ruff: PASS
- Backend mypy: PASS, 6 source files
- Focused SPOT API tests: 83 tests PASS
- Backend unittest discovery: 504 tests PASS
- NSIS operational-ready self-test: PASS
- HTTP/1.0 close loopback:
  - cold callers 20 → upstream 1
  - fresh callers 100 → additional upstream 0
  - expiry callers 20 → additional upstream 1
  - fresh batch 100 calls total 0.686ms, 0.006862ms/call
  - leaders 2, true coalesced waiters 38, cache hits 100, refresh failures 0
- Clean PyInstaller/NSIS package:
  - commit `45263ff46ce184ef0cb63f1cec7658f929167b2e`
  - installer SHA-256
    `25E2DE9036E43EA309B4380691E5545663623CB3494D276D3EFBF6BFD734DCCD`
  - packaged backend SHA-256
    `9A9F1A50028BA126ADAF6B9CC232DABA7875111D7C6584B0B38ED63183E316BB`
- Actual server 15-minute smoke: **FAIL**
- Actual server 120-minute canary: prohibited because the 15-minute gate failed

### Field Act iteration 3 local validation

- PDCA design-code analysis iteration 4: `100%`
- Focused SPOT API: 86 tests PASS
- Backend unittest discovery: 507 tests PASS
- Backend Ruff 0.15.15: PASS
- Backend mypy 1.20.2: PASS, 6 source files
- Electron startup/lifecycle: 38 tests PASS
- Frontend: typecheck PASS, ESLint PASS, 33 files / 250 tests PASS
- NSIS operational-ready self-test: PASS
- `git diff --check`: PASS
- package/installer build: not run; 별도 Check 승인 전
- actual-server 15-minute smoke: not run; 새 package와 별도 Check 승인 필요

### Field Act iteration 3 package와 실제 서버 Check

별도 Check 승인 후 Act iteration 3을 clean package로 만들고 실제 서버에서
15분 passive smoke를 수행했다.

| Identity | Value |
|---|---|
| source commit | `a03bf2c4ef47e31fd18ec1520e37287e0837f3e3` |
| installer SHA-256 | `38C771E7F5E997961B7AC765F01901B4ED12D5EE52888C3C75A4EC9C9457E05D` |
| packaged backend SHA-256 | `4F577276D83E80E4AC8512E86929BB3D905013DC30F1CCA8CD93B82259B7F0C4` |
| backend bundle SHA-256 | `822F90FEA685CB420992431A2929677E9C1FDE86405C8D3E75C8CFCD36C5616F` |
| sanitized evidence SHA-256 | `9F57E062D581105C683EE0C4BE37EFAA47DEDA375DD9659361DC36B5112C6CE8` |

15분 packet/app 증거의 hard gate 결과:

| Gate | Required | Observed | Verdict |
|---|---:|---:|---|
| image upstream 60초 p95 | `<=0.5/s` | `0.3333/s` | PASS |
| 전체 SPOT 신규 TCP 60초 p95 | `<=6/s` | `3.1333/s` | PASS |
| baseline `37.674/s` 대비 감소 | `>=80%` | `91.82%` | PASS |
| 동일 4-tuple 5초 미만 재사용 | `0` | `0` | PASS |
| 동일 4-tuple 60초 미만 재사용 | `0` | `33`, 최소 `51.052s` | **FAIL** |
| SPOT handshake/HTTP/body | 전부 성공 | `2,788/2,788` | PASS |
| ConnectTimeout/SPOT 5xx/RST | `0` | `0` | PASS |
| ping/NIC error-discard | `0` | `0` | PASS |

요청 예산과 diagnostic decimation은 의도대로 동작했고 통신 실패도 재현되지
않았다. 그러나 Windows source-port allocator는 `3.1333/s`에서도 같은 4-tuple을
60초 안에 다시 선택했다. 따라서 요청률 제한만으로 빠른 재사용 0건을 보장한다는
설계 가정은 반증됐고 field promotion은 실패했다.

관리형 스위치 counter가 없어 수집 상태는 `PARTIAL`이지만, 위 제품 hard gate의
packet과 app 자료는 보존돼 있다. switch 자료 부재는 33건의 재사용 실패를
무효화하지 않는다.

### 최종 rollback closure

후보는 정상 종료 후 검증된 v1.0.16으로 rollback됐다.

- rollback backend SHA-256:
  `F1A65AC7E2C27FC049398EA0AF2A6DAA775A081DE0311E42A3EAA87CE4A15A54`
- config SHA-256:
  `3E839DE1523906344BEA1087BE74F89E7C8DBC1A2F6258A32C3953E304B48704`
- backend process `1`, Electron process `4`, health `200`, image status `ok`
- evidence:
  `server_check_after_approved_rollback_retry_20260727_102549.json`

오류 큐는 clear하지 않았고 120분 canary는 실행하지 않았다. 실제 서버는 계속
rollback v1.0.16을 운영한다.

### 후속 Act 설계

요청률 추가 감소로는 재사용 0건을 보장할 수 없으므로 후속 기능을 별도 PDCA로
분리했다.

- Plan:
  `docs/01-plan/features/spot-tcp-source-port-quarantine-v2.plan.md`
- Design:
  `docs/02-design/features/spot-tcp-source-port-quarantine-v2.design.md`
- 핵심:
  - 75초 source-port quarantine
  - OS가 동적으로 할당한 exclusive guard port 768개
  - Python 표준 `http.client` parser와 `source_address`
  - single-worker I/O 격리
  - pool 실패 시 OS 자동 port fallback 금지
  - 폐기된 raw-socket parser와 allocator code 재사용 금지

이번 승인 범위는 Plan과 Design까지이며 제품 source는 아직 변경하지 않는다.

## Remaining Operational Risk

- 로컬 loopback은 실제 SPOT 장비의 응답 지연, 관리형 스위치 오류 및 Windows 현장 부하를
  재현하지 않는다.
- 새 cache는 process-local이므로 backend process가 여러 개 실행되면 process별로
  upstream refresh가 발생한다. 실제 설치 전 backend 단일 process를 확인해야 한다.
- rollback은 검증된 v1.0.16 설치본과 SHA-256을 유지하는 방식이다.
- schema 및 migration 변경은 없으므로 데이터 migration 위험은 없다.
- 현장 실패 모드는 이미지 갱신 지연 또는 502로 나타나며, 기존 성공 frame과 오류
  관측성 계약은 유지된다.
- 실패 package는 운영 `refresh_interval=1.0s`에서 image upstream 억제율이
  `4.97%`에 그쳤고 diagnostic이 `7.9956/s`였다. 이번 Act의 계산 상한은 두 원인을
  함께 제한하지만 실제 장비의 신규 TCP 연결률은 아직 현장 검증되지 않았다.
- diagnostic sweep 주기가 1초에서 10초로 느려지므로 diagnostic 표시는 최대 약
  20초 age를 정상으로 허용한다. 온도 poll과 operator control cadence는 유지된다.
- 관리형 스위치 자료가 없어 SPOT 장비와 switch 사이의 물리 상태는 배제하지 못했다.
  다만 이번 15분 구간에는 SPOT 전용 TCP/HTTP 실패가 없었다.
- request-budget iteration 3은 연결률과 모든 HTTP 안정성 gate를 통과했지만
  60초 미만 동일 4-tuple 재사용 33건으로 promotion할 수 없다.
- source-port quarantine v2는 표준 parser를 사용하더라도 Windows guard socket,
  worker cancellation과 pool exhaustion이라는 새 운영 실패 모드를 도입한다.
  따라서 local loopback만으로 promotion할 수 없고 실제 Windows 15분 packet
  Check가 필수다.

## Recommendations

1. 검증된 rollback v1.0.16을 현재 운영 상태로 유지하고 오류 큐를 clear하지 않는다.
2. 실패한 기존 candidate를 재설치하거나 120분 canary를 수행하지 않는다.
3. 별도 Do 승인 전까지 `spot-tcp-source-port-quarantine-v2` 제품 코드를
   수정하지 않는다.
4. Do 승인 후 표준 `http.client`와 guard-port lease를 최소 범위로 구현하고
   cancellation, exhaustion, HTTP/1.0 close 회귀를 로컬에서 먼저 검증한다.
5. local Check 통과 뒤 별도 package/actual-server Check 승인을 받아 15분 smoke의
   모든 기존 gate와 60초 미만 동일 4-tuple 재사용 0건을 다시 확인한다.

## Next Steps

- [x] Design-code gap analysis
- [x] Blocking gap 수정
- [x] 전체 local Check 재실행
- [x] Match rate 100% 및 package gate 해제
- [x] Clean Act commit 생성
- [x] clean package 생성 및 identity 검증
- [x] 실제 서버 설치 및 15분 smoke 수행
- [x] 15분 smoke 실패 증거 보존
- [x] 검증된 v1.0.16 rollback
- [x] rollback identity와 운영 상태 확인
- [x] Field Act iteration 3 설계 및 최소 구현
- [x] Field Act local quality gate와 gap analysis 100%
- [x] Field Act iteration 3 clean commit/package와 identity 검증
- [x] 실제 서버 15분 smoke 수행 및 60초 미만 재사용 33건 확인
- [x] 후보 정상 종료와 검증된 v1.0.16 rollback
- [x] `spot-tcp-source-port-quarantine-v2` Plan 작성
- [x] `spot-tcp-source-port-quarantine-v2` Design 작성
- [ ] 별도 Do 승인 후 source-port quarantine v2 구현
- [ ] local Check와 design-code gap analysis
- [ ] 별도 승인 후 clean package와 실제 서버 15분 smoke
- [ ] 120분 canary는 새 15분 smoke가 모두 통과할 때까지 보류
