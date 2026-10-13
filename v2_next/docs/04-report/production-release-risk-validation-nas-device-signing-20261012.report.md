# 2026-10-12 NAS 사본 전수 파싱·장비 직접 대조·서명 선행 조건

이번 단계는 실제 NAS 과거 CSV 사본 검사와 장비 화면의 추가 직접 대조를 수행했다.
전체 목표는 Do 진행 중이며 R1~R6 정식 출시 HOLD를 유지한다.

## NAS 공유 자료의 출처와 사본

증거 루트: `C:/Users/user/Desktop/SmartFactory/PDCA_DEPEND_20261012_f0b8bd00`.
개발 PC `DESKTOP-SS5CURC`에서 이전 고정 scope의 NAS UNC 주소를 직접 읽었다.
개발 PC Z 매핑은 hostname 표기이고 scope는 IP 표기여서 최초의 문자열 일치 guard가 exit 1로 중단됐다.
이를 연결 실패로 기록하지 않는다. R2는 원래 UNC 주소를 직접 사용했으며 Z alias 동일성을 가정하지 않았다.
서버 RDP의 새 NAS 도우미 실행/로컬 해시 검증을 대신하는 증거로 사용하지 않는다.

NAS 최상위와 직계 하위 목록은 일반 파일 1,528개·디렉터리 37개·1,565행·2,473,076,202 bytes다.
오류/시간 예산 초과 0, 최초 2.8235838초·종료 목록 3.3445428초, native PS5.1 exit 0.
더 깊은 하위와 recycle 내부는 미조사다. Source JSONL·summary 해시와 전체 행 중복을 독립 대조했다.

선택한 CSV 1,523개는 총 2,313,401,165 bytes, 가장 최근 수정 시각은 2026-02-09이다.
모든 선택 파일의 SMB Read 공유 스트림을 복사 전에 열어 협력 writer/delete를 차단했다.
기존 writer가 있으면 열기를 실패시키며 최근 수정 자료도 별도 절차 대상으로 거부한다.
같은 스트림의 SHA256 → 사본 SHA256 → 마지막 전체 입력 재해시를 대조했다.
선택 입력 전체가 일치했고 native PS5.1 복사 exit 0, 328.9232776초다.
전체 NAS/서버의 원자적 snapshot이나 다른 접근 프로토콜의 writer 통제를 주장하지 않는다.

사본 manifest SHA256: `38858DE1611CF58B9220545B0227A72F427F04CBCBA3FE480650890BE95F4C20`.
검사 후 원본 선택 CSV의 경로 집합·크기·수정 시각을 다시 대조해 변화가 없음을 확인했다.
12개는 archive와 같은 내용의 추가 사본이다. 원본을 삭제/변경하지 않았으며 물리 파일/행 집계에 중복 사본이 포함된다.

## CSV 전체 행 검사와 남은 의미 검증

| 관측된 형식 | 파일 | 행 |
|---|---:|---:|
| 6열 병합 자료 | 1 | 89,776 |
| 19열 과거 로그 | 1,327 | 1,569,896 |
| 21열 과거 로그 | 195 | 17,658,777 |
| 전체 물리 사본 | 1,523 | 19,318,449 |

`audit-nas-plaintext.py`가 모든 행의 strict CSV 구문·UTF-8·행 너비·빈/중복 header·NUL을 검사했다.
구조/인코딩 문제 0, 날짜 파싱 문제 0, 검사 전후 모든 사본 해시와 파일 identity 일치, exit 0.
80.59399999999732초다. 같은 내용 사본을 합친 unique content는 1,511개·15,867,019행이다.
현재 `validate_csv_v2_shadow.py`의 CLI는 v2와 metadata가 필요하고 v1 required 이름도 이 과거 header와 다르다.
과거 자료에 현행 v2 요구사항/프로파일을 소급하지 않고 구조 검사와 생성 버전·센서 의미 판정을 구분한다.

시간 값 감소는 물리 파일 10개/unique content 8개에서 관측됐다.
예: 2025-12-15의 20:26:20.916 → 20:26:08.992(-11.924초). 실제 OS/생성자 timing 증거가 없어 원인은 UNCONFIRMED다.
숫자가 아닌 온도 898건은 단일 병합 파일의 `-` 값이다. 누락 표지의 생성/승인 의미는 미확인이다.
이 관측을 정상·손상·현행 프로그램 결함으로 단정하거나 원본을 보정하지 않는다.
`historical_schema_and_sensor_semantic_gate=NOT_EVALUATED`, `full_data_gate=NOT_EVALUATED`를 유지한다.

## 실제 장비 추가 직접 읽기

장비 홈 source에 있는 Enter 폼 GET으로 메뉴를 열고 HTML을 공유 return으로 저장/회수했다.
메뉴 HTML의 30초 자동 홈 복귀를 확인했다. 앞선 클릭 전에 화면이 만료했을 가능성이 있다(추정).
메뉴에 실제 노출된 I/O·Alarms·Settings 링크로 이동했다. 값/checkbox/radio를 수정하거나 적용하지 않았다.
인증·펌웨어·네트워크 설정 조작은 수행하지 않았으며 이후 홈으로 복귀했다.

| 항목 | 실제 화면 관측 |
|---|---|
| I/O | 4-20mA, N-Open, 4mA=200°C, 20mA=800°C, Span unchecked, CMD In `-----`, CMD Out Alarms |
| Low Signal | enabled unchecked, 2% |
| 기타 Alarm | Low Target 200°C, High Target 700°C, Low Instrument 0°C, High Instrument 60°C; 모두 unchecked |
| Core | App1: AL E, 200-900°C, Units C |
| Emissivity 화면 | 순간 표시 E1=0.066, E2=0.061, Non-Greyness=1.081; 이를 고정 승인 상수로 사용하지 않음 |
| 부가 표시 | Background unchecked/0°C, Process Window unchecked, Window Obsc 12.0% |

Mode/range·analog 4/20mA·Low Signal enabled/threshold가 이전 설정/metadata의 해당 필드와 일치한다.
모델 표시명 매핑·승인된 전체 프로파일·운영자 실명·comparator `<`/`<=` 경계·최종 build attestation은 미완료다.
기존 fingerprint mismatch/effective verification false를 유지하며 GUI 대조 때문에 PASS나 새 attestation으로 바꾸지 않는다.
SDK `not_supported` 기록은 유지하고 이 GUI 수동 읽기 증거를 별도로 구분한다.

## 서명 빌드의 실제 선행 조건

GitHub read-only API로 protected 기본 브랜치 master와 commit `eb9af6f1398d588733f3f1884411e2612496d267`을 확인했다.
현재 로컬 base와 같으며 후보 변경은 아직 uncommitted다.
production-signing 환경은 master branch policy이고 현재 required reviewer rule은 표시되지 않는다.
2026-10-12T05:25:45Z 최종 재조회에서 환경/저장소 secret 목록 각각 0개(exit 0)다.
환경/저장소 `WINDOWS_CODE_SIGNING_CERT_SHA1` 조회는 각각 HTTP404/exit1이다.
User 소유 저장소여서 조직 secret 상속으로 이 부재를 보완한다고 가정하지 않는다.

필수 `WINDOWS_CODE_SIGNING_PFX_BASE64`, `WINDOWS_CODE_SIGNING_PFX_PASSWORD`, 기대 서명자 변수가 없다.
개발 PC CurrentUser/LocalMachine My의 code-signing 인증서 0, 선택 서버 목록의 pfx/p12/cer/crt 파일명 0이다.
서버 certificate store·다른 경로·archive 전체 부재를 증명한 것은 아니다. 개인키/secret 값을 읽거나 출력하지 않았다.
승인 인증서의 사용 가능 여부·담당자를 요청했으며 아직 답변이 없다. 서명 workflow/설치/승격은 실행하지 않았다.

## 전체 목표에서 계속 남은 일

실제 담당자/승인 프로파일, NAS native 추가 실행, 현재 AppData 전체 일관된 사본·이미지·모든 CSV/fact/schema/종료 delta,
NAS 하위/다른 자료 범위, 과거 의미/원인, 원본 timeout/drop 인과·전체 성능, 최종 clean commit의 서명 설치본,
동일 설치·복구·현장 QA·15분/120분 및 실제 승격 후 다음 롤백 기준 갱신은 미완료다.
운영본/롤백은 기존 승인·검증된 541d 설치본 기준을 보존한다. 새 데이터 검사 완료가 전체 PDCA 완료는 아니다.
