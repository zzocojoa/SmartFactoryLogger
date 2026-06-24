# Performance Observability Baseline Review Prep

> **Summary**: Review checklist and evidence map for the DOC_ONLY performance observability baseline.
>
> **Project**: SmartFactoryLogger v2
> **Version**: 0.2
> **Author**: Codex
> **Date**: 2026-06-24
> **Status**: Draft, DOC_ONLY
> **Plan**: `docs/01-plan/features/performance-observability-baseline.plan.md`
> **Design**: `docs/02-design/features/performance-observability-baseline.design.md`

---

## 1. Summary

This review-prep document exists so the documentation diff can be reviewed before implementation starts. It maps each proposed requirement to current evidence and review gates.

Expected review verdict:

- Approve if the documents are clear enough for an implementation PR and remain DOC_ONLY.
- Request changes if the docs require source changes, expose sensitive environment details, mix operational Header warnings with debug performance data, or make `/api/performance/summary` mandatory without justification.
- Needs clarification if thresholds or validation scope are too vague to implement safely.

## 2. Existing Logic Inventory

| Evidence area | Files to review | Expected conclusion |
|---------------|-----------------|---------------------|
| HTTP stats and route middleware | `backend/app.py`, `backend/Observability/service.py` | `/stats` already exists and should be extended additively. |
| Memory and profiler state | `backend/Observability/memory_service.py` | `/api/memory/state` and `/api/memory/details` can provide memory, thread, handle, open file, profiler, and collector evidence. CPU must come from the resource monitor artifact unless a future implementation explicitly adds an API field. |
| Communication log pressure | `backend/Observability/metrics_logger.py` | EX, LS, and SPOT backoff/recovery are already observable. |
| CSV queue and buffer pressure | `backend/FacilityData/repository.py` | Queue size, buffer size, and last batch size exist as runtime state. |
| Dashboard polling | `frontend/src/domains/FacilityData/` | Poll latency, degraded state, backoff, visibility pause, leader mode, and backfill already exist. |
| React profiler | `frontend/src/shared/profiling/reactRenderProfiler.tsx`, `scripts/collect_react_profiler.cjs` | Profiler artifact fields already exist and should be standardized as review evidence. |
| SPOT live image QA | `scripts/qa_spot_live_server.ps1`, `docs/04-deploy/spot-live-image-nsis-qa.md` | Short live-image loop and `/stats` delta evidence already exist. |
| General performance guidance | `docs/web_performance_guide.md` | Current budgets can seed operational thresholds. |
| Packaging context | `package.json`, `frontend/package.json` | QA script is packaged; React profiler script exists; no package edits needed for DOC_ONLY. |

## 3. Proposed Additional Logic

Reviewer should confirm the docs propose only additive future implementation:

- `/stats.performance_contract_version`
- `/stats.thresholds`
- `/stats.polling.paths["/api/spot/live_image"].success_count`
- `/stats.polling.paths["/api/spot/live_image"].failure_count`
- `/stats.polling.paths["/api/spot/live_image"].stale_count`
- `/stats.polling.paths["/api/spot/live_image"].avg_age_sec`
- React profiler artifact standard fields: `sampleCount`, `maxActualDuration`, `avgActualDuration`, `consoleErrors`, `pageErrors`
- Optional Settings performance summary
- Optional `/api/performance/summary`

Reviewer should reject any interpretation that requires:

- New active device probes for summary data.
- Long automatic production load tests.
- Body logging.
- OpenTelemetry.
- High-frequency CSV performance rows.
- Header promotion of debug-only performance warnings.

## 4. Do-not-implement Scope

The documentation diff must not contain:

- Source code changes.
- Package or lockfile changes.
- Config changes.
- DB, CSV, PLC, or SPOT setting changes.
- Dist, installer, or generated artifact changes.
- Raw internal IPs.
- Full internal URLs.
- Full local filesystem paths.
- Credentials, tokens, secrets, passwords, or API keys.

## 5. API Contract Proposal

Review gates:

| Gate | Pass condition |
|------|----------------|
| Backward compatibility | Existing `/stats` fields remain documented as retained. |
| Versioning | New `performance_contract_version` is required. |
| Thresholds | Operational thresholds and regression budgets are separated. |
| Live image stats | Live image path stats include success, failure, stale, and average age fields. |
| Optional summary | `/api/performance/summary` is clearly optional. |
| No new probes | Summary and stats are documented as aggregation-only. |
| Sensitive data | Raw internal host/URL/path/secret data is forbidden. |

## 6. UI / Settings Proposal

Review gates:

| Gate | Pass condition |
|------|----------------|
| Settings boundary | Performance summary is optional and diagnostic-only. |
| Header boundary | Header remains focused on operational warnings. |
| Operator clarity | Debug/profiler details are not presented as production failure unless operationally relevant. |
| Masking | Client, host, URL, and path values are masked or omitted in UI/export guidance. |
| Existing UI compatibility | The design can fit into current Settings observability/memory surfaces without requiring a new workflow. |

## 7. Metrics and Thresholds

Review gates:

| Metric group | Required evidence |
|--------------|-------------------|
| User-perceived performance | LCP, CLS, dashboard render, polling latency, chart update, SPOT image display. |
| Remote access performance | External dashboard smoke, HTTP latency, request rate, cache header split, SPOT image response. |
| Server resource performance | CPU, memory, threads, handles, open files, CSV queue, PLC/SPOT backoff, log pressure. |
| CPU source | CPU must be documented as `scripts/monitor_resource.py` artifact evidence by default, or as an app API field only after the implementation PR adds and tests that field. |
| Regression budget | Timing, bundle size, and request-count thresholds are separate from operational limits. |
| Growth criteria | Resource growth must ignore the first 2 minutes as warm-up, then evaluate a 5-minute window. With the current 5-second sampling cadence, prefer 60 samples and require at least 48 samples across at least 4 minutes for an automated verdict. |

Resource growth review rule:

- Fewer than 48 valid samples is inconclusive, not pass.
- Compare the first 20% and last 20% of the valid window and inspect the full window for a mostly upward trend.
- Treat sustained upward RSS/VMS, thread, handle, open file, or CSV queue growth as warning.
- Treat growth plus exhaustion symptoms, queue near-capacity, row drops, repeated recovery loops, or repeated warning/error log pressure as failure.

## 8. Acceptance Criteria

Documentation acceptance:

- Three docs are present.
- Only docs changed.
- `git diff --check` passes.
- New docs have no trailing whitespace.
- New docs do not expose raw internal IP, full URL, credential, token, secret, password, API key, or full local path values.
- Review context is sufficient for a separate reviewer to approve or request changes.

Implementation acceptance for a later PR:

- Additive `/stats` contract implemented.
- Live image metrics implemented.
- React profiler artifact standard enforced.
- Optional Settings summary does not pollute Header.
- QA evidence includes backend, frontend, browser, resource, and SPOT live image checks.

## 9. Validation Plan

Required DOC_ONLY commands:

```powershell
git status --short --branch --untracked-files=all
git diff --check
```

Required DOC_ONLY scans:

```powershell
rg -n "[ \t]$" docs/01-plan/features/performance-observability-baseline.plan.md docs/02-design/features/performance-observability-baseline.design.md docs/03-review/performance-observability-baseline.review.md
rg -n "([0-9]{1,3}\.){3}[0-9]{1,3}|https?://[^ )`]+|[A-Za-z]:\\|credential|secret|token|api[_ -]?key|password" docs/01-plan/features/performance-observability-baseline.plan.md docs/02-design/features/performance-observability-baseline.design.md docs/03-review/performance-observability-baseline.review.md
```

Expected scan interpretation:

- Trailing whitespace scan should return no matches.
- Sensitive-data scan may match generic words such as `token` or `password` inside the masking policy. That is acceptable only when no real secret value, internal host, full URL, or full local path appears.

## 10. Risk / Rollback / Observability

Review risks:

| Risk | Review action |
|------|---------------|
| Docs over-specify implementation | Request changes to mark optional items optional and keep source decisions reviewable. |
| Docs under-specify thresholds | Request clarification or add non-blocking note depending on severity. |
| Sensitive data leakage | Request changes. |
| Header/UI boundary unclear | Request changes if operator warning semantics can change. |
| Long load test implied | Request changes. |

Rollback:

- This doc-only branch can be reverted by deleting the three docs.
- No runtime rollback is needed for this DOC_ONLY diff.
- Future implementation rollback remains separate from documentation rollback.

Observability:

- This branch creates review context only.
- Future implementation must use existing runtime observability surfaces first.

## 11. Next Implementation Prompt

After this DOC_ONLY diff is reviewed, start a separate implementation branch with this prompt:

```text
Implement only the approved performance observability baseline.

Base the work on:
- docs/01-plan/features/performance-observability-baseline.plan.md
- docs/02-design/features/performance-observability-baseline.design.md
- docs/03-review/performance-observability-baseline.review.md

Do not change production DB, CSV data, PLC/SPOT settings, installer, or deployment state.
Keep `/stats` backward-compatible.
Add `performance_contract_version`, `thresholds`, and live image result aggregation.
Treat Settings summary and `/api/performance/summary` as optional.
Keep Header operational-warning focused.
Run targeted backend/frontend tests and short smoke validation.
```

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.2 | 2026-06-24 | Recreated DOC_ONLY review preparation document | Codex |
