# v1.0.26 static server staging preparation

This is a separate, locally hash-bound staging helper, not an installer or live Canary launcher.
It preserves the committed v1.0.26 product/canary identity and uses the disabled review kit.
`SERVER_GUIDE.md` describes the exact server actions and remaining acceptance gates.

## Build host only

Use native x64 Windows PowerShell 5.1. **`build-transfer.ps1` is historical, not a new-build
entrypoint:** its pre-commit HEAD check is intentionally preserved with the original bytes.
Use **`build-transfer-r2.ps1`** in the current checkout. First generate a fresh offline review
kit at that same HEAD using `scripts/canary-v1026/build-canary-kit.ps1 -ReviewOnly`.
Retain its self-test/71-regression/loopback evidence and externally record the build-result SHA256.
Never substitute the synthetic OfflineCi result for a real release-review receipt.

Run `build-transfer-r2.ps1` with the exact existing v1.0.26 release candidate directory,
`-CanaryBuildResult`, `-ExpectedCanaryBuildResultSha256` and a new `-OutputRoot`.
It verifies the candidate's 14 files, clean committed canary source, source snapshot and all kit
bytes, and assembles the helper from explicit reviewed functions. No script from a transfer
directory is imported on the server before external binding, extraction and read-lock verification.

r2 accepts a newer repository HEAD only when its Canary subtree is exactly
`df4ebc25261b78f355bad5f52884a18a77ba66b9`. It checks clean Git status, raw committed
blob bytes, exact membership (including ignored extras), and every source-snapshot hash.
The receipt must belong to the current HEAD; after any commit, regenerate the review kit.
No old commit object or full Git history is needed, so a shallow checkout works.
The original helper, launcher, guide and contract bytes are pinned and unchanged.
The immutable v1 manifest's `tooling_commit` remains the historical Canary baseline
`c03f7c76ff6e75bfe330275ac0fa01326f357261`, **not** the new builder HEAD. The separate
`build-result.json` records `builder_head`, `canary_source_tree`, both revised builder input
hashes, and the externally supplied receipt hash. Failure retains partial output, with no
automatic cleanup or retry. Use a new output directory each time.

This is build-host reproduction for review, not approval to run the historical staging
launcher on a server. Its legacy server paths are unchanged for compatibility. Any new
server execution helper must separately follow the SFLOps path policy and execution review.

The transfer ZIP contains 32 entries: release 14, disabled kit 15, helper, guide and manifest.
The existing v1.0.25 recovery EXE is not copied again: the helper verifies its fixed server path.
Missing/changed recovery files cause HOLD. Recovery suitability is not approved by a hash match.
The final ZIP is closed/flushed/reopened and every entry verified before publishing the sidecar.
The external `START_V1026_STAGE.txt` pins ZIP, helper and manifest bytes, and runs verified helper
bytes in memory. Only the ZIP and ZIP sidecar need transfer to the server.

## Local fixtures

`test-transfer-binding-r2.ps1 -OutputRoot <new-fixture>` creates a fresh shallow Git checkout
and checks the exact production source/receipt gates without private release assets. It does
not mock the expected Canary tree or run a server main. Full release packaging remains a
separate build-host check with the actual pinned release directory and a fresh review receipt.

```powershell
& .\scripts\server-stage-v1026\test-stage.ps1 `
    -OutputRoot '<new local fixture directory>' `
    -TransferBuildResult '<new transfer build-result.json>'
```

Fixtures exercise path/content/overwrite rejection, actual ZIP extraction and rehash, config
replacement, optional fields without zero coercion, runtime identity comparisons and ACL rules.
They do not query a live app, create an administrator ProgramData directory or install software.
Actual host/token/ACL creation and API behavior remain server-stage validation gaps, not fixture PASS claims.
Full product health/build is not rerun for this packaging-only change. Product dependencies and
the moving emphasis UI are unchanged.

## Failure and recovery

All writes use new destinations; failed outputs remain for review. No evidence deletion, forced
process exit, settings update, image load test, scheduled monitoring or automatic rollback exists.
Live config reads allow write/delete sharing and reopen the path at each sample. Equal endpoint
hashes do not prove every intermediate state was unchanged. A snapshot is not operational health.

If this helper is defective, stop using it and prepare a corrected separately pinned artifact.
Do not edit a distributed ZIP, overwrite prior source evidence or automatically rerun staging.
Code changes remain local until separately committed/reviewed. Release/canary historical source
status strings are retained, and current staging provenance is recorded separately.

## After the completed server stage

`read-current-v1025.ps1` is a separate read-only baseline command, pinned to the server staging
receipt `F4B2FA04...AA5C86`. It is not included retroactively in the distributed staging ZIP.
It checks the current v1.0.25 tree/recovery EXE and reads four loopback endpoints twice around a
30-second wait. Config uses short shared reads; configured storage values are not claimed as
resolved active paths. No settings changes, file writes, restart, backup, installation or new
Canary observation are performed. An unchanged runtime/config is required; differences HOLD.

`test-current-v1025.ps1` is **build-host only**. It imports function ASTs, uses local temporary
fixtures, and never executes the server main or queries an app. Never send this test to operators.
The separate baseline artifact contains a byte-identical `.txt` command, validation receipt and
recovery-risk report. The report keeps installed-directory data and Electron profile downgrade
risks pending until actual backup/restore review; a short sample is not installation approval.

## Retained error and capture-drop details

`read-error-details-v1025.ps1` is a separate read-only follow-up to the reported three retained
errors and 467 historical image-capture drops. It requires the same exact v1.0.25 runtime as the
previous baseline. It makes five bounded loopback GETs (health, errors twice, SPOT config and
cached config), with proxy/redirects disabled. It does not clear the queue, scan raw logs, read
images or fact files, create exports, change settings, restart, back up, install or observe a Canary.

The shareable output is a selected projection. Only known fixed diagnostic strings are displayed;
unknown free-form text is withheld with a hash and length. Device details and arbitrary paths are
not exported. Python dict-like SPOT error detail is not evaluated or treated as JSON.

This v1.0.25 implementation combines over-size and queue-full capture drops in one counter and
does not record a per-drop reason/time at those branches. The command therefore cannot reconstruct
the individual causes of the historical 467 drops or declare them resolved. Error items and their
summary are separately locked snapshots; a concurrent count difference is flagged, not retried.

`test-error-details-v1025.ps1` is build-host only: native Windows PowerShell 5.1, function-AST
imports and synthetic fixtures, with no server-main execution or network requests. The new
`artifacts/v1026-preinstall-error-details-20260911` directory contains the byte-identical plain-text
server command, SHA256 sidecar, local validation receipt and review report. Existing staging,
baseline and historical Canary evidence remain untouched.

## Storage and recovery scope inspection

`read-storage-recovery-v1025.ps1` is the next read-only server command. It checks the same
v1.0.25 process instances and user SID, pinned config/recovery EXE, fixed local storage/profile
candidates and one recent API-reported capture path. Two capture/config snapshots surround a
10-second file-metadata activity sample. It does not import product Python, probe write access,
scan image trees recursively, export profile contents, back up, restore or install.
The operator-suggested `Desktop/SmartFactory` folder is also checked nonrecursively. Archive
metadata is not proof of a backup; arbitrary archive names are hashed and contents stay unopened.

Each selected directory is enumerated nonrecursively with entry/time budgets. Missing, partial
and access-denied results are distinguished. Reparse points observed in the ancestor path are
rejected; separate path checks do not promise native-handle protection against hostile races.
Cached configured paths, metadata activity and SID equality do not prove all effective runtime
paths, successful backup, profile downgrade compatibility or installation readiness.

`test-storage-recovery-v1025.ps1` uses build-host synthetic fixtures and real temporary-file
metadata/shared-read tests, never the server main. The separate
`artifacts/v1026-preinstall-storage-recovery-20260912` directory holds the raw command and review.

## Cold backup and file-restore preparation

`cold-backup-core.cs` and `backup-restore-v1025.ps1` implement a separate, offline-after-close
byte backup and file-restoration rehearsal. This is NOT a VSS snapshot, application restore,
profile downgrade test or installer. The three fixed server roots include the entire backend
AppData, Electron profile and installed directory. Existing data and backups are never overwritten.

The wrapper defaults to preparation-only. `launch-cold-backup.ps1` is different: it is an
execution launcher and supplies `-Execute`; use it only after separate server execution approval.
It pins the transfer externally, validates every entry before extracting into a new folder and
holds read pins until the child exits. The wrapper also requires a maintenance/destination token
before creating the private backup root and asking the operator to close the window normally.
It never issues a shutdown API call, force-stop, restart, cleanup, rollback or installer command.

Live recursive metadata inventory and capacity estimation happen before closure; retained process
handles and a fresh session-bound non-forced shutdown event must pass before byte copying. The new
image fact closeout digest is checked. Backup readback, separate restored-file readback, source
rehashing and exact membership checks are required before the completion receipt. Original metadata
and SDDL are recorded but not applied to copies; periodic checks are not hostile-race/atomic guarantees.

`test-cold-backup.ps1` runs synthetic native PS5.1 tests only. `-LargeFile` exercises a real
2 GiB + 17 byte file; `-EngineAssembly` plus `-ExpectedEngineSha256` tests the exact shipped binary.
`test-cold-backup-transfer.ps1` validates extraction and altered archive rejection without running
server main. `build-cold-backup-transfer.ps1` requires an exact-binary test receipt and creates a new
transfer without replacing earlier artifacts. See `COLD_BACKUP_GUIDE.md` for downtime, capacity,
privacy and recovery limitations. Final preparation is under
`artifacts/v1026-cold-backup-ready-20260912-r2`; the unshipped first assembly is superseded.

## Minimal backup preflight

`read-minimal-backup-preflight-v1025.ps1` is a later, separate read-only scope check for the
operator-approved minimal-backup path. It follows the new `C:\ProgramData\SFLOps\backups\<id>`
policy and does not modify or reuse the legacy `SFL26B-*` helper. It inventories only fixed
configuration/UI/operator-state files, the optional layouts tree and the Electron profile tree.
CSV/image/fact logs, snapshots and the installed program tree are explicitly excluded and the
result states that those business records cannot be recovered by the minimal backup.

The preflight performs no file creation, backup, stop, restart, install or rollback. It checks
current v1.0.25 identity, the pinned config hash, reparse/unsupported attributes, recursive
metadata bounds, projected PowerShell 5.1 path length, free space and an existing SFLOps root ACL.
PASS authorizes only preparation of a new hash-bound cold-copy helper. Local fixtures are in
`test-minimal-backup-preflight-v1025.ps1`; the transfer builder requires their receipt.

`minimal-cold-backup-v1025.ps1` is that separate execution helper. It pins the exact process
instances reported by the preflight, requires `-Execute` and an operator token, and then asks for
a normal window close. It copies the selected profile/layout/state scope only into a new protected
`C:\ProgramData\SFLOps\backups\v1025-min-<id>` child. The existing cold-backup engine is reused by
exact validated binary hash for recursive copying, manifest generation, separate restore rehearsal
and source rehash. The wrapper separately snapshots and rechecks the eight fixed state files.

The helper never uses force-stop, auto-restart, cleanup, installer or rollback. Completion leaves
the app stopped. CSV/image/fact logs, snapshots and the installed program directory remain excluded;
the completion receipt cannot be treated as recovery of that business data or installation approval.

## v1.0.26 install after the minimal backup

**Historical r1, not for new execution.** The original bytes/receipts below remain
`LEGACY_PINNED`. New work uses `install-v1026-after-minimal-backup-r2.ps1` and
`V1026_INSTALL_R2_GUIDE.md`. r2 verifies both backup trees and the original cold
state before approval and immediately before launch, and rejects process/port
query failures. This is not approval to reinstall an already running server.

`install-v1026-after-minimal-backup.ps1` is a separate execution helper bound to the exact completed
server stage and minimal-backup receipt. It requires an execution switch and a new operator token,
keeps the stopped boundary until approval, creates an RX-only installer launch copy, and observes that
the launched installer uses the same-session standard-user token. It does not force-stop, retry,
clean up, roll back or start Canary collection.

After installation it binds the v1.0.26 health version/commit to every one of the 1,645 packaged
payload files plus the exact generated uninstaller. A visible operator confirmation and a 30-second
local counter sample gate SPOT image liveness. The existing v1.0.26 Canary remains deliberately
server-disabled; a fresh 15-minute binding helper is the next separate step after this postflight.
See `V1026_INSTALL_AFTER_MINIMAL_BACKUP_GUIDE.md` for the excluded-backup and HOLD limitations.
