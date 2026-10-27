import json
from pathlib import Path
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch

from backend.FacilityData.persistence_trace import AdmissionRejectionLedger, PersistenceTraceWriter


class PersistenceTraceTests(unittest.TestCase):
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
        self.assertEqual(summary["rejection_range_count"], 4096)
        self.assertEqual(summary["omitted_rejection_count"], 1)
        self.assertEqual(summary["first_omitted_producer_seq"], 12291)
        self.assertEqual(summary["last_omitted_producer_seq"], 12291)
        ranges = ledger.rejection_ranges()
        self.assertEqual(len(ranges), 4096)
        self.assertEqual([(item.first_sequence, item.last_sequence) for item in ranges],
                         [(index * 3 + 3, index * 3 + 3) for index in range(4096)])
        ledger.record(12292, "REJECTED_LIMIT", "pending_byte_limit", 1)
        after = ledger.snapshot()
        self.assertTrue(after["details_incomplete"])
        self.assertEqual(after["rejected_count"], 4098)
        self.assertEqual(after["omitted_rejection_count"], 2)
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
