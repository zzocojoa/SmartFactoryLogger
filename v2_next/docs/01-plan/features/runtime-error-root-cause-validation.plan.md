# 운영 오류 전체 원인 검증 계획

> **Feature**: `runtime-error-root-cause-validation`
> **Version**: 1.0.2
> **Date**: 2026-07-17
> **Status**: Historical Plan Complete / Field Validation Completed
> **Level**: Dynamic
> **대상 사건**: 2026-07-16 SmartFactoryLogger 운영 오류 큐

> **역사적 상태 경계**: 이 문서는 당시 검증 계획을 보존한다. 실행은 완료됐으며,
> 현재 운영 상태와 후속 release 재검증 요구사항은
> [Completion Report](../../04-report/runtime-error-root-cause-validation.report.md)를 기준으로 한다.

---

## 1. 이 문서의 목적

### 1.1 목적

비개발자도 실제 서버 PC에서 무엇을, 왜, 어떤 순서로 확인해야 하는지
빠짐없이 실행할 수 있도록 전체 검증 절차를 정의한다.

이번 사건에는 서로 다른 세 문제가 함께 기록되어 있다.

1. 앱 시작 직후 `plc_driver` 오류 27회
2. 운전 중 `spot_image` 연결 타임아웃 2회
3. 별도 시각에 기록된 백엔드 `SystemExit: 3`

세 문제는 원인과 검증 방법이 다르므로 각각 따로 검증한 뒤, 동일 시간대의
통신·HTTP·CSV·메모리·브라우저 상태를 교차 확인한다.

### 1.2 이 계획이 답해야 하는 질문

- `plc_driver` 오류가 실제 PLC 장비 통신 실패인가, 앱 내부 데이터 변환 실패인가?
- 시작 직후 오류가 실제 데이터 생성과 CSV 기록에 어떤 영향을 주는가?
- SPOT 이미지 502가 장비, 네트워크, 서버 NIC, 앱 중 어디에서 시작되는가?
- 높은 이미지 요청률이 SPOT 타임아웃의 재발 조건인가?
- `SystemExit: 3`이 기존 백엔드 종료인가, 두 번째 백엔드 실행 실패인가?
- 오류가 누적된 뒤에도 현재 통신과 저장이 정상인지?
- 향후 수정이 이루어졌을 때 어떤 조건을 통과해야 운영 배포할 수 있는가?

### 1.3 관련 자료

- `<operator-profile>/Desktop/test/system.log`
- `<operator-profile>/Desktop/test/status.log`
- `<operator-profile>/Desktop/test/crash.log`
- `<operator-profile>/Desktop/test/observability_snapshot_20260716_180612.json`
- `<operator-profile>/Desktop/test/memory_snapshot_20260716_181039.json`
- `scripts/collect_operational_observability.ps1`
- `scripts/qa_spot_image_server.ps1`
- `docs/02-design/features/spot-camera-rest-api-conformance.design.md`
- `docs/03-analysis/spot-camera-rest-api-conformance.analysis.md`
- `docs/04-report/spot-camera-rest-api-conformance.server-validation.md`

---

## 2. 비개발자를 위한 용어 설명

| 용어 | 쉬운 설명 |
|------|-----------|
| `plc_driver` | EX·LS PLC와 SPOT 값을 모아 앱에서 사용할 한 묶음의 공장 데이터를 만드는 부분이다. 오류 이름이 `plc_driver`라고 해서 실제 PLC 장비 고장을 뜻하지는 않는다. |
| `diagnostics_age_ms` | SPOT 진단값이 수집된 후 얼마나 시간이 지났는지를 밀리초 숫자로 표시하는 값이다. |
| `ConnectTimeout` | 서버 PC가 제한 시간 안에 상대 장비와 TCP 연결을 시작하지 못한 상태다. HTTP 응답을 늦게 받은 것이 아니라 그 전 단계에서 연결이 성립하지 않은 것이다. |
| TCP `SYN` | 서버 PC가 상대 장비에 “연결을 시작하자”고 보내는 첫 패킷이다. |
| TCP `SYN-ACK` | 상대 장비가 “연결 요청을 받았다”고 응답하는 패킷이다. |
| `502` | SmartFactoryLogger가 SPOT에서 정상 결과를 받지 못해 화면에 반환한 서버 오류 코드다. |
| NIC | 서버 PC의 유선 또는 무선 네트워크 어댑터다. |
| 패킷 캡처 | 네트워크에서 오간 연결 요청과 응답을 시간 순서대로 저장하는 작업이다. |
| 콜드 스타트 | SmartFactoryLogger를 완전히 종료한 뒤 새로 실행하는 것이다. |
| 오류 큐 | 최근 오류를 보관하는 목록이다. 현재 장애가 복구되어도 과거 오류가 남아 있을 수 있다. |
| 반복 수 | 같은 오류가 여러 번 발생했을 때 합쳐 기록한 실제 발생 횟수다. |

---

## 3. 현재까지 확인된 사실

### 3.1 오류 큐 숫자의 의미

- 대기 항목은 3개다.
- 실제 반복 발생은 총 29회다.
- `plc_driver` 동일 오류 27회가 항목 1개로 합쳐져 있다.
- `spot_image` 오류 2회는 각각 별도 항목이다.
- 따라서 `backend 3건`은 실제 오류가 세 번만 발생했다는 뜻이 아니다.
- 위 숫자는 17:34:54에 시작한 마지막 백엔드 세션의 최근 오류 큐다. 하루 전체 로그의
  오류 수가 아니다.

### 3.2 `plc_driver` 확인 사실

- 발생 시간: 17:34:55부터 17:35:21까지 1초 간격으로 27회
- 메시지: `diagnostics_age_ms`에 빈 문자열 `""`이 들어와 숫자로 변환하지 못함
- 상태 변화: `Running -> Warning -> Offline -> Warning -> Running`
- 18:06 관측성 스냅샷과 17:34 마지막 세션 구간에서는 EX·LS PLC 연결 실패나 읽기
  실패가 기록되지 않음
- 오류가 멈춘 뒤 앱 상태가 다시 Running으로 복구됨

현재 가장 강한 가설은 다음과 같다.

```text
앱 시작 직후 SPOT 진단값이 아직 없음
-> diagnostics_age_ms를 빈 문자열로 만듦
-> plc_driver가 FactoryData를 생성하면서 숫자로 검증
-> 숫자 변환 실패
-> 최신 공장 데이터 생성 실패
```

### 3.3 SPOT 이미지 확인 사실

- 17:37:32: `ConnectTimeout`, 2,000ms, 앱 응답 502
- 17:42:11: `ConnectTimeout`, 2,015ms, 앱 응답 502
- 두 오류 모두 SPOT가 HTTP 오류 응답을 보낸 기록은 없음
- 오류 후 앱 상태는 각각 약 1분 안에 Running으로 복구됨
- 18:06 기준 최근 1분 이미지 요청 1,789건이 모두 성공함
- 관측 이미지 요청률은 약 29.8회/초였음

### 3.4 오프라인 전체 로그 추가 확인

Do 단계에서 `system.log` 전체 12,066개 JSON 레코드를 별도로 확인한 결과, 최근 오류 큐보다
넓은 범위의 사건이 확인되었다.

- 2026-07-16 하루 동안 `spot_image` 오류 레코드는 총 20개다.
- 그중 `ConnectTimeout`은 19개, 별도 `upstream-request-error`는 1개다.
- 시간 간격 10초를 기준으로 나누면 SPOT 오류 구간은 총 13개다.
- `plc_driver`의 동일 `diagnostics_age_ms=""` 변환 오류는 총 843개 레코드이며,
  10초 간격 기준 50개 구간으로 나뉜다.
- 같은 하루 전체 로그에는 Extruder 오류 234개와 LS PLC 오류 233개도 있다.
- 다만 마지막 17:34 세션의 `plc_driver` 27회 구간에는 Extruder/LS 오류가 동반되지 않았다.
- 성공한 백엔드 시작 36회를 전수 대조하자 36회 모두 시작 1~17초 안에 같은
  `diagnostics_age_ms` 오류가 발생했다.
- 그중 16회는 시작 뒤 120초 동안 Extruder와 LS 오류가 모두 0건이었다. 따라서 이 타입 오류는
  실제 EX·LS 통신 실패와 독립적으로 시작 시점마다 발생한 것으로 판정한다.

따라서 다음 두 문장은 동시에 참이다.

1. **마지막 17:34 구간**의 `plc_driver` 오류는 EX·LS 통신 실패보다 SPOT 진단값 타입
   변환과 직접 연결되어 있다.
2. **하루 전체 운영 상태**에는 별도의 EX·LS 실제 통신 오류 구간도 있었으므로 PLC 검증을
   생략할 수 없다.

### 3.5 백엔드 `SystemExit: 3` 확인 사실

- 17:55:03에 두 번째 frozen frontend 초기화 뒤 Uvicorn lifespan 시작 단계에서
  `SystemExit: 3`이 기록됨
- traceback의 `uvicorn/server.py` 106행은 bind 실패 분기가 아니라
  `lifespan.should_exit`이면 `STARTUP_FAILURE`로 종료하는 분기이며, 해당 상수 값은 `3`임
- 사건 버전의 앱 lifespan은 이미 살아 있는 PID의 단일 인스턴스 잠금을 만나면
  `RuntimeError("Instance already running")`를 발생시킴
- 기존 백엔드는 17:55:01과 그 뒤에도 HTTP 200을 계속 처리했고 새로운 성공 backend-start는 없음
- 따라서 첫 백엔드의 crash나 단순 포트 bind 추정이 아니라 **두 번째 앱 시작을 단일 인스턴스
  보호 로직이 거부한 사건**으로 확정함
- `crash.log`에는 2026-05-11부터 2026-07-16까지 `SystemExit: 3`이 총 11회 기록되어 있어
  단발성 사건이 아니다.

### 3.6 원인에서 우선 제외된 항목

- CSV queue 0/5000, drop 0
- 브라우저 오류 0
- 메모리 누수 의심 0
- EX·LS·SPOT 최신 통신 상태 정상
- 최근 1분 HTTP 5xx 0

이 항목들은 **18:06 스냅샷 시점의 현재 원인**으로 보이지 않지만, 하루 전체의 과거
장애를 배제하는 증거는 아니다. 현장 검증 중 상태가 변하지 않았는지 다시 교차 확인해야 한다.

---

## 4. 검증 범위

### 4.1 포함 범위

- 기존 증거 원본 보존과 시간 정렬
- 실제 서버 PC의 앱·패키지·프로세스·포트 확인
- 현재 정상 기준선 수집
- `plc_driver` 시작 오류 재검증
- EX·LS PLC 실제 통신 정상 여부 교차 검증
- 시작 오류가 실시간 데이터와 CSV 행에 미치는 영향 확인
- SPOT 정상 운전 상태의 앱 관측성 수집
- SPOT TCP 패킷, ping, NIC, 스위치 로그 수집
- SPOT 오류 발생 시 네트워크 계층 판정
- 정상 부하와 별도 부하 시험 분리
- 중복 백엔드 실행과 포트 점유 확인
- 메모리, CSV, 브라우저 오류, 오류 큐 보존 동작 확인
- 향후 수정 후 회귀 검증과 운영 배포 기준
- 증거 파일의 민감정보 제거와 보관 규칙

### 4.2 제외 범위

- 이번 Plan 단계에서 애플리케이션 로직 수정
- PLC 또는 SPOT 설정값 변경
- SPOT 펌웨어 업그레이드
- 운영 중 임의로 오류 큐 삭제
- 승인 없는 운영 서버 재시작
- 승인 없는 스위치 포트 재설정
- 승인 없는 장비 전원 재가동

---

## 5. 역할과 준비물

### 5.1 역할

| 역할 | 담당 작업 |
|------|-----------|
| 현장 운영자 | 앱 상태 유지, 정확한 발생 시각 기록, 화면 내보내기, 정상/이상 현상 기록 |
| 서버 관리자 | 관리자 PowerShell, `pktmon`, NIC 카운터, 프로세스·포트 확인 |
| 네트워크 관리자 | SPOT 연결 스위치 포트와 서버 연결 포트 로그 제공 |
| 개발 분석 담당 | 로그, JSON, PCAP, CSV 시간축 대조 및 최종 판정 |

한 사람이 여러 역할을 수행할 수 있지만, 각 작업의 결과 파일은 분리해서 남긴다.

### 5.2 필수 준비물

- SmartFactoryLogger가 실제로 실행되는 서버 PC
- 해당 서버 PC와 직접 통신하는 실제 SPOT 장비
- 서버 관리자 권한
- SPOT IP와 HTTP 포트 정보
- 백엔드 주소와 포트 정보, 기본값 `127.0.0.1:8000`
- 결과 저장 공간 최소 1GB
- 서버 PC와 스위치의 시간 동기화 상태
- 유지보수 시간 승인: 콜드 스타트와 부하 시험에만 필요
- 저장소 또는 필요한 PowerShell 스크립트 사본

### 5.3 검증 금지 조건

다음 중 하나라도 해당하면 재시작·부하 시험을 시작하지 않는다.

- 현재 생산 공정 중단 위험이 있음
- 결과 파일 저장 공간이 부족함
- 기존 `pktmon` 또는 다른 패킷 캡처가 실행 중임
- 서버 PC 시간이 맞지 않음
- SPOT IP 또는 대상 NIC를 확정하지 못함
- 운영 책임자의 재시작 승인이 없음
- 기존 로그와 내보내기 파일을 먼저 보존하지 않음

---

## 6. 우선순위 전체 목록

| 순위 | ID | 검증 항목 | 실행 위치 | 중단 위험 | 실행 조건 |
|------|----|-----------|-----------|-----------|-----------|
| P0 | SAFE-01 | 기존 증거 원본 보존 | 서버 PC | 없음 | 가장 먼저 |
| P0 | ENV-01 | 시간·버전·설치본·프로세스·포트 기록 | 서버 PC | 없음 | 가장 먼저 |
| P0 | BASE-01 | 현재 정상 기준선 수집 | 서버 PC | 없음 | 앱 실행 상태 |
| P1 | PLC-01 | `plc_driver` 데이터 타입 경로 확인 | 분석 PC | 없음 | 완료된 로그·코드 사용 |
| P1 | PLC-02 | 현재 설치본 콜드 스타트 90초 선택 검증 | 서버 PC | 앱 재시작 | 현재 버전 회귀 확인을 원할 때만 |
| P1 | PLC-03 | EX·LS PLC 통신 정상 교차 확인 | 서버 PC | 없음 | PLC-02와 동시에 |
| P1 | PLC-04 | 실시간 데이터·CSV 시간 공백 확인 | 서버 PC/분석 PC | 없음 | PLC-02 직후 |
| P1 | PLC-05 | SPOT 진단값 생성 후 자동 복구 확인 | 서버 PC | 없음 | PLC-02와 동시에 |
| P1 | SPOT-01 | 정상 운전 15분 앱 관측성 수집 | 서버 PC | 없음 | 앱과 카메라 정상 표시 |
| P1 | SPOT-02 | 같은 15분 SPOT TCP 패킷 수집 | 서버 PC | 없음 | 관리자 권한 |
| P1 | SPOT-03 | 같은 15분 ping 손실 수집 | 서버 PC | 없음 | 평소 ping 응답 확인 |
| P1 | SPOT-04 | NIC 카운터 전후 비교 | 서버 PC | 없음 | SPOT-01 전후 |
| P1 | SPOT-05 | 스위치·장비 로그 확보 | 네트워크/장비 | 없음 | 오류 발생 시 즉시 |
| P1 | SPOT-06 | 오류 시각 기준 전체 증거 대조 | 분석 PC | 없음 | SPOT 자료 수집 후 |
| P1 | PROC-01 | 백엔드 단일 프로세스·포트 소유 확인 | 서버 PC | 없음 | 정상 실행 중 |
| P1 | PROC-02 | `SystemExit: 3` 전후 기존 서버 생존 확인 | 분석 PC | 없음 | 기존 로그 사용 |
| P1 | COMMON-01 | CSV queue/drop, 메모리, 브라우저 오류 교차 확인 | 서버 PC | 없음 | 모든 현장 시험 중 |
| P2 | SPOT-07 | 정상 관측 시간 60분으로 연장 | 서버 PC | 없음 | 15분 미재현 시 |
| P2 | LOAD-01 | 앱 프록시 추가 부하 15분 시험 | 서버 PC | 부하 증가 | 유지보수 승인 필요 |
| P2 | LOAD-02 | 앱 중지 후 SPOT 직접 요청 비교 | 서버 PC | 앱 중단 | P1·LOAD-01 불충분 시 |
| P2 | PLC-NET-01 | PLC 패킷·ping 추가 조사 | 서버 PC | 없음 | 실제 PLC read failure가 있을 때만 |
| P2 | PROC-03 | 단일 인스턴스 보호 회귀 재현 | 테스트 PC | 두 번째 실행 | 향후 launcher 회귀 확인 시만 |
| P3 | REG-01 | 향후 `plc_driver` 수정 후 회귀 시험 | 테스트/서버 PC | 재시작 | 수정본이 있을 때만 |
| P3 | REG-02 | 향후 SPOT 수정 후 장시간 시험 | 서버 PC | 부하 가능 | 수정본이 있을 때만 |
| P3 | RELEASE-01 | 운영 배포 승인 판정 | 검토 회의 | 없음 | 모든 필수 증거 완료 후 |

---

## 7. P0: 모든 시험 전에 반드시 수행

### 7.1 SAFE-01 기존 증거 원본 보존

#### 목적

재시작이나 새 시험 때문에 기존 로그가 회전·덮어쓰기 되는 것을 방지한다.

#### 수행 방법

1. 별도 결과 폴더를 만든다.
2. 현재 `system.log`, `status.log`, `crash.log`를 복사한다.
3. 앱에서 관측성 내보내기와 메모리 내보내기를 다시 실행한다.
4. 파일 이름에 수집 시각을 포함한다.
5. 원본 파일은 수정하지 않는다.
6. 가능하면 각 파일의 SHA-256을 기록한다.

```powershell
$Out = Join-Path $env:USERPROFILE ("Desktop\runtime_validation_{0}" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Path $Out | Out-Null
Get-Date -Format o | Set-Content -LiteralPath "$Out\collection_started_at.txt"
```

파일 해시 예시:

```powershell
Get-ChildItem -LiteralPath "<OUTPUT_DIR>" -File |
  Get-FileHash -Algorithm SHA256 |
  Export-Csv "<OUTPUT_DIR>\file_hashes.csv" -NoTypeInformation -Encoding UTF8
```

#### 합격 기준

- 기존 6개 첨부 자료와 새 현장 자료가 서로 다른 폴더에 보존됨
- 원본 파일을 편집하거나 덮어쓰지 않음
- 모든 파일의 생성·수집 시각을 알 수 있음

### 7.2 ENV-01 환경과 실행 주체 기록

#### 기록 항목

- 검증 시작·종료 KST 시각
- SmartFactoryLogger 표시 버전
- 사용한 설치 파일 이름과 SHA-256
- 서버 PC 이름
- Windows 버전
- SPOT IP와 HTTP 포트, 공유용 문서에서는 마스킹
- 백엔드 포트
- 실행 중인 SmartFactoryLogger/Electron/백엔드 PID
- 백엔드 포트 8000을 소유한 PID
- 활성 NIC 이름, 링크 속도, MAC 주소, 공유용 문서에서는 마스킹
- 앱 화면에서 카메라가 표시되는지

프로세스와 포트 확인 예시:

```powershell
Get-Process | Where-Object { $_.ProcessName -match "SmartFactory|Electron" } |
  Select-Object ProcessName,Id,StartTime,Path

Get-NetTCPConnection -LocalPort 8000 -State Listen |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

시간 동기화 확인 예시:

```powershell
Get-Date -Format o
w32tm /query /status
```

#### 합격 기준

- 어느 설치본과 어느 프로세스를 검증했는지 다시 확인할 수 있음
- 포트 8000의 Listener 소유 PID가 하나임
- 모든 증거 시간을 KST 또는 UTC로 변환할 수 있음

### 7.3 BASE-01 현재 정상 기준선 수집

#### 목적

시험 전부터 존재한 이상과 시험 중 새로 생긴 이상을 구분한다.

#### 수집 항목

- `/health`
- `/stats`
- `/api/observability/errors`
- `/api/memory/state`
- `/api/memory/details`
- `/api/spot/config`
- EX·LS·SPOT 연결 상태와 최근 성공 시각
- HTTP 최근 60초 요청·오류·5xx·p95
- 오류 큐 항목 수와 반복 합계
- CSV queue, drop, lag
- 메모리 누수 의심·경고·오류
- 브라우저 오류 수

#### 합격 기준

- 시험 시작 시점의 모든 값을 파일로 보존함
- 기존 오류 큐를 삭제하지 않고 시작값을 기록함
- 이후에는 절대값이 아니라 시작값 대비 증가량으로 판단함

---

## 8. P1-A: `plc_driver` 전체 검증

### 8.1 왜 TCP·ping 검증과 분리하는가

현재 `plc_driver` 오류 메시지는 네트워크 연결 실패가 아니라 숫자 변환 실패다.
따라서 SPOT 이미지 검증에 사용하는 TCP 패킷·ping·NIC 검증으로 이 오류를 입증할 수
없다.

그러나 실제 PLC 고장이 아니라는 것을 확정하기 위해 같은 시간의 EX·LS PLC 연결 상태와
읽기 실패 수는 반드시 확인한다. 실제 `read_failures`가 증가할 때만 별도의 PLC 네트워크
검증으로 확장한다.

### 8.2 PLC-01 앱 내부 데이터 경로 확인

#### 확인할 경로

```text
SPOT 진단값 미수집
-> diagnostics_age_ms=""
-> real_plc가 값을 FactoryData로 전달
-> FactoryData는 Optional[float] 요구
-> Pydantic float_parsing 오류
-> source=plc_driver로 기록
```

#### 합격 기준

- 오류 로그의 필드명과 코드에서 빈 문자열을 만드는 필드가 동일함
- 빈 문자열이 숫자형 스키마까지 변환 없이 전달됨
- 동일 오류 27회가 시작 직후 연속 발생한 시간과 일치함
- 실제 PLC 연결 실패 메시지와 구분됨

이 항목은 기존 로그와 사건 버전 소스 대조로 이미 충족된 상태다. 성공한 백엔드 시작
36회 모두에서 1~17초 안에 같은 오류가 발생했고, 그중 16회는 이후 120초 동안 EX·LS 오류가
0건이었다. 따라서 사건 원인을 다시 입증하기 위한 현장 재시작은 필요하지 않다. 현장 재시작은
현재 설치본의 재현 여부나 데이터·CSV 영향, 향후 회귀를 확인하려는 경우에만 별도로 수행한다.

### 8.3 PLC-02 현재 설치본 콜드 스타트 90초 선택 검증

이 절차는 2026-07-16 사건의 직접 원인을 확정하기 위한 필수 절차가 아니다. 현재 설치된
1.0.16에서 같은 시작 오류가 남아 있는지 확인하려는 경우에만 유지보수 승인을 받고 수행한다.

#### 실행 전 조건

- 유지보수 시간 승인
- 생산 공정 영향 확인
- SAFE-01, ENV-01, BASE-01 완료
- 검증 담당자와 복구 담당자 대기

#### 실행 순서

1. 종료 직전 시각을 기록한다.
2. SmartFactoryLogger를 정상 종료한다.
3. 백엔드 포트 8000 Listener가 사라졌는지 확인한다.
4. 10초 후 SmartFactoryLogger를 한 번만 실행한다.
5. 실행 버튼이나 바로가기를 두 번 누르지 않는다.
6. 시작 시각을 기록한다.
7. 90초 동안 앱을 조작하지 않는다.
8. 90초 후 관측성·메모리 내보내기를 실행한다.
9. `system.log`, `status.log`, 최신 CSV를 복사한다.

#### 반드시 기록할 값

- 최초 `plc_driver` 오류 시각
- 마지막 `plc_driver` 오류 시각
- 실제 반복 횟수
- `diagnostics_age_ms` 입력값
- Running, Warning, Offline 전환 시각
- 첫 정상 `FactoryData` 생성 시각
- 첫 SPOT 진단 성공 시각
- EX·LS PLC `connected`, `read_failures`, `last_success_time`
- CSV 마지막 정상 행과 다음 정상 행의 시각

#### 현재 버전의 원인 검증 합격 기준

- `diagnostics_age_ms=""` 오류가 앱 시작 직후 재현됨
- 오류 발생 중에도 EX·LS PLC 연결은 유지되고 `read_failures`가 증가하지 않음
- SPOT 진단값 준비 후 오류가 멈추고 `diagnostics_age_ms`가 숫자가 됨
- 앱 상태가 별도 수동 조치 없이 Running으로 복구됨

위 조건이 모두 맞으면 “PLC 장비 통신 고장”이 아니라 “시작 시 SPOT 진단값의 앱 내부
타입 처리 오류”로 확정한다.

#### 재현되지 않았을 때

- 실패가 아니라 `NOT_REPRODUCED`로 기록한다.
- 기존 27회 로그와 현재 실행의 SPOT 진단 준비 순서를 비교한다.
- 앱 버전과 설정이 기존 사건 당시와 같은지 확인한다.
- 재시작을 반복하지 말고 분석 담당자가 다음 실행 필요성을 판단한다.

### 8.4 PLC-03 실제 PLC 통신 정상 교차 확인

#### 합격 기준

- EX 연결 `true`
- LS 연결 `true`
- EX·LS 최근 성공 시각이 계속 갱신됨
- EX·LS `read_failures` 증가량 0
- backoff 증가량 0
- reconnect/recovery가 불필요하거나 증가량 0

#### 별도 PLC 네트워크 조사로 전환하는 조건

다음 중 하나가 발생할 때만 `PLC-NET-01`을 실행한다.

- EX 또는 LS `connected=false`
- `read_failures` 증가
- PLC 응답 timeout 또는 socket 오류
- PLC backoff/reconnect 증가
- 같은 시각에 공장 네트워크 장애가 기록됨

`diagnostics_age_ms` 숫자 변환 오류만 존재한다면 PLC ping·패킷 캡처는 하지 않는다.

### 8.5 PLC-04 실시간 데이터와 CSV 공백 확인

CSV queue drop 0은 “생성된 행을 버리지 않았다”는 뜻이다. `FactoryData` 자체가 만들어지지
않은 시간은 queue drop에 나타나지 않을 수 있으므로 별도로 확인한다.

#### 확인 방법

1. 앱 시작 전 마지막 CSV 행의 시각을 찾는다.
2. 오류 27회 구간의 CSV 행 존재 여부를 찾는다.
3. 복구 후 첫 CSV 행의 시각을 찾는다.
4. 정상 수집 주기와 비교해 빠진 행 수를 계산한다.
5. 화면의 최신 데이터 시각도 같은 구간과 비교한다.

#### 판정

| 결과 | 판정 |
|------|------|
| 오류 구간에 CSV 행이 없고 복구 후 재개 | 시작 오류로 데이터 생성 공백 발생 |
| CSV 행은 있으나 진단 필드만 비어 있음 | 일부 필드 실패로 격리됨, 전체 행 손실 아님 |
| CSV queue drop 증가 | 별도의 CSV 저장 문제도 함께 발생 |
| 화면만 멈추고 CSV는 정상 | 프런트 표시 또는 API 전달 문제 추가 조사 |

### 8.6 PLC-05 자동 복구 확인

#### 합격 기준

- 오류가 계속 무한 반복되지 않음
- SPOT 진단 준비 후 `diagnostics_age_ms`가 유효한 숫자로 바뀜
- 최신 데이터 시각이 다시 갱신됨
- 상태가 Running으로 돌아옴
- 수동 재연결, 설정 저장, 장비 재부팅이 필요하지 않음

---

## 9. P1-B: SPOT `ConnectTimeout` 전체 검증

### 9.1 실행 원칙

- 실제 SmartFactoryLogger와 실제 SPOT가 통신하는 서버 PC에서 수행한다.
- 최초 시험은 앱을 평소처럼 실행한 정상 운전 상태에서 수행한다.
- 앱 관측성, TCP 패킷, ping을 같은 15분 동안 동시에 수집한다.
- NIC 카운터는 시작 직전과 종료 직후를 비교한다.
- 최초 시험에는 추가 이미지 부하를 넣지 않는다.
- 오류가 발생해도 즉시 앱을 재시작하지 않는다.
- 오류 발생 후 복구를 확인하기 위해 최소 60초 더 수집한다.

### 9.2 SPOT-01 앱 관측성 15분 수집

저장소 루트의 일반 PowerShell에서 실행한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\collect_operational_observability.ps1 `
  -ApiBase http://127.0.0.1:8000 `
  -Samples 90 `
  -IntervalSec 10 `
  -TimeoutSec 10 `
  -OutputRoot "<OUTPUT_DIR>\observability"
```

#### 반드시 확인할 값

- `/api/spot/image.jpg` 요청 수와 초당 요청률
- 이미지 success, failure, 5xx 증가량
- 전체 HTTP 5xx 증가량
- 오류 큐 `spot_image` 반복 증가량
- 오류 타입 `ConnectTimeout` 증가량
- 각 오류의 정확한 KST/UTC 시각
- SPOT 온도 poll 성공·실패
- SPOT 진단 성공·실패
- EX·LS PLC 성공·실패
- HTTP p95
- 메모리 및 CSV 상태

### 9.3 SPOT-02 TCP 패킷 15분 수집

관리자 PowerShell에서 기존 캡처가 없는지 확인한다.

```powershell
pktmon status
```

캡처 시작:

```powershell
$SpotIp = "<SPOT_IP>"
$Out = "<OUTPUT_DIR>"

pktmon filter remove
pktmon filter add SpotHttp -i $SpotIp -t TCP -p 80
pktmon start --capture --comp nics --pkt-size 128 `
  --file-name "$Out\spot_tcp.etl" `
  --file-size 512 `
  --log-mode circular
```

캡처 종료와 변환:

```powershell
pktmon stop
pktmon etl2pcap "<OUTPUT_DIR>\spot_tcp.etl" `
  --out "<OUTPUT_DIR>\spot_tcp.pcapng"
pktmon filter remove
```

Wireshark 표시 필터:

```text
ip.addr == <SPOT_IP> && tcp.port == 80
```

연결 실패 후보 필터:

```text
ip.addr == <SPOT_IP> && tcp.port == 80 &&
(tcp.flags.syn == 1 || tcp.analysis.retransmission)
```

#### 반드시 측정할 값

- 앱 오류 시각과 같은 TCP 연결의 최초 SYN 시각
- SYN-ACK 수신 여부와 시각
- SYN 재전송 횟수
- TCP RST 수신 여부
- 연결 후 HTTP 요청 전송 여부
- HTTP 응답 시작 여부
- 정상 연결의 SYN에서 SYN-ACK까지 시간 분포

### 9.4 SPOT-03 ping 손실 15분 수집

다른 PowerShell 창에서 실행한다.

```powershell
$SpotIp = "<SPOT_IP>"
$Out = "<OUTPUT_DIR>"
$deadline = (Get-Date).AddMinutes(15)

while ((Get-Date) -lt $deadline) {
    $at = (Get-Date).ToString("o")
    $raw = & ping.exe -n 1 -w 1000 $SpotIp 2>&1
    [ordered]@{
        at        = $at
        exit_code = $LASTEXITCODE
        output    = ($raw -join " ")
    } |
    ConvertTo-Json -Compress |
    Add-Content -LiteralPath "$Out\ping.jsonl" -Encoding UTF8
    Start-Sleep -Seconds 1
}
```

#### 주의

SPOT가 평소부터 ping에 응답하지 않는다면 ping 실패는 장애 증거로 사용할 수 없다.
시험 시작 전에 정상 ping 3회 이상이 성공하는지 먼저 확인한다.

### 9.5 SPOT-04 NIC 카운터 전후 비교

시작 전:

```powershell
Get-NetAdapterStatistics |
  Select-Object Name,ReceivedBytes,SentBytes,
    ReceivedPacketErrors,OutboundPacketErrors,
    ReceivedDiscardedPackets,OutboundDiscardedPackets |
  Export-Csv "<OUTPUT_DIR>\nic_before.csv" -NoTypeInformation -Encoding UTF8
```

종료 후:

```powershell
Get-NetAdapterStatistics |
  Select-Object Name,ReceivedBytes,SentBytes,
    ReceivedPacketErrors,OutboundPacketErrors,
    ReceivedDiscardedPackets,OutboundDiscardedPackets |
  Export-Csv "<OUTPUT_DIR>\nic_after.csv" -NoTypeInformation -Encoding UTF8
```

#### 합격 기준

- 서버가 사용하는 NIC의 packet error 증가량 0
- discard 증가량 0
- 시험 중 링크 down/up Windows 이벤트 없음

### 9.6 SPOT-05 스위치와 장비 로그

오류가 발생하면 네트워크 관리자에게 정확한 시작·종료 시각과 다음 자료를 요청한다.

- SPOT 연결 포트 Link up/down 및 flap
- 서버 연결 포트 Link up/down 및 flap
- CRC/FCS 오류
- input/output error
- drop/discard
- 속도 및 duplex 변경
- STP 재계산 또는 포트 차단
- PoE 장비라면 전원 협상·리셋
- 스위치 CPU 또는 포트 과부하
- 가능하면 SPOT 장비의 같은 시각 CPU·연결·HTTP 서비스 로그

### 9.7 SPOT-06 종합 판정표

| 관측 결과 | 우선 판정 | 다음 조치 |
|-----------|-----------|-----------|
| ping 손실과 SYN 무응답이 같은 시각 발생 | 장비 전체 또는 네트워크 경로 장애 | 스위치·장비 로그 대조 |
| ping 정상, SYN 재전송, SYN-ACK 없음 | SPOT HTTP 연결 수락 지연 또는 TCP 80 경로 문제 | 장비 연결 한계·HTTP 서비스·스위치 확인 |
| SYN-ACK이 정상 시간에 도착했는데 앱은 ConnectTimeout | 서버 PC TCP 계층 또는 앱 HTTP client 조사 | Windows TCP 이벤트·앱 연결 풀 분석 |
| 오류 시각에 서버에서 SYN 자체가 보이지 않음 | 앱 내부에서 실제 connect 이전에 대기했을 가능성 | 앱 lock·pool·timeout 경로 분석 |
| TCP 연결 후 HTTP 응답이 오지 않음 | Connect가 아니라 응답 지연에 가까움 | 로그의 실제 timeout type 재확인 |
| NIC error/discard 증가 | 서버 NIC·드라이버·케이블·스위치 포트 | 물리 연결 점검 |
| 스위치 CRC/FCS 증가 또는 link flap | 물리 네트워크 문제 | 케이블·포트·속도/duplex 교체 점검 |
| 높은 요청률에서만 실패하고 직접 저부하 정상 | SPOT 처리량 또는 연결 압력 가능성 | LOAD-01/02 비교 |
| SPOT 온도·진단도 같은 시각 실패 | 장비 전체 요청 처리 또는 공통 네트워크 문제 | 장비 전체 로그 확인 |
| 이미지만 실패하고 온도·진단 정상 | 이미지 HTTP 서비스 또는 이미지 요청 부하 문제 | 이미지 경로 집중 분석 |
| 15분 오류 없음 | 비재현, 원인 부정 아님 | SPOT-07로 60분 연장 또는 재발 대기 |

---

## 10. P1-C: 백엔드 중복 실행 검증

### 10.1 PROC-01 정상 상태의 단일 실행 확인

#### 수행 방법

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen |
  Select-Object LocalAddress,LocalPort,OwningProcess

Get-Process | Where-Object { $_.ProcessName -match "SmartFactory|Electron" } |
  Select-Object ProcessName,Id,StartTime,Path
```

각 `OwningProcess`를 `Get-Process -Id <PID>`로 대조한다.

#### 합격 기준

- 포트 8000 Listener 소유 프로세스가 하나임
- 앱 한 번 실행 시 백엔드가 한 번만 시작됨
- 동일 PID와 시작 시간이 로그의 세션 정보와 일치함

### 10.2 PROC-02 기존 `SystemExit: 3` 판정

#### 확인할 증거

- 17:55:03 직전 기존 서버 HTTP 200
- 17:55:03의 새 `Frontend static root resolved`
- 같은 시각 Uvicorn startup의 `SystemExit: 3`
- 17:55:03 직후 기존 서버 HTTP 200
- 같은 시간의 앱/Electron launcher 로그
- Windows 포트 소유 PID 기록이 있으면 함께 대조

#### 확정 조건

다음 증거가 서로 일치하므로 “두 번째 앱 시작이 단일 인스턴스 보호 로직에서 거부됨”으로
확정한다.

- traceback의 Uvicorn 106행이 bind 실패가 아닌 lifespan startup 실패 분기와 일치함
- `STARTUP_FAILURE` 상수 값이 `3`임
- 사건 버전의 lifespan이 살아 있는 기존 PID를 감지하면 명시적으로 시작을 거부함
- 두 번째 frontend 초기화 뒤 새 backend-start는 없고, 첫 백엔드는 HTTP 200을 계속 처리함

당시 PID와 포트 소유자 자료는 향후 운영 증거를 더 명확히 하는 보강 자료이지, 이번 사건의
원인 확정에 필요한 필수 조건은 아니다.

### 10.3 PROC-03 재현 제한

- 이번 사건 원인 확정을 위해 의도적인 재현을 수행하지 않는다.
- 향후 launcher 회귀 검증이 필요할 때만 테스트 PC에서 수행한다.
- 운영 서버에서는 재현하지 않는다. 불가피한 유지보수 검증은 별도 승인과 복구 담당자가 필요하다.
- 재현할 때는 기존 PID·잠금 파일·포트 소유자와 첫 서버 생존을 함께 기록한다.
- 테스트가 끝나면 두 번째 프로세스가 남아 있지 않은지 확인한다.

---

## 11. P1-D: 공통 교차 검증

### 11.1 COMMON-01 통신

- EX connected
- LS connected
- SPOT 최근 온도 성공
- 각 장비 last_success_time 증가
- read_failures 증가량
- backoff 증가량
- recovery 증가량

### 11.2 COMMON-02 HTTP

- 최근 60초 request_count
- error_count
- 4xx·5xx
- p95 latency
- `/api/spot/image.jpg` 요청률·성공·실패
- `/api/data` 성공 여부
- `/health` 성공 여부

### 11.3 COMMON-03 오류 큐

- queue_size 시작값과 종료값
- repeat_total 시작값과 종료값
- `plc_driver` 반복 증가량
- `spot_image` 반복 증가량
- 마지막 오류 시각
- 현재 건강 상태가 정상이어도 과거 오류가 대기 상태로 남는지

오류 큐의 항목 수와 현재 장애 상태를 같은 의미로 해석하지 않는다.

### 11.4 COMMON-04 CSV

- queue 현재값·용량
- drop 증가량
- lag
- 마지막 저장 성공 시각
- 시작 오류 구간의 실제 행 존재 여부
- 정상 복구 후 행 저장 재개 여부

### 11.5 COMMON-05 메모리

- RSS와 private bytes
- thread count
- leak_suspects
- budget severity
- PLC history collector 상태와 latency
- SPOT image state

단일 스냅샷에서 `leak_suspects=0`은 해당 시점에 감지된 누수 후보가 없다는 뜻이다.
장기 누수 전체를 부정하는 근거로 사용하지 않는다.

### 11.6 COMMON-06 브라우저

- browser error count
- 개발자 콘솔 오류가 있다면 발생 시각과 메시지
- 이미지 오류 화면 표시 시각
- 이미지 자동 복구 시각

브라우저 오류가 0이고 백엔드 502가 존재하면 오류는 브라우저 코드보다 백엔드와 SPOT
사이에서 발생한 것으로 우선 판정한다.

---

## 12. P2: P1으로 확정되지 않을 때만 수행

### 12.1 SPOT-07 정상 관측 60분 연장

- P1의 관측성·TCP·ping·NIC 절차를 동일하게 유지한다.
- 패킷 파일은 512MB 원형 모드로 제한한다.
- 15분 무오류를 “문제 없음”으로 결론 내리지 않는다.
- 60분에도 무오류면 `NOT_REPRODUCED`로 기록하고 재발 시 자동 수집 체계를 검토한다.

### 12.2 LOAD-01 앱 프록시 추가 부하 시험

#### 주의

이 시험은 이미지 요청을 추가하므로 정상 관측과 결과를 섞지 않는다. 유지보수 승인 후
실행한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\qa_spot_image_server.ps1 `
  -BackendBaseUrl http://127.0.0.1:8000 `
  -SpotIp "<SPOT_IP>" `
  -ObservationSeconds 900 `
  -LogLookbackMinutes 30 `
  -OutputPath "<OUTPUT_DIR>\spot_image_load_test.json"
```

#### 해석 주의

- 대시보드 카메라 요청이 계속되면 두 요청자가 동시에 부하를 만든다.
- 이 경우 결과는 “정상 단일 사용자 시험”이 아니라 “다중 요청자 스트레스 시험”이다.
- 실패하면 요청률과 첫 오류 시각을 반드시 기록한다.
- 성공해도 실제 간헐 장애가 없다고 단정하지 않는다.

### 12.3 LOAD-02 SPOT 직접 요청 비교

#### 목적

앱 프록시를 통과할 때만 실패하는지, 앱을 제외하고 SPOT에 직접 요청해도 실패하는지
구분한다.

#### 실행 조건

- 생산 영향 승인
- SmartFactoryLogger와 백엔드를 완전히 중지할 수 있음
- SPOT 직접 URL과 포트를 확정함
- TCP·ping·NIC 캡처를 동일하게 수행함

#### 판정

| 직접 SPOT | 앱 프록시 | 판정 |
|-----------|-----------|------|
| 정상 | 실패 | 앱 부하·연결 풀·중재 경로 우선 조사 |
| 실패 | 실패 | SPOT 장비 또는 네트워크 우선 조사 |
| 정상 | 정상 | 간헐 장애 비재현 |
| 실패 | 정상 | 시험 방식·캐시·직접 클라이언트 조건 재확인 |

### 12.4 PLC-NET-01 실제 PLC 네트워크 조사

이 항목은 EX·LS `read_failures`, disconnect, socket timeout이 실제로 증가할 때만 수행한다.

- 해당 PLC IP ping
- PLC 포트 TCP 또는 프로토콜 패킷 캡처
- 서버 NIC 카운터
- PLC 연결 스위치 포트 로그
- PLC 장비 로그
- `plc_driver` 숫자 변환 오류와 별도 사건 번호로 관리

---

## 13. P3: 향후 수정 후 필수 회귀 검증

현재 요청은 원인 조사만이며 로직을 수정하지 않는다. 아래 항목은 향후 수정본이 생길 때
반드시 실행할 운영 배포 기준이다.

### 13.1 REG-01 `plc_driver` 수정 후

- 단위 테스트: 진단값 미수집 상태
- 단위 테스트: `diagnostics_age_ms` 숫자 상태
- 단위 테스트: future clock 또는 stale 상태
- 통합 테스트: 빈 문자열이 `FactoryData`로 전달되지 않음
- 콜드 스타트 최소 3회
- 각 시작의 `plc_driver` validation error 0
- EX·LS PLC 통신 성공 유지
- 초기 90초 데이터·CSV 공백 없음 또는 승인된 명시적 초기화 행만 존재
- Warning/Offline 비정상 하강 없음
- SPOT 진단 준비 후 정상 숫자 갱신

### 13.2 REG-02 SPOT 수정 후

- 정상 운전 15분 무오류
- 필요 시 60분 안정성 시험
- 이미지 요청률 기록
- 이미지 5xx 증가량 0
- SPOT 온도·진단 실패 증가량 0
- EX·LS 실패 증가량 0
- TCP 재전송과 ping 손실 비정상 증가 없음
- CSV drop 0
- 메모리 누수 후보 0
- 브라우저 오류 0

### 13.3 RELEASE-01 배포 승인

다음 조건을 모두 충족하기 전에는 운영 배포 완료로 표시하지 않는다.

- PLC 시작 오류 원인과 영향 범위 확정
- SPOT 타임아웃 하위 계층 확정 또는 재현 불가 상태와 감시 대안 승인
- 중복 백엔드 실행 원인 확정 또는 별도 운영 리스크로 승인
- 필수 증거 파일 누락 없음
- 민감정보 제거본 검토 완료
- 수정이 있다면 회귀 시험 완료
- 설치본 버전과 SHA-256 기록
- 실패 시 되돌릴 설치본과 절차 준비

---

## 14. 성공 기준

### 14.1 조사 완료 기준

- [ ] 세 사건을 하나의 원인으로 합치지 않고 별도로 판정함
- [ ] `plc_driver` 오류의 앱 내부 데이터 경로를 증거로 확인함
- [ ] 같은 시간의 EX·LS 통신 상태로 실제 PLC 고장 여부를 판정함
- [ ] 시작 오류 구간의 실시간 데이터와 CSV 영향 범위를 확인함
- [ ] SPOT 오류 시각에 앱·TCP·ping·NIC·스위치 중 확보 가능한 증거를 모두 대조함
- [ ] SPOT 하위 원인을 장비·네트워크·서버·앱 중 하나로 확정하거나 `NOT_REPRODUCED`로 명시함
- [ ] `SystemExit: 3`을 기존 서버 종료와 두 번째 실행 실패 중 하나로 판정함
- [ ] 메모리·CSV queue·브라우저 오류가 원인인지 아닌지 증거로 기록함
- [ ] 현재 정상과 과거 누적 오류를 구분함
- [ ] 원본과 공유용 정제본을 분리 보존함

### 14.2 결과 상태 정의

| 상태 | 의미 |
|------|------|
| `PASS_CONFIRMED` | 가설이 현장 증거로 확인됨 |
| `PASS_EXCLUDED` | 해당 계층이 원인이 아님을 충분히 확인함 |
| `NOT_REPRODUCED` | 관측 시간에 현상이 다시 발생하지 않음 |
| `INCONCLUSIVE` | 증거가 부족하거나 서로 충돌함 |
| `BLOCKED` | 권한·운영 승인·장비 로그 부족으로 실행하지 못함 |
| `FAIL_NEW_ISSUE` | 기존 사건과 다른 새 오류가 발견됨 |

`NOT_REPRODUCED`는 `PASS_CONFIRMED`와 같은 의미가 아니다.

---

## 15. 증거 산출물 체크리스트

### 15.1 공통

- [ ] `collection_started_at.txt`
- [ ] 앱 버전과 설치본 SHA-256
- [ ] 서버 PC 시간 동기화 결과
- [ ] 프로세스·PID·포트 소유자 목록
- [ ] 검증 시작·종료 시각
- [ ] 운영자 관찰 메모

### 15.2 PLC 시작 검증

- [ ] 시작 전·후 `system.log`
- [ ] `status.log`
- [ ] 관측성 내보내기
- [ ] 메모리 내보내기
- [ ] 시작 전·오류 중·복구 후 CSV 구간
- [ ] EX·LS health 시작값과 종료값
- [ ] 앱 실행·복구 시각

### 15.3 SPOT 검증

- [ ] 관측성 수집 폴더
- [ ] `spot_tcp.etl`
- [ ] `spot_tcp.pcapng`
- [ ] `ping.jsonl`
- [ ] `nic_before.csv`
- [ ] `nic_after.csv`
- [ ] 오류 발생 시각 메모
- [ ] 스위치 포트 로그
- [ ] 가능한 경우 SPOT 장비 로그
- [ ] 오류 후 최소 60초 복구 구간

### 15.4 중복 실행 검증

- [ ] Listener와 PID 목록
- [ ] 앱/Electron launcher 로그
- [ ] `crash.log`
- [ ] 오류 직전·직후 HTTP 성공 로그
- [ ] 테스트 환경 재현 결과가 있으면 별도 보존

---

## 16. 보안과 개인정보

- PCAP에는 내부 IP, MAC, HTTP 헤더가 포함될 수 있다.
- 원본 관측성 JSON에는 로컬 경로와 내부 장비 정보가 포함될 수 있다.
- 설정 파일 전체를 공유하지 않는다.
- 비밀번호, 토큰, 사용자 정보, 내부 URL은 공유본에서 제거한다.
- 원본은 접근 제한 폴더에 저장한다.
- 외부 공유에는 sanitized 산출물만 사용한다.
- 삭제가 필요하면 보존 기간과 담당자 승인을 먼저 확인한다.

---

## 17. 위험과 대응

| 위험 | 영향 | 가능성 | 대응 |
|------|------|--------|------|
| 운영 중 앱 재시작으로 데이터 공백 발생 | 높음 | 중간 | PLC 콜드 스타트는 유지보수 시간에만 수행 |
| 추가 이미지 부하가 장애를 새로 만듦 | 중간 | 높음 | 정상 관측과 부하 시험을 분리하고 LOAD-01은 P2로 제한 |
| 패킷 파일이 디스크를 가득 채움 | 높음 | 낮음 | 512MB 원형 모드와 128바이트 캡처 사용 |
| 기존 패킷 캡처를 중단함 | 중간 | 낮음 | 시작 전 `pktmon status` 확인, 기존 캡처가 있으면 중단 |
| 서버·스위치 시간이 달라 상관관계 오류 | 높음 | 중간 | 시작 전 시간 동기화 결과 기록 |
| 오류 큐를 지워 기존 증거 손실 | 높음 | 중간 | 시작값을 보존하고 검증 전 삭제 금지 |
| CSV drop 0을 데이터 무손실로 오해 | 높음 | 높음 | 실제 CSV 행 시각을 별도 비교 |
| ping 미지원 장비를 네트워크 장애로 오해 | 중간 | 중간 | 평상시 ping 기준선 확인, 미지원이면 판정에서 제외 |
| 중복 실행을 운영에서 재현해 포트 충돌 | 중간 | 중간 | 테스트 환경 우선, 운영은 읽기 전용 확인만 수행 |
| 원본 자료에 내부 주소 노출 | 높음 | 중간 | 원본과 정제본 분리, 외부 공유 전 검토 |
| 15분 무오류를 문제 해결로 오해 | 높음 | 높음 | `NOT_REPRODUCED`로 기록하고 필요 시 60분 연장 |

---

## 18. 중단과 복구 절차

### 18.1 즉시 중단 조건

- 생산 데이터가 예상보다 오래 갱신되지 않음
- EX 또는 LS 실제 연결이 끊김
- CSV drop 증가
- 서버 디스크 여유가 1GB 미만
- 메모리 또는 CPU가 운영 한계를 초과
- 패킷 캡처가 다른 운영 도구와 충돌
- SPOT 이미지뿐 아니라 온도·진단 전체가 지속 실패

### 18.2 복구 순서

1. 추가 부하 스크립트를 중지한다.
2. `pktmon stop`으로 캡처를 종료한다.
3. `pktmon filter remove`로 필터를 제거한다.
4. 원본 로그와 산출물을 보존한다.
5. SmartFactoryLogger가 Running으로 복구되는지 확인한다.
6. 필요할 때만 승인된 기존 설치본으로 재실행한다.
7. EX·LS·SPOT 통신과 CSV 저장을 다시 확인한다.
8. 복구 시각과 수행자를 기록한다.

이 계획은 설정과 로직을 변경하지 않으므로 데이터베이스 마이그레이션과 코드 롤백은
없다. 앱 재시작 또는 부하 시험에서 문제가 생겼을 때는 시험을 중지하고 기존 설치본의
정상 실행 상태로 되돌린다.

---

## 19. 실행 일정

| 단계 | 권장 시간 | 상태 |
|------|-----------|------|
| Plan 문서 작성 | 2026-07-17 | Complete |
| P0 증거 보존·환경 기록 | 20~30분 | Pending |
| P1 PLC 콜드 스타트 | 유지보수 시간 15~30분 | Pending approval |
| P1 SPOT 정상 관측 | 15분 + 준비·정리 30분 | Pending |
| P1 분석 | 자료 수집 후 1~2시간 | Pending |
| P2 장시간·부하·직접 비교 | P1 불충분 시 별도 승인 | Conditional |
| P3 수정 후 회귀 | 수정본이 있을 때 | Future |
| 완료 보고서 | 모든 필수 판정 후 | Pending |

---

## 20. 다음 PDCA 단계

1. 이 Plan을 운영자·서버 관리자·네트워크 관리자와 검토한다.
2. 실제 서버 PC의 유지보수 가능 시간을 승인받는다.
3. `$pdca design runtime-error-root-cause-validation`에서 다음을 확정한다.
   - 작업자별 정확한 실행 화면과 명령
   - 자동 수집 스크립트 사용 범위
   - 증거 파일 이름과 폴더 구조
   - 판정 보고서 형식
4. Design 승인 전에는 운영 서버 재시작과 부하 시험을 실행하지 않는다.
5. 현장 실행은 코드 구현이 아니라 증거 수집 작업으로 관리한다.
6. 결과는 `docs/03-analysis/runtime-error-root-cause-validation.analysis.md`에 기록한다.

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-07-17 | `plc_driver`, SPOT ConnectTimeout, 중복 백엔드, 공통 운영 상태를 포함한 전체 우선순위 검증 계획 작성 | Codex |
| 1.0.1 | 2026-07-17 | 최근 오류 큐와 하루 전체 로그 범위를 분리하고 반복 사건 범위를 반영 | Codex |
| 1.0.2 | 2026-07-17 | 시작 36회 상관분석과 단일 인스턴스 guard 증거로 PLC·SystemExit 판정 및 현장 재현 우선순위 정정 | Codex |
