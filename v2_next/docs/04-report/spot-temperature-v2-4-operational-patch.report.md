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
- [x] Count 0..2 production motion is kept out of `production_stable` through the startup promotion gate; Count 3 remains eligible for stable promotion.
- [x] CSV logger runtime state supplies recent production motion, count hold duration, and previous operator context.
- [x] v2.3/v2.4 schema constants split and feature-flagged at file-open time.
- [x] known v2.3/v2.4 header transitions roll over instead of mixing schemas in one CSV.
- [x] v2.4 metadata records active schema, rule versions, feature flag state, and promotion bundle metadata.
- [x] `spot_observation_fact.py` emits idempotent per-poll facts and isolates writer failure through failure count plus JSONL retry spool.
- [x] `changeover_candidate_resolution_fact.py` emits candidate resolution and process phase event facts.
- [x] repeated candidate ids are split by contiguous occurrence and sample sequence to avoid merging unrelated candidate windows.
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
- `[operator-provided evidence]` latest sampled realtime CSV rows `6140` through `6144` reported `schema_version=2.4.0`, `temperature_output_status=valid`, non-empty `process_phase_candidate=idle_candidate`, and non-empty `spot_observation_key`.
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
- [ ] Design `production_stabilizing` as a separate future enum only after reviewing CSV schema, validator, and downstream consumer compatibility.
- [ ] Verify downstream v2.4 consumer compatibility before any legacy `Temperature_quality` semantic promotion.
- [ ] Keep rollback drill documented: disable `CSV_V2_OPERATIONAL_FIELDS_ENABLED` and roll over to v2.3-compatible output if v2.4 consumers fail.

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
