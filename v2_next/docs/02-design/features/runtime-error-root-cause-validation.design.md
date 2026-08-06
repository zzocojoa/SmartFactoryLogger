# 운영 오류 전체 원인 검증 상세 설계

> **Feature**: `runtime-error-root-cause-validation`
> **Version**: 1.1.1
> **Date**: 2026-07-17
> **Status**: Historical Design Complete / Field Execution Completed
> **Level**: Dynamic
> **Plan**: `docs/01-plan/features/runtime-error-root-cause-validation.plan.md`
> **대상 사건**: 2026-07-16 SmartFactoryLogger 운영 오류 큐

> **역사적 상태 경계**: 이 문서는 당시 현장 실행 설계를 보존한다. 실행은 완료됐으며,
> 현재 운영 상태와 후속 release 재검증 요구사항은
> [Completion Report](../../04-report/runtime-error-root-cause-validation.report.md)를 기준으로 한다.

---

## 1. 문서 목적과 범위

### 1.1 목적

이 문서는 실제 SmartFactoryLogger 서버 PC에서 비개발자 작업자와 네트워크 담당자가
같은 순서로 검증하고, 수집한 증거만으로 아래 세 사건의 하위 원인을 구분할 수 있도록
화면 절차, 명령, 역할, 파일 이름, 중단 조건과 판정 기준을 확정한다.

1. 마지막 17:34 세션의 앱 시작 직후 `plc_driver` 오류 27회
2. 마지막 오류 큐의 `spot_image` `ConnectTimeout` 2회
3. 백엔드 `SystemExit: 3`

위 27회와 2회는 마지막 세션의 최근 오류 큐 범위다. 오프라인 전체 로그에서는 같은 날
`plc_driver` 오류 843개 레코드와 SPOT 오류 20개 레코드가 확인되었다. 따라서 현장 분석은
항상 `최근 세션`, `하루 전체`, `재발 수집 실행`을 서로 다른 범위로 표시한다.

### 1.2 이번 Design의 결과물

- 작업자가 클릭해야 할 실제 화면과 버튼 순서
- PowerShell 창별 실행 명령과 실행 시점
- 앱·SPOT·PLC·서버 NIC·스위치에서 확보할 증거
- 한 실험이 다른 실험에 영향을 주지 않도록 분리한 검증 트랙
- 25개 검증 항목의 합격·실패·판정 불가 기준
- 원본 증거, 외부 공유용 정제본, 해시와 작업 메모의 보관 구조
- 장애 악화 시 즉시 멈추고 정상 운전으로 돌아가는 절차

### 1.3 하지 않는 일

- 앱 소스 코드, 설정, DB, 장비 설정을 변경하지 않는다.
- 오류 큐의 `비우기`를 누르지 않는다.
- 운영 중인 프로세스를 강제 종료하지 않는다.
- 운영 서버에서 의도적으로 백엔드를 두 번 실행하지 않는다.
- 승인 없이 SPOT 부하 시험, 앱 재시작, PLC 재연결, 스위치/NIC 설정 변경을 하지 않는다.
- 패킷 내용, 내부 IP, 장비 식별자, 계정 정보가 포함된 원본을 외부에 전송하지 않는다.

### 1.4 설계 원칙

1. **증거 우선**: 오류를 지우거나 재시작하기 전에 먼저 내보낸다.
2. **원인별 분리**: PLC, SPOT, 프로세스 충돌을 같은 원인으로 합치지 않는다.
3. **한 번에 한 변수**: 정상 운전 관찰과 부하 시험을 같은 실행에서 섞지 않는다.
4. **시간 동기화**: 모든 증거에 KST와 가능한 경우 UTC를 함께 기록한다.
5. **읽기 전용 우선**: 먼저 화면 새로고침, GET 조회, 패킷 관찰만 수행한다.
6. **운영 우선**: 생산 영향이 보이면 원인 규명보다 정상 운전 복구를 우선한다.
7. **판정 보수성**: 증거가 부족하면 추측하지 않고 `INCONCLUSIVE`로 기록한다.

---

## 2. 네 가지 검증 트랙

### 2.1 트랙 개요

```text
공통 사전 점검
    |
    +-- A. PLC 시작 트랙 -------- plc_driver 27회, EX/LS 통신, CSV 영향
    |
    +-- B. SPOT 수동 관찰 트랙 -- 앱 요청 + TCP + ping + NIC + 스위치
    |                                 |
    |                                 +-- 필요할 때만 SPOT 부하 트랙
    |
    +-- C. 프로세스 트랙 -------- SystemExit:3, 단일 인스턴스 guard, 두 번째 실행 거부
    |
    +-- D. 공통 건전성 트랙 ----- HTTP, 브라우저, 메모리, CSV, 복구 상태

각 트랙의 증거 -> 시간축 정렬 -> 가설별 판정 -> 검토자 승인
```

### 2.2 트랙을 분리하는 이유

| 트랙 | 확인하려는 오류 | 주된 질문 | 다른 트랙으로 대신할 수 없는 이유 |
|------|-----------------|-----------|-----------------------------------|
| A | 최근 27회 및 하루 전체 `plc_driver` 반복 | SPOT 진단값의 빈 문자열 변환 오류인가, 실제 EX/LS 통신 실패인가? | ping과 SPOT TCP만으로 앱 내부 데이터 변환과 CSV 영향을 알 수 없다. |
| B | 최근 2회 및 하루 전체 `spot_image` 오류 | 연결 요청이 서버, NIC, 네트워크, 장비 중 어디에서 막혔는가? | 앱 로그만으로 TCP SYN과 응답 유무를 볼 수 없다. |
| C | `SystemExit: 3` | 기존 서버가 죽었는가, 두 번째 실행이 단일 인스턴스 guard에서 거부되었는가? | 장비 통신 지표와 무관한 앱 시작 보호 경로이므로 별도로 판정한다. |
| D | 공통 상태 | 사건 전후에도 서비스와 저장이 정상인가? | 개별 오류가 복구되었어도 데이터 누락이나 메모리 문제가 남을 수 있다. |

### 2.3 필수 실행 순서

1. P0 공통 사전 점검과 원본 보존
2. P1-A PLC 과거 시작 36회 증거 대조 — 사건 원인 판정에 사용; 현재 버전 콜드 스타트는 선택 사항
3. P1-B SPOT 정상 운전 수동 관찰 — 15분 이상
4. P1-C 프로세스·포트 읽기 전용 확인
5. P1-D 공통 건전성·CSV 확인
6. P2 SPOT 부하 시험 또는 장비 직접 시험 — P1로 구분되지 않을 때만
7. 결과 정리와 2인 검토
8. 향후 패치가 생긴 뒤에만 P3 회귀·릴리스 게이트 수행

---

## 3. 역할과 승인 체계

### 3.1 역할

| 역할 | 필수 여부 | 책임 |
|------|-----------|------|
| 현장 작업자 | 필수 | 앱 화면 조작, 시간 기록, 정상 운전 확인, 중단 판단 |
| 서버 관리자 | 필수 | 관리자 PowerShell, `pktmon`, 프로세스·포트·NIC 증거 수집 |
| 네트워크 담당자 | SPOT 트랙 필수 | SPOT 연결 경로, 스위치 포트, VLAN, 링크·드롭 로그 제공 |
| 장비 담당자 | 필요 시 | SPOT 장비 상태·재부팅·자체 로그 확인, 장비 직접 시험 승인 |
| 분석 담당자 | 필수 | 모든 파일의 시간축 정렬과 판정표 작성 |
| 운영 승인자 | 재시작/부하 시 필수 | 유지보수 시간, 생산 영향, 중단·복구 승인 |

### 3.2 작업 전 승인표

다음 표가 채워지지 않으면 P0의 읽기 전용 증거 수집까지만 허용한다.

| 항목 | 기입 내용 |
|------|-----------|
| 작업 일시 | `YYYY-MM-DD HH:mm:ss KST` |
| 작업 종료 예정 | `YYYY-MM-DD HH:mm:ss KST` |
| 서버 식별자 | 외부 공유본에는 마스킹 |
| 앱 버전 | 설정 화면 또는 실행 파일 정보에서 확인 |
| 설치 패키지 SHA-256 | 패키지가 있을 때만 기록 |
| 현장 작업자 | 이름/연락 수단 |
| 서버 관리자 | 이름/연락 수단 |
| 네트워크 담당자 | 이름/연락 수단 |
| 운영 승인자 | 이름과 승인 시각 |
| 재시작 승인 | 예/아니요 |
| 부하 시험 승인 | 예/아니요 |
| 생산 중단 허용 | 예/아니요, 허용 시간 |
| 정상 복구 기준 | EX·LS·SPOT·CSV·HTTP가 모두 정상 |

### 3.3 작업자 간 음성 확인 문구

각 단계 시작 전에 현장 작업자가 아래처럼 읽고 서버 관리자가 확인한다.

> 지금 시작하는 단계는 `[단계 ID]`이며, 변경 여부는 `[읽기 전용/재시작/부하]`입니다.
> 시작 시각은 `[시각]`이고 중단 기준은 `[기준]`입니다. 증거 폴더는 `[경로]`입니다.

---

## 4. 실행 상태와 안전 게이트

### 4.1 한 번의 실행 상태

```text
PRECHECK
  -> BASELINE_CAPTURE
  -> TRACK_RUNNING
  -> POST_FAILURE_OBSERVE_60S       실패가 발생한 경우
  -> FINAL_CAPTURE
  -> STOP_COLLECTORS
  -> RECOVERY_CHECK
  -> HASH_AND_SANITIZE
  -> READY_FOR_ANALYSIS
```

### 4.2 단계별 진입 조건

| 상태 | 진입 조건 | 완료 조건 |
|------|-----------|-----------|
| `PRECHECK` | 역할과 시간이 정해짐 | 시간 동기화·디스크·관리자 권한·장비 주소 확인 |
| `BASELINE_CAPTURE` | 앱이 정상 운전 중 | 앱/오류 큐/NIC/프로세스/포트의 전 상태 저장 |
| `TRACK_RUNNING` | 해당 트랙 승인 완료 | 정해진 시간 관찰 또는 재현 완료 |
| `POST_FAILURE_OBSERVE_60S` | 오류 발생 | 오류 뒤 60초간 복구와 후속 요청 확인 |
| `FINAL_CAPTURE` | 관찰 종료 | 앱/오류 큐/NIC/CSV/로그의 후 상태 저장 |
| `STOP_COLLECTORS` | 최종 캡처 완료 | `pktmon`과 ping/수집기를 정상 종료 |
| `RECOVERY_CHECK` | 수집기 종료 | EX·LS·SPOT·HTTP·CSV 정상 확인 |
| `HASH_AND_SANITIZE` | 원본 폴더 닫힘 | 해시, 인덱스, 정제본 생성 |

### 4.3 즉시 중단 조건

다음 중 하나라도 발생하면 부하·재시작·직접 장비 시험을 멈춘다.

- 생산 데이터가 2개 이상의 예상 주기 동안 갱신되지 않는다.
- EX 또는 LS 통신이 `Offline`으로 바뀌고 60초 안에 복구되지 않는다.
- SPOT 영상이 멈추고 정상 운전에 필요한 상태로 60초 안에 돌아오지 않는다.
- CSV queue가 계속 증가하거나 drop이 1 이상 증가한다.
- HTTP 5xx가 연속 발생하거나 앱 UI가 응답하지 않는다.
- 서버 CPU·메모리·디스크가 현장 운영 기준을 넘어선다.
- 작업자가 실행 중인 명령이나 대상 IP/포트를 확신할 수 없다.
- 기존 `pktmon` 캡처 또는 필터가 다른 작업에서 사용 중이다.

### 4.4 중단 후 금지 사항

- 원인을 더 보려고 반복 클릭하거나 요청률을 높이지 않는다.
- 오류 큐를 비우지 않는다.
- 증거 복사 전에 앱이나 장비를 연속 재시작하지 않는다.
- 기존 프로세스를 확인하지 않고 새 앱을 실행하지 않는다.

---

## 5. 증거 저장 설계

### 5.1 실행 ID

실행 ID는 `YYYYMMDD_HHmmss_트랙명` 형식으로 만든다.

예: `20260717_181500_spot_passive`

### 5.2 폴더 구조

```text
runtime_validation_<실행ID>/
  00_run/
    run_manifest.json
    operator_notes.jsonl
    evidence_index.csv
    approvals.txt
  01_baseline/
    time_sync.txt
    process_before.csv
    port_before.csv
    nic_before.csv
    pktmon_filter_before.txt
    observability_ui_before.png
    memory_ui_before.png
  02_plc_startup/
    launch_timeline.txt
    system.log
    status.log
    crash.log
    observability_after_start.json
    csv_gap_analysis.csv
  03_spot_passive/
    app/
    network/
      spot_tcp.etl
      spot_tcp.pcapng
      ping_spot.jsonl
      nic_after.csv
      pktmon_status.txt
    switch/
      switch_port_log.txt
      switch_counter_before.txt
      switch_counter_after.txt
    device/
      spot_device_status.txt
  04_process/
    process_after.csv
    port_after.csv
    startup_attempt_timeline.txt
  05_common_health/
    http_summary.json
    browser_error.json
    csv_summary.json
    memory_export.json
  90_sanitized/
    README.txt
    evidence_index_sanitized.csv
  99_hashes/
    sha256_manifest.csv
```

없는 트랙 폴더는 빈 상태로 두어도 된다. 파일을 다른 폴더로 옮겨 원본 위치를
바꾸지 말고, 분석용 사본을 별도로 만든다.

### 5.3 실행 폴더 생성 명령

PowerShell에서 아래 명령을 실행한다. `<증거상위폴더>`와 `<실행ID>`는 현장 값으로
바꾼다. 경로에 공백이 있으면 따옴표를 유지한다.

```powershell
$EvidenceRoot = '<증거상위폴더>\runtime_validation_<실행ID>'
$Folders = @(
  '00_run','01_baseline','02_plc_startup','03_spot_passive\app',
  '03_spot_passive\network','03_spot_passive\switch','03_spot_passive\device',
  '04_process','05_common_health','90_sanitized','99_hashes'
)
$Folders | ForEach-Object {
  New-Item -ItemType Directory -Force -Path (Join-Path $EvidenceRoot $_) | Out-Null
}
```

### 5.4 `run_manifest.json` 필드

| 필드 | 필수 | 설명 |
|------|------|------|
| `run_id` | 예 | 실행 ID |
| `timezone` | 예 | `Asia/Seoul`, `UTC+09:00` |
| `server_id_masked` | 예 | 외부 공유 가능한 마스킹 식별자 |
| `app_version` | 예 | 실행 중인 앱 버전 |
| `installer_sha256` | 조건부 | 설치 패키지가 제공된 경우 |
| `backend_port` | 예 | 실제 수신 포트 |
| `spot_endpoint_masked` | 예 | 외부 공유본에는 마스킹 |
| `operators` | 예 | 역할별 담당자 |
| `started_at_kst` | 예 | 시작 시각 |
| `ended_at_kst` | 예 | 종료 시각 |
| `maintenance_approved` | 예 | 재시작 승인 여부 |
| `load_test_approved` | 예 | 부하 시험 승인 여부 |
| `stages` | 예 | 단계별 시작·종료·상태 |
| `final_result` | 예 | 전체 결과 또는 `PENDING` |

### 5.5 작업 메모 형식

`operator_notes.jsonl`은 한 줄에 하나의 사건을 기록한다.

```json
{"at_kst":"2026-07-17T18:22:11+09:00","stage":"SPOT-03","event":"ui_error","observation":"SPOT image 502 표시","action":"클릭하지 않고 60초 관찰","actor":"현장 작업자"}
```

반드시 기록할 사건은 다음과 같다.

- 앱 실행과 종료
- 수집기 시작과 종료
- SPOT 화면을 연 시각
- 오류가 화면에 보인 정확한 시각
- EX·LS·SPOT 상태 변화
- CSV 갱신 지연
- 네트워크 케이블·장비·스위치에 사람이 손댄 시각
- 중단 판단과 복구 행동

### 5.6 증거 인덱스

`evidence_index.csv` 열은 아래 순서를 사용한다.

```text
evidence_id,validation_id,collected_at_kst,source,relative_path,sha256,sensitivity,status,note
```

`sensitivity` 값은 `PUBLIC`, `INTERNAL`, `RESTRICTED` 중 하나다. 패킷 원본, 내부 IP,
장비 로그는 기본적으로 `RESTRICTED`다.

### 5.7 결과 상태

| 상태 | 의미 |
|------|------|
| `CONFIRMED` | 해당 가설을 직접 지지하는 증거가 있음 |
| `EXCLUDED` | 해당 가설과 양립할 수 없는 증거가 있음 |
| `NOT_REPRODUCED` | 정해진 조건에서 재발하지 않음. 원인 배제를 뜻하지 않음 |
| `INCONCLUSIVE` | 필요한 증거가 없거나 서로 충돌하여 판정 불가 |
| `BLOCKED` | 승인, 권한, 장비 접근 또는 환경 문제로 실행 못 함 |
| `NEW_ISSUE` | 기존 세 사건과 다른 신규 문제 발견 |

---

## 6. 실제 앱 화면 절차

## 6.1 운영/관측성 화면

### 진입

1. SmartFactoryLogger를 연다.
2. 설정 화면을 연다.
3. 왼쪽 항목에서 `운영/관측성`을 선택한다.
4. 화면 상단 시각이 현재 서버 시각과 맞는지 확인한다.

### 확인과 기록

1. `현재 상태`의 상태·설명·최근 시각을 화면 캡처한다. Windows에서는
   `Win+Shift+S`로 해당 영역을 선택한 뒤 `observability_ui_<시각>.png` 이름으로
   실행 폴더에 저장한다.
2. `통신 상태`에서 EX·LS·SPOT 상태와 최근 성공 시각을 기록한다.
3. `HTTP 응답`에서 요청, 에러, 5xx, p95를 기록한다.
4. `최근 오류`에서 backend/browser 개수와 최근 시각을 기록한다.
5. `백오프/복구`에서 백오프, 복구, 대기 시간을 기록한다.
6. `CSV 저장`에서 queue, drop, lag를 기록한다.
7. `메모리 연결`에서 누수 의심, 경고, 오류를 기록한다.
8. `상세 진단 원자료`를 펼친다.
9. `윈도 지표`에서 요청률, 에러율, p95, RPS, 누적 4xx/5xx와 SPOT image
   요청 수/RPS/client 수를 기록한다.
10. `에러 큐`에서 대기, 최근, 소스, 메시지, `source`별 반복 수를 기록한다.
11. `새로고침`을 한 번 누르고 새로고침 시각을 작업 메모에 적는다.

### 내보내기

1. `지표 내보내기` 영역을 연다.
2. `내보내기`를 한 번 누른다.
3. 완료 표시가 나타날 때까지 기다린다.
4. `경로 복사`로 저장 위치를 작업 메모에 붙여 넣는다.
5. `폴더 열기`로 실제 파일이 있는지 확인한다.
6. 원본 파일을 해당 실행의 `app` 또는 `05_common_health` 폴더로 복사한다.
7. 복사한 파일의 생성 시각과 크기를 `evidence_index.csv`에 기록한다.

### 절대 누르지 않는 버튼

- `에러 큐`의 `비우기`: 과거 오류와 반복 수가 삭제되어 비교가 불가능해진다.

## 6.2 메모리 화면

### 진입과 안전한 수집

1. 설정 화면의 `메모리`를 선택한다.
2. `메모리 진단`에서 현재 상태, 누수 의심, 마지막 GC, 마지막 수집 시각을 기록한다.
3. `새로고침`을 한 번 누른다.
4. `내보내기`를 한 번 누른다.
5. 저장된 파일을 `05_common_health/memory_export.json`으로 복사한다.

### SPOT 수동 관찰 중 누르지 않는 버튼

- `상세 추적 시작`: 추적 자체가 추가 부하를 만들 수 있다.
- `GC 전후 비교`: 강제 GC가 실행 상태와 지연시간을 바꿀 수 있다.
- `즉시 스냅샷`: 메모리 문제 전용 시험이 아닌 동안에는 사용하지 않는다.

이미 상세 추적이 켜져 있다면 임의로 끄지 말고 시작 상태를 기록한 뒤 분석 담당자에게
알린다. 기존 상태 변경도 실험 변수이기 때문이다.

## 6.3 SPOT 화면

1. 평소 운영자가 사용하는 SPOT 영상 화면을 연다.
2. 정상 운전과 같은 탭·창 수를 유지한다.
3. 수동 관찰 중에는 새로고침 연타, 탭 복제, 초점·구동 명령, 장비 재부팅을 하지 않는다.
4. 영상이 정상 갱신되는지 보되, 오류가 나타나면 정확한 시각만 적고 60초간 추가 조작하지 않는다.
5. 60초 동안 자동 복구, 다음 이미지 성공, 오류 큐 증가 여부를 관찰한다.

---

## 7. API와 수집기 사용 설계

### 7.1 수동 관찰에서 허용되는 API

| 메서드 | 경로 | 목적 | 수동 관찰 허용 |
|--------|------|------|----------------|
| GET | `/health` | 백엔드 생존 확인 | 예 |
| GET | `/stats` | 통신·HTTP·CSV·SPOT 지표 | 예 |
| GET | `/api/observability/errors?limit=200` | 오류 큐 조회 | 예 |
| GET | `/api/memory/state` | 메모리 상태 | 예 |
| GET | `/api/memory/details` | 메모리 상세 | 예 |
| GET | `/api/spot/config` | SPOT 설정 확인 | 예, 외부 공유 시 마스킹 |
| POST | `/api/observability/export` | 관측성 파일 생성 | 종료 시 1회 |
| POST | `/api/memory/export` | 메모리 파일 생성 | 종료 시 1회 |

### 7.2 수동 관찰에서 금지되는 API/기능

| 기능 | 금지 이유 |
|------|-----------|
| 오류 큐 clear API | 원본 오류 증거 삭제 |
| 메모리 profiler 시작/중지 | 실행 부하와 상태 변경 |
| 메모리 snapshot/GC API | 메모리·지연시간 변화 |
| 반복 이미지 호출 | 정상 요청률을 바꾸므로 별도 부하 트랙에서만 허용 |
| 장비 초점·구동·재시작 API | 장비 상태를 변경하므로 별도 승인 필요 |

### 7.3 관측성 수집 스크립트

서버에 전체 저장소가 없다면 다음 두 파일만 승인된 USB/사내 배포 경로로 복사하고,
복사 전후 SHA-256을 기록한다.

- `scripts/collect_operational_observability.ps1`
- `scripts/qa_spot_image_server.ps1`

스크립트 해시는 다음처럼 확인한다.

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '<스크립트경로>\collect_operational_observability.ps1'
Get-FileHash -Algorithm SHA256 -LiteralPath '<스크립트경로>\qa_spot_image_server.ps1'
```

관측성 수집기는 `/health`, `/stats`, 오류 큐, 메모리, SPOT 설정을 일정 간격으로 조회하고
원본·정제본·요약·해시를 생성한다. 정상 관찰 15분 기준 명령은 다음과 같다.

```powershell
Set-Location '<저장소 또는 스크립트 상위 경로>'
.\scripts\collect_operational_observability.ps1 `
  -ApiBase 'http://127.0.0.1:<백엔드포트>' `
  -Samples 180 `
  -IntervalSec 5 `
  -TimeoutSec 3 `
  -OutputRoot '<증거폴더>\03_spot_passive\app'
```

완료 후 PowerShell에 표시되는 아래 세 경로를 작업 메모에 복사한다.

- `sanitized_dir=`
- `sanitized_zip=`
- `summary_json=`

### 7.4 비개발자용 현장 수집 패키지

실제 서버에서 사용자가 관리자 권한으로 직접 실행한다는 확인에 따라 다음 세 파일을 하나의
현장 패키지로 제공한다.

- `scripts/run-spot-connecttimeout-evidence-as-admin.cmd`
- `scripts/collect-spot-connecttimeout-evidence.ps1`
- `scripts/collect_operational_observability.ps1`

CMD launcher는 UAC 관리자 실행만 담당한다. PowerShell wrapper는 다음을 한 실행으로 묶는다.

1. 관리자 권한·5GB 여유 공간·localhost health·SPOT 설정·기존 pktmon 필터 사전 점검
2. 프로세스·포트·NIC 전 상태
3. SPOT 대상 TCP header 캡처와 1초 ping
4. 기존 읽기 전용 관측성 collector의 5초 간격 15분 GET 수집
5. NIC·프로세스·포트 후 상태와 Windows System 이벤트
6. 앱 로그 사본, SHA-256, ETL·PCAPNG 원본
7. IP·MAC을 가린 packet text와 공유용 sanitized ZIP
8. 자신이 추가한 pktmon filter와 수집 job의 종료 정리

기존 pktmon filter가 하나라도 있으면 전체 filter remove를 실행하지 않고 사전 점검에서 중단한다.
wrapper가 filter를 추가한 직후 목록을 저장하고 종료 직전 목록과 정확히 비교한다. 두 목록이
같아서 wrapper filter만 존재한다고 확인되는 경우에만 전체 filter remove를 허용한다. 목록이
달라지면 다른 관리자의 filter를 보호하기 위해 아무 filter도 삭제하지 않고 실패로 기록한다.
원본 패킷·로그는 실제 서버의 `raw_private`에 남기고, 외부 전달은 `sanitized_share` ZIP을 우선한다.

`qa_spot_image_server.ps1`은 이미지 요청을 발생시키므로 정상 운전 수동 관찰 패키지에서
제외한다. 부하 시험은 P2 별도 승인 전에는 실행하지 않는다.

---

## 8. P0 공통 사전 점검 절차

### 8.1 필요한 준비물

- 서버 관리자 권한 계정
- 운영 승인자가 정한 유지보수 시간
- SPOT 장비 IP와 포트 — 문서 외부 공유 시 마스킹
- SPOT이 연결된 스위치와 포트 번호
- 5GB 이상의 여유 공간이 있는 증거 저장 경로
- 서버에서 실행 중인 실제 SmartFactoryLogger 버전 정보
- 수집 스크립트와 그 SHA-256
- 문제가 생겼을 때 사용할 정상 설치 패키지와 복구 담당자

### 8.2 관리자 권한 확인

관리자 PowerShell 제목 표시줄에 `관리자`가 있는지 확인한다. 다음 명령 결과가 `True`여야
`pktmon` 단계로 진행할 수 있다.

```powershell
([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator
)
```

### 8.3 시간과 디스크 확인

```powershell
Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff K'
w32tm /query /status
Get-PSDrive -PSProvider FileSystem | Select-Object Name,Used,Free
```

판정:

- 서버 시각이 현장 기준 시각과 1초 이상 다르면 먼저 시간 동기화 담당자에게 알린다.
- 시간 설정을 검증 중 임의 변경하지 않는다.
- 증거 드라이브 여유 공간이 5GB 미만이면 패킷 캡처를 시작하지 않는다.

### 8.4 프로세스와 포트 기준선

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'SmartFactoryLogger|python|uvicorn' } |
  Select-Object ProcessId,ParentProcessId,Name,CreationDate,ExecutablePath,CommandLine |
  Export-Csv -NoTypeInformation -Encoding UTF8 '<증거폴더>\01_baseline\process_before.csv'

Get-NetTCPConnection -State Listen |
  Sort-Object LocalPort |
  Select-Object LocalAddress,LocalPort,OwningProcess,State |
  Export-Csv -NoTypeInformation -Encoding UTF8 '<증거폴더>\01_baseline\port_before.csv'
```

### 8.5 NIC 기준선

```powershell
Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,LinkSpeed,MacAddress |
  Export-Csv -NoTypeInformation -Encoding UTF8 '<증거폴더>\01_baseline\nic_inventory.csv'

Get-NetAdapterStatistics |
  Select-Object Name,ReceivedBytes,SentBytes,ReceivedUnicastPackets,SentUnicastPackets,
    ReceivedDiscardedPackets,OutboundDiscardedPackets,ReceivedPacketErrors,OutboundPacketErrors |
  Export-Csv -NoTypeInformation -Encoding UTF8 '<증거폴더>\01_baseline\nic_before.csv'
```

### 8.6 기존 `pktmon` 작업 확인

```powershell
pktmon status | Out-File -Encoding utf8 '<증거폴더>\01_baseline\pktmon_status_before.txt'
pktmon filter list | Out-File -Encoding utf8 '<증거폴더>\01_baseline\pktmon_filter_before.txt'
```

기존 캡처가 실행 중이거나 다른 담당자가 만든 필터가 있다면 임의로 중지·삭제하지 않는다.
네트워크 담당자와 사용 목적을 확인할 때까지 SPOT 패킷 캡처를 `BLOCKED`로 기록한다.

### 8.7 앱 기준선 내보내기

6.1과 6.2의 화면 절차로 운영/관측성 및 메모리 자료를 먼저 내보낸다. 이 단계가 끝나기
전에는 앱 재시작, 오류 큐 비우기, SPOT 부하를 실행하지 않는다.

---

## 9. P1-A PLC 시작 트랙

### 9.1 이 트랙에서 확인하는 것

- `plc_driver` 오류가 앱 시작 직후 다시 발생하는지
- 오류 메시지에 `diagnostics_age_ms`, 빈 문자열, 숫자 변환이 다시 나타나는지
- 같은 시간에 EX·LS 연결·읽기 실패가 실제로 증가하는지
- 오류 27초 동안 CSV 행 또는 필드가 누락되는지
- 앱 상태가 `Running -> Warning/Offline -> Running`으로 자동 복구되는지

이 트랙은 **PLC 검증을 생략하는 것이 아니다**. 오류의 직접 지점이 앱 내부 데이터 변환으로
보이더라도, EX·LS 통신과 CSV 데이터를 함께 확인해 실제 PLC 장애가 아니라는 것을 증거로
배제해야 한다.

### 9.1.1 과거 증거로 대체 가능한 범위

2026-07-16의 성공한 백엔드 시작 36회를 전수 대조한 결과, 36회 모두 1~17초 안에 같은
`diagnostics_age_ms` 변환 오류가 발생했다. 그중 16회는 시작 뒤 120초 동안 Extruder와 LS
오류가 모두 0건이었다. 사건의 직접 원인과 EX·LS 통신 실패 독립성은 이 과거 증거로 충족한다.

따라서 사건 원인을 다시 입증하려고 운영 앱을 재시작하지 않는다. 9.2~9.6의 콜드 스타트는
현재 설치본 1.0.16의 재현 여부, CSV 영향 또는 향후 회귀를 추가 확인하려는 경우에만 선택하며,
반드시 유지보수 승인을 받는다.

### 9.2 사전 조건

- 앱 재시작이 승인된 유지보수 시간이다.
- P0 원본 내보내기가 완료되었다.
- 현재 프로세스와 포트 소유자가 기록되었다.
- EX·LS·SPOT 장비가 정상 운전 중임을 현장 작업자가 확인했다.
- 정상 설치 패키지 또는 기존 실행 방법을 운영 담당자가 확인했다.

### 9.3 콜드 스타트 절차

1. 현장 작업자가 앱 화면에서 최종 EX·LS·SPOT 상태와 CSV 최근 갱신 시각을 기록한다.
2. 정상 종료 메뉴로 SmartFactoryLogger를 종료한다.
3. 작업 메모에 종료 클릭 시각을 기록한다.
4. 서버 관리자가 프로세스와 백엔드 포트가 종료되었는지 읽기 전용 명령으로 확인한다.
5. 프로세스가 남아 있으면 강제 종료하지 말고 60초 기다린 뒤 운영 승인자에게 알린다.
6. 기존 프로세스가 완전히 종료된 경우에만 승인된 방법으로 앱을 한 번 실행한다.
7. 실행 클릭 시각, 첫 화면 표시 시각, 백엔드 포트 수신 시작 시각을 기록한다.
8. 앱을 90초 동안 조작하지 않는다.
9. EX·LS·SPOT 상태 변화, 오류 배너, CSV 갱신만 관찰해 시각을 기록한다.
10. 90초 뒤 운영/관측성 화면을 열어 오류 큐와 원자료를 내보낸다.
11. 앱 로그와 같은 시간대 CSV 사본을 증거 폴더에 복사한다.

종료 확인 명령:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'SmartFactoryLogger|python|uvicorn' } |
  Select-Object ProcessId,ParentProcessId,Name,CreationDate,ExecutablePath,CommandLine

Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalPort -eq <백엔드포트> } |
  Select-Object LocalAddress,LocalPort,OwningProcess,State
```

### 9.4 로그 복사

실제 로그 경로가 `%APPDATA%\SmartFactoryLogger\logs`인 배포본은 다음처럼 복사한다.
경로가 다르면 화면 내보내기 경로를 기준으로 실제 경로를 확인하고 작업 메모에 기록한다.

```powershell
$LogRoot = Join-Path $env:APPDATA 'SmartFactoryLogger\logs'
Get-ChildItem -LiteralPath $LogRoot -File -Recurse |
  Where-Object { $_.Name -in @('system.log','status.log','crash.log') } |
  Copy-Item -Destination '<증거폴더>\02_plc_startup' -Force
```

### 9.5 PLC 교차 판정

| 관찰 | 판정 |
|------|------|
| 같은 시각에 빈 문자열 숫자 변환 오류가 발생하고 EX·LS 실패는 0 | 앱 내부 타입/정규화 가설 `CONFIRMED`, PLC 통신 장애 가설 `EXCLUDED` |
| 오류 시각에 EX 또는 LS 연결/읽기 실패도 증가 | PLC 또는 공통 네트워크 영향 가능, 별도 PLC 네트워크 트랙 필요 |
| 오류는 재현되지 않고 EX·LS 정상 | `NOT_REPRODUCED`; 과거 로그 분석 결과는 유지하되 원인 확정 범위를 넓히지 않음 |
| 로그에는 오류가 있으나 CSV/통신 시각을 맞출 수 없음 | `INCONCLUSIVE` |

### 9.6 CSV 영향 확인

1. 오류 시작 1분 전부터 종료 2분 후까지의 CSV를 복사한다.
2. 설정된 저장 주기를 확인한다.
3. 연속 행의 타임스탬프 차이를 계산한다.
4. 예상 주기의 2배보다 큰 간격을 `gap`으로 표시한다.
5. EX·LS 값이 빈 값, 직전 값 유지, 정상 갱신 중 무엇인지 기록한다.
6. SPOT `diagnostics_age_ms` 필드가 빈 값, 누락, 숫자 중 무엇인지 기록한다.
7. CSV queue/drop/lag 전후 값을 함께 기록한다.

CSV가 계속 기록되었더라도 값이 직전 값으로 고정되었을 수 있으므로, 행 존재와 값 갱신을
둘 다 확인한다.

---

## 10. P1-B SPOT 수동 관찰 트랙

### 10.1 목적

정상 운영 요청률을 바꾸지 않은 상태에서 앱 관측성, SPOT 대상 TCP 패킷, 연속 ping,
서버 NIC 카운터, 스위치 포트 로그를 같은 15분 동안 수집한다. 이 다섯 증거가 같은 시간대에
있어야 `ConnectTimeout`이 앱 내부 대기, 서버 NIC, 경로, 스위치 또는 장비 무응답 중 어디에
가까운지 구분할 수 있다.

### 10.2 PowerShell 창 구성

| 창 | 권한 | 역할 |
|----|------|------|
| A | 관리자 | `pktmon` 필터·캡처·변환 |
| B | 일반 가능 | 1초 간격 ping 기록 |
| C | 일반 가능 | 앱 관측성 5초 간격 수집 |
| D | 일반 가능 | NIC 전후 카운터와 프로세스·포트 기록 |

창 제목이나 메모장에 A~D를 표시해 잘못된 창에서 중지 명령을 실행하지 않도록 한다.

### 10.3 실행 전 변수

각 창에서 필요한 실제 값을 설정한다.

```powershell
$SpotIp = '<SPOT_IP>'
$SpotPort = <SPOT_PORT>
$EvidenceRoot = '<증거폴더>'
```

IP와 포트를 모르면 추측하지 않고 SPOT 설정 화면 또는 네트워크 담당자에게 확인한다.

### 10.4 실행 순서

#### 1단계 — NIC와 화면 기준선

창 D:

```powershell
Get-NetAdapterStatistics |
  Select-Object Name,ReceivedBytes,SentBytes,ReceivedUnicastPackets,SentUnicastPackets,
    ReceivedDiscardedPackets,OutboundDiscardedPackets,ReceivedPacketErrors,OutboundPacketErrors |
  Export-Csv -NoTypeInformation -Encoding UTF8 "$EvidenceRoot\01_baseline\nic_before.csv"
```

현장 작업자는 6.1 절차로 관측성 화면을 캡처하고 오류 큐를 기록한다.

#### 2단계 — 기존 패킷 작업 재확인

창 A:

```powershell
pktmon status
pktmon filter list
```

다른 작업이 없을 때만 다음 단계로 간다.

#### 3단계 — SPOT TCP 패킷 캡처 시작

창 A:

```powershell
pktmon filter add SpotHttpValidation -i $SpotIp -p $SpotPort
pktmon start --capture --comp nics --pkt-size 128 --file-size 256 --log-mode circular `
  --file-name "$EvidenceRoot\03_spot_passive\network\spot_tcp.etl"
pktmon status | Out-File -Encoding utf8 "$EvidenceRoot\03_spot_passive\network\pktmon_status.txt"
```

`pktmon start`가 오류를 반환하면 반복 실행하지 말고 메시지를 저장하고 `BLOCKED`로 기록한다.

#### 4단계 — 연속 ping 시작

창 B:

```powershell
while ($true) {
  $now = Get-Date -Format 'yyyy-MM-ddTHH:mm:ss.fffK'
  $r = Test-Connection -ComputerName $SpotIp -Count 1 -ErrorAction SilentlyContinue
  if ($null -eq $r) {
    [pscustomobject]@{ at_kst=$now; success=$false; latency_ms=$null } |
      ConvertTo-Json -Compress |
      Add-Content -Encoding utf8 "$EvidenceRoot\03_spot_passive\network\ping_spot.jsonl"
  } else {
    [pscustomobject]@{ at_kst=$now; success=$true; latency_ms=$r.ResponseTime } |
      ConvertTo-Json -Compress |
      Add-Content -Encoding utf8 "$EvidenceRoot\03_spot_passive\network\ping_spot.jsonl"
  }
  Start-Sleep -Seconds 1
}
```

SPOT이 ICMP ping에 응답하지 않도록 설정된 장비라면 전체 실패가 네트워크 장애 증거가
아니다. 시작 전 평상시 ping 응답 여부를 장비 담당자에게 확인하고 메모한다.

#### 5단계 — 앱 관측성 수집 시작

창 C:

```powershell
Set-Location '<저장소 또는 스크립트 상위 경로>'
.\scripts\collect_operational_observability.ps1 `
  -ApiBase 'http://127.0.0.1:<백엔드포트>' `
  -Samples 180 `
  -IntervalSec 5 `
  -TimeoutSec 3 `
  -OutputRoot "$EvidenceRoot\03_spot_passive\app"
```

#### 6단계 — 정상 운전 15분 관찰

1. SPOT 화면은 평소 사용 상태를 유지한다.
2. 탭 수, 클라이언트 수, 화면 새로고침 방식을 바꾸지 않는다.
3. 현장 작업자는 화면 오류와 상태 변화의 시각만 기록한다.
4. 네트워크 담당자는 같은 15분의 스위치 포트 카운터와 링크 이벤트를 보존한다.
5. 오류가 발생하면 클릭하지 않고 60초 동안 다음 이미지 성공과 자동 복구를 관찰한다.

#### 7단계 — NIC 후 상태

창 D:

```powershell
Get-NetAdapterStatistics |
  Select-Object Name,ReceivedBytes,SentBytes,ReceivedUnicastPackets,SentUnicastPackets,
    ReceivedDiscardedPackets,OutboundDiscardedPackets,ReceivedPacketErrors,OutboundPacketErrors |
  Export-Csv -NoTypeInformation -Encoding UTF8 "$EvidenceRoot\03_spot_passive\network\nic_after.csv"
```

#### 8단계 — 수집 종료

창 B의 ping은 `Ctrl+C`로 중지한다. 창 A에서:

```powershell
pktmon stop
pktmon etl2pcap "$EvidenceRoot\03_spot_passive\network\spot_tcp.etl" `
  --out "$EvidenceRoot\03_spot_passive\network\spot_tcp.pcapng"
pktmon filter list | Out-File -Encoding utf8 "$EvidenceRoot\03_spot_passive\network\pktmon_filter_after.txt"
```

`pktmon filter remove`는 이름 하나가 아니라 **등록된 필터 전체를 삭제**한다. 따라서 검증
시작 전에 다른 필터가 없었고, 종료 시점에도 `SpotHttpValidation`만 남아 있음을 다시 확인한
경우에만 다음 명령을 실행한다. 그 외에는 네트워크 담당자 승인 없이 실행하지 않는다.

```powershell
pktmon filter remove
```

#### 9단계 — 앱 최종 내보내기

6.1과 6.2 절차로 운영/관측성 및 메모리를 내보내고, 최신 `system.log`, `status.log`,
`crash.log`를 복사한다.

### 10.5 SPOT 패킷 판정표

| 앱 오류 시각의 증거 | 해석 | 다음 확인 |
|----------------------|------|-----------|
| TCP SYN이 서버에서 나가고 SYN-ACK이 없음 | 서버 앱 밖으로 요청은 나감. 장비 또는 중간 경로 가능성 | 스위치 포트/VLAN/장비 로그 |
| SYN 반복 + 같은 시각 ping 손실 | 네트워크 경로·링크·장비 무응답 가능성 높음 | NIC·스위치 드롭/링크·장비 전원 |
| SYN 반복 + ping 성공 + SYN-ACK 없음 | IP 계층은 응답하지만 SPOT TCP 포트가 응답하지 않음 | 장비 서비스/포트/접속 한도 |
| SYN-ACK이 정상인데 앱은 ConnectTimeout | 패킷의 4-tuple·시각·프록시 여부 재검토, 앱 연결 풀/서버 자원 가능성 | 앱 스택과 자원 지표 |
| 오류 시각에 SYN 자체가 없음 | 앱 요청이 네트워크 호출 전 단계에서 막혔거나 잘못된 NIC에서 캡처 | 앱 요청 로그, 캡처 인터페이스/필터 |
| 정상 handshake 뒤 HTTP 5xx | ConnectTimeout과 다른 HTTP/장비 응답 문제 | HTTP 상태와 장비 응답 시간 |
| NIC error/discard 증가 | 서버 NIC, 드라이버, 케이블, 스위치 포트 가능성 | 이벤트 로그와 포트 카운터 |
| 패킷·ping·NIC 모두 정상이고 오류 미재현 | `NOT_REPRODUCED`; 원인 배제 아님 | 더 긴 수동 관찰 또는 승인된 P2 |

### 10.6 스위치/NIC에 반드시 요청할 자료

- 서버가 연결된 스위치 포트 번호와 SPOT이 연결된 포트 번호
- 검증 시작·종료 시각의 RX/TX packet, error, discard, CRC, drop 카운터
- 링크 up/down, speed/duplex 변경, STP/VLAN 이벤트
- MAC address 이동 또는 포트 보안 이벤트
- 같은 시각대 장비 재부팅·전원·서비스 로그
- NIC 드라이버 이벤트와 Windows System 이벤트

누적 카운터는 숫자 하나만으로 판단하지 않고 **검증 전후 증가량**을 계산한다.

---

## 11. P1-C 프로세스·포트 트랙

### 11.1 목적

`SystemExit: 3`이 운영 중인 첫 번째 백엔드의 비정상 종료인지, 두 번째 앱 시작이
단일 인스턴스 보호 로직의 lifespan 단계에서 거부된 것인지 구분한다.

사건 자료와 사건 버전 소스 대조 결과는 후자를 확정한다. 당시 PID·포트 자료는 향후 같은
사건의 운영 가시성을 높이는 보강 자료이며, 이번 원인 판정의 필수 조건은 아니다.

### 11.2 안전 원칙

- 운영 서버에서 재현을 위해 앱을 두 번 실행하지 않는다.
- 기존 프로세스를 종료하지 않는다.
- 프로세스 ID, 부모 PID, 생성 시각, 명령행, 포트 소유자만 읽는다.

### 11.3 수집 명령

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'SmartFactoryLogger|python|uvicorn' } |
  Select-Object ProcessId,ParentProcessId,Name,CreationDate,ExecutablePath,CommandLine |
  Export-Csv -NoTypeInformation -Encoding UTF8 '<증거폴더>\04_process\process_after.csv'

Get-NetTCPConnection -State Listen |
  Sort-Object LocalPort |
  Select-Object LocalAddress,LocalPort,OwningProcess,State |
  Export-Csv -NoTypeInformation -Encoding UTF8 '<증거폴더>\04_process\port_after.csv'
```

향후 같은 경고가 발생하면 `system.log`와 `crash.log`에서 다음 사건을 시간 순서로 적는다.

- 첫 번째 앱/백엔드 시작
- 포트 수신 시작
- 두 번째 실행 시도 흔적
- 단일 인스턴스 잠금 거부, lifespan startup 실패, `SystemExit: 3`
- 첫 번째 백엔드의 `/health` 성공 지속 여부
- 첫 번째 앱 종료 또는 재시작 여부

### 11.4 판정

| 증거 | 판정 |
|------|------|
| Uvicorn 106행 lifespan 실패, `STARTUP_FAILURE=3`, 기존 HTTP 생존, 새 backend-start 없음 | 두 번째 실행의 단일 인스턴스 guard 거부 `CONFIRMED` |
| 기존 PID가 사라진 뒤 Exit 3이고 이후 `/health`도 실패 | 이번 사건과 다른 기존 백엔드 종료 가능성; 별도 조사 필요 |
| 향후 재발에서 기존 PID·잠금·포트 소유자까지 수집됨 | 확정 판정의 운영 보강 증거 |
| 포트 bind 오류 원문이 별도로 존재 | 단일 인스턴스 guard 사건과 다른 포트 충돌로 분리 판정 |

---

## 12. P1-D 공통 건전성 트랙

### 12.1 확인 항목

- EX·LS·SPOT 최근 성공 시각이 계속 갱신되는가
- HTTP 요청/에러/5xx/p95가 사건 전후 정상 범위인가
- 브라우저 오류가 증가하는가
- 백오프·복구·대기 시간이 증가하는가
- CSV queue/drop/lag와 실제 파일 갱신이 정상인가
- 메모리 누수 의심·경고·오류가 증가하는가
- 오류 큐가 과거 누적인지 현재도 반복 증가하는지

### 12.2 현재와 과거 오류 구분

오류 큐에 3개가 남아 있어도 최근 성공 시각이 계속 갱신되고 새 오류 시각이 늘지 않으면
현재 장애가 아니라 **복구된 과거 오류가 보존된 상태**일 수 있다. 다음 네 값을 함께 본다.

1. 마지막 오류 시각
2. 마지막 성공 시각
3. 오류 반복 수의 증가 여부
4. 현재 통신·HTTP·CSV 상태

### 12.3 공통 합격 기준

- EX·LS·SPOT 최근 성공 시각이 설정된 정상 주기에 맞게 갱신된다.
- 관찰 구간의 HTTP 5xx 증가량이 0이다.
- 브라우저 오류 증가량이 0이다.
- CSV drop 증가량이 0이고 queue가 관찰 종료 후 0으로 회복된다.
- CSV lag가 현장 정상 기준 이내다.
- 누수 의심·메모리 오류 증가량이 0이다.
- 수집 종료 후 앱이 조작 없이 정상 상태를 유지한다.

---

## 13. P2 조건부 SPOT 부하·직접 시험

### 13.1 진입 조건

다음을 모두 만족할 때만 실행한다.

- P1 수동 관찰에서 오류가 재현되지 않았거나 패킷 증거가 부족하다.
- 운영 승인자가 요청률 증가와 잠재적 SPOT 부하를 승인했다.
- 생산 중단이 허용되는 유지보수 시간이다.
- P1 원본 증거가 별도 실행 ID로 이미 보존되었다.
- 즉시 중단할 현장 작업자와 장비 담당자가 대기 중이다.

### 13.2 부하 시험 원칙

- P1과 다른 새 실행 ID를 사용한다.
- 처음에는 클라이언트 1개와 낮은 요청률로 시작한다.
- 요청 수를 한 단계씩만 올리고 각 단계 사이에 정상 복구를 확인한다.
- `qa_spot_image_server.ps1`의 `blockers`가 1 이상이면 실패로 보고 더 올리지 않는다.
- 5xx, timeout, CSV drop, EX/LS 이상이 나타나면 즉시 중단한다.

명령의 실제 파라미터는 운영 기준과 스크립트 도움말을 먼저 확인한다.

```powershell
Get-Help '<스크립트경로>\qa_spot_image_server.ps1' -Detailed
```

스크립트에 존재하지 않는 파라미터를 추측해 실행하지 않는다. 실행한 전체 명령과 출력 경로,
`blockers=<수>`를 증거로 저장한다.

### 13.3 장비 직접 시험

앱을 우회한 장비 직접 호출은 장비 서비스에 부하를 줄 수 있으므로 장비 담당자 승인 없이는
실행하지 않는다. 실행할 경우 앱 시험과 별도 실행 ID를 사용하고 다음을 기록한다.

- 호출 PC와 네트워크 위치
- 대상 IP/포트 — 정제본 마스킹
- 요청 간격, 총 요청 수, timeout 설정
- 장비 응답 성공/실패/지연시간
- 같은 시간의 패킷, ping, NIC, 스위치 로그

직접 시험은 “장비가 항상 정상”을 증명하지 않는다. 같은 시간에 앱 실패/직접 성공이 반복되면
앱 경로나 연결 관리 차이를 의심할 수 있고, 둘 다 실패하면 장비·네트워크 가능성이 커진다.

---

## 14. 25개 검증 항목 상세 판정표

| ID | 우선순위 | 실행/확인 | 합격 또는 판정 기준 | 필수 증거 |
|----|----------|-----------|---------------------|-----------|
| SAFE-01 | P0 | 역할, 유지보수, 중단·복구 승인 | 모든 필수 담당자와 승인 시각 기입 | approvals, manifest |
| ENV-01 | P0 | 실제 서버·버전·포트·장비 대상 확인 | 사건 서버와 검증 서버가 동일, 버전 식별 가능 | manifest, version, port |
| BASE-01 | P0 | 오류 큐·관측성·메모리 원본 보존 | 오류 삭제 전 원본과 해시 존재 | exports, hash |
| PLC-01 | P1 | 과거 시작 36회 대조; 현재 버전 재시작은 선택 | 사건은 36/36 시작 오류와 16회 EX·LS 무오류 창으로 판정, 현장은 현재 버전 회귀만 확인 | timeline, logs |
| PLC-02 | P1 | `diagnostics_age_ms` 타입 확인 | 오류 시 빈 문자열 또는 실제 값 식별 | error export, system.log |
| PLC-03 | P1 | EX 통신 교차 확인 | 같은 시각 연결/읽기 실패 증가 여부 판정 | stats, status.log |
| PLC-04 | P1 | LS 통신 교차 확인 | 같은 시각 연결/읽기 실패 증가 여부 판정 | stats, status.log |
| PLC-05 | P1 | 시작 오류 자동 복구 확인 | 90초 안 상태와 데이터가 정상 복구 | timeline, stats |
| SPOT-01 | P1 | 정상 운전 앱 지표 15분 | 요청·RPS·client·502·timeout 시간축 존재 | collector output |
| SPOT-02 | P1 | SPOT TCP 캡처 | 오류 전후 SYN/SYN-ACK 또는 미발생 확인 가능 | ETL, PCAPNG |
| SPOT-03 | P1 | 1초 ping | 오류 전후 성공/손실/지연 확인 가능 | ping JSONL |
| SPOT-04 | P1 | NIC 전후 카운터 | error/discard 증가량 계산 가능 | NIC CSV 2개 |
| SPOT-05 | P1 | 스위치 포트 로그 | 링크/drop/CRC/VLAN 사건 확인 가능 | switch evidence |
| SPOT-06 | P1 | 장비 상태·서비스 로그 | 오류 시각 장비 재부팅/서비스 중단 확인 | device evidence |
| SPOT-07 | P1 | 오류 뒤 60초 복구 관찰 | 다음 성공, 복구 시간, 반복 수 판정 | notes, stats, packets |
| PROC-01 | P1 | 프로세스·부모 PID·시각 | 실행 인스턴스 수와 관계 식별 | process CSV |
| PROC-02 | P1 | 백엔드 포트 소유자 | 단일 PID 또는 충돌 PID 식별 | port CSV |
| PROC-03 | P1 | Exit 3 stack·guard·기존 HTTP 생존 대조 | 두 번째 실행의 단일 인스턴스 guard 거부 확인 | source, logs, health, timeline |
| COMMON-01 | P1 | HTTP·브라우저·메모리·복구 | 신규 5xx/browser/memory 오류 없음 | common exports |
| LOAD-01 | P2 | 승인된 단계별 SPOT 부하 | 첫 오류 임계 요청률 또는 무오류 상한 식별 | QA output, packets |
| LOAD-02 | P2 | 앱 우회 장비 직접 시험 | 앱 경로와 장비 직접 결과 비교 가능 | direct result, packets |
| PLC-NET-01 | P2 | EX/LS 실패가 동반될 때 PLC망 확인 | PLC 장비/경로/앱 중 범위 축소 | PLC network evidence |
| REG-01 | P3 | 향후 패치 후 PLC 시작 회귀 | 타입 오류 0, EX/LS·CSV 정상 | regression output |
| REG-02 | P3 | 향후 패치 후 SPOT 회귀 | 정상·부하 기준에서 timeout/5xx 기준 통과 | QA and packet output |
| RELEASE-01 | P3 | 배포 승인 게이트 | P3 통과, 롤백 패키지·관측성·승인 존재 | release checklist |

어떤 ID도 증거 없이 `정상`으로 표시하지 않는다. 미실행 항목은 삭제하지 않고 `BLOCKED`
또는 `PENDING`으로 남긴다.

---

## 15. 시간축 상관 분석 절차

### 15.1 기준 시각

모든 결과의 기준은 KST ISO 8601 형식으로 한다.

```text
2026-07-17T18:22:11.123+09:00
```

로그가 UTC이면 9시간을 더한 KST 열을 별도로 만들되 원본 시각을 덮어쓰지 않는다.

### 15.2 사건 창

각 오류마다 다음 구간을 잘라 비교한다.

- 오류 60초 전
- 오류 발생 순간
- 오류 60초 후
- 정상 복구 후 첫 성공

### 15.3 SPOT 상관 순서

1. 앱 `spot_image` 오류 시각을 기준점으로 잡는다.
2. 같은 시각 ±2초의 TCP SYN/SYN-ACK을 찾는다.
3. 같은 시각 ±2초의 ping 성공/손실/지연을 찾는다.
4. 해당 15분의 NIC error/discard 증가량을 계산한다.
5. 스위치 링크/drop/CRC 이벤트를 찾는다.
6. SPOT 장비 서비스·재부팅 로그를 찾는다.
7. 앱 요청 RPS/client 수와 직전 1분 평균을 비교한다.
8. 60초 안 다음 이미지 성공과 오류 큐 반복 수를 확인한다.
9. 10.5의 판정표에 따라 가설별 `CONFIRMED/EXCLUDED/INCONCLUSIVE`를 기록한다.

### 15.4 PLC 상관 순서

1. `plc_driver` 오류 첫 시각과 마지막 시각을 잡는다.
2. 오류 payload의 `diagnostics_age_ms` 실제 값을 확인한다.
3. 같은 구간 EX·LS 연결·읽기 실패 증가량을 확인한다.
4. 앱 상태 전이와 자동 복구 시각을 확인한다.
5. CSV 타임스탬프 간격과 값 갱신을 확인한다.
6. PLC 장비 고장 가설과 앱 데이터 변환 가설을 각각 별도로 판정한다.

### 15.5 프로세스 상관 순서

1. `SystemExit: 3` 시각을 잡는다.
2. 해당 시각 전후 PID와 부모 PID 생성 시각을 확인한다.
3. 백엔드 포트 소유 PID를 대응시킨다.
4. `/health` 성공이 계속되었는지 확인한다.
5. 첫 인스턴스 생존과 두 번째 인스턴스 실패를 분리해 기록한다.

---

## 16. 합격·실패 보고서 형식

각 검증 ID마다 아래 양식을 채운다.

```text
검증 ID:
실행 ID:
가설:
시작/종료 시각:
실행자/검토자:
실행한 화면 절차 또는 명령:
관찰 결과:
결과 상태: CONFIRMED / EXCLUDED / NOT_REPRODUCED / INCONCLUSIVE / BLOCKED / NEW_ISSUE
근거 파일 evidence_id:
운영 영향:
추가로 필요한 증거:
```

### 16.1 전체 완료 기준

- P0 3개 항목이 모두 완료되었다.
- P1 16개 항목이 모두 실행되거나, 미실행 사유가 `BLOCKED`로 명시되었다.
- 세 사건 각각에 최소 하나의 직접 증거와 반대 가설을 검토한 기록이 있다.
- 원본과 정제본이 분리되어 있다.
- 모든 핵심 파일에 SHA-256이 있다.
- 수집 후 EX·LS·SPOT·HTTP·CSV 정상 복구를 확인했다.
- 분석 담당자와 운영 담당자가 결과를 2인 검토했다.

`NOT_REPRODUCED`는 전체 성공이나 원인 해결을 뜻하지 않는다. 재발 조건을 잡지 못했다는
뜻으로만 보고한다.

---

## 17. 해시와 외부 공유용 정제

### 17.1 SHA-256 생성

원본 수집이 끝난 뒤 원본을 더 수정하지 않고 실행한다.

```powershell
Get-ChildItem -LiteralPath '<증거폴더>' -File -Recurse |
  Where-Object { $_.FullName -notmatch '\\99_hashes\\' } |
  ForEach-Object {
    $h = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
    [pscustomobject]@{
      relative_path = $_.FullName.Substring('<증거폴더>'.Length).TrimStart('\')
      length = $_.Length
      last_write_time_kst = $_.LastWriteTime.ToString('yyyy-MM-ddTHH:mm:ss.fffK')
      sha256 = $h.Hash
    }
  } | Export-Csv -NoTypeInformation -Encoding UTF8 '<증거폴더>\99_hashes\sha256_manifest.csv'
```

### 17.2 정제 대상

- 서버 이름, 사용자 이름, 내부 IP, MAC address
- SPOT/PLC 장비 주소와 포트
- 파일 경로에 포함된 개인 이름
- 계정, 토큰, 쿠키, 인증 헤더
- 생산 품목·고객·공정 식별 데이터
- 패킷 payload

원본은 제한된 내부 위치에 보관한다. 외부 공유는 수집 스크립트가 만든 `sanitized` 결과와
별도 검토된 요약만 사용한다. 패킷 원본은 네트워크/보안 승인 없이 외부 공유하지 않는다.

---

## 18. 복구와 롤백

### 18.1 수집기 종료

1. ping 창에서 `Ctrl+C`.
2. 관리자 창에서 `pktmon stop`.
3. 관측성 수집기가 완료될 때까지 기다리거나 한 번만 `Ctrl+C`.
4. QA 부하 스크립트가 실행 중이면 새 요청이 더 생성되지 않도록 정상 중지.
5. 네트워크 필터 정리는 기존 필터 유무를 확인한 뒤 수행.

### 18.2 앱 복구

1. 앱이 응답하면 재시작하지 않고 통신·CSV 복구를 먼저 확인한다.
2. 앱이 응답하지 않을 때만 운영 승인자의 지시에 따라 정상 종료한다.
3. 기존 프로세스와 포트가 종료된 것을 확인한다.
4. 승인된 정상 설치본/실행 방법으로 한 번만 실행한다.
5. EX·LS·SPOT 최근 성공, HTTP, CSV queue/drop/lag를 확인한다.
6. 복구 시각과 수행자를 작업 메모에 기록한다.

### 18.3 완료 후 반드시 정상이어야 하는 항목

- 백엔드 포트를 소유한 프로세스가 하나다.
- `/health`가 성공한다.
- EX·LS·SPOT 최근 성공 시각이 갱신된다.
- CSV queue는 0으로 돌아오고 drop은 증가하지 않는다.
- `pktmon status`가 캡처 중이 아님을 표시한다.
- 부하 스크립트가 남아 있지 않다.
- 새로운 오류가 있다면 큐를 지우지 않고 별도 기록했다.

---

## 19. 보안·호환성·운영 영향

### 19.1 보안

- 관리자 권한은 `pktmon`과 필요한 시스템 조회에만 사용한다.
- 스크립트는 승인된 해시와 일치하는 파일만 실행한다.
- 원본 패킷과 로그 접근자는 최소 인원으로 제한한다.
- PowerShell 명령에 비밀번호, 토큰, 인증 헤더를 직접 넣지 않는다.
- 장비 주소를 외부 보고서에 그대로 넣지 않는다.

### 19.2 호환성

- 앱 로직, API 계약, CSV 스키마, 장비 설정을 변경하지 않으므로 마이그레이션은 없다.
- `pktmon`, `Get-NetAdapterStatistics`, `Get-NetTCPConnection` 사용 가능 여부는 서버 Windows
  버전과 권한에 따라 다를 수 있다. 사용할 수 없으면 실패를 숨기지 말고 `BLOCKED`로 기록하고
  네트워크 담당자의 승인된 대체 도구를 사용한다.

### 19.3 예상 운영 영향

| 작업 | 예상 영향 | 허용 조건 |
|------|-----------|-----------|
| UI 새로고침/GET 수집 | 매우 낮음 | 정상 운전 중 가능 |
| 128바이트 헤더 패킷 캡처 | 낮음 | 디스크·관리자 권한·보안 승인 |
| 1초 ping | 낮음 | 장비 정책 확인 |
| 앱 콜드 스타트 | 높음 | 유지보수 승인 필수 |
| SPOT 부하 시험 | 높음 | 별도 유지보수·장비 승인 필수 |
| 장비 직접 시험 | 높음 | 장비 담당자 승인 필수 |

---

## 20. 현장 실행 체크리스트

### 작업 전

- [ ] 운영 승인자, 현장 작업자, 서버 관리자, 네트워크 담당자 지정
- [ ] 실행 ID와 증거 폴더 생성
- [ ] 서버·앱 버전·백엔드 포트·SPOT IP/포트 확인
- [ ] 시간 동기화와 디스크 여유 확인
- [ ] 스크립트 SHA-256 확인
- [ ] 기존 프로세스·포트·NIC·`pktmon` 상태 저장
- [ ] 관측성·메모리·오류 큐 원본 내보내기
- [ ] 중단·복구 기준 음성 확인

### PLC 시작 트랙

- [ ] 재시작 승인 확인
- [ ] 앱 정상 종료
- [ ] 남은 프로세스·포트 확인
- [ ] 앱 한 번만 실행
- [ ] 90초 무조작 관찰
- [ ] 오류·EX·LS·SPOT·CSV 시각 기록
- [ ] 로그·관측성·CSV 복사

### SPOT 수동 관찰 트랙

- [ ] NIC before 저장
- [ ] 기존 `pktmon` 캡처·필터 확인
- [ ] SPOT TCP 캡처 시작
- [ ] 1초 ping 시작
- [ ] 앱 관측성 5초 수집 시작
- [ ] 정상 운전 상태로 15분 관찰
- [ ] 오류 시 60초 무조작 복구 관찰
- [ ] NIC after 저장
- [ ] ping과 `pktmon` 정상 종료
- [ ] PCAPNG 변환
- [ ] 스위치·장비 로그 확보
- [ ] 앱 최종 내보내기

### 프로세스·공통 트랙

- [ ] PID·부모 PID·생성 시각 저장
- [ ] 포트 소유자 저장
- [ ] Exit 3 전후 `/health`와 로그 정렬
- [ ] HTTP·브라우저·CSV·메모리 전후 비교

### 작업 후

- [ ] EX·LS·SPOT·HTTP·CSV 정상 복구
- [ ] `pktmon`과 부하 수집기 종료 확인
- [ ] 원본 파일 잠금·보관
- [ ] SHA-256 manifest 생성
- [ ] 외부 공유용 정제본 분리
- [ ] 25개 ID 모두 결과 또는 미실행 사유 기록
- [ ] 분석 담당자·운영 담당자 2인 검토

---

## 21. 다음 PDCA 단계 인계

다음 `Do` 단계는 코드 구현이 아니라 **이 설계에 따른 현장 증거 수집**이다.

인계 시 필요한 입력은 다음과 같다.

1. 운영 승인된 작업 일시
2. 실제 서버의 앱 버전과 백엔드 포트
3. SPOT IP/포트와 스위치 포트 담당자
4. 재시작 승인 여부
5. 부하 시험 승인 여부
6. 증거를 저장할 내부 경로

Do 단계에서는 P0와 P1을 먼저 수행한다. P2는 P1 결과가 부족하고 별도 승인이 있을 때만
수행한다. 앱 로직 패치는 별도 요청과 별도 PDCA 없이는 진행하지 않는다.

---

## 22. 버전 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| 1.0.0 | 2026-07-17 | 화면·명령·역할·증거·판정·중단·복구를 포함한 최초 Design 확정 |
| 1.0.1 | 2026-07-17 | 최근 오류 큐와 하루 전체 로그 범위를 분리하고 전체 반복 사건을 현장 범위에 반영 |
| 1.0.2 | 2026-07-17 | 과거 시작 36회 증거를 PLC 사건 판정에 채택하고 `SystemExit: 3`을 단일 인스턴스 guard 거부로 정정 |
| 1.1.0 | 2026-07-17 | 실제 서버 관리자 직접 실행 조건에 맞춘 읽기 전용 15분 수집 패키지와 정제·중단 설계 추가 |
| 1.1.1 | 2026-07-17 | pktmon filter 등록 직후·종료 직전 상태 비교로 동시 관리자 filter 보호 강화 |
