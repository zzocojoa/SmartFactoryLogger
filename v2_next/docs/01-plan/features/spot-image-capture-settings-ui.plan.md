# SPOT Image Capture Settings UI Plan

> Date: 2026-07-01 | Feature: `spot-image-capture-settings-ui`

## Goal

Expose the existing SPOT evidence image capture policy in Settings > SPOT camera without changing the capture writer, upstream fetch, retention cleanup, or image file format.

## Requirements

1. The default visible policy remains `enabled=false` and `mode=off`.
2. Operators can set enabled, mode, path, min interval, max bytes, retention days, and observation-link behavior.
3. The UI warns that enabling capture increases disk usage and stores field images.
4. Save payload writes the existing `[SPOT] imagecapture*` config.ini keys.
5. The path input accepts only a relative path under the log directory.
6. Tests cover frontend helper policy and backend config snapshot/update behavior.

## Scope Out

- No writer behavior changes.
- No SPOT upstream fetch changes.
- No retention cleanup changes.
- No review/gallery UI for captured images.
- No chunk splitting or build performance tuning.

## Rollback

Revert the PR commit. Operationally, save `enabled=false` and `mode=off` from the UI or set `SPOT_IMAGE_CAPTURE_ENABLED=false`.
