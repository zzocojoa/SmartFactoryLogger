# spot-request-churn-remediation - Plan Document

> Version: 1.0.0 | Date: 2026-07-24 | Status: Plan and Design complete, Do approval required
> Level: Dynamic
> Branch: `codex/spot-request-churn-remediation`
> Base: `master` / `v1.0.16` / `834ed85`

---

## 1. 개요

### 1.1 목적

SmartFactoryLogger의 정상 운영 화면이 SPOT 장비에 만드는 신규 TCP 연결 수를
안전하게 줄인다. 핵심 수단은 화면 이미지 요청 주기를 기존 설정값에 맞게
정상화하고, 동시에 들어오는 이미지 요청을 백엔드의 단일 upstream 요청과
짧은 수명 cache로 합치는 것이다.

이번 Plan·Design은 현장에서 확정된 `pre-HTTP TCP connect failure`의 재발 가능성을
낮추기 위한 제품 개선 계획이다. SPOT 또는 Windows의 source port를 직접 지정하거나
새 HTTP parser를 만드는 계획이 아니다.

### 1.2 사업 목표

- SPOT 영상, 온도, 진단, focus/actuator 제어를 계속 사용할 수 있어야 한다.
- 간헐적인 SPOT `ConnectTimeout`과 `/api/spot/image.jpg` 502 때문에 운영 화면이
  `조치 필요`로 전환되는 빈도를 실질적으로 0으로 낮춘다.
- 장비가 처리해야 하는 신규 TCP 연결량을 줄여 SPOT TCP stack, Windows 동적 port,
  중간 network path에 걸리는 압력을 동시에 낮춘다.
- Windows registry, NIC, switch, SPOT 설정 변경 없이 애플리케이션 범위에서
  rollback 가능한 개선으로 배포한다.
- 실패했던 이전 제품 후보의 custom raw-socket transport를 재사용하지 않는다.

### 1.3 위험도와 승인 경계

이 작업의 위험도는 **production-critical**이다. 실제 생산 화면과 SPOT 장비 통신
cadence를 변경하며, 잘못 구현하면 영상 정지, 오래된 영상 표시, 온도·진단 지연 또는
제어 요청 starvation이 발생할 수 있다.

현재 승인 범위는 다음과 같다.

- 완료 승인: 새 브랜치 생성, 현장 근거 정리, Plan, Design
- 미승인: 제품 source 수정, installer 생성, 실제 서버 설치, canary, master 병합

Do는 Plan·Design 완료 뒤 사용자의 별도 명시적 승인을 받아야 한다.

## 2. 확정 근거와 문제 정의

### 2.1 최종 현장 증거

2026-07-24 실제 서버에서 rollback v1.0.16
`F1A65AC7E2C27FC049398EA0AF2A6DAA775A081DE0311E42A3EAA87CE4A15A54`
를 정상 화면으로 운영하면서 신규 `spot_image ConnectTimeout`을 자동 포착했다.
공식 공유 ZIP SHA-256은
`2D73AA9164C43EB8BEECA905CFE4C8C8CA86CCA7372989D17567A26DC426D213`
이며 private manifest 391개 파일과 공유본 13개 파일의 누락·크기·hash 불일치는
모두 0건이었다.

| 근거 | 결과 | 의미 |
|---|---:|---|
| 관측 구간 | 약 1,283초 | 신규 오류와 75초 이상 복구 구간 포함 |
| TCP 연결 시도 | 48,340건, 평균 37.674/s | 정상 화면 자체가 높은 신규 연결량을 생성 |
| handshake 성공/실패 | 48,331 / 9 | 장애는 일부 연결에 선택적으로 발생 |
| 정상 HTTP 응답 | 48,330건 | 대부분의 장비 응답은 정상 |
| 응답 framing | 전부 HTTP/1.0, Content-Length 있음, body 완료, server FIN | HTTP parser/framing은 이번 원인에서 제외 |
| 직접 실패 | initial SYN 9건에 SYN-ACK 없음 | HTTP 전 TCP connect 단계 실패 |
| 앱 오류 | image ConnectTimeout 2,031ms 및 4,015ms | packet 사건과 앱 502가 시간상 일치 |
| 정상 복구 | 마지막 실패 뒤 HTTP 200, 후속 정상 응답 2,322건 | 약 8.6초의 일시적 장애 |
| 동일 4-tuple 재사용 | 33,401건 | 높은 연결 churn과 함께 반복 |
| 최소 재사용 간격 | 약 827.8ms | 매우 빠른 재사용이 실제 존재 |
| 60초 미만 재사용 | 5,172건, 15.485% | 위험 노출이 예외가 아닌 지속 상태 |
| Windows TCP | active open +50,190, failed attempt +10, RST sent +11 | SPOT packet과 같은 방향의 보조 근거 |
| ping | 1,098/1,098 성공, 사건 주변 70/70 성공 | 일반 IP reachability 단절은 아님 |
| 서버 NIC | error/discard 0 | 서버 NIC 오류 근거 없음 |

직접 원인은 **SPOT 대상 initial SYN에 응답이 오지 않은 pre-HTTP TCP connect
failure**로 확정한다. 높은 연결 churn과 빠른 4-tuple 재사용은 유력한 기여
메커니즘이지만, privacy를 지킨 aggregate 통계만으로 실패 flow와 재사용 flow를
1:1 결합할 수 없으므로 단독 원인으로 확정하지 않는다.

관리형 switch 및 SPOT 장비 내부 로그가 없어 최종 물리 행위자가 SPOT TCP stack인지
switch/network path인지 구분할 수 없다. 이 물리 한계는 제품 개선을 막지는 않지만,
개선 뒤 같은 오류가 재발하면 원인 세분화의 제한으로 남는다.

### 2.2 v1.0.16 코드에서 확인된 생성 원인

현재 구조는 다음과 같다.

1. frontend `useSpotViewModel`이 이미지 응답을 Blob으로 표시한다.
2. 이미지 `onLoad`가 성공하면 `runSpotFetch("completed")`를 즉시 다시 호출한다.
3. `/api/spot/config`의 `refresh_interval`은 비교·표시되지만 다음 이미지 요청
   scheduling에는 사용되지 않는다.
4. backend `_img_fetch_lock`과 `_spot_device_request_lock`은 동시 실행을 하나로
   제한하지만, 빠른 요청을 시간 기준으로 줄이지는 않는다.
5. SPOT은 매 응답을 HTTP/1.0 + server FIN으로 끝내므로 `httpx.AsyncClient`를
   재사용해도 실질적인 keep-alive 연결 재사용을 기대할 수 없다.
6. dashboard와 settings 또는 복수 client가 각각 이미지를 요청하면 backend가
   이를 같은 frame 요청으로 합치지 않는다.

즉, 현재 문제는 단순한 “동시성 과다”가 아니라 **성공 완료 즉시 다음 요청을 만드는
completion-driven loop와 짧은 연결의 반복 생성**이다.

### 2.3 이전 후보에서 배운 제한

#### 이미지 cadence 후보

`codex/spot-tcp-connection-reuse-remediation`은 image upstream을 최대 5/s로
제한했지만 실제 60분 canary에서 실패했고 병합되지 않았다. 이 후보는 frontend의
즉시 재요청 원인을 그대로 둔 채 backend에서 각 요청을 지연했으며, 모든 SPOT
연결 종류를 충분히 줄이지 못했다.

#### 전역 source-port 후보

`codex/spot-tcp-global-lifecycle-remediation`은 custom raw-socket transport,
source-port pool과 60초 quarantine을 도입했다. 로컬 시험은 통과했지만 실제 서버
pre-smoke에서 image 12건, temperature 7건, diagnostic 7건의 transport failure가
발생해 즉시 rollback됐다.

따라서 새 개선은 다음 금지선을 지킨다.

- 이전 실패 브랜치를 merge하거나 새 브랜치의 base로 사용하지 않는다.
- custom raw socket, 수동 HTTP framing/parser, source-port bind/pool/quarantine을
  제품 코드에 넣지 않는다.
- 실패했던 cadence 구현을 그대로 복사하지 않는다.
- Windows TCP registry나 동적 port 범위를 변경하지 않는다.

## 3. 목표와 우선순위

### 3.1 P0 필수 목표

- [ ] **P0-01:** frontend 이미지 성공 완료 후 즉시 재요청을 제거하고
  `SPOT_REFRESH_INTERVAL`에 맞춰 다음 요청을 예약한다.
- [ ] **P0-02:** backend에서 같은 freshness window 안의 복수 이미지 요청을
  한 번의 upstream `/image.jpg` 요청으로 합친다.
- [ ] **P0-03:** 성공한 최신 JPEG를 bounded in-memory cache로 보관하고,
  freshness window 안에서만 downstream caller에게 공유한다.
- [ ] **P0-04:** cache가 만료된 상태에서 동시에 들어온 caller는 하나의
  single-flight refresh 결과만 기다리며 새 TCP 연결을 각각 만들지 않는다.
- [ ] **P0-05:** stale frame을 현재 영상처럼 HTTP 200으로 반환하지 않는다.
  만료 뒤 refresh가 실패하면 기존 502 오류 계약을 유지한다.
- [ ] **P0-06:** 기존 `httpx.AsyncClient`, response validation, timeout,
  `_spot_device_request_lock`을 유지하고 custom transport를 만들지 않는다.
- [ ] **P0-07:** image 개선이 temperature, diagnostics, focus, actuator 요청을
  굶기거나 의미를 바꾸지 않아야 한다.
- [ ] **P0-08:** 신규 TCP 연결률, upstream image 요청률, downstream 요청률,
  cache hit, coalesced waiter, cache age와 failure를 구분해서 관측한다.
- [ ] **P0-09:** DB, CSV, config migration 없이 기존 installer로 즉시 rollback할
  수 있어야 한다.

### 3.2 P1 검증 목표

- [ ] **P1-01:** HTTP/1.0 close 모의 SPOT에서 다중 caller가 있어도 upstream image
  시작률이 설정 주기를 넘지 않는지 자동 검증한다.
- [ ] **P1-02:** cache hit, cache expiry, concurrent miss, refresh failure,
  cancellation, shutdown을 deterministic test로 검증한다.
- [ ] **P1-03:** frontend timer가 initial, success, failure retry, manual retry,
  visibility/unmount lifecycle에서 중복 실행되지 않는지 검증한다.
- [ ] **P1-04:** 실제 서버 15분 smoke 후 120분 event-trigger canary를 수행하고
  TCP, 앱, ping, NIC와 가능하면 switch counter를 같은 시각 기준으로 판정한다.
- [ ] **P1-05:** field gate가 실패하면 증거를 보존하고 검증된 v1.0.16 installer로
  rollback한다.

### 3.3 P2 후속 목표

- [ ] **P2-01:** 개선 후에도 aggregate SPOT 연결률이 높으면 diagnostic 8개 parameter
  fan-out을 장비가 공식 지원하는 단일 endpoint로 합칠 수 있는지 별도 조사한다.
- [ ] **P2-02:** 관리형 switch 접근권이 확보되면 서버·SPOT port의 link/CRC/error/
  discard 시작·종료 자료를 canary evidence에 추가한다.

P2는 이번 Do의 자동 포함 범위가 아니다. P0/P1 결과가 필요성을 증명할 때 별도
Plan·승인을 거친다.

## 4. 기능 요구사항

### 4.1 frontend cadence

- **FR-01:** 최초 화면 진입은 image URL이 있으면 즉시 한 번 요청해야 한다.
- **FR-02:** 정상 이미지 표시가 완료되면 즉시 다음 요청을 시작하지 않고,
  유효한 `refresh_interval` 초 뒤 다음 요청을 시작해야 한다.
- **FR-03:** `refresh_interval`이 비정상 값이면 기존 backend 기본값과 일치하는
  안전한 기본값을 사용하고 tight loop로 fallback하지 않아야 한다.
- **FR-04:** 다음 정상 fetch timer는 instance당 최대 하나만 존재해야 한다.
- **FR-05:** hidden/unmounted 화면은 정상 fetch timer를 해제하고 background
  image churn을 만들지 않아야 한다.
- **FR-06:** 기존 자동 오류 재시도 `500/1000/2000ms`와 정상 refresh timer는
  동시에 실행되지 않아야 한다.
- **FR-07:** manual retry는 중복 in-flight를 만들지 않아야 하며 backend freshness
  정책을 우회하는 강제 upstream 파라미터를 보내지 않아야 한다.
- **FR-08:** image Blob URL revoke, 마지막 정상 frame 유지, payload validation과
  기존 오류 표시 계약을 유지해야 한다.

### 4.2 backend cache와 single-flight

- **FR-09:** cache는 유효한 JPEG bytes, upstream captured epoch, captured monotonic,
  upstream latency와 freshness 정보를 bounded process memory에만 저장해야 한다.
- **FR-10:** freshness 판단은 system clock 변경의 영향을 받지 않는 monotonic
  elapsed time을 사용해야 한다.
- **FR-11:** freshness window는 기존 `SPOT_REFRESH_INTERVAL`을 사용하되,
  tight-loop 오설정을 막는 내부 최소값과 과도한 stale 허용을 막는 최대값을 적용해야 한다.
- **FR-12:** fresh cache hit는 새 SPOT 요청 없이 동일 bytes와 원래 captured time을
  반환해야 한다.
- **FR-13:** expired/missing cache에서 첫 caller만 upstream refresh를 수행하고
  나머지는 동일 single-flight 결과를 기다려야 한다.
- **FR-14:** single-flight 성공 결과는 waiter 모두에게 전달하되 이미지 capture
  writer에는 upstream 성공 한 번만 enqueue해야 한다.
- **FR-15:** single-flight 실패는 waiter 모두에게 기존 `SpotImageFetchError` 의미로
  전달하고 실패를 성공 cache로 바꾸지 않아야 한다.
- **FR-16:** expired cache는 refresh 실패 시 보관할 수 있으나 downstream HTTP 200
  fallback에 사용해서는 안 된다.
- **FR-17:** caller 취소가 공유 upstream 작업을 임의로 취소해 다른 caller 결과를
  깨뜨리지 않아야 하며, 앱 shutdown은 남은 task를 bounded하게 정리해야 한다.
- **FR-18:** 기존 image/temperature/diagnostics/control 공용 장비 잠금 순서에
  역순 잠금을 추가하지 않아야 한다.

### 4.3 API와 관측성

- **FR-19:** `/api/spot/image.jpg`의 method, status, `image/jpeg`, payload validation,
  cache-control 및 기존 오류 detail 계약을 유지해야 한다.
- **FR-20:** `X-Spot-Image-Source`는 실제 upstream 응답과 fresh cache 응답을
  구분해야 한다.
- **FR-21:** 응답은 원래 capture 시각과 현재 cache age를 구분 가능한 additive
  header/metadata로 제공해야 한다.
- **FR-22:** `/api/spot/config.image` 또는 기존 SPOT diagnostics에 다음 process-local
  누계를 additive로 제공해야 한다.
  - downstream image request
  - upstream image request
  - fresh cache hit
  - single-flight leader/waiter
  - cache age/TTL/last refresh
  - refresh success/failure
- **FR-23:** 진단값에 SPOT IP, source port, MAC, packet payload, credential 또는
  사용자 절대 경로를 노출하지 않아야 한다.
- **FR-24:** 기존 error queue에는 실제 upstream failure만 기록하고 fresh cache hit를
  오류나 upstream 성공으로 중복 집계하지 않아야 한다.

## 5. 비기능 요구사항

### 5.1 성능

- **NFR-01:** 기본 `refresh_interval=3s`에서 image upstream 시작률의 60초 p95는
  `0.5/s` 이하여야 한다.
- **NFR-02:** 정상 화면의 전체 SPOT 신규 TCP 연결률 60초 p95는 `6/s` 이하이고,
  현장 baseline `37.674/s`보다 최소 80% 감소해야 한다.
- **NFR-03:** fresh cache hit의 backend 처리 p95는 개발 모의 환경에서 50ms
  이하여야 하며 네트워크 호출을 만들지 않아야 한다.
- **NFR-04:** cache는 JPEG 한 장과 상수 크기 metadata만 보유해야 한다.
- **NFR-05:** event loop에서 blocking sleep, blocking socket I/O 또는 busy loop를
  추가하지 않아야 한다.

### 5.2 안정성과 호환성

- **NFR-06:** existing config.ini의 `refreshinterval` 의미를 복구해 사용하되
  새 필수 설정이나 자동 migration을 만들지 않아야 한다.
- **NFR-07:** DB/CSV schema, stored image fact schema와 운영 데이터의 migration은
  없어야 한다.
- **NFR-08:** EX·LS 통신, CSV queue/drop/lag, memory, browser error에 신규 회귀가
  없어야 한다.
- **NFR-09:** focus/actuator 요청은 image cache와 무관하게 기존 공식 endpoint를
  사용하고 기능 성공/실패 의미를 유지해야 한다.
- **NFR-10:** 온도와 진단 freshness 및 poll interval 계약을 변경하지 않아야 한다.
- **NFR-11:** 이전 frontend가 새 backend에 요청하거나 새 frontend가 v1.0.16
  backend에 요청해도 기존 필수 응답 필드 수준에서 동작해야 한다.

### 5.3 보안

- **NFR-12:** 외부 caller가 query parameter로 upstream URL, TTL, force-refresh,
  source port를 주입할 수 없어야 한다.
- **NFR-13:** cache bytes는 process memory와 기존 image capture 정책 밖에 새로
  영속 저장하지 않아야 한다.
- **NFR-14:** raw socket, unsafe deserialization, shell 실행, Windows network
  policy 변경을 제품 경로에 추가하지 않아야 한다.

## 6. 범위

### 6.1 포함

- frontend 정상 image refresh scheduling
- backend bounded fresh image cache
- backend concurrent image single-flight
- 실제 source를 나타내는 additive response metadata
- SPOT image churn 진단 counter
- backend/frontend 단위·통합·회귀 테스트
- HTTP/1.0 close 다중 caller 부하 시험
- clean build, package identity, 15분 smoke, 120분 canary와 rollback gate

### 6.2 제외

- PLC `diagnostics_age_ms=''` 자료형 오류
- EX·LS 자체 로직
- custom raw-socket transport와 수동 HTTP parser
- explicit source-port bind, pool 또는 quarantine
- Windows registry, TCP stack, firewall, NIC, switch, SPOT firmware/설정 변경
- stale-while-error 이미지 반환
- MJPEG, WebSocket, streaming 또는 새 device endpoint
- diagnostic 8개 request를 비공식 방식으로 합치는 작업
- 수집기 재설계
- 관리형 switch 접근권 확보 자체

## 7. 성공 기준과 배포 Gate

### 7.1 개발 환경

- [ ] Plan의 모든 P0/FR/NFR이 Design test case로 추적된다.
- [ ] backend focused test와 전체 unittest가 통과한다.
- [ ] frontend cadence, lifecycle, auto-retry, Blob tests가 통과한다.
- [ ] frontend typecheck와 lint가 통과한다.
- [ ] Ruff, mypy와 repository `npm run health`가 통과한다.
- [ ] HTTP/1.0 close 모의 장비에서 복수 caller가 한 freshness window당 upstream
  1건만 만든다.
- [ ] cache TTL 경계, 동시 miss, failure, cancellation, shutdown test가 통과한다.
- [ ] `git diff --check`, secret/internal address scan, clean build provenance가 통과한다.

### 7.2 실제 서버 15분 smoke

- [ ] 검증 대상 backend SHA-256과 rollback installer SHA-256을 설치 전 확인한다.
- [ ] 앱 정상 화면에서 EX·LS·SPOT·CSV·memory 기본 상태가 유지된다.
- [ ] image upstream 60초 p95 `<=0.5/s`.
- [ ] 전체 SPOT 신규 TCP 연결 60초 p95 `<=6/s`.
- [ ] baseline 대비 신규 연결률 감소 `>=80%`.
- [ ] 동일 4-tuple 5초 미만 및 60초 미만 재사용 `0건`.
- [ ] SYN 무응답, RST 이상, retransmission 기반 failure `0건`.
- [ ] SPOT image 5xx/ConnectTimeout `0건`.
- [ ] temperature/diagnostic/control 신규 failure `0건`.
- [ ] ping loss, 서버 NIC error/discard 증가 `0건`.
- [ ] 설정 주기에 맞는 영상 갱신이 지속되고 freeze가 없다.

### 7.3 실제 서버 120분 canary

15분 smoke가 모두 통과한 동일 package만 120분 canary로 진행한다.

- [ ] 15분의 모든 gate를 120분 연속 구간에서도 유지한다.
- [ ] error queue의 기존 baseline과 신규 오류를 분리하며 신규 SPOT 오류가 없다.
- [ ] CSV drop 0, queue 정상 복귀, lag 정상 범위다.
- [ ] backend process/PID lifecycle, port 8000, memory가 안정적이다.
- [ ] frontend browser error와 image retry storm이 없다.
- [ ] 관리형 switch 자료를 확보할 수 있으면 link/CRC/error/discard 증가 0을 확인한다.

switch 자료가 계속 없더라도 제품 후보의 TCP/앱 gate는 판정할 수 있다. 그러나
ConnectTimeout이 한 건이라도 재발하면 물리 원인은 더 세분화하지 못하더라도 후보는
실패로 판정하고 rollback한다.

### 7.4 즉시 실패 및 rollback 조건

다음 중 하나라도 발생하면 promotion하지 않는다.

- 신규 SPOT ConnectTimeout, image 5xx 또는 upstream failure
- image upstream 또는 전체 SPOT 연결률 gate 초과
- 빠른 동일 4-tuple 재사용 재현
- 영상 freeze, 설정 주기보다 지속적으로 빠른 요청 또는 stale 200 반환
- temperature/diagnostic/focus/actuator 회귀
- EX·LS, CSV, memory 또는 browser 신규 회귀
- package/backend identity 불일치
- field collector 무결성 또는 packet 방향 preflight 실패

롤백은 검증된 v1.0.16 installer로 복귀하고 backend SHA-256, EX·LS·SPOT·HTTP·CSV·
memory 상태를 다시 확인하는 방식이다. DB/CSV/config migration이 없으므로 data
downgrade는 필요 없다.

## 8. 일정과 승인 Gate

| 단계 | 산출물 | 상태 |
|---|---|---|
| Plan | 근거, 목표, 범위, 요구사항, 성공/rollback 기준 | Complete |
| Design | timer/cache/single-flight/lifecycle/API/test 상세 설계 | Complete |
| Do | 최소 제품 패치와 자동 테스트 | 별도 승인 전 Pending |
| Check | local health, clean package, 15분 smoke, 120분 canary | Pending |
| Act | 실패 gap 수정 또는 rollback/폐기 결정 | Pending |
| Report | 최종 판정과 잔여 물리 한계 기록 | Pending |

## 9. 위험과 완화

| 위험 | 영향 | 가능성 | 완화 |
|---|---|---|---|
| 영상 갱신이 기존보다 느리게 보임 | 중간 | 높음 | 이미 존재하는 3초 설정값을 UI에 적용하고 현장 사용성 확인 |
| cache가 오래된 영상을 정상으로 위장 | 높음 | 중간 | monotonic TTL, 만료 후 stale 200 금지, source/age metadata |
| 복수 caller가 cache miss에서 연결을 각각 생성 | 높음 | 중간 | backend single-flight와 다중 caller test |
| waiter 취소가 공유 refresh를 취소 | 높음 | 중간 | caller lifecycle과 shared task ownership을 분리 |
| frontend 정상 timer와 오류 retry가 겹침 | 높음 | 중간 | timer 단일 소유권과 fake timer test |
| image lock/device lock deadlock | 높음 | 낮음 | 잠금 순서 고정, cache lock에 network await 금지, concurrency test |
| control 요청 starvation | 높음 | 낮음 | image refresh 빈도 감소, 공용 lock 계약 유지, control latency test |
| image를 줄여도 diagnostics fan-out이 높음 | 중간 | 중간 | 전체 연결률 계측; 필요 시 P2 별도 PDCA |
| 실제 원인이 switch/SPOT 내부라 재발 | 높음 | 중간 | 15분→120분 gate, 재발 즉시 rollback, switch 한계 명시 |
| 이전 실패 transport가 다시 섞임 | 높음 | 낮음 | clean master base, prohibited-components review |
| config가 비정상 값 | 높음 | 낮음 | bounded normalization과 tight-loop 금지 test |
| rollback package가 혼동됨 | 높음 | 낮음 | installer/backend SHA-256과 build provenance 강제 |

## 10. 대안 평가

| 대안 | 결정 | 이유 |
|---|---|---|
| frontend timer만 수정 | 단독 채택 안 함 | 복수 client와 이전 frontend가 backend churn을 다시 만들 수 있음 |
| backend 200ms cadence만 적용 | 재사용 안 함 | 이전 field canary 실패, 불필요한 downstream 대기를 매번 upstream으로 전달 |
| backend fresh cache + single-flight | 채택 | caller 수와 무관하게 장비 요청을 freshness window당 1건으로 제한 |
| custom raw-socket/source-port pool | 금지 | 실제 서버 pre-smoke에서 다종 SPOT request failure 발생 |
| HTTP keep-alive 강제 | 제외 | 장비가 HTTP/1.0과 server FIN으로 연결 종료 |
| Windows port/TIME_WAIT 조정 | 제외 | 서버 전체 영향이 크고 제품 churn 원인을 숨김 |
| stale-while-error | 제외 | 현장 현재 영상처럼 오래된 frame을 표시할 안전 위험 |
| diagnostics 즉시 통합 | P2 보류 | 공식 single endpoint 지원과 field 의미 검증이 선행되어야 함 |

## 11. 운영 및 관측성 원칙

- downstream UI 요청 수와 실제 SPOT upstream 연결 수를 반드시 분리한다.
- cache hit는 upstream 성공으로 중복 계산하지 않는다.
- source는 `upstream`과 `cache`를 구분하고 captured time과 age를 함께 본다.
- process restart 시 counter와 cache가 초기화되는 in-memory 상태임을 명시한다.
- source port 번호, raw payload, 내부 IP는 일반 관측성에 기록하지 않는다.
- 실제 서버 수집은 정상 화면을 유지하고 탭 추가, 반복 refresh, image load test를
  하지 않는 passive 방식으로 수행한다.
- 관리형 switch 자료가 없으면 `PARTIAL physical attribution`을 기록하되 이를
  제품 실패를 정상으로 바꾸는 근거로 사용하지 않는다.

## 12. 참고 자료

- `docs/03-analysis/spot-transport-failure-diagnostics.analysis.md`
  - 진단 브랜치 `codex/spot-transport-failure-diagnostics`, commit `0d0ef9e`
- `docs/01-plan/features/spot-tcp-connection-reuse-remediation.plan.md`
  - 실패 근거 보존 브랜치 전용, merge 금지
- `docs/03-analysis/spot-tcp-global-lifecycle-remediation.analysis.md`
  - 폐기된 custom transport의 실제 서버 실패 근거
- `backend/FacilityData/drivers/spot_api.py`
- `backend/app.py`
- `frontend/src/domains/FacilityData/hooks/useSpotViewModel.ts`
- `frontend/src/domains/FacilityData/hooks/useSpotViewModelEffects.ts`
- `frontend/src/domains/FacilityData/hooks/useSpotViewModel.service.ts`

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 1.0.0 | 2026-07-24 | 최종 trigger evidence와 v1.0.16 코드 구조 기반 신규 연결 churn 개선 계획 | Codex |
