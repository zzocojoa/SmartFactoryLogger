# Implementation Guide: dependency-security-upgrade-nsis

> Date: 2026-07-12 | Design: docs/02-design/features/dependency-security-upgrade-nsis.design.md

---

## Pre-Implementation Checklist

- [x] Plan document reviewed.
- [x] Design document reviewed.
- [x] Repository was clean before PDCA documentation changes.
- [x] Current manifest, lockfile, repo-local venv, build scripts, and package
  configuration were inspected.
- [x] Approved direct dependency targets were identified.
- [x] Backend venv is synchronized with declared dev/build requirements.

## Change Checklist

### 1. Release Metadata and Python Security Floors

- [x] Set root application version to `1.0.12`.
- [x] Set frontend application version to `1.0.12`.
- [x] Set backend runtime metadata version to `1.0.12`.
- [x] Add `CHANGELOG.md` entry for `1.0.12`.
- [x] Set `python-multipart==0.0.32`.
- [x] Set `Pillow==12.3.0`.

### 2. Root Desktop Dependencies

- [x] Run bkit pre-write check for root manifest/lock changes.
- [x] Set Electron to `^41.10.1`.
- [x] Set electron-builder to `^26.15.3`.
- [x] Regenerate root lockfile.
- [x] Verify no unrelated direct dependency changed.

### 3. Frontend Build Dependencies

- [x] Run bkit pre-write check for frontend manifest/lock changes.
- [x] Set Vite to `^7.3.6`.
- [x] Set Vitest to `^3.2.7`.
- [x] Regenerate frontend lockfile.
- [x] Verify Grafana Scenes remains `6.52.0` in the lockfile.

### 4. Environment Synchronization

- [x] Install `backend/requirements-dev.txt` in the repo-local venv.
- [x] Install `backend/requirements-build.txt` in the repo-local venv.
- [x] Run `pip check` and record exact selected versions.
- [x] Run clean root and frontend `npm ci`.

## Verification Checklist

### 5. Static and Automated Tests

- [x] Root direct dependency verification passes.
- [x] Frontend direct dependency verification passes.
- [x] Python direct dependency verification passes.
- [x] Root and frontend security audits are captured.
- [x] `npm run health` passes.
- [x] Frontend production build passes.

### 6. PyInstaller and Portable Packaging

- [x] Run `scripts/deploy.ps1` without bypassing failures.
- [x] Verify `backend/dist/SmartFactoryBackend.exe`.
- [x] Verify portable frontend sidecar and required assets.
- [x] Verify `SmartFactory_v1.0.12_Portable.zip`.
- [x] Record backend EXE and portable ZIP SHA-256.

### 7. NSIS Packaging

- [x] Run `npm run dist`.
- [x] Confirm the successful makensis output contains no warnings; the initial
  `-WX` failure was limited to the known `IsPowerShellAvailable` warning 6000.
- [x] Verify `smart-factory-logger-v2 Setup 1.0.12.exe`.
- [x] Inspect unpacked/ASAR contents.
- [x] Run packaged startup smoke and observe `renderer.dashboard-ready`.
- [x] Record NSIS size, modification time, and SHA-256.

## Hard Gates

- Stop if root or frontend direct dependencies drift beyond the approved set.
- Stop if Grafana Scenes changes from `6.52.0`.
- Stop if the full health suite fails.
- Stop if the PyInstaller backend or frontend sidecar is missing.
- Stop if electron-builder cannot produce the versioned NSIS artifact.
- Do not claim installer validation if only compilation, not startup, was tested.

## Key References

- Plan: `docs/01-plan/features/dependency-security-upgrade-nsis.plan.md`
- Design: `docs/02-design/features/dependency-security-upgrade-nsis.design.md`
- Root build: `package.json`
- Frontend build: `frontend/package.json`, `frontend/vite.config.ts`
- Backend build: `backend/requirements-build.txt`,
  `backend/build_specs/SmartFactoryBackend.spec`
- Packaging: `scripts/deploy.ps1`

## Post-Implementation

- [x] Call `bkit_post_write` for modified source/configuration files.
- [x] Run PDCA gap analysis against the implementation.
- [x] Resolve or explicitly accept gaps until match rate is at least 90%.
- [x] Create completion report with validation and artifact evidence.
