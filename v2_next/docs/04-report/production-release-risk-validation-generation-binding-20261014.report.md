# 인증된 백엔드 세대의 관찰 경계 결합

작성일: 2026-10-14. 기준 HEAD: `fe95b2cd20c4711c5c72eaddb6ba0714d333c9ce`.
개발용 수집기에 인증된 시작·종료 식별 검사를 연결했다. 최종 인증8·통합23·HTTP31시험은
모두 exit0/skip0이며 실제 후보·서버 QA는 수행하지 않았다. R1–R6 HOLD,
full_data_gate NOT_EVALUATED, 운영/다음 롤백541d/08C 및 미서명 내부 운영 정책을 유지한다.

## 변경과 검증 범위

[인증 식별 모듈](../../scripts/field-v1028/field_generation_binding.py)은 잠긴 설치 payload와
선택한 main/backend 경로를 확인한 뒤 OS PID/create-time/exe·listener를 대조한다.
backend 환경 API가 반환한 사전에서 embedded 표시·token·generation 세 항목만 사용한다.
전체 환경 사전은 메모리에서 읽지만 결과에 저장하지 않는다. 토큰과 요청 헤더도 저장하지 않는다.
환경 조회 앞뒤와 인증 GET 뒤의 OS 식별값이 다르면 FAIL이다. provider 예외는 타입과 고정된
오류 이유만 기록한다. 토큰 참조 해제는 메모리의 안전한 소거를 뜻하지 않는다.

[HTTP 모듈](../../scripts/field-v1028/field_http_sampling.py)은 고정 loopback의
`GET /api/control/health`에만 `X-SFL-Control-Token`을 허용한다. redirect를 따라가지 않고 기존
전체 요청 deadline·본문/헤더 제한을 적용한다. 응답에 토큰 원문·대소문자 변형·ASCII JSON
unicode escape가 있으면 본문/헤더를 비우고 FAIL로 기록한다. 임의 인코딩에 대한 완전한
민감정보 탐지라고 주장하지 않는다. 기본 health2초/data6초/image250ms 채널은 유지한다.

실제 후보4cc의 `main.js`·`backend/app.py`를 Git에서 읽어 현재 제품 소스와 바이트가 같음을
확인하고 `product-contract`에 보존했다. 계약은 running=true, 정확한 PID, 환경값과 같은
32자리 generation, 12자리 session, 프로세스 생성 이후 허용 범위의 UTC 시작 시각이다.
제품 코드·설정·설치본을 변경하지 않았다.

[통합 관찰](../../scripts/field-v1028/field_observation.py)은 첫 인증 검사를 통과해야 주기 관찰을
시작하고 마지막 인증 검사에 같은 identity를 요구한다. 두 GET 각각200ms 조건을 적용하며
첫 지연도 실패로 남긴다. 범위는 `AUTHENTICATED_BOUNDARY_SAMPLES`이며 표본 사이 모든
순간의 무변경을 입증하지 않는다. 이미 실행 중인 앱을 시작·종료하거나 설정을 바꾸지 않는다.

## 실제 시험과 실패 보존

증거 루트: [PDCA_GEN128_20261014_c734df19](C:/Users/user/Desktop/SmartFactory/PDCA_GEN128_20261014_c734df19).
최종 수정본은 그 아래 `final-r2/source-final`의12개 Python 파일이다.
Windows11/Python3.12.6/psutil7.2.2/Pillow12.3.0에서 실행했다.
native 프로세스·환경·listener 시험도 복사한 Python 바이너리의 격리 HTTP fixture를 사용한다.
실제 Electron/후보 backend가 실행됐다는 의미는 아니다.

| 검사 | 최종 결과와 의미 |
| --- | --- |
| 인증8시험 | 2.587초, exit0/skip0. 계약 오류12사례, 토큰 범위, 403/302, 전체 deadline, 응답 토큰 처리, 환경/프로세스 변경 포함 |
| 통합23시험 | 61.621초, exit0/skip0. 기존 Job 정리/앱 생존·IPC·원문 실패와 새 인증 세션 변경·첫 인증 지연 포함 |
| HTTP31시험 | 8.124초, exit0/skip0. 기존 공개 채널의 주기·응답·크기·오류 보존 계약 유지 |
| Unicode 토큰 응답 회귀 | 수정 전8시험 중1실패/exit1. `escaped-body-echo` 응답이 성공 처리된 문제를 재현하고 수정 후 exit0 |
| 정상6.2초 통합 fixture | health4/data2/image25, 누락·오류·timeout0. 공개 경계 GET 포함 health6개 |
| 인증 경계 | 첫1.2806ms/마지막18.107ms, 같은 PID/generation/session/시작 시각 |
| 지연 fixture | 첫 인증251.7227ms → FAIL. HTTP 주기 수집 폴더 생성 전 중단 |
| 세션 변경 fixture | 초기PASS/종료FAIL, 전체 관찰FAIL |
| 원문 검산 | 통합 manifest·worker-result SHA·native 인증3표본 본문 SHA/크기 확인, 종료 후 계측 Job 활성0 |
| Ruff | 최종12파일 및 외부 검산 도우미 검사 각각 exit0 |

수정 전 로그와 `source-before`를 보존했다. 임시 시험 토큰 자체를 실패 로그에 출력하지 않았다.
최종 stdout은 모두 비어 있고 stderr 전체·실제 종료 코드·원문을 확인했다.
이전420초 관찰은 이전 소스의 결과다. 이번에는 경계 인증 및 토큰 처리 변경에 영향을 받는
62시험을 실행했으며 장시간 성능·전체 제품 health·NSIS·현장 시험을 반복하지 않았다.
과거 ENOSPC 원인도 계속 미확정이다.

재검증 예시(저장소 루트 PowerShell, 기존 결과를 재사용하지 않음):

```powershell
$generationCheckRoot = Join-Path ([Environment]::GetFolderPath('Desktop')) ('SmartFactory/GENCHECK_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $generationCheckRoot | Out-Null
$env:SFL_GENERATION_TEST_ROOT = Join-Path $generationCheckRoot 'generation'
$env:SFL_OBSERVATION_TEST_ROOT = Join-Path $generationCheckRoot 'observation'
$env:SFL_HTTP_TEST_ROOT = Join-Path $generationCheckRoot 'http'
.\backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_generation_binding.py -v
.\backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_observation.py -v
.\backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_http_sampling.py -v
```

각 명령 직후 `$LASTEXITCODE`와 전체 출력을 보존·확인한다. 실행 전 `source-final.json`의
SHA와 사용 소스를 비교하고 각 결과의 manifest·경계 identity·Job 정리 결과까지 검산한다.
위 명령은 개발 PC fixture 검사이며 서버 실행 명령이 아니다.

## 최종 바이트와 공유 보존

| 최종 파일 | SHA256 |
| --- | --- |
| field_generation_binding.py | `8ff247c56a15f90598a3bd692cd628ff93bf1f27f69375dc8e86c2ed26b4ac7f` |
| field_http_sampling.py | `6762a7ab86543ddc2436b49ee03401dd76ebfc647af0f1bcc16bbcc88d80699e` |
| field_observation.py | `db08a244a586dd5dcddfab9152a3db7d99dbd5ac8bade4e29eeeb923628451d5` |
| test_field_generation_binding.py | `11625cbdd344d7157597b3bf51a3777995e7090e483d6f35f4d49f0ee10774cf` |
| test_field_observation.py | `06edef1bdb9fbec97ada637cc71113ade3db5017a02697fc5512892c795427f3` |

최종 보존 위치는 `Z:/SmartFactory/20261014/records/PDCA_GEN128_c734df19_r2`다.
ZIP6,600항목(그중 manifest1개), 원문116,959,089바이트(manifest 제외)를 담았다.
ZIP은45,219,301바이트/SHA256 `6165dd9c00a9a63cfc1029058d50d5aebdb07d86fc8a2e192c03bee94fa5686c`,
manifest SHA256은 `5a2d4edaf9ad89c7776d0a3f47c95c2f2fa88d335b0cd88fa29459c6a1e593a7`이다.
ZIP의 모든 항목은 원문 SHA/크기/CRC로, 공유 ZIP·manifest는 전체 SHA로 대조했다.

Unicode 보완 전 묶음은 별도 `Z:/SmartFactory/20261014/records/PDCA_GEN128_c734df19`에 보존했다.
12,943항목, 원문189,923,082바이트, ZIP SHA256
`275e22d2762f7683c909c1b42e3de6be203b04abf546f19f21931eed89250052`, manifest SHA256
`417ff93b88881ad74041d24f75f8f8436289ea4164dd68d7d48cb8a75e1ce934`다.
두 묶음의 봉인 뒤 문서/저장소 확인 영수증은 별도 로컬 파일로 보존하며 기존 봉인을 수정하지 않는다.

## 설계 대비 남은 조건

설계5.9의 경계 인증은 위 개발 범위에서 확인했다. 보호된 외부 launcher와 잠긴 실행 바이트,
최종 장비 fingerprint/attestation, UI/packet, 정상 앱 종료·최종 데이터 delta 통합이 남는다.
실제 후보/서버 설치·복구·세 번 시작·15분/120분 QA, 제조사 경계 근거와 물리 시험,
과거 finding 처리·전체 데이터 gate·운영 승격/실제 적용 확인도 미완료다.
새 모듈의 서버 전달·실행·설치 및 운영/롤백 기준 갱신은 수행하지 않았다.
