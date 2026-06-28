# Memory Diagnostics R10 Export V2 Do Checklist

## 1. Rule

- [ ] `memory-diagnostics-r09-frontend-exactness` Report 완료를 확인한다.
- [ ] 완료 전에는 `memory-diagnostics-r11-tests-ci`를 구현하지 않는다.

## 2. Implementation

- [ ] export payload에 `schema_version`을 추가한다.
- [ ] `runtime` block을 추가한다.
- [ ] `summary_state` block을 유지한다.
- [ ] `details_state` block을 유지한다.
- [ ] `frontend` block을 유지한다.
- [ ] `analysis` block을 추가한다.
- [ ] `budget_results`를 analysis에 포함한다.
- [ ] `leak_suspects`를 analysis에 포함한다.
- [ ] `collector_runtime_state`를 analysis에 포함한다.
- [ ] `last_gc_snapshot`을 analysis에 포함한다.
- [ ] `get_budget_results()` accessor를 추가하거나 equivalent method를 제공한다.
- [ ] `get_leak_suspects()` accessor를 추가하거나 equivalent method를 제공한다.
- [ ] `get_collector_runtime_state()` accessor를 추가하거나 equivalent method를 제공한다.
- [ ] `get_last_gc_snapshot()` accessor를 추가하거나 equivalent method를 제공한다.
- [ ] profiler state/diff를 analysis에 포함한다.
- [ ] redaction metadata를 추가한다.
- [ ] recursive redaction helper를 추가한다.
- [ ] sensitive key fragments를 redaction한다.
- [ ] frontend snapshot이 없어도 export가 성공하게 한다.

## 3. Tests

- [ ] export v2 schema test를 추가한다.
- [ ] recursive redaction test를 추가한다.
- [ ] export without frontend snapshot test를 추가한다.
- [ ] Electron snapshot included test를 추가한다.

## 4. Validation

- [ ] targeted export tests를 실행한다.
- [ ] sanitized export smoke를 실행한다.
- [ ] `npm run health`를 실행한다.
- [ ] `git diff --check`를 실행한다.
- [ ] export에 raw credential/live URL/private key가 없는지 확인한다.

## 5. PDCA Close Gate

- [ ] analysis 문서를 작성한다.
- [ ] bkit analyze match rate가 90% 이상이다.
- [ ] iterate 필요 시 재분석한다.
- [ ] report 문서를 작성한다.
- [ ] 다음 feature 시작 가능 상태로 status를 갱신한다.
