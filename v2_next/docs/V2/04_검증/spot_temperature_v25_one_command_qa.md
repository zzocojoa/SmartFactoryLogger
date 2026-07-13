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
Press Enter to stop backend logging safely and continue validation
```

이때 SmartFactoryLogger 창을 먼저 닫지 말고 Enter만 누른다. QA가 백엔드의 내장
graceful shutdown API로 CSV와 manifest를 마무리하고 validator까지 계속 실행한다.
장비 설정과 `config.ini`는 변경하지 않는다.

마지막에 다음 문구가 나오면 검증 완료다.

```text
FINAL RESULT: PASS
```

PASS 또는 FAIL 결과가 나온 뒤 남아 있는 SmartFactoryLogger 창을 닫는다.

## FAIL인 경우

화면에 표시된 `Evidence:` JSON 파일 하나만 개발 담당자에게 전달한다. 강제 종료하거나
attestation을 반복하지 않는다. 로그 경로를 자동으로 찾지 못한 경우에만 다음처럼 지정한다.

```powershell
.\qa_spot_temperature_v25.cmd -LogPath "C:\path\to\logs"
```

## 안전 범위

QA는 loopback 주소의 현재 백엔드만 정상 종료할 수 있다. 원격 BackendBaseUrl에는 종료
요청을 보내지 않는다. SPOT 설정, 네트워크, CSV 내용 또는 config 값을 변경하지 않는다.

## 검증 기록

SmartFactoryLogger 1.0.13과 실장비 SPOT을 사용한 최종 서버 검증은 `31/31 PASS`,
warning `0`, full CSV validator PASS로 완료됐다.

- [서버 검증 보고서](../../04-report/spot-temperature-v2-5-server-validation.md)
- [Sanitized evidence](../../04-report/evidence/sfl-spot-temperature-v25-qa-20260713-233141.sanitized.json)
