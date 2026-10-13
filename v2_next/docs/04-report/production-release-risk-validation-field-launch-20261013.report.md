# 1.0.28 현장 패키지 읽기 실행 도우미 검증·전달

2026-10-13. 이미 전달한 후보·롤백·QA 패키지를 같은 잠금 바이트로 검증하고 결과를 보존하는
도우미를 구현·시험했다. 서버 로컬 5파일과 절대경로를 화면으로 확인하고 명령문을 열어 두었다.
실제 서버 관리자 실행·서버 패키지 SHA 확인은 아직 미확인이다. 설치·현장 QA·15분/120분
canary·승격은 이번 도우미 범위에 없으며 R1–R6 HOLD, `full_data_gate=NOT_EVALUATED`를 유지한다.

## 식별과 실행 계약

| 대상 | SHA256 | 바이트 |
| --- | --- | ---: |
| [컨트롤러](../../scripts/field-v1028/invoke-field-package-read.ps1) | `eeb9ddb8fb92fb47514bea9292b40ad94f6bb88d64038dc896f3650bfe4cc20e` | 12597 |
| 전달 검증기 | `56144abd5439b15bdd8dda8c00840d1561fdb5370bc0fdb065187eb5e176fb5e` | 10449 |
| 기존 패키지 manifest | `58012882bd9ae382c741e2b5e2fc045c8fa9a7959fe273083db8b1113c43fd6b` | 기존 고정값 |
| 실제 서버 실행 명령문 | `8ba65c24a7605f5a2c794963492b73dc4eb7b21308f220358df2f22b19742d95` | 아래 준비 기록 |
| 새 전달 묶음 manifest | `d76129f7c26e4ea9faf86a1c7b5d3c7c05ea91120b506c97c9b140714aa52d63` | 아래 준비 기록 |

[준비 기록](C:/Users/user/Desktop/SmartFactory/PDCA_FREAD128_20261013_06df50b9/launch-preparation.json)에
5파일/18,673바이트, 각 소스·템플릿·명령문과 패키지의 결합을 기록했다.
패키지의 후보는 clean build `4cc7393e1bafbf90a329726aed9470fe0daacb21`, installer SHA
`8821746bbed47850ead68c66894e5580afac63483b1569865915dadc30cfc848`다.
현재 운영본·다음 변경의 롤백 기준은 `541d701d544eea6a8a4e4836047077eaf9cfaf30`/`08c061ee…`로 유지한다.
제품을 수정·재빌드하지 않았고 미서명 내부 운영 정책을 그대로 적용한다.

[명령 템플릿](../../scripts/field-v1028/read-launch.template.txt)의 외부 고정 SHA 검사는 컨트롤러를
읽기 잠금한 동일 스트림에서 실행한다. 컨트롤러가 만든 네이티브 Windows PowerShell 5.1 x64
자식도 전달 검증기의 길이·SHA를 확인한 동일 잠금 바이트를 UTF-8로 해석해 실행한다.
전달 검증기56144abd와 저장소 검증기f8a3f357의 마지막 LF1바이트 차이는
[기존 패키지 보고](production-release-risk-validation-field-package-20261013.report.md)의 보존 이력을 따른다.

기존 패키지와 부모 폴더는 수정하지 않는다. 새 `r-시각-GUID` 폴더에만 결과를 만들고
Administrators/SYSTEM 쓰기와 운영자 읽기 권한을 확인한다. 상대경로·ADS·reparse·240자 초과·
기존 파일 덮어쓰기를 거부한다. 120초 제한은 직접 만든 검증 자식 프로세스에만 적용한다.
앱 프로세스 제어·장비 HTTP·설정 변경은 없다. stdout/stderr/result/manifest를 새 파일로 쓰고
`RESULT_PATH`·`MANIFEST_SHA256`·`LAUNCH_EXIT`를 콘솔로 남긴다.
사용자 쓰기 가능 부모의 모든 적대적 경로 교체를 방어한다고 주장하지 않는다.

## 실제 검사와 한계

| 검사 | 실제 종료·결과 |
| --- | --- |
| 네이티브 parse·생성할 운영 ACL, 정확한 검증기 자식 실행 | 시험 wrapper exit0, 정상 검증기 child exit0 |
| 길이/SHA/manifest 불일치·누락·잘못된 UTF-8·NTFS junction | wrapper exit0, 대상 child exit1 및 해당 이유 |
| 실행 중 같은 파일 쓰기/삭제 거부·작은따옴표 경로 | wrapper/child exit0, 두 잠금 거부 확인 |
| 직접 만든 시험 자식의 시간 초과 | wrapper exit0, child exit-1·timeout true·해당 PID 종료 |
| 결과 경로·CreateNew·비관리자 무변경 거부 | 경로 시험 exit0, 실제 비관리자 실행 exit1·administrator-required |
| 권한 치환 fixture의 정상 실행·재실행 | 각 exit0, 서로 다른 결과 폴더와 manifest 2개 |
| 잘못된 manifest 실패 보존·패키지 내부 결과 경로 거부 | 각 exit1, 실패 결과 manifest 1개 보존 |
| 외부 bootstrap 정상·해시/길이/junction 변조·실제 명령 parse | 정상/parse exit0, 변조 3개 exit1 |

[기본14시험](C:/Users/user/Desktop/SmartFactory/PDCA_FREAD128_20261013_06df50b9/test-result.json)과
[추가7시험](C:/Users/user/Desktop/SmartFactory/PDCA_FREAD128_20261013_06df50b9/launch-test-result.json)의
총21개 조건이 기대 종료 코드와 일치했다. 기본14 wrapper stderr는 비어 있고, bootstrap 실패3개의
stderr는 의도한 HOLD 예외다. 시간 초과 자식의 `#< CLIXML` stderr도 원문에 보존했다.
[최종 검산](C:/Users/user/Desktop/SmartFactory/PDCA_FREAD128_20261013_06df50b9/verification-reviewed.json)은
원시 출력·종료 코드, 실제 결과 manifest3개, 전달5파일과 공유5파일 SHA를 대조해 exit0이었다.
시험기·준비기·검산기3개의 Ruff F/E9도 exit0이다.

첫 시험은 ACL의 `ReadAndExecute`에 자동 포함되는 `Synchronize`를 예상하지 못해 exit1이었다.
운영 ACL 생성값을 확인하고 시험의 기대 mask만 보완했다. 최초 실패·원래 시험 소스·ACL 관찰은
[첫 시도 폴더](C:/Users/user/Desktop/SmartFactory/PDCA_FREAD128_20261013_95beaba3)에 보존했다.
컨트롤러 바이트는 변경하지 않았다.

개발 PC 계정은 비관리자다. 정상 결과 생성 시험은 관리자 guard1곳과 owner SID3곳만 치환한
격리 사본으로 수행했으며 [치환 기록](C:/Users/user/Desktop/SmartFactory/PDCA_FREAD128_20261013_06df50b9/fixture-substitutions.json)을 남겼다.
운영 ACL 객체의 계약 검사는 했지만 실제 관리자 ACL 생성·운영자 접근은 서버 실행에서 확인해야 한다.
이 로컬 시험을 실제 서버 실행이나 현장 QA PASS로 확대하지 않는다.

## 서버 전달·보존

- 공유: `Z:\SmartFactory\20261013\send\FREAD128_20261013_06df50b9`.
- 서버 로컬: `C:\Users\user\Desktop\SmartFactory\FREAD128_20261013_06df50b9`.
- 읽을 서버 패키지: `C:\Users\user\Desktop\SmartFactory\PDCA_FIELD128_20261013_450e9f1b`.
- 실행 문서: `PINNED_FIELD_READ_COMMAND_06df50b9.txt`의 `& {`로 시작하는 본문 전체.
- [화면 확인 기록](C:/Users/user/Desktop/SmartFactory/PDCA_FREAD128_20261013_06df50b9/server-copy-observation.json):
  22:08–22:09 KST 파일5개·절대경로 확인. 22:16 재확인에도 메모장에 명령문이 열려 있었으며 실행 콘솔 결과는 관찰되지 않았다.

사용자에게 앱을 Running으로 유지하고 관리자 Windows PowerShell5.1에서 본문을 직접 실행하도록
요청했다. computer-use skill이 필수로 참조하는 Windows 자동화 지침은
“Do not run Windows terminal commands via UI automation directly or indirectly.”라고 제한한다.
파일 전달·문서 열기는 완료했으며 이 제한 때문에 원격 UI에서 명령을 실행하지 않았다.
사용자 응답이나 메모장 표시만으로 서버 해시 검증 성공을 기록하지 않는다.

시험·전달·첫 실패·소스 사본·화면 기록129파일은
`Z:\SmartFactory\20261013\records\PDCA_FREAD128_06df50b9`에 보존하고 전체 SHA를 대조했다.
manifest 제외811,781바이트, [기록 manifest](C:/Users/user/Desktop/SmartFactory/PDCA_FREAD128_20261013_06df50b9/records-manifest.json)
SHA256은 `2b503f75147a9777cdb776f622c5f525ea2a1d6ef3abda21980315cf5a745796`다.
실제 junction1개는 따라가지 않았다. [전송 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_FREAD128_20261013_06df50b9/record-transfer.json)은 봉인 이후 별도로 보존한다.
준비 당시 소스 미커밋·서버 미실행 표지는 당시 사실로 유지한다.

## 다음 단계

1. 사용자 실행 뒤 콘솔의 경로·manifest SHA·종료 코드를 확인하고 결과4파일을 새 `return` 폴더로 회수한다.
2. 콘솔 SHA와 회수 바이트, 실제 서버·SID·child exit·패키지 identity·HOLD 범위를 대조한다.
3. 전체15분/120분 수집·판정 도구와 설정 attestation·현장 QA를 준비한다. 현재 도우미는 패키지 읽기 단계다.
4. 제조사 App1 경계 근거·물리 시험, 과거 finding 영향/처리, 최종 delta 등 기존 gate를 해결한 뒤
   동일 설치본의 현장 검증·운영 승격·실제 적용 확인과 다음 롤백 기준 갱신을 수행한다.

제품 변경이 없어 전체 health/NSIS·대규모 원본 전수 검사는 반복하지 않았다.
이번 기록은 설치나 승격의 선행 조건 면제 또는 정식 출시 완료가 아니다.
