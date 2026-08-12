# TODOS

## Release

### Validate the v1.0.20 private diagnostic-instrumentation release

**What:** Produce an unsigned private release kit bound to the final v1.0.20 commit and complete the controlled server validation sequence.

**Why:** The v1.0.19 `0c1ad4f` candidate completed re-attestation, native-X QA, passive smoke, 120-minute canary, and final closeout, but two diagnostic requests became unresponsive during the canary and the retained evidence could not attribute their field, timeout phase, or transport lifecycle.

**Context:** Keep production/customer release blocked until a new exact-commit artifact proves the bounded append-only request journal under timeout, cancellation, recovery, concurrency, rotation, smoke, instrumented canary, and native-X closeout. Reuse v1.0.19 evidence only as a comparison baseline, not as promotion evidence. Keep the approved v1.0.16 installer as rollback.

**Effort:** L
**Priority:** P0
**Depends on:** Merged exact commit and a newly built hash-locked private release kit

### Sign portable Windows distribution before promotion

**What:** Add independent Authenticode signing and verification for the portable
backend executable before publishing a portable ZIP as an operational release.

**Why:** The protected signed-release workflow intentionally publishes only the
verified NSIS installer. A portable ZIP must not inherit the word "signed" from a
different artifact while its executable has not been independently verified.

**Context:** PR CI may continue producing an explicitly named unsigned portable
artifact for internal validation. This does not block NSIS-based server validation.

**Effort:** M
**Priority:** P1
**Depends on:** Approved portable-distribution requirement and production signing method

### Move production signing to non-exportable key custody

**What:** Replace the exportable PFX secret with an approved HSM, EV token, or remote signing service that never exposes private-key material to the build process.

**Why:** The current protected workflow limits PFX access to the approved exact-commit signing job and deletes the ephemeral file, but electron-builder and its child processes can access that key while `npm run dist` is running.

**Context:** This is a key-custody hardening item. It does not weaken the current exact-commit, protected-environment, signer-thumbprint, timestamp, extracted-payload, or final-hash gates. Revoke the PFX and disable the environment immediately if exposure is suspected.

**Effort:** L
**Priority:** P1
**Depends on:** Approved organization signing service or hardware-backed certificate

## Engineering Debt

### Bound the initial observation archive scan

**What:** Replace the first writer-lifecycle scan of existing schema-mismatch archives with a bounded or persisted pending-count strategy.

**Why:** Recurring health requests no longer rescan archives, but the first pending-count call can still scale with accumulated historical archive size.

**Context:** Preserve the current fail-closed manifest semantics and mutation-aware cached counts. This is not part of the v1.0.19 promotion gate unless field evidence shows startup or first-health latency regression.

**Effort:** M
**Priority:** P2

### Bound process-lifetime poll-sequence diagnostics

**What:** Replace the process-lifetime growing poll-sequence gap set with a bounded data structure or equivalent aggregate accounting.

**Why:** Long-running processes should not retain one diagnostic identifier per observed gap indefinitely.

**Context:** Preserve duplicate/gap observability and existing API field semantics. Add long-duration or synthetic high-cardinality coverage before changing the representation.

**Effort:** M
**Priority:** P2

## Completed
