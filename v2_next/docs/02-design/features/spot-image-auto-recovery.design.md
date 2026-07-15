# spot-image-auto-recovery - Design Document

> Version: 1.0.0 | Date: 2026-07-14 | Status: Approved
> Level: Dynamic | Plan: docs/01-plan/features/spot-image-auto-recovery.plan.md

---

## 1. Overview

### 1.1 Purpose

Add bounded automatic recovery to the singleton SPOT image state machine
without changing the manufacturer-defined `/image.jpg` resource or the normal
completion-driven request flow.

### 1.2 Design Goals

- Recover transient failures without an operator click.
- Keep persistent failures actionable and observable.
- Keep manual Retry as an immediate override and final fallback.
- Prevent retry timers or multiple mounted consumers from creating duplicate
  upstream requests.
- Separate camera acquisition errors from focus/actuator control errors.

## 2. Architecture

### 2.1 System Architecture

```text
successful displayed JPEG
        |
        v
completion callback ----------------------+
        |                                  |
        v                                  |
GET /api/spot/image.jpg                    |
        |                                  |
        +--> success -> validate -> Blob --+
        |
        +--> transient failure -> bounded retry scheduler
        |                           |             |
        |                           +-> success --+
        |                           +-> exhausted -> manual Retry
        |
        +--> persistent failure ----------------> manual Retry

focus/actuator request -> independent controlError (never imageError)
```

The backend image bridge, official upstream resource, JPEG validation, and
device-wide lock remain unchanged.

### 2.2 Component Design

#### Pure recovery policy

Add `spotImageRecoveryPolicy.pure.ts` containing:

- retryable code/status classification;
- immutable retry delays;
- a pure function returning the delay for the next consecutive retry;
- no timers, React state, or network access.

The retry delays are `500 ms`, `1,000 ms`, and `2,000 ms`. They apply only
after failure. Successful frame acquisition receives no delay.

#### `useSpotViewModel`

The singleton view model owns:

- one retry timer ref;
- one consecutive retry-attempt ref;
- the existing in-flight guard;
- retry scheduling/cancellation;
- image and control error state updates.

No component owns a retry timer. Dashboard and Settings remain passive
consumers of the same state.

#### `useSpotViewModelEffects`

Config URL changes and unmount cleanup cancel any pending retry before the old
request generation can run again.

#### Control errors

Focus and actuator failures write `spotControlError` in the Dashboard store.
`CameraWidget` renders that message next to the control buttons. Successful
control operations clear it. It is not passed to `getCameraStatus` and cannot
show the image Retry action.

### 2.3 Failure Classification

| Failure | Automatic retry |
| --- | --- |
| browser/fetch network exception | Yes |
| `upstream-timeout` | Yes |
| `upstream-request-error` | Yes |
| `empty-body` | Yes |
| bridge `502` unknown/non-payload failure | Yes |
| upstream HTTP `408`, `425`, `429`, or `5xx` | Yes |
| browser Blob display/decode failure | Yes |
| missing SPOT configuration | No |
| upstream non-retryable `4xx` | No |
| HTML, invalid JPEG, invalid MIME/size/length | No |

Unknown response failures use the HTTP status: a bridge `5xx` is transient;
other unknown statuses are terminal. A JavaScript exception without an HTTP
response is transient because it represents the fetch/transport boundary.

### 2.4 Retry State Machine

```text
displayed
  -> fetching
  -> blob_pending_display
  -> displayed (clear error + reset attempts)

fetching -> transient_error
  -> retry_wait(1, 500ms)
  -> retry_wait(2, 1000ms)
  -> retry_wait(3, 2000ms)
  -> exhausted (manual Retry remains)

fetching -> persistent_error -> manual Retry
blob_pending_display -> transient_error -> same bounded retry path

manual Retry:
  cancel timer -> reset attempts -> fetch immediately
```

The retry timer is scheduled only once. A second consumer error event sees the
existing timer and cannot consume another attempt or create another request.

## 3. Data Model

### 3.1 Frontend Diagnostics

Extend `SpotPollingDiagnostics` with:

| Field | Type | Meaning |
| --- | --- | --- |
| `automatic_retry_count` | `number` | total automatic requests scheduled |
| `consecutive_retry_attempt` | `number` | current failure streak attempt |
| `automatic_retry_pending` | `boolean` | retry timer is armed |
| `automatic_retry_exhausted` | `boolean` | bounded budget has been consumed |
| `next_retry_scheduled_at` | `number \| null` | browser epoch milliseconds |
| `last_failure_retryable` | `boolean \| null` | most recent classification |

These are frontend in-memory diagnostics only. No API, persistence, or CSV
schema changes are introduced.

### 3.2 Dashboard Control State

Add `spotControlError: string | null` and `setSpotControlError()` to the
Dashboard store. It is distinct from `spotImageError`.

## 4. API Specification

No backend API changes.

- Image acquisition remains `GET /api/spot/image.jpg`.
- Upstream remains `GET http://{SPOT_IP}/image.jpg`.
- Existing response status and error detail fields are used to classify the
  frontend recovery policy.
- Caller-selected URLs and undocumented device resources remain prohibited.

## 5. Implementation Plan

### 5.1 Files

- `frontend/src/domains/FacilityData/utils/spotImageRecoveryPolicy.pure.ts`
- `frontend/src/domains/FacilityData/utils/spotImageRecoveryPolicy.pure.test.ts`
- `frontend/src/domains/FacilityData/hooks/useSpotViewModel.ts`
- `frontend/src/domains/FacilityData/hooks/useSpotViewModelEffects.ts`
- `frontend/src/domains/FacilityData/hooks/useSpotViewModel.integration.test.ts`
- `frontend/src/shared/types.ts`
- `frontend/src/store/useDashboardStore.ts`
- `frontend/src/domains/FacilityData/components/widgets/CameraWidget.tsx`
- `frontend/src/domains/FacilityData/components/widgets/CameraWidget.focusDirection.test.tsx`
- `frontend/src/App.css`
- PDCA analysis/report documents.

### 5.2 Implementation Order

1. Add the pure classification and retry-delay policy with unit tests.
2. Add retry ownership, cleanup, and diagnostics to the view model.
3. Separate focus/actuator errors into store control state.
4. Add integration tests for recovery, exhaustion, persistent failures,
   duplicate events, manual override, and cleanup.
5. Run focused and full checks; fix gaps.
6. Commit the verified source and build clean PyInstaller/NSIS artifacts.

## 6. Test Plan

### 6.1 Unit Tests

- transient error codes and statuses are retryable;
- configuration and payload rejection are terminal;
- delay lookup returns exactly three bounded retries and then exhaustion.

### 6.2 Hook Integration Tests

- timeout then success performs one automatic retry and resumes completion;
- payload rejection performs no automatic retry;
- four consecutive transient failures stop after three automatic retries;
- manual Retry cancels a pending timer and requests immediately;
- two browser display errors schedule only one automatic retry;
- unmount/config change prevents a pending stale retry;
- successful displayed frame resets the retry budget;
- focus limit/error and actuator error do not set image error;
- successful focus/actuator operation clears control error.

### 6.3 UI Tests

- image Retry appears only for `spotImageError`;
- control error renders separately and cannot trigger image Retry;
- Retry remains disabled only while an image request is actively loading.

### 6.4 Repository and Package Tests

- focused Vitest suite;
- frontend typecheck, lint, and full tests;
- full `npm run health`;
- `git diff --check` and sensitive-value scan;
- clean Git commit;
- `scripts/deploy.ps1` PyInstaller and NSIS build;
- backend/frontend resource existence, installer SHA-256, and packaged build
  provenance verification.

## 7. Security and Operations

- Automatic retry never changes the server-derived upstream URL.
- Retry classification consumes bounded backend fields only.
- No response body, device URL, or credential is added to UI diagnostics.
- Finite attempts prevent accidental denial-of-service loops.
- Existing backend observability remains authoritative for upstream failures;
  frontend counters explain recovery behavior.
- Rollback is a single feature-commit revert followed by a package rebuild.
- The development build cannot replace the required physical-device server
  validation; server installation and the established 15-minute observation
  remain the post-build operational gate.
