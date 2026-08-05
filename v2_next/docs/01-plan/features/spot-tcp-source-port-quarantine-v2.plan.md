# spot-tcp-source-port-quarantine-v2 - Plan Document

> Version: 1.2.0 | Date: 2026-07-31 | Status: Current HEAD field revalidation required
> Level: Dynamic | Parent: `spot-request-churn-remediation`
> Operational update (2026-08-05): packaged commit `49fbf6b` reproduced the
> shutdown-closeout QA failure and the server was restored to verified v1.0.16.
> Historical `575e869` field evidence remains valid only for that exact package;
> no later development package is approved or installed on the server.

---

## 1. 개요

### 1.1 목적

Windows 서버에서 SmartFactoryLogger가 생성한 SPOT TCP 연결이 동일 4-tuple을
60초 안에 다시 사용하지 않도록 애플리케이션 계층에서 source-port lifecycle을
결정적으로 관리한다.

기존 request-budget 후보는 전체 신규 연결률을 충분히 낮췄지만 동일 4-tuple
60초 미만 재사용을 제거하지 못했다. 이번 후속 기능은 요청률 제한을 유지하면서
source port의 최소 재사용 간격을 75초로 보장한다.

### 1.2 확정 근거

2026-07-27 실제 서버 15분 smoke 결과는 다음과 같다.

| 항목 | 결과 | 판정 |
|---|---:|---|
| 후보 source commit | `a03bf2c4ef47e31fd18ec1520e37287e0837f3e3` | 확인 |
| 후보 backend SHA-256 | `4F577276D83E80E4AC8512E86929BB3D905013DC30F1CCA8CD93B82259B7F0C4` | 확인 |
| sanitized evidence SHA-256 | `9F57E062D581105C683EE0C4BE37EFAA47DEDA375DD9659361DC36B5112C6CE8` | 확인 |
| 전체 SPOT 신규 연결 60초 p95 | `3.1333/s` | PASS (`<=6/s`) |
| image upstream 60초 p95 | `0.3333/s` | PASS (`<=0.5/s`) |
| baseline 대비 감소 | `91.82%` | PASS (`>=80%`) |
| 동일 4-tuple 5초 미만 재사용 | `0건` | PASS |
| 동일 4-tuple 60초 미만 재사용 | `33건`, 최소 `51.052s` | **FAIL** |
| SPOT handshake/HTTP/body | `2,788/2,788` 성공 | PASS |
| ConnectTimeout, SPOT 5xx, RST | `0건` | PASS |

따라서 “신규 연결률을 6/s 아래로 낮추면 Windows가 같은 source port를 60초
안에 재할당하지 않는다”는 가정은 반증됐다. 요청률 제한만 더 조정하는 방식은
재사용 0건을 보장할 수 없다.

### 1.3 이전 실패 후보와의 경계

폐기된 `spot-tcp-global-lifecycle-remediation` 후보는 source-port quarantine
자체는 동작했지만 custom raw-socket HTTP parser에서 image, temperature,
diagnostic transport failure가 발생해 실제 서버 pre-smoke에서 rollback됐다.

이번 기능은 다음을 금지한다.

- 폐기 브랜치의 `spot_transport.py` import, cherry-pick 또는 코드 복사
- 수동 HTTP request serialization
- 수동 status/header/body/chunked framing parser
- Windows TCP registry, NIC, switch 또는 SPOT 장비 설정 변경

HTTP 생성과 parsing은 Python 표준 라이브러리 `http.client`에만 위임한다.
`HTTPConnection`과 `HTTPSConnection`이 공식 제공하는 `source_address`를 사용해
source port만 명시한다.

## 2. 목표

### 2.1 필수 목표

- [x] 동일 SPOT 4-tuple의 connect start 간격을 최소 `75.0s`로 보장한다.
- [x] image, temperature, internal temperature, diagnostic, focus, actuator의 모든
      공식 SPOT 연결이 동일 lease 정책을 통과한다.
- [x] 기존 `spot-background-request-budget-v2`와
      `spot-image-demand-shaping-v2` 정책을 유지한다.
- [x] HTTP response parsing과 framing은 `http.client`가 담당한다.
- [x] source-port pool 고갈 또는 초기화 실패 시 OS 자동 포트로 우회하지 않는다.
- [x] 실제 port 번호, 4-tuple, IP, URL 및 payload를 제품 diagnostics에 노출하지
      않는다.
- [x] 실제 서버 15분 smoke의 모든 기존 gate와 60초 미만 재사용 0건을 통과한다.

### 2.2 비목표

- SPOT의 HTTP/1.0 close 동작을 keep-alive로 강제 변경하지 않는다.
- 운영 `config.ini`, DB, CSV 또는 image fact schema를 변경하지 않는다.
- Windows dynamic port range나 `TcpTimedWaitDelay`를 변경하지 않는다.
- PLC 입력 오류, host stall 또는 관리형 스위치 원인을 함께 수정하지 않는다.
- stale image를 성공 응답으로 반환하거나 기존 오류를 숨기지 않는다.

## 3. 범위

### 3.1 포함

- Windows 전용 dynamic guard-port lease pool
- 최소 75초 monotonic quarantine
- Python `http.client` 기반 표준 HTTP/1.x transport adapter
- blocking 표준 라이브러리 호출을 격리하는 단일 전용 worker
- 기존 SPOT 요청 종류 전체의 transport adapter 통합
- cancellation, timeout, shutdown 및 pool exhaustion 처리
- allowlisted aggregate diagnostics
- 단위, loopback 통합, 회귀 및 실제 서버 Check

### 3.2 제외

- frontend polling 또는 화면 계약 변경
- 외부 proxy/service 도입
- 새 third-party dependency
- custom raw socket 또는 custom HTTP parser
- source port를 설정·API·query parameter로 입력하는 기능
- 실제 서버 설치, 15분 smoke 및 120분 canary
  - 별도 Check 승인이 있어야 수행한다.

## 4. 기능 요구사항

- **FR-01:** Windows packaged runtime은 시작 시 OS가 할당한 port를 exclusive guard
  socket으로 예약해 bounded pool을 만든다.
- **FR-02:** 기본 pool capacity는 `768`이며 일반 관측성에 실제 port 번호를
  노출하지 않는다.
- **FR-03:** lease를 얻은 요청은 guard를 해제한 뒤 같은 port를
  `HTTPConnection(source_address=("", port))` 또는 HTTPS 동등 경로에 전달한다.
- **FR-04:** request 종료, timeout, HTTP 오류, cancellation 및 parse 오류 모두
  해당 lease를 최소 `75.0s` quarantine으로 이동한다.
- **FR-05:** quarantine 종료 후 같은 port의 guard 재설정이 실패하면 해당 lease를
  available로 반환하지 않고 bounded retry 상태로 유지한다.
- **FR-06:** bind race는 다른 lease로 제한 횟수만큼 재시도하고, 사용했던 lease는
  quarantine한다.
- **FR-07:** pool 고갈, 초기화 실패 또는 bind retry 고갈 시 typed transport
  failure를 반환하며 OS 자동 source port로 fallback하지 않는다.
- **FR-08:** 모든 실제 blocking I/O와 lease release는 전용 worker 내부에서
  완료된다. caller cancellation은 worker나 lease cleanup을 중단하지 않는다.
- **FR-09:** HTTP method, URL, header, body, status, response header/body 및 기존
  오류 분류 계약은 유지한다.
- **FR-10:** 기존 `_spot_device_request_lock`과 request-budget scheduler를
  유지해 SPOT 장비 요청은 전역 직렬화한다.
- **FR-11:** shutdown은 신규 요청을 차단하고, 진행 중 worker를 bounded wait한 뒤
  모든 guard socket을 닫는다.
- **FR-12:** diagnostics에는 policy/support/active, pool 상태별 개수, bind collision,
  exhaustion, rebind retry, 요청 종류별 성공/실패 및 관측된 최소 재사용 간격만
  additive field로 제공한다.
- **FR-13:** diagnostics에 source port, local/remote IP, URL, MAC, payload,
  credential 또는 absolute path를 포함하지 않는다.

## 5. 비기능 요구사항

### 5.1 정확성과 안정성

- quarantine 계산은 `time.monotonic()`만 사용한다.
- 재사용 판정은 connect start 간격 기준이며 경계 `75.0s` 미만을 허용하지 않는다.
- pool state 전이는 `guarded -> leased -> quarantined -> guarded` 순서를 따른다.
- 어느 예외 경로에서도 lease가 available과 active에 동시에 존재하지 않는다.
- loopback HTTP/1.0 server close, Content-Length, chunked, empty body 및 HTTP 오류는
  표준 parser 결과로 검증한다.

### 5.2 성능

- 전체 SPOT 신규 연결 60초 p95 `<=6/s`를 유지한다.
- image upstream 60초 p95 `<=0.5/s`를 유지한다.
- port pool 대기는 정상 15분 smoke에서 `0건`이어야 한다.
- 이벤트 루프에서 blocking socket I/O 또는 `time.sleep()`을 실행하지 않는다.

### 5.3 호환성과 보안

- 기존 FastAPI endpoint와 frontend 응답 계약을 변경하지 않는다.
- 기존 image/temperature/diagnostic/focus/actuator 오류가 동일 public 오류 경계로
  매핑돼야 한다.
- URL은 기존 내부 config에서만 읽으며 caller가 target이나 source port를 주입할
  수 없다.
- 새 dependency, shell 실행, unsafe deserialization 또는 OS 설정 변경이 없다.

## 6. 성공 기준

### 6.1 개발 환경

- [x] lease pool exact-boundary, exhaustion, bind race, delayed rebind 테스트 통과
- [x] HTTP/1.0 close loopback에서 표준 parser와 명시적 source port 검증
- [x] cancellation 후에도 worker 완료와 lease quarantine 검증
- [x] image, temperature, diagnostic 및 PUT control 회귀 테스트 통과
- [x] actual port 번호가 API/log/sanitized diagnostics에 없음
- [x] Ruff, mypy, backend tests, Electron tests 및 `npm run health` 통과
- [x] retired raw transport code가 source/import/diff에 없음

### 6.2 실제 서버 15분 smoke

- [x] candidate/backend/config/package identity 확인
- [x] 전체 SPOT 신규 연결 60초 p95 `<=6/s`
- [x] image upstream 60초 p95 `<=0.5/s`
- [x] baseline 대비 연결 감소 `>=80%`
- [x] 동일 4-tuple 5초 미만 및 60초 미만 재사용 `0건`
- [x] internal minimum reuse interval `>=75.0s`
- [x] pool exhaustion, bind retry exhaustion, transport failure `0건`
- [x] ConnectTimeout, SPOT HTTP 5xx, RST 및 handshake 실패 `0건`
- [x] image/temperature/diagnostic/focus/actuator 회귀 `0건`
- [x] ping loss와 server NIC error/discard `0`

관리형 스위치 자료가 없으면 물리 원인 세분화는 `PARTIAL`로 남을 수 있지만,
제품 promotion gate는 packet과 app 증거로 모두 통과해야 한다.

### 6.3 120분 canary

15분 smoke 통과 후 승인된 120분 canary와 최종 read-only live gate가
`575e869` package identity로 통과했다. 관리형 스위치 증거 부재만
`PHYSICAL_PATH_PARTIAL`로 남는다.

## 7. 위험과 완화

| 위험 | 영향 | 가능성 | 완화 |
|---|---|---|---|
| 표준 transport 전환 회귀 | 높음 | 중간 | 모든 SPOT method/kind loopback contract test |
| worker cancellation 후 orphan I/O | 높음 | 중간 | worker-owned lease와 bounded socket timeout |
| pool exhaustion | 높음 | 낮음 | 768 capacity, 75초 격리, no-fallback, diagnostics |
| guard 해제와 bind 사이 race | 중간 | 중간 | exclusive guard, bounded alternate-lease retry |
| OS socket 상태로 guard 복구 지연 | 중간 | 중간 | unavailable 유지, monotonic retry, exhaustion gate |
| 실제 port 정보 노출 | 높음 | 낮음 | aggregate allowlist와 privacy tests |
| Linux CI 차이 | 중간 | 중간 | platform adapter/fake pool; Windows field gate를 최종 근거로 사용 |

## 8. Rollback과 운영 경계

- 현재 실제 서버는 검증된 v1.0.16 rollback package를 운영한다.
- v1.0.16 rollback installer와 SHA-256은 비상 복구용으로 유지한다.
- adversarial review 후 추가된 CSV pre-write 검증, exact QA CSV binding,
  Electron partial-response 처리, authenticated X-button shutdown, loopback-only
  shutdown control, observation spool health-count cache는 새 product-runtime/QA
  delta이므로 `575e869` field 증거를 상속하지 않는다.
- 후보 설치 전 기존 installer/backend/config SHA-256을 다시 확인한다.
- field gate 하나라도 실패하면 정상 종료 후 검증된 v1.0.16 installer로 복귀한다.
- 오류 큐를 clear하거나 Windows/SPOT/network 설정을 변경하지 않는다.
- 이후 product-runtime 변경은 re-attestation, QA, 15분 smoke, 120분 canary를
  다시 통과해야 한다.

## 9. 일정과 승인

| 단계 | 상태 |
|---|---|
| Plan | 완료 |
| Design | 완료 |
| Do | 완료 |
| Local Check | code candidate 전체 health 및 개발 package native X-close PASS |
| Package/actual server 15분 Check | signed final-commit package 필요 |
| 120분 canary | `575e869` historical PASS, final package 재검증 필요 |

## 10. 참고

- `docs/01-plan/features/spot-request-churn-remediation.plan.md`
- `docs/02-design/features/spot-request-churn-remediation.design.md`
- `docs/03-analysis/spot-request-churn-remediation.analysis.md`
- 폐기 증거 전용:
  `docs/03-analysis/spot-tcp-global-lifecycle-remediation.analysis.md`
- Python 3.12 local runtime 검증:
  `http.client.HTTPConnection(..., source_address=None)` 및
  `HTTPSConnection(..., source_address=None)`
