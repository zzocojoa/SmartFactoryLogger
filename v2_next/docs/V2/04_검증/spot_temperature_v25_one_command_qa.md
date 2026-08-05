# SPOT Temperature v2.5 한 번에 검증

> 이 묶음은 SmartFactoryLogger를 업그레이드하거나 설정을 임의로 변경하지 않는다.
> 서버에는 v2.5 설치본이 있어야 하며, 최초 한 번의 config attestation은 별도 도구로 적용한다.

## 서버로 옮길 파일

개발 컴퓨터에서 다음 명령으로 portable QA 묶음을 만든다.

```powershell
.\scripts\build_spot_temperature_v25_qa_bundle.ps1
```

생성된 ZIP 하나를 서버로 복사해 압축을 푼다.

```text
dist\spot-temperature-v25-qa.zip
```

압축을 풀면 다음 파일이 같은 폴더에 있어야 한다.

```text
qa_spot_temperature_v25.cmd
qa_spot_temperature_v25.ps1
apply_spot_temperature_v25_attestation.cmd
apply_spot_temperature_v25_attestation.ps1
validate_csv_v2_shadow.exe
README.md
bundle-manifest.json
```

서버에 Python이나 Git 저장소를 설치할 필요는 없다.

## 최초 attestation

이미 `ATTESTATION APPLIED`를 확인했다면 이 단계는 다시 하지 않는다.

처음 한 번만 SmartFactoryLogger를 완전히 닫고 다음 명령을 실행한다.

```powershell
.\apply_spot_temperature_v25_attestation.cmd
```

화면에 표시된 SPOT model, app mode, Low Signal 설정이 실제 장비와 일치할 때만
운영자 ID를 입력하고 `CONFIRM`을 입력한다. 도구는 기존 `config.ini`를 백업한 뒤
다음 네 개의 `[SPOT]` attestation 필드만 갱신한다.

```text
config_operator_verified
config_verified_at
config_verified_by
config_verified_fingerprint_sha256
```

새 설치본으로 업그레이드하면 build commit이 fingerprint에 포함되므로 첫 QA에서
`fingerprint_mismatch`가 한 번 발생할 수 있다. 이 경우 QA가 백엔드를 정상 종료한 뒤
attestation 도구를 다시 실행한다. 도구는 `spot_config_fingerprint_sha256` 단독 drift만
운영자 재확인 대상으로 허용하며, 장비 readback이나 다른 drift는 계속 차단한다.

## 한 번에 QA 실행

1. SmartFactoryLogger를 실행한다.
2. 화면에 SPOT 온도가 표시될 때까지 기다린다.
3. QA 폴더에서 다음 명령을 실행한다.

```powershell
.\qa_spot_temperature_v25.cmd
```

도구가 60초 동안 runtime을 관찰한 뒤 다음 안내를 표시한다.

```text
Finalizing SmartFactoryLogger CSV files safely.
[ACTION] Close SmartFactoryLogger with the window X button.
Do not use Task Manager and do not stop SmartFactoryBackend.exe directly.
After closing the SmartFactoryLogger window, press Enter to continue
```

이때 SmartFactoryLogger 창의 X 버튼으로 정상 종료하고 backend가 완전히 종료될 때까지
기다린 뒤 Enter를 누른다. QA는 backend 종료를 직접 요청하지 않으며, 정상 UI 종료가
CSV와 manifest를 마무리한 뒤 validator를 계속 실행한다. 작업 관리자나
`SmartFactoryBackend.exe` 직접 종료는 사용하지 않는다. 장비 설정과 `config.ini`는
변경하지 않는다.

마지막에 다음 문구가 나오면 검증 완료다.

```text
FINAL RESULT: PASS
```

PASS 또는 FAIL 결과가 나온 뒤 운영이 필요하면 SmartFactoryLogger를 다시 실행한다.

## 종료 파일 선택 기준

QA는 60초 관찰 중 보였던 CSV 파일명 하나를 그대로 신뢰하지 않는다.
운영자가 창의 X로 정상 종료한 뒤 동일 logger instance와 build commit의
sidecar 중 `csv_closeout.closeout_reason=shutdown`인 파일을 찾는다.
daily rollover나 설정 변경으로 닫힌 파일은 선택하지 않는다.

종료 sidecar의 `final_persisted_sample_seq`는 해당 파일의 CSV write와 flush가
성공한 뒤 기록된 값이어야 한다. repository validator는 이 값을 실제 CSV의
마지막 행 및 최댓값 `sample_seq`와 비교한다. 값이 없거나 다르면 QA는
fail closed 처리한다.

## FAIL인 경우

화면에 표시된 `Evidence:` JSON 파일 하나만 개발 담당자에게 전달한다. 강제 종료하거나
attestation을 반복하지 않는다. 로그 경로를 자동으로 찾지 못한 경우에만 다음처럼 지정한다.

```powershell
.\qa_spot_temperature_v25.cmd -LogPath "C:\path\to\logs"
```

## 안전 범위

QA는 백엔드 종료 API를 호출하지 않는다. 운영자가 SmartFactoryLogger 창의 X 버튼으로
정상 종료한 사실과 backend process drain만 확인한다. SPOT 설정, 네트워크, CSV 내용
또는 config 값을 변경하지 않는다.

## 검증 기록

SmartFactoryLogger 1.0.13과 실장비 SPOT을 사용한 최종 서버 검증은 `31/31 PASS`,
warning `0`, full CSV validator PASS로 완료됐다.

### v1.0.17 릴리스 상태 (2026-08-05)

`575e869` 패키지의 re-attestation, QA, 15분 smoke, 120분 canary 결과는 그
commit에만 유효하다. 이후 `49fbf6b` 패키지는 X 버튼 종료 뒤 현재 session의
`csv_closeout.finalized=true` sidecar를 만들지 못해 QA가 fail closed 처리했고,
서버는 검증된 v1.0.16 installer로 rollback됐다. 이후 개발 패키지의 local native
X-close 검증은 통과했지만 서버에 설치되지 않았다. 최종 서명 package는 자신의
commit-bound re-attestation과 이 QA 전체를 새로 통과해야 한다.

- [서버 검증 보고서](../../04-report/spot-temperature-v2-5-server-validation.md)
- [Sanitized evidence](../../04-report/evidence/sfl-spot-temperature-v25-qa-20260713-233141.sanitized.json)
