# TODOS

## Release

### Complete v1.0.17 signed field validation

**What:** Produce a signed release kit bound to the final commit and complete the controlled server validation sequence.

**Why:** Earlier field evidence belongs to different commits, and packaged commit `49fbf6b` failed CSV shutdown-closeout QA before the verified v1.0.16 rollback.

**Context:** Start only after CI and packaged native X-close validation pass for the exact final commit. Then run the read-only preinstall gate, install, commit-bound re-attestation, one-command QA, 15-minute smoke, 120-minute canary, and final read-only live gate. Do not reuse `575e869`, `49fbf6b`, or `949ef38` field evidence.

**Effort:** XL
**Priority:** P0
**Depends on:** Production Authenticode signing and exact-commit CI artifacts

## Engineering Debt

### Bound the initial observation archive scan

**What:** Replace the first writer-lifecycle scan of existing schema-mismatch archives with a bounded or persisted pending-count strategy.

**Why:** Recurring health requests no longer rescan archives, but the first pending-count call can still scale with accumulated historical archive size.

**Context:** Preserve the current fail-closed manifest semantics and mutation-aware cached counts. This is not part of the v1.0.17 promotion gate unless field evidence shows startup or first-health latency regression.

**Effort:** M
**Priority:** P2

### Bound process-lifetime poll-sequence diagnostics

**What:** Replace the process-lifetime growing poll-sequence gap set with a bounded data structure or equivalent aggregate accounting.

**Why:** Long-running processes should not retain one diagnostic identifier per observed gap indefinitely.

**Context:** Preserve duplicate/gap observability and existing API field semantics. Add long-duration or synthetic high-cardinality coverage before changing the representation.

**Effort:** M
**Priority:** P2

## Completed
