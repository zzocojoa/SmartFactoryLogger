# spot-tcp-source-port-quarantine-v2 - Design Document

> Version: 1.0.0 | Date: 2026-07-27 | Status: Design approved, Do pending
> Level: Dynamic
> Plan: `docs/01-plan/features/spot-tcp-source-port-quarantine-v2.plan.md`

---

## 1. 설계 개요

### 1.1 목적

기존 request-budget과 image demand-shaping을 유지하면서 Windows가 같은 SPOT
source port를 60초 안에 다시 선택할 수 없도록 source-port lifecycle을
애플리케이션이 소유한다.

HTTP protocol 처리는 Python 표준 `http.client`에 위임한다. 폐기된 후보의 custom
raw-socket request serializer와 response parser는 사용하지 않는다.

### 1.2 핵심 결정

| 항목 | 결정 |
|---|---|
| quarantine | connect 종료 시점부터 최소 `75.0s` |
| pool | OS가 동적으로 할당한 guard port `768개` |
| port 소유권 | Windows `SO_EXCLUSIVEADDRUSE` guard socket |
| HTTP parser | Python `http.client` |
| async 격리 | single-worker `ThreadPoolExecutor` |
| device 직렬화 | 기존 `_spot_device_request_lock` 유지 |
| request budget | 기존 `spot-background-request-budget-v2` 유지 |
| 실패 정책 | pool/guard 실패 시 fail-closed; OS 자동 포트 fallback 금지 |
| API | 기존 계약 유지, aggregate diagnostics만 additive |
| persistence | DB/CSV/config migration 없음 |
| rollout | clean package와 실제 서버 15분 smoke 별도 승인 |
| rollback | 검증된 v1.0.16 installer |

### 1.3 왜 요청률 추가 감소만으로 해결하지 않는가

실제 서버에서 전체 SPOT 신규 연결률은 p95 `3.1333/s`까지 감소했지만 동일
4-tuple 재사용이 `51.052s`부터 33건 발생했다. OS allocator 동작은 요청률만으로
결정적으로 통제할 수 없다.

화면과 진단 freshness를 더 희생해 연결률을 낮추는 방법도 재사용 0건을 보장하지
못한다. 따라서 freshness 계약은 유지하고 port 재선택 자체를 차단한다.

## 2. 아키텍처

### 2.1 구성

```text
FastAPI / poll / control caller
        |
        v
existing _spot_device_request_lock
        |
        +-- async request -----------------------------+
        |                                              |
        |                         single-worker executor
        |                                              |
        +-- focus/actuator sync operation              |
                                                       v
                                           StdlibSpotHttpTransport
                                                       |
                                  +--------------------+-------------------+
                                  |                                        |
                                  v                                        v
                         SourcePortLeasePool                 http.client.HTTP(S)Connection
                                  |                          source_address=("", lease_port)
                                  |                                        |
                                  +--------------------+-------------------+
                                                       v
                                             SPOT HTTP/1.x endpoint
```

### 2.2 파일 경계

| 파일 | 책임 |
|---|---|
| `backend/FacilityData/drivers/spot_port_quarantine.py` | guard socket, lease state, quarantine, aggregate diagnostics |
| `backend/FacilityData/drivers/spot_http_transport.py` | URL validation, stdlib HTTP request/response, timeout/error mapping, worker lifecycle |
| `backend/FacilityData/drivers/spot_api.py` | 기존 request kind별 validation과 public 오류 계약, transport 주입 및 lifecycle 연결 |
| `backend/tests/test_spot_port_quarantine.py` | state machine과 exact boundary |
| `backend/tests/test_spot_http_transport.py` | HTTP/1.0 loopback, source address, failure/cancellation |
| `backend/tests/test_spot_api.py` | image/temperature/diagnostic/control 회귀와 diagnostics |

`spot_transport.py`라는 이름을 재사용하지 않는다. 폐기 브랜치의 parser, allocator,
exception 또는 test fixture를 import하거나 복사하지 않는다.

### 2.3 플랫폼 경계

실제 enforcement는 Windows packaged runtime에만 활성화한다.

- Windows:
  - `SO_EXCLUSIVEADDRUSE`가 없거나 guard pool 초기화가 실패하면 정책을
    `active=false`로 낮추지 않고 transport startup을 실패시킨다.
  - SPOT upstream 요청은 시작하지 않는다.
- non-Windows 개발/CI:
  - production enforcement가 지원되지 않음을 diagnostics에 명시한다.
  - lease state machine은 fake socket adapter로 검증한다.
  - loopback protocol test는 명시적 `source_address` 지원 범위에서 실행한다.

Windows 후보 package의 pre-smoke는 `supported=true`, `active=true`,
`pool_capacity=768`을 hard gate로 확인한다.

## 3. SourcePortLeasePool

### 3.1 상수

```text
POLICY_VERSION = "spot-source-port-quarantine-v2"
POOL_CAPACITY = 768
QUARANTINE_SECONDS = 75.0
ACQUIRE_TIMEOUT_SECONDS = 5.0
BIND_RETRY_LIMIT = 8
REBOUND_RETRY_INTERVAL_SECONDS = 1.0
```

`768`은 hard field gate `6 connections/s`에서 75초 동안 필요한 450개 lease보다
70% 이상 크다. 운영 후보의 예상값 `3.133/s`에서는 약 235개가 quarantine에
머문다. 실제 가용성은 diagnostics와 pre-smoke에서 다시 확인한다.

### 3.2 내부 상태

```text
guarded
  |
  | acquire: close exclusive guard
  v
leased
  |
  | every terminal request path
  v
quarantined
  |
  | monotonic now >= released_at + 75s
  | and exclusive guard bind succeeds
  v
guarded
```

guard 재설정이 OS TCP state 때문에 실패하면 `rebind_pending`으로 남기고
available queue에 넣지 않는다. 이후 bounded timer가 다시 guard를 시도한다.

### 3.3 초기화

각 record는 다음 순서로 만든다.

1. IPv4 TCP socket 생성
2. `SO_EXCLUSIVEADDRUSE=1`
3. configured local host와 port `0`에 bind
4. OS가 선택한 실제 port를 record 내부에만 저장
5. 중복 여부를 확인하고 guarded queue에 추가

중간 실패 시 이미 만든 모든 guard socket을 닫고 초기화를 실패시킨다. 부분 pool로
운영하지 않는다.

### 3.4 lease와 bind race

1. acquire가 guarded record 하나를 leased로 전환한다.
2. guard socket을 닫는다.
3. transport가 동일 port를 `source_address`로 지정한다.
4. bind 관련 `OSError`가 발생하면 해당 record를 quarantine하고 다른 lease로
   최대 8회 재시도한다.
5. connect timeout, connection refused, protocol error 등 bind 외 오류는 다른
   port로 숨기지 않고 기존 오류 계약으로 반환한다.

`EADDRINUSE`, Windows `WSAEADDRINUSE(10048)`처럼 확인된 bind 충돌만 alternate
lease 대상이다.

### 3.5 재사용 invariant

각 record는 내부적으로 마지막 connect start monotonic 값을 가진다.

```text
current_connect_started - previous_connect_started >= 75.0
```

이 invariant가 깨지면 요청을 보내지 않고 fatal policy violation으로 전환한다.
실제 port와 timestamp 배열은 외부 diagnostics에 노출하지 않는다.

### 3.6 pool 고갈

acquire가 5초 안에 lease를 얻지 못하면 `SpotPortPoolExhausted`를 발생시킨다.
다음 동작은 금지한다.

- `source_address=None`으로 재시도
- 임의 port를 caller가 지정
- quarantine 시간을 단축
- stale image를 HTTP 200으로 반환

고갈은 15분 field gate 즉시 실패와 rollback 조건이다.

## 4. 표준 HTTP transport

### 4.1 request 모델

```python
@dataclass(frozen=True)
class SpotHttpRequest:
    kind: SpotRequestKind
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None
    connect_timeout_sec: float
    read_timeout_sec: float
```

`SpotRequestKind`는 최소 다음 값을 가진다.

- `image`
- `temperature`
- `internal_temperature`
- `diagnostic`
- `focus_read`
- `focus_write`
- `actuator_read`
- `actuator_write`

### 4.2 response 모델

```python
@dataclass(frozen=True)
class SpotHttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes
    elapsed_ms: float
```

source port와 local/remote address는 response 모델에 포함하지 않는다.

### 4.3 URL validation

transport 진입 전에 `urllib.parse.urlsplit`로 다음을 확인한다.

- absolute `http` 또는 `https`
- hostname 존재
- username/password 없음
- fragment 없음
- method는 allowlist `GET`, `PUT`

path와 query는 `http.client`에 전달할 origin-form으로 조립한다. caller가
source port, local address 또는 target override를 전달할 field는 만들지 않는다.

### 4.4 request 실행

worker 내부 실행 순서는 다음과 같다.

1. request validation
2. lease acquire
3. `HTTPConnection` 또는 `HTTPSConnection` 생성
4. constructor에 `source_address=("", lease.port)`와 connect timeout 전달
5. `connect()` 실행
6. 연결된 socket의 read timeout 설정
7. `request(method, path, body, headers)`
8. `getresponse()`
9. 표준 `HTTPResponse.read()`로 body 읽기
10. status/header/body를 immutable response로 복사
11. connection close
12. `finally`에서 lease quarantine

HTTP status 해석, Content-Length, chunked framing 및 EOF 처리는
`http.client.HTTPResponse`에만 맡긴다.

### 4.5 async와 cancellation

transport는 single-worker executor를 소유한다.

- background async caller는 `run_in_executor` 결과를 `asyncio.shield`로 기다린다.
- caller가 취소돼도 worker는 socket timeout 안에서 종료될 때까지 실행한다.
- lease release는 worker `finally`가 소유하므로 caller task가 직접 release하지
  않는다.
- cancellation 이후 결과는 폐기하되 worker failure는 aggregate diagnostics와
  bounded log로 남긴다.
- 전용 worker가 하나이므로 caller cancellation 뒤 다른 SPOT 요청이 동시에
  장비로 전송되지 않는다.

기존 `_spot_device_request_lock`도 유지해 queue 진입 전 request 종류 간 순서를
보존한다.

### 4.6 focus와 actuator

현재 focus/actuator는 `urllib.request.urlopen`을 default executor에서 실행한다.
Do에서는 URL resolution, position parsing, clamp 및 verify loop를 유지하고 실제
GET/PUT 부분만 `SpotHttpTransport.request_sync()`로 교체한다.

기존 control operation 전체가 이미 `_spot_device_request_lock`과
`asyncio.shield`로 감싸져 있으므로 다음을 유지한다.

- read -> write -> verify 순서
- caller cancellation 후 실제 operation 완료 대기
- 기존 error class와 operator-facing message

## 5. 오류 계약

### 5.1 transport 내부 오류

| 내부 오류 | 조건 | public mapping |
|---|---|---|
| `SpotPortPoolInitError` | Windows exclusive guard 초기화 실패 | startup/pre-smoke fail |
| `SpotPortPoolExhausted` | acquire timeout | 기존 request error/502 |
| `SpotPortBindError` | bind retry 고갈 | 기존 request error/502 |
| `SpotTransportTimeout` | connect/read timeout | 기존 timeout classification |
| `SpotTransportRequestError` | DNS/connect/send/receive OS error | 기존 request error |
| `SpotTransportProtocolError` | stdlib parser/response 오류 | 기존 invalid upstream error |
| `SpotTransportClosedError` | shutdown 이후 요청 | controlled shutdown error |

### 5.2 기존 public 오류 유지

- image: `SpotImageFetchError`
- temperature: `SpotTemperatureFetchError`
- internal temperature: `SpotInternalTemperatureFetchError`
- focus: `SpotFocusControlError`
- actuator: `SpotActuatorControlError`

오류 message에 source port를 넣지 않는다. 내부 port bind 오류도 stage와 OS error
type/code만 allowlist하고 port 값은 제거한다.

## 6. lifecycle

### 6.1 startup

FastAPI lifespan에서 SPOT poll loop를 시작하기 전에 transport를 초기화한다.

```text
initialize transport
  -> initialize full guard pool
  -> start single worker
  -> mark active
  -> start existing SPOT poll loop
```

부분 초기화나 `active=false` 상태로 poll loop를 시작하지 않는다.

### 6.2 shutdown

```text
stop accepting image requests
  -> stop poll/diagnostic/control scheduling
  -> wait existing image refresh
  -> close transport intake
  -> bounded wait for worker
  -> close all guard sockets
  -> close legacy httpx client if still allocated on non-Windows
```

shutdown timeout 시 process termination을 무기한 막지 않되, diagnostics와 lifecycle
log에 worker drain 실패를 남긴다.

### 6.3 test reset

module-level pool, executor, counters 및 policy state를 초기화하는 test helper를
제공한다. production API에서는 호출할 수 없다.

## 7. diagnostics와 API

기존 `/api/spot/config`의 `image` 객체에 다음 aggregate field를 추가한다.

| field | type |
|---|---|
| `source_port_policy_version` | string |
| `source_port_enforcement_supported` | boolean |
| `source_port_enforcement_active` | boolean |
| `source_port_quarantine_seconds` | number |
| `source_port_pool_capacity` | integer |
| `source_port_pool_guarded_count` | integer |
| `source_port_pool_leased_count` | integer |
| `source_port_pool_quarantined_count` | integer |
| `source_port_pool_rebind_pending_count` | integer |
| `source_port_pool_acquire_wait_count` | integer |
| `source_port_pool_exhaustion_count` | integer |
| `source_port_bind_collision_count` | integer |
| `source_port_rebind_retry_count` | integer |
| `source_port_reuse_violation_count` | integer |
| `source_port_minimum_reuse_interval_seconds` | number/null |
| `source_port_transport_started_count` | integer |
| `source_port_transport_success_count` | integer |
| `source_port_transport_failure_count` | integer |

요청 종류별 count는 고정 allowlist mapping으로 제공할 수 있다. key나 label에 URL,
host 또는 port를 사용하지 않는다.

모든 counter는 process-local이며 restart 시 0으로 초기화된다. packet evidence가
field gate의 source of truth이고 내부 minimum interval은 보조 진단이다.

## 8. 구현 순서

1. `spot_port_quarantine.py`의 pure state model과 fake socket test
2. Windows guard socket adapter와 초기화/cleanup test
3. `spot_http_transport.py` request/response와 HTTP/1.0 loopback test
4. timeout, bind race, exhaustion, cancellation, shutdown test
5. image/temperature/diagnostic request path 교체
6. focus/actuator GET/PUT path 교체
7. transport startup/shutdown을 FastAPI lifecycle에 연결
8. aggregate diagnostics 추가
9. 전체 backend/Electron/health 검증
10. clean diff에서 retired raw transport 유사 코드와 prohibited import 검토

Do는 위 순서를 따르며 각 단계가 독립 테스트를 통과하기 전 다음 단계로 진행하지
않는다.

## 9. 테스트 계획

### 9.1 lease unit test

- 74.999초에는 같은 lease가 available이 아님
- 75.000초와 guard 성공 이후에만 available
- request success/failure/timeout/cancellation 모두 quarantine
- bind collision lease는 즉시 재사용하지 않음
- rebind 실패 record는 available count에서 제외
- 768개가 모두 unavailable이면 acquire timeout과 exhaustion count 증가
- fatal invariant violation 이후 신규 request 차단
- diagnostics에 실제 port 값이 없음

### 9.2 HTTP transport loopback

표준 라이브러리 기반 local server를 사용한다.

- HTTP/1.0 + Content-Length + server close
- HTTP/1.1 + chunked
- GET image bytes
- GET numeric temperature
- GET diagnostic text
- PUT focus body/header
- actuator query
- HTTP 4xx/5xx와 body 보존
- delayed connect/read timeout
- malformed response가 controlled protocol error
- server가 관측한 peer port와 leased port 일치
- 같은 lease가 75초 전에 다시 사용되지 않음

테스트 server는 제품 transport parser를 대체하지 않으며 fixture 내부에서만
동작한다.

### 9.3 cancellation과 shutdown

- caller cancellation 뒤 worker가 종료될 때까지 lease가 active/quarantined 상태
- cancellation 직후 두 번째 request가 실제 장비 I/O와 겹치지 않음
- shutdown 이후 신규 request 거부
- bounded worker drain 성공
- drain timeout 시 guard cleanup과 상태가 명시적으로 실패

### 9.4 regression

- 기존 `backend/tests/test_spot_api.py`
- image cache/single-flight/request-budget
- temperature/internal temperature/diagnostic freshness
- focus/actuator clamp, write ack, verify loop
- FastAPI image/config endpoint 계약
- Electron startup/shutdown

### 9.5 quality gate

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_spot_port_quarantine.py -q
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_spot_http_transport.py -q
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_spot_api.py -q
.\backend\.venv\Scripts\python.exe -m ruff check backend
.\backend\.venv\Scripts\python.exe -m mypy
npm test
npm run health
git diff --check
```

## 10. 실제 서버 Check

### 10.1 package gate

- clean source commit
- installer/backend/bundle SHA-256와 file count
- policy version `spot-source-port-quarantine-v2`
- quarantine `75.0s`, pool `768`
- verified rollback installer와 backend SHA-256
- config hash baseline

### 10.2 pre-smoke

- backend 1개, Electron 1개 이상, health 200
- `source_port_enforcement_supported=true`
- `source_port_enforcement_active=true`
- guarded + leased + quarantined + rebind_pending = capacity
- exhaustion, bind retry exhaustion, reuse violation 0
- 기존 request-budget total `<=6/s`

### 10.3 15분 passive smoke

정상 화면을 유지하고 오류를 clear하거나 image load test를 실행하지 않는다.

필수 결과:

```text
total SPOT opens 60s p95 <= 6/s
image upstream 60s p95 <= 0.5/s
connection reduction >= 80%
same 4-tuple reuse under 5s = 0
same 4-tuple reuse under 60s = 0
internal minimum reuse interval >= 75s
pool exhaustion / bind retry exhaustion = 0
SPOT transport failure / ConnectTimeout / HTTP 5xx = 0
temperature / diagnostic / control regression = 0
ping loss / server NIC error-discard = 0
```

관리형 스위치 접근이 없으면 `PARTIAL`을 기록하되 위 제품 gate를 완화하지 않는다.

### 10.4 실패와 rollback

다음 중 하나면 즉시 promotion을 중단한다.

- 60초 미만 동일 4-tuple 재사용 1건 이상
- transport failure, pool exhaustion 또는 reuse violation 1건 이상
- image/temperature/diagnostic/control 회귀
- ConnectTimeout, 5xx, RST 또는 handshake failure
- config drift, backend identity mismatch 또는 health failure

수집을 안전 종료하고 증거 SHA를 보존한 뒤 앱을 정상 종료해 검증된 v1.0.16으로
rollback한다. 오류 큐와 운영 설정은 변경하지 않는다.

120분 canary는 15분 smoke의 모든 hard gate가 통과한 뒤 별도 승인으로만 수행한다.

## 11. 보안과 privacy

- 실제 source port는 transport module 밖으로 반환하지 않는다.
- log/API/CSV/sanitized evidence에 port, IP, MAC, payload, credential을 추가하지
  않는다.
- caller가 URL, local address, source port, quarantine 또는 pool capacity를
  지정하는 API를 만들지 않는다.
- OS registry, firewall, NIC 및 switch 설정을 실행하거나 변경하지 않는다.
- 새 dependency와 shell command 실행이 없다.
- pool 초기화 실패를 silent fallback으로 숨기지 않는다.

## 12. 변경 영향과 rollback

### 12.1 호환성

- endpoint, request/response schema와 config 파일은 하위 호환
- transport exception을 기존 domain exception으로 매핑
- Windows packaged runtime의 SPOT device HTTP implementation만 변경

### 12.2 migration

DB, CSV, config 및 filesystem migration은 없다.

### 12.3 observability

aggregate lifecycle counter가 추가된다. 실제 network identifier는 추가하지 않는다.

### 12.4 operational failure mode

pool이 비정상일 때 SPOT 요청이 fail-closed될 수 있다. 이는 임의 source port
fallback으로 field gate를 조용히 위반하는 것보다 명확하지만 운영 영향이 크므로
pre-smoke와 즉시 rollback gate가 필수다.

### 12.5 rollback

코드 rollback은 feature commit revert, 실제 서버 rollback은 검증된 v1.0.16
installer 재설치다. persistence migration이 없어 data rollback은 없다.
