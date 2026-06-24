import csv
import tempfile
import unittest
from pathlib import Path

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

    def test_v2_4_row_appends_operational_fields_and_blanks_legacy_temperature(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data()
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertEqual(len(row), len(V2_4_CSV_COLUMNS))
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("schema_version")], "2.4.0")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("Temperature")], "")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "under_range")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")], "under_range")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("process_phase_candidate")], "setup_candidate")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_observation_key")], "spot-service-1:14")

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

    def test_v2_4_validator_accepts_operational_row(self) -> None:
        header = V2_4_CSV_COLUMNS
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data()
        timestamp = service._parse_timestamp(data)
        row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, service._build_row(data, timestamp))

        self.assertEqual(validate_v2_4_operational_invariants([row], header), [])

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

    def test_v1_temperature_index_remains_stable(self) -> None:
        self.assertEqual(V1_CSV_COLUMNS.index("Temperature"), 2)


if __name__ == "__main__":
    unittest.main()
