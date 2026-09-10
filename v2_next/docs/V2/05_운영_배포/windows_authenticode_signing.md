# Windows Authenticode 서명 운영

## 목적

Windows 외부·고객 배포 및 정식 상용 운영 설치본은 정확한 Git commit에서 생성되고, 승인된
게시자 인증서로 서명되며, 타임스탬프와 build provenance까지 검증된 경우에만
production 배포를 위한 서버 검증으로 진행한다. 비공개 개인 사용과 사내
개발·검증용 미서명 설치본은 아래의 서로 다른 유예 정책을 따른다. 두 예외 모두
정식 production 배포 승인을 뜻하지 않는다. 서명 유예는 게시자 신뢰를 검증했다는
뜻이 아니며, SHA-256만으로 게시자 신뢰를 대체할 수 없다.

PR 검증용 unsigned artifact와 운영용 signed artifact는 서로 다른 workflow를
사용한다. PR workflow에는 코드서명 개인키가 전달되지 않는다.

## 서명 검증 경로

- `.github/workflows/windows-release-artifact.yml`은 PR용 unsigned artifact만
  생성한다.
- `.github/workflows/windows-signed-release.yml`은 보호된 기본 브랜치에서 수동
  승인 실행되며 `production-signing` GitHub Environment를 참조하는 운영 서명
  workflow다.
- `scripts/verify_windows_release_signature.ps1`은 installer와 packaged
  application의 Authenticode signer, timestamp, SHA-256, manifest commit,
  provenance commit을 fail-closed 방식으로 검증한다.
- 인증서 등록 여부, GitHub Environment 보호 설정과 릴리스 검증 상태는 준비
  시점마다 다시 확인한다. 과거 v1.0.18 후보의 미승인 기록은 현재 버전의 상태나
  새 릴리스의 배포 승인을 대신하지 않는다.

## 개인 사용 중 서명 유예 정책

Smart Factory Logger가 소유자 본인이 관리하는 장비에서만 비공개로 사용되는
동안에는 유료 공개 신뢰 Authenticode 인증서의 구매와 등록을 유예할 수 있다.
이 예외는 unsigned installer를 운영 서명본으로 간주한다는 뜻이 아니다.

서명을 유예한 내부 설치본은 다음 조건을 모두 지켜야 한다.

1. 설치 대상과 파일 전달 경로를 소유자가 직접 통제한다.
2. installer SHA-256, build commit, release identity, helper SHA-256의 기대값을
   실행 대상 kit 밖의 신뢰된 Git commit 또는 별도 인증 채널에서 먼저 확보한다.
   같은 미서명 kit 안의 sidecar만 신뢰 기준으로 사용하지 않는다.
3. read-only preinstall gate가 통과한 뒤에만 설치를 승인한다.
4. 각 commit마다 re-attestation, QA, smoke, canary 증거를 새로 만든다.
5. unsigned 내부 검증본임을 release identity와 배포 기록에 명시한다.

다음 중 하나라도 시작되기 전에는 개인 사용 유예를 종료한다. 사내 개발·검증용은
다음 절의 별도 조건을 적용하며, 그 범위를 벗어나는 배포에는 공개 신뢰 코드서명을
구성해야 한다.

- 고객 또는 제3자에게 installer 제공
- 공개 다운로드 또는 외부 배포
- 상업 운영 환경이나 조직 관리 장비에 설치
- Windows 게시자 신뢰가 배포 승인 조건인 환경으로 전환

## 사내 개발·검증용 서명 유예

`정책 변경 기준: 2026-09-10`

책임 개발자가 지정된 사내 장비와 전달 경로를 통제하고 개발·검증 목적의 미서명
사용을 명시적으로 승인한 경우, 조직 관리 장비에도 제한된 개발 시험용 NSIS
installer를 준비할 수 있다. 인증서 구매·등록과 `production-signing` 환경 구성은
이 개발용 빌드의 선행조건이 아니다. 회사·공장 장비를 개인 사용 장비로 재분류하지
않으며, "아직 개발 단계"라는 설명만으로 실제 서버 설치나 정식 운영을 승인하지 않는다.

다음 조건을 모두 적용한다.

1. 책임자, 대상 장비, 검증 목적, 대상 버전·정확한 commit과 검증 기간을 배포
   기록에 명시한다. 빌드 준비와 실제 설치·정상 종료·재시작의 승인을 구분한다.
   운영과 개발이 같은 장비에서 이루어지면 운영 영향, 시험 시간대와 중단·복구
   조건을 설치 전에 확인한다. 명칭만 개발용으로 바꾸어 상시 운영을 승인하지 않는다.
2. 설치본·release identity·전달 기록에 사내 개발·검증용 미서명(`UNSIGNED_INTERNAL`)
   임을 명시하고, signed artifact나 정식 운영 승인본으로 표시하지 않는다.
   이 문서 변경만으로 기존 도우미의 자동 지원이나 새 설치본의 검증 완료를 주장하지 않는다.
3. clean Git의 정확한 commit에서 빌드하고 해당 commit의 health suite, 의존성
   보안 감사와 패키지 검증 결과를 확인한다. 미실행·실패 항목을 숨기거나 이전
   버전의 통과 결과로 대체하지 않는다. 보안 감사의 미해결 항목은 영향과 수용 여부를
   검토·기록하기 전까지 설치 준비 완료로 처리하지 않는다.
4. installer·helper·최종 전달 ZIP의 SHA-256 기대값과 build commit은 실행 대상
   kit 밖의 신뢰된 Git commit 또는 별도 인증 채널에서 확보한다. 같은 미서명
   kit 안의 sidecar만 신뢰 기준으로 삼지 않는다. 실제 installer를 격리 추출하여
   payload·manifest·provenance 결합을 검증하고, 최종 ZIP도 닫은 뒤 다시 열어
   승인된 파일 목록·각 파일의 길이와 SHA-256을 재검증한다.
5. 서버의 read-only preinstall 점검으로 현재 실행본·설정·데이터 보존 조건을
   확인한 후 별도 설치 승인을 받는다. Windows 보안 정책·백신·SmartScreen을
   비활성화하거나 경고를 자동 승인하지 않는다. 대상 환경의 게시자 신뢰 요구와
   충돌하면 해당 설치는 중단하고 승인된 서명 경로를 사용한다.
6. 복구 후보의 정확한 버전·commit·installer 해시뿐 아니라 설정·데이터 호환성과
   운영 적합성을 검토한다. 오래된 설치본이 존재하거나 해시가 일치한다는 이유만으로
   복구 가능하다고 판단하지 않는다. 정상 종료 및 보존 절차를 지키고 자동 롤백,
   강제 종료, 증거 덮어쓰기 또는 실패 카운터 초기화를 수행하지 않는다.
7. 설치 후 새 commit에 대한 re-attestation, QA, smoke, 승인된 canary와 변경
   목적에 맞는 현장 비교 검증을 수행한다. 관측·오류 수집 기능을 유지하고 이상이나
   검증 실패 시 증거를 보존하여 HOLD로 처리한다. 종전 15분·120분 증거를 새 commit의
   통과로 재사용하거나 원래의 HOLD 판정을 소급 변경하지 않는다.
8. 승인된 사내 대상 밖으로 개발 설치본과 현장 증거를 전달하지 않는다. 고객·협력사·
   제3자 제공, 공개 다운로드, 상용 납품, 정식 운영 배포 또는 대상 환경의 게시자
   신뢰 요구가 시작되기 전에는 이 유예를 종료하고 서명·운영 검증 경로를 따른다.
   검증 기간 종료나 대상·목적·commit 변경 시 다시 검토하며 무기한 예외로 간주하지 않는다.

서명 유예는 signed workflow나 signature verifier의 검사를 완화하는 방식으로
구현하지 않는다. 개발용 빌드 경로를 분리하고, 서명 환경의 필수 승인·비밀정보·
태그 보호 설정과 운영 서명 검증은 그대로 유지한다. 기존 PR artifact도 위 조건을
충족하는 exact-commit 검토 없이 서버 설치본으로 승격하지 않는다. 과거 설치나
관측 결과에는 이 정책을 소급 적용하지 않는다.

## 정식 서명 전환 시 인증서 선택

CA가 발급한 인증서가 항상 export 가능한 PFX로 제공되는 것은 아니다. 토큰,
HSM 또는 클라우드 키 저장소 기반 인증서는 개인키 반출을 시도하지 않고 해당
공급자가 지원하는 원격 서명 workflow를 사용한다.

## GitHub Environment 준비

저장소 관리자가 GitHub의 `Settings > Environments`에서
`production-signing` 환경을 만든다.

다음 보호 규칙을 적용한다.

1. Required reviewer를 지정한다.
2. 가능하면 배포를 시작한 사용자의 self-review를 금지한다.
3. deployment branch policy는 보호된 기본 브랜치만 허용한다. tag commit의
   workflow code가 직접 secret을 소비하게 두지 않는다.
4. 관리자가 보호 규칙을 임의로 우회하지 못하게 설정한다.
5. 별도 repository ruleset으로 `v*` tag 생성 권한을 release 관리자에게만
   제한하고 tag 삭제와 강제 갱신을 금지한다.

Environment secret:

- `WINDOWS_CODE_SIGNING_PFX_BASE64`: 승인된 PKCS#12/PFX 파일의 base64 값
- `WINDOWS_CODE_SIGNING_PFX_PASSWORD`: PFX 비밀번호

Environment variable:

- `WINDOWS_CODE_SIGNING_CERT_SHA1`: 공백 없는 40자리 인증서 thumbprint

개인키, PFX 원본, base64 값 또는 비밀번호를 Git, issue, PR, 채팅, 로그,
release ZIP에 저장하지 않는다. GitHub secret 크기 제한을 넘는 인증서나 HSM/EV
인증서는 PFX secret 방식 대신 승인된 원격 서명 서비스를 사용해야 한다.

## Workflow 동작

Signed workflow는 보호된 기본 브랜치의 workflow에서만 수동 실행한다. 실행 시
기존 `v<major>.<minor>.<patch>` release tag를 입력하며, 그 tag가 현재 workflow의
정확한 기본 브랜치 commit을 가리킬 때만 계속한다. 임의 branch 또는 tag에 들어
있는 workflow code는 signing secret을 받을 수 없다. job은 `production-signing`
환경 승인을 통과하기 전에는 환경 secret에 접근할 수 없다.

workflow는 다음 조건을 모두 확인한다.

1. workflow ref가 보호된 기본 브랜치이고 checkout SHA와 `github.sha`가 일치한다.
2. 입력한 tag가 `v<package.json version>`과 일치하고 바로 그 checkout SHA를
   가리킨다.
3. packaged application 내부 backend bundle manifest와 build provenance가
   checkout SHA와 일치한다.
4. Node.js `22.22.2`, Python `3.12.6`을 사용하고, Windows release 전용 Python
   lock의 모든 전이 의존성을 SHA-256과 함께 `--require-hashes`로 설치한다.
5. Electron, frontend, backend, lint, type-check와 release helper 전체 health
   suite가 그 commit에서 통과한다.
6. PFX가 private key를 포함하고 현재 유효하며 Code Signing EKU를 포함한다.
7. PFX thumbprint가 `WINDOWS_CODE_SIGNING_CERT_SHA1`과 일치한다.
8. electron-builder가 installer와 packaged Electron executable을 서명한다.
9. 업로드할 installer 복사본 자체를 격리 디렉터리에 풀고, 그 내부 Electron
   실행 파일과 backend bundle을 검증한다. manifest에 기록된 모든 파일의 경로,
   길이, SHA-256, 파일 수와 집계 SHA-256이 실제 추출 payload와 일치해야 한다.
10. installer와 추출된 Electron 실행 파일 모두 Authenticode `Valid`, signer
   thumbprint 일치, timestamp 존재를
   만족한다.
11. `signed_release_identity.json`에 installer, manifest, provenance SHA-256과
   bundle 검증 결과를 기록하고, 업로드 직전 installer 해시를 다시 비교한다.
12. `signed_release_identity.json`과 `SHA256SUMS.txt`를 signed artifact에
   포함한다.
13. 임시 PFX 파일과 추출 payload를 artifact upload 전에 제거한다.
14. 운영 signed artifact에는 검증된 NSIS installer만 포함한다. 별도 portable
    ZIP은 내부 PR 검증 산출물이며 portable backend 실행 파일에 대한 독립 서명과
    검증이 추가되기 전에는 운영 배포본으로 승격하지 않는다.

조건 하나라도 실패하면 signed artifact를 업로드하지 않는다.

Windows release lock을 변경할 때는 Windows/Python 3.12에서 `pip-tools`로
`backend/requirements-windows-release.in`을 다시 compile하고 전체 health suite를
통과시킨다. lock의 해시를 수동으로 추가하거나 삭제하지 않는다.

## 로컬 검증

검증 helper의 secret 없는 회귀 테스트는 다음과 같이 실행한다.

```powershell
powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File .\scripts\verify_windows_release_signature.ps1 `
    -SelfTest

powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File .\scripts\verify_windows_release_workflow_contract.ps1 `
    -SelfTest
```

실제 signed artifact 검증은 workflow와 동일하게 installer, packaged
application, bundle manifest, build provenance, expected commit, expected signer
thumbprint를 모두 전달해야 한다. installer 서명만 확인하고 provenance 검사를
생략해서는 안 된다.

## 서버 검증 전 gate

Signed workflow가 통과한 뒤에도 바로 설치하지 않는다.

1. artifact의 `SHA256SUMS.txt`와 실제 파일 해시를 비교한다.
2. `signed_release_identity.json`의 commit, signer, timestamp, SHA-256을 다시
   확인한다.
3. commit-bound server release kit와 read-only preinstall helper를 만든다.
4. 서버에서 preinstall gate가 통과한 뒤에만 정상 UI 종료와 설치를 승인한다.
5. 새 commit에 대해 re-attestation, one-command QA, smoke, canary를 새로
   수행한다. 이전 commit의 증거는 재사용하지 않는다.

## 인증서 교체와 사고 대응

- 인증서 갱신 시 Environment secret 두 개와 thumbprint variable을 같은 변경
  창에서 교체한다.
- thumbprint가 다르면 workflow가 서명 전에 실패해야 한다.
- 개인키 노출이 의심되면 Environment를 즉시 비활성화하고 인증서를 폐기한 뒤,
  영향받은 artifact SHA와 workflow run을 기록한다.
- 서명 실패 또는 출처 불일치 시 새 설치를 중단하고 기존 실행본과 증거를 보존한다.
  고정된 과거 버전으로 자동 복귀하지 않으며, 실행 중인 버전에 문제가 있으면 별도로
  검토·승인된 복구 경로를 따른다.

## 참고

- electron-builder는 Windows 인증서 경로/base64와 비밀번호를
  `WIN_CSC_LINK`, `WIN_CSC_KEY_PASSWORD`로 받는다.
- GitHub Environment secret은 해당 environment를 참조하는 job에만 제공되며,
  보호 규칙 승인이 필요한 경우 승인 전에는 job이 secret에 접근할 수 없다.
