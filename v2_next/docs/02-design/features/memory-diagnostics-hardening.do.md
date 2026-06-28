# Memory Diagnostics Hardening To-Do Checklist

## 1. Purpose

이 문서는 `memory-diagnostics-hardening` 후속 구현을 추적하기 위한 do-phase 체크리스트다. 실제 구현 완료 문서가 아니며, PDCA 상태에서 do phase를 완료 처리하지 않는다.

목표는 세 개의 작은 PR로 나누어 진단 부하를 통제하면서 blind spot을 줄이는 것이다. 체크박스는 해당 구현, 테스트, 검증이 실제로 완료된 뒤에만 선택한다.

## 2. Global Preconditions

- [ ] Branch가 `codex/memory-diagnostics-pdca-design` 또는 후속 구현 브랜치인지 확인한다.
- [ ] `docs/01-plan/features/memory-diagnostics-hardening.plan.md`를 기준 요구사항으로 사용한다.
- [ ] `docs/02-design/features/memory-diagnostics-hardening.design.md`를 기준 설계로 사용한다.
- [ ] production code 편집 전 PDCA pre-write check를 통과한다.
- [ ] 모든 PR은 compatibility alias가 명시된 경우를 제외하고 additive 변경으로 유지한다.
- [ ] rollback path, observability impact, migration risk, test coverage gap을 PR 설명에 포함한다.

## 3. PR 1: Diagnostic Foundation

### 3.1 MemoryService Collector Contract

Files:

- `backend/Observability/memory_service.py`
- `frontend/src/shared/types.ts`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`

Implementation:

- [ ] `MemoryService`에 `_collector_runtime_state`를 추가한다.
- [ ] collector 호출 전후 `time.perf_counter()`로 `latency_ms`를 측정한다.
- [ ] collector item에 `latency_ms`를 추가한다.
- [ ] collector item에 `status`를 추가한다.
- [ ] collector item에 `last_ok_at`을 추가한다.
- [ ] collector item에 `last_error_at`을 추가한다.
- [ ] collector item에 `error_count`를 추가한다.
- [ ] collector item에 `stale`을 추가한다.
- [ ] collector item에 `source`를 추가한다.
- [ ] 기존 collector item fields를 유지한다.
- [ ] collector 예외를 전체 sampler 실패가 아니라 per-collector error item으로 격리한다.
- [ ] slow threshold 기본값을 `250ms`로 둔다.
- [ ] stale threshold 기본값을 `60s`로 둔다.
- [ ] UI가 새 fields가 없는 구버전 payload도 렌더링하도록 optional 처리한다.
- [ ] Backend growth table에 latency/status/stale 표시를 추가한다.

Tests:

- [ ] collector exception isolation test를 추가한다.
- [ ] collector latency recording test를 추가한다.
- [ ] slow status threshold test를 추가한다.
- [ ] stale state test를 추가한다.
- [ ] old payload compatibility rendering test를 추가한다.

Validation:

- [ ] targeted backend MemoryService tests를 실행한다.
- [ ] frontend typecheck를 실행한다.
- [ ] `npm run health`를 실행한다.
- [ ] `git diff --check`를 실행한다.

### 3.2 PLC History Collector

Files:

- `backend/FacilityData/service.py`
- `backend/app.py`
- backend memory tests

Implementation:

- [ ] `PLCService.get_history_memory_summary(sample_size=128)`를 추가한다.
- [ ] `history_lock` 안에서는 count, bounds, bounded sample copy만 수행한다.
- [ ] `estimate_size_bytes()`는 lock 밖에서 수행한다.
- [ ] empty history에 대해 zero-safe response를 반환한다.
- [ ] bounded sample 기반으로 `estimated_bytes`를 계산한다.
- [ ] `avg_bytes_per_sample`을 계산한다.
- [ ] `fill_ratio`를 계산한다.
- [ ] `_collect_plc_history()`를 `backend/app.py`에 추가한다.
- [ ] `_register_memory_collectors()`에 `facility.plc_history`를 등록한다.
- [ ] note에 count, max, fill ratio, avg bytes를 포함한다.

Tests:

- [ ] summary returns count and estimated bytes test를 추가한다.
- [ ] lock is not held during size estimation test를 추가한다.
- [ ] empty history returns zero-safe fields test를 추가한다.
- [ ] collector registration test를 추가한다.

Validation:

- [ ] Backend growth table에서 `facility.plc_history`가 보이는지 확인한다.
- [ ] 1시간 history fill ratio와 estimated bytes가 표시되는지 확인한다.

### 3.3 CSV Logger Queue/Drop/Lag

Files:

- `backend/FacilityData/repository.py`
- `backend/app.py`
- backend CSV logger tests

Implementation:

- [ ] `CSVLoggerService`에 `_drop_count`를 추가한다.
- [ ] `CSVLoggerService`에 `_last_drop_at`을 추가한다.
- [ ] `CSVLoggerService`에 `_last_enqueue_at`을 추가한다.
- [ ] `CSVLoggerService`에 `_last_write_at`을 추가한다.
- [ ] `CSVLoggerService`에 `_payload_bytes_ema`를 추가한다.
- [ ] `CSVLoggerService`에 `_runtime_lock`을 추가한다.
- [ ] enqueue path에서 payload size EMA를 갱신한다.
- [ ] queue full drop path에서 drop count와 last drop time을 갱신한다.
- [ ] writer loop flush 완료 시 `last_write_at`을 갱신한다.
- [ ] `get_runtime_state()`에 queue ratio를 추가한다.
- [ ] `get_runtime_state()`에 writer lag를 추가한다.
- [ ] `get_runtime_state()`에 estimated queue bytes를 추가한다.
- [ ] `_collect_csv_logger()` bytes 기준을 `estimated_queue_bytes` 중심으로 바꾼다.
- [ ] note에 `queue=.../... drop=... lag=...s`를 포함한다.

Tests:

- [ ] full queue increments drop count test를 추가한다.
- [ ] writer lag null before first write test를 추가한다.
- [ ] writer lag positive after delay test를 추가한다.
- [ ] queue bytes scale with queue size test를 추가한다.

Validation:

- [ ] Backend growth table에서 `facility.csv_logger` bytes가 queue backlog에 비례하는지 확인한다.
- [ ] note/detail에서 drop count와 lag가 보이는지 확인한다.

### 3.4 PR 1 Merge Gate

- [ ] MemoryService targeted tests pass.
- [ ] PLCService targeted tests pass.
- [ ] CSVLoggerService targeted tests pass.
- [ ] frontend typecheck pass.
- [ ] `npm run health` pass.
- [ ] `git diff --check` pass.
- [ ] Backend growth table에 collector runtime fields가 표시된다.
- [ ] `facility.plc_history`가 표시된다.
- [ ] enhanced `facility.csv_logger`가 표시된다.
- [ ] rollback path가 PR 설명에 포함된다.

## 4. PR 2: Cause And Risk Classification

### 4.1 SPOT Image/Live Cache Collectors

Files:

- `backend/FacilityData/drivers/spot_api.py`
- `backend/app.py`
- backend SPOT tests

Implementation:

- [ ] `get_image_cache_memory_summary()`를 추가한다.
- [ ] static image cache bytes를 `image_bytes`로 보고한다.
- [ ] live image cache bytes를 `live_image_bytes`로 보고한다.
- [ ] retry/backoff state를 summary에 포함한다.
- [ ] failure count를 summary에 포함한다.
- [ ] live image URL 원문을 반환하지 않는다.
- [ ] `spot.image_cache` collector를 등록한다.
- [ ] `spot.live_cache` collector를 등록한다.
- [ ] 기존 `spot.cache` compatibility alias 유지 여부를 PR 설명에 명시한다.

Tests:

- [ ] static image bytes exact reporting test를 추가한다.
- [ ] live image bytes exact reporting test를 추가한다.
- [ ] failure/retry fields included test를 추가한다.
- [ ] raw live URL not exported test를 추가한다.

Validation:

- [ ] Memory UI에서 `spot.image_cache`와 `spot.live_cache`가 분리되어 보인다.
- [ ] live image 활성 상태에서 live cache가 별도로 증가하는지 확인한다.

### 4.2 Budget Severity Engine

Files:

- `backend/Observability/memory_service.py`
- `frontend/src/shared/types.ts`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`

Implementation:

- [ ] `DEFAULT_MEMORY_BUDGETS`를 추가한다.
- [ ] `facility.plc_history` bytes budget을 추가한다.
- [ ] `facility.csv_logger` queue ratio budget을 추가한다.
- [ ] `spot.live_cache` bytes budget을 추가한다.
- [ ] normalize 이후 budget을 적용한다.
- [ ] collector item에 `severity`를 추가한다.
- [ ] collector item에 `severity_reasons`를 추가한다.
- [ ] collector item에 `budget` metadata를 추가한다.
- [ ] UI 기본 정렬을 severity, delta, bytes 순서로 변경한다.
- [ ] `status=error`와 `severity`를 별도 축으로 표시한다.

Tests:

- [ ] warn threshold test를 추가한다.
- [ ] critical threshold test를 추가한다.
- [ ] CSV queue ratio threshold test를 추가한다.
- [ ] UI severity sort order test를 추가한다.

Validation:

- [ ] `facility.plc_history`가 warn bytes 이상일 때 `WARN`으로 표시된다.
- [ ] `facility.plc_history`가 critical bytes 이상일 때 `CRITICAL`로 표시된다.

### 4.3 Slope Leak Detector

Files:

- `backend/Observability/memory_service.py`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`

Implementation:

- [ ] process history 기반 slope 계산 함수를 추가한다.
- [ ] collector history 기반 slope 계산 함수를 추가한다.
- [ ] monotonic ratio를 계산한다.
- [ ] 최소 샘플 수 미달 시 empty result를 반환한다.
- [ ] process fields `rss_bytes`, `uss_bytes`, `private_bytes`를 분석한다.
- [ ] collector `bytes` series를 분석한다.
- [ ] `leak_suspects`를 `/api/memory/details`에 포함한다.
- [ ] UI 문구를 leak 확정이 아니라 leak suspect로 제한한다.

Tests:

- [ ] monotonic growth detected test를 추가한다.
- [ ] spike without sustained slope not detected test를 추가한다.
- [ ] insufficient samples return empty result test를 추가한다.
- [ ] frontend leak suspect rendering test를 추가한다.

Validation:

- [ ] steady growth fixture에서 `leak_suspects`가 생성된다.
- [ ] one-shot spike fixture에서 `leak_suspects`가 생성되지 않는다.

### 4.4 Manual GC Snapshot

Files:

- `backend/Observability/memory_service.py`
- `backend/app.py`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`
- frontend memory API hook files

Implementation:

- [ ] `MemoryService.capture_gc_snapshot()`을 추가한다.
- [ ] before process sample을 저장한다.
- [ ] `gc.collect(0)`, `gc.collect(1)`, `gc.collect(2)`를 수동 호출한다.
- [ ] GC latency를 측정한다.
- [ ] after process sample을 저장한다.
- [ ] rss/uss/private delta를 계산한다.
- [ ] `self._last_gc_snapshot`을 저장한다.
- [ ] `POST /api/memory/gc` endpoint를 추가한다.
- [ ] profiler control 근처에 GC comparison button을 추가한다.
- [ ] latest GC snapshot을 export에 포함한다.

Tests:

- [ ] before/after/delta fields present test를 추가한다.
- [ ] endpoint handles failure with 500 test를 추가한다.
- [ ] UI renders GC delta test를 추가한다.
- [ ] UI renders GC latency test를 추가한다.

Validation:

- [ ] GC snapshot은 자동 sampler에서 호출되지 않는다.
- [ ] UI에서 GC 실행 후 delta와 latency가 표시된다.

### 4.5 PR 2 Merge Gate

- [ ] backend SPOT tests pass.
- [ ] backend budget tests pass.
- [ ] backend slope tests pass.
- [ ] backend GC tests pass.
- [ ] frontend severity sorting tests pass.
- [ ] frontend leak suspects rendering tests pass.
- [ ] frontend GC rendering tests pass.
- [ ] `npm run health` pass.
- [ ] `git diff --check` pass.
- [ ] UI가 large item, risky item, slow collector, leak suspect를 구분한다.
- [ ] rollback path가 PR 설명에 포함된다.

## 5. PR 3: App-Wide Forensics

### 5.1 Electron Metrics

Files:

- `main.js`
- `preload.js`
- `package.json`
- `frontend/src/shared/types.ts`
- `frontend/src/domains/Observability/hooks/useMemoryViewModel.ts`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`

Implementation:

- [ ] `main.js`에 `ipcMain` import를 추가한다.
- [ ] `BrowserWindow.webPreferences.preload`를 설정한다.
- [ ] `preload.js`를 추가한다.
- [ ] `smartFactoryElectron.getMemory()` bridge를 추가한다.
- [ ] arbitrary IPC invoke는 노출하지 않는다.
- [ ] IPC handler `sfl:get-electron-memory`를 추가한다.
- [ ] `app.getAppMetrics()` 결과를 포함한다.
- [ ] `process.getProcessMemoryInfo()` 결과를 포함한다.
- [ ] V8 heap statistics를 가능한 경우 포함한다.
- [ ] Electron KB values를 UI에서 일관되게 변환한다.
- [ ] packaged build에 `preload.js`가 포함되는지 `package.json`을 확인한다.

Tests:

- [ ] preload exposes only allowed API test를 추가한다.
- [ ] hook handles Electron unavailable in browser mode test를 추가한다.
- [ ] UI renders Electron process metrics test를 추가한다.

Validation:

- [ ] Memory UI에서 Backend Python, Electron Main, Renderer, GPU/Utility가 분리되어 보인다.
- [ ] browser-only dev mode에서 Electron API 부재가 안전하게 처리된다.

### 5.2 Frontend Exactness

Files:

- `frontend/src/shared/types.ts`
- `frontend/src/domains/Observability/hooks/useMemoryViewModel.ts`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`

Implementation:

- [ ] `MemoryExactness` type을 확장한다.
- [ ] browser memory API result를 `observed`로 표시한다.
- [ ] storage enumeration result를 `estimated-enumerated`로 표시한다.
- [ ] app structure heuristic result를 `estimated`로 표시한다.
- [ ] unsupported browser memory result를 `unavailable`로 표시한다.
- [ ] exactness badge를 UI에 표시한다.
- [ ] low-confidence estimated 항목은 alert reason에 반영한다.

Tests:

- [ ] unsupported mode returns unavailable test를 추가한다.
- [ ] storage collectors use estimated-enumerated test를 추가한다.
- [ ] heuristic collectors remain estimated test를 추가한다.
- [ ] exactness badge rendering test를 추가한다.

Validation:

- [ ] UI exact column이 `estimated` 반복이 아니라 observed/estimated/unavailable을 구분한다.

### 5.3 Export Schema V2

Files:

- `backend/Observability/memory_service.py`
- `backend/app.py`
- frontend export caller

Implementation:

- [ ] `schema_version: memory-export-v2`를 추가한다.
- [ ] `runtime` block을 추가한다.
- [ ] `summary_state` block을 유지한다.
- [ ] `details_state` block을 유지한다.
- [ ] `frontend` block을 유지한다.
- [ ] `analysis` block을 추가한다.
- [ ] `redaction` metadata를 추가한다.
- [ ] collector runtime state를 export에 포함한다.
- [ ] budget results를 export에 포함한다.
- [ ] leak suspects를 export에 포함한다.
- [ ] latest GC snapshot을 export에 포함한다.
- [ ] profiler state/diff를 export에 포함한다.
- [ ] recursive redaction을 적용한다.

Tests:

- [ ] schema v2 snapshot test를 추가한다.
- [ ] redaction of sensitive keys test를 추가한다.
- [ ] frontend Electron snapshot included when available test를 추가한다.
- [ ] export without frontend snapshot test를 추가한다.

Validation:

- [ ] export JSON 하나로 backend, frontend, Electron, collector, budget, leak suspect, GC, profiler context를 확인할 수 있다.
- [ ] export JSON에 raw credential, live URL 원문, private key 값이 없다.

### 5.4 CI Guardrail

Files:

- existing backend unittest locations
- existing frontend test locations
- `package.json` scripts only if needed

Implementation:

- [ ] backend memory diagnostics tests가 existing health script에 포함되는지 확인한다.
- [ ] frontend memory view model tests가 test suite에 포함되는지 확인한다.
- [ ] `MemorySection` rendering tests가 test suite에 포함되는지 확인한다.
- [ ] export schema regression test를 추가한다.
- [ ] CI에서 schema snapshot regression이 실패하도록 연결한다.

Validation:

- [ ] `npm run health` pass.
- [ ] targeted backend unittest pass.
- [ ] frontend tests pass.
- [ ] frontend typecheck pass.
- [ ] `git diff --check` pass.

### 5.5 PR 3 Merge Gate

- [ ] Electron IPC security review complete.
- [ ] export redaction tests pass.
- [ ] schema v2 snapshot tests pass.
- [ ] `npm run health` pass.
- [ ] packaged Electron build에서 preload file inclusion 확인 완료.
- [ ] rollback path가 PR 설명에 포함된다.

## 6. Operational Review Gates

Before each PR merge:

- [ ] raw token value가 export에 저장되지 않는다.
- [ ] raw password value가 export에 저장되지 않는다.
- [ ] raw authorization value가 export에 저장되지 않는다.
- [ ] private key value가 export에 저장되지 않는다.
- [ ] live image URL 원문이 export에 저장되지 않는다.
- [ ] new collectors는 read-only다.
- [ ] lock-held section은 bounded 작업만 수행한다.
- [ ] UI는 older backend payload의 missing fields를 처리한다.
- [ ] rollback path가 PR description에 문서화되어 있다.
- [ ] operational failure mode가 PR description에 문서화되어 있다.

## 7. Next Source Step

- [ ] PR 1부터 시작한다.
- [ ] PR 1에서 collector safety contract를 먼저 구현한다.
- [ ] PR 1에서 `facility.plc_history` collector를 구현한다.
- [ ] PR 1에서 CSV queue/drop/lag collector를 구현한다.
- [ ] PR 1이 merge되기 전에는 Electron IPC, export v2, GC endpoint를 구현하지 않는다.

## 8. Evidence Checklist

Pre-implementation evidence:

- [x] Idle/non-production server baseline collected.
- [x] Sanitized evidence artifact prepared: `sfl-memory-precheck-idle-baseline-20260628.sanitized.zip`.
- [x] Backend memory endpoints verified reachable in idle mode.
- [x] Memory export verified writable in idle mode.
- [x] SPOT live smoke verified in idle mode.
- [x] Existing collector inventory captured.
- [x] Current export schema confirmed as pre-v2.

Evidence still required:

- [ ] Production or production-like PLC history fill baseline.
- [ ] Production or production-like CSV queue/drop/lag baseline.
- [ ] Production or production-like SPOT live cache growth baseline.
- [ ] Post-PR2 severity threshold verification.
- [ ] Post-PR2 slope leak suspect verification.
- [ ] Post-PR3 packaged Electron process memory verification.
- [ ] Post-PR3 export v2 redaction verification.

## 9. Ranked Micro-PDCA Feature Map

The implementation is now controlled by rank-specific PDCA features. Complete one feature through Report before implementing the next.

- [ ] `memory-diagnostics-r01-collector-contract`
- [ ] `memory-diagnostics-r02-plc-history`
- [ ] `memory-diagnostics-r03-csv-logger-runtime`
- [ ] `memory-diagnostics-r04-spot-cache`
- [ ] `memory-diagnostics-r05-budget-severity`
- [ ] `memory-diagnostics-r06-leak-slope`
- [ ] `memory-diagnostics-r07-gc-snapshot`
- [ ] `memory-diagnostics-r08-electron-memory`
- [ ] `memory-diagnostics-r09-frontend-exactness`
- [ ] `memory-diagnostics-r10-export-v2`
- [ ] `memory-diagnostics-r11-tests-ci`

The PR 1/2/3 grouping above remains a release grouping reference only. The implementation gate is the child feature's own Plan, Design, Do, Analyze, Iterate, and Report cycle.
