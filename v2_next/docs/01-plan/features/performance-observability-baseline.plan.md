# Performance Observability Baseline Plan

> **Summary**: Define the implementation baseline for user-perceived performance, remote access performance, and server resource performance before source changes.
>
> **Project**: SmartFactoryLogger v2
> **Version**: 0.2
> **Author**: Codex
> **Date**: 2026-06-24
> **Status**: Draft, DOC_ONLY

---

## 1. Summary

This document sets the pre-implementation standard for performance observability. It is not an implementation change. The next implementation PR must use this plan and the paired design document as the contract for what to add, what to leave unchanged, and how to verify the result.

The business goal is to make three performance axes reviewable with evidence:

1. User-perceived performance: page load, dashboard render, polling latency, chart update, and SPOT image display.
2. Remote access performance: external browser access to the server app, HTTP latency, request rate, cache behavior, and SPOT image response health.
3. Server resource performance: backend CPU, memory, thread, handle, CSV queue, PLC/SPOT backoff, and log pressure.

The implementation must improve observability only. It must not change operating data, control values, CSV output cadence, PLC/SPOT settings, installer behavior, or production deployment state.

## 2. Existing Logic Inventory

| Area | Current evidence | Current limitation |
|------|------------------|--------------------|
| Backend HTTP stats | `backend/app.py` records every request through middleware and exposes `/stats` with total, average latency, error counts, last request, window metrics, error summary, and polling metrics. | No `performance_contract_version`; no explicit threshold snapshot. |
| `/health` | `backend/app.py` combines PLC health, runtime info, and frontend static status. | Health proves service state but not performance budget compliance. |
| Polling path stats | `backend/Observability/service.py` aggregates quiet paths into `/stats.polling.paths` with count, requests per second, average latency, error rate, unique clients, and top clients. | `/api/spot/live_image` gets generic path stats only; proxy image has success, stale, and age stats, live image does not. |
| SPOT proxy image | `/api/spot/proxy_image` records proxy success age and stale state through `record_spot_proxy_result`. | Existing proxy-specific fields should not be assumed to cover live image behavior. |
| SPOT live image | `/api/spot/live_image` returns `image/jpeg`, no-store headers, source and age headers, and backoff/fetch errors. | Live image result is not separately classified into success/failure/stale/average age in stats. |
| Frontend static cache | Frontend hashed assets use immutable cache headers; non-immutable runtime files use no-store. | Remote performance review must verify this split because no-store on runtime files is intentional. |
| Backend memory diagnostics | `/api/memory/state` and `/api/memory/details` expose RSS, VMS, thread count, handle count, open file count, profiler state, collector history, and tracemalloc diff. CPU currently comes from the external resource monitor artifact unless a future implementation explicitly adds an app API field. | No single performance verdict exists; consumers must interpret several fields and keep CPU source explicit. |
| CSV writer resource state | `backend/FacilityData/repository.py` uses a bounded queue, batch flush, and exposes queue size, buffer size, and last batch size. | Queue growth needs a baseline rule rather than a one-off value. |
| Communication metrics | `backend/Observability/metrics_logger.py` writes queued rotating comm metrics for EX, LS, and SPOT including backoff, recovery, and disconnect events. | Log pressure is observable but not tied to a performance acceptance budget. |
| Dashboard polling | `frontend/src/domains/FacilityData/` polls `/api/data` at the existing interval, tracks `latencyMs`, degraded state, failure count, visibility pause, leader mode, worker backoff, and history backfill. | Dashboard render and polling health are not summarized as a stable performance artifact. |
| React render profiling | `frontend/src/shared/profiling/reactRenderProfiler.tsx` and `scripts/collect_react_profiler.cjs` collect React profiler samples, `sampleCount`, `maxActualDuration`, `avgActualDuration`, `consoleErrors`, and `pageErrors`. | Artifact fields exist but need to be declared as the standard review evidence. |
| Server QA script | `scripts/qa_spot_live_server.ps1` performs short live-image loops, `/stats` before/after capture, endpoint checks, cache header checks, and JSON artifact output. | It is a short smoke tool, not a long automatic load test. |
| Existing performance docs | `docs/web_performance_guide.md` gives general web/API budgets; `docs/04-deploy/spot-live-image-nsis-qa.md` gives SPOT live image deployment QA context. | Some historical docs contain environment-specific examples; new docs must not copy internal addresses or full local paths. |

## 3. Proposed Additional Logic

The next implementation should add aggregation and summary contracts, not new active probes.

| ID | Candidate | Requirement level | Notes |
|----|-----------|-------------------|-------|
| PERF-01 | Add `performance_contract_version` to `/stats`. | Required candidate | Version the shape of performance fields so the frontend and QA scripts can detect drift. |
| PERF-02 | Add `/stats.thresholds` snapshot. | Required candidate | Include operational thresholds and regression budgets in one read-only payload. |
| PERF-03 | Extend `/stats.polling.paths["/api/spot/live_image"]`. | Required candidate | Add live-image `success_count`, `failure_count`, `stale_count`, and `avg_age_sec`. |
| PERF-04 | Standardize React profiler artifacts. | Required candidate | Required fields: `sampleCount`, `maxActualDuration`, `avgActualDuration`, `consoleErrors`, `pageErrors`. |
| PERF-05 | Add a Settings performance summary. | Optional UI | Use existing `/stats`, `/health`, `/api/memory/state`, and `/api/memory/details`; no new polling source unless justified. |
| PERF-06 | Add `/api/performance/summary`. | Optional API | Only if the Settings summary becomes too expensive or duplicated in frontend logic. |
| PERF-07 | Define server resource growth rules. | Required candidate | Use bounded observation windows and monotonic-growth criteria across memory, thread, handle, open files, CSV queue, and CPU when an explicit CPU source is selected. |
| PERF-08 | Define remote-access smoke evidence. | Required candidate | Verify external browser access using masked base URLs and short smoke loops only. |

## 4. Do-not-implement Scope

The performance baseline must explicitly avoid these changes:

- No backend or frontend source changes in this DOC_ONLY task.
- No package, lockfile, config, DB, CSV, PLC, SPOT, dist, installer, or generated artifact changes.
- No production DB writes.
- No changes to operator metadata live values.
- No PLC or SPOT configuration writes.
- No long automatic load test during production hours.
- No per-request body logging.
- No raw internal IP, full URL with internal host, credential, token, secret, or full local path in docs, logs, exports, or UI.
- No OpenTelemetry rollout in this scope.
- No high-frequency CSV performance row append.
- No implementation of `/api/performance/summary` unless the implementation PR separately justifies it.

## 5. API Contract Proposal

The implementation baseline should keep existing APIs backward-compatible.

Required `/stats` additions:

- `performance_contract_version`: string, for example `"1.0"`.
- `thresholds`: object containing operational thresholds and regression budgets.
- `polling.paths["/api/spot/live_image"]`: must keep existing generic path fields and add live-image result fields.

Required compatibility rule:

- Existing fields under `/stats.total_requests`, `/stats.avg_latency_ms`, `/stats.error_count`, `/stats.total_http_error_count`, `/stats.last`, `/stats.window`, `/stats.errors`, `/stats.polling`, and `/stats.uptime_sec` must remain available.
- New fields must be additive.
- Missing optional data must be represented with `null` or absent optional subfields, not by removing current fields.

Optional API:

- `/api/performance/summary` may be proposed only as an aggregation layer over `/stats`, `/health`, and `/api/memory/*`.
- It must not run new active probes.
- It must not expose raw internal hostnames, full URLs, full local paths, credentials, tokens, or request bodies.

## 6. UI / Settings Proposal

The optional Settings performance summary should be a diagnostic surface, not an operational alert source.

Required UI boundaries:

- Header status stays focused on operational warnings: PLC, SPOT, data freshness, critical backend health, and user-actionable production conditions.
- Settings may show performance summary cards for backend HTTP, polling paths, SPOT live image, memory, CPU, threads, handles, open files, CSV queue, and React profiler artifacts. CPU must be labeled as either external resource monitor evidence or a future app API field, not assumed from current `/api/memory/state`.
- Debug/performance details must not be promoted into the Header unless they clearly indicate an operational production problem.
- Internal addresses, full URLs, full local paths, credentials, and raw request details must be masked or omitted.
- Client identifiers in `top_clients` should be rendered as counts or masked labels unless the operator explicitly exports a diagnostic artifact.

## 7. Metrics and Thresholds

Thresholds are split into operational thresholds and regression budgets.

### 7.1 Operational thresholds

| Metric | Target | Warning | Failure |
|--------|--------|---------|---------|
| `/health` latency | <= 50 ms | > 50 ms | >= 200 ms or non-200 |
| `/api/data` latency | <= 100 ms | > 100 ms | >= 500 ms or repeated failure |
| `/api/spot/live_image` latency | <= 500 ms | > 500 ms | non-image, repeated 5xx, or stale loop |
| `/api/spot/proxy_image` latency | <= 500 ms | > 500 ms | non-image or repeated 5xx |
| `/stats.window.p95_latency_ms` | <= agreed local baseline | > 20% over baseline | > 50% or > 500 ms over baseline |
| `/stats.window.error_rate` | 0 for normal smoke | any non-zero during smoke | repeated non-zero or rising 5xx |
| LCP | <= 2.5 s | > 2.5 s | > 4.0 s |
| CLS | <= 0.1 | > 0.1 | > 0.25 |
| React `maxActualDuration` | <= baseline budget | > 20% over baseline | > 50% over baseline |
| CSV queue size | stable near 0 under normal logging | sustained growth | queue approaches capacity or drops rows |
| Memory, thread, handle, open files | stable after warm-up | monotonic growth across observation window | unbounded growth or resource exhaustion symptoms |

Default server resource growth gate:

- Ignore the first 2 minutes after backend start or after beginning a smoke session as warm-up.
- Evaluate a 5-minute observation window after warm-up.
- With the current 5-second memory sampling cadence, prefer 60 samples and require at least 48 samples spanning at least 4 minutes for an automated verdict.
- Treat fewer samples as inconclusive, not pass.
- Raise warning only when RSS/VMS, thread count, handle count, open file count, or CSV queue size trends upward across the valid window and the final-window average is higher than the initial-window average.
- Raise failure when the upward trend is paired with resource exhaustion symptoms, row drops, queue near-capacity, repeated recovery loops, or repeated warning/error log pressure.

### 7.2 Regression budgets

Use the benchmark skill regression rules as implementation review defaults:

- Timing metric regression: more than 50% slower or more than 500 ms absolute increase.
- Timing metric warning: more than 20% slower.
- Bundle size regression: more than 25% increase.
- Bundle size warning: more than 10% increase.
- Request count warning: more than 30% increase.

## 8. Acceptance Criteria

The documentation phase is complete when:

- This plan document exists.
- The paired design document exists.
- A review-prep document exists if useful for diff review.
- Only docs are changed.
- `git diff --check` passes.
- Trailing whitespace checks on the new docs pass.
- New docs do not contain raw internal IPs, full internal URLs, credentials, tokens, secrets, or full local paths.
- The final report gives document diff review context and stops before implementation.

The future implementation phase is complete only when:

- `/stats` remains backward-compatible and includes the new version and threshold fields.
- `/stats.polling.paths["/api/spot/live_image"]` exposes live-image success, failure, stale, and average age fields.
- React profiler output uses the standard artifact fields.
- Optional Settings summary, if implemented, stays separate from Header operational alerts.
- Validation includes local smoke, remote-access smoke, browser render evidence, resource snapshots, and no source of production writes.

## 9. Validation Plan

Document-only validation:

1. Confirm working tree contains only planned docs.
2. Run `git diff --check`.
3. Search new docs for trailing whitespace.
4. Search new docs for raw internal IPs, full internal URLs, credential/secret/token terms, and full local path patterns.
5. Review diff for DOC_ONLY scope.

Future implementation validation:

1. `/health` HTTP smoke.
2. `/stats` schema smoke and backward compatibility check.
3. `/api/memory/state` and `/api/memory/details` snapshot review.
4. Short `/api/spot/live_image` loop using the existing server QA script.
5. External browser dashboard smoke using masked base URL in reports.
6. React profiler collection with `sampleCount`, `maxActualDuration`, `avgActualDuration`, `consoleErrors`, and `pageErrors`.
7. Browser checks for LCP, CLS, dashboard first render, chart update, and SPOT image display.
8. Resource observation for CPU, memory, threads, handles, open files, CSV queue, and log pressure.

## 10. Risk / Rollback / Observability

| Risk | Impact | Mitigation |
|------|--------|------------|
| `/stats` contract drift | Settings and QA tools may read the wrong fields. | Version the contract and keep all existing fields additive. |
| Performance UI becomes operational noise | Operators may react to debug-only warnings. | Keep Header operational-only and put diagnostics in Settings. |
| Remote diagnostics expose environment data | Internal addresses or paths may leak into screenshots or artifacts. | Mask internal hosts, URLs, full paths, and client identifiers by default. |
| Live image stats increase overhead | High-frequency image requests may add CPU or lock pressure. | Aggregate in existing request middleware and response metadata only. |
| Resource thresholds are too rigid | False positives on slow server hardware. | Use local baseline plus regression budgets; separate target, warning, and failure. |
| Long load tests affect production | Operator dashboard or device network may slow down. | Use short smoke loops and manual observation; forbid long automatic load tests. |

Rollback path:

- Documentation PR rollback: delete or revert these docs.
- Implementation PR rollback before merge: revert the implementation branch commits.
- Implementation PR rollback after merge: revert the merge commit.
- Production rollback: reinstall the previous known-good installer and keep the performance docs as investigation context.

Observability impact:

- This DOC_ONLY change has no runtime impact.
- Future implementation should reuse `/stats`, `/health`, `/api/memory/*`, React profiler artifacts, and existing QA scripts before adding new endpoints.

## 11. Next Implementation Prompt

Use the plan and design docs for a source-change PR with this scope:

```text
Implement the SmartFactoryLogger performance observability baseline.

Constraints:
- Keep `/stats` backward-compatible.
- Add `performance_contract_version` and `thresholds` to `/stats`.
- Add live-image result aggregation under `/stats.polling.paths["/api/spot/live_image"]` with success_count, failure_count, stale_count, and avg_age_sec.
- Standardize React profiler review artifacts around sampleCount, maxActualDuration, avgActualDuration, consoleErrors, and pageErrors.
- Treat `/api/performance/summary` and Settings performance summary as optional; implement only if the PR explicitly justifies them.
- Do not add long production load tests, per-request body logging, raw internal URL logging, OpenTelemetry, or high-frequency CSV performance rows.
- Keep Header status operational-warning focused.
- Mask internal addresses, full URLs, full local paths, credentials, tokens, and secrets in logs, docs, exports, and UI.

Validation:
- Run backend/frontend unit checks relevant to touched code.
- Run `/health`, `/stats`, `/api/memory/state`, `/api/memory/details` smoke.
- Run short SPOT live image server QA loop.
- Collect React profiler artifact.
- Report working tree status and remaining risks.
```

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.2 | 2026-06-24 | Recreated DOC_ONLY performance observability baseline plan | Codex |
