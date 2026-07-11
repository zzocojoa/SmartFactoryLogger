import csv
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backend.FacilityData.drivers.csv_replay import CsvReplayDriver
from backend.FacilityData.repository import (
    CSV_SCHEMA_VERSION_V2_3,
    CSV_SCHEMA_VERSION_V2_4,
    CSV_SCHEMA_VERSION_V2_5,
    CSVLoggerService,
    V2_3_CSV_COLUMNS,
    V2_4_CSV_COLUMNS,
    V2_5_CSV_COLUMNS,
)
from backend.FacilityData.schemas import FactoryData
from backend.FacilityData.spot_observation_fact import (
    SPOT_OBSERVATION_FACT_FILENAME,
    SpotObservationFactWriter,
)
from scripts.validate_csv_v2_shadow import validate as validate_csv_v2_shadow


class SpotTemperatureStage5VerificationTests(unittest.TestCase):
    def _valid_data(self) -> FactoryData:
        return FactoryData(
            Time="2026-07-11T02:30:00+00:00",
            Status="Running",
            Speed=1.0,
            Press=30.0,
            Count=3,
            Spot=560.7,
            Billet_Length=650.0,
            Temp_F=31.0,
            Temp_B=32.0,
            EndPos=10.0,
            Mold1=1.0,
            Mold2=2.0,
            Mold3=3.0,
            Mold4=4.0,
            Mold5=5.0,
            Mold6=6.0,
            Billet_Temp=500.0,
            At_Pre=1.0,
            At_Temp=20.0,
            Die_ID="DIE-1",
            Billet_Cycle_ID="CYCLE-1",
            Product_No_operator="100",
            Mold_No_operator="7",
            operator_metadata_valid=True,
            operator_metadata_missing_fields=[],
            operator_metadata_updated_at="2026-07-11T02:29:00Z",
            captured_at_extruder=1_783_736_999.0,
            captured_at_ls=1_783_736_999.0,
            captured_at_spot=1_783_737_000.0,
            MainRamPosition_D0010=15.0,
            ContainerPosition_D0012=16.0,
            extruder_process_state_online="extruding",
            process_state_online_rule_version="process-state-online-v1",
            spot_target_state_observed_shadow="present",
            spot_target_state_observed_source="valid_temperature",
            label_validation_state="shadow",
            temperature_status_shadow="ok",
            temperature_status_rule_version="temperature-status-shadow-v1",
            spot_poll_status="success",
            spot_raw_validity="valid_temperature",
            spot_cache_status="fresh",
            spot_source_freshness="fresh",
            temperature_value_origin="current_observation",
            cache_fallback_allowed=False,
            spot_service_instance_id="stage5-spot-service",
            spot_service_started_at="2026-07-11T02:00:00Z",
            spot_poll_seq=17,
            spot_observation_seq=17,
            spot_temperature_observed_c=560.7,
            spot_temperature_raw="560.7",
            spot_temperature_raw_truncated=False,
            spot_raw_payload_hash="stage5-sanitized-payload-hash",
            spot_raw_payload_encoding="utf-8-replace",
            spot_http_status_code=200,
            spot_poll_duration_ms=12.5,
            spot_response_content_length=5,
            spot_last_poll_started_at="2026-07-11T02:29:59.987Z",
            spot_last_poll_completed_at="2026-07-11T02:30:00Z",
            spot_last_response_at="2026-07-11T02:30:00Z",
            spot_last_valid_value_at="2026-07-11T02:30:00Z",
            spot_snapshot_age_ms=0.0,
            spot_value_age_ms=0.0,
        )

    def _fact_snapshot(self, data: FactoryData) -> dict[str, object]:
        return {
            "spot_service_instance_id": data.spot_service_instance_id,
            "spot_poll_seq": data.spot_poll_seq,
            "spot_observation_seq": data.spot_observation_seq,
            "spot_poll_status": data.spot_poll_status,
            "spot_raw_validity": data.spot_raw_validity,
            "spot_raw_value_text": data.spot_temperature_raw,
            "spot_raw_payload_hash": data.spot_raw_payload_hash,
            "spot_http_status_code": data.spot_http_status_code,
            "spot_response_content_length": data.spot_response_content_length,
            "spot_last_poll_started_at": data.spot_last_poll_started_at,
            "spot_last_poll_completed_at": data.spot_last_poll_completed_at,
            "spot_poll_duration_ms": data.spot_poll_duration_ms,
            "diagnostics_capture_status": "missing",
            "diagnostics_collection_mode": "async_fact_only",
            "diagnostics_binding_status": "missing",
            "diagnostics_missing_fields": [],
            "diagnostics_field_status": {},
        }

    def _write_controlled_artifact(
        self,
        log_dir: Path,
        schema_version: str,
    ) -> tuple[Path, Path, Path | None, list[str]]:
        operational = schema_version in {CSV_SCHEMA_VERSION_V2_4, CSV_SCHEMA_VERSION_V2_5}
        hardening = schema_version == CSV_SCHEMA_VERSION_V2_5
        service = CSVLoggerService()
        service.fallback_log_dir = log_dir
        service.apply_config(
            log_path=log_dir,
            auto_save=True,
            csv_v1_enabled=False,
            csv_v2_enabled=True,
            csv_v2_operational_fields_enabled=operational,
            csv_v2_temperature_hardening_enabled=hardening,
        )
        contract = service._get_active_v2_contract()
        self.assertEqual(contract.schema_version, schema_version)

        data = self._valid_data()
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)
        row = service._build_v2_row(data, timestamp, datetime.now(timezone.utc), 1, v1_row)
        schema_suffix = schema_version.replace(".", "_")
        v2_path = log_dir / f"Factory_Integrated_Log_v2_20260711_023000_{schema_suffix}.csv"
        with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(contract.columns)
            writer.writerow(row)

        fact_path: Path | None = None
        with patch("backend.FacilityData.repository.config.SPOT_OBSERVATION_FACT_ENABLED", operational):
            if operational:
                fact_path = log_dir / SPOT_OBSERVATION_FACT_FILENAME
                written = SpotObservationFactWriter(fact_path).write_fact(self._fact_snapshot(data))
                self.assertIsNotNone(written)
            service._write_v2_sidecar(v2_path, contract)
            if operational:
                service.refresh_spot_observation_fact_manifest_for_csv(v2_path)

        metadata_path = v2_path.with_suffix(".metadata.json")
        output = io.StringIO()
        with redirect_stdout(output):
            result = validate_csv_v2_shadow(
                None,
                v2_path,
                metadata_path,
                spot_observation_fact_path=fact_path,
            )
        self.assertEqual(result, 0, output.getvalue())
        return v2_path, metadata_path, fact_path, row

    def test_writer_validator_matrix_accepts_v2_3_v2_4_and_v2_5(self) -> None:
        expected_columns = {
            CSV_SCHEMA_VERSION_V2_3: V2_3_CSV_COLUMNS,
            CSV_SCHEMA_VERSION_V2_4: V2_4_CSV_COLUMNS,
            CSV_SCHEMA_VERSION_V2_5: V2_5_CSV_COLUMNS,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for schema_version, columns in expected_columns.items():
                with self.subTest(schema_version=schema_version):
                    log_dir = root / schema_version.replace(".", "_")
                    log_dir.mkdir()
                    v2_path, metadata_path, _, row = self._write_controlled_artifact(
                        log_dir,
                        schema_version,
                    )
                    with v2_path.open("r", encoding="utf-8-sig", newline="") as handle:
                        header = next(csv.reader(handle))
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    self.assertEqual(header, columns)
                    self.assertEqual(len(row), len(columns))
                    self.assertEqual(metadata["schema_metadata"]["schema_version"], schema_version)

    def test_v2_5_sanitized_replay_and_fact_link_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            v2_path, metadata_path, fact_path, _ = self._write_controlled_artifact(
                log_dir,
                CSV_SCHEMA_VERSION_V2_5,
            )
            self.assertIsNotNone(fact_path)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            coverage = metadata["spot_observation_fact_manifest"]["link_coverage"]
            self.assertEqual(coverage["realtime_rows_with_observation_key"], 1)
            self.assertEqual(coverage["linked_rows"], 1)
            self.assertEqual(coverage["missing_fact_key_rows"], 0)
            self.assertEqual(coverage["coverage_pct"], 100.0)

            artifact_text = v2_path.read_text(encoding="utf-8-sig") + metadata_path.read_text(
                encoding="utf-8"
            )
            self.assertNotIn("http://", artifact_text)
            self.assertNotIn("https://", artifact_text)

            cwd = Path.cwd()
            os.chdir(log_dir)
            try:
                with redirect_stdout(io.StringIO()):
                    replay = CsvReplayDriver(str(v2_path))
                    self.assertTrue(replay.connect())
                    replayed = replay.read_data()
            finally:
                os.chdir(cwd)
            self.assertEqual(replayed.Spot, 560.7)
            self.assertEqual(replayed.spot_value_age_clock_status, "ok")

    def test_hardening_rollback_opens_v2_4_without_mutating_v2_5(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v1_enabled=False,
                csv_v2_enabled=True,
                csv_v2_operational_fields_enabled=True,
                csv_v2_temperature_hardening_enabled=True,
            )
            v2_5_handle, _ = service._open_v2_log_file(
                "20260711_023000",
                "Factory_Integrated_Log_v2",
            )
            self.assertIsNotNone(v2_5_handle)
            service._close_v2_file(v2_5_handle)
            v2_5_path = log_dir / "Factory_Integrated_Log_v2_20260711_023000.csv"
            v2_5_metadata = v2_5_path.with_suffix(".metadata.json")
            v2_5_csv_before = v2_5_path.read_bytes()
            v2_5_metadata_before = v2_5_metadata.read_bytes()

            service.apply_config(csv_v2_temperature_hardening_enabled=False)
            v2_4_handle, _ = service._open_v2_log_file(
                "20260711_023100",
                "Factory_Integrated_Log_v2",
            )
            self.assertIsNotNone(v2_4_handle)
            service._close_v2_file(v2_4_handle)
            v2_4_path = log_dir / "Factory_Integrated_Log_v2_20260711_023100.csv"
            v2_4_metadata = v2_4_path.with_suffix(".metadata.json")

            with v2_5_path.open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(next(csv.reader(handle)), V2_5_CSV_COLUMNS)
            with v2_4_path.open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(next(csv.reader(handle)), V2_4_CSV_COLUMNS)
            self.assertEqual(v2_5_path.read_bytes(), v2_5_csv_before)
            self.assertEqual(v2_5_metadata.read_bytes(), v2_5_metadata_before)
            rollback_metadata = json.loads(v2_4_metadata.read_text(encoding="utf-8"))
            self.assertEqual(
                rollback_metadata["schema_metadata"]["schema_version"],
                CSV_SCHEMA_VERSION_V2_4,
            )
            self.assertFalse(
                rollback_metadata["schema_metadata"]["csv_v2_temperature_hardening_enabled"]
            )


if __name__ == "__main__":
    unittest.main()
