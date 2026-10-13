# 2026-10-12 서버 목록 회수와 UNC 경로 보완

서버 메타데이터 목록을 실제 실행하고 서버 → 새 공유 return → 개발 PC로 회수했다.
전체 후속 PDCA는 Do 진행 중이며 R1~R6 정식 출시는 HOLD다.

## 실제 실행·회수·무결성

사용자가 관리자 Windows PowerShell 5.1에서 고정 helper를 잠근 직접 명령의 본문을 실행했다.
Codex는 터미널 입력/명령 실행을 조작하지 않았다. 적용한
[computer-use SKILL.md](C:/Users/user/.codex/plugins/cache/openai-bundled/computer-use/26.1007.21434/skills/computer-use/SKILL.md)가 참조하는 `docs/guidance.md:232`의
“Do not run Windows terminal commands via UI automation directly or indirectly.” 제한에 따른다.

- 서버 결과: `C:/Users/user/Desktop/SmartFactory/SFL_INV_20261012_cb2f404d/r-20261012-034359-27900b4e`.
- 공유 회수: `Z:/SmartFactory/20261012/return/INV_20261012_bacadba4/r-20261012-034359-27900b4e`.
- 개발 증거: `C:/Users/user/Desktop/SmartFactory/PDCA_INV_RUN_20261012_bacadba4/server-result`.
- 실제 computer_name: `DESKTOP-CIIT7LK`; 운영 logger 세대 `20d2045c-d2e8-41bd-907e-3786534c87c2` 검사 통과.
- 완료 출력 관측. PS 프로세스 종료 코드/handle wait는 측정하지 않음.
- 실행 main의 새 결과 Administrators 소유·보호 ACL·접근 규칙 검사 통과 후 운영 사용자 탐색기 접근/복사를 확인함.

콘솔 manifest SHA256: `1969A6582F30B7FCE5EB07B0696097F5B2E145424BA500DC8ED60D31E429D739`.
최초 작은 화면에서 일부 문자를 잘못 전사해 비교가 실패했다. 콘솔 영역을 별도 캡처해 정확한 값을 읽고 재대조했다.
공유/개발 사본의 manifest와 기록된 `files.jsonl` 122,097,130 bytes, `summary.json` 5,037 bytes의 해시·크기가 모두 일치한다.
실행 시 같은 잠금 바이트의 helper/scope/basis 해시가 검사됐다. 서버 묶음의 모든 안내/시험 파일 해시를 측정한 것은 아니다.

## 관측 규모와 한계

| 집계 | 실제 값 |
|---|---:|
| 일반 파일 / 디렉터리 / 미추적 reparse | 410,291 / 1,506 / 1 |
| JSONL 행 / 파일 표시 크기 합 | 411,798 / 101,831,614,007 bytes |
| 시간 / 출력 오류·시간 예산 초과 | 243.892462초 / 없음 |
| 루트 오류 | NAS 1곳 |
| 이미지 이름 분류 / CSV / metadata | 364,919 / 1,019 / 497 |
| image fact / observation fact / archive / shortcut | 7 / 6 / 14 / 6 |

`analyze-inventory.py`가 모든 행의 JSON·대소문자 무시 경로 중복·파일/디렉터리/reparse 수·
크기 합·종류별 집계를 summary와 독립적으로 대조했다(exit 0). 원본 내용 해시는 미측정이다.
`full_data_gate=NOT_EVALUATED`, `scope_complete=false`, `atomic_snapshot=false`를 유지한다.

| 선언 루트 | 일반 파일 | 크기 합(bytes) |
|---|---:|---:|
| Logger AppData | 327,625 | 55,027,906,624 |
| Electron AppData | 99 | 342,552,095 |
| Desktop SmartFactory | 80,759 | 41,839,923,436 |
| 설치 payload | 1,772 | 560,624,891 |
| 기존 SFLOps 읽기 범위 | 13 | 68,561 |
| 바탕화면 최상위 발견 | 18 | 135,792,160 |
| C 최상위 발견 | 5 | 3,924,746,240 |

합계에는 시스템 pagefile/hiberfil, 설치본과 과거 사본이 포함돼 운영 자료의 확정 복사 용량과 다르다.
`logs/test_data`에 현재 수정 중인 fact와 약 50.46GB의 파일이 있다. 폴더명만으로 테스트 자료로 제외하지 않는다.
역할/프로파일 후보 114개는 파일명 분류이며 Python `operator.py`도 포함한다. 실제 담당자 114명이 확인된 것이 아니다.

## UNC 오류 수정과 NAS 보완

NAS share 루트가 정규화에서 끝 구분자를 잃은 뒤 같은 경로의 재검사에서 거부됐다.
이를 NAS 권한/연결 실패로 확대하지 않는다. native PS5.1 회귀 exit 1을 재현한 뒤
UNC share 뒤 구분자 또는 문자열 끝을 허용하도록 정규식 한 줄을 수정했다.
share 없는 UNC host·drive-relative 경로는 계속 거부한다. 기존 모든 검사와 새 UNC 회귀, 최종 발행 바이트 시험은 exit 0이다.

첫 NAS 준비본은 native PS5.1이 BOM 없는 준비 소스의 한국어 리터럴을 잘못 읽은 것을 scope 사전 검사에서 발견했다.
보존하되 서버에 전달/실행하지 않았다. 최종 R2는 ASCII 준비 소스가 이전 고정 scope를 UTF-8로 읽어 경로를 가져온다.
이전 경로와 정확한 일치 및 개발 PC 접근 가능을 확인했다.

- 서버 최종: `C:/Users/user/Desktop/SmartFactory/SFL_INV_NAS_20261012_bacadba4_r2`.
- 서버 안내: `C:/Users/user/Desktop/SmartFactory/PINNED_INVENTORY_NAS_20261012_bacadba4_r2.txt`.
- 공유 전달: `Z:/SmartFactory/20261012/send/NAS_DELIVERY_20261012_bacadba4_r2`.
- 탐색기로 상위 6개 파일과 basis 2개, 서버 명령 TXT의 열린 내용을 확인함.
- 개발↔공유 묶음 8개와 별도 명령 해시 일치. NAS 서버 실행은 이 시점에 대기 중.

| 최종 R2 식별 | SHA256 |
|---|---|
| helper | `4d66fb164bfbb375d976af524203af9f5ba53818665713990001f376833d351a` |
| scope | `a19e12c732a4e98fef7f8d34bd215d5425707f8e3f6e3edf6f58ebcb433844fa` |
| 명령 안내 | `d09b9047dce1037e38e2921d137d380b11d999b85068bfd6a4c2c5e159ac0b1a` |

NAS 보완 뒤에도 하위/다른 share·shortcut·archive 범위는 별도 확정해야 한다.
전체 일관된 사본·전수 schema/image/역참조·종료 delta·실명 역할/전체 장비 attestation·
최종 서명 설치본/동일 설치·복구·현장 QA·15분/120분·실제 승격/다음 롤백 기준은 미완료다.
