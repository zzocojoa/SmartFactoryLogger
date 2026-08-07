# Windows Authenticode 서명 운영

## 목적

Windows 외부·고객·상용 운영 설치본은 정확한 Git commit에서 생성되고, 승인된
게시자 인증서로 서명되며, 타임스탬프와 build provenance까지 검증된 경우에만
production 서버 검증으로 진행한다. 소유자가 통제하는 비공개 개인 사용 설치본은
아래 유예 정책에 따른 내부 검증만 허용되며 production 배포 승인을 뜻하지 않는다.

PR 검증용 unsigned artifact와 운영용 signed artifact는 서로 다른 workflow를
사용한다. PR workflow에는 코드서명 개인키가 전달되지 않는다.

## 현재 상태

- `.github/workflows/windows-release-artifact.yml`은 PR용 unsigned artifact만
  생성한다.
- `.github/workflows/windows-signed-release.yml`은 보호된 기본 브랜치에서 수동
  승인 실행되며 `production-signing` GitHub Environment를 참조하는 운영 서명
  workflow다.
- `scripts/verify_windows_release_signature.ps1`은 installer와 packaged
  application의 Authenticode signer, timestamp, SHA-256, manifest commit,
  provenance commit을 fail-closed 방식으로 검증한다.
- 현재 개발 PC와 GitHub Environment에는 승인된 운영 인증서가 구성되지 않았다.
  따라서 현재 v1.0.18 후보는 신규 exact-commit 서버 검증 전까지 배포 승인을
  받지 않았다.

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

다음 중 하나라도 시작되기 전에는 이 유예를 종료하고 공개 신뢰 코드서명을
구성해야 한다.

- 고객 또는 제3자에게 installer 제공
- 공개 다운로드 또는 외부 배포
- 상업 운영 환경이나 조직 관리 장비에 설치
- Windows 게시자 신뢰가 배포 승인 조건인 환경으로 전환

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
- 서명 실패 또는 출처 불일치 시 서버는 검증된 v1.0.16 상태를 유지한다.

## 참고

- electron-builder는 Windows 인증서 경로/base64와 비밀번호를
  `WIN_CSC_LINK`, `WIN_CSC_KEY_PASSWORD`로 받는다.
- GitHub Environment secret은 해당 environment를 참조하는 job에만 제공되며,
  보호 규칙 승인이 필요한 경우 승인 전에는 job이 secret에 접근할 수 없다.
