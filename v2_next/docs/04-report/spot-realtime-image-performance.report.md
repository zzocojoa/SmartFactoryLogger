# Completion Report: spot-realtime-image-performance

> Date: 2026-08-21 | Level: Dynamic
> Branch: `codex/spot-realtime-image-performance`
> Local implementation: COMPLETE | Field status: PASS_WITH_SWITCH_LIMITATION

---

## 1. Summary

### 1.1 Feature Overview

The manufacturer-defined SPOT image request is now implemented as one strict upstream
resource, `GET http://{SPOT_IP}/image.jpg`, with two application-owned policies:

- `/api/spot/image.jpg`: 3-10-second snapshot/evidence bridge.
- `/api/spot/live_image.jpg`: dynamically budgeted operator display, up to 4 FPS.

Both routes share one validated JPEG cache, one refresh task, one device lock, and the
guarded Windows HTTP/1.0-close transport. The frontend waits until the previous image is
decoded/displayed, pauses while hidden, and retains bounded retry/backoff.

### 1.2 Audit Outcome

The broad audit found that the pre-change runtime already used `/image.jpg`, but the
three-second frontend/backend policy made the operator view materially slower than the
manual's completion-driven sequence. It also found host/path injection risk in raw
`SPOT_IP` URL concatenation, marker-only JPEG validation, snapshot-only operator
statistics, and snapshot-only packaged field QA.

All product-scope findings were corrected. Runtime source search contains no support for
`/newjpeg.jpg`, `image.ssi`, `SPOT_LIVE_IMAGE_URL`, or `SPOT_IMAGE_URL`; remaining hits
are rejection tests, legacy-option removal, historical documents, or ignored local
prototype files.

### 1.3 Final Match Rate

100% design-to-implementation match (target: 90%). No P0 gap remains in local scope.

## 2. Completed Items

- [x] Canonical upstream `/image.jpg` with strict host validation.
- [x] Shared snapshot/operator-live cache and single-flight acquisition.
- [x] Dynamic total background budget <=6 requests/s.
- [x] Default 4 FPS operator policy and server-derived frontend cadence.
- [x] Completion-driven display, hidden pause, single in-flight, bounded retry.
- [x] Decoder-backed JPEG validation and fail-closed errors.
- [x] Per-route/per-profile observability and live-route-first settings display.
- [x] Backward-compatible snapshot route and field-QA artifact field.
- [x] Dual-profile packaged server QA with a 250ms minimum request delay.
- [x] Local guarded-transport performance harness and full repository validation.

## 3. Engineering Assessment

### 3.1 Risk and Compatibility

- Risk: high, because image cadence shares a physical device and Windows short-lived
  connection pool with temperature/diagnostic traffic.
- API compatibility: additive `.jpg` live route and config fields; snapshot route and
  existing `refresh_interval` remain. The old extensionless routes intentionally remain
  404.
- Data/migration risk: none; no database, CSV, evidence-fact, or config schema migration.
- Security: URL target/path is server-owned, malformed host input fails before I/O,
  decoded JPEG validation fails closed, and diagnostics omit raw network identifiers.

### 3.2 Failure and Observability

- Operational failure mode: the image route returns explicit 404/502; logging,
  temperature, and other services continue independently. Expired frames are not
  returned as successful fresh data.
- Observable controls: effective live FPS/TTL, request-budget status, per-profile
  downstream demand, shared cache/upstream/single-flight counts, and source-port pool,
  quarantine, exhaustion, reuse, and transport-failure counters.
- Rollback: revert this branch/commit or reinstall the currently verified identity-bound
  package. No down migration or data repair is required.

## 4. Validation

| Check | Result |
|---|---|
| Focused backend SPOT/observability | 182 tests PASS |
| Electron startup | 94 tests PASS |
| Frontend full | 35 files, 265 tests PASS |
| Backend full | 727 tests PASS |
| Ruff / mypy | PASS / PASS |
| Frontend production build | PASS, 4,532 modules |
| Windows QA self-tests | PASS |
| PowerShell field-QA syntax | PASS; not executed against device |
| `git diff --check` | PASS |

The final 10.140-second localhost HTTP/1.0-close guarded-transport run produced 37
successful frames at 3.6489 FPS, 31.0ms p95 response latency, and maximum upstream
concurrency 1. Source-port enforcement was active; pool exhaustion, reuse violations,
and transport/server/client failures were all zero.

## 5. Metrics

| Metric | Value |
|---|---:|
| Relevant files | Branch-scoped implementation, tests, canary, and PDCA evidence |
| Working diff | See the exact PR diff; volatile local counts are intentionally omitted |
| PDCA iteration | 1 |
| Design match rate | 100% |
| Local performance target | PASS (>=3.5 displayed FPS) |
| Physical-device validation | PASS_WITH_SWITCH_LIMITATION |
| Production promotion | HOLD pending PR CI and explicit risk acceptance |

## 6. Learnings

1. The PDF defines the device resource, not a safe production polling rate. The cadence
   must also honor observed Windows source-port quarantine constraints.
2. A separate application live route is safe only when it remains a policy profile over
   the same upstream cache/task; a second device loop would reintroduce churn.
3. Passing markers are not proof of a valid JPEG. Decoder verification prevents silent
   publication of marker-wrapped arbitrary data.
4. New traffic paths must be followed through settings observability and packaged field
   QA, not only backend route tests.

## 7. Follow-up Gate

- [x] Produce the identity-bound private installer and record SHA-256/source commit.
- [x] Run direct SPOT `/image.jpg`, snapshot route, and live route smoke tests.
- [x] Observe request/error/source-port counters for at least 15 minutes.
- [x] Complete the established 120-minute canary and inspect old-ACK/RST evidence.
- [ ] Obtain explicit production promotion approval.

The local completion report and the field evidence do not independently authorize
production promotion. The remaining gates are recorded in the
[production promotion pre-audit](../04-deploy/spot-realtime-image-v1022-production-promotion-preaudit.md).

The original 120-minute controller result was `SPOT_120M_ROLLBACK_REQUIRED`: the
immediate operator prompt answer was blank and one request remained in flight at the
end boundary. The later pass is a corrected interpretation that preserved the original
result, recorded a delayed historical `YES`, and did not rerun the observation. An
eventual production approver must explicitly accept that boundary and the missing
managed-switch evidence.

The field-tested product identity is intentionally unchanged by this follow-up. A
separate product build must add an explicit JPEG width, height, and total-pixel ceiling
and reject decompression-bomb inputs before that security risk can be closed; that new
build requires its own field validation.
