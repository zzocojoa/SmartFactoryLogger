# Gap Analysis: spot-realtime-image-performance

> Date: 2026-08-21 | Design: `docs/02-design/features/spot-realtime-image-performance.design.md`
> Scope: local implementation and guarded-transport validation only

---

## Match Rate: 100%

## Summary

The implementation matches all ten functional requirements and all eight component
responsibilities in the approved design. Both application profiles use one canonical
SPOT `GET /image.jpg` resource, one cache, and one refresh task. The local guarded
Windows transport benchmark demonstrates the intended operator cadence without port
pool or concurrency violations.

This 100% score is design-to-code conformance, not production readiness. No request was
sent to the configured physical SPOT device, no installer was produced, and no 15- or
120-minute field canary was run.

## Requirement Traceability

| Requirement | Implementation evidence | Result |
|---|---|---|
| FR-01 canonical `/image.jpg` | Strict `_resolve_spot_image_url()` constructs the path server-side. | PASS |
| FR-02 shared cache/task | Both profiles call `fetch_image_async()` and share `_img_cache_entry`/`_img_refresh_task`. | PASS |
| FR-03 snapshot 3-10 s | Snapshot profile retains existing normalized TTL. | PASS |
| FR-04 dynamic <=6/s budget | Live rate subtracts temperature/internal/diagnostic rates and caps at 4 FPS. | PASS |
| FR-05 visibility pause | Hidden state cancels timers; visible resume starts one fetch. | PASS |
| FR-06 bounded retry | Existing 0.5/1/2-second retry policy remains covered by integration tests. | PASS |
| FR-07 single upstream | Double-checked cache plus shared single-flight task; benchmark max concurrency 1. | PASS |
| FR-08 route/profile response | Both `.jpg` routes return no-store JPEG and `X-Spot-Image-Profile`. | PASS |
| FR-09 removed paths | `/api/spot/live_image` and `/api/spot/proxy_image` return 404 in route tests. | PASS |
| FR-10 host hardening | Scheme, credentials, whitespace, path, query, fragment, and invalid port fail before I/O. | PASS |

The broad repository audit also aligned the operator settings statistics with the live
route and extended the packaged field QA to both application profiles. An ignored,
unregistered developer-local prototype that references public internet URLs was
classified as non-product state and preserved unchanged.

## Component Match

- [x] Host validator and canonical URL builder.
- [x] Snapshot and operator-live freshness policies.
- [x] Shared immutable JPEG cache and single-flight refresh.
- [x] Dynamic background request budget.
- [x] Profile-aware FastAPI routes and observability.
- [x] Server-derived frontend cadence with legacy compatibility fallback.
- [x] Completion-driven/visibility-aware/bounded-backoff view model.
- [x] Repeatable localhost HTTP/1.0-close guarded-transport benchmark.
- [x] Live-route-first operator statistics with old-backend snapshot fallback.
- [x] Dual-profile packaged field QA contract.

## Validation Evidence

| Check | Result |
|---|---|
| Focused backend SPOT/observability suite | 182 tests PASS |
| Electron startup suite | 94 tests PASS |
| Frontend full suite | 35 files, 265 tests PASS |
| Backend full suite | 711 tests PASS |
| Ruff | PASS |
| mypy | PASS, 6 source files |
| Frontend production build | PASS, 4,532 modules transformed |
| Windows QA self-tests | PASS |
| `git diff --check` | PASS |

## Performance Evidence

The 10.140-second localhost HTTP/1.0-close run used the real guarded Windows SPOT
transport and a decoder-valid JPEG response:

- 37 successful frames; 3.6489 displayed and upstream FPS.
- 4.0 FPS effective cap and 250 ms effective interval.
- 31.0 ms p95 response latency.
- Maximum upstream concurrency 1.
- Source-port enforcement active with a 768-port pool.
- Pool exhaustion, reuse violations, server/client failures, and transport failures: 0.

## Missing Items

No missing item exists within the approved local implementation scope.

## Operational Gaps Outside Match Rate

- [ ] Build and identify the exact installer artifact by SHA-256.
- [ ] Verify the physical SPOT `/image.jpg` response and both application routes.
- [ ] Compare request/error counters and Windows transport diagnostics for 15 minutes.
- [ ] Complete the established 120-minute canary with old-ACK/RST and port-pool review.
- [ ] Obtain explicit production promotion approval.

## Deviations

No functional deviation remains. JPEG validation was strengthened from marker checks to
Pillow decoder verification, and the broad-audit peripheral fixes were incorporated into
design version 1.0.2.

## Recommendation

Proceed to the local completion report. Keep production status as
`FIELD_REVALIDATION_REQUIRED` until the identity-bound installer and physical-device
canary gates pass.
