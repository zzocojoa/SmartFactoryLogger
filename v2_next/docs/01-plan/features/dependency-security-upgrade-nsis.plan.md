# Dependency Security Upgrade and NSIS Plan

> Version: 1.0.0 | Date: 2026-07-12 | Status: Approved for implementation
> Level: Dynamic

---

## 1. Overview

### 1.1 Purpose

Remove the smallest actionable set of known dependency vulnerabilities, restore
reproducible Python security floors, upgrade the unsupported Electron runtime and
vulnerable installer toolchain, and produce a newly versioned Windows NSIS
installer from the verified source tree.

### 1.2 Background

The repository audit confirmed exact npm lock versions and the versions installed
in the repository-local Python virtual environment. Direct low-change fixes exist
for Vite, Vitest, Pillow, and python-multipart. Electron 33 is outside the current
three-major support window, while electron-builder 24 is on a vulnerable build
dependency path. The Python runtime requirements are mostly unpinned, so the two
security-sensitive packages in this change must also become explicit build inputs.

## 2. Goals

### 2.1 Primary Goals

- [ ] Upgrade Vite `7.3.3` to `7.3.6` and Vitest `3.2.4` to `3.2.7`.
- [ ] Pin python-multipart `0.0.32` and Pillow `12.3.0` in backend requirements.
- [ ] Upgrade Electron `33.4.11` to the smallest currently supported secure line,
  `41.10.1`.
- [ ] Upgrade electron-builder `24.13.3` to `26.15.3`.
- [ ] Bump application and installer version from `1.0.11` to `1.0.12`.
- [ ] Keep the backend runtime/API/CSV metadata version synchronized at `1.0.12`.
- [ ] Pass the full repository health suite after clean dependency installation.
- [ ] Rebuild the PyInstaller backend and generate a new NSIS setup artifact.
- [ ] Record artifact identity, size, SHA-256, validation evidence, and rollback.

### 2.2 Non-Goals

- Do not upgrade React, TypeScript, Grafana, Grafana Scenes, FastAPI, Uvicorn,
  Pydantic, Playwright, PyInstaller, or pyinstaller-hooks-contrib.
- Do not run broad `npm audit fix` or introduce npm overrides.
- Do not modify application data schemas, CSV contracts, API contracts, or UI
  behavior.
- Do not publish, install on a production machine, commit, or push artifacts.

## 3. Scope

### 3.1 In Scope

- Root and frontend npm manifests and lockfiles.
- Backend runtime requirements for Pillow and python-multipart.
- Release version metadata and changelog.
- Full typecheck, lint, unit tests, frontend production build, PyInstaller build,
  portable bundle validation, electron-builder packaging, and NSIS generation.
- Read-only inspection of generated ASAR and installer metadata where tooling
  permits.

### 3.2 Out of Scope

- Grafana/Scenes migrations that would require revalidating an internal ESM alias
  and postinstall source patch.
- Electron latest-major adoption beyond the minimum supported line selected here.
- Automated CI introduction or code-signing configuration.
- Server-PC installation and hardware-integrated acceptance testing.

## 4. Functional Requirements

- `[FR-01]` npm lockfiles resolve the six selected npm packages exactly to their
  approved target versions.
- `[FR-02]` backend build requirements resolve Pillow and python-multipart to the
  approved exact versions.
- `[FR-03]` root and frontend package versions remain synchronized at `1.0.12`.
- `[FR-03A]` backend `__version__` and frozen runtime metadata equal `1.0.12`.
- `[FR-04]` the PyInstaller build embeds the current clean source and produces
  `backend/dist/SmartFactoryBackend.exe`.
- `[FR-05]` electron-builder produces
  `dist/smart-factory-logger-v2 Setup 1.0.12.exe`.
- `[FR-06]` generated artifacts are uniquely identifiable by SHA-256.

## 5. Non-Functional Requirements

- Preserve `contextIsolation: true` and `nodeIntegration: false`.
- Preserve existing NSIS target, application ID, executable name, extra resources,
  and ASAR policy.
- Preserve backward compatibility for persisted configuration and CSV data.
- Use exact Python pins for the two upgraded runtime packages.
- Do not expose credentials, private paths, or machine-specific secrets in docs.

## 6. Success Criteria

- [ ] `[AC-01]` `npm ci` succeeds in root and frontend using committed lockfiles.
- [ ] `[AC-02]` `npm run health` passes with the declared dev-tool versions.
- [ ] `[AC-03]` `npm audit` no longer reports the selected Vite, Vitest,
  Electron, or electron-builder vulnerable versions.
- [ ] `[AC-04]` clean backend dependency installation reports Pillow `12.3.0`,
  python-multipart `0.0.32`, PyInstaller `6.20.0`, and hooks `2026.5`.
- [ ] `[AC-05]` frontend production build succeeds without changing the pinned
  Grafana Scenes internal alias contract.
- [ ] `[AC-06]` PyInstaller and portable package verification succeed.
- [ ] `[AC-07]` electron-builder creates the versioned NSIS installer.
- [ ] `[AC-07A]` makensis emits no warning other than electron-builder 26's known
  `IsPowerShellAvailable` forward-declaration warning.
- [ ] `[AC-08]` artifact existence, version, size, and SHA-256 are recorded.
- [ ] `[AC-09]` final Git diff contains only planned manifests, lockfiles, release
  metadata, and PDCA documents.

## 7. Implementation Order

1. Create Plan, Design, and Do tracking documents.
2. Patch version metadata and backend Python pins.
3. Regenerate root npm lock for Electron and electron-builder.
4. Regenerate frontend npm lock for Vite and Vitest.
5. Synchronize the backend virtual environment with dev/build requirements.
6. Run security audits, typecheck, lint, unit tests, and frontend build.
7. Run `scripts/deploy.ps1` to rebuild the PyInstaller backend and portable ZIP.
8. Run `npm run dist` to generate the NSIS installer.
9. Inspect artifacts, calculate hashes, perform PDCA gap analysis, and report.

## 8. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Electron 33 to 41 Chromium/Node behavior change | Desktop startup or renderer regression | Medium | Keep main/preload APIs unchanged; run full tests, production build, ASAR inspection, and packaged startup smoke where possible. |
| electron-builder dependency collection change | Missing packaged resources | Medium | Verify ASAR entries, `extraResources`, backend EXE, frontend sidecar, NSIS build, and installer contents. |
| electron-builder 26 NSIS forward-declaration warning | Default warnings-as-errors blocks installer creation | High | Use the documented `warningsAsErrors: false` option and fail manual review if any warning other than `IsPowerShellAvailable` appears. |
| Python parser behavior tightening | Form parsing regression | Low | Repository has no active Form/File endpoint; run all backend tests and import/startup checks. |
| Pillow decoder hardening | Tray/splash image failure | Low | Rebuild PyInstaller executable and smoke-test packaged startup/assets. |
| Grafana transitive advisories remain | Residual security findings | High | Do not force incompatible overrides; document residual findings for a dedicated Grafana migration. |
| Dev environment differs from requirements | False-positive validation | Medium | Install `requirements-dev.txt` before running health checks. |
| Same-version installer ambiguity | Incorrect rollback/deployment | High | Bump root and frontend versions together to `1.0.12` and record SHA-256. |

## 9. Rollback

- Revert root/frontend manifests and both npm lockfiles together.
- Revert backend requirement pins and release metadata together.
- Rebuild from the last known-good commit and retain the previous `1.0.11`
  installer SHA-256 where available.
- No database, configuration, or CSV migration rollback is required.

## 10. Observability and Failure Modes

- Compare Electron startup milestones and renderer-ready events in
  `debug_electron.log` against the existing baseline.
- Check backend startup/import errors, `/health`, renderer crashes, and process
  cleanup behavior.
- Packaging failures are hard gates; do not publish a partial portable/NSIS set.
- Unsigned installer warnings are expected unless code signing is configured;
  they are not treated as functional success evidence.

## 11. References

- `package.json`, `package-lock.json`
- `frontend/package.json`, `frontend/package-lock.json`
- `backend/requirements.txt`, `backend/requirements-build.txt`
- `scripts/deploy.ps1`
- `backend/build_specs/SmartFactoryBackend.spec`
- `docs/V2/05_운영_배포/build_commit_provenance.md`
- `docs/01-plan/features/nsis-startup-render-performance.plan.md`
- Electron support policy and breaking changes
- Vite, Vitest, Pillow, and python-multipart security/release documentation
