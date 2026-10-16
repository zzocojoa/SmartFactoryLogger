# Health 지연 조건부 Windows 추적 준비

작성일: 2026-10-16. 제품 설치본은 1.0.29 / `acaf77d95101a050f4d3ecd76125d3502036f5a7`이다.
현재 단계는 도우미 검증이며 현장 추적 실행·지연 원인 확정·운영 승격은 완료되지 않았다.
기존 15분 FAIL, 물리 경계 NOT_TESTED, 출시 HOLD를 유지한다.

## 변경 목적과 판정 조건

[직전 시간 구간 진단](production-release-risk-validation-observation-timing-20261016.report.md)에서
207.5919ms 응답의 route 이전·worker 대기·route 재개 이후에 지연이 분산됐다.
6초 추적에는 같은 느린 요청이 없었다. 최대 15분 동안 health 요청을 2초 간격으로
관찰하며, 처음 발생한 200ms 초과 응답 근처의 Windows 스레드 이벤트를 저장하는
별도 진단 계약을 추가했다. 제품의 임계값·앱 코드·설치본은 변경하지 않았다.

성공 조건은 다음과 같다.

1. 설치 바이트·승인 설정·main/backend PID와 생성 시각·서비스 세대가 결합돼야 한다.
2. 첫 **검증된** 200ms 초과 응답에서 수집을 끝내고 해당 probe/원본/시각을 보존한다.
   정확히 200ms는 trigger가 아니다. 450건 모두 조건을 충족하지 않으면
   `NO_OUTLIER_OBSERVED`이며 성능 QA 통과를 뜻하지 않는다.
3. 독립 감시자는 최대 960초 뒤 자신이 만든 고유 WPR instance를 정리한다.
   수집기 실패·제어 프로세스 종료·시간 제한은 정리 결과와 별개로 보존한다.
4. ETL과 요청이 같은 실행에 결합되고 선택한 요청 전후의 이벤트가 실제로 남아 있어야
   원인 분석에 사용한다. 저장 성공만으로 실행/대기 시간의 완전성을 주장하지 않는다.

## 계약과 호환성

| 항목 | 기존 진단 | 조건부 추적 |
| --- | --- | --- |
| 요청 schema | `sfl-health-diagnostic-request-v1` | `sfl-health-outlier-request-v1` |
| 측정 시간 | 6초 고정 | 최대 900초 고정 |
| contract / lease | `sfl-health-trace-*-v1` | `sfl-health-outlier-*-v1` |
| 감시 제한 | 30초 | 960초 |
| outer 제한 | 600초 | 1500초 |
| 결과 의미 | 수집 완료 | 지연 포착 / 미관찰을 구분한 수집 완료 |

고정 예산·schema를 섞은 요청은 거부한다. 잠긴 입력, 원본 보존, 고유 결과 폴더,
운영 사용자 읽기 권한, owned job 정리, ETL 상한 256MiB를 유지한다.
outer의 자연 종료 drain도 전체 시간 제한 안에 들어가며, 검산 전에
`native-child.json`을 남겨 종료 증거를 먼저 보존한다.

같은 프로파일 `SFLThreadScheduling.wprp`의 SHA256은
`603c872d5bb638661eb6e133f2b23b4f778e8bab5f440dbda3017c09ea0ff486`이다.
설정은 Memory / 64KiB × 256 buffers이며 요청 버퍼 합계는 16MiB다.
전체 WPR 프로세스의 메모리 상한이라는 뜻은 아니다. Microsoft 문서에 따라 memory
mode는 순환 버퍼이며 오래된 이벤트가 덮어써진다.
[Logging Mode](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/logging-mode),
[SystemCollector](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/systemcollector).

trigger는 응답 후 runtime/native 검증과 원본 기록을 마친 시점에 판단한다.
`response_finished_ns`와 `decision_ns`를 함께 저장한다. 두 시점 사이의 지연이나
WPR 정지 지연으로 필요한 이벤트가 사라지면 해당 추적은 분석 범위 부족으로 기록한다.
health만 추가 조회하는 조건이므로 직전 health/data/image 동시 부하 시험과 동일한
성능 실험으로 비교하지 않는다. 추적 자체의 부하도 있으므로 정식 15분 QA를 대체하지 않는다.

## SSH 실행 전제 확인

기록 위치: `C:\Users\user\Desktop\SmartFactory\PDCA_OUTLIER_TRACE_20261016_531e4f91`.

서버 `DESKTOP-CIIT7LK`를 인증된 SSH로 읽었다. 04:00:08Z의 프로세스는 관리자이나
job 내부였으며, 04:01:10Z의 limit flags는 10240 (`0x2800`)이었다.
`BREAKAWAY_OK`는 켜져 있고 `SILENT_BREAKAWAY_OK`는 꺼져 있다. 따라서 독립 실행을
**시도할 수 있는 설정**은 확인됐으나 실제 서버에서 job 밖으로 분리되는지는 아직 미검증이다.
상위 job 설정을 바꾸지 않고 `CREATE_BREAKAWAY_FROM_JOB`으로 suspended 자식을 만든 뒤,
native API로 job 밖임을 확인한 경우에만 재개하도록 했다. 실패한 suspended 자식은
종료·종료 신호 확인 후 핸들을 닫는다. [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

서버 작업 정보는 현장 입력으로 03:56:09Z에 **60313 / 금형 2**로 바뀌어 있었다.
사용자가 이전에 알려 준 60313 / 1로 되돌리지 않았다. 앱은 Running이며 운영 화면이
전면에 보이는 것을 확인했다. 새 전체 백업·앱 종료·설치·서버 설정 변경은 하지 않았다.

## 완료한 검증

아래 명령은 저장소의 `backend/.venv/Scripts/python.exe`로 실행했다.
unit 명령은 `scripts/field-v1028`에서 실행하며 각 `SFL_*_TEST_ROOT`를 위 기록 위치의
새 하위 폴더로 지정했다. 기존 결과 폴더를 재사용하지 않는다.

| 검사 | 결과 |
| --- | --- |
| `-m unittest test_field_health_collection test_field_health_trace test_field_health_runner` | 34 tests, exit 0 |
| `-m unittest test_field_health_diagnostic test_health_timing_validation test_field_health_timing` | 15 tests, exit 0; loopback fixture, lifespan/hardware 비활성 |
| `test_health_trace_validation.py --output <root>/native-trace-r3` | 8 groups, exit 0 |
| `test_health_entry_validation.py --output <root>/native-entry-r2` | 8 groups, exit 0 |
| `test_trace_validation.py --output <root>/native-lifecycle-r1` | lifecycle 14 / process suites 11, exit 0 |
| 변경 Python 8파일 `ruff check` | exit 0 |
| `git diff --check` | exit 0 |

450개 응답 전부 보존, 첫 초과에서 조기 종료, 정확히 200ms의 비-trigger,
검증되지 않은 느린 응답의 실패, schema/예산 혼합 거부, 기존 6초 경로, 정리·시간 제한을
확인했다. 실제 관리자 WPR는 이 로컬 검사에서 실행하지 않았다.

개발 PC native probe에서는 breakaway를 요청해도 다른 상위 job이 남아 있었다.
첫 시험 `native-trace-r2`는 이를 예상하지 않은 시험 assertion으로 exit 1이었다.
자식을 재개하지 않는 거부 동작은 유지하고 종료 확인을 강화했다. `native-trace-r3`는
이 제약과 실행 전 정리를 명시적으로 확인했다. 개발 PC에서 독립 실행에 성공했다고
보고하지 않는다. 서버 성공도 이 시험으로 대신하지 않는다.

제품 코드·의존성이 변경되지 않아 전체 `npm run health`는 반복하지 않았다.
변경된 도우미와 그 경계·프로세스 정리 검사를 실행했다.

## 이어갈 단계

1. 고정 helper commit의 실행 파일을 빌드하고 그 실행 파일의 요청 거부·원본 잠금·종료를 검증한다.
2. 새 묶음을 Z 전송 후 CRD 탐색기로 서버 로컬까지 복사하고 파일별 해시를 확인한다.
3. 짧고 읽기 전용인 자식으로 서버의 실제 독립 실행과 종료를 먼저 확인한다.
4. 새 runtime/config 관찰에 결합한 요청으로 조건부 추적을 한 번 수행한다.
5. 결과를 회수해 trigger와 ETL 시계·생성 세대·이벤트 범위를 대조한다.
   지연 원인을 확정하기 전 제품 수정·120분 시험·승격을 하지 않는다.
6. 작업 후 Smart Factory 창과 현재 작업 정보를 전면에서 확인한다.
