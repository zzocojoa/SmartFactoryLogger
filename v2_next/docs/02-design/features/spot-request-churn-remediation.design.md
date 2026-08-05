# spot-request-churn-remediation - Design Document

> Version: 1.1.0 | Date: 2026-07-27 | Status: Field Act iteration 3 locally implemented
> Level: Dynamic
> Plan: `docs/01-plan/features/spot-request-churn-remediation.plan.md`
> Branch: `codex/spot-request-churn-remediation`
> Base: `master` / `v1.0.16` / `834ed85`

---

## 1. 개요

### 1.1 목적

v1.0.16의 SPOT 공식 HTTP 경로와 검증된 `httpx` 동작은 유지하면서 정상 화면이
생성하는 신규 TCP 연결을 줄인다. 설계는 세 방어 계층으로 구성한다.

1. frontend가 성공한 image 표시 직후 재요청하지 않고 기존
   `SPOT_REFRESH_INTERVAL`에 맞춰 다음 요청을 예약한다.
2. backend가 fresh image cache와 single-flight를 제공하여 복수 caller가 같은
   freshness window에 만든 요청을 한 번의 SPOT upstream 연결로 합친다.
3. backend가 8개 diagnostic parameter sweep를 매 temperature poll마다 실행하지
   않고 장비 보호 간격에 맞춰 재사용한다.

이 설계는 source port를 직접 제어하지 않는다. 4-tuple 재사용 위험은 신규 연결
총량을 80% 이상 줄이는 방식으로 완화하며, 실제 재사용 감소는 packet canary에서
검증한다.

### 1.2 핵심 설계 결정

| 항목 | 결정 |
|---|---|
| frontend cadence | image 표시 완료 후 effective refresh interval만큼 `setTimeout` |
| 주기 입력 | 기존 `SPOT_REFRESH_INTERVAL` 재사용 |
| frontend 주기 경계 | 최소 1.0초, 최대 10.0초 |
| backend cache | process-local JPEG 1개와 상수 크기 metadata |
| freshness 시계 | `time.monotonic()` |
| image upstream 최소 간격 | 3.0초 |
| cache TTL | `max(frontend effective interval, 3.0초)` |
| diagnostic sweep 최소 간격 | 10.0초 |
| 전체 background SPOT budget | 이론상 최대 6 connections/s |
| concurrent miss | shared `asyncio.Task` 하나를 `asyncio.shield`로 await |
| fresh cache | upstream 요청 없이 반환 |
| stale-on-error | 금지; 만료 뒤 refresh 실패는 기존 502 |
| HTTP client | 기존 `httpx.AsyncClient` 유지 |
| device serialization | 기존 `_spot_device_request_lock` 유지 |
| source port | OS 기본 할당; bind/pool/quarantine 금지 |
| API | 기존 계약 유지, source/age/diagnostics만 additive |
| persistence | DB/CSV/config migration 없음 |
| rollback | 검증된 v1.0.16 installer 복귀 |

### 1.3 구현 원칙

- 요청을 “늦게 많이 처리”하는 대신 불필요한 요청 자체를 만들지 않는다.
- backend가 최종 방어선이므로 복수 tab, LAN browser, settings preview 또는
  구버전 frontend가 있어도 upstream rate가 caller 수에 비례하지 않게 한다.
- cache는 성능 장치이면서 장비 보호 장치다. 오류를 숨기는 가용성 fallback으로
  사용하지 않는다.
- standard library와 `httpx` 위에서만 구현한다.
- 실패했던 raw-socket parser의 source, framing logic, source-port allocator를
  복사하거나 import하지 않는다.

## 2. 현재 구조

### 2.1 현재 정상 경로

```text
CameraWidget image onLoad
  -> runSpotFetch("completed") 즉시 실행
  -> GET /api/spot/image.jpg?t={timestamp}
  -> fetch_image_async()
  -> _img_fetch_lock
  -> _spot_device_request_lock
  -> httpx GET http://{SPOT}/image.jpg
  -> HTTP/1.0 200 + Content-Length + server FIN
  -> Blob 표시
  -> onLoad가 다음 요청 즉시 실행
```

`_img_fetch_lock`은 image 동시 실행을 하나로 제한하고
`_spot_device_request_lock`은 image·temperature·diagnostics·control 요청을
직렬화한다. 두 lock은 동시성은 막지만 완료와 다음 시작 사이의 시간을 제한하지
않는다. SPOT 응답이 빠르면 frontend loop도 빠르게 회전한다.

### 2.2 현재 polling 구성

- frontend image: 성공 완료 기반 tight loop
- temperature: `SPOT_REFRESH_INTERVAL`, 기본 3초
- internal temperature: temperature loop에서 별도 async task
- diagnostics: 각 temperature poll에 최대 8개 parameter를 순차 요청
- control: operator action 때만 실행

초기 설계에서는 image가 지배적이라고 가정했으나 실제 candidate 15분 smoke에서
image는 `0.9618/s`, diagnostics는 `7.9956/s`였다. 전체 `10.9562/s` 중 diagnostic
8개 fan-out이 가장 큰 background 부하였다. 따라서 image만 낮추고 diagnostics를
temperature poll마다 유지하는 설계로는 `6/s` field gate를 통과할 수 없다.

## 3. 목표 구조

### 3.1 전체 data flow

```text
visible frontend instance
  |
  | initial 또는 scheduled GET
  v
/api/spot/image.jpg
  |
  v
fetch_image_async()
  |
  +-- fresh cache? -- yes --> bytes + source=cache + original captured_at
  |
  no
  |
  +-- refresh task exists? -- yes --> shielded await as waiter
  |
  no
  |
  +-- create one shared refresh task as leader
        |
        +-- existing _spot_device_request_lock
        +-- existing httpx.AsyncClient GET /image.jpg
        +-- status/JPEG validation
        +-- atomically publish immutable cache entry
        +-- image capture enqueue exactly once
        +-- leader/waiters receive same entry
```

frontend는 반환된 Blob의 표시 성공 뒤 바로 fetch하지 않는다.
`effective_refresh_interval_sec` 뒤 한 번만 fetch한다. backend cache는
`max(effective_refresh_interval_sec, 3초)` TTL을 사용하므로 운영 설정이 1초이고
caller가 둘 이상이어도 SPOT upstream image 요청은 최대 약 `0.333/s`로 제한된다.

### 3.2 component 책임

| component | 책임 | 하지 않는 일 |
|---|---|---|
| refresh policy pure helper | config 값을 1~10초로 정규화 | timer 생성, network 호출 |
| `useSpotViewModel` | 정상 timer와 오류 retry의 단일 소유권 | upstream TTL 우회 |
| image lifecycle effect | visibility/unmount cleanup | backend cache 제어 |
| `fetch_image_async` | downstream count, fresh check, shared refresh join | raw socket 사용 |
| shared refresh helper | 실제 upstream 1회, validation, cache publish | stale fallback |
| diagnostic budget scheduler | 10초 이상 간격의 8-field sweep | temperature poll 차단 |
| diagnostics snapshot | cache/churn/budget counter의 best-effort 표시 | source port 노출 |
| route `spot_image` | 기존 HTTP 계약과 additive headers | browser cache 허용 |

### 3.3 Field Act background budget

운영 `refresh_interval=1.0s`, internal temperature URL 사용을 기준으로 한 상한은
다음과 같다.

| 종류 | 규칙 | 최대 요청률 |
|---|---|---:|
| image | backend TTL 최소 3초 | `0.333/s` |
| temperature | 기존 1초 poll 유지 | `1.000/s` |
| internal temperature | 기존 1초 poll 유지 | `1.000/s` |
| diagnostics | 8 requests / 최소 10초 sweep | `0.800/s` |
| 합계 | operator control 제외 background 상한 | `3.133/s` |

설정 오류 또는 legacy 설정으로 temperature poll이 내부 하한 `0.5s`까지 빨라져도
상한은 image `0.333` + temperature `2.0` + internal `2.0` + diagnostics `0.8`
= `5.133/s`다. 따라서 source port를 직접 제어하지 않고도 `6/s` gate 아래를
유지한다. focus/actuator는 operator action이므로 background budget에 포함하지
않으며 기존 device serialization을 그대로 사용한다.

diagnostic sweep는 startup 첫 poll에서 즉시 한 번 실행한다. 이후 monotonic start
간격이 10초보다 짧으면 새 task를 만들지 않고 기존 snapshot을 사용한다. 실행 중인
sweep가 있으면 중복 실행하지 않는다. diagnostic max age는 effective sweep interval의
2배 이상으로 맞춰 정상 decimation을 stale failure로 오인하지 않는다.

## 4. frontend 상세 설계

### 4.1 effective refresh interval

새 pure helper는 seconds 입력을 다음 규칙으로 정규화한다.

```text
parse finite number
  -> invalid 또는 <= 0: 3.0s
  -> 0 < value < 1.0: 1.0s
  -> 1.0 <= value <= 10.0: value
  -> value > 10.0: 10.0s
```

상수:

```text
DEFAULT_SPOT_IMAGE_REFRESH_INTERVAL_SEC = 3.0
MIN_SPOT_IMAGE_REFRESH_INTERVAL_SEC = 1.0
MAX_SPOT_IMAGE_REFRESH_INTERVAL_SEC = 10.0
```

최소값은 tight-loop와 과도한 connection churn을 막는다. 최대값은 잘못된 설정 때문에
운영자가 10초 넘게 같은 frame을 현재 영상으로 보는 것을 막는다. 기존 기본값 3초에는
변화가 없다.

### 4.2 timer 상태

`useSpotViewModel`은 기존 automatic retry timer와 별도로 다음 ref를 소유한다.

| 상태 | 초기값 | 의미 |
|---|---:|---|
| `normalRefreshTimerRef` | `null` | 다음 정상 image fetch timer |
| `nextNormalRefreshAtRef` | `null` | 진단용 예정 epoch ms |
| `isDocumentVisibleRef` | 현재 visibility | background polling 차단 |

helper:

- `cancelNormalImageRefresh()`
- `scheduleNormalImageRefresh()`
- `resumeImageRefreshWhenVisible()`

정상 timer와 automatic retry timer는 상호 배타적이다.

### 4.3 상태 전이

#### 최초 진입

1. config와 image URL을 확인한다.
2. visible이면 `runSpotFetch("initial")`을 즉시 한 번 실행한다.
3. hidden이면 timer를 만들지 않고 visibility 복귀를 기다린다.

#### 정상 fetch와 표시 성공

1. fetch 성공과 JPEG validation 뒤 새 Blob URL을 게시한다.
2. `<img>`의 `onLoad`에서 이전 Blob URL을 정리한다.
3. automatic retry state를 초기화한다.
4. `runSpotFetch("completed")`를 즉시 호출하지 않는다.
5. effective interval 뒤 `runSpotFetch("scheduled")` 하나를 예약한다.

주기는 upstream 시작 간격이 아니라 **표시 완료부터 다음 fetch 시작까지**다.
따라서 slow response에서도 중첩 요청이 생기지 않고 device load는 설정 주기보다
높아지지 않는다.

#### retryable failure

1. 정상 refresh timer를 취소한다.
2. 기존 `500/1000/2000ms` automatic retry 정책을 유지한다.
3. retry 중 성공하면 표시 완료 뒤 정상 timer로 복귀한다.
4. retry가 소진되면 정상 timer를 자동 재개하지 않고 기존 오류/수동 Retry UX를
   유지한다.

실패 상태에서 정상 timer와 retry timer가 동시에 요청을 보내면 안 된다.

#### manual retry

1. 정상 timer와 pending retry를 취소한다.
2. in-flight가 없을 때만 `runSpotFetch("manual")`을 호출한다.
3. `force=true`, cache bypass, TTL 같은 query parameter를 보내지 않는다.
4. 성공하면 정상 cadence로 복귀한다.

#### hidden, visible, unmount

- hidden: 정상 timer를 취소한다. 진행 중 fetch는 강제 취소하지 않고 결과 처리를
  완료하되 다음 정상 timer는 만들지 않는다.
- visible 복귀: in-flight와 retry pending이 없고 image URL이 있으면 즉시 한 번
  fetch한 뒤 정상 cadence로 복귀한다.
- unmount: 정상 timer, retry timer와 Blob URL을 모두 기존 lifecycle 규칙대로 정리한다.

### 4.4 frontend diagnostics

기존 `SpotPollingDiagnostics`의 의미를 복구한다.

| 필드 | 값 |
|---|---|
| `refresh_interval_ms` | effective interval × 1000 |
| `next_fetch_scheduled_at` | 정상 timer 예정 epoch ms 또는 null |
| `last_fetch_reason` | `initial`, `scheduled`, `manual`, `automatic-retry`, `visible-resume` |
| `in_flight` | 실제 backend fetch 진행 중 |
| retry 필드 | 기존 의미 유지 |

config 변경으로 interval만 바뀌면 기존 timer를 취소하고 새 interval로 다시 예약한다.
image URL이 바뀌면 기존 Blob/recovery lifecycle과 initial fetch 계약을 유지한다.

## 5. backend cache와 single-flight 설계

### 5.1 immutable cache entry

private frozen dataclass 또는 동등한 immutable structure를 사용한다.

```python
@dataclass(frozen=True)
class _SpotImageCacheEntry:
    image_bytes: bytes
    captured_at_epoch: float
    captured_at_monotonic: float
    upstream_latency_ms: float
```

cache는 entry 하나만 가진다. 최대 payload는 기존 upstream/image capture 제한과
route validation을 그대로 적용한다. 새 파일 저장, database row 또는 CSV field는
만들지 않는다.

### 5.2 process state

```text
_spot_image_cache_entry: Optional[_SpotImageCacheEntry]
_spot_image_refresh_task: Optional[asyncio.Task[_SpotImageCacheEntry]]
_img_fetch_lock: existing asyncio.Lock
```

diagnostics counter:

```text
_img_downstream_request_count
_img_upstream_request_count
_img_cache_hit_count
_img_singleflight_leader_count
_img_coalesced_waiter_count
_img_refresh_success_count
_img_refresh_failure_count
_img_last_upstream_started_at
_img_last_upstream_completed_at
```

모든 counter는 process-local best-effort 값이며 앱 재시작 시 0이 된다.

### 5.3 freshness 판정

backend도 frontend와 같은 1~10초 정규화 함수를 Python으로 구현한다.

```python
age_sec = max(0.0, time.monotonic() - entry.captured_at_monotonic)
fresh = age_sec < effective_refresh_interval_sec
```

- wall clock은 header 표시용 captured time에만 사용한다.
- monotonic 값이 비정상적으로 미래면 fresh로 무한 유지하지 않고 cache miss로
  처리하고 진단 warning counter를 남긴다.
- TTL 경계와 같거나 큰 entry는 expired다.

### 5.4 double-check와 task 생성

개념 알고리즘:

```python
async def fetch_image_async():
    resolve image URL
    increment downstream count

    entry = read fresh cache
    if entry:
        increment cache hit
        return cached response

    async with _img_fetch_lock:
        entry = read fresh cache again
        if entry:
            increment cache hit and coalesced waiter
            return cached response

        task = current refresh task
        if task is None or task.done():
            task = create_task(refresh_and_publish(image_url))
            current refresh task = task
            increment leader count
        else:
            increment coalesced waiter count

    entry = await asyncio.shield(task)
    return upstream for leader, cache/coalesced metadata for waiter
```

실제 구현은 lock 안에서 network await를 하지 않는다. lock은 fresh 상태 재확인과
shared task reference 교체만 보호한다.

leader와 waiter source 구분은 caller별로 결정한다.

- shared task를 새로 만든 caller: `source="upstream"`
- 기존 task를 join한 caller: `source="coalesced"`
- task 완료 뒤 fresh entry를 읽은 caller: `source="cache"`

외부 API가 단순 source만 사용해야 한다면 `coalesced`는 additive 허용값으로
노출한다. cache hit 통계에는 coalesced를 별도 집계하여 중복 계산하지 않는다.

### 5.5 refresh task

`_refresh_and_publish_spot_image()`가 다음을 한 번 수행한다.

1. 기존 `_get_http_client()`를 사용한다.
2. 기존 `_request_spot_image()`를 호출한다.
3. `_request_spot_image()` 안의 `_spot_device_request_lock`, timeout, HTTP status,
   JPEG validation을 유지한다.
4. 실제 network 시작/완료 시각과 upstream counter를 기록한다.
5. 유효한 bytes만 immutable cache entry로 publish한다.
6. 기존 `_record_image_success()`를 한 번 호출한다.
7. 기존 `_maybe_enqueue_spot_image_capture()`를 한 번 호출한다.
8. 성공/failure counter를 한 번 갱신한다.

오류 기록은 shared task에서 한 번만 수행한다. waiter 수만큼 upstream failure
counter를 증가시키지 않는다. 각 downstream route가 같은 502를 관측하는 기존 HTTP
요청 통계는 별개로 유지한다.

### 5.6 failure와 stale cache

refresh failure의 규칙:

- 기존 `SpotImageFetchError.code`, upstream status, transport error type,
  request elapsed를 유지한다.
- 이전 cache entry가 있어도 expired면 HTTP 200으로 반환하지 않는다.
- expired entry를 즉시 삭제할 필요는 없다. diagnostics의 last-good captured time과
  recovery 분석에만 남길 수 있다.
- 다음 automatic/manual/scheduled caller는 TTL을 우회하지 않지만 expired 상태이므로
  새 shared refresh를 시작할 수 있다.
- invalid/HTML/empty payload는 cache에 publish하지 않는다.

이 정책은 영상 stale 안전 위험과 오류 은폐를 방지한다.

### 5.7 cancellation과 shutdown

모든 caller는 shared task를 `asyncio.shield()`로 기다린다.

- waiter 취소: waiter만 취소되고 shared refresh는 계속된다.
- leader caller 취소: caller만 취소되고 shared refresh는 다른 waiter와 cache를
  위해 계속된다.
- 모든 caller 취소: task done callback이 exception/result를 회수해 unobserved task
  warning을 만들지 않는다.
- 앱 shutdown: 신규 refresh 생성 금지 flag를 먼저 세우고 active refresh task를
  기존 shutdown timeout 안에서 기다린다. timeout이면 task를 취소하고 결과를
  warning으로 기록하되 product shutdown을 무한 대기시키지 않는다.
- test reset: active task 종료, cache와 counter 초기화를 보장한다.

shutdown 동안 stale image를 반환하거나 새로운 background retry를 만들지 않는다.

### 5.8 lock 순서

고정 순서:

```text
caller:
  _img_fetch_lock
    -> cache/task reference 확인
  release _img_fetch_lock
    -> shielded refresh await

refresh task:
  _spot_device_request_lock
    -> httpx upstream request
```

금지:

- `_spot_device_request_lock`을 보유한 채 `_img_fetch_lock` 획득
- `_img_fetch_lock`을 보유한 채 network await
- thread lock과 asyncio lock을 교차 획득
- cache diagnostics sync read에서 network 호출

temperature, diagnostics, control 경로는 `_img_fetch_lock`을 사용하지 않는다.

## 6. API 설계

### 6.1 `GET /api/spot/image.jpg`

request 계약은 변경하지 않는다.

- query의 기존 timestamp는 browser cache busting용으로 무시한다.
- `force`, `ttl`, `upstream_url`, `source_port` 같은 새 입력은 추가하지 않는다.
- browser/proxy cache 금지 header는 유지한다. server-side bounded cache와
  browser cache는 서로 다른 계층이다.

### 6.2 성공 응답

기존:

```text
200
Content-Type: image/jpeg
Cache-Control: no-store, no-cache, must-revalidate, max-age=0
Pragma: no-cache
Expires: 0
X-Spot-Image-At: <original capture epoch ms>
X-Spot-Image-Source: upstream | cache | coalesced
X-Spot-Image-Latency-Ms: <original upstream acquisition latency>
```

additive:

```text
X-Spot-Image-Age-Ms: <route response 시점의 cache age>
```

`X-Spot-Image-Latency-Ms`는 cache hit 처리시간이 아니라 해당 JPEG를 실제 SPOT에서
획득할 때의 latency를 유지한다. frontend가 측정하는 전체 fetch latency는 기존
`receivedAt - startedAt`으로 별도 존재한다.

### 6.3 오류 응답

기존 status와 detail을 유지한다.

- config missing: 404
- upstream timeout/request/HTTP/payload failure: 502
- payload rejection header: 유지
- error queue source/path/status: 유지

cache가 있었음을 오류 detail에 넣어 stale data의 존재를 외부 caller에게 노출하거나
자동 fallback을 유도하지 않는다. 운영 diagnostics에서는 last-good age를 볼 수 있다.

### 6.4 diagnostics

기존 `/api/spot/config`의 `image` object에 다음을 additive로 추가한다.

| 필드 | 타입 | 의미 |
|---|---|---|
| `image_request_policy_version` | string | `spot-image-demand-shaping-v2` |
| `image_refresh_interval_sec_effective` | number | 3~10초 backend upstream 보호 결과 |
| `image_downstream_request_count` | integer | backend route가 요청한 누계 |
| `image_upstream_request_count` | integer | 실제 SPOT GET 시작 누계 |
| `image_cache_hit_count` | integer | immediate fresh cache 반환 누계 |
| `image_singleflight_leader_count` | integer | shared refresh 생성 누계 |
| `image_coalesced_waiter_count` | integer | existing refresh join 누계 |
| `image_refresh_success_count` | integer | upstream 성공/publish 누계 |
| `image_refresh_failure_count` | integer | upstream refresh 실패 누계 |
| `image_cache_present` | boolean | last-good entry 존재 여부 |
| `image_cache_fresh` | boolean | 현재 TTL 안인지 |
| `image_cache_age_ms` | number/null | monotonic age |
| `image_refresh_in_flight` | boolean | shared task 진행 여부 |
| `image_last_upstream_started_at` | number/null | epoch seconds |
| `image_last_upstream_completed_at` | number/null | epoch seconds |
| `request_budget_policy_version` | string | `spot-background-request-budget-v2` |
| `request_budget_target_max_per_sec` | number | field gate `6.0` |
| `request_budget_*_max_per_sec` | number | image/temperature/internal/diagnostics 상한 |
| `request_budget_total_background_max_per_sec` | number | 설정 기준 합산 상한 |
| `request_budget_within_target` | boolean | 합산 상한이 field gate 이하인지 |
| `diagnostics_refresh_interval_sec_effective` | number | 최소 10초 sweep 간격 |
| `diagnostics_refresh_in_flight` | boolean | sweep task 실행 여부 |
| `diagnostics_sweep_started_count` | integer | 실제 sweep 시작 누계 |
| `diagnostics_upstream_request_count` | integer | diagnostic upstream GET 누계 |
| `diagnostics_suppressed_poll_count` | integer | interval budget으로 생략한 poll 누계 |
| `diagnostics_inflight_suppressed_count` | integer | 실행 중 중복을 생략한 poll 누계 |
| `diagnostics_last_started_at` | number/null | 마지막 sweep 시작 epoch |
| `diagnostics_last_completed_at` | number/null | 마지막 sweep 종료 epoch |

IP, URL, source port, MAC, payload 또는 absolute path는 추가하지 않는다.

## 7. data와 persistence

### 7.1 영속 변경 없음

- database migration 없음
- CSV header/row 변경 없음
- config.ini 새 key 또는 자동 rewrite 없음
- image fact schema 변경 없음
- frontend localStorage schema 변경 없음

### 7.2 image capture writer

기존 image evidence capture는 실제 upstream 성공에만 연결한다.

- leader upstream success: 기존 정책에 따라 enqueue 가능
- cache hit: enqueue하지 않음
- coalesced waiter: enqueue하지 않음
- refresh failure: enqueue하지 않음

따라서 downstream caller 수가 evidence 파일 수를 부풀리지 않는다.

## 8. 예정 파일과 최소 변경

### 8.1 필수 파일

| 파일 | 예정 변경 |
|---|---|
| `frontend/src/domains/FacilityData/hooks/useSpotViewModel.ts` | 즉시 completion loop를 정상 timer로 교체 |
| `frontend/src/domains/FacilityData/hooks/useSpotViewModelEffects.ts` | visibility/unmount cadence lifecycle |
| `frontend/src/domains/FacilityData/hooks/useSpotViewModel.integration.test.ts` | timer/retry/visibility 통합 test |
| `frontend/src/domains/FacilityData/utils/spotImageRefreshPolicy.pure.ts` | 1~10초 pure normalization |
| `frontend/src/domains/FacilityData/utils/spotImageRefreshPolicy.pure.test.ts` | boundary test |
| `frontend/src/domains/FacilityData/api/spotService.types.ts` | additive age/source metadata 필요 시 확장 |
| `backend/FacilityData/drivers/spot_api.py` | cache, shared refresh, counter, lifecycle |
| `backend/tests/test_spot_api.py` | cache/single-flight/failure/cancellation tests |
| `backend/app.py` | additive image age header |
| 관련 app route test | 기존 API 계약과 additive header 검증 |

### 8.2 조건부 파일

| 파일 | 변경 조건 |
|---|---|
| `frontend/src/shared/types.ts` | diagnostics 필드를 정적 타입으로 소비할 때만 |
| operational QA script | local HTTP/1.0 multi-client rate gate가 기존 script로 불가능할 때 |
| field guide | clean package 승인 뒤 실제 서버 Check 단계 |

### 8.3 변경 금지

- `backend/FacilityData/drivers/spot_transport.py` 신규 생성 금지
- diagnostics 브랜치의 retired adapter import 금지
- raw-socket parser, source-port allocator, port quarantine code 금지
- OS/network configuration script 추가 금지
- PLC/EX/LS/CSV schema 변경 금지

구현 중 변경 금지 범위가 필요해지면 Do를 중단하고 Plan·Design과 승인 범위를
다시 갱신한다.

## 9. 구현 순서

### Do-0 baseline과 guard

1. branch, clean status, base `834ed85` 확인
2. relevant backend/frontend test baseline 실행
3. prohibited component scan 기준 확정
4. refresh interval pure helper와 boundary test 구현

### Do-1 frontend cadence

5. normal timer ref와 cancel/schedule helper 추가
6. completion 즉시 재요청을 scheduled fetch로 교체
7. automatic retry와 정상 timer 상호 배제
8. visibility/config/unmount lifecycle 연결
9. fake timer 기반 frontend tests 통과

### Do-2 backend demand shaping

10. immutable cache entry와 diagnostics state 추가
11. freshness helper와 immediate cache hit 추가
12. shared refresh task 생성/join/shield 추가
13. upstream success/failure/image capture를 shared task 단위로 이동
14. shutdown/test reset lifecycle 추가
15. additive diagnostics와 age header 추가
16. deterministic backend concurrency/cancellation tests 통과

### Do-3 local Check 준비

17. HTTP/1.0 close multi-client QA 실행
18. focused tests, full health, diff/security scan
19. Design-code gap analysis
20. 별도 Check 승인 전 installer를 만들지 않음

각 Do 묶음은 작은 commit으로 분리할 수 있지만 최종 package는 clean 통합 commit
하나의 provenance를 가져야 한다.

## 10. test 설계

### 10.1 frontend pure tests

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| FE-POL-01 | undefined/null/NaN/string 오류 | 3.0초 |
| FE-POL-02 | 0/음수 | 3.0초 |
| FE-POL-03 | 0.1/0.999 | 1.0초 |
| FE-POL-04 | 1/3/10 | 입력 유지 |
| FE-POL-05 | 10 초과/Infinity | 10.0초 또는 invalid default 정책에 맞는 bounded 값 |

Infinity는 invalid로 먼저 분류하므로 3초를 사용한다. 유한 11은 10초로 clamp한다.

### 10.2 frontend integration tests

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| FE-INT-01 | initial config load | 즉시 image 요청 1회 |
| FE-INT-02 | image onLoad | 즉시 추가 요청 0, 3초 뒤 1회 |
| FE-INT-03 | 연속 성공 | interval당 1회, timer 중복 0 |
| FE-INT-04 | slow fetch | in-flight 중 timer 신규 요청 0 |
| FE-INT-05 | retryable failure | 정상 timer 취소, 500/1000/2000ms만 실행 |
| FE-INT-06 | retry 성공 | onLoad 뒤 정상 cadence 복귀 |
| FE-INT-07 | retry 소진 | 자동 정상 loop 재개 안 함 |
| FE-INT-08 | manual retry | timer 정리, 요청 1회, force query 없음 |
| FE-INT-09 | hidden | 정상 timer 정리, background 요청 0 |
| FE-INT-10 | visible 복귀 | 즉시 1회 뒤 정상 timer |
| FE-INT-11 | unmount | timer와 Blob URL 모두 정리 |
| FE-INT-12 | interval config 변경 | 구 timer 취소 후 새 interval 적용 |
| FE-INT-13 | 두 image DOM consumer | 같은 view-model에서 backend fetch 중복 없음 |

### 10.3 backend unit tests

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| BE-CACHE-01 | cache 없음 | upstream 1회, source upstream |
| BE-CACHE-02 | TTL 안 재요청 | upstream 증가 0, source cache |
| BE-CACHE-03 | TTL 경계 | expired, upstream refresh 1회 |
| BE-CACHE-04 | wall clock 역행 | monotonic freshness 영향 없음 |
| BE-CACHE-05 | monotonic future 이상 | cache miss로 안전 처리 |
| BE-CACHE-06 | 유효 JPEG 성공 | entry publish와 capture enqueue 1회 |
| BE-CACHE-07 | invalid/empty/HTML | entry 미게시, 기존 오류 유지 |
| BE-CACHE-08 | refresh failure + expired entry | stale 200 금지, 기존 502 |
| BE-CACHE-09 | failure 뒤 recovery | 다음 shared refresh 성공, cache 교체 |
| BE-CACHE-10 | config missing | task/network/counter 오염 없음 |

### 10.4 backend concurrency tests

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| BE-CON-01 | 20 concurrent cold callers | upstream 1회, leader 1, waiter 19 |
| BE-CON-02 | 20 concurrent fresh callers | upstream 0회, cache hit 20 |
| BE-CON-03 | waiter cancellation | shared task와 다른 waiter 성공 |
| BE-CON-04 | leader caller cancellation | shared task와 waiter 성공 |
| BE-CON-05 | 모든 caller cancellation | task exception warning/누수 없음 |
| BE-CON-06 | image refresh 중 temperature | fixed lock 순서로 순차 완료 |
| BE-CON-07 | image refresh 중 control | deadlock/starvation 없이 완료 |
| BE-CON-08 | shutdown 중 active refresh | bounded drain 또는 명시적 cancel |
| BE-CON-09 | refresh task 완료/교체 race | 같은 task만 clear, 새 task reference 보존 |
| BE-CON-10 | failure with 20 waiters | upstream failure counter 1, caller 오류 일관 |

### 10.5 route/API tests

- 기존 200/JPEG/cache-control headers 유지
- upstream/cache/coalesced source와 captured time 유지
- additive age header finite/nonnegative
- 기존 404/502/detail/payload rejection 유지
- cache hit가 SPOT upstream call과 image capture enqueue를 늘리지 않음
- diagnostics field 타입, 초기값, 누계와 process reset 확인
- 3초 image 하한과 10초 diagnostic sweep 하한의 strict boundary 확인
- 가장 빠른 0.5초 poll에서도 계산된 background 상한 `<=6/s`
- diagnostic sweep 실행 중 또는 10초 안에는 새 task가 생성되지 않음
- URL/IP/source port/payload가 diagnostics에 없음

### 10.6 HTTP/1.0 close multi-client QA

모의 SPOT은 매 요청마다 다음을 수행한다.

1. `HTTP/1.0 200 OK`
2. 유효한 JPEG와 Content-Length 반환
3. 응답 뒤 server FIN
4. keep-alive 없음

동시에 1, 2, 10개 caller로 backend route를 호출한다.

backend image 보호 간격 3초의 최소 gate:

```text
downstream success = 100%
upstream image requests per 60s <= 30
upstream image 60s p95 rate <= 0.5/s
one freshness window upstream count <= 1
cache/coalesced source counts > 0 when caller > 1
SPOT request 5xx = 0
unhandled task / handle leak = 0
```

짧은 자동 test에서는 fake monotonic 또는 축소 가능한 test-only dependency injection을
사용한다. production TTL을 환경 변수나 request parameter로 변경하지 않는다.

### 10.7 repository regression

- `backend/tests/test_spot_api.py`
- SPOT app route/observability/image capture tests
- frontend `useSpotViewModel`과 image recovery/payload tests
- frontend typecheck, lint, Vitest
- Ruff, mypy, backend unittest
- Electron startup tests
- `npm run health`
- `git diff --check`
- secret, private IP, absolute server path scan
- raw socket/source-port prohibited pattern review

## 11. 실제 서버 Check 설계

### 11.1 package gate

제품 Do와 local Check가 별도 승인으로 완료된 뒤에만 package를 만든다.

1. clean Git HEAD 확인
2. branch/commit 기록
3. PyInstaller backend manifest 검증
4. NSIS installer SHA-256 기록
5. 설치된 backend 예상 SHA-256 기록
6. rollback installer
   `42A076B37ADA66CEAEE816128A1FC67C40CCD1C5417F9BDED5E885478974F615`
   재확인

### 11.2 15분 smoke

- 현재 프로그램 정상 종료 후 검증 package 설치
- backend SHA-256/health/process count 확인
- 앱 정상 화면과 사전 운영/관측성 상태 보존
- packet direction preflight
- passive 15분 수집
- Plan 7.2의 모든 gate 판정

한 항목이라도 실패하면 120분으로 진행하지 않는다.

### 11.3 120분 canary

15분 smoke를 통과한 동일 binary/config로 진행한다.

- 정상 화면 유지
- error trigger와 packet tail 보존
- downstream/upstream/cache counter 동시 수집
- TCP attempts/handshake/failure/reuse/RST/retransmission 분석
- ping/NIC/Windows TCP counter 비교
- managed switch가 없으면 physical attribution만 PARTIAL로 표시

### 11.4 판정 계산

```text
connection_reduction_pct
  = (1 - candidate_total_spot_opens_per_sec / 37.674) * 100

upstream_suppression_ratio
  = 1 - image_upstream_request_count / image_downstream_request_count
```

required:

```text
connection_reduction_pct >= 80%
total SPOT opens 60s p95 <= 6/s
image upstream starts 60s p95 <= 0.5/s
same 4-tuple reuse under 60s = 0
ConnectTimeout / SPOT 5xx = 0
temperature / diagnostic / control regression = 0
```

downstream image requests가 여전히 많아도 upstream suppression과 전체 TCP gate를
통과하면 장비 보호 목표는 달성한 것이다. 그러나 frontend cadence 자체가 적용되지
않은 것이므로 frontend request rate gate는 별도로 실패 처리하고 수정한다.

### 11.5 field 중단과 rollback

중단 시:

1. packet/app evidence 안전 종료
2. raw/private와 sanitized hash 보존
3. 앱 정상 종료
4. v1.0.16 rollback installer 설치
5. backend SHA-256 확인
6. 앱 재시작
7. EX·LS·SPOT image/temperature, HTTP, CSV, memory 확인
8. 후보를 promotion하지 않고 failure evidence로 보존

오류 queue를 지우거나 실패 package로 재실행해 증거를 덮어쓰지 않는다.

## 12. 보안과 privacy

- upstream URL은 기존 server config에서만 해석한다.
- caller가 TTL, force refresh, source port 또는 upstream target을 제공하지 않는다.
- cache bytes는 process memory 밖으로 새로 저장하지 않는다.
- diagnostics는 allowlisted 숫자/boolean/source label만 노출한다.
- source port 번호와 4-tuple은 제품 로그에 남기지 않는다.
- raw packet은 field collector의 private 영역에서만 보관하고 sanitized 공유 정책을
  유지한다.
- custom parser, unsafe deserialization, shell/network policy 변경이 없다.
- 새 dependency를 추가하지 않는다.

## 13. 호환성과 migration

| 영역 | 영향 |
|---|---|
| backend endpoint | method/status/body 유지, headers additive |
| old frontend + new backend | fresh cache를 투명하게 사용 |
| new frontend + old backend | frontend cadence만으로 요청률 감소 |
| config.ini | 기존 refresh interval 사용, rewrite 없음 |
| DB/CSV | migration 없음 |
| image fact | upstream 성공 기준 유지 |
| SPOT 장비 | 공식 endpoint와 HTTP client 유지, 요청량 감소 |
| EX/LS | 직접 변경 없음 |

frontend와 backend를 함께 package하지만 양쪽 방어 계층은 각각 독립적으로 안전한
감소 효과가 있어 mixed-version 진단도 가능하다.

## 14. 운영 실패 모드

| 실패 모드 | 관측 | 동작 |
|---|---|---|
| frontend timer 미적용 | downstream rate 높음, upstream은 cache로 제한 | candidate Check 실패, backend 보호는 유지 |
| cache TTL 미적용 | upstream/downstream 비율 1에 가까움 | 즉시 rollback |
| cache가 영구 fresh | image age 증가, upstream count 정지 | stale safety 실패, 즉시 rollback |
| shared refresh deadlock | in-flight true 지속, image freeze | timeout/evidence 보존 후 rollback |
| SPOT connect failure 재발 | SYN 무응답/502 | physical attribution과 무관하게 rollback |
| diagnostics 정상 decimation | 10초 sweep, max age 20초 이상 | cached snapshot 사용 |
| diagnostics starvation | max age 초과 missing/stale/timeout 증가 | rollback |
| control starvation | focus/actuator 지연/실패 | rollback |
| config invalid | effective interval diagnostic 3초 | tight loop 없이 운영 |
| process restart | cache/counter 0, 첫 요청 upstream | 정상 cold start |

## 15. 요구사항 추적성

| Plan 요구사항 | Design |
|---|---|
| P0-01, FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, FR-07, FR-08 | 4.1~4.4 |
| P0-02, P0-03, P0-04, FR-09, FR-10, FR-11, FR-12, FR-13, FR-14, FR-15 | 5.1~5.5 |
| P0-05, FR-16 | 5.6, 6.3 |
| P0-06, 금지선 | 1.2~1.3, 8.3, 12 |
| P0-07, FR-17, FR-18 | 5.7~5.8, 10.4 |
| P0-08, FR-19, FR-20, FR-21, FR-22, FR-23, FR-24 | 6.1~6.4 |
| P0-09 | 7, 11.5, 13 |
| P1-01, P1-02, P1-03 | 10.1~10.6 |
| P1-04, P1-05 | 11.1~11.5 |
| P2-01 | Field Act iteration 3에서 3.3, 6.4, 10.5로 승격 |
| P2-02 | 관리형 switch 접근 부재로 후속 범위 유지 |
| NFR-01, NFR-02, NFR-03, NFR-04, NFR-05 | 4, 5, 10.6, 11.4 |
| NFR-06, NFR-07, NFR-08, NFR-09, NFR-10, NFR-11 | 7, 10.7, 13 |
| NFR-12, NFR-13, NFR-14 | 6.1, 8.3, 12 |
| 성공/실패 gate | 10.6~10.7, 11 |

## 16. 승인 Gate

- Plan: Complete
- Design: Complete
- Do iteration 2: Complete
- Actual-server Check: **Failed / rollback completed**
- Act iteration 3: **Local implementation and quality gates complete**
- package build: Not authorized
- actual server install/check: Not authorized
- merge/promotion: Not authorized

다음 단계는 별도 Check 승인 후 clean commit/package identity와 실제 서버 15분
smoke를 검증하는 것이다. 이번 Act 완료 자체는 installer 생성 또는 실제 서버 작업
권한이 아니다.

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 1.1.0 | 2026-07-27 | image 3초 하한, diagnostic 10초 sweep, 전체 SPOT budget Field Act | Codex |
| 1.0.0 | 2026-07-24 | frontend cadence + backend fresh cache/single-flight 상세 설계 | Codex |
