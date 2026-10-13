# 1.0.28 휴대형 CSV 검사기 준비·서버 전달

2026-10-13. 검사기 준비와 개발 PC 검증, 서버 로컬 파일 전달을 완료했다.
실제 현장 QA·장비 경계 시험·설치·canary·운영 승격은 미실행이며 출시 HOLD를 유지한다.

## 정확한 대상과 산출물

- 후보 build: `4cc7393e1bafbf90a329726aed9470fe0daacb21`, 1.0.28.
- 기존 installer SHA256: `8821746bbed47850ead68c66894e5580afac63483b1569865915dadc30cfc848`.
- 검사기: 9,494,053바이트, SHA256 `e728730ad841dd4a754a6c0880e0e1216de5e3d0cd5646c22de9245fc85b0b2f`.
- [개발 묶음](C:/Users/user/Desktop/SmartFactory/PDCA_QA128_20261013_32adee4e/QA128/README.md), [빌드 기록](C:/Users/user/Desktop/SmartFactory/PDCA_QA128_20261013_32adee4e/build-result.json),
  [최종 검산](C:/Users/user/Desktop/SmartFactory/PDCA_QA128_20261013_32adee4e/verification-reviewed.json).
- bundle manifest SHA256: `e2598e47c1f2c1e5140e07e55faca11842a082efc51ac60f34349d56c8e1ea29`.
- [보존 기록 manifest](C:/Users/user/Desktop/SmartFactory/PDCA_QA128_20261013_32adee4e/records-manifest.json): SHA256 `8075b4eae153795c76b262d0273ef7c995c2e3ae1f532525df4d3984ee98a08e`.

검증된 후보 source의 Python3.12.6·PyInstaller6.20.0와 같은 잠금 의존성으로 빌드했다.
소스/설치본을 재빌드·수정하지 않았다. source의 tracked1,009파일 전후 해시,
clean commit, installer SHA, 설치된 의존성40개의 동일성을 확인했다.
EXE 내 Python DLL과 직접 참조하는 backend 모듈7개도 확인했다.
PyInstaller optional/타 OS 모듈 경고는 원문으로 보존했다.

## 검증 결과

| 입력 | Python / EXE 실제 종료 코드 | 확인 |
| --- | --- | --- |
| 기존 NSIS 후보 설치 정상 종료327행 | 0 / 0 | 출력 동일 |
| 기존 NSIS 후보 재시작 정상 종료296행 | 0 / 0 | 출력 동일 |
| 종료 sequence 불일치 | 1 / 1 | 최종/최대 CSV sequence 불일치 검출 |
| sample_seq 헤더 제거 | 1 / 1 | 필수 헤더/열 hash 불일치 검출 |
| image 최종 manifest SHA 변조 | 1 / 1 | fact hash 불일치 검출 |
| image fact 마지막 행 절단 | 1 / 1 |133행 대비132행·hash 불일치 검출 |
| observation fact 경로 누락 | 1 / 1 | 필수 fact 부재 검출 |

7조건14실행에서 표준 출력이 바이트 단위로 같고 stderr는 비어 있다.
정상 입력의 위치 필드 미설정 경고2종을 유지한다. 이 입력은 격리 합성 장비 자료다.
실제 물리 설정·현장 정합성 통과를 뜻하지 않는다.
Python 검색 PATH를 제외하고 소스 밖 cwd/별도 AppData·Temp에서 EXE를 실행했다.
서버 자체 실행이나 모든 Windows 환경에서의 실행은 아직 검증하지 않았다.

검증 도우미 최초 실행은 환경 변수 대소문자 `SystemRoot`로 입력 복사 전에 exit1이었다.
수정 실행은 14개 프로그램 종료/출력이 모두 예상대로였으나 검산 기대 문자열
`row count`와 실제 `row_count`의 차이로 exit1이었다. 두 실패 기록을 보존했다.
정확한 실패 문구·원시 행 수를 대조하고 해당 절단 조건만 Python/EXE로 재실행해
두 프로그램 exit1을 확인했다. 최종 검산 도우미 exit0, 총16프로그램 실행이다.
제품/검사기 바이트는 이 보완 중 변경되지 않았다.

네이티브 Windows PowerShell5.1에서 원본 QA/attestation 스크립트2개 parse 오류0,
검사기 Authenticode `NotSigned`를 확인했다. 미서명 정책에 따라 서명은 필수 조건이 아니다.
이번 새 helper의 Ruff F/E9 exit0. 제품 코드 변경이 없어 전체 health를 반복하지 않았다.

## 서버 전달과 실행 범위

- 공유: `Z:\SmartFactory\20261013\send\PDCA_QA128_20261013_32adee4e`.
- 서버 로컬: `C:\Users\user\Desktop\SmartFactory\PDCA_QA128_20261013_32adee4e`.
- 12파일 /9,563,976바이트. 개발→공유 파일 전체 SHA를 대조했다.
- 서버 탐색기의 최종 절대경로와12개 파일을 확인했다.
  [전달 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_QA128_20261013_32adee4e/server-delivery.json).
- 서버 로컬 SHA는 미측정이며 화면 확인을 hash 검증으로 표현하지 않는다.
- 부모 ACL 변경·덮어쓰기·설치·재시작·attestation·QA 실행은 하지 않았다.
- 21:08KST 앱 화면은 Running, 작업60322/9였다. 복원 표본의 Temp UNDER_RANGE와
 마지막 표시557.4°C는 그대로 기록하며 같은 poll의 값이나 정상 온도로 해석하지 않는다.
 Windows Security cloud scan 필요 알림도 관찰했으며 보안 설정을 조작하지 않았다.

묶음 README는 선행 조건과 미실행 상태를 명시한다. 원본 사용 설명서는
README-source.md로 보존한다. 원본 attestation 도구는 설정 쓰기 기능이 있으므로
현장 진입 조건을 통과한 실행에서만 사용한다. 현재 도구를 실행하라는 지시가 아니다.
서버 파일 최대 경로106자로 경로 예산240자 이내다.

## 남은 순서

1. [현재 조건](production-release-risk-validation-current-gates-20261013.report.md)의 제조사 App1/40.38
   적용·동일값 방법·물리 경계 시험과 과거 finding 영향/처리를 확보한다.
2. 1.0.28의 전체 현장 실행 도우미, 외부 신뢰 SHA 및 잠금 실행,15분/120분 canary 구성을 준비한다.
   기존 canary-v1026의 d7a1b20 pin을 새 후보의 실행 근거로 사용하지 않는다.
3. 진입 조건 충족 후 동일 설치본의 실제 QA·정상 시작3회·정상 종료·새 데이터 전수 검증을 수행한다.
4. 운영 승격·실제 적용 확인 후 build/installer SHA를 다음 롤백 기준으로 갱신한다.

공유 보존 기록은 `Z:\SmartFactory\20261013\records\PDCA_QA128_32adee4e`, 94파일이며
기존 증거와 제품·운영본 identity를 유지한다. R1–R6 HOLD, full_data_gate NOT_EVALUATED.
