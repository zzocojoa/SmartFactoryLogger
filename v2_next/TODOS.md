# TODOS

## Release

### Complete v1.0.17 signed field validation

**What:** Produce a signed release kit bound to the final commit and complete the controlled server validation sequence.

**Why:** Earlier field evidence belongs to different commits, and packaged commit `49fbf6b` failed CSV shutdown-closeout QA before the verified v1.0.16 rollback.

**Context:** Start only after CI and packaged native X-close validation pass for the exact final commit. Then run the read-only preinstall gate, install, commit-bound re-attestation, one-command QA, 15-minute smoke, 120-minute canary, and final read-only live gate. Do not reuse `575e869`, `49fbf6b`, or `949ef38` field evidence.

**Effort:** XL
**Priority:** P0
**Depends on:** Production Authenticode signing and exact-commit CI artifacts

## Completed
