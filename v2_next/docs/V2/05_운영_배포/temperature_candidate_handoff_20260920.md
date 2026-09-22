# Temperature 후보 준비와 서버 전달

> **후속 상태 (2026-09-21):** [브랜치 완료 상태](../../../TEMPERATURE_BRANCH_STATUS.md)를 참조한다.
> 아래 전달·백업·남은 준비는 9월 20일의 이력이며, 이후 짧은 시험과 7시간 관찰·원본 복귀를 완료했다.
> 전체 현장 검증과 운영 승격은 별도이며 기존 영수증·고정 증거는 보존한다.

2026-09-20 사용자 지시에 따라 모델명 확인과 분리해 원래 후보 릴리스 준비 상태를 다시 확인했다.
최종 준비 판정은 기존 `trc-260919-2304/scope-r2` 기록이다. 상위 폴더의 이전 판정을 사용하지 않는다.

## 재확인 결과

- 후보: `72a410331ddf612e0de1a1fa2b0834432a7d7fab`, 표시 버전 1.0.26.
- Git tree: `c84c2adcfdd20e3e0f22b68656602c99c260afc8`. 기존 빌드 checkout의 HEAD/tree/clean 상태를 재확인했다.
- 직전 설치/복귀 기준: `d7a1b20f96711fb07fc7add0867e79ee36506fce`, 표시 버전 1.0.26.
- 새 PowerShell 전체 health, 후보 실제 앱 격리 QA, 후보 내부 bytecode 34개 시험,
  d7a1b20 별도 데이터 경로 복귀·재시작 시험의 최종 통과 증거가 이미 있다.
- 검토 ZIP 339개 항목과 manifest가 선언한 338개 파일의 길이·SHA256을 다시 대조했다.
- 읽기 전용 검토자가 직전 NSIS 및 이전 unpacked 1,645개 파일을 재해시해 누락·불일치 0을 확인했다.
- 제품 소스 변경이 없어 유효한 전체 시험을 반복하지 않았다. 새 제품 빌드/commit은 없다.

따라서 준비 목표는 `field_trial_ready=true`다. `field_validation_passed=false`,
`production_release_approved=false`를 유지한다. SPOT 모델명과 comparator 확인을 준비 완료의
추가 선행 조건으로 만들지 않는다. 기존 미검증 상태와 안전 제한을 유지한다.

## 접근 가능한 보존 위치

개발 PC 전체 검토 자료:
`C:\Users\user\Desktop\SmartFactory\SFL_TRC_20260920_R1`

- `TEMPERATURE_REMEDIATION_REVIEW_BUNDLE.zip`: 기존 최종 ZIP의 동일 바이트 사본.
- `release`: 전체 검토 ZIP을 검증하며 추출한 339개 파일. 내부 상대 링크 유지.
- `accessible-copy-receipt.json`: 출처·새 경로·전체 파일 해시 및 현재 clean source 확인.
- `historical-receipts`: 원래 최종 감사/ZIP 영수증의 동일 바이트 사본.

과거 증거·원본 폴더·ACL은 변경하지 않았다. 보존 문서 안의 과거 절대경로는 출처이며 새 실행 위치가 아니다.
과거 실행 도우미는 실행하지 않는다. 새 작업·전달·결과는 바탕화면 정책을 적용한다.

## 서버 전달 묶음

개발 준비 위치:
`C:\Users\user\Desktop\SmartFactory\SFL_TRC_STAGE_20260920_R1`

동일 이름의 `Z:\SFL_TRC_STAGE_20260920_R1`은 전송용이다.
최종 서버 위치는 `C:\Users\user\Desktop\SmartFactory\SFL_TRC_STAGE_20260920_R1`이다.
Codex가 공유 폴더부터 서버 로컬 폴더까지 복사하고 후보 ZIP의 압축 해제와 사본 회수를 완료했다.

묶음은 후보 ZIP/NSIS, 이전 d7a1b20 NSIS, 원문 증거 발췌, 새 안내문, manifest와 SHA 목록이다.
설치·실행 도우미는 포함하지 않는다. `historical-evidence`는 발췌이므로 전체 링크·소스·로그는 개발 보존본을 참조한다.

서버의 `runtime\app`에 후보 전체 Electron 앱이 추출돼 있다. 새 추출 경로의 최대 길이는 199자다.
압축 해제 완료와 서버 절대경로를 탐색기에서 확인한 뒤, 서버 사본을
`Z:\SFL_TRC_RETURN_20260920_R1\SFL_TRC_STAGE_20260920_R1`로 다시 복사했다.
2026-09-20 16:38:25 +09:00 검산 완료: **1,829개 파일 / 1,121,958,257바이트 / 길이·해시 불일치 0**.
원래 전달 파일 16개와 추출 파일 1,813개를 모두 개발 원본/검증 ZIP 항목과 대조했다.
서버에서 해시 명령을 실행한 것이 아니라 탐색기 왕복 사본을 검산한 결과다.

개발 보존 폴더의 `expected-server-files.json`, `verify_server_return.py`,
`server-delivery-receipt.json`에 전체 기준과 재현 검증·영수증을 보관했다. 검증 종료코드는 0이다.
`stage-manifest.json`의 서버 복사 pending 값은 생성 당시 기록이며 최종 상태는 위 영수증으로 판단한다.
START_HERE의 후보 미실행 표현은 **이 서버에서의 미실행**을 뜻한다. 개발 격리 실행은 이미 완료했다.
읽기 전용 전달 문서 검토에서 중대한 불일치는 없었다. 제품 코드/설정/설치/프로세스 조작은 없었다.

| 산출물 | SHA256 |
| --- | --- |
| 후보 전체 앱 ZIP | `18526cfaada3eb308ce63b6bb25b07e76bc9e4381ecd9101cdcbd76ecebd808b` |
| 후보 NSIS | `a58057c4666bee689c579ec271d86db193de807e9530aaf1fa5e8b915727aa86` |
| 복귀 d7a1b20 NSIS | `1096276cc7c82e765a7bd1f03597cc09ff285ae587ac6b666cc86a04a3bfc25f` |
| 전체 검토 ZIP | `d76642d51c470265df9e997772e92822b9ed98319e67dc2e24191bbcca1b8a9e` |

## 실제 현장 단계의 범위

후속 사용자 승인과 정상 종료·전체 백업 도우미의 서버 전달 상태는
[현장 전환 백업 준비](temperature_field_cold_backup_20260920.md)에 기록했다.
진행 승인은 받았다. R3 실행은 경로 길이 검사에서 앱 종료 전에 HOLD했다.
R4는 정상 종료 후 전체 백업을 시작했지만, 짧은 격리 현장시험에 비해 범위가 과도하여 사용자와 중단했다.
2026-09-20 21:02 기존 설치 d7a1b20 앱을 탐색기에서 재시작했다. 21:07 회수 CSV 1,389행의
sample_seq 불연속 0과 마지막 30행 `success / fresh / valid`를 확인했다.
시작 직후 SPOT STALE 경고는 이후 SPOT OK/Comm OK로 회복됐다. 전체 백업과 복원 검산은 미완료다.
아래 항목을 새 승인 요청 목록으로 해석하지 않는다.

남은 준비는 필요한 설정/상태의 제한된 백업과 후보의 별도 profile/data/image/fact/spool 경로,
짧은 전환·복귀 절차 및 관측 한도다. 전체 누적 이력 백업을 다시 선행 조건으로 만들지 않는다.
모델명 답변은 이 준비 작업의 재개 조건이 아니다.
후보와 현재 앱이 같은 장비나 파일에 동시에 접근하지 않도록 전환한다.

2026-09-20 후속 진행으로 작성한 준비 전용 도우미와 소규모 복사 범위는
[격리 시험 준비](temperature_isolated_trial_preparation_20260920.md)에 기록한다.
운영 수집을 유지한 채 작은 설정/상태만 준비하며 실제 일반 사용자 후보 실행은 후속 단계다.

현장 전환 위험은 높다. NSIS 설치/업그레이드, 실제 백업 복원, 장기 이력 성능은 미검증이다.
준비 단계의 파일 복사에는 제품 migration과 관측 동작 변경이 없다. 롤백은 d7a1b20 번들과
그 빌드의 호환 설정/별도 데이터 경로를 사용하며 후보 2.5.1 파일을 구버전이 append하지 않는다.
저장/queue/spool 실패와 종료 timeout은 미완료 기록으로 보존하고 정상 종료로 바꾸지 않는다.
