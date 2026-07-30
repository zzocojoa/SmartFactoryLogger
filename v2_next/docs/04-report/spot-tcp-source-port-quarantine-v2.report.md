# Completion Report: SPOT TCP Source-Port Quarantine v2

> Date: 2026-07-31 | Level: Dynamic | Match Rate: 100%
> Validated package: `FIELD_CANARY_PASS / PHYSICAL_PATH_PARTIAL`
> Current PR HEAD: `FIELD_REVALIDATION_REQUIRED`
> Closure: `F101D88_DONE_WITH_CONCERNS / CURRENT_HEAD_OPEN`
> Evidence scope: packaged source commit `f101d8842bfbcc422007465f49a5f8391e4704b4`

---

## 1. Summary

SmartFactoryLogger now owns the complete Windows source-port lifecycle for every
SPOT HTTP request. A 768-record exclusive guard pool leases OS-assigned ports,
routes requests through the Python standard HTTP client, and enforces a
75-second application-monotonic quarantine before reuse.

The implementation closes the field-observed same 4-tuple reuse risk without
changing public routes, configuration, CSV, or database contracts. It
intentionally reduces background request cadence and extends backward-compatible
image metadata and `/api/spot/config.image` diagnostics. The final `1.0.17`
package from commit `f101d88` passed commit-bound operator re-attestation, the
full one-command CSV QA, the approved 15-minute smoke, a 120-minute passive
canary, and the final live gate on the actual server. No new `spot_image`
ConnectTimeout, SPOT handshake failure, HTTP error, pool exhaustion, transport
failure, or reuse violation occurred.

Managed-switch evidence was unavailable, so the software promotion gate passes
for the exact `f101d88` package while physical-path attribution remains partial.
This limitation does not require rollback of the server. A post-field
adversarial review subsequently found and fixed a rare observation-fact
post-append `stat()` failure path in commit `70b9339`; because that is a runtime
change, its eventual package must repeat the commit-bound field gates before
promotion.

```text
Completion rate: 100%
Design checkpoints: 32 / 32
Blocking local gaps: 0
Act iterations: 1
Field result: FIELD_CANARY_PASS
Physical-path result: PHYSICAL_PATH_PARTIAL
```

## 2. Related Documents

| Phase | Document | Status |
|---|---|---|
| Plan | `docs/01-plan/features/spot-tcp-source-port-quarantine-v2.plan.md` | Complete |
| Design | `docs/02-design/features/spot-tcp-source-port-quarantine-v2.design.md` | Complete |
| Analysis | `docs/03-analysis/spot-tcp-source-port-quarantine-v2.analysis.md` | 100% |
| Parent analysis | `docs/03-analysis/spot-request-churn-remediation.analysis.md` | Updated |

## 3. Completed Items

### 3.1 Functional requirements

- [x] Create the complete 768-port exclusive guard pool before SPOT polling.
- [x] Lease each guarded port to `http.client` through `source_address`.
- [x] Quarantine success, error, timeout, protocol failure, and cancelled work
  for at least 75 seconds.
- [x] Retry only bounded bind collisions with another guarded lease.
- [x] Prohibit OS-selected source-port fallback on Windows.
- [x] Serialize SPOT I/O through one worker while retaining the existing device
  request lock and request budget.
- [x] Route image, temperature, internal temperature, diagnostic, focus, and
  actuator requests through the guarded transport.
- [x] Drain the worker and close guards with bounded shutdown behavior.
- [x] Preserve existing domain and operator-facing error contracts.
- [x] Expose only aggregate, allowlisted source-port lifecycle diagnostics.

### 3.2 Act closure

- [x] Unsupported Windows enforcement now raises during startup.
- [x] Cancelled worker failures emit one privacy-safe bounded warning.
- [x] Concurrent and asyncio wrapper exceptions are both collected.
- [x] Internal test reset drains and clears transport/client state.
- [x] Drain-probe failures preserve the original lifespan exception and cannot
  bypass control-shutdown closeout.
- [x] Partial guard-close failures attempt all guards and remain retryable.
- [x] Source-port diagnostics keep one key schema before, during, and after the
  guarded transport lifecycle.
- [x] Observation and image fact writers maintain exact runtime manifest state,
  so shutdown closeout does not rescan indefinitely growing historical files.
- [x] A LogPath fallback or live path change preserves v2 CSV recording while
  marking unmatched runtime fact manifests incomplete and failing closeout
  closed.
- [x] One-command QA records the observed current CSV basename for active-file
  evidence, then selects the final metadata sidecar by the exact live
  logger-service instance, build commit, shutdown closeout reason, and persisted
  sample sequence. It also requires repeated health failure plus zero product
  processes before treating UI shutdown as complete.
- [x] Observation and image closeout reject earlier writer failures or pending
  observation spool work, including unreadable, malformed, and schema-mismatched
  restarted spools, instead of emitting a falsely clean final manifest.
- [x] Direct failure, protocol, cancellation, request-kind, and shutdown tests
  cover the designed transport contract.

## 4. Quality Metrics

| Metric | Target | Final | Status |
|---|---:|---:|---|
| Design match rate | `>=90%` | `100%` | PASS |
| Source-port quarantine | `>=75.0s` | `75.0s` | PASS |
| Guard pool capacity | `768` | `768` | PASS |
| Reuse at 74.999 seconds | blocked | blocked | PASS |
| Reuse at 75.000 seconds | allowed | allowed | PASS |
| Focused backend tests | all | 112 tests + 2 subtests | PASS |
| Full backend tests | all | 637 | PASS |
| Electron tests | all | 40 | PASS |
| Frontend tests | all | 253 / 34 files | PASS |
| Ruff / mypy | no errors | no errors | PASS |
| Unhandled future warnings | `0` | `0` | PASS |
| NSIS QA self-test | all checks | all checks | PASS |
| Actual source-port values emitted | `false` | `false` | PASS |
| Actual-server canary duration | `120 min` | `7,201.944s` | PASS |
| New `spot_image` ConnectTimeout | `0` | `0` | PASS |
| SPOT handshakes / HTTP bodies | all | `22,184 / 22,184` | PASS |
| SPOT handshake/HTTP/RST failures | `0` | `0` | PASS |
| Same 4-tuple reuse under 5s | `0` | `0` | PASS |
| Same 4-tuple reuse under 60s | `0` | `0` | PASS |
| Internal minimum reuse interval | `>=75.0s` | `75.0s` | PASS |
| Total SPOT opens, fixed 60s p95 | `<=6.0/s` | `3.1333/s` | PASS |
| Image upstream, fixed 60s p95 | `<=0.5/s` | `0.3333/s` | PASS |
| Pool exhaustion / reuse violation | `0 / 0` | `0 / 0` | PASS |
| SPOT transport failure | `0` | `0` | PASS |
| Server NIC errors/discards | `0` | `0` | PASS |

## 5. Field Verification

### 5.1 Package and live gate

- Source commit:
  `f101d8842bfbcc422007465f49a5f8391e4704b4`
- Product version: `1.0.17`
- Candidate installer SHA-256:
  `98A6CC5FC8BFBDC94B6A379D332F2D0C57EAC44F65490EF9193AA08DE554B4F8`
- Installed backend SHA-256:
  `FAE64D4BBAF86184308B96E42E1B30EFF906B7A03F4B2CDA35584CB50BFDF18F`
- Attested config SHA-256:
  `117A79AE9E79C0032D73E7E0425DFD26B3DD2BD44B6FC913C9E68AA1C849B592`
- The one-command SPOT Temperature v2.5 QA passed all runtime, attestation,
  finalized CSV, fact-manifest, and repository-validator checks. Its evidence
  SHA-256 is
  `D570376BC3D406EB5F1F0617E9F71900AD66CA436C43FF59E42D410ACC1469B7`.
- Attestation remained verified, operator-verified, fingerprint-matched, and
  free of configuration drift.
- `spot-source-port-quarantine-v2`, the 768-record pool, 75-second quarantine,
  `spot-background-request-budget-v2`, and `spot-image-demand-shaping-v2`
  remained active.
- The post-canary live gate at 2026-07-31 00:33:08 KST reconfirmed the exact
  backend and config hashes, source commit, HTTP 200 health, one backend
  process, four Electron processes, verified attestation, no drift, an active
  source-port policy, and zero reuse, exhaustion, or transport failures.

### 5.2 15-minute passive smoke

The actual-server run `runtime_validation_20260730_170609` observed normal-screen
operation for `901.308s` and stopped at the fixed deadline without a trigger.
Bidirectional packet preflight passed with 120 outbound and 142 inbound
packets. All 2,807 SPOT HTTP events completed their TCP handshake, header, and
body; failed connections, retransmitted SYNs, reset-before-response events, and
same 4-tuple reuse under 60 seconds were zero. All 891 ping probes succeeded.

The dedicated trigger monitor completed 900 polls with zero monitor errors, a
maximum poll gap of `1,044.332ms`, and no error-queue change. The smoke remained
`PHYSICAL_PATH_PARTIAL` because managed-switch evidence was unavailable.

### 5.3 120-minute passive canary

The actual-server run `runtime_validation_20260730_221516` observed normal-screen
operation for `7,201.944s` and stopped at the fixed deadline without a trigger.

- Bidirectional packet preflight passed with 115 outbound and 142 inbound
  packets before the full capture.
- All 22,184 captured SPOT HTTP events completed their TCP handshake, HTTP
  header, and response body. All responses used the device's expected
  `HTTP/1.0` framing.
- HTTP non-200, 5xx, retransmitted SYN, RST-before-response, unresolved flow,
  and no-response counts were all zero.
- Packet-derived same 4-tuple reuse under 60 seconds was zero. The
  application-monotonic minimum remained exactly 75.0 seconds and the
  reuse-violation counter remained zero.
- The fixed 60-second total-open rate had p95 `3.1333/s`; the image rate had
  p95 `0.3333/s`.
- The dedicated error trigger monitor completed 7,166 polls with 17 transient
  localhost polling errors. The maximum poll gap was `3,381.210ms`, below the
  5-second detection warning threshold; the full error snapshots did not
  change and no new `spot_image` ConnectTimeout occurred.
- All 7,062 ping probes succeeded. Server NIC receive/transmit errors and
  discards remained zero.
- The final live gate reported cumulative handled totals of 3,992 bind
  collisions and 170 rebind retries. Pool exhaustion, reuse violations, and
  transport failures remained zero, demonstrating bounded recovery rather
  than fallback.
- Image status remained `ok`, accepted requests, and recorded zero refresh
  failures.

### 5.4 Evidence integrity

- Canonical sanitized artifact:
  `runtime_validation_20260730_221516_sanitized_share.zip`
- Canonical sanitized SHA-256:
  `9C11F91D414C246EC715E2B142061B6442185D7E2F3632094EEF14EBF1349C40`
- Transferred full run archive:
  `runtime_validation_20260730_221516.zip`
- Transferred full run archive SHA-256:
  `33B0550B84496201A9CD9D0D5741FD700F13DAA547C4B984D8A66FC0292C20D7`
- Final live-gate evidence:
  `server_check_after_f101d88_120min_canary_final_20260731_003308.json`
- Final live-gate evidence SHA-256:
  `60E858924B6A3EC2FE3CC9C1FE8A3142FD346487B975C06D84F333274CEA5BA5`
- Pre-canary live-gate evidence
  `server_check_before_f101d88_120min_canary_20260730_221230.json` has SHA-256
  `412AE69246B5A1325F52E6650DB1700361E0186C3018AD06FE01C3E547AF2FE1`.
- The transferred 15-minute run archive
  `runtime_validation_20260730_170609.zip` has SHA-256
  `7224BC7E801D2C3349C58D1943F61FB1CD839686076425D1BFD02470850BD0FF`;
  its canonical sanitized artifact has SHA-256
  `BFA1291A76FE05AAEA90A9983ED7F2F6E5317337450AC50CD6D64A0CF66C2CD6`.
- The raw-private archive contains sensitive operational paths and network
  details and must not be published or attached to public issues.

### 5.5 Validation expression normalization

An earlier `163d31b` one-off wrapper applied a generic boolean cast to a
structured drift-field value and produced a reporting-only false negative.
The `f101d88` pre-canary and final wrappers normalized drift fields before
building their boolean `Checks` object. The canonical final evidence therefore
records `DriftFieldsClear: true` directly, with all 32 checks passing. No
manually printed pass line or post-hoc value coercion is used for the final
promotion decision.

## 6. Security and Operations

- No source port, IP, URL, MAC, credential, payload, or absolute path is added to
  product diagnostics or lifecycle warnings.
- No registry, firewall, NIC, switch, SPOT setting, config, database, or CSV
  migration is introduced.
- Fail-closed pool initialization and exhaustion are intentional. They can stop
  SPOT polling instead of silently violating the quarantine invariant.
- Rollback requires the already verified v1.0.16 installer; no data repair or
  schema rollback is needed.
- The actual server remains on the verified `1.0.17` package built from
  `f101d88`. Current evidence does not indicate rollback.
- The final package, backend, config, attestation, QA, canary, and live-gate
  identities are bound to the same `f101d88` source commit.
- Error-queue deletion, configuration changes, and forced image-load tests are
  not required for the running package.
- Commit `70b9339` preserves observation-fact deduplication when the row append
  succeeds but the immediate file-size probe fails. Its manifest still fails
  closed, and a regression test proves the durable row is neither spooled nor
  duplicated.
- The post-field runtime fix cannot inherit `f101d88` package evidence. Its
  final package must pass re-attestation, QA, 15-minute smoke, 120-minute
  canary, and the final live gate before promotion.

## 7. Lessons Learned

### Keep

- Preserve standard-library HTTP framing instead of maintaining a custom parser.
- Use actual Windows socket behavior as a required complement to fake-clock unit
  tests.
- Keep network identifiers out of application diagnostics and logs.

### Problem

- Reducing request rate alone did not prevent Windows from reusing the same
  4-tuple in less than 60 seconds.
- Caller cancellation can leave multiple future layers requiring explicit,
  bounded result collection.

### Try

- Verify packaged backend policy diagnostics before any physical-server smoke.
- Treat pool state sums, exhaustion counters, and minimum reuse interval as
  mandatory pre-smoke and smoke gates.

## 8. Field Closure and Concerns

- [x] Clean PyInstaller backend and NSIS installer generated from the frozen
  commit.
- [x] Commit, installer, backend, bundle, file count, policy, pool, quarantine,
  and rollback identities verified.
- [x] Actual-server pre-install state and rollback baseline recorded.
- [x] Actual-server 15-minute passive smoke passed.
- [x] Operator re-attestation completed with no configuration drift.
- [x] Actual-server 120-minute passive canary passed the software gates.

The collector returned exit code 2 only because managed-switch start/end
counters were unavailable. Therefore faults between the SPOT device and the
managed-switch path cannot be fully excluded. Server-side SPOT TCP, HTTP, ping,
NIC, application, process, source-port, and image evidence passed.

The earlier PowerShell structured-value normalization defect in Section 5.5
was a non-product reporting defect. The `f101d88` wrappers corrected it before
the final promotion gate.

## 9. Next Action

Keep the verified `1.0.17` package from commit `f101d88` running on
the verified target server. Do not rollback, clear the error queue, or change
SPOT settings based on the current evidence. Build the final PR HEAD only after
local and CI gates pass, then repeat commit-bound re-attestation, QA, 15-minute
smoke, 120-minute canary, and final live-gate verification for that new package.
If governance later requires full physical-path sign-off, collect managed-switch
port counters and logs as a separate operational evidence task. If the SPOT
under-range state returns unexpectedly, inspect the physical process and device
range separately from this closed TCP remediation.

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-07-27 | Local PDCA completion report |
| 1.1 | 2026-07-28 | Actual-server 15-minute smoke and 120-minute field canary closure |
| 1.2 | 2026-07-28 | Scoped field evidence to packaged commit `931c869`; final `1.0.17` promotion remains gated |
| 1.3 | 2026-07-29 | Final `0c641b7` package QA, 15-minute smoke, 120-minute canary, and final live-gate closure |
| 1.4 | 2026-07-29 | Kept `0c641b7` field evidence separate from later current-HEAD promotion gates and refreshed automated test totals |
| 1.5 | 2026-07-29 | Added exception-preserving, retryable shutdown cleanup and stable lifecycle diagnostics with regression coverage |
| 1.6 | 2026-07-29 | Made fact-manifest shutdown closeout independent of accumulated historical file size |
| 1.7 | 2026-07-29 | Preserved v2 CSV logging across LogPath fallback and transition while failing unmatched fact closeout closed |
| 1.8 | 2026-07-29 | Bound QA to the exact live CSV closeout and rejected malformed, mismatched, unreadable, or pending spool work |
| 1.9 | 2026-07-29 | Bound QA to the actual shutdown closeout and verified persisted sample sequence against the finalized CSV |
| 2.0 | 2026-07-30 | Froze final `163d31b` QA, smoke, 120-minute canary, live-gate evidence, and structured-value normalization finding |
| 2.1 | 2026-07-31 | Froze identity-matched `f101d88` QA, 15-minute smoke, 120-minute canary, corrected live-gate evidence, and production operating decision |
| 2.2 | 2026-07-31 | Kept `f101d88` as the verified runtime and reopened current-HEAD field promotion after the post-field observation-fact durability fix |
