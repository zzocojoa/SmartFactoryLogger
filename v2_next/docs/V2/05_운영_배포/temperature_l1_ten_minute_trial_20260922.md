# Temperature L1 후보 10분 현장 검증

기준일: 2026-09-22 KST. 사용자가 선택한 10분 시작·수집·저장·종료 시험과
원본 복귀를 완료했다. 최종 작업정보 확인까지 마친 판정은
`TEN_MINUTE_FIELD_TRIAL_COMPLETE`이며, 이번 시험의 미완료 확인 항목은 없다.

전체 현장 검증과 운영 승격은 별도다. `ten_minute_evidence_passed=true`,
`field_validation_passed=false`, `production_release_approved=false`를 구분한다.
이 문서는 보존된 결과의 게시용 요약이며 새 서버 실행이나 재빌드 기록이 아니다.

## 후보와 증거 범위

| 구분 | 식별·범위 |
| --- | --- |
| 시험 후보 | `df4b731ee648216237958240d3123024eed07596`, schema 2.5.2 |
| 복귀 원본 | `d7a1b20f96711fb07fc7add0867e79ee36506fce`, schema 2.5.0 |
| 표시 버전 | 둘 다 v1.0.26이므로 commit·파일 해시로 구분 |
| 승인한 관찰 | 600초 목표, 실제 602.6383874초·38회 표본, `duration-complete` |
| 실제 CSV 기록 구간 | 2026-09-22 09:23:08.500460~09:33:23.830382 KST |
| 최종 결과 | `TRIAL EXIT 0`, 후보 종료 후 기존 원본 복귀 |

CSV 구간은 준비·종료 경계의 행을 포함하므로 600초 관찰 구간과 같지 않다.
기존 G1~G5 후보 `72a4103`의 [7시간 결과](temperature_seven_hour_trial_20260921.md)는
별도 실행본의 증거로 보존한다. 이번 10분 결과를 새 후보의 7시간 통과로 확대하지 않는다.
코드 단계의 합성 production-path 시험은 [L1 결과](../../../LIFECYCLE_RESULT_L1.md),
[C1~C3 결과](../../../TEMPERATURE_CLOCK_RESULT_C1_C3.md),
[T1~T3 결과](../../../TEMPERATURE_FOLLOWUP_RESULT.md)에 구분돼 있다.

## 수집·저장 검산

| 항목 | 실제 결과 |
| --- | --- |
| CSV | 2,558행·110열, sample_seq 1~2558 연속 |
| 온도 출력 | valid 2,552행, startup_pending 6행 |
| 시작 표본 | 초기 6행 Temperature·observation key 공백 유지 |
| SPOT observation fact | 614건, 단일 서비스 poll_seq 1~614, 중복·gap 0 |
| CSV→fact | key가 있는 2,552행 모두 연결, service/poll/observation/payload hash 일치 |
| closeout | shutdown, finalized=true, final_persisted_sample_seq=2558 |
| 최종 fact 저장 | 행 수·SHA 일치, spool_pending=0, write_failure=0 |
| 이미지 fact | 559건, 최종 manifest의 행 수·SHA 일치, failure/drop 0 |
| 작업정보 | 시험 CSV·복귀 화면의 값 유지, 사용자가 실제 작업과 일치함을 확인 |

38회 표본에서 CSV rows 40→2551, poll12→613과 파일 크기가 계속 증가했다.
마지막 표본의 fact pending/inflight 1건은 종료 후 최종 CSV/fact의 poll614,
manifest와 명시적 drain 완료로 교차 확인했다. 표본별 관찰이 연속 최대 지연을 증명하지는 않는다.

metadata 안의 이미지 manifest는 실시간 snapshot이며 최종본이 아니다. 검증기에
`spot_image_fact_manifest.final.json`을 명시해 559건의 최종 상태를 확인했다.
이미지 바이너리는 회수·해시 검증하지 않았다. V1 CSV는 기존 설정이 false여서 대상이 아니다.
posthoc phase/changeover/linkage 산출물의 `unknown/not_applicable`을 통과로 변경하지 않았다.

## 종료·원본 복귀

- 후보 main/backend exit0, forced=false 및 프로세스·8000포트 해제를 receipt로 확인했다.
- system 로그의 종료 stage 9개 모두 success=True이며, 별도 observation final drain=True와
  최종 shutdown success=True/exit0을 확인했다. drain을 열 번째 stage 로그로 세지 않는다.
- Electron의 dashboard-operational-ready와 동일 session의 단일 정상 종료 기록,
  후보 trace의 SHA·연속 sequence·종료 경계 순서·trace.closed가 일치했다.
- 원본 초기 종료도 main/backend exit0·forced=false·프로세스/포트 해제를 확인했다.
  기존 원본의 trace는 null이므로 후보와 같은 계측 증거를 주장하지 않는다.
- 원본 설정 hash가 유지됐고 후보 상태를 역복사하지 않았다. 복귀 후 3회에서
  rows1102→1255, poll6→38, CSV bytes1523332→1728466으로 증가했다.
- 완료 콘솔을 사용자가 닫은 뒤 09:54~09:55 KST 원격 화면에서 Running,
  EX/LS/SPOT/Comm OK와 실시간 값 갱신을 확인했다. 이 확인은 사용자 응답과 UI 관찰이며,
  콘솔 종료 후 새로운 PID/포트/API receipt를 수집한 것은 아니다.
- 사용자의 후속 작업정보 확인을 별도 closeout에 추가했다. 실제 식별값과 응답 원문은
  로컬 증거에 보존하며 앱의 metadata는 수정하지 않았다.

## 오류·미검증 범위

후보 종료 시작 뒤 이미지 요청 2건이 HTTP502/type=shutdown으로 거절됐다.
ERROR 원문을 보존하고 종료·drain 성공과 함께 기록한다. 로그 오류가 없었다고 표현하지 않는다.

원본 준비 완료는 약241초로 기존900초 한도 내였다. 복귀 후 첫 표본의 stale 누적1073행은
이후 3개 표본에서 증가하지 않았으며 fresh 수집이 진행됐다. 발생 구간·지연 원인은 확정하지 않았다.

SPOT attestation=fingerprint_mismatch, operator/comparator verified=false와
async_fact_only를 유지했다. 작업 제품·금형 확인은 장비 설정 attestation이 아니다.
Count0~2, PLC 부분 실패, worker timeout, wall-clock 조정, 통신 장애 복구와 자정 전환은
이번 현장에서 미검증이다. 이전 합성 시험을 해당 현장 사건으로 표시하지 않는다.
NSIS 설치·업그레이드, 구버전의 새 형식 파일 append, 전체 운영 이력 규모도 이 시험의 범위가 아니다.
history/API P2는 별도 보류하며 이번 종료조건에 추가하지 않는다.

## 명령·검토 근거

Windows / Python 3.12.6에서 저장소 `scripts/validate_csv_v2_shadow.py`를 실행했다.
`--v2`, `--metadata`, `--spot-observation-fact`, `--spot-image-fact`,
`--spot-image-fact-final-manifest`에 회수 파일을 명시했고 exit0/PASS였다.
환경 override는 `PYTHON_DOTENV_DISABLED=1`, `PYTHONUTF8=1`이다.
정확한 인수·환경·0.782초 실행 시간은 `field-validator-command.json`, 출력은 `field-validator.log`에 있다.

후속 증거 감사 `review_field.py`는 최종 exit0, 33 pass/0 fail이었다.
최초 감사는 기존 원본에도 trace가 있다는 가정으로 exit1이었고, 원본 trace:null을 확인한 후
실제 종료·release 증거로 판정했다. 후보 trace 필수 검사는 유지했다.
실패 원문·당시 스크립트와 이후 실행 기록을 모두 보존했다.
독립 읽기 검토에서 receipt·CSV/fact·manifest·종료 로그의 blocker는 없었다.
독립 검토의 초기 Count 집계 오류도 행별 파싱으로 정정했고 원문 검토 기록에 남겼다.

이번 게시 작업은 문서만 변경하므로 제품 health·장비 시험·빌드를 다시 실행한 것으로 세지 않는다.
문서의 값·해시·링크·diff 및 게시 범위는 자체 검토한다. 제품 시험은 시험한 commit의 기록으로 유지한다.

## 보존 위치와 무결성

원시 CSV·로그·작업 식별값은 Git에 포함하지 않는다. 아래 로컬 증거는 저장소 복제만으로
제공되는 첨부물이 아니며, 검토자는 저장소의 합성 시험과 현장 요약을 구분해야 한다.

- [최종 사용자 확인](C:/Users/user/Desktop/SmartFactory/L1_T10_R1_evidence/field-closeout.json)
- [최종 closeout manifest](C:/Users/user/Desktop/SmartFactory/L1_T10_R1_evidence/field-closeout-manifest.json)
- [증거 감사](C:/Users/user/Desktop/SmartFactory/L1_T10_R1_evidence/field-review.json)
- [실제 검증 명령](C:/Users/user/Desktop/SmartFactory/L1_T10_R1_evidence/field-validator-command.json)
- [감사 실행 기록](C:/Users/user/Desktop/SmartFactory/L1_T10_R1_evidence/field-review-executions.json)
- [회수 파일 해시 목록](C:/Users/user/Desktop/SmartFactory/L1_T10_R1_evidence/server-result-inventory.json)

회수 자료는 381개 파일·6,125,351바이트다. receipt JSON185개와 동봉 SHA185개를 검증했고,
공유→개발 사본의 전체 길이·해시가 일치했다. CSV SHA는 회수본에서 계산한 값이며
서버 로컬에서 별도로 다시 계산했다고 주장하지 않는다. observation/image fact는 생산자 manifest와 일치했다.

| 자료 | SHA256 |
| --- | --- |
| 콘솔과 대조한 result.json | `12DD9BC0B83280BC6CDBA0BA243044A98C21F71CA086523489AFD8A901ABFBA8` |
| 최종 CSV | `b7627d5d5f7bce83b4532e8d21e7cb1bb89fd9af892f3052c7011c7c9ac892e0` |
| observation fact | `9ef3cfc60724e66428f4eb09d166bc79df96e35efc9f78230844f6db3b623c94` |

공유 회수는 `Z:\SmartFactory\20260922\return\L1_T10_R1_RESULT`,
검토·종료 기록은 같은 날짜의 `records\L1_T10_R1_FIELD_RESULT`와
`records\L1_T10_R1_FIELD_CLOSEOUT`에 보존한다. 확인 대기였던 기존 보고서를 덮어쓰지 않고
별도 사용자 확인 기록으로 종료했다. 과거 helper·bundle·manifest·receipt는 수정하지 않았다.

## 게시 단계와 다음 승인

이번 문서 변경은 위험도 낮음이며 제품 호환성·migration·관측 동작에 변화가 없다.
문서 정정은 해당 문서 commit으로 추적할 수 있다. 검증한 운영 복귀는 후보 정상 종료 후
기존 원본과 기존 설정·경로로 돌아가는 방식이며 새 형식 데이터의 downgrade를 뜻하지 않는다.
worker 잔존·저장/drain 실패는 종료 실패로 드러나야 하는 기존 계약으로 유지한다.

사용자는 문서 기록·해당 문서의 commit/push·PR #193 본문 반영을 승인했다.
병합, 운영 적용 또는 P2 착수 전에 각각 다음 단계 진행 여부를 다시 확인한다.
