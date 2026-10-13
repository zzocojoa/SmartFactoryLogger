# 1.0.28 현장 준비 패키지 식별 검증과 서버 전달

2026-10-13. 후보·현재 롤백 설치본, QA 구성요소와 기준 자료를 결합한 준비 패키지의
개발 PC 검증과 서버 로컬 복사를 완료했다. 설치·설정 attestation·현장 QA·15분/120분
관찰·승격은 미실행이다. R1–R6 HOLD, `full_data_gate=NOT_EVALUATED`를 유지한다.

## 대상과 고정 바이트

| 역할 | 버전 / build commit | installer SHA256 / 바이트 |
| --- | --- | --- |
| 후보 | 1.0.28 / `4cc7393e1bafbf90a329726aed9470fe0daacb21` | `8821746bbed47850ead68c66894e5580afac63483b1569865915dadc30cfc848` /164618981 |
| 현재 운영본·다음 변경의 롤백 기준 | 1.0.26 / `541d701d544eea6a8a4e4836047077eaf9cfaf30` | `08c061ee35a1a01788f05b00ee7395aa40774150c92c06726a92f3df1bf75c3c` /163826264 |

두 설치본의 실제 Authenticode는 `NotSigned`다. 미서명 내부 운영 정책이 적용되며,
서명 확보를 남은 조건으로 추가하지 않는다. 기존 설치본·제품 소스는 수정하거나 재빌드하지 않았다.

- [개발 패키지 설명](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/package/README_KO.md): 27파일 /338,491,556바이트.
- [패키지 manifest](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/package/package-manifest.json) SHA256: `58012882bd9ae382c741e2b5e2fc045c8fa9a7959fe273083db8b1113c43fd6b`.
- [패키지에 전달한 검증기](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/package/verify-field-package.ps1) SHA256: `56144abd5439b15bdd8dda8c00840d1561fdb5370bc0fdb065187eb5e176fb5e`.
- [최종 저장소 소스](../../scripts/field-v1028/verify-field-package.ps1) SHA256: `f8a3f3575b6a513bdff0c3158d53f31235bc67b2bf752669861629f09b454eec`. 아래 최종 줄 정리 이력을 따른다.
- [복사 출처](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/source-copies.json)에 원본 경로·크기·SHA를 보존했다. 원본→패키지→원본 해시가 같았다.

QA12파일은 [직전 휴대형 검사기](production-release-risk-validation-portable-qa-20261013.report.md)와 같은 바이트다.
reference10파일에는 payload1814파일 목록, backend1687파일 출처, Electron 검증,
기존 health·NSIS 판정·프로파일 승인·운영/롤백 기준·경로 정책·출시 계획이 들어 있다.
health의 `installer_built=false`는 빌드 전 당시 기록이고, 이후 payload 검증과 구분한다.
NSIS 누적114/118·exit1과 후보 두 종료의 신규502=0 기록을 그대로 보존했다.

## 검증 범위와 결과

`verify-field-package.ps1`은 네이티브 Windows PowerShell5.1 x64에서 읽기만 수행한다.
외부 고정 manifest SHA를 확인한 뒤 manifest와 모든 선언 파일의 read handle을 유지하며
크기·해시·정확한 파일 목록·후보/롤백 identity·기존 payload/backend/QA 증거 연결을 검사한다.
경로 traversal·ADS 이름·중복·reparse·240자 초과를 거부한다. 설치/HTTP/프로세스 제어/
장비 설정 변경은 없다. 성공 출력에도 설치·canary·승격 false와 `release_gate=HOLD`를 남긴다.

| 시험 | 실제 종료 코드 | 결과 |
| --- | --- | --- |
| 실제 정상 패키지 최초/최종 | 0 /0 | 정상 묶음 확인 |
| 외부 hash, 후보 identity, 롤백 identity, canary 승인 주장 변조 | 각1 | 해당 원인으로 거부 |
| 중복, traversal, ADS 이름, 문자열 크기, 목록 누락, 파일 hash, 실물 누락 | 각1 | 해당 원인으로 거부 |
| 파일 hash를 다시 맞춘 payload commit, backend 출처, QA manifest 변조 | 각1 | 의미/고정 출처 연결 오류 거부 |
| 실제 NTFS junction, 실물 추가 파일 | 각1 | reparse-path /exact-file-set 거부 |

정상2·부정16, 총18실행의 stdout 전체를 결과 JSON과 대조하고 stderr18개가 비어 있음을
확인했다. [최초16시험](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/build-and-test-result.json),
[추가2시험](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/guard-test-result.json),
[최종 검산](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/verification-reviewed.json)을 보존한다.
producer2개·전송·최종 검산 도우미의 실제 종료는 모두0이며, 마지막 도우미는 동일 원본/검증기
SHA와 모든 원시 시험 출력을 재대조했다. 네이티브 PS5.1 parse 오류0·exit0,
외부 Python 도우미4개의 Ruff F/E9 exit0이다. 제품 변경이 없어 전체 health/NSIS는 반복하지 않았다.

최초 staged `git diff --check`는 파일 끝의 빈 줄1개로 exit2였다. 저장소 검증기 끝의 LF1바이트만
제거했고, 전달한 도구·manifest·봉인 기록은 변경하지 않았다. 최종 소스+LF1바이트가 앞선
시험/전달 바이트와 정확히 같은 것을 [소스 정리 기록](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/source-finalization.json)에 남겼다.
[최종 저장소 소스 실행](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/repository-final-test.json)도
실제 정상 패키지에 exit0·stderr0·기존 성공 JSON과 동일했다. 이 추가1실행은 위18실행과 구분한다.
두 후속 기록은 봉인 이후 로컬에 별도 보존한다. 서버 launcher를 준비할 때는 실제 전달 바이트의
SHA56144abd를 사용하며 저장소 파일 SHA와 혼동하지 않는다.

이 검사는 전달 묶음의 바이트/출처를 확인한다. 실제 설치 트리의 전수 해시 검증이나
현장 기술 QA가 아니다. 검증기 자체를 외부 SHA로 고정하고 같은 잠금 바이트를 실행하는
서버 launcher는 후속 준비 대상이다. 현재 스크립트를 서버에서 바로 실행하도록 안내하지 않았다.
read handle과 사전 경로 검사만으로 사용자 쓰기 가능 부모의 모든 적대적 경로 교체를 막는다고 주장하지 않는다.

## 서버 전달

- 공유: `Z:\SmartFactory\20261013\send\PDCA_FIELD128_20261013_450e9f1b`.
- 서버 로컬: `C:\Users\user\Desktop\SmartFactory\PDCA_FIELD128_20261013_450e9f1b`.
- [개발→공유 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/shared-transfer.json): 27파일 전체 크기·SHA 일치, exit0.
- [서버 화면 확인](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/server-copy-observation.json): 21:36–21:39 KST 탐색기 폴더 복사 완료,
  실제 절대경로와 root3/installers2/qa12/reference10 파일 존재 확인. 서버 로컬 SHA는 미검증이다.

공유 동기화 중 첫 화면은 installers만 보였으며, root6항목이 모두 나타난 뒤 복사했다.
기존 폴더를 덮어쓰지 않았다. 탐색기를 최소화하여 운영 화면으로 복귀했다.
복귀 표본은 Running·EX/LS/SPOT/Temp/Comm OK, 제품60366·금형2·최근 적용21:25:53이었다.
이는 UI 표본이며 build/logger 동일성·지속 무오류 운전의 검증이 아니다. 작업 정보는 변경하지 않았다.

선택한 시험/전송 기록92파일은 `Z:\SmartFactory\20261013\records\PDCA_FIELD128_450e9f1b`에
복사하고 전체 SHA를 대조했다. manifest 제외1,469,156바이트,
[기록 manifest](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/records-manifest.json) SHA256은
`408eeaa7db723d75148e36408a6cd164514ae5e050eed4f6f287c267a95084dd`다.
대형 설치본/부정 fixture 사본은 중복 복사하지 않았고 junction을 따라가지 않았다.
봉인 뒤 만든 [기록 전송 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD128_20261013_450e9f1b/record-transfer.json)은 로컬에 별도 보존한다.
빌드 당시 검증기 소스 미커밋·서버 미전달 표지는 당시 값으로 유지하며 이 후속 전달 기록으로 연결한다.

## 다음 실행 조건

1. 잠긴 실행 launcher와 1.0.28용15분/120분 수집·판정 도구를 준비·검증한다. 기존1.0.26
   검토용 canary는 이전 설치본에 고정돼 있고 live 수집이 차단돼 있어 버전명 치환으로 재사용하지 않는다.
2. 제조사 App1/40.38 경계 근거·물리 시험, 과거 finding 영향/처리와 계획의 적용 전 조건을 확인한다.
3. 실제 서버 최신 상태·닫힌 최종 delta·백업/복구 적합성, 같은 build의 설정 attestation과 현장 QA를 연결한다.
4. 최종 QA·15분/120분 결과·정상 종료·실제 승격/적용 확인 뒤 운영본/다음 롤백 기준을 갱신한다.

이번 패키지 전달은 위 조건의 면제나 설치·승격 승인 기록이 아니다.
