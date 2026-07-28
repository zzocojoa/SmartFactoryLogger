# Completion Report: SPOT TCP Source-Port Quarantine v2

> Date: 2026-07-28 | Level: Dynamic | Match Rate: 100%
> Status: `FIELD_CANARY_PASS / PHYSICAL_PATH_PARTIAL`

---

## 1. Summary

SmartFactoryLogger now owns the complete Windows source-port lifecycle for every
SPOT HTTP request. A 768-record exclusive guard pool leases OS-assigned ports,
routes requests through the Python standard HTTP client, and enforces a
75-second application-monotonic quarantine before reuse.

The implementation closes the field-observed same 4-tuple reuse risk without
changing request cadence, public endpoints, configuration, CSV, database, or
frontend contracts. The packaged candidate passed the approved 15-minute smoke
and a 120-minute passive canary on the actual server. No new `spot_image`
ConnectTimeout, SPOT handshake failure, HTTP error, pool exhaustion, transport
failure, or reuse violation occurred.

Managed-switch evidence was unavailable, so the software promotion gate passes
while physical-path attribution remains partial. This limitation does not
require rollback or another immediate canary.

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
| Full backend tests | all | 533 | PASS |
| Electron tests | all | 38 | PASS |
| Frontend tests | all | 250 / 33 files | PASS |
| Ruff / mypy | no errors | no errors | PASS |
| Unhandled future warnings | `0` | `0` | PASS |
| NSIS QA self-test | all checks | all checks | PASS |
| Actual source-port values emitted | `false` | `false` | PASS |
| Actual-server canary duration | `120 min` | `7,201.543s` | PASS |
| New `spot_image` ConnectTimeout | `0` | `0` | PASS |
| SPOT handshakes / HTTP bodies | all | `22,322 / 22,322` | PASS |
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
  `931c869e34e00b62acc8344a3f3f01731a776b7f`
- Candidate installer SHA-256:
  `DAF98A7191C38A3D06C1B71D2B48D2B4B3A26C220EE24A18C16EB99467F7821F`
- Installed backend SHA-256:
  `F85FE38E0F9E8073C2536F0D244BA62C66BB60F0A6B582B877AAF0B5775BDAFE`
- Attested config SHA-256:
  `35773C53C115C9F2B479534C9CD417132A35F70D8F21D1FF1DD2D76EF7FB2B96`
- Attestation remained verified, operator-verified, fingerprint-matched, and
  free of configuration drift.
- `spot-source-port-quarantine-v2`, the 768-record pool, 75-second quarantine,
  `spot-background-request-budget-v2`, and `spot-image-demand-shaping-v2`
  remained active.

### 5.2 120-minute passive canary

The actual-server run `runtime_validation_20260728_131749` observed normal-screen
operation from 2026-07-28 13:18:25 through 15:18:26 KST. It stopped at the fixed
deadline without a trigger.

- All 22,322 captured SPOT HTTP events completed their TCP handshake, HTTP
  header, and response body.
- HTTP non-200, 5xx, retransmitted SYN, RST-before-response, unresolved flow,
  and no-response counts were all zero.
- The packet-derived same 4-tuple reuse minimum was 74.008 seconds, with zero
  events under 60 seconds. The application-monotonic minimum remained exactly
  75.0 seconds and the reuse-violation counter remained zero. The small
  packet/application boundary difference reflects scheduling between the
  internal connect-start marker and the on-wire SYN; it does not violate either
  formal field gate.
- The pool recorded 455 handled bind collisions and 59 handled rebind retries.
  Acquire waits, pool exhaustion, reuse violations, and transport failures
  remained zero, demonstrating bounded recovery rather than fallback.
- The fixed 60-second total-open rate had p95 3.1333/s and maximum 3.1667/s.
  The image rate had p95 and maximum 0.3333/s.
- The error trigger monitor completed 7,199 polls with zero matching errors.
  The existing general error baseline did not change.
- Backend RSS changed by approximately +1.92 MiB over the run, thread count
  remained stable, and the backend process did not restart.

### 5.3 Evidence integrity

- Canonical sanitized artifact:
  `runtime_validation_20260728_131749_sanitized_share.zip`
- Canonical sanitized SHA-256:
  `95585ADFD1AACC5371A52AA95454308EC0192B99D5E83E541525071F79781D97`
- The raw-private archive was independently checked against its 4,715-row
  manifest with zero missing, size-mismatched, or hash-mismatched files.
- The raw-private archive contains sensitive operational paths and network
  details and must not be published or attached to public issues.

## 6. Security and Operations

- No source port, IP, URL, MAC, credential, payload, or absolute path is added to
  product diagnostics or lifecycle warnings.
- No registry, firewall, NIC, switch, SPOT setting, config, database, or CSV
  migration is introduced.
- Fail-closed pool initialization and exhaustion are intentional. They can stop
  SPOT polling instead of silently violating the quarantine invariant.
- Rollback requires the already verified v1.0.16 installer; no data repair or
  schema rollback is needed.
- The actual server remains on the verified candidate. Current evidence does not
  indicate rollback.
- Error-queue deletion, configuration changes, forced image-load tests, and an
  immediate repeat of the 120-minute canary are not required.

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
managed-switch path cannot be fully excluded. One isolated ping timeout out of
7,095 samples and one isolated `/stats` plus one isolated `/api/spot/config`
timeout recovered on the next sample and had no correlated SPOT, NIC, HTTP, or
process failure. They are retained as non-blocking canary concerns.

## 9. Next Action

Freeze this branch and its evidence as
`FIELD_CANARY_PASS / PHYSICAL_PATH_PARTIAL`. Keep the verified candidate running
on the server. No further server action or immediate 120-minute repetition is
required. If governance later requires full physical-path sign-off, collect
managed-switch port counters and logs as a separate operational evidence task;
do not redesign the product solely to close that evidence gap.

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-07-27 | Local PDCA completion report |
| 1.1 | 2026-07-28 | Actual-server 15-minute smoke and 120-minute field canary closure |
