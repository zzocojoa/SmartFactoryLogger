import tempfile
import unittest
from pathlib import Path

from backend.FacilityData.spot_observation_fact import (
    SpotObservationFactWriter,
    build_spot_observation_fact,
    build_spot_observation_key,
)


class SpotObservationFactTests(unittest.TestCase):
    def test_observation_key_is_service_instance_and_poll_seq(self) -> None:
        snapshot = {"spot_service_instance_id": "svc-1", "spot_poll_seq": 42}

        self.assertEqual(build_spot_observation_key(snapshot), "svc-1:42")

    def test_writer_is_idempotent_per_poll_key(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 42,
            "spot_observation_seq": 42,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "450.0",
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            writer = SpotObservationFactWriter(output_path)

            first = writer.write_fact(snapshot)
            second = writer.write_fact(snapshot)

            self.assertIsNotNone(first)
            self.assertIsNone(second)
            rows = output_path.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(len(rows), 2)

    def test_failed_write_spools_and_next_success_flushes_pending_fact(self) -> None:
        failed_snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 7,
            "spot_observation_seq": 7,
            "spot_poll_status": "timeout",
            "spot_raw_validity": "not_received",
        }
        success_snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 8,
            "spot_observation_seq": 8,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "455.0",
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            invalid_parent = tmp_path / "not_a_dir"
            invalid_parent.write_text("occupied", encoding="utf-8")
            spool_path = tmp_path / "spot_observation_fact.failed.jsonl"

            failing_writer = SpotObservationFactWriter(
                invalid_parent / "spot_observation_fact.csv",
                spool_path=spool_path,
            )
            self.assertIsNone(failing_writer.write_fact(failed_snapshot))
            self.assertEqual(failing_writer.failure_count, 1)
            self.assertTrue(spool_path.exists())

            output_path = tmp_path / "spot_observation_fact.csv"
            retrying_writer = SpotObservationFactWriter(output_path, spool_path=spool_path)
            self.assertIsNotNone(retrying_writer.write_fact(success_snapshot))

            rows = output_path.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(len(rows), 3)
            self.assertIn("svc-1:7", rows[1])
            self.assertIn("svc-1:8", rows[2])
            self.assertFalse(spool_path.exists())


    def test_build_fact_uses_missing_diagnostics_status(self) -> None:
        fact = build_spot_observation_fact(
            {
                "spot_service_instance_id": "svc-1",
                "spot_poll_seq": 1,
                "spot_poll_status": "timeout",
                "spot_raw_validity": "not_received",
            }
        )

        self.assertEqual(fact["diagnostics_capture_status"], "missing")
        self.assertEqual(fact["spot_observation_key"], "svc-1:1")


if __name__ == "__main__":
    unittest.main()
