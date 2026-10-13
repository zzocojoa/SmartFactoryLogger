# 2026-10-12 서버 직접 확인 기록

후속 전체 PDCA는 Do 진행 중이며 R1~R6 정식 출시는 **HOLD**다.
사용자가 다시 연결한 `DESKTOP-Extrusion`의 Chrome 원격 탭에서 직접 확인했다.
2026-10-10의 서버 오프라인 조건은 해소됐다. 유지보수는 언제든 가능하다는 기존 승인을 유지한다.

## 운영본과 현재 실행

- 화면은 `Running`, EX·LS·SPOT·Temp·Comm OK다. health는 `running=true`, `mode=REAL`,
  `app_version=1.0.26`, frozen backend를 보고했다.
- 최신 metadata와 health의 build는 `541d701d544eea6a8a4e4836047077eaf9cfaf30`이다.
  logger 세대는 `20d2045c-d2e8-41bd-907e-3786534c87c2`, 시작은 2026-10-12 07:39:37 KST다.
  현재 installer 실물의 서명·SHA256을 새로 검사한 결과와 구분한다.
- `C:\Users\user\Desktop\SmartFactory`와
  `C:\Users\user\AppData\Roaming\SmartFactoryLogger`에 일반 탐색기로 접근했다.
  설정의 실제 로그 경로는 `...\logs\test_data`, capture root는 그 아래 `spot_images`다.
- 서버 운영 화면으로 복귀한 뒤 갱신된 카메라 화면과 Running 상태를 확인했다.
  앱 정상 종료·재시작·장비 설정 수정·새 설치는 이번 읽기 단계에서 수행하지 않았다.

## 승인 기록과 설정 대조

운영 AppData의 최상위 파일 20개, 51,483바이트를 새 공유 폴더로 복사하고 개발 PC로 회수했다.
실행 상태·잠금 파일 3개와 하위 로그 폴더는 이 설정 사본에 포함하지 않았다.
공유 파일의 복사 전후 해시와 개발 PC 사본의 SHA256을 대조했다.
서버 원본 파일의 직접 SHA256 측정과 동일하게 보고하지 않는다.

| 항목 | 직접 회수한 기록과 판정 |
|---|---|
| 운영자 확인 기록 | `config.ini`의 `Operator1`, 2026-08-21T03:33:44.0146479Z. 과거 ID이며 실명·현재 QA/릴리즈 담당자 지정의 증거가 아님 |
| 기록된 프로파일 | metadata의 SPOT+ AL, App1: AL E, 200~900°C, analog 4mA 200°C/20mA 800°C |
| Low Signal | alarm disabled, threshold 2.0%, comparator `lt`, configured verification true |
| 실제 유효성 | 최신 metadata의 `config_attestation_status=fingerprint_mismatch`, effective operator/comparator verification false, drift field는 fingerprint 하나 |
| fingerprint | 현재 `f84f9d9d…4d5`, 과거 확인 `74d2c051…8ab`; build가 fingerprint에 포함됨. 이 차이만으로 실제 장비 설정 변경을 단정하지 않음 |
| readback | `not_supported`; 현재 실장비 화면·승인 프로파일과의 직접 대조/운영자 확인은 미완료 |
| 설정 의미의 보존 | 회수 config의 canonical SHA256 `55ea6a48…220`이 시작 metadata와 일치 |

`settings_file_sha256`은 attestation·민감 키를 제외한 정규화 설정 해시다.
config 원시 바이트 SHA256 `6841c848…47e`와 동일한 계산이 아니다.
계약 함수는 `backend/FacilityData/spot_config_provenance.py:69`이며 541d와 현재 HEAD 사이 변경이 없다.
초기 분석의 원시/정규화 해시 비교는 별도 보존하고 계약에 맞는 결과로 정정했다.

config의 이미지 저장은 enabled/all, 최대 2,000,000바이트, 간격 1초, retention 7일이다.
이 설정만으로 과거 이미지 부재의 삭제 원인을 확정하거나 R3를 PASS로 바꾸지 않는다.

## 실제 CSV·fact와 현재 누락 기록

| 자료 | 확인 결과와 검증 범위 |
|---|---|
| 현재 CSV 실물 | 사본 36,545,542바이트, 110열, 26,885행. 처음 07:39:37·마지막 09:21:39 KST, 동일 logger 세대. 전체 서버 snapshot은 아님 |
| 탐색기의 0KB 표시 | 실제 사본에는 위 데이터가 있었음. 디렉터리 표시만으로 실제 파일이 비었거나 저장이 중단됐다고 판정하지 않음 |
| health 관측 fact | accepted/completed 5,585/5,585, failure·pending·queue 0, initialization ready. 기존 fact hash 2.094초·index 10.953초, 전체 초기화 13.172초 |
| health 행 카운터 | rows_total 24,504. 코드상 행 구성 시 증가하므로 디스크 저장 완료의 대체 증거로 사용하지 않음 |
| image capture API | enqueued/written 5,071/5,071, queue 0, failure 0, dropped 44. fact row count 4,128,668·manifest state ready |
| image fact 실물 | 2,115,849,144바이트·4,128,668행. 공유 사본의 읽기/복사 후 해시·개발 사본 해시가 API digest와 일치. 선택 fact 전체 기본 형식 검사 오류 0, 51.578초, verifier exit 0 |

현재 44건은 이번 541d 실행 세대의 카운터다. 과거 4c97d4a drop15와 합산하거나 같은 원인이라고 하지 않는다.
541d API에는 새 원인별 drop 계수가 없어 44건의 원인은 **UNCONFIRMED**다.
startup metadata의 image written/drop/failure 0은 시작 시 snapshot이며 현재 카운터를 대신하지 않는다.

선택 fact SHA256은 `b237cdb55c4aa8e7fd3ce897445de3ff2c2ec120232b30eba44579705997f137`이다.
전 행의 열 수·ID 존재·해시/크기 형식·안전한 상대경로를 검사했다.
전역 ID/path 중복, 이미지 실물, 전체 CSV/metadata join, 원자적 서버 snapshot·종료 delta는 아직 검사하지 않았다.
`image-fact-format-precheck.json`의 `full_data_gate`는 **NOT_EVALUATED**다.

브라우저 확인 중 운영 창이 가려진 상태에서 image cache age가 컸지만 refresh in-flight·failure는 false/0이었다.
소스의 이미지 갱신은 요청에 의해 시작한다. cache age만으로 장비 장애나 writer 정지를 단정하지 않는다.
복귀 후 새 카메라 화면을 관찰했으며 UI 표시와 실제 저장·전수 검증의 범위를 구분한다.

## 실제 과거 입력의 격리 재현과 보완

회수 fact의 첫 4,091,827행을 CSV 논리 행 기준으로 원시 바이트 그대로 복원했다.
2,096,974,605바이트의 SHA256 `303725d9a1f6b8b0cb8c7046d558b10c184a30b07eb6b10ebac6ee914249e6cc`가
2026-10-09 `csv_001-metadata.bin`의 시작 manifest와 정확히 일치한다.
복원/constructor runner는 exit 0, constructor는 23.109초였다.

개발 PC의 격리 AppData·loopback HTTP·lifespan 비활성 환경에서 실제 앱의
`/api/spot/config` 경로를 시험했다. 수정 전 첫 요청은 5,079ms에 timeout,
초기화는 19,671ms였고 동시 다음 요청은 14,671ms에 응답했다.
서버 원본 timeout의 route는 기존 수집 순서에 따른 추론이며,
이 재현만으로 그 원본 사건의 원인을 확정하지 않는다.

`backend/app.py`, `backend/FacilityData/drivers/spot_api.py`,
`backend/FacilityData/spot_image_fact.py`를 보완해 설정 조회만 준비된 manifest를 즉시 읽는다.
writer 미생성·초기화 중·파일 잠금 사용 중·설정 경로 변경 후에는
행 수/해시 `null`, ready `false`를 반환한다. 원래 시작 metadata·worker·종료 manifest의
전수 검사와 fail-closed 경로는 유지한다. 서버에 새 설치본을 적용한 상태는 아니다.

| 검사 | 결과와 범위 |
|---|---|
| 대기 회귀 | 새 한 건이 수정 전 exit 1 → 수정 후 exit 0 |
| 집중 회귀 | 5건 exit 0. 초기화/파일 잠금·cold HTTP·경로 변경·준비 완료/외부 변조 포함 |
| 같은 실제 입력의 수정 후 HTTP | high-resolution clock으로 cold 65.328ms, 초기화 중 3.593ms, 완료 후 14.877ms. 세 요청 HTTP 200, runner exit 0 |
| 전수 검사 보존 | 수정 후 초기화 21.031초, 완료 후 4,091,827행·기존 SHA256·ready true 확인 |
| 전체 소스 검사 | 최종 변경 상태의 `npm run health` exit 0. backend 915건 중 914 PASS/기존 private F01 skip 1, frontend 434·Electron 94·dependency 14·frontend Node 9·QA 도우미 6, ruff·mypy 9파일 통과 |

최초 수정 후 계측의 Windows `monotonic` 값에는 0ms 표본이 있어 원문을 보존하고
`http-hires`에서 `perf_counter`로 재측정했다. 추가 회귀의 최초 실패는 테스트가
기존 helper의 예외 변환 계약을 잘못 예상했기 때문이며, 원문을 보존하고
ready false와 writer 직접 digest 예외를 함께 검사하도록 바로잡았다.
격리 시험 child 종료 코드 1은 시험 프로세스 종료 결과이며 정상 운영 종료 검증이 아니다.
세 개의 로컬 표본은 전체 R2·15/120분 현장 시험의 PASS가 아니다.
private F01은 `TEMPERATURE_GOAL_PACKAGE`가 없어 기존과 같이 미검증이다.
npm audit의 기존 root high1/moderate8·frontend high6/moderate2는 이 health로 닫히지 않는다.

## 증거와 다음 단계

개발 증거: `C:/Users/user/Desktop/SmartFactory/PDCA_FIELD_20261012_1650181c`.
공유 회수: `Z:/SmartFactory/20261012/return/PDCA_PROFILE_1650181c`.
원본 API·metadata·사본·실패/정정 분석과 SHA 영수증을 보존한다. 민감 원문은 Git에 포함하지 않는다.

- `profile-return-receipt.json`: 20개 설정 사본의 범위·해시.
- `latest-metadata-return-receipt.json`, `current-profile-analysis.json`: build·세대·fingerprint·정규화 설정 대조.
- `health-001.json`, `spot-config-001.json`, `current-image-status-analysis.json`: 실제 현재 실행의 읽기 응답.
- `current-csv-return-receipt.json`, `verify-field-data.py`와 출력: 선택한 사본의 형식·sequence·세대 대조.
- `image-fact-return-receipt.json`, `image-fact-format-precheck.json`, `verify-field-data-exit.json`: 실제 2GB fact 사본의 해시·전 행 기본 형식 및 exit 0.
- `historical-prefix-receipt.json`, `historical-constructor-benchmark.json`: 과거 시작 manifest와 정확히 같은 실물 입력.
- `cold-config-http-reproduction.json`, `http-hires/fixed-config-http-verification.json`: 실제 HTTP 수정 전/후와 입력/소스 식별값.
- `health-final.txt`, `health-final-exit.json`, `health-final-output-review.json`: 최종 전체 검사·종료 코드·전체 출력 검토. 기존 음성 fixture 진단과 신규 로그 문구를 실제 서버 오류와 구분해 기록.
- `source-state-final.json`, `source-snapshot`, `file_manifest.json`, `manifest-verification.json`: 최종 소스/문서와 이번 사본·분석의 식별·전수 해시 검증. 원본 서버 전체 검증과 구분.
- `server-monitoring-restored.jpg`, `server-monitoring-final.jpg`, `server-monitoring-closeout.jpg`: 운영 화면 복귀·연결 유지 확인. 마지막 서버 화면은 10:23 KST, Running·EX/LS/SPOT/Temp/Comm OK이며 count 31→36 변화 확인.

남은 gate:

1. 실제 담당자와 승인 장비 프로파일/실장비·comparator 확인, 최종 build의 attestation.
2. 실제 입력으로 timeout/drop44와 과거 drop15의 인과·영향을 각각 재현·대조한다.
3. 전체 과거/현재 데이터 목록, 일관된 사본, 스키마별 검사와 모든 이미지 실물·역참조, 종료 delta를 완료한다.
4. 전용 2초 client sampler·전체 성능/자원 계약과 최종 서명 설치본의 설치·복구·현장 QA·15/120분 시험을 수행한다.
5. 실제 운영 승격·적용 확인을 마친 새 build/installer만 다음 rollback 기준으로 갱신한다.

선택 사본의 해시나 기본 형식 검사는 전체 R4·현장 QA PASS가 아니다.
기존 운영본·롤백 기준은 유지하며 전체 목표를 완료로 처리하지 않는다.


## 2026-10-13 실제 과거 fact의 10회 동시 HTTP 계측

최종 health exit 0을 받은 동일 소스에서 2,096,974,605바이트/4,091,827행의
과거 입력을 사용해 새 AppData·새 loopback 서버 프로세스 10회를 실행했다.
입력은 전체 실행 동안 읽기 핸들로 보호했고 시작/끝 SHA256은 기존 과거 manifest의
`303725d9a1f6b8b0cb8c7046d558b10c184a30b07eb6b10ebac6ee914249e6cc`와 일치했다.
첫 실제 HTTP 요청을 /health로 남기고 초기화 중 2초 비중첩 health와 설정 조회를 측정했다.
TCP 연결·요청 전송·헤더 대기·본문 읽기·JSON 처리 시간을 분리했다.
200ms 판정은 요청 시작부터 전체 본문 수신까지이며 첫 표본을 제외하지 않았다.

| 회차 | health 수 | 첫 응답 ms | 최대 ms | fact 초기화 초 | child exit |
|---|---:|---:|---:|---:|---:|
| 1 | 11 | 17.2123 | 25.3309 | 17.782 | 0 |
| 2 | 11 | 13.0853 | 13.0853 | 17.823 | 0 |
| 3 | 11 | 13.2504 | 31.8273 | 17.067 | 0 |
| 4 | 12 | 12.6300 | 17.9072 | 18.083 | 0 |
| 5 | 11 | 12.1108 | 27.9928 | 17.839 | 0 |
| 6 | 11 | 15.0197 | 31.8181 | 17.077 | 0 |
| 7 | 11 | 12.6340 | 20.3772 | 17.704 | 0 |
| 8 | 12 | 14.4378 | 32.9487 | 18.385 | 0 |
| 9 | 11 | 15.1774 | 15.1774 | 17.408 | 0 |
| 10 | 11 | 13.5904 | 28.5351 | 17.458 | 0 |

전체 HTTP 142개(health 112·설정 30)는 HTTP 200·오류/timeout/200ms 초과 0이었다.
health 82개는 요청 전체가 실제 초기화 시작과 끝 사이에 포함됐다.
health 최대 32.9487ms, p50 7.7619ms,
p95 27.8027ms, p99 31.8263ms다.
분위수는 전체 112표본에 (n−1)×p 선형 보간을 적용했다. 2초 주기 실제 간격은
1.999497–2.000508초이고 비중첩이다. 모두 초기화 전/중에는 manifest 미준비/null,
완료 뒤에는 정확한 행 수·SHA256/ready와 저장·drop·실패 0을 확인했다.
10개 소유 시험 서버는 정상 제어 종료 exit 0이었다. 원본 운영 앱의 종료 증거는 아니다.

도우미 시험 3개, 본 측정 및 독립 원문/수량/시각 정산은 각각 exit 0이다.
독립 정산은 모든 응답 바이트의 해시·JSON·시간 합계, 첫 요청과 큐 비중첩,
초기화 전/중/후 경계, child 로그 872줄과 정확한 소스 8개 해시를 확인했다.
자료: `C:/Users/user/Desktop/SmartFactory/PDCA_COLD_HTTP_20261013_fc14a639`. 실제 Python QueryPerformanceCounter 시계 해상도는 1e-7초다.

한계: lifespan·장비 worker·GUI가 없는 API 격리 시험이다. R2의 전체 앱 시작 10회,
서버 시작 3회·1/3탭·자원/화면·15/120분·계측 off 비교는 여전히 미완료다.
OS 파일 캐시를 초기화하지 않았고 호스트 부하를 독점하지 않았다. 초안/summary의
동시 PLC 부하 문구는 시작 시점 가정이었으며 실제 PLC 작업은 측정 시작보다
9.086521초 먼저 종료했다.
`measurement-conditions.json`과 `review.json`에 정정하고 원문은 보존했다.
초기 timeout fixture의 Windows ConnectionAbortedError 출력은 fixture에서 처리한 뒤
동일 시험 3개를 깨끗한 출력으로 통과했다. 실제 측정 실패를 제거한 것이 아니다.
과거 서버 timeout 원인은 UNCONFIRMED, formal_performance_gate=NOT_EVALUATED다.
이번에는 제품 코드를 바꾸지 않아 동일 소스의 전체 health를 반복하지 않았다.

추가 응답 범위 확인: health 112개 모두 `running=false`, `driver_connected=false`,
CSV mode다. 격리 cwd에는 기본 v1 replay CSV가 없어 import 로그에 File not found가
기록됐고 수집 worker를 시작하지 않았다. 실제 과거 SPOT fact 초기화만 부하로 사용했다.
여기서 통과는 HTTP 응답/지연 기준이며 운영 준비/수집 정상 판정이 아니다.

최종 묶음 414파일(목록·영수증 포함)을 `Z:\SmartFactory\20261013\records\PDCA_COLD_HTTP_fc14a639`에
복사하고 모든 입력/공유 파일의 읽기 핸들을 유지한 상태에서 크기·해시와 최종 로컬 원본 해시를
확인했다(exit 0). manifest SHA256은 `02860e1ba220041d7cbc4359ab933464e1210c4fa3a0b9532b77d5840b25b9e7`다.
명시적 제외: 없음. 원본 증거는 재작성하지 않았다.
