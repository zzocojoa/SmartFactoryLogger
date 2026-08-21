# Gap Analysis: spot-tcp-connection-reuse-remediation

> Date: 2026-07-21
> Design: `docs/02-design/features/spot-tcp-connection-reuse-remediation.design.md`
> Status: Historical failed candidate; superseded

> **Historical snapshot.** 이 분석의 “브랜치는 병합하지 않는다” 판정은
> `bfd9be7` 후보에 적용된 당시 fail-closed 결정이다. 현재 구현·운영 기준은
> `docs/04-report/spot-tcp-source-port-quarantine-v2.report.md`와
> `docs/03-analysis/spot-request-churn-remediation.analysis.md`를 따른다.

---

## Match Rate: local design-code 100% (30/30), production promotion 0% (mandatory gate failed)

## 1. 판정 요약

승인된 로직 패치 범위는 설계와 일치한다. 백엔드의 공통 이미지 경계에
`200ms` completion-to-next-start cadence를 추가했고, cadence 대기 중 SPOT
공용 장비 잠금을 점유하지 않으며, 실제 upstream 시도가 시작된 경우 성공·HTTP
오류·request 오류·timeout·payload 오류·취소 모두 완료 시각을 기록한다.

기존 `/api/spot/image.jpg`, 공식 `/image.jpg`, JPEG 검증, 오류 분류,
frontend completion-driven lifecycle과 자동 복구 정책은 변경하지 않았다.
새 관측성 필드는 `/api/spot/config.image`에 additive 방식으로 추가됐다.

이 100%는 **로컬 Do 구현과 자동 검증 범위**의 design-code 일치율이다. 실제
서버 package와 60분 packet canary까지 수행한 결과 mandatory error/TCP gate가
실패했다. 따라서 design-code 일치와 무관하게 production promotion은 0%로 판정한다.

## 2. 변경 파일

| 파일 | 구현 내용 | 판정 |
|---|---|---|
| `backend/FacilityData/drivers/spot_api.py` | cadence 상수·상태·대기·upstream lifecycle 기록·additive 진단 | Match |
| `backend/tests/test_spot_api.py` | cadence, 실패, 취소, 잠금, HTTP/1.0 close, API 회귀 테스트 | Match |
| `scripts/qa_spot_image_server.ps1` | 실제 관찰 elapsed/rate와 `5.1/s` 초과 blocker | Match |
| `backend/config.py` | 변경 없음 | Match |
| `backend/app.py` | 변경 없음 | Match |
| `frontend/**` | 변경 없음 | Match |

## 3. 기능 요구사항 대조

| ID | 구현 근거 | 테스트 근거 | 판정 |
|---|---|---|---|
| FR-01 | 마지막 완료 시각이 `None`이면 즉시 반환 | `test_image_cadence_first_request_does_not_sleep` | Match |
| FR-02 | 완료 monotonic + `0.2`에서 남은 시간 계산 | `test_image_cadence_limits_consecutive_upstream_starts` | Match |
| FR-03 | public `fetch_image_async()` 공통 경계에 cadence 배치 | call-site 검색 결과 production caller는 app route 1개 | Match |
| FR-04 | 기존 `_img_fetch_lock` 유지 | 기존 single-flight 및 새 concurrent cadence 테스트 | Match |
| FR-05 | image lock 안, device lock 밖에서 cadence await | `test_image_cadence_wait_does_not_hold_device_lock` | Match |
| FR-06 | 계산에 `time.monotonic()`만 사용 | `test_image_cadence_uses_monotonic_clock_only` | Match |
| FR-07 | `client.get()`/status 처리 공통 `finally`에서 완료 기록 | success, timeout, HTTP, request, invalid payload 테스트 | Match |
| FR-08 | sleep 취소를 변환·기록하지 않고 전파 | `test_cancelling_cadence_wait_does_not_start_upstream_or_record_error` | Match |
| FR-09 | success timer를 cadence 뒤에 시작, request timer는 device lock 뒤 유지 | success/timeout elapsed 분리 테스트 | Match |
| FR-10 | app route 소스 무변경 | 기존 route 성공·404·502·payload rejection 테스트 | Match |
| FR-11 | config `image` 객체에 7개 additive 필드 | diagnostics 및 route config 테스트 | Match |
| FR-12 | cache 없이 호출마다 upstream GET | 기존 official resource 테스트와 HTTP/1.0 5-connection 테스트 | Match |
| FR-13 | frontend 소스·재시도 정책 무변경 | frontend integration 12개 포함 전체 237개 통과 | Match |
| FR-14 | 온도/진단/focus/actuator 소스 계약 무변경 | SPOT 전체 91개 및 backend 전체 528개 통과 | Match |

## 4. 상태 및 관측성 대조

| 설계 상태/필드 | 구현 | 판정 |
|---|---|---|
| `_SPOT_IMAGE_MIN_COMPLETION_TO_START_SEC = 0.2` | private 상수로 구현 | Match |
| 마지막 완료 monotonic | process-local optional float | Match |
| upstream request count | 실제 `client.get()` 직전 증가 | Match |
| cadence wait count/total/max | 완료된 양수 sleep만 누적 | Match |
| 최근 upstream 시작/완료 epoch | additive diagnostics로 노출 | Match |
| config/DB/CSV persistence 없음 | 관련 파일과 schema 무변경 | Match |
| 민감정보 미노출 | IP/MAC/body/credential 신규 필드 없음 | Match |

## 5. 테스트 설계 대조

| Test ID | 증거 | 판정 |
|---|---|---|
| CAD-01 | 첫 호출 sleep 0회 | Match |
| CAD-02 | 50ms 경과 상태에서 남은 약 150ms 요청 | Match |
| CAD-03 | interval 경과 후 sleep 0회 | Match |
| CAD-04 | 연속 실제 upstream 시작 간격 200ms 기준 | Match |
| CAD-05 | ConnectTimeout 후 다음 호출에도 cadence 적용 | Match |
| CAD-06 | 설정 누락은 upstream count/시각 미변경 | Match |
| CAD-07 | HTML payload reject 후 connection completion 유지 | Match |
| CAD-08 | 두 caller 직렬화 및 cadence 우회 0 | Match |
| CAD-09 | cadence sleep 취소 시 네트워크·오류 기록 0 | Match |
| CAD-10 | active `client.get()` 취소 시 완료 기록 후 취소 전파 | Match |
| CAD-11 | cadence 중 temperature request 완료 가능 | Match |
| CAD-12 | wall clock 미사용 | Match |
| CAD-13 | 음수 remaining은 sleep 없이 진행 | Match |
| CAD-14 | 7개 진단 필드 초기값·누적·기존 필드 유지 | Match |
| CAD-15 | success latency와 timeout elapsed에서 cadence 제외 | Match |

## 6. 검증 결과

### 6.1 자동 검사

| 검사 | 결과 |
|---|---|
| 기존 이미지 기준선 8개 | PASS |
| 새 cadence 집중 테스트 | PASS |
| `backend.tests.test_spot_api` | 91 tests PASS |
| PowerShell AST parse | PASS |
| `npm run health` 최종 | PASS, 74.3s |
| Electron startup | 38 tests PASS |
| Frontend | typecheck/lint PASS, 31 files / 237 tests PASS |
| Backend | Ruff/mypy PASS, 528 tests PASS |
| QA self-test | PASS |
| `git diff --check` | PASS |
| 변경 파일 민감 문자열 scan | 신규 secret/credential 없음 |

테스트 로그의 의도된 error-path 메시지와 FastAPI TestClient deprecation warning은
기존 테스트 동작이며 전체 명령 종료 코드는 0이었다.

### 6.2 로컬 HTTP/1.0 close 검증

실제 loopback TCP 서버가 `HTTP/1.0`, `Connection: close`, 유효 JPEG를 매 요청
반환하도록 구성했다. 5개의 image upstream 연결이 모두 성공했고 인접 시작 간격은
설계 허용 오차 `>=190ms`, 관찰률은 `<=5.1/s`였다.

### 6.3 QA script 양방향 검증

| 모의 backend | 요청률 | 실패 | blocker | 결과 |
|---|---:|---:|---:|---|
| 응답마다 약 220ms 소요 | `4.436/s` | 0 | 0 | PASS |
| 지연 없는 HTTP/1.0 close | `615.745/s` | 0 | rate blocker 1 | 기대대로 FAIL |

따라서 QA 스크립트는 정상 제한 상태를 통과시키고 cadence가 없는 과속 상태를
실제로 차단한다.

## 7. 누락 및 변경 사항

### 7.1 승인된 로컬 Do 범위의 누락

없음.

### 7.2 설계 대비 변경

없음. 구현 중 `backend/config.py`, `backend/app.py`, `frontend/**` 수정이
필요하지 않았으며 설계의 최소 변경 경계를 유지했다.

### 7.3 운영 Gate 결과

- [x] feature 파일 clean commit `bfd9be785f7a87aa4150445945861a54bca98f33` 확정.
- [x] clean commit 기반 PyInstaller backend와 NSIS package 생성.
- [x] package commit 및 installer SHA-256/provenance 확인.
- [x] 실제 서버 정상 화면 60분 이상 canary와 연장 packet/log 수집.
- [x] SPOT image upstream rate 확인: p95 `4.683/s`, 최대 `4.783/s`.
- [ ] 동일 4-tuple 60초 미만 재사용 0건: 필수 60분 최소 731건으로 실패.
- [ ] old ACK → RST 0건: 전체 수집 구간 6건으로 실패.
- [ ] ConnectTimeout/image 5xx 0건: 필수 60분 3회, 전체 구간 5회로 실패.
- [ ] SPOT 온도 회귀 0건: 09:19 temperature timeout 동시 발생으로 실패.
- [x] EX·LS, CSV queue/drop/lag, sustained memory leak, browser error 회귀 없음.
- [x] 오류 시점 ping 성공, 서버 NIC error/discard 증가 및 Windows link event 0.
- [ ] switch CRC/error/discard: 자료 미포함으로 미판정.
- [ ] 화면 갱신 p95: browser timing 자료가 없어 미판정.

현장 canary는 rate 감소를 증명했지만 원인 재발 방지를 증명하지 못했다. Design의
즉시 중단·rollback 조건이 충족됐으며 같은 package의 반복 canary는 필요하지 않다.

### 7.4 현장 TCP 직접 상관

09:19 첫 오류 구간은 PCAP inbound 누락 때문에 하위 TCP sequence를 직접 판정할 수
없었다. 그러나 PCAP이 정상 양방향으로 기록된 연장 구간에서 다음이 확인됐다.

| 시각 | 재사용 간격 | packet sequence | app 결과 |
|---|---:|---|---|
| 약 11:00:51 | 약 219ms | new SYN → old ACK → PC RST, 1초 뒤 반복 | 11:00:53 ConnectTimeout/502 |
| 약 11:20:19 | 약 232ms | new SYN → old ACK → PC RST, 1초 뒤 반복 | 11:20:21 ConnectTimeout/502 |

이는 1차 패치 후에도 기존 4-tuple 충돌 메커니즘이 실제 사용자 502를 만든 직접
증거다. 10:55에는 diagnostics 요청과 관련된 같은 충돌이 있었지만 app-level
image 502로 이어지지는 않았다.

### 7.5 새 gap 목록

| ID | 구분 | Gap | 우선순위 | Act 처리 |
|---|---|---|---|---|
| G-01 | Changed assumption | 200ms image cadence가 4-tuple 재사용을 막지 못함 | P0 | 단순 상수 조정 금지, transport 재설계 |
| G-02 | Missing in design | 전체 SPOT 요청원 약 14.7 SYN/s와 diagnostics fan-out을 해결 경계로 다루지 않음 | P0 | 요청원별 계측·freshness 포함 |
| G-03 | Missing in code/design | application이 local source-port lifecycle을 통제하지 않음 | P0 | quarantine/장기 연결 prototype gate |
| G-04 | Missing in collector | 본 수집 전 bidirectional packet 여부를 검증하지 않음 | P0 | 10초 passive preflight 구현 |
| G-05 | Missing evidence | switch 시작·종료 counter/log 미포함 | P1 | 다음 현장 checklist에서 필수 확인 |
| G-06 | Measurement ambiguity | 60분 app sampling이 약 76분, packet은 약 156분 지속 | P1 | phase별 실제 시작·종료 시각 분리 |

G-01~03은 추가 app 로직 구현 전 Plan/Design 및 별도 승인이 필요하다. 이번 Act에서
즉시 구현하는 항목은 이미 승인된 G-04 collector fail-closed preflight뿐이다.

## 8. 위험 및 롤백 재확인

- 영상은 기존 약 30fps에서 이론상 최대 5fps 이하로 낮아진다. 현장 사용성은
  60분 canary에서 확인해야 한다.
- 이미지 외 SPOT 온도/진단 연결이 남으므로 전체 SYN 목표는 packet으로 검증해야 한다.
- 08:10 host-side stall과 PLC empty-string 오류는 이번 패치 범위 밖이며 남아 있다.
- DB/CSV/config migration은 없다.
- rollback은 직전 검증 package 재설치와 앱 재시작이다.

## 9. 결론 및 다음 단계

로컬 로직은 1차 Design과 100% 일치하지만 현장 mandatory gate를 실패했으므로
package 후보 지위를 상실했다. 당시 서버는 canary 직전 검증 package로 rollback하고,
해당 후보 브랜치는 병합하지 않는다.

PDCA는 `Act iteration 2`로 되돌린다. 다음 구현 전 단계는 전체 SPOT transport 대안의
prototype과 source-port quarantine 가능성을 증명하는 것이다. packet direction
preflight는 별도 수집 안전성 gap으로 구현·self-test하되, 그 완료를 SPOT 원인 해결로
간주하지 않는다.

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 1.0.0 | 2026-07-20 | 승인된 local Do design-code gap 분석 및 운영 pending gate 기록 | Codex |
| 1.1.0 | 2026-07-21 | field canary 실패, TCP 직접 상관, 새 P0 gap과 Act iteration 2 판정 반영 | Codex |
| 1.2.0 | 2026-08-21 | 실패 후보를 역사 기록으로 동결하고 현재 source-port quarantine 운영 기준 링크 추가 | Codex |
