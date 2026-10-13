# 2026-10-12 실장비 대조와 서버 데이터 범위 조사 준비

전체 후속 PDCA는 Do 진행 중이며 R1~R6 정식 출시는 **HOLD**다.
직전 단계는 실제 fact 입력의 설정 조회 timeout 재현·보완과 최종 로컬 health exit 0이다.
이번 단계는 실장비의 일부 항목을 직접 대조하고 메타데이터 목록 수집 묶음을 서버 최종 폴더까지 전달했다.
이 보고서의 준비 단계 이후 실제 실행·회수와 UNC 보완은
[서버 목록 회수 보고](production-release-risk-validation-server-inventory-20261012.report.md)에 기록했다.
전체 일관된 사본·전수 검사는 미완료다.

## 실장비 직접 대조

Chrome 원격 데스크톱 `DESKTOP-Extrusion`에서 설정에 기록된 SPOT 주소를 열었다.
관측된 `info.ssi` 화면을 직접 읽고 11:34 KST의 표시 프레임을 동일 바이트로 저장했다.
조작은 홈·카메라·정보 화면 조회이며 설정 값 입력, 펌웨어 갱신, 인증 입력은 수행하지 않았다.
홈/정보/메뉴의 조작 의미는 [AMETEK Land SPOT+ 사용자 안내 3.3](https://www.ametek-land.com/-/media/ameteklandinstruments/documentation/products/fixedspotnoncontactthermometers/spot-plus/ametek_land_815954_new_spotplus_family_user_guide_issue_19_en.pdf?la=en&revision=dfc0deb3-02df-49f4-ad8c-b816e86883be#page=19)을 확인했다.

| 항목 | 직접 화면에서 확인한 값과 한계 |
|---|---|
| 표시명 | `AL Spot`. 기존 metadata의 `SPOT+ AL` 명칭과 제품 형식의 동일 여부는 기기 식별 자료와 연결해 확정해야 함 |
| Application/범위 | `App1: AL E, 200-900C`. 기존 기록의 mode·range와 일치 |
| Emissivity | `App` |
| Focus | `6071mm` |
| Output Time | `100ms` |
| 표시 버전 | `40.38` |
| Alarm/Instrument 상태 | `----`. 현재 표시 상태이며 Low Signal 구성의 비활성/threshold/comparator 확인을 대신하지 않음 |
| 추가 기기 식별값 | 지역 증거에 보존. Git 보고에는 원문 식별값을 넣지 않음 |

첫 저장 이미지 `spot-device-info.jpg`는 정보 화면의 timeout 이후 홈으로 돌아간 프레임이었다.
이를 보존하고 `spot-device-info-capture-002.jpg`에서 표시된 Info 프레임을 그대로 저장했다.
두 파일의 의미를 구분하며 첫 파일을 Info 값의 증거로 사용하지 않는다.
저장한 Chrome source-viewer HTML은 별도 디코딩했으며 장비 스크립트를 실행하지 않았다.

아날로그 4/20mA 매핑·Low Signal 설정/comparator와 실제 QA/릴리즈 담당자·현재 승인 기록은 미완료다.
과거 `Operator1` ID·2026-08-21 확인 기록과 현재 effective fingerprint mismatch를 유지한다.
기본 mode/range 일치만으로 attestation을 갱신하거나 R3를 PASS로 바꾸지 않는다.

## 목록 도우미와 검증

새 도우미는 `scripts/read-operating-data-inventory.ps1`, 회귀는 `.test.ps1`이다.
선언 루트의 경로·크기·수정 시각·파일 종류·오류를 JSONL로 기록하고,
겹친 재귀 루트·현재 실행 묶음·reparse·긴 경로·시간/출력 제한을 명시한다.
원본 파일 내용의 전수 해시·스키마/이미지 검사·archive 전개·원자적 snapshot과 구분한다.
`full_data_gate=NOT_EVALUATED`, `scope_complete=false`를 유지한다.

실행 전 운영 사용자 `user`, native Windows PowerShell 5.1, 관리자 토큰,
실제 REAL 앱 v1.0.26와 logger `20d2045c-d2e8-41bd-907e-3786534c87c2`를 검사한다.
다른 PC/재시작된 세대는 수집 전에 거부한다. 15분·출력 512MiB 예산, 결과 전 2GiB 여유 공간 조건이 있다.
관리자는 새 결과 자식의 보호 ACL 생성에 필요하며 부모/운영 폴더 ACL을 변경하지 않는다.
새 결과에는 Administrators/SYSTEM FullControl과 운영 사용자 ReadAndExecute+Windows Synchronize만 허용한다.
실제 관리자 소유 결과 생성은 서버 실행 시 사전 검증한다. 개발 PC의 비관리자 fixture 시험과 구분한다.

| 검증 | 실제 결과 |
|---|---|
| 최초 원본/링크 회귀 | 모듈 없음 exit 1 → 구현 후 exit 0 |
| drive-relative 경로 회귀 | 실제 거부 실패 exit 1 → 절대경로 선행 검사 후 exit 0 |
| 출력 오류 회귀 | 반복 쓰기 실패 exit 1 → 첫 출력 오류에서 중단, 명시된 오류/미출력 행 정산 후 exit 0 |
| native PS5.1 최종 시험 | 원본 보존·junction 미추적·경로·출력 오류·겹친 루트·실행 묶음 제외·예산·새 파일 덮어쓰기 거부·운영 세대 검사, exit 0 |
| ACL 규칙/왕복 | Windows Allow의 Synchronize 및 왕복의 `AI` 표기를 실제로 확인. 소유자/보호 여부와 실제 규칙을 검사하며 Everyone Write 추가를 거부. fixture 소유자는 현재 사용자, 운영 Administrators 소유는 미실행 |
| 발행 바이트 시험 | 묶음에 포함된 동일 시험으로 native PS5.1 exit 0 |
| 변조 launcher 시험 | 변조 helper가 실행되기 전 고정 SHA 불일치로 child exit 1, 확인 runner exit 0 |
| 잠긴 직접 명령 시험 | 같은 helper SHA를 검사한 잠금 바이트가 관리자 사전 검사에 도달해 child exit 1. 비관리자임을 확인한 runner exit 0; 서버 수집 실행 결과와 구분 |

원래 전체 health는 backend 915건 중 914 PASS/private F01 skip 1, frontend 434·Electron 94·QA 6 등 exit 0이다.
이번에는 제품 Python 소스를 바꾸지 않았다. 새 PowerShell 도우미의 최종 native 시험을 별도로 실행했다.
첫 준비 묶음과 R2 변형을 보존했다. 경로의 표시 escape를 실제 코드포인트로 재검토해 원래 경로도 유효함을 확인했고,
최종 전달은 원래 묶음이다. R2를 경로 오류 수정이나 운영본으로 취급하지 않는다.

## 서버 최종 전달

- 개발 증거: `C:/Users/user/Desktop/SmartFactory/PDCA_SCOPE_20261012_cb2f404d`.
- 공유 전송: `Z:/SmartFactory/20261012/send/SFL_INV_20261012_cb2f404d`.
- **서버 최종 폴더**: `C:/Users/user/Desktop/SmartFactory/SFL_INV_20261012_cb2f404d`.
- 일반 탐색기에서 최종 절대경로와 상위 7개 파일, `basis/current-profile-analysis.json`을 확인했다. 총 일반 파일 8개다.
- 개발↔공유 8개 파일 SHA256 일치. 서버 로컬 SHA 직접 검사와 동일하게 보고하지 않는다.
- 고정 직접 실행 안내도 서버 `C:/Users/user/Desktop/SmartFactory/PINNED_INVENTORY_COMMAND_cb2f404d.txt`에 복사하고 파일 존재를 확인했다.

실행 시 이 별도 안내의 직접 명령을 사용한다. helper를 FileShare.Read로 잠근 같은 스트림에서
외부 고정 SHA256을 검사하고 그 바이트를 실행한다. scope/basis도 고정 해시와 잠금으로 확인한다.
이전 묶음/Run/manifest 바이트를 재작성하지 않았다.

| 식별 | SHA256 |
|---|---|
| helper | `3d2d93b6ff6ee2c3e2553a14f5ba71b892fcc93fc52858fa40beb15ac2023a75` |
| scope | `714f1aaba63ede72bcb41a834fc8b2655c77d6ddbd4a85af6c00b956d2f33f79` |
| 별도 잠금 명령 안내 | `a830ec5f62bcb95f5e38b43ddc2c72d7880c8db0c62bb0e35056d7433a6f3749` |

실행에는 사용자 조작이 필요하다. 적용한 computer-use SKILL.md가 필수로 참조하는
`docs/guidance.md:232`는 “Do not run Windows terminal commands via UI automation directly or indirectly.”라고 제한한다.
기존 운영 호스트 이름에 대한 read-only WinRM 식별 요청은 exit 1이었고 설정된 SSH alias 파일은 없었다.
이 실패를 현재 원격 화면 컴퓨터의 모든 remoting 경로 부재 증거로 확대하지 않는다.
서버 실행 후 `RESULT_PATH`/`MANIFEST_SHA256`을 받아 Codex가 서버 결과→새 공유 return→개발 PC 회수·분석을 이어서 수행한다.

## 12:39~12:41 KST 실행 안내와 작업 정보 재확인

사용자가 안내 TXT 경로를 PowerShell에 입력한 뒤 메모장만 열린다고 알려 주었다.
실제 화면에서 관리자 PowerShell의 TXT 경로 입력과 명령 본문이 열린 메모장을 확인했다.
이 관측 시점에는 수집 결과 경로/manifest 해시가 없으며 목록 실행 완료로 기록하지 않는다.
파일 경로 대신 메모장의 `$inventoryBundle=`로 시작하는 본문 전체를 복사해
이미 열린 관리자 Windows PowerShell에 붙여넣고 Enter를 누르도록 안내하고 메모장으로 돌려놓았다.
Codex는 터미널 입력·명령 실행·명령 clipboard 준비를 수행하지 않았다.

사용자가 현재 생산 값을 `60332, 6`으로 확인했다.
앱을 다시 보았을 때 제품번호 `60332`, 금형번호 `6`, `적용됨`, `작업 정보 OK`,
최근 적용 `2026-10-12 12:34:51`이 이미 표시되어 중복 입력/적용하지 않았다.
이전 필수값 미입력 상태의 발생 원인과 실제 적용 주체는 미확인이다.
UI 적용 확인을 재시작 후 유지·서버 원본 파일/CSV 검증으로 확대하지 않는다.

이번 화면 증거는 별도 `C:/Users/user/Desktop/SmartFactory/PDCA_LIVE_20261012_25f5c4a3`에 기록했다.
이전 `PDCA_SCOPE_20261012_cb2f404d` 봉인과 원문은 변경하지 않는다.

## 계속 남은 전체 목표

1. 실제 담당자·현재 승인 프로파일/실장비 전체 항목·최종 build attestation.
2. 원본 timeout/drop15와 현행 drop44의 인과·영향, 모든 성능/자원 계약.
3. 이번 목록으로 전체 데이터 범위를 확정하고 일관된 전체 사본·스키마·이미지·역참조·종료 delta 검증.
4. 최종 clean commit의 서명 설치본, 동일 설치본 설치/복구/현장 QA·초기15분/canary120분.
5. 실제 운영 승격/적용 확인 후 다음 롤백 기준 갱신.

목록 수집 준비나 일부 장비 대조는 전체 PDCA 완료가 아니다. 기존 운영본·롤백 기준은 유지한다.
