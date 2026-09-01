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
2. v1.0.22 설치 후 15분 진단
3. 15분 증거 보존 및 검토

15분 증거가 아직 identity에 묶이지 않았으므로 이 키트의 120분 launcher는
의도적으로 `EVIDENCE_HOLD`에서 멈춘다. 15분 결과를 검토한 후 별도의
commit-bound 120분 키트를 생성한다.

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

## 15분 진단 판정

다음 조건을 모두 확인한다.

- backend PID, config SHA256, build commit 유지
- 신규 transport/image/temperature 및 기타 failure delta 0
- failure event journal 신규 항목과 drop 0
- 보정된 동일 four-tuple 재사용 최소 간격 75초 이상
- `reuse violation`, pool wait, pool exhaustion 0
- 양방향 RST, 응답 누락, 실패 handshake, SYN 재전송 0
- SPOT 영상 지속 갱신 및 전체 앱 화면 신규 오류 없음

관리형 스위치 자료가 없으면 결과는 제한 판정으로 유지한다. 제품 hard failure가
확인된 경우에만 v1.0.20 복구본을 사용한다. 계측 불완전인 `EVIDENCE_HOLD`에서는
자동 롤백하거나 즉시 재실행하지 않는다.

## 제공할 증거

15분 실행 뒤 다음을 제공한다.

- `runtime_validation_*_sanitized_share.zip`
- `sanitized_share_sha256.txt`
- 해당 `canary-control-*` 폴더의 ZIP
- 15분 동안 영상 갱신과 화면 오류 여부에 대한 사용자 확인

원본 `raw_private` 폴더는 서버에서 삭제하지 않는다. 공유 ZIP은 원문 주소와
source port 값을 포함하지 않는 정제 증거만 사용한다.

## 운영 제한

- 이 키트와 설치본은 서명되지 않은 내부 검증용이다.
- 15분 통과만으로 production 승격을 승인하지 않는다.
- 120분 검증 전에는 v1.0.22를 운영 후보로 확정하지 않는다.
- 관리형 스위치 증거가 끝까지 없으면 최대 판정은
  `PASS_WITH_SWITCH_LIMITATION`이다.
