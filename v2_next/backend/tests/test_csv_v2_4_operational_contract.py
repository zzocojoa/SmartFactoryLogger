import csv
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.FacilityData.repository import (
    CSVLoggerService,
    V1_CSV_COLUMNS,
    V2_3_CSV_COLUMNS,
    V2_4_CSV_COLUMNS,
)
from backend.FacilityData.schemas import FactoryData
from scripts.validate_csv_v2_shadow import validate_v2_4_operational_invariants


class CsvV24OperationalContractTests(unittest.TestCase):
    def create_data(self) -> FactoryData:
        return FactoryData(
            Time="2026-06-25T08:00:00",
            Status="Running",
            Speed=0.0,
            Press=0.0,
            Count=1,
            Spot=None,
            Product_No_operator="100",
            Mold_No_operator="7",
            operator_metadata_valid=True,
            operator_metadata_missing_fields=[],
            extruder_process_state_online="unknown",
            spot_poll_status="success",
            spot_raw_validity="invalid_sentinel",
            spot_source_freshness="fresh",
            spot_cache_status="available_not_used",
            temperature_value_origin="none",
            cache_fallback_allowed=False,
            spot_device_status_code="temperature_under_range",
            spot_service_instance_id="spot-service-1",
            spot_poll_seq=14,
            spot_observation_seq=14,
            spot_snapshot_age_ms=10.0,
            spot_value_age_ms=10.0,
            spot_temperature_raw="6553.4",
        )

    def build_v2_row(
        self,
        service: CSVLoggerService,
        data: FactoryData,
        sample_seq: int = 1,
    ) -> list[object]:
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)
        return service._build_v2_row(data, timestamp, timestamp.astimezone(), sample_seq, v1_row)

    def test_v2_4_row_appends_operational_fields_and_blanks_legacy_temperature(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data()

        row = self.build_v2_row(service, data)

        self.assertEqual(len(row), len(V2_4_CSV_COLUMNS))
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("schema_version")], "2.4.0")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("Temperature")], "")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "under_range")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")], "under_range")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("process_phase_candidate")], "setup_candidate")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("process_segment_id")], "")
        self.assertTrue(row[V2_4_CSV_COLUMNS.index("changeover_candidate_id")].startswith("chg_"))
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_observation_key")], "spot-service-1:14")

    def test_v2_4_row_uses_spot_diagnostic_evidence_codes_for_under_range_cause(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(update={"spot_diagnostic_evidence_codes": '["signal_below_threshold"]'})

        row = self.build_v2_row(service, data)

        self.assertEqual(
            row[V2_4_CSV_COLUMNS.index("temperature_under_range_cause_candidate")],
            "low_signal_candidate",
        )
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_cause_confidence")], "0.6")
        self.assertEqual(
            row[V2_4_CSV_COLUMNS.index("temperature_cause_evidence_codes")],
            '["phase_setup_candidate","signal_below_threshold"]',
        )

    def test_low_count_high_motion_under_range_does_not_promote_to_production_stable(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "Count": 0,
                "Speed": 1.0,
                "Press": 35.0,
                "extruder_process_state_online": "extruding",
            }
        )

        row = self.build_v2_row(service, data)

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("Temperature")], "")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "under_range")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("process_phase_candidate")], "setup_alignment_candidate")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_expectedness_candidate")], "expected_candidate")
        self.assertNotEqual(row[V2_4_CSV_COLUMNS.index("process_phase_candidate")], "production_stable")

    def test_build_v2_row_uses_runtime_state_for_pre_changeover_under_range_sequence(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        production_row = self.create_data().model_copy(
            update={
                "Time": "2026-06-25T08:00:00",
                "Speed": 1.0,
                "Press": 35.0,
                "Count": 12,
                "Spot": 500.0,
                "extruder_process_state_online": "extruding",
                "spot_raw_validity": "valid_temperature",
                "spot_cache_status": "fresh",
                "temperature_value_origin": "current_observation",
                "cache_fallback_allowed": True,
                "spot_device_status_code": None,
                "spot_temperature_observed_c": 500.0,
                "spot_temperature_raw": "500.0",
            }
        )
        under_range_row = self.create_data().model_copy(
            update={
                "Time": "2026-06-25T08:00:31",
                "Speed": 0.0,
                "Press": 0.0,
                "Count": 12,
                "extruder_process_state_online": "stopped",
            }
        )
        timeout_row = self.create_data().model_copy(
            update={
                "Time": "2026-06-25T08:00:36",
                "Speed": 0.0,
                "Press": 0.0,
                "Count": 12,
                "extruder_process_state_online": "stopped",
                "spot_poll_status": "timeout",
                "spot_raw_validity": "not_received",
                "spot_cache_status": "available_not_used",
                "temperature_value_origin": "none",
                "spot_device_status_code": None,
                "spot_temperature_raw": "",
            }
        )
        timeout_row_2 = timeout_row.model_copy(update={"Time": "2026-06-25T08:00:41"})
        valid_again_row = production_row.model_copy(
            update={
                "Time": "2026-06-25T08:00:46",
                "Count": 13,
                "spot_poll_seq": 15,
                "spot_observation_seq": 15,
                "spot_temperature_observed_c": 510.0,
                "spot_temperature_raw": "510.0",
                "Spot": 510.0,
            }
        )

        rows = [
            self.build_v2_row(service, production_row, 1),
            self.build_v2_row(service, under_range_row, 2),
            self.build_v2_row(service, timeout_row, 3),
            self.build_v2_row(service, timeout_row_2, 4),
            self.build_v2_row(service, valid_again_row, 5),
        ]

        segment_id = rows[0][V2_4_CSV_COLUMNS.index("process_segment_id")]
        pre_changeover_id = rows[1][V2_4_CSV_COLUMNS.index("changeover_candidate_id")]

        self.assertEqual(rows[0][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "production_stable")
        self.assertTrue(segment_id.startswith("seg_"))
        self.assertEqual(rows[0][V2_4_CSV_COLUMNS.index("changeover_candidate_id")], "")
        self.assertEqual(rows[1][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "pre_changeover_hold_candidate")
        self.assertEqual(rows[1][V2_4_CSV_COLUMNS.index("process_segment_id")], "")
        self.assertTrue(pre_changeover_id.startswith("chg_"))
        self.assertEqual(rows[1][V2_4_CSV_COLUMNS.index("temperature_output_status")], "under_range")
        self.assertEqual(rows[1][V2_4_CSV_COLUMNS.index("temperature_expectedness_candidate")], "expected_candidate")
        self.assertEqual(
            rows[1][V2_4_CSV_COLUMNS.index("temperature_under_range_cause_candidate")],
            "unknown",
        )
        self.assertEqual(rows[1][V2_4_CSV_COLUMNS.index("temperature_cause_confidence")], "0.0")
        self.assertEqual(rows[2][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "pre_changeover_hold_candidate")
        self.assertEqual(rows[2][V2_4_CSV_COLUMNS.index("changeover_candidate_id")], pre_changeover_id)
        self.assertEqual(rows[2][V2_4_CSV_COLUMNS.index("temperature_output_status")], "source_error")
        self.assertEqual(rows[3][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "pre_changeover_hold_candidate")
        self.assertEqual(rows[3][V2_4_CSV_COLUMNS.index("changeover_candidate_id")], pre_changeover_id)
        self.assertEqual(rows[4][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "production_stable")
        self.assertEqual(rows[4][V2_4_CSV_COLUMNS.index("changeover_candidate_id")], "")
        self.assertTrue(rows[4][V2_4_CSV_COLUMNS.index("process_segment_id")].startswith("seg_"))

    def test_build_v2_row_passes_previous_operator_context_for_stopped_change(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        production_row = self.create_data().model_copy(
            update={
                "Time": "2026-06-25T08:00:00",
                "Speed": 1.0,
                "Press": 35.0,
                "Count": 20,
                "Spot": 500.0,
                "extruder_process_state_online": "extruding",
                "spot_raw_validity": "valid_temperature",
                "spot_cache_status": "fresh",
                "temperature_value_origin": "current_observation",
                "cache_fallback_allowed": True,
                "spot_device_status_code": None,
                "spot_temperature_observed_c": 500.0,
                "spot_temperature_raw": "500.0",
            }
        )
        changed_context_row = self.create_data().model_copy(
            update={
                "Time": "2026-06-25T08:00:10",
                "Speed": 0.0,
                "Press": 0.0,
                "Count": 20,
                "Product_No_operator": "200",
                "Mold_No_operator": "8",
                "extruder_process_state_online": "stopped",
            }
        )

        self.build_v2_row(service, production_row, 1)
        row = self.build_v2_row(service, changed_context_row, 2)

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("process_phase_candidate")], "die_change_candidate")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_expectedness_candidate")], "expected_candidate")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("process_segment_id")], "")
        self.assertTrue(row[V2_4_CSV_COLUMNS.index("changeover_candidate_id")].startswith("chg_"))

    def test_changeover_candidate_id_spans_lifecycle_and_excludes_general_segments(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        production_row = self.create_data().model_copy(
            update={
                "Time": "2026-06-25T08:00:00",
                "Speed": 1.0,
                "Press": 35.0,
                "Count": 20,
                "Spot": 500.0,
                "extruder_process_state_online": "extruding",
                "spot_raw_validity": "valid_temperature",
                "spot_cache_status": "fresh",
                "temperature_value_origin": "current_observation",
                "cache_fallback_allowed": True,
                "spot_device_status_code": None,
                "spot_temperature_observed_c": 500.0,
                "spot_temperature_raw": "500.0",
            }
        )
        die_change_row = production_row.model_copy(
            update={
                "Time": "2026-06-25T08:00:05",
                "Speed": 0.0,
                "Press": 0.0,
                "Count": 20,
                "Product_No_operator": "200",
                "Mold_No_operator": "8",
                "extruder_process_state_online": "stopped",
            }
        )
        setup_alignment_row = die_change_row.model_copy(
            update={
                "Time": "2026-06-25T08:00:10",
                "Speed": 1.0,
                "Press": 35.0,
                "Count": 0,
                "extruder_process_state_online": "extruding",
            }
        )
        stabilizing_row = setup_alignment_row.model_copy(
            update={
                "Time": "2026-06-25T08:00:15",
                "Count": 3,
            }
        )
        stable_after_row = stabilizing_row.model_copy(
            update={
                "Time": "2026-06-25T08:00:20",
                "Count": 4,
            }
        )

        rows = [
            self.build_v2_row(service, production_row, 1),
            self.build_v2_row(service, die_change_row, 2),
            self.build_v2_row(service, setup_alignment_row, 3),
            self.build_v2_row(service, stabilizing_row, 4),
            self.build_v2_row(service, stable_after_row, 5),
        ]
        segment_id_before = rows[0][V2_4_CSV_COLUMNS.index("process_segment_id")]
        changeover_id = rows[1][V2_4_CSV_COLUMNS.index("changeover_candidate_id")]
        segment_id_after = rows[4][V2_4_CSV_COLUMNS.index("process_segment_id")]

        self.assertEqual(rows[0][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "production_stable")
        self.assertTrue(segment_id_before.startswith("seg_"))
        self.assertEqual(rows[0][V2_4_CSV_COLUMNS.index("changeover_candidate_id")], "")
        self.assertEqual(rows[1][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "die_change_candidate")
        self.assertEqual(rows[2][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "setup_alignment_candidate")
        self.assertEqual(rows[3][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "production_stabilizing")
        self.assertTrue(changeover_id.startswith("chg_"))
        for row in rows[1:4]:
            self.assertEqual(row[V2_4_CSV_COLUMNS.index("process_segment_id")], "")
            self.assertEqual(row[V2_4_CSV_COLUMNS.index("changeover_candidate_id")], changeover_id)
        self.assertEqual(rows[4][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "production_stable")
        self.assertEqual(rows[4][V2_4_CSV_COLUMNS.index("changeover_candidate_id")], "")
        self.assertTrue(segment_id_after.startswith("seg_"))
        self.assertNotEqual(segment_id_after, segment_id_before)

    def test_stale_row_preserves_raw_device_status_but_outputs_stale(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "spot_source_freshness": "stale",
                "spot_snapshot_age_ms": 10_000.0,
            }
        )
        timestamp = service._parse_timestamp(data)
        row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, service._build_row(data, timestamp))

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_device_status_code")], "temperature_under_range")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "stale")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")], "stale_observation")

    def test_v2_4_validator_accepts_stale_observation_value_not_used(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "Spot": None,
                "spot_poll_status": "success",
                "spot_raw_validity": "valid_temperature",
                "spot_source_freshness": "stale",
                "spot_cache_status": "available_not_used",
                "temperature_value_origin": "none",
                "spot_device_status_code": None,
                "spot_temperature_observed_c": 560.7,
                "spot_temperature_raw": "560.7",
                "spot_snapshot_age_ms": 10_000.0,
                "spot_value_age_ms": 10_000.0,
            }
        )
        timestamp = service._parse_timestamp(data)
        row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, service._build_row(data, timestamp))

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("Temperature")], "")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_value_origin")], "none")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_temperature_observed_c")], "560.7")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "stale")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")], "stale_observation")
        self.assertEqual(validate_v2_4_operational_invariants([row], V2_4_CSV_COLUMNS), [])

    def test_v2_4_validator_accepts_operational_row(self) -> None:
        header = V2_4_CSV_COLUMNS
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data()
        timestamp = service._parse_timestamp(data)
        row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, service._build_row(data, timestamp))

        self.assertEqual(validate_v2_4_operational_invariants([row], header), [])

    def test_v2_4_runtime_summary_counts_operational_rows(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_enabled=True, csv_v2_operational_fields_enabled=True)
        under_range = self.create_data()
        stale = self.create_data().model_copy(
            update={
                "Time": "2026-06-25T08:00:05",
                "spot_source_freshness": "stale",
                "spot_snapshot_age_ms": 10_000.0,
            }
        )

        self.build_v2_row(service, under_range, 1)
        self.build_v2_row(service, stale, 2)

        summary = service.get_v2_4_operational_summary()
        self.assertTrue(summary["enabled"])
        self.assertEqual(summary["rows_total"], 2)
        self.assertEqual(summary["rows_by_temperature_output_status"]["under_range"], 1)
        self.assertEqual(summary["rows_by_temperature_output_status"]["stale"], 1)
        self.assertEqual(summary["rows_by_temperature_unavailable_reason"]["under_range"], 1)
        self.assertEqual(summary["rows_by_temperature_unavailable_reason"]["stale_observation"], 1)
        self.assertEqual(
            summary["sentinel_counts_by_spot_device_status_code"]["temperature_under_range"],
            2,
        )
        self.assertEqual(summary["stale_threshold_breach_count"], 1)
        self.assertEqual(summary["process_phase_candidate_counts"]["setup_candidate"], 2)
        self.assertEqual(summary["observation_fact_link_failure_count"], 0)
        self.assertEqual(service.get_runtime_state()["v2_4_operational"]["rows_total"], 2)

    def test_v2_4_runtime_summary_counts_missing_fact_link_when_fact_enabled(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_enabled=True, csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(update={"spot_service_instance_id": ""})

        with patch("backend.FacilityData.repository.config.SPOT_OBSERVATION_FACT_ENABLED", True):
            self.build_v2_row(service, data, 1)

        summary = service.get_v2_4_operational_summary()
        self.assertEqual(summary["observation_fact_link_failure_count"], 1)

    def test_schema_rollover_uses_separate_file_when_contract_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)

            handle, _ = service._open_v2_log_file("20260625_080000", "Factory_Integrated_Log_v2")
            service._close_file(handle)
            service.apply_config(csv_v2_operational_fields_enabled=True)
            handle, _ = service._open_v2_log_file("20260625_080000", "Factory_Integrated_Log_v2")
            service._close_file(handle)

            files = sorted(log_dir.glob("Factory_Integrated_Log_v2_20260625_080000*.csv"))
            self.assertEqual(len(files), 2)
            with files[0].open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(next(csv.reader(handle)), V2_3_CSV_COLUMNS)
            with files[1].open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(next(csv.reader(handle)), V2_4_CSV_COLUMNS)
            self.assertNotEqual(files[0].name, files[1].name)

    def test_schema_rollover_accepts_prior_v2_4_prefix_header_when_contract_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v2_enabled=True,
                csv_v2_operational_fields_enabled=True,
            )
            original_path = log_dir / "Factory_Integrated_Log_v2_20260626_000000.csv"
            prior_v2_4_columns = [column for column in V2_4_CSV_COLUMNS if column != "process_segment_id"]
            with original_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(prior_v2_4_columns)

            handle, _ = service._open_v2_log_file("20260626_000000", "Factory_Integrated_Log_v2")
            service._close_file(handle)

            rollover_path = log_dir / "Factory_Integrated_Log_v2_20260626_000000_2_4_0.csv"
            self.assertTrue(rollover_path.exists())
            with original_path.open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(next(csv.reader(handle)), prior_v2_4_columns)
            with rollover_path.open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(next(csv.reader(handle)), V2_4_CSV_COLUMNS)

    def test_v1_temperature_index_remains_stable(self) -> None:
        self.assertEqual(V1_CSV_COLUMNS.index("Temperature"), 2)


PROMOTION_FLAGS = (
    "CSV_V2_OPERATIONAL_FIELDS_ENABLED",
    "SPOT_OBSERVATION_FACT_ENABLED",
    "PROCESS_PHASE_EVENT_FACT_ENABLED",
)


class ConfigPromotionBundleTests(unittest.TestCase):
    def import_config(self, **overrides: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for flag in PROMOTION_FLAGS:
            env[flag] = "false"
        env.update(overrides)
        env["V2_MODE"] = "MOCK"
        repo_root = Path(__file__).resolve().parents[2]
        env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, "-c", "import backend.config; print('config-import-ok')"],
            cwd=repo_root,
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
        )

    def test_partial_v2_4_promotion_bundle_is_rejected_on_import(self) -> None:
        result = self.import_config(CSV_V2_OPERATIONAL_FIELDS_ENABLED="true")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Partial v2.4 promotion flag configuration is not allowed", result.stderr + result.stdout)

    def test_full_v2_4_promotion_bundle_is_allowed_on_import(self) -> None:
        result = self.import_config(
            CSV_V2_OPERATIONAL_FIELDS_ENABLED="true",
            SPOT_OBSERVATION_FACT_ENABLED="true",
            PROCESS_PHASE_EVENT_FACT_ENABLED="true",
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("config-import-ok", result.stdout)


class V24HealthCounterTests(unittest.TestCase):
    def test_spot_temperature_health_exposes_v2_4_operational_counters(self) -> None:
        from backend.FacilityData import service as facility_service

        summary = {
            "enabled": True,
            "schema_version": "2.4.0",
            "rows_total": 3,
            "rows_by_temperature_output_status": {"under_range": 2, "stale": 1},
            "rows_by_temperature_unavailable_reason": {"under_range": 2, "stale_observation": 1},
            "sentinel_counts_by_spot_device_status_code": {"temperature_under_range": 3},
            "stale_threshold_breach_count": 1,
            "observation_fact_link_failure_count": 0,
            "process_phase_candidate_counts": {"setup_candidate": 3},
            "last_sample_seq": 3,
            "last_updated_at": "2026-06-25T00:00:00Z",
        }
        with (
            patch.object(facility_service.logger_service, "get_v2_4_operational_summary", return_value=dict(summary)),
            patch(
                "backend.FacilityData.drivers.spot_api.get_image_proxy_diagnostics",
                return_value={"spot_poll_status": "success"},
            ),
            patch(
                "backend.FacilityData.drivers.spot_api.get_spot_observation_fact_health",
                return_value={"enabled": True, "write_failure_count": 2},
            ),
        ):
            payload = facility_service.plc_service._spot_temperature_health()

        self.assertTrue(payload["diagnostics_available"])
        self.assertEqual(payload["v2_4_operational"]["rows_total"], 3)
        self.assertEqual(payload["v2_4_operational"]["observation_fact_write_failure_count"], 2)
        self.assertTrue(payload["v2_4_operational"]["observation_fact_enabled"])


if __name__ == "__main__":
    unittest.main()
