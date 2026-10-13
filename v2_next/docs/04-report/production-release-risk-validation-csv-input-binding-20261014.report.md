# CSV 검사 입력과 종료 metadata 결합 검증

작성일: 2026-10-14 KST. 시작 HEAD `c9d0e05c5c8502b40f473fa37e79a829a8b17462`.
범위: 개발 PC의 새 사본, Windows 파일 잠금, 기존 고정 CSV 검사 EXE.

## 결과와 범위

CSV 검사기의 여섯 기본 입력과 선택적 posthoc fact/report를 고정 크기·SHA에 대조하고,
검사가 끝날 때까지 읽기 공유 핸들로 유지하는 `field_csv_inputs.py`를 추가했다.
종료 기대값과 최종 설정 기준도 같은 잠긴 원본 metadata에 대조한다.
16개 시험 exit0/skip0, 고정 CSV EXE 실제 12실행, 최종 Ruff exit0이다.
보존 I4/I5 원본 12파일과 검사 EXE는 바뀌지 않았다.

이는 개발 검증 모듈이다. 서버에서 실행 가능한 통합 묶음·보호된 외부 실행기는 아직 아니다.
`input_binding_status=PASS`는 선택한 입력 바이트의 결합만 뜻한다. CSV 내용 검사 exit,
이미지 바이트 검사, 실제 정상 종료, 설정/물리 attestation 및 현장 QA는 별도 조건이다.
R1–R6 HOLD, full_data_gate NOT_EVALUATED, promotion_allowed=false를 유지한다.
미서명 내부 운영 정책과 운영본/다음 롤백 `541d701d` / installer `08C061EE…`는 유지한다.
제품 코드·후보 `4cc7393e` 설치본은 변경하거나 재빌드하지 않았다.

## 발견한 동작과 보완

기존 `validate_csv_v2_shadow.py`는 선택적 fact 경로를 metadata에서 읽는다. posthoc CLI
override를 주면 manifest의 SHA·행 수 불일치를 보고하더라도 실패로 만들지 않는다.
새 모듈은 원본을 보존하고, 해당 fact_path/report_path만 잠긴 사본으로 바꾼 파생 metadata를
만들어 그 기본 검증 경로를 유지한다. 원본/파생본 해시와 변경 목록, 나머지 필드 동등성을 기록한다.
관찰 fact·이미지 fact·최종 manifest는 각각 명시적으로 지정하며 과거 promotion opt-in은 쓰지 않는다.

원본 선택적 manifest가 row_count=0/sha256=null이고 닫힌 사본에도 파일이 없을 때만 부재를
허용한다. 잠긴 일반 파일 `ABSENT_INPUT` 아래 자식 경로를 지정해 검사 중 그 경로에 파일이
생길 수 없게 한다. 빈 fact를 합성하지 않는다. 원래 사본 위치에 파일이 새로 생겨도 종료 검사를
실패시킨다. 선언된 파일 이름·쌍·SHA·크기, JSON 중복 키, UNC/ADS/예약 이름/상위 경로도 검사한다.

기존 EXE는 `spot_image_linkage_fact_manifest.report_sha256`을 강제하지 않았다.
잘못된 report SHA로 EXE exit0을 재현했고 새 모듈은 소비 전에 잠긴 report SHA와 대조해 거부한다.
해당 회귀 시험의 최초 실패(r2, 14시험 중 1실패/exit1)를 보존한 뒤 수정했다.

Windows native 시험에서 입력/파생 metadata/부재 표시 파일의 쓰기·이름 변경과 입력/작업
폴더 이름 변경이 거부됐다. 이는 일반 파일 접근에 대한 검증이며 적대적인 부모 소유자의
모든 경로 교체에 대한 보안 경계가 아니다. 파일별 2 GiB, metadata 4 MiB, 역할 최대10개 및
경로 예산을 코드로 제한한다. 이번 시험이 실제 2 GiB 성능 시험을 뜻하지는 않는다.

## 실제 검사 EXE와 시험

고정 EXE: `C:/Users/user/Desktop/SmartFactory/PDCA_QA128_20261013_32adee4e/QA128/validate_csv_v2_shadow.exe`

- bytes: `9494053`
- SHA256: `e728730ad841dd4a754a6c0880e0e1216de5e3d0cd5646c22de9245fc85b0b2f`
- 자료: `PDCA_NSIS_FIX_20261013_6b39ce41/output/matrix`의 I4 설치/I5 재시작 닫힌 사본.
- 원본의 기존 data-after.json 크기·SHA와 대조한 뒤 새 사본에서만 오류를 주입했다.

| 실제 EXE 조건 | 실행 수 | 실제 exit | 해석 |
| --- | ---: | --- | --- |
| I4 / I5 사본 | 2 | 0 / 0 | CSV 327 / 296행, 원본 metadata 보존 |
| 외부 오염 fact: 원본 경로 / 파생 경로 | 2 | 1 / 0 | 파생 경로는 외부 파일을 소비하지 않음 |
| 올바른 선택적 fact | 1 | 0 | 기본 manifest 검사 유지 |
| 잘못된 SHA / 행 수, 기본 경로 | 2 | 1 / 1 | 두 불일치 모두 실패 |
| 같은 오류에 기존 CLI override 사용 | 2 | 0 / 0 | 기존 도구의 완화 동작 대조군 |
| 유효 linkage fact/report | 1 | 0 | 네 경로만 변경한 metadata 검증 |
| 잘못된 최종 이미지 manifest | 1 | 1 | CSV 내용 실패 유지 |
| 잘못된 linkage report SHA, 기존 EXE 단독 | 1 | 0 | 새 모듈은 이후 소비 전 거부 |

총12실행 중 exit0 8개/exit1 4개는 예상 결과와 모두 일치했다. stderr는 모두 비었다.
위치값 두 열이 비어 있다는 기존 경고는 보존했다. 이미지 JPEG 바이트는 CSV 검사의 범위가 아니다.

최종 명령은 repo Python 3.12.6에서 다음과 같다.

```text
python -B -m unittest discover -s scripts/field-v1028 -p test_field_csv_inputs.py -v
```

`run_checks.py r4`가 새 환경/사본 경로를 설정하고 소유한 Windows Job에 시험 worker와 자손을
연결했다. 최종16시험은 17.780초, exit0/skip0; Job total40/active0/terminated0, worker exit0이다.
원문은 r4.stderr.log/r4-terminal.json이다. 쓰기/교체 거부, 부재 경로, 입력/EXE 해시,
JSON/경로, context 수명과 종료 오류도 검증했다.
초기 Ruff의 unused hashlib F401(exit1)을 제거했고, 최종 두 모듈과 외부 runner를 대상으로
`python -m ruff check --isolated --select F,E9 <3 files>`를 실행해 exit0을 확인했다.
제품/설치본 불변이므로 전체 health·빌드·설치·장시간 현장 시험을 이 변경에서 반복하지 않았다.

## 같은 metadata에서 종료와 설정 확인

`shutdown_csv_inputs`는 관찰한 CSV 이름·logger/build/schema/최소 sample 기대값과
고정 설정 기준을 CSV에 제공할 바로 그 원본 metadata의 잠긴 핸들에서 검토한다.
보존 I4 실제 metadata는 identity PASS, 최종 configuration/attestation FAIL이며 계속 거부된다.
별도 합성 사본/기준은 통합 경로의 PASS를 확인했고 SYNTHETIC_TEST_NOT_FIELD_APPROVAL로 구분했다.
합성 설정으로 실제 CSV EXE를 실행하거나 이를 현장 승인 근거로 사용하지 않았다.
기준 파일도 context 동안 쓰기가 거부됐고 context 종료 오류에는 PASS가 남지 않았다.

후속 통합 체크리스트:

1. 인증한 관찰 결과·정상 종료 결과에서 기대값과 닫힌 사본 inventory를 얻는다. 이 모듈은
   호출자가 주는 inventory의 승인·출처를 자체 인증하지 않는다.
2. 외부 고정 목록으로 `CsvInputs`를 구성하고 `shutdown_csv_inputs(...)` context 안에서만
   `bound.command()`를 소유한 Job으로 실행한다. 자손 종료까지 잠금을 유지한다.
3. 실제 CSV exit와 원문 출력, context 종료 결과를 각각 기록한다. 바이트 결합 PASS만으로
   내용 검사를 PASS로 만들지 않는다. 최종 이미지 바이트 검사도 별도로 결합한다.
4. 보호된 launcher·최종 설정 attestation·UI/packet·최종 delta·현장 3회 시작/15분/120분 QA,
   제조사 계약/물리 경계·과거 데이터 판정 및 나머지 출시 조건을 확인한다.

## 증거

개발 기록: `C:/Users/user/Desktop/SmartFactory/PDCA_CSV_BIND_20261014_0de1f544`.
source-red에는 실패 당시 모듈/시험, source-final에는 관련 Python19파일과 각 해시를 보존했다.
consumer-results.json에는 실제12명령/exit/출력 해시·마지막 판정, originals-final.json에는
보존 원본12파일의 최종 대조, verification-summary.json에는 범위와 잔여 gate를 기록했다.
이전 이미지 검사 단계의 BEFORE_AFTER_ONLY 부재 검증 기록은 당시 결과로 그대로 보존한다.
이번 모듈의 잠금 검증을 이전 실행이나 아직 수행하지 않은 서버 실행으로 소급하지 않는다.

공유 보존: `Z:/SmartFactory/20261014/records/PDCA_CSV_BIND_0de1f544`.
1,079파일/원문72,809,607 bytes를 봉인했고 ZIP 항목별 크기·SHA/CRC와 공유 사본 SHA를 검산했다.

| 산출물 | bytes | SHA256 |
| --- | ---: | --- |
| evidence.zip | 5152908 | `1aac168ea18b91216239b305b2029ce6d090ab29748c8d1678ab554031cdc785` |
| manifest.json | 253115 | `c074f0529d26517a9c1e990c29347ea1c1477bb5a665f8c21914aa56a638f695` |

봉인 후 문서·상태·commit 대조 영수증은 개발 기록의 sealed 아래 별도로 둔다.
공유 보존은 서버 로컬 전달이나 서버 실행 확인을 뜻하지 않는다.
