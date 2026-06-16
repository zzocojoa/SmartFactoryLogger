# CSV v2 UI 필드 의미 보정

작성일: 2026-06-16

## 목적

기존 UI 문서에서 `EndPos`가 공정 위치 계열 값처럼 묶여 있어 실제 이동 위치로 오해될 수 있다.
현장 HMI/PLC shadow logging 검증 결과를 기준으로 UI 표시 의미를 아래와 같이 정정한다.

## UI 표시 규칙

| 표시 후보 | source | UI 의미 | 표시 권장 |
| --- | --- | --- | --- |
| `EndPos` | `D0421 / 10.0` | 압출 종료 위치 설정값 또는 메인 램 총 길이 성격의 고정 설정값 | "종료 위치 설정값"처럼 설정값임을 드러낸다. 실제 위치 trend로 사용하지 않는다. |
| `MainRamPosition_D0010` | `D0010 / 10.0` | 메인 램 실시간 현재 위치 | v2 화면 또는 분석 화면에서 실제 위치 trend로 사용한다. |
| `ContainerPosition_D0012` | `D0012 / 10.0` | 콘테이너 실시간 현재 위치 | v2 화면 또는 분석 화면에서 실제 위치 trend로 사용한다. |
| `ButtLength_HMI_B1880` | `B1880 Float32 LH` | HMI의 "버트 길이" | 현재 UI 본문 지표가 아니라 mapping metadata로만 다룬다. v1 `BilletLength` 대체값으로 표시하지 않는다. |
| `BilletLength` | `D1911` via `D1900[11]` | 빌렛 투입 구간의 빌렛 길이 | v1 호환 표시를 유지한다. 예열/idle 및 투입 완료 후 0이 정상일 수 있다. |

## UI 구현 주의사항

- v1 화면에서 `EndPos` 이름을 유지해야 한다면 tooltip 또는 label에서 "설정값" 성격을 표시한다.
- 실제 위치 차트가 필요하면 v2 CSV의 `MainRamPosition_D0010`, `ContainerPosition_D0012`를 사용한다.
- 두 실제 위치 컬럼은 `POSITION_READ_ENABLED=true` 또는 `[EXTRUDER] position_read_enabled=true`일 때만 채워질 수 있다.
- `EndPos` threshold는 실제 위치 급변 감지가 아니라 설정값 변경 또는 비정상 설정값 감지로 해석해야 한다.
- `ButtLength_HMI_B1880`은 sidecar metadata에 존재하는 별도 HMI field다. v2 CSV 본문에는 넣지 않는다.
