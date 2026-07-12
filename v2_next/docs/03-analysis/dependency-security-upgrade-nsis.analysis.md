# Gap Analysis: dependency-security-upgrade-nsis

> Date: 2026-07-13 | Design: docs/02-design/features/dependency-security-upgrade-nsis.design.md

---

## Match Rate: 100%

The implementation satisfies all 24 evaluated design and release controls.
The dependency set, version invariant, automated checks, PyInstaller packaging,
portable bundle, NSIS generation, artifact integrity, and packaged startup all
match the design. The final release-operations follow-up installed the NSIS on a
supported Windows host, launched the installed application, observed renderer and
backend readiness, closed it through the native window lifecycle, and removed it
without deleting user data.

## Implemented Items

- [x] Root, frontend, backend, and changelog versions agree on `1.0.12`.
- [x] Electron is `41.10.1` and electron-builder is `26.15.3`.
- [x] Vite is `7.3.6` and Vitest is `3.2.7`.
- [x] `python-multipart==0.0.32` and `Pillow==12.3.0` are exact pins.
- [x] Grafana Scenes remains exactly `6.52.0`; unrelated direct dependencies
  remain unchanged.
- [x] Clean root and frontend installs completed; `pip check` reported no broken
  requirements.
- [x] Root audit reports zero vulnerabilities. Frontend audit decreased from 39
  to 37 findings; remaining direct advisory paths are Grafana and React Router,
  which are outside the approved minimal set.
- [x] `npm run health` passed frontend typecheck, lint, 27 files/182 tests and
  backend Ruff, mypy, 471 tests.
- [x] Frontend production build passed with Vite `7.3.6`.
- [x] `scripts/deploy.ps1` produced the frozen backend, verified frontend sidecar,
  portable directory, and portable ZIP from clean commit
  `18cceb270b8860bbcebda3bae1861b80c5bc0f8f`.
- [x] PyInstaller archive contains `backend/build_provenance.json`.
- [x] Frozen backend smoke returned `app_version=1.0.12`,
  `runtime_kind=frozen`, and `frontend_static_ready=true`.
- [x] `npm run dist` produced the versioned NSIS installer and blockmap. The
  successful makensis output contained no warnings.
- [x] ASAR contains `main.js`, `preload.js`, `package.json`, and `tree-kill`, and
  excludes Electron/electron-builder/app-builder runtime packages.
- [x] Unpacked Electron startup reached `renderer.dashboard-ready` with eight
  widgets, served the frontend shell with HTTP 200, and used the frozen backend.
- [x] Current-user NSIS installation completed with exit code 0. The installed
  registry version was `1.0.12`, the PE product version was `1.0.12.0`, and the
  installed backend and ASAR hashes matched the packaged files.
- [x] The installed Electron application reached `renderer.dashboard-ready` with
  eight widgets, reported `app_version=1.0.12`, `runtime_kind=frozen`, and
  `frontend_static_ready=true`, and accepted native `WM_CLOSE`.
- [x] Normal window closure left zero installed application/backend processes and
  released port 8000 without forced termination.
- [x] Current-user NSIS removal completed with exit code 0 and removed the
  registry entry, installation directory, and shortcut while preserving all 65
  files in the existing user-data directory.
- [x] SHA-256, size, and modification time were recorded for all primary
  artifacts.

## Missing Items

- None for the approved current-user Windows release path.

## Changed Items (Deviations from Design)

- [x] The initial electron-builder run failed because `-WX` promoted the known
  `IsPowerShellAvailable` forward-reference warning to an error. The documented
  `nsis.warningsAsErrors=false` setting was used, without modifying
  `node_modules`; the final successful build emitted zero makensis warnings.
- [x] The final lifecycle check used electron-builder's supported silent
  current-user switches (`/S /currentuser`) for deterministic installation and
  removal. The installed application itself ran with a visible native window and
  was closed through `WM_CLOSE`.

## Artifact Evidence

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `backend/dist/SmartFactoryBackend.exe` | 65,415,050 | `C542D685216E4C8DB744427B79931190BCFF6987C427269E55E15B586D510B48` |
| `dist/SmartFactory_v1.0.12_Portable.zip` | 362,893,567 | `DB8F483F21DB7A273EC74AF6EB993F4B40A85710321281563F60736571DD375A` |
| `dist/smart-factory-logger-v2 Setup 1.0.12.exe` | 163,061,248 | `E7444AD46564BF7A9853FA2503323CFC85839E1ACD8C34AF5EF8CB0607C9ED94` |
| `dist/smart-factory-logger-v2 Setup 1.0.12.exe.blockmap` | 171,341 | `8B87AFE668DEADBBC8CC8FC18D5AFC2AFD9DF9B75EBC49B3894BC94B0C72341E` |

## Recommendations

1. Add Authenticode signing before external release; the current installer is
   `NotSigned` and may trigger SmartScreen warnings.
2. Upgrade Grafana packages and React Router only in separate compatibility-led
   work because those changes exceed this minimal security set.
3. If a future release adds per-machine installation, validate its elevation and
   multi-user removal path separately; this release uses the current-user path.

## Next Steps

- [x] Match rate is 100%; release-operations validation is complete.
