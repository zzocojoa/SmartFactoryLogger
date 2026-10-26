# C32 현장 적용·검증과 준비 이력

## 현재 상태: 2026-10-23

현장에는 **1.0.32 / cd46692ac9c551080c57d8168fa9ea5abd530206**이 설치됐다.
설치본 SHA256은 `558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f`다.
설치 전후 원본 보존, 정상 종료·일반 사용자 재시작, 15분·120분 수집 및 실행 식별 정보 대조를 완료했다.
120분 결과의 PASS 범위는 `COLLECTION_AND_BINDING_ONLY`이며 전체 출시 합격을 뜻하지 않는다.
종료한 세 실행의 이미지 9,074개는 해시·디코딩 검사를 마쳤고, 마감된 현재 CSV 37,944행의
상세 검사도 원래 실행 `78383`에서 종료 코드 0으로 완료됐다. 수신 기록 참조 37,926건의
누락은 0건이다. 운영 승격과 등록 롤백 기준 갱신은 하지 않았다.

전체 출시는 **HOLD**, `promotion_allowed=false`다. 서버의 일반 실행과 작업자 화면 복귀는
21:44 KST에 다시 확인했다. 최신 범위와 한계는 [목표 대조 보고서](production-release-risk-validation-goal-alignment-20261022.report.md)와
[실행 기록](C:/Users/user/Desktop/SmartFactory/C32START_20261023_cd46692a/completed-stage.json)을 따른다.

## 2026-10-23 실제 서버 정상 시작 3회 완료

동일 설치본·동일 승인 설정·일반 사용자 조건에서 정상 종료 후 시작을 세 번 측정했다.
실행 요청 직전부터 대시보드 준비 이벤트까지 **14.542 / 14.569 / 16.102초**, 앱 내부는
14.412 / 14.426 / 15.962초였다. 별도 Stopwatch의 관측 완료 상한도16.132 / 15.831 / 17.904초다.
각 PID·시작 세션의 필수 시작 단계9개, backend 단계9개와 raf 준비 이벤트를 확인했고
기존 계획의 시작30초 조건을 세 번 모두 충족했다. OS 캐시 제거·cold boot·모든 화면 프레임·
물리 온도 샘플 완전성이나 전체 성능 계약의 PASS로 확대하지 않는다.

각 시작 전에 정상 UI 종료, 관련 프로세스5개 종료코드0, CSV21,989 / 398 / 426행의 순번과
마감, 이미지 worker4,739 / 84 / 79건 저장·잔량/실패/거부0을 검산했다. 마지막 종료 대상의
stale30행은 모두 종료 요청 이후이고 온도 필드는 빈칸이다. 이미지 종료 단계10.6824초 동안
수집 중단과 시점이 겹친 기록이며 유효 온도나 이미지 유실로 바꾸지 않는다. 세부 대기 원인은 미확정이다.

설치 payload1,867개와 고정된 제거 프로그램1개, 동일 설정 SHA7d75bc47…을 세 번 대조했다.
실행·회수·내용 검산은 모두 종료0, 독립 검산 종료0(473e67), 공유 보존·상태표 갱신 종료0(9b659d)다.
선택 증거126파일/35,845,639바이트를 공유 return에 해시 검산 보존했다. 운영 전체 백업은 아니다.
로컬 검산기의 payload 개수·영수증 XML 인코딩 처리 오류를 수정했으며 서버 시험은 재실행하지 않았다.

최종 main13632는 실행 중이고21:44 화면의 Running·온도·영상·작업 정보60409/2를 확인해
창을 최대화했다. 작업자의20:16:23 입력을 유지했다. 새 설치·설정 변경·120분 반복·승격은 없다.
[결과와 제한](C:/Users/user/Desktop/SmartFactory/C32START_20261023_cd46692a/actual-startups-review.md),
[원시 결과 독립 대조](C:/Users/user/Desktop/SmartFactory/C32START_20261023_cd46692a/actual-startups-verification.json).


## 2026-10-23 21:22 KST 실제 서버 시작 시간 계측 준비

[계측 준비·검증 기록](C:/Users/user/Desktop/SmartFactory/C32START_20261023_cd46692a/review.md)을 추가했다.
기존 일반 사용자 EXE 직접 실행을 유지하고, 예약 작업 실행 요청 직전 UTC와 독립 Stopwatch를
기록한다. C32의 파싱·판정 함수 12개를 재사용하며 기본 측정 도구의 taskkill 경로는 포함하지 않는다.
로컬 24개 검사 exit0(44c398), 새 서버 폴더 STIME32_20261023_cd46692a의 4파일/26,686바이트
전달·해시 검산 exit0(4b1ca0)이다. 이는 새로운 서버 시작 시험 결과가 아니며 실제 3회 계측은 남아 있다.
21:17 SSH 읽기 확인은 같은 main7036/backend20832와 승인 설정 해시를 확인했다. 21:21 화면은
Running·카메라·60409/2(20:16:23 적용)·전면 표시다. 사용자 생산 중 아님 답변은 이전 질문에 대한
시점 기록으로 보존하며 이후 작업자 입력을 지우거나 덮어쓰지 않았다. 이번에는 앱 종료·재시작·
설정 변경·전체 백업을 하지 않았다. 최신 상태는 [준비 단계 기록](C:/Users/user/Desktop/SmartFactory/C32START_20261023_cd46692a/prepared-stage.json)이다.

## 최초 준비 시점: 보존 이력

아래의 C31 실행 중·C32 설치 전 문구는 최초 준비 시점의 상태다. 후속 실제 결과는 위 현재 상태와
이 문서 뒤쪽의 날짜별 검증 기록으로 구분한다.

작성일: 2026-10-23. 범위는 같은 C32 설치본의 현장 도우미 검증·전달과 현재 C31의 정상 종료 관찰 준비다.
현재 서버에 C32를 설치한 결과가 아니며, 전체 출시 판정은 `HOLD`, `promotion_allowed=false`다.

## 버전과 실제 변경 범위

| 구분 | 식별값 |
|---|---|
| 새 후보 | 1.0.32 / `cd46692ac9c551080c57d8168fa9ea5abd530206` |
| 동일 설치본 | 164,158,258 bytes / SHA256 `558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f` |
| 이번 도우미 | clean commit `bb6fbc807ecea4182efe90b369f1b110436b14eb` |
| 서버 현재 실행본 | 1.0.31 / `a7e5149b718f56d7dfa75df73bfba4a21d16a758` |
| 등록 복귀 기준 | 기존 1.0.26 / `541d701d544eea6a8a4e4836047077eaf9cfaf30`, 이번 단계에서 갱신하지 않음 |

도우미는 C32의 정확한 설치본·payload·제거 파일·build를 식별하도록 확장했다. 현재 C31 종료 요청은
기존 v7 형식을 유지하고, C32 실행용 v8과 구분한다. 보존 검산과 설치 도우미에는 C31→C32의
정확한 변경 조건을 추가했다. 도우미 commit은 제품 build commit과 다르다.

기존 미서명 내부 운영 결정과 백업 필요성 기준을 적용했다. 새 전체 백업은 만들지 않았다.
현재 단계의 서버 변경은 검산된 새 작업 폴더의 파일 전달뿐이며, 앱 종료·설치·운영 설정 변경·삭제는 없다.
이전 실패·원본 자료와 C31 현장 검증 기록은 보존한다.

## 로컬 도우미 검증

| 실제 검사 | 결과 |
|---|---|
| Python 도우미 회귀 | 167 tests, exit 0 |
| 설정 확인 스크립트 | 기존 13 tests, exit 0; C32 대상 7개 하위 조건 추가 검사 통과 |
| 설치·정상 종료·원본 관찰 | 각각 151·20·38 checks, exit 0 |
| 종료 후 fact 캡처 | 수정된 R2 15 checks, exit 0 |
| health 실행 진입점 | 9 cases, 검사기 exit 0; 권한 전제조건 거부는 예상 exit 1 |
| 실행 파일 빌드 | PyInstaller exit 0, 고정 소스 116파일·의존성 전후 일치 |
| 패키지 직접 실행 | 6회 native 호출; 정상 합성 실행과 잘못된 입력·build·pin 거부를 확인 |

첫 캡처 검사는 `runtime-library-pin`으로 실패했다. 작업본의 CRLF 해시와 Git에서 내보낸 LF 바이트의
해시를 혼동한 원인이었다. 실제 묶음의 LF 해시로 결합을 수정하고 영향받은 캡처 검사만 다시 실행했다.
최초 실패와 입력은 보존했다. 최종 `checks-final-review.json`은 해당 수정 전후 소스 차이와 실제 결과를 연결한다.

직접 실행 검사는 소유 자식 프로세스 정리와 입력·패키지 불변을 확인했다. 이 검사로 운영 ACL 적용이나
실제 서버 설치가 통과했다고 표현하지 않는다. 앞선 [격리 VM 설치·복구 결과](production-release-risk-validation-c32-vm-matrix-20261023.report.md)의 제한도 유지한다.

## 서버 전달과 사전 검사

- 개발 준비: `C:/Users/user/Desktop/SmartFactory/F32PREP_20261023_cd46692a`
- 공유 전달: `Z:/SmartFactory/20261023/send/FIELD32_cd46692a`
- 서버 최종 묶음: `C:/Users/user/Desktop/SmartFactory/FIELD32_20261023_cd46692a`
- 26파일 / 206,618,292 bytes의 정확한 목록·크기·SHA256을 공유 사본과 서버에서 대조했다.
- 기존 승인 SSH 호스트·계정·접속 주소 제한을 유지했고, 기존 경로를 덮어쓰지 않았다.
- 서버의 라이브러리 로드와 frozen `--describe`는 exit 0, 종료 후 도우미 잔류 0이다.
  이때 운영 원본 데이터 접근이나 실제 관찰은 시작하지 않았다.

서버 1.0.31의 main 6168 / backend 11128과 logger `77f1d84c-0286-4dbc-a7cf-3b49482fc555`가
같은 실행으로 계속 동작함을 확인했다. 이후 종료 요청 준비에서는 현재 CSV의 첫 완전한 행을 읽어
실제 시작 sample sequence와 결합했다. 파일 전체 검산은 정상 종료 뒤에 수행하는 단계다.

## 정상 종료 관찰 준비

- 새 입력 폴더: `C:/Users/user/Desktop/SmartFactory/F32CLOSE_20261023_cd46692a`
- 입력 4파일 / 12,740 bytes, 서버 목록·크기·해시 일치.
- 실제 서버의 `preservation`, `runtime-close` 두 `-ValidateOnly` 실행 모두 exit 0.
- 요청 SHA256: `7a2f2c418796a3b688a0f5055e5485e741a87e091c72f3e6ca144429ae85f364`.
- 현재 CSV: `Factory_Integrated_Log_v2_20261023_010622.csv`, 첫 sample sequence 1.
- 설정 SHA256: `e9792bfa97ee5dd3f60a7a24a796d443a50bf3c3965c7b940ad719a01b847e12`.
- 두 실행 명령을 준비하고 native PowerShell 구문 검사를 통과했다. 실제 관찰기는 아직 시작하지 않았다.

기존 SSH 연결 단절 시험에서 자신의 진단 프로세스만 정리하고 잠금을 해제한 보호 실행 경로를 재사용한다.
원래 코드에 대한 변경은 현재 경로·버전·요청 식별값이며 역치환 일치 검사를 기록했다.
시작 직전 현재 logger·CSV·설정과 서버 상태가 다르면 중단한다. 오래된 요청을 임의로 재사용하지 않는다.

서버 작업 정보는 12:47 KST 이후 자동 초기화된 공란이었고, 사용자가 **“생산 중 아님”**이라고 답했다.
이전 제품·금형을 다시 입력하지 않는다. 이 응답은 관찰 준비 시점의 생산 상태이며 미래 상태를 보장하지 않는다.

다음 순서는 운영자의 창 닫기 가능 시점 확인 → 원본 관찰기 시작·준비 확인 → 종료 관찰기 시작·준비 확인
→ X로 정상 종료 → 실제 종료 코드·CSV·이미지·원본 검산 → 조건 충족 시 동일 C32 설치 요청 구성이다.
실제 종료 대기는 450초이므로 두 관찰기가 준비된 뒤에만 X 클릭을 안내한다. 강제 종료는 사용하지 않는다.

원격 화면 도구는 Chrome 현재 주소 확인 오류로 중단됐다. 따라서 서버 파일 경로와 해시 검증은 완료했으나
이번 단계의 탐색기 화면·Smart Factory 전면 표시를 직접 확인하지 못했다. X 클릭 시점만 사용자와 맞추며
명령 실행·검산은 SSH로 진행한다. 현재 앱은 실행 상태를 유지한다.

## 미완료와 증거

C32의 실제 서버 설치·재시작·변경 영향에 맞춘 현장 관찰은 미완료다. 이번 준비와 VM 결과만으로
C31의 120분 결과를 C32에 이전하거나 운영 승격하지 않는다. 물리 Low Signal 경계, 과거 손상 자료와
timeout/drop 원인에 관한 기존 미확정 항목도 유지한다.

주요 증거는 준비 폴더의 `checks-final-review.json`, `commit-verification.json`, `portable/summary.json`,
`field-transfer-plan.json`, `ssh-verify-bundle.json`, `server-library-preflight.json`, `post-delivery-read.json`과
종료 입력 폴더의 `runtime-and-csv-read.json`, `readiness.json`, `execution-preparation.json`이다.

## 2026-10-23 14시 종료 관찰 시간 초과와 재준비

위의 ‘관찰 미시작·앱 실행 중’은 최초 준비 시점의 상태다. 이후 두 관찰기를 실제 시작했으나,
450초의 창 닫기 대기를 넘겨 각각 `normal-exit-timeout-no-force`, exit 1로 끝났다.
두 관찰기 종료 결과의 외부 SHA256을 대조하고 실패 영수증 26파일을 회수했다.
보호 실행기는 자신의 자식 프로세스를 정리했으며 제품 강제 종료는 하지 않았다.

사용자의 ‘종료됨’ 응답 후 실제 앱·백엔드와 8000 포트 리스너가 없음을 확인했다.
CSV metadata는 14:00:03 KST에 `finalized=true`, `closeout_reason=shutdown`, 마지막 저장 sequence
199,442를 기록했다. Electron 로그에는 같은 backend 11128이 14:00:09에 exit 0,
`forced=false`로 끝난 기록이 있다. 이는 기록에 따른 저장·백엔드 종료 확인이며,
관찰기가 보존해야 할 전체 프로세스의 native 종료 코드나 CSV 전수 내용 검산을 대신하지 않는다.
따라서 이 관찰을 PASS로 처리하거나 이를 근거로 1.0.32를 설치하지 않았다.

실패 증거: `F32CLOSE_20261023_cd46692a/timeout-review/review.json`.
최초 두 보호 실행 결과 SHA256은 각각
`e58da9408522423f04610c84638286598f6af695fe0eb92875eaf00249f74b70`,
`2eae818ecb50ce5fdce85b5e1c6bad3996098f1683909173800e66eace511f31`이다.

기존 검증된 C31 시작 도우미를 바이트 변경 없이 재사용했고, 실행 전 cold 상태·현재 설정·
종료 metadata 해시를 추가 확인했다. 14:09:51 KST에 main 1948로 일반 사용자 세션에서 시작했고,
시작 exit 0·결과 5파일 해시·일회성 작업 정의 제거를 확인했다. 새 실제 runtime은 1.0.31,
REAL/Running, logger `0b9fa18a-7432-49ca-823b-51cce309bf0d`,
CSV `Factory_Integrated_Log_v2_20261023_140954.csv`이며 설정 해시는 불변이다.
재설치·설정 변경·전체 백업은 없었다. 화면 전면 표시는 아직 직접 확인하지 못했다.

새 실행 폴더 `F32CLOSE_20261023_cd46692a_R2`에 현재 세대의 요청 4파일 12,746 bytes를
전달·검산했고 두 `-ValidateOnly`와 native PowerShell 구문 검사가 모두 exit 0이다.
새 preservation 관찰기 `G5f22f515b215`를 시작했다. 최초 시간 초과 기록을 보존하고,
새 두 관찰기가 실제 준비된 뒤 X 클릭을 다시 안내한다. 설치·운영 승격은 여전히 미완료다.

이전 종료 CSV는 별도로 읽기 회수 전후 원본 해시를 대조하고 199,442행 전부의 열 구성·
동일 logger·sequence 1~199,442의 연속성과 종료 metadata 마지막 번호를 확인했다(exit 0).
SHA256은 `78f2b970cf87230ca7aaeac5bc3cefb90f89a1c3e2e8014f8d5df2a5f8f74374`이다.
startup_pending 10 / valid 149,462 / under_range 49,877 / stale 93행이며 stale 93행은 지우거나
정상 온도로 바꾸지 않았다. 이 검사는 이미지·fact 전체 대응이나 놓친 native 종료 증거를
대신하지 않는다. 근거는 `F32CLOSE_20261023_cd46692a/previous-csv-review/review.json`이다.
최초 로컬 검사기의 경로 이스케이프 구문 오류(exit 1, 서버 미접속)를 수정한 뒤 실제 검사를 마쳤다.

14:19:43 KST의 실제 조회에서 새 두 관찰기의 동일 PID/생성 시각·READY·오류 없음·미종료를 확인했다.
preservation: `G5f22f515b215` → `Od937d489`, runtime-close: `G5e9be019a977` → `R7e713212276c`.
preservation READY는 14:19:09.790959 KST이며 450초 대기 종료는 14:26:39.790959다.
사용자에게는 **14:24 이후 안내를 보면 닫지 않고 ‘시간 지남’을 회신**하도록 더 이른 X 클릭 제한을
명시했다. 두 관찰기는 종료 대기 중이며, 이를 정상 종료·원본 검산 완료로 기록하지 않는다.

14:27:23 KST에 두 관찰기 모두 실제 terminal exit 1과 controller 소멸을 확인했다.
원인은 동일한 `normal-exit-timeout-no-force`이며 제품은 종료되지 않았다.
소유 Job의 남은 프로세스는 각각 0이고 제품 강제 종료는 없었다. 실제 terminal 결과 2개의
콘솔 SHA256과 회수 원문·stdout/stderr·hold 기록을 대조했다(exit 0).
`F32CLOSE_20261023_cd46692a_R2/timeout-review/review.json`에 기록했다.
작은 원시 영수증은 `Z:/SmartFactory/20261023/return/F32CLOSE_R2_TIMEOUT_cd46692a`에도 보존했다.

14:28:42 KST의 서버 health는 동일 C31/REAL/Running·동일 logger, 새 CSV 4,665행이다.
관찰기만 종료됐으며 앱·설치본·설정은 변경하지 않았다. 새 전체 백업도 없다.
원격 Chrome 창 목록 조회는 성공했지만 상태 캡처는 현재 브라우저 URL 확인 오류로 다시 중단됐다.
UI 입력·전면 확인은 수행하지 못했다. 이전 X 안내는 만료됐고 자동 관찰 재실행은 하지 않는다.

현재 단계는 새 정상 종료를 실행할 운영자 조작 가능 시점 또는 허용된 원격 화면 조작 복구를 기다린다.
두 결과 대조/설치 요청 준비 도구는 현재 실행과 C32 설치본으로 식별값만 바꿔 역치환 일치·구문·
기본 실행 시 서버 미변경을 확인했다. 실제 close/preservation 결과가 없으므로 해당 대조와 설치는 미실행이다.
전체 목표는 active/HOLD, 실행 중인 관찰기는 0개다. 1.0.32 적용 완료로 보고하지 않는다.

## 2026-10-23 원격 화면 복구와 R3 정상 종료

기존 승인된 Chrome 원격 데스크톱 탭을 브라우저 도구로 직접 연결해 현재 URL과 실제 화면을 확인했다.
Smart Factory 창의 시스템 메뉴 열기·닫기로 입력 반영도 확인했다. 이전 native 화면 경로의 URL 오류와
구분하며, 이후 창 닫기를 사용자에게 다시 요청하지 않았다. 화면의 작업 정보는 60365·7이었고 변경하지 않았다.

R3 로컬 기록은 `F32CLOSE_20261023_cd46692a_R3`에 남긴다. 서버 R2 입력 4파일을 해시로 다시 검증하고
두 사전 검사 exit 0을 확인해 재사용했다. 재전송·전체 백업·설정 변경은 없다.
새 preservation `Ge4484dc151ee` → `O8674483e`, runtime-close `Gf0cd5a97bfbe` → `R5007daf5caaf`의
동일 프로세스 세대·READY·오류 없음·미종료를 14:46:28 KST에 확인했다.
관찰 준비 후 실제 서버 창의 정상 닫기 단축키 Alt+F4를 전달했다. 14:47:16 KST에 앱 프로세스가
없음을 확인했고, 화면에서도 창이 사라졌음을 직접 확인했다. 강제 종료는 수행하지 않았다.

종료 관찰기는 실제 exit 0, 보호 실행기 PASS, 남은 자식 0이었다. 콘솔의 결과 SHA256
`42d04be633e2e89cd1b4fe316fbea855dbe869583ae6aa3a5b4999146dafd96d`와 회수 파일을 대조하고
`review_health_runtime_close.py`로 내용 검산을 완료했다(exit 0).
현재 C31 logger `0b9fa18a-7432-49ca-823b-51cce309bf0d`의 CSV 9,384행은 sequence 1~9,384로
누락·중복 없이 종료 metadata의 마지막 저장 번호와 일치한다. 관련 native 프로세스 5개 모두 exit 0이다.
startup_pending 25 / valid 9,358 / stale 1행을 그대로 보존한다.

이 검사는 해당 실행의 CSV·프로세스 종료 증거 범위다. 이미지 전체 대응이나 과거 데이터 QA를 대신하지 않는다.
전체 원본의 default/named stream·metadata 관찰과 재검산은 아직 실행 중이며, 앱은 종료 상태를 유지한다.
두 실제 결과를 결합해 검산한 뒤에만 승인된 C32 설치 요청을 생성한다. 기존 두 timeout 실패 기록은 보존한다.
근거: R3의 `normal-close-verified-stage.json`, `recovered-runtime-close-e74f8ea78a06/content-review.json`,
`normal-close-preservation-running-stage.json`. 현재 C32 설치·운영 승격은 미완료이며 release HOLD다.

완료된 종료 검증 기록 37파일 / 12,680,124 bytes를
`Z:/SmartFactory/20261023/return/F32CLOSE_R3_NORMAL_cd46692a`에 파일별 해시 대조해 보존했다.
이는 이번 실행의 검증 증거이며 전체 데이터 백업이 아니다. 기존 설치·이전본·롤백 입력 6개와
서버 cold 상태 재확인은 exit 0이다. C32 시작 도우미 식별값 결합과 26개 거부 경계 검사,
읽기 전용 runtime 요청의 합성 경계 13개·native PowerShell 구문·기본 미실행 검사도 exit 0이다.
첫 시작 도우미 로컬 검사는 native Utility module 자동 검색 문제로 exit 1이었다. 해당 오류를 보존하고
로컬 시험 wrapper에서 native module을 명시적으로 import해 통과했다. 서버 환경·제품 코드는 바꾸지 않았다.
준비된 시작/읽기 도구의 성공은 실제 C32 설치·실행 확인을 대신하지 않는다.

후속 검토에서 초기 C32 읽기/종료 어댑터 R2가 C31용 v7 요청 형식을 유지한 오류를 발견했다.
앞서 13/8개 합성 검사 통과는 내부 형상 검사였으며 실제 native consumer의 호환성을 증명하지 못했다.
서버 요청 생성·전달·실행 전에 R3의 요청을 C32용 v8로 수정했고, 수정된 13/8개 검사와 기본 미실행
검사를 모두 exit 0으로 다시 확인했다. `check_runtime_contract_r3.py`는 서버에 전달한 것과 동일한
SHA256 `08c7a2ea...`의 native consumer 함수를 사용해 9개 조건을 exit 0으로 검증했다.
잘못된 C32/v7 및 잘못된 build·sequence·config·logger·CSV는 거부하고 C32/v8과 기존 C31/v7은
각 올바른 버전으로 허용했다. 이전 준비·오류 기록은 보존한다. 현재 C31 원본 검산에는 영향이 없으며,
설치 후에는 `read_candidate_runtime_r3.py`, `prepare_candidate_observer_r3.py`를 사용한다.


## 2026-10-23 15:12 KST 원본 검산과 설치 후 확인 준비

동일 preservation PID 15912 / FILETIME 134372074481977911이 실행 중이다. 15:12:03 KST에
observe-original 366,491파일 / 11,518,692,192 bytes, 오류 출력 없음, 앱 프로세스 없음,
최종 결과 미생성을 확인했다. 실제 exec session 78096도 계속 실행 중이며 설치는 미실행이다.

기존 C31 설정 확인·회수·재시작 준비 도구 5개를 새 로컬 R3 폴더에 C32용으로 작성했다.
변경은 버전·commit·실행 경로·고정 해시와 C32 v8 요청 형식이다. 역치환 원문 일치와 Python 구문
5개, 기본 미실행 3개, 필수 인수 도움말 exit 0을 확인했다. 이후 재시작 준비도 생성했으며
기본 미실행 2개가 exit 0이다. 실제 시작 PowerShell은 26개 경계 검사를 마친 것과 동일 바이트다.

실제 C32 설치 결과와 새 버전의 정상 종료·metadata·설정 해시가 있어야 기존 USER_SELF 승인
네 확인 항목의 묶음을 만들고 적용할 수 있다. 현재 묶음 미생성, 서버 전달·설정 변경·앱 시작 없음.
준비 검사는 실제 현장 실행 통과를 뜻하지 않는다. 근거는 R3의 attestation-adapters-preparation.json,
after-attestation-start/adapter-preparation.json, attestation-prepared-preservation-running-stage.json이다.


## 2026-10-23 15:20 KST 현재 종료 실행의 worker·이미지 마감 대조

C31 backend 860 / logger 0b9fa18a-7432-49ca-823b-51cce309bf0d의 이미 발행된 종료 영수증
4개와 별도 이미지 final manifest를 읽기 전용으로 회수했다. 서버 source·설정·앱은 변경하지 않았다.
기존 제한된 읽기 도구에서 PID와 닫힌 관찰기의 경로·고정 해시만 치환했고 역치환과 native parse는
exit 0이었다. 실제 SSH 두 읽기도 exit 0이며, 회수 본문·sidecar·외부 해시를 대조했다.

review_closure.py 실제 exit 0: native 5개 정상 종료와 같은 생성 시각·CSV 종료 시각·worker의
begin/final 시각을 연결했다. 10개 필수 종료 단계가 완료됐고, worker 보고 이미지 등록 1,959건과
저장 1,959건이 일치한다. 대기·실패·drop 0, writer 정지·drain 완료도 별도 final manifest와 일치한다.
이 결과는 앱의 보고와 종료 증거를 결합한 범위이며 이미지 1,959개 실파일과 누적 ledger 전체 대조는
아직 NOT_EVALUATED다. CSV metadata의 원래 image-persistence-pending-at-open 표시는 보존했다.

근거: F32CLOSE_20261023_cd46692a_R3/closed-generation-evidence/review.json.
원시 증거·리뷰 26파일 / 54,054 bytes를 Z:/SmartFactory/20261023/return/F32CLOSE_R3_DRAIN_cd46692a에
전 파일 해시 대조해 보존했다. 전체 백업이 아니다. 이미지 final manifest SHA256은
d2c66c151964c8d7f7c41ac18e37e0c90dbc726900a534885fc438ef1e2262aa다.

15:20:13 KST 현재 같은 preservation controller 15912/FILETIME 134372074481977911은 살아 있으며
observe-original 422,368파일 / 11,984,862,650 bytes, stderr/hold 없음이다. 실제 exec78096도 실행 중이다.
앱은 종료 상태이고 1.0.32 설치는 아직 미실행이다. 원본 전수 검산과 독립 결과 검토를 기다린다.


15:26 KST 현재 첫 원본 Capture는 439,487파일 / 19,828,372,572 bytes를 읽고 끝났으며,
같은 Observer의 Verify가 진행 중이다. 소스의 Capture → Verify 호출과 각 단계의 집계 초기화를
실제 로그의 한 번의 files reset과 대조했다. 두 번째 단계는 21,883파일 / 8,240,827,044 bytes다.
같은 controller PID/생성 시각과 live exec78096을 확인했으며 새 실행·설치·앱 재시작은 없다.
최종 결과 미생성, stderr/hold 없음. 전체 보존 검산 PASS는 아직 판정하지 않는다.
근거: preservation-second-pass-stage.json 및 observer-live-read/read-20261023T062632558962Z.json.
이번 목표 턴은 VERIFIED_WAIT이며 기존 실행 완료를 기다린다.


## 2026-10-23 15:31 KST 닫힌 CSV 참조 범위 확정

이미 회수한 C31 CSV 9,384행을 고정 SHA256 전후 대조해 읽었다. review_csv_references.py는 exit 0이다.
온도 관측 참조 9,359행은 서로 다른 관측 2,178개에 연결되며 반복 참조는 7,181행이다.
참조 없는 25행은 startup_pending이다. 이를 CSV 순번 중복이나 장비 원시 샘플 누락으로 해석하지 않는다.
현재 service b6790219-2222-4c46-a696-b09c0c3e57ad의 참조 poll 범위는 2–2,226이다.
전체 fact 원장을 읽기 전에는 참조되지 않은 poll의 상태·저장 여부를 판정하지 않는다.

이미지 참조는 5,722행 / 서로 다른 1,792개이며 빈 참조는 3,662행이다.
첫 이미지 참조는 416행, 첫 CSV 이후 111.8277초다. 이 시각은 최초 화면 표시나 최초 이미지
수신·저장 시각을 뜻하지 않는다. 현재 C31 commit의 repository.py 2023–2057과 spot_api.py 968–970을
직접 읽어, 최신 이미지 fact의 observation key와 CSV의 key가 다르면 참조를 비우는 규칙을 확인했다.
따라서 빈 참조 전체를 파일 손실로 단정하지 않는다. 각 행의 원인과 저장 이미지 전체의 대응은
fact 원장·실파일 대조가 남아 있다. 원본이나 연결값을 소급 수정하지 않았다.

근거는 R3/closed-generation-evidence/csv-references의 review.json, references.json,
reference-semantics.json, execution.json이다. 5파일 / 453,362 bytes를
Z:/SmartFactory/20261023/return/F32CLOSE_R3_CSVREF_cd46692a에 전 파일 해시 대조해 보존했다.
화면 연속성·장비 샘플 완전성·학습 적합성은 이 검사의 판정 밖이다.

15:31:10 KST 같은 원본 Verify 작업은 90,738파일 / 8,908,066,092 bytes까지 진행했다.
controller 15912/동일 FILETIME 및 실제 exec78096이 계속 실행 중이다. 오류 출력·최종 결과 없음,
앱 종료 상태이며 C32 설치는 아직 시작하지 않았다.


## 2026-10-23 15:43 KST 기존 원장 사본 재사용 검산

기존 온도 관측·이미지 원장 사본 네 파일을 읽기 잠금 상태에서 다시 해시 대조했다.
verify_existing_fact_prefixes.py 실제 exit 0이며 각 부분의 크기·SHA256과 순서대로 연결한
전체 SHA256이 이전 closed-delta-review.json과 일치한다. 재사용 바이트는 3,474,840,335다.
본문 복사·서버 읽기·새 전체 백업은 하지 않았다. 작은 검증 기록 네 파일만
Z:/SmartFactory/20261023/return/F32CLOSE_R3_PREFIX_cd46692a에 해시 대조해 보존했다.

현재 종료 시점의 원장에는 이전 사본보다 온도 관측 48,600행·이미지 44,925행이 더 있다는
마감 manifest가 있다. 이는 추가 수집 대상의 예상 범위이며 실내용 검사는 아직 미완료다.
기존 부분과 추가분을 연결한 해시가 현재 마감 해시와 일치해야 현재 실행의 참조 검산에 쓴다.
근거는 R3/fact-prefix-reuse의 review.json, terminal.json, delta-plan.json, archive.json이다.
원본 preservation 검사는 같은 실행에서 계속 진행 중이며 C32 설치·앱 재시작은 아직 없다.


## 2026-10-23 16:00 KST 원본 보존 검산 완료·1.0.32 적용 절차 시작

preservation exec78096 실제 exit 0, owned PASS/exit0/Job [2,0,0]이며 종료 요청 없이 끝났다.
회수 도구와 review_preservation.py도 실제 exit 0이다. 원본 두 루트의 439,487파일,
233폴더, 추가 스트림 680개, 19,828,372,572 bytes를 재대조하고 현재 C31 정상 종료와 결합했다.
result SHA256 c7fc1e04ec899655dd7e95583f22f19b44c05ffce5042dce7b4d6e591a0b3a79,
manifest SHA256 f633259377e7ad2403606470a9cf283f2e3c79156a54f34f3dd6b0326399f1a6.
작은 내용 검토를 포함한 증거 38파일/213,646,426 bytes를
Z:/SmartFactory/20261023/return/F32CLOSE_R3_PRESERVATION_cd46692a에 전 파일 해시 대조했다.
운영 원본 본문이나 새 전체 백업을 추가 복사한 것이 아니다.

설치 요청 SHA256 37c15648a44aea6d62183cf7c8f99c7f0dcb7cf7083c77b410734cba75ce1b5f와
요청 묶음 3파일을 서버 I32_20261023_cd46692a에 전달·재검산했다. prepare 및 stage 실제 exit0.
15:56:28 KST 승인된 한 번의 적용 절차를 시작했다. exec7250, 개발 SSH35420,
서버 wrapper19536/FILETIME134372121903891479, child16052다. 15:58:26 서버 읽기에서 같은
wrapper가 살아 있고 앱/8000 listener가 없음을 확인했다. 이후 실제 exec7250도 계속 실행 중이다.
현재 단계는 설치 전 원본 재검산이며 설치 완료나 실제 C32 실행을 아직 주장하지 않는다.
설치 명령 반복·강제 종료·임의 앱 시작은 금지한다. 콘솔이 조용해도 같은 실행을 확인한다.

다음: 실제 exec7250 terminal0 → 콘솔 RESULT_PATH/SHA 확인 → recover_current_install.py --execute
→ 검토 성공 후 start-preparation/run_standard_start.py --execute 및 retrieve_start.py --execute
→ read_candidate_runtime_r3.py --execute. 이후 실제 C32 v8 정상 종료 관찰·기존 승인 네 필드 결합·
재시작 및 변경 영향 현장 검증을 계속한다. 자세한 경로는 installation-started-stage.json에 기록했다.

보존 manifest에서 현재 두 원장의 종료 시점 크기·해시를 추출해 이전 사본과 결합했다.
온도 관측 추가분은 53,494,941 bytes/48,600행, 이미지 원장 추가분은 23,156,941 bytes/44,925행이다.
합계 76,651,882 bytes이며 아직 회수·내용 대조는 미실행이다. 기존 3.47GB 사본을 재사용하고
이 범위의 추가분을 마감 해시로 연결해야 한다. 근거는 fact-prefix-reuse/closed-ledger-extents.json.
물리 경계/전체 자료 QA/학습 적합성은 미완료이며 release HOLD와 promotion false를 유지한다.


## 2026-10-23 16:22 KST 현재 C31 수신 참조·이미지 원본·해독 검증

진행 중인 C32 적용 절차와 독립적으로, 앱이 종료된 현재 C31 데이터에 대해 읽기 전용 검사를 완료했다.
기존 검증된 range reader와 종료 guard를 재사용한 새 어댑터는 경계 거부 37검사와 PowerShell 5.1
스크립트 6개 parse를 실제 exit0으로 마쳤다. 정해진 76,651,882 bytes만 6구간으로 읽었고,
read owner 실제 exit0/강제 종료 없음/작업 프로세스 0개 정리를 확인했다. 서버 데이터 변경은 없다.

기존 로컬 원장 부분들과 추가분을 읽기 잠금 상태에서 연결해 전체 마감 해시를 검산했다.
온도 관측 원장 1,092,084,308 bytes/943,047행, 이미지 원장 2,459,407,909 bytes/4,799,378행의
마감 해시는 앞서 원본 보존 manifest와 CSV metadata/image final manifest에 결합한 값과 일치한다.
새 부분에는 이전 service 9aa01423... 관측 46,373행·이미지 42,966행과 현재 service b6790219...
관측 2,227행·이미지 1,959행이 있다. 전체 이전 부분의 의미 검사를 새로 통과시켰다는 뜻은 아니다.

현재 CSV 9,384행/순번 1–9,384의 온도 참조 9,359행·서로 다른 관측 2,178개가 모두 원장에 존재하고
raw payload hash가 일치한다. poll 1–2,227의 gap은 0이다. CSV가 참조하지 않은 49개는 모두
valid_temperature이고 원장에 보존돼 있다. 반복 참조를 CSV 순번 중복으로, 미참조 관측을 장비 샘플
손실로 바꾸어 해석하지 않는다. 이미지 참조 5,722행/1,792개는 실제 capture ID·경로·관측 key와 일치한다.
빈 이미지 참조 3,662행은 보존했고 이미지를 임의로 보충하거나 학습용 대응관계를 추정하지 않았다.

현재 저장 이미지 1,959개/18,441,978 bytes를 보존 manifest의 원본 파일 크기·SHA256과 대조했다.
그 정확한 이미지들만 읽기로 회수하고 기존 고정 validate_spot_image_files.exe를 실행했다.
소비자 실제 exit0, owner 실제 exit0, 입력 잠금/전후 해시 PASS, 남은 프로세스 0이다.
결과 1,959행 모두 PASS·issues 없음, JPEG 512×288/decoded_frames1이며 고아 파일 0개다.
이는 이 종료 실행에서 등록·저장한 이미지 범위이며 센서의 모든 물리 프레임·화면 연속성·학습 적합성
또는 정식 출시 PASS를 의미하지 않는다. 이 짧은 유지보수 실행의 전체 CSV 소비자는 아직 실행하지 않았다.

근거: R3/current-fact-tail-read, current-closed-data, current-image-validation,
current-data-verified-install-running-stage.json. 원시 base64 영수증은 로컬에 보존했고,
해독된 추가분·compact 영수증·선택 이미지·검증 기록 2,047파일/103,832,963 bytes를
Z:/SmartFactory/20261023/return/F32CLOSE_R3_CURRENT_DATA_cd46692a에 전 파일 해시 대조했다.
새 전체 백업은 없다. 과거 손상/거부 기록을 PASS로 변경하지 않았다.

C32 적용은 같은 exec7250/서버 wrapper19536/child16052에서 계속 실행 중이다.
16:19:45 KST 같은 wrapper 생성 시각과 앱/8000 listener 없음을 확인했고 실제 exec도 살아 있다.
현재 설치 전 재검산 단계다. 다음 동작은 설치 완료 영수증 회수·검산이며 이미 시작한 설치를 반복하지 않는다.
기존 C31 결과를 C32 QA 통과로 옮기지 않는다. release HOLD·promotion false를 유지한다.


## 2026-10-23 16:38 KST 실제 설치 종료 0·설치 후 원본 대조 진행

서버 J9f4b09c5의 요청 SHA를 현재 설치 요청과 대조하고 중간 영수증을 읽었다.
설치 직전 원본 439,487파일/19,828,372,572 bytes 재검산은 16:28:57 KST에 끝났다.
설치 프로그램 PID11744는 16:29:01에 시작해 16:29:32에 실제 native 종료 코드 0,
강제 종료 없음으로 끝났다. 등록 버전은 1.0.32이며 설치 파일 영수증도 생성돼 있다.
이는 실제 설치 프로그램 종료 확인이고, 전체 설치 절차의 최종 성공 판정은 아직 아니다.
같은 exec7250/wrapper19536/controller16052가 설치 후 원본 대조를 수행 중이다.
단계가 바뀌며 파일 수가 다시 0부터 증가한 것이며 재설치가 아니다. 앱은 종료 상태로 유지한다.
최종 terminal0과 result SHA 회수 후 recover_current_install.py의 전체 검토를 수행한다.

근거: install-execution/installation-receipts-20261023T073150908457Z.json,
live-20261023T073005691263Z.json, native-installed-postverify-running-stage.json.
첫 중간 영수증 읽기는 PowerShell 자동 변수 Matches와 로컬 변수명이 겹쳐 실패했다.
지역 변수명을 transactionRoots로 고친 읽기는 exit0이며 설치 실행·데이터에는 영향을 주지 않았다.

다음 15분 입력 준비기 prepare_operational_observation.py를 C32 식별값으로 준비했다.
원본 역치환 일치·구문·기본 실행 시 서버 미접속을 확인했고 실제 요청 소비자 9조건은 exit0이다.
초기 경로 대조에서 source-final의 capture-closed-facts.ps1 해시 불일치를 발견했다.
실제 commit의 source-r2로 한 줄 수정한 뒤 116소스/8패키지 파일을 전부 대조했다.
최종 준비기 SHA256은 6393ba001f9dc8f2dcd96dd4b2dfbadf1ec22ecb51d5deed42e510b03102f04c.
operational-preparer-checks-r2/result.json이 현재 검증이며 초기 준비 기록은 보존한다.

이 준비기는 실제 설치 검토→일반 사용자 시작→C32 v8 정상 종료→승인 네 필드 연결→일반 재시작
및 attested-candidate-runtime 검토가 끝난 뒤 --prepare로 실행한다. 아직 실행 입력·C32 관찰 guard
전달·15분 측정은 시작하지 않았다. 준비 뒤 기존 단절 정리 guard를 정확한 C32 핀에 결합·검사한다.
물리 경계·정식 QA·운영 승격은 미완료이며 release HOLD/promotion false다. 새 전체 백업은 없다.


## 2026-10-23 16:54 KST 다음 관찰 guard 준비·검사

1.0.32 설치 후 원본 대조는 같은 exec7250에서 계속 진행 중이다. 최종 결과 전 앱은 시작하지 않았다.
Chrome 원격 화면에서도 바탕화면·앱 종료·오류 창 없음을 직접 확인했다. 이번 turn은 실제 다음
관찰에 필요한 로컬 준비와 검사를 완료했으므로 PROGRESS다.

prepare_operational_guard.py는 실제 attested C32 runtime에 결합된 15분 입력이 있어야 묶음을 만든다.
기존 검증된 단절 정리 guard 본문은 유지하고 build·경로·request/config SHA·logger/CSV·native PID/
FILETIME을 대조해 치환한다. 전송·실행·회수·재계산 driver 5개도 준비하며 아직 서버에 전달하지 않았다.
로컬 합성 runtime 11조건, Python driver 5개 구문, native PowerShell 2개 parse, 기본 실행/회수 기본
실행의 서버 미접속을 확인했다. check_operational_guard.py 실제 exit0, 기록은
operational-guard-checks-ceb997cb/result.json이다. 최초 SHA 문자열 오타는 poll 소스 검산에서 거부됐고
수정 후 전체 영향 검사를 통과했다. guard 준비기 SHA는
58468ee9c432552bf2c690edb5181b0a6319d824b2636d4669f4885663a2fc64다.

operational-preparation-archive.json의 목록·해시로
Z:/SmartFactory/20261023/records/F32_OBSERVATION_PREPARATION_cd46692a에 보존했다.
처음 records 부모가 없어 보존 단계만 중단됐고, 날짜 폴더 확인 후 records를 만들고 이어갔다.
실제 C32 runtime/관찰 합격이 아니다. 설치 검산·시작·C32 v8 정상 종료·승인 네 필드 결합·재시작 후
prepare_operational_observation.py --prepare → prepare_operational_guard.py --prepare 순서다.
실제 생성 entry/launcher도 native parse한 뒤 stage_observers.py로 서버 사전 검사를 한다.
이후 launch_observer.py --role observe15 --execute를 한 번 실행하고 실제 종료 후
recover_observation.py --execute와 review_observation.py의 원시 재계산을 수행한다.
실제 15/120분·화면·전체 QA·물리 경계·운영 승격은 현재 준비 결과로 대체하지 않는다.


## 2026-10-23 17:12 KST C32 설치 검산·정상 종료·승인 설정 연결·재시작 완료

설치 exec7250이 실제 exit0으로 끝났고 recover_current_install.py도 실제 exit0이다.
J9f4b09c5 결과 SHA256 b18c200c4ed318ac09f0728a69656d6d92b4af2bd27ff6a4bcfe9ef862792dcf에
결합한 23영수증을 회수·검토했다. 설치 payload1,867파일과 제거 파일, 원본439,487파일/
233폴더/680추가 스트림/19,828,372,572 bytes의 본문·메타데이터·구성이 보존됐고 설정은 같았다.
새 전체 백업은 없고 설치는 한 번만 수행했다. 설치 기록은 installation-final-review에 있다.

일반 사용자 시작 ST32_43a387f2 후 실제1.0.32/REAL/Running과 대시보드·영상·작업 정보를
확인했다. C32CLOSE_20261023_cd46692a 사전 검사와 READY를 확인한 뒤 CUA에서 정상 Alt+F4를
한 번 보냈다. 오류 창 없이 닫혔고 exec66720과 회수·내용 검토 모두 실제 exit0이다.
Rd257d0f58a96 결과 SHA256 45bc70a5918ec8169201e7d3788654d2f1025c29b53c3a3dad0c9056329e0b75,
native5개 모두 exit0, CSV493행/순번1–493/valid472/startup_pending21을 확인했다.
전체 이미지·수신 원장·전체 CSV QA까지 통과했다는 뜻은 아니다.

실제 닫힌 metadata에 결합한 승인 확인 네 필드만 갱신했다. 실제 생성 controller/core2개의
native parse와 검토 후 적용·회수 모두 exit0이며 A696aaa98 결과 SHA256은
d9b4917bec354dbf35474a85361340699d32a039e1bab80a3240fb57984e5fc5다.
나머지 설정 본문이 동일하고 Low Signal은 OFF, 물리 경계 NOT_TESTED다.
쓰기 실패 복구용 기존 config2,671바이트 사본 한 개 외 전체 백업은 만들지 않았다.

ST32_b73f3b70의 일반 사용자 재시작·회수도 exit0이다. main11128/backend11024,
logger a5f5b189-cda3-49fd-b9e8-e27ef079898a,
CSV Factory_Integrated_Log_v2_20261023_170713.csv에 결합했다.
설정 SHA256 7d75bc47f52ede158095745aba8d085f06b9e7bbe768a5a8ddb3743eabc318f2,
설정 drift0, native 프로세스 일반 사용자 토큰을 확인했다.
재시작 대시보드는 전면 표시됐고 작업 정보60365·7을 직접 확인했다.
c32-restarted-dashboard.jpg에 화면을 보존했다.

15분 입력은 이 실제 재시작에 결합해 소비자 검토를 통과했다. 실제 생성 entry/launcher2개의
native parse exit0 후5파일12,482bytes를 새 O15C32_20261023_cd46692a에 전달·해시 검산했고
서버 사전 검사도 exit0이다. 17:09:43KST exec92191로 관찰기를 한 번 시작했다.
서버G369786de833d/controller18084의 동일 생성 시각·실행 중과 앱 세대 유지를 확인했다.
관찰 합격이나120분 완료는 아직 아니다. 현재는 operational-observe로 health/data/resource를
검사하며200/500ms 초과는 진단값이다. 고정250ms 이미지 부하 시험과 화면 연속성을 대신하지 않는다.

설치 증거는 Z:/SmartFactory/20261023/return/I32_20261023_cd46692a에 보존했다.
추가 정상 종료·설정 연결·재시작 증거259파일/3,540,660bytes는
Z:/SmartFactory/20261023/return/C32_RUNTIME_cd46692a에 전 파일 해시 대조했다.
candidate-runtime-archive.json과 installed-restarted-observe15-stage.json이 최신 연결 기록이다.
현재 앱을 닫지 말고 exec92191 실제 종료 뒤 recover_observation.py --execute 및
review_observation.py의 원시 재계산 결과를 확인한다. C31의 결과를 C32 통과로 옮기지 않는다.
정식QA·물리 경계·운영 승격은 HOLD, promotion false이며 목표는 계속 진행 중이다.


## 2026-10-23 17:30 KST 과거 종료 요청 답변 후 닫힌 앱 복구·15분 R2 관찰

사용자가 14:24 유효 시각이 있는 과거 요청에 “종료됨”으로 답했다. 현재 상태를 새로 확인하니
앱은 닫혔고 최초15분 관찰 exec92191은 실제 exit1로 끝났다. run-b4b968effe4f를
콘솔 SHA256 76f7f70c609ea2785050ba9bcfbaec04e4e88de789a103ade4594fcd19a10549에 대조해
회수했다. 원시 HTTP/자원/종합 판정 재계산은 exit0, RECORDED_SUMMARIES_REPRODUCED이고
실제 관찰 판정은 FAIL/INCOMPLETE다. 15분 통과가 아니며 원본 실패 기록을 그대로 보존했다.
원인은 앱 종료와 관찰 중단이 맞물린 것으로 판단하되, 200/500ms 초과만으로 판정하지 않았다.

닫힌 실행 logger a5f5b189-cda3-49fd-b9e8-e27ef079898a의 CSV2,547행을 회수·해시 확인했다.
순번1–2547, 동일 logger, metadata의 최종 저장2547/종료 사유shutdown/finalized=true가 일치한다.
최종 저장시각은17:18:36KST, valid2530/startup_pending16/stale1이다. 설정 SHA는 그대로다.
이때 종료 관찰용 native handle을 미리 보유하지 않아 OS 종료 코드까지 확인한 것은 아니다.
전체 이미지/원장 QA를 이 제한된 종료 확인으로 대신하지 않는다. late-close-review/review.json 참조.
최초 읽기에서 Desktop 전용 경계 함수가 AppData 경로를 거부했으므로, 별도 고정 AppData 경로와
상위 reparse 검사를 사용한 읽기로 교정했다. 운영 원본 변경은 없다.

기존 검증된 시작 도우미의 바이트를 재사용했고 새 전달·결과 경로와 종료 검토 조건만 연결했다.
실제 시작·결과 회수 exit0, ST32_8d8ba3a9/result SHA
f1b5ed1e5813a0ee5b8a0276ca0ab561757788491214f541f1f001b58b1a372f.
현재 main14404/backend16376, logger9a245aa0-46ad-4ac3-b908-69c334f49835,
CSV Factory_Integrated_Log_v2_20261023_172545.csv, 일반 사용자/REAL/1.0.32/설정 drift0이다.
추가 설치·확인 설정 갱신·전체 백업은 없다.

새 O15C32R2_20261023_cd46692a는 현재 실제 PID/생성시각/설정/CSV에 결합했다.
실제 생성 entry/launcher2개 native parse exit0,5파일12,487bytes 전송·서버사전검사 exit0 뒤
exec53100으로 한 번 시작했다. Gc6c53ca8b772/controller3700의 동일 생성시각·실행 중을 확인했다.
현재 앱은 닫지 않는다. R2 결과 이후 회수·재계산해 통과 여부를 판단한다.
120분 준비기는 prepare_operational120_r2.py 및 prepare_operational120_guard_r2.py를 사용한다.
초안 회수 스크립트 치환 순서 문제를 R2에 고쳤고11조건/5Python/2native parse가 exit0이다.
아직120분 입력 생성/서버 실행은 없으며 R2 15분 실제 COMPLETE/PASS가 선행 조건이다.

원격 화면에서 대시보드·영상·전면 표시를 확인했다. 17:29:01 이후 작업 정보는 필수값 미입력으로
바뀌어 현재 생산 여부를 질문했다. 이전60365·7을 임의 재입력하지 않는다. 이는 관찰의 대기조건이 아니다.
latest canonical은 late-close-restarted-observe15-r2-stage.json이다. 목표 active/PROGRESS,
release HOLD/promotion false, 물리 경계 NOT_TESTED 및 전체 QA 미완료를 유지한다.


## 2026-10-23 17:50 KST C32 15분 R2 기록 검증·120분 시작

현재 생산 중이 아니라는 사용자 답변은 17:38:31 KST에 기록했다. 이후 실제 화면에는
17:38:38에 적용된 제품60365·금형6이 표시됐다. 두 시점의 확인을 구분하고 값을 임의 변경하지 않았다.

15분 R2 exec53100은 실제 exit0으로 완료됐다. run-ea3318eb7f33을 콘솔/guard 결과에 결합해
회수했고 회수·재계산 모두 exit0이다. launcher SHA256
0cab2f6e36dd7d2fea1e2de1346fb8ceb3bbae4137c9de2338b2ef171e1c8fd8,
review SHA256 63958e5fb6d78aca1848a6c747781b0ae43843fb12680002c104b18f17dcd6f0.
원시 기록 재계산 RECORDED_SUMMARIES_REPRODUCED, COLLECTION_AND_BINDING_ONLY 범위
PASS/COMPLETE다. health450건(경계 포함452), data150건과 자원181회가 모두 기록됐고
요청 오류·타임아웃·예정 측정 누락0이다. health200ms 초과6건/최대1495.1224ms,
data500ms 초과0건/최대270.6153ms는 진단값으로 보존한다.
운영 지연 허용치·화면 연속성·저장 완전성·물리 성능을 이 결과로 PASS 처리하지 않는다.
최초15분 FAIL/INCOMPLETE도 별도로 그대로 보존했다.

실제 현재 main14404/backend16376/logger9a245aa0-46ad-4ac3-b908-69c334f49835에 결합해
prepare_operational120_r2.py와 prepare_operational120_guard_r2.py를 실행했다.
실제 생성 entry/launcher native parse2개와 driver AST5개 exit0,5파일12,489bytes의
공유/서버 해시 검산 및 서버 사전 검사 exit0 뒤 17:48:56 KST exec7704를 한 번 시작했다.
O120C32_20261023_cd46692a/launches/observe120-d516e9a16f74,
서버G5960843e8711/controller11060/createdFILETIME134372189392815581이다.
17:49:31 KST 실제 읽기에서 동일 앱 세대·관찰기 실행 중·stderr 없음·hold 없음이 확인됐다.
아직120분 완료가 아니며 최종 결과와 원시 재계산을 확인해야 한다. 관찰 중 앱을 닫지 않는다.

관찰 종료 후 사용할 prepare_post120_close.py를 현재 세대에 연결해 로컬 준비했고,
post120-close-preparation-checks/review.json의 원문 역치환·native parse·driver2개 AST 검사를
exit0으로 마쳤다. 아직 --prepare/전달/실행하지 않았고 앱 종료도 하지 않았다.
120분 실제 결과 확인 뒤 이 준비기로 runtime-close만 생성·검산·전달하고 READY를 확인한
직후 직접 정상 종료한다. 종료된 CSV/수신·이미지 원장과 저장 파일을 대조한 뒤
일반 실행으로 복귀하고 작업자 화면을 전면에 둔다. 새 전체 백업·재설치는 없다.

최신 연결 기록은 operational15-r2-verified-observe120-stage.json이다.
목표 active/PROGRESS, release HOLD/promotion false 및 물리 경계 NOT_TESTED를 유지한다.


## 2026-10-23 18:02 KST C32 종료 CSV 구성요소 검사

현재120분 관찰 exec7704는18:02:10 서버 실제 읽기에서도 같은 앱 세대·controller11060으로
계속 실행 중이며 stderr/hold/최종 결과는 없다. 관찰 중 재시작·무거운 데이터 회수는 하지 않았다.

이미 회수한 C32 CSV두 개3,040행에 대해 원래 build의 소스5개를 추출해 행 규칙7개,
순번·inline metadata·설정 snapshot·최종 저장 계약을 검사했다. 코드 실행 exit0,
부정 입력12검사 통과, 입력4파일/원 Git 소스5개 독립 대조 exit0, 해당 규칙 finding0이다.
valid3002/startup_pending37/stale1과 당시60365·7을 구분·보존했다.
Ruff는 Python312에 모듈이 없어 실행되지 않았다(exit1). 통과했다고 기록하지 않는다.
기록: c32-closed-csv-components/summary.json, verification.json, review.md.
수신 원장·이미지 바이트 대조/전체 consumer/학습 적합성/물리 샘플 완전성은 여전히 별도 미완료다.

최신 기록은 closed-csv-components-observe120-stage.json이다. 목표 active/PROGRESS,
release HOLD/promotion false.120분 실제 결과 후 종료 관찰과 원장 추가분·최종 manifest 대조를 이어간다.


## 2026-10-23 18:25 KST C32 종료 후 작은 증거 회수 준비

현재120분 관찰 exec7704는 실제 실행 핸들에서 계속 실행 중이다.18:19:05 서버 조회에서도
같은 앱 세대와controller11060, stderr/hold/최종 결과 없음이 확인됐다.18:21 이후 직접 본
Smart Factory 화면은 Running·대시보드·카메라와 작업60365·6을 표시한다.17:38:31에 받은
'생산 중 아님' 답변과17:38:38에 적용된 후속 UI값을 구분하고 임의 수정하지 않았다.

prepare_post120_evidence.py는120분 결과 검토와 같은 logger의 정상 종료 내용 검산 이후에만
최종 이미지 manifest 및 저장 worker의 begin/final 영수증을 읽는다. 기존 검증된 읽기 코드의
고정 바이트를 재사용하며 전체 원장·이미지 사본이나 백업은 만들지 않는다. 앱을 제어하지 않는다.
정상 종료 후 이 작은 증거를 먼저 확보해야 다음 시작으로 최종 manifest가 바뀌기 전에 대조할 수 있다.
16개 잘못된 경로·해시·종료 세대 거부 검사와 실제 생성PS2개 native parse가 exit0이다.
실제 첫 C32 종료 기록의 오사용 거부와120분 미완료 시 원격 모듈 실행 차단도 독립 검사 exit0이다.
초안의 Python문자열 escape 경고는 수정했고 최종 -W error 실행은 exit0이다. 초안 기록은 보존했다.

기록은 post120-evidence-preparation-r2/review.json 및 independent-verification.json이다.
아직 서버에서 이 도우미를 실행하지 않았다. 다음 순서는 실제120분 종료·재계산 → 정상 종료
관찰 READY → 정상 UI닫기 → close 내용 검산 → 작은 증거 회수 → 원장 추가분/CSV/이미지 대조
→ 승인된 일반 사용자 실행·전면 표시다. 이전 C32두 실행의 fact/image 대조도 최신 닫힌 원장에서
분리해 확인한다. 아직 전체 저장 QA·물리 경계·운영 승격을 완료한 것은 아니다.


## 2026-10-23 18:35 KST 교체 직전 C31 CSV 상세 검사 진행

C32 120분 관찰 exec7704를 유지하면서, 이미 회수한 직전 C31 실행의 CSV9,384행에 대한
고정 상세 소비자 검사를 추가 시작했다. 이는 C32 검사로 집계하지 않는다. 이전에 이 실행의
CSV참조·수신 원장·이미지1,959개·정상 종료 잔량은 확인했지만 상세 소비자는 NOT_EVALUATED였다.

현재 C31LASTQA_20261023_cd46692a의 consumer-inputs 5개3,564,112,113bytes는 기존 고정
원장3부분을 잠긴 상태로 연결한 검사용 작업 공간이다. 출처별 크기·SHA256과 합친 전체 해시,
원본CSV·metadata·실제 image final을 대조했고 준비 exec74205는 exit0이다.
운영 원본이나 서버에는 접근하지 않았고 새 운영 백업도 아니다. 기존 검증된 소비자가 실제
파일 경로를 요구하므로 검사용 재구성이 필요했다. 원래 회수 증거는 변경하지 않았다.

검사기는 기존 SHA e728730ad841dd4a754a6c0880e0e1216de5e3d0cd5646c22de9245fc85b0b2f
바이트를 사용한다. 실제 실행 exec44262, 소유 driver31316/created1792747848.9156537,
09:30:55Z 입력 재검산 완료 후 검사 시작이다. 프로세스 Job·입력 잠금·7200초 제한과
소유 프로세스 정리를 기존 검증 경로로 적용했다. 검사 중이며 아직 CSV PASS는 아니다.
최종 실제 종료·출력·입력 재검산·잔류 프로세스 검산이 필요하다.

prepare_post120_evidence.py 준비는 그대로 보존했다. C32 120분이 끝난 뒤 실제 결과를 검토하고
정상 종료·최신 저장 자료 검산을 이어간다. 전체 출시 HOLD, promotion false, 물리 경계 NOT_TESTED다.


## 2026-10-23 18:54 KST 종료 후 원장 추가분 읽기 준비·시작 증거 범위 점검

120분 관찰 exec7704와 직전 C31 상세 소비자 exec44262는 실제 실행 핸들에서 계속 실행 중이다.
18:51:43 서버 조회에서 같은 main14404/backend16376/controller11060, 오류·hold·최종 결과 없음이
확인됐다. 현재 화면도 Running·온도·카메라·작업60365/6을 전면 표시한다. 기존 생산 여부 답변과
후속 화면 적용 시점을 구분하며 작업값은 변경하지 않았다.

prepare_post120_fact_tails.py는 기존 C31 냉간 범위 읽기와 소유 Job 실행기를 재사용한다.
기존3,551,492,217바이트 prefix를 다시 서버에서 복사하지 않고 추가분만16MiB씩 읽는다.
실제120분 검토·같은 세대 정상 종료·최종 이미지 manifest 회수 전에는 실행하지 않는다.
잘못된 입력26개 거부·생성PS4개 native parse exit0, 독립 실행흐름5개 검사 exit0이다.
독립 검사에는 실제 미완료120분 차단과 가상 전송4바이트·SID/control/pin 오류 거부가 포함된다.
이는 로컬 준비 검증이며 아직 서버 읽기·최신 원장 완전성 PASS가 아니다. 회수 후 prefix와
추가분의 전체 해시·행 수·세대별 CSV/이미지·worker 종료 대조를 수행해야 한다.

기록: post120-fact-tail-preparation/README.md, review.json, independent/verification.json.
원본56파일216,550바이트를 Z:/SmartFactory/20261023/records/C32_POST120_TAIL_PREP_cd46692a에
파일별 해시 대조하여 보존했다. 전체 백업·설치·설정 변경·앱 종료는 하지 않았다.

startup-evidence-scope-review.json/md에는 시작10회가C30, 현장시작3개가C31이며 C32 VM의
3개 electron-ready는 화면운영 준비 완료 시각이 아님을 기록했다. 시작 계측 코드는 바뀌지
않았으나 포트 임대 변경의 초기 통신 영향은 미평가다. 기존10회/전체matrix를 자동 반복하지
않고, 계획된 종료 후 C32 보존startup 로그를 먼저 확인한 뒤 실제 빠진 증거만 판단한다.
현재 C32 전체 시작 계약은 NOT_EVALUATED, 전체 출시 HOLD/promotion false다.

최신 canonical은 post120-tail-prepared-observe120-stage.json이다. 두 실제 실행의 최종
종료를 먼저 검산한다.120분 관찰 중 앱을 닫거나 prepared helper를 실행하지 않는다.


## 2026-10-23 19:04 KST C32 종료 내용 검토 준비

현재 exec7704의120분 관찰과 exec44262의 직전C31 CSV9,384행 상세 검사는 실제 실행 핸들에서
계속 실행 중이다(19:02:24 KST 확인). 두 실행을 재시작하지 않았고 앱도 닫지 않았다.

review_post120_worker_closure.py는 고정된 기존 review_records 계약을 재사용하여 관찰 전후
logger/service/native 세대, 실제 프로세스 종료0, worker begin/final 및10개 종료 단계, 이미지
등록=저장·잔량/실패/거부0, CSV마감/순번/시각을 연결한다. 실제120분 결과·같은 세대 종료·
작은 증거 회수 이후에만 C32 실제 검토를 허용한다.

보존된 C31 이미지23,022건 실행의 기존 자료를 재현하고 부정 입력13개를 거부했다(exit0).
출처12개 재검산·실제120분 미완료 차단 독립 검사도 exit0이다. 이를 C32 결과로 계산하지 않는다.
4파일16,448바이트를 공유 records/C32_POST120_WORKER_PREP_cd46692a에 해시 확인해 보존했다.
실제 C32 worker 판정, full ledger/CSV/imagebytes, 시작 전체 계약은 아직 미완료다.

최신 canonical은 post120-worker-prepared-observe120-stage.json이다. 목표 정합성 보고서 앞부분에
현재1.0.32 설치·VM·15분 결과와120분/저장 검증 진행 상태를 연결했다. 과거 C31 시점 자료는
보존 이력으로 구분했다. 운영/롤백 기준은 변경하지 않았고 전체 출시 HOLD/promotion false다.


## 2026-10-23 19:20 KST 직전 C31 상세 CSV 완료·C32 과거 이미지 마감 증거 공백

직전 C31 마지막 CSV9,384행 고정 상세 검사가 실제 exec44262 exit0으로 완료됐다.
수신 원장943,047행·이미지 원장4,799,378행의 전체 행 수/해시, CSV참조9,359건과 누락0을
확인했다. 실제 stdout·terminal·입력 결합과 소유 Job 잔류/강제 종료0을 재대조했다.
기록은 C31LASTQA_20261023_cd46692a/review.json 및 verification.json이다.
이전 C31 내용 검사 결과이며 현재 C32 결과·학습 적합성·물리 샘플 완전성으로 확대하지 않는다.

C32 첫 두 CSV493/2,547행은 metadata에 당시 image final이 없고 pending-at-open 표시만
남아 있다. 고정 소스의 공통 final 교체와 메타데이터 개시 동작을 확인했으며 이 표시를
종료 실패/이미지 손실로 단정하지 않는다. 로컬 해당 파일명1,120개 탐색에서 큰 원장에
대응하는 final 세 사본은 모두 C31이었다. 서버·압축 내부까지 부재를 증명한 것은 아니다.
read_prior_c32_receipts.py는 현재120분 완료와 정상 종료·현재 final 확보 뒤 과거4888/11024의
생성 시각을 결합한 작은 worker 영수증만 읽는다. PS parse+부정4개와 별도11개 검사 exit0,
아직 서버 실행 전이다. audit JSON/MD와 검색 범위·오류16개를 보존했다.

19:20:25 서버 조회에서 현재 main14404/backend16376/controller11060의 같은 세대 실행과
오류/hold/최종 결과 없음을 확인했다. 화면은 Running·카메라·60365/6·전면 표시이며
사용자의17:38 생산 중 아님 답변 이후 적용된 값을 임의로 바꾸지 않았다.
23파일649,470바이트를 Z records/C31LASTQA_COMPLETE_C32_GAP_cd46692a에 해시 대조했다.
최신 canonical은 prior-c31-complete-c32-gap-observe120-stage.json이다.120분/최종 C32 저장
검산은 아직 진행 중이고 전체 출시 HOLD·promotion false를 유지한다.


## 2026-10-23 19:29 KST C32 보존 시작 로그 읽기와 실행 결합 준비

이전 turn은 직전C31 실제 CSV9,384행 상세 검사 종료0·출력 결합을 완료한 PROGRESS다.
현재120분 exec7704는19:29:18 실제 실행 핸들4248c7에서 계속 실행 중이며 재시작하지 않았다.

read_post120_startup_logs.py는 기존4개 로그 reader 원문을 재사용하고 현재 정상 종료 control
고정 해시 및 앱/8000포트 종료를 읽기 전후 확인한다. 각9MiB 한도·동일 파일 prefix 두 번
해시를 유지하며120분 결과와 현재 마감 증거 회수 전에 원격 읽기를 실행하지 않는다.
PowerShell native parse exit0, 기존 본문 일치·전후 guard·잘못된 control/hash 거부·현재
미완료120분 차단6개 검사 exit0이다. 실제 C32 startup 로그 회수는 아직 하지 않았다.

post120-startup-reader-preparation/contract.json은 실제 C32 commit의 시작 요건9개와
backend progress9개, 보존된 native 실행3개의 PID/생성 시각/최초 관찰 시각/logger/config를
결합했다. 처음 실행은 확인 설정 연결 전이고 뒤 둘은 연결 후여서 같은 조건3회로 합산하지 않는다.
외부 실행 stopwatch·OS cold cache·사용자가 본 모든 frame은 이 로그만으로 증명되지 않는다.

11파일44,898바이트를 Z records/C32_STARTUP_READ_PREP_cd46692a에 해시 대조했다.
현재 설치/설정/서버 상태/작업값은 변경하지 않았고 추가 시작 시험이나 백업도 하지 않았다.
최신 canonical은 startup-reader-prepared-observe120-stage.json이며 목표active/출시HOLD,
promotion false다. 실제120분 종료 뒤 계획된 정상 종료·마감자료/로그 대조를 이어간다.


## 2026-10-23 19:38 KST 세 C32 실행의 원장·CSV 참조 검토 준비

120분 exec7704는19:38:16 실제 핸들44a734에서 계속 실행 중이다. 앱/관찰기를 재시작하지 않았다.
이전 turn은 C32 실제 시작요건과 native3세대 연결 및 제한된 로그 reader 검사를 완료한 PROGRESS다.

review_post120_fact_tails.py는 현재 정상 종료·worker 검토·원장 추가분 회수 후 로컬에서만
기존 전체 prefix와 추가분을 잠금 읽어 전체 해시·행 수를 대조한다. C32세 service를 분리하고
과거 수신 manifest의943,163/943,834행 지점 및 현재 마감 지점의 원시 해시도 확인한다.
이미지 최종 manifest가 없는 과거두 세대는 최신 final을 당시 final로 바꿔 쓰지 않는다.
각 CSV 순번/logger/build/관찰 참조/raw hash/이미지 참조·age와 작업자 입력 구간을 검토한다.
현재 이미지 수는 현재 세대 worker의 실제 저장 건수와 일치해야 한다. 다른 service나
알 수 없는 추가행을 무시하지 않는다. 실제 파일의 모든 바이트/decode·고정 전체 소비자는 별도다.

준비는 보존된 C31 실제9,384행/1,959이미지 참조 및 작은3세대 따옴표/줄바꿈 바이트를 대조했다.
잘못된 hash·행 수·마감지점·service·잘린/형태오류 행과 미완료120분을 거부했다(11검사 exit0).
현재 C32 전체 원장/CSV/이미지 QA가 통과한 것으로 표시하지 않았다. helper5585바이트의
시작 로그 reader와 별개로 이번 데이터 reviewer는13,751바이트다.

고정 image validator는 F31/F32 모두 SHA5601b347637bd0dcb9971839ec93bdc2860ad4594e5ba328acd4e70fa91d5f14로
같다. 기존 named-image reader는 이전 service/count/final hash가 고정되어 있어 새 선택표에 맞게
검산된 적용이 필요하며 원문은 변경하지 않는다. 공유 records/C32_DATA_JOIN_PREP_cd46692a에
5파일19,331바이트 해시 대조를 마쳤다. 서버·설정·작업값 변경/추가 백업은 하지 않았다.

최신 canonical은 three-generation-data-review-prepared-observe120-stage.json이다.
목표active/출시HOLD/promotion false, 관찰 실제 종료 이후 검증을 계속한다.


## 2026-10-23 20:21 KST C32 120분·정상 종료·이미지·보존 시작 로그 완료

120분 exec7704 실제 종료0, 회수 exec83425 종료0, 원시 재계산 exec36607 종료0을 확인했다.
상태 확인3,602건·데이터 조회1,200건의 오류/타임아웃/측정 누락은0, 자원 관찰은1,441회 전부다.
200ms 진단 참조 초과5건·최대320.7756ms와 legacy FAIL은 보존한다. 새 기준의 PASS 범위는
COLLECTION_AND_BINDING_ONLY이며 화면/저장/물리 샘플 완전성 전체 판정으로 확대하지 않는다.

관찰 종료 뒤 준비 완료를 읽고 정상 UI 종료를 한 번 수행했다. 현재 세대 main14404/backend16376과
자식까지5개 실제 종료코드0, CSV37,944행 순번1..37,944·마감, image worker8,375건 저장·잔량/실패/거부0을
대조했다. 미회수였던 과거 두 worker도102/597건 저장과10개 종료 단계·잔량0을 확인했다. 과거 image final
두 개와 늦게 닫힌 실행의 native exit는 새 기록으로 대체하지 않았다.

세 C32 실행의 CSV40,984행과 수신 원장952,932행·이미지 원장4,808,452행의 전체 prefix/추가분 해시,
마감 지점 및 참조를 대조했다. 누락 참조/원시 payload 충돌은0이다. 원장에 이름이 있는 이미지9,074개
(83,605,542바이트)의 해시·디코딩 검증3개 모두 실제 종료0, 오류0·소유 프로세스 잔류/강제 종료0이다.
이름이 있는 저장 파일의 완전성과 장비의 모든 물리 샘플 보존은 별도다. 현재 CSV에서 작업 정보가 빈
2,183행은 그대로 보존하며 품목/금형을 소급 입력하지 않았다.

보존된 startup 로그4개에서 세 실행을 PID·생성 시각·설정과 연결했다. 각각 필수 시작 단계9개와
backend progress9개가 있으며 내부 dashboard operational ready는13,522.8/15,484.3/15,967.5ms다.
첫 실행은 확인 항목 갱신 전이므로 같은 조건3회로 합산하지 않는다. 외부 stopwatch·cold cache·
사용자가 본 모든 frame은 입증하지 못하며 전체 시작 계약은 NOT_EVALUATED다.
review_retained_c32_startup_and_workers.py 실제 종료0(228843), worker 부정 입력6개 거부를 확인했다.

서버는 일반 사용자로 정상 재시작했다. main7036/backend20832, 새 logger93194b7b-8035-4ce7-86e1-92ae2e9861f1,
CSV Factory_Integrated_Log_v2_20261023_200404.csv다. 설정 SHA7d75bc47…은 동일하고 drift0이다.
20:09:37 KST 화면에서 Running·카메라·60365/6·전면 표시를 직접 확인했다. 사용자의17:38 생산 중 아님
답변과 이후 작업자가 적용한 값을 구별하며 값을 바꾸거나 실제 생산 상태를 추측하지 않았다.

원본 9,419파일의 결과/선택 이미지 사본을 공유 return/C32POST120_20261023_cd46692a에 검산 보존했다.
archive347,832,320바이트 SHA6700eb480b6aa2eaf7aeaad90bd69e3bab4fd9fd6ae877aae7645b16c60f171a이며
archive exec43968 실제 종료0(a4b02b)이다. 운영 데이터 전체 백업·설치·설정 변경·삭제는 추가하지 않았다.

종료 관찰 파일 전달 첫 시도는 설치용 여유 공간 기준을 상속해 생성 전 중단됐다. 실제 CSV50.8MB와
종료 helper의1GiB 최대 CSV 제한을 확인한 뒤 읽기/마감용2GiB+64KiB 기준의 새 stage R2를 만들었다.
원래 실패/원문을 보존했고 설치 기준·운영 프로그램은 변경하지 않았다. stage-r2-preparation.json에 근거가 있다.

현재 C32의 CSV37,944행 고정 상세 소비자는 exec78383에서20:08:43 시작, 아직 결과를 기다리고 있다.
기존 actual 실행을 재시작하지 않는다. source image fact4,808,452행을 함께 검사하며 원시 입력 크기/해시는
C32LASTQA_20261023_cd46692a/inputs.json에 고정했다. 완료 후 stdout/stderr·validator/owned terminal·
입력 결합·review.json을 대조해야 한다. 앞선 두 CSV는 구성요소+참조 검토 범위이며 전체 소비자 결과와 구분한다.

최신 canonical: post120-complete-restarted-csv-running-stage.json.
record_post120_completion.py 종료0(5540f7), canonical과 progress 및 docs/.pdca-status.json의 최신 key/본문이
모두 일치한다. 다음은 exec78383 실제 종료 확인과 잔여 R1–R6 근거/판단 정리다. 서버는 계속 Running으로
유지한다. 이미 완료한120분/시작 시험을 자동 반복하지 않는다. 목표active·출시HOLD·promotion false다.


### 수신 원장과 CSV의 정보량 구분

[세 C32 실행의 기록 간격 분석](C:/Users/user/Desktop/SmartFactory/F32CLOSE_20261023_cd46692a_R3/c32-recorded-cadence/review.json)을 추가했다(로컬 분석 종료0, f17dd9).
CSV가 참조한 원장 행의 누락은0이지만, 원장에만 남고 CSV가 참조하지 않은 관측은239건이다.
그중 valid_temperature205건·invalid_sentinel34건이며 원장에 보존돼 있으므로 저장 유실로 단정하지 않는다.
CSV의 반복 참조도 새 온도 관측으로 세지 않는다. 향후 학습 입력 선정 때 CSV만을 모든 수신 기록으로
간주하면 안 된다. 원시 관측·유효성·시간·작업 정보 귀속을 함께 판단해야 한다.

현재 닫힌 실행의 HTTP 관측 완료 시각 간격 중앙값0.999989초, p99 1.084018초, 최대2.710821초다.
이는 이미지 주기나 CSV 디스크 쓰기 주기가 아니다. wall clock 기반 기술 통계이며 센서의 물리 샘플
생성 간격·최소 변화 포착 능력·학습 적합성이나 운영 허용 기준으로 승인한 값이 아니다.
현재 데이터/설정/수집 주기를 바꾸지 않았고 추가 부하·현장 시험도 하지 않았다.

최신 canonical은 post120-cadence-csv-running-stage.json이다. exec78383만 진행 중이며 결과를 중복 실행하지 않는다.


## 2026-10-23 20:33 KST 정식 QA 선행 조건과 전체 완료 요구 대조

이전 turn은120분/정상 종료/이미지/시작/원장 대응을 완료하고 근거를 갱신한 PROGRESS다.
현재 CSV exec78383은 같은 실제 핸들033544에서 실행 중임을 확인했고 재실행하지 않았다.

후보commit의 qa_spot_temperature_v25.ps1 원문은 C31에서 사용한 동일 SHA d56d07e9…이다.
현재 C32 정상 종료 metadata/result 해시에 결합해9개 선행 조건을 대조했다(exit0, daef61).
미충족은 low_signal_comparator_verified=false 한 항목이다. 나머지8조건 확인은 전체 QA 합격률이
아니며 one-command QA는 실행하지 않았다. 실제 경계 시험 없이 플래그를 바꾸지 않는다.
근거: formal-qa-readiness-c32/review.json 및 변경을 입력 identity로 한정한 preparation.json.

C32 설치본164,158,258바이트/SHA558658cf…와 패키지 근거30파일을 새로 해시 대조했다(exit0,8693ec).
로컬 commit 태그와 원격 refs/tags/v1.0.32 조회는 모두 종료0/빈 결과였다. 아직 태그가 없으며 발행하지 않았다.
health의private F01 skip1을 다시 확인했고 환경 변수와지정3루트의 정확한 파일명 검색에서 자료를 찾지
못했다(rg exit1은일치없음,stderr없음). 이를전체디스크부재나통과로바꾸지 않는다.

[audit](C:/Users/user/Desktop/SmartFactory/F32CLOSE_20261023_cd46692a_R3/completion-audit/review.md)는
계획의R1–R6 DoD24개와4개목표를원문/증거29개에연결한다. audit actualexit0(56e9f4), 결과는
COMPLETION_NOT_PROVEN이다. 물리시험·공정허용지연·과거원자료/마감공백·현재CSV·정식QA·
운영승격·롤백기준갱신이남는다. 사용자미서명정책·원본보존/자료사용보류·LowSignalOFF제한을유지한다.

검증종료경계는닫힌logger9a245aa0의37,944행이다. 이후일반실행에서늘어나는모든자료까지끝없이
다시종료/검사하는조건으로바꾸지않는다. 새일반실행은수집/설정/화면복귀확인범위로별도기록한다.
최신canonical은completion-audited-csv-running-stage.json이며두현재상태사본과일치한다.
추가서버조작·설치·백업·설정변경·태그발행·기준갱신은없다. 목표active·출시HOLD·승격false다.
