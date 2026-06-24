import csv
import os
import tempfile
import unittest
from pathlib import Path

from backend.FacilityData.drivers.csv_replay import CsvReplayDriver
from backend.FacilityData.repository import CSV_SCHEMA_VERSION, V1_CSV_COLUMNS, V2_CSV_COLUMNS


class CsvReplayDriverTests(unittest.TestCase):
    def _write_v1_csv(self, path: Path, count: int, speed: float = 1.0) -> None:
        row = [
            "2026-03-09",
            "07:20:25.123",
            "450.0",
            "120.0",
            "650.0",
            "30.0",
            "31.0",
            str(count),
            str(speed),
            "10.0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "500.0",
            "1.0",
            "20.0",
            "DIE-1",
            "CYCLE-1",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(V1_CSV_COLUMNS)
            writer.writerow(row)

    def _write_v2_csv(self, path: Path, count: int, temperature: str = "450.0") -> None:
        values = {column: "" for column in V2_CSV_COLUMNS}
        values.update(
            {
                "schema_version": CSV_SCHEMA_VERSION,
                "sample_seq": str(count),
                "timestamp_local": "2026-03-09T07:20:25.123+09:00",
                "timestamp_utc": "2026-03-08T22:20:25.123Z",
                "ingest_timestamp": "2026-03-09T07:20:25.123+09:00",
                "Product_No_operator": "12345",
                "Mold_No_operator": "123",
                "operator_metadata_valid": "true",
                "operator_metadata_missing_fields": "",
                "operator_metadata_updated_at": "2026-03-09T07:20:20Z",
                "Date": "2026-03-09",
                "Time": "07:20:25.123",
                "Temperature": temperature,
                "MainPress": "120.0",
                "BilletLength": "650.0",
                "Temp_F": "30.0",
                "Temp_B": "31.0",
                "Count": str(count),
                "Speed": "1.0",
                "EndPos": "10.0",
                "Mold1": "1",
                "Mold2": "2",
                "Mold3": "3",
                "Mold4": "4",
                "Mold5": "5",
                "Mold6": "6",
                "Billet_Temp": "500.0",
                "At_Pre": "1.0",
                "At_Temp": "20.0",
                "DIE_ID": "DIE-1",
                "Billet_CycleID": "CYCLE-1",
                "MainPress_quality": "ok",
                "MainPress_missing_reason": "not_missing",
                "MainPress_unit": "bar",
                "Temperature_quality": "ok" if temperature else "missing",
                "Temperature_missing_reason": "not_missing" if temperature else "source_missing",
                "Temperature_unit": "degC",
                "Speed_quality": "ok",
                "Speed_missing_reason": "not_missing",
                "Speed_unit": "mm/s",
                "BilletLength_quality": "ok",
                "BilletLength_missing_reason": "not_missing",
                "BilletLength_unit": "mm",
                "DIE_ID_derived": "true",
                "Billet_CycleID_derived": "true",
                "derivation_version": "cycle-heuristic-v1",
                "cycle_confidence": "0.0",
                "cycle_state": "unknown",
                "logger_service_instance_id": "logger-1",
                "logger_service_started_at": "2026-03-09T07:19:00Z",
                "extruder_process_state_online": "extruding",
                "process_state_online_rule_version": "process-state-online-v1",
                "spot_target_state_observed_shadow": "present" if temperature else "unknown",
                "spot_target_state_observed_source": "valid_temperature" if temperature else "unknown",
                "label_validation_state": "shadow",
                "temperature_status_shadow": "ok" if temperature else "no_target",
                "temperature_status_rule_version": "temperature-status-shadow-v1",
                "spot_poll_status": "success",
                "spot_raw_validity": "valid_temperature" if temperature else "verified_no_target",
                "spot_cache_status": "fresh" if temperature else "invalidated",
                "spot_source_freshness": "fresh",
                "temperature_value_origin": "current_observation" if temperature else "none",
                "cache_fallback_allowed": "false",
                "spot_service_instance_id": "spot-service-1",
                "spot_service_started_at": "2026-03-09T07:19:00Z",
                "spot_poll_seq": "7",
                "spot_observation_seq": "7",
                "spot_temperature_observed_c": temperature,
                "spot_temperature_raw": temperature,
                "spot_temperature_raw_truncated": "false",
                "spot_raw_payload_hash": "hash-1",
                "spot_raw_payload_encoding": "utf-8-replace" if temperature else "",
                "spot_http_status_code": "200",
                "spot_poll_duration_ms": "12.5",
                "spot_response_content_length": str(len(temperature)),
                "spot_last_poll_started_at": "2026-03-09T07:20:24.000Z",
                "spot_last_poll_completed_at": "2026-03-09T07:20:24.012Z",
                "spot_last_response_at": "2026-03-09T07:20:24.012Z",
                "spot_last_valid_value_at": "2026-03-09T07:20:24.012Z" if temperature else "",
                "spot_snapshot_age_ms": "188.0",
                "spot_value_age_ms": "188.0" if temperature else "",
            }
        )
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(V2_CSV_COLUMNS)
            writer.writerow([values[column] for column in V2_CSV_COLUMNS])

    def test_replay_loads_directory_daily_v1_files_in_timestamp_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            first = log_dir / "Factory_Integrated_Log_20260309_235959.csv"
            second = log_dir / "Factory_Integrated_Log_20260310_000000.csv"
            self._write_v1_csv(second, 2)
            self._write_v1_csv(first, 1)

            cwd = Path.cwd()
            os.chdir(log_dir)
            try:
                driver = CsvReplayDriver(str(log_dir))
            finally:
                os.chdir(cwd)

            self.assertTrue(driver.connect())
            self.assertEqual(driver.read_data().Count, 1)
            self.assertEqual(driver.read_data().Count, 2)

    def test_replay_rejects_mixed_v1_and_v2_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            v1_path = log_dir / "Factory_Integrated_Log_20260309_235959.csv"
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_235959.csv"
            self._write_v1_csv(v1_path, 1)
            self._write_v2_csv(v2_path, 1)

            driver = CsvReplayDriver(f"{v1_path}{os.pathsep}{v2_path}")

            self.assertEqual(driver.rows, [])
            self.assertFalse(driver.connect())

    def test_replay_maps_v2_3_spot_shadow_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_235959.csv"
            self._write_v2_csv(v2_path, 1)

            cwd = Path.cwd()
            os.chdir(log_dir)
            try:
                driver = CsvReplayDriver(str(v2_path))
            finally:
                os.chdir(cwd)

            self.assertTrue(driver.connect())
            data = driver.read_data()
            self.assertEqual(data.Spot, 450.0)
            self.assertEqual(data.extruder_process_state_online, "extruding")
            self.assertEqual(data.temperature_status_shadow, "ok")
            self.assertEqual(data.temperature_value_origin, "current_observation")
            self.assertEqual(data.spot_poll_status, "success")
            self.assertEqual(data.spot_raw_validity, "valid_temperature")
            self.assertEqual(data.spot_cache_status, "fresh")
            self.assertEqual(data.spot_source_freshness, "fresh")
            self.assertEqual(data.spot_poll_seq, 7)
            self.assertEqual(data.spot_observation_seq, 7)
            self.assertEqual(data.spot_temperature_observed_c, 450.0)
            self.assertFalse(data.cache_fallback_allowed)
            self.assertFalse(data.spot_temperature_raw_truncated)
            self.assertEqual(data.spot_raw_payload_hash, "hash-1")
            self.assertEqual(data.spot_http_status_code, 200)

    def test_replay_preserves_empty_temperature_as_none_for_v2_3_origin_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_235959.csv"
            self._write_v2_csv(v2_path, 1, temperature="")

            cwd = Path.cwd()
            os.chdir(log_dir)
            try:
                driver = CsvReplayDriver(str(v2_path))
            finally:
                os.chdir(cwd)

            self.assertTrue(driver.connect())
            data = driver.read_data()
            self.assertIsNone(data.Spot)
            self.assertEqual(data.temperature_status_shadow, "no_target")
            self.assertEqual(data.temperature_value_origin, "none")
            self.assertEqual(data.spot_cache_status, "invalidated")
            self.assertIsNone(data.spot_temperature_observed_c)
            self.assertIsNone(data.spot_last_valid_value_at)

    def test_replay_maps_v2_operator_metadata_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_235959.csv"
            self._write_v2_csv(v2_path, 1)

            cwd = Path.cwd()
            os.chdir(log_dir)
            try:
                driver = CsvReplayDriver(str(v2_path))
            finally:
                os.chdir(cwd)

            self.assertTrue(driver.connect())
            data = driver.read_data()
            self.assertEqual(data.Product_No_operator, "12345")
            self.assertEqual(data.Mold_No_operator, "123")
            self.assertTrue(data.operator_metadata_valid)
            self.assertEqual(data.operator_metadata_missing_fields, [])
            self.assertEqual(data.operator_metadata_updated_at, "2026-03-09T07:20:20Z")


if __name__ == "__main__":
    unittest.main()
