# 서버 승인 자료 탐색과 제조사 DB 검사

2026-10-13. 승인 프로파일의 근거를 찾기 위해 기존 서버 목록과 제조사 자료 폴더를
확인했다. 추가로 발견한 SpotViewer DB의 사본 무결성과 전체 행 집계는 확인했으나
정확한 물리 모델·승인 프로파일은 확정하지 못했다. **R3 및 정식 출시 HOLD**를 유지한다.

## 탐색 범위와 발견

기존 서버 metadata 목록 `PDCA_INV_RUN_20261012_bacadba4/server-result/files.jsonl`의
411,798행을 승인/교정/구매 관련 파일명 정규식으로 검색했다. 목록 SHA256은
`e0cdb803979e0075ad0eed966e1d13dd12f4f7fa739f6443a76eb481fdabf68b`이며 일치 파일명은 0개다.
이는 정규식과 당시 목록에 한정된 결과이며, 파일 내용이나 서버 전체의 부재 증명이 아니다.

Chrome 원격 데스크톱의 Explorer에서 확인한 범위:

- 사용자 Documents 직계: EasyTune, WindowsPowerShell, Default 원격 연결 파일.
- 바탕화면 SpotViewerV520 직계: SpotViewerSetup 설치 파일. 실행하지 않았다.
- `C:/Documents/SpotViewer`: `LandData.db` 발견. 속성 화면의 수정 시각은
  2024-11-21 20:41:43 KST, 크기는 874,827,776바이트였다.

새 DB 경로는 이전 목록의 재귀 수집 대상 밖이었다. 기존 서버 CSV/이미지 cold 사본과
동일 snapshot으로 취급하지 않는다. 일반 Explorer 복사로
`Z:/SmartFactory/20261013/return/PDCA_SPOTVIEWER_bcf53e17/LandData.db`에 회수했다.
초기 단축키 복사는 동작하지 않아 빈 목적지를 확인한 뒤 Explorer 복사/붙여넣기 버튼으로
완료했다. 원본이나 기존 파일을 삭제·교체하지 않았다.

## DB 사본의 실제 검사

개발 PC 사본을 `mode=ro&immutable=1`, `PRAGMA query_only=ON`으로 열었다.
공유 사본의 복사 전/후와 개발 사본의 분석 전/후 SHA256이 같았다.

`95ca1fe92d85c1636027bb8109bf80bb3efdfd2be871319e95962f4db6e04c42`

**서버 원본 해시는 미측정**이다. 원본 DB가 실행 중이었는지와 복사의 원자성은
Explorer 시각·크기만으로 증명하지 않는다. SQLite 구조 검사는 확보한 사본에만 적용한다.

| 검사 | 결과 |
| --- | --- |
| SQLite integrity_check | ok |
| DataTag 전체 | 17,966,329행 |
| Temperature | 5,494,857행; NULL 1,689,070행; non-NULL 값 200.0–782.5 |
| TemperatureFast | 12,471,472행; NULL 0행; 값 199.0–787.5 |
| Frame / Recording / Settings / SystemInfo | 각각 0행 |
| DeviceName | SPOT 한 종류 |

태그별·DataContext별·저장 타입별 집계 합계가 전체 행 수와 일치했다.
DateTime은 정수지만 epoch와 시간대 계약은 확인하지 않았다. DataContext 의미,
NULL과 199.0의 원인, 센서 정확도·연속성·보존 누락은 미검증이다.
NULL 1,689,070행을 손상이나 수집 실패 건수로 판정하지 않는다.
설정과 시스템 정보 테이블이 비어 있어 모델·승인 설정의 근거는 얻지 못했다.

## 화면 이름과 실제 모델의 구분

전날 보존한 장비 정보 화면은 상단 `AL Spot`, 본문 `App1: AL E / 200–900°C`를
보여준다. 제조사의 [SPOT Web Simulator](https://www.ametek-land.com/simulator)는
화면의 이름을 사용자가 지정하는 장비/측정 위치 명칭으로 설명한다.
[SPOT User Guide 813452 Issue 2](https://www.ametek-land.com/-/media/ameteklandinstruments/documentation/products/fixedspotnoncontactthermometers/spot/ametek_land_813452_new_spot_pyrometer_user_guide_issue_2_en.pdf?la=en&revision=f811e381-7f32-4d05-9108-8025abee963f)의
검색 반환문도 3.3절 항목 2 Name을 같은 의미로 설명했다.
따라서 `AL Spot`만으로 정확한 모델을 확정할 수 없다.

위 설명은 검색 도구가 반환한 공식 출처의 색인 본문을 확인한 범위다. 후속 원문/그림
요청은 제조사 점검 화면을 반환했고 직접 HTTP 다운로드도 HTML 7,291바이트였다.
PDF 실물 수신·그림 대조는 완료하지 못했다. 저장한 HTML을 PDF로 취급하지 않는다.
화면 위치와 Name 항목의 정확한 대응은 이 조회로 확정하지 않았다.
소프트웨어 metadata의 SPOT+ AL 기본 문자열도 실제 모델 readback을 대신하지 않는다.

## 판정과 다음 단계

담당자 USER_SELF, 언제든 유지보수 가능, 미서명 운영, 실제 모델 미정이라는 기존
답변을 유지한다. 새 승인 자료를 찾지 못했다는 이유로 동일 질문을 반복하지 않는다.
확인할 다음 증거는 다음과 같다.

1. 장비 라벨/구매·교정 기록과 승인된 실제 프로파일의 연결.
2. 물리 LowSignal 경계 comparator 및 최종 build/fingerprint/운영자 확인.
3. 새 역사 DB 범위의 데이터 의미·보존/처리 판단. 기존 이미지 drop 사건과 합산하지 않는다.
4. 적용 전 조건 충족 후 동일 1.0.28 후보의 현장 QA·정상 시작3회·15/120분·종료 delta.

이 DB 검사로 전체 데이터 gate를 통과시키지 않는다. 현재 운영본541d와 후보4cc7393e,
각 설치본 SHA 및 롤백 기준은 유지한다. 서버 앱·장비 설정·작업 정보의 적용 변경,
설치·재시작·승격을 수행하지 않았다.

## 검증 기록

`read_db.py`, `review_db.py` actual exit0; 두 도우미 Ruff F/E9 exit0.
근거는 [실행 기록](C:/Users/user/Desktop/SmartFactory/PDCA_PROFILE_SEARCH_20261013_bcf53e17/README.md),
[DB 집계](C:/Users/user/Desktop/SmartFactory/PDCA_PROFILE_SEARCH_20261013_bcf53e17/database-review.json),
[사본 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_PROFILE_SEARCH_20261013_bcf53e17/database-copy-receipt.json)에 있다.
제품·빌드 설정 변경이 없어 완료된 health/NSIS/성능 시험은 반복하지 않았다.

선택한 닫힌 조사 기록16파일(manifest 포함), 증거117,416바이트를
`Z:/SmartFactory/20261013/records/PDCA_PROFILE_SEARCH_bcf53e17`에 보존했다.
manifest SHA256은 `ba3fae36f46ed3c04c9e2100b87b4b22d1437d3d2b59daa4a74dd77534a54f78`다.
대형 DB는 앞서 검증한 return 폴더에 보존하고 manifest의 외부 데이터 항목에
경로·크기·해시를 기록했다. 작업 폴더 전체 봉인이나 서버 원본 해시 검증을 뜻하지 않는다.
공유 보존·최종 문서/PDCA 정합성 검산 및 `git diff --check`는 exit0으로 확인했다.

## 후속: NULL 온도와 고속 온도 기록의 관계

이 절은 위 역사 DB의 의미를 추가 조사한 결과다. 장비 모델과 관찰 프로파일 승인은 이후
[장비 직접 조회·승인 기록](production-release-risk-validation-device-profile-20261013.report.md)으로
보완됐으며, 앞부분의 모델·승인 미정은 최초 탐색 시점의 기록이다.

같은 개발 사본의 17,966,329행을 읽기 전용으로 순회했다. 분석 전후 SHA256은 위의
`95ca1fe9…`와 같았다. SQL 교차 집계에서 `Temperature=NULL` 1,689,070행은 모두
`DataContext=0`이고, 나머지 Temperature 3,805,787행과 TemperatureFast 12,471,472행은
모두 `DataContext=1`이었다. 이는 저장된 값의 관계이며 enum의 의미를 확정한 것은 아니다.

`DataTagId` 순서의 Temperature 한 행부터 다음 Temperature 직전까지의 TemperatureFast를
한 저장 구간으로 묶었다. **행 인접성만 비교했으며 같은 취득 시점·원자적 측정으로 간주하지 않는다.**

| Temperature가 NULL인 구간 | 구간 수 | NULL 전체 대비 |
| --- | ---: | ---: |
| 뒤따르는 고속 값이 모두 199.0 | 1,633,135 | 96.69% |
| 199.0과 다른 고속 숫자가 섞임 | 39,418 | 2.33% |
| 뒤따르는 고속 값에 199.0이 없음 | 16,517 | 0.98% |
| 합계 | 1,689,070 | 100.00% |

반대로 Temperature가 숫자인데 뒤따르는 고속 값이 모두 199.0인 구간도 4,613개다.
따라서 NULL 1,689,070행을 모두 199.0과 같은 의미로 판정하거나, 인접 고속 값으로
채워 넣을 근거는 없다. NULL 쪽 예외 55,935구간과 반대쪽 4,613구간을 합친
60,548구간의 행ID·원시 시각·값 범위를 별도 CSV에 보존했다.
예: 행98529의 Temperature는 NULL이나 뒤따르는 두 고속 값은 343.1과 445.5다.

Temperature 태그 순서의 연속 NULL 구간은 49,558개이고, 가장 긴 구간은 179,455행이다.
실제 경과 시간의 단위·epoch·시간대 및 공정 상태 계약을 확인하지 못했으므로 이를
정지 시간이나 통신 장애 횟수로 해석하지 않는다. 행ID 연속성도 취득 데이터의 무누락을 증명하지 않는다.
Temperature 태그 안에서 원시 DateTime이 앞선 값보다 감소한 지점4개도 별도 SQL로 확인했다.
해당 행ID는 7023557, 7559151, 7974596, 10982315이며 시계 보정·저장 순서 등 원인은 미확정이다.

[제조사 SPOTPro 안내서 812953 Issue3](https://ameteklandinstrumentscn.cdn.ametekweb.com/-/media/ameteklandinstruments/documentation/products/software/spotpro/ametek_land_812953_spotpro_user_guide_issue-3_en.pdf?la=zh-cn&revision=29448605-2d36-48ac-9767-6714ea97a8b5)의
6-2쪽 색인 표는 현재 온도와 장비 속도의 고속 온도 스트림을 구분한다. 다른 소프트웨어의
이 설명은 이번 SpotViewer DB의 NULL·199.0·DataContext 계약을 증명하지 않는다.
SpotViewer 안내서 후속 검색의 점검 HTML 응답도 문서 안에 설명이 없다는 증거로 사용하지 않았다.

[전체 분석](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_NULL_20261013_c1b03095/null-analysis.json),
[예외 구간 목록](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_NULL_20261013_c1b03095/contradictory-or-unpaired-blocks.csv),
[연속 NULL 구간](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_NULL_20261013_c1b03095/null-runs.csv),
[문서 근거와 한계](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_NULL_20261013_c1b03095/source-review.json)를 보존했다.
전체 집계 정산과 별도 SQL로 재조회한 6분류 표본72개가 일치했고 분석 actual exit0이다.
[독립 검산](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_NULL_20261013_c1b03095/analysis-review.json)에서
CSV 60,548구간·연속 NULL 49,558구간/1,689,070행과 원시 시각 감소4지점을 대조해 exit0을 확인했다.
원본 DB·서버·후보 코드는 변경하지 않았다. 다음 확인 대상은 실제 기록 소프트웨어의 버전과
NULL/199.0/DataContext 변환 계약, 예외 구간의 취득 관계다. R4 원인·영향·처리 및
서버 원본 해시/사본 원자성은 미완료이며 `full_data_gate=NOT_EVALUATED`를 유지한다.

## 후속: 보존된 SPOTViewer 5.2 설치 자료의 저장 규칙

NAS 보존 목록의 `99. 참고/SpotViewerV520.zip` 사본에서 설치 파일을 추출했다.
ZIP의 전후 SHA256과 멤버 EOF·CRC를 확인했으며, `SpotViewerSetup.exe`는
124,828,528바이트/SHA256 `d0a29b4225343292c027f21c1e1aa21bc5f12d9fd94bae9de7ae9a1f1512e0bd`다.
MSI File 표에서 SpotViewer 실행 파일 버전은 `5.2.0.7443`, 주요 Land 라이브러리는
`1.6.3.7443`이었다. 설치 프로그램과 제조사 코드를 실행하지 않고, CAB·MSI를 읽기 전용으로
열어 선택 파일17개를 추출·해시 대조한 뒤 ILSpy 9.1.0.7988로 C#와 IL을 정적 분석했다.

**아래는 이 설치 자료의 구현이며 역사 DB의 실제 실행본·설정 경로는 아직 확정하지 않았다.**
서버 보존 목록에 같은 이름/크기의 ZIP이 있다는 사실도 동일 바이트나 당시 실행 이력을 증명하지 않는다.

| 확인한 구현 경로 | 이 바이트에서 확인한 규칙 | 해석의 한계 |
| --- | --- | --- |
| `TagDataContext` | `0=Unknown`, `1=TemperatureC`, `2=TemperatureF`, `3=TemperatureK` | 0 자체를 실패 플래그로 해석하지 않음 |
| `DataLogService`의 무효 `TimedDouble` | `-`와 기본 context0을 전달; 숫자 파싱 실패 시 nullable Value를 비워 둠 | 다른 비숫자 입력도 같은 결과 가능; 행별 무효 사유 미저장 |
| `SqlLiteDataLogger.Log` | Value가 없으면 null 매개변수, 있으면 소수2자리 반올림; 시각은 `DateTime.Ticks` 저장 | 원인·원시 레지스터·시간대는 이 열에 남지 않음 |
| `System5.ParseTemperature` | unsigned65534는 하한−1/무효, 65535는 상한+1/무효, 그 외 signed short는 10으로 나눠 유효 값으로 구성 | 장비가 당시 어느 레지스터를 보냈는지는 미확인 |
| `System5.ParseLiveReadings` | 스캔 중 온도 유지 상태에서도 일반/검출기 온도를 무효로 구성 | 당시 스캔 유지 사용·작동을 증명하지 않음 |
| `FileDataLogger.ReadValue` | Value 부재 시 `-` 출력; 단위 context가 있으면 표시 단위로 변환 | 모든 과거 CSV의 생성 경로·placeholder 원인이 확인된 것은 아님 |

일반 `TimedDouble`을 저장하는 DataLogService 경로는 기록할 때의 `DateTime.Now`를 쓰고,
컬렉션 직접 저장 경로는 원소의 `TimeStamp`를 쓴다. 그러나 cached 컬렉션 경로는 원소를
일반 경로에 다시 넘기므로 시각을 새로 만들 수 있다. 별도의 `ConditionalDataLoggingStrategy`는
TimeStamp를 유지하고 DataContext를 지정하지 않는 경로도 있다. 당시 선택된 기록 전략을
확인하기 전에는 모든 고속 온도 시각이 장비 자체 시각이라고 해석하지 않는다.

System5의 실제 통신 분기에서는 고속 버퍼 시각을 `DateTime.Now`에서
`deviceUpdateRate` 간격으로 역산하며, 일반 온도 태그에는 경과300ms 이상에서 갱신하는
분기가 있다. 이는 정적 구현의 조건이고, 당시 실제 취득 주기·기록 설정을 측정한 결과가 아니다.
이 차이 때문에 인접 Temperature/TemperatureFast 행을 같은 취득의 대체 값으로 사용할 수 없다.

[Microsoft DateTime.Ticks 문서](https://learn.microsoft.com/en-us/dotnet/api/system.datetime.ticks?view=net-8.0)는
0001-01-01 자정 기준 100ns 단위와 Kind에 따른 시간대 의미를 설명한다.
이번 IL에서 해당 속성 사용은 확인했으나, 역사 실행본·시간대 확인 없이 원시 정수를
확정된 UTC/KST 시각으로 바꾸거나 시간 역전을 시계 보정으로 단정하지 않았다.

Common의 생성문과 역사 DB의 DataTag/Recording/Settings/Frame/SystemInfo 정의5개는
대소문자·공백·대괄호·선택적 IF NOT EXISTS·세미콜론을 정규화한 뒤 모두 일치했다.
DB는 immutable/read-only로 열었고 전후 SHA256 `95ca1fe9…`가 같았다.
이 구조 일치는 조사한 구현과의 일관성 근거이며 정확한 역사 버전의 증명은 아니다.
NULL 1,689,070행을 일괄 저온/통신 실패/199.0으로 바꾸거나 복구하지 않았다.

[구현 검토와 한계](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_SOFTWARE_20261013_be7bb618/static-contract-review.json),
[바이트·스키마 대조](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_SOFTWARE_20261013_be7bb618/contract-verification.json),
[설치 자료 출처](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_SOFTWARE_20261013_be7bb618/installer-extraction.json)를 보존했다.
7z의 MSI 조회 exit1과 ILSpy 최신 버전 설치 exit1은 보존하고, 각각 Windows MSI 읽기 전용
API와 ILSpy 9.1로 진행했다. MSI의 Burn SHA1과 추출 CAB 검증이 성공했으므로
7z 메시지만으로 설치 자료 손상을 판정하지 않았다. 상세 실패·대체 절차는 검토 기록에 있다.

C# 추출6개·IL 추출4개와 `verify_contract.py`는 actual exit0이다.
후속 체크리스트는 당시 실행본/기록 설정의 연결, 동시기 레지스터·스캔·시계 로그 또는
행 대조 가능한 내보내기 자료, 데이터 책임자의 영향·보존/처리 결정이다.
제품·서버·원본을 변경하지 않아 health·NSIS·현장 시험을 반복하지 않았다.
R4의 원인/영향/처리와 최종 현장 종료 delta는 미완료이며 전체 출시 HOLD를 유지한다.

## 후속: 서버 설치본·설정과 과거 SPOTViewer 로그

서버 Explorer에서 `C:/Program Files (x86)/AMETEK Land/SPOTViewer/SpotViewer.exe`의
파일·제품 버전 `5.2.0.7443`을 확인했다. 설치 폴더의 선택 파일17개를 공유 return으로
복사한 뒤 개발 PC에서 대조했으며, 모두 위 보존 설치 자료의 추출 파일과 SHA256이 같았다.
실행 파일 SHA256은 `327563d27a421224dd64377fa8f102e0b3e956136bdce478ee2da66351a7a349`다.
이로써 **현재 서버에서 회수한 설치 파일과 분석한 설치 자료의 연결**을 확보했다.
2024년 당시 실행 파일·설정이 계속 같았다는 증명이나 서버 원본 해시 측정은 아니다.

`C:/ProgramData/LandInstruments/SpotViewer`의 설정·예외 기록8개와 `Logs`의 선택 로그8개도
Explorer로 회수했다. 로그 폴더에서 보인124항목 중 선택8개이며 전체 로그 조사는 아니다.
초기 Explorer 파일명 검색은 실제 존재하는 파일에도0건을 반환해 목록 탐색으로 전환했다.
검색0건을 파일 부재로 해석하지 않는다. 공유 return은
`Z:/SmartFactory/20261013/return/PDCA_SPOTVIEWER_INSTALLED_f259c582`이며
공유 사본의 복사 전/후와 개발 사본 해시가 일치했다. 서버 원본의 해시·원자적 snapshot은 미확인이다.

| 설정·구현 근거 | 확인한 내용 | 범위와 한계 |
| --- | --- | --- |
| 현재 `LoggingConfiguration.xml` | `LogGroupConfiguration`, `SettingsVersion=1.0`; Continuous/PT1S/FileStorage/CSV 두 경로에 Temperature·TemperatureFast | 바탕화면 `새 폴더 (2)` 및 NAS `출구부 온도/2호기`; 파일 수정 시각2024-11-19, 과거 설정 연속성 미확인 |
| 현재 `SpotActuatorSettings.xml` | `HoldOnScan=false` | 수정 시각2024-11-19; 이전 NULL 구간의 스캔 상태를 증명하지 않음 |
| `SettingsBase` | 같은 XML 이름을 `DataLogSettings`와 `LogGroupConfiguration`이 각각 읽음 | 전자는 `Version=1.0`을 요구하므로 현재의 다른 형식을 같은 DB 기록 설정으로 취급하지 않음 |
| `Processors.Logging.LogProcess` | 무효 TimedDouble을 `-`/기본 context0으로 전달하고 숫자 파싱 실패 시 Value를 비움; 일반 값은 Now, 컬렉션은 원소 TimeStamp | 보존 DLL 정적 구현; 당시 선택한 경로와 개별 NULL 사유는 미확인 |
| `SystemInformation.txt` | SPOTViewer5.2.0.7443 표기2회; DB 열기 실패와 multimedia Timer 시작 실패 스택 | 내용 자체의 사건 시각 없음; 수정 시각을 각 사건 시각으로 바꾸지 않음 |

설치 실행 파일의 부트스트랩은 `Tags.DataLogService`도 생성한다. 별도의
`Processors.Logging.LogService`는 LogGroupConfiguration을 사용하며 과거 예외 스택에도 나온다.
따라서 앞 절의 DataLogService만을 모든 역사 행의 유일한 생성 경로로 단정하지 않는다.
현재 설정과 기록을 수정하거나 제조사 코드를 실행하지 않았다.

로그8개는 838,860,271바이트, LF 기준6,738,533행이었다. 최초 UTF-8 분석은 디코딩 오류로
exit1이었고, 같은 바이트를 CP949 strict로 읽은 후속 분석은 exit0이었다. 대체 문자로
문제를 숨기거나 파일 인코딩을 변환하지 않았다. 내부 timestamp 범위는
2024-09-02 13:43:27.3897부터2024-10-19 12:56:55.8090까지이며,
파일 이름은 최초 사건 시각과 다를 수 있다. 이 범위가 무중단 수집이나 완전한 보존을 뜻하지 않는다.

| 선택 로그의 메시지 | 기록 수 | 확인 범위 |
| --- | ---: | --- |
| `Connection lost to device: SPOT` | 769,640 | 호출 때마다 남기는 경고 수; 독립 장애 횟수 아님 |
| `Connection lost to device: Actuator` | 5,439,082 | 동일하게 반복 경고 수로 보존 |
| `Error in MultiMediaTimerTick` | 35,272 | FileLogger의 네트워크 경로 접근 실패 스택 표본 확인; 소실 행 수로 환산하지 않음 |
| `WaitForFile` 잠금 실패 / 10회 재시도 포기 / `WriteDelimited` 오류 | 41 / 3 / 3 | 2024-09-10, NAS `LandData 2024-09-09-08-14-15.csv`; 다른 프로세스 사용 중이라는 IOException |
| 기록 창 열기 FATAL / DispatcherUnhandledException | 2 / 1 | 9월2일·4일 TimerStartException 스택 확인 |
| Actuator 스캔 스레드 예외 | 1 | 9월30일01:13:46.7545, TcpClientConnection.get_IsConnected의 NullReferenceException |

현재 설치 파일의 NLog 규칙은 Warn 이상만 남긴다. 연결 경고 출력은
`StartConnectionPolling`에서 기존 polling thread 유무를 확인하기 **전**에 발생한다.
따라서 경고 개수를 단절 횟수로 세거나 경고가 없는 시간을 정상 수신으로 판단하지 않는다.
형식 미지원/기본값 사용 경고11개와 선택 파일 순서의 timestamp 감소2개도 보존했다.

가장 긴 NULL179,455행의 원시 정수를 .NET ticks로 해석하면 날짜 표지는
2024-09-28 06:12:10.4897471–2024-09-30 08:03:00.5970325다.
**DB와 로그가 같은 시계·시간대를 썼다는 확인 없이 비교한 조건부 구간**에 SPOT 경고695,983개,
Actuator 경고4,848,837개와 위 스캔 예외1개가 들어간다. SPOT 경고의 첫/마지막 표지는
9월28일07:42:03.4282와9월30일07:35:07.3368로 NULL 양 끝과도 일치하지 않는다.
동일 시계가 확인되더라도 시간 겹침만으로 모든 NULL의 통신 원인을 확정할 수 없다.
NULL·199.0을 치환하거나 과거 소실/손상 finding을 해소 처리하지 않았다.

[설치 파일 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_INSTALLED_20261013_f259c582/installed-copy-receipt.json),
[설정 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_INSTALLED_20261013_f259c582/settings-copy-receipt.json),
[로그 사본 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_INSTALLED_20261013_f259c582/logs-copy-receipt.json),
[로그 집계·원문 표본](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_INSTALLED_20261013_f259c582/log-analysis.json),
[독립 검산](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_INSTALLED_20261013_f259c582/installed-verification.json),
[해석과 재사용 체크리스트](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_INSTALLED_20261013_f259c582/README.md)를 보존한다.
독립 검산은 사본33개 해시·XML 두 경로·rg의 로그 수준별24집계·원문 표본·정수 ticks 기반
조건부 구간 집계·분별 합계를 대조한다. 최초 코드 절의 유일성 검사 실패도 별도로 보존하고,
확인한 DataLogSettings 위치로 범위를 좁힌 최종 검산 exit0을 기록한다.

20:18 KST 서버 앱을 전면으로 복원해 Running, EX/LS/SPOT/Temp/Comm OK와 작업60322/9를
관찰했다. 기존 제품·장비 설정이나 운영본·롤백 기준을 변경하지 않았다. 남은 확인은 역사 DB와
실제 실행 경로/시계의 연결, 오류의 영향 행·보존/처리 판단, 최종 후보의 현장 검증이다.
제품 변경이 없어 health·NSIS를 반복하지 않으며 R4와 전체 출시 HOLD를 유지한다.
