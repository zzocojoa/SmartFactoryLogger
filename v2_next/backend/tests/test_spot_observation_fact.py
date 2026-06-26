import tempfile
import unittest
from pathlib import Path

from backend.FacilityData.spot_observation_fact import (
    SpotObservationFactWriter,
    build_spot_observation_fact,
    build_spot_observation_key,
    derive_spot_diagnostic_evidence_codes,
    encode_spot_diagnostic_evidence_codes,
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

    def test_build_fact_preserves_diagnostics_and_derives_evidence_codes(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 2,
            "spot_poll_status": "success",
            "spot_raw_validity": "invalid_sentinel",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
            "alarmstatus": "LOW SIGNAL",
            "signalpc": "3.2",
            "peak_picker_off_mode": "reset",
            "actuator_scan_state": "scanning",
            "spot_diagnostic_evidence_codes": '["target_absent_verified"]',
        }

        fact = build_spot_observation_fact(snapshot)
        evidence_codes = derive_spot_diagnostic_evidence_codes(snapshot)

        self.assertEqual(fact["diagnostics_capture_status"], "same_response")
        self.assertEqual(fact["diagnostics_age_ms"], "0.0")
        self.assertEqual(fact["alarmstatus"], "LOW SIGNAL")
        self.assertEqual(fact["signalpc"], "3.2")
        self.assertEqual(fact["peak_picker_off_mode"], "reset")
        self.assertEqual(fact["actuator_scan_state"], "scanning")
        self.assertEqual(
            set(evidence_codes),
            {
                "actuator_scanning",
                "alarm_low_signal",
                "peak_picker_off_mode_reset_configured",
                "target_absent_verified",
            },
        )
        self.assertEqual(
            encode_spot_diagnostic_evidence_codes(snapshot),
            '["actuator_scanning","alarm_low_signal","peak_picker_off_mode_reset_configured","target_absent_verified"]',
        )

    def test_numeric_alarmstatus_bit_four_derives_alarm_low_signal(self) -> None:
        self.assertEqual(
            derive_spot_diagnostic_evidence_codes({"alarmstatus": "16"}),
            ("alarm_low_signal",),
        )
        self.assertEqual(
            derive_spot_diagnostic_evidence_codes({"alarmstatus": "0x10"}),
            ("alarm_low_signal",),
        )
        self.assertEqual(derive_spot_diagnostic_evidence_codes({"alarmstatus": "0"}), ())

    def test_signalpc_with_configured_lte_threshold_derives_signal_below_threshold(self) -> None:
        snapshot = {
            "signalpc": "3.2",
            "low_signal_threshold_pc": "5.0",
            "low_signal_comparator": "lte",
        }

        self.assertEqual(derive_spot_diagnostic_evidence_codes(snapshot), ("signal_below_threshold",))
        self.assertEqual(encode_spot_diagnostic_evidence_codes(snapshot), '["signal_below_threshold"]')

    def test_signalpc_threshold_edge_respects_lt_and_lte_comparators(self) -> None:
        lte_snapshot = {
            "signalpc": "5.0",
            "low_signal_threshold_pc": "5.0",
            "low_signal_comparator": "lte",
        }
        lt_snapshot = {
            "signalpc": "5.0",
            "low_signal_threshold_pc": "5.0",
            "low_signal_comparator": "lt",
        }

        self.assertEqual(derive_spot_diagnostic_evidence_codes(lte_snapshot), ("signal_below_threshold",))
        self.assertEqual(derive_spot_diagnostic_evidence_codes(lt_snapshot), ())

    def test_signalpc_without_valid_threshold_or_invalid_value_does_not_set_low(self) -> None:
        cases = [
            {"signalpc": "3.2"},
            {"signalpc": "3.2", "low_signal_threshold_pc": "5.0"},
            {
                "signalpc": "3.2",
                "low_signal_threshold_pc": "5.0",
                "low_signal_comparator": "unknown",
            },
            {
                "signalpc": "5.1",
                "low_signal_threshold_pc": "5.0",
                "low_signal_comparator": "lte",
            },
            {
                "signalpc": "not-a-number",
                "low_signal_threshold_pc": "5.0",
                "low_signal_comparator": "lte",
            },
            {
                "signalpc": "nan",
                "low_signal_threshold_pc": "5.0",
                "low_signal_comparator": "lte",
            },
            {
                "signalpc": "101",
                "low_signal_threshold_pc": "5.0",
                "low_signal_comparator": "lte",
            },
            {
                "signalpc": "3.2",
                "low_signal_threshold_pc": "nan",
                "low_signal_comparator": "lte",
            },
        ]

        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                self.assertEqual(derive_spot_diagnostic_evidence_codes(snapshot), ())


if __name__ == "__main__":
    unittest.main()
