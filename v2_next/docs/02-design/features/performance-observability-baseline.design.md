# Performance Observability Baseline Design

> **Summary**: Additive design contract for performance observability across dashboard UX, remote access, and server resources.
>
> **Project**: SmartFactoryLogger v2
> **Version**: 0.2
> **Author**: Codex
> **Date**: 2026-06-24
> **Status**: Draft, DOC_ONLY
> **Planning Doc**: `docs/01-plan/features/performance-observability-baseline.plan.md`

---

## 1. Summary

This design describes the future implementation contract. It does not modify runtime behavior. The design intentionally reuses existing observability surfaces and adds only additive fields where current evidence is too weak for review.

Primary design rule:

- Measure from existing request, response, memory, profiler, and QA artifacts.
- Do not introduce new production probes, long-running load tests, body logging, or operational writes.

## 2. Existing Logic Inventory

### 2.1 Backend API and stats

Current backend surfaces:

- `/health` returns PLC health, runtime information, and frontend static status.
- `/stats` returns total request count, average latency, HTTP error counts, last request metadata, sliding-window metrics, error summary, polling path metrics, and uptime.
- Request middleware records path, status code, latency, and client host in `backend/Observability/service.py`.
- Quiet paths include `/api/data`, `/health`, `/stats`, `/api/memory/state`, `/api/memory/details`, `/api/spot/proxy_image`, and `/api/spot/live_image`.
- Frontend immutable static assets and runtime files use separate cache policies.

Current `/stats` shape to preserve:

```json
{
  "total_requests": 0,
  "avg_latency_ms": null,
  "error_count": 0,
  "total_http_error_count": 0,
  "total_http_4xx_count": 0,
  "total_http_5xx_count": 0,
  "last": {},
  "window": {},
  "errors": {},
  "polling": {},
  "uptime_sec": 0
}
```

### 2.2 SPOT image paths

`/api/spot/proxy_image` currently records successful proxy image age and stale state through `record_spot_proxy_result`.

`/api/spot/live_image` currently returns:

- `image/jpeg` body on success.
- `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`.
- Live image age and source headers when available.
- 404, 503, or 502 errors for config, backoff, upstream, payload, or unknown failures.

Design gap:

- `/stats.polling.paths["/api/spot/live_image"]` should show live-image result fields, not only generic path latency and error rate.

### 2.3 Frontend dashboard and profiler

Current frontend surfaces:

- Dashboard metrics polling tracks latency, degraded state, failure count, backoff, visibility pause, leader/follower mode, and history backfill.
- Time-series rendering uses frame updates and capped series buffers.
- React profiler collection is available through `ProfilerProbe` and `scripts/collect_react_profiler.cjs`.
- The profiler artifact already includes `sampleCount`, `summary[].maxActualDuration`, `summary[].avgActualDuration`, `consoleErrors`, and `pageErrors`.

Design gap:

- The artifact contract needs to be explicitly required so review does not rely on ad hoc browser observation.

### 2.4 Settings, observability, and memory

Current Settings and diagnostics surfaces:

- Settings has existing sections for summary, communication, observability, memory, SPOT camera, storage, thresholds, and security.
- Observability state is already passed into Settings through existing view model data.
- Memory diagnostics show backend RSS, frontend heap/app memory, sample state, profiler state, alerts, history rows, and export actions.
- `/api/memory/state` and `/api/memory/details` expose server resource snapshots and profiler details.

Design boundary:

- Header status must stay operational-warning focused.
- Optional performance summary belongs in Settings, not in Header.

### 2.5 QA and deployment evidence

Current QA surfaces:

- `scripts/qa_spot_live_server.ps1` performs endpoint checks, short live-image loop, `/stats` before/after capture, cache header checks, log lookback, and JSON artifact output.
- `package.json` packages the QA script with the application resources.
- Existing docs contain SPOT live image QA and general web performance guidance.

Design boundary:

- New docs and future artifacts must not copy raw internal addresses, full internal URLs, full local paths, credentials, tokens, or secrets.

## 3. Proposed Additional Logic

### 3.1 `/stats` additive contract

Add these fields to `/stats`:

```json
{
  "performance_contract_version": "1.0",
  "thresholds": {
    "operational": {
      "health_latency_ms": { "target": 50, "failure": 200 },
      "data_latency_ms": { "target": 100, "failure": 500 },
      "spot_image_latency_ms": { "target": 500 },
      "lcp_ms": { "target": 2500, "failure": 4000 },
      "cls": { "target": 0.1, "failure": 0.25 }
    },
    "regression_budget": {
      "timing_warning_ratio": 1.2,
      "timing_regression_ratio": 1.5,
      "timing_regression_absolute_ms": 500,
      "bundle_warning_ratio": 1.1,
      "bundle_regression_ratio": 1.25,
      "request_count_warning_ratio": 1.3
    }
  }
}
```

Rules:

- The exact numeric values may be adjusted in implementation, but the shape must separate operational thresholds from regression budgets.
- Existing `/stats` fields remain unchanged.
- Threshold values are read-only diagnostics, not configuration writes.

### 3.2 Live image polling metrics

Extend the live image path entry under `/stats.polling.paths`.

Current generic path fields to preserve:

```json
{
  "count": 0,
  "requests_per_sec": 0,
  "avg_latency_ms": 0,
  "error_rate": 0,
  "unique_clients": 0,
  "top_clients": []
}
```

Required live-image additions:

```json
{
  "success_count": 0,
  "failure_count": 0,
  "stale_count": 0,
  "avg_age_sec": null
}
```

Implementation constraints:

- Count from existing request middleware and live image response metadata.
- Use status code and image metadata to classify success/failure.
- Use live image age header or metadata to aggregate `avg_age_sec`.
- Treat stale as `0` unless live image metadata can prove stale state.
- Do not fetch the SPOT device only to populate metrics.
- Do not log image bodies, raw URLs, or device credentials.

### 3.3 React profiler artifact standard

The profiler artifact used for review must include:

```json
{
  "sampleCount": 0,
  "summary": [
    {
      "id": "DashboardHeader",
      "maxActualDuration": 0,
      "avgActualDuration": 0
    }
  ],
  "consoleErrors": [],
  "pageErrors": []
}
```

Rules:

- `sampleCount` must be greater than zero for a passing artifact.
- `consoleErrors` and `pageErrors` must be empty unless each entry is explicitly triaged as unrelated.
- `maxActualDuration` and `avgActualDuration` must be compared to the captured baseline or declared review budget.
- The artifact must not include raw internal URLs, full local paths, credentials, tokens, secrets, or request bodies.

### 3.4 Optional Settings performance summary

If implemented, Settings may add a diagnostic section or card group with:

- `/stats.window.p95_latency_ms`
- `/stats.window.requests_per_sec`
- `/stats.window.error_rate`
- `/stats.polling.paths["/api/data"]`
- `/stats.polling.paths["/api/spot/live_image"]`
- `/stats.polling.paths["/api/spot/proxy_image"]`
- `/api/memory/state` summary fields
- `/api/memory/details` profiler state
- CPU only from an explicit source: external resource monitor artifact by default, or `/api/memory/state` only if the implementation PR adds a CPU field.
- CSV queue size, buffer size, and last batch size when exposed through memory collectors
- React profiler artifact import or latest captured summary, if already available

UI rules:

- Settings performance summary is optional.
- Header status remains operational-warning focused.
- Debug-only performance warnings stay inside Settings.
- Internal host/client/path details are masked.
- The operator must not need to understand developer-only thresholds to keep production running.

### 3.5 Optional `/api/performance/summary`

This endpoint remains optional. Use it only if frontend aggregation would duplicate too much logic.

Allowed behavior:

- Aggregate existing `/stats`, `/health`, `/api/memory/state`, and `/api/memory/details` data.
- Return a summary object with masked labels.
- Keep latency low by avoiding device calls, file scans, body reads, or long computations.

Forbidden behavior:

- No active SPOT/PLC probe.
- No request body logging.
- No CSV performance row append.
- No OpenTelemetry setup.
- No raw internal host, URL, full local path, credential, token, secret, or request body exposure.

## 4. Do-not-implement Scope

The implementation must not:

- Change DB, CSV, PLC, SPOT, operator metadata, installer, or deployment state.
- Change polling cadence unless a separate performance PR justifies it.
- Add long automatic load tests.
- Add per-request body logging.
- Add internal IP, raw internal URL, full local path, credential, token, or secret output.
- Add OpenTelemetry.
- Add high-frequency CSV performance rows.
- Promote performance debug details into Header status.
- Remove any current `/stats`, `/health`, `/api/memory/*`, or SPOT image fields.

## 5. API Contract Proposal

### 5.1 Existing APIs Retained

| Method | Path | Status |
|--------|------|--------|
| GET | `/health` | Retained |
| GET | `/stats` | Retained with additive fields |
| GET | `/api/memory/state` | Retained |
| GET | `/api/memory/details` | Retained |
| GET | `/api/spot/live_image` | Retained |
| GET | `/api/spot/proxy_image` | Retained |
| POST | `/api/observability/export` | Retained |
| POST | `/api/memory/export` | Retained |

### 5.2 `/stats` response additions

Required additive fields:

| Field | Type | Required | Source |
|-------|------|----------|--------|
| `performance_contract_version` | string | Yes | Static server contract |
| `thresholds.operational` | object | Yes | Static defaults or config-free constants |
| `thresholds.regression_budget` | object | Yes | Static defaults aligned with benchmark review |
| `polling.paths["/api/spot/live_image"].success_count` | number | Yes | Existing request/live image response handling |
| `polling.paths["/api/spot/live_image"].failure_count` | number | Yes | Status-code classification |
| `polling.paths["/api/spot/live_image"].stale_count` | number | Yes | Live metadata when available, otherwise `0` |
| `polling.paths["/api/spot/live_image"].avg_age_sec` | number or null | Yes | Live metadata age aggregation |

Backward compatibility:

- Existing consumers must continue to work if they ignore new fields.
- Missing age should be `null`, not a sentinel string.
- Missing path entries remain allowed when no request has occurred in the window.

### 5.3 `/api/performance/summary` optional response

If implemented:

```json
{
  "performance_contract_version": "1.0",
  "generated_at": "2026-06-24T00:00:00Z",
  "source": {
    "stats": "available",
    "health": "available",
    "memory": "available"
  },
  "overall": {
    "status": "ok",
    "warnings": []
  },
  "http": {},
  "polling": {},
  "spot_image": {},
  "resources": {},
  "masking": {
    "internal_hosts": "masked",
    "full_paths": "masked"
  }
}
```

Rules:

- `status` may be `ok`, `warning`, `critical`, or `unknown`.
- `warnings` must use user-safe messages.
- Endpoint must be read-only.
- Endpoint must not perform new probes.

## 6. UI / Settings Proposal

### 6.1 Settings performance summary

Recommended placement:

- Existing Settings diagnostics area, near observability or memory.
- Do not add a new top-level workflow unless the Settings list becomes too dense.

Recommended cards:

| Card | Data source | Display |
|------|-------------|---------|
| HTTP window | `/stats.window` | P95, average latency, requests per second, error rate |
| Polling paths | `/stats.polling.paths` | `/api/data`, live image, proxy image rate/error/age |
| Server resources | `/api/memory/state` plus explicit CPU source | RSS, threads, handles, open files; CPU only from resource monitor artifact or a newly implemented API field |
| Memory profiler | `/api/memory/details` | profiler enabled, TTL, last diff state |
| CSV writer | memory collector or runtime state | queue size, buffer size, last batch size |
| React profiler | artifact import or latest QA output | sample count, max/avg actual duration, errors |

### 6.2 Header boundary

Header should keep these categories only:

- Connection and communication health.
- Data freshness.
- Production-impacting PLC/SPOT/backend failures.
- Required operator action.

Header should not show:

- Benchmark warnings without operational impact.
- Developer profiler details.
- Raw latency tables.
- Client lists.
- Internal addresses or paths.

### 6.3 Masking policy

UI and exported diagnostics must mask:

- Internal hosts and full URLs.
- Full local file paths.
- Credentials, tokens, secrets, and API keys.
- Request bodies.
- Raw client identifiers where not needed for operator action.

Allowed labels:

- `server-localhost`
- `external-server-url`
- `spot-device-address`
- `client-1`, `client-2`
- Repository-relative source paths in developer docs.

## 7. Metrics and Thresholds

### 7.1 User-perceived performance

| Metric | Evidence | Target |
|--------|----------|--------|
| Initial dashboard load | Browser performance entries or Lighthouse-style capture | LCP <= 2.5 s, CLS <= 0.1 |
| Dashboard first usable render | React profiler and screen smoke | Baseline captured and not regressed |
| Polling latency | Frontend `latencyMs`, `/stats.polling.paths["/api/data"]` | <= 100 ms target, < 500 ms failure |
| Chart update | React profiler and time-series frame observation | No visible stall; profiler within baseline |
| SPOT image display | Browser smoke and `/stats.polling.paths["/api/spot/live_image"]` | image response <= 500 ms target |

### 7.2 Remote access performance

| Metric | Evidence | Target |
|--------|----------|--------|
| External dashboard access | Browser smoke from external PC using masked base URL | dashboard loads without route fallback error |
| HTTP request rate | `/stats.window.requests_per_sec` and polling path rates | no unexpected > 30% request-count increase |
| Cache header split | response headers | immutable assets cached, runtime files no-store |
| Live image response | short QA loop and `/stats` delta | no failed live image responses in short smoke |
| Remote client concentration | `/stats.polling.paths.*.unique_clients` and masked top clients | no unexpected duplicate polling fanout |

### 7.3 Server resource performance

| Metric | Evidence | Target |
|--------|----------|--------|
| CPU | `scripts/monitor_resource.py` artifact by default; `/api/memory/state` only if the implementation PR adds an explicit CPU field | stable after warm-up |
| RSS/VMS | `/api/memory/state` history | no unbounded monotonic growth over observation window |
| Threads/handles/open files | `/api/memory/state` | stable after warm-up |
| CSV queue | CSV runtime collector | queue does not approach capacity; no row drops |
| PLC/SPOT backoff | comm metrics and `/health` | backoff explained, no recovery loop storm |
| Log pressure | comm log and server logs | no repeated high-rate warning/error loop |

Default automated growth rule:

- Discard the first 2 minutes after backend start or smoke start as warm-up.
- Evaluate the next 5 minutes as the resource observation window.
- Current backend memory sampling is 5 seconds, so the preferred window contains 60 samples.
- An automated pass/fail verdict requires at least 48 samples spanning at least 4 minutes.
- If the sample requirement is not met, report `inconclusive` and keep the raw snapshots for review.
- Use the first 20% and last 20% of valid samples for average comparison, then check the full window for a mostly upward trend.
- Warn on sustained upward trend in RSS/VMS, thread count, handle count, open file count, or CSV queue size.
- Fail only when sustained growth is paired with exhaustion symptoms, queue near-capacity, dropped rows, repeated recovery loops, or repeated warning/error log pressure.

## 8. Acceptance Criteria

### 8.1 Documentation acceptance

- Plan, design, and review-prep docs are present.
- Only docs are changed.
- `git diff --check` passes.
- New docs pass trailing whitespace checks.
- New docs pass raw internal address, full local path, credential, token, and secret scans.
- Review context identifies implementation candidates and non-goals.

### 8.2 Implementation acceptance

- `/stats` includes `performance_contract_version` and `thresholds`.
- `/stats` remains backward-compatible.
- Live image path metrics include success, failure, stale, and average age.
- React profiler artifacts contain required fields.
- Settings summary, if implemented, stays diagnostic-only.
- Header remains operational-warning focused.
- No new production-write behavior is introduced.
- QA evidence covers `/health`, `/stats`, `/api/memory/state`, `/api/memory/details`, short SPOT live loop, browser render, and React profiler artifact.

## 9. Validation Plan

### 9.1 DOC_ONLY validation

Run:

```powershell
git diff --check
git status --short --branch --untracked-files=all
```

Also scan new docs for:

- trailing whitespace
- raw internal IPs
- full internal URLs
- full local paths
- credential, token, secret, password, and API key leakage

### 9.2 Future source validation

Backend:

- Unit tests around `ObservabilityService` path aggregation.
- FastAPI route smoke for `/stats` additive fields.
- SPOT live image success/failure classification tests.
- Memory endpoint smoke for `/api/memory/state` and `/api/memory/details`.

Frontend:

- Typecheck for new Settings summary types.
- Component tests for Settings performance summary.
- Header tests proving debug performance warnings are not promoted.
- Browser smoke for dashboard load and SPOT image display.

QA:

- Short `qa_spot_live_server.ps1` loop.
- React profiler capture.
- External browser smoke with masked base URL.
- Resource snapshot before and after smoke.

## 10. Risk / Rollback / Observability

Runtime risks for the future implementation:

| Risk | Failure mode | Mitigation |
|------|--------------|------------|
| Stats aggregation lock pressure | High-frequency image requests slow `/stats`. | Reuse existing bucket aggregation; keep payload small. |
| Live image failure classification mismatch | False failure or false success counts. | Classify by status code and response metadata; test 200, 404, 503, 502. |
| Settings summary noise | Operators see developer warnings as production failures. | Keep diagnostic UI in Settings and Header operational-only. |
| Sensitive environment leakage | Internal network details appear in docs or exports. | Mask internal hosts, URLs, full paths, and client identifiers. |
| Threshold false positives | Slow server hardware trips generic budgets. | Use local baseline plus regression budgets and separate warning/failure levels. |

Rollback:

- Documentation rollback: revert these docs.
- Implementation rollback before merge: revert implementation commits.
- Implementation rollback after merge: revert merge commit.
- Production rollback: reinstall previous known-good installer and keep diagnostics read-only.

Observability:

- The future implementation should improve visibility without changing control flow.
- All new metrics should be read-only and aggregate-only.
- No new persistence path is required.

## 11. Next Implementation Prompt

```text
Implement the performance observability baseline from the DOC_ONLY plan/design.

Must implement:
- Add additive `/stats.performance_contract_version`.
- Add additive `/stats.thresholds` with operational thresholds and regression budgets.
- Extend `/stats.polling.paths["/api/spot/live_image"]` with success_count, failure_count, stale_count, and avg_age_sec.
- Preserve all existing `/stats` fields and current API behavior.
- Keep React profiler artifacts compatible with sampleCount, maxActualDuration, avgActualDuration, consoleErrors, and pageErrors.

May implement:
- Settings performance summary if the UI remains diagnostic-only.
- `/api/performance/summary` only if it avoids duplicated frontend aggregation.

Must not implement:
- Long production load tests.
- Active device probes only for performance summary.
- Per-request body logging.
- Raw internal address, URL, credential, token, secret, or full local path exposure.
- OpenTelemetry.
- High-frequency CSV performance rows.
- Header debug-performance warnings.

Validation:
- Backend tests for stats aggregation.
- Frontend typecheck/tests for any UI changes.
- `/health`, `/stats`, `/api/memory/state`, `/api/memory/details` smoke.
- Short SPOT live image server QA loop.
- React profiler artifact capture.
- Browser smoke for dashboard and SPOT image.
```

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.2 | 2026-06-24 | Recreated DOC_ONLY performance observability baseline design | Codex |
