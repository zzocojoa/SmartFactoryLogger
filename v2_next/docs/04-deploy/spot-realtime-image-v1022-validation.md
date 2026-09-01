# SPOT 실시간 이미지 v1.0.22 서버 검증

> 범위: `1.0.22` / `5cc34b4fffd70195ec7fdd9d27acf4880cecbd80`
>
> 분류: `PRIVATE_UNSIGNED_INTERNAL_VALIDATION_ONLY`

## 목적

v1.0.21에서 실측된 75초 미만 source-port 재사용 문제를 수정한 v1.0.22를
서버에서 안전하게 검증한다. 제품은 최소 75초에 2초 여유를 더한 77초
quarantine을 사용한다.

이 키트는 다음 단계까지만 허용한다.

1. 파일·commit·rollback·서버 상태 preflight
2. 검토 완료된 v9 15분 증거의 SHA-256 재검증
3. 실행 직전 30~60초 이미지 활성 확인
4. 120분 관찰과 증거 보존

2026-09-01의 v9 15분 결과는 앱 요청 4,989/성공 4,989, 이미지 요청
2,491/성공 2,491, 신규 실패 0, HTTP 응답 누락 0, SYN 재전송 0, RST 0,
동일 four-tuple 최소 재사용 75.992초로 검토됐다. 정정 결과 JSON, 정제 ZIP,
control ZIP의 SHA-256을 v10 identity에 고정했으며 이 세 파일이 모두 일치해야
120분을 시작할 수 있다. 이 승인은 120분 내부 검증에만 적용하며 production
승격을 승인하지 않는다.

- 승인 범위 식별자: `120-minute-canary-only`

## 고정 제품 계약

- 제품 버전: `1.0.22`
- 제품 commit: `5cc34b4fffd70195ec7fdd9d27acf4880cecbd80`
- 정책: `spot-source-port-quarantine-v3`
- 최소 요구 간격: `75초`
- 안전 여유: `2초`
- 실제 quarantine: `77초`
- 제품 pool: `768개`
- 6회/초 × 77초 최소 용량: `462개`
- 복구본: v1.0.20 / `cd8cfa649203494cf087206cf656dc2197107ea1`

## 서버 폴더 구조

Canary 폴더는 다음 release 폴더 바로 아래에 둔다.

```text
spot-realtime-image-performance-v1.0.22-5cc34b4\
  release_identity.json
  smart-factory-logger-v2 Setup 1.0.22.exe
  SmartFactoryLogger_SPOT_Realtime_Image_v1022_Canary_*\
```

v1.0.20 복구 설치본은 기존 검증 경로에 그대로 보존한다. Canary는 앱을
재시작하거나 오류 큐를 지우거나 설정을 바꾸지 않는다.

## 진행 표시

검증 명령은 단계, 경과 시간, 남은 시간, 진행률, 예상 종료 시각과 backend
생존 상태를 표시해야 한다. 진행 표시는 로컬 시계와 프로세스 상태만 사용하며
SPOT 또는 backend API 호출을 추가하지 않는다.

The observation prints progress every 30 seconds and does not add SPOT or
backend API requests.

## 120분 시작 절차

1. v10 ZIP과 SHA-256 sidecar를 검증한다.
2. 승인된 v9 15분 결과 JSON, 정제 ZIP, control ZIP을
   `server-evidence\v1022-pending\approved-15m-v9-20260901-135039`에 둔다.
3. v1.0.20 복구본과 기존 `preinstall-summary.json`, `health-before.json`을
   검증한다.
4. 새 30초 historical baseline과 packet preflight를 통과한다.
5. SmartFactory 카메라 화면을 계속 표시한 상태에서 30~60초 이미지 요청·성공·
   파일 생성 카운터가 증가하는지 확인한다.
6. `RUN-120M`을 입력해 정확히 한 번 실행한다.

120분 중에는 앱을 최소화하거나 탭을 바꾸거나 오류를 지우거나 부하 시험을
실행하지 않는다. 오류가 보이면 그대로 두고 시각을 기록한다.

## 관찰 종료 경계

- 부모 수집기가 monotonic 15분 또는 120분 경계에서 즉시 종료 스냅샷을
  저장한다.
- 부모 수집기는 같은 경계 시각을 담은 원자적 완료 요청을 자식 오류 모니터에
  전달한다.
- 패킷·ping 종료 상태를 먼저 고정한 뒤 자식 완료 신호를 확인한다.
- 자식 완료 신호가 경계 후 5초 안에 확인되지 않거나 부모 요청 ID와 다르면
  제품 실패로 대체하지 않고 `EVIDENCE_HOLD`로 판정한다.
- 압축·로그 수집·패킷 분석 시간은 관찰 구간 실패 delta와 요청률 계산에서
  제외한다.

## HTTP 무응답 분류

- `request_no_response_after_handshake_attempts`는 TCP handshake 뒤 실제 outbound
  HTTP 요청 payload가 관측됐지만 응답 payload가 없는 경우만 집계한다.
- handshake만 완료되고 outbound 요청 payload가 없는 흐름은
  `handshake_only_without_request_attempts` 또는
  `handshake_only_at_capture_end`로 별도 기록한다.
- handshake-only 흐름은 HTTP 요청 무응답 제품 실패로 판정하지 않는다.
- 패킷 분석에서만 무응답이 보이더라도 같은 관찰 구간의 transport 시작/성공,
  image 시작/성공, image upstream 카운터가 모두 일치하고 관련 failure counter와
  failure event 증가가 0이면 `capture-or-flow-attribution-discrepancy`로 기록한다.
  이 경우 패킷 후보 자체는 제품 실패나 `EVIDENCE_HOLD`로 승격하지 않는다.
- 위 aggregate app-success 계약의 필수 카운터가 없거나 관계가 일치하지 않으면
  제품 성공으로 추정하지 않고 `EVIDENCE_HOLD`로 보존한다.
- 패킷 무응답과 앱 failure 증가가 함께 확인된 경우에만
  `no-response-after-handshake-app-corroborated` 제품 hard failure로 판정한다.
- 이 분리는 원문 주소와 source port를 공유 ZIP에 노출하지 않는다.

## 연결 전 패킷 후보 분류

- 패킷 분석에서 TCP handshake 전 실패 후보가 보이면 앱 failure counter 또는
  failure event 증가가 있는지 먼저 확인한다. 증가가 있으면
  `failed-connection-attempt-app-corroborated` 제품 hard failure다.
- 앱의 같은 관찰 구간 transport 시작/성공, image 시작/성공/upstream 카운터가
  모두 일치하고 failure 증가가 0이어야 앱 성공 증거로 인정한다.
- 앱 성공 증거와 함께 캡처 구간 보존, timestamp 정렬, clock calibration 완료,
  SYN 재전송 0, reset-before-response 0, 양방향 RST 0이 모두 확인되면 해당
  패킷 후보는 `capture-or-flow-attribution-discrepancy`로 기록한다. 제품 실패나
  `EVIDENCE_HOLD`로 승격하지 않는다.
- 위 조건 중 하나라도 누락되거나 불일치하면 성공으로 추정하지 않고
  `EVIDENCE_HOLD`로 보존한다.

## 15분 진단 판정

15분 수집을 시작하기 직전에 SmartFactory 카메라 화면을 표시한 상태로 30초 이상,
최대 60초 동안 이미지 활성 상태를 확인한다. PowerShell은 화면 옆에 배치하고 앱을
최소화하거나 다른 탭으로 이동하지 않는다. 이 확인은 로컬
`/api/spot/config` 카운터만 읽으며 SPOT 이미지 요청을 추가하지 않는다.

다음 값이 모두 증가해야 본 관찰을 시작한다.

- image downstream/upstream 요청 수
- source-port image 시작/성공 수와 화면 갱신 성공 수
- 이미지 캡처 enqueue/write/fact row 수
- 마지막 capture ID와 상대 경로

증가하지 않으면 제품 실패나 롤백으로 단정하지 않고
`SPOT_IMAGE_LIVENESS_EVIDENCE_HOLD`로 멈춘다. 15분 전체 구간의 이미지 요청 수가
0인 경우에도 같은 원칙으로 `EVIDENCE_HOLD`이며 자동 롤백 사유가 아니다.

다음 조건을 모두 확인한다.

- backend PID, config SHA256, build commit 유지
- 신규 transport/image/temperature 및 기타 failure delta 0
- failure event journal 신규 항목과 drop 0
- 보정된 동일 four-tuple 재사용 최소 간격 75초 이상
- `reuse violation`, pool wait, pool exhaustion 0
- 양방향 RST, SYN 재전송 0
- HTTP 무응답 및 연결 전 실패 후보는 위 앱 결과 상관판정 계약을 통과하거나 0
- SPOT 영상 지속 갱신 및 전체 앱 화면 신규 오류 없음

관리형 스위치 자료가 없으면 결과는 제한 판정으로 유지한다. 제품 hard failure가
확인된 경우에만 v1.0.20 복구본을 사용한다. 계측 불완전인 `EVIDENCE_HOLD`에서는
자동 롤백하거나 즉시 재실행하지 않는다.

## 제공할 증거

120분 실행 뒤 다음을 제공한다.

- `runtime_validation_*_sanitized_share.zip`
- `sanitized_share_sha256.txt`
- 해당 `canary-control-*` 폴더의 ZIP
- `canary-120m-gate.json`이 있는 해당 `canary-control-*` 폴더
- 120분 동안 영상 갱신과 화면 오류 여부에 대한 사용자 확인

원본 `raw_private` 폴더는 서버에서 삭제하지 않는다. 공유 ZIP은 원문 주소와
source port 값을 포함하지 않는 정제 증거만 사용한다.

## 운영 제한

- 이 키트와 설치본은 서명되지 않은 내부 검증용이다.
- 15분 통과와 120분 실행 승인만으로 production 승격을 승인하지 않는다.
- 120분 결과를 별도로 검토하기 전에는 v1.0.22를 운영 후보로 확정하지 않는다.
- 관리형 스위치 증거가 끝까지 없으면 최대 판정은
  `PASS_WITH_SWITCH_LIMITATION`이다.
