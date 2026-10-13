# 최종 설정 기준과 실행 중 보고된 fingerprint의 경계 대조

작성일: 2026-10-14. 기준 HEAD: `0a17f2d51b6ce08ff48faa409e56e9f954b67a4e`.
설정 지문을 재계산하고 외부 SHA로 고정한 최종 attestation 기준과 비교하는 읽기 전용 모듈을
통합 관찰에 연결했다. 실제 후보/서버의 최종 attestation이나 물리 장비 검증은 완료하지 않았다.
R1–R6 HOLD·full_data_gate NOT_EVALUATED·목표 active·운영/다음 롤백541d/08C를 유지한다.

## 구현과 판단 범위

[설정 결합 모듈](../../scripts/field-v1028/field_configuration_binding.py)은
`/api/spot/config`의 `image` 진단에서 제품과 동일한22개 fingerprint 입력을 선택하고
canonical JSON SHA256을 재계산한다. 실제 제품 함수와 입력 집합·계산 결과를 대조했다.
build4cc, 설정 SHA·현재/승인 fingerprint, USER_SELF, UTC 확인 시각, readback·comparator·
drift·ratio 별칭과 필수 타입을 검사한다. 숫자로 보이는 문자열이나 bool을 숫자로 변환하지 않는다.

승인 기록 `94873cc2a677ccc79bfbda11f65b736717ff97ed0bf07fc8449254253cf995df`와 연결된
프로파일 중 소프트웨어에 표현된15개 값(모델/모드·범위·출력·Low Signal·필터·window·focus)을
비교한다. 방사율·출력 시간·Averager2·물리 배선 등 이 fingerprint에 없는 장비 조건은
별도 장비 증거가 필요하다. `not_supported`는 일치하는 운영자 attestation을 요구하며,
물리 readback 성공으로 바꾸지 않는다. API의 comparator=true도 물리 시험 증거 자체는 아니다.

최종 설정 기준 파일은32KiB 상한·외부 SHA·엄격 JSON·기존 Windows 잠금 읽기를 적용한다.
관찰 동안 잠금을 유지하고 종료 시 같은 바이트를 재검사한다. 문서가 스스로 일관된다는 사실은
승인의 증명이 아니다. 보호된 launcher가 실제 승인/attestation 출처를 확인하고 SHA를 고정해야 한다.
현재 운영본의 `fingerprint_mismatch`나 사용자 프로파일 승인만으로 최종 기준을 생성하지 않았다.
시험에서 사용하는 기준은 `SYNTHETIC_TEST_NOT_FIELD_APPROVAL`로 구분한다.

[통합 관찰](../../scripts/field-v1028/field_observation.py)은 첫 인증 뒤 설정 GET의
OS 식별/listener·SPOT 서비스·backend 생성 이후 snapshot과 기준을 확인한다. 초기 실패는
주기 수집 전에 중단하고, 종료 설정 불일치는 관찰 전체를 FAIL로 남긴다. 설정 GET에는 기존
전체5초 timeout을 적용하고 별도 성능 상한을 만들지 않는다. 기본 HTTP 주기는 유지한다.
범위는 `REPORTED_CONFIGURATION_BOUNDARIES`다. 이 결과는 보고된 시작·종료 설정의 일치이며
중간 모든 시점의 무변경, 설정 파일 자체의 독립 전수 읽기, 실제 장비 동작을 입증하지 않는다.

## 실패 재현과 검증

증거: [PDCA_CFG128_20261014_3b038f3d](C:/Users/user/Desktop/SmartFactory/PDCA_CFG128_20261014_3b038f3d).
최종 수정본은 `final-r2/source-final`의14개 Python 파일이다. native 프로세스/HTTP 시험은
개발 PC의 복사한 Python 바이너리를 사용한 격리 fixture이며 실제 Electron/후보 backend가 아니다.

| 검사 | 범위/결과 |
| --- | --- |
| 설정7시험 | 실제 제품22입력/지문 일치, 필수 필드22누락, 확인 상태/타입/시간16부정 사례, 외부 기준 SHA·읽기 잠금, 원문/서비스·OS 식별 |
| 통합26시험 | 정상 관찰, 초기 미확인·종료 설정 변경, 기준 종료 읽기 오류, 기존 세대·Job·IPC·timeout·원문 실패 |
| 인증8·HTTP31시험 | 기존 인증 토큰/loopback 계약과 HTTP 주기·예산·deadline·실패 보존 회귀 |
| 정상6.2초 fixture | health4/data2/image25, 누락·오류·timeout0. 공개 경계 GET 포함 health6, 자원/OS 각각2표본, 자원 coverage NOT_MEASURED |
| 실제 서버 보존 응답2개 | 원문 해시 대조 뒤 기존 fingerprint 재계산 일치. 후보 build/운영자/승인 지문·drift 검사는 FAIL 유지 |

기준 context의 종료 읽기에 오류를 주입한 회귀는 수정 전 exit1이었다. 감독 결과는 이미 FAIL이었으나
하위 worker에 PASS가 남았다. 예외 시 worker 상태도 FAIL로 바꾸고 수정 후 통합 회귀로 확인했다.
원래 실패·소스·원문은 `source-closeout-before`/`closeout-before`에 보존했다.
기본 Ruff 설정의 제외 규칙과 별도로 `--isolated --select F,E9`도 적용했다. 그 검사에서 발견한
미사용 timezone import를 제거한 뒤 최종 수정본의 설정·통합·인증·HTTP 검사를 다시 실행했다.
제품 코드·설정·설치본은 변경하지 않아 전체 제품 health/NSIS/현장 설치를 반복하지 않았다.
이번 소스로 새420초/15분/120분 성능 검사를 실행한 것은 아니다.

재검증(저장소 루트 PowerShell, 시험별 새 폴더):

```powershell
$configurationCheckRoot = Join-Path ([Environment]::GetFolderPath('Desktop')) ('SmartFactory/CFGCHECK_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $configurationCheckRoot | Out-Null
$env:SFL_CONFIGURATION_REPO = (Get-Location).Path
$env:SFL_CONFIGURATION_TEST_ROOT = Join-Path $configurationCheckRoot 'configuration'
$env:SFL_OBSERVATION_TEST_ROOT = Join-Path $configurationCheckRoot 'observation'
$env:SFL_GENERATION_TEST_ROOT = Join-Path $configurationCheckRoot 'generation'
$env:SFL_HTTP_TEST_ROOT = Join-Path $configurationCheckRoot 'http'
.\backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_configuration_binding.py -v
.\backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_observation.py -v
.\backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_generation_binding.py -v
.\backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_http_sampling.py -v
```

각 명령 직후 종료 코드와 stdout/stderr 전체를 보존한다. 사용 소스 SHA와 `source-final.json`을
대조하고 기준·응답 본문·구성요소 manifest·worker-result·Job 잔존0까지 검산한다.
이미 사용한 결과 경로는 재사용하지 않는다. 위 명령은 개발 fixture이며 서버 명령이 아니다.

## 최종 결과와 보존

최종72시험은 모두 exit0/skip0이다. 설정7시험2.790초, 통합26시험81.319초,
인증8시험2.552초, HTTP31시험8.144초였다.14개 소스와 검산 도우미의 독립 Ruff F/E9도
exit0이다. 정상 통합의 설정 GET은 시작2.1227ms/종료1.7012ms였으며 원문/판정/기준 SHA와
구성요소 manifest·worker-result를 재검산했다. 이 표본 수치를 장시간 성능 PASS로 확대하지 않는다.

최종 모듈 SHA256은 `96267dc3a859af8aed83f58288a1d3f6f261cc5bcc65ea37c3bfc440b29f4b98`,
통합 관찰은 `f9bbe24511aad94fbc40f8de7d0b8aab6ac740d7161d9e341c9b3ed7c3558936`다.
전체14파일의 길이/해시는 `final-r2/source-final.json`에 있다.

공유 보존 위치는 `Z:/SmartFactory/20261014/records/PDCA_CFG128_3b038f3d_r2`다.
ZIP6,838항목(manifest1개 포함), 원문189,975,893바이트(manifest 제외)를 보존했다.
ZIP72,539,852바이트/SHA256 `090f235037f2f425cbdc58c3ca4613a4f84fbbffb9f267d771d51e23af067296`,
manifest SHA256 `9ce97def5ae1a1d1efc6c93e00ea99e380e598c9b6a09b47eaf098b33b420284`다.
모든 ZIP 항목의 SHA/크기/CRC와 공유 ZIP·manifest의 전체 SHA를 검산했다.

실패 재현과 import 정리 전 결과는 별도 `Z:/SmartFactory/20261014/records/PDCA_CFG128_3b038f3d`에
13,683항목으로 보존했다. 원문379,711,717바이트, ZIP SHA256
`91a173dd429d9783352a228965fb33623efc1f70a6376b84a7909ff3eb37e9bd`, manifest SHA256
`9e4b08d59d42622fc6ab09ec163674bf4a985e728bd59f8ef295020c58b76dcb`다.
봉인 뒤 문서/상태/최종 저장소 확인 영수증은 별도 로컬 파일로 보존한다.

## 발견한 기존 프로파일 계약 차이

4cc의 `validate_csv_v2_shadow.py --require-current-server-promotion-profile`은
`low_signal_comparator_verified=False`를 요구한다. 같은 후보의 `qa_spot_temperature_v25.ps1`
최종 QA는 True를 요구한다. 실제 제품 함수로 만든 verified snapshot을 첫 검사에 넘겨 정확히
그 한 필드가 거부되는 것을 재현했다(`existing-profile-contract-conflict.json`).
현재 운영 프로파일 옵션과 최종 QA의 적용 범위를 정합화해야 하며, 과거 결과를 PASS로 바꾸거나
검사를 생략해서 해결하지 않는다. 이번에는 두 기존 도구를 수정하지 않았고 현장 실행 조건으로 남겼다.

## 설계 대비 남은 조건

설계5.10의 읽기 전용 기준/경계 결합은 개발 범위에서 제공한다. 실제 승인된 최종 기준은 아직
없으며 제조사 App1 경계 답변·물리 시험·최종 attestation과 종료 metadata 대조가 필요하다.
보호된 외부 실행기·UI/packet·정상 종료/최종 delta·실제 설치/복구/세 번 시작·15분/120분 QA,
과거 finding 처리와 전체 데이터 gate·운영 승격/롤백 기준 갱신도 계속 남는다.
새 모듈의 서버 전달·실행·설치와 운영 설정 변경은 수행하지 않았다.
