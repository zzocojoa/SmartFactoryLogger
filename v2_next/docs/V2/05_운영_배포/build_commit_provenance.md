# Packaged Build Commit Provenance

## 목적

PyInstaller로 만든 backend가 Git이 없는 운영 PC에서도 실제 build source commit을
CSV v2 metadata의 `schema_metadata.git_commit`에 기록하도록 한다. 검증되지 않은
값을 commit으로 기록하지 않는 것이 우선이다.

## Build 정책

- `backend/build_specs/SmartFactoryBackend.spec`은 패키징 시작 시 repository 전체의
  `git status --porcelain --untracked-files=normal`을 확인한다.
- 작업트리가 clean이고 `git rev-parse --verify HEAD`가 정확한 lowercase 40자리
  hexadecimal SHA를 반환할 때만 build를 계속한다.
- 검증된 SHA는 `backend/build_provenance.json`으로 PyInstaller bundle에 포함된다.
- Executable assembly 후 worktree와 HEAD를 다시 확인하며, 최초 SHA와 다르거나 dirty가
  되면 생성된 package를 승인하지 않고 build를 실패시킨다.
- dirty, no-Git, Git command 실패, invalid SHA이면 패키징을 중단한다. 이전 commit을
  추측하거나 환경변수 값으로 대체하지 않는다.
- 생성 파일에는 schema version, `clean_git_head` source, SHA만 포함하며 source path나
  credential은 포함하지 않는다.

## Runtime 정책

- Dev runtime은 기존 동작대로 현재 checkout이 clean일 때 Git HEAD를 기록한다.
- Frozen runtime은 Git command를 실행하지 않고 `backend/version.py` 옆에 포함된
  `build_provenance.json`만 읽는다.
- Bundled file이 없거나 JSON/schema/source/SHA 검증이 실패하면
  `schema_metadata.git_commit=null`을 기록한다.
- Runtime metadata 생성 경계에서도 SHA를 다시 검증해 정확한 lowercase 40자리
  hexadecimal 외 값은 거부한다.

## 검증과 실패 관측

- 정상 package log에는 `Build provenance git commit: <sha>`가 한 번 출력된다.
- Build 실패 시 clean worktree와 valid HEAD 요구사항을 명시한 오류로 중단된다.
- 회귀 테스트는 clean Git, dirty Git, invalid/missing Git, valid/invalid/missing bundle,
  frozen no-Git metadata 기록을 포함한다.

## Rollback

`backend/version.py`의 provenance helper, repository fallback, PyInstaller data 항목을
함께 revert한다. 그러면 frozen/no-Git runtime은 기존처럼 `git_commit=null`로
복귀하며 CSV schema나 저장 데이터 migration은 필요하지 않다.
