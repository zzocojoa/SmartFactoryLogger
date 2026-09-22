# Temperature 후보 7시간 관찰

브랜치 전체의 완료 범위와 남은 현장·배포 조건은 [브랜치 완료 상태](../../../TEMPERATURE_BRANCH_STATUS.md)에 연결했다.
이 문서는 해당 7시간 시험의 결과와 준비 이력을 보존한다.

## 최종 관찰 결과

2026-09-21 실제 서버에서 **7시간 자연 관찰·정상 종료·원본 복귀 검증을 통과**했다.
판정은 `SEVEN_HOUR_OBSERVATION_REVIEW_PASS`이며, 전체 현장 검증이나 운영 승격 승인은 아니다.
사용자는 복귀 후 현재 실제 작업이 원본 화면과 일치함을 확인했다.
후보의 마지막 선택과 달랐지만 현재 작업 확인으로 해결했으며 앱 데이터를 수정하지 않았다.
실제 제품·금형 식별값은 공개 문서에서 생략하며 로컬 `operator-context-confirmation.json`에 보존한다.

| 항목 | 확인 결과 |
| --- | --- |
| 실행 폴더 | `C:\Users\user\Desktop\SmartFactory\U76fbb38e` |
| 관찰 | 01:23:23~08:23:24 KST, 도우미 25,202.158초, duration-complete |
| 진단 표본 | 1,552회, 같은 main 22764/backend 1340 및 logger/SPOT instance 유지 |
| 최종 CSV | 117,742행, sample_seq 1~117742 연속·중복 없음, 정상 종료 closeout |
| observation fact | 25,212행, poll 1~25212 연속, 중복·gap·잘못된 신원 0 |
| CSV→fact 연결 | key가 있는 117,737행 전부 연결, 누락 0; startup 5행은 key 없음 |
| 저장 | 표본의 reject/write/spool/fact write/link/origin 오류 0, 기존 drift 1 유지 |
| writer | 초기화 약 31ms, 표본 queue/pending 최대 각각 1, 정상 종료 drain 확인 |
| PLC·SPOT | 매 표본 두 PLC snapshot·CSV·poll 증가, 모든 fact poll success |
| 온도 상태 | valid 109,193 / under_range 8,535 / stale 9 / startup_pending 5 |
| 값 누출 | 모든 non-valid Temperature blank·origin none, 독립 불변식 위반 0 |
| Count 0/1/2 | 실제 CSV 각각 8,866 / 2,986 / 2,347행, production_stable/stabilizing 오분류 0 |
| 이미지 fact | 22,407행, final manifest의 행수·해시 일치, failure/drop 0; 이미지 본문 미회수 |
| 원본 복귀 | 기존 d7 설치본·schema 2.5.0·설정 SHA·로깅 계약 유지, 후보 state 미이관 |
| 복귀 후 수집 | 08:27:52~08:28:24 3표본, rows 1068→1224 / poll 6→38 / CSV 1,483,080→1,689,384바이트 |

Count 0/1/2의 phase 분포는 각각 setup 7,639/1,265/599행, setup_alignment 1,169/1,652/1,653행,
unknown 58/69/95행이다. 이를 실제 물리 공정의 확정 라벨로 승격하지 않는다.
under_range→valid 직접 전환 5회를 확인했다. stale 9행도 값은 비어 있으며 원인 고장을 확정하지 않는다.
fact 진단은 async_complete 23,213 / async_partial 1,998 / missing 1로 기록됐다.
부분 진단을 전체 성공으로 바꾸거나 poll 통신 실패와 혼합하지 않았다.

고정 후보 commit의 `validate_csv_v2_shadow.py`가 CSV 전체 행·metadata·observation fact·image fact와
최종 image manifest 검사에서 exit 0 / PASS를 반환했다. 추가 읽기 검토 58/58개 확인도 통과했다.
후보 정상 종료는 main/backend exit 0, forced=false, trace 정상 경계, 프로세스·포트 해제로 확인했다.
원본 준비 표본은 약 230.766초(콘솔 약 232초)이며, 기존 원본의 시작 지연 원인은 이번 결과로 확정하지 않는다.

### 최종 증거 위치

- 공유 회수: `Z:\SmartFactory\20260921\return\SFL_TRC_7H_RESULT_U76fbb38e`
- 개발 증거: `C:\Users\user\Desktop\SmartFactory\SFL_TRC_7H_R3_evidence\server-run-U76fbb38e`
- receipt: 12,482개 파일, 6,241 JSON/SHA256 쌍, 20,524,940바이트. 모두 검산했고 결과·복귀 요약 해시는 서버 콘솔과 대조.
- 후보 데이터: 선택한 5개 파일, 200,684,693바이트. 공유→개발 사본의 모든 길이·해시가 일치.
- `review-summary.json` SHA256: `35BA4966E7E29944F4B3746584B71E20B802D3A7B8DED7455E1656E57430A1E3`
- CSV SHA256: `1907F20C699D4E0D4FCCC2FDE7E45D444B6DBA27DA9BF7636532CF6F7CDF474C`
- observation fact SHA256: `915ECAA267940F37489DF01DA3BB16E81FBD08AF5A15BA8FF39EA6D6423E2A2E`
- 사용자 작업 정보 확인은 `operator-context-confirmation.json`에 기록. 앞선 `event-review-summary.json`의 확인 대기 상태를 후속 기록으로 해소.

기존 파일을 수정하지 않고 최종 사본·검산·리뷰를 추가했다. CSV 해시는 회수본에서 계산한 값이며
서버 로컬에서 별도로 다시 계산한 최종 CSV 해시가 아니다. observation/image fact는 생산자 manifest와도 일치한다.

### 남은 검증 범위

사용자가 별도로 지정한 자정 파일 전환은 아직 현장에서 검증하지 않았다. 이번 fact의 모든 poll이
success여서 실제 timeout/connection_error/http_error 복구·TTL fallback·invalid clock 현장 사건은
미검증이다. 물리 장애를 주입하지 않았다. queue/지연은 표본 통계여서 연속 최대치를 보장하지 않는다.
이번 복귀의 결과 콘솔 종료 후 생존 확인, phase 후처리 fact 생성·확정, 이미지 본문 검사는 수행하지 않았다.
`field_validation_passed=false`, `production_release_approved=false`를 유지하고 운영 설치·승격하지 않았다.

2026-09-21 사용자가 남은 현장 검증 진행을 승인하고 **최대 7시간, 자정 전환은 별도**로 지정했다.
R7 짧은 관찰·종료 CSV/fact 검증과 원본 복귀 후 수집 증가 검증에 이어 수행하는 단계다.
기존 후보 commit `72a410331ddf612e0de1a1fa2b0834432a7d7fab`의 실제 번들을 사용한다.
원본은 v1.0.26/d7a1b20이다. 후보 설치·운영 승격·제품 소스 변경은 이번 작업에 포함하지 않는다.

## 실행 묶음과 범위

- 최종 묶음: `C:\Users\user\Desktop\SmartFactory\SFL_TRC_7H_R3`
- 사용자 실행: 위 폴더의 `RUN_TRIAL.cmd` 일반 더블클릭. 관리자 실행은 거부한다.
- helper SHA256: `835570D03D97B054EDA131050711F5C34B11BAFA666EE486D348BFCC4C58E3EE`
- CMD SHA256: `5AE975737A55121704E86D3A09677C93A86A1BAE3FC64E66BE56E6F208300CBC`
- 개발 검증: `Desktop\SmartFactory\SFL_TRC_7H_R3_evidence`
- 공유 전달: `Z:\SmartFactory\20260921\send\SFL_TRC_7H_R3`
- 전달 검산 회수: `Z:\SmartFactory\20260921\return\SFL_TRC_7H_DELIVERY_R3`

R1/R2는 개발 중간 산출물이며 서버에 전달하지 않는다. 기존 R7/R4 묶음·영수증도 수정하지 않는다.
7개 파일에 준비 결과와 후보/원본 manifest가 포함된다. 실제 서버 최종 사본의 존재 확인과
왕복 파일별 검산이 완료된 뒤에만 실행 준비 완료로 보고한다. 전달 기록은 별도 evidence에 보존한다.

2026-09-21 01:18 KST 서버 탐색기에서 위 최종 절대경로와 7개 파일을 확인했다.
서버 로컬 폴더를 `Z:\SmartFactory\20260921\return\SFL_TRC_7H_DELIVERY_R3\SFL_TRC_7H_R3`로
다시 복사한 뒤 개발 묶음·고정 build manifest와 이름/길이/SHA256을 대조했다.
7개, 총 910,509바이트가 모두 일치한다. 전달 영수증은
`C:\Users\user\Desktop\SmartFactory\SFL_TRC_7H_R3_evidence\server-delivery-receipt.json`이며
SHA256은 `DA4B6F4BD607653131A8F89023FBCBAD66213398B7DE9B19DBBAE2CF1FA4626D`다.
상태는 `SERVER_LOCAL_DELIVERED_HASH_VERIFIED_NOT_EXECUTED`이며 서버 시험 실행·현장 합격을 뜻하지 않는다.

## 첫 실행과 시작 점검

사용자가 위 묶음 실행 완료를 알렸고, 실제 실행 폴더는
`C:\Users\user\Desktop\SmartFactory\U76fbb38e`다. 원본 정상 종료는 main/backend exit 0,
forced=false, 프로세스·포트 해제로 확인했다. 후보는 2026-09-21 01:23 KST에 준비됐으며
main PID 22764 / backend PID 1340이다. 첫 표본 기준 관찰 종료 예상은 당일 08:23 KST 전후이고,
이는 7시간 완료 보장 시각이 아니다. 종료·원본 복귀 시간이 추가된다.

서버 receipt 폴더의 초기 사본을 `Z:\SmartFactory\20260921\return\SFL_TRC_7H_START_U76fbb38e`로
회수했다. 개발 PC의 `Desktop\SmartFactory\SFL_TRC_7H_R3_evidence\server-run-U76fbb38e`에
72개 파일(36개 JSON/SHA256 쌍), 104,067바이트를 보존하고 공유 사본·각 영수증 해시를 모두 검산했다.
`initial-review-summary.json`에 아래 시작 점검을 기록했다.

- 01:23:23~01:25:01, 약 98초의 7표본에서 같은 프로세스 시작 시각·logger·SPOT instance 유지.
- rows 47→483, poll 13→111, 같은 CSV 크기 57,924→676,372바이트 증가.
- 두 PLC의 snapshot 갱신, 모든 표본 poll success/fresh, 설정 검사 통과.
- 관찰 표본의 writer queue/pending/rejected/write/spool 및 fact write/link/origin 오류 0, 기존 drift 1 유지.
- 화면 `SPOT STALE`과 함께 6표본에서 `temperature-invalid-sentinel`, 마지막 누적 `under_range` 424행을 관찰했다.
  이때도 새 poll·PLC snapshot·CSV 저장은 증가했다. 물리적 원인과 CSV 각 행의 의미는 아직 검증하지 않았다.
- 초기 Count는 42로 Count 0~2 사건은 없었다. 초기 진행 확인은 7시간 완료·전체 현장 합격을 뜻하지 않는다.

검증 중 앱·도우미를 추가 실행하거나 설정/장비/네트워크를 변경하지 않았다. 현재 서버의 같은 실행을
계속 관찰해야 하며, 종료 후 전체 receipt와 닫힌 후보 CSV/fact의 별도 검증이 남아 있다.

추가 시작 사본은 위 공유 회수 폴더의 `count-zero-snapshot\receipt`에서 받았으며,
개발 evidence의 `count-zero-receipt`와 `count-zero-review-summary.json`에 보존했다.
208개 파일(104 JSON/SHA256 쌍), 326,187바이트가 모두 일치했다. 01:29:53까지 24표본에서
rows 1,611 / poll 402로 진행했고 같은 프로세스·서비스 세대, CSV 실제 저장, 두 PLC snapshot 갱신,
설정 검사와 오류 카운터 기준을 유지했다. 01:25:52 표본부터 Count 0이 나타나 총 15표본을 확보했다.
Count 1/2 표본은 없었으며 Count 0 표본 확보는 CSV phase 검증 통과를 의미하지 않는다.
마지막 누적 under_range는 1,550행이었다. 작업 정보 재입력 표시가 화면에 나타났지만
발생 원인·행위자는 확인하지 않았으며 Codex가 제품·금형 정보를 수정하지 않았다.

## 전환과 관찰 순서

1. 실행 중 원본의 신원·설정·로깅 계약, 두 소프트웨어 트리, 복귀 조건을 확인한다.
2. 원본에 정상 종료를 요청하고 프로세스·포트가 해제됐는지 확인한다.
3. 작은 설정·상태 5파일만 새 바탕화면 `SmartFactory\U<실행 ID>`에 보존한다.
4. 후보를 별도 데이터·프로필·환경에서 시작하고 준비 후 최대 25,200초 관찰한다.
5. 후보에 정상 종료를 요청하고 trace·exit code·프로세스·포트 해제를 확인한다.
6. 기존 원본 설치본과 원래 데이터로 복귀하고 15초 간격 3표본의 poll·CSV 파일 증가를 검사한다.

관찰 7시간 외에 준비·종료·복귀 시간이 추가된다. 후보 준비는 180초, 원본 준비는 900초,
각 정상 종료는 450초 한도다. 진행 중 제한된 I/O와 관찰 1회 소요 시간만큼 경계가 늦어질 수 있다.
7시간 시계는 monotonic stopwatch다. PC 절전·종료·도우미 콘솔 강제 종료는 자동 복귀를 보장하지 않는다.
도우미가 시작한 앱은 R7과 동일하게 `ELECTRON_NO_ATTACH_CONSOLE=1`로 실행하지만,
시험 자체를 지속하려면 도우미 콘솔은 유지해야 한다.

## 수집 자료와 중단 기준

15초 간격으로 health 원본 선택 필드, 런타임 세대, writer 상태, live provenance, CSV 파일 크기,
디스크 여유 및 로컬 `/api/data`의 선택 필드를 새 JSON과 SHA256 파일로 기록한다.
데이터 GET은 백엔드 메모리 snapshot을 읽으며 별도 장비 요청·설정 변경을 하지 않는다.
초기 health는 후속 API 오류나 판정 전에 먼저 기록한다. 최대 1,800표본·CSV 32파일 경계가 있다.

| 항목 | 관찰·중단 기준 |
| --- | --- |
| 실행 신원·스레드 | 동일 PID/시작 시각/logger/SPOT instance 유지. 변경·스레드 종료는 즉시 중단 |
| 설정·provenance | 원본 계약의 경로 외 값, mismatch/effective=false/comparator=false, drift=1 유지 |
| 저장 | fact write/link/origin, writer reject/write/spool 오류 및 spool pending은 0 유지 |
| CSV 진행 | 실제 파일 크기 증가가 60초 이상 없으면 중단. rows_total 증가만으로 통과하지 않음 |
| poll 진행 | poll sequence가 120초 이상 증가하지 않으면 중단 |
| 자연 통신 장애 | 불량 상태 연속 300초 도달 시 중단. 통신 오류·회복 구간을 기록 |
| PLC worker 정체 | 압출기와 LS 각각 snapshot_at 미갱신/null 300초 도달 시 중단. 연결=true만으로 정상 판정하지 않음 |
| 저장 공간 | 시작 시 20GiB 이상. 관찰 중 10GiB 미만 또는 시작 대비 여유 감소 10GiB 도달 시 중단 |
| metadata 전환 | null CSV 이름 또는 유효 이름의 제한된 준비 경합만 최대 60초 유예. 잘못된 경로·신원·계약은 즉시 중단 |

이 수치는 이번 관찰의 보수적인 중단 한도이며 제품 성능 SLO나 전체 현장 합격 한도가 아니다.
디스크 여유 감소는 해당 드라이브 전체 변화로서 후보만의 사용량이 아니다.
실제 파일 크기 증가는 저장 진행 신호이며 완전한 행·의미·최종 무결성은 종료 후 별도 검증한다.
queue/pending/처리 지연은 표본 값이며 연속 high-watermark나 모든 enqueue 지연을 제공하지 않는다.

통신 오류 원문은 저장하지 않고 존재 여부와 허용된 수치만 기록한다. 자연 통신 불량은 잠시
관찰하지만 저장 실패·설정 변경·런타임 신원 이상을 유예하지 않는다. 관찰 오류 후에도 정확한
후보 정상 종료가 확인된 경우 원본으로 복귀하고 복귀 후 3표본을 검사한다. 원본 복귀가
확인되지 않은 상태에서 후속 함수가 앱을 새로 실행하거나 강제 종료하지 않는다.

## 중간 정상 복귀 요청

사용자는 결과 콘솔의 `RESULT ROOT` 폴더에 있는 `STOP_OBSERVATION.ready`를
`STOP_OBSERVATION.txt`로 이름만 바꿀 수 있다. 다음 관찰에서 `operator-stop` 영수증을 남기고
후보 정상 종료·원본 복귀 순서로 진행한다. 파일 내용은 실행하거나 파싱하지 않는다.
디렉터리·reparse·1KiB 초과 marker는 거부한다. 후보 창이나 콘솔을 직접 닫는 방식으로 중단하지 않는다.
조기 종료는 완료된 관찰 범위만 의미하며 7시간·Count·장애 복구를 통과 처리하지 않는다.

## Count·복구·파일 전환의 판정 범위

Count 0/1/2 표본 수는 사건 징후다. 실제 phase는 CSV writer에서 계산하므로 API Count와
API phase를 같은 판정 자료로 사용하지 않는다. API에 공개되지 않는 PLC usable/threshold 값을
실측했다고 기록하지 않는다. 종료 후 각 CSV의 같은 행에서 Count, phase, 온도·origin·age 규칙을
전수 대조한다. 사건이 없으면 미검증이며 시간을 채웠다는 이유로 통과시키지 않는다.

장비 케이블 분리·방화벽 변경·전원 차단·PLC/SPOT 값 조작·clock 변경은 수행하지 않는다.
자연 장애가 있으면 오류 표본과 snapshot 갱신 재개를 연결하고 CSV/fact 의미를 검증한다.
TTL/invalid clock/물리 장애 원인은 이번 관찰에서 별도로 발생·입증되지 않으면 미검증이다.
자정 전환은 이번 사용자가 별도 시험으로 지정했다. 실행 시각 때문에 자연 전환이 발생해도
중간 deferred manifest를 실패로 오인하지 않고 종료 후 모든 생성 CSV의 closeout을 검증한다.

## 복귀와 남은 위험

위험도는 높음이다. 시작·종료 동안 수집 공백이 있으며, 종료나 파일/프로세스 신원이 불명확하면
HOLD하여 자동 복귀가 완료되지 않을 수 있다. 새 데이터·spool과 증거를 보존하고 확인해야 한다.
기존 이력 전체 백업·복원·NSIS 설치·migration은 없다. 복귀는 기존 d7 설치본과 원래 상태다.
후보에서 바뀐 제품·금형 등 운영 선택은 원본에 자동 덮어쓰지 않는다. **복귀 후 현재 제품·금형을
운영자가 확인해야 한다.** 원본 설정이 외부에서 바뀌면 원본 불변 검사에서 HOLD할 수 있다.

복귀 후 fresh SPOT와 같은 logger, poll·CSV 증가를 검사하며 원본 d7에 없는 writer 지표는 null로
남긴다. 이 자동 확인은 결과 콘솔 종료 후 생존 시험을 수행했다는 뜻이 아니다.
`field_validation_passed=false`, `production_release_approved=false`는 결과 검토 전까지 유지한다.

## 개발 검증

- 고정 R7의 실행·환경·cold state·신원·정상 종료·복귀·계약 함수 13개가 바이트 단위 동일함을 빌더에서 확인.
- 최종 R3 native PowerShell 5.1 공통 경계 95 PASS. 기존 3분 observer 사례는 이번 7시간 전용 사례로 대체.
- 7시간 전용 76 PASS: 시간 종료/조기 종료, 오류 전 증거, CSV 실제 저장 정체, poll/PLC 300초 경계,
  자연 복구, 디스크 부족, 설정/신원/카운터 오류, 복귀 후 실제 progress 함수 및 실패 경로 포함.
- 실제 CMD/자식 환경/후보 config 모듈 8 PASS. helper 변조·누락과 경로/설정/attestation 경계 포함.
- 독립 읽기 검토에서 발견한 오류 후 복귀 표본 누락과 PLC snapshot 정체 누락을 수정하고 재검토 완료.
- R7의 실제 소유 ConPTY 3 PASS는 변경되지 않은 환경·시작 함수의 기존 근거로 참조한다.
  이번에 서버 후보를 개발 시험용으로 실행하거나 동일 시험을 반복했다고 기록하지 않는다.
- 제품 코드·바이너리는 동일하므로 전체 제품 회귀 시험은 재실행하지 않았다. 실제 7시간 서버 결과는 별도다.

수정 파일은 새 `temperature-extended-observation.ps1`, `build-temperature-extended-trial.py`,
`test-temperature-extended-trial.ps1` 및 공통 시험기의 선택적 `SkipShortObserverCases` 매개변수다.
이 문서와 검증 기록을 포함해 새 결과를 보존하며 기존 해시 결합 자료는 변경하지 않는다.
