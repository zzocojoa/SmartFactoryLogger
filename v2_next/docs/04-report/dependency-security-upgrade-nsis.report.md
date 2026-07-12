# Completion Report: dependency-security-upgrade-nsis

> Date: 2026-07-13 | Level: Dynamic

---

## 1. Summary

### 1.1 Feature Overview

SmartFactoryLogger was advanced to `1.0.12` with the approved minimal dependency
set: Electron `41.10.1`, electron-builder `26.15.3`, Vite `7.3.6`, Vitest
`3.2.7`, python-multipart `0.0.32`, and Pillow `12.3.0`. Root and frontend npm
locks were regenerated, Python security inputs were pinned exactly, and no
behavior-bearing application logic or persistent data contract changed.

The complete local release workflow succeeded from clean build provenance commit
`18cceb270b8860bbcebda3bae1861b80c5bc0f8f`: frontend build, PyInstaller backend,
portable bundle/ZIP, electron-builder unpacked application, and NSIS installer.

### 1.2 Final Match Rate

100% (24 of 24 controls; target: 90%)

## 2. Completed Items

- [x] Verified repository versions before choosing upgrade targets.
- [x] Applied only the six approved direct dependency upgrades.
- [x] Preserved Grafana Scenes `6.52.0`, Grafana `12.3.1`, React Router `6.30.3`,
  root Playwright `1.60.0`, and Python Playwright `1.58.0`.
- [x] Synchronized root/frontend npm installs and the repo-local Python venv.
- [x] Passed the full health suite and frontend production build.
- [x] Produced and integrity-checked the frozen backend and portable ZIP.
- [x] Produced and integrity-checked `smart-factory-logger-v2 Setup 1.0.12.exe`.
- [x] Verified frozen backend health, frontend sidecar readiness, Electron
  renderer dashboard readiness, ASAR contents, and scoped process cleanup.
- [x] Installed the NSIS in the current-user scope, launched the installed app,
  observed the dashboard and frozen backend, closed it through native
  `WM_CLOSE`, and removed the installation.
- [x] Verified removal of the installation directory, uninstall registry entry,
  and shortcut while preserving the existing user-data directory.
- [x] Recorded remaining audit findings and operational release risks.

## 3. Engineering Assessment

### 3.1 Risk and Compatibility

- Overall change risk: medium. Electron crosses eight major versions, but the
  application uses a small stable API surface and both packaged and installed
  startup/normal-shutdown checks passed.
- Migration risk: none for database, CSV schema, settings, or HTTP API. Lockfiles
  must be rolled back together with manifests.
- Security impact: root npm audit is clean and the selected Python parsers/codecs
  are pinned. Frontend still reports 37 findings in Grafana/React Router paths.
- Observability: existing `/health`, Electron startup events, PyInstaller build
  provenance, and artifact hashes were used; no telemetry schema changed.
- Failure mode: unsigned installer reputation warnings, a future Electron runtime
  regression outside the tested dashboard path, or Grafana advisory exposure.

### 3.2 Rollback

Redeploy the last verified `1.0.11` installer and revert the two implementation
commits together. No data migration reversal is required. Do not reuse a mixed
manifest/lockfile state.

## 4. Validation

| Check | Result |
|---|---|
| Root `npm ci` / audit | Pass / 0 vulnerabilities |
| Frontend `npm ci` / audit | Pass / 37 remaining (1 low, 17 moderate, 18 high, 1 critical) |
| Python `pip check` | Pass / no broken requirements |
| Frontend typecheck, lint, tests | Pass / 27 files, 182 tests |
| Backend Ruff, mypy, tests | Pass / 471 tests |
| Frontend production build | Pass / Vite 7.3.6, 4,520 modules |
| PyInstaller + portable deploy | Pass |
| Frozen backend smoke | Pass / v1.0.12, frozen, frontend ready |
| electron-builder NSIS | Pass / final makensis warnings: 0 |
| Electron unpacked smoke | Pass / HTTP 200 and `renderer.dashboard-ready` |
| ASAR minimum runtime check | Pass / build-only packages excluded |
| NSIS current-user install | Pass / exit 0, registry `1.0.12`, PE `1.0.12.0` |
| Installed file integrity | Pass / backend and ASAR hashes match package |
| Installed application lifecycle | Pass / frozen backend, 8 widgets, native `WM_CLOSE` |
| Normal shutdown cleanup | Pass / 0 processes, port 8000 released |
| NSIS current-user removal | Pass / exit 0, registry/directory/shortcut removed |
| User-data preservation | Pass / directory retained, 65 of 65 files retained |
| Authenticode | Not signed |

The PyInstaller build emitted an existing `tzdata` hidden-import warning but
completed successfully. Runtime smoke passed. This remains a packaging warning to
watch if timezone behavior is expanded.

## 5. Artifacts

| Artifact | Modified (KST) | Bytes | SHA-256 |
|---|---|---:|---|
| `backend/dist/SmartFactoryBackend.exe` | 2026-07-12 02:27:59 | 65,415,050 | `C542D685216E4C8DB744427B79931190BCFF6987C427269E55E15B586D510B48` |
| `dist/SmartFactory_v1.0.12_Portable.zip` | 2026-07-12 02:28:47 | 362,893,567 | `DB8F483F21DB7A273EC74AF6EB993F4B40A85710321281563F60736571DD375A` |
| `dist/smart-factory-logger-v2 Setup 1.0.12.exe` | 2026-07-12 02:29:32 | 163,061,248 | `E7444AD46564BF7A9853FA2503323CFC85839E1ACD8C34AF5EF8CB0607C9ED94` |
| `dist/smart-factory-logger-v2 Setup 1.0.12.exe.blockmap` | 2026-07-12 02:29:37 | 171,341 | `8B87AFE668DEADBBC8CC8FC18D5AFC2AFD9DF9B75EBC49B3894BC94B0C72341E` |

## 6. Metrics

| Metric | Value |
|---|---|
| Behavior-bearing application LoC | 0 |
| Tracked files touched | 13, including generated lockfiles and PDCA documents |
| PDCA analysis iterations | 3 |
| Installed lifecycle validation | 2026-07-13 08:00-08:01 KST |
| Build provenance commit | `18cceb270b8860bbcebda3bae1861b80c5bc0f8f` |

## 7. Deviations and Test Gaps

- electron-builder required `nsis.warningsAsErrors=false` for its bundled NSIS
  template forward reference. The final build emitted zero warnings.
- The supported current-user install/remove path was exercised. Per-machine
  elevation was not exercised because it is not configured for this release.
- No dedicated timezone scenario was added for the existing PyInstaller
  `tzdata` warning.

## 8. Learnings

1. electron-builder upgrades must be validated against the bundled NSIS template,
   not just npm audit resolution.
2. Clean Git provenance is a real release input for this repository; dependency
   and packaging configuration must be committed before PyInstaller runs.
3. Unpacked smoke remains useful for fast diagnosis, while installed lifecycle
   validation proves native window shutdown and NSIS cleanup behavior.

## 9. Follow-up Items

- [ ] Sign the installer with the production Authenticode certificate.
- [ ] Handle Grafana and React Router advisories in separate compatibility-led
  work rather than expanding this upgrade set.
- [ ] Validate elevation only if a future release adds per-machine installation.
