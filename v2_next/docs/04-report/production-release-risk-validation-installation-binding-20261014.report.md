# 현장 수집기: 설치 파일·프로세스·서비스 식별 결합

2026-10-14. 실제 후보 payload 1,814파일/562,754,082바이트에 새 검증기를 적용하고
최초 해시·핸들 보존·종료 전 재검사를 통과했다. 새 단위/통합23시험과 Ruff는 exit0다.
실행 중인 서버 후보와의 전체 결합은 아직 검증하지 않았다. R1–R6 HOLD,
`full_data_gate=NOT_EVALUATED`, 현재 운영/롤백541d/08C 및 미서명 정책을 유지한다.

## 변경과 사용 계약

기준 HEAD: `35aca6cbaaa9582d437cc48f5eae43059f7ca139`.
[수집기 결합 모듈](../../scripts/field-v1028/field_installation_binding.py)과
[회귀 검사](../../scripts/field-v1028/test_field_installation_binding.py)를 추가했다.
기존 제품·HTTP/자원 수집기는 변경하지 않았다.

- `InstalledPayload`는 외부 고정 reference SHA, 후보4cc7393e/1.0.28/installer8821746b,
  payload 수량·바이트·정확한 파일 집합과 clean Git provenance를 확인한다.
  기본 reference SHA는 `a5de26c2db81c8d69418fd3e574d4180b2dd895ab94b9cbf064959369644af5c`다.
- 로컬 절대경로240자, 원문 JSON2MiB, 파일512MiB/합계2GiB, 트리6000항목을 제한하고
  traversal·ADS 경로 이름·장치 이름·대소문자 중복·reparse·hardlink를 거부한다.
  일반 파일의 기본 스트림을 확인하는 검사이며 추가 스트림 전체 검사는 아니다.
- Windows `CreateFileW`의 read sharing만 허용한 핸들을 유지하고 그 핸들의 최종 경로와
  실제 파일 ID/크기/해시를 확인한다. 컨텍스트 종료와 진입 실패 때 핸들을 해제한다.
  [공유 모드와 잠금 수명](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
  [핸들의 최종 경로](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)를 근거로 구현했다.
  사용자 쓰기가 가능한 부모의 모든 적대적 경로 교체나 이미 로드된 메모리까지 증명하지 않는다.
- NSIS 추가 파일은 `Uninstall smart-factory.exe`와 `uninstallerIcon.ico`만 허용하며,
  호출자가 별도 신뢰 근거의 정확한 크기/SHA를 제공해야 한다. 관찰한 파일 자체에서
  허용 해시를 만들어 넣으면 안 된다. 이번 실제 추출 트리에는 추가 파일이 없었다.
- PID/create-time/exe, backend의 main 하위 관계, 해당 TCP 포트의 모든 관찰 listener 소유자를
  API 요청 앞뒤로 대조한다. IPv4 loopback에 도달할 listener도 요구한다.
  `/health` 원문과 시간·오류를 보존하고 version/frozen/REAL/frontend, build commit,
  SPOT·CSV logger UUID를 확인한다. 후속 표본의 서비스 ID 변경은 FAIL이다.
  연결 전후의 표본 검사이며 표본 사이의 모든 상태를 증명하지 않는다.

후속 launcher의 사용 순서:

1. 잠긴 launcher에서 기본 reference SHA와 NSIS 추가 파일의 출처를 고정한다.
   시험용 `expected_reference_sha256` 교체를 서버 실행 옵션으로 노출하지 않는다.
2. `InstalledPayload` 컨텍스트를 열고 정확한 실행 경로의 main/backend 생성 시각을 확정한다.
3. `capture_runtime_binding` 첫 결과가 PASS일 때만 그 프로세스/서비스 식별값을 고정한다.
   이후 같은 값으로 비교하고 실패·접근 거부·중단을 수집 실패로 보존한다.
4. 모든 health 요청의 최초값/지연/오류를 전체 HTTP 판정에 포함한다. 식별용 최초 GET도
   성능 통계에서 버리지 않는다. 이 모듈의 PASS는 식별 범위에만 해당한다.
5. 관찰 종료 때 `recheck()`로 파일 집합·ID·바이트를 대조한 뒤 핸들을 해제한다.
   파일/드라이버 대기에는 별도 외부 watchdog이 필요하며 앱 강제 종료를 대신하지 않는다.

## 실제 검증과 보존한 실패

증거 루트: [PDCA_BIND128_20261014_71b290fa](C:/Users/user/Desktop/SmartFactory/PDCA_BIND128_20261014_71b290fa).

| 검증 | 실제 결과와 범위 |
| --- | --- |
| 최초18시험 | exit1/errors2. 잘못 지정한 제거 프로그램 이름과 venv 중간 실행기 PID를 실제 listener PID로 가정한 시험 오류. 원문·수정 전 소스 보존 |
| 이름·PID handshake 수정 후18시험 | exit0. PID 검사를 완화하지 않고 자식이 보고한 실제 PID를 OS 조회로 검증 |
| 최종23시험 | exit0/skip0. 실제 쓰기·rename·delete 잠금, 기존 writer 충돌, 잠금 해제, hardlink/junction 거부, 잘못된 payload·출처·서비스·listener·프로세스 종료·권한 오류 등 |
| 실제 후보 추출 트리 | 1,814파일/562,754,082바이트, 시작/종료 전 재검사 통과·핸들 해제. 전체22,441.047ms. 서버 설치 트리나 실행 중인 후보는 아님 |
| 실제 OS 프로세스/TCP | 개발 PC 시험 부모95744/자식96500, loopback52943 소유96500. 다른 PID 소유 포트·변경된 생성 시각·정상 종료 후 조회 거부. 시험 자식 종료0 |
| API 실패/세션 교체 fixture | 반환 원문25개(기대 PASS3/FAIL22)의 바이트·SHA 확인. 프로세스 관계는 이 fixture에서 모의 값이며 실제 OS 시험과 구분 |
| 기존 NSIS 후보 표본 | I4-candidate-runtime15개 health를 오프라인 파서로 검사. 같은 SPOT/logger ID 확인. 과거 실행을 현재 live 결합으로 계산하지 않음 |
| Ruff | 최종 모듈·시험·직접 의존4파일 exit0. 외부 검증/봉인 도우미2개 F/E9 exit0 |

명령은 `python -m unittest discover -s <final-source> -p test_field_installation_binding.py -v`와
`python -m ruff check <최종4파일>`이다. [최종 실행 기록](C:/Users/user/Desktop/SmartFactory/PDCA_BIND128_20261014_71b290fa/unit-final.json),
[전체 payload 결과](C:/Users/user/Desktop/SmartFactory/PDCA_BIND128_20261014_71b290fa/real-payload.json),
[원문 검산](C:/Users/user/Desktop/SmartFactory/PDCA_BIND128_20261014_71b290fa/verification-reviewed.json)에 연결한다.
제품·기존 HTTP/자원 바이트가 같으므로 기존 전체 health/NSIS/420초 시험은 반복하지 않았다.

최종 소스 SHA256:

- 모듈: `851f21190109cfb78f12930ea0331a4d676064d45d57a2020b1b08ab569a3d6c`.
- 시험: `43e9bb188bf5539769325affd9f7c504787f2de97ca3f05a3fb79ee8f0832fc1`.
- 기존 HTTP `e32ecdab…`, 자원 `517a28f6…`와 [최종 소스 기록](C:/Users/user/Desktop/SmartFactory/PDCA_BIND128_20261014_71b290fa/source-final.json)을 대조했다.

457파일을 `Z:/SmartFactory/20261014/records/PDCA_BIND128_71b290fa`에 복사하고 전부 해시 대조했다.
manifest 제외1,647,294바이트, manifest SHA256
`bd10e0bd0dfb08495cc8bf7292a11f0fb10ab7a368185459bc79122d9740de7b`.
시험 junction1개는 따라가지 않고 제외 목록에 기록했다. 입력 reference와 기존15표본도 묶음에 포함했다.
봉인 후 전송 영수증과 저장소 최종 검증 기록은 별도 로컬 파일로 보존한다.

## 현장 상태와 남은 조건

2026-10-14 00:00 KST 원격 탐색기에서 기존 `FREAD128_20261013_06df50b9`를 새로 고침했다.
원래5파일만 보였고 새 결과 폴더는 보이지 않았다. 이 관찰은 명령 미실행의 확정이나
서버 패키지 해시 통과가 아니다. 서버·장비 설정, 설치 및 운영본을 변경하지 않았다.

이번 새 모듈은 서버 미전달·미실행이다. 전체 보호 launcher/외부 watchdog,
authenticated backend generation·설정 fingerprint·승인 attestation,
HTTP/자원/화면/packet 및 최종 데이터·정상 종료의 같은 관찰 구간 연결이 남는다.
실제 후보 서버 설치/복구/3회 시작/15분/120분/현장 QA·과거 finding 처리·승격 후 적용 확인과
롤백 기준 갱신도 미완료다. 제조사 경계 답변과 물리 시험을 이 식별 검사로 대체하지 않는다.
