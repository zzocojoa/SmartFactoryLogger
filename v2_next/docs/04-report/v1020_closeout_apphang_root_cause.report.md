# v1.0.20 closeout AppHang root-cause report

## Verdict

- Field candidate: `v1.0.20 / c823d91432e3519dee9cb6b770098d8eb1540405`
- Patch state: local working-tree fix; no commit-bound release package exists yet
- Root-cause class: packaged Electron main-thread blocking on synchronous Windows stdout
- Field attribution: high confidence from the exact failure boundary and deterministic local
  reproduction; server Evidence retains `root_cause_resolved=false` because no dump exists
- Server policy: keep SmartFactoryLogger stopped; release hold remains active

## Field failure boundary

- `backend.shutdown-start` was durably appended to `debug_electron.log`.
- No backend shutdown HTTP request, `backend.closed`, `backend.shutdown-complete`, or
  `backend.shutdown-failed` record followed.
- CSV and journal activity continued for about 89 seconds, proving the backend remained alive.
- Windows recorded `AppHangB1` for Electron main PID `8284` about 90 seconds later.
- The final read-only WER inventory found one `Report.wer` and no process dump,
  cabinet, or dump reference.

## Final WER inventory

- Evidence SHA-256:
  `E0F46C49826611FE5E474D85D6D59C2FD624A020BD20882E24EA72CEEAAB6C83`
- Evidence contract: `PASS`, checks `61/61`, failed checks `0`
- Archive inventory SHA-256 before and after inspection:
  `E5CD186A0954A1951AD0C43EC93D5F4A0CBC1031F044A0246247E8448CD7C968`
- Archive contents: one `Report.wer`, zero subdirectories
- `Report.wer` SHA-256:
  `F2CAF919CDFA692D89008499DCA74E41F92CB4E9D55743CA390AD31F1D0F0C9B`
- WER identity: `AppHangB1`, application `smart-factory.exe`
- Dump candidates: `0`; cabinets: `0`; dump references: `0`
- The helper performed no WER, application, config, pktmon, or existing Evidence mutation.

## Reproduction

The pre-fix regression test connected stdout to a Windows pipe and intentionally did not
consume it. The Electron logger first completed its file append, then stopped at:

```text
logger.append-complete
logger.console-start
```

The child did not return within two seconds. This matches the field boundary: the file log
contains `backend.shutdown-start`, but shutdown transport never begins.

Node documents that `console.log()` uses `process.stdout`, that pipe writes are synchronous
on Windows, and that a pipe without a reader can block the event loop:
<https://nodejs.org/api/process.html#a-note-on-process-io>.

## Patch

- Keep the bounded rotating file log unchanged.
- Disable stdout/stderr console echo only when `app.isPackaged` is true.
- Retain console echo for unpackaged development runs.
- Add opt-in worker-backed shutdown boundary tracing. The trace worker writes independently
  of the Electron main thread and is enabled only by the diagnostic argument or environment.
- Do not change backend shutdown API, closeout ordering, grace timeout, force-stop policy,
  config, data schema, or installer behavior.

## Validation

- Pre-fix blocked-pipe test: failed at `logger.console-start` as expected.
- Post-fix blocked-pipe test: passed.
- Electron startup/shutdown/runtime suite: 88/88 passed.
- Frontend tests: 253/253 passed; frontend type check and lint passed.
- Backend tests: 690/690 passed; Ruff and mypy passed.
- Full `npm run health` and test-only `npm run pack`: passed.
- Packed `app.asar` contains `main.js`, `electronRuntimeSafety.js`,
  `shutdownDiagnosticTrace.js`, and `shutdownDiagnosticTraceWorker.js`; their
  SHA-256 values match the corresponding source files.
- Instrumented packaged native-X runs:
  - PowerShell: 3/3 exit code `0`, dump count `0`
  - Windows shortcut: 3/3 exit code `0`, dump count `0`
  - stdout blocked pipe: 1/1 exit code `0`, dump count `0`
- All runtime reproductions used temporary APPDATA and loopback-only PLC/SPOT endpoints.

## Release gate

- The WER inventory is complete, but the absence of a dump means no server thread stack can
  be recovered from this incident. The local deterministic mechanism and field boundary are
  sufficient for the patch, not for declaring the server release hold resolved.
- The current dirty-working-tree package is test-only and must not be deployed. Create a new
  commit, rebuild from that exact clean commit, and verify packaged backend and Electron
  provenance before producing any server validation kit.
- After review, use separate steps for stopped-state operator re-attestation, normal Windows
  launch, QA, passive smoke, instrumented canary, and final closeout. None is approved by this
  report alone; the server must remain stopped meanwhile.
- Rollback remains the verified v1.0.16 package. No migration is required.
- Bounding retention for opt-in shutdown diagnostic JSONL files remains a P2 backlog item.
