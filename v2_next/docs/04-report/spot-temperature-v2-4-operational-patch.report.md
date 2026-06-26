# Completion Report: spot-temperature-v2-4-operational-patch

> Date: 2026-06-25 KST | Level: Dynamic
> PR: #68 `Implement SPOT temperature v2.4 operational contract`
> Branch: `codex/spot-temperature-v2-4-operational-implementation`
> Pre-report implementation HEAD: `35122cbb0f69bfa6adeb952a2fef7d0728723cb6`
> PDCA report commit: `1973bc54008ad7878e71a339b34b0c11f7ace4c0`

---

## 1. Summary

### 1.1 Feature Overview

`spot-temperature-v2-4-operational-patch` keeps the PR #65 v2.3 SPOT sentinel and shadow-instrumentation baseline, then adds an explicit v2.4 temperature operational contract for downstream consumers.

Main outcomes:

- `6553.4` and `6553.5` sentinel responses remain separate from ordinary numeric temperatures and generic missing values.
- v2.3 shadow fields remain evidence only and are not promoted to operational truth.
- v2.4 CSV fields are behind feature flags, so default v2.3 consumers remain compatible.
- realtime CSV rows, per-poll `spot_observation_fact`, and post-hoc process phase event facts are separated.
- post-hoc fact generation never mutates source CSV input and only emits outputs when `PROCESS_PHASE_EVENT_FACT_ENABLED=true`.

### 1.2 Match Rate Evidence

- Latest `bkit_pdca_analyze` result: 90% / iteration 9.
- Manual follow-up audit: 100% / iteration 10.

The 100% figure is a manual post-tool audit after closing NONBLOCK-1 and NONBLOCK-2, not a new `bkit_pdca_analyze` return value.

```text
v2.3 baseline preservation: 7/7
v2.4 operational deliverables: 13/13
overall design match: 20/20 = 100%
```

### 1.3 Merge Readiness

PR #68 is merge-ready for the default-off v2.4 implementation scope at report time.

- PR state: open, not draft
- mergeStateStatus: `CLEAN`
- CI: `Build Windows artifacts` PASS
- Local working tree before report generation: clean

---

## 2. Completed Items

### 2.1 v2.3 Baseline Preservation

- [x] PR #65 sentinel classification baseline preserved.
- [x] invalid sentinel cache suppression baseline preserved.
- [x] immutable SPOT snapshot metadata baseline preserved.
- [x] v2.3 SPOT shadow CSV columns preserved.
- [x] v2.3 validator sentinel checks preserved.
- [x] post-hoc process segment/fact separation preserved.
- [x] CSV formula escaping for existing text fields preserved.

### 2.2 v2.4 Operational Contract

- [x] `temperature_operational.py` added as a pure adapter over `temperature_state.py`.
- [x] `temperature_output_status`, `temperature_unavailable_reason`, expectedness, cause, confidence, and row freshness fields added.
- [x] stale row precedence prevents old sentinel values from being interpreted as current operational state.
- [x] realtime `process_phase_candidate` implemented without SPOT status or future context.
- [x] Count 0..2 production motion is kept out of `production_stable`; general rows use `process_segment_id`, and eligible changeover lifecycles carry one `changeover_candidate_id` through `production_stabilizing`.
- [x] CSV logger runtime state supplies recent production motion, count hold duration, and previous operator context.
- [x] v2.3/v2.4 schema constants split and feature-flagged at file-open time.
- [x] known v2.3/v2.4 header transitions roll over instead of mixing schemas in one CSV.
- [x] v2.4 metadata records active schema, rule versions, feature flag state, and promotion bundle metadata.
- [x] `spot_observation_fact.py` emits idempotent per-poll facts and isolates writer failure through failure count plus JSONL retry spool.
- [x] `changeover_candidate_resolution_fact.py` emits candidate resolution and process phase event facts.
- [x] post-hoc changeover facts ignore legacy/polluted idle-only IDs; general idle/production intervals belong to `process_segment_id` segment analysis.
- [x] `pre_changeover_hold_candidate` only confirms post-hoc when later Count reset, operator context change, or die-change marker evidence exists; otherwise it is `posthoc_rejected`.
- [x] repeated lifecycle candidate IDs can span non-contiguous realtime rows and still produce one terminal lifecycle fact; unrelated general segments use `process_segment_id` instead.
- [x] `scripts/infer_process_phase_events_for_csv.py` is gated by `PROCESS_PHASE_EVENT_FACT_ENABLED` and never mutates the source CSV.
- [x] `scripts/validate_csv_v2_shadow.py` supports `2.4.0` while preserving `2.1.0` through `2.3.0` checks.

### 2.3 Review Follow-ups Closed

- [x] BLOCK-1: realtime process phase now receives runtime production-motion/count/operator-context state.
- [x] BLOCK-2: process phase event fact generation is gated behind `PROCESS_PHASE_EVENT_FACT_ENABLED`.
- [x] NONBLOCK-1: unrelated local harness dirty state was separated into local branch `codex/preserve-harness-skill-local-20260625`, and the PR branch working tree was restored to clean.
- [x] NONBLOCK-2: PDCA report generated in this document.
- [x] NONBLOCK-3: mypy coverage expanded to v2.4 operational/fact modules.

---

## 3. Deviations from Design

### 3.1 Aggregate Counters Implemented

Read-only v2.4 operational aggregate counters are exposed through `/health` under `spot_temperature.v2_4_operational`. The runtime summary records rows by `temperature_output_status`, rows by `temperature_unavailable_reason`, sentinel counts by `spot_device_status_code`, stale threshold breach count, observation fact link failure count, observation fact write failure count, and process phase candidate counts.

### 3.2 Promotion Bundle Guard Implemented

The three promotion flags have concrete runtime or CLI effects:

```text
CSV_V2_OPERATIONAL_FIELDS_ENABLED=true
SPOT_OBSERVATION_FACT_ENABLED=true
PROCESS_PHASE_EVENT_FACT_ENABLED=true
```

Runtime config loading now rejects partial combinations. Operators must enable all three flags together for v2.4 promotion or disable all three to stay on the default-off path.

### 3.3 Operational Promotion Not Claimed

This report closes implementation evidence for PR #68. It does not claim production operational truth promotion, alert suppression, legacy `Temperature_quality` semantic promotion, or ML input readiness.

---

## 4. Metrics

| Metric | Value |
|--------|-------|
| Latest bkit analyze match rate | 90% |
| Latest bkit analyze iteration | 9 |
| Manual follow-up coverage | 100% |
| Manual follow-up iteration | 10 |
| Canonical design items implemented after follow-up | 20 / 20 |
| Follow-up implementation diff | 7 tracked files updated |
| Pre-report implementation HEAD | `35122cbb0f69bfa6adeb952a2fef7d0728723cb6` |
| PDCA report commit | `1973bc54008ad7878e71a339b34b0c11f7ace4c0` |
| CI at report time | `Build Windows artifacts` PASS |
| Merge state at report time | `CLEAN` |
| Local working tree before report | clean |

---

## 5. Validation Evidence

### 5.1 Local Checks

The following checks are recorded in the analysis and follow-up validation history.

```text
npm --prefix frontend run lint: PASS
npm --prefix frontend run typecheck: PASS
npm --prefix frontend run build: PASS, existing Vite warnings only
.\backend\.venv\Scripts\python.exe -m ruff check backend scripts: PASS
.\backend\.venv\Scripts\python.exe -m mypy: PASS, 5 source files after NONBLOCK-3
C:\Python312\python.exe -m pytest backend\tests\test_temperature_operational.py backend\tests\test_process_phase.py backend\tests\test_changeover_candidate_resolution_fact.py backend\tests\test_spot_observation_fact.py backend\tests\test_csv_v2_4_operational_contract.py backend\tests\test_infer_process_phase_events_for_csv.py -q: PASS, 28 passed
node scripts\run_backend_unittest.cjs: PASS, 250 tests
```

### 5.2 Source Replay Evidence

The analysis records validator PASS on three local v2.3 source CSV files totaling 109,010 rows:

- `Factory_Integrated_Log_v2_20260624_105757.csv`: 6,577 rows
- `Factory_Integrated_Log_v2_20260624_112050.csv`: 7,153 rows
- `Factory_Integrated_Log_v2_20260624_114532.csv`: 95,280 rows

The CSV files remain local evidence only and are intentionally ignored because they are large operational data artifacts.

### 5.3 GitHub Evidence

- PR: https://github.com/zzocojoa/SmartFactoryLogger/pull/68
- Check: `Build Windows artifacts` PASS
- Merge state: `CLEAN`

### 5.4 Post-merge Full-bundle Server Smoke

Evidence level: `[operator-provided evidence]`. The following server-PC smoke results were provided by the operator after PR #68 was merged to `master` as `b5a0a82ba943caca7c513c412a4cdbce53397c03`. Raw operational artifacts were not committed to this repository, so this section records the provided PowerShell output and does not re-label it as direct local verification.

Server runtime and promotion bundle:

- `[operator-provided evidence]` NSIS-built `smart-factory-logger-v2 Setup 1.0.11.exe` was installed and executed on the server PC.
- `[operator-provided evidence]` `/health` reported `runtime_kind=frozen`, packaged frontend resources ready, REAL mode PLC/SPOT connectivity healthy, and `spot_temperature.v2_4_operational.enabled=true`.
- `[operator-provided evidence]` server `config.ini` had all three promotion flags enabled together:
  - `csv_v2_operational_fields_enabled = true`
  - `spot_observation_fact_enabled = true`
  - `process_phase_event_fact_enabled = true`
- `[operator-provided evidence]` `/health` v2.4 counters reported `schema_version=2.4.0`, increasing rows, `observation_fact_enabled=true`, `observation_fact_write_failure_count=0`, `observation_fact_link_failure_count=0`, and `stale_threshold_breach_count=0`.

CSV and fact outputs:

- `[operator-provided evidence]` `spot_observation_fact.csv` existed, was growing, had no failed spool file, and its latest sampled rows had `spot_poll_status=success` plus `spot_raw_validity=valid_temperature`.
- `[operator-provided evidence]` realtime CSV `Factory_Integrated_Log_v2_20260625_154904.csv` contained all required v2.4 headers checked during smoke:
  - `schema_version`
  - `temperature_output_status`
  - `temperature_unavailable_reason`
  - `process_phase_candidate`
  - `spot_observation_key`
- `[operator-provided evidence]` latest sampled realtime CSV rows `6140` through `6144` reported `schema_version=2.4.0`, `temperature_output_status=valid`, non-empty `process_phase_candidate=idle_candidate`, non-empty `process_segment_id`, blank `changeover_candidate_id`, and non-empty `spot_observation_key`.
- `[operator-provided evidence]` sidecar metadata parsed as JSON with `schema_metadata.schema_version=2.4.0`, `spot_temperature_shadow_metadata.schema_version=2.4.0`, and promotion bundle flags all `true`.

Verdict: PASS for the controlled three-flag full-bundle server smoke. This validates server installation, frozen runtime startup, v2.4 operational health counters, realtime v2.4 CSV field emission, SPOT observation fact emission, and sidecar metadata readability under the enabled promotion bundle.

Scope note: This smoke does not claim downstream consumer compatibility, legacy `Temperature_quality` semantic promotion, alerting policy changes, or ML input readiness.

---

## 6. Learnings

1. v2.3 shadow instrumentation should remain evidence, not operational truth. The v2.4 fields make this boundary explicit without breaking existing consumers.
2. Sentinel raw status and row-time operational status must stay separate. Stale precedence prevents old `under_range` or `over_range` observations from being treated as current state.
3. Fact tables are safer than widening realtime rows indefinitely. Per-poll SPOT facts and post-hoc process phase facts preserve lineage without mutating source CSV.
4. Feature flags need both runtime behavior and rollout policy. This PR now rejects partial v2.4 promotion flag combinations during runtime config loading.
5. Type-check coverage should follow new operational modules as they are added. The mypy scope now includes the v2.4 operational/fact modules.

---

## 7. Follow-up Items

- [x] Add first-class v2.4 aggregate counters to `/health` before declaring long-running operational observability complete.
- [x] Add runtime config guardrails so partial promotion flag combinations cannot be accidentally used in production rollout.
- [x] Run controlled server-PC promotion smoke with all three promotion flags enabled together. Evidence level: [operator-provided evidence].
- [x] Split `process_segment_id` from `changeover_candidate_id`; `production_stabilizing` is now the terminal lifecycle candidate for eligible changeover IDs.
- [ ] Verify downstream v2.4 consumer compatibility before any legacy `Temperature_quality` semantic promotion.
- [ ] Keep rollback drill documented: disable `CSV_V2_OPERATIONAL_FIELDS_ENABLED` and roll over to v2.3-compatible output if v2.4 consumers fail.

---

### 7.1 Downstream Consumer Replay Gate

This gate is mandatory after merge and before broader operational promotion because v2.4 now appends `process_segment_id` and adds `production_stabilizing` to `process_phase_candidate`.

Required server-PC evidence:

1. Install the NSIS build produced from the merged commit.
2. Enable the full promotion bundle together: `CSV_V2_OPERATIONAL_FIELDS_ENABLED=true`, `SPOT_OBSERVATION_FACT_ENABLED=true`, and `PROCESS_PHASE_EVENT_FACT_ENABLED=true`.
3. Run the server-PC full-bundle smoke again and capture `/health`, `/stats`, latest v2.4 CSV header, sidecar metadata parse, and fact-file presence.
4. Run each downstream CSV consumer against the latest server-PC v2.4 CSV and matching `.metadata.json` sidecar.
5. Record the consumer name/version, input CSV path, input row count, rejected row count, exit status, and whether the consumer accepted both `process_segment_id` and `production_stabilizing`.

PowerShell evidence collection scaffold:

```powershell
$dir = "$env:APPDATA\SmartFactoryLogger\logs\test_data"
$csv = Get-ChildItem $dir -Filter "Factory_Integrated_Log_v2*.csv" -File |
  Where-Object { $_.Length -gt 0 } |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
$metadata = [System.IO.Path]::ChangeExtension($csv.FullName, ".metadata.json")

$header = Get-Content -LiteralPath $csv.FullName -First 1 -Encoding UTF8
@(
  "schema_version",
  "temperature_output_status",
  "process_phase_candidate",
  "process_segment_id",
  "changeover_candidate_id",
  "spot_observation_key"
) | ForEach-Object {
  [pscustomobject]@{ field = $_; present = $header.Contains($_) }
}

Get-Content -LiteralPath $metadata -Raw -Encoding UTF8 |
  ConvertFrom-Json |
  Select-Object -ExpandProperty schema_metadata |
  Select-Object schema_version,active_schema_version,promotion_bundle_required_flags

Import-Csv -LiteralPath $csv.FullName |
  Select-Object -Last 20 schema_version,sample_seq,process_phase_candidate,process_segment_id,changeover_candidate_id,spot_observation_key
```

Replay PASS criteria:

- latest server-PC CSV is `schema_version=2.4.0` and contains `process_segment_id`.
- sidecar metadata parses as JSON and records all three promotion flags as `true`.
- downstream consumer exits successfully with zero rejected rows caused by exact column count or unknown enum values.
- at least one replay sample or synthetic fixture proves the consumer does not fail on `process_phase_candidate=production_stabilizing`.
- if any consumer fails, rollback is to disable the full v2.4 promotion bundle and roll over to v2.3-compatible output before production use.

Current PR local evidence: generated v2.4 consumer replay with `process_segment_id`, `changeover_candidate_id`, `process_phase_candidate`, and `production_stabilizing` passed `scripts.validate_csv_v2_shadow.validate`. This local validator replay is not a substitute for server-PC downstream consumer replay.

Post-merge local evidence update, 2026-06-26:

- PR #70 merged to `master` at `bd2a64dd3a054eff490b8beffba1d593ac008886`.
- The merged commit produced `dist/smart-factory-logger-v2 Setup 1.0.11.exe` with SHA-256 `57CA33C6E12EAF9CBF4BB8A8A7ED05AE341901F4EE08116FD74872F65F257329`.
- Operator-provided server-PC install smoke for the new build reported `/health` with `app_version=1.0.11`, `runtime_kind=frozen`, and `/dashboard` HTTP 200.
- Local checked-in CSV replay passed `scripts/validate_csv_v2_shadow.py --v2-glob docs/data/Factory_Integrated_Log_v2_*.csv --metadata-glob docs/data/Factory_Integrated_Log_v2_*.metadata.json` across three fixture pairs.
- Local internal consumer replay passed `scripts/infer_process_segments_for_csv.py` on `docs/data/Factory_Integrated_Log_v2_20260624_105757.csv` with `process_segment_fact_rows=25`.
- Local full-bundle internal consumer replay passed `scripts/infer_process_phase_events_for_csv.py` on the same fixture with zero generated event rows, which is expected because that fixture predates v2.4 realtime process-phase columns.
- A synthetic v2.4 CSV fixture containing `process_phase_candidate=production_stabilizing`, `process_segment_id`, and `changeover_candidate_id` passed `validate_v2_4_operational_invariants` with zero failures.
- The same synthetic fixture passed `scripts/infer_process_phase_events_for_csv.py`; output confirmed `process_phase_confirmed=production_stabilizing` and `resolution_reason=production_stabilizing_mapped_posthoc`.
- The same synthetic fixture passed `scripts/infer_process_segments_for_csv.py` with `process_segment_fact_rows=3`.
- Operator-provided server-PC full-bundle evidence after installing the PR #70 build reported `schema_version=2.4.0`, promotion flags enabled, metadata and fact file present, and healthy `/stats`. However, the selected latest server CSV `Factory_Integrated_Log_v2_20260626_000000.csv` did not contain `process_segment_id` in the header, so the downstream replay gate remained FAIL.
- Local follow-up fixed the schema rollover recognition path so prior v2 prefix-compatible headers can roll over to the current `2.4.0` header instead of blocking same-day migration to `process_segment_id`.
- PR #71 merged to `master` at `ba3090a374bb20d13ef936186bc3e935c24f3736` with CI `Build Windows artifacts` success.
- A first local PR #71 installer attempt with SHA-256 `61D25C984DDD7E59D5B05CDDE99348B21FC119A02CFB55D8BAFD120EE2C5E32F` was invalid for server replay because `npm run dist` packaged the stale `backend/dist/SmartFactoryBackend.exe` from 2026-06-25 15:38:40.
- Operator-provided server-PC evidence for that stale-backend installer still showed no `process_segment_id` in the latest CSV candidates, including newly created `Factory_Integrated_Log_v2_20260626_112930.csv`; the downstream replay gate remained FAIL.
- Corrected build order is backend PyInstaller first, then NSIS: `backend/.venv/Scripts/python.exe -m PyInstaller --noconfirm --clean build_specs/SmartFactoryBackend.spec` from `backend/`, then `npm run dist` from `v2_next/`.
- The corrected backend executable `backend/dist/SmartFactoryBackend.exe` was rebuilt at 2026-06-26 11:36:56 with SHA-256 `8833596CD7865AD148EF1FE243055485FC67214BAF6682554A67C705372E7FCA`.
- The corrected NSIS installer was rebuilt at 2026-06-26 11:37:53 with SHA-256 `200FF781FE0385ACA0EEB623004365924BE751477C24C1C8BACD9D6266C31C94`; this supersedes the `61D25C...` installer.
- Operator-provided server-PC evidence after installing the corrected `200FF781...` installer reported `runtime_kind=frozen` and `executable_mtime=2026-06-26T11:37:50`.
- Corrected server-PC full-bundle smoke PASS: `spot_temperature.v2_4_operational.enabled=true`, `schema_version=2.4.0`, `rows_total=450`, `observation_fact_enabled=true`, `observation_fact_link_failure_count=0`, and `observation_fact_write_failure_count=0`.
- Corrected server-PC CSV header PASS: `Factory_Integrated_Log_v2_20260626_114019.csv` was selected as the current-header CSV, its sidecar metadata and `spot_observation_fact.csv` existed, and the header contained `process_segment_id`, `changeover_candidate_id`, and `spot_observation_key`.
- Corrected server-PC row sample PASS: latest sampled rows `444` through `453` had `schema_version=2.4.0`, `temperature_output_status=valid`, `process_phase_candidate=production_stable`, non-empty `process_segment_id=seg_f2752e5385d5c615`, blank `changeover_candidate_id`, and non-empty `spot_observation_key`. Phase counts were `production_stable=452` and `unknown=1`.
- Corrected server-PC metadata PASS: `schema_version=2.4.0`, `active_schema_version=2.4.0`, and all promotion bundle flags were `true`.
- Remaining gap: run every real downstream CSV consumer against the corrected current-header server CSV and record consumer name/version, input path, row count, exit status, rejected row count, and handling of `process_segment_id` plus `production_stabilizing` before broader operational promotion.

---

## 8. Related Documents

- `docs/01-plan/features/spot-temperature-v2-4-operational-patch.plan.md`
- `docs/02-design/features/spot-temperature-v2-4-operational-patch.design.md`
- `docs/03-analysis/spot-temperature-v2-4-operational-patch.analysis.md`
- `docs/04-report/spot-temperature-state-labeling.report.md`
- `docs/04-report/spot-temperature-final-report/SPOT_Temperature_Report.html`
- `docs/04-report/spot-temperature-final-report/source_note.json`

---

## 9. Closure Verdict

PDCA report phase is complete for the PR #68 implementation scope.

This report closes the implementation evidence and records the post-merge controlled server-PC smoke PASS from operator-provided evidence. The remaining item before broader operational promotion is downstream v2.4 consumer compatibility, plus the existing rollback path if v2.4 consumers fail.
