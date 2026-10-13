# 관찰 실행과 정상 종료 자료의 식별·설정 대조

작성일: 2026-10-14. 기준 HEAD: `faf8aeada597d53097b209005bf9b00ff4aa75a9`.
계측 마지막 health에 기록된 CSV를 종료 sidecar와 연결하는 모듈을 추가했다.
개발 검증57시험·독립 Ruff F/E9는 exit0/skip0이다. 실제 서버 정상 종료나 전체 현장 QA를
수행한 것은 아니다. R1–R6 HOLD·full_data_gate NOT_EVALUATED와 운영/다음 롤백541d/08C를 유지한다.

## 구현과 범위

[통합 관찰](../../scripts/field-v1028/field_observation.py)은 마지막 검증 health의 원문
크기/SHA·build·logger/SPOT UUID·schema·CSV 파일명·마지막 sample 번호를 확인하고
`shutdown-expectation.json`과 파일 해시를 worker 결과에 보존한다. 원문을 다시 HTTP로
요청하지 않는다. 잘못된 마지막 번호 등 필수 값 오류는 전체 관찰 FAIL이다.

[종료 파일 대조](../../scripts/field-v1028/field_shutdown_binding.py)는 기대값의 정확한
CSV/metadata 이름만 읽는다. 다른 실행의 최신 파일로 대체하지 않는다. Windows 읽기 공유
핸들로 원문을 잠그고 파일 식별·크기·SHA를 재확인한다. CSV는2GiB, metadata는4MiB 상한이다.
양쪽 build/logger·schema/hardening·finalized=true·shutdown 사유·최종 sample>=관찰 sample과
외부 SHA로 고정한 최종 설정의 fingerprint/attestation을 대조한다. 기준 context 종료에서
읽기 오류가 발생하면 내부 비교가 PASS여도 최종 결과는 FAIL이다.

`persisted_at`은 마지막 저장 시각이며 관찰 health보다 앞설 수 있다. 이를 프로세스 종료 시각으로
해석하지 않는다. 파일 식별 PASS만으로 정상 종료 수행/프로세스 소멸, CSV 전체 행·fact/image
연결을 증명하지 않는다. 관련 gate는 NOT_EVALUATED·release HOLD·promotion false다.
보호된 caller가 성공한 감독 결과/기대값 SHA와 이후 full validator 입력 바이트를 결합해야 한다.

## 기존 프로파일 옵션의 적용 범위 정리

후보4cc와 같은 제품 소스5개를 현재 checkout과 대조했다(EOL 차이만 정규화).
`qa_spot_temperature_v25.ps1`의 실제 validator 인수에는
`--require-current-server-promotion-profile`이 없다. 이 opt-in은 특정 과거 운영 프로파일의
comparator verified=false를 요구한다. 최종 QA는 별도로 verified=true를 요구한다.

합성 최종 설정을 일반 validator에 넣으면 오류0, opt-in을 적용하면 comparator 필드만 오류1이었다.
일반 범위/provenance 검사와 opt-in 동작을 기존5시험으로 확인했다. 따라서 제품 상수나
후보 설치본을 변경하지 않고 [계획 R4](../01-plan/features/production-release-risk-validation-codex-production-release-risk-validation-20261010.plan.md)의
적용 범위를 명확히 했다. 직전 보고서의 조건 차이 관찰은 보존하며, 실제 QA 호출 간 충돌은
없다는 후속 근거를 이 보고서에 추가한다. 최종 attestation 필요 조건은 유지한다.

## 검증

증거: [PDCA_END128_20261014_e5a85db5](C:/Users/user/Desktop/SmartFactory/PDCA_END128_20261014_e5a85db5).
`source-final`16개 Python 파일을 현재 소스와 바이트 단위로 대조했다. 시험별 stdout/stderr
전체와 명령·실제 종료 코드가 `test-results.json`, `csv-profile-test.json`에 있다.

| 검사 | 결과 |
| --- | --- |
| 종료 대조10시험 | 잘못된 build/logger/파일/schema/sample/종료 상태18사례, 필수 section/기대값 오류, 설정 재계산 변조, 실제 파일 잠금·원문 SHA·기준 종료 오류·다른 sidecar 대체 거부 |
| 통합27시험 | 정상6.2초, 새 종료 기대값/원문 SHA, 마지막 sample 오류, 기존 OS/Job/IPC/인증·설정 경계 실패 |
| 설정7·인증8시험 | 제품 fingerprint 직렬화 및 Windows/loopback 기존 계약 회귀 |
| CSV 프로파일5시험 | 일반 검사·opt-in·범위 거부·legacy provenance·readback fingerprint 회귀 |
| 독립 Ruff | 변경한4개 Python 파일에 `check --isolated --select F,E9`, exit0 |

정상6.2초 fixture의 health4/data2/image25 요청과 공개 경계 포함 health6을 확인했다.
HTTP/자원/프로세스 manifest의72파일 크기·SHA를 재검산했다. 계측 Job 잔존0,
자원 coverage NOT_MEASURED다. 이 합성 Python 앱은 실제 Electron/후보/현장 성능 증거가 아니다.

보존된 실제 후보 I4/I5의 정확한 sidecar SHA를 재확인하고 각 마지막 health의 logger·CSV·
sample과 대조했다. 두 건 모두 식별 PASS, 설정/attestation FAIL이다. 과거 JSON health는
재직렬화한 비교 입력으로 명시하며 새 collector의 wire 증거로 표시하지 않았다.
실제 최종 승인 기준을 만들거나 기존 기록을 수정하지 않았다.

재검증 예(저장소 루트 PowerShell, 항상 새 결과 폴더):

```powershell
$shutdownCheckRoot = Join-Path ([Environment]::GetFolderPath('Desktop')) ('SmartFactory/ENDCHECK_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $shutdownCheckRoot | Out-Null
$env:SFL_SHUTDOWN_TEST_ROOT = Join-Path $shutdownCheckRoot 'shutdown'
$env:SFL_OBSERVATION_TEST_ROOT = Join-Path $shutdownCheckRoot 'observation'
$env:SFL_CONFIGURATION_TEST_ROOT = Join-Path $shutdownCheckRoot 'configuration'
$env:SFL_CONFIGURATION_REPO = (Get-Location).Path
$env:SFL_GENERATION_TEST_ROOT = Join-Path $shutdownCheckRoot 'generation'
$env:SFL_SHUTDOWN_ARCHIVE = 'C:/Users/user/Desktop/SmartFactory/PDCA_NSIS_FIX_20261013_6b39ce41/output/matrix'
.\backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_shutdown_binding.py -v
.\backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_observation.py -v
.\backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_configuration_binding.py -v
.\backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_generation_binding.py -v
```

각 명령 직후 실제 exit와 원문을 보존한다. 기존 CSV5시험의 정확한 명령은 증거의
`csv-profile-test.json`에 있다. 서버 실행 명령이나 전체 QA 완료 절차가 아니다.

## 보존과 남은 조건

공유 기록: `Z:/SmartFactory/20261014/records/PDCA_END128_e5a85db5`.
ZIP6,811항목·83,294,240바이트, 원문219,177,967바이트(별도 manifest 제외)를 보존했다.
ZIP 내부 전 항목 크기/SHA/CRC와 공유 ZIP·manifest SHA를 확인했다.

- ZIP SHA256: `b8a49b1a7552c742e5060f7e78eaa2d4d1e72ec5225f4157ed435b000c6a7cf8`
- manifest SHA256: `cf97fb18deb6af5cefe5786e9f540256dd10a1c33b12b7813016c09f5b227f80`

이번 범위는 설계5.11의 기대값 보존·파일/설정 대조 모듈까지다. 보호된 외부 실행기·잠긴 배포,
화면/packet·정상 종료/최종 delta·full validator 바이트 연결·실제 최종 attestation 및 물리
comparator 확인은 남는다. 실제 서버 설치/복구/3회 시작/15분/120분 QA와 승격도 미완료다.
제품 코드·설치본을 변경하지 않아 전체 제품 health/build/NSIS를 반복하지 않았다.
이번 소스의 장시간 성능 검사와 서버 전달/실행은 수행하지 않았다. 목표는 active다.
