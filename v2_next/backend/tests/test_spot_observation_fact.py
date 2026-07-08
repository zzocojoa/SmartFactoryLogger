import csv
import json
import tempfile
import unittest
from pathlib import Path

from backend.FacilityData.spot_observation_fact import (
    SPOT_OBSERVATION_FACT_COLUMNS,
    SpotObservationFactWriter,
    build_spot_observation_fact,
    build_spot_observation_fact_manifest,
    build_spot_observation_key,
    derive_spot_diagnostic_evidence_codes,
    encode_spot_diagnostic_evidence_codes,
)
from scripts.validate_csv_v2_shadow import validate_spot_observation_fact_invariants


class SpotObservationFactTests(unittest.TestCase):
    def test_observation_key_is_service_instance_and_poll_seq(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 42,
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
        }

        self.assertEqual(build_spot_observation_key(snapshot), "svc-1:42")

    def test_observation_key_requires_positive_poll_seq_completed_at_and_non_startup_state(self) -> None:
        base = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 42,
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
            "spot_poll_status": "success",
        }

        self.assertEqual(build_spot_observation_key({**base, "spot_poll_seq": 0}), "")
        self.assertEqual(build_spot_observation_key({**base, "spot_poll_seq": -1}), "")
        self.assertEqual(build_spot_observation_key({**base, "spot_last_poll_completed_at": ""}), "")
        self.assertEqual(build_spot_observation_key({**base, "spot_poll_status": "not_attempted"}), "")
        self.assertEqual(build_spot_observation_key({**base, "temperature_output_status": "startup_pending"}), "")
        self.assertEqual(build_spot_observation_key({**base, "temperature_status_shadow": "startup_pending"}), "")

    def test_writer_is_idempotent_per_poll_key(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 42,
            "spot_observation_seq": 42,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "450.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
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

    def test_writer_loads_existing_key_index_after_restart(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 42,
            "spot_observation_seq": 42,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "450.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            first_writer = SpotObservationFactWriter(output_path)
            self.assertIsNotNone(first_writer.write_fact(snapshot))

            restarted_writer = SpotObservationFactWriter(output_path)
            self.assertIsNone(restarted_writer.write_fact(snapshot))

            rows = output_path.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(len(rows), 2)

    def test_fact_manifest_summarizes_file_and_realtime_link_coverage(self) -> None:
        base_snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_observation_seq": 1,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "450.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
            "alarmstatus": "0",
            "signalpc": "3.2",
            "d1temperature": "31.0",
            "d2temperature": "31.1",
            "e1out": "1.0",
            "e2out": "1.1",
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            writer = SpotObservationFactWriter(output_path)
            self.assertIsNotNone(writer.write_fact({**base_snapshot, "spot_poll_seq": 1}))
            self.assertIsNotNone(writer.write_fact({**base_snapshot, "spot_poll_seq": 3}))

            manifest = build_spot_observation_fact_manifest(
                fact_path=output_path,
                enabled=True,
                write_failure_count=0,
                spool_pending_count=0,
                realtime_rows=[
                    {"spot_observation_key": "svc-1:1"},
                    {"spot_observation_key": "svc-1:3"},
                    {"spot_observation_key": "svc-1:99"},
                ],
            )

        self.assertTrue(manifest["enabled"])
        self.assertEqual(manifest["schema_version"], "1.2.1")
        self.assertEqual(manifest["row_count"], 2)
        self.assertEqual(manifest["distinct_observation_key_count"], 2)
        self.assertEqual(manifest["first_poll_seq"], 1)
        self.assertEqual(manifest["last_poll_seq"], 3)
        self.assertEqual(manifest["poll_seq_gap_count"], 1)
        self.assertRegex(manifest["sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(manifest["link_coverage"]["realtime_rows_with_observation_key"], 3)
        self.assertEqual(manifest["link_coverage"]["linked_rows"], 2)
        self.assertEqual(manifest["link_coverage"]["missing_fact_key_rows"], 1)
        self.assertEqual(manifest["diagnostic_field_coverage"]["signalpc_nonblank_count"], 2)

    def test_failed_write_spools_and_next_success_flushes_pending_fact(self) -> None:
        failed_snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 7,
            "spot_observation_seq": 7,
            "spot_poll_status": "timeout",
            "spot_raw_validity": "not_received",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
        }
        success_snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 8,
            "spot_observation_seq": 8,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "455.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:01Z",
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

    def test_writer_archives_existing_fact_when_header_mismatches_current_schema(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-current",
            "spot_poll_seq": 10,
            "spot_observation_seq": 10,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "455.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            old_columns = SPOT_OBSERVATION_FACT_COLUMNS[:40]
            self.assertEqual(len(old_columns), 40)
            with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(old_columns)
                writer.writerow(["legacy"] * len(old_columns))

            writer = SpotObservationFactWriter(output_path)
            fact = writer.write_fact(snapshot)

            self.assertIsNotNone(fact)
            archives = list(output_path.parent.glob("spot_observation_fact.*.schema-mismatch.csv"))
            self.assertEqual(len(archives), 1)
            with archives[0].open("r", encoding="utf-8-sig", newline="") as handle:
                archived_rows = list(csv.reader(handle))
            self.assertEqual(archived_rows[0], old_columns)
            self.assertEqual(len(archived_rows[1]), len(old_columns))

            with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[0], SPOT_OBSERVATION_FACT_COLUMNS)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(rows[1]), len(SPOT_OBSERVATION_FACT_COLUMNS))
            self.assertIn("svc-current:10", rows[1])

    def test_spool_flush_archives_mismatched_existing_fact_before_writing_pending_rows(self) -> None:
        pending_snapshot = {
            "spot_service_instance_id": "svc-spooled",
            "spot_poll_seq": 11,
            "spot_observation_seq": 11,
            "spot_poll_status": "timeout",
            "spot_raw_validity": "not_received",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
        }
        success_snapshot = {
            "spot_service_instance_id": "svc-current",
            "spot_poll_seq": 12,
            "spot_observation_seq": 12,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "456.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:01Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_path = tmp_path / "spot_observation_fact.csv"
            spool_path = tmp_path / "spot_observation_fact.failed.jsonl"
            old_columns = SPOT_OBSERVATION_FACT_COLUMNS[:40]
            with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(old_columns)
                writer.writerow(["legacy"] * len(old_columns))
            spool_path.write_text(
                json.dumps(build_spot_observation_fact(pending_snapshot), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            writer = SpotObservationFactWriter(output_path, spool_path=spool_path)
            fact = writer.write_fact(success_snapshot)

            self.assertIsNotNone(fact)
            self.assertFalse(spool_path.exists())
            archives = list(output_path.parent.glob("spot_observation_fact.*.schema-mismatch.csv"))
            self.assertEqual(len(archives), 1)
            with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[0], SPOT_OBSERVATION_FACT_COLUMNS)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(len(row) == len(SPOT_OBSERVATION_FACT_COLUMNS) for row in rows[1:]))
            self.assertIn("svc-spooled:11", rows[1])
            self.assertIn("svc-current:12", rows[2])

    def test_build_fact_uses_missing_diagnostics_status(self) -> None:
        fact = build_spot_observation_fact(
            {
                "spot_service_instance_id": "svc-1",
                "spot_poll_seq": 1,
                "spot_poll_status": "timeout",
                "spot_raw_validity": "not_received",
                "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
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
            "peak_picker_enabled": True,
            "peak_picker_off_mode": "reset",
            "actuator_scan_state": "scanning",
            "spot_diagnostic_evidence_codes": '["target_absent_verified"]',
        }

        fact = build_spot_observation_fact(snapshot)
        evidence_codes = derive_spot_diagnostic_evidence_codes(snapshot)

        self.assertEqual(fact["diagnostics_capture_status"], "same_response")
        self.assertEqual(fact["diagnostics_age_ms"], "0.0")
        self.assertIn("alarm_low_signal", fact["spot_diagnostic_evidence_codes"])
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
                "signalpc_present_threshold_unknown",
                "target_absent_verified",
            },
        )
        self.assertEqual(
            encode_spot_diagnostic_evidence_codes(snapshot),
            '["actuator_scanning","alarm_low_signal","peak_picker_off_mode_reset_configured","signalpc_present_threshold_unknown","target_absent_verified"]',
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

    def test_signalpc_with_configured_lte_threshold_derives_signal_below_threshold_when_alarm_enabled(self) -> None:
        snapshot = {
            "signalpc": "3.2",
            "low_signal_alarm_enabled": True,
            "low_signal_threshold_pc": "5.0",
            "low_signal_comparator": "lte",
        }

        self.assertEqual(derive_spot_diagnostic_evidence_codes(snapshot), ("signal_below_threshold",))
        self.assertEqual(encode_spot_diagnostic_evidence_codes(snapshot), '["signal_below_threshold"]')

    def test_signalpc_below_threshold_alarm_disabled_records_non_causal_evidence(self) -> None:
        snapshot = {
            "signalpc": "1.5",
            "low_signal_alarm_enabled": False,
            "low_signal_threshold_pc": "2.0",
            "low_signal_comparator": "lt",
        }

        self.assertEqual(
            derive_spot_diagnostic_evidence_codes(snapshot),
            ("signal_below_configured_threshold_alarm_disabled",),
        )

    def test_signalpc_threshold_edge_respects_lt_and_lte_comparators(self) -> None:
        lte_snapshot = {
            "signalpc": "5.0",
            "low_signal_alarm_enabled": True,
            "low_signal_threshold_pc": "5.0",
            "low_signal_comparator": "lte",
        }
        lt_snapshot = {
            "signalpc": "5.0",
            "low_signal_alarm_enabled": True,
            "low_signal_threshold_pc": "5.0",
            "low_signal_comparator": "lt",
        }

        self.assertEqual(derive_spot_diagnostic_evidence_codes(lte_snapshot), ("signal_below_threshold",))
        self.assertEqual(
            derive_spot_diagnostic_evidence_codes(lt_snapshot),
            ("signal_at_or_above_configured_threshold",),
        )

    def test_signalpc_without_threshold_records_threshold_unknown(self) -> None:
        self.assertEqual(
            derive_spot_diagnostic_evidence_codes({"signalpc": "3.2"}),
            ("signalpc_present_threshold_unknown",),
        )

    def test_signalpc_at_or_above_configured_threshold_records_non_low_evidence(self) -> None:
        snapshot = {
            "signalpc": "6.0",
            "low_signal_alarm_enabled": False,
            "low_signal_threshold_pc": "2.0",
            "low_signal_comparator": "lt",
        }

        self.assertEqual(
            derive_spot_diagnostic_evidence_codes(snapshot),
            ("signal_at_or_above_configured_threshold",),
        )

    def test_invalid_signalpc_value_does_not_set_low(self) -> None:
        cases = [
            {"signalpc": "not-a-number", "low_signal_threshold_pc": "5.0", "low_signal_comparator": "lte"},
            {"signalpc": "nan", "low_signal_threshold_pc": "5.0", "low_signal_comparator": "lte"},
            {"signalpc": "101", "low_signal_threshold_pc": "5.0", "low_signal_comparator": "lte"},
        ]

        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                self.assertEqual(derive_spot_diagnostic_evidence_codes(snapshot), ())

    def test_valid_signalpc_with_invalid_threshold_records_threshold_unknown(self) -> None:
        self.assertEqual(
            derive_spot_diagnostic_evidence_codes(
                {"signalpc": "3.2", "low_signal_threshold_pc": "nan", "low_signal_comparator": "lte"}
            ),
            ("signalpc_present_threshold_unknown",),
        )

    def test_peak_picker_disabled_does_not_emit_reset_evidence(self) -> None:
        snapshot = {"peak_picker_enabled": False, "peak_picker_off_mode": "reset"}

        self.assertEqual(derive_spot_diagnostic_evidence_codes(snapshot), ())

    def test_spot_observation_fact_validator_accepts_alarmstatus_bit4_with_evidence(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 9,
            "spot_observation_seq": 9,
            "spot_poll_status": "success",
            "spot_raw_validity": "invalid_sentinel",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
            "alarmstatus": "0x10",
            "signalpc": "6.0",
            "low_signal_alarm_enabled": False,
            "low_signal_threshold_pc": "2.0",
            "low_signal_comparator": "lt",
            "peak_picker_enabled": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            writer = SpotObservationFactWriter(output_path)
            fact = writer.write_fact(snapshot)

            self.assertIsNotNone(fact)
            assert fact is not None
            self.assertIn("spot_diagnostic_evidence_codes", fact)
            self.assertIn("alarm_low_signal", fact["spot_diagnostic_evidence_codes"])
            self.assertEqual(validate_spot_observation_fact_invariants(output_path), [])

    def test_spot_observation_fact_validator_rejects_row_length_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(SPOT_OBSERVATION_FACT_COLUMNS)
                writer.writerow([""] * (len(SPOT_OBSERVATION_FACT_COLUMNS) - 1))

            failures = validate_spot_observation_fact_invariants(output_path)

        self.assertTrue(any("columns, expected" in failure for failure in failures))

    def test_spot_observation_fact_validator_rejects_alarmstatus_bit4_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            row = {column: "" for column in SPOT_OBSERVATION_FACT_COLUMNS}
            row.update(
                {
                    "alarmstatus": "16",
                    "spot_diagnostic_evidence_codes": "[]",
                    "low_signal_alarm_enabled": "false",
                    "low_signal_threshold_pc": "2.0",
                    "low_signal_comparator": "lt",
                    "peak_picker_enabled": "false",
                }
            )
            with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=SPOT_OBSERVATION_FACT_COLUMNS)
                writer.writeheader()
                writer.writerow(row)

            failures = validate_spot_observation_fact_invariants(output_path)

        self.assertTrue(any("alarmstatus bit4 requires alarm_low_signal" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
