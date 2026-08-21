# spot-tcp-connection-reuse-remediation - Design Document

> Version: 1.2.0 | Date: 2026-08-21 | Status: Historical failed candidate, superseded
> Level: Dynamic | Plan: docs/01-plan/features/spot-tcp-connection-reuse-remediation.plan.md
> Branch: `codex/spot-tcp-connection-reuse-remediation` | Do authorization: Granted 2026-07-20

> **Historical snapshot.** 이 설계는 `bfd9be7`의 실패한 1차 cadence 후보를
> 설명한다. 현재 구현·운영 기준은
> `docs/04-report/spot-tcp-source-port-quarantine-v2.report.md`와
> `docs/02-design/features/spot-request-churn-remediation.design.md`를 따른다.

> Act gate: packet direction preflight implementation is authorized. A second SPOT
> application logic patch is not authorized until the iteration 2 transport design is
> proven and separately approved.

---

## 1. 개요

### 1.1 목적

기존 SPOT 이미지 획득 계약을 유지하면서 백엔드에서 이미지 upstream 연결
생성률을 제한한다. 직전 이미지 네트워크 시도가 끝난 뒤 다음 이미지 네트워크
시작까지 최소 `200ms`를 보장하여, 현장에서 확인된 local source port의 빠른
순환과 TCP 4-tuple 재사용 충돌을 줄인다.

이 문서는 구현 방법과 검증 기준을 확정하지만 구현을 수행하지 않는다.

### 1.2 설계 결정 요약

| 항목 | 결정 |
|---|---|
| 제한 위치 | 백엔드 `fetch_image_async()`의 단일 이미지 경계 |
| 최소 간격 | 직전 image upstream 완료 → 다음 image upstream 시작 `200ms` |
| 최대 이미지 시작률 | `5회/초` 이하 |
| 시계 | `time.monotonic()` |
| 대기 방식 | 취소 가능한 `await asyncio.sleep()` |
| 잠금 순서 | image lock → cadence 대기 → device lock → upstream request |
| 사용자 설정 | 1차 구현에서는 제공하지 않음; private 안전 상수 사용 |
| cache | 추가하지 않음 |
| API | 기존 계약 유지, `/api/spot/config.image` 진단 필드만 additive 추가 |
| frontend | 변경하지 않음 |
| OS/장비 | Windows TCP, NIC, switch, SPOT 설정 변경 없음 |

### 1.3 설계 목표

- 모든 이미지 호출자가 같은 제한을 통과하게 한다.
- 이미지 cadence 대기가 SPOT 온도·진단·제어 통신을 막지 않게 한다.
- 실제 TCP/HTTP 지연과 애플리케이션이 의도한 cadence 대기를 구분한다.
- 실패 후 자동 재시도도 제한하되 기존 재시도 정책은 유지한다.
- stale frame이나 성공 위장 없이 매 성공 응답마다 새 JPEG를 가져온다.
- 구현과 배포를 작은 diff와 명확한 rollback 단위로 유지한다.

## 2. 현재 구조와 문제

### 2.1 현재 성공 경로

```text
CameraWidget <img> onLoad
        |
        v
singleton useSpotViewModel.runSpotFetch("completed")
        |
        v
GET /api/spot/image.jpg
        |
        v
spot_api.fetch_image_async()
        |
        +--> _img_fetch_lock
        +--> _spot_device_request_lock
        +--> GET http://{SPOT_IP}/image.jpg
        |
        v
HTTP/1.0 200 + JPEG + SPOT FIN
        |
        v
Blob 표시 완료 즉시 다음 요청
```

프런트엔드는 하나의 요청만 in-flight로 유지하지만 성공 직후 지연 없이 다음
요청을 시작한다. SPOT은 `HTTP/1.0` 응답마다 연결을 닫기 때문에 백엔드
`AsyncClient`가 있어도 이미지 TCP 연결은 재사용되지 않았다. 그 결과 이미지
API만 평균 약 `30.659/s`, 전체 SPOT TCP SYN은 약 `42.757/s`가 되었다.

### 2.2 변경 후 경로

```text
GET /api/spot/image.jpg
        |
        v
_img_fetch_lock 획득
        |
        v
직전 image upstream 완료 후 200ms가 지났는가?
        |                         |
       예                        아니오
        |                         |
        |                  asyncio.sleep(남은 시간)
        |                         |
        +------------+------------+
                     |
                     v
          _spot_device_request_lock 획득
                     |
                     v
           GET SPOT /image.jpg
                     |
                     v
     성공/실패/취소 시 실제 시도 완료 시각 기록
```

중요한 경계는 cadence sleep 중 `_spot_device_request_lock`을 잡지 않는 것이다.
따라서 이미지 호출 한 개는 기다리고 있어도 온도, 진단, focus 또는 actuator가
공용 장비 잠금을 먼저 얻어 실행할 수 있다.

## 3. 구성요소 설계

### 3.1 고정 안전 상수

`backend/FacilityData/drivers/spot_api.py`에 다음 의미의 private 상수를 둔다.

```python
_SPOT_IMAGE_MIN_COMPLETION_TO_START_SEC = 0.2
```

이 값은 이미지 저장 간격인 `SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC` 및 온도/진단
주기인 `SPOT_REFRESH_INTERVAL`과 전혀 다른 값이다. 이름과 주석에 이 차이를
명시한다.

1차 구현에서는 config.ini, 환경 변수, Settings UI에 노출하지 않는다.

- 안전 하한을 운영자가 실수로 `0`으로 바꿔 보호 기능을 제거하지 못한다.
- 기존 config.ini 자동 수정과 설정 migration이 없다.
- 단일 검증 package와 단일 rollback package의 동작이 결정적이다.
- 현장 canary 결과로 다른 값이 필요하면 별도 Plan/Design 갱신 후 설정화한다.

### 3.2 프로세스 내부 상태

다음 상태는 프로세스 시작 시 초기화되고 영속 저장하지 않는다.

| 상태 | 초기값 | 의미 |
|---|---:|---|
| `_img_last_upstream_completed_monotonic` | `None` | cadence 계산용 마지막 실제 네트워크 시도 완료 시각 |
| `_img_upstream_request_count` | `0` | 실제 image upstream 시도가 시작된 누적 횟수 |
| `_img_cadence_wait_count` | `0` | 양수 시간만큼 cadence 대기를 완료한 횟수 |
| `_img_cadence_wait_total_ms` | `0.0` | 완료한 cadence 대기의 누적 시간 |
| `_img_cadence_wait_max_ms` | `0.0` | 한 번의 cadence 대기 최댓값 |
| `_img_last_upstream_started_at` | `None` | 운영 표시용 최근 시작 epoch seconds |
| `_img_last_upstream_completed_at` | `None` | 운영 표시용 최근 완료 epoch seconds |

monotonic 값은 간격 계산에만 사용하고 API에 직접 노출하지 않는다. 운영 표시용
epoch 시각은 상관 분석을 위한 참고값이며 cadence 계산에는 사용하지 않는다.

상태는 기존 이미지 상태처럼 프로세스 내부 scalar다. 진단 endpoint가 읽는 순간의
best-effort snapshot이며 영속 counter 또는 과금/감사용 정확도 계약은 아니다.

### 3.3 cadence 계산

개념 알고리즘은 다음과 같다.

```python
async def wait_for_image_cadence():
    previous = _img_last_upstream_completed_monotonic
    if previous is None:
        return

    remaining = max(
        0.0,
        previous + _SPOT_IMAGE_MIN_COMPLETION_TO_START_SEC - time.monotonic(),
    )
    if remaining <= 0.0:
        return

    started = time.monotonic()
    await asyncio.sleep(remaining)
    record_completed_wait(max(0.0, time.monotonic() - started))
```

규칙은 다음과 같다.

1. 첫 요청 또는 이미 200ms가 지난 요청은 즉시 진행한다.
2. 시스템 wall clock이 변경되어도 간격은 monotonic clock으로 계산한다.
3. `asyncio.sleep()`의 실제 완료 시간을 counter에 기록한다.
4. sleep 중 취소되면 `CancelledError`를 그대로 전파한다. upstream request와
   image 오류 count를 만들지 않으며 완료 대기 counter에도 포함하지 않는다.
5. clock 또는 scheduling 오차로 음수가 되면 `max(0.0, ...)`로 즉시 진행한다.

### 3.4 upstream 시작·완료 기록

cadence를 정확히 적용하려면 “route 호출 시작”이 아니라 실제 SPOT 네트워크
시도를 기준으로 한다.

- `_img_fetch_lock` 획득 후 cadence를 기다린다.
- cadence가 끝난 뒤 `_request_spot_image()`가 기존
  `_spot_device_request_lock`을 획득한다.
- 공용 잠금을 획득한 직후, `client.get()` 직전에 upstream start count와 시각을
  기록한다.
- `client.get()`이 성공, HTTP/request/timeout 오류 또는 취소로 끝나면 `finally`에서
  monotonic 및 epoch 완료 시각을 기록한다.
- 설정 누락처럼 네트워크 시도를 시작하지 않은 오류는 start/complete count와
  cadence 기준 시각을 변경하지 않는다.
- 응답 JPEG payload 검증 실패는 네트워크 연결 자체는 완료된 뒤이므로 완료 시각을
  이미 갱신한 상태로 처리한다.

이 규칙으로 timeout이나 invalid payload 직후에도 다음 호출이 200ms cadence를
우회할 수 없다.

### 3.5 잠금 순서와 동시성

고정 잠금 순서는 다음과 같다.

```text
image caller:
    _img_fetch_lock
        -> cadence sleep (device lock 미보유)
        -> _spot_device_request_lock
            -> image upstream GET

temperature/diagnostics/control caller:
    _spot_device_request_lock
        -> 해당 upstream request
```

- `_spot_device_request_lock`을 획득한 채 cadence sleep을 호출하지 않는다.
- 온도/진단/제어 경로가 `_img_fetch_lock`을 획득하지 않게 유지한다.
- 두 개의 image caller가 동시에 들어오면 두 번째 caller는 `_img_fetch_lock`에서
  대기하므로 cadence state를 동시에 계산하거나 갱신하지 않는다.
- 새 잠금이나 역순 잠금 경로를 추가하지 않으므로 deadlock surface를 늘리지 않는다.

### 3.6 latency 의미

세 가지 시간을 구분한다.

| 값 | 포함 | 제외 |
|---|---|---|
| `image_cadence_wait_*` | 의도한 200ms cadence 대기 | device lock 및 네트워크 |
| `X-Spot-Image-Latency-Ms` / success `latency_ms` | cadence 종료 후 image fetch 처리, 기존 device lock 대기 및 upstream 처리 | cadence sleep |
| error `request_elapsed_ms` | device lock 획득 후 실제 `client.get()` 시간 | cadence sleep 및 device lock 대기 |

기존 latency 의미를 바꾸지 않기 위해 `fetch_image_async()`의 success timer는 cadence
대기 후 시작한다. `SpotImageFetchError.request_elapsed_ms`의 측정 위치는 현재와 같이
`client.get()` 직전으로 유지한다.

## 4. 데이터 및 API 설계

### 4.1 이미지 API

`GET /api/spot/image.jpg` 계약은 변경하지 않는다.

| 항목 | 유지 계약 |
|---|---|
| 성공 | `200 image/jpeg`, 최신 upstream JPEG |
| cache | `Cache-Control: no-store, no-cache...`, `Pragma`, `Expires` 유지 |
| success headers | `X-Spot-Image-At`, `X-Spot-Image-Source`, `X-Spot-Image-Latency-Ms` 유지 |
| 설정 누락 | 기존 `404`, `config-missing` 유지 |
| upstream 실패 | 기존 `502`, code/status/error type/elapsed/diagnostics 유지 |
| payload rejection | 기존 `X-Spot-Payload-Rejection: 1` 유지 |

cadence 때문에 route의 전체 응답 시간은 늘 수 있지만 HTTP timeout으로 분류하거나
새 status code를 반환하지 않는다.

### 4.2 additive 진단 필드

기존 `GET /api/spot/config` 응답의 `image` 객체에 다음 필드만 추가한다.

| 필드 | 타입 | 의미 |
|---|---|---|
| `image_cadence_min_interval_ms` | `number` | 고정 cadence 값, 기본 `200.0` |
| `image_cadence_wait_count` | `number` | 완료된 양수 cadence 대기 누적 횟수 |
| `image_cadence_wait_total_ms` | `number` | 완료된 cadence 대기 누적 시간 |
| `image_cadence_wait_max_ms` | `number` | 단일 cadence 대기 최댓값 |
| `image_upstream_request_count` | `number` | 실제 image upstream 시도 시작 누계 |
| `image_last_upstream_started_at` | `number \| null` | 최근 시작 epoch seconds |
| `image_last_upstream_completed_at` | `number \| null` | 최근 완료 epoch seconds |

필드는 모두 프로세스 재시작 시 초기화되는 진단값이다. 기존 필드를 삭제·변경하지
않으므로 구버전 frontend consumer는 추가 필드를 무시하고 계속 동작한다.

### 4.3 영속 데이터

- DB table 또는 migration 없음.
- CSV header 또는 row 변경 없음.
- config.ini 변경 및 자동 backfill 없음.
- 이미지 evidence 저장 schema와 저장 최소 간격 변경 없음.
- 관측성 export가 `/api/spot/config` 원문을 포함하면 새 필드는 additive로만 전달됨.

## 5. 오류 및 lifecycle 설계

### 5.1 정상 성공

1. cadence 통과.
2. SPOT 공용 잠금 획득.
3. upstream count/start 기록.
4. `GET /image.jpg` 성공 및 connection 완료 기록.
5. HTTP status와 JPEG payload 검증.
6. 기존 success 상태, evidence enqueue, metadata 반환.
7. 프런트 이미지 표시 완료 후 다음 route 요청.

### 5.2 timeout 또는 request 오류

1. 실제 네트워크 시도 시작과 완료 시각을 기록한다.
2. 기존 `SpotImageFetchError` code와 `request_elapsed_ms`를 유지한다.
3. route는 기존 502와 관측성 error를 남긴다.
4. 프런트 자동 복구가 `500/1000/2000ms` 정책으로 재호출한다.
5. 재호출도 cadence gate를 통과한다. 재시도 지연이 이미 200ms보다 길면 추가
   cadence sleep은 0이 된다.

### 5.3 invalid payload

네트워크 완료 시각을 기록한 뒤 기존 JPEG 검증이 오류를 낸다. 기존 정책대로
자동 재시도를 무한 수행하지 않고 명시적인 오류/Retry 상태를 유지한다.

### 5.4 취소 및 종료

- cadence sleep 중 취소: 네트워크 미실행, image 오류 미기록, 취소 전파.
- device lock 대기 중 취소: 네트워크 미실행, 마지막 완료 시각 미변경.
- `client.get()` 중 취소: 실제 연결 시도가 있었으므로 완료 시각을 `finally`에서
  기록하고 취소는 변환하지 않고 전파.
- 앱 종료 시 새 background task를 만들지 않으므로 별도 shutdown drain은 없다.

### 5.5 cadence 내부 오류

상수와 scalar state만 사용하므로 정상 경로에서 별도 도메인 오류를 만들지 않는다.
진단 counter 기록 실패가 발생하더라도 upstream 오류로 잘못 분류하지 않도록
상태 갱신은 단순하고 예외 없는 숫자 연산으로 제한한다.

## 6. 구현 범위와 순서

### 6.1 예정 파일

| 파일 | 예정 변경 | 필수 여부 |
|---|---|---|
| `backend/FacilityData/drivers/spot_api.py` | cadence 상수·상태·대기·기록·진단 필드 | 필수 |
| `backend/tests/test_spot_api.py` | 시간, 잠금, 실패, 취소, 진단 회귀 테스트 | 필수 |
| `scripts/qa_spot_image_server.ps1` | 관찰 request rate 계산과 `5/s` 초과 blocker | 필수 |
| `docs/03-analysis/spot-tcp-connection-reuse-remediation.analysis.md` | 구현 후 design-code gap 및 검증 결과 | Check 단계 |
| Report | mandatory gate 실패로 별도 완료 보고서 미생성 | 미진입 |

1차 구현에서 변경하지 않을 파일:

- `backend/config.py`
- `backend/app.py`
- `frontend/**`
- DB/CSV schema 및 migration
- 기존 현장 증거 원본

실제 구현 중 위 비변경 파일을 수정해야 할 필요가 발견되면 즉시 Do를 중단하고
Plan/Design 및 사용자 승인을 먼저 갱신한다.

### 6.2 구현 순서

1. `codex/spot-tcp-connection-reuse-remediation` 브랜치와 깨끗한 기준 commit을 확인한다.
2. 관련 기존 backend 및 frontend 회귀 테스트를 먼저 실행해 baseline을 기록한다.
3. `spot_api.py`에 상수, cadence state와 작은 helper를 추가한다.
4. image lock/device lock 사이에 cadence를 연결하고 actual start/complete를 기록한다.
5. 기존 diagnostics payload에 additive 필드를 추가한다.
6. deterministic unit/concurrency/cancellation 테스트를 추가한다.
7. QA script에 관찰률과 blocker를 추가한다.
8. focused/full test, typecheck/lint/health, diff/security 검사를 수행한다.
9. 구현 commit을 만든 뒤 clean provenance package를 생성한다.
10. 별도 배포 승인 후 실제 서버 60분 canary와 rollback 판단을 수행한다.

## 7. 테스트 설계

### 7.1 단위 테스트

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| CAD-01 | 프로세스 첫 이미지 호출 | sleep 없이 upstream 1회 |
| CAD-02 | 직전 완료 후 50ms에 다음 호출 | 약 150ms cadence wait 후 upstream |
| CAD-03 | 직전 완료 후 200ms 이상 | sleep 없음 |
| CAD-04 | 연속 성공 호출 | 실제 upstream 시작률 최대 5/s |
| CAD-05 | timeout/request error 후 즉시 호출 | 실패 완료 기준으로 cadence 적용 |
| CAD-06 | 설정 누락 | 네트워크 count/완료 기준 시각 변경 없음 |
| CAD-07 | HTML/invalid JPEG | 연결 완료 시각 갱신, 기존 payload error 유지 |
| CAD-08 | 두 image caller 동시 실행 | 하나씩 실행, 두 번째가 cadence 우회하지 않음 |
| CAD-09 | cadence sleep 중 취소 | upstream 0회, image 오류 증가 없음, cancellation 전파 |
| CAD-10 | client.get 중 취소 | 완료 시각 갱신, cancellation 전파 |
| CAD-11 | cadence 중 temperature 호출 | temperature가 device lock을 획득해 완료 가능 |
| CAD-12 | wall clock 변경 | monotonic 간격은 영향 없음 |
| CAD-13 | clock 계산 음수 | sleep 없이 안전 진행 |
| CAD-14 | diagnostics 조회 | 새 필드 타입·초기값·누적값 정확, 기존 필드 유지 |
| CAD-15 | latency 구분 | cadence wait는 success latency/request elapsed에서 제외 |

시간 테스트는 실제 200ms sleep에 의존하지 않고 monotonic clock과 sleep을 제어하는
fake/patch를 사용한다. 동시성 테스트만 event와 짧은 실제 scheduling을 사용하되
시간 허용 오차를 넓혀 flaky test를 방지한다.

### 7.2 백엔드 route 회귀 테스트

- 성공 200/JPEG 및 모든 cache/header 유지.
- config-missing 404 유지.
- timeout/request/HTTP/payload 오류 502와 detail 유지.
- cadence 때문에 오류 count나 `request_elapsed_ms`가 변조되지 않음.
- `/api/spot/config.image`의 기존 consumer 필드 유지 및 새 필드 additive 확인.

### 7.3 HTTP/1.0 close 통합 테스트

로컬 TCP 모의 SPOT 서버가 매 요청마다 다음을 수행하게 한다.

1. `HTTP/1.0 200 OK`와 유효한 최소 JPEG를 반환한다.
2. keep-alive를 보내지 않는다.
3. 응답 후 연결을 닫는다.

관찰 시간 동안 completion-driven caller로 backend route를 반복 호출하고 다음을
검증한다.

- 성공률 100%.
- 요청 간격 최소 기준과 평균 시작률 `<= 5/s`.
- 매 응답은 fresh request이며 stale/cache source가 없음.
- QA script 결과의 `request_rate_per_sec <= 5.1`.

`5.1`은 timer 해상도와 짧은 관찰 구간의 bucket 경계 오차를 허용하는 QA 한계다.
제품 상수의 실제 계약은 `200ms` completion-to-start이므로 지속 평균은 5/s보다 낮다.

### 7.4 기존 회귀 테스트

- `backend/tests/test_spot_api.py` 전체.
- SPOT app route 관련 backend 테스트.
- `useSpotViewModel` singleton, completion, Blob display 및 auto-recovery 테스트.
- frontend typecheck, lint, Vitest.
- repository `npm run health` 또는 현재 canonical health command.
- `git diff --check`와 민감정보/내부 주소 scan.
- clean Git commit 기반 PyInstaller backend 및 NSIS package provenance.

### 7.5 실제 서버 canary

#### 준비

1. 직전 정상 installer/package, Git commit, SHA-256, config.ini를 백업한다.
2. 관리자 PowerShell, pktmon, ping, NIC counter, 앱 관측성 수집이 가능한지 확인한다.
3. 서버와 SPOT switch port의 시작 RX/TX/error/discard/CRC/link 값을 저장한다.
4. 앱 정상 화면을 열고 탭 추가, 반복 refresh, 별도 이미지 부하 시험을 하지 않는다.

#### 60분 관찰

동일 시계 기준으로 다음을 수집한다.

- 앱 `/stats`, `/health`, `/api/spot/config`, error queue.
- SPOT 대상 TCP packet 및 SYN/ACK/FIN/RST sequence.
- SPOT 1초 ping.
- 서버 process, port, CPU, memory, event-loop/HTTP latency.
- 서버 NIC와 switch port 종료 counter.
- 운영자가 본 이미지 멈춤, focus/actuator 동작 및 정확한 사건 시각.

#### 판정

Plan 6.2의 기준을 모두 적용한다. 특히 다음을 함께 만족해야 한다.

```text
image upstream start rate <= 5/s
total SPOT SYN 60-second p95 <= 20/s (정상 화면 기준)
same 4-tuple reuse under 60s = 0
old ACK -> PC RST collision = 0
SPOT image ConnectTimeout = 0
image route 5xx = 0
display update interval p95 <= 500ms
EX/LS/SPOT/CSV/memory/browser regression = 0
```

60분 동안 오류가 없더라도 packet rate가 제한되지 않았다면 실패다. 반대로 전체
SYN이 일시적으로 20/s를 넘으면 해당 시각의 온도/진단/제어 요청을 분리 분석한 뒤
판정한다.

## 8. 배포, 중단 및 롤백

### 8.1 브랜치 및 승인 Gate

- 모든 변경은 `codex/spot-tcp-connection-reuse-remediation`에서만 수행한다.
- 현재 승인 범위는 Plan/Design이다.
- 사용자가 별도로 “로직 패치 승인”하기 전에는 Do를 시작하지 않는다.
- Do 승인 후에도 source edit 전 `git status`, 기준 commit, 기존 미추적 파일과의
  충돌 여부를 다시 확인한다.
- 이 feature의 파일만 선택적으로 stage/commit하고 기존 조사 산출물을 섞지 않는다.

### 8.2 단계적 배포

1. 개발 PC 자동 검증 완료.
2. clean commit과 package SHA-256 확정.
3. 실제 서버 유지보수 시간에 기존 package 백업.
4. 새 package 설치 및 앱 재시작.
5. 기본 EX·LS·SPOT·CSV health 확인.
6. 60분 canary와 evidence 수집.
7. 통과 시 유지, 실패 시 즉시 증거 보존 후 rollback.

### 8.3 즉시 중단 조건

- SPOT image `ConnectTimeout` 또는 새 5xx 발생.
- 이미지 멈춤 또는 표시 갱신 p95가 1초 초과.
- SPOT 온도/진단/focus/actuator 오류 또는 눈에 띄는 지연 발생.
- EX/LS timeout 증가.
- CSV drop, queue 지속 증가 또는 memory/browser 경고 발생.
- packet에서 old ACK → RST 충돌 재현.
- 앱/서버 CPU 또는 event-loop 지연이 기존 baseline보다 유의하게 악화.

### 8.4 롤백

1. 수집 중인 packet/app evidence를 안전하게 종료하고 hash를 보존한다.
2. 앱을 종료한다.
3. 직전 검증 installer/package로 복구한다.
4. 앱을 재시작한다.
5. EX·LS·SPOT image/temperature, HTTP, CSV 및 memory 상태를 확인한다.
6. rollback package commit/SHA-256과 완료 시각을 기록한다.

DB, CSV 및 config migration이 없으므로 데이터 rollback은 필요하지 않다. 이전
package로 되돌리는 것이 전체 rollback 경로다.

## 9. 보안 및 운영 영향

- upstream URL은 기존과 같이 서버 설정의 `SPOT_IP`로만 구성한다.
- cadence 값은 request parameter, frontend 또는 사용자 설정에서 받지 않는다.
- 진단에 IP/MAC/response body/credential을 노출하지 않는다.
- raw PCAP은 내부 IP, MAC, HTTP payload를 포함할 수 있으므로 제한 저장소에 두고
  외부 공유에는 sanitized evidence만 사용한다.
- OS TCP registry, 방화벽, NIC, switch, SPOT 설정을 변경하지 않는다.
- 추가 background thread/task가 없어 shutdown 및 memory lifecycle 영향이 작다.

## 10. 호환성 및 잔여 위험

### 10.1 호환성

| 영역 | 영향 |
|---|---|
| Backend API consumer | 기존 응답 유지, config diagnostics만 additive |
| Frontend | 소스 변경 없음, 응답을 기다리는 시간만 약 200ms 증가 가능 |
| SPOT device | 공식 `/image.jpg`만 사용, 연결 생성률 감소 |
| EX/LS | 직접 변경 없음 |
| CSV/DB | schema/migration 없음 |
| 설정 | config.ini 변경 없음 |

### 10.2 잔여 위험

- 5fps가 현장 영상 사용성에 충분한지는 실제 운영자가 canary에서 확인해야 한다.
- 전체 SPOT 연결 중 이미지 외 온도/진단이 약 12/s 수준을 유지할 수 있다. 5fps
  적용 후에도 TCP 충돌이 남으면 이미지 cadence를 무작정 더 줄이기 전에 요청원별
  SYN 비율과 진단 polling fan-out을 다시 분석한다.
- SPOT 내부 TCP state 보존 시간은 장비 로그가 없어 정확히 측정되지 않았다. 따라서
  packet에서 빠른 4-tuple 재사용과 old ACK/RST가 사라지는지 현장 검증이 필수다.
- 08:10 host-side stall과 PLC 입력 오류는 의도적으로 남아 있으며 별도 개선 대상이다.

## 11. 추적성

| Plan 요구사항 | Design 섹션 |
|---|---|
| FR-01~03 첫 요청/간격/공통 경계 | 3.1, 3.3, 3.4 |
| FR-04~05 image/device lock | 3.5 |
| FR-06 monotonic clock | 3.2, 3.3 |
| FR-07~08 실패/취소 | 3.4, 5.2~5.4 |
| FR-09 latency 분리 | 3.6 |
| FR-10~11 API/진단 호환 | 4.1, 4.2 |
| FR-12 no cache/fresh JPEG | 1.3, 4.1, 7.3 |
| FR-13 retry 유지 | 5.2 |
| FR-14 온도/진단/제어 유지 | 3.5, 7.1, 10.1 |
| 개발/현장 성공 기준 | 7.1~7.5 |
| rollback/운영 실패 모드 | 8.2~8.4, 10.2 |

## 12. 명시적 제외 사항

- PLC empty-string 정규화 패치.
- host CPU/disk/scheduler/event-loop stall 계측 패치.
- frontend success timer.
- stale image cache, streaming 또는 새로운 image endpoint.
- Windows ephemeral port/TIME_WAIT registry 조정.
- SPOT firmware, switch 또는 NIC 설정 변경.
- Plan/Design 승인만으로 소스 구현, package build 또는 실제 서버 설치 수행.

## 13. Act iteration 2 재설계

### 13.1 Check 판정과 폐기된 가정

2026-07-21 실제 서버 canary에서 image cadence p95 `4.683/s`, 최대 `4.783/s`로
1차 rate limit은 정확히 동작했다. 그럼에도 필수 60분에 image
`ConnectTimeout/502` 3회, 전체 packet/log 보존 구간에 5회가 발생했다.

연장 양방향 packet 구간의 11:00과 11:20 사건은 다음 순서를 직접 보여준다.

```text
previous image connection
  -> same 4-tuple reused after about 219ms / 232ms
  -> SPOT returns an old plain ACK instead of SYN-ACK
  -> server sends RST
  -> OS retransmits the SYN about one second later
  -> old ACK / RST repeats
  -> application ConnectTimeout and HTTP 502 after about two seconds
```

따라서 다음 1차 가정은 폐기한다.

- `200ms` completion-to-start cadence가 local port의 60초 미만 재사용을 막는다는 가정.
- image rate만 `5/s` 이하로 낮추면 전체 SPOT TCP state 충돌이 제거된다는 가정.
- 요청률 목표 통과만으로 production promotion이 가능하다는 가정.

1차 구현은 rate 감소 효과가 있는 partial mitigation이지만 mandatory TCP/error gate를
통과하지 못했다. 당시 package를 승격하거나 해당 후보 브랜치를 병합하지 않는다.

### 13.2 전체 SPOT 요청 경계

2차 설계는 다음 요청원을 하나의 SPOT TCP system으로 본다.

| 요청원 | 현재 의미 | 2차 설계 보존 조건 |
|---|---|---|
| image | 정상 화면 JPEG, 약 5/s 제한 | fresh JPEG, 표시 latency/freshness 명시 |
| temperature | 1초 공정 온도 관측 | 측정 freshness와 cache origin 유지 |
| internal temperature | 장비 내부 온도 | background poll starvation 금지 |
| diagnostics | 여러 output parameter fan-out | 필드별 age/status 및 전체 갱신 주기 명시 |
| focus/actuator | 운영자 제어 | polling보다 높은 우선순위와 중복 실행 방지 |

기존 `_spot_device_request_lock`은 동시 요청을 직렬화하지만, 응답마다 SPOT이
`HTTP/1.0` 연결을 닫은 뒤 Windows가 local port를 다시 선택하는 것을 통제하지
못한다. 따라서 기존 lock에 단순 sleep을 추가하는 것만으로는 충분하지 않다.

### 13.3 구현 전 대안 실증 Gate

다음 대안을 작은 독립 prototype으로 비교한 후 하나를 선택한다. production
`spot_api.py`에는 이 단계에서 추가 변경을 하지 않는다.

| 대안 | 기대 효과 | 주요 위험 | Act 결정 |
|---|---|---|---|
| image cadence 상수만 증가 | image 연결률 추가 감소 | port 재사용 0건 보장 불가, 화면 지연 | 단독 해법 제외 |
| 전체 요청 global delay | 총 SYN 감소 | 온도 freshness와 focus/actuator 지연 | 단독 해법 제외 |
| diagnostics fan-out 분산/축소 | 약 10/s 진단 연결 감소 | 필드 age 증가, 여전히 port lifecycle 미통제 | 보조 후보 |
| application-owned source-port quarantine | 같은 target 4-tuple 재사용을 직접 방지 | custom transport, socket/port 고갈, shutdown 복잡성 | 우선 실증 후보 |
| SPOT 공식 장기 연결/stream resource | connection churn 제거 | 장비 지원, payload/freshness/복구 계약 불명 | 장비 지원 확인 후보 |
| timeout 내부 retry | 사용자 502 감소 가능 | 2초 이상 latency, 같은 충돌 반복, 부하 증가 | port 전략과 결합할 때만 검토 |
| stale frame HTTP 200 | 화면 멈춤 감소 | 오래된 영상을 현재값으로 오인, evidence 오염 | 제외 |

source-port quarantine prototype은 최소한 다음을 증명해야 한다.

1. 동일 SPOT target IP/port에 사용한 local port를 종료 후 최소 60초 다시 사용하지 않는다.
2. 필요한 port/socket 상한을 계산하고 Windows 기본 범위를 임의 변경하지 않는다.
3. bind 충돌, 취소, timeout, 앱 종료 시 socket을 누수 없이 정리한다.
4. httpx/httpcore 비공개 API에 의존한다면 버전 고정과 실패 시 fallback을 명시한다.
5. image, temperature, diagnostics 및 operator control의 기존 payload/error 계약을 유지한다.
6. HTTP/1.0 close 모의 서버에서 4-tuple reuse 0건과 resource budget을 자동 증명한다.

이 prototype이 위 조건을 충족하지 못하면 application transport 구현을 중단하고,
SPOT이 공식 지원하는 장기 연결 resource 또는 현장 gateway 대안을 다시 설계한다.

### 13.4 packet direction preflight 상세 설계

현장 PCAP은 수집 시작부터 09:32:43까지 SPOT→서버 패킷을 포함하지 않았다.
앱은 같은 구간에 정상 SPOT 응답을 받았으므로 이 구간은 실제 단방향 장애가 아니라
capture blind spot이다. 다음 수집기는 본 관찰 전에 passive probe를 수행한다.

```text
existing filter safety check
  -> add this script's SPOT TCP filter
  -> start a separate pktmon probe ETL
  -> wait 10 seconds while the normal screen remains unchanged
  -> stop and convert the probe to brief text
  -> count server:any -> SPOT:80 packets
  -> count SPOT:80 -> server:any packets
       | both > 0                  | either = 0 / conversion failed
       v                           v
  start full evidence capture     fail closed, preserve raw probe, clean owned filter
```

설계 규칙:

- 10초 probe는 30초 safety limit 안에서 끝난다.
- probe를 위해 HTTP, ping 또는 image load 요청을 새로 만들지 않는다.
- localized `Direction Tx/Rx` 문구에 의존하지 않고 brief packet의 IPv4 TCP endpoint
  순서와 configured SPOT target port `80`을 판독한다.
- probe ETL/text는 `raw_private/network`에만 보존한다.
- sanitized summary에는 `passed/failed`, probe seconds 및 방향별 count만 기록한다.
- 한쪽 방향이 0이거나 변환이 실패하면 본 app/ping/packet 수집을 시작하지 않는다.
- 실패 시 앱 재시작, 오류 clear, NIC/pktmon 설정 변경을 제안하거나 자동 수행하지 않는다.
- 기존 filter가 있었으면 시작하지 않고, 이 script가 소유한 filter만 기존 안전 규칙으로 정리한다.

### 13.5 preflight 테스트

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| DIR-01 | outbound와 inbound brief line 각 1개 | `passed=true`, count 1/1 |
| DIR-02 | outbound만 존재 | `passed=false` |
| DIR-03 | inbound만 존재 | `passed=false` |
| DIR-04 | 빈/인식 불가 text | `passed=false`, 예외 없는 count 0/0 |
| DIR-05 | Korean/English packet header | endpoint line만 사용하므로 동일 판정 |
| DIR-06 | probe conversion 실패 | full capture 미시작, manifest FAILED |
| DIR-07 | probe 실패 중 cleanup | 소유 filter만 제거하고 raw probe 보존 |
| DIR-08 | sanitized export | target/server IP와 MAC 미노출 |

### 13.6 rollback 및 다음 승인점

canary는 Design 8.3의 즉시 중단 조건을 충족했다. 실제 서버에서는 직전 검증
installer/package로 복귀하고 EX·LS, SPOT image/temperature, HTTP, CSV 및 memory를
확인해야 한다. rollback package가 식별되지 않은 상태에서 임의 installer를 실행하면
안 된다.

수집기 preflight 구현·self-test 완료 후에도 다음 SPOT application patch는 시작하지
않는다. 13.3 prototype 결과, 선택 대안, freshness/latency/resource budget과 rollback을
Design에 확정하고 사용자의 별도 구현 승인을 받는 시점이 다음 gate다.

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 1.0.0 | 2026-07-20 | backend image cadence와 현장 검증/롤백 설계 확정 | Codex |
| 1.0.1 | 2026-07-20 | 승인된 로컬 구현 완료와 현장 validation pending 상태 반영 | Codex |
| 1.1.0 | 2026-07-21 | canary 실패와 4-tuple 충돌 재확인, 전체 SPOT transport 실증 gate 및 bidirectional capture preflight 설계 추가 | Codex |
| 1.2.0 | 2026-08-21 | 실패 후보를 역사 기록으로 동결하고 현재 source-port quarantine 운영 기준 링크 추가 | Codex |
