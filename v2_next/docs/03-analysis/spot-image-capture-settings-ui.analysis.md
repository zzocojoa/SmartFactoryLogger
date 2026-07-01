# SPOT Image Capture Settings UI Analysis

> Date: 2026-07-01 | Feature: `spot-image-capture-settings-ui`

## Decision

Use the existing `/api/config` settings path instead of adding a new endpoint. This keeps SPOT capture policy with the rest of operator-editable config and preserves the existing local override, pending config, backup, and apply-result behavior.

## Safety Notes

- The highest operational risk is disk growth and unintended field image retention.
- The default remains off, and disabled state forces mode off.
- The path is constrained to a relative log-subdirectory path from the UI.
- Backend clamps numeric values to non-negative or positive bounds.

## Test Focus

- Snapshot defaults prove missing config keys become disabled/off.
- Update tests prove UI-shaped payloads write the intended config.ini keys.
- SettingsModal helper tests prove off remains the first/safest UI option.
