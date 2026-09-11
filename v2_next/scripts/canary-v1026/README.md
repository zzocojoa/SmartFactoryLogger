# v1.0.26 Canary 오프라인 이식 후보

제품은 clean master `d7a1b20f96711fb07fc7add0867e79ee36506fce`의 기존 설치본이다.
이 도구 변경은 제품 재빌드나 서버 설치를 포함하지 않는다. 강조 애니메이션도 유지한다.

## 범위와 실행 차단

- v15 controller의 평가·self-test를 별도 경로에 이식했다. 기존 공용 도구와 과거 증거는 수정하지 않는다.
- 제품 1.0.26, installer SHA와 1645파일 payload manifest에 정확히 결합한다.
- 15분/120분은 새 관측 전까지 PENDING이다. 과거 PASS·사후 진술은 수입하지 않는다.
- 커밋 전 local source snapshot을 ZIP으로 결합하며 HEAD를 변경분의 commit으로 표시하지 않는다.
- 이 kit의 controller/collector 실서버 진입은 차단된다. 오프라인 평가와 self-test만 허용한다.
- 오프라인 evaluator의 generic PASS는 제공된 summary에 대한 판정일 뿐, 제품/원본 해시 결합이나
  v1.0.26 관측 승인이 아니다. 해당 한계를 결과 필드에 명시한다.
- 현재 상태·설정·전체 설치 트리·복구 적합성·사용자 승인을 결합하는 서버 도우미는 후속 단계다.
- SHA는 게시자 서명이 아니다. 사내 개발·검증용 예외 외 배포나 정식 운영 승인이 아니다.

## 검증 계약

관측 실패 카운터는 정확한 13개, 이미지 스냅샷 필드는 33개다. bind retry exhaustion을
누락하거나 과거 12/32 계약으로 돌아가면 실패한다. 120분 최소는 7200초다.
모니터 5초 공백·종료경계·패킷 coverage 판정은 완화하지 않는다. 상태 검사는 추가 이미지
요청을 하지 않는다. 진행 출력은 로컬 시계/프로세스 상태만 사용한다.

ZIP 모듈은 새 대상에만 생성하고 shared-read 원본을 복사·재해시한다. 닫고 flush한 ZIP을
재개봉하여 엔트리 집합·이름·크기·SHA-256을 비교한 뒤 외부 영수증을 쓴다.
원본 변경, 중복, 경로 이탈, 링크, 덮어쓰기는 거부한다. 실패 파일은 보존하고 PASS 영수증을
발행하지 않는다. ZIP 완료는 관측 PASS가 아니다. 공유 읽기는 writer 중지를 입증하지 않는다.
Kit verifier는 신뢰된 호출자가 kit 밖에서 확보한 `ExpectedManifestSha256`를 필수로 받는다.
해시 목록과 모든 도구 파일을 검증·읽기 잠금한 뒤에만 모듈을 import한다. 같은 kit에서 읽은
sidecar를 스스로 기대값으로 사용하면 외부 신뢰 검증이 되지 않는다.

## 로컬 검증

64-bit Windows PowerShell 5.1에서 다음 인수를 사용한다. 서버에서는 실행하지 않는다.

```powershell
& .\scripts\canary-v1026\build-canary-kit.ps1 `
    -ReleaseKitRoot '<검증된 installer-candidate-review-only 폴더>' `
    -OutputRoot '<로컬 검토 산출물 폴더>' -ReviewOnly
```

회귀 시험은 가상 파일/객체와 별도 임시 폴더만 사용한다. 원본 제품·서버 증거·설정은
변경하지 않는다. pinned Python trigger 시험의 HTTP는 전용 loopback fixture만 대상으로 한다.
서버 설치·장시간 관측·GUI 체감 비교는 이 오프라인 시험으로 대체되지 않는다.

## 공개 fixture 전용 CI

`Canary Offline CI`는 GitHub-hosted Windows의 native x64 PowerShell 5.1에서 동작한다.
같은 빌더에 `-OfflineCi -ReviewOnly`를 사용하므로 수집기 overlay, 해시 검증, 71개 이상
회귀시험과 loopback 통합시험은 로컬 검토 빌드와 같은 경로를 사용한다. Python은 표준
라이브러리만 사용하며 pip/npm 설치, 서버 접근, 실제 설치본 전송이 없다.

```powershell
& .\scripts\canary-v1026\test-canary-ci.ps1 `
    -OutputRoot '<새 시험 결과 폴더>' `
    -PythonPath '<로컬 python.exe>'
```

CI에서는 `-ExpectedCommit`에 PR HEAD를 전달하고 관련 입력 파일의 clean 상태를 요구한다.
직접 로컬 시험할 때 생략하면 수정 중인 소스를 시험할 수 있지만 commit 검증은 주장하지 않는다.
기본 release-review 모드는 여전히 정확한 `ReleaseKitRoot`를 요구하며 `OfflineCi`와 혼용할 수 없다.
두 승인 switch의 false 값, 누락/없는 설치본, 혼합 인수는 negative test로 검사한다.

CI 결과 `V1026_CANARY_OFFLINE_CI_PASS`는 공개 합성 fixture의 도구 시험 PASS다.
`release_candidate_verified=false`이며 제품 설치본 검증 PASS나 서버 관측 PASS가 아니다.
CI는 `fixture-kit-not-for-distribution.zip`만 내부 시험용으로 재검증한다. 검토 배포용 ZIP과
`build-result.json`은 만들지 않으며, Actions 업로드 대상도 synthetic 시험 로그/CI 영수증으로
제한한다. 실제 설치본의 전체 해시 검증은 별도의 로컬 release-review 빌드로 유지한다.

Workflow는 관련 소스·pinned core·무결성 모듈·줄바꿈 정책 변경에서 실행된다.
Actions는 SHA로 고정하고 token 권한은 contents read, checkout credential 저장은 끈다.
실패하면 runner PASS를 발행하지 않으며 기존 결과를 덮어쓰지 않는다.

## 복구와 잔여 위험

복구 후보 v1.0.25의 정확한 installer 해시만 등록했다. 설정/데이터 호환성, 실제 복구
가능성은 새 서버 검토가 필요하다. 자동 롤백·재시작·오류 초기화·관측 재실행은 하지 않는다.
도구 변경 철회는 별도 경로를 사용하지 않는 것으로 가능하며 기존 제품과 증거는 그대로다.
