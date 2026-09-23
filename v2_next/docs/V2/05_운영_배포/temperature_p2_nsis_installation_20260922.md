# Temperature P2 내부 설치 검증

> **후속 결과 — 2026-09-23:** [실제 120분 서버 설치 검증과 원본 복귀](temperature_p2_nsis_120min_trial_20260923.md)가 완료됐다.
> 아래 내용은 단계별 작성 시점의 기록이며, 정식 운영 승격과 구분한다.

2026-09-22. P2 병합본의 **미서명 내부 NSIS 설치·업그레이드·재시작·원본 재설치 시험을
격리 Windows Sandbox에서 완료했다.** 최종 증거 대조 73 pass / 0 fail이며,
후보 CSV에 대한 exact-build production validator 2회도 종료 0이다.
이 수치는 제품 단위시험 수가 아니라 이번 실제 설치 실행의 증거 대조 수다.

`isolated_nsis_validation_passed=true`, `server_installation_performed=false`,
`production_release_approved=false`를 구분한다. 서버 설치 직전 점검과 실제 설치 승인은 별도다.

## 대상과 환경

| 항목 | 검증 대상 |
| --- | --- |
| 후보 | `d254871f89c98154b4e32879e29601df78f7e159`, CSV schema 2.5.2 / fact 1.4.0 |
| 원본 | `d7a1b20f96711fb07fc7add0867e79ee36506fce`, CSV schema 2.5.0 / fact 1.3.0 |
| 표시 버전 | 둘 다 1.0.26; commit·파일 해시로 판정 |
| 후보 NSIS SHA256 | `7264F6CD4B6C494092AB3B88995E4E963EE501F9BE2D2BE23ACE2B3CCF565FC6` |
| 원본 NSIS SHA256 | `1096276CC7C82E765A7BD1F03597CC09FF285AE587AC6B666CC86A04A3BFC25F` |
| 실행 환경 | 개발 PC Windows 11 Pro의 별도 Sandbox Windows 11 Enterprise, Python 3.12.6 |
| 격리 | 네트워크·클립보드·오디오·비디오·프린터 공유 끔; 입력 폴더 읽기 전용, 새 결과 폴더만 쓰기 공유 |
| 통신 | 모의 MELSEC/LS/SPOT transport와 loopback만 사용; 시작·종료 시 비-loopback IPv4 없음 |
| 설치 위치 | Sandbox 사용자의 실제 기본 설치 위치와 등록 정보; `/D` 임시 경로 우회 없음 |
| 저장·프로필 | Sandbox의 실제 APPDATA·Electron profile을 upgrade/reinstall 동안 재사용; 생산 데이터 반입 없음 |

사용자 승인으로 개발 PC의 Sandbox 기능 하나를 Disabled→Enabled로 변경했다. 사용자가 재부팅했고
새 부팅 시각과 guest 부팅을 확인했다. 호스트 자동 재부팅·서버 OS 변경은 없었다.

## 실제 설치 실행

| 단계 | 결과 |
| --- | --- |
| 후보 신규 설치 | NSIS 종료 0, payload 1,812파일 일치, 등록 1개·실제 설치 위치·바로가기 일치, 자동 앱 실행 없음 |
| 후보 제거 | 실제 uninstaller 종료 0, 설치 등록·앱 파일 제거 확인, 앱을 실행하지 않아 AppData/profile 없는 초기 상태 확보 |
| 원본 신규 설치 | NSIS 종료 0, payload 1,645파일 일치; 원본 실제 앱으로 수집·저장·정상 종료 |
| 원본→후보 upgrade | NSIS 종료 0, 후보 1,812파일 일치, 닫힌 AppData·profile·data 전후 해시 동일 |
| 후보 최초 실행·재시작 | 실제 Electron/backend/driver/service/repository, 2세대 수집·저장·종료 확인 |
| 후보→원본 재설치 | 계획된 복귀 단계에서 NSIS 종료 0, 원본 1,645파일 일치, AppData·profile·data 해시 동일 |
| 복귀 원본 실행 | 기존 시험 데이터·수동 작업정보를 유지한 채 다시 수집·저장·정상 종료 |

각 설치 전에 앱·백엔드·8000 포트가 비었는지 확인했다. 등록 위치는 NSIS의 `Software/APP_GUID`
키와 uninstall 키를 각각 조회했다. 실제 설치 후에 payload 전체와 embedded commit을 재검증했다.
계획된 복귀는 정상 종료 이후에만 수행했고, 실패에 반응하는 자동 롤백은 사용하지 않았다.

## 수집과 저장 검산

| 실행 | 관찰 시간 | V2 행 | valid | startup blank | 신규 온도 fact |
| --- | ---: | ---: | ---: | ---: | ---: |
| 원본 | 75.60초 | 356 | 341 | 15 | 24 |
| 후보 upgrade 후 | 74.13초 | 344 | 329 | 15 | 24 |
| 후보 재시작 | 73.43초 | 291 | 281 | 10 | 24 |
| 원본 재설치 후 | 74.19초 | 355 | 340 | 15 | 24 |
| 합계 | 별도 4세대 | 1,346 | 1,291 | 55 | 96 |

각 파일의 sample_seq 연속성, 실제 commit/schema, 정상 온도 500°C와 모의 Count/Speed/Press,
비정상 상태의 Temperature blank, final persisted sequence와 finalized closeout을 대조했다.
4개 SPOT service의 각 poll 1~24와 observation key 유일성·wide 연결을 확인했다.
후보 API는 상태 표본 30회에서 2페이지씩 총 60페이지와 재시작 시 이전 cursor reset을 확인했다.
관찰한 MELSEC/LS/SPOT snapshot이 계속 전진했고 해당 backend PID의 WARN/ERROR 로그는 없었다.

### 버전 전환 시 fact 보관

원본 fact 1.3.0은 54열, 후보 1.4.0은 55열이며 `spot_poll_duration_status`가 추가된다.
양쪽 production writer는 헤더 불일치 시 현재 fact 파일을 `*.schema-mismatch.csv`로 보관한 뒤
새 현재 파일을 만든다. 이번 실제 upgrade와 원본 재설치에서 이 동작을 확인했다.

- 원본→후보: 원본 24건 파일의 전체 SHA256이 보관본과 일치.
- 후보 재시작: 같은 schema의 기존 24건을 바이트 prefix 그대로 유지하며 48건까지 append.
- 후보→원본: 후보 48건 파일의 전체 SHA256이 새 보관본과 일치. 앞선 원본 보관본도 불변.
- 최종 보관본 72건과 현재 파일 24건을 합쳐 96개 유일 key·4개 service가 보존됨.
- 이전 wide CSV와 metadata 파일은 원래 바이트 그대로 보존됨.

따라서 버전 전환 후 현재 `spot_observation_fact.csv` 하나만 세어 과거 fact가 사라졌다고 판단하면 안 된다.
현장 전환에서도 보관 파일과 전환 전후 식별·해시를 함께 기록해야 한다. 과거 metadata의 closeout
집계는 당시 범위를 뜻하며 이 시험에서 과거 metadata를 다시 쓰지 않았다.

## 종료와 검증 명령

앱 실행 4회 모두 Electron/backend 종료 코드 0/0, 강제 종료 없음, 잔존 프로세스와 8000 listener 없음.
후보 두 번은 9개 shutdown stage와 drain/closeout/trace 종료를 대조했다. 최종 독립 조회에서
앱·백엔드·Python fixture와 80/8000/18761/18762 listener가 없음을 확인한 뒤 시험 Sandbox를 해제했다.

- guest Python: `guest_install_qa_r3.py` → 종료 0. 실제 installer `/S /currentuser` 실행.
- host Python: `review_closed.py` → 최종 종료 0, 73 pass / 0 fail.
- exact-build venv: `scripts/validate_csv_v2_shadow.py --v2 ... --metadata ... --v1 ... --spot-observation-fact ...`
  → 후보 최초 실행·재시작 각각 종료 0. 실제 전체 명령과 원문은 증거 JSON/log에 보존.
- harness 구문 및 Ruff F821/F822/F823/E9 검사 통과. 기본 Python에 Ruff가 없어 기존 exact-build venv 사용.
- CSV validator는 선택적 위치 두 열이 비었다는 경고를 남겼다. 이번 설정은 위치 읽기·이미지 검증 범위가 아니며
  검사 삭제나 값을 채워 경고를 숨기지 않았다. 운영 promotion profile 통과를 주장하지 않는다.

기존 동일 commit의 source health·패키지 QA는 보존했고 이번에는 제품 코드·바이너리를 바꾸지 않아 재실행하지 않았다.
이번 검토는 **자체 검토**다.

## 도우미 보완과 실패 기록

초기 설치는 종료 0이었지만 QA가 InstallLocation을 uninstall 키에서 찾으려다 중단됐다.
실제 NSIS 소스와 guest registry를 대조해 올바른 별도 설치 키로 수정했다. 초기 실패·stderr·원문을 보존했다.
재시도 결과 폴더 생성 순서 오류도 앱/설치 실행 전에 중단됐으며 별도 기록을 남겼다.
최종 재개에서는 이미 설치된 후보를 전수 해시 재검증한 뒤 이어갔다. 제품 assertion을 삭제하지 않았다.

최초 후처리는 모든 버전에서 fact append만 가정해 66 pass / 2 fail이었다. production의 schema rollover와
보관 파일의 실제 해시를 확인하고, 동일 schema는 정확한 prefix, 다른 schema는 정확한 전체 보관본을 요구하도록
대조를 바로잡았다. 이전 결과와 스크립트를 보존했고 이미 통과한 두 CSV validator 실행은 재사용했다.
이는 설치·제품 실패를 통과로 바꾼 것이 아니라 잘못된 QA 가정을 실제 저장 계약에 맞춘 것이다.

## 근거와 다음 단계

로컬 원문 루트: `Desktop/SmartFactory/P2_NSIS_QA_R1`.
`closed-data-review.json`, `output/attempt-3`, `output/guest-final-read.json`, `sandbox-release-receipt.json`,
`MANIFEST.json`에 실행·수정 이력·보존 파일 해시를 기록한다. 공개 Git에는 합성 결과 요약만 남긴다.

서버는 이번 시험에 접근하지 않았다. 다음 단계는 설치 직전 서버의 현재 원본·설정·경로·작업정보에 대한
읽기 전용 사전점검과 현장 설치·정상 종료·복귀 도우미 준비다. 실제 설치의 목적·시험 시간·중단/복귀 조건을
확정한 뒤에만 현장 설치를 진행한다. 이번 짧은 모의 시험은 생산 데이터 규모·실장비·장시간·자정 검증을 대체하지 않는다.
형식 전환의 보관 동작, 종료 실패 시 HOLD, 원본 재설치 및 작은 상태 복구 필요 여부를 현장 계획에 반영한다.
전체 생산 이력·이미지 백업을 다시 선행조건으로 만들지 않는다.

이전 [10분 현장 시험](temperature_p2_ten_minute_trial_20260922.md)과
[코드 검증 결과](../../../HISTORY_API_RESULT_P2.md)는 각각의 원문을 보존한다.
Windows Sandbox 제어는 [Microsoft CLI 문서](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-cli)의
guest 실행·목록·해제 명령을 사용했다. 서버 설치·commit/push/PR/merge·정식 운영 승격은 수행하지 않았다.
