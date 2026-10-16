# CPU 샘플을 포함한 health 지연 진단

2026-10-16. 설치 앱은 1.0.29 / `acaf77d95101a050f4d3ecd76125d3502036f5a7`이며
이 작업은 진단 도우미에만 적용한다. 출시 판정은 HOLD다.

## 목적과 이전 증거

[이전 같은 요청 추적](production-release-risk-validation-outlier-trace-20261016.report.md)의
203.3337ms 요청에서 PLC 조회 내부 186.6288ms 중 CSwitch 기준 CPU 배정 구간은
181.1570ms였다. CPU 배정 시간에는 인터럽트 실행이 포함될 수 있어 함수 실행 비용으로
단정할 수 없다. CPU 샘플·스택과 DPC/ISR을 추가하여 같은 요청 안에서 구분한다.
기존 15분 QA 실패와 물리 경계 시험 미완료를 이 진단으로 대체하지 않는다.

## 첫 CPU 프로파일 시도의 중단

`PDCA_CPU_STACK_20261016_72d6a1ce`에 기존 프로파일의 파생본을 준비했다.
기존 Thread/CSwitch/ReadyThread 정보에 Loader, DPC, Interrupt, SampledProfile과
SampledProfile 스택을 추가했다. 64KiB × 1024 버퍼, 최대 수집 900초,
독립 guard 960초, ETL 상한 256MiB를 유지했다. 버퍼 합계는 프로세스 전체 메모리
상한을 의미하지 않는다. 로컬과 서버의 WPR 프로파일 구문 확인은 exit 0이었다.

프로파일과 manifest만 바꾼 첫 서버 실행은 helper 내부의 기존 고정 프로파일 해시와
일치하지 않아 `health-trace-profile-pin`에서 중단됐다. 이 검사를 사전에 놓쳤다.
제어 폴더는 `Dfa34ef22c3df`, 결과는 `H965671fec410`, trace 폴더는
`T5d71a8f9a2f7`이다. 인증된 launcher SHA256은
`a6f5ef192afb0095c88364a59475276bec1411e614eef961d374abec6406292a`다.

`failed-capture-audit-r2.json`에서 trace 폴더의 파일이 사전 실패 요약 하나뿐임을
확인했다. WPR·요청 수집은 시작되지 않았고 관련 실행 프로세스도 남지 않았다.
외부 실행기의 `run_path` 누락 오류는 이 사전 중단을 처리하면서 발생한 추가 보고 오류다.
이 추가 보고 오류까지 수정됐다고 주장하지 않는다. 최초 audit 명령의 배열 구성 오류와
exit 1도 보존했으며, 수정한 읽기 명령은 exit 0이었다.

## 고정 프로토콜을 구분한 수정

helper commit `bb12f6ee975b1cda80f286dca3a80a830e06ac41`은 기존 프로파일 pin을
완화하지 않고 CPU 진단용 요청·contract·lease·scope를 별도로 추가했다.

- 요청: `sfl-health-cpu-outlier-request-v1`
- contract: `sfl-health-cpu-outlier-contract-v1`
- lease: `sfl-health-cpu-outlier-lease-v1`
- 프로파일 SHA256: `3ad310b110ead5c2867b9632ff96ec71e0381a030bac7f7ec91bddf5f5c94fee`
- 결과 범위: `CPU_OUTLIER_CAPTURE_NOT_FIELD_PERFORMANCE`

기존 6초·900초 scheduling 전용 계약은 유지했다. 새 계약은 CPU 모드·900초·고정
프로파일을 함께 확인한다. 예를 들어 CPU 계약에 기존 프로파일을 넣거나, 기존 계약에
CPU 프로파일을 넣으면 둘 다 실행 전에 거부한다.

검증 기록은 `PDCA_CPU_STACK_20261016_72d6a1ce`에 있다.

| 실제 수행 검사 | 결과 |
| --- | --- |
| collection/trace/runner 단위 검사 | 36개 통과, exit 0 |
| `test_health_trace_validation.py` | 9개 그룹, exit 0 |
| `test_health_entry_validation.py` | 8개 그룹, exit 0 |
| 변경 Python 파일 Ruff | exit 0 |
| `git diff --check` | exit 0 |

CPU 계약은 정상 2개·거부 7개 경로를 확인했다. 실제 개발 PC의 상위 job 때문에
독립 실행이 허용되지 않는 경우에는 자식을 재개하기 전에 정리되는 것을 확인했다.
이 로컬 검사들은 서버에서 실제 WPR을 실행했다는 증거가 아니다.

## 실행 파일과 서버 전달

`PDCA_CPU_BUILD_20261016_b7497ef0`에서 위 commit의 Git 소스 85개를 추출하여
PyInstaller 빌드 exit 0을 확인했다. 추출 소스와 의존성은 빌드 전후 같았다.
제품 설치본은 재빌드하거나 재설치하지 않았다.

| 항목 | 바이트 / SHA256 |
| --- | --- |
| 진단 EXE | 16,091,371 / `97d171c86b97a08ddbdbff2a12799f3bd46d5d4b36f60b5bd455bd556b910481` |
| package manifest | 1,759 / `cedbc6aed23eb814635b902caaf4f9edac5e3077d854b7afdd1cd2b8afd99117` |
| helper-source.zip | 335,464 / `2aeba7b09971cf88cb8d51ee36705c0a9018b0ec14952822066ac5633e8962aa` |

`verify_frozen.py` exit 0: describe exit 0, 틀린 pin·섞인 시간·중복 JSON key·빈 설치
폴더는 각각 기대한 exit 1이다. 유효한 CPU 요청은 새 계약과 worker까지 진입한 뒤
빈 설치 폴더의 정확한 파일 집합 검사에서 중단됐다. 실제 WPR은 시작하지 않았고
worker가 종료됐다. `frozen-verification.json`은 이 제한된 검사 범위를 명시한다.

`PDCA_CPU_FIELD_20261016_a0294bd3`에서 새 묶음을 준비하고
`Z:\SmartFactory\20261016\send\CS29R2_20261016_a0294bd3`를 거쳐 CRD 탐색기로
서버 `C:\Users\user\Desktop\SmartFactory\CS29R2_20261016_a0294bd3`까지 복사했다.
19개 파일, 16,907,997 bytes를 인증된 SSH에서 전부 검산했다.
최종 확인은 `server-delivery-verification.json`이며, 준비 단계의 원본 기록은 재작성하지 않았다.

## 현장 조건과 실행

14:11:47 KST에 앱이 count-to-zero 전환으로 제품·금형번호를 비웠다.
사용자는 현재 생산 중이 아니라고 답했다. 실행 직전에는 작업자가 14:21:00 KST에
`60374·1`을 입력한 사실을 확인했다. 첫 bootstrap은 비어 있는 작업 정보를 예상했기
때문에 제어 프로세스·WPR 생성 전에 exit 1로 중단됐다.

작업자가 입력한 값을 바꾸지 않고, 사용자 답변 `NOT_IN_PRODUCTION`과 관찰된
작업 정보 `60374·1`을 모두 기록했다. 작업 정보 입력만으로 생산 시작을 추정하지 않는다.
이 조건의 결과는 생산 중 성능 QA로 사용하지 않는다.

새 bootstrap은 같은 작업 정보와 갱신 시각, 앱 프로세스 세대, Running 1.0.29,
고정된 실행 파일·요청을 다시 확인하고 14:24:35 KST에 SSH로 실행했다.
사용자의 수동 PowerShell 실행은 필요하지 않았다.

- 요청 SHA256: `e5bae3ce81bae92ab5d23a4b2ebe593a7426771b86e74b748cc56c561ca01494`
- 제어 폴더: `C:\Users\user\Desktop\SmartFactory\D1420193f234f`
- 결과 폴더: `C:\Users\user\Desktop\SmartFactory\Hb598a1f04e98`
- 독립 감시자 PID 9448, 실행기 PID 17280
- 실행 시점 범위: `CPU_OUTLIER_DIAGNOSTIC_USER_REPORTED_NOT_IN_PRODUCTION`

이 절의 실행 시작 기록은 완료·추적 품질·원인 판정의 증거가 아니다.
완료 후 인증된 결과 해시, 프로세스 정리, 설정 보존, 같은 요청의 시계·native 수명과
추적 내용을 검산해야 한다. 서버 작업 후에는 Smart Factory를 전면 표시한다.

## 실행 종료와 조건 관찰

sequence 401, probe `c0c1fec208a8435e8e5f3d3b6637ab8b`에서 205.8605ms가 관찰되어
402건으로 수집을 끝냈다. 감시자 결과는 14:38:53 KST에 저장됐으며 실행기 exit 0,
stdout/stderr 작성 종료, 감시자·실행기 프로세스 부재를 14:39:02 KST에 확인했다.
인증된 launcher SHA256은
`d99ea8118bb375b0f49831e0aa03b7a765478af3ca8bfdc61bd08fe8b61786bc`다.

14:34 화면에는 속도 5.5mm/s, 압력 162.0bar, 카운트 3이 표시됐다. 14:45 화면은
속도·압력 0, 카운트 8이었다. 따라서 사용자의 비생산 답변을 전체 측정 구간의
고정 부하 증거로 해석하지 않는다. 작업 정보와 실제 움직임 관찰을 별도로 보존하며
이번 health 단독 수집을 생산 중 동시 부하 QA로 대체하지 않는다.

CRD 탐색기에서 결과 폴더를
`Z:\SmartFactory\20261016\return\CPU_a0294bd3\Hb598a1f04e98`로 복사했다.
최초 키보드 복사는 대상 폴더가 생성되지 않았으며, 화면과 파일 부재를 확인한 뒤
탐색기 복사·붙여넣기 버튼으로 완료했다. 이후 Smart Factory를 전면 복원했다.
`smart-factory-after-cpu-capture.png`에 Running과 작업 정보 `60374·1`이 보인다.

`read_closeout.py` exit 0: 14:47:14 KST에도 앱 1.0.29 Running, 기존 main/backend
프로세스 생성 시각, logger·SPOT 서비스 세대, 작업 정보가 유지됐다.
제조사 문의 thread는 이 단계에서도 발신 메일 1건뿐이며 답변은 관찰되지 않았다.

## 오프라인 디코더 준비 범위

`PDCA_CPU_DECODE_20261016_c2af1430`에서 이미 설치된 TraceEvent 4.0.0과 동일한
lock 파일로 별도 분석 도구를 빌드했다. 빌드 exit 0, 경고·오류 0이다.
처음 사용한 `dotnet build --locked-mode`는 지원되지 않아 exit 1이었고, 올바른
`RestoreLockedMode=true` 속성으로 수정했다. 기존 설치 앱과 서버 도구는 변경하지 않았다.

기존 scheduling-only ETL을 이용한 회귀 확인은 exit 0이며 CPU 이벤트·스택 0개를
정확히 보고했다. 헤더의 7개 시계·손실·프로세서 필드는 기존 독립 raw 검산과 일치했다.
틀린 ETL 해시와 기존 출력 폴더는 각각 비정상 종료로 거부했고 기존 결과를 덮어쓰지 않았다.
CPU payload 합성 검사에서는 정상 3개·변조 8개를 각각 수용·거부했다.
이 결과만으로 새 CPU 이벤트나 같은 요청 결합을 검증했다고 주장하지 않는다.

디코더는 원본 ETW와 변환 ETLX의 CPU 이벤트를 함께 내보낸다. 두 경로 모두 TraceEvent를
사용하므로 변환·payload 대조이며 독립 ETL reader 검증과 구분한다. 심볼 자동 조회는
사용하지 않고, Python 함수 이름이나 원인을 추측하지 않는다.

## 회수 검산과 같은 요청의 CPU 구간

`recover_and_review_cpu.py` exit 0으로 481개 파일, 103,204,289 bytes를 인증된
SSH launcher 해시와 대조했다. 수집기·coordinator exit 0, 남은 worker 0,
WPR 정상 저장·정리, 기존 앱 세대와 설정 해시 보존을 확인했다.
ETL은 76,546,048 bytes이며 SHA256은
`0768ac65ce0b0aad4a87edaccd096df3bd7660d13f748be4faa65df51ee148fa`다.

CPU 디코더 실행은 exit 0이었다. CPU 샘플 112,478개, DPC 46,312개,
ISR 30,625개를 읽었으며 ETW 원문과 ETLX 변환의 선택 payload 대조도 exit 0이다.
전체에서 스택 누락 1,508개와 leaf/IP 불일치 66개가 있어 전체 스택 품질 PASS로
표시하지 않는다. 아래 PLC 구간의 170개에는 이 두 문제가 없었다.

같은 probe와 backend PID 11520의 생성 시각, worker TID 13792의 생성 시각을
결합했다. 루프·worker·수집기 세 native 시간 구간이 모두 선택 CSwitch 기록과
연결됐다. 단계 경계의 불확실성을 제외한 내부 구간은 다음과 같다.

| 단계 | 내부 경과 시간(ms) | CSwitch 배정 시간(ms) | 기록된 DPC/ISR 중첩 합집합(ms) | CPU 샘플 |
| --- | ---: | ---: | ---: | ---: |
| PLC 조회 | 182.4558 | 169.1613 | 0.2349 | 170 |
| runtime 정보 | 7.8378 | 0.4319 | 0 | 0 |
| frontend 상태 | 8.1315 | 3.3494 | 0.0548 | 3 |

배정 시간은 정확한 함수 CPU 시간으로 바꾸어 쓰지 않는다. DPC/ISR의 중첩은
같은 CPU의 구간 합집합으로 계산하여 겹친 이벤트를 중복 합산하지 않았다.

## 독립 reader와 실제 스택 대조

Windows `tracerpt`도 같은 ETL을 읽었다. 별도 오프라인 도구의 출력 한도는
2GiB, 명령 시간 제한은 기존 native 실행기의 60초다. 서버 수집의 256MiB ETL
한도나 기존 검증 계약은 변경하지 않았다. 실제 XML은 1,271,509,411 bytes,
명령은 25.54초에 exit 0, 작업 묶음의 잔존 프로세스 0으로 끝났다.

`crosscheck_cpu_xml.py` 최종 exit 0:

- 전체 이벤트 1,251,849개, 선택 scheduling 이벤트 846,818개의 시각·CPU·ID·payload 일치.
- CPU 샘플 112,478개의 시각·CPU·16-byte payload 일치.
- DPC/ISR 76,937개의 종료 시각·CPU·routine 주소 일치.
- 대상 PLC 구간의 170개 스택이 원문 stack timestamp·PID·TID·주소열과 모두 일치.
- 7개 헤더 필드 일치, EventsLost·BuffersLost 0.

`tracerpt`의 DPC/ISR 시작 시각은 FILETIME으로 변환되므로 이 필드는 독립 대조에
포함하지 않았다. XML의 schema 오류 envelope(15005 17,272개, 111 112,636개)는
보존했고, 선택 thread/stack은 그 안의 원문 바이트를 읽었다. 모든 이벤트 의미나
정확한 CPU 시간을 검증한 것은 아니다.

처음 XML 명령의 BOM 인코딩·120초 인자 오류는 실행 전 중단됐고 새 R2로 수정했다.
분석기의 기존 512MiB 해시 한도와 decoded/raw 두 stack 형태 처리 오류도 실제 입력에서
확인해 수정했다. 기존 공용 helper 한도는 그대로 두고 이 새 오프라인 분석에만 명시적
2GiB 읽기 상한을 사용했다. 앞선 실패를 성공으로 재작성하지 않았다.

## 정확한 Python 심볼과 GC 관찰

설치 payload의 `python312.dll`과 개발 PC 파일은 모두 6,927,640 bytes,
SHA256 `c045b57348c21f5f810bae60654ae39490846b487378e917595f1f95438f9546`다.
ETL의 image base `0x7ffb369f0000`, image size 6,979,584와 checksum 6,970,278도
해당 PE와 일치했다.

[Python 공식 3.12.6 배포 디렉터리](https://www.python.org/ftp/python/3.12.6/amd64/)의
`core_pdb.msi`에서 데이터 스트림을 읽어 PDB를 추출했다. 설치 프로그램은 실행하지 않았다.
처음 7za의 MSI 내부 CAB 직접 해석은 data error로 실패했고, Windows Installer의
읽기 전용 stream API로 올바른 CAB를 추출한 뒤 exit 0이었다.

PDB는 18,239,488 bytes, SHA256
`722772e58bc27487e0c2b800f5256af2b34c0b0578e5886169ca42ef1829f931`다.
DLL CodeView와 PDB의 GUID `635f2b4c-2735-4638-86d7-6217d73d5f3c`, age 1이
일치한다. TraceEvent 4.0.0의 로컬 심볼 해석기는 빌드·실행 exit 0이며, 공개 PE
export 3개의 시작 주소도 대조했다. 자동 심볼/소스 다운로드는 사용하지 않았다.

대상 PLC 구간 170개 샘플 중 **168개**에 아래 native 호출이 함께 있었다.

```text
_Py_HandlePending → _Py_RunGC → gc_collect_generations → gc_collect_main
```

관찰된 leaf는 set_traverse 46개, dict_traverse 41개, untrack_dicts 21개,
update_refs 15개, gc_list_size 13개, untrack_tuples 12개 등이었다.
첫 GC 샘플부터 마지막 GC 샘플까지 177.3945ms다. 이는 샘플 시각의 범위이며
연속 GC 실행 시간이나 정확한 CPU 시간은 아니다. 한 caller 주소의 `??deque_traverse`
범위 경고는 보존하고 확정 함수명으로 사용하지 않았다. 대상 leaf에는 그 경고가 없다.

이 한 요청에서 자동 GC가 지연에 크게 관여한 근거가 확보됐다. 아직 어떤 Python
객체가 비용을 키웠는지, 어느 GC 세대인지, 앞선 모든 지연도 같은 원인인지는 미확정이다.
GC 중지·임계값 변경이나 제품 코드를 수정하지 않았다.

## 이력 보관의 로컬 재현

15:06 KST 서버의 기존 `/api/memory/state`, `/api/memory/details` 캐시만 읽었다.
backend 세대는 같았고 `facility.plc_history`는 15,800개, 추정 110,025,398 bytes였다.
이는 샘플 기반 추정치이며 heap 전수 계측이 아니다. 수동 GC나 profiler는 실행하지 않았다.

서버와 같은 `FactoryData`·`FactoryDataHistorySample` 소스 및 Python DLL로,
개발 PC의 격리 프로세스에서 이력 보관 구조를 재현했다. 각 조건은 같은 합성 데이터와
별도 프로세스, 7회의 full GC를 사용했다. 자동 GC는 켜진 상태다.

| 보관 방식 | 이력 수 | 추가 tracked 객체 | GC 중앙값(ms) |
| --- | ---: | ---: | ---: |
| 현재 Pydantic 모델 | 15,800 | 142,249 | 29.8420 |
| 직렬화 문자열·일반 tuple 시제품 | 15,800 | 49 | 2.4357 |
| 현재 Pydantic 모델 | 36,000 | 324,049 | 61.1244 |
| 직렬화 문자열·일반 tuple 시제품 | 36,000 | 49 | 3.3430 |

모든 명시적 GC에서 회수 객체 수는 0이었다. 따라서 이 재현은 유지 중인 객체를
검사하는 비용도 증가할 수 있음을 보여 주며 메모리 누수의 증거로 해석하지 않는다.
직렬화 시제품의 1,000개 복원은 23.66/25.26ms였고 선택 항목의 JSON 값은 같았다.
실제 서버의 객체 원인, 전체 응답 계약, 동시 접근, 서버 성능 개선은 아직 증명하지 않았다.
현장 15분 QA·120분 시험·운영 승격을 대신하지 않는다.

## 보존 자료와 다음 확인

- 현장/회수: `C:/Users/user/Desktop/SmartFactory/PDCA_CPU_FIELD_20261016_a0294bd3`
- 분석: `C:/Users/user/Desktop/SmartFactory/PDCA_CPU_DECODE_20261016_c2af1430`
- 실행 검산: `field-capture-review.json`, `control-recovery-verification.json`, `server-closeout.json`
- CPU/독립 검산: `cpu-export-check.json`, `cpu-window-analysis.json`, `cpu-independent-crosscheck.json`
- 심볼/재현: `symbols/symbol-analysis.json`, `history-gc-experiment.json`

다음 변경은 이력 시간·수량·cursor·데이터 격리·공개 JSON 계약을 유지하면서 장기 보관
객체 수를 줄이는 안을 검증한다. 로컬 재현의 개선을 서버 개선으로 선기록하지 않는다.
현재 제품 설치본·롤백 기준은 그대로이며 `field_gate=NOT_EVALUATED`,
`release_gate=HOLD`, `promotion_allowed=false`를 유지한다.
