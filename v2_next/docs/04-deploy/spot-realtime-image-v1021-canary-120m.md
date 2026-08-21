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

## 진행 상태 표시

관측이 시작되면 콘솔에 30초마다 다음 상태가 표시된다.

```text
[CANARY PROGRESS] stage=observing elapsed=00:30:00 remaining=01:30:00 percent=25.0 backend_pid=... backend_alive=True checked_at=...
```

이 진행 표시는 로컬 시계와 Windows process 상태만 읽는다. SPOT 또는 backend API를
추가 호출하지 않으므로 검증 중 요청률을 높이지 않는다. 초기 관리자·디스크·pktmon
검사, 스위치 자료 입력, 방향 확인, packet 후처리 단계는 별도 `[STEP]` 또는
`[PROGRESS]` 문구로 표시된다.

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
C:\Users\user\Desktop\SmartFactory\rollback\smart-factory-logger-v2.Setup.1.0.16.exe
42A076B37ADA66CEAEE816128A1FC67C40CCD1C5417F9BDED5E885478974F615
```

- 에러 큐를 지우거나 앱을 재시작하지 않는다.
- 같은 수집기를 동시에 두 번 실행하지 않는다.
- 최소 5GB 여유 공간과 관리자 권한이 필요하다.

## 실행

압축을 푼 폴더에서 다음 파일 하나를 더블클릭한다.

```text
run-spot-realtime-image-canary-120m-as-admin.cmd
```

키트 검증과 preflight가 먼저 실행된다. preflight가 실패하면 120분 수집은 시작하지
않는다. 정상 실행 중에는 앱의 평상시 화면을 유지하고 탭 추가, 반복 새로고침, 부하
시험을 하지 않는다.

관리형 스위치 화면을 사용할 수 있으면 안내되는 폴더에 서버 포트와 SPOT 포트의
시작·종료 RX/TX, error, discard, CRC, link 상태를 저장한다. 접근 권한이나 관리
화면 자체가 없을 때만 `UNAVAILABLE`을 입력한다. 이 경우 런타임과 packet 검증은
계속되지만 최종 상태는 `PASS_WITH_SWITCH_LIMITATION`이다.

## 종료 판정

| 결과 | 의미 | 조치 |
|---|---|---|
| `SPOT_120M_GATE_PASS` | 앱·packet·source-port·화면·스위치 게이트 통과 | 증거 전달, production 승격은 별도 승인 |
| `SPOT_120M_PASS_WITH_SWITCH_LIMITATION` | 앱·packet 게이트 통과, 스위치 원인만 미배제 | 증거 전달, 제한사항 유지 |
| `SPOT_120M_EVIDENCE_HOLD` | packet 보존 범위나 진단 자료 불충분 | 재실행하지 말고 자료 검토 |
| `SPOT_120M_ROLLBACK_REQUIRED` | 신규 ConnectTimeout, runtime failure, 재시작, 화면 오류 등 | 증거 보존 후 정상 종료·v1.0.16 rollback |
| `SPOT_120M_PREFLIGHT_FAILED` | 수집 전 identity·권한·디스크·pktmon 조건 실패 | 원인 수정 전 실행 금지 |

`same_four_tuple_reuse_interval_ms_min >= 75000`, `reset_before_response=0`,
`source_port_reuse_violation_count=0`을 함께 사용해 늦은 ACK/RST 위험을 간접 검증한다.
수집기는 모든 늦은 ACK의 발신 주체를 직접 확정한다고 주장하지 않는다.

## 제공할 자료

실행 후 다음 자료를 전달한다.

1. `runtime_validation_*_sanitized_share.zip`
2. 같은 폴더의 `sanitized_share_sha256.txt`
3. `server-evidence\20260821-190022\canary-control-*` 폴더
4. 최종 CMD 화면

`raw_private`에는 비식별 처리 전 네트워크 정보가 있을 수 있으므로 명시적 요청 전에는
공유하지 않는다.

## 롤백

`ROLLBACK REQUIRED`이면 먼저 수집 자료를 보존하고 SmartFactoryLogger를 정상 UI로
종료한다. 그다음 위에서 해시를 확인한 v1.0.16 설치본을 실행한다. 강제 종료, 설정
수정, 에러 큐 삭제, 즉시 재수집은 하지 않는다.
