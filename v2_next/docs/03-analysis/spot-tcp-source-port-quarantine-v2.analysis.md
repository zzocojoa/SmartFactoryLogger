# Gap Analysis: spot-tcp-source-port-quarantine-v2

> **Historical local-Check snapshot — superseded.** The package, actual-server
> smoke, 120-minute canary, and final live gate were subsequently completed for
> commit `575e869b63d3052156624886fe0358fb39d6c98a`, which remains the
> authoritative `FIELD_CANARY_PASS / PHYSICAL_PATH_PARTIAL` operating
> baseline. The later adversarial failure-path delta is
> `FIELD_REVALIDATION_REQUIRED` in
> `docs/04-report/spot-tcp-source-port-quarantine-v2.report.md`.
>
> Date: 2026-07-27
> Design: `docs/02-design/features/spot-tcp-source-port-quarantine-v2.design.md`
> Re-check scope: approved Act changes, local regression, and actual Windows socket behavior
> Server package/install/smoke scope: not executed

---

## Match Rate: 100%

The implementation matches all 32 design checkpoints after Act iteration 1.

```text
Match rate = 32 implemented / 32 design checkpoints * 100 = 100%
```

The four Check gaps are closed. Local implementation and Windows socket behavior
are ready for the next separately approved packaging and actual-server Check.
Package generation, server installation, and the 120-minute canary were not
authorized by this Act and remain blocked.

## Act Re-check Result

```text
STATUS: ACT_RECHECK_PASS_LOCAL
LOCAL_MATCH_RATE: 100%
WINDOWS_SOCKET_RUNTIME: PASS
PACKAGE_GENERATION: BLOCKED_PENDING_SEPARATE_APPROVAL
ACTUAL_SERVER_CHECK: BLOCKED_PENDING_SEPARATE_APPROVAL
CANARY_120_MINUTES: BLOCKED
```

## Design-to-Code Matrix

| Category | Implemented | Total | Result |
|---|---:|---:|---|
| Source-port lifecycle and invariant | 8 | 8 | Match |
| Standard HTTP transport and request kinds | 7 | 7 | Match |
| SPOT integration and public error contracts | 5 | 5 | Match |
| Platform and lifecycle fail-closed behavior | 4 | 4 | Match |
| Diagnostics, privacy, and security | 3 | 3 | Match |
| Cancellation, reset, and failure-path validation | 5 | 5 | Match |
| **Total** | **32** | **32** | **100%** |

## Implemented Items

### Source-port lifecycle

- [x] Windows `SO_EXCLUSIVEADDRUSE` guard sockets reserve OS-assigned IPv4 ports.
- [x] The default pool is exactly 768 records and partial initialization fails
  after closing every created guard.
- [x] State transitions are guarded, leased, quarantined, rebind-pending, and
  guarded.
- [x] Every terminal transport path releases a lease into quarantine.
- [x] A port is unavailable at 74.999 seconds and eligible at 75.000 seconds.
- [x] Rebind failure keeps the record unavailable and schedules monotonic retry.
- [x] Pool exhaustion and reuse invariant violations fail closed.
- [x] Bind collision retries use alternate guarded leases and never use an
  OS-selected fallback port.

### Standard HTTP transport

- [x] `http.client.HTTPConnection` and `HTTPSConnection` own HTTP framing.
- [x] The connection constructor receives `source_address=("", lease.port)`.
- [x] URL parsing allows only absolute HTTP(S) URLs without credentials or
  fragments.
- [x] Only GET and PUT are accepted.
- [x] Connect and read timeout values remain explicit.
- [x] A single-worker executor and request lock prevent overlapping SPOT I/O.
- [x] All eight request kinds are present: image, temperature, internal
  temperature, diagnostic, focus read/write, and actuator read/write.

### Integration and compatibility

- [x] Existing `_spot_device_request_lock` and request-budget scheduling remain.
- [x] Image, temperature, internal-temperature, and diagnostic async paths use
  the guarded transport when active.
- [x] Focus and actuator synchronous HTTP calls use the same transport.
- [x] Existing domain error classes and operator-facing mappings remain.
- [x] No database, CSV, config, dependency, endpoint, or frontend migration was
  introduced.

### Lifecycle, observability, and privacy

- [x] Full pool initialization precedes poll scheduling.
- [x] Unsupported exclusive enforcement raises during startup on Windows.
- [x] Non-Windows development reports unsupported enforcement and retains the
  existing test/development fallback.
- [x] Shutdown blocks intake, drains the worker with a bound, closes guards on
  successful drain, and closes the legacy client.
- [x] Aggregate pool, collision, exhaustion, reuse, and request-kind counters are
  exposed additively.
- [x] Response models and diagnostics do not expose source ports, addresses,
  URLs, credentials, or payloads.
- [x] Cancelled worker failures emit one bounded warning containing only the
  allowlisted event code and exception class.
- [x] Both concurrent and asyncio wrapper exceptions are consumed after caller
  cancellation; the final backend run emitted zero unhandled-future warnings.
- [x] No retired `spot_transport.py`, custom SPOT HTTP parser, or prohibited
  source-address fallback is present.

### Reset and failure-path validation

- [x] Internal async test reset drains and clears transport/client state without
  adding a production route.
- [x] Connect and read timeouts map to the public timeout contract and quarantine
  the lease.
- [x] Malformed responses map to protocol errors and quarantine the lease.
- [x] HTTP error status/body and empty successful responses are preserved.
- [x] Cancellation, success, failure, timeout, and bounded shutdown paths assert
  lease and drain state.
- [x] Real loopback tests cover temperature, diagnostic text, PUT body/header,
  and actuator query framing.

## Resolved Act Gaps

### GAP-1 — Windows unsupported startup enforcement

Resolved. `SpotHttpTransport.start()` raises `SpotPortPoolInitError` when
exclusive enforcement is unavailable on Windows. The non-Windows development
fallback remains explicit.

### GAP-2 — Cancelled worker warning and exception collection

Resolved. Cancelled worker failures emit a privacy-safe warning with only
`spot-http-cancelled-worker-failure` and the mapped exception class. Concurrent
and asyncio wrapper futures are both consumed, preventing duplicate traceback
output.

### GAP-3 — Test-only reset helper

Resolved. `_reset_spot_http_transport_state_for_tests()` drains the transport,
closes the legacy client, and clears module state. It is an internal function and
is not reachable through the production API.

### GAP-4 — Direct transport failure-path tests

Resolved. Direct tests now cover timeouts, malformed protocol responses, HTTP
status/body preservation, cancellation, shutdown timeout/recovery, real
loopback request kinds, and lease-state invariants.

## Missing or Changed Items

No design gaps or unapproved deviations remain in the local Act scope.

## Actual Windows Socket Re-check

The re-check used the project virtual environment and production
`SystemGuardSocketFactory`. No actual source-port value was printed or persisted.

| Check | Result |
|---|---|
| Platform is Windows and exclusive guard support is available | PASS |
| Competing bind is blocked while guard is held | PASS |
| Reuse at 74.999 seconds is rejected | PASS |
| Reuse at 75.000 seconds is allowed | PASS |
| Minimum observed reuse interval is 75.0 seconds | PASS |
| Real loopback HTTP request uses a guarded source address | PASS |
| Loopback transport failure and reuse violation counts remain zero | PASS |
| Bounded loopback shutdown drains successfully | PASS |
| Complete 768-record guard pool initializes | PASS |
| Actual port values emitted | PASS (`false`) |

This is a local Windows runtime check, not packaged-PyInstaller or actual-SPOT
evidence.

## Automated Validation

The repository health gate completed with exit code 0:

- Electron startup: 38 tests passed
- frontend typecheck: passed
- frontend lint: passed
- frontend Vitest: 33 files, 250 tests passed
- backend Ruff: passed
- backend mypy: 6 source files passed
- backend unittest: 533 tests passed
- NSIS operational-ready QA self-test: all checks passed

Post-fix focused validation also passed:

- source-port/transport/API pytest: 112 tests and 2 subtests passed
- full backend test re-run: exit code 0
- unhandled asyncio future warnings: 0
- `git diff --check`: passed

The only reported warning is the existing third-party
`pythonjsonlogger.jsonlogger` deprecation warning.

## Engineering Assessment

- Risk remains production-critical because failure of the guard pool intentionally
  prevents SPOT polling rather than silently reverting to unsafe source-port use.
- Compatibility impact is limited to the Windows guarded transport; public API,
  config, CSV, database, and frontend contracts are unchanged.
- The rollback path remains the verified rollback v1.0.16 installer and backend
  identity. No rollback or server operation occurred in this Act.
- Observability is aggregate and privacy bounded. No source ports, addresses,
  internal URLs, credentials, or payloads were added to logs or API responses.
- There is no migration risk because no persistent schema or configuration was
  changed.
- Operational failure modes are explicit: pool initialization failure, pool
  exhaustion, bind retry exhaustion, reuse violation, and shutdown drain timeout.
- Packaged PyInstaller behavior and actual-server SPOT behavior remain unverified
  until the next separately approved Check.

## Next Steps

- [x] Implement GAP-1 through GAP-4.
- [x] Re-run the repository health gate and final backend regression.
- [x] Re-run the actual Windows socket check without exposing port values.
- [ ] Obtain separate approval for clean commit/package identity generation.
- [ ] Perform the actual-server 15-minute smoke only after package verification.
- [ ] Keep the 120-minute canary blocked until the 15-minute promotion gate passes.
