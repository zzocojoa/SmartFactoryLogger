# Temperature P2 병합본 현장 검증

> **후속 결과 — 2026-09-23:** [실제 120분 서버 설치 검증과 원본 복귀](temperature_p2_nsis_120min_trial_20260923.md)가 완료됐다.
> 아래 내용은 단계별 작성 시점의 기록이며, 정식 운영 승격과 구분한다.

기준일: 2026-09-22 KST. P2 병합본의 승인된 10분 시작·수집·저장·정상 종료·원본 복귀 시험과
콘솔 종료 후 수집 지속 확인을 완료했다. **45개 증거 대조 통과, 실패 0개**다.
이 문서는 완료된 실행의 게시용 요약이다. 제품 코드 변경이나 추가 서버 실행 기록이 아니다.

`ten_minute_evidence_passed=true`, `field_validation_passed=false`,
`production_release_approved=false`를 구분한다. 미서명 내부 검증본이며 설치·업그레이드와
정식 운영 승격은 수행하지 않았다. 운영 장비는 기존 원본으로 복귀했다.

## 후보와 기준

| 구분 | 실제 식별 |
| --- | --- |
| 병합 | [PR #194](https://github.com/zzocojoa/SmartFactoryLogger/pull/194), 2026-09-22 |
| 후보 commit | `d254871f89c98154b4e32879e29601df78f7e159` |
| 원본 commit | `d7a1b20f96711fb07fc7add0867e79ee36506fce` |
| schema | 후보 2.5.2 / 원본 2.5.0 |
| 표시 버전 | 둘 다 1.0.26; commit·파일 해시로 구분 |
| 배포 유형 | `UNSIGNED_INTERNAL` |
| 승인 관찰 | 600초 목표, 실제 601.7652359초, 상태 표본 38개 |
| CSV 시간 | 15:07:13.339288~15:17:25.492071 KST |
| 종료 | `[TRIAL EXIT] 0`, 정상 종료 후 원본 복귀 |

이전 [L1 후보 10분 시험](temperature_l1_ten_minute_trial_20260922.md)과
[G1~G5 후보 7시간 관찰](temperature_seven_hour_trial_20260921.md)은 각 후보의 별도 증거다.
이번 후보의 장시간·자정 통과 기록으로 재사용하지 않는다.

## 수집·저장·종료

| 항목 | 이번 실행 결과 |
| --- | --- |
| CSV | 2,637행, 110열, sample_seq 1~2637 연속 |
| 온도 상태 | valid 2,634행 / startup_pending 3행 |
| 시작 대기 | Temperature와 observation key 공백 유지 |
| observation fact | 613건, 단일 service의 poll 1~613 연속·중복 없음 |
| CSV 연결 | key가 있는 2,634행의 service/poll/observation/payload hash 일치 |
| 이미지 fact | 564건, 최종 manifest 행 수·SHA 일치, failure/drop 0 |
| 진단 journal | 472요청, queued/running/completed 각 472개, 1,416 event 연속 |
| 표본 건강 상태 | 동일 실행 세대, 행·poll 증가, PLC 읽기/연결 실패 및 snapshot 오류 없음 |
| 저장 대기 | 표본 queue_depth 최대 0, pending_write 최대 1; 연속 최대값 측정 아님 |
| 종료 단계 | 9개 성공, SPOT final drain=True |
| closeout | finalized=True, shutdown, final_persisted_sample_seq=2637 |
| 프로세스 | 후보 main/backend exit 0/0, forced=False, 프로세스·포트 해제 |

fact 최종 manifest의 pending/write failure는 0이다. 마지막 CSV는 poll612를 참조하고,
poll613은 마지막 CSV timestamp보다 1.996ms 뒤 완료되어 독립 fact 파일에 남았다.
closeout 이전 완료·최종 manifest·연속 poll·명시적 drain 로그로 확인했다.
CSV와 fact의 마지막 번호가 같아야 한다는 초기 감사 가정은 실패(40 pass/1 fail)로 보존하고,
실제 독립 저장 계약에 맞춰 대조했다. 제품 테스트 assertion이나 안전 검사를 삭제하지 않았다.

종료 시작 뒤 이미지 요청 거절 ERROR 2건(502, `error_type=shutdown`)이 있다.
다른 WARNING/ERROR/CRITICAL은 없었다. 이를 숨기거나 전체 로그 오류 0건으로 표현하지 않는다.

## P2 API 확인 범위

38회마다 `/api/data/history`의 처음 두 페이지(limit=3)를 조회해 76개 응답을 회수했다.
같은 history instance, 페이지 내·간 sequence 순서와 중복 없음, next_cursor 연결,
latest/history identity와 reset/truncated/has_more 형태를 대조했다.
live latest sequence는 36→2633으로 증가했다.

실제 반환 표본은 각 조회의 sequence 1~6이다. 전체 이력 76페이지나 2,637행 전체의
API 복구를 검증한 것이 아니다. 현장 reset·retention 만료·재연결·시계 보정·숨김 탭 복귀는
유발하지 않았다. [P2 코드 결과](../../../HISTORY_API_RESULT_P2.md)의 production-path 합성시험 및
동일 패키지 격리 재시작/이전 cursor reset 시험과 현장 증거를 구분한다.

## 원본 복귀와 후속 화면

원본 실행·설정 SHA 보존, 후보 상태 역복사 없음, 복귀 후 3개 표본에서 CSV 파일과 행·poll 증가를
확인했다. 행 수 1112→1189→1266, poll 5→21→37이다. 원본 준비 완료까지 241.417초가 걸렸고,
첫 복귀 표본의 누적 stale 1,084행은 세 표본 동안 증가하지 않았다. 정확한 발생 구간·원인은 미확정이다.

시험·복귀 당시 작업정보가 실제 작업과 일치함을 사용자가 확인했다. 이후 사용자가 완료 콘솔을 닫았고,
17:12·17:13 KST 원격 화면에서 Running 및 EX/LS/SPOT/Comm OK와 측정값 갱신을 확인했다.
후속 화면의 작업정보는 시험 당시 값과 달라 별도 시점으로 기록했으며 수정하지 않았다.
실제 제품·금형 식별값은 로컬 원문에만 보존한다.

콘솔 종료 이후의 근거는 사용자 종료 확인과 두 번의 화면 관찰이다. 새 process/API/CSV 영수증은
만들지 않았으며, 시험 종료부터 후속 확인까지 전 구간 무중단 운전을 주장하지 않는다.

## 실행·검토 근거

로컬 증거 루트는 `Desktop/SmartFactory/P2_T10_R1_evidence`다. 서버의 이번 격리 실행 결과를
승인된 `Z:/SmartFactory/20260922/return/P2_T10_R1_RESULT`로 회수했다.
서버 receipt JSON 261개와 SHA sidecar, 콘솔의 result pin, 공유/개발 사본을 대조했다.

| 검증 | 명령·결과 | 원문 |
| --- | --- | --- |
| CSV/fact validator | 정확한 d254871 checkout의 `scripts/validate_csv_v2_shadow.py`, exit 0/PASS | `field-validator-command.json`, `field-validator.log` |
| 증거 대조 | Python 3.12.6 `review_field.py`, 최종 45 pass/0 fail, exit 0 | `field-review.json`, `field-review-attempt-*.json/.log` |
| 콘솔 종료 후 | 사용자 확인 + 원격 화면 2회 | `console-close-observation.json` |
| 원문 목록·해시 | 공유 사본과 SHA256 일치 | `server-result-inventory.json`, `field-evidence-manifest.json` |

실제 전체 argv·cwd·환경·종료코드는 로컬 command JSON에 보존했다. 초기 감사 실패도 보존한다.
이번 검토는 **자체 검토**이며 공개 저장소만으로 비공개 현장 원문을 재현할 수는 없다.
전체 운영 이력·이미지 바이너리 백업은 하지 않았다. 과거 hash-bound 원문도 바꾸지 않았다.

## 범위와 운영 전환 조건

이번 후보로 Count0~2·부분 PLC 실패·worker timeout·벽시계 보정·7시간·자정 시험을 추가하지 않았다.
posthoc phase/changeover/linkage 산출물은 없어 validator의 unknown/not_applicable을 검증 완료로
바꾸지 않았다. 이미지 fact의 manifest를 검증했으며 이미지 바이너리별 해시는 검증하지 않았다.
SPOT fingerprint_mismatch, operator/comparator verified=False, async_fact_only는 그대로 유지했다.

서버 전환 위험도는 **높음**이다. 이번 시험에서 확인한 복귀는 분리 후보 종료 후 남아 있는 원본 실행이다.
NSIS 설치가 원본을 대체한 뒤 재설치/downgrade하는 경로는 아직 검증하지 않았다.
현재 계획에는 운영 데이터 migration이 없으며 새 설치 전에는 실제 출력 경로·append·metadata·profile
호환성을 확인해야 한다. 종료/drain 실패 때 중복 실행이나 강제 종료로 우회하지 않는다.

2026-09-22 읽기 확인에서 PR #194와 원격 master는 d254871이고 v1.0.26 태그는 없었다.
GitHub `production-signing` 환경은 있지만 secret·variable은 비어 있으며 required reviewer 규칙도
없다. 실제 installer·Electron·backend는 `NotSigned`이며 기존 패키지 해시와 일치했다.
이는 현재 서명 workflow 준비가 안 된 근거이며 다른 장소의 인증서 소유 여부를 단정하지 않는다.

다음 실행 경로는 [서명 정책](windows_authenticode_signing.md)에 따른 정식 서명 배포 준비 또는
대상·기간을 정한 미서명 내부 설치 검증으로 구분한다. 사용자가 선택한 기존 범위는 미서명 내부 검증이며
정식 운영 승격은 별도 결정이었다. 이번 문서 작성이 그 승인을 대신하지 않는다.
