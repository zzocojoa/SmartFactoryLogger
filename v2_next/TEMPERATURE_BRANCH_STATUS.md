# Temperature 브랜치 완료 상태

> **2026-09-23 서버 설치 검증 완료:** P2 병합본 `d254871`의 미서명 NSIS 설치와
> 실제 120분 관찰·정상 종료·원본 재설치·콘솔 종료 후 수집 지속 확인을 완료했다.
> 실행/회수 42항목과 원문 검사 16항목이 통과했다. 실제 작업정보 일치도 사용자가 확인했다.
> [120분 현장 결과](docs/V2/05_운영_배포/temperature_p2_nsis_120min_trial_20260923.md)를 참조한다.
> 현재 서버는 원본으로 복귀했으며 정식 운영 승격은 별도다. 아래 이전 상태는 당시 기록이다.

> **2026-09-22 격리 설치 검증 완료:** 같은 P2 병합본 `d254871`을 Windows Sandbox에서 실제 NSIS로
> 신규 설치·업그레이드·재시작·원본 재설치했다. 증거 대조 73/73과 후보 CSV 검증 2회가 통과했다.
> [설치 검증 결과](docs/V2/05_운영_배포/temperature_p2_nsis_installation_20260922.md)에 fact 형식 전환 시 보관본 보존과 한계를 기록한다.
> 실제 서버 설치와 정식 운영 승격은 미실행이다. 아래 기록은 각 작성 시점 기준으로 보존한다.


> **2026-09-22 P2 후속 완료:** history/API P2는 PR #194에서 `d254871`로 병합됐으며,
> 같은 병합본의 미서명 내부 패키지 준비와 **10분 시험·원본 복귀·콘솔 종료 후 수집 확인**을 완료했다.
> [P2 병합본 현장 결과](docs/V2/05_운영_배포/temperature_p2_ten_minute_trial_20260922.md)에
> CSV 2,637행·온도 fact 613건·P2 API 표본 76페이지와 최종 증거 대조 45/45를 기록한다.
> P2 코드가 보류 상태인 것은 아니다. 설치·업그레이드·정식 운영 승격은 아직 수행하지 않았다.
> 아래 L1 및 G1~G5 상태표는 각 기록 당시 기준으로 보존한다.

> **2026-09-22 후속 상태:** T1~T3·C1~C3·L1 코드 보완 이후 후보 `df4b731`의
> **10분 현장 시험과 최종 작업정보 확인을 완료했다.**
> [새 후보 10분 결과](docs/V2/05_운영_배포/temperature_l1_ten_minute_trial_20260922.md)에
> 2,558행 CSV·614건 fact 검산, 정상 종료·원본 복귀, 콘솔 종료 후 수집 지속과 한계를 기록한다.
> 전체 현장 검증·운영 승격은 계속 별도이며 history/API P2는 보류한다.
> 아래 2026-09-21 G1~G5 후보·7시간 기록은 당시 기준으로 보존한다.
> 이전 후보의 7시간 결과를 새 후보의 장시간 검증으로 해석하지 않는다.

기준일: 2026-09-21 (KST). 사용자의 브랜치 목적 재확인과 후속 기록 정리 승인에 따른 통합 상태표다.
기존 시험 결과와 보존 증거를 연결하며, 새로운 시험 실행·제품 변경·운영 배포 승인을 뜻하지 않는다.

## 현재 판정

**G1~G5 코드 개선과 현장 검증용 후보 준비는 완료했다. 추가 승인한 7시간 자연 관찰도 통과했다.**
전체 현장 검증과 정식 운영 승격은 완료하지 않았다. 자정 시험 등 후속 현장 항목 때문에
이미 통과한 코드·후보 준비 목표를 다시 미완료로 바꾸지 않는다.

| 구분 | 현재 상태 | 근거 |
| --- | --- | --- |
| 원래 코드 목표 | 완료 | G1~G5 수정, 원본 186,878행 검증, 회귀·통합·계약 시험 및 독립 diff 검토 |
| 추가 후보 준비 목표 | 완료, `field_trial_ready=true` | R1 소스·증거 대조, R2 commit·빌드 고정, R3 격리 QA 1~6, R4 현장·복귀 계획 |
| 추가 승인한 서버 시험 | 짧은 시험 및 7시간 관찰 통과 | 고정 후보 실행, CSV/fact 검산, 정상 종료와 기존 앱 복귀 |
| 전체 현장 검증 | 미완료, `field_validation_passed=false` | 자정·통신 장애 복구 등 미검증 범위는 아래에 구분 |
| 정식 운영 배포 | 미승인, `production_release_approved=false` | 후보 설치·업그레이드와 운영 승격을 수행하지 않음 |

7시간 검산 JSON의 `full_field_validation_passed=false`도 전체 현장 검증 미완료를 뜻한다.
짧은 시험이나 장시간 관찰의 통과를 전체 현장 합격으로 확대하지 않는다.

## 브랜치와 실행본 식별

| 대상 | 식별 |
| --- | --- |
| 브랜치 | `codex/temperature-remediation-20260909` |
| 제품 수정·후보 commit | `72a410331ddf612e0de1a1fa2b0834432a7d7fab` |
| 후보 build Git tree | `c84c2adcfdd20e3e0f22b68656602c99c260afc8` |
| 후보 표시 버전·실행 schema | v1.0.26 / 2.5.1 |
| 기존 설치본·복귀 기준 | v1.0.26 / `d7a1b20f96711fb07fc7add0867e79ee36506fce` / schema 2.5.0 |

두 실행본의 표시 버전은 같으므로 commit과 파일 해시로 구분한다. 후보는 동일 commit의
clean checkout에서 빌드했다. 현재 로컬 작업 트리에는 운영 도우미·문서와 기존 사용자 변경이
남아 있으며, 현재 작업 트리 전체가 clean이라고 주장하지 않는다. 이번 정리는 문서만 변경한다.

## 원래 목표와 완료 근거

| 목표 | 완료한 개선 | 해석 한계 |
| --- | --- | --- |
| G1 캐시 TTL | 행 시점의 finite age·clock·TTL 재검증, sentinel 이후 캐시 억제 | 7시간 현장에서 TTL fallback 사건은 관찰되지 않음 |
| G2 freshness | 입력 오류와 정상 default 구분, 일관된 행 평가 시각, unknown 우회 차단 | 원본에 없는 monotonic 시각을 실측으로 복원하지 않음 |
| G3 PLC source | 수집 당시 freshness를 공정 판정에 전달, stale/error의 phase·lifecycle 오판 방지 | 실제 PLC 장애 복구는 이번 자연 관찰에서 검증되지 않음 |
| G4 저장 분리 | bounded queue 256·단일 writer, 비차단 poll, 실패·drain·timeout·rollover 검증 | 과거 192.769초 시작 지연의 실제 원인은 미입증 |
| G5 poll 전수성 | 서비스별 관측 범위의 gap 합산, 중복 별도 집계, runtime/reload/offline 일치 | 9월 9일 원본 fact 부재는 새 시험 데이터로 해소되지 않음 |

[코드 결과](TEMPERATURE_REMEDIATION_RESULT.md), [진행 이력](TEMPERATURE_REMEDIATION_PROGRESS.md),
[회귀 매트릭스](TEMPERATURE_REMEDIATION_REGRESSION_MATRIX.json)에 요구사항과 시험 근거가 있다.
원본 CSV 186,878행과 후보 현장 CSV 117,742행은 서로 다른 데이터다.

코드 단계 backend 765개는 후보 commit의 tracked 시험 748개와 별도 ignored 보충 시험 17개로
구분한다. 후보 준비 기록은 frontend 291개·보조 9개·Electron 94개·PowerShell QA 5개를 포함한다.
새 Windows PowerShell 5.1 프로세스의 전체 `npm run health`는 2026-09-20 exit 0이며,
전역 실행정책 변경은 없었다. 이번 문서 정리에서 제품 시험을 재실행한 결과는 아니다.

## 후보 준비와 현장 시험

후보 준비는 실제 패키지 EXE의 격리 실행과 패키지 내부 production bytecode 통합 시험 34개를
구분해 판정했다. 합성 clock·저장 장애·rollover 시험을 실장비 사건으로 표시하지 않았다.
의도한 저장 장애의 backend exit 2·미완료 closeout·도우미 FAIL은 원문대로 보존했다.
이를 정상 종료 통과로 바꾸지 않고 실패가 드러나는 동작의 근거로 사용했다.

[후보 준비·전달 기록](docs/V2/05_운영_배포/temperature_candidate_handoff_20260920.md),
[짧은 시험 기록](docs/V2/05_운영_배포/temperature_short_trial_launcher_20260920.md),
[7시간 시험 결과](docs/V2/05_운영_배포/temperature_seven_hour_trial_20260921.md)를 순서대로 연결한다.

| 7시간 시험 항목 | 최종 결과 |
| --- | --- |
| 관찰 구간 | 2026-09-21 01:23:23~08:23:24 KST, 1,552개 진단 표본 |
| CSV | 117,742행, sample_seq 연속·중복 없음 |
| observation fact | 25,212행, 관측 범위 gap·중복 0 |
| CSV→fact 연결 | key 있는 117,737행 전부 연결, startup 5행은 key 없음 |
| Count 0/1/2 | 각각 8,866/2,986/2,347행, production_stable/stabilizing 오분류 0 |
| 값과 저장 | non-valid Temperature 누출 0, 표본 reject/write/spool 실패 0, 정상 drain |
| 최종 검산 | 고정 후보 validator exit 0, 추가 검산 58/58 통과 |
| 원본 복귀 | d7a1b20 기존 앱·설정 유지, 후보 state 미이관, 복귀 후 3표본에서 수집·저장 증가 |
| 실제 작업 정보 | 사용자가 확인한 현재 작업과 복귀 화면이 일치하여 수정 없음. 실제 식별값은 로컬 증거에 보존 |

under_range 8,535행, stale 9행, startup_pending 5행의 존재는 자체로 실패가 아니다.
상태에 맞는 값 차단과 데이터 무결성을 검사했다. 표본 queue/pending 최대 1은 연속 최대치가 아니다.
원본 복귀 확인은 해당 시험 종료 시점의 증거이며 상시 상태 감시를 뜻하지 않는다.

## 남은 범위와 실행 조건

| 항목 | 현재 위치와 다음 판단 |
| --- | --- |
| 실제 자정 파일 전환 | 사용자가 7시간 관찰과 별도로 남긴 현장 시험. 미실행이며 코드·후보 준비 완료의 추가 조건이 아님 |
| PLC/온도 통신 장애·TTL·clock 사건 | 코드·격리 시험 근거는 있음. 실제 현장 사건은 미검증으로 유지하고 자연 사건 또는 별도 허용 범위에서 검증 |
| 장기 누적 이력 성능 | 합성 2,000행 cold start 및 새 격리 경로의 7시간 관찰이 전체 운영 이력 규모를 대신하지 않음 |
| 추가 관찰 공백 | 이번 복귀 콘솔 종료 후 생존, phase 후처리 fact, 이미지 본문은 7시간 판정 범위 밖 |
| 과거 지연 원인·원본 fact | 자료·원인 입증 과제. 후보 기능 완료 조건과 분리하며 추정으로 통과 처리하지 않음 |
| 설치·업그레이드 | unpacked 실행과 복귀를 검증했으며 NSIS 설치·업그레이드·실제 백업 복원은 미검증 |
| 전체 현장 합격 | 후속 현장 범위와 미검증 항목의 처리 근거를 정리한 뒤 별도로 판정. 7시간 통과만으로 true 변경 금지 |
| 정식 운영 승격 | 정확한 배포 commit·산출물, 해당 배포 방식의 검증·복구 조건 및 사용자 승인을 별도로 확정 |

자정 시험을 자동으로 즉시 실행하는 다음 단계로 안내한 것은 2026-09-21 목적 재확인에서 정정했다.
후속 현장 항목은 남겨 두되, 기록 정리 승인을 새 서버 시험이나 운영 승격 승인으로 확장하지 않는다.
SPOT 모델명 확인이나 전체 누적 이력 백업을 코드·후보 준비의 추가 선행 조건으로 만들지 않는다.
operator/comparator 미검증 상태와 기존 안전 제한은 그대로 유지한다.

## 운영 위험과 복귀 기준

이번 문서 변경의 위험은 낮다. 제품 코드·설정·관측 동작·데이터 migration 변화는 없다.
후속 운영 전환의 위험은 높으며 다음 기존 계약을 유지한다.

- 복귀는 후보를 정상 종료한 뒤 기존 d7a1b20 앱과 그 설정·데이터 경로로 돌아가는 방식이다.
  후보 schema 2.5.1 파일을 구버전이 append하는 downgrade나 상태 이관의 성공을 뜻하지 않는다.
- queue 포화·쓰기/spool 실패·종료 timeout은 계수와 미완료 closeout으로 남긴다.
  유한 queue에서 무한 저장 장애의 무손실을 보장하지 않는다. 관측·알림 동작은 이번에 바꾸지 않는다.
- 후보 NSIS는 미서명이다. 실제 배포 방식은 기존
  [서명 정책](docs/V2/05_운영_배포/windows_authenticode_signing.md)을 적용한다.
  내부 검증 예외가 정식 운영 승격을 뜻하지 않는다.
- 새 서버 작업은 [경로·전달 정책](docs/V2/05_운영_배포/server_validation_path_policy.md)을 따른다.
  서버 최종 로컬 복사까지 Codex가 맡으며, 기존 원문·해시 결합 증거는 보존한다.

## 고정 증거 찾아보기

아래 절대경로 링크는 이 개발 PC의 보존 사본이다. Git 저장소 복제만으로 포함되지 않으며
원본 private CSV·운영 raw 로그를 문서 정리를 이유로 Git에 추가하지 않는다.

- [후보 준비 판정서](C:/Users/user/Desktop/SmartFactory/SFL_TRC_20260920_R1/release/RELEASE_CANDIDATE_READINESS.md)
- [후보 manifest](C:/Users/user/Desktop/SmartFactory/SFL_TRC_20260920_R1/release/release_candidate_manifest.json)
- [새 PowerShell health 결과](C:/Users/user/Desktop/SmartFactory/SFL_TRC_20260920_R1/release/evidence/fresh-powershell-health.json)
- [격리 QA 독립 검토](C:/Users/user/Desktop/SmartFactory/SFL_TRC_20260920_R1/release/INDEPENDENT_SCOPE_REVIEW.md)
- [현장 계획](C:/Users/user/Desktop/SmartFactory/SFL_TRC_20260920_R1/release/FIELD_VALIDATION_PLAN.md)
- [복귀 계획](C:/Users/user/Desktop/SmartFactory/SFL_TRC_20260920_R1/release/ROLLBACK_PLAN.md)
- [7시간 최종 검산](C:/Users/user/Desktop/SmartFactory/SFL_TRC_7H_R3_evidence/server-run-U76fbb38e/review-summary.json)
- [작업 정보 확인](C:/Users/user/Desktop/SmartFactory/SFL_TRC_7H_R3_evidence/server-run-U76fbb38e/operator-context-confirmation.json)

| 고정 자료 | SHA256 |
| --- | --- |
| 후보 앱 ZIP | `18526cfaada3eb308ce63b6bb25b07e76bc9e4381ecd9101cdcbd76ecebd808b` |
| 후보 NSIS | `a58057c4666bee689c579ec271d86db193de807e9530aaf1fa5e8b915727aa86` |
| 기존 d7a1b20 NSIS | `1096276cc7c82e765a7bd1f03597cc09ff285ae587ac6b666cc86a04a3bfc25f` |
| 후보 준비 검토 ZIP | `d76642d51c470265df9e997772e92822b9ed98319e67dc2e24191bbcca1b8a9e` |
| 7시간 review-summary.json | `35BA4966E7E29944F4B3746584B71E20B802D3A7B8DED7455E1656E57430A1E3` |

위 해시는 기존 증거의 식별값이다. 이번 정리에서는 최종 검산·작업 확인 JSON의 sidecar 해시와
상태 값을 재확인했으며 대용량 번들·CSV 전체 검산이나 서버 접속을 다시 수행하지 않았다.
보존 ZIP/manifest/영수증은 수정하지 않는다. 과거 보고서의 HEAD `09e81777`·미커밋·현장 미실행은
해당 코드 검증 당시 상태이며 현재 상태는 이 문서의 범위별 판정으로 읽는다.

## 이번 기록 정리의 종료 기준

현재 상태표와 기존 보고서 연결, 근거 값·링크·diff 확인으로 이번 문서 작업을 마친다.
2026-09-21 문서 검사에서 상태표 링크 16개와 기존 문서의 역방향 링크 4개가 모두 유효했고,
안내문을 제외한 기존 4개 문서의 본문 동일성을 확인했다. 후보 commit·완료 상태·58/58 검산 값과
최종 검산 SHA256이 보존 증거와 일치하며 `git diff --check`를 통과했다.
제품 소스 변경이 없어 health 전체 재실행과 재빌드를 추가하지 않는다.
이 기록 정리 시점에는 문서와 운영 도우미가 미커밋 상태였으며, 후속 Git 정리는 아래에 구분한다.
후속 현장 시험 또는 배포 작업을 정할 때 이 표의 미검증 범위와 해당 승인 범위를 기준으로 삼는다.

## PR 범위와 기준 정리

2026-09-21 사용자가 관련 변경의 commit·push·PR 생성을 승인했다. 기준 브랜치는 `master`다.
기존 운영 도구 6개 commit은 PR #192에서 `c6b7954`로 squash 병합되었다.
`09e81777`과 `c6b7954`의 전체 Git tree가 동일함을 확인한 뒤 `master`를 현 브랜치에 병합했다.
기준 정리 commit `aef40a3`의 전체 tree도 검증 후보 `72a4103`과 동일하다.
기존 후보 commit을 재작성하지 않았으며 PR의 비교 차이는 제품 개선 26개 파일로 정리되었다.

후속 문서 commit에는 이 상태표·코드 결과/진행 안내·Temperature 현장 보고서 5개와
사용자가 지정한 서버 경로/전달 정책을 포함한다. 이 문서 commit은 제품 코드·시험 소스를 변경하지 않는다.
로컬 전용 실행 도우미, 기타 운영 조사 문서, 기존 사용자 assets 및 private 원본은 포함하지 않는다.
보고서의 도우미 시험 수는 로컬 보존 증거이며 이번 PR에 그 실행 도우미가 포함됐다는 뜻이 아니다.

공개 저장소에 불필요한 실제 제품·금형 식별값은 게시 문서에서 생략하고 원문은 로컬에 보존했다.
로컬 증거 링크는 GitHub에서 재현 가능한 첨부물이 아니므로, 검토자는 저장소 내 합성 시험과
기록된 현장 요약을 구분해야 한다. Git 작업 승인은 merge·서버 설치·운영 승격을 포함하지 않는다.

## PR 검토 후 QA 호환성 보완

PR #193의 `f0b3b86`에서 GitHub CI 2개는 통과했으나, 자동 리뷰가 기존 서버 QA·attestation의
`2.5.0` 고정 판정을 발견했다. 실제 PowerShell 실행으로 후보 schema `2.5.1` 거부를 재현했다.
`apply_spot_temperature_v25_attestation.ps1`과 `qa_spot_temperature_v25.ps1`에
`2.5.0/2.5.1` 명시적 허용을 적용하고, QA runtime과 종료 sidecar의 버전 일치를 요구한다.
미지원·결측 버전은 계속 거부하며 hardening·comparator·drift·fingerprint 제한은 유지한다.

보완 후 PowerShell 진입점 회귀 8개와 정상 종료·현재 session 파일 선택·validator/rollover·replay
관련 회귀 6개가 통과했다. Ruff·diff 검사 및 읽기 전용 독립 검토도 통과했다.
새 QA 회귀는 실제 스크립트와 합성 health/파일을 사용하고, validator 없는 묶음의 최종 FAIL을
명시적으로 요구한다. 개별 schema 검사 통과를 전체 CSV 검증 성공으로 보고하지 않는다.
기존 고정 후보 앱·현장 증거와 운영 설정은 변경하지 않았고 서버 시험·attestation도 실행하지 않았다.
변경된 QA 스크립트의 실장비 실행과 새 QA 묶음 전달은 이번 PR 보완의 검증 범위가 아니다.
후속 commit의 CI는 이전 통과 기록과 구분하여 PR Checks에서 확인한다.
