# 프로덕션 출시 후속 PDCA 진행 기록

작성일: 2026-10-10. 전체 목표 진행 중, R1~R6 정식 출시 **HOLD**.
기준은 [원래 출시 계획](../01-plan/features/production-release-risk-validation-codex-production-release-risk-validation-20261010.plan.md)이다.
앞선 검토·초기 구현 요청의 완료와 이번 현장 PDCA 목표의 완료를 구분한다.

**현재 운영 정책(2026-10-12): 사용자는 인증서가 없으며 앞으로도 미서명으로만 운영하도록 지시했다.**
최종 clean commit의 미서명 내부 운영 설치본을 대상으로 계속 진행한다. 서명 인증서·담당자·
서명 빌드·유효 서명·서명자·타임스탬프 조건 및 인증서 답변 대기를 제거했다.
실제 `NotSigned`와 `signature_requirement=NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY`를 기록하고,
정확한 commit·SHA256·payload/provenance·설치/복구·장비/성능/전체 데이터·현장 QA는 유지한다.
서명 상태를 PASS로 바꾸지 않으며 R1~R6 전체 출시 HOLD는 남은 기술 검증에 따른다.
아래 과거 서명 조사 결과와 봉인 자료는 당시 사실로 보존한다.

2026-10-12 서버 연결이 복구돼 운영 AppData·설정·최신 metadata·health·현재 CSV 실물을 직접 확인했다.
최신 결과는 [서버 직접 확인 기록](production-release-risk-validation-server-read-20261012.report.md)에 연결한다.
아래 오프라인 내용은 2026-10-10 당시 기록이다. 전체 목표는 계속 진행 중이며 R1~R6 HOLD를 유지한다.

## Plan: 실행 조건과 원본 증거

- 사용자는 장비 프로파일·운영자 기록을 Codex가 서버에서 직접 확인하고, 유지보수는 언제든 수행해도 된다고 지시했다.
- Chrome 원격 목록에서 `DESKTOP-Extrusion`은 연결 링크 없이 마지막 온라인 오전 8:02로 표시됐다.
  연결 가능한 `회사컴터`에 접속하니 현재 개발 PC 자신이었다. 서버 작업을 수행하지 않고 목록으로 복귀했다.
  목록 새로고침 뒤에도 같은 서버 오프라인 상태를 확인했다. 유지보수 시간은 확정됐으므로 다시 묻지 않는다.
  당시 서버의 설정·승인 프로파일·운영자/검토자·실행 세대·데이터 전체 범위는 직접 확인하지 못했다.
- 최초 APPLY 원본 manifest의 17개 파일, 후속 POST의 64개 파일을 크기/SHA256으로 직접 대조했다.
  원본 파일과 manifest는 수정하지 않았다. 새 기록은 `Desktop/SmartFactory/PDCA_20261010_2702b6a0`에 있다.
- APPLY는 `post-sampling`의 `GetResponse` timeout이다. 요청 제한 5,000ms와
  health→spot/config 요청 순서, health 결과 존재·spot/config 결과 부재로 `/api/spot/config`를 추론한다.
  실제 서버 원인은 계속 `UNCONFIRMED`다.
- 원본 startup health는 362.4042ms, 다음 health는 26.2021ms다. 원본 `Sample`은
  UTF8 본문 변환과 `ConvertFrom-Json` 이후 Stopwatch 값을 읽는다. 별도 JSON 처리 시간이 없어
  이를 현재 수집기의 JSON parsing 제외 측정과 동일한 값으로 대조하거나 200ms 실패를 재분류하지 않는다.
  후속 첫 health 223.4887ms 기록도 유지한다.
- 과거 d7a1b20의 drop51/저장 실패16 기록과 이번 계획의 4c97d4a drop15는 다른 실행이다.
  같은 원인/손실로 합산하거나 최신 후보 실패로 귀속하지 않는다.

## Do: 실제 이미지 검사 보완

새 `scripts/validate_spot_image_files.py`와 backend 회귀 10건을 추가했다.
저장소 `.gitignore`에는 이 합성 회귀 파일 한 개만 기존 tests 허용 목록에 추가했다.

- 선택한 fact를 CSV로 순차 읽고 실제 파일의 SHA256·크기와 기록 값을 대조한다.
- Pillow의 구조 검사와 모든 프레임 `load()`를 수행한다. 잘린 픽셀, truncated 허용 모드,
  decompression bomb, 기록된 MIME/치수의 불일치를 실패로 남긴다.
- 디스크 SQLite 인덱스로 capture ID/경로 중복과 모든 capture 파일의 역참조를 확인한다.
  미참조 파일·임시/알 수 없는 파일을 조용히 제외하지 않는다.
  Windows의 대소문자 경로 별칭도 동일 파일로 정산하며 중복 참조를 검출한다.
- 전체 이미지 하위 폴더의 전후 파일 목록·stat identity·SHA256을 대조한다.
  같은 크기/mtime로 복원된 변조도 해시 차이로 검출한다. fact 전후 해시/identity도 검사한다.
- `..`·절대경로·UNC·ADS, symlink/reparse를 거부한다. 출력은 입력 사본 밖의 새 폴더에만 만들며
  기존 출력 재사용/덮어쓰기를 거부한다. 원본 자료를 삭제·수정하지 않는다.
- 결과는 `inventory-before.jsonl`, `inventory-after.jsonl`, `image-checks.jsonl`, `summary.json`이다.
  요약에 도구 SHA256과 fact 전후 SHA256을 남긴다.

개발 PC의 검증된 사본에 대한 실행 예:

```powershell
& .\backend\.venv\Scripts\python.exe scripts/validate_spot_image_files.py `
  --fact C:\Users\user\Desktop\SmartFactory\DATA_COPY\spot_image_fact.csv `
  --capture-root C:\Users\user\Desktop\SmartFactory\DATA_COPY\spot_images `
  --output-dir C:\Users\user\Desktop\SmartFactory\IMAGE_CHECK_NEW_RUN
```

fact 경로는 사본 log root 기준 상대경로여야 하고 capture root는 그 하위여야 한다.
다른 원본 capture 경로는 별도 복사 대응표로 연결하며 fact/원본을 재작성하지 않는다.
이 도구의 PASS는 **선택된 fact와 이미지 사본 범위**다. `full_data_gate=NOT_EVALUATED`를 유지한다.
전체 서버 snapshot의 원자성, 모든 CSV 스키마·metadata·observation·manifest·종료 영수증 및
시작/종료 delta의 전체 R4 검증은 기존 CSV validator와 별도 전체 목록 검증이 필요하다.

## Check: 이번 로컬 검증

| 검증 | 결과와 범위 |
|---|---|
| 잘린 JPEG regression | 모듈 없음 exit1 → 실제 해시 일치/전체 디코딩 실패 확인 exit0 |
| 역참조·원본 보존 regression | exit1 → exit0. 첫 구현의 SQLite 미종료/Windows 파일 점유 실패도 보존하고 연결 종료를 수정 |
| 중복 fact 고유 파일 수 regression | exit1 → exit0, 행 2건/고유 파일 1건 정산 |
| Windows 대소문자 경로 정산 regression | exit1 → exit0, 두 경로 별칭을 고유 파일 1건/중복 참조로 정산 |
| 경계 회귀 | 10건 통과, exit0. 해시/크기·경로·누락·다중 프레임·변경 탐지·출력 재사용 포함. Windows 조건 회귀도 이번 Windows 실행에서 skip 없이 통과 |
| 실제 CLI 규모 시험 | 최종 Windows 경로 수정 후 같은 합성 이미지 5,000개 전수 PASS, CLI exit0, 20.996초. fact 639,023바이트·이미지 3,225,000바이트. 최초 24.563초 결과도 보존. 서버 규모/성능 결과가 아님 |
| 실제 CLI 격리 장애 시험 | 최종 도구로 변조·누락·고아 각 1건 FAIL, 예상 CLI exit1을 확인한 시험 runner exit0 |
| 격리 저장 오류 주입 | ENOSPC·EACCES 두 독립 시험 PASS, exit0. 각각 failure1/drop0/write0, drain·정산 참, integrity_unresolved 참, 종료 gate 거부. 실제 디스크 채우기/ACL 변경/서버 장애 주입은 하지 않음 |
| focused ruff | 새 스크립트/시험 파일 검사 exit0 |
| 첫 전체 `npm run health` | exit0, backend910건(909통과/1skip), frontend Vitest434건 통과. 최종 Windows 경로 수정 전 결과로 보존 |
| 최종 전체 `npm run health` | exit0, backend911건(910통과/private F01 skip1), frontend Vitest434건·Electron94건·의존성14건·frontend Node9건 통과, ruff/mypy·QA selftest6개 통과. 01:11:49.152Z~01:17:12.332Z |

저장 오류 시험의 첫 시도는 하나의 unittest 안에서 두 subtest가 같은 프로세스 카운터를 공유해
두 번째 failure_count가 2가 되었다. `2 != 1` 실패 로그와 최초 시험 소스를 보존했다.
기존 프로세스 격리 fixture를 두 독립 시험에 각각 적용하자 통과했다. 제품의 누적 실패 보존 동작은 바꾸지 않았다.

private F01은 `TEMPERATURE_GOAL_PACKAGE`가 제공되지 않아 skip됐다. 초기 단계의 frontend build exit0은
기존 증거로 유지하며, 이번에는 frontend 변경이 없어 재빌드하지 않았다. 기존 npm 감사의 root high1/moderate8,
frontend high6/moderate2 항목과 런타임 영향 판정은 미해결이다. 로컬 검사 통과는 현장·서명 설치본 QA 통과가 아니다.

원격 master는 `eb9af6f1398d588733f3f1884411e2612496d267`을 확인했고 `v1.0.27` tag 조회는 결과가 없었다.
GitHub workflow_dispatch 실행 목록은 총 6건/6건을 반환했으며 `windows-signed-release.yml` 실행은 없었다.
이는 실제 서명 환경·인증서/비밀의 존재/승인 여부를 검증한 결과가 아니다. API의 workflow 경로 조회 거부는
승인된 `actions/runs` 조회로 보완했다. 최종 후보를 빌드하거나 workflow를 dispatch하지 않았다.

## Act: 남은 실행과 재개 조건

1. 서버 연결과 현재 운영 경로·실행 세대·과거 Operator1 기록은 직접 확인했다. 직접 답변 “모두 본인”으로 장비·운영 확인/QA/릴리즈 판단 책임자를 사용자 본인으로 확정했다. 승인 실장비 프로파일과 전체 과거/현재 데이터 범위는 이어서 확정한다.
2. 일관된 전체 사본·목록을 확보해 기존 스키마별 CSV 검사와 새 이미지 검사를 적용한다.
   과거 누락은 retention으로 추정하지 않고 근거·복구 가능성·데이터 책임자의 처리 결정을 연결한다.
3. 실제 규모의 초기화·동시 health, 전용 2초 sampler, 시작/화면/자원 계약과 격리 장애 재현을 완료한다.
4. R1~R5 및 보안 감사의 근거를 정리한 최종 clean 소스를 검토·병합한 뒤 정확한 commit/tag의 미서명 내부 운영 후보를 만든다.
5. 동일 설치본의 payload/출처/해시/NotSigned/설치/복구 및 현장 초기15분/canary120분/설정/데이터/동일 세대 종료를 검증한다.
6. 운영 승격·실제 적용 확인이 끝난 새 build/installer만 다음 rollback 기준으로 갱신한다.

서버 복사와 실행은 기존 [경로 정책](../V2/05_운영_배포/server_validation_path_policy.md)을 따른다.
2026-10-10에는 서버 전달·서버 실행·설정 변경·설치·롤백·기준 갱신이 없었다. 2026-10-12 직접 읽기/회수의 범위는 새 보고에 기록했다. 전체 목표와 R1~R6 DoD를 축소하지 않는다.

2026-10-12 회수 fact는 4,128,668행·2,115,849,144바이트로 API 해시와 일치하고 선택 전 행 기본 형식 검사 exit0이다.
과거 시작 metadata와 해시가 같은 4,091,827행 입력으로 실제 loopback `/api/spot/config`의 첫 5초 timeout을 재현하고,
설정 조회만 대기 없는 준비 상태 snapshot을 읽도록 보완했다. 수정 후 high-resolution HTTP 세 표본은
65.328/3.593/14.877ms, runner exit0이며 완료 후 원래 해시·행 수를 확인했다.
시작/종료 전수 검사와 미확인/fail-closed 계약은 유지한다.
상세 수정·회귀/전체 검사 결과는 [서버 직접 확인 보고](production-release-risk-validation-server-read-20261012.report.md)에 기록한다.
원본 timeout/drop15·현행 drop44의 인과, 전체 사본·현장 성능·최종 미서명 설치본 QA는 여전히 미완료다.

2026-10-12 서버 진단 51개 파일을 탐색기로 회수하고 공유·개발 사본 해시를 대조했다.
진단 JSONL 14,990행에서 parse 오류 0, 실패 journal의 값 해석 실패 746행과 장비 connect timeout 6행을 확인했다.
과거 이미지 큐 종료 실패를 별도 세대로 보존했고, 운영 541d의 설정 조회 성공 로그 생략도 실제 코드로 확인했다.
개발 PC의 NAS 전체 메타데이터 탐색은 1,029,146파일·200,089,154,934 bytes,
657.359초/exit0이며 전 행 고유 경로·수/크기 합계·manifest 해시 대조 exit0이다.
recycle·사본을 포함한 물리 목록으로, 전체 내용 검사나 서버 native NAS 실행을 대신하지 않는다.
상세 결과와 저장 공간/일관성 한계는 [서버 진단·전체 범위 기록](production-release-risk-validation-diagnostics-scope-20261012.report.md)에 연결한다.
전체 R1~R6 HOLD·full_data_gate=NOT_EVALUATED를 유지한다.

미서명 정책 반영 후 NAS 온도 하위 전체 1,471파일/27.53GB의 검증용 사본 작업을 완료했다.
모든 입력 스트림을 먼저 Read 공유로 열었고, session 79262는 5,791.790268초/exit 0,
원본 최종 재해시·사본 해시·전체 파일 집합/합계 정산이 일치했다.
전 사본 구조 검사 session 20569는 576,684,549기록을 읽고 19파일/33행 너비 불일치로 exit 1이다.
후속 원문 조사는 18파일 끝의 NUL 기록과 1파일의 15개 기록 조각을 확인했으며 실패 원문은 보존했다.
header 없는 2파일·과거 스키마/센서 의미·원인/복구/처리 판단은 미완료다.
ZIP 439개 중 437개의 중앙 목록을 읽어 내부 항목 1,055,977개를 정산했고 2개의 끝 정보 부재를 보존했다.
이는 압축 내용 CRC/전체 바이트 검사 완료가 아니다. 서버 탐색기에서 원래 NAS 주소와 온도 폴더도 직접 확인했다.
진행/완료 범위와 남은 전체 데이터 QA는 [온도 사본·압축 범위 기록](production-release-risk-validation-temperature-archive-20261012.report.md)에 연결한다.

같은 세대의 과거 종료 metadata와 종료 전 표본을 연결해 저장 실패 16건과 종료 경고의 의미를 대조했다.
`backend/app.py`의 경고 2곳만 실제 반환 조건에 맞게 정정했으며 최종 `npm run health` exit 0이다.
backend 915건 중 private F01 skip1, frontend Vitest 434건과 나머지 health 단계 통과를 실제 전체 출력으로 확인했다.
첫 직접 focused 실패와 격리 후 248건/exit 0, 미확정 과거 종료 상태는
[종료 경고 정정 기록](production-release-risk-validation-shutdown-warning-20261012.report.md)에 보존한다.

추가 장비 Time Functions 화면에서 5개 필터 bool과 이전 운영 metadata의 값이 일치함을 확인했다.
운영 model_info는 소프트웨어 설정값이고 실제 하드웨어 readback이 아님을 구분했다.
사용자는 실제 모델명/부품번호를 “미정”으로 답했으므로 답변 대기를 종료하고 해당 기술 확인은 미완료로 유지한다.
[장비 프로파일 추가 기록](production-release-risk-validation-device-profile-20261012.report.md)에 실제 화면·출처·한계를 연결한다.

93개 외부 원본의 핸들을 먼저 유지하고 내부 ZIP 161개/2,255,774,869 bytes의 사본 hash/원래 member CRC를 확인했다.
최초 중첩 경로 검사는 1,024작업/8단계 제한에서 exit 1이었다. 후속 실제 내용 해시 기준 정산은
121종류/45개 연결에 모든 초기 내부 항목과 미완료 경로 241개가 대응함을 확인해 exit 0이다.
일반 내부 파일의 전체 내용·스키마 QA는 별도 미완료이며 private F01도 발견하지 못했다.
현재 생산 의존성 범위 npm audit 두 건은 각각 exit 0/보고 취약점 0이지만 개발/빌드 도구와 최종 payload의 영향 판단을 대신하지 않는다.
[내부 압축 자료 기록](production-release-risk-validation-nested-archive-20261012.report.md)에 범위·실패·회복 정산과 남은 QA를 연결한다.

현재 생산 제품번호/금형번호는 사용자가 `60332, 6 유지`로 다시 확인했다.
서버 화면의 기존 적용값을 새로고침해 두 값과 Running을 확인했고 추가 제출은 하지 않았다.
선택 AppData 두 루트의 한 벌 사본 도우미를 새 서버 로컬 폴더까지 전달했으나,
실제 실행은 앱 종료 전 `alternate-data-stream` 사전 검사에서 HOLD했다.
읽기 전용 후속 진단은 `logs/test_data/CLOSE_ONCE_AFTER_APPROVAL.cmd`의
`:Zone.Identifier:$DATA` 26바이트를 첫 거절 원인으로 확인했다.
결과의 콘솔/공유/개발 사본 해시가 일치하며, 원본 스트림·앱·운영본은 유지했다.
추가 스트림 보존을 지원한 새 사본 도우미와 실제 사본/종료/재시작 검증은 미완료다.
[사본 사전 검사·추가 스트림 기록](production-release-risk-validation-cold-copy-20261012.report.md)에
개발 검사 21/58건, carrier 검사와 읽기 전용 4건, 실제 실패/회수/다음 실행 기준을 연결한다.

후속으로 추가 스트림 보존 엔진을 별도 구현했다. 실제 NTFS fixture와 2GiB 초과 파일을 포함한
native 94 assertions, 동일 세대/공간/ACL wrapper 43 checks, carrier 5 checks는 최종 exit 0이다.
새 7파일 묶음과 TXT를 서버 로컬까지 전달한 뒤 사용자가 실행했다.
실제 사전 목록은 314,592파일/245폴더/680추가 스트림, 총 55,560,334,970 bytes이며 공간 조건을 충족했다.
READY 확인 후 앱의 정상 닫기 버튼을 눌렀고 23:45:02 KST의 앱/backend/8000 부재 기록을 회수했다.
같은 `Qa0596a` 실행의 사본 작성이 진행 중이다. 후속 Electron 로그에서 동일 PID/세션의
비강제 종료(exit 0, forced=false, 8,242.5ms)를 확인했다. CSV 257,208행 순번과 마지막 행의
종료 metadata/logger 결합 검사 exit 0, backend 9개 종료 단계와 observation drain 성공을 확인했다.
종료 중 이미지 요청 `shutdown`/502 ERROR 4건은 그대로 보존했다. 최종 사본 해시·재시작과
전체 과거 데이터 검사는 아직 미완료다. 작업 정보 초기화 2회는 Count 59→0/41→0에 따른
기존 자동 초기화로 로그·CSV·운영 build 소스가 일치했다. 작업 정보나 해당 정책은 변경하지 않았다.
[추가 스트림 보존 사본 기록](production-release-risk-validation-stream-copy-20261012.report.md)에
변경·실패 보존·검증·전송·실제 실행 범위와 다음 기준을 연결한다. R1~R6 HOLD는 유지한다.

2026-10-13 선택 image fact 4,143,509행의 SQLite 정산은 103.298초/exit 0으로 완료했다.
ID/경로 중복 0, 초기 4,123,597행 prefix hash가 시작 metadata와 일치하며 추가 19,912행이
최종 written 및 현재 SPOT 세대와 일치한다. 개별 이미지 실물·drop 원인·전체 CSV 규칙은 별도다.
봉인된 내부 ZIP의 고유 내용 121개에 대해서도 일반 member 13,328개/4,770,179,392 bytes의
CRC·길이·SHA256 검사를 완료했다(29.445초/exit 0). 기본 JSON/JSONL/CSV 구문은 읽었지만
업무 스키마 의미·나머지 외부 ZIP 내용 QA는 미완료다. 기존 봉인 루트는 그대로 보존했다.

현재 닫힌 CSV의 전체 validator는 2,066.926초/exit 1로 종료했다. 실제 보고 실패는 운영 설정의
`config_operator_verified=false` 한 건이며 이를 유지한다. observation 207,561행·연결 257,188행과
image fact 4,143,509행의 hash/개수 대조는 일치했다. 개별 이미지·전체 서버 사본 QA는 별도다.
외부 ZIP 439개/58.29GB의 기본 바이트 사본도 시작했다. 원래 IP 접근의 인증 오류(exit 1)를 보존하고,
같은 NAS의 기존 Z 연결에서 전체 입력 크기/mtime 대조와 439개 Read 공유 핸들 선점을 완료했다.
새 session 42943의 실제 복사/해시 검증이 진행 중이며 최종 재해시 완료는 아직 아니다.

실제 대용량 image fact 검사의 메모리 사용을 줄이도록 validator의 해시/CSV 읽기를 순차 처리로
보완했다. 경로 해석·경계 확인 및 오류 순서는 유지했다. 변경 전 2만 행 메모리 재현은 exit 1,
변경 후 관련 82개 검사와 별도 84가지 전후 결과 대조는 exit 0이다. 실제 전체 입력의 전후
stdout/exit 대조(session 21403)와 실제 Python 메모리 관찰(39781)은 진행 중이다.
최종 health(83365)는 355.722초/exit 0으로 종료했고 backend 918개 중 기존 private F01 skip 1개,
frontend 434개 및 나머지 검사가 통과했다. 실제 서버 현장 QA와 전체 데이터 gate는 별도다.
서버 사본도 01:04 KST에 backup 199,884파일까지 진행 중이며 최종 검산·앱 재시작은 미완료다.

2026-10-13 01:43 후속 확인에서 실제 전체 입력 비교는 2,404.041초/exit 0으로 종료했다.
변경 전후 stdout은 동일하며 실제 validator exit 1(운영자 설정 확인 필수)은 유지된다.
입력 8개의 최종 hash를 다시 대조했고 실제 Python의 관측 OS peak는 4,161,220,608바이트였다.
완료 메모리/검사 증거 28파일만 별도 봉인·공유 검산했다. manifest SHA256은
`1b9827e8e9ed072f2c9a692b7092078a0bac720a83a50eac32f4a855224ea205`다.

서버 backup은 314,675파일/55,562,005,735바이트 표시 후 원본·사본 최종 검산 단계로 전환했다.
성공 result/hash 결합과 기존 앱 재시작은 아직 미완료다. NAS 외부 ZIP의 완료 사본 125개 시점에서
CSV member 5,909개를 검사했고, 과거 압출기 CSV 한 파일의 마지막 NUL 108바이트를 확인했다.
일반 CSV 검사 exit 1과 후속 형식 분류 exit 0을 구분하며 원인·영향은 미확인으로 유지한다.
전체 439개 압축 사본과 member 검사는 같은 작업으로 계속 진행 중이다.

02:04 KST에는 두 번째 손상 OCR ZIP의 전체 사본 대조를 마쳤다(exit 0).
정상 비교본과 앞 860,880,896바이트가 같고, 이후 2,272,588,647바이트가 전부 0임을 확인했다.
실제 손상 원인·사라진 원래 바이트·복구 완료로 확대하지 않으며 두 손상 ZIP의 실패를 유지한다.
외부 ZIP 원본의 마지막 재해시와 서버 cold copy의 최종 검산은 계속 진행 중이다.

추가로 [과거 PLC CSV 사본 검사](production-release-risk-validation-plc-csv-20261013.report.md)를
착수했다. 기존 전체 NAS 목록에 결합된 127,158파일/972,602,108바이트 범위이며,
최종 도우미 로컬 fixture 11개 exit 0 후 session 40390에서 원본 목록을 대조 중이다.
독립 CSV마다 Read 공유를 유지하며, 전체 원본 핸들을 동시에 잠근 NAS snapshot으로 주장하지 않는다.
최종 사본/원본 hash·전후 목록·모든 CSV 행 검사 결과가 나오기 전까지 미완료로 유지한다.

02:30 KST 후속 기록: 외부 ZIP 439개 사본의 내용 결과가 모두 기록됐으며, 원본의 마지막 재해시를
기다린다. 두 손상 ZIP은 계속 실패이며 읽을 수 있는 고유 member는 1,036,015개/130.46GB다.
앞선 선택과 겹치지 않는 CSV 11,137개/28.07GB를 bounded-read 파서로 검사 중이다(session 38762).
기존 결과 대조 18개와 20MiB 메모리 fixture/시간 제한 검사는 exit 0이었다.

과거 PLC CSV의 첫 느린 목록 조사(40390)는 검증된 대체 경로가 마련된 뒤 소유 프로세스만
종료해 보존했다(exit 1, 원본 불일치 판정 아님). 대체 경로의 폴더 보호 초기 시험 실패도 보존하고,
수정 후 로컬/NAS 핸들 16개·사본 연계 15개 시험 exit 0을 확인했다. 새 전체 목록 사전 대조는
session 4030에서 진행 중이며 원본 CSV 사본 생성은 아직이다. 서버 최종 검산도 02:28 KST에
162,882파일 누적 읽기까지 진행 중이다. 기존 앱은 계속 닫혀 있고 재시작·수집 재개 확인은 남아 있다.

02:39 KST 기록: 추가 CSV 11,137개/28.07GB의 검사가 397.187초/exit 1로 종료했다.
149개 finding은 BOM만 있는 이벤트 내보내기 78개, 과거 Rect header 9열/본문 4열 자료 70개,
matplotlib 주석 예제 1개로 분류했다. 원인·이벤트/업무 완전성 승인은 아니며 원문은 보존했다.
결과 정산 및 남은 member 실제 바이트 재검산은 각각 exit 0이다.

PLC 목록 trial 4030은 10만 파일 진행 뒤 15분 제한으로 종료했다(exit 1, 목록 일치/불일치 미확정).
최종 도우미의 반환값/실제 종료 코드를 보완한 18개 시험 exit 0 후, 기존 6시간 전체 예산의
본 작업을 session 78990 / PID 37268로 시작했다. 처음 전체 목록 대조부터 진행하며
서버 앱 재시작·운영 승격·새 설치본 적용과는 별개다.

외부 ZIP 내용 검사를 source 사본 작업과 연결해 시작했다(session 96822). 도우미 fixture 10개는
exit 0이며 01:26 KST까지 103사본을 처리했다. 84번 portable의 BadZipFile은 보존했고,
완료한 고유 member 834,349개/60.74GB의 EOF·CRC·길이·SHA256 결과를 저장했다.
손상 portable은 정상 비교본과 앞 210MiB가 같고 뒤 160,824,015바이트가 모두 0임을 전수 비교했다.
정상 비교본 자체의 내용 검사는 통과했지만 손상 원인의 확정이나 원래 뒷부분 복원 증거로 바꾸지 않는다.
다른 손상 OCR ZIP도 별도 정상 비교본과 앞/뒤 표본을 대조했고, 전체 사본 회수 후 비교를 이어간다.
[외부 압축 내용·손상 비교 기록](production-release-risk-validation-temperature-archive-20261012.report.md)에
도우미·진행 수치·hash·실패·복구 한계를 연결한다. 서버는 01:25 KST에 backup 267,307파일,
48,059,859,483바이트를 표시했으며 같은 실행의 최종 Verify/result와 앱 재시작은 아직이다.

## 2026-10-13 03:00 KST 빌드 의존성 후속 검증

기존 감사의 `source-map-js` indexed source map 문제를
[공식 수정 commit](https://github.com/7rulnik/source-map-js/commit/cf76580)과
[수정 버전 공지](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)로 확인했다.
생성자만 호출하는 제한된 fixture에서 과도한 단일/중첩 offset을 거부하도록 회귀를 추가했다.
큰 mapping을 실제로 직렬화하거나 확장하지 않았다. 기존 1.2.1에서는 예상 예외가 없어 exit 1,
기존 semver 범위 안의 1.2.2 적용 후 의존성 회귀 15건은 exit 0이다.
`frontend/package-lock.json`의 해당 패키지 version/resolved/integrity만 바뀌었으며
root package/lock과 frontend package 정의는 전후 SHA256이 같다.

| 검사 | 실제 결과 |
|---|---|
| `npm --prefix frontend run postinstall` | exit 0, 기존 Grafana patch·Router 계약 확인 |
| `npm run health` | 318.084초, exit 0. 의존성 15·Electron 94·frontend Node 9·Vitest 434 통과, ruff/mypy 통과 |
| backend·QA self-test | backend 918건 중 917통과/private F01 skip 1, QA self-test 통과. F01 환경 변수 미제공 확인 |
| `npm --prefix frontend run build` | 17.448초, exit 0. production Router graph 계약 통과 |
| frontend 전체 npm audit | exit 1, high 5/moderate 2. source-map-js 항목 제거, 다른 잔여 항목 유지 |
| frontend `--omit=dev` audit | exit 0, 보고된 취약점 0. 실제 NSIS payload 검증을 대체하지 않음 |
| root 전체 npm audit | exit 1, high 1/moderate 8 유지. 이번 root 의존성 변경 없음 |

Node 22.22.2/npm 10.9.7 환경이다. health의 의도된 오류 fixture·Starlette deprecation/asyncio
관측 출력, 빌드의 zod 주석 위치 경고 2개를 원문으로 보존했다. 경고 없는 실행으로 표시하지 않는다.
검증 자료는 `C:/Users/user/Desktop/SmartFactory/PDCA_BUILD_AUDIT_20261013_f6c82a19`에 있다.
`verify-build-audit.py`의 전후 lock·종료 코드·전체 로그/감사 정산은 exit 0이고,
`verification.json` SHA256은 `11a7009e985cf325ed2c001de64f218981fa468522ab55752080bc8270a2e159`다.
서버 설치·후보 NSIS 빌드·운영 승격은 수행하지 않았으며 전체 목표 active/R1~R6 HOLD를 유지한다.

## 2026-10-13 서버 사본 검산 완료와 기존 운영본 재시작

[추가 스트림 사본 결과](production-release-risk-validation-stream-copy-20261012.report.md#2026-10-13-0310-완료-결과와-0326-이후-재시작)를
03:23 KST 공유 폴더로 회수했다. 콘솔/파일 SHA256, 전체 manifest의 파일 314,675·폴더 245·
추가 스트림 680개 및 55,562,005,735바이트 정산, 기존 닫힌 입력 8개 결합 검사는 exit 0이다.
최초 콘솔 해시 전사 오기는 원본 화면과 파일을 재대조해 새 영수증에 정정했고 이전 기록을 보존했다.

기존 541d 운영 앱을 정상 시작하고 REAL 수집, 새 backend/logger/SPOT 세대, CSV 저장 재개,
제품/금형 `60332 / 6` 지속성을 확인했다. API 두 표본은 poll 312→375·수집 행 1,413→1,678,
회수된 실제 CSV 사본은 seq 1~1,783·2,266,874바이트였다. 읽기/대조 스크립트 모두 exit 0이다.
이후 UI Warning을 관측해 03:36~03:37의 이미지 502/`SpotTransportConnectTimeout` 3건과
transport correlation ID를 대조했다. capture writer failure/drop 0과 upstream timeout은 구분한다.
앱은 실행 중이며 config fingerprint mismatch, 초기 stale 172행, timeout 원인 및 전체 데이터 QA는
해결된 것으로 표시하지 않는다. 후속 자료는 같은 private stage의 `restart-review.json`과
`restart-warning-review.json`에 있다. 설치·승격·기준 갱신 없이 전체 목표 active/R1~R6 HOLD다.

빌드 의존성의 `http-cache-semantics`도 별도 합성 정책 fixture로 조사했다.
[공식 GHSA](https://github.com/advisories/GHSA-ch52-4w7c-c8xp)의 max-stale/Set-Cookie 상황을
현재 4.2.0과 npm registry의 별도 4.3.0 바이트에서 재현했다(exit 0: 양쪽 모두 같은 동작 확인).
실제 HTTP 요청·실제 쿠키 없이 정책 객체만 평가했고 4.3.0 tarball의 registry SHA512를 대조했다.
4.3.0을 해결책으로 적용하지 않았으며 현재 설치 의존성을 추가 변경하지 않았다.
실제 Electron 다운로드 경로의 노출·악용 여부는 미확인이다. 자료는
`C:/Users/user/Desktop/SmartFactory/PDCA_CACHE_AUDIT_20261013_92d034cb`에 보존한다.
앞선 source-map-js 변경 후 전체 health/build 결과는 그대로 유지하며 잔여 npm audit HOLD를 해제하지 않는다.

추가 이미지 manifest 연결 검사에서는 312,969개 경로·크기·해시가 일치했고 불일치 0,
현재 capture root에 없는 과거 fact 참조 3,830,540개·미참조 파일 16개를 보존했다(exit 1).
닫힌 직전 세대의 19,912개는 모두 일치했다. 누락의 실제 원인·백업 존재·디코딩은 미확인이다.
정산 검사는 exit 0이며 [상세 사본 기록](production-release-risk-validation-stream-copy-20261012.report.md#이미지-기록과-cold-manifest의-전체-연결-대조)에 연결한다.

03:47 KST NAS archive 사본 439개의 원본 최종 재해시가 exit 0으로 끝났다.
압축 내용 검사는 기존 손상 ZIP 2개를 유지해 exit 1이고, 콘솔 hash·전체 영수증·SQLite 정산은 exit 0이다.
[종료 결과](production-release-risk-validation-temperature-archive-20261012.report.md#2026-10-13-0347-kst-외부-zip-사본내용-검사-종료)에
각 범위와 421고유 내용/1,036,015 member 검산을 기록했다. 과거 PLC CSV 127,158개 작업은
초기 전체 목록 대조 뒤 같은 session 78990에서 진행 중이며, 최신 완료 표본 1,000파일/4,157,129바이트의
구조 finding은 0이다. 전체 PLC 사본·최종 원본/목록 대조 완료로 표시하지 않는다.


## 2026-10-13 04시 후속 관찰과 이미지 복구 후보

서버는 같은 logger 세대에서 Running을 유지했다. 영상 오류 큐 6건과 전체 SPOT transport 실패 13건을 구분하고, 운영 원문의 correlation ID 처리 차이를 확인했다. 03:58:41 KST 실제 operator 입력이 `60192 / 17`로 바뀌었고 Codex는 적용하지 않았다.

과거 없는 이미지 참조 3,830,540개를 읽을 수 있는 NAS archive 일반 member 1,031,166개 및 cold 사본의 내용 해시와 대조했으나 일치 0이었다. retention 원인은 확정하지 않는다. 기존 NAS 목록에서 선택한 이미지 20,157개/449,350,328바이트의 사본·전체 디코딩·최종 원본 재해시를 session 70742로 시작했다. 6개 도우미 시험 exit 0, 초반 0바이트 recycle 이미지 2개는 finding으로 보존했다.

[상세 증거·정정·진행 상태](production-release-risk-validation-image-recovery-20261013.report.md)를 따른다. PLC/NAS 이미지 실제 종료와 서버 이미지 decode는 아직이며 전체 R1~R6 HOLD를 유지한다.


## 2026-10-13 이미지 사본 검사 최종 결과

NAS 선택 이미지 20,157개의 사본과 최종 원본 재해시를 완료했다. 디코딩 PASS 20,154,
과거 recycle 0바이트 FAIL 3으로 실제 exit 1이었다. 없는 참조 중 7건의 동일 바이트를 찾아
격리 복구 후보로 보존하고 독립 검증했다. 운영 원본에 복원하지 않았다.
서버 cold 이미지 ZIP은 312,985파일의 개별 해시·크기·디코딩을 모두 확인해 실제 exit 0이었다.
미참조 16개는 정상 이미지이며 같은 service의 18.876658초 fact 간격에 모이지만 원인은 미확정이다.
[최종 수량·해시·범위](production-release-risk-validation-image-recovery-20261013.report.md)를 따른다.
PLC는 마지막 `original_source_final_recheck` 18,000파일로 아직 종료 전이다.
제품 코드·설치본·롤백 기준 변경 없이 R1~R6 정식 출시 HOLD를 유지한다.


## 2026-10-13 저장 실패 추적 정보 보완

서버 cold 로그 45파일의 해시를 확인하고 기존 PID 12156의 실패 16건을 재대조했다.
개별 오류 원인은 미확정이다. 현재 경고의 시각·예외·capture 식별자 누락을 보완했다.
회복 후 고립 이미지 식별과 큐/종료 회귀 5개, 최종 전체 health는 실제 exit 0이었다.
backend 920개 중 919통과·기존 private fixture 1생략이다.
[회수 범위·수정 전후 검사](production-release-risk-validation-image-recovery-20261013.report.md#2026-10-13-서버-로그-회수와-저장-실패-기록-보완)를 따른다.
제품 변경은 로컬 검증 단계이며 서버 적용·운영 승격은 수행하지 않았다.
PLC `original_source_final_recheck` 96000파일 관측, 전체 종료 전이다.
R1–R6 HOLD 및 기존 운영본/다음 롤백 기준을 유지한다.


## 2026-10-13 PLC 사본 종료와 실제 입력 반복 계측

PLC 선택 127,158파일의 사본/구조/최종 원본 및 목록 대조가 실제 exit 0으로 끝났다.
15,454,901행 중 빈 행 125,385개이며 구조 finding은 0이다. 업무 의미 검증은 남아 있다.
[최종 수량과 해시](production-release-risk-validation-plc-csv-20261013.report.md#2026-10-13-0528-kst-plc-사본-검사-종료)를 따른다.
같은 최종 소스와 과거 2GB fact로 독립 process 10회를 계측했다. HTTP 142개 중
health 112개·초기화 중 health 82개, 오류/timeout/200ms 초과 0, 최대 32.9487ms다.
[실제 조건·원문 대조·제한](production-release-risk-validation-server-read-20261012.report.md#2026-10-13-실제-과거-fact의-10회-동시-http-계측)에 기록했다.
API 격리 시험이며 전체 앱/현장 성능 PASS가 아니다. 원래 원인 미확정·장비 설정·전체 데이터 의미 검증·
최종 clean 미서명 패키지/설치/복구/현장 QA는 미완료다. R1–R6 HOLD와 목표 active를 유지한다.

## 2026-10-13 PLC 값·시간 전수 검사

PLC 사본 127,158파일의 15,329,516개 데이터 행 및 107,306,612개 숫자 값을 검사했다.
관찰 형식 문법 finding 0, 실제 exit 0이며 원장 독립 정산과 별도 시간 파서 대조도 exit 0이다.
원시의 비자정 시각 감소 6건, 날짜를 유지한 정리 파일의 자정 경계 15건과 0.04초 감소 1건,
인접 동일 행 원시 24/정리 19쌍을 원문 위치와 함께 보존했다. 과거 날짜/값을 보정하지 않았다.
[전체 수량·원문 예·검사 범위](production-release-risk-validation-plc-csv-20261013.report.md#2026-10-13-0554-kst-plc-값시간-전수-검사)를 따른다.
원 생산기 계약과 업무 의미·순서 현상의 원인은 아직 미확인이다. 전체 R4/출시 PASS로 확장하지 않으며
목표 active, full_data_gate=NOT_EVALUATED 및 R1–R6 HOLD를 유지한다.

## 2026-10-13 전체 앱 격리 초기 시작 10회

현재 소스의 Electron 화면·backend lifespan·실제 CSV/fact 사본·합성 SPOT으로
정상 시작/수집/종료 10회를 계측했다. 준비 10.13~13.15초, health 192개 최대 35.1973ms,
data 70개 최대 25.8825ms, 계획된 HTTP 282개 오류/timeout/각 시간 상한 초과 0이었다.
새 CSV 1,511행·이미지 360개, 기존 fact prefix, 세대별 closeout와 최종 manifest를 독립 검산했다.
도우미 회귀 8개, 최종 검산·원본/현재 소스 대조·정적 검사·공유 보존은 실제 exit 0이다.

실패한 준비 시행과 도우미/검산 조건 정정은 원문·해시와 함께 보존했다.
별도로 각 초기 UI의 layout 404 및 정상 종료 시작 뒤 이미지 502 14건이 남아 있다.
[실제 조건·원시 지표·예외·해시](production-release-risk-validation-app-start-20261013.report.md)를 따른다.
전체 R2 자원/다중 탭/계측 off/화면 성능/현장 시작 및 최종 clean 미서명 설치본 QA는 남아 있다.
운영 서버 변경 없이 전체 목표 active, full_data_gate=NOT_EVALUATED와 R1–R6 HOLD를 유지한다.

## 2026-10-13 단일 화면 120초 준비·300초 자원 관측

큰 fact/실제 CSV 사본과 합성 SPOT으로 native Electron 화면 1개를 계측했다.
관측 61표본/300.0002초, backend/collector 각각 고유 60표본/296.2290초를 독립 검산했다.
계획 HTTP 464개 모두 성공, health 최대 32.4872ms이며 새 CSV 1,825행·이미지 389개와
기존 fact prefix·같은 세대의 정상 종료를 확인했다. 주 실행·독립 검산·공유 보존은 실제 exit 0이다.

화면 renderer의 첫/끝 20% 평균 RSS가 +143.27 MiB, 전체 프로세스 합계는 +158.07 MiB였다.
CSV queue 최대 1/5,000·drop 0이지만 메모리 증가 원인은 미확정이며 자원 안정성 PASS가 아니다.
종료 시작 뒤 이미지 502 한 건도 보존했다.
[입력·측정·증가 추세·검증·증거 해시](production-release-risk-validation-runtime-performance-20261013.report.md)를 따른다.
동일 브라우저 1/3탭·계측 off·화면 표시/열린 파일·현장 시작·최종 미서명 패키지 QA는 남아 있다.
이번 단계에서 제품/서버를 변경하지 않았으며 전체 목표 active와 R1–R6 HOLD를 유지한다.

## 2026-10-13 renderer 메모리 수명 후속 관측

격리 앱에서 120초 준비+300초 baseline과 GC 뒤 추가 300초를 관측했다.
계획 HTTP 804개·새 CSV 2,867행·이미지 662개·정상 종료 및 원본 prefix를 독립 검산했고
주 실행/USS companion/최종 검산은 실제 exit 0이다. 실패한 초기 도우미 실행은 보존했다.

49개 CDP 표본에서 활성 URL 1개/순간 최대 2개를 유지했다. 두 GC 직후 비교는
JS heap +0.75 MiB/RSS +1.24 MiB/DOM -9개/listener 변화 0이었다.
회수 가능한 메모리의 기여는 확인했지만 초기 RSS 증가 전체의 원인과 장기 안정성은 미확정이다.
30초 일반 파일 열거와 후반 USS 부분 측정의 한계를 포함해
[수명 진단 결과](production-release-risk-validation-runtime-performance-20261013.report.md#2026-10-13-0744-kst-renderer-수명-후속-진단)에 기록했다.
다음은 Blink 캐시 분리 관찰과 URL 교체 패턴 격리 재현이며 제품/서버 변경·승격은 수행하지 않았다.
전체 목표 active, full_data_gate=NOT_EVALUATED 및 R1–R6 HOLD를 유지한다.

## 2026-10-13 이미지 URL 교체·캐시 격리 비교

조건별 120초 준비+300초 관측, 각각 1,619프레임/이미지 오류 0/정상 종료를 검산했다.
URL 교체의 RSS 평균 변화는 +58.65 MiB, 재사용은 +3.73 MiB였다.
USS는 각각 +3.05/+3.67 MiB였고 활성 URL과 이미지 캐시 항목은 모두 1개였다.
교체 패턴에서 RSS 증가가 재현됐지만 전체 앱 증가 원인·누수·장기 안정성은 미확정이다.
[실제 조건·원시 검산·개입·증거 해시](production-release-risk-validation-runtime-performance-20261013.report.md#image-cache-comparison-20261013)에 기록했다.

주 실행 두 개, native smoke 두 개, 최종 검산/회귀/정적 검사/공유 보존은 실제 exit 0이다.
숨겨진 작은 화면과 동일 JPEG의 조건별 단일 시행으로 실제 화면·계측 off 검사를 대체하지 않는다.
제품/서버 변경 없이 실제 상주 페이지 종류와 보이는 전체 앱의 캐시/그리기를 후속 확인한다.
전체 목표 active, full_data_gate=NOT_EVALUATED 및 R1–R6 HOLD를 유지한다.

## 2026-10-13 renderer 상주 페이지 종류 대조

재사용→교체 순서에서도 300초 RSS 평균 변화 +3.95/+60.13 MiB가 재현됐다.
각 1,618프레임·오류 0·정상 종료와 상주 페이지 5표본씩을 검산했다.
약 125→405초의 두 표본에서 교체 상주 증가량 77,377,536바이트 중 90.43%가
공유 속성을 가진 MEM_MAPPED 순증가였다. 실제 객체/전체 앱 원인은 미확정이다.
[원시 목록·종류별 정산·RSS 잔차·제한·보존 해시](production-release-risk-validation-runtime-performance-20261013.report.md#resident-page-attribution-20261013)에 기록했다.

주 실행 두 개·native/self smoke·회귀·정적 검사·공유 보존은 실제 exit 0이다.
파일명 조회 실패와 RSS 잔차를 보존했고, 공유 메모리를 무비용/누수 아님으로 판단하지 않았다.
다음은 Chromium 내부 할당기 소유 관계와 보이는 전체 앱의 검증이다.
제품/서버 변경 없이 목표 active, full_data_gate=NOT_EVALUATED 및 R1–R6 HOLD를 유지한다.

## 2026-10-13 memory-infra 소유 관계 확인·전체 앱 표시 조건 실패

작은 시험의 이미지 캐시 → discardable 소유 관계를 실제 Chromium 기록으로 확인했다.
전체 앱은 HTTP 474회·CSV 1,897행·이미지 53개·정상 종료 검산을 통과했으나,
창이 준비 구간부터 숨겨져 300초 동안 이미지 표시 횟수가 39회에 머물렀다.
따라서 보이는 전체 앱 메모리 비교는 무효이며 RSS 감소를 개선으로 해석하지 않는다.
[표시 조건·미보고 크기·분석기 보완·원시 근거·보존 해시](production-release-risk-validation-runtime-performance-20261013.report.md#memory-infra-attribution-20261013)에 기록했다.

미보고 allocator 크기 처리 회귀 4개·수정 검산·정적 검사·공유 보존은 실제 exit 0이다.
초기 분석 실패와 표시 조건 실패를 보존했다. 다음은 준비 구간의 창 상태/프레임 갱신 확인이다.
제품/서버 변경 없이 목표 active, full_data_gate=NOT_EVALUATED 및 R1–R6 HOLD를 유지한다.

## 2026-10-13 표시 상태의 전체 앱 이미지 캐시 증가 확인

29개 renderer 표본과 440개 native 기록에서 표시/비최소화 조건을 유지했다.
이미지 캐시는 약 164MiB→312.5MiB, 같은 관측 구간의 renderer RSS 처음/마지막 평균은
약 124.25MiB 증가했다. 모든 이미지 항목의 discardable 소유 관계를 확인해 구체적인
기여 경로를 확보했다. 1,000개 항목의 짧은 종료 관측을 장기 안정성이나 RSS 상한으로
해석하지 않는다. [수치·실패 원문·압축/계측 조건·보존 해시](production-release-risk-validation-runtime-performance-20261013.report.md#visible-app-cache-growth-20261013)에 기록했다.

HTTP 472회·새 CSV 1,759행·이미지 392개·정상 종료 검산, 도우미 회귀·정적 검사,
2,103개 입력 파일의 보존은 exit 0이었다. 종료 시작 후 별도 UI 이미지 502 한 건과
초기 복사/수집 실패를 보존했다. 제품·서버 변경은 없다. 다음은 동일 브라우저의
1개/3개 탭과 계측을 끈 표시 성능이다. 전체 목표 active, R1–R6 HOLD를 유지한다.

## 2026-10-13 실제 같은 브라우저 1개·3개 탭 비교

사용자가 시험 창 유지 가능 시간을 확인한 후 동일 비압축 초기 데이터로 각 조건의
120초 준비+300초 관측을 완료했다. 두 조건의 HTTP 477/503회, 새 CSV 2,041/2,178행,
이미지 389/391개와 정상 종료를 검산했다. health 최대 30.55/32.68ms,
탭별 LCP 1512 및 1448/448/384ms, CLS 모두 0.022 미만이었다.
3개 탭은 한 창에서 전면 1개·숨김 2개였고 숨김 탭의 이미지 갱신은 정지했다.
[조건·수치·실패 원문·보존 해시](production-release-risk-validation-runtime-performance-20261013.report.md#same-browser-one-three-tabs-20261013)에 기록했다.

RSS는 두 조건 모두 증가했으며, 기본 레이아웃 부재의 404 2/6회를 보존했다.
최종 검산·정적 검사·공유 보존은 exit 0이다. 제품/서버 변경은 없다.
계측 OFF·필요한 물리 디스크 관측 및 남은 후보/현장 조건은 미완료이며 R1–R6 HOLD를 유지한다.


## 2026-10-13 추가 backend 계측 부담 검증

[동일 입력 ON/OFF 비교](production-release-risk-validation-runtime-performance-20261013.report.md#supplemental-backend-probe-overhead-20261013)를 완료했다.
OFF→ON→ON→OFF 네 회의 요청 2,920개에서 실패·200ms health 초과 0, 최대 health 46.831ms였다.
측정 health 평균 OFF 6.0804ms/ON 10.9042ms로 차이 +4.8238ms를 기록했고 계측 영향 없음으로 해석하지 않았다.
새 CSV 2,413행·이미지 508개·원래 fact 접두부·동일 세대 정상 종료를 검증했다.
공통 host disk counters와 ON 추가 프로세스/API 표본도 보존했다. 30/120초 backend 시험은
전면 브라우저/CDP OFF나 정식 자원·실장비 QA를 대체하지 않는다.
수집/각 검산/최종 검산/봉인 모두 실제 exit 0이며 제품 소스가 같아 전체 health는 반복하지 않았다.
전체 목표 active, R1–R6 HOLD, full_data_gate=NOT_EVALUATED 및 미서명 내부 운영 정책을 유지한다.


## 2026-10-13 출시 잠금 환경 사전 검증

[출시 환경 사전 검증](production-release-risk-validation-candidate-preflight-20261013.report.md)에
개발 환경과 잠금 파일의 9개 버전 차이, 새 40개 wheel 해시/버전 확인, pip check/Ruff/mypy exit 0을 기록했다.
최신 backend CLI는 920개 중 919개 통과·비공개 F01 1개 건너뜀으로 actual exit 0이었다.
앞선 두 전체 실행의 종료 receipt timeout은 원인 미확정이며, 초기 인코딩 오류와 후속 JSON
기록 오류는 도우미 실패로 별도 보존했다. 246개 부분 검사 5회 통과도 실패 해결로 해석하지 않았다.
root/frontend npm audit는 high 1/5를 포함해 각각 exit 1이다.
627개 증거 파일의 스냅샷 검산·공유 보존 exit 0이며 설치 환경 바이너리/cache는 명시적으로 제외했다.
제품·기존 개발 환경·서버 변경은 없다. 최종 빌드와 설치/현장 QA는 진행하지 않았고,
전체 목표 active, 미서명 내부 운영 정책, R1–R6 HOLD와 full_data_gate=NOT_EVALUATED를 유지한다.

## 2026-10-13 v1.0.27 미서명 후보 빌드·정적 검증

clean `19e0e314f7c1dc29b38691382aeda637f4ff3032`에서 미서명 v1.0.27을 만들었다.
installer SHA256은 `f17040fc65d5856c29b04c2b919c6a4bebfca46520dccbb3ea046de2c034166d`다.
clean checkout에서 빠졌던 기존 테스트 17개를 추적하도록 보완한 뒤 출시 잠금 환경의
전체 health exit 0(backend 919통과/비공개 F01 1skip), 빌드·정적 패키지 검사 exit 0을 확인했다.
실제 installer payload 1,814파일, frontend 50파일의 두 배치, backend manifest 1,687파일,
ASAR 소스·provenance 및 installer/앱/backend의 `NotSigned`를 검증했다.

[상세 범위·실패 원문·소스/설치본 identity·보존 해시](production-release-risk-validation-unsigned-candidate-20261013.report.md)를 따른다.
275개 입력 파일과 ZIP/공유 사본 검산 exit 0이며 환경/cache·합성 ADS fixture는 제외했다.
간헐 종료 timeout 원인·npm audit 항목·tzdata 빌드 경고와 실제 런타임/설치/업그레이드/복구/
현장 QA는 남아 있다. 서버 적용·승격·기준 갱신은 수행하지 않았다.
전체 목표 active, R1–R6 HOLD와 full_data_gate=NOT_EVALUATED를 유지한다.
