# Temperature 짧은 격리 시험 실행기

2026-09-20 사용자의 진행 지시에 따라 기존 `d7a1b20` 정상 종료, 후보 `72a4103`의
초기 180초 관찰, 후보 정상 종료, 원래 설치본 복귀를 묶은 실행기를 준비했다.
실제 시험은 사용자가 서버에서 실행한다. 아래 R7 결과는 짧은 관찰 시험과 정상 복귀의
검증 기록이며, 전체 현장 검증 통과나 운영 승격을 뜻하지 않는다.

## 2026-09-21 현재 실행 대상: R7

사용자의 후속 진행 승인으로 R4의 판정·콘솔 결함을 수정했다. 현재 전달 대상은
`C:\Users\user\Desktop\SmartFactory\SFL_TRC_RUN_R7\RUN_TRIAL.cmd` 일반 실행이다.
R4는 실패 증거로 보존하며 다시 실행하지 않는다. R5/R6는 개발 중간 묶음으로 서버에 전달하지 않았다.

- helper SHA256: `37C9A0DFD577DD8C5EBC1A21DF7A38CE762DC992CEDFE524FC60D3F60E2E84A7`
- CMD SHA256: `253FDB1208901C987BEBD56A97737FA26D2F5A6F9342439ED22EF414277FC48E`
- 7파일, 894,439바이트. 준비 결과·제품 manifest·후보 72a4103 및 원본 d7a1b20 바이트는 그대로다.
- 개발 근거: `Desktop\SmartFactory\SFL_TRC_RUN_R7_evidence`
- 공유 전송: `Z:\SmartFactory\20260921\send\SFL_TRC_RUN_R7`
- 서버 최종 사본 검산: `Z:\SmartFactory\20260921\return\SFL_TRC_RUN_DELIVERY_R7\SFL_TRC_RUN_R7`

00:12~00:14(KST) 서버 로컬 새 폴더 복사와 왕복 검산을 완료했다. 서버 탐색기에서 새 로컬
사본을 빈 공유 회수 폴더로 복사하고 7개 파일 크기·SHA256을 개발 원본과 대조했다.
이 전달 시점에는 R7를 아직 실행하지 않았으며, 이후 사용자가 실행한 결과는 아래와 같다.

### R7 서버 결과: 짧은 시험 통과·원본 복귀

2026-09-21 00:19~00:28(KST) 실행은 `Udc7d3bfb`에 기록됐다. 콘솔의 `[TRIAL EXIT] 0`,
원본 복귀 표시와 실행 중인 제품 화면을 확인했다. `receipt` 108파일(144,396바이트)을
`Z:\SmartFactory\20260921\return\SFL_TRC_RUN_RESULT_R7\receipt`로 회수하고, JSON 54개
해시 및 모든 복사 파일의 크기·SHA256을 검산했다. 콘솔 result SHA256도 회수본과 일치한다.

- result SHA256: `5D92BEB2D109853323331306D6580D60759C07001772C5C1F0C5523815A195F9`
- 개발 보존: `Desktop\SmartFactory\SFL_TRC_RUN_R7_evidence\server-run-Udc7d3bfb`
- 원본 영수증은 그대로 보존하며 `review-summary.json`에 파생 판정과 한계를 기록했다.

| 항목 | 확인 결과 |
| --- | --- |
| 후보 | commit 72a4103, schema 2.5.1, main PID 9652 / backend PID 27420 |
| 관찰 | 00:20:51~00:24:04, 13표본, 표본 사이 193.064초 / helper 관찰 194.091초 |
| CSV 증가 | 49 → 959행, 모든 표본에서 증가 |
| SPOT poll 증가 | 13 → 206, 모든 표본 success/fresh, 서비스 세대 유지 |
| 저장·연결 오류 | fact write/link/origin mismatch, writer reject/write/spool failure 모두 0 |
| writer | 초기화 약 31ms, 표본 queue/pending 0, accepted=completed, drained=true |
| provenance | fingerprint_mismatch, requested=true, effective=false, comparator=false 유지, drift 1 유지 |
| 후보 종료 | main/backend exit 0, forced=false, trace 정상 경계 및 프로세스/포트 해제 확인 |
| 원본 복귀 | commit d7a1b20, schema 2.5.0, main PID 268 / backend PID 23604 |
| 원본 준비 | 약 235초 후 ready, 당시 poll 4 / CSV 1,106행 |
| 원본 보존 | 설정 SHA256·값 해시·로깅 계약 유지, 후보 상태를 원본에 복사하지 않음 |

writer의 표본별 마지막 queue residence 최대는 약 47ms, 마지막 write duration 최대는 약 140ms다.
이는 13회 표본에서 확인한 값이며 전체 실행의 최고 지연이나 queue 최고점이 아니다.
원본 준비 지연이 기존 180초 예산을 넘었다는 것은 확인했지만 원인까지 확정하지 않는다.

#### 종료 CSV와 fact 검증

종료된 후보 `Udc7d3bfb\work\data`에서 CSV, metadata, observation fact, image fact,
image final manifest 5개(1,646,313바이트)만 추가 회수했다. 이미지 원문·설정·진단 요청 이벤트·
원본의 대형 이력은 복사하지 않았다. 공유본과 개발 보존본의 크기·해시를 모두 대조했다.
고정 후보 72a4103의 `validate_csv_v2_shadow.py`를 실행해 **exit 0 / PASS**를 얻었다.

- 최종 CSV 964행, sample_seq 1~964, 중복·누락 없음. shutdown finalized=true 및 마지막 순번 일치.
- startup_pending 8행은 origin=none이며 valid 956행은 모두 current_observation이다.
- observation fact 207행, 같은 서비스의 poll 1~207. 키 중복·poll 누락 0, 기록된 poll 모두 success.
- 유효 온도 956행 모두 fact 키에 연결되며 누락 0, 연결률 100%, 진단 source mismatch 0.
- observation fact 행 수·SHA256은 metadata manifest와 일치한다.
- image fact 177행은 별도 final manifest의 행 수·SHA256과 일치한다. failure/dropped 0.
  이미지 파일 자체와 image linkage 파생 결과는 검증하지 않았다.
- process resolution/phase event fact는 생성되지 않았고 metadata도 0행/null hash다.
  해당 파일의 unknown 검증 결과를 통과한 값으로 바꾸지 않는다.
- 첫 valid는 sample 9, logger 시작 기록 후 3.144초다. 첫 poll 완료는 서비스 시작 기록 후
  1.821초다. fact에 기록된 poll duration 최대 249.375ms, wall-clock poll 시작 간격 최대 1,144.750ms다.
  독립 monotonic 계측이나 전체 cold-start 소요 시간으로 해석하지 않는다.

최종 CSV SHA256은 `A0C4FB3019A85297DF8AA80D88B90491D46BE05387C363C5A588F65D8515A871`이다.
CSV에는 별도의 생산자 최종 해시가 없으므로 로컬 계산값으로 기록한다. observation/image fact는
생산자 manifest 해시와 일치하지만 서버 로컬 파일 해시를 별도 명령으로 재계산한 것은 아니다.
초기 provenance-baseline의 sidecar 해시는 초기 기록이며 shutdown 후 metadata 해시와 달라도 된다.
최종 metadata의 provenance 필드는 초기 baseline과 동일함을 별도로 대조했다.
`review_run.py`의 203개 증거 비교가 모두 일치했다. 이는 제품 회귀 시험 203개라는 뜻이 아니다.

이번 CSV의 Count는 초기 공란 외에 18~20이다. Count 0~2, 장애·복구, TTL 초과 cache와
invalid clock, 장시간·rollover 현장 사례는 미검증이다. `field_validation_passed=false`,
`production_release_approved=false`를 유지한다. 설치·migration·제품 코드 변경은 없다.

#### 후속 확인: 콘솔 종료 안내 후 원본 수집 지속

R7 결과 검토 당시 원본 ready 한 시점과 실행 화면은 확인했지만 복귀 이후 여러 표본의 CSV 증가와
실제 서버의 결과 콘솔 종료 후 앱 생존은 아직 확인하지 않았다. 기존 `SFL_TRC_DIAG_R3\READ_STATUS.cmd`를
원본 상태 읽기 용도로 재사용할 수 있음을 대조했다. R3의 원본 commit·설정 값 해시·로깅 계약은
R7 preflight와 동일하며 helper SHA256도 기존 전달값과 같다. 별도 앱 시작·종료·설정 변경은 없다.

사용자가 R7 결과 콘솔 창만 닫은 후 원본 제품이 유지되는 상태에서 R3를 일반 실행한다.
회수 시 원본 main PID 268 / backend PID 23604와 시작 시각이 R7 복귀 세대와 같은지,
세 표본의 poll·CSV 행·파일 바이트 증가와 설정 계약을 확인한다. 앱까지 종료되면 반복 실행하지
않고 원본 복귀 상태부터 조사한다. R3의 `candidate_metadata`는 과거 R4 루트 `Ue2c2b56e`를
가리키므로 **이번 R7 후보 판정에 사용하지 않는다**. R7 후보 판정은 위 새 영수증과 CSV/fact만 사용한다.
진단 재사용 근거는 `post-restore-diagnostic-compatibility.json`에 별도로 기록했다.

#### R7 복귀 후 진단 결과: 동일 실행 세대 수집 유지

사용자가 위 안내 후 실행 완료를 알렸다. 서버의 새 결과 `SFL_TRC_DIAG_R3\results-874963fb`와
`[DIAGNOSTIC EXIT] 0`, 원본 제품 Running/SPOT OK/Comm OK 화면을 확인했다.
JSON 4개와 해시 파일 4개를 `Z:\SmartFactory\20260921\return\SFL_TRC_R7_POST_RESTORE_DIAG`로
회수하고 개발 근거의 `server-run-Udc7d3bfb\post-restore-diagnostic`에 보존했다.
파일별 크기·해시, JSON 4개 해시, 콘솔 result 해시, 개별 sample과 result 내 표본을 대조했다.
result SHA256은 `78E94A5EC9ACFF5A32CCD0C01D506F0E75DBBAF1D51237C05DCDAAA484525938`다.

| 항목 | 표본 1 | 표본 2 | 표본 3 |
| --- | ---: | ---: | ---: |
| 시각(KST) | 00:45:37 | 00:45:53 | 00:46:10 |
| SPOT poll | 1,047 | 1,064 | 1,080 |
| CSV rows_total | 6,254 | 6,336 | 6,416 |
| CSV 파일 바이트 | 8,466,502 | 8,570,238 | 8,678,483 |
| fact write/link/origin 오류 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| config drift count | 1 | 1 | 1 |

32.918초 동안 poll 33회, CSV 162행·211,981바이트 증가했다. 세 표본 모두 원본 d7a1b20,
v1.0.26/schema 2.5.0/REAL이며 main PID 268 / backend PID 23604 및 전체 제품 프로세스의
시작 시각이 R7 `original-restored.json`과 정확히 같다. 중간에 재시작된 다른 세대가 아니다.
CSV도 복귀 당시 `Factory_Integrated_Log_v2_20260921_002420.csv`와 같고 수정 시각이 증가했다.
logger instance 및 sidecar commit/schema도 health와 일치한다.

driver 연결·thread·SPOT success/fresh, 설정 파일 SHA256, 설정 값 해시, 저장/이미지 안전 설정,
로깅 계약 검사는 세 번 모두 통과했다. 기존 fingerprint_mismatch/effective=false/comparator=false를
유지한다. 원본 d7에서 제공하지 않는 persistence/queue 필드는 null로 보존했다.
원본 fact는 크기 4,675,282,754바이트와 시각만 읽었으며 내용 복사·전체 해시는 하지 않았다.
진단의 과거 R4 candidate_metadata는 이번 후보 판정에서 제외했다.

판정은 **R7 복귀 원본의 동일 실행 세대 유지 및 세 표본의 수집·CSV 기록 진행 확인**이다.
사용자에게 R7 콘솔 종료 후 진단을 안내했고 그 후 완료 응답을 받았으나, 콘솔 종료 이벤트
자체의 시각·OS 기록을 별도로 수집하지는 않았다. 이 구분을 `review-summary.json`에 보존했다.
파생 검토 69개 비교가 모두 일치했으며, 전체 현장 검증/운영 승격 false는 유지한다.
현재 읽기 전용 진단은 제품을 실행하거나 종료하지 않았으므로 완료된 진단 결과 창은 닫아도 된다.
SmartFactory 원본은 계속 유지한다. 다음 단계는 후보의 Count 0~2·장시간·장애 복구·rollover
현장 검증 범위를 준비하는 것이다. 이번 진단에서는 제품 코드·설정·설치·migration 변경이 없다.

### 변경한 판정과 실행 방식

- 기존 fingerprint_mismatch, requested=true, effective verified=false, comparator=false,
  readback=not_supported, drift fields=[spot_config_fingerprint_sha256]를 요구한다.
  새 후보의 처음 확인된 sidecar와 live provenance를 대조해 baseline을 고정한다.
  경로가 반영된 current fingerprint는 실행별로 달라질 수 있으며 R4 값을 재사용하지 않는다.
  verified fingerprint는 원본 baseline과 같아야 한다. 세션 내 카운터 1을 유지하고 추가 변경을 차단한다.
- 수집된 health의 카운터·writer 상태와 provenance를 판정 전에 별도 영수증으로 보존한다.
  누락 카운터는 null로 남긴 뒤 거부한다. runtime/logger/SPOT instance 연속성을 검사한다.
  초기 런타임 신원·상위 JSON 구조 검사가 실패하면 sample 생성 전에 중단될 수 있다.
- 두 자식 환경에 `ELECTRON_NO_ATTACH_CONSOLE=1`을 명시하고 `ELECTRON_RUN_AS_NODE`는 계속 제외한다.
  시작 함수에서 이 조건을 다시 검사한다. `CreateNoWindow=true`만으로 해결됐다고 해석하지 않는다.
- 후보 준비는 180초, 원본 복귀 준비는 900초까지 기다린다. 15초 간격의 준비 상태와 timeout
  영수증을 추가했다. 반복 진입 기준의 시간 예산이므로 진행 중인 제한된 I/O 시간만큼 초과할 수 있다.
  timeout 이후 무조건 재실행하거나 강제 종료하지 않는다.

수정 소스는 `temperature-trial-run.body.ps1`, `build-temperature-trial-run.py`,
`test-temperature-trial-run.ps1`과 새 `test-temperature-trial-console.py`다.
모두 `scripts/server-stage-v1026` 아래 있으며 제품 소스·바이너리·운영 설정은 변경하지 않았다.

### 개발 검증과 한계

- 일반 사용자 native PowerShell 5.1 경계 **158 PASS**. 최초 검토 152개에 verified hash 동시 변경 및
  두 번째 표본 logger 교체 검사를 보강했다. 첫 표본과 이후 표본의 drift/fingerprint/fields 변경,
  쓰기·연결·spool 실패, 누락·잘못된 카운터의 증거 보존, 늦은 원본 준비와 timeout을 포함한다.
- 실제 CMD 정상·변조·누락, 자식 환경 및 실제 후보 config 모듈 등 **8 PASS**.
- 비제품 Electron 44.3.0으로 실제 소유 ConPTY 종료 **3 PASS**. 기존 방식은 콘솔에 연결돼
  콘솔 종료와 함께 죽었고, 수정한 후보·원본 환경은 연결되지 않으며 같은 프로세스 핸들·시작 시각의
  heartbeat가 계속 증가했다. 정상 종료 marker도 확인했다. 제품 backend와 실장비는 실행하지 않았다.
- 실제 후보 production provenance 함수와 driver drift 전이 회귀 **9 PASS**.
  상세 출력은 R6 근거의 `production-provenance-tests`에 보존했다. 제품 코드는 R7에서도 같다.
- 두 읽기 전용 독립 검토에서 추가 차단 결함 없음. 최종 R7 전체 해시와 시험 기록을 대조했다.
- R5의 첫 provenance 비교 시험에서 속성 순서에 따른 오탐을 발견해 projection 순서를 정규화했다.
  R6의 첫 launcher/config 시험은 전역 Python 환경에서 실패했고 프로젝트 venv로 통과했다.
  실패 기록은 보존했고 R7은 venv에서 통과했다.

콘솔 검증 근거는 [Electron 환경 변수](https://www.electronjs.org/docs/latest/api/environment-variables#electron_no_attach_console-windows),
[Electron 44.3.0 시작 코드](https://github.com/electron/electron/blob/v44.3.0/shell/app/electron_main_win.cc#L147),
[Microsoft ConPTY 종료](https://learn.microsoft.com/en-us/windows/console/closepseudoconsole)다.
이 시험은 다른 상위 job의 강제 종료까지 보장하지 않으며 실제 서버 재시험을 대체하지 않는다.

운영 영향은 여전히 높음이다. 시험 중 시작·종료에 따른 수집 공백이 생기며, 복귀 경로는 검증된
기존 d7 설치본과 원래 데이터다. 설치·migration·대형 이력 백업은 없다. 후보 관측 실패 시
정확한 후보 세대의 정상 종료를 확인한 뒤 원본으로 복귀하지만 종료·신원이 불명확하면 HOLD한다.
준비 지연과 실패 수치의 관측 가능성을 보강했으며 전체 CSV/fact 의미, 장시간·장애 복구 검증은 남았다.
현장 검증 통과와 운영 승격은 계속 false다. 실행 중 및 결과 확인 전에는 콘솔 창을 닫지 않는다.

## R4 과거 실행 위치와 식별

- 서버 최종 폴더: `C:\Users\user\Desktop\SmartFactory\SFL_TRC_RUN_R4`
- 진입점: `RUN_TRIAL.cmd` 일반 더블클릭. 관리자 실행은 거부한다.
- helper SHA256: `679E2AE51EFC2D4FB28D4A589CBD6308EF8B454561043B37A42363EE4A279057`
- CMD SHA256: `6F6568B52A6D86849D41944F85AF49FE86CAAD9F5B18CAA3CA4E857E5D638656`
- 준비 결과 SHA256: `C04A78DFA0EFB01A5046BC75AB401A42B9045ABDB43963EB6E5E42DD75E9BE08`
- 공유 전송: `Z:\SmartFactory\20260920\send\SFL_TRC_RUN_R4`
- 전달 검산 회수: `Z:\SmartFactory\20260920\return\SFL_TRC_RUN_DELIVERY_R4`
- 개발 근거: `Desktop\SmartFactory\SFL_TRC_RUN_R4_evidence`

묶음은 7파일, 887,733바이트다. 개발 원본과 Z 사본은 모두 SHA256이 일치한다.
22:24(KST) 서버 로컬 최종 폴더에서 회수한 7개 파일의 크기·SHA256이 모두 일치했다.
서버 로컬 복사·왕복 검산 결과는 개발 근거의 `server-delivery-receipt.json`에 기록했다.
22:28 서버 탐색기에서 최종 로컬 폴더와 `RUN_TRIAL.cmd`를 확인했다. 기존 앱은 실행 중이며
도우미 실행이나 앱 시작·종료는 수행하지 않았다.
R1~R3는 개발 중간 산출물이며 서버 전달·실행 대상으로 사용하지 않는다.

## 실행 순서와 경계

1. native PS5.1 일반 사용자/서버 SID/세션, 중복 도우미 mutex, 준비 결과 해시,
   원본 설치본 1,646파일과 후보 1,812파일, 현재 config 해시·경로·런타임·로깅 계약을 확인한다.
   설정 drift나 중앙 동기화 활성 상태, 읽기 실패가 있으면 운영 앱 종료 전에 HOLD한다.
2. 운영 앱의 정확한 main/backend PID와 시작 시각 및 핸들을 확보하고 정상 종료를 한 번 요청한다.
   최대 450초 동안 기다린다. 두 종료 코드 0, 잔존 앱/백엔드 및 8000 LISTEN 없음,
   정확한 세션의 `forced=false` 종료 기록과 실패 기록 없음이 모두 필요하다.
   Electron 자체는 390초 뒤 강제 종료를 시도할 수 있어 단순 프로세스 부재를 정상으로 보지 않는다.
3. config.ini 및 선택 JSON 4개만 정지 상태에서 새 `Desktop\SmartFactory\U<8자리>\cold`에 복사한다.
   파일당 1MiB, 합계 5MiB다. 누적 CSV/이미지/fact/spool/index/프로필은 복사하지 않는다.
4. 후보를 같은 사용자로 실행한다. 새 work 아래 AppData/LocalAppData/USERPROFILE/temp/profile,
   config, log/snapshot/image 및 종료 진단을 사용한다. 실제 CSV/sidecar와 health의 commit/schema/instance도 대조한다.
   준비 완료 후 180초 동안 15초 간격으로 poll/품질/행 증가와 writer queue·거절·쓰기/spool 실패를 기록한다.
5. 후보도 동일한 정상 종료 판정을 거친다. 새 shutdown trace의 정확한 PID·session·sequence와
   verified-stop → shutdown-complete → quit-call → trace.closed 순서를 추가 확인한다.
6. 원본 작은 상태의 존재/크기/해시 불변과 기존 설치본을 다시 확인하고, 원래 설치 경로 및 데이터로 복귀한다.
   복귀 후 config 값 해시, 실제 logger 계약, 이미지 저장 mode, config 해시를 다시 대조한다.

새 U 폴더는 일반 사용자/SYSTEM/Administrators만 FullControl이며 부모 ACL은 바꾸지 않는다.
T15596b의 보호된 준비 자료는 그대로 둔다. 그 아래 계획됐던 `w`는 사용하지 않는다.
일반 사용자의 실제 쓰기 권한이 필요한 작업용 경로를 별도로 만든 결정이며, 원본 자료 이동이 아니다.

## 환경과 설정 보존

후보·복귀 환경을 각각 OS allowlist로 새로 만든다. 원래 프로세스 환경 전체를 읽거나
동일성까지 증명한 것은 아니다. `.env`를 비활성화하고 상속받은 proxy/Node/Python/장비/중앙 동기화
override를 넘기지 않는다. 복귀에는 원래 config·프로필·temp·8000 포트와 실행 직전 관측한 logger 값을 명시한다.
복귀 기본값을 추정하거나 후보 플래그를 그대로 재사용하지 않는다.

후보는 검토된 6개 logger opt-in을 true로 설정하고 V1 활성 여부는 실제 원본 sidecar 값을 보존한다.
`process_fact` 값은 직접 존재하지 않는 manifest.enabled 필드에서 읽지 않는다.
고정된 두 빌드의 config 시작 검사가 operational/observation/process 플래그를 모두 같게 강제하므로
관측한 operational/observation 일치로 추론하고 그 근거를 결과에 명시한다.
원래 attestation 요청과 fingerprint, comparator 및 async_fact_only 설정은 수정하지 않는다.

## 검증과 남은 한계

- 실제 일반 사용자 PowerShell 5.1 경계 시험 **82개 통과**.
- 실제 CMD 정상/변조/누락, ProcessStartInfo 자식 환경, 실제 후보 config 모듈,
  오염된 .env 차단, 경로·플래그·안전 설정 보존, manifest와 로컬 해시 기록의 동시 변조 거부 등 **8개 통과**.
- 읽기 전용 독립 검토에서 최종 R4 변경분과 묶음 해시 결합 승인.
- 제품 코드·후보 바이너리는 변경하지 않았다. 기존 전체 제품 QA는 반복하지 않았다.
- 시험 fixture만 실행했고 개발 PC에서 제품/실장비를 실행·접속하지 않았다.
- R2 첫 orchestration 시험은 fixture의 originalCommit 누락으로 실패했고 보존했다.
  최종 R4는 해당 누락과 발견된 helper scope/환경/계약 문제를 수정한 별도 빌드다.

관찰 지표의 queue 최대값은 15초 표본의 최대이며 지속 측정 high-watermark가 아니다.
최초 poll 관측 대기시간도 실제 첫 poll 소요시간이 아니다. CSV/fact 전수 의미 검증,
종료 manifest 전체 해시·서비스별 전수성, 재시작/rollover/장애 복구/장시간 생산은 후속 검증 범위다.
이 단계만으로 `field_validation_passed`나 `production_release_approved`를 true로 만들지 않는다.

## 실패와 복귀

### 일반 사용자 실행: 후보 관찰 및 복귀 준비 검사 HOLD

22:35~22:39(KST) R4 일반 사용자 실행 결과는 **HOLD**다. 판정 JSON 8개와 각각의
SHA256 파일 8개를 서버 `Desktop\SmartFactory\Ue2c2b56e\receipt`에서 회수했다.
공유 회수는 `Z:\SmartFactory\20260920\return\SFL_TRC_RUN_RESULT_R4\receipt`, 개발 보존은
`Desktop\SmartFactory\SFL_TRC_RUN_R4_evidence\server-run-20260920-2235`다.
8개 JSON 해시와 복사 바이트를 검증했고 hold/candidate-closed 해시는 콘솔 표시와도 일치한다.

- 원본 정상 종료, 작은 상태 복사, 후보 실행 완료. 후보 준비 대기는 약 11.5초였다.
- 첫 관찰의 `candidate-persistence-or-contract-failure`로 중단해 3분 관찰을 수행하지 못했다.
  검사 전에 sample을 쓰지 않아 당시 write failure/drift/origin mismatch 중 실제 값은 보존되지 않았다.
- 후보 main/backend 종료 코드 0, forced=false, 프로세스·포트 해제 및 정상 trace 경계 확인.
- 기존 설치본 파일 검증 후 원본을 실행했으나 WaitReady 180초 내 준비 조건을 충족하지 못했다.
  `original_restored=false`는 복귀 검증 미완료이며 원본 실행 부재를 뜻하지 않는다.
- 22:40 원격 UI Running/SPOT STALE, 이후 22:41~22:52 Running/SPOT OK/Comm OK를 관측했다.
  화면 회복만으로 CSV 기록·설정·복귀 검증을 통과 처리하지 않는다.

코드 검토에서 R4 판정 오류를 발견했다. 유지해야 하는 fingerprint_mismatch는 provenance의
config_drift_detected를 true로 만들고 최초 signature에서 drift 카운터를 1 증가시킨다.
따라서 CandidateSettings의 mismatch 필수 조건과 Observation의 drift==0 조건은 충돌한다.
이는 helper 기준의 결함이다. 저장 실패·origin mismatch의 동반 여부는 아직 미확정이다.
원본 d7의 기존 fact 전체 해시/인덱스 복원이 poll 및 첫 CSV sidecar 준비를 막을 수 있는
코드 경로를 확인했지만, 이번 180초 초과의 실제 원인으로 확정하지 않는다.

현재 R4 묶음은 수정하거나 재실행하지 않는다. 먼저 읽기 전용 진단 R3로 원본 상태와
중지된 후보의 작은 메타데이터를 확인한다. 후속 시험기는 관측값 저장 후 판정,
기대 drift 상태와 신규 drift 변화 구분, 복귀 준비 지연 근거 보존을 보완해야 한다.

### 읽기 전용 진단 R3

서버 전달 대상은 `Desktop\SmartFactory\SFL_TRC_DIAG_R3\READ_STATUS.cmd` 일반 실행이다.
helper SHA256은 `C7AB4CB1538D72F811DA8441C31AE90070948E61589D6198AB53D54567D49484`다.
현재 앱을 유지하며 프로세스 신원·로컬 GET API·설정 해시·CSV sidecar를 15초 간격 3회 읽는다.
d7에는 없는 persistence 필드는 null로 보존한다. 고정 후보 루트의 작은 metadata는 1MiB/파일,
최대 8파일로 제한하고 선택 필드만 출력한다. 원본 fact는 크기·시각만 읽는다.
설정 원문·인증정보·예외 원문·장비 URL을 출력하지 않으며 앱 시작/종료나 설정 변경을 하지 않는다.
새 결과 자식만 생성하며 부모 ACL과 원본 파일은 보존한다. 진단 자체는 통과 판정이 아니다.

PS5.1 경계 21개 및 실제 CMD의 정상/변조/누락 3개 시험을 통과했다. 독립 읽기 검토 완료.
R2 첫 boundary fixture의 backend process fact 누락을 보완했으며 R3 시험 21개는 모두 통과했다.
R1/R2 개발 중간 산출물은 서버 전달하지 않는다. 전송·최종 서버 왕복 검산은
`Desktop\SmartFactory\SFL_TRC_DIAG_R3_evidence`에 별도 기록한다.
22:54~22:55(KST) 서버 로컬 최종 사본의 5파일(32,982바이트)을 빈 공유 회수 폴더로
왕복 복사하고 개발 원본과 모든 파일의 크기·SHA256 일치를 확인했다.
`server-delivery-receipt.json`에 기록했다. 이후 서버 실행 결과는 다음 절에 기록한다.

### 진단 R3 서버 결과: 실행 구성 확인 실패

사용자가 22:56(KST) 진단 R3를 실행했다. 종료 코드 0은 진단 자료 기록 완료이며 앱 정상 판정이 아니다.
서버 결과 `SFL_TRC_DIAG_R3\results-676abd29`의 JSON 4개와 SHA256 파일 4개를
`Z:\SmartFactory\20260920\return\SFL_TRC_DIAG_RESULT_R3`로 회수했다.
4개 JSON 해시와 콘솔 result 해시 `D9CEF21B0AAFF6C1FC5E3CFC666E10BF215B5DE575D010F798526768AB159797`를
대조했다. 개발 보존은 `SFL_TRC_DIAG_R3_evidence\server-diagnostic-20260920-2256`다.

- 세 표본 모두 `runtime-membership`에서 중단했다. 앱·백엔드·8000 listener 단일 소유 조건 중
  무엇이 어긋났는지는 이 코드 하나로 구분할 수 없다. health·설정·CSV 증가는 이번 진단에서 미검증이다.
- 후보 metadata는 commit 72a4103/schema 2.5.1, fingerprint_mismatch, effective verified=false,
  comparator=false, config_drift_detected=true다. R4 drift==0 판정의 모순과 일치한다.
- 후보 metadata 기록상 shutdown finalized=true, fact 13행, write_failure/spool_pending/poll_gap/
  duplicate/invalid_poll_identity는 모두 0이다. 해당 fact 원문 전체 해시는 이번 진단에서 다시 계산하지 않았다.
  origin mismatch 동반 여부도 이 선택 필드만으로 확정할 수 없다.
- 원본 fact 크기는 4,669,382,724바이트, 마지막 수정 시각은 22:56:07.4036969(KST)이다.
  파일 내용은 읽지 않았다. 이 크기만으로 앞선 준비 지연의 원인을 확정하지 않는다.
- 22:57~23:00 원격 화면에 앱이 없고 작업 관리자 smart 필터에도 제품 프로세스가 보이지 않았다.
  이후 사용자가 "powershell을 종료하면서 같이 종료되었다."고 확인했다.

### 콘솔 창 종료 이후 원본 재실행

사용자 확인에 따라 원본 복귀 도우미가 실행한 앱이 결과 콘솔 창 종료와 함께 종료된 사건으로
기록한다. 읽기 전용 진단 R3에는 앱 실행·종료 기능이 없다. R4의 자식 환경에는
`ELECTRON_NO_ATTACH_CONSOLE`이 없어 Electron의 부모 콘솔 연결 가능성이 있다.
당시 콘솔/작업 객체 상태를 수집하지 않았으므로 정확한 Windows 종료 경로까지 확정하지 않는다.
후속 시험기는 앱 수명을 결과 콘솔 창과 분리하고 실제 창 종료 후 생존·수집을 검증해야 한다.

23:07~23:08(KST) 서버 탐색기에서 기존 설치 경로의 `smart-factory.exe`를 직접 실행했다.
후보나 R4를 재실행하지 않았고 설정·설치 파일·운영 데이터 경로를 바꾸지 않았다.
재실행 직후 Running/SPOT STALE/Comm 1! 및 갱신되는 PLC 값과 카메라를 관측했다.
23:14에는 Running/SPOT OK/Comm OK와 온도 갱신을 관측했으나 23:15에 STALE/Comm 1!이
다시 표시됐다. 따라서 지속적인 정상 수집이나 CSV 기록 복구를 화면만으로 선언하지 않는다.

탐색기 직접 실행에는 R4가 명시하던 logger 환경 변수를 주입하지 않았다. 기본 사용자 환경과
설정으로 시작한 실제 logger 계약이 시험 직전과 같은지는 R3의 다음 표본으로 확인해야 한다.
기존 진단 결과는 보존하며 재실행마다 새 결과 자식 폴더를 생성한다.
이 시점의 우선순위는 원본 런타임·설정·CSV 증가의 읽기 전용 검증이었다. 다음 실행에서 확인한
범위는 아래와 같다. 후보 재시험·운영 승격은 보류한다.

### 원본 재실행 후 R3 재진단: 수집·기록 진행 확인

사용자가 앱을 켠 채 R3를 다시 실행했다. `results-79555c45`의 23:44:09~23:44:42(KST)
세 표본에서 원본 런타임·설정·로깅 계약과 실제 CSV 기록 증가를 확인했다.
앱 main PID 23072, backend PID 25984 및 시작 시각은 세 표본에서 같았으며 런타임 경로·사용자·
세션·비승격 상태와 8000 listener 소유 검사도 통과했다. 실제 commit은 원본 d7a1b20,
버전 1.0.26, schema 2.5.0이다.

| 항목 | 표본 1 | 표본 2 | 표본 3 |
| --- | ---: | ---: | ---: |
| SPOT poll | 1,961 | 1,977 | 1,994 |
| CSV rows_total | 10,663 | 10,746 | 10,827 |
| CSV 파일 바이트 | 14,792,614 | 14,907,737 | 15,015,437 |
| observation fact write failure | 0 | 0 | 0 |
| origin decision mismatch | 0 | 0 | 0 |
| observation fact link failure | 0 | 0 | 0 |
| config drift count | 1 | 1 | 1 |

세 표본 모두 poll success/fresh, driver 연결 및 thread 정상이며 CSV 수정 시각도 증가했다.
약 33초 동안 164행·222,823바이트 증가했다. CSV는 `Factory_Integrated_Log_v2_20260920_230803.csv`로
같고 sidecar의 commit/schema/logger instance가 health와 일치한다. 설정 파일 SHA256,
시험 전 config 값 해시, 저장/이미지 경로와 안전 설정, 로깅 계약 검사는 각각 3회 모두 통과했다.
원래 fingerprint_mismatch/effective verified=false/comparator=false 상태를 유지하며 drift count는
1로 일정하다. `process_fact=true`는 고정된 시작 검사 계약에서 추론한 값임을 그대로 보존한다.

새 결과 JSON 4개와 SHA256 파일 4개는
`Z:\SmartFactory\20260920\return\SFL_TRC_DIAG_RESULT_R3_RESUME\results-79555c45`로 회수했다.
개발 보존 위치는 `Desktop\SmartFactory\SFL_TRC_DIAG_R3_evidence\server-diagnostic-after-explorer-resume`다.
8개 복사 파일과 4개 JSON 해시, 개별 sample과 result 안의 동일 표본을 대조했다.
콘솔 result SHA256은 `59E7D27F458630C21520207202BD10E9F14F1A2469E7E56B76C176C0AB8EE23B`로
회수 파일과 일치한다. 상세 판정과 한계는 로컬 `review-summary.json`에 기록했다.

판정 범위는 **원본 앱 재실행 후 세 표본의 설정 일치 및 수집·기록 재개 확인**이다.
연속 장시간 정상, 이전 STALE의 원인, 전체 CSV/fact 의미 검증, fact 전체 해시는 여전히 미검증이다.
원본 d7에 없는 queue/persistence 지표의 null을 0으로 해석하지 않는다.
원본 fact는 크기 4,671,504,795바이트와 수정 시각만 확인했다.
R4 원본 영수증과 실패 판정은 수정하지 않는다. 후보 현장 검증 및 운영 승격은 계속 미승인이다.
다음 준비 작업은 R4의 기대 drift 판정, 실패 전 관측값 저장, 콘솔과 앱 수명 분리,
원본 시작 지연의 진단 보강을 별도 도우미와 테스트로 검증하는 것이다.

### 최초 서버 실행: 권한 조건에서 중단

22:29~22:30(KST) 사용자 실행 후 원격 화면에서 콘솔 제목 `관리자:`와
`[HOLD] host / native-standard-user-ps51-required`, `[TRIAL EXIT] 1`을 확인했다.
고정된 R4 제어 흐름상 첫 호스트 검사에서 중단했으며 새 작업 루트 생성·기존 앱 종료·후보 실행
전이다. 기존 앱은 화면에서 Running 및 변하는 센서 값을 유지했다. 이는 읽기 전용 화면 관측이며
별도 서버 API 검증이나 현장 시험 통과가 아니다. 개발 근거에 `server-host-hold-observation-*.json`을
별도 보존했다. R4 파일과 해시는 변경하지 않았다. 다음 실행은 서버 탐색기에서 일반 더블클릭이며,
그 경우에도 관리자 창이 뜨면 반복 실행하지 않고 실행 컨텍스트를 조사한다.

운영 영향 위험도는 높음이다. 정상적인 흐름에서도 두 번의 시작·종료 동안 수집 공백이 생긴다.
관찰 중 지표 오류는 기록하고 정확한 후보 세대를 정상 종료한 뒤 복귀한다.
시작 중 신원 불일치, 종료 실패, 원본 상태 변경, 프로세스/포트 잔존은 HOLD한다.
종료가 불명확하면 무조건 재시작하지 않으므로 수집 중단이 지속될 수 있다.
도우미 창을 강제 종료해도 자동 복구되지 않는다. 이때 결과와 화면을 확인한 후 복귀를 결정한다.

설치/migration/원본 덮어쓰기는 없다. 복귀는 기존 d7 설치본과 원래 상태를 사용하는 방식이며
후보 상태를 원본에 덮어쓰지 않는다. 새 `cold/work`에는 비밀 설정이 들어갈 수 있어 서버에 보존한다.
Codex가 회수할 기본 대상은 비밀값을 제외한 `receipt` 폴더다.
