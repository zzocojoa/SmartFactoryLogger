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
| `[LOGGING] csv_v1_enabled` | `CSV_V1_ENABLED` | `true` | `Factory_Integrated_Log_*.csv` 저장 |
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
