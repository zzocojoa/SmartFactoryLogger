# 같은 종료 사본의 CSV·이미지 QA 통합

작성일: 2026-10-14 KST. 시작 HEAD `67b8ebf609d27792cd0a171ee4bf707a99f0b14a`.
범위: 개발 PC, 보존된 격리 후보 I4/I5의 새 사본, 고정된 두 검사 EXE.

## 결과

`field_closed_data_qa.py`에서 CSV·이미지 검사를 같은 잠긴 입력과 연결했다.
최종15시험 exit0/skip0, 실제 고정 EXE 14실행의 예상 exit0 12개/exit1 2개를 확인했다.
두 검사 결과뿐 아니라 파일 집합·크기·SHA, 이미지 도구의 실제 소비 목록, worker/자손 종료,
context 종료까지 확인한 뒤 결과를 기록한다. 보존 원본344파일과 두 EXE는 변경되지 않았다.

현장 전체 QA를 완료한 것은 아니다. 실제 보존 attestation은 FAIL로 유지되며,
합성 설정 기준을 넣은 사본에서만 상위 API의 성공 경로를 검증했다.
R1–R6 HOLD, full_data_gate NOT_EVALUATED, promotion_allowed=false를 유지한다.
사용자 승인에 따른 UNSIGNED_INTERNAL 정책, 운영본/다음 롤백541d/08C 및 후보4cc/882는 그대로다.
제품 코드·설치본 변경, 실제 앱 종료·설치·서버 실행은 수행하지 않았다.

## 연결한 실행 흐름

1. 기존 `CsvInputs`로 여섯 기본 파일과 선택적 posthoc 입력을 고정하고 원본 metadata를 보존한다.
2. `ImageInputs`는 같은 root의 spot_images 전체 선택 목록을 고정 크기·SHA와 대조한다.
   이미지마다 단일 링크의 일반 파일인지 검사하고 읽기 공유 핸들을 유지한다. 이미지 EXE도
   고정 SHA로 잠근다. 누락·새 미선언 파일·이름/해시/도구 불일치는 소비 전에 실패한다.
3. 같은 image fact로 두 고정 EXE를 순차 실행한다. 새 multiprocessing worker를 이름 없는
   Windows Job에 넣은 뒤 gate를 열고, 제한된 환경과 새 작업 폴더에서 실행한다.
   실제 앱이나 이름으로 찾은 프로세스를 Job에 넣지 않는다.
4. 실제 exit, stdout/stderr, worker exit, Job 잔존·강제 종료 여부와 파일 해시를 보존한다.
   시간 제한과 stdout/stderr별128 MiB 예산을 실행 중 및 종료 후 확인한다.
   시간 초과·출력 초과·남은 자손·결과 누락은 FAIL이고 소유한 검사 자손만 정리한다.
5. 이미지 도구의 summary와 inventory-before/after, image-checks를 읽기 공유로 잠가 대조한다.
   도구 소스 SHA·fact 전후 SHA·건수·issues와 각 소비 경로/크기/SHA가 외부 목록에 일치해야 한다.
   PASS 문자열이나 exit0 하나만으로 데이터 검사를 통과시키지 않는다.
6. 이미지/CSV context 종료 검사까지 통과한 뒤 상위 `closed-data.json`에 판정을 기록한다.
   결과 파일은 새로 만들고 flush/fsync한다. 선행 실행 결과나 원본을 덮어쓰지 않는다.

`check_bound_data`는 이미 활성인 CSV context 안에서 데이터 소비만 검사하는 API다.
최종 `validate_closed_data`는 종료 기대값·고정 설정 기준을 필수로 받아 같은 잠긴 metadata에
대조한 후 두 검사를 수행한다. 바깥 CSV context 종료 실패도 최종 FAIL이 된다.
정상 종료를 실제 수행했거나 observation/inventory/기준의 승인 출처를 인증했다는 뜻은 아니다.
그 연결은 보호된 외부 실행기와 실제 현장 결과에 남아 있다.

## 고정 도구와 최종 시험

| 도구 | bytes | SHA256 |
| --- | ---: | --- |
| CSV EXE | 9494053 | `e728730ad841dd4a754a6c0880e0e1216de5e3d0cd5646c22de9245fc85b0b2f` |
| 이미지 EXE | 16208474 | `5601b347637bd0dcb9971839ec93bdc2860ad4594e5ba328acd4e70fa91d5f14` |
| 이미지 EXE 동봉 소스 | — | `067f2a50f69d44e7665020ebd64898964f215f32cbf7fc2caca72cea1edc79db` |

원본은 `PDCA_NSIS_FIX_20261013_6b39ce41/output/matrix`의 I4/I5 closed-data이며
기존 data-after.json의 크기/SHA에 복사 전후 및 최종 원본을 대조했다.

| 최종 실제 검사 조건 | CSV exit | 이미지 exit | 통합 판정 |
| --- | ---: | ---: | --- |
| I4 실제 사본, 이미지133개/CSV327행 | 0 | 0 | 선택 데이터 검사 PASS |
| I5 실제 사본, 이미지199개/CSV296행 | 0 | 0 | 선택 데이터 검사 PASS |
| 합성 최종 설정을 추가한 사본 | 0 | 0 | 상위 API PASS, field 미평가 |
| 올바른 사본이나 CSV context 종료 오류 주입 | 0 | 0 | 상위 API FAIL |
| 잘못된 최종 이미지 fact manifest | 1 | 0 | FAIL |
| 이미지 바이트 손상, 사본 목록만 새 바이트와 일치 | 0 | 1 | FAIL |
| 올바른 검사 후 소비 inventory 변조 대조군 | 0 | 0 | 원래 검사 PASS, 변조 출력 재검증 거부 |

I4/I5 이미지 수에는 서로 겹치는 누적 파일이 있다. 두 수의 합을 고유 이미지 수로 보고하지 않는다.
실제14검사 실행은 모두 worker exit0, stderr 비어 있음, 기록된 Job active0이며,
CSV의 기존 위치 두 열 미입력 경고는 그대로 남았다.
별도 실제 attestation FAIL 사례는 identity PASS여도 검사 명령을 시작하지 않았다.
이미지 누락·미선언 파일·SHA 불일치·잘못된 EXE 역시 명령 실행 전 차단했다.

추가 native 시험에서 파일 쓰기/이동 거부, context 중 새 파일 발견, 잘못된 소비 inventory,
시간 초과, 종료 후 출력 예산, 잔류 자손을 확인했다. 종료 후 출력 예산 시험은 부모 조회를
지연해 실제 consumer/worker exit0을 먼저 확인한 상태에서도 FAIL이 되는지 검증했다.
독립된 별도 시험 프로세스는 살아 있었고 검사 Job의 자손만 종료됐다.
감독자 강제 종료 사례는 확인한 자손 PID 전체가 사라지고 PASS 영수증이 생성되지 않았다.
consumer exit7 대조군은 worker exit0과 구분해 실제 exit7을 보존했다.

최종 실행 명령:

```text
backend/.venv/Scripts/python.exe -B -m unittest discover -s scripts/field-v1028 -p test_field_closed_data_qa.py -v
```

환경 변수 `SFL_DATA_QA_TEST_ROOT`는 매번 새 r1/r2/r3/r4 폴더를 지정한다.
`SFL_CSV_INPUT_ARCHIVE`, `SFL_CSV_INPUT_EXE`, `SFL_IMAGE_INPUT_EXE`는 위 고정 자료/도구 위치이며,
기존 설정 fixture import용 `SFL_OBSERVATION_TEST_ROOT`도 별도 미사용 경로로 설정한다.
최종 r4: Python3.12.6, 15시험/45.257초/exit0/skip0. 원문 r4.log와 r4-terminal.json을 보존했다.
최종 두 모듈과 외부 감사 스크립트의 `ruff check --isolated --select F,E9`도 exit0이다.
최초 Ruff의 미사용 import 두 건(exit1)은 정리했다. 이전 실행 기록/소스는 그대로 보존했다.
제품 및 기존 모듈은 바꾸지 않았으므로 전체 health·빌드·설치·15분/120분은 이번에 반복하지 않았다.

## 후속 호출과 잔여 조건

호출자는 승인 출처를 확인한 닫힌 사본 inventory, 관찰 기대값, 최종 설정 기준 SHA를 준비한다.
`CsvInputs`를 구성한 뒤 `validate_closed_data(bound, image_files, image_executable, output,
expected_shutdown, configuration_path, configuration_sha256)`를 호출한다.
새 output은 입력 밖에 두고, 결과의 closed_data_status와 각 검사 exit/원문/context 판정을 함께 검토한다.
실제 데이터에 합성 기준을 사용하거나 반환된 PASS를 field/release PASS로 바꾸지 않는다.

일반 파일 잠금과 소비 목록 대조는 적대적인 부모 소유자를 막는 완전한 보안 경계가 아니다.
400,000이미지/1,000,000항목 상한은 코드의 자원 한도이며 그 규모의 이번 실측 결과는 아니다.
보호된 launcher·ACL/출처 인증·관찰과 실제 정상 종료의 연결·UI/packet·최종 delta,
현장 설정/물리 경계 및 동일 설치본의 서버3회 시작·15분/120분·승격 검증이 남는다.
현재 모듈은 서버 실행 패키지로 전달하거나 실행하지 않았다.

## 증거 위치

`C:/Users/user/Desktop/SmartFactory/PDCA_DATAQA_20261014_73d9a82c`에 모든 실행과 실패 조건을 보존한다.
최종 대조는 final-r4/verification-summary.json, consumer-results.json, originals-final.json이며
final-r4/source-final에는 관련 Python20파일과 해시를 고정했다. 이전 source-final은 r3 당시 기록이다.
19개 process 영수증의 Job active0을 대조했고 감독자 손실은 별도 native 시험 기록으로 구분한다.

공유 보존은 `Z:/SmartFactory/20261014/records/PDCA_DATAQA_73d9a82c`다.
8,291항목/원문47,032,998 bytes의 ZIP 항목 크기·SHA/CRC와 공유 ZIP·manifest SHA를 검산했다.

| 파일 | bytes | SHA256 |
| --- | ---: | --- |
| evidence.zip | 8292678 | `1c748943d44b14a54fced99738951e9272a1b0dc5f7d3d4294c693346c86e1ea` |
| manifest.json | 1685680 | `a347fe4b6b567da749d3ed6a96f9a0a12d99b96d02fbe39c62a69366c580ef4f` |

봉인 이후 상태·문서·commit 대조 영수증은 sealed에 별도로 보존한다.
