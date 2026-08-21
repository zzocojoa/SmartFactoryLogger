# spot-tcp-connection-reuse-remediation - Plan Document

> Version: 1.2.0 | Date: 2026-08-21 | Status: Historical failed candidate, superseded
> Level: Dynamic | Do authorization: Granted 2026-07-20

> **Historical snapshot.** 이 문서는 `bfd9be7`의 실패한 1차 cadence 후보와 당시
> rollback 결정을 보존한다. 현재 구현·운영 기준은
> `docs/04-report/spot-tcp-source-port-quarantine-v2.report.md`와
> `docs/03-analysis/spot-request-churn-remediation.analysis.md`를 따른다.

---

## 1. 개요

### 1.1 목적

SmartFactoryLogger가 SPOT의 공식 이미지 자원 `GET /image.jpg`를 너무 빠르게
반복 호출하여 짧은 TCP 연결과 로컬 source port를 과도하게 소비하는 문제를
완화한다. 목표는 SPOT 이미지의 정상 표시와 기존 API 계약을 유지하면서,
현장에서 확인된 TCP 4-tuple 조기 재사용 충돌과 그 결과인
`ConnectTimeout`을 재발하지 않게 하는 것이다.

Plan과 Design 승인 후 2026-07-20 로직 패치가 별도로 승인되어 로컬 소스와
테스트를 구현했다. 설치 패키지, 실제 서버 PC, SPOT 및 네트워크 장비는 아직
변경하지 않았다.

### 1.2 사업 및 운영 목표

- 운영 화면에서 SPOT 영상이 계속 표시되어야 한다.
- 간헐적인 SPOT `ConnectTimeout` 때문에 운영/관측성 화면이
  `조치 필요`로 전환되는 빈도를 제거하거나 실질적으로 0에 가깝게 낮춘다.
- 운영자가 Windows TCP 레지스트리, NIC, 스위치 또는 SPOT 장비 설정을
  임의로 조정하지 않아도 애플리케이션 수준에서 연결 생성 압력을 낮춘다.
- EX, LS, SPOT 온도/진단/제어, CSV 저장, 메모리 관측성에는 회귀가 없어야 한다.

### 1.3 확정된 현장 근거

2026-07-20 실제 서버 수집 자료에서 다음이 확인되었다.

| 근거 | 현장 결과 | 해석 |
|---|---:|---|
| SPOT 이미지 API 요청률 | 평균 약 `30.659 req/s` | 화면의 성공 완료가 즉시 다음 요청을 생성함 |
| SPOT 대상 고유 TCP SYN | 25분간 `64,862`, 평균 `42.757/s` | 이미지 외 온도/진단 요청까지 포함해 짧은 연결이 매우 많음 |
| 서로 다른 local source port | `16,238`개 | Windows 기본 동적 포트 범위와 유사한 규모를 빠르게 순환함 |
| local port 재사용 | `48,624`회 | 같은 포트를 반복 사용함 |
| SPOT HTTP 응답 | `HTTP/1.0`, keep-alive 0건 | 매 응답 후 TCP 연결이 종료되어 연결 풀로 재사용할 수 없음 |
| 08:33 실패 연결 | SYN 대신 이전 연결의 ACK 수신, PC RST, 재시도 후 2.016초 timeout | 같은 4-tuple의 조기 재사용 충돌을 패킷 순서로 직접 확인함 |
| ping / 서버 NIC | ping 손실 0, NIC error/discard 증가 0 | 서버 NIC·케이블·일반 네트워크 단절이 주원인은 아님 |

정상 연결이 종료된 지 35ms 후 같은 4-tuple이 재사용되었고, SPOT은 새
SYN에 SYN-ACK가 아닌 이전 연결의 plain ACK를 반환했다. 서버 PC는 이를
현재 연결에 맞지 않는 응답으로 판단하여 RST를 보냈으며, 최종적으로
`ConnectTimeout`이 발생했다.

### 1.4 원인 범위의 분리

이 계획은 다음 세 사건을 하나로 합치지 않는다.

1. **이번 개선 대상:** 고빈도 SPOT 이미지 요청과 짧은 `HTTP/1.0` 연결로
   인한 TCP 4-tuple/source-port 재사용 충돌.
2. **별도 PLC 문제:** `plc_driver`의 `diagnostics_age_ms=''` 실수 변환 오류.
   EX·LS 통신 장애가 아니라 시작 시점 입력 정규화 문제이며 별도 PDCA가 필요하다.
3. **별도 서버 정체:** 08:10의 약 4.8초 SPOT packet 공백, Extruder timeout,
   ping 프로세스 지연이 겹친 host-side stall. CPU, 디스크, 프로세스 스케줄링,
   event-loop lag를 추가 수집하는 별도 PDCA가 필요하다.

따라서 이번 변경이 완료되어도 PLC 입력 오류와 08:10 서버 정체까지 해결됐다고
판정해서는 안 된다.

### 1.5 2026-07-21 현장 Check 결과

커밋 `bfd9be785f7a87aa4150445945861a54bca98f33` 기반 package를 실제 서버에
설치하고 정상 화면에서 수집했다. 이미지 cadence는 모든 720개 app 표본에서
`200ms`로 확인됐고 이미지 요청률은 p95 `4.683/s`, 최대 `4.783/s`로 목표를
충족했다. 그러나 mandatory gate는 다음 이유로 실패했다.

| 근거 | 현장 결과 | 판정 |
|---|---:|---|
| SPOT image ConnectTimeout/502 | 필수 60분 3회, 전체 수집 구간 5회 | 실패 |
| 동일 4-tuple 60초 미만 재사용 | 필수 60분 최소 731회, 전체 3,026회 | 실패 |
| old ACK → PC RST | 전체 연장 구간 6회 | 실패 |
| 직접 상관관계 | 11:00과 11:20 충돌 직후 약 2초 ConnectTimeout/502 | 기존 메커니즘 재확인 |
| SPOT 온도 | 09:19 image 오류와 temperature timeout 동시 | image-only 범위 부족 |
| EX·LS / CSV / memory | 신규 회귀 없음 | 통과 |

11:00과 11:20에는 이전 image 연결 직후 약 `219ms`, `232ms` 만에 같은
4-tuple이 재사용됐다. SPOT은 새 SYN에 이전 연결의 plain ACK를 반환했고 서버는
RST로 응답했으며, 같은 SYN 재전송도 충돌한 뒤 `ConnectTimeout`이 발생했다.
따라서 `200ms` image cadence가 적용됐다는 사실과 TCP 충돌 제거는 동치가 아니다.

초기 PCAP은 수집 시작부터 09:32:43까지 SPOT→서버 패킷이 누락됐다. 이후 구간은
양방향 packet과 app 오류가 직접 일치했지만, 다음 수집부터는 본 관찰 전에
양방향 capture 자체를 자동 검증해야 한다.

## 2. 목표

### 2.1 주요 목표

- [x] 모든 백엔드 SPOT 이미지 upstream 호출에 공통으로 적용되는 최소 간격을 둔다.
- [x] 첫 단계 기본값은 직전 이미지 upstream 시도 완료 후 다음 시도 시작까지
      최소 `200ms`로 하여 이미지 연결 생성률을 최대 `5회/초` 이하로 제한한다.
- [x] 현장 평균 이미지 요청률을 기존 약 `30.659/s`에서 최대 `5/s` 이하로 낮춰
      최소 약 83% 줄인다.
- [x] 이미지 cadence 대기 중에는 SPOT 장비 공용 잠금을 점유하지 않아
      온도, 진단, focus 및 actuator 요청의 실행 기회를 보장한다.
- [x] 기존 공식 자원 `/image.jpg`, 백엔드 API `/api/spot/image.jpg`, JPEG 검증,
      오류 상태, 화면 단일 요청 소유권 및 제한된 자동 재시도를 유지한다.
- [x] cadence 적용 여부와 실제 대기량을 운영 진단에서 확인할 수 있게 한다.
- [ ] 개발 환경 자동 테스트와 실제 서버 정상 운전 검증을 모두 통과한 경우에만
      완료로 판정한다.
- [ ] 이미지뿐 아니라 온도·진단·제어를 포함한 전체 SPOT connection source를
      계측하고, image cadence와 별개인 총 연결 생성 압력을 통제할 2차 설계를 확정한다.
- [ ] 단순 지연값 증가가 아니라 local source port 재사용을 방지하거나 충돌을
      사용자 502로 노출하지 않는 transport 전략을 실증한 뒤 구현 여부를 결정한다.

### 2.2 비목표

- PLC `diagnostics_age_ms=''` 오류를 수정하지 않는다.
- 08:10 host-side stall의 하위 원인을 수정하지 않는다.
- Windows 동적 포트 범위, `TIME_WAIT`, TCP 레지스트리, NIC offload 설정을 바꾸지 않는다.
- SPOT 펌웨어, SPOT 네트워크 설정 또는 스위치 설정을 바꾸지 않는다.
- SPOT이 닫은 `HTTP/1.0` 연결을 강제로 keep-alive로 전환하지 않는다.
- `/image.ssi`, `/newjpeg.jpg`, MJPEG, WebSocket 또는 별도 proxy 경로를 도입하지 않는다.
- stale/current 이미지 cache를 추가하거나 실패를 과거 프레임의 HTTP 200으로 숨기지 않는다.
- 정상 화면의 프런트엔드 상태 머신이나 실패 재시도 횟수 `500/1000/2000ms`를
  이번 1차 변경에서 재설계하지 않는다.

## 3. 범위

### 3.1 포함

- 백엔드 이미지 upstream 호출 직전의 전역 cadence gate.
- 단조 증가 시계(monotonic clock)에 기반한 간격 계산.
- cadence 대기와 upstream 네트워크 지연의 구분.
- additive 방식의 SPOT 이미지 cadence 진단 필드.
- 동시 호출, 실패, 취소, 공용 장비 잠금과의 상호작용에 대한 자동 테스트.
- HTTP/1.0 응답 후 연결을 닫는 로컬 모의 장비 부하 검증.
- 실제 서버에서 정상 화면을 사용한 단계적 배포, 패킷/관측성 검증 및 롤백 기준.

### 3.2 제외

- 프런트엔드 화면, store, hook, 사용자 설정 UI 변경.
- 데이터베이스, CSV, 메모리 snapshot, 관측성 export의 기존 schema 변경.
- SPOT 이미지 자체 저장 주기인 `SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC` 변경.
- SPOT 온도/진단 주기인 `SPOT_REFRESH_INTERVAL`을 이미지 frame 속도 제어에 재사용.
- 운영자가 변경할 수 있는 새 config.ini 항목이나 환경 변수의 1차 도입.
- PLC 및 host-side stall 조사/패치.

### 3.3 Act iteration 2 포함

- 실패 canary의 app/TCP/ping/NIC/CSV/memory 증거를 Plan·Design·Analysis에 반영.
- 전체 SPOT 요청원별 연결률과 freshness/latency 계약을 다시 정의.
- source-port quarantine, 장기 연결 endpoint, 진단 fan-out 축소 및 제한적 내부
  recovery 대안을 코드 변경 전에 비교 실증.
- pktmon 본 수집 전 30초 이내에 SPOT TCP 송신·수신을 모두 확인하는 passive
  preflight와 manifest 진단.
- 실패한 canary package의 rollback 절차와 검증 항목 재확정.

### 3.4 Act iteration 2 제외

- 대안 실증과 갱신된 Design 승인 전 추가 SPOT 애플리케이션 로직 패치.
- `200ms`를 근거 없이 더 큰 상수로 바꾸는 조정.
- stale image를 현재 frame처럼 반환하거나 502를 관측성에서 숨기는 변경.
- Windows TCP registry, NIC, switch 또는 SPOT 설정 변경.

## 4. 기능 요구사항

- **FR-01:** 첫 이미지 upstream 요청은 cadence 때문에 지연되지 않아야 한다.
- **FR-02:** 두 번째 이후 요청은 직전 이미지 upstream 시도가 완료된 시점부터
  다음 upstream 시도 시작까지 최소 `200ms`를 보장해야 한다.
- **FR-03:** cadence는 화면뿐 아니라 `fetch_image_async()`를 호출하는 모든
  백엔드 호출자에게 동일하게 적용되어야 한다.
- **FR-04:** 기존 `_img_fetch_lock`으로 이미지 요청은 계속 하나씩 처리해야 한다.
- **FR-05:** cadence 대기는 `_img_fetch_lock` 안이되 `_spot_device_request_lock`
  밖에서 수행하여, 대기 중 온도/진단/제어 요청이 SPOT과 통신할 수 있어야 한다.
- **FR-06:** cadence 계산에는 시스템 시간 보정에 영향받지 않는 monotonic clock을
  사용해야 한다.
- **FR-07:** 성공, HTTP 오류, request 오류 및 timeout처럼 실제 upstream 시도가
  시작된 경우 모두 완료 시점을 기록하여 실패 직후의 tight retry도 제한해야 한다.
- **FR-08:** cadence 대기 중 작업이 취소되면 네트워크 요청과 이미지 오류 기록 없이
  취소가 그대로 전파되어야 한다.
- **FR-09:** cadence 대기 시간은 `request_elapsed_ms`와
  `X-Spot-Image-Latency-Ms`에 upstream 지연으로 합산하지 않아야 한다.
- **FR-10:** `/api/spot/image.jpg`의 method, path, 성공/실패 status, content type,
  cache header, JPEG payload와 오류 detail 계약은 유지해야 한다.
- **FR-11:** `/api/spot/config`의 기존 필드는 유지하고 cadence 상태는 하위
  `image` 객체에 additive 필드로만 추가해야 한다.
- **FR-12:** 성공한 응답은 매번 새 upstream JPEG여야 하며 cache나 stale frame을
  반환해서는 안 된다.
- **FR-13:** 기존 자동 복구의 실패 후 `500ms`, `1000ms`, `2000ms` 재시도와
  수동 Retry는 유지하되 모든 실제 upstream 호출은 cadence gate를 통과해야 한다.
- **FR-14:** focus, actuator, 온도 및 진단 요청의 URL, timeout, 오류 처리와
  직렬화 계약은 변경하지 않아야 한다.
- **FR-15:** 2차 설계는 image cadence만으로 4-tuple 재사용 0건을 보장한다고
  가정해서는 안 되며, 실제 source-port lifecycle을 독립된 설계 대상으로 둬야 한다.
- **FR-16:** image, temperature, internal temperature, diagnostics, focus 및 actuator의
  요청 시작률·성공·timeout을 요청원별로 구분할 수 있어야 한다.
- **FR-17:** 전체 SPOT 통신 정책은 측정값 freshness, focus/actuator 우선순위와
  영상 갱신 latency를 명시적으로 보존해야 한다.
- **FR-18:** transport recovery를 도입할 경우 fresh/stale 여부를 숨기지 않고,
  evidence 저장에는 fresh upstream 응답만 기록해야 한다.
- **FR-19:** 현장 수집기는 정상 화면의 기존 통신만 사용해 pktmon 시작 후 30초
  이내 SPOT TCP outbound와 inbound를 각각 1개 이상 확인해야 한다.
- **FR-20:** packet direction preflight가 한쪽 방향만 보거나 변환에 실패하면 앱,
  설정 및 네트워크 장비를 바꾸지 않고 본 수집을 중단해야 한다.
- **FR-21:** direction 결과, probe 시간 및 방향별 packet count를 raw manifest와
  sanitized summary에 남기되 IP·MAC·payload는 sanitized 자료에 노출하지 않는다.

## 5. 비기능 요구사항

### 5.1 성능 및 안정성

- 기본 이미지 upstream 시작률은 장시간 평균과 1초 bucket 모두 `5/s`를 넘지 않는다.
- cadence로 대기하는 호출 수는 기존 단일-flight 구조상 요청당 최대 하나여야 한다.
- event loop를 막는 `time.sleep()`이 아니라 취소 가능한 `asyncio.sleep()`을 사용한다.
- cadence 적용 후 일반 화면의 표시 갱신 간격 p95 목표는 `500ms` 이하다.
- 추가 메모리는 상수 크기의 시각·counter 상태로 제한한다.

### 5.2 호환성

- 데이터베이스 migration과 CSV migration은 없어야 한다.
- 기존 config.ini가 그대로 동작해야 하며 자동으로 새 설정을 쓰지 않아야 한다.
- Dashboard와 Settings는 기존 하나의 Blob/image lifecycle을 계속 공유해야 한다.
- 이전 SPOT 이미지 자동 복구와 camera REST conformance 테스트가 계속 통과해야 한다.

### 5.3 보안

- 클라이언트가 upstream URL, IP, cadence 값을 요청 파라미터로 주입할 수 없어야 한다.
- 진단 필드에는 IP, MAC, 원본 payload, credential 또는 내부 경로를 추가하지 않는다.
- 장비 및 OS 전역 TCP 설정을 변경하지 않는다.

### 5.4 관측성

- 설정된 최소 간격, 누적 대기 횟수·합계·최댓값, upstream 시도 횟수,
  최근 시작·완료 시각을 확인할 수 있어야 한다.
- cadence 대기와 실제 connect/read timeout은 서로 다른 값으로 관찰되어야 한다.
- 모든 counter는 프로세스 재시작 시 0으로 초기화되는 in-memory 값임을 명시한다.

## 6. 성공 기준

### 6.1 개발 환경 기준

- [x] 첫 요청 무대기, 연속 요청 최소 간격, 실패 후 간격, 동시 호출 직렬화 테스트 통과.
- [x] cadence 대기 중 온도/진단 호출이 공용 장비 잠금을 획득할 수 있음을 테스트로 증명.
- [x] 대기 중 취소가 네트워크 요청과 오류 count를 만들지 않음을 증명.
- [x] HTTP/1.0 응답 후 연결을 닫는 로컬 모의 서버에서 이미지 upstream 시작률이
      `5/s` 이하임을 증명.
- [x] 기존 SPOT backend와 frontend 회귀 테스트, typecheck, lint 및 repository health 통과.
- [x] `/api/spot/image.jpg` 계약 snapshot과 기존 오류 분류가 변경되지 않음.
- [x] `git diff --check`와 변경 파일 민감정보 scan 통과.
- [ ] clean commit 및 package provenance 검사 통과.

### 6.2 실제 서버 기준

배포 승인을 별도로 받은 뒤 실제 SmartFactoryLogger 서버 PC에서 정상 화면을
그대로 사용하여 최소 60분 canary를 수행한다.

- [ ] SPOT image upstream SYN/요청 시작률이 최대 `5/s` 이하.
- [ ] 정상 화면에서 전체 SPOT 대상 SYN의 60초 p95가 `20/s` 이하.
- [ ] 동일 4-tuple의 60초 미만 재사용 0건.
- [ ] 새 SYN에 대한 이전 연결 plain ACK → PC RST 충돌 0건.
- [ ] SPOT image `ConnectTimeout` 0건, `/api/spot/image.jpg` 5xx 0건.
- [ ] 화면 이미지 표시 갱신 간격 p95 `500ms` 이하, 멈춤 0건.
- [ ] SPOT 온도/진단/focus/actuator 회귀 오류 0건.
- [ ] EX·LS 통신, HTTP, CSV queue/drop/lag, 메모리 및 browser 오류가 정상 범위.
- [ ] ping 손실, 서버 NIC error/discard 및 switch CRC/error/discard 증가 0건.

`20/s` 전체 SYN 기준은 기존 현장 평균 `42.757/s`에서 이미지 약 `30.659/s`를
최대 `5/s`로 줄였을 때의 예상치에 운영 여유를 더한 1차 기준이다. 다른 정상
SPOT 작업이 일시적으로 이 값을 넘으면 즉시 실패로 단정하지 않고 해당 시각의
요청 종류와 패킷을 함께 판독한다.

## 7. 일정 및 승인 Gate

| 단계 | 산출물/작업 | 상태 |
|---|---|---|
| Plan | 원인 범위, 목표, 성공 기준 확정 | Complete |
| Design | cadence 위치, 상태, 잠금, 테스트, 배포/롤백 설계 | Complete |
| Do | 최소 백엔드 패치와 테스트 작성 | Complete |
| Check | 자동 테스트 및 현장 canary | Local complete, field pending |
| Act | gap 보완 또는 롤백 판단 | Pending |
| Report | 최종 결과와 잔여 위험 기록 | Pending |

2026-07-21 Check에서 mandatory gate가 실패했으므로 당시 상태는 `Act active`였다.
당시 package를 production 완료로 승격하거나 후보 브랜치를 병합하지 않는다. 수집기
보강은 승인됐지만 2차 SPOT 애플리케이션 로직은 갱신된 Design과 별도 구현 승인이
필요하다.

Do는 사용자의 별도 명시적 승인 후 전용 브랜치에서 수행했다. 로컬 Do 완료는
package build 또는 실제 서버 배포 승인으로 간주하지 않는다.

## 8. 위험 및 완화

| 위험 | 영향 | 가능성 | 완화 |
|---|---|---|---|
| 영상이 기존보다 덜 부드러움 | 중간 | 높음 | 5fps를 1차 절충값으로 사용하고 표시 갱신 p95를 현장에서 검증 |
| cadence 대기가 온도/제어를 막음 | 높음 | 낮음 | 공용 장비 잠금 밖에서만 대기하고 동시성 테스트 수행 |
| 실패 직후 재시도가 cadence를 우회함 | 높음 | 낮음 | 성공/실패 모두 실제 upstream 시도 완료 시각을 기록 |
| 여러 UI/호출자가 제한을 우회함 | 높음 | 낮음 | 프런트가 아닌 공통 백엔드 `fetch_image_async()`에서 제한 |
| latency 지표가 대기와 네트워크를 혼합함 | 중간 | 중간 | cadence wait와 request latency의 측정 시작점을 분리 |
| 내부 상수 조정에 재배포가 필요함 | 낮음 | 중간 | 1차는 안전한 고정값으로 운영 오설정을 방지; 현장 결과 후 설정화 여부 별도 검토 |
| 원인이 다른 08:10 stall이 다시 발생함 | 높음 | 중간 | 이번 성공 판정과 분리하고 별도 host telemetry PDCA로 추적 |
| PLC 오류가 남아 전체 오류 queue가 0이 아님 | 중간 | 높음 | source별로 판정하고 PLC 입력 정규화 PDCA를 별도 진행 |

## 9. 운영, 배포 및 롤백 원칙

- **브랜치:** Plan부터 Report까지 `codex/spot-tcp-connection-reuse-remediation`
  전용 브랜치에서 관리한다. `master`에서 직접 로직을 수정하지 않는다.
- **배포 전:** 기존 설치 파일, Git commit, config.ini 및 package SHA-256을 기록한다.
- **배포 방식:** 자동 테스트와 clean build를 통과한 한 개의 검증 패키지만 실제 서버에 설치한다.
- **관찰 방식:** 앱 정상 화면을 켠 상태에서 앱 관측성, SPOT TCP packet, 1초 ping,
  서버 NIC 및 가능하면 switch port counter를 같은 시각 기준으로 수집한다.
- **중단 기준:** 새 5xx/ConnectTimeout, 영상 멈춤, 온도/제어 지연, EX·LS 오류 증가,
  CSV drop 또는 메모리 경고가 발생하면 canary를 중단하고 증거를 보존한다.
- **롤백:** 직전 검증 installer/package로 복귀한 뒤 앱을 재시작하고 EX·LS·SPOT·CSV
  정상 여부를 확인한다. DB/CSV migration은 없으므로 데이터 downgrade는 필요 없다.
- **운영 실패 모드:** cadence가 너무 길면 영상 갱신만 느려지고, 너무 짧으면 기존
  TCP 충돌 위험이 남는다. 1차 값은 사용자가 임의로 변경할 수 없게 한다.

## 10. 대안 검토

| 대안 | 결정 | 이유 |
|---|---|---|
| 프런트엔드 성공 timer만 추가 | 제외 | 다른 백엔드 호출자가 우회할 수 있고 화면 상태 머신 계약까지 바뀜 |
| 최근 JPEG cache 공유 | 제외 | stale frame을 현재 영상처럼 반환할 위험과 새 cache lifecycle이 생김 |
| Windows port 범위/TIME_WAIT 조정 | 제외 | 서버 전체 네트워크에 영향을 주며 애플리케이션 과부하 원인을 숨김 |
| SPOT keep-alive 강제 | 제외 | 장비가 `HTTP/1.0`으로 매 응답 연결을 종료하므로 보장할 수 없음 |
| 모든 SPOT 요청을 하나의 전역 rate limit으로 제한 | 1차 제외 | focus/actuator/온도/진단 의미까지 바뀌므로 영향 범위가 큼 |
| 백엔드 이미지 cadence gate | 채택 | 지배적인 이미지 연결률을 공통 경계에서 가장 작은 변경으로 제한 가능 |
| 200ms image cadence만 연장 | 단독 해결책에서 제외 | 219~232ms 재사용과 1초 SYN 재전송 충돌이 확인돼 임의 상수 조정으로 0건을 보장할 수 없음 |
| 전체 SPOT 요청 admission control | 2차 후보 | 총 연결률을 줄일 수 있지만 freshness·제어 우선순위와 port lifecycle을 함께 설계해야 함 |
| application-owned source-port quarantine | 2차 실증 후보 | 4-tuple 재사용을 직접 다루지만 custom transport와 socket 자원 위험 검증이 필요 |
| 장기 연결/stream endpoint | 2차 실증 후보 | 연결 수를 크게 줄일 수 있으나 SPOT 공식 지원·freshness·복구 계약 확인 필요 |
| timeout 후 stale frame 성공 반환 | 제외 유지 | 운영 화면과 evidence에 오래된 영상을 현재 데이터처럼 보일 위험 |

## 11. 참고 자료

- `docs/03-analysis/runtime-error-root-cause-validation.analysis.md`
- `docs/04-report/runtime-error-root-cause-validation.report.md`
- `docs/02-design/features/spot-camera-rest-api-conformance.design.md`
- `docs/02-design/features/spot-image-auto-recovery.design.md`
- `backend/FacilityData/drivers/spot_api.py`
- `backend/app.py`
- `frontend/src/domains/FacilityData/hooks/useSpotViewModel.ts`

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 1.0.0 | 2026-07-20 | 현장 TCP 증거 기반 연결 재사용 충돌 개선 계획 수립 | Codex |
| 1.0.1 | 2026-07-20 | Do 승인·로컬 구현·검증 결과와 현장 pending gate 반영 | Codex |
| 1.1.0 | 2026-07-21 | 현장 canary 실패, 200ms 가정 폐기, 전체 SPOT/port lifecycle 재설계와 packet direction preflight 계획 반영 | Codex |
| 1.2.0 | 2026-08-21 | 실패 후보를 역사 기록으로 동결하고 현재 source-port quarantine 운영 기준 링크 추가 | Codex |
