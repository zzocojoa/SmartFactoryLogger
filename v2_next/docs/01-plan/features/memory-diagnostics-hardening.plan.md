# Memory Diagnostics Hardening Plan

## 1. Summary

- Feature: `memory-diagnostics-hardening`
- Phase: Plan
- Date: 2026-06-27
- Scope: 메모리 진단 기능의 안정화, 주요 resident buffer 계측, 운영 판정, forensic export, 테스트 가드레일 설계
- Business goal: 현장 앱의 메모리 증가 원인을 Python backend, Electron shell, renderer, frontend heap, collector 단위로 분해해 운영자가 단일 증거 파일로 판단할 수 있게 한다.

이 작업은 먼저 문서화 단계만 수행한다. 런타임 소스 변경은 후속 PR에서 세 묶음으로 분할한다.

## 2. Engineering Assessment

- Risk level: High
- Runtime: Python FastAPI backend, React/Vite frontend, Electron main/renderer, Windows packaged desktop app
- Package context: npm workspace scripts, backend Python unittest/health script, Electron builder packaging
- Deployment context: packaged desktop app에서 backend process를 spawn하고 frontend renderer가 로컬 backend API를 호출하는 구조
- Smallest safe change now: 구현 전 plan/design/do 문서를 고정하고, 실제 변경은 additive API와 UI 확장으로만 설계한다.

주요 위험은 진단 로직 자체가 PLC loop, CSV writer, SPOT image fetch, renderer thread에 부하를 만들 수 있다는 점이다. 따라서 P0는 새 collector 추가보다 collector contract와 런타임 상태 관리가 먼저다.

## 3. Current Baseline

현재 기준으로 backend `MemoryService`는 process RSS/VMS/USS/private, thread/open file/handle, GC count, collector top/growth, profiler diff를 제공한다. Profiler는 `tracemalloc.compare_to(..., "lineno")` 기반 diff를 만든다.

현재 등록된 backend collector는 다음 6개다.

| Collector | Current role | Gap |
| --- | --- | --- |
| `observability.requests` | 요청 통계 상태 | latency/status 계약 없음 |
| `observability.errors` | 에러 통계 상태 | severity budget 없음 |
| `facility.plc_state` | 최신 PLC scalar 일부 | PLC history deque 메모리 미계측 |
| `facility.csv_logger` | queue/buffer 기본 상태 | drop, lag, estimated queue bytes 미계측 |
| `configuration.snapshot` | 설정 snapshot | stale/failure 상태 없음 |
| `spot.cache` | 일반 이미지 cache | live cache, retry, failure 상태 분리 안 됨 |

기존 관측 blind spot은 `PLCService.history`, CSV queue backlog, SPOT live image cache, Electron child processes, frontend exactness다.

## 4. In Scope

| Priority | Item | Goal |
| --- | --- | --- |
| P0 | Memory collector safety/common contract | 진단 로직 장애와 부하를 격리한다. |
| P0 | `facility.plc_history` collector | 가장 유력한 상시 resident buffer를 계측한다. |
| P0 | CSV logger queue/drop/lag collector | writer 지연과 queue 누적을 운영 지표로 분리한다. |
| P1 | SPOT image/live cache collector | static image cache와 live frame cache를 분리한다. |
| P1 | collector budget/severity engine | size/delta를 운영 경고로 변환한다. |
| P1 | slope-based leak detector | 순간 spike와 지속 증가를 구분한다. |
| P2 | GC before/after snapshot | 회수 가능 메모리와 retained memory를 분리한다. |
| P2 | Electron process memory | Python backend와 Electron main/renderer/GPU를 분리한다. |
| P2 | frontend memory exactness | observed, estimated, unavailable 값을 명확히 구분한다. |
| P3 | forensic export payload v2 | 원격 장애 분석용 단일 증거 파일을 만든다. |
| P3 | memory tests and CI guardrail | 진단 기능 회귀를 막는다. |

## 5. Out Of Scope

- 이 문서 작업에서 런타임 코드 변경
- DB schema migration
- CSV 파일 포맷 변경
- PLC/SPOT 제어 명령 변경
- 자동 `gc.collect()` 주기 실행
- 운영 환경에서 장시간 부하 테스트 실행
- secret, token, password, authorization value, private key를 export에 저장

## 6. Implementation Slicing

### PR 1: Diagnostic Foundation

목표는 진단 프레임워크 자체의 안전성을 확보하고 가장 큰 blind spot 두 개를 계측하는 것이다.

- Item 1: collector runtime contract 확장
- Item 2: `facility.plc_history` collector 추가
- Item 3: CSV queue/drop/lag collector 강화
- 최소 UI: Backend growth table에 latency/status/stale/severity-compatible fields 표시
- Merge gate: backend unit tests, frontend typecheck, `npm run health`

### PR 2: Cause And Risk Classification

목표는 큰 항목을 보여주는 수준에서 위험 항목을 판정하는 수준으로 올리는 것이다.

- Item 4: SPOT image/live cache collector 분리
- Item 5: collector budget/severity engine
- Item 6: slope-based leak detector
- Item 7: manual GC snapshot endpoint and UI
- Merge gate: severity/slope/GC unit tests, UI rendering tests, export backward compatibility check

### PR 3: App-Wide Forensics

목표는 backend만 보는 관측을 전체 desktop app 관측으로 확장하고 export/test로 고정하는 것이다.

- Item 8: Electron main/renderer/GPU process memory
- Item 9: frontend memory exactness 개선
- Item 10: forensic export schema v2
- Item 11: memory diagnostics tests and CI guardrail
- Merge gate: Electron IPC security review, export redaction tests, `npm run health`

## 7. Acceptance Criteria

- `/api/memory/details`에서 backend collector item에 `latency_ms`, `status`, `stale`, `last_ok_at`, `last_error_at`, `error_count`, `source`가 포함된다.
- `facility.plc_history`가 Backend growth table에 나타나고 count, max, fill ratio, average bytes per sample을 note/detail로 확인할 수 있다.
- `facility.csv_logger`의 bytes가 queue backlog와 비례하고 drop count, lag, queue ratio를 확인할 수 있다.
- `spot.image_cache`와 `spot.live_cache`가 분리된다.
- collector별 `severity`가 `ok`, `warn`, `critical`로 계산되고 UI 기본 정렬에 반영된다.
- `leak_suspects`는 leak 확정이 아니라 steady growth suspicion으로 표시된다.
- `/api/memory/gc`는 수동 호출만 지원하고 before/after/delta를 반환한다.
- Electron memory는 preload bridge를 통해 제한된 API로만 노출된다.
- frontend exactness는 `observed`, `estimated`, `estimated-enumerated`, `unavailable`을 구분한다.
- export schema v2는 runtime, analysis, frontend, details를 포함하고 redaction을 수행한다.
- `npm run health`에 memory diagnostics regression tests가 포함된다.

## 8. Risk And Mitigation

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Collector가 느려 sampler thread를 지연 | 운영 진단이 앱 부하가 됨 | latency 측정, soft timeout 상태, stale reuse 설계 |
| PLC history lock 장시간 점유 | PLC data loop와 history API 지연 | lock 안에서는 bounded sample copy만 수행 |
| CSV payload size estimate 과부하 | enqueue hot path 지연 | `model_dump_json()` 길이 기반 EMA, 실패 시 conservative fallback |
| leak false positive | 운영자 오판 | 명칭을 `leak_suspect`로 제한, slope와 monotonic ratio 병행 |
| GC snapshot pause | UI/API latency spike | 수동 endpoint만 제공하고 latency를 기록 |
| Electron IPC attack surface | renderer compromise 시 정보 노출 | preload에서 `getMemory()`만 expose, no arbitrary IPC |
| export 민감정보 포함 | 보안 사고 | key-based redaction, argv/config/path 최소화 |

## 9. Rollback And Operations

- Rollback path: 각 PR은 additive 변경으로 유지하고, 이상 시 해당 PR revert 또는 collector registration flag off로 되돌린다.
- Observability impact: memory details/export의 진단 범위가 확장된다. 별도 external telemetry는 추가하지 않는다.
- Migration risk: DB/CSV schema migration은 없다. export schema는 v2 additive로 유지한다.
- Operational failure mode: collector failure는 개별 item `status=error`로 격리하고 sampler/API 전체 실패로 전파하지 않는다.
- Test coverage gap: 실제 현장 장시간 memory slope 검증은 local CI에서 재현하기 어렵다. synthetic history tests와 operator smoke test로 보완한다.

## 10. References

- Existing plan: `docs/01-plan/features/performance-observability-baseline.plan.md`
- Existing design: `docs/02-design/features/performance-observability-baseline.design.md`
- Electron `app.getAppMetrics()`: https://www.electronjs.org/docs/latest/api/app
- Electron `process.getProcessMemoryInfo()`: https://www.electronjs.org/docs/latest/api/process

## 11. Pre-Implementation Server Evidence

- Evidence artifact: `sfl-memory-precheck-idle-baseline-20260628.sanitized.zip`
- Evidence type: idle/non-production baseline
- Collection window: 2026-06-28 00:26:49 to 00:30:49 KST
- Process samples: 60 rows
- Observed process groups: packaged app shell, backend process, browser process, Windows SmartScreen process
- Backend memory at idle snapshot:
  - RSS: about 277.4 MB
  - USS: about 224.8 MB
  - private: about 239.3 MB
  - threads: 20
  - handles: 427
  - open files: 9
- Existing backend collectors observed: `observability.requests`, `observability.errors`, `spot.cache`, `facility.plc_state`, `configuration.snapshot`, `facility.csv_logger`
- Existing `facility.csv_logger` idle state: `queue=0 buffer=0`
- Existing SPOT live smoke: HTTP 200, `image/jpeg`, about 9 KB response
- Existing memory export: succeeded, but current schema is pre-v2 and does not include `schema_version`, `runtime`, or `analysis`

This evidence confirms that the server app, backend memory endpoints, memory export, process sampling, and SPOT live smoke are reachable in idle mode. It does not validate production load behavior. Production evidence is still required for PLC history fill, CSV writer backlog/drop/lag, SPOT live cache growth, slope thresholds, and final severity budgets.

## 12. Ranked Micro-PDCA Execution Policy

The implementation will now run as rank-specific PDCA features instead of one large all-at-once implementation cycle. This parent document remains the roadmap and shared evidence source.

Execution order:

1. `memory-diagnostics-r01-collector-contract`
2. `memory-diagnostics-r02-plc-history`
3. `memory-diagnostics-r03-csv-logger-runtime`
4. `memory-diagnostics-r04-spot-cache`
5. `memory-diagnostics-r05-budget-severity`
6. `memory-diagnostics-r06-leak-slope`
7. `memory-diagnostics-r07-gc-snapshot`
8. `memory-diagnostics-r08-electron-memory`
9. `memory-diagnostics-r09-frontend-exactness`
10. `memory-diagnostics-r10-export-v2`
11. `memory-diagnostics-r11-tests-ci`

Each rank must complete Plan, Design, Do, Check/analyze, Act/iterate if needed, and Report before the next rank begins implementation. The previous three-PR slicing remains useful as release grouping, but it is no longer the execution control unit.
