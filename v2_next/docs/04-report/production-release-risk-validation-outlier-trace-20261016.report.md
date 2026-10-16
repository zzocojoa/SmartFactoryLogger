# Health 지연 조건부 Windows 추적과 현장 분석

작성일: 2026-10-16. 제품 설치본은 1.0.29 / `acaf77d95101a050f4d3ecd76125d3502036f5a7`이다.
현장 추적에서 203.3337ms 응답을 포착하고 같은 요청의 스레드 실행 구간을 검산했다.
PLC 조회 내부 186.6288ms 중 CSwitch 기준 CPU 배정 시간은 181.1570ms였다.
함수별 실행·DPC/ISR 기여는 아직 측정하지 않아 지연 원인 확정·운영 승격은 미완료다.
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

## 실행 파일 빌드와 검사

helper commit `cd2b7d22fb2830cadacebdc26aa2e090609fe682`의 Git 바이트만 별도 source 폴더로
추출해 실행 파일을 빌드했다. 해당 helper 트리는 변경 없음으로 확인했다. 다른 작업에서
수정 중인 `AGENTS.md`와 병렬 운영 문서는 이 commit에 포함하거나 되돌리지 않았다.
빌드 전후 의존성 목록·추출 소스 해시가 같으며 PyInstaller exit 0이다.

- 폴더: 위 기록 위치의 `package-r1`
- EXE: `health_diagnostic_runner.exe`, 16,090,713 bytes
- EXE SHA256: `01f2d6009cd4255d6ac5acfb0c603f37c77191ecddc0401252d90927615873a5`
- package manifest SHA256: `c3c7ffa14d1b1709439025675f03b9af66c24e33f0e0148cd239767ccad20ffb`
- trace manifest SHA256: `d36ce79b1f56d20fbf0a3698ec655e4fae5fc411685e6cbce687672f950994ee`

이 EXE로 `--describe` exit 0, 틀린 요청 pin·섞인 6초 요청·중복 JSON key·빈 설치 폴더는
각각 기대한 exit 1을 확인했다. 유효한 900초 요청은 outlier contract와 owned worker까지
진입하고 빈 설치 폴더의 `exact-installed-file-set`에서 실패했다. 샘플 0개,
`collector-ready.json` 없음, worker 종료, active job 0, 강제 종료 없음이었다.
따라서 frozen CLI와 실패 시 중단 경로의 검사이며 실제 WPR/설치 앱 통합 PASS가 아니다.
검사 후 package의 모든 파일을 다시 검산했다.

`frozen-verification.json` SHA256:
`60f935a770f60250ec8d82eda83c47ac6e56a775ab61834f4a7bcb215c7b753b`.
`verify_frozen.py` exit 0. 이 단계에서는 서버 전달·서버 독립 실행·새 추적을 시작하지 않았다.

## 현장 전달과 독립 실행 확인

이하 결과는 위 준비 단계 이후에 수행한 별도 증거다. 기록 위치는
`C:\Users\user\Desktop\SmartFactory\PDCA_OUTLIER_FIELD_20261016_27ab2088`이다.
준비 단계의 원본 기록과 고정 해시는 다시 쓰지 않았다.

`OT29_20261016_27ab2088`의 16개 파일을 `Z:\SmartFactory\20261016\send`를 거쳐
CRD 탐색기로 서버 바탕화면 `SmartFactory` 아래까지 복사하고 모든 해시를 검산했다.
짧은 독립 실행 시험은 실제 서버에서 모든 job 밖의 자식 생성, SSH 부모 종료 이후
자식의 결과 저장, 자식 종료를 확인했다. `independent-probe-verification.json`의 판정은
`OUTLIVED_SSH_PARENT_AND_CHILD_EXITED`다. 첫 시도는 PowerShell 실행 정책에 의해
스크립트 실행 전에 중단됐다. 두 번째는 검산한 스크립트에 프로세스 범위의
`-ExecutionPolicy Bypass`를 적용했으며 시스템 정책과 상위 job 제한은 변경하지 않았다.

새 요청·감시 스크립트도 `OC29_20261016_27ab2088`로 서버 로컬 전달 후 검산했다.
인증된 SSH에서 독립 감시자를 실행했고 사용자의 수동 명령 실행은 필요하지 않았다.
감시자·실행기 종료 코드 0, 결과 저장, 수집기·제어기 종료, 남은 worker 0,
해당 고유 WPR instance 정리를 확인했다. 앱 재시작·설치·전체 백업은 하지 않았다.

| 증거 | 값 |
| --- | --- |
| 서버 제어 폴더 | `C:\Users\user\Desktop\SmartFactory\Da517479f3ab8` |
| 서버 결과 폴더 | `C:\Users\user\Desktop\SmartFactory\H5e26d951a11a` |
| 요청 SHA256 | `8a0f6d369e66810198ecc7c1362153e9278f79c121be324e004532c418f611ce` |
| 인증된 SSH에서 확인한 launcher SHA256 | `bdc7de63fbaa9713c1cb80d77e69633f5c312506b1f9d7989f134c1d32e7af81` |
| ETL | 17,563,648 bytes / `1d46748a835323608205281ccb8d9788527f960b652c77ee2773a0a5bf9c0fde` |
| 로컬 회수 | `recovered-H5e26d951a11a`, 132개 파일 / 36,554,319 bytes |

`field-capture-review.json`은 파일별 해시, 실행 전후 설정, 앱의 native 생성 시각,
서비스 세대, 53개 요청과 원본의 연결을 확인했다. 회수 파일의 자체 해시만 비교한 것이
아니라 SSH에서 확보한 launcher SHA256과 대조했다. 최종 운영 화면은
`smart-factory-after-capture.png`에 보존했다. 앱은 Running, 현장 작업 정보는 60313 / 2였다.

## 같은 요청의 추적 분석

첫 200ms 초과는 sequence 52, probe `979d3d14dabb472691884088ab5d32e1`이었다.
요청·본문 수신까지 203.3337ms였고 응답 후 trigger 판단까지 19.9551ms였다.
53건에서 조기 종료했으므로 450건 정식 QA 결과가 아니다.

원본 ETL을 선택 이벤트 디코더와 Windows `tracerpt`로 각각 읽었다. 선택 디코더는
exit 0이었다. `tracerpt` 자체도 exit 0이지만 XML이 390,928,523 bytes여서 기존
내보내기 래퍼의 256MiB 제한에서 exit 1로 끝났다. 이 실패를 보존하고, 이미 생성된
정확한 크기·해시의 XML만 별도 512MiB 읽기 상한으로 검산했다. 서버 수집 상한이나
저장소의 내보내기 기준은 완화하지 않았다. 따라서 전체 내보내기 PASS로 보고하지 않는다.

`crosscheck_outlier.py` exit 0: 두 경로의 419,947개 이벤트가 값·개수 모두 일치했다.
CSwitch 266,903, ReadyThread 150,057, 시작 190, 종료 192, rundown 2,605개이며
중복 0개였다. ETL header EventsLost/BuffersLost는 0이다. 이 값만으로 모든 종류의
추적 품질을 통과 처리하지 않는다.

`join_outlier.py` exit 0: trigger 요청의 loop·worker·collector native 수명과 QPC 구간을
결합하고, 선택 디코더 및 raw XML에서 따로 계산한 CPU별 구간이 일치함을 확인했다.
대상 3개 구간 모두 수명·CPU 연결 검사를 통과했고 거부된 결합은 0개였다.

| 대상 구간 | 벽시계 시간(ms) | CSwitch 기준 CPU 배정(ms) | 그 밖의 시간(ms) |
| --- | ---: | ---: | ---: |
| backend worker 전체 | 199.6363 | 185.8249 | 13.8114 |
| PLC 조회 내부 | 186.6288 | 181.1570 | 5.4718 |
| runtime 정보 내부 | 2.5814 | 0.4397 | 2.1417 |
| frontend 상태 내부 | 10.1708 | 4.1532 | 6.0176 |
| backend loop | 199.9651 | 3.3900 | 196.5751 |
| 요청 수집기 | 203.3395 | 0.8662 | 202.4733 |

내부 구간은 checkpoint 시각의 불확실성을 제외한 보수적인 범위다.
`analyze_phases.py` exit 0의 상세 결과는 `outlier-phase-analysis.json`에 있다.
PLC 조회 지연 전부를 CPU 배정 없이 기다린 시간으로 설명할 수는 없다.
다만 CSwitch 구간에는 미측정 인터럽트 실행이 포함될 수 있으며, Python 함수·GC·정확한
CPU 시간을 식별하지 못한다. 원인 판정은 `UNDETERMINED`다.
Microsoft도 CSwitch 기반 구간, 샘플링된 함수·스택, DPC/ISR을 별도 분석 대상으로 설명한다.
[CPU Analysis](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/cpu-analysis).

## 검증 범위와 다음 단계

`recover_and_review.py`, `crosscheck_outlier.py`, `join_outlier.py`, `analyze_phases.py`는
각각 exit 0이었다. 현장 설치 commit과 분석에 사용한 관련 backend 7파일의
`git diff --exit-code`도 exit 0이다. 이번 단계는 별도 계측·분석이며 제품 코드를 바꾸지 않아
제품 전체 테스트와 재빌드는 반복하지 않았다. 기존 15분 FAIL과 물리 경계 NOT_TESTED,
출시 HOLD를 유지한다. 이번 health 단독 추적을 이전 동시 부하 시험의 통과로 대체하지 않는다.

다음은 PLC 조회 경로의 함수별 비용과 DPC/ISR 기여를 구분할 계측을 검토하고,
확인된 원인만 보완하는 것이다. 근거 없는 캐시·임계값 변경, 같은 설치본의 반복 설치,
120분 시험·승격을 먼저 하지 않는다. 서버 작업 후 Smart Factory를 전면에 표시한다.
