# Completion Report: spot-image-auto-recovery

> Date: 2026-07-14 | Level: Dynamic

---

## 1. Summary

### 1.1 Feature Overview

SPOT camera display failures now recover automatically when the failure is
transient. The existing manual **Retry** action remains available as an immediate
operator override and as the final recovery path after the bounded automatic
retry budget is exhausted.

The normal completion-driven image loop is unchanged. The application still uses
the backend `/api/spot/image.jpg` route backed by the documented SPOT
`/image.jpg` endpoint, and no fixed 35 ms, 100 ms, or 150 ms polling timer was
introduced.

### 1.2 Final Match Rate

100% (Target: 90%, PDCA iteration 2)

## 2. Completed Items

- [x] Retry transient request, timeout, HTTP, empty-body, and browser display
  failures after 500 ms, 1,000 ms, and 2,000 ms.
- [x] Stop automatically after three retry attempts and preserve the visible
  manual Retry action.
- [x] Treat configuration and image payload rejection failures as terminal.
- [x] Make manual Retry cancel a pending timer, reset the budget, and request
  immediately.
- [x] Cancel pending recovery work on unmount and image-route change.
- [x] Deduplicate retry scheduling when more than one image consumer reports the
  same display failure.
- [x] Separate focus and actuator errors from `spotImageError`.
- [x] Keep Dashboard and Settings > SPOT Camera on the same shared image state and
  recovery policy.
- [x] Publish frontend recovery counters and state without changing backend,
  device, CSV, or metadata schemas.
- [x] Build a clean-provenance PyInstaller backend and versioned NSIS installer.

## 3. Engineering Assessment

- Risk: medium. This changes production camera recovery behavior but keeps the
  successful frame loop and backend/device request contract unchanged.
- Compatibility: no API, CSV, configuration, migration, or stored-data change.
- Security: no credentials, new external endpoint, or dynamic executable input
  was added. The added-line sensitive-value scan returned zero hits.
- Observability: frontend diagnostics now expose total automatic retries,
  consecutive attempt, pending/exhausted state, scheduled time, and whether the
  last failure was retryable.
- Operational failure mode: persistent failures or four consecutive failed
  requests (initial request plus three automatic attempts) leave the last frame
  or error state visible and require manual Retry.
- Rollback: revert implementation commit
  `b239df20cf959f99a5c573ea47dd0fc8e866ae31` and redeploy the preceding verified
  installer. No migration rollback is required.

## 4. Validation

| Check | Result |
|---|---|
| Recovery policy + integration tests | Pass / 27 tests |
| Frontend typecheck and ESLint | Pass |
| Full frontend tests | Pass / 28 files, 206 tests |
| Backend Ruff and mypy | Pass |
| Full backend tests | Pass / 475 tests |
| `npm run health` | Pass |
| `git diff --check` | Pass |
| Added-line sensitive scan | Pass / 1,298 lines, 0 hits |
| Frontend production build | Pass / Vite 7.3.6, 4,529 modules |
| PyInstaller provenance | Pass / start and post-build commit matched |
| electron-builder NSIS | Pass / exit 0 |
| Packaged backend integrity | Pass / source and packaged SHA-256 matched |
| Packaged frontend integrity | Pass / 49 files, 0 mismatches |
| Executable naming | Pass / `smart-factory.exe`; legacy name absent |

The production build emitted the existing Vite large-chunk warning and the
existing PyInstaller `tzdata` hidden-import warning. Both builds completed. The
NSIS build did not emit a makensis warning.

## 5. Build Artifacts

Build provenance commit:
`b239df20cf959f99a5c573ea47dd0fc8e866ae31`

| Artifact | Modified (KST) | Bytes | SHA-256 |
|---|---|---:|---|
| `backend/dist/SmartFactoryBackend.exe` | 2026-07-14 00:40 | 65,503,810 | `8465FFEC1BDE530EEF237F1D742294AA8FD7EC3DCC15507CE0BF7EE5BEC0EABB` |
| `dist/smart-factory-logger-v2 Setup 1.0.13.exe` | 2026-07-14 00:41:03 | 163,218,425 | `66548E83FCBA37E6DA149D0966D8E6E63139D9F53D14FE9D11463AF7D49ED18B` |
| `dist/smart-factory-logger-v2 Setup 1.0.13.exe.blockmap` | 2026-07-14 00:41 | 171,347 | `5CB7302FB6DE0DDD2F1C6F3027AF1C1EE5B199CDDE0D1539B2D75E67567DF3C3` |

The installer is not Authenticode-signed. Windows reputation or publisher
warnings therefore remain possible.

## 6. Metrics

| Metric | Value |
|---|---|
| Implementation commit files | 16 |
| Implementation diff | +1,298 / -139 |
| New automatic retry timers in successful flow | 0 |
| Automatic retry budget | 3 |
| PDCA match rate | 100% |
| PDCA iterations | 2 |

## 7. Deviations and Test Gaps

- No server-computer or physical-device validation was run from the development
  computer. The generated installer still requires the established 60-second
  preflight and at least 15 minutes of SPOT image, Temperature, diagnostics, CSV,
  and observability monitoring on the server computer.
- Automatic retry progress is available in diagnostics, while the existing error
  and Retry UI remains intentionally stable to avoid a broader camera-widget
  redesign.
- This feature does not alter SPOT request serialization; it relies on the
  existing backend serialization implemented and previously device-validated.

## 8. Learnings

1. A manual Retry action is useful as a fallback, but transient recovery should
   not require operator attention.
2. Recovery delays belong only on failure paths; changing the successful image
   cadence would mix reliability policy with device throughput policy.
3. Image acquisition errors and camera-control errors require separate state so
   a focus or actuator failure cannot stop image recovery.

## 9. Next Action

Copy the installer to the server computer, verify its SHA-256, and run the
physical-device preflight plus 15-minute monitoring gate before deployment
approval.
