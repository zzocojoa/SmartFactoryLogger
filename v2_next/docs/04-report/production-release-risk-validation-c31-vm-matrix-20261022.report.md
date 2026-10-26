# 1.0.31 오프라인 VM 설치·복귀 검증

2026-10-22. 목표 상태 `active`, 출시 `HOLD`, 운영 승격 불가.

## 범위와 현재 상태

레이아웃 로딩 보완 clean commit `a7e5149b718f56d7dfa75df73bfba4a21d16a758`의
미서명 1.0.31 설치본을 기존 시험 VM에서 검증한다. 소스·패키지 검증은
[앞선 후보 보고서](production-release-risk-validation-layout-candidate-20261022.report.md)에 있으며,
이 문서는 실제 설치·복귀와 Electron 창·정상 종료 검증을 별도로 기록한다.

1.0.31의 오프라인 설치·업그레이드·재시작·두 이전본 복귀·데이터 보존·정상 종료 검증을
마쳤다. 대용량 기록의 실행 중 초기화 완료를 놓친 R4는 종료 1로 보존하고, 같은 데이터의
추가 관찰 R5에서 해당 항목을 확인했다. 최종 결합 판정은 `VERIFIED_WITH_DECLARED_LIMITATIONS`다.
541d 복귀 기준의 종료 중 이미지 502와 실제 현장 QA 공백 때문에 전체 출시 HOLD를 유지한다.
운영 서버에는 접속하거나 변경하지 않았다. 새 전체 백업을 만들지 않았고 기존 시험 자료를 재사용했다.

## 입력 결합

- 호스트 기록: `C:/Users/user/Desktop/SmartFactory/C31VM_20261022_a7e5149b_R2`.
- 게스트 실행: `C:/Users/SFLQA/Desktop/SmartFactory/C31VM_20261022_a7e5149b`.
- VM `SFL-QA-20261021-83be8a5a`, ID `b7ee8fcd-dd3d-46b5-901a-f465f9e06f6b`.
- 게스트 `DESKTOP-GK5R521`, SFLQA 로그인 세션 2, 외부 NIC 0개, 일반 권한 작업.
- manifest 930파일, 2,999,147,642바이트; SHA256
  `5f89b21421f1bbc7f1af9760eb132c1f01fa5b3e0dda853a911f37388ab9a55a`.
- 새로 전달한 설치본·목록·pins 6파일은 `records/action-002/transfer-verification.json`,
  전체 재사용 입력 검산은 `records/action-003/prepare-result.json`에 기록했다.

| 역할 | 버전 / build | 설치본 SHA256 |
|---|---|---|
| 새 후보 | 1.0.31 / a7e5149b | a10a59aa544a7bfa60e40778f05b89e3cc5be6da8ca284f94f740b6e6ae4a1dc |
| 직전 후보 | 1.0.30 / 240a4952 | 56ec126261970efbcee26fa22789d57c313dc8d27e5a71bb6b9296c3cab891b4 |
| 등록된 복귀 기준 | 1.0.26 / 541d701d | 08c061ee35a1a01788f05b00ee7395aa40774150c92c06726a92f3df1bf75c3c |

## 실행 경로와 준비 검증

첫 연결 도구의 변수 표기 오류로 세션이 종료됐다. 해당 실패 원본은
`C31VM_20261022_a7e5149b/records/result.json`에 보존했다. R2에서 수정 후
경계 검사 11개와 정상·인증 취소·게스트 읽기 실패·작업 실패 후 연결 유지·시간 제한
흐름 5개가 모두 종료 코드 0이었다. 사용자가 다시 인증한 연결을 재사용하며
암호는 저장하지 않는다.

- matrix 계약 검사 6개, Electron 제어기 경계 검사 2개, PowerShell 구문 검사 통과.
- 실행 작업은 해시 결합된 입력을 잠그고 기존 Python·Node·Playwright·2.35GB fact를 재사용한다.
- 실제 설치 EXE의 창을 Playwright Electron API로 관찰하고 `BrowserWindow.close()`로
  정상 종료한다. 제품 코드나 종료 로직을 바꾸지 않는다.
- 소유한 프로세스 job의 정리 결과와 실제 main/backend 종료 코드를 기록한다.
  강제 정리가 개입한 실행은 정상 종료 합격으로 처리하지 않는다.
- 호스트 검토기로 원격 회수 결과의 파일별 해시, 설치 파일 목록, CSV/fact/이미지 연결,
  세대별 저장 완료, renderer 종료 순서를 독립적으로 대조했다. 아래의 보류 항목을 유지한다.

## 남은 검토

### 첫 실행의 시험 도구 오류와 재개

`records/action-004`의 실제 작업·entry·worker 종료 코드는 1이다. 1.0.31 새 설치와
1.0.30 재설치까지 각 설치 프로세스 종료 0, 설치 파일 1,867개·등록 정보 대조가
완료됐으나, 첫 1.0.30 화면 시험의 PID 검사에서 중단됐다. matrix의 중간
`RUNNING` 문자열은 이 최종 실패를 대체하지 않는다.

원인은 Playwright의 Windows 경로가 `shell=true`로 실행한 `cmd.exe`를
`app.process()`로 반환한다는 점을 제어기가 놓친 것이다. 실제 읽은 재사용 driver
`lib/coreBundle.js`의 Electron launch 구현에서 이를 확인했다. 이는 제품 종료 오류나
새 설치본의 화면 실패로 판정하지 않는다. 첫 실행은 정상 종료 증거가 없고 소유 job의
8개 잔여 프로세스를 강제 정리했으며 정리 후 0개를 확인했다. 37개 결과 파일을
해시로 회수했고 실패·강제 정리 기록을 보존한다.

R2는 Electron main context에서 실제 PID·EXE를 확인하고, 부모 실행기와 구분한다.
그 PID의 native process handle을 보유해 종료 코드를 직접 읽는다. 실제 자식의 종료
코드 0·7, 잘못된 생성 시각/EXE 거부, 실행기 0이 본체 7을 숨기지 않음, 제어기 소멸을
성공으로 처리하지 않음을 검사한 4개 테스트와 재개 계약 검사 6개가 종료 0이었다.

실패한 VM 실행에서 만들어진 AppData 4파일과 Electron 프로파일 53파일은
크기·해시 재확인 후 기존 실행 폴더의 `preserved-failed-state`로 보존 이동했다.
복사 백업·삭제는 하지 않았다. R2는 새 `C31VMR2_20261022_a7e5149b` 폴더를 사용하고,
이미 통과한 새 설치·제거를 반복하지 않고 240a 설치 상태를 대조한 뒤 화면 시험부터
재개한다. 950개 입력 검산·보존 이동은 `records/action-006/prepare-result.json`,
실행은 `records/action-007`에 기록한다. 최초 실패 결과를 PASS로 재작성하지 않는다.

R2 실행은 기존 폴더에 있는 `original-files.json`을 새 입력 폴더에서 찾은 참조 오류로
모듈 import 단계에서 종료 1이었다. 제품 앱은 시작되지 않았고 job 잔여 0개,
강제 정리 없음, 결과 6파일 회수를 확인했다. R3는 기존 3개 설치 파일 목록을
검산된 첫 입력 폴더에서 읽도록 수정했다. 새 계약 검사 6개, 실제 VM의 matrix import와
Electron API import가 모두 종료 0이었다. `records/action-008/prepare-result.json`의
입력 950파일 SHA256은 `9c087bb8c7e86081e30c3e05b34fcb1f68d7e0a398ff8bedcb2334aa5c525958`다.
R3 폴더는 `C31VMR3_20261022_a7e5149b`, 실행·회수 기록은 `records/action-009`다.

R3의 240a 실제 Electron 실행은 15개 표본, main/backend 종료 0, 잔여 프로세스 0을
기록했다. 이어진 1.0.31 업그레이드도 설치 종료 0, 1,867개 파일 대조, data/config/profile
바이트 보존을 통과했다. 그러나 새 후보의 DOM이 렌더링된 직후 아직 숨겨진 창을
제어기가 즉시 실패 처리했다. 이때 실제 Electron 종료 1이 기록됐으나 제어기 오류 후
발생했으므로 제품 자발 종료로 단정하지 않는다. 실제 로그는 실행 약 557ms 시점의
renderer 초기 렌더까지 기록됐고, 정상 종료 시험은 성립하지 않았다.

R3 결과 158파일은 해시 회수됐고 job 강제 정리 없이 잔여 0개다. 이후 cold data 73파일은
I2 정상 종료 당시와 모두 같았다(`records/action-010/cold-state.json`). R4는 기존 제품
표시 동작을 바꾸지 않고 180초 준비 시간 안에서 실제 visible/non-minimized 상태를
기다리며 관찰값을 남긴다. 숨김→표시, 계속 최소화, 이미 종료된 프로세스의 3조건 검사와
입력 계약 6개가 통과했다. 실제 게스트 import·950파일·cold data/config/profile 대조도
종료 0이다. R4는 검증된 1.0.31 설치와 I2의 닫힌 데이터를 재사용해 I4 화면 실행부터
이어간다. 준비 `records/action-011`, 실행·회수 `records/action-012`, 새 폴더
`C31VMR4_20261022_a7e5149b`다.

### R4 종료와 독립 검산

`records/action-012` 결과 1,453파일을 회수·해시 대조했다. 작업·entry·worker 종료는
1이고, 강제 정리 없이 job 잔여 0이다. I4·I5·I6·I8·I10의 실제 main/backend는 모두
정상 창 닫기 후 종료 0이었다. 설치 단계는 각 종료 0이며 후보/240a는 1,867파일,
541d는 1,771파일을 대조했다. 업그레이드·복귀의 닫힌 data/config/profile은 바이트가
보존됐다. 별도 `action-013`에서 앱·시험 프로세스, 관련 리스너·임시 작업·외부 주소가
모두 없고 설치된 후보 commit 및 EXE 해시가 일치함을 확인했다.

독립 검산 `matrix-review-r4/review.json`의 208항목 중 14개 보류를 원본 그대로 보존한다.
그중 이미지 검사 5건은 격리 APPDATA 때문에 Pillow를 찾지 못한 검산 환경 오류였다.
기존 Pillow 12.2.0 경로를 명시한 별도 `matrix-review-supplement/review.json`에서
같은 소스 검산기를 다시 실행해 모두 종료 0이었다. 누적 이미지 66·132·199·266·332개의
파일 디코딩·fact 대조·고아 파일 검사를 통과했다. CSV 검산 5건도 각각 종료 0이다.

추가 검산 24항목은 종료 0이다. 시작 중의 renderer 요청 거부/중단은 원문에 남기고,
같은 main 세대의 operational-ready 이후 관찰 오류 0과 구분했다. 따라서 전체 실행의
요청 오류가 0이었다고 보고하지 않는다. 541d의 종료 중 이미지 502 기록도 보존하며
복귀 기준 자체의 알려진 제한으로 남긴다. 새 후보의 실행 오류로 소급하지 않는다.
I4 초기 화면, I5/I10 종료 전 캡처를 직접 확인했다. Running, 합성 온도 500°C,
시험 작업 99001·1, 파란색 시험 이미지와 조준점이 보인다. 실제 장비 영상 연속성의
증거가 아니다.

대용량 I10의 닫힌 기록에서는 4,586,586행·2,350,216,905바이트 이미지 fact가 입력
SHA256 `0470b637d5af91aa575cdc08865f039cdbd7f5be58623f49a84450b515aaecb4`와 같고,
이미지 기록 OFF·실패/누락/신규 쓰기 0이었다. `review_retained_scale_r4.py`는 종료 1,
보류 2항목으로 실행 중 초기화 완료와 최종 성공 receipt 부재를 정확히 유지했다.

R5(`records/action-015` 준비, `action-016` 실행)는 동일 설치본·기존 2.35GB 작업
데이터를 재사용한다. 새 설치·설정 변경·대용량 추가 복사 없이 최대 300초의 진단 관찰에서
읽기 완료를 기다린다. 이는 새로운 현장 성능 합격 기준이 아니다. 이전 실행의 CSV를
제외하고 이번 실행의 새 CSV가 초기화 중에도 실제 저장되는지 확인하도록 했다.
입력 계약 6개, 관찰 종료 조건 5개와 설치 호출 부재 검사, PowerShell 구문 검사,
실제 VM의 950파일 대조와 Python/Electron import가 통과했다.

### R5 최종 결과

R5 작업·launcher·entry·worker 종료는 모두 0이다. 130개 결과 파일을 정확한 목록·크기·
SHA256으로 회수했다. 표본 15개 중 새 CSV 저장과 초기화 진행을 함께 확인한 표본이 5개이며,
첫 표본으로부터 30.9165초 뒤 표본에서 이미지 fact 초기화 완료를 처음 관찰했다.
정확한 완료 순간이나 성능 보장값은 아니다. 파일 캐시를 통제하지 않았으므로 이전 실행과의
속도 차이를 원인 규명이나 성능 개선으로 해석하지 않는다.

`review_retained_scale_r5.py`: 39항목/실패 0, 실제 종료 0.
`review_final_evidence.py`: 회수·실행·정리·입력 결합 11항목/실패 0, 실제 종료 0.
이전 닫힌 CSV/metadata와 4,586,586행 이미지 fact 해시가 유지됐고, 이번 CSV/fact의
세대 연결·행 순서·정상 저장 완료·종료 잔량을 대조했다. 원본 이미지 전체의 의미 검사는 아니다.
이번 화면의 시작 요청 오류 3건은 보존했고, 로그의 정확한 operational-ready 시각 이후에는
요청 오류와 renderer 오류가 없었다. 종료 전 실제 캡처도 직접 확인했다.

`records/action-017/cold-closeout.json`에서 앱·backend·시험 프로세스·관련 리스너·임시 작업·
외부 주소가 모두 0임을 확인했다. 소유 job 정리 완료, 강제 종료 없음, 설치된 a7 후보의
앱·backend 해시 일치를 확인했다. VM은 오프라인으로 유지하며 시험 앱은 정상 종료 상태다.

최종 근거는
[결합 검산](C:/Users/user/Desktop/SmartFactory/C31VM_20261022_a7e5149b_R2/final-evidence-review.json),
[대용량 기록 검산](C:/Users/user/Desktop/SmartFactory/C31VM_20261022_a7e5149b_R2/retained-scale-review-r5.json),
[이미지·단계별 보완 검산](C:/Users/user/Desktop/SmartFactory/C31VM_20261022_a7e5149b_R2/matrix-review-supplement/review.json)이다.

이번 시험은 실제 장비·실제 3대 PC 네트워크·현장 15/120분을 대신하지 않는다.
기존 240a 현장120 결과를 새 설치본의 결과로 바꾸지 않는다. 다음 단계는 이 정확한 설치본의
변경 영향에 맞는 현장 준비·검증과 남은 출시 조건을 결합하는 것이다.

기존 541d 종료 오류, 물리 경계 미시험, 전체 과거 데이터 품질·과거 timeout/drop 원인,
현장 요구 수치·최종 승격과 롤백 기준 갱신은 이 준비 완료로 닫히지 않는다.
