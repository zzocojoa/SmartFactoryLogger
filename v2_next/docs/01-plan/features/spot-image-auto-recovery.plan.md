# spot-image-auto-recovery - Plan Document

> Version: 1.0.0 | Date: 2026-07-14 | Status: Approved
> Level: Dynamic

---

## 1. Overview

### 1.1 Purpose

Keep the AMETEK LAND SPOT+ completion-driven `GET /image.jpg` contract while
making transient camera failures recover without requiring an operator click.
The existing Retry action remains available as a manual recovery fallback.

### 1.2 Background

The current frontend stops its image acquisition loop after any HTTP, network,
payload, or browser display failure. A single transient failure can therefore
leave the camera stopped until an operator notices and selects Retry. The same
`spotImageError` state is also used for focus and actuator failures, so the
camera Retry action can appear even when image acquisition is healthy.

## 2. Goals

### 2.1 Primary Goals

- [ ] Automatically retry bounded transient image transport/display failures.
- [ ] Keep normal successful frame acquisition completion-driven with no frame
      interval timer.
- [ ] Stop automatic retries for persistent configuration or invalid-payload
      failures and preserve an explicit Retry action.
- [ ] Remove focus and actuator failures from `spotImageError`.
- [ ] Keep Dashboard and Settings on the same image lifecycle and recovery
      state.
- [ ] Preserve retry attempts and terminal errors in frontend diagnostics.
- [ ] Produce a clean-commit PyInstaller backend and NSIS installer.

### 2.2 Non-Goals

- Do not change the SPOT device resource from `/image.jpg`.
- Do not restore `/image.ssi`, `/newjpeg.jpg`, live/proxy routes, stale-frame
  substitution, or a fixed camera polling interval.
- Do not change temperature, diagnostics, focus, actuator, CSV, or evidence
  schemas.
- Do not hide persistent failures or report stale frames as current.

## 3. Scope

### 3.1 In Scope

- Frontend image failure classification and bounded retry scheduling.
- Retry timer cancellation on success, manual retry, config change, and
  unmount.
- Focus/actuator error isolation from image state.
- Dashboard and Settings retry presentation behavior.
- Focused regression tests, full repository health, PDCA records, PyInstaller,
  and NSIS packaging.

### 3.2 Out of Scope

- Backend SPOT URL resolution and device-wide request serialization.
- Device firmware behavior and the SPOT `/image.ssi` HTML page.
- Server-computer physical-device observation, which requires installing the
  resulting NSIS on the server computer after this development-PC build.

## 4. Functional Requirements

- **FR-01:** A successful displayed frame requests the next frame exactly once.
- **FR-02:** Transient failures (`upstream-timeout`, connection/request errors,
  retryable HTTP status, unexpected bridge/network failure, or browser decode
  failure) schedule a bounded automatic retry.
- **FR-03:** Configuration absence and rejected/invalid image payloads do not
  automatically retry.
- **FR-04:** Consecutive automatic retries use a bounded delay and stop after a
  finite attempt limit.
- **FR-05:** Manual Retry cancels any pending retry, resets the consecutive
  retry budget, and requests immediately.
- **FR-06:** A validated and displayed frame clears the error and retry budget.
- **FR-07:** Focus and actuator failures never set `spotImageError` and never
  expose the camera Retry action.
- **FR-08:** Unmount and image URL/config changes cancel pending timers so no
  stale request can run.

## 5. Non-Functional Requirements

- Only one image request may be in flight.
- Normal successful acquisition adds no fixed delay and remains aligned with
  the manufacturer completion-driven example.
- Retry delays must be constants with deterministic tests; no unbounded tight
  loop is permitted.
- Existing last-valid image may remain visible but must retain an explicit
  error overlay until recovery succeeds.
- No backend, CSV, migration, credential, or security-boundary change.

## 6. Success Criteria

- [ ] Transient failure followed by success recovers without operator action.
- [ ] Persistent payload/config failure makes no automatic follow-up request.
- [ ] Automatic retries stop at the configured maximum.
- [ ] Manual Retry remains usable after automatic retry exhaustion.
- [ ] Focus/actuator failures do not change shared image error state.
- [ ] Dual Dashboard/Settings consumers cannot schedule duplicate retries.
- [ ] Focused tests, frontend typecheck/lint/tests, full `npm run health`,
      `git diff --check`, and sensitive-value scan pass.
- [ ] Clean Git commit is embedded in the PyInstaller backend provenance.
- [ ] NSIS output exists, has a recorded SHA-256, and contains the freshly
      built backend/frontend resources.

## 7. Schedule

| Phase | Target Date | Status |
|-------|------------|--------|
| Plan | 2026-07-14 | Complete |
| Design | 2026-07-14 | In Progress |
| Implementation | 2026-07-14 | Pending |
| Check / Act | 2026-07-14 | Pending |
| Report / NSIS | 2026-07-14 | Pending |

## 8. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Retry loop overloads the device | High | Low | Finite retry budget, bounded delays, existing single-flight and device lock. |
| Duplicate UI consumers schedule retries | Medium | Medium | Retry ownership remains inside singleton `useSpotViewModel`; completion identity guard remains. |
| Persistent invalid payload is hammered | High | Low | Classify payload/config failures as non-retryable. |
| Timer fires after config change/unmount | Medium | Medium | Generation guard plus explicit timer cleanup. |
| Control error becomes invisible | Medium | Low | Keep control rejection observable through its own operation result/console path; do not mislabel it as image failure. |
| Package provenance does not match source | High | Low | Commit first, require clean worktree, then run the repository packaging script. |

## 9. Operations

- **Observability:** retain image error count/status and add automatic retry
  scheduling/exhaustion diagnostics without masking backend errors.
- **Failure mode:** transient failures recover automatically; persistent or
  exhausted failures keep the last frame plus error and manual Retry.
- **Rollback:** revert the feature commit and rebuild PyInstaller/NSIS. No
  migration or configuration rollback is required.
- **Server validation gap:** development-PC packaging cannot prove physical
  device behavior; the generated installer requires the established 15-minute
  server validation after installation.

## 10. References

- `docs/reference/ametek_land_spot.pdf`, sections 2.3 and 5.3.
- `docs/02-design/features/spot-camera-rest-api-conformance.design.md`.
- `docs/04-report/spot-camera-rest-api-conformance.server-validation.md`.
