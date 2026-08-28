# SPOT 실시간 이미지 v1.0.21 120분 canary

> 범위: `1.0.21` / `5971fc4fbdeec07ef65681a945319f0ae12d55cb`
> 분류: `PRIVATE_UNSIGNED_INTERNAL_CANARY_ONLY`
> 제품 승격: 허용하지 않음

## 목적

실제 SPOT 화면을 평상시처럼 유지하면서 최대 120분 동안 다음 항목을 함께 검증한다.

- 신규 `spot_image ConnectTimeout` 발생 여부
- 설치된 버전·commit·`app.asar`·backend bundle·설정 파일 identity
- backend PID와 포트 8000 소유권 유지
- source-port pool 대기·고갈·재사용 위반·transport failure
- 전체 SPOT 요청률과 이미지 upstream 요청률
- packet 캡처의 RST 전 응답 누락, handshake 후 무응답, SYN 재전송
- 동일 4-tuple 재사용 최소 75초 준수
- 120분 전체 화면의 연속 영상 갱신과 화면 오류 부재

이 키트는 설치본·제품 binary·설정·에러 큐를 변경하지 않는다. 패킷 본문은 최종
공유 자료에 보존하지 않는다.

Canary identity v4 이하 키트는 관찰 종료 시 부모 수집기와 전용 오류 감시 작업의
시계가 어긋나 정상 실행을 `trigger-monitor-job-failed`로 오판할 수 있으므로 다시
실행하지 않는다. identity v5는 관찰 종료 시 원자적 완료 요청을 전달하고, 감시
작업이 최종 증거를 저장한 뒤 종료하도록 고정한다.

## 진행 상태 표시

관측이 시작되면 콘솔에 30초마다 다음 상태가 표시된다.

```text
[CANARY PROGRESS] stage=observing elapsed=00:30:00 remaining=01:30:00 percent=25.0 expected_end=... backend_pid=... backend_alive=True
```

이 진행 표시는 로컬 시계와 Windows process 상태만 읽는다. SPOT 또는 backend API를
추가 호출하지 않으므로 검증 중 요청률을 높이지 않는다. 초기 관리자·디스크·pktmon
검사, 스위치 자료 입력, 방향 확인은 별도 `[STEP]`으로 표시된다. 120분 관찰이 끝난
뒤에는 `[POSTPROCESS PROGRESS] step=1/4`부터 `4/4`까지 관찰과 분리된 후처리 경과
시간을 표시한다.

## 파일 배치

전달받은 ZIP과 `.sha256.txt`를 기존 릴리스 폴더에 둔다.

```text
C:\Users\user\Desktop\SmartFactory\spot-realtime-image-performance-v1.0.21-5971fc4
```

ZIP을 이 폴더 바로 아래 새 폴더로 압축 해제한다. 구조는 다음과 같아야 한다.

```text
spot-realtime-image-performance-v1.0.21-5971fc4\
  smart-factory-logger-v2 Setup 1.0.21.exe
  server-evidence\20260821-190022\...
  SmartFactoryLogger_SPOT_Realtime_Image_v1021_Canary_...\
    run-spot-realtime-image-canary-120m-as-admin.cmd
```

## ZIP 검증

일반 PowerShell에서 ZIP 해시를 먼저 확인한다.

```powershell
$zip = ".\SmartFactoryLogger_SPOT_Realtime_Image_v1021_Canary_<commit>_<time>.zip"
$expected = (Get-Content -LiteralPath "$zip.sha256.txt" -Raw).Trim()
$actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
$actual
$expected
$actual -ceq $expected
```

마지막 값이 `True`가 아니면 압축을 풀거나 실행하지 않는다.

## 실행 전 조건

- v1.0.21 앱이 정상 화면에서 실행 중이어야 한다.
- 15분 증거 폴더 `server-evidence\20260821-190022`를 이동·수정하지 않는다.
- rollback 설치본은 다음 경로와 해시가 일치해야 한다.

```text
C:\Users\user\Desktop\SmartFactory\v1020_cd8cfa6_internal_private_server_deploy_20260821_R3\smart-factory-logger-v2 Setup 1.0.20.exe
F3C52902EFA2081A5060D4CD2C579E8B20B9DBA2DE34E174C946390BEDA0DE19
```

키트는 `preinstall-summary.json`의 `current_version=1.0.20`과
`health-before.json`의 `app_version=1.0.20`,
`build_git_commit=cd8cfa649203494cf087206cf656dc2197107ea1`을 함께 검증한다.
파일 해시가 맞더라도 이 직전 배포 기준선과 버전·commit이 다르면 preflight에서
중단한다.

- 에러 큐를 지우거나 앱을 재시작하지 않는다.
- 같은 수집기를 동시에 두 번 실행하지 않는다.
- 최소 5GB 여유 공간과 관리자 권한이 필요하다.

preflight는 누적 failure counter의 절대값이 0인지 강제하지 않는다. 먼저 현재 값을
`historical_failure_baseline`으로 기록하고 30초 동안 backend PID와 설정을 유지한 채
신규 증가분이 없는지 확인한다. 이 대기 중 진행 상태는 10초마다 로컬 시계와 process
상태만으로 표시하며 SPOT 요청을 추가하지 않는다. 안정성 확인 뒤 진단 snapshot을 한
번 읽어 기준선을 확정한다. 기존 에러 큐는 지우지 않으므로 2026-08-25 19:32 KST의
`spot_image upstream-request-error` 같은 과거 오류도 `recent_spot_errors`에 가능한
범위에서 함께 보존된다.

## 실행

압축을 푼 폴더에서 다음 파일 하나를 더블클릭한다.

```text
run-spot-realtime-image-canary-120m-as-admin.cmd
```

키트 검증과 preflight가 먼저 실행된다. preflight가 실패하면 120분 수집은 시작하지
않는다. 정상 실행 중에는 앱의 평상시 화면을 유지하고 탭 추가, 반복 새로고침, 부하
시험을 하지 않는다.

런타임 수집 자료는 Windows PowerShell 5.1의 장문 경로 실패를 피하기 위해 기본적으로
`%LOCALAPPDATA%\SFLCanary` 아래에 저장한다. preflight는 가장 긴 임시 증거 경로를
미리 계산하며 240자를 초과하면 `trigger-evidence-path-too-long`으로 수집 전에
중단한다. 이 경로에는 비식별 처리 전 자료가 포함될 수 있으므로 서버 사용자 계정의
로컬 폴더에 그대로 보존한다.

관리형 스위치 화면을 사용할 수 있으면 안내되는 폴더에 서버 포트와 SPOT 포트의
시작·종료 RX/TX, error, discard, CRC, link 상태를 저장한다. 접근 권한이나 관리
화면 자체가 없을 때만 `UNAVAILABLE`을 입력한다. 이 경우 런타임과 packet 검증은
계속되지만 최종 상태는 `PASS_WITH_SWITCH_LIMITATION`이다.

## 종료 판정

| 결과 | 의미 | 조치 |
|---|---|---|
| `SPOT_120M_GATE_PASS` | 앱·packet·source-port·화면·스위치 게이트 통과 | 증거 전달, production 승격은 별도 승인 |
| `SPOT_120M_PASS_WITH_SWITCH_LIMITATION` | 앱·packet 게이트 통과, 스위치 원인만 미배제 | 증거 전달, 제한사항 유지 |
| `SPOT_120M_EVIDENCE_HOLD` | 수집기 오류 또는 packet 보존 범위·진단 자료 불충분 | 제품 롤백 없이 자료 보존·검토 |
| `SPOT_120M_ROLLBACK_REQUIRED` | 관찰 구간의 신규 ConnectTimeout, failure delta, 재시작, 화면 오류 등 제품 hard failure | 증거 보존 후 정상 종료·검증된 v1.0.20 rollback |
| `SPOT_120M_PREFLIGHT_FAILED` | 수집 전 identity·권한·디스크·pktmon 조건 실패 | 원인 수정 전 실행 금지 |

중복 제거와 wall-clock/monotonic 보정을 거친
`same_four_tuple_monotonic_corrected.interval_ms_min >= 75000`,
`reset_before_response=0`,
`source_port_reuse_violation_count=0`을 함께 사용해 늦은 ACK/RST 위험을 간접 검증한다.
수집기는 모든 늦은 ACK의 발신 주체를 직접 확정한다고 주장하지 않는다.

요청률과 failure delta는 불변 파일 `canary-observation-start.json`과
`canary-observation-end.json`의 `observation-start-to-observation-end` 구간만 사용한다.
종료 스냅샷이 없거나 5초 안에 저장되지 않으면 이후 상태로 대체하지 않고
`EVIDENCE_HOLD` 처리한다. packet 변환·로그 수집·압축 중 상태는
`canary-postprocess-state.json`에 별도로 남으며 관찰 구간 제품 실패에 합산하지 않는다.
수집기 자체 실패도 별도 제품 hard gate가 없으면 `EVIDENCE_HOLD`이다.

관찰 시간이 끝나면 `trigger_monitor_completion_request.json`을 원자적으로 기록한다.
전용 감시 작업은 요청 ID와 관찰 종료 시각을 최종 요약·정지 신호에 연결한다. 이때
관찰 종료 시각은 감시 작업의 후처리 완료 시각으로 덮어쓰지 않는다.

failure counter 판정도 동일한 증거 연속성을 사용한다. 30초 안정성 확인을 통과한
`historical_failure_baseline`은 실행 전 이력으로 보존하고, 실제 판정은 관찰 시작과
관찰 종료 스냅샷을 비교한다. 기존 누적값은 유지하되 120분
관측 중 신규 증가분이 하나라도 있으면 fail-closed로 `ROLLBACK_REQUIRED` 처리한다.
counter가 감소한 경우도 backend 상태 초기화 또는 증거 불연속으로 간주해 통과시키지
않는다.

`source_port_request_event_drop_count`는 통신 실패 수가 아니다. 정상 요청을 포함하는
제한 크기 일반 요청 journal에서 오래된 항목이 밀려난 누적 횟수이므로 스냅샷에는
보존하되 failure gate에는 사용하지 않는다. 실제 실패 journal의 손실을 나타내는
`source_port_request_failure_event_drop_count`와 실제 failure counter의 신규 증가만
제품 hard failure로 판정한다.

packet 결과에는 인터페이스별 집계, 중복 SYN, 시각 역행, 양방향 RST, 관찰 범위 밖
제외 수, 원본·중복 제거·monotonic 보정 재사용 간격이 포함된다. 보정 상태가 확정되지
않으면 74초대를 제품 결함으로 단정하거나 기준을 완화하지 않고 `EVIDENCE_HOLD`한다.
수정 도구의 15분 진단에서 보정 후에도 75초 미만이고 캡처 이상이 없을 때만 제품
v1.0.22와 77초 quarantine 변경을 검토한다.

## 제공할 자료

실행 후 다음 자료를 전달한다.

1. `%LOCALAPPDATA%\SFLCanary\runtime_validation_*\runtime_validation_*_sanitized_share.zip`
2. 같은 실행 폴더의 `sanitized_share_sha256.txt`
3. `server-evidence\20260821-190022\canary-control-*` 폴더
4. 최종 CMD 화면

control 폴더에는 `historical-failure-baseline.json`, `canary-postflight.json`,
`canary-postprocess-state.json`이 포함되어야 한다. 공유 ZIP에는 두 관찰 경계와
`spot_http_framing_summary.json`이 포함되어야 한다.

`raw_private`에는 비식별 처리 전 네트워크 정보가 있을 수 있으므로 명시적 요청 전에는
공유하지 않는다.

## 롤백

`ROLLBACK REQUIRED`이면 먼저 수집 자료를 보존하고 SmartFactoryLogger를 정상 UI로
종료한다. 그다음 위에서 해시와 기준선 identity를 확인한 v1.0.20 `cd8cfa6...`
설치본을 실행한다. 강제 종료, 설정
수정, 에러 큐 삭제, 즉시 재수집은 하지 않는다.
