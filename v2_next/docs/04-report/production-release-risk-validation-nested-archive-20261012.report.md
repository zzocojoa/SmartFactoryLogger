# 2026-10-12 내부 ZIP 바이트 회수와 중첩 자료 연결 정산

미서명 내부 운영 정책으로 후속 PDCA Do를 계속 진행한다. 장비·운영 확인/QA/릴리즈 판단은
사용자 본인이며 실제 장비 모델명은 사용자 답변 “미정”으로 `UNDETERMINED`다.
전체 R1~R6 출시 HOLD, `full_data_gate=NOT_EVALUATED`를 유지한다.

## 고정 입력과 사본 범위

새 실행 루트는 `C:/Users/user/Desktop/SmartFactory/PDCA_ARCHIVE_20261012_a0ddb009`다.
완료 증거 1,063파일/3,292,083,557 bytes를 봉인했으며 manifest SHA256은
`71d8248eab13b722965efe7a2b142e1bfa4a2cca12648718d343c9de14e2f9e7`다.
경로/합계/stat 독립 정산 exit 0, 공유 `Z:/SmartFactory/20261012/records/PDCA_ARCHIVE_a0ddb009`의
manifest 사본 해시도 일치한다. 완료 루트에는 이후 결과를 추가하지 않는다.
앞서 읽은 원본 ZIP 437개 중 내부 ZIP이 있는 93개를 선택했다. 이전 전체 NAS 목록의 크기/mtime와
원본 identity를 대조해 내부 항목 161개/2,255,774,869 bytes를 정산했다.
입력 선정은 14.422초/exit 0이다. 전체 외부 ZIP 내용의 CRC/해시를 확인한 범위가 아니다.

모든 외부 원본 93개를 Read 공유 스트림으로 먼저 연 뒤 첫 사본을 만들었다.
각 내부 ZIP을 EOF까지 읽어 해당 원래 ZIP 항목의 CRC를 확인하고 사본 SHA256과 대조했다.
최초 내부 항목 161개가 모두 일치했다. 모든 입력 핸들을 유지한 상태로 최종 원본 identity를
다시 대조한 뒤 닫았다. 전체 외부 ZIP 재해시나 다른 프로토콜 writer/전체 NAS atomic snapshot을 주장하지 않는다.
원본이나 기존 증거를 변경하지 않았으며 원래 entry 이름으로 경로를 만들거나 코드/설치본을 실행하지 않았다.

## 최초 bounded 실행과 해시 기준 연결 정산

처음에는 항목별 중첩 경로를 따라 읽었다. 1,024작업·8단계 제한에 도달해
중앙 목록 1,024개/사본 내용 3,288,867,571 bytes를 확인하고 241개 연결을 미완료로 남겼다.
245.812초/exit 1을 원문과 함께 보존했다. 완료된 사본의 실제 SHA256은 121종류였다.

후속 `reconcile_nested_content_graph.py`는 파일 이름·CRC만으로 중복을 가정하지 않는다.
각 실제 내용 SHA256의 대표 사본을 해시 전후/identity로 확인하고 동일 부모 바이트의 고유 member에
한해 앞선 정확한 내부 사본 해시/CRC 증거를 재사용했다. 중첩 경로를 반복해서 복사하는 대신
부모 내용 SHA256·member·자식 내용 SHA256의 연결을 정산했다.

| 최종 선택 내부 ZIP 연결 정산 | 결과 |
|---|---|
| 최초 내부 항목 | 161개 모두 사본 hash/원래 member CRC 확인 |
| 실제 내용 종류 | 121개, 각 대표 사본 해시 전후/identity 확인 |
| 고유 부모/member/자식 연결 | 45개, 정확한 기존 바이트 증거 연결 |
| 앞선 미완료 경로 관측 | 241개 모두 위 내용/연결에 대응함을 독립 정산 |
| 후속 실행 | 2.781초/exit 0; 독립 정산 exit 0 |
| scope 밖 | 일반 내부 파일 전체의 CRC/내용/CSV·JSON 스키마 검증 미실행 |

이 결과는 원래 161개 내부 ZIP에서 도달하는 고유 ZIP 내용과 중앙 목록 연결의 완료다.
기존 외부 원본 두 파일의 끝 정보 부재, 일반 member 내용 및 나머지 서버/NAS 사본 QA를 해결한 결과가 아니다.
원래 exit 1과 새 연결 정산 exit 0을 구분해 보존한다.

읽은 내부 중앙 목록에도 정확한 `F01_startup_and_poll1.csv` 후보 이름은 없었다.
private F01 SHA256 `bab8f61354124b5fdfa155abdb289255a2514fb710f4fa5e23a7e43418dec4b4`의
회복을 주장하지 않으며 기존 health의 private skip1을 유지한다. 다른 이름의 동일 바이트나 미열람 경로의 부재 증명은 아니다.

## 과거 온도 파일의 복구 사본 탐색 범위

전체 NAS 메타데이터 1,032,015행의 원래 SHA256을 읽으며 과거 문제 파일 19개의 basename을 찾았다.
동일 이름 후보 19개는 모두 원래 `출구부 온도` 하위 파일이었다. 다른 loose 경로 후보는 없었다.
121종류 내부 ZIP 중앙 목록에서도 해당 이름 후보는 없었다.
이름이 다른 사본, 다른 외부 ZIP member, 다른 서버 경로 또는 실제 복구 가능성 전체를 배제하지 않는다.
문제 파일의 원본/사본과 NUL·기록 조각 증거는 이전 봉인 자료 그대로 보존한다.

## 생산 의존성 감사의 좁은 결과

현재 lock의 생산 의존성 범위로 `npm audit --omit=dev --json` 및
`npm --prefix frontend audit --omit=dev --json`을 실행했다.
두 npm process 모두 exit 0, registry 보고 취약점 0, stderr 0 bytes이며 전체 JSON을 읽어 정산했다.
개발/빌드 도구를 포함한 앞선 전체 감사의 root high1/moderate8·frontend high6/moderate2는 별도 미해결이다.
이 검사만으로 최종 NSIS payload에 들어갈 패키지나 런타임 노출·R6 전체 보안 gate를 통과 처리하지 않는다.
패키지·lock·제품 소스를 변경하지 않았으므로 통과한 최종 소스 health를 반복하지 않았다.

다음 검토 양식: 선택 원본/사본 SHA256 · 검사한 ZIP 내용/일반 member 구분 · schema/생성 버전 ·
실패·미확인 항목과 원시 증거 · 복구 사본 동일성/영향 범위 · 사용자 본인의 처리 판단 ·
최종 미서명 후보 commit/installer/payload와 실제 현장 QA 연결.

## 2026-10-13 후속: 선택 내부 ZIP의 모든 member 바이트 검사

새 결과 루트 `C:/Users/user/Desktop/SmartFactory/PDCA_ARCHIVE_CONTENT_20261013_82d6b150`에서
기존 봉인 루트를 변경하지 않고 위 121개 고유 내용의 대표 사본을 검사했다.
기존 manifest pin과 node 목록의 hash를 확인하고, 모든 121개 사본을 Read 공유로 먼저 열었다.
각 ZIP은 내용 hash/identity를 검사 전후 대조했으며 member 이름으로 경로를 만들거나 실행하지 않았다.

중앙 목록의 실제 총량을 먼저 확인한 뒤 일반 member 13,328개/4,770,179,392 bytes를 끝까지
읽어 CRC32·길이·SHA256을 확인했다. 29.445초/exit 0, 미완료 member 0이다.
이는 위 2026-10-12의 일반 member 내용 미실행 범위를 해당 121개 고유 ZIP에 한해 보완한 결과다.
원래 외부 ZIP 437개 전체의 member 검사나 끝 정보가 없는 두 파일의 복구를 뜻하지 않는다.

선택 내용에서 JSON 4,300개, JSONL 75개, CSV 161개는 UTF-8 구문 읽기를 완료했다.
CSV는 파일별 기록 수·너비 분포를 보존했으며 승인 스키마·시간/센서 의미는 미확인이다.
일반 JSON 파싱은 업무 스키마나 RFC 엄격 적합성의 PASS가 아니다.
모든 member의 실제 SHA256을 private F01 지정 hash와 비교했으나 일치하는 바이트는 없었다.
다른 외부 자료의 부재 증명이나 private skip 해소로 확대하지 않는다.

`member-content-results.jsonl`, `node-content-results.jsonl`, `summary.json`에 결과를 보존한다.
member/node별 파일 수·바이트·구문 결과 독립 정산은 exit 0이다. 새 결과 루트의 manifest SHA256은
`f1451bc53b15b8ef46e22bdb85bc36bd8c281f29edfc598aaaf00307d96c52a5`이며,
`Z:/SmartFactory/20261013/records/PDCA_ARCHIVE_CONTENT_82d6b150`에 완료 기록을 복사해 해시를 대조했다.
봉인한 두 과거/후속 루트에 이후 결과를 추가하지 않는다.
이 추가 결과 이후에도 `full_data_gate=NOT_EVALUATED`, R1~R6 HOLD를 유지한다.
