# Completion Report: SPOT TCP Source-Port Quarantine v2

> Date: 2026-07-31 | Level: Dynamic | Match Rate: 100%
> Validated package: `FIELD_CANARY_PASS / PHYSICAL_PATH_PARTIAL`
> Validated runtime source: `575e869b63d3052156624886fe0358fb39d6c98a`
> Current PR HEAD: `FIELD_REVALIDATION_REQUIRED`
> Closure: `575E869_DONE_WITH_CONCERNS / CURRENT_HEAD_OPEN`
> Post-validation delta: CSV durability, QA identity, Electron response, and health hot paths

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
package from commit `575e869` passed commit-bound operator re-attestation, the
full one-command CSV QA, the approved 15-minute smoke, a 120-minute passive
canary, and the final live gate on the actual server. No new `spot_image`
ConnectTimeout, SPOT handshake failure, HTTP error, pool exhaustion, transport
failure, or reuse violation occurred.

Managed-switch evidence was unavailable, so the software promotion gate passes
for the exact `575e869` package while physical-path attribution remains partial.
This limitation does not require rollback of the server. The package includes
the observation-fact post-append durability fix from commit `70b9339`.

A final adversarial review found three additional failure paths after the
`575e869` canary: v2 persistence validation occurred after the durable write,
the QA helper did not compare the shutdown CSV basename with the expected
current-session basename, and Electron did not settle a connection-test request
when a backend HTTP response ended prematurely. The same review found that each
health request rescanned the active observation spool and every quarantined
archive. The current PR fixes those paths with direct regression coverage and
a mutation-aware pending-count cache. Because the changes affect runtime code
and the QA bundle, they cannot inherit the `575e869` field evidence.
The extracted Electron connection-test client is also explicitly included in
the packaging allowlist so the next installer cannot omit a startup dependency.

```text
Implementation completion rate: 100%
Design checkpoints: 32 / 32
Blocking local gaps: 0
Blocking promotion gaps: 6
Act iterations: 1
Field result: FIELD_CANARY_PASS
Physical-path result: PHYSICAL_PATH_PARTIAL
Current PR HEAD: FIELD_REVALIDATION_REQUIRED
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

Local-suite rows below apply to the post-validation current HEAD. Field and
transport rows apply only to the packaged `575e869` baseline.

| Metric | Target | Final | Status |
|---|---:|---:|---|
| Design match rate | `>=90%` | `100%` | PASS |
| Source-port quarantine | `>=75.0s` | `75.0s` | PASS |
| Guard pool capacity | `768` | `768` | PASS |
| Reuse at 74.999 seconds | blocked | blocked | PASS |
| Reuse at 75.000 seconds | allowed | allowed | PASS |
| Focused backend tests | all | 112 tests + 2 subtests | PASS |
| Current HEAD full backend tests | all | 641 | PASS |
| Current HEAD Electron tests | all | 45 | PASS |
| Current HEAD frontend tests | all | 253 / 34 files | PASS |
| Ruff / mypy | no errors | no errors | PASS |
| Unhandled future warnings | `0` | `0` | PASS |
| NSIS QA self-test | all checks | all checks | PASS |
| Actual source-port values emitted | `false` | `false` | PASS |
| Actual-server canary duration | `120 min` | `7,202.847s` | PASS |
| New `spot_image` ConnectTimeout | `0` | `0` | PASS |
| SPOT handshakes / HTTP bodies | all | `22,321 / 22,321` | PASS |
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
  `575e869b63d3052156624886fe0358fb39d6c98a`
- Product version: `1.0.17`
- Candidate installer SHA-256:
  `23F455A7C4D2D021BE5864D78496285A5C289880BC00048CD4E072CC9BA9E016`
- Installed backend SHA-256:
  `294C228EF4B8D99730F14A40C1EB438695611FA816BDF6B1E17270DA3CD3FB0D`
- Attested config SHA-256:
  `36F86150C50BDAD4449AB09DFAD528313326119DC0AE61CDE59DEFDFF7BB3EDE`
- The one-command SPOT Temperature v2.5 QA passed all runtime, attestation,
  finalized CSV, fact-manifest, and repository-validator checks. Its evidence
  SHA-256 is
  `613A9D69AE82CF3C4496E7AFD777EF64E3E967E5052CA1784D53C42C8E2CCEE1`.
- Attestation remained verified, operator-verified, fingerprint-matched, and
  free of configuration drift.
- `spot-source-port-quarantine-v2`, the 768-record pool, 75-second quarantine,
  `spot-background-request-budget-v2`, and `spot-image-demand-shaping-v2`
  remained active.
- The post-canary live gate at 2026-07-31 15:18:48 KST reconfirmed the exact
  backend and config hashes, source commit, HTTP 200 health, one backend
  process, four Electron processes, verified attestation, no drift, an active
  source-port policy, and zero reuse, exhaustion, or transport failures.

### 5.2 15-minute passive smoke

The actual-server run `runtime_validation_20260731_092800` observed normal-screen
operation for `903.055s` and stopped at the fixed deadline without a trigger.
Bidirectional packet preflight passed with 129 outbound and 148 inbound
packets. All 2,816 SPOT HTTP events completed their TCP handshake, header, and
body; failed connections, retransmitted SYNs, reset-before-response events, and
same 4-tuple reuse under 60 seconds were zero. All 895 ping probes succeeded.

The dedicated trigger monitor completed 900 polls with zero monitor errors, a
maximum poll gap of `1,071.953ms`, and no error-queue change. The smoke remained
`PHYSICAL_PATH_PARTIAL` because managed-switch evidence was unavailable.

### 5.3 120-minute passive canary

The actual-server run `runtime_validation_20260731_104647` observed normal-screen
operation for `7,202.847s` and stopped at the fixed deadline without a trigger.

- Bidirectional packet preflight passed with 115 outbound and 138 inbound
  packets before the full capture.
- All 22,321 captured SPOT HTTP events completed their TCP handshake, HTTP
  header, and response body. All responses used the device's expected
  `HTTP/1.0` framing.
- HTTP non-200, 5xx, retransmitted SYN, RST-before-response, unresolved flow,
  and no-response counts were all zero.
- Packet-derived same 4-tuple reuse under 60 seconds was zero. The
  application-monotonic minimum remained exactly 75.0 seconds and the
  reuse-violation counter remained zero.
- The fixed 60-second total-open rate had p95 `3.1333/s`; the image rate had
  p95 `0.3333/s`.
- The dedicated error trigger monitor completed 7,197 polls with zero polling
  errors. The maximum poll gap was `2,230.561ms`, below the
  5-second detection warning threshold; the full error snapshots did not
  change and no new `spot_image` ConnectTimeout occurred.
- All 7,101 ping probes succeeded. Server NIC receive/transmit errors and
  discards remained zero.
- The final live gate reported cumulative handled totals of 2,869 bind
  collisions and 247 rebind retries. Pool exhaustion, reuse violations, and
  transport failures remained zero, demonstrating bounded recovery rather
  than fallback.
- Image status remained `ok`, accepted requests, and recorded zero refresh
  failures.

### 5.4 Evidence integrity

- Canonical sanitized artifact:
  `runtime_validation_20260731_104647_sanitized_share.zip`
- Canonical sanitized SHA-256:
  `3393C32C8C248704448E10DD5BC38A49012E8FA07B89362CFE7306B70BFA6350`
- Transferred full run archive:
  `runtime_validation_20260731_104647.zip`
- Transferred full run archive SHA-256:
  `295F7C278B71174DF2FDAB247C489BD7BEA21F29733B7172BC91011AC1F24BC1`
- Final live-gate evidence:
  `server_check_after_575e869_120min_canary_final_20260731_151848.json`
- Final live-gate evidence SHA-256:
  `68F784B611DA7334356B039BF5B794761F3B8C27C6A9F4A401BD3D2FD83356D5`
- The corrected final read-only helper has SHA-256
  `C0AE075633A9FD48E437A8605124A0067CB445709B1CBFE8A5CD5C0A3672277B`.
- The transferred 15-minute run archive
  `runtime_validation_20260731_092800.zip` has SHA-256
  `B17B0EA762753D380994D90E987073F208683FE1967EE1C7FA760188960C03AE`;
  its canonical sanitized artifact has SHA-256
  `7623781C82FFAE1935ADE77AC0A0A198B193581E09AD0196C7BC0840231E44E1`.
- The raw-private archive contains sensitive operational paths and network
  details and must not be published or attached to public issues.

### 5.5 Validation expression normalization

An earlier wrapper read `build_git_commit` from the `/api/spot/config` root even
though the commit is exposed under `image.build_git_commit`. The first final
gate therefore stopped with `PropertyNotFoundStrict` after its live sample
passed. The corrected helper reads the documented nested field and was
SHA-256-verified before execution. The canonical final evidence records all
39 checks as `true`, including `SpotConfigCommitMatch` and
`DriftFieldsClear`; no manually printed pass line or post-hoc value coercion is
used for the final promotion decision.

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
  `575e869`. Current evidence does not indicate rollback.
- The final package, backend, config, attestation, QA, canary, and live-gate
  identities are bound to the same `575e869` source commit.
- Error-queue deletion, configuration changes, and forced image-load tests are
  not required for the running package.
- Commit `70b9339`, included in the validated package, preserves
  observation-fact deduplication when the row append
  succeeds but the immediate file-size probe fails. Its manifest still fails
  closed, and a regression test proves the durable row is neither spooled nor
  duplicated.
- The current PR validates v2 batch persistence metadata before `writerows`,
  binds QA to the exact shutdown CSV basename, and handles backend response
  `aborted`, `error`, and premature `close` events with a single-settlement
  Electron client. These changes require a new package and field validation.
- Observation spool/archive pending rows are scanned once per writer lifecycle
  and then tracked on spool append and drain, removing archive-size-dependent
  filesystem work from the recurring health path.
- The first pending-count call still scans existing schema-mismatch archives,
  and the in-memory set used for poll-sequence gap diagnostics grows for the
  process lifetime. These are non-blocking long-run follow-ups; recurring
  health requests no longer rescan the archives.

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

The earlier PowerShell property-path defect in Section 5.5 was a non-product
reporting defect. The corrected `575e869` wrapper passed before the final
promotion decision.

## 9. Next Action

Keep the verified `1.0.17` package from commit `575e869` running on
the verified target server. Do not rollback, clear the error queue, or change
SPOT settings based on the current evidence. Build the current PR HEAD only
after local and CI gates pass, then repeat commit-bound re-attestation, QA,
15-minute smoke, 120-minute canary, and final live-gate verification for that
new package.
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
| 2.3 | 2026-07-31 | Froze identity-matched `575e869` re-attestation, QA, smoke, 120-minute canary, corrected 39-check final gate, and production operating decision |
| 2.4 | 2026-07-31 | Preserved `575e869` as the operating baseline and reopened current-HEAD promotion for adversarial CSV, QA identity, Electron partial-response, and health hot-path fixes |
