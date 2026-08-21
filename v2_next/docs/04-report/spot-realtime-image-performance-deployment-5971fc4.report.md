# SPOT realtime image v1.0.21 deployment gate report

> Generated: 2026-08-21
> Candidate version: `1.0.21`
> Build commit: `5971fc4fbdeec07ef65681a945319f0ae12d55cb`
> Classification: `PRIVATE_UNSIGNED_INTERNAL_CANARY_ONLY`
> Verdict: `BLOCKED_BEFORE_INSTALL`

## 1. Candidate identity

| Item | Evidence |
|---|---|
| Installer | `smart-factory-logger-v2 Setup 1.0.21.exe` |
| Installer SHA-256 | `01CF544C999FB21FADB7F36965DC35FB9E8AEE36D1EEBD3319A1EB7296AD191A` |
| Installer length | `149170277` bytes |
| Authenticode | `NotSigned` |
| Backend bundle SHA-256 | `B818383DF7B035DC73C86E57F0080489B287C958086C8E2C426639C0622CB094` |
| Backend files verified | `1385 / 1385` |
| Extracted `app.asar` SHA-256 | `50734BC222DF943A2DC6605E35EDEA0AD600C909A0A32E4ADEFF2A2A0952C048` |
| Bundle manifest SHA-256 | `C15C8A4133BA80D7A5D8ADA4990CFFC8B75D042F4DA8C97DEE936FD510546F9A` |
| Build provenance SHA-256 | `20932B2B361F3CDDF03701B9F8B501F1336BDA4C4CEC92A359E560767210A610` |
| Extraction helper SHA-256 | `223B873C50380FE9A39F1A22B6ABF8D46DB506E1C08D08312902F6F3CD1F7AC3` |

The installer, extracted backend manifest, extracted build provenance, and
packaged Electron sources all resolve to the exact build commit above. The
artifact kit is stored locally under
`artifacts/spot-realtime-image-performance-v1.0.21-5971fc4/`; it is not a
signed production release and must not be promoted or distributed externally.

## 2. Completed gates

- Clean detached-worktree build from the exact commit: `PASS`.
- Frontend production build: `PASS`, 4,532 modules transformed.
- PyInstaller provenance check before and after packaging: `PASS`.
- Backend bundle integrity: `PASS`, 1,385 files and aggregate hash matched.
- NSIS extraction into an isolated temporary directory: `PASS`.
- Extracted Electron runtime-source identity: `PASS`.
- Root health suite: Electron `94`, frontend `265`, backend `711`, Ruff, mypy,
  and Windows helper self-tests passed. The first helper invocation failed only
  because the Codex runtime shadowed the Windows PowerShell module path; the
  same helper suite passed after explicitly restoring the system module path.

## 3. Target baseline

The expected server service was reachable through its existing LAN HTTP
endpoint on 2026-08-21.

- `/health`: HTTP `200`, installed `app_version=1.0.20`.
- `/stats`: HTTP `200`.
- Existing `/api/spot/image.jpg`: HTTP `200`, `image/jpeg`, 9,692 bytes,
  `X-Spot-Image-Source=cache`. This confirms only the old snapshot path and does
  not substitute for a v1.0.21 physical-device smoke.
- `/api/spot/live_image.jpg`: HTTP `404`, confirming that the v1.0.21
  candidate has not been installed.
- The development PC could not directly reach the SPOT device at port 80.

No target configuration, process, error queue, or SPOT device state was
modified during this baseline check.

## 4. Install blockers

Installation was not attempted because the fail-closed preinstall conditions
were incomplete.

1. The candidate is unsigned. It is eligible only for the documented
   owner-controlled private-use exception, never customer, public, commercial,
   or organization-managed deployment.
2. No approved remote execution channel was available from the development PC:
   WinRM and SSH were unavailable and administrative SMB shares were not
   accessible.
3. The required rollback installer was not present. The design records the
   expected v1.0.16 SHA-256 as
   `42A076B37ADA66CEAEE816128A1FC67C40CCD1C5417F9BDED5E885478974F615`,
   but no local candidate could be hashed and matched.
4. Target-side read-only preinstall, normal UI close, installed payload
   re-attestation, and operator visual confirmation remain pending.

## 5. Canary status

| Gate | Status |
|---|---|
| Target preinstall | `PENDING` |
| v1.0.21 installation | `NOT_RUN` |
| Actual SPOT 15-minute smoke | `NOT_RUN` |
| Actual SPOT 120-minute canary | `NOT_RUN` |
| Request-rate comparison | `NOT_MEASURED` |
| old-ACK/RST comparison | `NOT_MEASURED` |
| source-port pool comparison | `NOT_MEASURED` |

No release, production, or field-resolution claim is permitted from the local
build result. Resume only on the owner-controlled server after the rollback
installer hash and target-side execution channel are available. The 120-minute
canary may start only after the same binary and configuration pass the complete
15-minute hard gate.
