# 고정 요청 기반 현장 도우미와 실행기 검증

작성일: 2026-10-14 KST. 도우미 빌드 소스: `c98a7b1e8a58e89825c33d99dd611d515ef686ae`.
범위: 개발 PC의 격리 사본 검사, native Windows 실행 감독, 서버 로컬 패키지 전달.

## 결과와 범위

관찰/종료 사본 QA 모듈을 `field_runner.exe`로 묶고, 요청 SHA와 실행기 SHA를 고정하는
진입 명령을 연결했다. Python9시험, native12조건, portable6실행, 최종 bootstrap4조건이
각각 예상 결과와 일치했다. 빌드·최종 감사·Ruff F/E9·Git diff/show 검사는 exit0이다.
미서명 내부 운영 승인에 따른 `UNSIGNED_INTERNAL`을 유지한다.

서버 `C:/Users/user/Desktop/SmartFactory/RUN128_20261014_f1378d29`에 8파일을 복사하고
2026-10-14 04:47 KST에 탐색기의 실제 절대경로와 파일 목록을 확인했다.
서버 로컬 해시·관리자 실행·최종 현장 요청은 아직 미검증이다. 패키지 전달은 현장 실행 완료가 아니다.
R1–R6 HOLD, full_data_gate NOT_EVALUATED, promotion_allowed=false를 유지한다.
운영본/다음 롤백541d/08C, 제품 후보4cc/882 및 기존 승인 조건은 바꾸지 않았다.

## 실행과 보호 경계

- `field_runner.py`: 외부 SHA로 잠긴 요청, 정확한 후보/정책/필드, 관찰900/7200초 조건을 확인한다.
  원문 요청·단계 결과·전체 결과 파일 목록/크기/SHA를 새 session에 보존한다.
  정상 종료 기대값과 설정 기준이 맞는 경우에만 두 고정 검사 EXE를 실행한다.
- `invoke-field-run.template.ps1`: 관리자 Windows PowerShell5.1 x64에서 새 결과 자식의
  관리자/SYSTEM 쓰기·운영자 읽기 ACL을 만들고 패키지/요청을 읽기 공유로 잠근다.
  EXE를 suspended 상태로 만들고 이름 없는 Windows Job에 등록한 뒤 실행한다.
  stdin/stdout/stderr만 상속하며 실제 앱은 Job에 넣지 않는다. 앱 설치·종료·재시작 기능은 없다.
- 실제 exit, 시간/출력 예산, Job 잔존, 결과 파일 집합/해시와 frozen 상태를 대조한다.
  timeout·잔류 자손·감독자 손실에서는 소유한 검사 자손만 정리하고 FAIL을 유지한다.
- `run-launch.template.txt`: 외부 길이/SHA에 맞는 동일 잠금 controller 바이트를 실행한다.
  native PS5.1 NoProfile과 제한된 PATH/PSModulePath를 사용하고 요청 경로/SHA를 전달한다.
  아직 현장용 요청을 만들지 않았으므로 이 template을 실행 가능한 현장 명령으로 보고하지 않는다.

일반 파일 잠금과 새 자식 ACL은 관리자나 부모 소유자의 적대적 경로 교체에 대한 완전한
보안 경계가 아니다. 개발 PC의 현재 토큰은 비관리자다. 실제 운영 ACL 적용 PASS를 주장하지 않는다.

## 빌드와 바이트 식별

clean c98a7b1e의 Git 원문27파일에서 PyInstaller6.20.0/Python3.12.6으로 빌드했다.
빌드 전후 Git 상태·HEAD·의존성 목록·추출 소스가 일치했고 실제 빌드15.266초/exit0이다.
EXE 안의10개 field 모듈과 두 sampling 소스 원문을 확인했다. 실행 시 자기 소스 해시를
읽는 두 파일은 Git LF 원문 그대로 포함했다. Authenticode 상태는 `NotSigned`다.
bootstrap template은 별도 검증 대상이며 이 후속 파일 때문에 제품 후보나 도우미 EXE를 재빌드하지 않았다.

| 대상 | bytes | SHA256 |
| --- | ---: | --- |
| field_runner.exe | 16058064 | `0e4026fe36dcbcb6bd36e457e5a1fc50f95299b3d5ab38fc277f2739eaf65937` |
| RUN128 manifest.json | 1182 | `7319a035a5333e3542b11d9f0139aec76109e447a7b3ff17e0654937356725a4` |
| invoke-field-run.ps1 | 22366 | `cf4528b8a3ead699895efdc05f28d42e42c5f0d3d1fcc80e2f156c65b72fccff` |

고정 CSV EXE는 e728730a, 이미지 EXE는5601b347, 후보 payload 기준은a5de26c2로 기존 바이트다.
8파일/42,133,697 bytes의 공유 사본은
`Z:/SmartFactory/20261014/send/RUN128_20261014_f1378d29`에서 전부 크기/SHA를 대조했다.
서버 화면 확인과 공유 해시 검산을 구분하며 서버 실행 영수증은 아직 없다.

## 실제 검증

| 검사 | 최종 결과 | 검증 범위 |
| --- | --- | --- |
| Python 단위 | 9시험/8.468초/exit0/skip0 | 요청 계약·원문 보존·실제 두 EXE·승격 오판 차단 |
| native PS5.1 | 12조건/검사 script exit0 | 인수/환경/EOF·ACL descriptor·exit7·timeout·잔류 자손·감독자 손실·결과 변조 |
| portable | 6실행/검사 script exit0 | describe, 비관리자 차단, 합성 성공, 실제 attestation 실패, 중복 JSON, 잘못된 요청 SHA |
| 최종 bootstrap r3 | 4조건/검사 script exit0 | 실제 인수 전달 성공, 비관리자·controller SHA·request SHA 차단 |
| 최종 감사 | exit0 | 원문27파일·기준 입력282파일·패키지8파일·결과 manifest·공유 사본 대조 |

비관리자 PC의 전체 흐름 시험에는 별도 `DEV-ONLY-controller`를 사용했다. 관리자 조건을
비관리자 조건으로 바꾸고 owner/owner 검사와 개발 사용자 쓰기 권한만 바꾼 정확한4개 차이를
기록했다. production controller는 변경하지 않았다. 운영 ACL descriptor의3규칙과
운영자 ReadAndExecute 조건, 실제 production controller의 비관리자 거부를 따로 검사했다.

합성 설정 사본은 CSV327행·이미지133개를 두 고정 EXE로 검사했고 각 exit0이다.
실제 보존 metadata는 식별 PASS이나 최종 설정/attestation FAIL로 두 EXE 실행 전에 거부됐다.
위의 합성 성공은 실제 장비 승인이나 물리 경계 PASS가 아니다. CSV의 위치 두 열 미입력 경고는 유지했다.
portable 및 bootstrap r2/r3의 총5개 생성 launcher 영수증은 모두 Job active0,
강제 정리 없음, 결과 파일 집합/크기/SHA 일치다. 성공 흐름의 Job total11과 실패 흐름의 total3을
기록했다. native 감독자 손실 시험은 별도의5개 자손이 모두 사라지고 무관한 fixture는 살아 있었다.

최초 native spike에서 FileStream으로 NUL 장치를 열 수 없는 실제 실패를 보존하고,
새 빈 일반 파일을 stdin으로 사용하는 최종 구현을 검증했다. bootstrap r1은 개발 fixture에만
붙인 UTF-8 BOM이 scriptblock 파싱을 막아 실패했다. 생산 controller와 같은 BOM 없는 사본으로
고쳤다. r2의 실제 실행은 exit0이나 시험 코드가 stderr의 CLIXML 정보2건을 오류로 간주했다.
r3은 두 기록이 stdout의 RESULT_PATH/LAUNCHER_SHA256과 정확히 같은 information인지
파싱해 검증하고 error 기록은 허용하지 않는다. 실패 기록은 모두 보존했다.

## 재사용 순서와 남은 조건

1. 실제 설치/프로세스/설정 읽기 결과와 승인 출처를 확인해 해당 단계의 request를 만든다.
2. 관찰은 실제 후보 프로세스 식별과 최종 설정 기준 SHA, 종료 QA는 실제 관찰 종료 기대값과
   닫힌 사본의 출처가 확인된 파일별 크기/SHA를 지정한다. 합성 fixture를 현장 입력에 사용하지 않는다.
3. controller와 request의 실제 길이/SHA, 서버 절대경로, 운영자 SID로 새 bootstrap을 고정한다.
   관리자 실행 후 RESULT_PATH/LAUNCHER_SHA256/LAUNCH_EXIT 및 회수 결과 원문을 대조한다.
4. 서버 ACL 적용·실제 관찰→정상 종료→최종 사본/delta·UI/packet·물리 시험·3회 시작·
   동일 후보 설치/복구와15분/120분 QA를 완료한 뒤에만 운영 승격을 판단한다.

이번 변경은 도우미/검증 자료다. 제품 health·제품 재빌드·현장15분/120분은 반복하지 않았다.
제조사 경계 계약, 실제 최종 attestation, 과거 데이터 처분과 timeout/drop 원인 미확정도 남아 있다.

## 증거

개발 증거: `C:/Users/user/Desktop/SmartFactory/PDCA_RUN128_20261014_f1378d29`.
build-result/source-inputs, native-r3, python-r1, portable-r1, bootstrap-r1/r2/r3,
verification-summary, shared-transfer/server-transfer 및 서버 화면2장을 보존했다.
소스·문서 후속 확인은 봉인 후 sealed 아래에 추가하며 기존 ZIP을 재작성하지 않는다.

공유 기록: `Z:/SmartFactory/20261014/records/PDCA_RUN128_f1378d29`.
1,472항목/원문112,165,279 bytes의 ZIP 내부 크기/SHA/CRC와 공유 바이트를 검산했다.

| 파일 | bytes | SHA256 |
| --- | ---: | --- |
| evidence.zip | 102857475 | `5c9bd2715b414b41c7241502731d47cbd65edb18d0e0c4034dfebc90f806c96f` |
| manifest.json | 290568 | `d32ab4d5553df739d077b261d0ff94d25b07031a14d8aed17981d82bb77a12ab` |
