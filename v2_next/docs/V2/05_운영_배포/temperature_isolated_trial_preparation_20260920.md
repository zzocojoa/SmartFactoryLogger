# Temperature 격리 시험 준비

2026-09-20 사용자의 다음 단계 진행 지시에 따라 준비 전용 도우미를 작성했다.
기존 d7a1b20 수집을 유지한다. 전체 이력 백업을 다시 선행 조건으로 두지 않는다.
실제 후보 실행과 기존 앱 종료는 이 준비 도우미에 포함하지 않는다.

## 작은 설정·상태만 준비

- 원본 `config.ini`와 선택 파일 `state.json`, `operator_metadata.json`,
  `operator_metadata_runtime_state.json`, `layout.json`만 읽는다. 파일당 1MiB, 합계 최대 5MiB다.
- 각 파일을 짧은 `ReadWrite | Delete` 공유 읽기로 두 번 읽어 일치하는 사본만 보존한다.
  파일 간 원자적 백업은 아니며, 실제 전환 직전 정상 종료 후 작은 상태의 최종 갱신이 필요하다.
- 누적 CSV, 이미지, fact, spool, index와 Electron profile을 열거·복사하지 않는다.
  pending/cache/backup config와 이전 export 경로 상태도 후보 활성 상태에 가져오지 않는다.
- 새 `Desktop\SmartFactory\T<6자리>`에 backup/prepared/receipt를 만든다.
  관리자/SYSTEM 쓰기, 운영 사용자 읽기를 보장하며 부모 ACL을 바꾸지 않는다.
  backup/prepared에는 비밀값이 포함될 수 있으므로 회수 대상은 receipt뿐이다.

## 후보 경로와 실행 경계

이미 전달한 후보 `72a410331ddf612e0de1a1fa2b0834432a7d7fab`의 전체 1,812파일,
562,772,956바이트를 기존 전달 inventory에 결합해 읽기 검증한다.
inventory SHA256은 기존 전달 영수증의
`0EE265AF2ED8B5C9417C27C5EAF48204FF43E1232B08550F05DCC017AB1D4AAC`로 고정한다.

복사 설정에서 변경하는 값은 logpath/snapshotpath/imagecapturepath 3개뿐이다.
장비 주소, 주기, attestation, comparator, async_fact_only는 그대로 둔다.
후속 일반 사용자 실행기는 APPDATA/LOCALAPPDATA/USERPROFILE/TEMP/TMP,
SFL_CONFIG_PATH, shutdown 진단과 Electron user-data-dir도 새 경로에 묶어야 한다.
중앙 동기화/.env/이전 환경 override를 상속하지 않고, 검토된 후보 logger opt-in과
schema 2.5.1을 실제 런타임에서 확인해야 한다. 준비 사본만으로 후보 시험 통과를 주장하지 않는다.

일반 사용자 실행기와 cold 상태 최종 갱신은 아직 후속 단계다.
기존 앱과 후보를 동시에 실행하지 않으며, 후보 정상 종료가 불확실하면 기존 앱을 중복 시작하지 않는다.
복귀는 기존 설치본·원래 설정·원래 데이터 경로를 사용하고 후보 상태를 원본에 덮어쓰지 않는다.

## 도우미와 검증

- 최종 묶음 이름: `SFL_TRC_PREP_R2`
- 실행 진입점: `PREPARE_TRIAL.cmd` — 사용자가 관리자 권한으로 실행한다.
- helper SHA256: `40F5F90F90439CA6424E9D6AC3BD32D5A9A207B35F726B8253D2E91EB7556B69`
- CMD SHA256: `8FC442A7139D149B5F03912C75898A1ECFFF6E2DE300804FA03425DB5A93664B`
- 개발 근거: `C:\Users\user\Desktop\SmartFactory\SFL_TRC_PREP_R2_evidence`

native PowerShell 5.1 경계 시험 34개 통과. 정상/변조/누락 CMD 시험 3개 통과.
Python ConfigParser로 정확히 경로 3개만 달라졌음을 비교하고, 깨끗한 후보 checkout의 실제 config 모듈을
합성 설정으로 import해 5개 실제 경로와 attestation/comparator/async_fact_only 보존을 확인했다.
제품 앱/장비는 시험 중 실행하지 않았다. 최초 global Python 시험은 dotenv 미설치로 실패했고
프로젝트 venv의 새 결과 폴더에서 통과했다. 실패 결과는 R1 개발 근거에 보존했다.
후보 파일 검증 함수를 기존 서버 왕복 사본에 적용해 1,812파일 검산도 통과했다.
해당 함수는 R1/R2가 동일하다. tree SHA256은
`0F239251F0D9D422C7A5586696C470C92AA67A83FFA44296EE2803473652191E`다.

제품 코드 변경과 migration은 없다. 새 경로 생성/권한·실제 서버 준비 실행은 전달 후 확인한다.
실패 시 HOLD를 남기고 원본과 부분 결과를 보존한다. 운영 앱 종료·자동 복구는 수행하지 않는다.
기존 전체 제품 QA는 코드가 동일해 반복하지 않았다.

## 전달과 현재 상태

서버 최종 경로는 `C:\Users\user\Desktop\SmartFactory\SFL_TRC_PREP_R2`다.
후속 공유 폴더 정리 지시에 따라 현재 전송 위치는
`Z:\SmartFactory\20260920\send\SFL_TRC_PREP_R2`, 검산 회수 위치는
`Z:\SmartFactory\20260920\return\SFL_TRC_PREP_RETURN_R2`다.
기존 영수증의 당시 Z 경로 문자열은 보존하며 `records\path-map.json`으로 현재 위치를 찾는다.
서버 로컬 실행 경로와 이미 전달된 파일 내용은 그대로다.
개발→Z 전송 5파일/392,460바이트 해시 일치를 확인했다.
최종 서버 복사와 왕복 검산 상태는 개발 근거의 `server-delivery-receipt.json`에 기록한다.
21:34경 최종 로컬 폴더→Z 회수 검산을 완료했다. 5파일/392,460바이트 모두 원본과 일치한다.
읽기 전용 독립 검토에서도 추가 차단 결함이 없었다. 준비 실행은 아직 사용자에게 인계할 단계다.
전달 중 첫 탐색기 선택에서 이전 `SFL_TRC_BACKUP_RETURN_R4` 도우미 사본 폴더가
서버 SmartFactory 아래 추가 복사됐다. 실행하지 않았고 원본도 바꾸지 않았다.
현재 준비 대상은 `SFL_TRC_PREP_R2`만이며, 그 이전 도우미 사본은 삭제하지 않고 별도로 보존했다.
이 문서만으로 서버 실행 완료를 의미하지 않는다. 결과는
`PREPARED_LIVE_SNAPSHOT_REVIEW_REQUIRED` 또는 HOLD로 수집하며,
`trial_launcher_ready=false`, `field_validation_passed=false`, `production_release_approved=false`를 유지한다.

## 서버 준비 실행과 결과 확인 완료

사용자가 PREPARE_TRIAL.cmd 실행을 완료했다. 21:44~21:45 서버 화면에서
`PREPARE EXIT 0`과 기존 앱의 Running / EX OK / LS OK / SPOT OK / Comm OK를 확인했다.
실제 결과는 21:39:25에 `C:\Users\user\Desktop\SmartFactory\T15596b`에 기록됐다.
운영 수집을 중단하거나 후보를 실행한 결과가 아니다.

`receipt`의 결과 JSON과 해시 파일만 서버 탐색기로
`Z:\SmartFactory\20260920\return\SFL_TRC_PREP_RESULT_R2`에 회수했다.
원본 설정이 들어 있는 backup/prepared는 서버에 보존했다.
콘솔 표시 SHA256, 회수 JSON의 실제 SHA256, 동봉 해시가 모두 일치한다.

- 결과: `PREPARED_LIVE_SNAPSHOT_REVIEW_REQUIRED`
- 결과 SHA256: `C04A78DFA0EFB01A5046BC75AB401A42B9045ABDB43963EB6E5E42DD75E9BE08`
- 후보 1,812파일 / 562,772,956바이트 / 기존 candidate tree SHA256 일치
- 작은 설정·상태 5파일 / 총 7,717바이트만 복사
- 원본 config SHA256 유지, 사본의 저장 경로 3개만 변경
- 기존 d7a1b20 프로세스 유지, 후보/설치 파일 실행 없음
- fingerprint_mismatch / operator_verified=false / comparator_verified=false 보존

개발 PC의 `Desktop\SmartFactory\SFL_TRC_PREP_R2_evidence\server-preparation-20260920-2139`에
회수 원문과 12개 계약 검사 결과 `receipt-review.json`을 보존했다.
이 단계의 서버 준비와 회수 검증은 완료다. 준비 도우미를 재실행할 필요는 없다.

다음 작업은 일반 사용자 격리 실행기와 정상 종료·복귀 절차의 구현 및 검증이다.
그 작업이 완료될 때까지 기존 앱을 유지한다. 실행 직전 후보 파일을 재검증하고,
기존 앱 정상 종료 후 작은 상태만 최종 갱신해야 한다. 준비 사본은 운영 중 읽기이므로
최종 정지 상태를 대신하지 않는다. `trial_launcher_ready=false`,
`field_validation_passed=false`, `production_release_approved=false`는 계속 유지한다.

이후 일반 사용자 짧은 시험 실행기 R4의 구현·개발 검증을 완료했다.
후속 상태와 실행 경계는 [짧은 격리 시험 실행기](temperature_short_trial_launcher_20260920.md)에 기록한다.
이 준비 영수증의 원문이나 당시 `trial_launcher_ready=false` 값을 수정하지 않는다.
