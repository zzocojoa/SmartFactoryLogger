# 운영 오류 전체 원인 검증 실행 추적

> **Feature**: `runtime-error-root-cause-validation`  
> **Version**: 1.0.1  
> **Date**: 2026-08-06  
> **Status**: Field Investigation and Check Complete  
> **Plan**: `docs/01-plan/features/runtime-error-root-cause-validation.plan.md`  
> **Design**: `docs/02-design/features/runtime-error-root-cause-validation.design.md`  
> **변경 정책**: 조사 전용, 앱 로직·설정·장비 설정 변경 금지

> **기록 경계**: 이 문서는 2026-07-17~20 조사 실행 기록이다. 2026-07-31의
> `575e869` QA·smoke·120분 canary 및 2026-08-05의 `49fbf6b` QA 실패·v1.0.16
> 롤백에 따른 현재 운영 결론은
> [완료 보고서](../../04-report/runtime-error-root-cause-validation.report.md)를 기준으로 한다.

---

## 1. 이 문서의 역할

이 문서는 PDCA Do 단계의 실행 기록이다. 이번 Do는 앱 기능 구현이 아니라 다음 두 작업으로
구성된다.

1. 제공된 파일과 현재 로컬 환경을 이용한 오프라인 증거 분석
2. 실제 서버에서 재발 시 수행할 P0/P1 현장 증거 수집

오프라인 분석으로 확인된 사실과 현장 수집이 없어서 아직 확인할 수 없는 사실을 분리한다.
앱 소스 코드, 설정, 장비, 네트워크에는 변경을 가하지 않는다.

---

## 2. 현재 진행 상태

| 단계 | 상태 | 설명 |
|------|------|------|
| Plan | 완료 | 전체 원인 검증 범위와 25개 검증 ID 확정 |
| Design | 완료 | 화면·명령·역할·증거·판정·복구 절차 확정 |
| Do-A 오프라인 분석 | 완료 | 제공된 6개 파일, 전체 로그, 현재 저장소 로직을 읽기 전용 분석 |
| Do-B 환경 식별 | 완료 | 실제 서버 관리자 preflight와 config·process·port 확인 통과 |
| Do-C P0 원본 보존 | 완료 | raw·sanitized 분리, manifest·ZIP SHA-256·CRC 확인 |
| Do-D PLC 시작 검증 | 사건 원인 완료 | 성공 시작 36/36 오류, 16회 EX·LS 무오류 창으로 오프라인 확정; 현재 버전 재시작은 선택 |
| Do-E SPOT 수동 관찰 | 완료 | 약 47분 앱·TCP·ping·NIC 동시 수집, ConnectTimeout 5회 재현 |
| Do-F 프로세스 판정 | 완료 | Uvicorn startup stack·단일 인스턴스 guard·기존 HTTP 생존으로 원인 확정 |
| Do-G 스위치·장비 로그 | Gap 기록 | 스위치와 SPOT 내부 서비스 로그는 미확보, raw TCP 판정의 보조 자료로 유지 |
| Check | 완료 | 설계 25개 중 23개 Match, 정합률 92% |

Do 단계는 완료한다. 핵심 원인 판정에 필요한 현장 증거가 확보됐고, 미확보 자료 두 건과 08:10
host-side stall의 후속 범위가 명시됐다.

---

## 3. 제공 증거 원본 목록

### 3.1 파일과 해시

| 파일 | 크기 | SHA-256 |
|------|------|---------|
| `system.log` | 3,351,802 bytes | `C7A1116A71142F3F02A2843412990E78D67ABC7110C40B3F06D88274E80AA01A` |
| `crash.log` | 5,316 bytes | `95F8DA48F004169B24D2B3613BE8BE3FA424FA9863CD2DEFDCED73EEA16E1F25` |
| `memory_snapshot_20260716_181039.json` | 457,934 bytes | `A61F2C40F3D3DB00971E2C4E7F80B5111507187B30F7DEDC6A0895A829FAB9ED` |
| `observability_last_export.json` | 176 bytes | `E722D9A8662C238DD01E39BBEECFEAEAC39D6AF7FA3639F4AB94C2E681C3EB2D` |
| `observability_snapshot_20260716_180612.json` | 16,594 bytes | `9C3CD1A8B8F7A385FC52C57DABED1BB11DCAB1EF622860F3E8AD7E9870E9D619` |
| `status.log` | 2,408,324 bytes | `F907AF5D4ACD6B4782948F9C35462E1EC32439B4954341754F18E3514CAE8468` |

### 3.2 원본 보존 판정

- 제공 파일 6개가 모두 존재한다.
- 각 파일의 현재 SHA-256을 계산했다.
- 원본은 수정하지 않았다.
- 별도 현장 실행 폴더의 `run_manifest.json`, `evidence_index.csv`, 2인 승인 기록은 아직 없다.
- 따라서 `BASE-01`은 `PARTIAL`이다.

---

## 4. 환경에서 자동 확인된 값

### 4.1 확인된 값

| 항목 | 확인 결과 | 증거 범위 |
|------|-----------|-----------|
| 백엔드 포트 | `8000` | 2026-07-16 `system.log`의 모든 성공 시작 레코드 |
| 실행 형태 | 패키지된 Electron + `SmartFactoryBackend.exe` | 로그의 frozen runtime 경로, 메모리 runtime |
| 운영 모드 | `REAL` | 18:06 관측성 스냅샷 |
| 운영체제 | Windows 11, 64-bit | 메모리 runtime |
| Python runtime | 3.12.10 | 메모리 runtime |
| 현재 저장소 버전 | `1.0.16` | `package.json`, `backend/version.py` |
| 현재 설치 파일 버전 | `1.0.16.0` | 2026-07-17 로컬 설치 파일 메타데이터 |
| 현재 설치 빌드 | release `1.0.16`, commit `834ed85b5b3e9efe9cfb19b63935cbeb07cd4eec` | 설치 provenance와 현재 HEAD 일치 |
| 사건 추정 버전 | 높은 신뢰도로 `1.0.15` | 사건 직전 release commit, 당일 AppData metadata 시간대, 사건 뒤 1.0.16 설치 시각 대조 |
| SPOT 설정 | IP와 HTTP 대상이 설정되어 있음 | 현재 `%APPDATA%` 설정, 실제 값은 문서에서 마스킹 |
| SPOT HTTP 포트 | 기본 HTTP 포트 | 현재 설정 URL |
| SPOT timeout | 2.0초 | 현재 설정과 오류 elapsed 약 2,000ms 일치 |
| SPOT 영상 요청률 | 29.817 req/s, client 1개 | 18:06 스냅샷의 직전 60초 |
| 현재 앱 실행 상태 | 실행 프로세스 없음 | 2026-07-17 16:38 KST 이전 읽기 전용 확인 |
| 현재 포트 8000 | LISTEN 없음 | 2026-07-17 16:38 KST 이전 읽기 전용 확인 |

### 4.2 아직 확정되지 않은 값

- 실제 운영 서버에서 명령을 실행할 작업자 또는 접근 방법
- 실제 서버에서 사용할 증거 저장 드라이브와 여유 공간
- SPOT이 연결된 스위치와 포트 번호
- 앱 재시작이 허용되는 유지보수 시간
- SPOT 패킷 캡처를 수행할 Windows 관리자 권한

사건 직전 release는 2026-07-16 16:46의 1.0.15이고, 당일 18:12 이후 AppData metadata도
1.0.15를 기록한다. 현재 1.0.16 설치본은 2026-07-17 11:23에 작성되었고 provenance가 현재
release commit과 일치한다. 17:34 정확한 metadata가 없어 사건 버전을 절대 확정하지는 않지만,
시간축과 빌드 이력상 사건 버전은 높은 신뢰도로 1.0.15다. 첨부 로그와 동일한 AppData 로그
원본은 현재 위치에 남아 있지 않아 파일 해시로 동일 환경을 직접 확인할 수는 없다.

---

## 5. 마지막 세션 사건 시간축

### 5.1 시간축

| KST 시각 | 사건 | 증거 |
|----------|------|------|
| 17:34:54 | 백엔드 세션 시작, PID 14204 | `system.log` |
| 17:34:54 | 상태 `Offline -> Running` | `status.log` |
| 17:34:55 | `plc_driver` 첫 타입 변환 오류 | `system.log`, 오류 큐 |
| 17:34:59 | 상태 `Running -> Warning` | `status.log` |
| 17:35:15 | 상태 `Warning -> Offline` | `status.log` |
| 17:35:21 | 27번째 `plc_driver` 오류, 해당 구간 마지막 오류 | `system.log`, 오류 큐 |
| 17:35:25 | 상태 `Offline -> Warning` | `status.log` |
| 17:36:21 | 상태 `Warning -> Running` | `status.log` |
| 17:37:32 | SPOT image `ConnectTimeout`, 약 2,000ms, 502 | `system.log`, 오류 큐 |
| 17:42:11 | SPOT image `ConnectTimeout`, 약 2,015ms, 502 | `system.log`, 오류 큐 |
| 17:55:03 | 두 번째 frozen frontend 초기화와 Uvicorn `SystemExit: 3` | `system.log`, `crash.log` |
| 18:06:12 | 기존 백엔드에서 관측성 export HTTP 200 | `system.log`, 스냅샷 |
| 18:06:12 | 직전 60초 SPOT image 1,789/1,789 성공 | 관측성 스냅샷 |
| 18:10:37 | 메모리 snapshot, leak suspect 0 | 메모리 스냅샷 |

### 5.2 마지막 세션에서 확정되는 사실

- `plc_driver` 27회는 모두 동일한 `diagnostics_age_ms=""` 숫자 변환 실패다.
- 오류는 앱 시작 1초 뒤 시작해 26초 동안 반복되었다.
- 마지막 오류 뒤 상태는 단계적으로 복구되어 17:36:21에 Running이 되었다.
- 이 27회 구간에는 Extruder 또는 LS PLC 오류 레코드가 함께 기록되지 않았다.
- 두 SPOT image 오류는 HTTP 상태 응답을 받은 실패가 아니라 `ConnectTimeout`이다.
- 각 SPOT image 연결 시도는 설정된 2초 connect timeout 부근에서 끝났다.
- 18:06에는 SPOT 영상 요청이 다시 성공하고 있었다.

### 5.3 마지막 세션만으로 확정할 수 없는 사실

- SPOT TCP SYN이 서버 NIC를 떠났는지
- SYN에 장비 또는 스위치가 응답했는지
- 같은 순간 ping 손실이나 NIC error/discard가 있었는지
- SPOT 장비 서비스가 순간적으로 접속을 거절하거나 멈췄는지
- 29.8 req/s가 타임아웃을 유발했는지, 평상시 정상 부하인지
- 17:34 오류 27초 동안 CSV 행 또는 값 갱신이 실제로 누락되었는지
- 17:55의 첫 백엔드와 두 번째 실행 시도 PID를 당시 Windows 자료로 직접 대응하는 것

---

## 6. 하루 전체 로그에서 추가 확인된 사실

### 6.1 오류 범위

`system.log` 전체에서 JSON으로 파싱된 레코드는 12,066개다. JSON 단일 레코드로 파싱되지
않은 106줄은 traceback 또는 비정형 줄이므로 원본을 유지하고 자동 집계에서 제외했다.

| 소스 | 오류 레코드 | 기간 또는 구간 | 해석 |
|------|-------------|----------------|------|
| `plc_driver` | 843 | 00:12:36~17:35:21, 10초 기준 50개 구간 | 마지막 27회만의 단발 문제가 아님 |
| Extruder | 234 | 00:12:34~12:55:15 | 실제 연결·송수신 timeout 기록 포함 |
| LS PLC | 233 | 00:12:34~11:21:56 | timeout, No Body/Header, 연결 종료 포함 |
| `spot_image` ConnectTimeout | 19 | 00:00:33~17:42:11 | 하루 동안 여러 세션에서 반복 |
| `spot_image` upstream request error | 1 | 03:24:38 | ConnectTimeout과 별도 유형 |

### 6.2 중요한 범위 구분

- **최근 오류 큐**: 마지막 17:34 세션의 3개 항목과 반복 합계 29회
- **하루 전체 로그**: 이전 세션까지 포함한 다수의 PLC·SPOT 오류
- **재발 검증 실행**: 향후 앱·패킷·ping·NIC·스위치를 동시에 수집하는 새 실행

최근 오류 큐가 3개라고 해서 하루 동안 오류가 세 번만 발생한 것은 아니다. 반대로 하루 전체에
PLC 통신 오류가 있었다고 해서 마지막 17:34의 타입 변환 오류가 PLC 통신 때문에 발생했다고
볼 수도 없다. 시간 구간을 분리해서 판정해야 한다.

### 6.3 SPOT 오류 구간

시간 간격 10초를 기준으로 나누면 하루의 SPOT 오류는 13개 구간이다.

- 00:00:33
- 02:03:40~02:03:49
- 02:47:23
- 03:24:38 — 별도 `upstream-request-error`
- 03:54:23
- 14:01:24~14:01:32
- 14:35:53
- 14:43:44
- 15:39:30
- 15:41:12~15:41:21
- 17:22:04~17:22:12
- 17:37:32
- 17:42:11

기존 `system.log`는 실패한 SPOT image 요청은 남기지만 성공 image 요청 전체를 access log에
남기지 않는다. 따라서 이 로그만으로 오류 직전 정확한 RPS를 계산할 수 없다. 재발 시
`collect_operational_observability.ps1`이 필요한 이유다.

### 6.4 백엔드 시작과 `plc_driver` 오류 상관

- 성공한 백엔드 시작은 총 36회다.
- 36회 모두 시작 1~17초 안에 같은 `diagnostics_age_ms` 숫자 변환 오류가 발생했다.
- 16회는 시작 뒤 120초 동안 Extruder와 LS 오류가 모두 0건이었다.
- 마지막 네 시작에서도 각각 27회, 33회, 2회, 27회의 같은 오류가 반복됐다.

따라서 이 오류는 실제 PLC 통신 실패가 있어야만 발생하는 현상이 아니라, SPOT 진단값이 아직
없는 시작 구간의 데이터 형상 때문에 결정적으로 발생한 현상이다. 사건 원인을 다시 증명하기 위한
의도적 앱 재시작은 필요하지 않다.

### 6.5 Windows 네트워크 이벤트 대조

2026-07-16 17:30~18:00 Windows System 로그에는 8개 이벤트가 있었지만 TCP/IP, NDIS,
Network, DHCP, DNS, NIC, WLAN, Kernel-PnP 계열 이벤트는 0건이었다. 하루 전체의 네트워크
관련 이벤트 36건도 주로 01:11, 02:30~02:33, 19:33에 있었고 17:37·17:42 SPOT 오류와
일치하지 않았다.

이는 사건 시각에 Windows가 기록한 링크 변경이 없었다는 **약한 음성 증거**다. 순간 패킷 손실,
스위치 drop, 케이블 문제, SPOT 장비 서비스 무응답은 System 이벤트가 없어도 발생할 수 있으므로
SPOT 하위 원인을 배제하는 근거로 사용하지 않는다.

---

## 7. 저장소 로직 대조 결과

이 절은 높은 신뢰도의 사건 버전 `1.0.15` commit과 현재 설치 버전 `1.0.16`을 각각 읽기
전용으로 대조한 결과다. 사건 버전 직접 metadata가 없는 한계는 유지하되, 두 버전에서 이번
판정에 필요한 경로가 존재하는지 분리해 확인했다.

### 7.1 `plc_driver` 경로

사건 버전 1.0.15 소스에서 다음 흐름이 존재한다.

```text
SPOT 진단 스냅샷 없음
-> diagnostics_age_ms = ""
-> real_plc가 값을 정규화하지 않고 FactoryData에 전달
-> FactoryData의 Optional[float] 검증
-> 빈 문자열 숫자 변환 실패
```

`Optional[float]`은 `None` 또는 숫자를 허용한다는 뜻이지 빈 문자열을 허용한다는 뜻이 아니다.
따라서 마지막 27회 오류 메시지와 사건 버전 코드 경로는 직접 일치한다.

### 7.2 SPOT image 경로

현재 저장소에서는 다음 제어가 존재한다.

- image 요청은 `_img_fetch_lock`으로 한 번에 하나씩 처리한다.
- image와 온도/진단 장비 요청은 `_spot_device_request_lock`을 공유한다.
- image connect timeout은 2초다.
- ConnectTimeout의 elapsed는 장비 요청 lock을 획득한 뒤부터 측정한다.
- 따라서 오류의 약 2,000ms는 단순 브라우저 대기열 시간이 아니라 실제 upstream 연결
  시도 구간과 일치한다.

이 사실은 “SPOT 장비 방향 연결이 2초 안에 성립하지 않았다”는 단계까지만 설명한다.
장비·스위치·NIC·케이블·서버 네트워크 스택 중 어느 하위 원인인지는 패킷과 네트워크 증거가
없어 확정할 수 없다.

### 7.3 프로세스 시작 경로

17:55:03에는 frozen frontend 초기화 뒤 Uvicorn startup에서 `SystemExit: 3`이 발생했고,
새로운 성공 backend-start 레코드는 없다. 18:06에는 관측성 export가 HTTP 200으로 처리됐다.

traceback과 Uvicorn 0.51 시작 경로를 대조하면 다음 흐름이 확정된다.

```text
기존 앱 PID가 단일 인스턴스 잠금을 보유하고 생존
-> 두 번째 앱/백엔드 실행 시도
-> 앱 lifespan의 acquire_single_instance_lock()이 거부
-> RuntimeError("Instance already running")
-> Uvicorn lifespan.should_exit
-> STARTUP_FAILURE 값 3으로 SystemExit
-> 기존 백엔드는 계속 요청 처리
```

traceback의 `uvicorn/server.py` 106행은 bind 실패 분기가 아니라 lifespan startup 실패
분기다. 사건 버전의 단일 인스턴스 guard가 살아 있는 PID를 감지하면 위 RuntimeError를
발생시키며, 새 backend-start가 없고 기존 HTTP가 생존한 시간축과 정확히 맞는다. 따라서 상태는
`CONFIRMED_SINGLE_INSTANCE_GUARD`다. 당시 PID·포트 스냅샷은 운영 가시성 보강 자료일 뿐,
원인 확정에 필수적인 누락 증거가 아니다. `crash.log`라는 파일명은 첫 백엔드가 죽은 것처럼
보이게 할 수 있으나 실제로는 두 번째 시작 거부 기록이다.

---

## 8. CSV와 메모리 증거 판정

### 8.1 CSV

- 18:06 관측성에서 queue 0, drop 0이 확인된다.
- 18:10 메모리 collector에도 queue 0/5000, drop 0, lag 0.4초가 기록되어 있다.
- 현재 확인 가능한 데이터 폴더에는 17:34~17:42 사건 구간을 포함하는 CSV 파일이 없다.
- 사건 뒤 확인되는 다음 별도 CSV 시작 파일은 18:12:52다.

따라서 “CSV logger가 18:06에 밀리지 않았다”는 것은 확인되지만, “17:34의 27초 동안 CSV
행과 값이 누락되지 않았다”는 것은 확인되지 않는다. `PLC-CSV 영향`은 `INCONCLUSIVE`다.

### 8.2 메모리

- 18:10:37 RSS는 약 796MiB다.
- leak suspect는 0개다.
- CSV, 관측성 오류 큐, SPOT image state collector severity는 `ok`다.
- `facility.plc_history`는 용량 예산상 `ok`지만 수집 상태가 `slow/stale`로 기록됐다.
- 메모리 profiler는 18:08:16부터 활성화되어 있었다.

따라서 이 메모리 파일은 누수 징후가 없다는 증거로는 사용할 수 있지만, profiler가 켜지지 않은
완전한 수동 관찰 기준선으로 사용할 수는 없다. 재발 수집에서는 Design 문서대로 profiler와
강제 GC를 사용하지 않는다.

---

## 9. 현재 가설별 판정

| 가설 | 현재 판정 | 확신도 | 근거 | 최종 확정에 필요한 증거 |
|------|-----------|--------|------|--------------------------|
| 마지막 27회는 빈 문자열 타입 변환 실패 | `CONFIRMED` | 높음 | 오류 원문, 사건 1.0.15 코드, 시작 36/36 상관 일치 | 없음 |
| 마지막 27회가 EX/LS 통신 실패 때문에 발생 | `EXCLUDED_FOR_17:34_WINDOW` | 높음 | 36/36 시작 오류, 그중 16회 EX·LS 무오류 120초 창 | 사건 판정에는 없음; 현재 버전 회귀는 선택 |
| 하루 전체에 EX/LS 통신 문제가 전혀 없음 | `EXCLUDED` | 높음 | Extruder 234, LS 233 오류 레코드 | 하위 네트워크 원인은 별도 수집 |
| SPOT image 오류는 ConnectTimeout | `CONFIRMED` | 높음 | 19개 ConnectTimeout, 약 2초 | 없음 |
| SPOT 하위 원인은 장비 자체 | `INCONCLUSIVE` | 낮음 | 패킷·장비 로그 없음 | SYN/SYN-ACK, 장비 로그 |
| SPOT 하위 원인은 서버 NIC/케이블/스위치 | `INCONCLUSIVE` | 낮음 | NIC·스위치 전후 카운터 없음 | ping, NIC, 스위치 로그 |
| 29.8 req/s가 SPOT timeout을 유발 | `INCONCLUSIVE` | 낮음 | 정상 성공 구간 RPS만 존재 | 오류 순간 RPS와 단계별 부하 시험 |
| SystemExit 3은 두 번째 실행의 단일 인스턴스 guard 거부 | `CONFIRMED_SINGLE_INSTANCE_GUARD` | 높음 | Uvicorn 106행, 상수 3, 사건 guard, 새 backend-start 없음, 기존 HTTP 생존 | 없음; 향후 PID·포트는 보강 자료 |
| CSV가 사건 중 정상 기록됨 | `INCONCLUSIVE` | 낮음 | 해당 시간 CSV 없음 | 사건 구간 CSV 또는 재발 수집 |
| 메모리 누수가 직접 원인 | `NOT_SUPPORTED` | 중간 | leak suspect 0, collector budgets ok | profiler 없는 장시간 기준선 |

---

## 10. 25개 검증 항목 진행표

| ID | 상태 | 현재 증거 또는 남은 작업 |
|----|------|---------------------------|
| SAFE-01 | `CONFIRMED_FIELD` | 사용자 승인, 관리자 preflight, 앱 무변경 안전 조건 통과 |
| ENV-01 | `CONFIRMED_FIELD` | 실제 서버의 process·port·SPOT 설정 확인 |
| BASE-01 | `CONFIRMED_FIELD` | raw·sanitized 분리, manifest·SHA-256·CRC 확인 |
| PLC-01 | `CONFIRMED_OFFLINE` | 사건은 시작 36/36 오류와 16회 EX·LS 무오류 창으로 판정; 현재 버전 재시작은 선택 |
| PLC-02 | `CONFIRMED_OFFLINE` | 빈 문자열 타입 오류 원문과 사건 1.0.15 코드 확인 |
| PLC-03 | `CONFIRMED_FOR_INCIDENT` | 마지막 구간 및 독립 시작 16회에서 EX 오류 0; 하루 전체 별도 통신 오류는 분리 |
| PLC-04 | `CONFIRMED_FOR_INCIDENT` | 마지막 구간 및 독립 시작 16회에서 LS 오류 0; 하루 전체 별도 통신 오류는 분리 |
| PLC-05 | `CONFIRMED_OFFLINE` | 마지막 세션 17:36:21 Running 복구 |
| SPOT-01 | `CONFIRMED_FIELD` | 180 sample·1,080 GET과 오류 5회 시간축 확보 |
| SPOT-02 | `CONFIRMED_FIELD` | PCAPNG raw flags·sequence로 08:33 충돌 직접 확인 |
| SPOT-03 | `CONFIRMED_FIELD` | ping 2,619/2,619 성공, 오류 시각 대조 |
| SPOT-04 | `CONFIRMED_FIELD` | NIC error·discard delta 모두 0 |
| SPOT-05 | `GAP_NONBLOCKING` | 같은 시간의 스위치 port counter·event 미확보 |
| SPOT-06 | `GAP_NONBLOCKING` | SPOT 장비 내부 service 상태 로그 미확보 |
| SPOT-07 | `CONFIRMED_FIELD` | 오류 15ms 뒤 다음 TCP 성공과 후속 정상 traffic 확인 |
| PROC-01 | `CONFIRMED_FIELD` | process before·after CSV 확보 |
| PROC-02 | `CONFIRMED_FIELD` | port owner before·after CSV 확보 |
| PROC-03 | `CONFIRMED_OFFLINE` | Uvicorn startup stack·단일 인스턴스 guard·기존 HTTP 생존 일치 |
| COMMON-01 | `CONFIRMED_FIELD` | HTTP·CSV queue·메모리·browser 상태와 복구 교차 확인 |
| LOAD-01 | `NOT_TRIGGERED` | 실제 오류와 TCP sequence를 확보해 위험한 추가 부하 불필요 |
| LOAD-02 | `NOT_TRIGGERED` | 앱 경로에서 원인이 확인돼 장비 직접 반복 시험 불필요 |
| PLC-NET-01 | `NOT_TRIGGERED` | 사건 PLC 오류에 EX·LS read failure가 동반되지 않음 |
| REG-01 | `NOT_APPLICABLE_YET` | 향후 패치 후 수행 |
| REG-02 | `NOT_APPLICABLE_YET` | 향후 패치 후 수행 |
| RELEASE-01 | `NOT_APPLICABLE_YET` | 향후 패치·회귀 통과 후 수행 |

---

## 11. 현장 실행 전 사용자 확인 상태

### 11.1 확인된 답변

| 항목 | 답변 | 조사 반영 |
|------|------|-----------|
| 현재 Codex PC가 실제 통신 서버인가 | 아니오 | 이 PC에서 앱 실행·패킷·ping·NIC 수집을 하지 않음 |
| 사건 뒤 앱 재설치 또는 업데이트 여부 | 예 | 현재 1.0.16과 사건 당시 높은 신뢰도 1.0.15를 분리해 판정 |
| 유지보수 가능 시간 | 아무 시간이나 가능 | 현재 버전 재시작을 선택할 경우 일정 제약 없음; 별도 실행 승인 문구는 유지 |
| SPOT 스위치 로그 담당자 | 사용자 본인이 가능 | 실제 서버 수집과 같은 15분의 포트 카운터·링크 로그 요청 가능 |
| 실제 서버 Windows 관리자 권한 | 사용 가능 | `pktmon` TCP 캡처와 NIC·이벤트 증거 수집 가능 |
| 실제 서버 명령 실행자 | 사용자 본인이 직접 실행 | 비개발자용 관리자 실행 패키지와 화면 절차를 제공 |

### 11.2 실행 시 자동 확인할 항목

| 항목 | 확인 방법 | 실패 시 조치 |
|------|-----------|------------|
| 증거 저장 공간 5GB 이상 | 수집 스크립트가 실제 서버 드라이브를 확인 | 수집 전 자동 중단 |
| 앱 `/health` HTTP 200 | localhost GET 사전 점검 | 앱을 자동 실행하지 않고 중단 |
| 기존 `pktmon` 필터 없음 | 관리자 권한으로 filter list 확인 | 기존 필터를 삭제하지 않고 중단 |
| SPOT 설정 주소 존재 | 실제 서버의 승인된 로컬 config 읽기 | 주소를 채팅에 쓰지 않고 현장 입력 |

비개발자용 상세 절차는
`docs/02-design/features/runtime-error-root-cause-validation.field-guide.md`에 기록한다.

SPOT IP, PLC IP, 내부 URL은 채팅이나 저장소 문서에 적지 않는다. 실제 서버의 설정값을
PowerShell 변수에 현장에서 직접 입력하거나 승인된 로컬 설정에서 읽는다.

---

## 12. 사용자 확인 뒤 실행 순서

### 12.1 현재 PC가 실제 서버인 경우

1. 앱이 꺼진 현재 상태에서 P0 프로세스·포트·NIC·시간·디스크 기준선을 저장한다.
2. 증거 폴더와 manifest를 생성한다.
3. 현재 1.0.16 시작 회귀 확인을 사용자가 원하고 유지보수 승인이 있을 때만 콜드 스타트를 1회 수행한다.
4. 선택적 콜드 스타트를 했다면 앱 조작 없이 90초 관찰하고 로그·오류 큐·CSV를 보존한다.
5. 정상 운전 상태에서 SPOT TCP, ping, NIC, 앱 관측성을 15분 동시 수집한다.
6. 네트워크 담당자가 같은 15분의 스위치 포트 카운터와 링크 로그를 보존한다.
7. 프로세스·포트와 공통 건전성의 후 상태를 저장한다.
8. 수집기를 종료하고 EX·LS·SPOT·HTTP·CSV 정상 복구를 확인한다.
9. 원본 해시와 외부 공유용 정제본을 만든다.

### 12.2 현재 PC가 실제 서버가 아닌 경우

현재 답변에 따라 이 절차를 사용한다.

1. Design 문서와 승인된 수집 스크립트만 실제 서버로 복사한다.
2. 복사 전후 스크립트 SHA-256을 비교한다.
3. 사용자가 실제 서버에서 관리자 실행 파일을 더블클릭해 P0/P1을 직접 실행한다.
4. 원본은 서버 내부에 보관하고 정제 zip, summary, NIC/ping/packet 증거만 전달한다.
5. 전달받은 파일의 SHA-256과 실행 ID를 이 문서에 추가한다.

### 12.3 준비된 현장 패키지

| 항목 | 값 |
|------|----|
| ZIP | `artifacts/runtime-error-root-cause-validation-field-kit-20260717_203214.zip` |
| ZIP 크기 | 19,300 bytes |
| ZIP SHA-256 | `C7F6CC5EA27FB8F32B4A840B5150D7B971A619793177ACC88DCF1F333221DF44` |
| 포함 파일 | 관리자 CMD, wrapper PS1, 읽기 전용 관측성 PS1, 한국어 안내서, manifest |
| 제외 파일 | 부하 QA 도구, 앱 실행 파일, 설정, 로그, 내부 주소 |
| PowerShell parser | 오류 0 |
| wrapper self-test | `SELF_TEST_PASS` |
| ZIP manifest 검증 | 필수 파일 누락 0, 금지 파일 0, 내부 파일 해시 불일치 0 |
| 관측성 collector mock E2E | 12/12 GET, raw 12, summary·ZIP 생성, mock IP 정제 확인 |
| pktmon 무필터 판정 | 한국어 `없음`, 영어 `None`·`There are no packet filters` 테스트 통과; 알 수 없는 출력은 안전 중단 |
| pktmon 출력 인코딩 | 코드페이지 949에서 UTF-8 직접 캡처 실패 재현, 실행 구간 UTF-8 적용 시 성공, 종료 후 원래 인코딩 복구 확인 |
| pktmon 동시 관리자 보호 | 등록 직후·종료 직전 filter list가 다르면 전체 remove를 건너뛰고 실패 기록 |

wrapper의 실행 가능 코드에는 비ASCII 문자가 없어서 Windows PowerShell 5.1의 BOM 없는 UTF-8
해석 문제를 피한다. 사용자 설명은 `README_KO.md`에 분리했다.

이전 `20260717_170809`와 `20260717_200829` 패키지는 폐기한다. 첫 패키지는 무필터 출력 전체를
기존 필터로 오판했고, 두 번째 패키지는 관리자 PowerShell 코드페이지 949가 pktmon UTF-8 출력을
깨뜨리는 조건을 처리하지 못했다. 두 실행 모두 사전검사에서 중단되어 pktmon 수집과 설정 변경은 없었다.

---

## 13. 안전·복구 상태

- 이번 오프라인 분석에서는 앱, 설정, 네트워크, 장비를 변경하지 않았다.
- 현재 확인 시점에 SmartFactoryLogger 프로세스와 포트 8000 LISTEN은 없었다.
- 앱이 꺼진 이유는 추측하지 않는다. 사용자 확인 없이 자동 실행하지 않는다.
- `pktmon`, ping, 부하 시험은 시작하지 않았다.
- 오류 큐를 비우지 않았다.
- 패킷 원본과 내부 주소를 외부에 출력하지 않았다.
- 로직 패치는 수행하지 않았다.

---

## 14. Do 완료 조건

다음 항목이 충족될 때만 PDCA Do를 완료한다.

- [x] 현재 Codex PC가 실제 서버가 아님을 확인
- [x] 실제 서버와 현장 실행자 확인
- [x] SAFE-01 사용자 승인과 관리자 preflight 기록
- [x] ENV-01 실제 서버·포트·대상 확인
- [x] BASE-01 manifest/index/hash 완료
- [x] PLC-01~03 사건 원인 오프라인 판정 — 현재 버전 재시작은 선택 사항
- [x] PLC-04~05 CSV 영향과 복구 범위의 증거·자료 제한 기록
- [x] SPOT-01~07 동시 증거 수집과 미확보 자료 기록
- [x] PROC-03 오프라인 원인 확정 — PROC-01~02는 향후 재발 시 선택적 보강 자료
- [x] COMMON-01 전후 건전성 확인
- [x] 모든 수집기 종료와 정상 복구 확인
- [x] P2 미실행 시 조건과 사유 기록
- [x] 운영자 제공 자료와 분석 결과의 역할 분리 검토

---

## 15. 버전 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| 0.1.0 | 2026-07-17 | 제공 증거 오프라인 분석, 환경 자동 확인, 25개 ID 진행 상태와 현장 질문 기록 |
| 0.2.0 | 2026-07-17 | AppData·빌드·Windows 이벤트·시작 36회·Uvicorn guard 대조로 PLC 및 SystemExit 판정 정정 |
| 0.2.1 | 2026-07-17 | 현재 PC 비서버, 사건 후 업데이트, 유지보수 가능, 스위치 로그 접근 가능 답변 반영 |
| 0.3.0 | 2026-07-17 | 실제 서버 관리자 권한·직접 실행자 확인 및 읽기 전용 15분 현장 수집 패키지 준비 |
| 0.3.1 | 2026-07-17 | 현장 패키지 parser·self-test·정제·ZIP manifest·SHA-256 검증 결과 고정 |
| 0.3.2 | 2026-07-17 | localhost mock으로 관측성 collector 12 GET·raw·summary·ZIP·IP 정제 종단 시험 통과 |
| 0.3.3 | 2026-07-17 | 수집 중 pktmon filter 상태 변경 경쟁 조건을 탐지해 타 관리자 filter 삭제 방지 |
| 0.3.4 | 2026-07-17 | 실제 서버 한국어 무필터 출력 오판 확인, 다국어 무필터 판정 self-test 추가, 현장 패키지 1.0.2 재발행 |
| 0.3.5 | 2026-07-17 | 실제 서버 코드페이지 949의 pktmon UTF-8 출력 깨짐 확정, 임시 UTF-8 적용·원복 검증, 패키지 1.0.3 재발행 |
| 1.0.0 | 2026-07-20 | 실제 서버 현장 수집과 raw PCAP 분석 완료, TCP port 재사용 충돌 확인, Do 종료 |
| 1.0.1 | 2026-08-06 | 완료된 현장 조사 상태와 후속 운영 결론의 문서 경계를 명시 |
