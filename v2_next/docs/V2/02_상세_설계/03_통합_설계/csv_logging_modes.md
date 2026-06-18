# CSV logging modes

작성일: 2026-06-16

## 목적

이 문서는 v1 CSV와 v2 CSV 저장 플래그 조합을 운영자가 확인할 수 있도록 정리한다.
기본 운영 정책은 기존 v1 CSV 소비자 호환성을 유지하는 것이다.
v2-only 저장은 opt-in이며, 서버 실측 검증과 downstream 소비자 확인 후에만 사용한다.

## 설정 키

| 설정 | 환경변수 | 기본값 | 의미 |
| --- | --- | --- | --- |
| `[SETTINGS] autosave` | 없음 | `true` | CSV 저장 전체 on/off |
| `[LOGGING] csv_v1_enabled` | `CSV_V1_ENABLED` | `true` | `Factory_Integrated_Log_YYYYMMDD_HHMMSS.csv` 저장 |
| `[LOGGING] csv_v2_enabled` | `CSV_V2_ENABLED` | `false` | `Factory_Integrated_Log_v2_*.csv` 저장 |
| `[LOGGING] csv_v2_sidecar_enabled` | `CSV_V2_SIDECAR_ENABLED` | `true` | `Factory_Integrated_Log_v2_*.metadata.json` 저장 |

## 저장 모드 조합

| `autosave` | `csv_v1_enabled` | `csv_v2_enabled` | 결과 |
| --- | --- | --- | --- |
| `true` | `true` | `false` | 기본값. v1 CSV만 생성 |
| `true` | `true` | `true` | v1 CSV와 v2 CSV를 병행 생성 |
| `true` | `false` | `true` | v2-only opt-in. v2 CSV와 sidecar만 생성 |
| `true` | `false` | `false` | 금지 조합. writer가 warning 후 v1을 강제로 다시 활성화 |
| `false` | any | any | CSV 저장 전체 중단 |

## 파일명 영향

- v1 CSV: `Factory_Integrated_Log_YYYYMMDD_HHMMSS.csv`
- v2 CSV: `Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv`
- v2 sidecar: `Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.metadata.json`
- v2 `schema_version=2.2.0`부터 작업자 입력 `Product_No_operator`, `Mold_No_operator`와
  `operator_metadata_valid`, `operator_metadata_missing_fields`, `operator_metadata_updated_at`가 기록된다.
  v1 CSV 21컬럼 contract는 변경하지 않는다.
- `Product_No_operator`와 `Mold_No_operator`는 작업자 입력 숫자 문자열이다. UI/API 모두 숫자만 허용하며,
  예시는 제품번호 `12345`, 금형 번호 `123`이다. `DW-` prefix는 더 이상 입력하거나 저장하지 않는다.
- 작업 정보 스냅카드의 `서버 값 새로고침`은 백엔드 저장값을 다시 불러오는 기능이다. `서버 저장값 리셋`은
  백엔드 `operator_metadata.json`까지 빈 값으로 저장해 `operator_metadata_valid=false`와
  `operator_metadata_missing_fields=product_no,operator_mold_no` 상태를 만든다. 리셋 이후 새 sample부터
  v2 CSV에 빈 `Product_No_operator`, 빈 `Mold_No_operator`, invalid 상태가 기록되며, 이미 logger queue에
  들어간 row는 소급 변경하지 않는다.
- 작업 정보 스냅카드의 RGB 외곽 펄스는 필수값 누락 상태에서 `적용`, `제품 변경`, Enter 저장을 시도하면
  시작한다. 작업자가 제품번호와 금형 번호를 입력하더라도 `적용`으로 서버 저장이 성공해
  `operator_metadata_valid=true`가 되기 전까지 펄스 경고는 유지한다.
- 작업 정보 스냅카드는 안내 문구 대신 `이전 작업` 영역을 표시한다. 새 제품번호/금형 번호 적용 또는 리셋 직전의
  유효한 작업 정보가 최근 순서로 최대 3개까지 `operator_metadata.json` history에 보존된다.
- v2 `schema_version=2.2.0` CSV는 53컬럼 contract다. index 기반으로 v2 CSV를 읽는 consumer는 header 기반
  매핑으로 전환하거나 배포 전 dry-run에서 실패 여부를 확인해야 한다.
- 운영 배포 전에는 실제 서버 샘플 1세트를 repo 내부 validator와 repo 밖 ETL/Excel 매크로에 각각 dry-run한다.
  repo 밖 consumer가 53컬럼을 처리하지 못하면 `csv_v2_enabled=false`로 유지한다.
- Validator compatibility: new writer output uses `schema_version=2.2.0`, but
  `scripts/validate_csv_v2_shadow.py` still accepts legacy `schema_version=2.1.0`
  v2 files without operator metadata columns so rollback and historical audits remain possible.
- glob 수집 시 v1과 v2를 같은 넓은 glob 패턴으로 섞지 말고,
  v1 파일 목록과 v2 파일 목록을 별도로 모은 뒤 timestamp suffix 기준으로 정렬/매칭한다.
- replay/validator도 같은 원칙을 따른다. v1/v2를 한 입력 목록에 섞지 않고, 날짜별 파일 set은 timestamp suffix로 정렬/매칭한다.

## Daily rollover 정책

- writer는 row timestamp를 서버 로컬 시간으로 해석한 calendar date를 파일 경계로 사용한다.
- 로컬 날짜가 바뀌면 v1 CSV, v2 CSV, v2 sidecar가 같은 boundary에서 새 파일로 전환된다.
- 새 파일명은 해당 daily 파일에 처음 쓰이는 row timestamp를 사용한다.
- v2 `sample_seq`는 프로세스/세션 단위로 계속 증가한다. 따라서 각 파일 안에서는 단조 증가하지만 rollover 시 1로 reset하지 않는다.
- rollover 직전 이전 날짜 buffer flush가 실패하면 새 날짜 row는 기존 날짜 파일에 쓰지 않고 보류한다.
  이전 날짜 flush가 복구된 뒤 같은 row를 다시 처리해 날짜별 파일 계약을 유지한다.
- shutdown 중 보류 row가 있으면 이전 날짜 final flush를 먼저 시도한다.
  final flush가 성공하면 보류 row를 새 날짜 파일에 기록하고, 실패가 지속되면 warning을 남긴다.
- 이 보류 중 queue 적체가 늘 수 있으므로 운영 로그에서 `CSV v1 daily rollover delayed`, `CSV v2 daily rollover delayed`,
  `CSV daily rollover delayed because flush raised an exception`, `CSV log queue full` warning을 함께 확인한다.

v2-only 모드에서는 v1 CSV 파일이 생성되지 않는다.
기존 Excel 작업, replay runner, downstream parser가 v1 파일명을 기대한다면 v2-only를 켜면 안 된다.

## hot reload 보존 정책

운영 중 `csv_v1_enabled=true`에서 `csv_v1_enabled=false`로 전환할 수 있다.
이때 전환 직전에 이미 v1 buffer에 들어간 row는 새 설정과 무관하게 기존 v1 CSV 파일로 flush한다.
전환 이후 새 row는 `csv_v1_enabled=false`, `csv_v2_enabled=true` 조합이면 v2 CSV에만 기록된다.

## 검증 명령

v1과 v2 병행 저장 검증:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\validate_csv_v2_shadow.py `
  --v1 "Z:\Factory_Integrated_Log_YYYYMMDD_HHMMSS.csv" `
  --v2 "Z:\Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv" `
  --metadata "Z:\Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.metadata.json"
```

v2-only 저장 검증:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\validate_csv_v2_shadow.py `
  --v2 "Z:\Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv" `
  --metadata "Z:\Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.metadata.json"
```

## 롤백

문제가 생기면 다음 설정으로 되돌린다.

```ini
[LOGGING]
csv_v1_enabled=true
csv_v2_enabled=false
csv_v2_sidecar_enabled=true
```

`position_read_enabled` 검증이 끝나기 전에는 별도로 `[EXTRUDER] position_read_enabled=false`를 유지한다.
