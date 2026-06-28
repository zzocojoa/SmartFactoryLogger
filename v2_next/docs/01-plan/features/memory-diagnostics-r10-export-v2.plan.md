# Memory Diagnostics R10 Export V2 Plan

## 1. Summary

- Feature: `memory-diagnostics-r10-export-v2`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 10
- Dependency: `memory-diagnostics-r09-frontend-exactness` Report 완료

## 2. Business Goal

운영 장애 분석 시 memory export JSON 하나로 runtime, backend, frontend, Electron, collector state, budget, leak suspect, GC, profiler context를 확인할 수 있게 한다. 동시에 민감정보는 저장하지 않는다.

## 3. Scope

- `schema_version: memory-export-v2` 추가
- runtime block 추가
- analysis block 추가
- collector runtime state, budget results, leak suspects, last GC snapshot 포함
- frontend/Electron snapshot 포함
- recursive redaction 적용
- export schema regression test 추가

## 4. Out Of Scope

- 외부 업로드 기능
- 암호화 저장
- cloud forensic pipeline
- export viewer 별도 앱

## 5. Acceptance Criteria

- export top-level에 `schema_version`, `runtime`, `summary_state`, `details_state`, `frontend`, `analysis`, `redaction`이 있다.
- token/password/secret/authorization/api_key 계열 key는 redacted 된다.
- raw credential, private key, live image URL 원문이 export에 남지 않는다.
- frontend snapshot이 없어도 export가 성공한다.

## 6. Validation Gate

- export v2 schema test 통과
- redaction test 통과
- frontend snapshot included test 통과
- sanitized export smoke 확인
- bkit analyze match rate 90% 이상

## 7. Rollback

v2 payload builder를 되돌려 기존 export payload로 복귀한다. export endpoint URL은 유지해 operator workflow를 깨지 않는다.

