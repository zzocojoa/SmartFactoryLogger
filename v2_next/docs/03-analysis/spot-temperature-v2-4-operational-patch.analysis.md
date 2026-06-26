# Gap Analysis: spot-temperature-v2-4-operational-patch

> Date: 2026-06-25 KST | Re-run after BLOCK-1/BLOCK-2 follow-ups
> Design: docs/02-design/features/spot-temperature-v2-4-operational-patch.design.md v1.1.1
> Scope: post-implementation gap analysis against the current branch
> bkit Analyze Iteration: 9
> Analyzed Branch/Ref: codex/spot-temperature-v2-4-operational-implementation @ c7f7bc35a9c1ccd66880651b3277d8ee422861a9
> Worktree Dirty During Analysis: true (pre-existing local `.gitignore`/`.agents/skills/harness` changes were present and excluded from PR commits)
> Analysis Command: $pdca analyze spot-temperature-v2-4-operational-patch via `bkit_init` + `bkit_pdca_analyze`

---

## Verdict

Implementation is ready for pre-landing review and PR creation. The branch now implements the v2.4 operational CSV contract while preserving the PR #65 v2.3 sentinel and cache-suppression invariants.

Blocking gaps were not found in the implemented P0/P1 contract:

- v2.3/v2.4 schema constants are split.
- `CSV_V2_OPERATIONAL_FIELDS_ENABLED` selects the active v2 file contract at file-open time.
- known v2.3/v2.4 header transitions roll over instead of mixing schemas in one CSV.
- `temperature_operational.py` reuses `temperature_state.py` for transport/freshness/cache decisions.
- stale row precedence overrides old raw sentinel status while preserving raw SPOT metadata.
- realtime `process_phase_candidate` does not use SPOT status or future context.
- Count 0..2 production motion is gated as `setup_alignment_candidate`; general rows use `process_segment_id`, and eligible changeover lifecycles keep one `changeover_candidate_id` through `production_stabilizing`.
- candidate resolution and confirmed process phase event facts are separate from realtime rows.
- `pre_changeover_hold_candidate` post-hoc confirmation now requires future evidence; false general-stop candidates become `posthoc_rejected`, and idle/production segment IDs no longer create confirmed changeover events.
- `spot_observation_fact.py` emits idempotent per-poll facts and isolates writer failure with failure count plus local JSONL retry spool.
- `scripts/infer_process_phase_events_for_csv.py` emits fact outputs without mutating source CSV only when `PROCESS_PHASE_EVENT_FACT_ENABLED=true`.
- `scripts/validate_csv_v2_shadow.py` validates v2.4 operational fields while preserving v2.3 checks.

## Match Rate

Tool execution result: 90%.
Manual follow-up audit: 100%.

The latest actual `bkit_pdca_analyze` result recorded by the tool remains 90% / iteration 9. The two remaining non-blocking gaps were then closed manually and verified with targeted tests, so the manual follow-up audit is 20 implemented items / 20 canonical design items. This manual score is not presented as a new `bkit_pdca_analyze` return value.

```text
v2.3 baseline preservation: 7/7
v2.4 operational deliverables: 13/13
overall design match: 20/20 = 100%
```

This is a post-follow-up implementation score. The previous remaining 10% is now closed by `/health` aggregate counters and runtime promotion bundle guardrails.

## PDCA Tool Execution Evidence

Latest analyze execution was run after BLOCK-1 and BLOCK-2 follow-up commits were pushed to PR #68.

```text
bkit_init(projectDir="C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next"): PASS
bkit_pdca_analyze(feature="spot-temperature-v2-4-operational-patch"): PASS
returned_matchRate=90
returned_iterationCount=9
returned_analysisPath=docs/03-analysis/spot-temperature-v2-4-operational-patch.analysis.md
analyzed_head=c7f7bc35a9c1ccd66880651b3277d8ee422861a9
status_side_effect=docs/.pdca-status.json updated to phase=check, matchRate=90, iterationCount=9, lastUpdated=2026-06-25T01:14:34.070Z
```

Follow-up note: the two remaining non-blocking implementation gaps were closed after this tool run. `docs/.pdca-status.json` keeps the actual tool result as `matchRate=90`, `iterationCount=9`, and records the 100% / iteration 10 result under `manualFollowUp`.

## Re-Run Evidence

Implemented files and behavior now present:

- `backend/FacilityData/temperature_operational.py`
- `backend/FacilityData/process_phase.py`
- `backend/FacilityData/changeover_candidate_resolution_fact.py`
- `backend/FacilityData/spot_observation_fact.py`
- `scripts/infer_process_phase_events_for_csv.py`
- v2.4 unit and contract tests under `backend/tests/test_*v2_4*`, `test_temperature_operational.py`, `test_process_phase.py`, `test_changeover_candidate_resolution_fact.py`, and `test_spot_observation_fact.py`
- `backend/FacilityData/repository.py` exposes `CSV_SCHEMA_VERSION_V2_3`, `CSV_SCHEMA_VERSION_V2_4`, `V2_3_CSV_COLUMNS`, `V2_4_OPERATIONAL_COLUMNS`, and `V2_4_CSV_COLUMNS`
- `scripts/validate_csv_v2_shadow.py` supports `2.1.0`, `2.2.0`, `2.3.0`, and `2.4.0`
- config flags exist for `CSV_V2_OPERATIONAL_FIELDS_ENABLED`, `SPOT_OBSERVATION_FACT_ENABLED`, and `PROCESS_PHASE_EVENT_FACT_ENABLED`

## Verification Summary

Commands run after implementation:

```text
npm --prefix frontend run lint: PASS
npm --prefix frontend run typecheck: PASS
npm --prefix frontend run build: PASS, with existing Vite chunk-size/module-type warnings
.\backend\.venv\Scripts\python.exe -m ruff check backend scripts: PASS
.\backend\.venv\Scripts\python.exe -m mypy: PASS
C:\Python312\python.exe -m pytest backend\tests\test_process_phase.py backend\tests\test_csv_v2_4_operational_contract.py backend\tests\test_temperature_operational.py backend\tests\test_changeover_candidate_resolution_fact.py backend\tests\test_spot_observation_fact.py -q: 21 passed
C:\Python312\python.exe -m pytest backend\tests\test_infer_process_phase_events_for_csv.py backend\tests\test_changeover_candidate_resolution_fact.py -q: 5 passed
node scripts\run_backend_unittest.cjs: 250 tests OK
C:\Python312\python.exe scripts\validate_csv_v2_shadow.py --v2 docs\data\Factory_Integrated_Log_v2_20260624_105757.csv --metadata docs\data\Factory_Integrated_Log_v2_20260624_105757.metadata.json: PASS, 6,577 rows
C:\Python312\python.exe scripts\validate_csv_v2_shadow.py --v2 docs\data\Factory_Integrated_Log_v2_20260624_112050.csv --metadata docs\data\Factory_Integrated_Log_v2_20260624_112050.metadata.json: PASS, 7,153 rows
C:\Python312\python.exe scripts\validate_csv_v2_shadow.py --v2 docs\data\Factory_Integrated_Log_v2_20260624_114532.csv --metadata docs\data\Factory_Integrated_Log_v2_20260624_114532.metadata.json: PASS, 95,280 rows
$env:CSV_V2_OPERATIONAL_FIELDS_ENABLED="true"; $env:SPOT_OBSERVATION_FACT_ENABLED="true"; $env:PROCESS_PHASE_EVENT_FACT_ENABLED="true"; C:\Python312\python.exe scripts\infer_process_phase_events_for_csv.py --input docs\data\Factory_Integrated_Log_v2_20260624_105757.csv --resolution-output C:\tmp\sfl-v2-4-resolution-facts-smoke.csv --event-output C:\tmp\sfl-v2-4-process-events-smoke.csv: PASS
```

The three local v2.3 source CSV files total 109,010 rows and remain local evidence only. They are intentionally ignored rather than committed because they are large operational data artifacts.

## Canonical Item Mapping

| # | Canonical item | Current status |
|---:|---|---|
| 1 | PR #65 sentinel classification baseline | implemented |
| 2 | invalid sentinel cache suppression baseline | implemented |
| 3 | immutable SPOT snapshot metadata baseline | implemented |
| 4 | v2.3 SPOT shadow CSV columns | implemented |
| 5 | v2.3 validator sentinel checks | implemented |
| 6 | post-hoc process segment fact separation | implemented |
| 7 | CSV formula escaping for existing text fields | implemented |
| 8 | operational adapter reusing `temperature_state.py` | implemented |
| 9 | v2.4 output status and unavailable reason fields | implemented |
| 10 | realtime expectedness candidate and post-hoc confirmed expectedness | implemented |
| 11 | under-range cause candidate, confidence, and evidence fields | implemented |
| 12 | row-time freshness and stale precedence | implemented |
| 13 | realtime process phase candidate without future context | implemented |
| 14 | candidate resolution fact and process phase event fact split | implemented |
| 15 | explicit `spot_observation_key` | implemented |
| 16 | idempotent `spot_observation_fact` with diagnostics and writer failure isolation | implemented |
| 17 | v2.3/v2.4 schema constants and feature-flag rollover | implemented |
| 18 | v2.4 metadata contract and promotion bundle metadata | implemented |
| 19 | v2.3/v2.4 validator support | implemented |
| 20 | synthetic, source replay, schema rollover, lifecycle, and recovery tests | implemented |

## Remaining Gaps

The previous aggregate counter and partial promotion guard gaps are now closed in code. `/health` exposes first-class `spot_temperature.v2_4_operational` counters, and runtime config loading rejects partial promotion flag combinations. Operational rollout should still set all three flags together:

```text
CSV_V2_OPERATIONAL_FIELDS_ENABLED=true
SPOT_OBSERVATION_FACT_ENABLED=true
PROCESS_PHASE_EVENT_FACT_ENABLED=true
```

## Non-Blocking Risks

- Frontend build still reports existing Vite chunk-size warnings. This branch does not change frontend bundles, so it is not a blocker.
- v2.4 operational fields are behind feature flags and default off. This protects existing v2.3 consumers but means production evidence requires an explicit promotion bundle deployment.
- `/health` aggregate counters now exist, but production promotion still needs controlled server-PC smoke with the full flag bundle enabled.

## Merge Readiness

The branch is ready for PR creation if the final code review gates remain clean:

- no new sentinel regression;
- no mixed v2.3/v2.4 CSV header append;
- no source CSV mutation by post-hoc scripts;
- working tree clean after staging/commit;
- CI passes on the PR branch.
