# 추가 스트림을 보존하는 운영 데이터 사본 검증

작성일: 2026-10-12. 후속 확인: 2026-10-13. 상태: 선택 사본 검산 완료, 기존 운영본 재시작·수집 확인, 이후 영상 연결 timeout 관측.
선택 AppData 두 루트의 사본 검증이며 전체 서버/NAS·복구·현장 QA 완료는 아니다.
`full_data_gate=NOT_EVALUATED`, `formal_release_gate=HOLD`, goal `active`를 유지한다.

## 확인된 원인과 변경

[첫 사전 검사와 읽기 전용 진단](production-release-risk-validation-cold-copy-20261012.report.md)은
원본의 `:Zone.Identifier:$DATA` 26바이트에 대한 기존 복사 엔진의 지원 부재를 확인했다.
원본 스트림 삭제/Unblock 없이 별도 `SflColdCopyStreamsV2` 엔진을 만들었다.
기존 엔진과 해시 결합 묶음은 보존한다.

- 파일 및 디렉터리의 이름 있는 `$DATA` 스트림을 실제 추가 스트림으로 복사한다.
  기본 데이터와 추가 스트림의 이름·크기·해시·집합을 원본/사본에서 각각 검산한다.
- `SFL-COLD-BACKUP-STREAMS-2` manifest는 부모 파일/폴더와 스트림을 결합한다.
  빈 스트림·Unicode 이름·버퍼보다 큰 스트림·긴 스트림 경로도 보존한다.
- 기존 경로 경계, 재분석 지점/EFS/sparse/offline 거절, 용량 reserve, 새 경로만 생성,
  runtime guard 및 실패 사본 보존 조건을 유지한다. 지원하지 않는 스트림은 HOLD한다.
- 서버 도우미는 동일 main/backend PID·생성 시각·실행 경로·8000 소유자를 결합하고
  `/health`의 Running REAL/버전/logger ID를 사전 검사 전후 대조한다.
  앱을 닫거나 강제 종료하지 않으며 정상 UI 종료 후 세 번의 부재 관찰을 기다린다.

개발 증거: `C:/Users/user/Desktop/SmartFactory/PDCA_STREAM_COPY_20261012_5a7ed041`.
아직 전체 증거 폴더를 봉인하지 않았다. 원본/설치 경로·부모 ACL은 변경하지 않는다.

## 실제 개발 검사

| 검사 | 결과와 범위 |
|---|---|
| 기존 엔진으로 실제 NTFS ADS fixture 재현 | `alternate-data-stream`, native exit 1. 실패 로그 보존 |
| `test-cold-backup-streams.ps1` 최종 `streams-tests-03` | native PS 5.1, 94 assertions, exit 0. 실제 2GiB+17바이트 파일, source/copy 변조·누락·추가·잠금·manifest 부모/개수 오류 등 포함 |
| `test-cold-operating-streams.ps1` 최종 `wrapper-tests-04` | 43 checks, exit 0. 공간·동일 세대·health·새 자식 ACL·덮어쓰기 거절 |
| pinned carrier | 5 checks, exit 0. 같은 잠금 바이트, pin/멤버/변조 검사; 서버 main은 이 개발 검사에서 미실행 |

94 assertions에는 fixture 경계 검사도 포함되며 서로 다른 테스트 사례 94개라는 뜻은 아니다.
중간 실패도 보존했다. 테스트 변수와 PowerShell switch의 대소문자 이름 충돌,
Windows ACL의 implicit Synchronize 비트, 비승격 개발 계정의 보호 자식 쓰기 거절을
시험에서 정확히 반영한 뒤 위 최종 검사를 실행했다. 원본 보호 조건은 완화하지 않았다.

제품 runtime 소스는 직전 전체 `npm run health` exit 0 이후 변경하지 않았다.
새 도구는 위 전용 검사를 적용했다. PyInstaller는 scripts 디렉터리를 포함하므로
향후 최종 후보의 payload 검증에는 새 도구 파일도 포함해야 한다.
이전 제품 health 결과를 새 도구나 최종 설치본의 검증 결과로 확대하지 않는다.

## 고정 묶음과 서버 실행

```text
server bundle: C:\Users\user\Desktop\SmartFactory\SFL_STREAM_COPY_5a7ed041
bundle manifest SHA256: EEB6FAC4D14458D64539E3075120250AC530342328A9F4B54FED6881D4AEB68F
command TXT SHA256: DC6E4E998532F65A3DE597406FA66115DA1356189EF8D48C9E086B9D7C1D39AA
engine DLL SHA256: FB12E3ACB370D86999156600EFB3CD23083D890DFEC1216CF4E06E9C1CCE2A26
actual result: C:\Users\user\Desktop\SmartFactory\Qa0596a
```

Codex가 `Z:/SmartFactory/20261012/send/PDCA_STREAM_COPY_5a7ed041`에서 서버 로컬로
7파일 묶음과 별도 TXT를 복사하고 절대경로/파일 존재를 화면에서 확인했다.
개발→공유 8파일 길이/해시 대조 exit 0. 사용자가 고정 TXT 본문을 실행했다.
서버의 READY 도달은 carrier/helper의 manifest·payload 검사 이후이며,
탐색기 화면 확인만으로 서버 해시 검사를 주장하지 않는다.

2026-10-12 23:43:40 KST의 사전 기록:

| 항목 | 실제 값 |
|---|---:|
| 파일 / 디렉터리 / 추가 스트림 | 314,592 / 245 / 680 |
| 기본+추가 스트림 bytes | 55,560,334,970 |
| 필요한 여유 bytes | 74,438,501,971 |
| 실제 여유 bytes | 75,624,677,376 |

정상 종료 직전 main PID 2424, backend PID 11668, logger
`20d2045c-d2e8-41bd-907e-3786534c87c2`였다. health의 build는 기존 운영본
`541d701d544eea6a8a4e4836047077eaf9cfaf30`, Running REAL이었다.
화면의 작업 정보 `60332 / 6`을 확인했으며 다시 제출하지 않았다.

READY를 확인한 뒤 Codex가 앱 창의 정상 닫기 버튼을 눌렀다.
23:45:02 KST 기록은 앱/backend/8000 부재 세 번과 앞선 PID/logger를 결합한다.
당시 부재 영수증의 `normal_nonforced_shutdown_receipt_verified=false` 원문은 유지한다.
후속으로 회수한 Electron 로그 934,206바이트의 STARTUP 3,499건을 파싱했다.
동일 `2424-mv4eo9mv-ls9omluc` 세션의 backend PID 11668 생성/종료 기록을 결합했고,
23:44:57.090 KST에 `reason=close`, `exit_code=0`, `forced=false`, 소요 8,242.5ms를 확인했다.
검사 exit 0이며 로그 SHA256은
`e179532f1225cb4d3a18045b3cdc7650b67aeeacdfbdbcff6f01181dd0e14087`이다.
전체 사본 manifest와 이 별도 회수 로그의 결합은 아직 미완료다.
앱은 닫힌 상태로 두고 같은 도우미의 복사/원본·사본 검산 완료를 기다린다.

완료된 사전 JSON 8개는 탐색기로
`Z:/SmartFactory/20261012/return/PDCA_STREAM_COPY_5a7ed041_preclose`에 회수했다.
공유/개발 사본 8개 해시 대조 exit 0이다. 서버의 각 JSON 콘솔 해시는 출력되지 않았다.
최종 사본 manifest/result와 재시작·수집 재개는 아직 확인하지 않았다.

현재 닫힌 CSV와 metadata, 전체 observation/image fact, 최종 image manifest,
현행 진단 JSONL 2개 및 Electron 로그는 별도 `return/PDCA_STREAM_COPY_5a7ed041_shutdown`에
탐색기로 회수했다. metadata는 같은 logger의 `finalized=true`, `closeout_reason=shutdown`,
`final_persisted_sample_seq=257208`을 기록한다. 실제 CSV 257,208행의 sample_seq가 1부터
마지막까지 연속이고 모든 행의 logger ID 및 마지막 순번이 종료 metadata와 일치했다(exit 0).
마지막 작업 정보는 `60332 / 6`이었다. 전체 규칙 대조의 후속 exit 1 결과는 아래에 구분한다.
image 최종 manifest는 row 4,143,509, written 19,912, failure 0, dropped 44를 기록한다.
과거/현재 drop 원인과 개별 이미지 무결성은 이 종료 기록으로 통과 처리하지 않는다.
개발 PC에서 모든 선택 입력을 먼저 Read 공유로 열어 복사/해시 대조하고,
기존 CSV validator의 현재 서버 프로파일·fact·최종 manifest 옵션으로 검사하는 작업을 시작했다.
이는 선택한 현재 CSV 검사이며 전체 과거 데이터/개별 이미지 QA가 아니다.

같은 공유 회수 폴더에 `system.log`와 `status.log`도 추가 회수하고 개발 사본과 해시를 대조했다.
system 로그 3,516건의 JSON 파싱 결과, 같은 backend PID/세션의 종료 단계 9개가 모두
`success=True`였고 observation final drain도 `complete=True`였다. backend 전체 종료 시간은
8,091.8ms이며 앞선 Electron의 프로세스 종료 시간 8,242.5ms와 측정 범위가 다르다.
23:44:49~52 KST에는 종료된 이미지 서비스에 대한 요청이 `shutdown`/502로 실패한 ERROR 4건이
있었다. 처음의 “종료 중 경고/오류 없음” 검사는 exit 1이었다. 실패 검사 원문과 로그를 보존하고,
실제 오류 4건을 명시한 후속 대조는 exit 0이다. 오류 없는 종료나 이미지 무결성 PASS로 바꾸지 않는다.

작업 정보 초기화 원인도 CSV와 실제 로그로 확인했다. 11:48:08 KST에는 Count 59→0,
14:28:08~09 KST에는 41→0과 함께 제품/금형이 비워졌으며 두 로그 모두
`reason=count_transition_to_zero`를 기록한다. 운영 build `541d701d`의
`FacilityData/service.py`에는 유효한 PLC 샘플의 양수→0 전환 시 작업 정보를 초기화하는
같은 로직이 있다. 21:59:48 KST의 기존 재입력 이후 마지막 행까지 `60332 / 6`을 유지했다.
이 확인에서 정책 변경이나 작업 정보 재제출은 하지 않았다.

위 후속 근거는 개발 증거 폴더의 `current-job-history-review.json` 및
`closed-system-log-review.json`이다. 기본 바이트의 공유↔개발 해시 일치 범위이며,
최종 서버 cold manifest와의 결합은 아직 미완료다. 전체 서버 사본은 진행 중이며,
앱 재시작 및 출시 판단은 완료 처리하지 않는다.

2026-10-13에는 선택 image fact의 4,143,509행을 streaming으로 읽어 SQLite 인덱스로 정산했다.
103.298초/exit 0이며 ID 중복 0, Windows 대소문자 정규화 경로 중복 0,
선택한 행 너비·경로·SHA256 형식·크기·시각 검사 오류 0이다. 전체 스키마 검사의 대체가 아니다.
파일 전후 identity/전체 hash가 같고, 최초 4,123,597행까지의 실제 바이트 SHA256
`6cb93b78726e2be73bc9b6cb19458cdfdd1d4f47b06f1571454e6a774852ac6e`가 시작 metadata와 일치한다.
이후 19,912행은 종료 manifest의 written과 같으며 모두 현재 SPOT service
`b5c413fc-08ea-40a9-86f5-a6fdee705aad`의 `fresh` 연결이다.
전체 기록은 89개 UTC 날짜·172개 service 값에 걸쳐 있고, fresh 4,137,079행,
stale 6,418행, missing_observation 12행이다. 개별 이미지 존재/바이트/디코딩이나 drop 44건의
원인은 이 기록 검사로 확정하지 않는다. `current-image-ledger-index/summary.json` 및
`image-ledger.sqlite`를 후속 실제 파일 manifest 대조에 사용할 수 있다.
완료한 인덱스 하위 폴더만 봉인했으며 manifest SHA256은
`ea26cb5ff2736b7cf90e942b8f26d7d8d5133227e3f3b7fdbc465ae9580d64cb`다.
진행 중인 상위 실행 폴더 전체가 봉인된 것은 아니다.

### 현재 CSV의 전체 validator 종료 결과

2026-10-13 00:37:26 KST에 session 22947은 2,066.926초/exit 1로 종료했다.
전체 stdout 12,064바이트(UTF-16)와 stderr 0바이트를 읽었고, 실제 실행 소스 SHA256
`fa52c8764e7a6c4369d441f4954cf4c9dc13b2e5544bff9950b81c78de445182`가 현재 파일과 일치한다.
선택 입력 8개의 종료 후 hash/길이도 처음 회수 영수증과 다시 일치했다.

- 보고된 실패 1건은 `spot_configuration_snapshot.config_operator_verified must be True`다.
  운영 metadata의 실제 값은 false이며 fingerprint mismatch/drift와 함께 유지한다.
  사용자 본인의 역할 지정만으로 이 기술 확인을 true로 변경하지 않는다.
- observation fact 207,561행·고유 key·SHA256·poll gap 0이 metadata와 일치한다.
  연결 key가 있는 realtime 257,188행 모두 fact에 연결되고 진단 source mismatch는 0이다.
- image fact 4,143,509행과 SHA256은 final manifest와 일치한다.
  개별 이미지 바이트/디코딩 검사, 전체 과거 CSV 검사, 최종 서버 사본 결합은 이 결과에 포함되지 않는다.
- 전체 현재 프로파일 판정은 FAIL/HOLD다. 데이터 관련 다른 실패가 출력되지 않았다는 사실을
  전체 R4·장비 설정·현장 QA PASS로 확대하지 않는다.

`current-csv-validation-review.json`의 출력·입력 독립 대조는 exit 0이며 원래 validator exit 1을 보존한다.
34분 검사 동안 개발 PC working set 10,940,825,600바이트를 관측했으나 정식 peak 측정은 아니다.
별도 10,000행 prefix fixture의 cProfile은 8.157초/exit 0이며 `Path.resolve`가 누적 6.336초였다.
이는 검증 도구의 경로 확인 비용 계측이며 서버 수집 앱의 R2 성능 측정이나 규칙 완화 근거가 아니다.
이 단계에서 validator/제품 소스는 변경하지 않았다.

### 이미지 기록 validator의 메모리 보완

이후 같은 실제 입력에서 관측한 메모리 사용을 근거로 `validate_spot_image_fact_manifest`만
보완했다. 전체 파일을 바이트/CSV 행 목록으로 적재하던 부분을 1MiB 해시 읽기와 CSV 순차
읽기로 바꿨다. 같은 열린 CSV에서 첫 번째 순회로 파싱과 개수를 확인하고 두 번째 순회로
행을 검사하므로 기존 오류 순서와 뒤쪽 파싱 실패 시 부분 행 오류를 보고하지 않는 계약을 유지한다.
각 이미지 경로의 실제 `Path.resolve`와 로그 폴더 경계 검사도 유지한다. 오류 목록 자체는
기존대로 모두 보존하므로 오류가 많은 입력까지 일정 메모리를 보장한다는 뜻은 아니다.

변경 전 소스는 `validator-memory-validation/validate_csv_v2_shadow.baseline.py`에 원래
`fa52c876...` SHA256으로 보존했다. 새 소스 SHA256은
`3040f3e92df9edd97cbd6c4d204a2a0ddfd04de030793d92e90934ecb5845725`다.
2만 행 재현 검사는 변경 전 peak 24,152,644바이트로 8MiB 상한을 넘겨 exit 1이었고,
변경 후 관련 운영 계약 검사 82개는 exit 0이었다. 별도 84가지 입력/manifest 모드의
이전·새 함수 결과가 동일했다(exit 0). 별도 2만 행 비교의 tracemalloc peak는
24,111,892→2,107,528바이트였다. 이 메모리 fixture만 경로 OS 조회를 대체했고,
나머지 비교와 실제 파일 검사에서는 실제 경로 확인을 사용한다.

실제 입력 8개의 Read 공유 핸들을 먼저 유지하고 원래 회수 hash/크기를 대조한 뒤
현재 CSV 전체 비교를 새로 시작했다(session 21403, 2026-10-13 01:01:20 KST).
원래 stdout·exit 1과 최종 결과를 비교하며 운영자의 설정 확인 실패를 PASS로 바꾸지 않는다.
가상환경 launcher PID 38428의 작은 메모리 수치는 실제 validator의 메모리가 아니다.
별도 관찰 session 39781은 CIM으로 부모/명령/생성 시각을 대조한 실제 Python PID 13380을
측정한다. 전체 자료의 비교·종료·최종 메모리 결과는 아직 미완료다.

최종 소스의 `npm run health`는 session 83365에서 355.722초/exit 0으로 종료했다.
의존성 14개, Electron 94개, frontend Node 9개·Vitest 434개, backend 918개 중 917개 통과와
기존 private F01 skip 1개, ruff/mypy 및 QA self-test를 확인했다. 의도된 실패 fixture의
오류 출력과 Starlette deprecation 경고를 보존하며 서버 현장 QA 통과로 확대하지 않는다.
이 절의 자료는 `validator-memory-validation` 하위에 보존하며 검사 중인 폴더를 봉인하지 않는다.
2026-10-13 01:04 KST 서버 화면은 같은 `Qa0596a`의 backup 단계에서 199,884파일,
47,389,165,463바이트를 표시했다. 최종 Verify/result가 나오기 전까지 앱은 닫힌 상태로 유지한다.

### 실제 전체 입력 비교 완료와 서버 최종 검산 시작

같은 전체 입력 비교 session 21403은 2,404.041초/exit 0으로 종료했다. 이는 변경 전후
출력 일치 검사의 종료 코드이며, 실제 validator는 이전과 같이 **exit 1**이다.
두 stdout 전체를 독립적으로 읽어 줄바꿈/인코딩 정규화 후 같음을 확인했고 stderr는 0바이트다.
유일한 실패는 기존 `config_operator_verified must be True`였다. 입력 8개의 최종 길이·SHA256과
검증 소스 `3040f3e9...`도 다시 대조했다(exit 0). 장비 설정·개별 이미지·전체 데이터 PASS로 바꾸지 않는다.

실제 Python PID 13380 관찰 session 39781도 exit 0으로 끝났다. 467개 표본의 최대 working set은
2,296,913,920바이트, 관측된 OS peak는 4,161,220,608바이트다. 시작 후 관찰이며 마지막 5초 미만의
peak를 보장하지 않는다. 이전 10,940,825,600바이트 관측은 정식 peak가 아니므로 동일 조건의
성능 시험으로 표현하지 않는다. 이번 전체 경과 시간은 이전 2,066.926초보다 길었으며
서버 앱의 성능 개선 근거로 사용하지 않는다.

완료한 `validator-memory-validation` 하위만 소스/시험 snapshot·출력·메모리 표본과 함께 봉인했다.
manifest SHA256은 `1b9827e8e9ed072f2c9a692b7092078a0bac720a83a50eac32f4a855224ea205`다.
28개 증거 파일 및 manifest를 `Z:/SmartFactory/20261013/records/PDCA_VALIDATOR_MEMORY_5a7ed041`에
복사하고 기본 파일 바이트 해시를 대조했다. 현재 데이터 입력 자체는 앞선 회수 폴더에 남겨 두고
그 8개 hash 영수증을 포함했다. 상위 서버 실행 폴더 전체를 봉인한 것은 아니다.

01:42~01:43 KST 서버 화면에서 backup의 마지막 314,675파일/55,562,005,735바이트와
`source-and-restored-verification` 전환을 확인했다. 이 phase 이름은 원본·사본 검산에 공통으로
쓰이는 엔진 표시이며, 이번 호출은 `restore=false`로 복구 실행이 아니다.
아직 최종 `RESULT_PATH`·manifest/result 콘솔 hash·성공 JSON을 확인하지 않았다.
`server-copy-verification-started-20261013.jpg`에 화면을 보존하고 같은 검산이 끝날 때까지 앱은 닫아 둔다.

## 이어서 확인할 조건

1. 같은 `Qa0596a` 실행의 결과/HOLD를 확인한다. 관찰이 끊겼다는 이유로 중복 실행하지 않는다.
2. 최종 manifest/result 콘솔 해시와 회수 바이트를 대조한다. 실패 시 부분 사본을 보존한다.
3. 동일 세대의 비강제 정상 종료와 데이터 closeout을 검증한다.
4. 기존 승인 운영 앱을 정상 시작하고 새 실행 세대·실제 저장 재개·제품/금형 지속성을 확인한다.
5. 불변 사본의 전체 CSV/metadata/observation/image/fact 검사를 진행한다.

미서명 내부 운영 정책, 사용자 본인의 담당 역할, 장비 모델 미정은 그대로다.
설치·운영 승격·롤백 기준 갱신은 수행하지 않았다.

## 2026-10-13 03:08 KST 최종 목록 대조 대기

서버 콘솔의 Verify 읽기 카운터가 314,675파일/111,124,011,470바이트에 도달했다.
바이트는 backup 55,562,005,735의 두 배로, 고정 도우미의 원본·사본 해시 읽기 경로와 일치한다.
이후 카운터는 유지되며 진행 신호가 계속 출력된다. 소스 코드상 마지막 파일/스트림 목록 대조
단계로 추론하며, 성공 result와 콘솔 hash가 아직 없어 최종 검증 완료로 기록하지 않는다.
앱은 종료 상태로 유지한다. 탐색기를 최소화해 완료 출력 영역을 노출했으며 콘솔에는 입력하지 않았다.
`server-observation-20261013-0308.json`과 같은 시각 화면에 관찰을 보존했다.

회수할 작은 최상위 결과/manifest 전용 폴더를
`Z:/SmartFactory/20261013/return/PDCA_STREAM_COPY_5a7ed041_Qa0596a_metadata`에 준비했다.
아직 결과를 복사하지 않았다. 앱 재시작·새 수집 세대·작업 정보 지속성 확인은 남아 있다.

## 2026-10-13 03:10 완료 결과와 03:26 이후 재시작

앞 절의 대기 상태는 아래 결과로 갱신한다. 같은 `Qa0596a` 실행이 03:10:44 KST에
`SELECTED_COLD_COPY_DEFAULT_AND_NAMED_DATA_STREAMS_VERIFIED`를 기록했고, 03:13 화면에서
완료 문구와 콘솔 프롬프트 복귀를 확인했다. Codex가 탐색기로 최상위 11파일을
`Z:/SmartFactory/20261013/return/PDCA_STREAM_COPY_5a7ed041_Qa0596a_metadata`로 회수했다.
서버 로컬의 `c/r0`, `c/r1` 사본은 그대로 보존한다.

| 확인 | 결과 |
|---|---|
| `files.tsv` | 151,456,422바이트, SHA256 `30B5967D88F102CD0618B191F99FDCD21C69FC59740B862D022FFCF0D02C85BF` |
| `result.json` | 2,148바이트, SHA256 `A114DD9901E75388B2D1D0C93F58FF5132F804A38EB3682A647AFAC4D93CA88A` |
| 전체 manifest 정산 | 파일 314,675·폴더 245·추가 스트림 680 |
| 데이터 크기 | 기본 바이트 55,561,988,055 + 추가 스트림 17,680 = 55,562,005,735 |
| 원본/사본 검산 | 기본·추가 스트림 재해시, 원본 metadata/stream membership 유지, 앱/backend/port 부재 참 |
| 닫힌 현재 입력 결합 | 기존 회수 8파일의 길이·SHA256이 해당 manifest의 유일한 항목과 일치 |

개발 PC `Get-FileHash`와 별도 `retrieve-terminal-results.py` 모두 exit 0이다.
스크립트는 전체 manifest의 형식·부모/추가 스트림 순서·개수·크기·중복 경로와 현재 입력을 대조했다.
`server-terminal-results-review.json` SHA256은
`66fe61dc2dfe63e3b9945f755015e9082d286087bb28dd79e8c3d33ffa047c31`이다.
최초 `server-console-terminal-20261013.json`에는 화면 해시 전사 오류가 있었다.
03:13 원본 화면을 다시 읽고 위 실제 파일 해시와 대조한 정정을 새 review에 남겼으며,
처음 기록과 원본 파일은 수정하지 않았다.

서버 결과 자체의 `normal_shutdown_attestation`은 여전히 `NOT_EVALUATED`다.
별도 동일 세대 비강제 종료 기록을 이번 manifest의 `debug_electron.log` 해시에 결합했다.
앞서 확인한 8,242.5ms/forced=false/exit 0, backend 종료 9단계 성공과 종료 중 이미지 502 오류
4건을 함께 유지한다. 이 결과는 실제 복구 실행·ACL 복원·전체 데이터 의미 검증을 증명하지 않는다.
공유 드라이브로 회수한 파일은 기본 바이트 대조 범위이며 NAS의 ADS 보존으로 확대하지 않는다.

### 기존 승인 운영본의 정상 재시작과 저장 재개

콘솔·회수 해시를 대조한 후 바탕화면의 기존 앱을 한 번 정상 시작했다. system/status 로그에는
03:26:56 backend PID `9028`, session `b43cc3193790` 시작과 03:27:01 Running 전환이 기록됐다.
서버 로그에서 확인한 `http://192.168.0.7:8000`에 읽기 전용 GET으로 접근할 수 있어
health·data·stats·작업 정보·memory·error queue를 두 차례 보존했다. 인증·설정은 변경하지 않았다.

- `/health`: 기존 build `541d701d544eea6a8a4e4836047077eaf9cfaf30`, frozen, REAL, 수집/driver thread 참.
- 새 logger `e9a785c0-46a2-45d2-bf7a-4187cce08771`, SPOT `efca4313-f987-4bb2-bcc8-4de40712396c`.
  약 63초 사이 poll 312→375, 수집 행 1,413→1,678, observation completed 312→375였다.
- 새 CSV `Factory_Integrated_Log_v2_20261013_032656.csv`와 metadata, system/status 로그를
  탐색기로 `Z:/SmartFactory/20261013/return/PDCA_STREAM_COPY_5a7ed041_restart`에 회수했다.
  CSV 사본은 2,266,874바이트/1,783행, seq 1~1,783, 헤더·행 너비·새 logger 일치, NUL 0이다.
  SHA256은 `37d8d07475c10e089fcb652bd0810a048621a022916f1dad84a517f54d72003c`다.
- 모든 회수 행과 API 작업 정보가 `60332 / 6`이었다. 적용 시각은 10월 12일 21:59:48 KST 그대로이며
  Codex가 재제출하지 않았다. CSV 온도 상태는 startup_pending 14·stale 172·valid 1,597행이었다.
- 앱을 탐색기 회수 때문에 최소화했다가 복원한 전후 image written은 51→125였다.
  각 표본의 capture writer failure/drop은 0이다. 수집 중 파일의 GUI 사본은 원자적 snapshot이 아니며
  서버 콘솔 해시나 전체 CSV validator를 갖춘 최종 닫힌 데이터 검사로 취급하지 않는다.

`read-restart-api.py` 두 실행, 이미지 GET 두 실행 및 `review-restart.py` 모두 exit 0이다.
client health 경과는 476.400/81.365ms였고 서버 stats의 해당 health 처리는 약 6ms였다.
네트워크 포함 client 시간과 서버 내부 시간을 혼용하지 않으며 정식 성능 gate 통과로 표현하지 않는다.
metadata의 `config_operator_verified=false`, `fingerprint_mismatch`와 drift는 계속 유지됐다.

### 후속 Warning: 이미지 연결 timeout 3건

03:37 KST 화면에 Warning/ErrQ 3이 나타나 별도 GET과 화면을 추가 보존했다.
03:36:02, 03:36:10, 03:37:40 KST의 `/api/spot/live_image.jpg` 502 세 건은
`SpotTransportConnectTimeout`, 요청 경과 2,000/2,000/2,015ms였다.
각 오류의 transport correlation ID가 같은 새 SPOT 세대의 failure event와 일치했다.
이전의 capture writer failure 0은 upstream 연결 오류가 없었다는 뜻이 아니다.

추가 시점 image capture written은 256, capture drop/failure는 0이고 원격 수집은 계속 실행 중이었다.
transport 누적은 image failure 3·temperature failure 2, port reuse violation/pool exhaustion 0,
quarantine 77초였다. 이 카운터만으로 네트워크/장비 원인이나 모든 timeout 원인을 확정하지 않는다.
`restart-warning-review.json`에 후속 대조를 보존했다(exit 0). 오류 큐를 비우거나 재시작·장비 설정·
요청 주기를 변경하지 않았다. 최신 UI Warning을 앞선 Running 표본으로 덮어쓰지 않는다.

다음 작업은 이 연결 오류 원인 조사와 불변 서버 사본의 전체 CSV/metadata/observation/image 의미 검사다.
설치·운영 승격·롤백 기준 갱신은 수행하지 않았으며 R1~R6 정식 출시 HOLD와 goal active를 유지한다.

완료한 terminal/restart 증거 62파일과 manifest를 별도 `terminal-restart-verified` 하위에 봉인했다.
manifest SHA256은 `8fb43c5736d14d75e1eed620efd04fec25768a3885be1796759e52c7893fc4dc`이며,
`Z:/SmartFactory/20261013/records/PDCA_STREAM_COPY_5a7ed041_terminal_restart`의 63파일 기본 바이트를
대조했다(exit 0). 이는 55GB 사본 전체의 NAS 전달이나 상위 실행 폴더 전체 봉인이 아니다.

## 이미지 기록과 cold manifest의 전체 연결 대조

기존 봉인된 image ledger SQLite SHA256과 이번 cold manifest를 검증한 뒤 4,143,509개 기록을
순차 대조했다. 비교 범위는 root 0의 `logs/test_data/spot_images`다. 13.983초/exit 1이며
다음 finding을 보존한다. 현재 운영 파일이나 기록은 수정하지 않았다.

| 항목 | 대조 결과 |
|---|---:|
| 실제 cold manifest의 이미지 파일 | 312,985 |
| fact 경로·크기·SHA256이 모두 일치 | 312,969 |
| 경로는 있으나 크기/해시 불일치 | 0 |
| 현재 선택 capture root에 파일이 없는 과거 fact 참조 | 3,830,540 |
| manifest에 있으나 fact 참조가 없는 파일 | 16 |

누락 참조의 UTC 날짜 범위는 7월 1일~10월 5일이다. 다른 백업 폴더·NAS 압축에서 해당 이미지를
찾는 작업은 아직이므로 영구 소실이나 삭제/보존 정책의 원인을 확정하지 않는다.
미참조 16파일은 10월 7일 23:12:38~55 UTC의 JPEG다. 자동 삭제/등록/복원을 수행하지 않았다.
종료 직전 SPOT 세대 `b5c413fc-08ea-40a9-86f5-a6fdee705aad`의 19,912개는 모두 경로·크기·해시가
일치했다. 실제 이미지 디코딩·모든 이전 세대의 완전성 PASS와 구분한다.

전체 개수 보존식·날짜/세대 집계·닫힌 세대 SQL 대조는 exit 0이고 원래 finding exit 1을 유지한다.
근거는 `image-ledger-cold-manifest-join/summary.json`, `review.json`, 미참조 전체 목록과 재현 스크립트다.
해시로 연결한 원본 index/manifest에서 전체 누락 집합을 다시 산출할 수 있으며 20개 예시는 전체 목록이 아니다.
이 완료 하위만 봉인·공유했다. manifest SHA256은
`8f0e2d8aa28998233dee6445c639d31716e1754e105d6a45451bba1a5b847e01`, 공유 위치는
`Z:/SmartFactory/20261013/records/PDCA_IMAGE_MANIFEST_JOIN_5a7ed041`이다.


## 04시 후속 관찰 연결

cold 사본 완료와 직전 세대 정상 종료 증거는 그대로 유지한다. 재시작 후 영상 connect timeout은 6건으로 늘었고, 전체 transport 실패 13건과 구분했다. 작업 정보는 03:58:41 KST 실제 operator 입력으로 `60192 / 17`이 됐으며 Codex는 값을 바꾸지 않았다. 과거 이미지 archive/cold 내용 해시 조인과 NAS loose 이미지 후속 검사는 [이미지 복구 후보 조사](production-release-risk-validation-image-recovery-20261013.report.md)에 기록했다. 새 관찰은 기존 봉인 기록을 대체·재작성하지 않는다.
