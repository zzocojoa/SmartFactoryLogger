# runtime-error-root-cause-validation Completion Report

> **Status**: `575E869_HISTORICAL_FIELD_CANARY_PASS / CURRENT_RELEASE_REVALIDATION_REQUIRED / PHYSICAL_PATH_PARTIAL`
> **Project**: SmartFactoryLogger v2_next
> **Author**: Codex
> **Completion Date**: 2026-07-31
> **Scope**: 원인 조사, source-port 격리 패치, 실제 서버 QA·smoke·120분 canary 검증
> **Operational supersession**: 2026-08-05 `49fbf6b` shutdown-closeout QA 실패 후
> 실제 서버는 검증된 v1.0.16으로 롤백됨

---

## 1. 요약

| 항목 | 내용 |
|------|------|
| Feature | `runtime-error-root-cause-validation` |
| 시작일 | 2026-07-17 |
| 종료일 | 2026-07-31 |
| 기간 | 15일 |
| Check 정합률 | 92% (23/25) |
| 현장 판정 | `FIELD_CANARY_PASS / PHYSICAL_PATH_PARTIAL` |
| 역사적 검증 commit | `575e869b63d3052156624886fe0358fb39d6c98a` |
| 현재 서버 runtime | 검증된 v1.0.16 롤백 |
| 현재 release 판정 | `FIELD_REVALIDATION_REQUIRED` |

### 1.1 최종 결과

1. `plc_driver` 오류는 `diagnostics_age_ms=''` 빈 문자열을 실수로 변환하는 시작 데이터 형상
   오류다. 같은 시각의 EX·LS 통신 실패가 원인이 아니다.
2. SPOT `ConnectTimeout`의 주된 메커니즘은 고율의 짧은 `HTTP/1.0` 연결과 local port 조기
   재사용으로 SPOT의 이전 TCP 종료 상태와 새 SYN이 충돌한 것이다.
3. 08:33 오류는 SYN, old ACK, RST, 재전송, 2.016초 timeout sequence로 직접 확인됐다.
   08:19의 세 오류도 수초 내 port 재사용 기록 때문에 같은 원인이 유력하다.
4. 08:10 오류는 SPOT packet 공백, 4.844초 앱 처리 지연, Extruder timeout, ping 프로세스
   지연이 함께 나타난 별도 host-side stall이다. 더 하위 원인은 미확정이다.
5. `SystemExit: 3`은 기존 backend 종료가 아니라 두 번째 실행의 단일 인스턴스 guard 거부다.
6. PLC 오류, SPOT TCP 충돌, 두 번째 실행 실패를 하나의 원인으로 합치지 않는다.
7. source-port quarantine v2를 포함한 `575e869` 설치본은 commit-bound re-attestation,
   one-command QA, 15분 smoke, 120분 canary와 최종 live gate를 통과했다. 다만 관리형
   스위치의 시작·종료 counter를 확보하지 못해 물리 경로 결함은 미배제 상태다.

### 1.2 완료율

```text
전체 설계 항목: 25
Match:          23 (92%)
Gap:             2 (8%)
```

`LOAD-01`, `LOAD-02`, `PLC-NET-01`은 P1 수동 증거로 원인이 좁혀져 진입 조건이 성립하지
않았다. `REG-01`은 PLC 로직을 변경하지 않아 적용 대상이 없었다. `REG-02`와
`RELEASE-01`은 초기 조사 단계에서는 미래 gate였고, 후속 source-port remediation의
`575e869` QA·smoke·canary로 역사적으로 충족했다. 이 판정은 현재 release에 재사용하지 않는다.

### 1.3 575e869 역사적 최종 현장 판정

| 항목 | 최종 증거 |
|------|-----------|
| 판정 | `FIELD_CANARY_PASS / PHYSICAL_PATH_PARTIAL` |
| 최종 gate 시각 | `2026-07-31T15:18:48.8849197+09:00` |
| build commit | `575e869b63d3052156624886fe0358fb39d6c98a` |
| backend SHA-256 | `294C228EF4B8D99730F14A40C1EB438695611FA816BDF6B1E17270DA3CD3FB0D` |
| config SHA-256 | `36F86150C50BDAD4449AB09DFAD528313326119DC0AE61CDE59DEFDFF7BB3EDE` |
| canary sanitized ZIP SHA-256 | `3393C32C8C248704448E10DD5BC38A49012E8FA07B89362CFE7306B70BFA6350` |
| 최종 gate JSON SHA-256 | `68F784B611DA7334356B039BF5B794761F3B8C27C6A9F4A401BD3D2FD83356D5` |
| 최종 gate checks | 39/39 `True` |

최종 live gate에서 health `200`, frozen runtime, backend/Electron process 수, runtime과
SPOT config commit, attestation `verified`, operator verification, config fingerprint,
source-port policy, 768개 pool partition, 75초 quarantine·minimum reuse interval이 모두
일치했다. reuse violation, pool exhaustion, transport failure, image refresh failure는
모두 0이고 image 상태는 `ok`였다. `rebind_retry_count=247`과
`bind_collision_count=2869`는 정책이 충돌을 처리한 관측 counter이며 실패 gate가 아니다.

최초 final-gate helper는 SPOT config 응답의 root에서 `build_git_commit`을 읽어
`PropertyNotFoundStrict`로 중단됐다. 실제 필드가 `image.build_git_commit`에 있음을 확인해
read-only helper만 수정했고, 수정본 SHA-256
`C0AE075633A9FD48E437A8605124A0067CB445709B1CBFE8A5CD5C0A3672277B`로 재실행한
최종 gate가 통과했다. 이 오류는 앱, 서버 상태, canary 수집 결과를 변경하지 않았다.

---

## 2. 관련 문서

| 단계 | 문서 | 상태 |
|------|------|------|
| Plan | [runtime-error-root-cause-validation.plan.md](../01-plan/features/runtime-error-root-cause-validation.plan.md) | 완료 |
| Design | [runtime-error-root-cause-validation.design.md](../02-design/features/runtime-error-root-cause-validation.design.md) | 완료 |
| Do | [runtime-error-root-cause-validation.do.md](../02-design/features/runtime-error-root-cause-validation.do.md) | 현장 실행 완료 |
| Check | [runtime-error-root-cause-validation.analysis.md](../03-analysis/runtime-error-root-cause-validation.analysis.md) | 92% |

---

## 3. 25개 항목 최종 판정

| ID | 최종 상태 | 근거 또는 미실행 사유 |
|----|-----------|------------------------|
| SAFE-01 | Match | 사용자 승인, 관리자 preflight, 앱 무변경 안전 조건 통과 |
| ENV-01 | Match | 실제 서버의 프로세스·포트·SPOT 설정을 현장 package가 확인 |
| BASE-01 | Match | raw·sanitized 분리, manifest와 SHA-256 확보 |
| PLC-01 | Match | 36/36 시작 상관과 독립 무통신 오류 창 대조 |
| PLC-02 | Match | `diagnostics_age_ms=''` 원문과 변환 경로 확인 |
| PLC-03 | Match | 사건 시각 EX 통신 실패 비동반 확인 |
| PLC-04 | Match | 사건 시각 LS 통신 실패 비동반 확인 |
| PLC-05 | Match | 마지막 세션의 상태 복구 확인 |
| SPOT-01 | Match | 180회 앱 관측성, 1,080 GET 모두 HTTP 200 |
| SPOT-02 | Match | ETL·PCAPNG와 TCP flags·sequence 분석 완료 |
| SPOT-03 | Match | ping 2,619/2,619 성공, 오류 시각 대조 완료 |
| SPOT-04 | Match | NIC error·discard delta 모두 0 |
| SPOT-05 | **Gap** | 같은 시간의 스위치 port counter·event 미확보 |
| SPOT-06 | **Gap** | SPOT 장비 내부 서비스 로그 미확보 |
| SPOT-07 | Match | 오류 직후 다음 SYN 성공과 장시간 후속 정상 traffic 확인 |
| PROC-01 | Match | process before·after CSV 확보 |
| PROC-02 | Match | port owner before·after CSV 확보 |
| PROC-03 | Match | startup stack·guard·기존 backend 생존 대조 완료 |
| COMMON-01 | Match | HTTP·CSV queue·메모리·browser 상태 교차 확인 |
| LOAD-01 | Match, 조건부 미실행 | 수동 부하 없이 실제 오류와 TCP 충돌을 재현해 위험한 부하 시험 불필요 |
| LOAD-02 | Match, 조건부 미실행 | raw packet으로 앱 경로 실패 sequence가 확인돼 장비 직접 반복 시험 불필요 |
| PLC-NET-01 | Match, 조건부 미실행 | 사건 PLC 오류에 EX·LS read failure가 동반되지 않아 진입 조건 불성립 |
| REG-01 | Match, 적용 대상 없음 | PLC 로직을 변경하지 않아 PLC 회귀시험 대상 없음 |
| REG-02 | Match, 후속 gate 충족 | `575e869`에서 SPOT QA·15분 smoke·120분 canary 통과 |
| RELEASE-01 | Match, 역사적 승인 | `575e869` commit-bound release gate 통과; 현재 release는 재검증 필요 |

---

## 4. 핵심 기술 증거

### 4.1 SPOT TCP 충돌

양방향 packet이 모두 기록된 약 25분 동안 고유 TCP SYN은 64,862건, 정상 SYN-ACK는
64,861건이었다. 서로 다른 local source port 16,238개가 사용됐고 같은 port는 48,624회
재사용됐다.

유일한 1초 미만 재사용은 정상 연결 종료 35ms 뒤 발생했다. SPOT은 새 SYN에 SYN-ACK가 아닌
이전 연결의 ACK를 반환했고 서버 PC는 RST를 보냈다. 1초 뒤 같은 교환이 반복된 다음 앱에
`ConnectTimeout`이 기록됐다. 오류 15ms 뒤 다른 port의 연결은 정상 성공했다.

### 4.2 물리망 반대 증거

- ping은 2,619회 모두 성공했다.
- 세 NIC의 received/outbound error·discard 증가는 0이다.
- 오류 시각의 Windows NIC·TCP/IP·link 경고는 없다.
- 08:33 실패 중에도 SPOT의 old ACK가 서버에 도착해 왕복 경로 자체는 살아 있었다.

따라서 서버 NIC 고장, 케이블·스위치 전체 단절, SPOT 장비 전체 다운은 주원인에서 제외한다.

### 4.3 별도 host-side stall

08:10 사건은 2초 설정과 달리 4.844초 뒤 timeout이 처리됐고 같은 시각 Extruder timeout도
발생했다. 이 사건은 TCP port 재사용만으로 전부 설명하지 않으며 CPU, disk latency,
process scheduling, event-loop lag를 다음 재발 시 1초 단위로 수집해야 한다.

---

## 5. 품질과 운영 평가

| 지표 | 목표 | 최종 | 판정 |
|------|------|------|------|
| Design Match Rate | 90% 이상 | 92% | 통과 |
| ZIP 경로 안전성 | 위험 경로 0 | 0 | 통과 |
| raw ZIP CRC | 오류 0 | 0 | 통과 |
| sanitized ZIP SHA-256 | 제공값 일치 | 일치 | 통과 |
| 앱 로직 변경 | 0 | 0 | 통과 |
| 관리자 수집기 정리 | 소유 filter만 제거 | `removed_owned_state` | 통과 |

### 5.1 보안

`raw_private`에는 내부 IP, MAC, 경로와 HTTP payload가 포함될 수 있다. 공개 채널에는
sanitized ZIP만 사용하고 raw 파일은 접근이 제한된 서버 저장소에 보관한다.

### 5.2 호환성과 롤백

DB, CSV schema, SPOT·PLC 장비 설정 migration은 없다. 설치 후 operator re-attestation으로
config의 승인된 attestation 필드만 변경됐고 backup이 이전 config SHA-256과 일치했다.
rollback 경로는 검증된 `smart-factory-logger-v2.Setup.1.0.16.exe`다. 수집 시 추가된
pktmon filter는 package가 소유 상태를 확인한 뒤 제거했으며 최종 앱 health는 `200`이다.

---

## 6. 남은 Gap과 후속 범위

### 6.1 비차단 Gap

- `SPOT-05`: 스위치 과거 link/CRC/error/discard event가 남아 있으면 보조 증거로 추가한다.
- `SPOT-06`: SPOT 장비가 service/TCP 상태 로그를 제공하면 08:33:14~08:33:17을 확인한다.

두 자료가 없어도 이미 확보한 양방향 TCP sequence에 따른 08:33 충돌 판정은 유지된다.

### 6.2 별도 조사 항목

08:10 host-side stall은 다음 재발 시 CPU, disk latency, process scheduling delay, 앱 event-loop
lag 수집을 추가하는 별도 PDCA 대상으로 분리한다.

### 6.3 패치와 운영 경계

source-port quarantine v2 패치는 별도 Plan·Design과 commit-bound release 절차로 구현됐다.
`575e869b63d3052156624886fe0358fb39d6c98a`의 2026-07-31 현장 판정은 역사적 증거로
유효하다. 그러나 이후 `49fbf6b`에서 X 버튼 종료 뒤 current-session metadata의
`csv_closeout.finalized=true`가 생성되지 않는 QA 실패가 재현됐고, 2026-08-05 실제 서버는
SHA-256이 검증된 v1.0.16 설치본으로 롤백됐다. 따라서 `575e869`의 과거 승인 또는 이
Report를 현재 HEAD, `49fbf6b`, `949ef38`이나 다른 설치본의 운영 승인으로 재사용하지 않는다.

`949ef38`은 개발 환경의 종료 hotfix 검증 기록만 있으며 실제 서버에 설치되지 않았다.
후속 후보는 exact-commit release identity, preinstall gate, re-attestation, QA, smoke,
120분 canary와 final live gate를 새로 통과해야 한다.

관리형 스위치 counter가 없어 canary 수집기는 `PARTIAL`로 종료됐다. 이는 앱 canary와 live
gate 실패가 아니라 물리 경로 미배제 표시다. 따라서 운영 판정은 `FIELD_CANARY_PASS`,
물리망 판정은 `PHYSICAL_PATH_PARTIAL`로 분리해 유지한다.

---

## 7. 교훈

### 7.1 유지할 점

- 앱·TCP·ping·NIC를 같은 시각으로 수집해 오류 메시지 아래의 실제 TCP sequence를 확인했다.
- raw와 sanitized 자료를 분리해 분석 가능성과 외부 공유 안전성을 함께 확보했다.
- PLC, SPOT, 중복 실행 사건을 서로 다른 원인으로 분리했다.

### 7.2 개선할 점

- collector의 sanitized sample 시각은 원본 envelope 시간이 아니라 summary 작성 시각으로
  기록돼 packet 상관에는 사용할 수 없었다.
- 수동 스위치 화면과 종료 후 상태 화면은 실행 절차에서 누락됐다.
- 08:28 이전 packet에는 수신 방향이 없어 앞선 세 오류의 TCP 응답을 직접 확인할 수 없었다.

### 7.3 다음에 시도할 것

- 재발 수집기는 원본 event 시각을 보존하고 TCP 양방향 capture를 preflight에서 검증한다.
- host stall 진단에는 CPU·disk·event-loop lag를 1초 단위로 추가한다.
- 로직 수정 PDCA에서는 HTTP/1.0 close와 동적 port 순환을 재현하는 회귀 기준을 먼저 설계한다.

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.2.0 | 2026-08-06 | 49fbf6b shutdown-closeout QA 실패, 미배포 949ef38, 검증된 v1.0.16 롤백과 현장 증거 재사용 금지 경계 반영 | Codex |
| 1.1.0 | 2026-07-31 | 575e869 QA·smoke·120분 canary와 최종 live gate 판정 동결 | Codex |
| 1.0.0 | 2026-07-20 | 현장 raw 증거 기반 조사 완료 보고서 작성 | Codex |
