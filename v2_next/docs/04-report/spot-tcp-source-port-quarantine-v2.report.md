# Completion Report: SPOT TCP Source-Port Quarantine v2

> Date: 2026-07-29 | Level: Dynamic | Match Rate: 100%
> Status: `FIELD_CANARY_PASS / PHYSICAL_PATH_PARTIAL`
> Evidence scope: packaged source commit `0c641b7e7c7ca7c6090bf7e731d5a3c409091f96`

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
package passed commit-bound operator re-attestation, the full one-command CSV
QA, the approved 15-minute smoke, a 120-minute passive canary, and the final
live gate on the actual server. No new `spot_image` ConnectTimeout, SPOT
handshake failure, HTTP error, pool exhaustion, transport failure, or reuse
violation occurred.

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
| Full backend tests | all | 599 at field commit / 606 at current HEAD | PASS |
| Electron tests | all | 38 | PASS |
| Frontend tests | all | 251 / 33 files | PASS |
| Ruff / mypy | no errors | no errors | PASS |
| Unhandled future warnings | `0` | `0` | PASS |
| NSIS QA self-test | all checks | all checks | PASS |
| Actual source-port values emitted | `false` | `false` | PASS |
| Actual-server canary duration | `120 min` | `7,203.111s` | PASS |
| New `spot_image` ConnectTimeout | `0` | `0` | PASS |
| SPOT handshakes / HTTP bodies | all | `22,297 / 22,297` | PASS |
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
  `0c641b7e7c7ca7c6090bf7e731d5a3c409091f96`
- Product version: `1.0.17`
- Candidate installer SHA-256:
  `67E645701ABFAD1D7A6AD97D527350220887788F03CBC3FEE6648DB34E5EB098`
- Installed backend SHA-256:
  `2F164C24D8111658F108C0C3015DA6A0B90177A13B5F12AC352D505B6AAD7C4F`
- Attested config SHA-256:
  `24E74BE7B85BCA61974B69775072C2A14269DF93BE6E7EE7B743F39ED666AFAF`
- The one-command SPOT Temperature v2.5 QA passed all runtime, attestation,
  finalized CSV, fact-manifest, and repository-validator checks. Its evidence
  SHA-256 is
  `D30BC85F03A7F500CBC396AB8FA13DD2FE22CC8B19BAF0D00920894317E60C83`.
- Attestation remained verified, operator-verified, fingerprint-matched, and
  free of configuration drift.
- `spot-source-port-quarantine-v2`, the 768-record pool, 75-second quarantine,
  `spot-background-request-budget-v2`, and `spot-image-demand-shaping-v2`
  remained active.
- The post-canary live gate at 2026-07-29 17:49:01 KST reconfirmed the exact
  backend and config hashes, source commit, HTTP 200 health, one backend
  process, four Electron processes, verified attestation, no drift, an active
  source-port policy, and zero reuse, exhaustion, or transport failures.

### 5.2 120-minute passive canary

The actual-server run `runtime_validation_20260729_150107` observed normal-screen
operation from 2026-07-29 15:01:30 through 17:01:33 KST. It stopped at the fixed
deadline without a trigger.

- All 22,297 captured SPOT HTTP events completed their TCP handshake, HTTP
  header, and response body.
- HTTP non-200, 5xx, retransmitted SYN, RST-before-response, unresolved flow,
  and no-response counts were all zero.
- The packet-derived same 4-tuple reuse minimum was 74.009593 seconds, with zero
  events under 60 seconds. The application-monotonic minimum remained exactly
  75.0 seconds and the reuse-violation counter remained zero. The small
  packet/application boundary difference reflects scheduling between the
  internal connect-start marker and the on-wire SYN; it does not violate either
  formal field gate.
- During the canary, the pool recorded 931 handled bind collisions and 166
  handled rebind retries. All 22,192 new transports succeeded. The final live
  gate later observed cumulative totals of 1,518 collisions and 228 retries.
  Acquire waits, pool exhaustion, reuse violations, and transport failures
  remained zero, demonstrating bounded recovery rather than fallback.
- The fixed 60-second total-open rate had p95 3.1333/s and maximum 3.1667/s.
  The image rate had p95 and maximum 0.3333/s.
- The error trigger monitor completed 7,198 polls with zero matching errors.
  One isolated monitor request error recovered on the next poll; its maximum
  gap was 2.006 seconds, below the 5-second detection warning. The existing
  general error baseline did not change.
- All 7,098 ping probes succeeded. Server NIC receive/transmit errors and
  discards remained zero.
- Backend private memory changed from approximately 293.6 MiB to 443.8 MiB
  during warm-up and then remained flat for the final 30 minutes. The backend
  PID and listening port were unchanged from the start through the end.
- Packet evidence retained traffic from before observation start until more
  than five seconds after observation end. The
  `capture-suffix-incomplete` label applies only to the capture shutdown tail,
  not to the 120-minute observation window.

### 5.3 Evidence integrity

- Canonical sanitized artifact:
  `runtime_validation_20260729_150107_sanitized_share.zip`
- Canonical sanitized SHA-256:
  `F10DEE822A4C9BDEBE3A4A2B1E861D1CCF1D4B2EAEF7D1CAA6E47A962040F69F`
- The raw-private archive was independently checked against its 4,308-row
  manifest with zero missing, size-mismatched, or hash-mismatched files.
- The server-original raw archive SHA-256 is
  `22BA5FEA850200AD663890FC9D49A06ECEB670B794E249C74FD626BFB4B15C0C`.
  A transferred, recompressed copy had a different outer ZIP hash, but all
  4,308 manifest-bound file hashes matched the canonical sanitized evidence.
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
- The actual server remains on the verified `1.0.17` package built from
  `0c641b7`. Current evidence does not indicate rollback.
- Error-queue deletion, configuration changes, forced image-load tests, and an
  additional 15-minute or 120-minute collection are not required.

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
managed-switch path cannot be fully excluded. Three isolated normal collector
API failures and one isolated dedicated trigger-monitor request error recovered
without a correlated SPOT, NIC, HTTP, or process failure.

At 16:43:35 KST, SPOT began returning the HTTP 200 under-range sentinel
`6553.4`. The application correctly rejected it as an invalid temperature
instead of presenting cached data as current. This is a separate device or
process condition, not a TCP connection failure; the final live gate no longer
reported a device-status code.

## 9. Next Action

Keep the verified `1.0.17` package from commit `0c641b7` running on
`DESKTOP-CIIT7LK`. Do not rollback, clear the error queue, change SPOT settings,
or repeat the 15-minute or 120-minute collection based on the current evidence.
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
