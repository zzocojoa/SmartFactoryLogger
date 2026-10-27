import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.FacilityData.persistence_trace import PersistenceTraceWriter


class PersistenceTraceTests(unittest.TestCase):
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
