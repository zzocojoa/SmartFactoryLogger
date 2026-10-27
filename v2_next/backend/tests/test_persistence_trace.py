import json
from pathlib import Path
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch

from backend.FacilityData.persistence_trace import AdmissionRejectionLedger, AdmissionRejectionRange, PersistenceTraceWriter
from backend.FacilityData.persistence_validation import validate_csv_persistence_trace


class PersistenceTraceTests(unittest.TestCase):
    def test_csv_trace_parser_rejects_malformed_or_unbounded_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            writer = PersistenceTraceWriter(Path(folder), "parser-fixture")
            writer.append({"kind": "admission_summary", "produced_count": 1, "accounted_count": 1,
                           "unaccounted_count": 0, "accepted_count": 1, "excluded_count": 0, "rejected_count": 0,
                           "after_producer_seq": 0, "last_producer_seq": 1, "outcome_counts": {"ACCEPTED": 1},
                           "details_incomplete": False})
            self.assertTrue(writer.flush(force=True))
            path = next(Path(folder).glob("*.trace.jsonl"))
            original = path.read_bytes()
            header, summary = original.splitlines(keepends=True)
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
                    contents = header + (json.dumps(amended) + "\n").encode("utf-8")
                    path.write_bytes(contents)
                    result = validate_csv_persistence_trace([path])
                    self.assertEqual(result["status"], "INCOMPLETE")
                    self.assertIn(issue, result["issues"])
                    self.assertEqual(result["data_integrity_status"], "NOT_EVALUATED")
                    self.assertEqual(path.read_bytes(), contents)
            cases = [
                (original[:-1], "INCOMPLETE", "incomplete_segment"),
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
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "workspace-producer")
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
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PersistenceTraceWriter(root, "producer-fixture")
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
