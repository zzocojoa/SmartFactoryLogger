# spot-camera-rest-api-conformance - Design Document

> Version: 1.0.0 | Date: 2026-07-11 | Status: Approved
> Level: Dynamic | Plan: docs/01-plan/features/spot-camera-rest-api-conformance.plan.md

---

## 1. Overview

### 1.1 Purpose

Replace the pre-manual dual live/snapshot camera architecture with one
completion-driven JPEG acquisition flow based on the SPOT+ REST API guide.

### 1.2 Normative Contract

The manufacturer guide is authoritative for the device boundary:

1. Sections 2.3 and 5.3 identify `GET http://[ipaddress]/image.jpg` as the
   current camera JPEG resource.
2. Section 5.3 reads the response as a Blob, displays it, revokes the previous
   object URL, and requests the next image on successful completion.
3. The guide does not define `/newjpeg.jpg`, a separate live URL, stale-frame
   substitution, a success delay, two acquisition loops, or a client-selected
   camera resource.
4. Section 3.3 contains the shorter `/image` spelling, but the parameter index,
   complete JavaScript example, current device configuration, and production
   response all establish `/image.jpg` as the canonical resource.

## 2. Architecture

### 2.1 Target Architecture

```text
SPOT IP configuration
        |
        v
http://{SPOT_IP}/image.jpg
        |
        v
single backend GET + JPEG validation + optional evidence enqueue
        |
        v
GET /api/spot/image.jpg
        |
        v
singleton useSpotViewModel fetch -> Blob URL
        |
        +----------------------+
        |                      |
Dashboard CameraWidget   Settings SPOT preview
```

The same Blob URL and lifecycle state are rendered by both UI consumers. There
is no visible/hidden image split and no second acquisition loop.

### 2.2 Backend Components

- `config.py`
  - `SPOT_IP` remains configurable.
  - the image URL is constructed only at request time as
    `http://{SPOT_IP}/image.jpg`; no image URL setting exists.
  - `SPOT_IMAGE_URL`, `SPOT_LIVE_IMAGE_URL`, `imageurl`, and `liveimageurl` override behavior are
    removed from runtime configuration.
- `spot_api.py`
  - one async lock and one direct acquisition function;
  - no current/stale image cache, exponential image backoff, alternate URL
    candidates, or live-specific state;
  - bounded connect/read timeout and JPEG payload validation remain;
  - successful bytes may still be passed to the existing evidence capture
    writer.
- `app.py`
  - one camera route: `GET /api/spot/image.jpg`;
  - the route returns the latest successful upstream response only;
  - no `/api/spot/live_image` or `/api/spot/proxy_image` route;
  - failures return an error instead of HTTP 200 with a stale frame.

### 2.3 Frontend Components

- `useSpotViewModel`
  - remains the only acquisition owner;
  - fetches `/api/spot/image.jpg` and creates a validated Blob URL;
  - only the first `onLoad` for the pending Blob triggers the next fetch;
  - a second mounted consumer cannot trigger a duplicate request;
  - `onError` stops recursion and preserves the error for explicit retry.
- `useSpotViewModelEffects`
  - starts the first request when the official image route becomes available;
  - removes refresh timers and visibility-triggered duplicate fetches;
  - retains configuration leader synchronization.
- `CameraWidget` and `SettingsModal`
  - render the same `spotImageUrl`;
  - both use the same load/error callbacks;
  - no component owns a separate timer or endpoint.

### 2.4 Preserved Safeguards

These controls do not alter the SPOT resource contract and remain:

- upstream URL is server-derived, never accepted from a request parameter;
- request timeout is bounded;
- response must be a valid JPEG and HTML is rejected;
- only one upstream request is in flight;
- errors and latency are observable;
- evidence capture consumes only successfully validated official JPEG bytes.

### 2.5 Device-Wide Request Serialization

Server validation showed that direct completion-driven `/image.jpg` access was
stable for 2,014 consecutive requests, while the packaged app produced image
and diagnostic upstream timeouts. The app currently serializes image requests
only; temperature, internal-temperature, and eight diagnostic output requests
can overlap the image request at the physical SPOT device.

All runtime requests targeting the SPOT device therefore share one fair async
device lock:

- official `/image.jpg` acquisition;
- `/output?p=temperature`;
- each diagnostic `/output?p=...` read;
- internal-temperature output;
- focus and actuator control transactions invoked by the API.

The lock is acquired before starting the HTTP timeout, so time waiting for a
different SPOT operation is not misclassified as an upstream timeout.
Diagnostic fields are requested sequentially rather than with
`asyncio.gather()`. The lock is released between diagnostic fields so queued
image and temperature requests receive a turn. Focus and actuator sync
transactions run in worker threads behind async wrappers while the same device
lock remains held, including cancellation cleanup.

This backend arbitration does not add a camera frame timer or alter the PDF
completion-driven UI state machine.

### 2.6 Application Pyrometer App Number

The AMETEK LAND REST API defines `appnumber` as an Application Pyrometer-only
control parameter. It must be read with `GET /control?p=appnumber`; it is not an
`/output` parameter. The SPOT+ AL server device confirmed this contract:

- `GET /output?p=appnumber` returned HTTP 400;
- `GET /control?p=info` returned `SPOT+ AL`;
- `GET /control?p=appnumber` returned HTTP 200 with value `7`.

The diagnostics collector routes `appnumber` to `/control` while all measured
output diagnostics remain on `/output`. Both paths use the same device-wide
request lock.

## 3. State Model

### 3.1 Image Lifecycle

```text
idle
  -> fetching
  -> response_validated
  -> blob_pending_display
  -> displayed
  -> fetching (next frame)

fetching -> error (HTTP/network/payload error)
blob_pending_display -> error (browser decode error)
error -> fetching only through explicit retry/reconnect
```

### 3.2 Single-Completion Guard

`pendingImageUrlRef` identifies the frame allowed to advance the loop. The first
consumer that loads the frame clears the pending token and starts the next
fetch. Later `onLoad` events for the same Blob are ignored for acquisition.

### 3.3 Removed State

- `_live_img_cache`, `_live_img_failure_count`, live retry timestamps;
- current/stale `_img_cache` frame bytes and image backoff state;
- frontend live timer/frame counter;
- configured live URL and alternate JPEG path.

## 4. API Specification

### 4.1 `GET /api/spot/image.jpg`

Request:

- no body;
- query values may be ignored cache-busters;
- caller cannot select the upstream target.

Success:

- status `200`;
- media type `image/jpeg`;
- body is the latest validated response from
  `http://{SPOT_IP}/image.jpg`;
- `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`;
- diagnostic headers may report capture time and request latency, but never
  claim a stale/cached source.

Failure:

- `404` only when SPOT IP configuration cannot produce the official URL;
- `502` for upstream HTTP/network/payload failures;
- no HTTP 200 stale-frame fallback;
- no application retry-after/backoff contract.

### 4.2 `GET /api/spot/config`

- `image_url` is `/api/spot/image.jpg`.
- `live_image_url`, `live`, and `proxy` objects are removed.
- one `image` diagnostic object reports current direct acquisition health.
- `refresh_interval` remains the measurement/diagnostics interval and is not a
  camera frame-rate control.

### 4.3 Removed Contracts

- `GET /api/spot/live_image`
- `GET /api/spot/proxy_image`
- `SPOT_LIVE_IMAGE_URL`
- `SPOT_IMAGE_URL`
- `[SPOT] liveimageurl`
- `[SPOT] imageurl` as an alternate upstream resource
- `/newjpeg.jpg` support and QA

## 5. Implementation Plan

### 5.1 Files

- Backend runtime:
  - `backend/config.py`
  - `backend/Configuration/Configuration_Structure.py`
  - `backend/Configuration/service.py`
  - `backend/Configuration/Configuration_DB_Manager.py`
  - `backend/FacilityData/drivers/spot_api.py`
  - `backend/Observability/service.py`
  - `backend/Observability/memory_service.py`
  - `backend/app.py`
- Frontend runtime:
  - `frontend/src/shared/types.ts`
  - `frontend/src/store/useDashboardStore.ts`
  - `frontend/src/domains/FacilityData/api/spotService.mapper.ts`
  - `frontend/src/domains/FacilityData/hooks/useSpotViewModel*`
  - `frontend/src/domains/FacilityData/components/widgets/CameraWidget.tsx`
  - `frontend/src/domains/Configuration/components/SettingsModal/SettingsModal*.tsx`
- Tests and documentation matching the affected contracts.
- Package QA:
  - `package.json`
  - `scripts/qa_spot_image_server.ps1`

### 5.2 Order

1. Lock configuration and backend upstream resolution to `/image.jpg`.
2. Collapse backend live/proxy state and routes into one direct route.
3. Collapse frontend acquisition into the singleton completion state machine.
4. Make Dashboard and Settings consume the same state.
5. Remove obsolete config/types/observability/docs/script references.
6. Run focused tests, full health, build, package smoke, and server validation.

## 6. Test Plan

### 6.1 Backend

- official URL is always derived from SPOT IP and ends in `/image.jpg`;
- request parameter/config cannot select another upstream URL;
- one request returns one latest validated JPEG;
- HTML/invalid/timeout/HTTP errors return failure without stale bytes;
- concurrent calls never create concurrent upstream requests;
- image, temperature, diagnostics, internal-temperature, focus, and actuator
  API operations never overlap at the SPOT device;
- diagnostic output fields are collected sequentially and retain per-field
  failure status;
- cancellation of a threaded control request does not release the device lock
  before the underlying request finishes;
- Application Pyrometer `appnumber` uses `/control?p=appnumber` and never
  `/output?p=appnumber`;
- successful official bytes still reach evidence capture when enabled;
- removed routes return `404`.

### 6.2 Frontend

- config maps to `/api/spot/image.jpg` only;
- first request starts once;
- successful Blob display triggers exactly one next fetch;
- two mounted consumers do not double-trigger;
- load failure stops recursion;
- Dashboard and Settings render the identical Blob URL;
- no 35ms/500ms live timers remain.

### 6.3 System

- frontend typecheck/lint/tests/build;
- backend ruff/mypy/unittest;
- sensitive-value and diff checks;
- PyInstaller/NSIS package provenance;
- server direct official image QA and 15-minute error-queue observation.

## 7. Security and Operations

- The internal bridge remains necessary because the packaged Electron `file:`
  origin cannot rely on the device's CORS behavior.
- Backend listening/firewall scope is unchanged and must remain restricted to
  trusted hosts.
- Removing stale fallback intentionally makes camera failure visible; operators
  must not mistake an old frame for a current view.
- Rollback restores the previous package and configuration backup; there is no
  data migration.
