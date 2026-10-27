import json
import os
from pathlib import Path
import sqlite3
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch

from backend.FacilityData.persistence_trace import AdmissionRejectionLedger, AdmissionRejectionRange, PersistenceTraceWriter
from backend.FacilityData.persistence_validation import validate_csv_persistence_trace
from backend.FacilityData.freshness import clock_domain_id


class PersistenceTraceTests(unittest.TestCase):
    def test_trace_probe_close_failure_blocks_reuse(self):
        clock, handles = [100.0], []
        original_open = Path.open
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "close-uncertain", clock=lambda: clock[0])
            writer.append({"kind": "first"})
            self.assertTrue(writer.flush(force=True))
            final, = root.glob("*.trace.jsonl")
            original = final.read_bytes()

            class UnclosedRead:
                def __init__(self, handle):
                    self.handle = handle

                def fileno(self):
                    return self.handle.fileno()

                def close(self):
                    raise OSError("injected read handle close uncertainty")

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    self.close()

            def open_file(path, *args, **kwargs):
                handle = original_open(path, *args, **kwargs)
                if path == final:
                    handles.append(handle)
                    return UnclosedRead(handle)
                return handle

            try:
                with patch.object(Path, "open", open_file):
                    clock[0] = 101.0
                    writer.probe_storage()
                    state = writer.snapshot()
                    self.assertTrue(state["manual_recovery_required"],
                                    "unclosed trace access handle did not block automatic reuse")
                    self.assertEqual(state["unresolved_access_handle_count"], 1)
                    self.assertTrue(state["incomplete"])
                    self.assertIsNone(state["next_probe_monotonic"])
                    self.assertIsNone(writer.append({"kind": "later"}))
                    self.assertFalse(writer.flush(force=True))
                    clock[0] = 1000.0
                    writer.probe_storage()
                    self.assertEqual(len(handles), 1)
                    self.assertFalse(handles[0].closed)
            finally:
                for handle in handles:
                    handle.close()
            self.assertEqual(final.read_bytes(), original)

    def test_new_trace_records_cannot_bypass_failed_required_file(self):
        clock, denied, attempts = [100.0], [True], []
        original_open = Path.open
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "required-file-retry", clock=lambda: clock[0])
            writer.append({"kind": "first"})
            self.assertTrue(writer.flush(force=True))
            final, = root.glob("*.trace.jsonl")
            original = final.read_bytes()

            def open_file(path, *args, **kwargs):
                if path == final and denied[0]:
                    attempts.append(clock[0])
                    raise PermissionError("injected required trace access failure")
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", open_file):
                clock[0] = 101.0
                writer.probe_storage()
                self.assertEqual(writer.snapshot()["current_storage_availability"], "blocked")
                writer.append({"kind": "second"})
                clock[0] = 101.5
                self.assertFalse(writer.flush(force=True),
                                 "new trace record bypassed a failed required file")
                self.assertEqual(attempts, [101.0])
                clock[0] = 102.0
                self.assertFalse(writer.flush(force=True))
                self.assertEqual(attempts, [101.0, 102.0])
                self.assertEqual(len(list(root.glob("*.trace.jsonl"))), 1)
                self.assertEqual(list(root.glob("*.pending")), [])
                self.assertEqual(writer.snapshot()["pending_records"], 1)
                denied[0] = False
                clock[0] = 103.0
                self.assertTrue(writer.flush(force=True))
            state = writer.snapshot()
            self.assertEqual(state["current_storage_availability"], "available")
            self.assertEqual(state["failure_count"], 1)
            self.assertEqual(state["probe_failure_count"], 1)
            self.assertEqual(state["pending_records"], 0)
            self.assertEqual(final.read_bytes(), original)
            kinds = [json.loads(line)["kind"] for path in sorted(root.glob("*.trace.jsonl"))
                     for line in path.read_text(encoding="utf-8").splitlines()[1:]]
            self.assertEqual(kinds, ["first", "second"])

    def test_trace_probe_preserves_changed_publication(self):
        for change in ("replace", "delete", "edit"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                clock = [100.0]
                root = Path(folder)
                writer = PersistenceTraceWriter(root, "owned-publication", clock=lambda: clock[0])
                writer.append({"kind": "first"})
                self.assertTrue(writer.flush(force=True))
                final, = root.glob("*.trace.jsonl")
                original = final.read_bytes()
                if change == "replace":
                    final.rename(root / "original-retained")
                    final.write_bytes(original)
                elif change == "delete":
                    final.unlink()
                else:
                    info = final.stat()
                    final.write_bytes(b"x" * len(original))
                    os.utime(final, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))
                after_change = {path.name: path.read_bytes() for path in root.iterdir()}
                clock[0] = 101.0
                writer.probe_storage()
                state = writer.snapshot()
                self.assertTrue(state["manual_recovery_required"],
                                "directory success concealed a changed trace publication")
                self.assertEqual(state["current_storage_availability"], "blocked")
                self.assertTrue(state["incomplete"])
                self.assertIsNone(state["next_probe_monotonic"])
                self.assertIsNone(writer.append({"kind": "later"}))
                self.assertFalse(writer.flush(force=True))
                clock[0] = 1000.0
                writer.probe_storage()
                self.assertEqual(state["probe_failure_count"], writer.snapshot()["probe_failure_count"])
                self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, after_change)

    def test_trace_retry_cap_and_reset_preserve_pending_bytes(self):
        clock, calls = [100.0], []
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "retry-cap", clock=lambda: clock[0])
            writer.append({"kind": "first"})

            def failed_publish(source, target):
                calls.append(clock[0])
                raise PermissionError("injected extended publication outage")

            with patch.object(Path, "replace", failed_publish):
                original = None
                for count, delay in enumerate((1., 2., 4., 8., 16., 30., 30.), 1):
                    self.assertFalse(writer.flush(force=True))
                    state = writer.snapshot()
                    self.assertEqual(state["failure_count"], count)
                    self.assertEqual(state["retry_delay_seconds"], delay)
                    next_retry = clock[0] + delay
                    self.assertEqual(state["next_retry_monotonic"], next_retry)
                    pending = next(root.glob("*.pending"))
                    original = pending.read_bytes() if original is None else original
                    self.assertEqual(pending.read_bytes(), original)
                    clock[0] = next_retry - .001
                    self.assertFalse(writer.flush(force=True))
                    self.assertEqual(len(calls), count)
                    clock[0] = next_retry
            self.assertTrue(writer.flush(force=True))
            self.assertEqual(writer.snapshot()["failure_count"], 7)
            writer.append({"kind": "second"})
            with patch.object(Path, "replace", failed_publish):
                self.assertFalse(writer.flush(force=True))
            state = writer.snapshot()
            self.assertEqual(state["retry_delay_seconds"], 1.)
            self.assertEqual(state["next_retry_monotonic"], clock[0] + 1.)
            self.assertEqual(state["failure_count"], 8)
            clock[0] += 1.
            self.assertTrue(writer.flush(force=True))
            records = [json.loads(line)["kind"] for path in sorted(root.glob("*.trace.jsonl"))
                       for line in path.read_text(encoding="utf-8").splitlines()[1:]]
            self.assertEqual(records, ["first", "second"])

    def test_trace_retry_backoff_is_not_bypassed_by_new_records(self):
        clock, attempts, failed = [100.0], [], [True]
        original_replace = Path.replace
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "retry-clock", clock=lambda: clock[0])

            def controlled_publish(source, target):
                attempts.append(clock[0])
                if failed[0]:
                    raise PermissionError("injected trace publication outage")
                return original_replace(source, target)

            with patch.object(Path, "replace", controlled_publish):
                writer.append({"kind": "first"})
                self.assertFalse(writer.flush(force=True))
                clock[0] = 100.99
                writer.append({"kind": "second"})
                self.assertFalse(writer.flush(force=True))
                self.assertEqual(attempts, [100.0], "new record or forced flush bypassed trace retry backoff")
                self.assertEqual(writer.snapshot()["next_retry_monotonic"], 101.0)
                clock[0] = 101.0
                self.assertFalse(writer.flush())
                self.assertEqual(attempts, [100.0, 101.0])
                self.assertEqual(writer.snapshot()["next_retry_monotonic"], 103.0)
                self.assertEqual(writer.snapshot()["current_storage_availability"], "blocked")
                clock[0] = 102.99
                writer.append({"kind": "third"})
                failed[0] = False
                self.assertFalse(writer.flush(force=True))
                self.assertEqual(attempts, [100.0, 101.0])
                clock[0] = 103.0
                self.assertTrue(writer.flush())
                state = writer.snapshot()
                self.assertEqual(state["failure_count"], 2)
                self.assertEqual(state["pending_recovery"], 0)
                self.assertEqual(state["pending_records"], 2)
                self.assertEqual(state["current_storage_availability"], "available")
                self.assertEqual(state["availability_scope"], "last_trace_publication")
                self.assertEqual(state["last_success_monotonic"], 103.0)
                self.assertIsNone(state["next_retry_monotonic"])
                self.assertEqual(state["retry_delay_seconds"], 1.0)
                self.assertTrue(writer.flush())
            records = [json.loads(line)["kind"] for path in sorted(root.glob("*.trace.jsonl"))
                       for line in path.read_text(encoding="utf-8").splitlines()[1:]]
            self.assertEqual(records, ["first", "second", "third"])
            self.assertEqual(writer.snapshot()["pending_records"], 0)

    def test_uncertain_trace_stays_held_after_external_repair(self):
        clock = [100.0]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "manual-recovery", clock=lambda: clock[0])
            writer.append({"kind": "first"})
            with patch.object(Path, "replace", side_effect=PermissionError("injected temporary outage")):
                self.assertFalse(writer.flush(force=True))
            pending = next(root.glob("*.pending"))
            original = pending.read_bytes()
            pending.write_bytes(b"uncertain partial bytes\n")
            clock[0] = 101.0
            self.assertFalse(writer.flush(force=True))
            self.assertTrue(writer.snapshot()["incomplete"])
            # Matching bytes supplied externally do not authorize this owner
            # to clear a previously observed uncertain-write condition.
            pending.write_bytes(original)
            self.assertFalse(writer.flush(force=True),
                             "uncertain trace resumed automatically after external repair")
            state = writer.snapshot()
            self.assertTrue(state["manual_recovery_required"])
            self.assertIsNone(state["next_retry_monotonic"])
            self.assertEqual(state["current_storage_availability"], "blocked")
            self.assertEqual(state["admission_blocked_reason"], "trace_manual_recovery")
            self.assertEqual(state["pending_records"], 1)
            self.assertEqual(state["pending_recovery"], 1)
            self.assertEqual(state["failure_count"], 2)
            self.assertIsNone(writer.append({"kind": "later"}))
            self.assertEqual(writer.snapshot()["pending_records"], 1)
            self.assertEqual(pending.read_bytes(), original)
            self.assertEqual(list(root.glob("*.trace.jsonl")), [])

    def test_trace_stage_clocks_survive_failure_and_new_segment(self):
        clock = [100.0]
        with tempfile.TemporaryDirectory() as folder:
            writer = PersistenceTraceWriter(Path(folder), "clock-run", clock=lambda: clock[0])
            self.assertIsNone(writer.snapshot().get("oldest_pending_monotonic"))
            writer.append({"kind": "first"})
            clock[0] = 100.6
            writer.append({"kind": "second"})
            initial = writer.snapshot()
            self.assertEqual(initial.get("oldest_pending_monotonic"), 100.0,
                             "trace evidence age has no first-record monotonic clock")
            self.assertEqual(initial["stage_due_monotonic"], 101.0)
            self.assertEqual(initial["pending_recovery"], 0)
            self.assertEqual(initial["clock_domain"], clock_domain_id())
            with patch.object(Path, "replace", side_effect=PermissionError("injected publish outage")):
                self.assertFalse(writer.flush(force=True))
            pending = next(Path(folder).glob("*.pending"))
            original = pending.read_bytes()
            clock[0] = 105.0
            writer.append({"kind": "third"})
            with patch.object(Path, "open", side_effect=AssertionError("snapshot performed file I/O")):
                failed = writer.snapshot()
            self.assertEqual(failed["oldest_pending_monotonic"], 100.0)
            self.assertEqual(failed["stage_due_monotonic"], 100.6,
                             "forced early publication did not preserve its original due time")
            self.assertEqual(failed["pending_records"], 3)
            self.assertEqual(failed["pending_recovery"], 2)
            self.assertEqual(pending.read_bytes(), original)
            clock[0] = 105.2
            self.assertTrue(writer.flush(force=True))
            recovered = writer.snapshot()
            self.assertEqual(recovered["oldest_pending_monotonic"], 105.0)
            self.assertEqual(recovered["stage_due_monotonic"], 106.0)
            self.assertEqual(recovered["pending_recovery"], 0)
            self.assertEqual(recovered["failure_count"], 1)
            clock[0] = 106.0
            self.assertTrue(writer.flush())
            empty = writer.snapshot()
            self.assertIsNone(empty["oldest_pending_monotonic"])
            self.assertIsNone(empty["stage_due_monotonic"])
            self.assertEqual(empty["pending_records"], 0)
            records = [json.loads(line)["kind"] for path in sorted(Path(folder).glob("*.trace.jsonl"))
                       for line in path.read_text(encoding="utf-8").splitlines()[1:]]
            self.assertEqual(records, ["first", "second", "third"])

    @staticmethod
    def terminal_outcomes(v1_committed=0):
        return {"contract_version": "CSV_PERSISTENCE_OUTCOMES_V1", "coverage": "TERMINAL_REQUIRED_SINK_COUNTS",
                "accepted_event_count": v1_committed, "fully_committed_event_count": v1_committed,
                "failed_event_count": 0, "outstanding_event_count": 0, "counts_reconciled": True,
                "sinks": {"csv_v1": {"accepted_count": v1_committed, "committed_count": v1_committed,
                                     "failed_count": 0, "outstanding_count": 0},
                          "csv_v2": {"accepted_count": 0, "committed_count": 0, "failed_count": 0, "outstanding_count": 0}}}

    def test_validator_rejects_missing_trace_segment(self):
        with tempfile.TemporaryDirectory() as folder:
            writer = PersistenceTraceWriter(Path(folder), "segment-run")
            writer.append({"kind": "producer_start", "after_producer_seq": 0})
            self.assertTrue(writer.flush(force=True))
            writer.append({"kind": "config_activated", "config_generation": 1})
            self.assertTrue(writer.flush(force=True))
            writer.append({"kind": "producer_stop", "final_producer_seq": 0})
            writer.append({"kind": "admission_summary", "produced_count": 0, "accounted_count": 0,
                           "unaccounted_count": 0, "accepted_count": 0, "excluded_count": 0, "rejected_count": 0,
                           "after_producer_seq": 0, "last_producer_seq": 0, "outcome_counts": {},
                           "details_incomplete": False, "required_sink_outcomes": self.terminal_outcomes()})
            self.assertTrue(writer.flush(force=True))
            paths = sorted(Path(folder).glob("*.trace.jsonl"))
            self.assertEqual(len(paths), 3)
            self.assertEqual(validate_csv_persistence_trace(paths)["issues"], [])
            original = {path: path.read_bytes() for path in paths}
            result = validate_csv_persistence_trace([paths[0], paths[2]])
            self.assertEqual(result["status"], "INCOMPLETE", "missing trace segment was not rejected")
            self.assertIn("noncontiguous_trace_segments", result["issues"])
            self.assertEqual({path: path.read_bytes() for path in paths}, original)
            self.assertIn("duplicate_trace_segment_id", validate_csv_persistence_trace(paths + [paths[1]])["issues"])
            self.assertEqual(validate_csv_persistence_trace(list(reversed(paths)))["issues"], [])
            header, *body = original[paths[1]].splitlines(keepends=True)
            for value, issue in [(True, "invalid_trace_segment_id"), (0, "invalid_trace_segment_id"),
                                 ("2", "invalid_trace_segment_id"), (1, "duplicate_trace_segment_id"),
                                 (2**70, "noncontiguous_trace_segments")]:
                with self.subTest(segment_id=value):
                    contents = (json.dumps(dict(json.loads(header), segment_id=value)) + "\n").encode() + b"".join(body)
                    paths[1].write_bytes(contents)
                    result = validate_csv_persistence_trace(paths)
                    self.assertEqual(result["status"], "INCOMPLETE")
                    self.assertIn(issue, result["issues"])
                    self.assertEqual(paths[1].read_bytes(), contents)
            paths[1].write_bytes(original[paths[1]])

    def test_validator_reconciles_ranges_without_expanding_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            writer = PersistenceTraceWriter(Path(folder), "range-run")
            records = [
                {"kind": "producer_start", "after_producer_seq": 0},
                {"kind": "csv_admission", "contract_version": "CSV_ADMISSION_EVENT_V1",
                 "producer_instance_id": "range-run", "producer_seq": 1, "status": "ACCEPTED",
                 "config_generation": 1, "source_payload_hash": "0" * 64, "required_sinks": ["csv_v1"]},
                {"kind": "admission_exclusion_range", "contract_version": "CSV_ADMISSION_EXCLUSIONS_V1",
                 "first_producer_seq": 2, "last_producer_seq": 1000001, "status": "DISABLED"},
                {"kind": "admission_rejection_range", "contract_version": "CSV_ADMISSION_REJECTIONS_V1",
                 "first_producer_seq": 1000002, "last_producer_seq": 1000002, "status": "INVALID"},
                {"kind": "producer_stop", "final_producer_seq": 1000002},
                {"kind": "admission_summary", "produced_count": 1000002, "accounted_count": 1000002,
                 "unaccounted_count": 0, "accepted_count": 1, "excluded_count": 1000000, "rejected_count": 1,
                 "after_producer_seq": 0, "last_producer_seq": 1000002,
                 "outcome_counts": {"ACCEPTED": 1, "DISABLED": 1000000, "INVALID": 1}, "details_incomplete": False,
                 "required_sink_outcomes": self.terminal_outcomes(1)},
                {"kind": "csv_row_data", "producer_seq": 1, "sink_id": "csv_v1", "record_version": 1,
                 "config_generation": 1, "source_payload_hash": "0" * 64},
            ]
            records.insert(4, records.pop())
            for record in records:
                self.assertIsNotNone(writer.append(record))
            self.assertTrue(writer.flush(force=True))
            path = next(Path(folder).glob("*.trace.jsonl"))
            original = path.read_bytes()
            tracemalloc.start()
            try:
                result = validate_csv_persistence_trace([path])
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertEqual(result["issues"], [])
            self.assertEqual(result["data_integrity_status"], "NOT_EVALUATED")
            self.assertLess(peak, 2 * 1024**2, "validator expanded excluded IDs into memory")
            header = original.splitlines(keepends=True)[0]
            cases = [
                (1, {"producer_seq": 2}, "overlapping_admission_identities"),
                (1, {"producer_instance_id": "foreign-run"}, "admission_producer_identity_mismatch"),
                (1, {"producer_seq": True}, "invalid_admission_identity"),
                (2, {"status": "INVALID"}, "invalid_admission_identity"),
                (2, {"last_producer_seq": 1}, "invalid_admission_identity"),
                (2, {"contract_version": "unknown"}, "invalid_admission_identity"),
                (3, {"first_producer_seq": 1000003, "last_producer_seq": 1000003},
                 "admission_identity_outside_producer_bounds"),
            ]
            for index, changes, issue in cases:
                with self.subTest(changes=changes):
                    amended = [dict(record) for record in records]
                    amended[index].update(changes)
                    contents = header + b"".join((json.dumps(record) + "\n").encode() for record in amended)
                    path.write_bytes(contents)
                    result = validate_csv_persistence_trace([path])
                    self.assertEqual(result["status"], "INCOMPLETE")
                    self.assertIn(issue, result["issues"])
                    self.assertEqual(path.read_bytes(), contents)
            path.write_bytes(original + (json.dumps(records[1]) + "\n").encode())
            result = validate_csv_persistence_trace([path])
            self.assertIn("overlapping_admission_identities", result["issues"])
            self.assertIn("admission_identity_totals_mismatch", result["issues"])
            for failed in (True, False):
                amended = [dict(record) for record in records if record["kind"] != "csv_row_data"]
                totals = self.terminal_outcomes(1)
                totals["fully_committed_event_count"] = 0
                state = "failed" if failed else "outstanding"
                totals[f"{state}_event_count"] = 1
                totals["sinks"]["csv_v1"]["committed_count"] = 0
                totals["sinks"]["csv_v1"][f"{state}_count"] = 1
                next(record for record in amended if record["kind"] == "admission_summary")["required_sink_outcomes"] = totals
                if failed:
                    amended.insert(4, dict(records[1], kind="csv_processing_failure", contract_version="CSV_PROCESSING_FAILURE_V1",
                                           sink_id="csv_v1", status="FAILED", reason="fixture_processing_failure"))
                path.write_bytes(header + b"".join((json.dumps(record) + "\n").encode() for record in amended))
                result = validate_csv_persistence_trace([path])
                self.assertNotIn("terminal_output_counts_mismatch", result["issues"])
                self.assertIn("recorded_csv_processing_failure" if failed else "missing_required_sink_evidence", result["issues"])
            path.write_bytes(original)
            with patch("backend.FacilityData.persistence_validation.sqlite3.connect",
                       side_effect=sqlite3.OperationalError("fixture workspace unavailable")):
                result = validate_csv_persistence_trace([path])
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertIn("validator_workspace_unavailable", result["issues"])
            self.assertEqual(path.read_bytes(), original)

    def test_validator_rejects_foreign_segment_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            writer = PersistenceTraceWriter(Path(folder), "run-a")
            writer.append({"kind": "producer_start", "after_producer_seq": 0})
            self.assertTrue(writer.flush(force=True))
            writer.append({"kind": "producer_stop", "final_producer_seq": 0})
            self.assertTrue(writer.flush(force=True))
            writer.append({"kind": "admission_summary", "produced_count": 0, "accounted_count": 0,
                           "unaccounted_count": 0, "accepted_count": 0, "excluded_count": 0, "rejected_count": 0,
                           "after_producer_seq": 0, "last_producer_seq": 0, "outcome_counts": {},
                           "details_incomplete": False, "required_sink_outcomes": self.terminal_outcomes()})
            self.assertTrue(writer.flush(force=True))
            paths = sorted(Path(folder).glob("*.trace.jsonl"))
            self.assertEqual(len(paths), 3)
            self.assertEqual(validate_csv_persistence_trace(paths)["issues"], [])
            header, *records = paths[1].read_bytes().splitlines(keepends=True)
            foreign = dict(json.loads(header), producer_instance_id="run-b")
            contents = (json.dumps(foreign) + "\n").encode() + b"".join(records)
            paths[1].write_bytes(contents)
            result = validate_csv_persistence_trace(paths)
            self.assertEqual(result["status"], "INCOMPLETE", "foreign trace segment was not rejected")
            self.assertIn("mixed_producer_identity", result["issues"])
            self.assertEqual(paths[1].read_bytes(), contents)
            for changes, issue in [({"writer_instance_id": "foreign-writer"}, "mixed_writer_identity"),
                                   ({"producer_instance_id": None}, "invalid_segment_identity"),
                                   ({"writer_instance_id": ""}, "invalid_segment_identity")]:
                with self.subTest(changes=changes):
                    amended = (json.dumps(dict(json.loads(header), **changes)) + "\n").encode() + b"".join(records)
                    paths[1].write_bytes(amended)
                    result = validate_csv_persistence_trace(paths)
                    self.assertEqual(result["status"], "INCOMPLETE")
                    self.assertIn(issue, result["issues"])
                    self.assertEqual(paths[1].read_bytes(), amended)
            paths[1].write_bytes(header + b"".join(records))
            self.assertEqual(validate_csv_persistence_trace(list(reversed(paths)))["issues"], [])

    def test_csv_trace_parser_rejects_malformed_or_unbounded_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            writer = PersistenceTraceWriter(Path(folder), "parser-fixture")
            writer.append({"kind": "producer_start", "after_producer_seq": 0})
            writer.append({"kind": "csv_admission", "contract_version": "CSV_ADMISSION_EVENT_V1",
                           "producer_instance_id": "parser-fixture", "producer_seq": 1, "status": "ACCEPTED",
                           "config_generation": 1, "source_payload_hash": "0" * 64, "required_sinks": ["csv_v1"]})
            writer.append({"kind": "csv_row_data", "producer_seq": 1, "sink_id": "csv_v1", "record_version": 1,
                           "config_generation": 1, "source_payload_hash": "0" * 64})
            writer.append({"kind": "producer_stop", "final_producer_seq": 1})
            writer.append({"kind": "admission_summary", "produced_count": 1, "accounted_count": 1,
                           "unaccounted_count": 0, "accepted_count": 1, "excluded_count": 0, "rejected_count": 0,
                           "after_producer_seq": 0, "last_producer_seq": 1, "outcome_counts": {"ACCEPTED": 1},
                           "details_incomplete": False, "required_sink_outcomes": self.terminal_outcomes(1)})
            self.assertTrue(writer.flush(force=True))
            path = next(Path(folder).glob("*.trace.jsonl"))
            original = path.read_bytes()
            header, start, admission, data, stop, summary = original.splitlines(keepends=True)
            prefix = header + start + admission + data + stop
            result = validate_csv_persistence_trace([path])
            self.assertEqual(result["status"], "NOT_EVALUATED")
            self.assertEqual(result["issues"], [])
            self.assertEqual(result["data_integrity_status"], "NOT_EVALUATED")
            self.assertEqual(path.read_bytes(), original)
            valid_summary = json.loads(summary)
            total_cases = [
                ({"accepted_count": True}, "invalid_admission_totals"),
                ({"excluded_count": -1}, "invalid_admission_totals"),
                ({"accounted_count": "1"}, "invalid_admission_totals"),
                ({"outcome_counts": {"ACCEPTED": True}}, "invalid_admission_status_counts"),
                ({"outcome_counts": {"UNKNOWN": 1}}, "invalid_admission_status_counts"),
                ({"outcome_counts": {}}, "admission_status_totals_mismatch"),
                ({"produced_count": 2, "last_producer_seq": 2, "unaccounted_count": 1}, "unaccounted_producer_ids"),
                ({"last_producer_seq": 2}, "admission_totals_mismatch"),
                ({"details_incomplete": True}, "reported_admission_detail_loss"),
            ]
            for changes, issue in total_cases:
                with self.subTest(summary_changes=changes):
                    amended = dict(valid_summary, **changes)
                    contents = prefix + (json.dumps(amended) + "\n").encode("utf-8")
                    path.write_bytes(contents)
                    result = validate_csv_persistence_trace([path])
                    self.assertEqual(result["status"], "INCOMPLETE")
                    self.assertIn(issue, result["issues"])
                    self.assertEqual(result["data_integrity_status"], "NOT_EVALUATED")
                    self.assertEqual(path.read_bytes(), contents)
            cases = [
                (original[:-1], "INCOMPLETE", "incomplete_segment"),
                (header + start + summary, "INCOMPLETE", "missing_producer_stop"),
                (header + start + start + stop + summary, "INCOMPLETE", "multiple_producer_start"),
                (header + start + stop + stop + summary, "INCOMPLETE", "multiple_producer_stop"),
                (header + start + b'{"kind":"producer_stop","final_producer_seq":2}\n' + summary,
                 "INCOMPLETE", "producer_boundary_mismatch"),
                (header + start + b'{"kind":"producer_stop","final_producer_seq":true}\n' + summary,
                 "INCOMPLETE", "invalid_producer_boundary"),
                (header + summary + summary, "INCOMPLETE", "multiple_admission_summaries"),
                (header + b'{"kind":"admission_summary","kind":"admission_summary"}\n', "INCOMPLETE", "invalid_trace_record"),
                (b'{"schema_version":1,"schema_version":1}\n' + summary, "INCOMPLETE", "invalid_segment_header"),
                (b'{"schema_version":2}\n' + summary, "NOT_EVALUATED", "unsupported_trace_schema"),
                (b'{"schema_version":true}\n' + summary, "NOT_EVALUATED", "unsupported_trace_schema"),
                (header + b'{}\n' * 1001, "INCOMPLETE", "segment_record_limit"),
            ]
            for contents, status, issue in cases:
                with self.subTest(issue=issue, contents_prefix=contents[:45]):
                    path.write_bytes(contents)
                    result = validate_csv_persistence_trace([path])
                    self.assertEqual(result["status"], status)
                    self.assertIn(issue, result["issues"])
                    self.assertEqual(result["data_integrity_status"], "NOT_EVALUATED")
                    self.assertEqual(path.read_bytes(), contents)
            path.write_bytes(b" " * (8 * 1024**2))
            tracemalloc.start()
            try:
                result = validate_csv_persistence_trace([path])
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertIn("segment_byte_limit", result["issues"])
            self.assertLess(peak, 2 * 1024**2, "trace validator read the entire oversized segment")
            missing = validate_csv_persistence_trace([Path(folder) / "missing.trace.jsonl"])
            self.assertEqual(missing["status"], "INCOMPLETE")
            self.assertIn("trace_read_error", missing["issues"])
            self.assertEqual(validate_csv_persistence_trace([])["status"], "NOT_EVALUATED")

    def test_exclusion_ranges_share_capacity_without_becoming_rejections(self):
        ledger = AdmissionRejectionLedger()
        with patch("backend.FacilityData.persistence_trace.ADMISSION_REJECTION_RANGE_LIMIT", 2):
            ledger.record(1, "DISABLED", "auto_save_disabled", 1)
            ledger.record(2, "DISABLED", "auto_save_disabled", 1)
            ledger.record(3, "INVALID", "bad_input", 1)
            ledger.record(4, "DISABLED", "auto_save_disabled", 2)
            before = ledger.snapshot()
            self.assertEqual(before["pending_exclusion_count"], 2)
            self.assertEqual(before["pending_rejection_count"], 1)
            self.assertEqual(before["outcome_range_count"], 2)
            self.assertEqual(before["exclusion_range_count"], 1)
            self.assertEqual(before["rejection_range_count"], 1)
            self.assertEqual(before["omitted_exclusion_count"], 1)
            self.assertEqual(before["omitted_rejection_count"], 0)
            self.assertEqual(before["first_omitted_exclusion_seq"], 4)
            self.assertEqual(before["last_omitted_exclusion_seq"], 4)
            self.assertTrue(before["details_incomplete"])
            first = ledger.claim_range()
            self.assertEqual((first.first_sequence, first.last_sequence, first.status), (1, 2, "DISABLED"))
            ledger.stage_range(first, 7)
            ledger.acknowledge_committed(6)
            self.assertEqual(ledger.snapshot()["pending_exclusion_count"], 2)
            ledger.acknowledge_committed(7)
            self.assertEqual(ledger.snapshot()["committed_exclusion_count"], 2)
            self.assertEqual(ledger.snapshot()["committed_rejection_count"], 0)
            ledger.record(5, "DISABLED", "auto_save_disabled", 2)
            second = ledger.claim_range()
            self.assertEqual(second.status, "INVALID")
            ledger.stage_range(second, 8)
            third = ledger.claim_range()
            self.assertEqual((third.first_sequence, third.last_sequence), (5, 5))
            ledger.stage_range(third, 8)
            ledger.acknowledge_committed(8)
            ledger.acknowledge_committed(8)
            final = ledger.snapshot()
            self.assertEqual(final["excluded_count"], 4)
            self.assertEqual(final["rejected_count"], 1)
            self.assertEqual(final["committed_exclusion_count"], 3)
            self.assertEqual(final["committed_rejection_count"], 1)
            self.assertEqual(final["committed_outcome_count"], 4)
            self.assertEqual(final["pending_outcome_count"], 0)
            self.assertEqual(final["outcome_range_count"], 0)
            self.assertEqual(final["omitted_outcome_count"], 1)
            self.assertTrue(final["details_incomplete"])

    def test_staged_rejection_ranges_wait_for_their_trace_commit(self):
        ledger = AdmissionRejectionLedger()
        with patch("backend.FacilityData.persistence_trace.ADMISSION_REJECTION_RANGE_LIMIT", 2):
            ledger.record(1, "INVALID", "bad_input", 1)
            ledger.record(2, "REJECTED_FULL", "queue_full", 1)
            first = ledger.claim_range()
            ledger.stage_range(first, 4)
            second = ledger.claim_range()
            self.assertIsNot(second, first, "staged evidence did not allow the next rejection range")
            self.assertEqual((second.first_sequence, second.last_sequence), (2, 2))
            ledger.stage_range(second, 5)
            ledger.record(3, "INVALID", "bad_input", 1)
            self.assertEqual(ledger.snapshot()["omitted_rejection_count"], 1)
            ledger.acknowledge_committed(3)
            self.assertEqual(ledger.snapshot()["committed_rejection_count"], 0)
            self.assertEqual(ledger.snapshot()["pending_rejection_count"], 2)
            ledger.acknowledge_committed(4)
            self.assertEqual(ledger.snapshot()["committed_rejection_count"], 1)
            self.assertEqual(ledger.snapshot()["rejection_range_count"], 1)
            ledger.acknowledge_committed(4)
            self.assertEqual(ledger.snapshot()["committed_rejection_count"], 1)
            ledger.record(4, "INVALID", "bad_input", 1)
            third = ledger.claim_range()
            self.assertEqual((third.first_sequence, third.last_sequence), (4, 4))
            ledger.stage_range(third, 5)
            ledger.acknowledge_committed(5)
            state = ledger.snapshot()
            self.assertEqual(state["committed_rejection_count"], 3)
            self.assertEqual(state["committed_rejection_range_count"], 3)
            self.assertEqual(state["pending_rejection_count"], 0)
            self.assertEqual(state["rejection_range_count"], 0)
            self.assertEqual(state["rejected_count"], 4)
            self.assertEqual(ledger.rejection_ranges(), ())
            self.assertTrue(state["details_incomplete"])

    def test_claimed_rejection_ranges_remain_reserved_until_acknowledged(self):
        ledger = AdmissionRejectionLedger()
        with patch("backend.FacilityData.persistence_trace.ADMISSION_REJECTION_RANGE_LIMIT", 2):
            ledger.record(1, "INVALID", "bad_input", 1)
            ledger.record(2, "INVALID", "bad_input", 1)
            first = ledger.claim_range()
            self.assertIsNotNone(first, "rejection range was not frozen for evidence publication")
            ledger.record(3, "INVALID", "bad_input", 1)
            ledger.record(4, "INVALID", "bad_input", 1)
            ledger.record(5, "REJECTED_FULL", "queue_full", 1)
            self.assertEqual((first.first_sequence, first.last_sequence), (1, 2))
            self.assertIs(ledger.claim_range(), first)
            self.assertEqual(ledger.snapshot()["rejection_range_count"], 2)
            self.assertEqual(ledger.snapshot()["pending_rejection_count"], 4)
            self.assertEqual(ledger.snapshot()["omitted_rejection_count"], 1)
            with self.assertRaises(ValueError):
                ledger.acknowledge_range(AdmissionRejectionRange(1, 2, "INVALID", "bad_input", 1))
            self.assertEqual(ledger.snapshot()["committed_rejection_count"], 0)
            ledger.acknowledge_range(first)
            with self.assertRaises(ValueError):
                ledger.acknowledge_range(first)
            self.assertEqual(ledger.snapshot()["rejection_range_count"], 1)
            self.assertEqual(ledger.snapshot()["committed_rejection_count"], 2)
            ledger.record(6, "REJECTED_LIMIT", "pending_byte_limit", 1)
            second = ledger.claim_range()
            self.assertEqual((second.first_sequence, second.last_sequence), (3, 4))
            ledger.acknowledge_range(second)
            third = ledger.claim_range()
            self.assertEqual((third.first_sequence, third.last_sequence), (6, 6))
            ledger.acknowledge_range(third)
            self.assertIsNone(ledger.claim_range())
            closed = ledger.snapshot()
            self.assertEqual(closed["rejected_count"], 6)
            self.assertEqual(closed["committed_rejection_count"], 5)
            self.assertEqual(closed["committed_rejection_range_count"], 3)
            self.assertEqual(closed["pending_rejection_count"], 0)
            self.assertEqual(closed["rejection_range_count"], 0)
            self.assertTrue(closed["details_incomplete"])

    def test_unaccounted_sequences_remain_incomplete_at_close(self):
        ledger = AdmissionRejectionLedger(after_sequence=10)
        ledger.record(11, "ACCEPTED", None, 1)
        ledger.record(13, "INVALID", "bad_input", 1)
        snapshot = ledger.snapshot()
        self.assertTrue(snapshot["details_incomplete"], "unaccounted producer sequence was presented as complete")
        self.assertEqual(snapshot["produced_count"], 3)
        self.assertEqual(snapshot["accounted_count"], 2)
        self.assertEqual(snapshot["unaccounted_count"], 1)
        ledger.close(15)
        closed = ledger.snapshot()
        self.assertEqual(closed["produced_count"], 5)
        self.assertEqual(closed["unaccounted_count"], 3)
        self.assertEqual(closed["accounted_count"], 2)
        self.assertEqual(closed["last_producer_seq"], 15)
        self.assertTrue(closed["details_incomplete"])
        self.assertEqual(closed["outcome_counts"], {"ACCEPTED": 1, "INVALID": 1})
        self.assertEqual(closed["omitted_rejection_count"], 0)
        self.assertEqual([(item.first_sequence, item.last_sequence) for item in ledger.rejection_ranges()], [(13, 13)])

    def test_rejection_ranges_merge_only_adjacent_matching_outcomes(self):
        ledger = AdmissionRejectionLedger()
        receipts = [(1, "INVALID", "bad_value", 7), (2, "INVALID", "bad_value", 7),
                    (3, "ACCEPTED", None, 7), (4, "INVALID", "bad_value", 7),
                    (5, "INVALID", "bad_type", 7), (6, "INVALID", "bad_type", 8),
                    (7, "REJECTED_FULL", "bad_type", 8), (8, "REJECTED_FULL", "bad_type", 8)]
        with patch("backend.FacilityData.persistence_trace.ADMISSION_REJECTION_RANGE_LIMIT", 5):
            for receipt in receipts:
                ledger.record(*receipt)
            ranges = ledger.rejection_ranges()
            self.assertEqual([(item.first_sequence, item.last_sequence) for item in ranges],
                             [(1, 2), (4, 4), (5, 5), (6, 6), (7, 8)],
                             "adjacent equivalent rejections were not compacted")
            self.assertEqual([(item.status, item.reason, item.config_generation) for item in ranges],
                             [("INVALID", "bad_value", 7), ("INVALID", "bad_value", 7),
                              ("INVALID", "bad_type", 7), ("INVALID", "bad_type", 8),
                              ("REJECTED_FULL", "bad_type", 8)])
            self.assertFalse(ledger.snapshot()["details_incomplete"])
            self.assertEqual(ledger.snapshot()["rejected_count"], 7)
            ledger.record(9, "REJECTED_FULL", "queue_full", 8)
            self.assertTrue(ledger.snapshot()["details_incomplete"])
            self.assertEqual(ledger.snapshot()["omitted_rejection_count"], 1)
            self.assertEqual(ledger.rejection_ranges(), ranges)

    def test_rejection_ranges_bound_details_without_losing_counts(self):
        ledger = AdmissionRejectionLedger()
        reasons = (("REJECTED_FULL", "queue_full"), ("REJECTED_LIMIT", "pending_byte_limit"),
                   ("REJECTED_UNAVAILABLE", "unavailable"), ("REJECTED_CLOSED", "closed"),
                   ("INVALID", "invalid"))
        for index in range(4097):
            sequence = index * 3 + 1
            ledger.record(sequence, "ACCEPTED", None, 1)
            ledger.record(sequence + 1, "DISABLED", "auto_save_disabled", 1)
            status, reason = reasons[index % len(reasons)]
            ledger.record(sequence + 2, status, reason, 1)
        summary = ledger.snapshot()
        self.assertTrue(summary["details_incomplete"], "range overflow was presented as complete coverage")
        self.assertEqual(summary["produced_count"], 12291)
        self.assertEqual(summary["accepted_count"], 4097)
        self.assertEqual(summary["excluded_count"], 4097)
        self.assertEqual(summary["rejected_count"], 4097)
        self.assertEqual(sum(summary["outcome_counts"].values()), 12291)
        # Exclusions now share the same retained-range budget; the limit is not doubled.
        self.assertEqual(summary["outcome_range_count"], 4096)
        self.assertEqual(summary["rejection_range_count"], 2048)
        self.assertEqual(summary["exclusion_range_count"], 2048)
        self.assertEqual(summary["omitted_rejection_count"], 2049)
        self.assertEqual(summary["omitted_exclusion_count"], 2049)
        self.assertEqual(summary["first_omitted_producer_seq"], 6147)
        self.assertEqual(summary["last_omitted_producer_seq"], 12291)
        self.assertEqual(summary["first_omitted_exclusion_seq"], 6146)
        self.assertEqual(summary["last_omitted_exclusion_seq"], 12290)
        ranges = ledger.rejection_ranges()
        self.assertEqual(len(ranges), 2048)
        self.assertEqual([(item.first_sequence, item.last_sequence) for item in ranges],
                         [(index * 3 + 3, index * 3 + 3) for index in range(2048)])
        ledger.record(12292, "REJECTED_LIMIT", "pending_byte_limit", 1)
        after = ledger.snapshot()
        self.assertTrue(after["details_incomplete"])
        self.assertEqual(after["rejected_count"], 4098)
        self.assertEqual(after["omitted_rejection_count"], 2050)
        self.assertEqual(after["last_omitted_producer_seq"], 12292)
        self.assertEqual(ledger.rejection_ranges(), ranges, "overflow extended an unrelated retained range")

    def test_unusable_workspace_is_not_transient_pressure(self):
        wide = "x" * 300_000 + "😀"
        for location in ("record", "header"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                writer = PersistenceTraceWriter(root, wide if location == "header" else "wide-record")
                record = {"event_id": 1, "detail": wide if location == "record" else "small"}
                self.assertIsNone(writer.append(record))
                state = writer.snapshot()
                self.assertTrue(state["incomplete"], "unusable workspace was treated as recoverable pressure")
                self.assertEqual(state["last_error"], f"{location}_workspace_too_large")
                self.assertIsNone(state["admission_blocked_reason"])
                self.assertEqual(state["pending_records"], 0)
                self.assertEqual(state["pending_bytes"], 0)
                self.assertEqual(state["refused_count"], 1)
                self.assertTrue(writer.flush(force=True))
                self.assertEqual(list(root.iterdir()), [])
                if location == "record":
                    self.assertIsNotNone(writer.append({"event_id": 2, "detail": "valid"}))
                    self.assertTrue(writer.flush(force=True))
                    files = list(root.glob("*.trace.jsonl"))
                    self.assertEqual(len(files), 1)
                    stored = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()[1:]]
                    self.assertEqual(stored, [{"event_id": 2, "detail": "valid"}])
                    self.assertTrue(writer.snapshot()["incomplete"])

    def test_workspace_pressure_blocks_admission_until_budget_returns(self):
        clock = [100.0]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "workspace-producer", clock=lambda: clock[0])
            detail = "x" * (384 * 1024)
            for sequence in range(4):
                self.assertIsNotNone(writer.append({"event_id": sequence, "detail": detail}))
            state = writer.snapshot()
            self.assertEqual(state["pending_segments"], 2)
            self.assertEqual(state["pending_records"], 4)
            self.assertIsNone(writer.append({"event_id": 4, "detail": detail}))
            state = writer.snapshot()
            self.assertEqual(state["last_error"], "trace_workspace_full")
            self.assertEqual(state["admission_blocked_reason"], "trace_workspace_full",
                             "byte pressure left the producer admission gate open")
            self.assertLessEqual(state["pending_bytes"], 2 * 1024**2)
            original_replace = Path.replace

            def failed_publish(source, target):
                if str(target).endswith(".trace.jsonl"):
                    raise OSError("injected trace storage unavailable")
                return original_replace(source, target)

            with patch.object(Path, "replace", failed_publish):
                self.assertFalse(writer.flush(force=True))
            self.assertEqual(writer.snapshot()["admission_blocked_reason"], "trace_workspace_full")
            self.assertEqual(writer.snapshot()["pending_records"], 4)
            clock[0] = 101.0
            self.assertTrue(writer.flush(force=True))
            self.assertIsNone(writer.snapshot()["admission_blocked_reason"])
            self.assertGreaterEqual(writer.snapshot()["failure_count"], 1)
            self.assertIsNotNone(writer.append({"event_id": 4, "detail": detail}))
            while writer.snapshot()["pending_records"]:
                self.assertTrue(writer.flush(force=True))
            stored = [json.loads(line) for path in sorted(root.glob("*.trace.jsonl"))
                      for line in path.read_text(encoding="utf-8").splitlines()[1:]]
            self.assertEqual(stored, [{"event_id": sequence, "detail": detail} for sequence in range(5)])
            self.assertEqual(writer.snapshot()["pending_bytes"], 0)

    def test_partial_trace_write_is_preserved_without_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "short-write-producer")
            for sequence in range(20):
                self.assertIsNotNone(writer.append({"event_id": sequence}))
            original_open = Path.open
            written = []

            class ShortWriteFile:
                def __init__(self, handle):
                    self.handle = handle

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.handle.close()

                def write(self, payload):
                    count = self.handle.write(payload[:len(payload)//2] if len(written) == 8 else payload)
                    written.append(count)
                    return count

                def flush(self):
                    self.handle.flush()

                def fileno(self):
                    return self.handle.fileno()

            def short_open(path, mode="r", *args, **kwargs):
                handle = original_open(path, mode, *args, **kwargs)
                return ShortWriteFile(handle) if path.suffix == ".pending" and mode == "xb" else handle

            with patch.object(Path, "open", short_open):
                self.assertFalse(writer.flush(force=True))
            self.assertEqual(list(root.glob("*.trace.jsonl")), [], "partially written trace was published")
            pending = list(root.glob("*.pending"))
            self.assertEqual(len(pending), 1)
            original = pending[0].read_bytes()
            complete_lines = original.splitlines()[:8]
            self.assertEqual([json.loads(line)["event_id"] for line in complete_lines[1:]], list(range(7)))
            self.assertEqual(len(written), 9, "writing continued after a short write")
            state = writer.snapshot()
            self.assertTrue(state["incomplete"])
            self.assertEqual(state["last_error"], "trace_short_write")
            self.assertEqual(state["committed_segment_seq"], 0)
            self.assertEqual(state["pending_records"], 20)
            self.assertFalse(writer.flush(force=True))
            self.assertEqual(pending[0].read_bytes(), original)
            self.assertEqual(list(root.glob("*.trace.jsonl")), [])
            self.assertTrue(writer.snapshot()["incomplete"])

    def test_first_record_deadline_is_not_postponed_by_later_records(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            clock = [10.]
            writer = PersistenceTraceWriter(root, "deadline-producer", clock=lambda: clock[0])
            writer.append({"event_id": 1})
            clock[0] = 10.9
            writer.append({"event_id": 2})
            self.assertTrue(writer.flush())
            self.assertEqual(list(root.glob("*.trace.jsonl")), [], "trace flushed before first record deadline")
            self.assertEqual(writer.snapshot()["next_flush_monotonic"], 11.)
            clock[0] = 11.
            self.assertTrue(writer.flush())
            self.assertEqual(writer.snapshot()["pending_records"], 0)
            self.assertIsNone(writer.snapshot()["next_flush_monotonic"])
            files = list(root.glob("*.trace.jsonl"))
            self.assertEqual(len(files), 1)
            self.assertEqual([json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()][1:],
                             [{"event_id": 1}, {"event_id": 2}])
            clock[0] = 11.2
            writer.append({"event_id": 3})
            self.assertEqual(writer.snapshot()["next_flush_monotonic"], 12.2)
            clock[0] = 12.1
            self.assertTrue(writer.flush())
            self.assertEqual(len(list(root.glob("*.trace.jsonl"))), 1)
            clock[0] = 12.2
            self.assertTrue(writer.flush())
            self.assertEqual(len(list(root.glob("*.trace.jsonl"))), 2)

    def test_trace_byte_limits_reject_oversized_records_without_copying(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "byte-producer")
            oversized = {"event_id": "too-large", "detail": "x" * (2 * 1024**2)}
            tracemalloc.start()
            try:
                token = writer.append(oversized)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertIsNone(token, "oversized trace record accepted")
            self.assertLessEqual(peak, 256 * 1024)
            self.assertEqual(writer.snapshot()["pending_bytes"], 0)
            self.assertTrue(writer.snapshot()["incomplete"])
            record = {"event_id": "one", "detail": "x" * (512 * 1024)}
            self.assertIsNotNone(writer.append(record))
            self.assertIsNotNone(writer.append(dict(record, event_id="two")))
            self.assertIsNone(writer.append(dict(record, event_id="three")))
            self.assertLessEqual(writer.snapshot()["pending_bytes"], 2 * 1024**2)
            while writer.snapshot()["pending_records"]:
                self.assertTrue(writer.flush(force=True))
            stored = []
            for path in sorted(root.glob("*.trace.jsonl")):
                self.assertLessEqual(path.stat().st_size, 1024**2)
                stored.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()[1:])
            self.assertEqual([r["event_id"] for r in stored], ["one", "two"])
            self.assertEqual([r["detail"] for r in stored], [record["detail"]] * 2)
            self.assertEqual(writer.snapshot()["pending_bytes"], 0)
            self.assertTrue(writer.snapshot()["incomplete"])

    def test_two_full_segments_refuse_new_records_until_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "bounded-producer")
            tokens = []
            for sequence in range(2000):
                token = writer.append({"event_id": sequence, "sink_id": "csv_v2"})
                self.assertIsNotNone(token)
                tokens.append(token)
            self.assertIsNone(writer.append({"event_id": 2000}), "trace accepted beyond two full segments")
            state = writer.snapshot()
            self.assertEqual(state["pending_segments"], 2)
            self.assertEqual(state["pending_records"], 2000)
            self.assertLessEqual(state["pending_bytes"], 2 * 1024**2)
            self.assertEqual(tokens[:1000], [1] * 1000)
            self.assertEqual(tokens[1000:], [2] * 1000)
            self.assertTrue(writer.flush(force=True))
            self.assertEqual(writer.snapshot()["pending_records"], 1000)
            self.assertIsNotNone(writer.append({"event_id": 2000, "sink_id": "csv_v2"}))
            while writer.snapshot()["pending_records"]:
                self.assertTrue(writer.flush(force=True))
            records = []
            for path in sorted(root.glob("*.trace.jsonl")):
                self.assertLessEqual(path.stat().st_size, 1024**2)
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()][1:]
                self.assertLessEqual(len(rows), 1000)
                records.extend(rows)
            self.assertEqual([r["event_id"] for r in records], list(range(2001)))
            self.assertEqual(writer.snapshot()["pending_bytes"], 0)

    def test_failed_publish_keeps_same_segment_for_retry(self):
        clock = [100.0]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "producer-fixture", clock=lambda: clock[0])
            first = {"event_id": "producer-fixture:1", "sink_id": "csv_v2", "status": "DATA_WRITTEN_EVIDENCE_PENDING"}
            second = dict(first, event_id="producer-fixture:2")
            token1 = writer.append(first)
            token2 = writer.append(second)
            self.assertIsNotNone(token1)
            self.assertEqual(token1, token2)
            original_replace = Path.replace

            def fail_publish(source, target):
                if str(target).endswith(".trace.jsonl"):
                    self.assertGreater(source.stat().st_size, 0)
                    raise OSError("synthetic evidence publish failure")
                return original_replace(source, target)

            with patch.object(Path, "replace", fail_publish):
                self.assertFalse(writer.flush(force=True), "failed evidence publication was reported as committed")
            self.assertEqual(writer.snapshot()["pending_records"], 2)
            self.assertEqual(writer.snapshot()["failure_count"], 1)
            self.assertEqual(list(root.rglob("*.trace.jsonl")), [])
            clock[0] = 101.0
            self.assertTrue(writer.flush(force=True))
            self.assertEqual(writer.snapshot()["pending_records"], 0)
            self.assertEqual(writer.snapshot()["pending_bytes"], 0)
            self.assertEqual(writer.snapshot()["failure_count"], 1)
            files = list(root.rglob("*.trace.jsonl"))
            self.assertEqual(len(files), 1)
            records = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["segment_id"], token1)
            self.assertEqual(records[1:], [first, second])
            self.assertTrue(writer.flush(force=True))
            self.assertEqual(len(list(root.rglob("*.trace.jsonl"))), 1)
