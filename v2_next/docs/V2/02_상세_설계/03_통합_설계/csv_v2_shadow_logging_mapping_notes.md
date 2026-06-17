# CSV v2 shadow logging 및 PLC mapping 검증 메모

작성일: 2026-06-16

## 목적

이 문서는 v1 CSV 호환성을 유지하면서 v2 CSV와 sidecar metadata에 추가된 검증용 필드의 의미를 정리한다.
운영 판단 기준은 서버 PC에서 수집한 v1 `Factory_Integrated_Log_YYYYMMDD_HHMMSS.csv`,
v2 `Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv`, v2 sidecar
`Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.metadata.json` 기준이다.

## 필드 의미 contract

| 필드 | 위치 | PLC source | 단위 | 상태 | 의미 |
| --- | --- | --- | --- | --- | --- |
| `EndPos` | v1 CSV, v2 CSV | `D0421 / 10.0` via `D0420[1]` | mm | `hmi_confirmed_setting_value` | 압출 종료 위치 설정값 또는 메인 램 총 길이 성격의 고정 설정값이다. 실시간 이동 위치가 아니다. |
| `MainRamPosition_D0010` | v2 CSV only | `D0010 / 10.0` | mm | `hmi_confirmed_actual_position` | 메인 램 실시간 현재 위치다. 압출 중 값이 변한다. |
| `ContainerPosition_D0012` | v2 CSV only | `D0012 / 10.0` | mm | `hmi_confirmed_actual_position` | 콘테이너 실시간 현재 위치다. 생산 중 짧아지고 생산 종료 후 빌렛 투입 시 증가한다. |
| `BilletLength` | v1 CSV, v2 CSV | `D1911` via `D1900[11]` | mm | `hmi_confirmed` | 빌렛 투입 시점에 600-690 mm 수준으로 나타나고, 예열/idle 및 투입 완료 후에는 0으로 표시된다. |
| `ButtLength_HMI_B1880` | sidecar metadata only | `B1880 Float32 LH` | mm | `hmi_confirmed_separate_field` | HMI의 "버트 길이" 값이다. v1 `BilletLength` 대체값이 아니므로 v2 본문 컬럼으로 쓰지 않는다. |

## HEADERS.csv 정책

v1 row 생성 순서는 `V1_CSV_COLUMNS` contract에 고정되어 있다. 따라서 `HEADERS.csv`는 자유 문자열이 아니라
위치별 canonical 또는 허용 alias만 사용할 수 있다.

허용되지 않는 예:

- 21개 컬럼 수는 맞지만 `Speed`와 `EndPos` 위치를 바꾼 header
- `BilletLength` 위치에 `ButtLength`처럼 다른 물리량을 넣은 header
- 알 수 없는 사용자 정의명을 기존 컬럼 위치에 넣은 header

이 경우 writer는 warning을 남기고 canonical v1 header로 fallback한다. v1 데이터 row의 21컬럼 순서는 바뀌지 않는다.

## 서버 24시간 shadow logging 검증 계획

### 1. 사전 조건

- 서버 PC에서 NSIS 재설치 전 `config.ini`, `state.json`을 백업한다.
- 기본 배포에서는 `position_read_enabled=false`를 유지한다. 이 상태에서는 v2 위치 컬럼이 빈 값일 수 있지만, 추가 PLC read 부하는 없다.
- 24시간 위치 검증을 수행할 때만 `config.ini`에 다음 설정을 둔다.

```ini
[EXTRUDER]
position_read_enabled=true

[LOGGING]
csv_v2_enabled=true
csv_v2_sidecar_enabled=true
```

환경변수로 실행하는 경우 `POSITION_READ_ENABLED=true`가 `[EXTRUDER] position_read_enabled=true`보다 우선한다.

- v1 CSV가 기존처럼 `Factory_Integrated_Log_YYYYMMDD_HHMMSS.csv` 형식으로 생성되는지 먼저 확인한다.
- v2 CSV가 `Factory_Integrated_Log_v2_*.csv`로 별도 생성되는지 확인한다.

### 2. 수집 산출물

개발 PC로 이동해도 되는 파일:

- `Factory_Integrated_Log_YYYYMMDD_HHMMSS.csv`
- `Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv`
- `Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.metadata.json`

이동하지 않는 파일:

- 서버 전체 `config.ini`
- `state.json`
- 앱 전체 로그 디렉터리
- 네트워크, 계정, 작업자, 고객 관련 민감 정보가 포함될 수 있는 파일

### 3. 1차 확인

10-30분 수집 후 다음을 확인한다.

- v1과 v2 파일이 동시에 생성된다.
- v1 header는 21컬럼이고 기존 소비자 contract와 동일하다.
- v2 header에는 `schema_version=2.2.0`, `MainRamPosition_D0010`, `ContainerPosition_D0012`,
  `Product_No_operator`, `Mold_No_operator`, `operator_metadata_valid`,
  `operator_metadata_missing_fields`, `operator_metadata_updated_at`가 있다.
- sidecar `sensor_metadata`에 `EndPos`, `MainRamPosition_D0010`, `ContainerPosition_D0012`, `ButtLength_HMI_B1880`의 `mapping_status`가 기록된다.
- sidecar `operator_metadata`에 `product_no`, `operator_mold_no` 필수 필드와 `operator_metadata_version=1.0.0`이 기록된다.
- Validator compatibility: `scripts/validate_csv_v2_shadow.py` accepts legacy
  `schema_version=2.1.0` files without operator metadata, while enforcing
  operator metadata columns and sidecar fields for `schema_version=2.2.0`.
- sidecar `schema_metadata.position_read_feature_flag`는 `EXTRUDER.position_read_enabled or POSITION_READ_ENABLED`로 기록된다.
- 앱 로그에 `CSV log queue full`, `CSV v2 buffer dropped`, PLC timeout 증가가 없는지 확인한다.

### 4. 24시간 확인

24시간 수집 후 다음을 비교한다.

- v1 row count와 v2 row count가 동일하거나, 재시작/rollover 시점의 차이가 설명 가능하다.
- v1 `EndPos`는 설정값 성격으로 큰 변동이 없어야 한다.
- v2 `MainRamPosition_D0010`은 압출 중 움직임을 보여야 한다.
- v2 `ContainerPosition_D0012`는 빌렛 투입과 생산 흐름에 맞는 변화를 보여야 한다.
- `sample_seq`는 v2 파일 내에서 단조 증가해야 한다.
- `captured_at_extruder`, `captured_at_ls`, `captured_at_spot`는 장비별 polling 주기 차이를 설명할 수 있어야 한다.

개발 PC로 파일을 옮긴 뒤 다음 명령으로 1차 contract 검증을 수행한다.

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\validate_csv_v2_shadow.py `
  --v1 "Z:\Factory_Integrated_Log_YYYYMMDD_HHMMSS.csv" `
  --v2 "Z:\Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv" `
  --metadata "Z:\Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.metadata.json"
```

이 스크립트는 다음을 확인한다.

- v1 header 21컬럼 canonical contract
- v2 필수 컬럼 존재
- metadata schema version과 mapping status
- v1/v2 row count parity
- v2 `sample_seq` 단조 증가
- `MainRamPosition_D0010`, `ContainerPosition_D0012` populated value 요약

### 5. 성공 기준

- v1 CSV 21컬럼 호환성 유지.
- v2 CSV/sidecar 생성 실패가 v1 CSV 저장을 막지 않음.
- 새 `D0010/D0012` read 추가 후 24시간 동안 queue drop, 반복 timeout, 파일 write failure가 운영상 증가하지 않음.
- `EndPos`를 실제 위치로 해석하는 downstream 문서나 분석 코드가 없음.

### 6. 실패 기준과 rollback

실패 기준:

- v1 CSV 누락, 컬럼 수 변경, header-row 의미 불일치 발생.
- v2 활성화 후 PLC timeout 또는 snapshot stale이 운영상 증가.
- v2 writer 실패가 반복되고 운영 로그가 warning/error로 계속 증가.

rollback:

```ini
[EXTRUDER]
position_read_enabled=false

[LOGGING]
csv_v2_enabled=false
```

이 설정으로 추가 위치 read와 v2 writer를 모두 중단한다. v1 CSV는 계속 유지한다.

### 7. Daily rollover 운영 추가 기준

- 자정이 포함된 24시간 수집에서는 날짜별로 v1/v2 CSV 파일 수가 증가한다.
  예: 자정 전후를 모두 포함하면 v1 2개, v2 2개, v2 sidecar 2개가 생성된다.
- downstream 소비자는 v1 파일 목록과 v2 파일 목록을 별도 패턴으로 모은 뒤 timestamp suffix 기준으로 정렬/매칭해야 한다.
- row count는 같은 날짜 boundary의 v1 파일과 v2 파일을 쌍으로 묶어 비교한다.
  전체 기간 합산 row count도 v1 합계와 v2 합계가 동일해야 한다.
- 각 v2 CSV는 같은 timestamp suffix를 가진 `.metadata.json` sidecar가 있어야 한다.
- rollover 직전 파일 write/flush 실패가 있으면 새 날짜 row가 기존 날짜 파일에 섞이면 안 된다.
  이전 날짜 flush가 복구된 뒤 새 날짜 파일에 기록되어야 하며, 관련 warning 로그를 함께 보존한다.
- shutdown 중 보류 row가 있으면 이전 날짜 final flush 성공 후 새 날짜 파일에 기록되어야 한다.
  실패가 지속되어 기록하지 못한 경우 warning 로그를 보존하고 row count 불일치 원인으로 기록한다.
- `sample_seq`는 프로세스/세션 단위 값이므로 rollover 시 1로 reset하지 않는다.
