import csv
import tempfile
import unittest
from pathlib import Path

from backend.FacilityData.spot_observation_fact import (
    SpotObservationFactWriter, summarize_spot_observation_fact, build_spot_observation_fact_manifest,
)
from scripts.validate_csv_v2_shadow import validate_spot_observation_fact_manifest


class PerServicePollTests(unittest.TestCase):
    def test_schema_archive_resets_incremental_bounds_and_previous_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "facts.csv"
            writer = SpotObservationFactWriter(path)
            for service, seq in [("previous", 1), ("A", 10)]:
                writer.write_fact({"spot_service_instance_id": service, "spot_poll_seq": seq,
                                   "spot_last_poll_completed_at": "2026-09-09T00:00:00Z"})
            path.write_text("legacy_header\nlegacy_value\n", encoding="utf-8")
            writer.write_fact({"spot_service_instance_id": "A", "spot_poll_seq": 20,
                               "spot_last_poll_completed_at": "2026-09-09T00:00:00Z"})
            runtime = writer.manifest_summary()
            for summary in [runtime, SpotObservationFactWriter(path).manifest_summary(),
                            summarize_spot_observation_fact(fact_path=path)]:
                self.assertEqual(summary["row_count"], 1)
                self.assertEqual((summary["first_poll_seq"], summary["last_poll_seq"], summary["poll_seq_gap_count"]), (20, 20, 0))
                self.assertEqual(set(summary["per_service_poll_ranges"]), {"A"})
            self.assertEqual(len(list(Path(tmp).glob("*.schema-mismatch.csv"))), 1)

    def test_empty_single_restart_duplicate_and_invalid_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spot_observation_fact.csv"
            writer = SpotObservationFactWriter(path)
            writer.ensure_initialized()
            self.assertEqual(writer.manifest_summary()["poll_seq_gap_count"], 0)
            self.assertEqual(summarize_spot_observation_fact(fact_path=path)["per_service_poll_ranges"], {})
            snapshot = {"spot_service_instance_id": "A", "spot_poll_seq": 9,
                        "spot_last_poll_completed_at": "2026-09-09T00:00:00Z"}
            writer.write_fact(snapshot)
            writer.write_fact(snapshot)
            restarted = SpotObservationFactWriter(path)
            restarted.write_fact(snapshot)
            self.assertEqual(restarted.manifest_summary()["row_count"], 1)
            self.assertEqual(restarted.manifest_summary()["poll_seq_gap_count"], 0)
            for service, seq in [(None, 1), (True, 1), ("", 1), ("A:B", 1), (" A", 1),
                                 ("A", None), ("A", True), ("A", 0), ("A", -1), ("A", 1.1),
                                 ("A", "bad"), ("A", 2**64)]:
                self.assertIsNone(restarted.write_fact(dict(snapshot, spot_service_instance_id=service, spot_poll_seq=seq)))
            self.assertEqual(restarted.invalid_input_count, 12)
            self.assertEqual(restarted.manifest_summary()["row_count"], 1)

    def test_persisted_duplicate_and_invalid_rows_reported_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spot_observation_fact.csv"
            writer = SpotObservationFactWriter(path)
            writer.write_fact({"spot_service_instance_id": "A", "spot_poll_seq": 1,
                               "spot_last_poll_completed_at": "2026-09-09T00:00:00Z"})
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream); header = reader.fieldnames; row = next(reader)
            with path.open("a", encoding="utf-8", newline="") as stream:
                out = csv.DictWriter(stream, fieldnames=header)
                out.writerow(row)
                out.writerow(dict(row, spot_service_instance_id="", spot_observation_key="bad-key"))
            runtime = SpotObservationFactWriter(path).manifest_summary()
            offline = summarize_spot_observation_fact(fact_path=path)
            for summary in [runtime, offline]:
                self.assertEqual(summary["duplicate_observation_key_count"], 1)
                self.assertEqual(summary["invalid_poll_identity_count"], 1)
                self.assertEqual(summary["poll_seq_gap_count"], 0)

    def test_manifest_summary_does_not_rescan_historical_poll_sets(self):
        class NoIterationSet(set):
            def __iter__(self):
                raise AssertionError("per-poll summary must not rescan the entire poll history")
        with tempfile.TemporaryDirectory() as tmp:
            writer = SpotObservationFactWriter(Path(tmp) / "facts.csv")
            for seq in range(100, 0, -1):
                writer.write_fact({"spot_service_instance_id": "A", "spot_poll_seq": seq,
                                   "spot_last_poll_completed_at": "2026-09-09T00:00:00Z"})
            writer._polls_by_service = {key: NoIterationSet(value) for key, value in writer._polls_by_service.items()}
            writer._seen_poll_sequences = NoIterationSet(writer._seen_poll_sequences)
            summary = writer.manifest_summary()
            self.assertEqual((summary["first_poll_seq"], summary["last_poll_seq"], summary["poll_seq_gap_count"]), (1, 100, 0))

    def test_each_service_observed_range_runtime_reload_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "facts.csv"
            writer = SpotObservationFactWriter(path)
            for service, seq in [("A", 3), ("B", 1), ("A", 1), ("B", 3), ("B", 2)]:
                writer.write_fact({"spot_service_instance_id": service, "spot_poll_seq": seq,
                                   "spot_last_poll_completed_at": "2026-09-09T00:00:00Z"})
            self.assertEqual(writer.manifest_summary()["row_count"], 5)
            for summary in [writer.manifest_summary(), SpotObservationFactWriter(path).manifest_summary(),
                            summarize_spot_observation_fact(fact_path=path),
                            build_spot_observation_fact_manifest(fact_path=path, enabled=True)]:
                with self.subTest(kind=summary.get("schema_version", "summary")):
                    self.assertEqual(summary["poll_seq_gap_count"], 1)
                    self.assertEqual(summary["row_count"], 5)
            manifest = build_spot_observation_fact_manifest(fact_path=path, enabled=True)
            self.assertEqual(manifest["per_service_poll_ranges"]["A"]["poll_seq_gap_count"], 1)
            # Offline validator uses the same per-service aggregation, independently rereading bytes.
            metadata = {"spot_observation_fact_manifest": manifest}
            failures, summary = validate_spot_observation_fact_manifest(
                metadata, Path(tmp) / "sample.metadata.json", ["spot_observation_key"], [])
            self.assertEqual(failures, [])
            self.assertEqual(summary["spot_observation_fact_actual_poll_seq_gap_count"], "1")
