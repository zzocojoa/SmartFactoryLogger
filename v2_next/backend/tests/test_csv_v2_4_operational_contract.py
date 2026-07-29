import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backend.FacilityData.changeover_candidate_resolution_fact import (
    CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS,
    CHANGEOVER_CANDIDATE_RESOLUTION_RULE_VERSION,
    CHANGEOVER_CANDIDATE_RESOLUTION_SCHEMA_VERSION,
    PROCESS_PHASE_EVENT_FACT_COLUMNS,
    PROCESS_PHASE_EVENT_RULE_VERSION,
    PROCESS_PHASE_EVENT_SCHEMA_VERSION,
    build_changeover_candidate_resolution_fact_manifest,
    build_process_phase_event_fact_manifest,
)
from backend.FacilityData.repository import (
    CSV_SCHEMA_VERSION_V2_4,
    CSV_SCHEMA_VERSION_V2_5,
    CSVLoggerService,
    V1_CSV_COLUMNS,
    V2_3_CSV_COLUMNS,
    V2_4_CSV_COLUMNS,
    V2_5_CSV_COLUMNS,
)
from backend.FacilityData.schemas import FactoryData
from backend.FacilityData.spot_observation_fact import (
    SPOT_OBSERVATION_FACT_COLUMNS,
    SPOT_OBSERVATION_FACT_SCHEMA_VERSION,
    SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS,
    SPOT_OBSERVATION_FACT_V1_2_1_SCHEMA_VERSION,
    build_spot_observation_fact_manifest,
)
from backend.FacilityData.spot_diagnostics import SPOT_DIAGNOSTIC_OUTPUT_FIELDS
from scripts.validate_csv_v2_shadow import (
    validate as validate_csv_v2_shadow,
    validate_changeover_candidate_resolution_fact_manifest,
    validate_process_phase_event_fact_manifest,
    validate_spot_image_fact_manifest,
    validate_spot_observation_fact_manifest,
    validate_spot_configuration_snapshot,
    validate_spot_invalid_sentinel_invariants,
    validate_temperature_value_origin_invariants,
    validate_v2_4_operational_invariants,
    validate_v2_5_temperature_hardening_invariants,
)


class CsvV24OperationalContractTests(unittest.TestCase):
    image_fact_header = [
        "spot_image_capture_id",
        "spot_image_path",
        "spot_image_sha256",
        "spot_image_size_bytes",
        "spot_image_mime",
        "spot_image_link_age_ms",
        "spot_image_link_status",
        "spot_image_linked_observation_key",
    ]

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

    def build_v2_5_row(
        self,
        data: FactoryData,
        *,
        row_created_monotonic: float = 100.0,
    ) -> tuple[CSVLoggerService, list[str]]:
        service = CSVLoggerService()
        service.apply_config(
            csv_v2_operational_fields_enabled=True,
            csv_v2_temperature_hardening_enabled=True,
        )
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)
        with patch(
            "backend.FacilityData.repository.time.monotonic",
            return_value=row_created_monotonic,
        ):
            row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)
        return service, row

    def eligible_diagnostics(self, poll_seq: int = 14) -> dict[str, object]:
        return {
            "diagnostics_snapshot_id": f"spot-service-1:diag:{poll_seq}",
            "diagnostics_source_poll_seq": poll_seq,
            "diagnostics_captured_at": "2026-06-25T08:00:00Z",
            "diagnostics_capture_status": "async_complete",
            "diagnostics_collection_mode": "async_same_poll",
            "diagnostics_source": "spot_output_parameter_get",
            "diagnostics_binding_status": "same_poll",
            "diagnostics_age_ms": 10.0,
            "diagnostics_max_age_ms": 6000.0,
            "diagnostics_missing_fields": [],
            "diagnostics_field_status": {
                field: "success" for field in SPOT_DIAGNOSTIC_OUTPUT_FIELDS
            },
        }

    def config_provenance_fields(self, *, verified: bool) -> dict[str, object]:
        fingerprint = "a" * 64
        return {
            "spot_config_revision": "spot-config-provenance-v1",
            "spot_config_fingerprint_sha256": fingerprint,
            "spot_config_verified_fingerprint_sha256": fingerprint if verified else "",
            "spot_config_verified_at": "2026-07-11T01:02:03Z" if verified else "",
            "spot_config_verified_by": "operator-01" if verified else "",
            "config_operator_verified_requested": verified,
            "config_operator_verified": verified,
            "config_attestation_status": "verified" if verified else "not_requested",
            "config_drift_detected": False,
            "config_drift_fields": [],
            "device_config_readback_status": "not_supported",
            "device_config_fingerprint_sha256": "",
            "settings_file_sha256": "",
            "build_git_commit": "b" * 40 if verified else "",
        }

    def write_image_fact(self, fact_path: Path, rows: list[list[str]]) -> str:
        with fact_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.image_fact_header)
            writer.writerows(rows)
        return hashlib.sha256(fact_path.read_bytes()).hexdigest()

    def image_fact_metadata(self, fact_path: Path, capture_root: Path, *, row_count: int, sha256: str | None) -> dict:
        return {
            "spot_image_fact_manifest": {
                "enabled": True,
                "mode": "event",
                "fact_path": str(fact_path),
                "capture_root": str(capture_root),
                "row_count": row_count,
                "sha256": sha256,
                "written": row_count,
                "dropped": 0,
                "failure": 0,
                "last_write_at": 1782896400.0,
            }
        }

    def write_csv_rows(self, path: Path, header: list[str], rows: list[list[str]]) -> str:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def observation_fact_row(self, **updates: str) -> list[str]:
        field_status = {field: "success" for field in SPOT_DIAGNOSTIC_OUTPUT_FIELDS}
        evidence_code = "signal_at_or_above_configured_threshold"
        values = {
            "spot_observation_fact_schema_version": SPOT_OBSERVATION_FACT_SCHEMA_VERSION,
            "spot_observation_key": "spot-service-1:14",
            "spot_service_instance_id": "spot-service-1",
            "spot_poll_seq": "14",
            "spot_observation_seq": "14",
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_temperature_raw": "560.7",
            "spot_raw_payload_hash": "payload-hash",
            "spot_last_poll_started_at": "2026-06-25T07:59:59Z",
            "spot_last_poll_completed_at": "2026-06-25T08:00:00Z",
            "spot_poll_duration_ms": "50.0",
            "diagnostics_captured_at": "2026-06-25T08:00:00Z",
            "diagnostics_capture_status": "async_complete",
            "diagnostics_age_ms": "10.0",
            "diagnostics_snapshot_id": "spot-service-1:diag:14",
            "diagnostics_source_poll_seq": "14",
            "diagnostics_binding_status": "same_poll",
            "diagnostics_missing_fields": "[]",
            "diagnostics_field_status_json": json.dumps(field_status, sort_keys=True),
            "diagnostics_source": "async_same_poll",
            "evidence_provenance_json": json.dumps(
                {
                    evidence_code: {
                        "source_field": "signalpc",
                        "field_status": "success",
                        "age_ms": 10.0,
                        "max_age_ms": 6000.0,
                    }
                },
                sort_keys=True,
            ),
            "spot_diagnostic_evidence_codes": json.dumps([evidence_code]),
            "alarmstatus": "0",
            "signalpc": "22.5",
            "d1temperature": "35.0",
            "d2temperature": "35.1",
            "e1out": "1.0",
            "e2out": "1.1",
            "peak_picker_enabled": "false",
            "peak_picker_off_mode": "reset",
            "actuator_position": "12.0",
            "actuator_scan_state": "holding",
            "low_signal_alarm_enabled": "true",
            "low_signal_threshold_pc": "2.0",
            "low_signal_comparator": "lt",
            "low_signal_comparator_verified": "true",
        }
        values.update(updates)
        return [values.get(column, "") for column in SPOT_OBSERVATION_FACT_COLUMNS]

    def write_observation_fact(self, path: Path, rows: list[list[str]]) -> str:
        return self.write_csv_rows(path, list(SPOT_OBSERVATION_FACT_COLUMNS), rows)

    def write_v2_source_fixture(self, path: Path) -> str:
        return self.write_csv_rows(
            path,
            ["schema_version", "sample_seq", "timestamp_utc"],
            [["2.4.0", "1", "2026-06-25T00:00:00Z"]],
        )

    def build_valid_temperature_v2_4_row(
        self,
        *,
        timestamp_utc: datetime | None = None,
        poll_completed_at: datetime | None = None,
    ) -> list[str]:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        poll_completed_at = poll_completed_at or datetime(2026, 6, 25, 8, 0, 0, tzinfo=timezone.utc)
        timestamp_utc = timestamp_utc or poll_completed_at
        data = self.create_data().model_copy(
            update={
                "Time": timestamp_utc.isoformat(),
                "Spot": 560.7,
                "spot_temperature_observed_c": 560.7,
                "spot_temperature_raw": "560.7",
                "spot_raw_validity": "valid_temperature",
                "spot_device_status_code": None,
                "temperature_status_shadow": "ok",
                "temperature_value_origin": "current_observation",
                "spot_last_poll_completed_at": poll_completed_at.isoformat().replace("+00:00", "Z"),
                "spot_snapshot_age_ms": 10.0,
                "spot_value_age_ms": 10.0,
            }
        )
        return service._build_v2_row(
            data,
            timestamp_utc,
            timestamp_utc,
            1,
            service._build_row(data, timestamp_utc),
        )

    def write_resolution_fact_fixture(self, path: Path, source_hash: str) -> str:
        return self.write_csv_rows(
            path,
            CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS,
            [
                [
                    CHANGEOVER_CANDIDATE_RESOLUTION_SCHEMA_VERSION,
                    "chg_1",
                    "confirmed",
                    "2026-06-25T00:00:00Z",
                    CHANGEOVER_CANDIDATE_RESOLUTION_RULE_VERSION,
                    f"sha256:{source_hash}",
                    "logger-1",
                    "1",
                    "1",
                    "",
                    "0",
                    "[]",
                    "setup_candidate_mapped_posthoc",
                    "0.650",
                ]
            ],
        )

    def write_event_fact_fixture(self, path: Path, source_hash: str) -> str:
        return self.write_csv_rows(
            path,
            PROCESS_PHASE_EVENT_FACT_COLUMNS,
            [
                [
                    PROCESS_PHASE_EVENT_SCHEMA_VERSION,
                    "pevt_1",
                    "chg_1",
                    f"sha256:{source_hash}",
                    "logger-1",
                    "1",
                    "1",
                    "2026-06-25T00:00:00Z",
                    "2026-06-25T00:00:00Z",
                    "setup",
                    "expected",
                    "posthoc_confirmed",
                    PROCESS_PHASE_EVENT_RULE_VERSION,
                    "setup_candidate_mapped_posthoc",
                    "0.650",
                ]
            ],
        )

    def process_phase_fact_metadata(
        self,
        *,
        v2_path: Path,
        resolution_path: Path,
        event_path: Path,
    ) -> dict:
        return {
            "schema_metadata": {
                "posthoc_fact_manifests": [
                    "changeover_candidate_resolution_fact_manifest",
                    "process_phase_event_fact_manifest",
                ]
            },
            "changeover_candidate_resolution_fact_manifest": (
                build_changeover_candidate_resolution_fact_manifest(
                    fact_path=resolution_path,
                    source_csv_path=v2_path,
                )
            ),
            "process_phase_event_fact_manifest": build_process_phase_event_fact_manifest(
                fact_path=event_path,
                source_csv_path=v2_path,
            ),
        }

    def test_spot_image_fact_manifest_validator_accepts_matching_fact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            fact_path = log_dir / "spot_image_fact.csv"
            capture_root = log_dir / "spot_images"
            fact_hash = self.write_image_fact(
                fact_path,
                [
                    [
                        "spotimg_20260701T010856283905Z_fe0d2cf21603",
                        "spot_images/2026/07/01/spotimg_20260701T010856283905Z_fe0d2cf21603.jpg",
                        "a" * 64,
                        "9064",
                        "image/jpeg",
                        "125.0",
                        "fresh",
                        "svc-1:42",
                    ]
                ],
            )
            metadata = self.image_fact_metadata(fact_path, capture_root, row_count=1, sha256=fact_hash)

            failures, summary = validate_spot_image_fact_manifest(metadata, log_dir / "sample.metadata.json")

        self.assertEqual(failures, [])
        self.assertEqual(summary["spot_image_fact_validation_source"], "metadata_manifest")
        self.assertEqual(summary["spot_image_fact_row_count_match"], "true")
        self.assertEqual(summary["spot_image_fact_sha256_match"], "true")

    def test_spot_image_fact_final_manifest_validator_accepts_matching_bundle_fact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            fact_path = log_dir / "spot_image_fact.csv"
            capture_root = log_dir / "spot_images"
            fact_hash = self.write_image_fact(
                fact_path,
                [
                    [
                        "spotimg_20260701T010856283905Z_fe0d2cf21603",
                        "spot_images/2026/07/01/spotimg_20260701T010856283905Z_fe0d2cf21603.jpg",
                        "a" * 64,
                        "9064",
                        "image/jpeg",
                        "125.0",
                        "fresh",
                        "svc-1:42",
                    ]
                ],
            )
            metadata = self.image_fact_metadata(
                log_dir / "missing_live_spot_image_fact.csv",
                capture_root,
                row_count=0,
                sha256=None,
            )
            final_manifest = self.image_fact_metadata(
                log_dir / "live_spot_image_fact.csv",
                capture_root,
                row_count=1,
                sha256=fact_hash,
            )["spot_image_fact_manifest"]
            final_manifest_path = log_dir / "spot_image_fact_manifest.final.json"
            final_manifest_path.write_text(
                json.dumps(final_manifest, ensure_ascii=False),
                encoding="utf-8",
            )

            failures, summary = validate_spot_image_fact_manifest(
                metadata,
                log_dir / "sample.metadata.json",
                spot_image_fact_path=fact_path,
                spot_image_fact_final_manifest_path=final_manifest_path,
            )

        self.assertEqual(failures, [])
        self.assertEqual(summary["spot_image_fact_validation_source"], "final_manifest")
        self.assertEqual(summary["spot_image_fact_final_manifest_provided"], "true")
        self.assertEqual(summary["spot_image_fact_final_manifest_file"], "spot_image_fact_manifest.final.json")
        self.assertEqual(summary["spot_image_fact_row_count_match"], "true")
        self.assertEqual(summary["spot_image_fact_sha256_match"], "true")

    def test_spot_image_fact_final_manifest_validator_rejects_mismatch_even_with_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            fact_path = log_dir / "spot_image_fact.csv"
            capture_root = log_dir / "spot_images"
            self.write_image_fact(
                fact_path,
                [
                    [
                        "spotimg_20260701T010856283905Z_fe0d2cf21603",
                        "spot_images/2026/07/01/spotimg_20260701T010856283905Z_fe0d2cf21603.jpg",
                        "a" * 64,
                        "9064",
                        "image/jpeg",
                        "125.0",
                        "fresh",
                        "svc-1:42",
                    ]
                ],
            )
            metadata = self.image_fact_metadata(
                log_dir / "missing_live_spot_image_fact.csv",
                capture_root,
                row_count=0,
                sha256=None,
            )
            final_manifest = self.image_fact_metadata(
                log_dir / "live_spot_image_fact.csv",
                capture_root,
                row_count=2,
                sha256="0" * 64,
            )["spot_image_fact_manifest"]
            final_manifest_path = log_dir / "spot_image_fact_manifest.final.json"
            final_manifest_path.write_text(
                json.dumps(final_manifest, ensure_ascii=False),
                encoding="utf-8",
            )

            failures, summary = validate_spot_image_fact_manifest(
                metadata,
                log_dir / "sample.metadata.json",
                spot_image_fact_path=fact_path,
                spot_image_fact_final_manifest_path=final_manifest_path,
            )

        self.assertIn("spot_image_fact_final_manifest.sha256 does not match fact file", failures)
        self.assertIn("spot_image_fact_final_manifest.row_count=2, actual spot_image_fact rows=1", failures)
        self.assertEqual(summary["spot_image_fact_validation_source"], "final_manifest")
        self.assertEqual(summary["spot_image_fact_row_count_match"], "false")
        self.assertEqual(summary["spot_image_fact_sha256_match"], "false")

    def test_spot_image_fact_manifest_validator_rejects_mismatched_stats_and_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            fact_path = log_dir / "spot_image_fact.csv"
            capture_root = log_dir / "spot_images"
            self.write_image_fact(
                fact_path,
                [
                    [
                        "spotimg_20260701T010856283905Z_fe0d2cf21603",
                        "../escape.jpg",
                        "not-a-sha",
                        "9064",
                        "image/jpeg",
                        "125.0",
                        "fresh",
                        "",
                    ]
                ],
            )
            metadata = self.image_fact_metadata(fact_path, capture_root, row_count=2, sha256="0" * 64)

            failures, summary = validate_spot_image_fact_manifest(metadata, log_dir / "sample.metadata.json")

        self.assertIn("spot_image_fact_manifest.sha256 does not match fact file", failures)
        self.assertIn("spot_image_fact_manifest.row_count=2, actual spot_image_fact rows=1", failures)
        self.assertIn("spot_image_fact row 2 spot_image_sha256 must be lowercase SHA-256", failures)
        self.assertIn("spot_image_fact row 2 fresh link requires spot_image_linked_observation_key", failures)
        self.assertIn("spot_image_fact row 2 spot_image_path must be a safe relative path", failures)
        self.assertEqual(summary["spot_image_fact_row_count_match"], "false")
        self.assertEqual(summary["spot_image_fact_sha256_match"], "false")

    def test_spot_image_fact_manifest_validator_rejects_raw_url_and_full_paths(self) -> None:
        unsafe_paths = (
            "http://10.1.10.50/image.jpg",
            "https://camera.local/image.jpg",
            "file:///C:/SmartFactory/image.jpg",
            "C:/SmartFactory/image.jpg",
            "\\\\server\\share\\image.jpg",
            "/var/smartfactory/image.jpg",
            "../escape.jpg",
        )
        for unsafe_path in unsafe_paths:
            with self.subTest(unsafe_path=unsafe_path), tempfile.TemporaryDirectory() as tmp:
                log_dir = Path(tmp)
                fact_path = log_dir / "spot_image_fact.csv"
                capture_root = log_dir / "spot_images"
                fact_hash = self.write_image_fact(
                    fact_path,
                    [
                        [
                            "spotimg_20260701T010856283905Z_fe0d2cf21603",
                            unsafe_path,
                            "a" * 64,
                            "9064",
                            "image/jpeg",
                            "125.0",
                            "fresh",
                            "svc-1:42",
                        ]
                    ],
                )
                metadata = self.image_fact_metadata(fact_path, capture_root, row_count=1, sha256=fact_hash)

                failures, _summary = validate_spot_image_fact_manifest(
                    metadata,
                    log_dir / "sample.metadata.json",
                )

            self.assertIn("spot_image_fact row 2 spot_image_path must be a safe relative path", failures)

    def test_spot_image_fact_manifest_validator_rejects_missing_header_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            fact_path = log_dir / "spot_image_fact.csv"
            capture_root = log_dir / "spot_images"
            header = [column for column in self.image_fact_header if column != "spot_image_link_status"]
            row = [
                "spotimg_20260701T010856283905Z_fe0d2cf21603",
                "spot_images/2026/07/01/spotimg_20260701T010856283905Z_fe0d2cf21603.jpg",
                "a" * 64,
                "9064",
                "image/jpeg",
                "125.0",
                "svc-1:42",
            ]
            with fact_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                writer.writerow(row)
            fact_hash = hashlib.sha256(fact_path.read_bytes()).hexdigest()
            metadata = self.image_fact_metadata(fact_path, capture_root, row_count=1, sha256=fact_hash)

            failures, summary = validate_spot_image_fact_manifest(metadata, log_dir / "sample.metadata.json")

        self.assertIn("spot_image_fact header missing columns: spot_image_link_status", failures)
        self.assertEqual(summary["spot_image_fact_actual_row_count"], "1")
        self.assertEqual(summary["spot_image_fact_row_count_match"], "true")
        self.assertEqual(summary["spot_image_fact_sha256_match"], "true")

    def test_process_phase_fact_manifest_validators_accept_matching_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260625_000000.csv"
            source_hash = self.write_v2_source_fixture(v2_path)
            resolution_path = log_dir / "changeover_candidate_resolution_fact.csv"
            event_path = log_dir / "process_phase_event_fact.csv"
            self.write_resolution_fact_fixture(resolution_path, source_hash)
            self.write_event_fact_fixture(event_path, source_hash)
            metadata = self.process_phase_fact_metadata(
                v2_path=v2_path,
                resolution_path=resolution_path,
                event_path=event_path,
            )

            resolution_failures, resolution_summary = validate_changeover_candidate_resolution_fact_manifest(
                metadata,
                log_dir / "sample.metadata.json",
                v2_path,
            )
            event_failures, event_summary = validate_process_phase_event_fact_manifest(
                metadata,
                log_dir / "sample.metadata.json",
                v2_path,
            )

        self.assertEqual(resolution_failures, [])
        self.assertEqual(event_failures, [])
        self.assertEqual(resolution_summary["changeover_candidate_resolution_fact_row_count_match"], "true")
        self.assertEqual(resolution_summary["changeover_candidate_resolution_fact_sha256_match"], "true")
        self.assertEqual(resolution_summary["changeover_candidate_resolution_fact_source_csv_sha256_match"], "true")
        self.assertEqual(event_summary["process_phase_event_fact_row_count_match"], "true")
        self.assertEqual(event_summary["process_phase_event_fact_sha256_match"], "true")
        self.assertEqual(event_summary["process_phase_event_fact_source_csv_sha256_match"], "true")

    def test_process_phase_fact_manifest_validator_rejects_mismatched_source_and_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260625_000000.csv"
            source_hash = self.write_v2_source_fixture(v2_path)
            resolution_path = log_dir / "changeover_candidate_resolution_fact.csv"
            header = [
                column
                for column in CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS
                if column != "source_file_id"
            ]
            self.write_csv_rows(resolution_path, header, [[""] * len(header)])
            event_path = log_dir / "process_phase_event_fact.csv"
            self.write_event_fact_fixture(event_path, source_hash)
            metadata = self.process_phase_fact_metadata(
                v2_path=v2_path,
                resolution_path=resolution_path,
                event_path=event_path,
            )
            manifest = metadata["changeover_candidate_resolution_fact_manifest"]
            manifest["source_csv_sha256"] = "0" * 64
            manifest["source_file_id"] = "sha256:" + ("0" * 64)

            failures, summary = validate_changeover_candidate_resolution_fact_manifest(
                metadata,
                log_dir / "sample.metadata.json",
                v2_path,
            )

        self.assertIn("changeover_candidate_resolution_fact_manifest.source_csv_sha256 does not match v2 CSV", failures)
        self.assertIn("changeover_candidate_resolution_fact header missing columns: source_file_id", failures)
        self.assertEqual(summary["changeover_candidate_resolution_fact_source_csv_sha256_match"], "false")

    def test_process_phase_fact_manifest_validator_accepts_portable_override_stats_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            bundle_dir = log_dir / "bundle"
            bundle_dir.mkdir()
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260625_000000.csv"
            source_hash = self.write_v2_source_fixture(v2_path)
            metadata = {
                "schema_metadata": {
                    "posthoc_fact_manifests": ["changeover_candidate_resolution_fact_manifest"]
                },
                "changeover_candidate_resolution_fact_manifest": (
                    build_changeover_candidate_resolution_fact_manifest(
                        fact_path=log_dir / "missing_changeover_candidate_resolution_fact.csv",
                        source_csv_path=v2_path,
                    )
                ),
            }
            manifest = metadata["changeover_candidate_resolution_fact_manifest"]
            manifest["row_count"] = 2
            manifest["sha256"] = "0" * 64
            override_path = bundle_dir / "changeover_candidate_resolution_fact.csv"
            self.write_resolution_fact_fixture(override_path, source_hash)

            failures, summary = validate_changeover_candidate_resolution_fact_manifest(
                metadata,
                log_dir / "sample.metadata.json",
                v2_path,
                fact_path=override_path,
            )

        self.assertEqual(failures, [])
        self.assertEqual(summary["changeover_candidate_resolution_fact_validation_source"], "override")
        self.assertEqual(summary["changeover_candidate_resolution_fact_row_count_match"], "false")
        self.assertEqual(summary["changeover_candidate_resolution_fact_sha256_match"], "false")

    def test_process_phase_fact_manifest_validator_ignores_legacy_metadata_without_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260625_000000.csv"
            self.write_v2_source_fixture(v2_path)
            metadata = {"schema_metadata": {"schema_version": "2.4.0"}}

            failures, summary = validate_changeover_candidate_resolution_fact_manifest(
                metadata,
                log_dir / "sample.metadata.json",
                v2_path,
            )

        self.assertEqual(failures, [])
        self.assertEqual(summary["changeover_candidate_resolution_fact_validation_source"], "not_applicable")

    def build_v2_row(
        self,
        service: CSVLoggerService,
        data: FactoryData,
        sample_seq: int = 1,
    ) -> list[object]:
        timestamp = service._parse_timestamp(data)
        ingest_timestamp = timestamp.astimezone()
        if data.spot_last_poll_completed_at is None:
            data = data.model_copy(
                update={
                    "spot_last_poll_completed_at": ingest_timestamp.astimezone(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                }
            )
        v1_row = service._build_row(data, timestamp)
        return service._build_v2_row(data, timestamp, ingest_timestamp, sample_seq, v1_row)

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

    def test_v2_4_row_ignores_explicit_observation_key_when_builder_disallows_key(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        timestamp = datetime(2026, 6, 25, 8, 0, 0, tzinfo=timezone.utc)
        index = V2_4_CSV_COLUMNS.index("spot_observation_key")
        cases = [
            {"spot_poll_seq": 0},
            {"spot_poll_seq": -1},
            {"spot_poll_status": "not_attempted"},
            {"spot_last_poll_completed_at": ""},
            {"temperature_output_status": "startup_pending"},
            {"temperature_status_shadow": "startup_pending"},
        ]

        for update in cases:
            with self.subTest(update=update):
                data = self.create_data().model_copy(
                    update={
                        "Time": timestamp.isoformat(),
                        "spot_last_poll_completed_at": "2026-06-25T08:00:00Z",
                        "spot_observation_key": "manual-service:999",
                        **update,
                    }
                )

                row = service._build_v2_row(data, timestamp, timestamp, 1, service._build_row(data, timestamp))

                self.assertEqual(row[index], "")

    def test_v2_4_row_uses_canonical_observation_key_over_explicit_key(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        timestamp = datetime(2026, 6, 25, 8, 0, 0, tzinfo=timezone.utc)
        data = self.create_data().model_copy(
            update={
                "Time": timestamp.isoformat(),
                "spot_last_poll_completed_at": "2026-06-25T08:00:00Z",
                "spot_observation_key": "manual-service:999",
            }
        )

        row = service._build_v2_row(data, timestamp, timestamp, 1, service._build_row(data, timestamp))

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_observation_key")], "spot-service-1:14")

    def test_v2_4_row_uses_signalpc_config_for_under_range_low_signal_cause(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "spot_diagnostic_evidence_codes": '["signal_below_threshold"]',
                "signalpc": 3.2,
                "low_signal_alarm_enabled": True,
                "low_signal_threshold_pc": 5.0,
                "low_signal_comparator": "lte",
                "low_signal_comparator_verified": True,
                **self.eligible_diagnostics(),
            }
        )

        row = self.build_v2_row(service, data)

        self.assertEqual(
            row[V2_4_CSV_COLUMNS.index("temperature_under_range_cause_candidate")],
            "low_signal_candidate",
        )
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_cause_confidence")], "0.65")
        self.assertEqual(
            row[V2_4_CSV_COLUMNS.index("temperature_cause_evidence_codes")],
            '["phase_setup_candidate","signal_below_threshold"]',
        )

    def test_v2_4_row_ignores_stale_low_signal_evidence_without_config_inputs(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(update={"spot_diagnostic_evidence_codes": '["signal_below_threshold"]'})

        row = self.build_v2_row(service, data)

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_under_range_cause_candidate")], "unknown")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_cause_confidence")], "0.0")
        self.assertEqual(
            row[V2_4_CSV_COLUMNS.index("temperature_cause_evidence_codes")],
            '["diagnostics_missing_or_stale","phase_setup_candidate"]',
        )

    def test_v2_4_row_suppresses_collectorless_cause_and_counts_it(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={"spot_diagnostic_evidence_codes": '["target_out_of_fov_evidence"]'}
        )

        row = self.build_v2_row(service, data)
        summary = service.get_v2_4_operational_summary()

        self.assertEqual(
            row[V2_4_CSV_COLUMNS.index("temperature_under_range_cause_candidate")],
            "unknown",
        )
        self.assertIn(
            "target_out_of_fov_evidence",
            json.loads(row[V2_4_CSV_COLUMNS.index("temperature_cause_evidence_codes")]),
        )
        self.assertEqual(summary["unsupported_evidence_suppressed_count"], 1)

        invalid_row = list(row)
        invalid_row[V2_4_CSV_COLUMNS.index("temperature_under_range_cause_candidate")] = (
            "target_out_of_fov_candidate"
        )
        failures = validate_v2_4_operational_invariants(
            [invalid_row],
            V2_4_CSV_COLUMNS,
            forbid_unsupported_causes=True,
        )
        self.assertTrue(any("provenance-capable collector" in failure for failure in failures))

    def test_v2_4_row_uses_alarmstatus_bit4_for_under_range_low_signal_cause(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={"alarmstatus": "0x10", **self.eligible_diagnostics()}
        )

        row = self.build_v2_row(service, data)

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_under_range_cause_candidate")], "low_signal_candidate")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_cause_confidence")], "0.85")
        self.assertEqual(
            row[V2_4_CSV_COLUMNS.index("temperature_cause_evidence_codes")],
            '["alarm_low_signal","phase_setup_candidate"]',
        )

    def test_v2_4_summary_counts_previous_poll_diagnostics_suppression(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "alarmstatus": "0x10",
                **self.eligible_diagnostics(),
                "diagnostics_source_poll_seq": 13,
                "diagnostics_binding_status": "previous_poll",
            }
        )

        row = self.build_v2_row(service, data)
        summary = service.get_v2_4_operational_summary()

        self.assertEqual(
            row[V2_4_CSV_COLUMNS.index("temperature_under_range_cause_candidate")],
            "unknown",
        )
        self.assertEqual(summary["diagnostics_capture_status_counts"], {"async_complete": 1})
        self.assertEqual(summary["diagnostics_binding_status_counts"], {"previous_poll": 1})
        self.assertEqual(summary["diagnostics_cause_suppressed_count"], 1)
        self.assertEqual(
            summary["diagnostics_cause_suppressed_reason_counts"],
            {"previous_poll": 1},
        )

    def test_v2_4_row_uses_local_max_age_instead_of_snapshot_override(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "alarmstatus": "0x10",
                **self.eligible_diagnostics(),
                "diagnostics_age_ms": 7000.0,
                "diagnostics_max_age_ms": 999999.0,
            }
        )

        with patch("backend.FacilityData.repository.config.SPOT_REFRESH_INTERVAL", 3.0):
            row = self.build_v2_row(service, data)
        summary = service.get_v2_4_operational_summary()

        self.assertEqual(
            row[V2_4_CSV_COLUMNS.index("temperature_under_range_cause_candidate")],
            "unknown",
        )
        self.assertEqual(
            summary["diagnostics_cause_suppressed_reason_counts"],
            {"stale": 1},
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

    def test_count_three_high_motion_under_range_maps_to_production_stabilizing(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "Count": 3,
                "Speed": 1.0,
                "Press": 35.0,
                "extruder_process_state_online": "extruding",
            }
        )

        row = self.build_v2_row(service, data)

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("Temperature")], "")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "under_range")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("process_phase_candidate")], "production_stabilizing")
        self.assertTrue(row[V2_4_CSV_COLUMNS.index("process_segment_id")].startswith("seg_"))
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("changeover_candidate_id")], "")
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
        weak_segment_id = rows[1][V2_4_CSV_COLUMNS.index("process_segment_id")]

        self.assertEqual(rows[0][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "production_stable")
        self.assertTrue(segment_id.startswith("seg_"))
        self.assertEqual(rows[0][V2_4_CSV_COLUMNS.index("changeover_candidate_id")], "")
        self.assertEqual(rows[1][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "stopped_after_production_candidate")
        self.assertTrue(weak_segment_id.startswith("seg_"))
        self.assertEqual(rows[1][V2_4_CSV_COLUMNS.index("changeover_candidate_id")], "")
        self.assertEqual(rows[1][V2_4_CSV_COLUMNS.index("temperature_output_status")], "under_range")
        self.assertEqual(rows[1][V2_4_CSV_COLUMNS.index("temperature_expectedness_candidate")], "unknown")
        self.assertEqual(
            rows[1][V2_4_CSV_COLUMNS.index("temperature_under_range_cause_candidate")],
            "unknown",
        )
        self.assertEqual(rows[1][V2_4_CSV_COLUMNS.index("temperature_cause_confidence")], "0.0")
        self.assertEqual(rows[2][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "stopped_after_production_candidate")
        self.assertEqual(rows[2][V2_4_CSV_COLUMNS.index("process_segment_id")], weak_segment_id)
        self.assertEqual(rows[2][V2_4_CSV_COLUMNS.index("changeover_candidate_id")], "")
        self.assertEqual(rows[2][V2_4_CSV_COLUMNS.index("temperature_output_status")], "source_error")
        self.assertEqual(rows[3][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "stopped_after_production_candidate")
        self.assertEqual(rows[3][V2_4_CSV_COLUMNS.index("process_segment_id")], weak_segment_id)
        self.assertEqual(rows[3][V2_4_CSV_COLUMNS.index("changeover_candidate_id")], "")
        self.assertEqual(rows[4][V2_4_CSV_COLUMNS.index("process_phase_candidate")], "production_stable")
        self.assertEqual(rows[4][V2_4_CSV_COLUMNS.index("changeover_candidate_id")], "")
        self.assertTrue(rows[4][V2_4_CSV_COLUMNS.index("process_segment_id")].startswith("seg_"))

    def test_external_pre_changeover_hold_candidate_under_range_is_not_trusted_as_strong_candidate(self) -> None:
        cases = [
            ("possible_pre_changeover_hold", "stopped_after_production_candidate", "unknown", "seg_", ""),
            ("pre_changeover_hold_candidate", "stopped_after_production_candidate", "unknown", "seg_", ""),
        ]

        for supplied_phase, emitted_phase, expectedness, segment_prefix, changeover_prefix in cases:
            with self.subTest(supplied_phase=supplied_phase):
                candidate_service = CSVLoggerService()
                candidate_service.apply_config(csv_v2_operational_fields_enabled=True)
                data = self.create_data().model_copy(update={"process_phase_candidate": supplied_phase})

                row = self.build_v2_row(candidate_service, data)

                self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "under_range")
                self.assertEqual(row[V2_4_CSV_COLUMNS.index("process_phase_candidate")], emitted_phase)
                self.assertEqual(row[V2_4_CSV_COLUMNS.index("phase_confirmation_state")], "realtime_candidate")
                self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_expectedness_candidate")], expectedness)
                process_segment_id = row[V2_4_CSV_COLUMNS.index("process_segment_id")]
                changeover_candidate_id = row[V2_4_CSV_COLUMNS.index("changeover_candidate_id")]
                if segment_prefix:
                    self.assertTrue(process_segment_id.startswith(segment_prefix))
                else:
                    self.assertEqual(process_segment_id, "")
                if changeover_prefix:
                    self.assertTrue(changeover_candidate_id.startswith(changeover_prefix))
                else:
                    self.assertEqual(changeover_candidate_id, "")

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

    def test_v2_4_row_computes_effective_age_at_row_from_poll_completed_at(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        poll_completed_at = datetime(2026, 6, 25, 8, 0, 0, tzinfo=timezone.utc)
        ingest_timestamp = poll_completed_at + timedelta(seconds=4)
        data = self.create_data().model_copy(
            update={
                "Time": ingest_timestamp.isoformat(),
                "spot_last_poll_completed_at": poll_completed_at.isoformat().replace("+00:00", "Z"),
                "spot_snapshot_age_ms": 10.0,
                "spot_value_age_ms": 10.0,
            }
        )
        with patch("backend.FacilityData.repository.config.SPOT_REFRESH_INTERVAL", 1.0):
            row = service._build_v2_row(
                data,
                ingest_timestamp,
                ingest_timestamp,
                1,
                service._build_row(data, ingest_timestamp),
            )

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_effective_age_ms_at_row")], "4000.0")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_effective_freshness_at_row")], "stale")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "stale")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")], "stale_observation")

    def test_v2_4_row_recomputes_effective_age_when_explicit_snapshot_age_is_present(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        poll_completed_at = datetime(2026, 6, 25, 8, 0, 0, tzinfo=timezone.utc)
        ingest_timestamp = poll_completed_at + timedelta(seconds=4)
        data = self.create_data().model_copy(
            update={
                "Time": ingest_timestamp.isoformat(),
                "spot_last_poll_completed_at": poll_completed_at.isoformat().replace("+00:00", "Z"),
                "spot_effective_age_ms_at_row": 10.0,
                "spot_snapshot_age_ms": 10.0,
                "spot_value_age_ms": 10.0,
            }
        )
        with patch("backend.FacilityData.repository.config.SPOT_REFRESH_INTERVAL", 1.0):
            row = service._build_v2_row(
                data,
                ingest_timestamp,
                ingest_timestamp,
                1,
                service._build_row(data, ingest_timestamp),
            )

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_snapshot_age_ms")], "10.0")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_effective_age_ms_at_row")], "4000.0")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_effective_freshness_at_row")], "stale")

    def test_v2_4_row_prefers_monotonic_effective_age_over_ingest_timestamp_age(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        poll_completed_at = datetime(2026, 6, 25, 8, 0, 0, tzinfo=timezone.utc)
        row_timestamp = poll_completed_at + timedelta(seconds=1)
        ingest_timestamp = poll_completed_at + timedelta(minutes=10)
        data = self.create_data().model_copy(
            update={
                "Time": row_timestamp.isoformat(),
                "spot_last_poll_completed_at": poll_completed_at.isoformat().replace("+00:00", "Z"),
                "spot_last_poll_completed_monotonic": 100.0,
                "spot_effective_age_ms_at_row": 9999.0,
                "spot_snapshot_age_ms": 10.0,
                "spot_value_age_ms": 10.0,
            }
        )

        with (
            patch("backend.FacilityData.repository.config.SPOT_REFRESH_INTERVAL", 1.0),
            patch("backend.FacilityData.repository.time.monotonic", return_value=101.25),
        ):
            row = service._build_v2_row(
                data,
                row_timestamp,
                ingest_timestamp,
                1,
                service._build_row(data, row_timestamp),
            )

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_effective_age_ms_at_row")], "1250.0")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_effective_freshness_at_row")], "fresh")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "under_range")

    def test_v2_4_row_timestamp_age_prevents_monotonic_threshold_bypass(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        poll_completed_at = datetime(2026, 6, 25, 8, 0, 0, tzinfo=timezone.utc)
        row_timestamp = poll_completed_at + timedelta(milliseconds=3006)
        data = self.create_data().model_copy(
            update={
                "Time": row_timestamp.isoformat(),
                "spot_last_poll_completed_at": poll_completed_at.isoformat().replace("+00:00", "Z"),
                "spot_last_poll_completed_monotonic": 100.0,
                "spot_snapshot_age_ms": 10.0,
                "spot_value_age_ms": 10.0,
            }
        )

        with (
            patch("backend.FacilityData.repository.config.SPOT_REFRESH_INTERVAL", 1.0),
            patch("backend.FacilityData.repository.time.monotonic", return_value=103.0),
        ):
            row = service._build_v2_row(
                data,
                row_timestamp,
                row_timestamp,
                1,
                service._build_row(data, row_timestamp),
            )

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_effective_age_ms_at_row")], "3006.0")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_effective_freshness_at_row")], "stale")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "stale")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")], "stale_observation")

    def test_v2_4_validator_accepts_source_stale_invalid_sentinel_with_fresh_effective_age(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "spot_source_freshness": "stale",
                "spot_cache_status": "expired",
                "temperature_status_shadow": "stale",
                "spot_target_state_observed_shadow": "unknown",
                "spot_snapshot_age_ms": 3_000.0,
                "spot_value_age_ms": 540_000.0,
            }
        )
        timestamp = service._parse_timestamp(data)
        row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, service._build_row(data, timestamp))

        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_effective_freshness_at_row")], "fresh")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "stale")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")], "stale_observation")
        self.assertEqual(validate_spot_invalid_sentinel_invariants([row], V2_4_CSV_COLUMNS), [])
        self.assertEqual(validate_v2_4_operational_invariants([row], V2_4_CSV_COLUMNS), [])

    def test_v2_4_validator_accepts_stale_invalid_sentinel_without_cached_value(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "spot_source_freshness": "stale",
                "spot_cache_status": "empty",
                "temperature_status_shadow": "unknown_missing",
                "spot_target_state_observed_shadow": "unknown",
                "spot_snapshot_age_ms": 4_375.0,
                "spot_value_age_ms": None,
            }
        )
        timestamp = service._parse_timestamp(data)
        row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, service._build_row(data, timestamp))
        row = list(row)
        row[V2_4_CSV_COLUMNS.index("spot_effective_freshness_at_row")] = "stale"
        row[V2_4_CSV_COLUMNS.index("temperature_output_status")] = "stale"
        row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")] = "stale_observation"
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_effective_freshness_at_row")], "stale")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "stale")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")], "stale_observation")
        self.assertEqual(validate_spot_invalid_sentinel_invariants([row], V2_4_CSV_COLUMNS), [])
        self.assertEqual(validate_v2_4_operational_invariants([row], V2_4_CSV_COLUMNS), [])

    def test_fresh_invalid_sentinel_invariant_remains_strict(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "spot_source_freshness": "fresh",
                "spot_cache_status": "available_not_used",
                "temperature_status_shadow": "invalid_value",
                "spot_target_state_observed_shadow": "unknown",
                "spot_snapshot_age_ms": 3_000.0,
            }
        )
        timestamp = service._parse_timestamp(data)
        row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, service._build_row(data, timestamp))

        self.assertEqual(validate_spot_invalid_sentinel_invariants([row], V2_4_CSV_COLUMNS), [])
        self.assertEqual(validate_v2_4_operational_invariants([row], V2_4_CSV_COLUMNS), [])

        stale_shadow_row = list(row)
        stale_shadow_row[V2_4_CSV_COLUMNS.index("temperature_status_shadow")] = "stale"
        self.assertIn(
            "row 2 temperature_status_shadow='stale', expected 'invalid_value'",
            validate_spot_invalid_sentinel_invariants([stale_shadow_row], V2_4_CSV_COLUMNS),
        )

        stale_output_row = list(row)
        stale_output_row[V2_4_CSV_COLUMNS.index("temperature_output_status")] = "stale"
        stale_output_row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")] = "stale_observation"
        self.assertIn(
            "row 2 invalid_sentinel output status 'stale', expected 'under_range'",
            validate_v2_4_operational_invariants([stale_output_row], V2_4_CSV_COLUMNS),
        )

    def test_v2_4_validator_accepts_stale_expired_observed_value_not_used(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "Spot": None,
                "spot_poll_status": "success",
                "spot_raw_validity": "valid_temperature",
                "spot_source_freshness": "stale",
                "spot_cache_status": "expired",
                "temperature_status_shadow": "stale",
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
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_cache_status")], "expired")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_temperature_observed_c")], "560.7")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_output_status")], "stale")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")], "stale_observation")
        self.assertEqual(validate_temperature_value_origin_invariants([row], V2_4_CSV_COLUMNS), [])
        self.assertEqual(validate_v2_4_operational_invariants([row], V2_4_CSV_COLUMNS), [])

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
        row = self.build_valid_temperature_v2_4_row()

        self.assertEqual(validate_v2_4_operational_invariants([row], header), [])

    def test_v2_4_validator_rejects_timestamp_stale_row_left_fresh_valid(self) -> None:
        header = V2_4_CSV_COLUMNS
        row = self.build_valid_temperature_v2_4_row()
        row[header.index("timestamp_utc")] = "2026-06-25T08:00:04Z"

        failures = validate_v2_4_operational_invariants(
            [row],
            header,
            row_time_freshness_threshold_ms=3000.0,
        )

        self.assertTrue(
            any("spot_effective_freshness_at_row='fresh'" in failure for failure in failures),
            failures,
        )
        self.assertTrue(
            any("temperature_output_status='valid'" in failure for failure in failures),
            failures,
        )

    def test_v2_4_validator_startup_row_allows_missing_poll_completed_timestamp(self) -> None:
        header = V2_4_CSV_COLUMNS
        row = self.build_valid_temperature_v2_4_row()
        row[header.index("Temperature")] = ""
        row[header.index("spot_poll_status")] = "not_attempted"
        row[header.index("spot_raw_validity")] = "not_received"
        row[header.index("spot_source_freshness")] = "unknown"
        row[header.index("spot_device_status_code")] = ""
        row[header.index("spot_last_poll_completed_at")] = ""
        row[header.index("spot_effective_freshness_at_row")] = "unknown"
        row[header.index("spot_row_age_clock_status")] = "unknown"
        row[header.index("temperature_output_status")] = "startup_pending"
        row[header.index("temperature_unavailable_reason")] = "startup_pending"
        row[header.index("temperature_value_origin")] = "none"
        row[header.index("spot_observation_key")] = ""

        self.assertEqual(
            validate_v2_4_operational_invariants(
                [row],
                header,
                row_time_freshness_threshold_ms=3000.0,
            ),
            [],
        )

    def test_v2_4_validator_rejects_nonblank_observation_key_for_startup_keyless_rows(self) -> None:
        header = V2_4_CSV_COLUMNS
        row = self.build_valid_temperature_v2_4_row()
        row[header.index("Temperature")] = ""
        row[header.index("spot_poll_status")] = "not_attempted"
        row[header.index("spot_poll_seq")] = "0"
        row[header.index("spot_raw_validity")] = "not_received"
        row[header.index("spot_source_freshness")] = "unknown"
        row[header.index("spot_device_status_code")] = ""
        row[header.index("spot_last_poll_completed_at")] = ""
        row[header.index("spot_effective_freshness_at_row")] = "unknown"
        row[header.index("spot_row_age_clock_status")] = "unknown"
        row[header.index("temperature_output_status")] = "startup_pending"
        row[header.index("temperature_unavailable_reason")] = "startup_pending"
        row[header.index("temperature_value_origin")] = "none"
        row[header.index("spot_observation_key")] = "spot-service-1:0"

        failures = validate_v2_4_operational_invariants(
            [row],
            header,
            row_time_freshness_threshold_ms=3000.0,
        )

        self.assertIn("row 2 nonblank spot_observation_key requires positive spot_poll_seq", failures)
        self.assertIn("row 2 not_attempted poll requires blank spot_observation_key", failures)
        self.assertIn("row 2 missing spot_last_poll_completed_at requires blank spot_observation_key", failures)
        self.assertIn("row 2 startup_pending row requires blank spot_observation_key", failures)

    def test_v2_4_validator_rejects_nonblank_observation_key_for_startup_shadow_status(self) -> None:
        header = V2_4_CSV_COLUMNS
        row = self.build_valid_temperature_v2_4_row()
        row[header.index("temperature_status_shadow")] = "startup_pending"

        failures = validate_v2_4_operational_invariants(
            [row],
            header,
            row_time_freshness_threshold_ms=3000.0,
        )

        self.assertIn("row 2 startup_pending shadow status requires blank spot_observation_key", failures)

    def test_full_validator_rejects_startup_row_with_nonblank_observation_key(self) -> None:
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
            row = self.build_valid_temperature_v2_4_row()
            row[V2_4_CSV_COLUMNS.index("Temperature")] = ""
            row[V2_4_CSV_COLUMNS.index("spot_poll_status")] = "not_attempted"
            row[V2_4_CSV_COLUMNS.index("spot_poll_seq")] = "0"
            row[V2_4_CSV_COLUMNS.index("spot_raw_validity")] = "not_received"
            row[V2_4_CSV_COLUMNS.index("spot_source_freshness")] = "unknown"
            row[V2_4_CSV_COLUMNS.index("spot_device_status_code")] = ""
            row[V2_4_CSV_COLUMNS.index("spot_last_poll_completed_at")] = ""
            row[V2_4_CSV_COLUMNS.index("spot_effective_freshness_at_row")] = "unknown"
            row[V2_4_CSV_COLUMNS.index("spot_row_age_clock_status")] = "unknown"
            row[V2_4_CSV_COLUMNS.index("temperature_output_status")] = "startup_pending"
            row[V2_4_CSV_COLUMNS.index("temperature_unavailable_reason")] = "startup_pending"
            row[V2_4_CSV_COLUMNS.index("temperature_value_origin")] = "none"
            row[V2_4_CSV_COLUMNS.index("spot_observation_key")] = "spot-service-1:0"
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260625_080000.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_4_CSV_COLUMNS)
                writer.writerow(row)
            service._write_v2_sidecar(v2_path, service._get_active_v2_contract())

            result = validate_csv_v2_shadow(None, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 1)

    def test_v2_4_validator_rejects_missing_row_timestamp(self) -> None:
        header = V2_4_CSV_COLUMNS
        row = self.build_valid_temperature_v2_4_row()
        row[header.index("timestamp_utc")] = ""

        failures = validate_v2_4_operational_invariants(
            [row],
            header,
            row_time_freshness_threshold_ms=3000.0,
        )

        self.assertIn("row 2 timestamp_utc must be a parseable UTC timestamp", failures)

    def test_v2_4_validator_accepts_timestamp_clock_anomaly_policy(self) -> None:
        header = V2_4_CSV_COLUMNS
        row = self.build_valid_temperature_v2_4_row()
        row[header.index("timestamp_utc")] = "2026-06-25T07:59:59Z"
        row[header.index("Temperature")] = ""
        row[header.index("spot_effective_freshness_at_row")] = "unknown"
        row[header.index("spot_row_age_clock_status")] = "clock_anomaly"
        row[header.index("temperature_output_status")] = "unknown"
        row[header.index("temperature_unavailable_reason")] = "unknown_freshness"
        row[header.index("temperature_value_origin")] = "none"

        self.assertEqual(
            validate_v2_4_operational_invariants(
                [row],
                header,
                row_time_freshness_threshold_ms=3000.0,
            ),
            [],
        )

    def test_full_validator_rejects_timestamp_stale_row_left_fresh_valid(self) -> None:
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
            row = self.build_valid_temperature_v2_4_row()
            row[V2_4_CSV_COLUMNS.index("timestamp_utc")] = "2026-06-25T08:00:04Z"
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260625_080004.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_4_CSV_COLUMNS)
                writer.writerow(row)
            with patch("backend.FacilityData.repository.config.SPOT_REFRESH_INTERVAL", 1.0):
                service._write_v2_sidecar(v2_path, service._get_active_v2_contract())

            result = validate_csv_v2_shadow(None, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 1)

    def test_spot_observation_fact_manifest_accepts_authoritative_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            row = self.build_valid_temperature_v2_4_row()
            row[V2_4_CSV_COLUMNS.index("temperature_cause_evidence_codes")] = json.dumps(
                ["signal_at_or_above_configured_threshold"]
            )
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260625_080000.csv"
            self.write_csv_rows(v2_path, list(V2_4_CSV_COLUMNS), [row])
            fact_path = log_dir / "spot_observation_fact.csv"
            self.write_observation_fact(fact_path, [self.observation_fact_row()])
            realtime_rows = [dict(zip(V2_4_CSV_COLUMNS, row))]
            metadata = {
                "spot_observation_fact_manifest": build_spot_observation_fact_manifest(
                    fact_path=fact_path,
                    enabled=True,
                    write_failure_count=0,
                    spool_pending_count=0,
                    realtime_rows=realtime_rows,
                )
            }
            metadata_path = log_dir / "Factory_Integrated_Log_v2_20260625_080000.metadata.json"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            failures, summary = validate_spot_observation_fact_manifest(
                metadata,
                metadata_path,
                list(V2_4_CSV_COLUMNS),
                [row],
                spot_observation_fact_path=fact_path,
            )

        self.assertEqual(failures, [])
        self.assertEqual(summary["spot_observation_fact_row_count_match"], "true")
        self.assertEqual(summary["spot_observation_fact_missing_fact_key_rows"], "0")
        self.assertEqual(summary["spot_observation_fact_link_coverage_pct"], "100.0")
        self.assertEqual(summary["spot_observation_fact_diagnostic_signalpc_nonblank_count"], "1")

    def test_spot_observation_fact_manifest_accepts_historical_v1_2_1_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            row = self.build_valid_temperature_v2_4_row()
            realtime_rows = [dict(zip(V2_4_CSV_COLUMNS, row))]
            historical_values = {
                "spot_observation_fact_schema_version": SPOT_OBSERVATION_FACT_V1_2_1_SCHEMA_VERSION,
                "spot_observation_key": "spot-service-1:14",
                "spot_service_instance_id": "spot-service-1",
                "spot_poll_seq": "14",
                "spot_observation_seq": "14",
                "spot_poll_status": "success",
                "spot_raw_validity": "valid_temperature",
                "spot_temperature_raw": "560.7",
                "spot_last_poll_completed_at": "2026-06-25T08:00:00Z",
                "diagnostics_capture_status": "async_enriched",
                "diagnostics_age_ms": "10.0",
                "spot_diagnostic_evidence_codes": "[]",
                "alarmstatus": "0",
                "low_signal_alarm_enabled": "false",
                "low_signal_comparator_verified": "false",
                "peak_picker_enabled": "false",
            }
            fact_path = log_dir / "spot_observation_fact.csv"
            self.write_csv_rows(
                fact_path,
                list(SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS),
                [
                    [
                        historical_values.get(column, "")
                        for column in SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS
                    ]
                ],
            )
            manifest = build_spot_observation_fact_manifest(
                fact_path=fact_path,
                enabled=True,
                write_failure_count=0,
                spool_pending_count=0,
                realtime_rows=realtime_rows,
            )
            manifest["schema_version"] = SPOT_OBSERVATION_FACT_V1_2_1_SCHEMA_VERSION
            manifest["required_columns"] = list(SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS)
            for key in (
                "diagnostics_capture_status_counts",
                "diagnostics_binding_status_counts",
                "diagnostics_missing_field_counts",
                "evidence_provenance_coverage",
            ):
                manifest.pop(key)
            metadata = {"spot_observation_fact_manifest": manifest}
            metadata_path = log_dir / "Factory_Integrated_Log_v2_20260625_080000.metadata.json"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            failures, summary = validate_spot_observation_fact_manifest(
                metadata,
                metadata_path,
                list(V2_4_CSV_COLUMNS),
                [row],
                spot_observation_fact_path=fact_path,
            )

        self.assertEqual(failures, [])
        self.assertEqual(summary["spot_observation_fact_link_coverage_pct"], "100.0")

    def test_spot_observation_fact_manifest_rejects_missing_evidence_source_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            row = self.build_valid_temperature_v2_4_row()
            row[V2_4_CSV_COLUMNS.index("temperature_cause_evidence_codes")] = json.dumps(
                ["signal_at_or_above_configured_threshold"]
            )
            fact_path = log_dir / "spot_observation_fact.csv"
            self.write_observation_fact(fact_path, [self.observation_fact_row(signalpc="")])
            metadata = {
                "spot_observation_fact_manifest": build_spot_observation_fact_manifest(
                    fact_path=fact_path,
                    enabled=True,
                    write_failure_count=0,
                    spool_pending_count=0,
                    realtime_rows=[dict(zip(V2_4_CSV_COLUMNS, row))],
                )
            }
            metadata_path = log_dir / "Factory_Integrated_Log_v2_20260625_080000.metadata.json"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            failures, summary = validate_spot_observation_fact_manifest(
                metadata,
                metadata_path,
                list(V2_4_CSV_COLUMNS),
                [row],
                spot_observation_fact_path=fact_path,
            )

        self.assertEqual(summary["spot_observation_fact_diagnostic_source_mismatch_count"], "1")
        self.assertTrue(any("signalpc" in failure for failure in failures))

    def test_spot_observation_fact_manifest_rejects_previous_poll_causal_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            row = self.build_valid_temperature_v2_4_row()
            row[V2_4_CSV_COLUMNS.index("temperature_cause_evidence_codes")] = json.dumps(
                ["signal_at_or_above_configured_threshold"]
            )
            fact_path = log_dir / "spot_observation_fact.csv"
            self.write_observation_fact(
                fact_path,
                [
                    self.observation_fact_row(
                        diagnostics_source_poll_seq="13",
                        diagnostics_binding_status="previous_poll",
                    )
                ],
            )
            metadata = {
                "spot_observation_fact_manifest": build_spot_observation_fact_manifest(
                    fact_path=fact_path,
                    enabled=True,
                    write_failure_count=0,
                    spool_pending_count=0,
                    realtime_rows=[dict(zip(V2_4_CSV_COLUMNS, row))],
                )
            }
            metadata_path = log_dir / "Factory_Integrated_Log_v2_20260625_080000.metadata.json"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            failures, _summary = validate_spot_observation_fact_manifest(
                metadata,
                metadata_path,
                list(V2_4_CSV_COLUMNS),
                [row],
                spot_observation_fact_path=fact_path,
            )

        self.assertTrue(any("same_poll diagnostics binding" in failure for failure in failures))

    def test_repository_refreshes_sidecar_observation_fact_manifest_with_link_coverage(self) -> None:
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
            row = self.build_valid_temperature_v2_4_row()
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260625_080000.csv"
            self.write_csv_rows(v2_path, list(V2_4_CSV_COLUMNS), [row])
            service._write_v2_sidecar(v2_path, service._get_active_v2_contract())
            self.write_observation_fact(log_dir / "spot_observation_fact.csv", [self.observation_fact_row()])

            refreshed_path = service.refresh_spot_observation_fact_manifest_for_csv(v2_path)
            self.assertIsNotNone(refreshed_path)
            assert refreshed_path is not None
            metadata = json.loads(refreshed_path.read_text(encoding="utf-8"))

        manifest = metadata["spot_observation_fact_manifest"]
        self.assertEqual(manifest["row_count"], 1)
        self.assertEqual(manifest["distinct_observation_key_count"], 1)
        self.assertEqual(manifest["link_coverage"]["realtime_rows_with_observation_key"], 1)
        self.assertEqual(manifest["link_coverage"]["linked_rows"], 1)
        self.assertEqual(manifest["link_coverage"]["missing_fact_key_rows"], 0)
        self.assertEqual(manifest["link_coverage"]["coverage_pct"], 100.0)
        self.assertEqual(manifest["diagnostic_field_coverage"]["signalpc_nonblank_count"], 1)
        self.assertRegex(manifest["sha256"], r"^[a-f0-9]{64}$")

    def test_repository_initializes_empty_enabled_observation_fact_for_replay_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v2_enabled=True,
                csv_v2_operational_fields_enabled=True,
                csv_v2_temperature_hardening_enabled=True,
            )
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260711_120000.csv"
            self.write_csv_rows(v2_path, list(V2_5_CSV_COLUMNS), [])

            with patch("backend.FacilityData.repository.config.SPOT_OBSERVATION_FACT_ENABLED", True):
                service._write_v2_sidecar(v2_path, service._get_active_v2_contract())
                service.refresh_spot_observation_fact_manifest_for_csv(v2_path)

            fact_path = log_dir / "spot_observation_fact.csv"
            with fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            metadata_path = v2_path.with_suffix(".metadata.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            failures, summary = validate_spot_observation_fact_manifest(
                metadata,
                metadata_path,
                list(V2_5_CSV_COLUMNS),
                [],
                spot_observation_fact_path=fact_path,
            )

        self.assertEqual(rows, [SPOT_OBSERVATION_FACT_COLUMNS])
        self.assertEqual(failures, [])
        self.assertEqual(summary["spot_observation_fact_row_count_match"], "true")
        self.assertEqual(summary["spot_observation_fact_link_coverage_pct"], "0.0")
        manifest = metadata["spot_observation_fact_manifest"]
        self.assertTrue(manifest["enabled"])
        self.assertEqual(manifest["row_count"], 0)
        self.assertEqual(manifest["write_failure_count"], 0)
        self.assertRegex(manifest["sha256"], r"^[a-f0-9]{64}$")

    def test_v2_4_row_links_latest_spot_image_fact_for_same_observation(self) -> None:
        header = V2_4_CSV_COLUMNS
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "spot_last_poll_completed_at": "2026-06-24T23:00:00Z",
            }
        )
        latest_fact = {
            "spot_image_capture_id": "spotimg_20260701T010856283905Z_fe0d2cf21603",
            "spot_image_path": "spot_images/2026/07/01/spotimg_20260701T010856283905Z_fe0d2cf21603.jpg",
            "spot_image_link_status": "fresh",
            "spot_image_link_age_ms": "42.000",
            "spot_image_linked_observation_key": "spot-service-1:14",
        }

        with patch("backend.FacilityData.drivers.spot_api.get_latest_spot_image_capture_fact", return_value=latest_fact):
            timestamp = service._parse_timestamp(data)
            row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, service._build_row(data, timestamp))

        self.assertEqual(
            row[header.index("spot_image_capture_id_nearest")],
            "spotimg_20260701T010856283905Z_fe0d2cf21603",
        )
        self.assertEqual(
            row[header.index("spot_image_path_nearest")],
            "spot_images/2026/07/01/spotimg_20260701T010856283905Z_fe0d2cf21603.jpg",
        )
        self.assertEqual(row[header.index("spot_image_link_status_nearest")], "fresh")
        self.assertEqual(row[header.index("spot_image_link_age_ms_nearest")], "42.000")
        self.assertEqual(validate_v2_4_operational_invariants([row], header), [])

    def test_v2_4_row_leaves_image_link_blank_for_different_observation(self) -> None:
        header = V2_4_CSV_COLUMNS
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "spot_last_poll_completed_at": "2026-06-24T23:00:00Z",
            }
        )
        latest_fact = {
            "spot_image_capture_id": "spotimg_20260701T010856283905Z_fe0d2cf21603",
            "spot_image_path": "spot_images/2026/07/01/spotimg_20260701T010856283905Z_fe0d2cf21603.jpg",
            "spot_image_link_status": "fresh",
            "spot_image_link_age_ms": "42.000",
            "spot_image_linked_observation_key": "spot-service-1:999",
        }

        with patch("backend.FacilityData.drivers.spot_api.get_latest_spot_image_capture_fact", return_value=latest_fact):
            timestamp = service._parse_timestamp(data)
            row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, service._build_row(data, timestamp))

        self.assertEqual(row[header.index("spot_image_capture_id_nearest")], "")
        self.assertEqual(row[header.index("spot_image_path_nearest")], "")
        self.assertEqual(row[header.index("spot_image_link_status_nearest")], "")
        self.assertEqual(row[header.index("spot_image_link_age_ms_nearest")], "")
        self.assertEqual(validate_v2_4_operational_invariants([row], header), [])

    def test_spot_configuration_validator_accepts_non_current_valid_profile_by_default(self) -> None:
        metadata = {
            "spot_configuration_snapshot": {
                "spot_model_info": "SPOT+ AL",
                "spot_app_mode": "App2: AL E",
                "spot_range_min_c": 100.0,
                "spot_range_max_c": 1200.0,
                "spot_analog_4ma_c": 100.0,
                "spot_analog_20ma_c": 1000.0,
                "low_signal_alarm_enabled": True,
                "low_signal_threshold_pc": 10.0,
                "low_signal_comparator": "lte",
                "low_signal_comparator_verified": True,
                "peak_picker_enabled": True,
                "limiter_enabled": True,
                "averager_enabled": False,
                "modemaster_enabled": False,
                "spot_ratio_raw_enabled": False,
                "window_obscuration_pc": 25.0,
                "focus_mm": 5000,
                "config_operator_verified": True,
                **self.config_provenance_fields(verified=True),
            }
        }

        self.assertEqual(validate_spot_configuration_snapshot(metadata, [], []), [])

    def test_spot_configuration_validator_requires_current_server_profile_only_when_requested(self) -> None:
        metadata = {
            "spot_configuration_snapshot": {
                "spot_model_info": "SPOT+ AL",
                "spot_app_mode": "App2: AL E",
                "spot_range_min_c": 100.0,
                "spot_range_max_c": 1200.0,
                "spot_analog_4ma_c": 100.0,
                "spot_analog_20ma_c": 1000.0,
                "low_signal_alarm_enabled": True,
                "low_signal_threshold_pc": 10.0,
                "low_signal_comparator": "lte",
                "low_signal_comparator_verified": True,
                "peak_picker_enabled": True,
                "limiter_enabled": True,
                "averager_enabled": False,
                "modemaster_enabled": False,
                "spot_ratio_raw_enabled": False,
                "window_obscuration_pc": 25.0,
                "focus_mm": 5000,
                "config_operator_verified": True,
                **self.config_provenance_fields(verified=True),
            }
        }

        failures = validate_spot_configuration_snapshot(
            metadata,
            [],
            [],
            require_current_server_promotion_profile=True,
        )

        self.assertTrue(
            any("current server promotion profile spot_configuration_snapshot.low_signal_threshold_pc" in failure
                for failure in failures)
        )
        self.assertTrue(
            any("current server promotion profile spot_configuration_snapshot.focus_mm" in failure for failure in failures)
        )

    def test_spot_configuration_validator_still_rejects_invalid_generic_ranges(self) -> None:
        metadata = {
            "spot_configuration_snapshot": {
                "low_signal_alarm_enabled": False,
                "low_signal_threshold_pc": 101.0,
                "low_signal_comparator": "bad",
                "low_signal_comparator_verified": False,
                "spot_range_min_c": 900.0,
                "spot_range_max_c": 200.0,
                "window_obscuration_pc": -1.0,
                **self.config_provenance_fields(verified=False),
            }
        }

        failures = validate_spot_configuration_snapshot(metadata, [], [])

        self.assertIn("spot_configuration_snapshot.low_signal_threshold_pc must be 0.0..100.0", failures)
        self.assertIn("spot_configuration_snapshot.low_signal_comparator must be lt/lte/unknown", failures)
        self.assertIn("spot_configuration_snapshot.spot_range_min_c must be <= spot_range_max_c", failures)
        self.assertIn("spot_configuration_snapshot.window_obscuration_pc must be 0.0..100.0", failures)

    def test_spot_configuration_validator_accepts_legacy_v3_snapshot_without_provenance(self) -> None:
        metadata = {
            "schema_metadata": {
                "temperature_operational_rule_version": "temperature-operational-v3"
            },
            "spot_configuration_snapshot": {
                "low_signal_alarm_enabled": False,
                "low_signal_threshold_pc": 2.0,
                "low_signal_comparator": "lt",
                "low_signal_comparator_verified": False,
                "spot_range_min_c": 200.0,
                "spot_range_max_c": 900.0,
                "window_obscuration_pc": 12.0,
            },
        }

        self.assertEqual(validate_spot_configuration_snapshot(metadata, [], []), [])

    def test_spot_configuration_validator_requires_current_fingerprint_for_matched_readback(self) -> None:
        base_snapshot = {
            "low_signal_alarm_enabled": True,
            "low_signal_threshold_pc": 2.0,
            "low_signal_comparator": "lt",
            "low_signal_comparator_verified": True,
            "spot_range_min_c": 200.0,
            "spot_range_max_c": 900.0,
            "window_obscuration_pc": 12.0,
            **self.config_provenance_fields(verified=True),
            "device_config_readback_status": "matched",
        }

        for device_fingerprint in ("", "c" * 64):
            with self.subTest(device_fingerprint=device_fingerprint or "blank"):
                snapshot = {
                    **base_snapshot,
                    "device_config_fingerprint_sha256": device_fingerprint,
                }
                failures = validate_spot_configuration_snapshot(
                    {"spot_configuration_snapshot": snapshot},
                    [],
                    [],
                )
                self.assertIn(
                    "spot_configuration_snapshot.device_config_readback_status=matched "
                    "requires current device fingerprint",
                    failures,
                )

        valid_snapshot = {
            **base_snapshot,
            "device_config_fingerprint_sha256": base_snapshot[
                "spot_config_fingerprint_sha256"
            ],
        }
        self.assertEqual(
            validate_spot_configuration_snapshot(
                {"spot_configuration_snapshot": valid_snapshot},
                [],
                [],
            ),
            [],
        )

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
        self.assertEqual(
            summary["logger_service_instance_id"],
            service.logger_service_instance_id,
        )
        self.assertEqual(
            summary["logger_service_started_at"],
            service.logger_service_started_at,
        )
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

    def test_v2_5_quality_mapping_covers_all_operational_statuses(self) -> None:
        valid = self.create_data().model_copy(
            update={
                "Time": "2026-06-25T08:00:00+00:00",
                "Spot": 560.7,
                "spot_poll_status": "success",
                "spot_raw_validity": "valid_temperature",
                "spot_cache_status": "fresh",
                "temperature_value_origin": "current_observation",
                "spot_device_status_code": None,
                "spot_temperature_observed_c": 560.7,
                "spot_last_poll_completed_at": "2026-06-25T08:00:00Z",
                "spot_last_valid_value_at": "2026-06-25T07:59:59Z",
                "spot_last_valid_value_monotonic": 99.0,
            }
        )
        cached = valid.model_copy(
            update={
                "Spot": 559.1,
                "spot_poll_status": "timeout",
                "spot_raw_validity": "not_received",
                "spot_cache_status": "reused",
                "temperature_value_origin": "cached_observation",
                "spot_temperature_observed_c": None,
                "cache_fallback_allowed": True,
            }
        )
        cases = {
            "valid-current": (valid, "valid", "ok", "not_missing", True),
            "valid-cached": (cached, "valid", "ok", "not_missing", True),
            "under-range": (
                self.create_data(),
                "under_range",
                "invalid",
                "invalid_value",
                False,
            ),
            "over-range": (
                self.create_data().model_copy(
                    update={"spot_device_status_code": "temperature_over_range"}
                ),
                "over_range",
                "invalid",
                "invalid_value",
                False,
            ),
            "stale": (
                self.create_data().model_copy(update={"spot_source_freshness": "stale"}),
                "stale",
                "stale",
                "stale_snapshot",
                False,
            ),
            "source-error": (
                self.create_data().model_copy(
                    update={
                        "spot_poll_status": "timeout",
                        "spot_raw_validity": "not_received",
                        "spot_cache_status": "empty",
                        "spot_device_status_code": None,
                    }
                ),
                "source_error",
                "missing",
                "source_error",
                False,
            ),
            "startup": (
                self.create_data().model_copy(
                    update={
                        "spot_poll_status": "not_attempted",
                        "spot_raw_validity": "not_received",
                        "spot_device_status_code": None,
                    }
                ),
                "startup_pending",
                "missing",
                "source_missing",
                False,
            ),
            "unknown": (
                self.create_data().model_copy(
                    update={
                        "spot_raw_validity": "not_received",
                        "spot_device_status_code": None,
                    }
                ),
                "unknown",
                "unknown",
                "source_missing",
                False,
            ),
        }

        for name, (data, status, quality, reason, has_temperature) in cases.items():
            with self.subTest(name=name):
                _, row = self.build_v2_5_row(data)
                self.assertEqual(row[V2_5_CSV_COLUMNS.index("schema_version")], CSV_SCHEMA_VERSION_V2_5)
                self.assertEqual(row[V2_5_CSV_COLUMNS.index("temperature_output_status")], status)
                self.assertEqual(row[V2_5_CSV_COLUMNS.index("Temperature_quality")], quality)
                self.assertEqual(row[V2_5_CSV_COLUMNS.index("Temperature_missing_reason")], reason)
                self.assertEqual(bool(row[V2_5_CSV_COLUMNS.index("Temperature")]), has_temperature)
                self.assertEqual(
                    validate_v2_5_temperature_hardening_invariants([row], V2_5_CSV_COLUMNS),
                    [],
                )

    def test_v2_5_value_age_prefers_monotonic_and_ignores_snapshot_age(self) -> None:
        data = self.create_data().model_copy(
            update={
                "spot_last_valid_value_at": "2026-06-25T00:00:00Z",
                "spot_last_valid_value_monotonic": 99.25,
                "spot_effective_value_age_ms_at_row": 1.0,
                "spot_value_age_ms": 2.0,
            }
        )

        _, row = self.build_v2_5_row(data, row_created_monotonic=100.0)

        self.assertEqual(row[V2_5_CSV_COLUMNS.index("spot_effective_value_age_ms_at_row")], "750.0")
        self.assertEqual(row[V2_5_CSV_COLUMNS.index("spot_value_age_clock_status")], "ok")

    def test_v2_5_value_age_uses_utc_fallback_only_without_monotonic(self) -> None:
        data = self.create_data().model_copy(
            update={
                "Time": "2026-06-25T08:00:00+00:00",
                "spot_last_valid_value_at": "2026-06-25T07:59:59Z",
                "spot_last_valid_value_monotonic": None,
            }
        )

        _, row = self.build_v2_5_row(data)

        self.assertEqual(row[V2_5_CSV_COLUMNS.index("spot_effective_value_age_ms_at_row")], "1000.0")
        self.assertEqual(row[V2_5_CSV_COLUMNS.index("spot_value_age_clock_status")], "ok")

    def test_v2_5_value_age_clock_anomalies_are_blank_and_counted(self) -> None:
        monotonic_data = self.create_data().model_copy(
            update={"spot_last_valid_value_monotonic": 101.0}
        )
        wall_clock_data = self.create_data().model_copy(
            update={
                "Time": "2026-06-25T08:00:00+00:00",
                "spot_last_valid_value_at": "2026-06-25T08:00:01Z",
            }
        )

        for name, data in (("monotonic", monotonic_data), ("wall-clock", wall_clock_data)):
            with self.subTest(name=name):
                service, row = self.build_v2_5_row(data, row_created_monotonic=100.0)
                self.assertEqual(row[V2_5_CSV_COLUMNS.index("spot_effective_value_age_ms_at_row")], "")
                self.assertEqual(row[V2_5_CSV_COLUMNS.index("spot_value_age_clock_status")], "clock_anomaly")
                self.assertEqual(service.get_v2_4_operational_summary()["value_age_clock_anomaly_count"], 1)

    def test_v2_5_value_age_is_unknown_when_both_sources_are_missing(self) -> None:
        _, row = self.build_v2_5_row(self.create_data())

        self.assertEqual(row[V2_5_CSV_COLUMNS.index("spot_effective_value_age_ms_at_row")], "")
        self.assertEqual(row[V2_5_CSV_COLUMNS.index("spot_value_age_clock_status")], "unknown")

    def test_v2_4_contract_preserves_legacy_quality_and_value_age_semantics(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "Spot": 560.7,
                "captured_at_spot": 1_782_374_400.0,
                "spot_source_freshness": "stale",
                "spot_device_status_code": None,
                "spot_effective_value_age_ms_at_row": 321.0,
            }
        )
        timestamp = service._parse_timestamp(data)
        row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, service._build_row(data, timestamp))

        self.assertEqual(service._get_active_v2_contract().schema_version, CSV_SCHEMA_VERSION_V2_4)
        self.assertEqual(list(service._get_active_v2_contract().columns), V2_4_CSV_COLUMNS)
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("Temperature_quality")], "ok")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("Temperature_missing_reason")], "not_missing")
        self.assertEqual(row[V2_4_CSV_COLUMNS.index("spot_effective_value_age_ms_at_row")], "321.0")
        self.assertNotIn("spot_value_age_clock_status", V2_4_CSV_COLUMNS)

    def test_v2_5_validator_rejects_quality_and_clock_status_contradictions(self) -> None:
        data = self.create_data().model_copy(
            update={
                "Spot": 560.7,
                "spot_raw_validity": "valid_temperature",
                "spot_cache_status": "fresh",
                "temperature_value_origin": "current_observation",
                "spot_device_status_code": None,
                "spot_temperature_observed_c": 560.7,
                "spot_last_valid_value_monotonic": 99.0,
            }
        )
        _, row = self.build_v2_5_row(data)

        blank_temperature = list(row)
        blank_temperature[V2_5_CSV_COLUMNS.index("Temperature")] = ""
        clock_conflict = list(row)
        clock_conflict[V2_5_CSV_COLUMNS.index("spot_value_age_clock_status")] = "clock_anomaly"

        quality_failures = validate_v2_5_temperature_hardening_invariants(
            [blank_temperature], V2_5_CSV_COLUMNS
        )
        clock_failures = validate_v2_5_temperature_hardening_invariants(
            [clock_conflict], V2_5_CSV_COLUMNS
        )
        self.assertTrue(any("blank Temperature cannot use ok/not_missing" in item for item in quality_failures))
        self.assertTrue(any("requires blank value age" in item for item in clock_failures))

    def test_full_validator_accepts_v2_5_temperature_hardening_contract(self) -> None:
        data = self.create_data().model_copy(
            update={
                "Time": "2026-06-25T08:00:00+00:00",
                "Spot": 560.7,
                "spot_raw_validity": "valid_temperature",
                "spot_cache_status": "fresh",
                "temperature_value_origin": "current_observation",
                "spot_device_status_code": None,
                "spot_temperature_observed_c": 560.7,
                "spot_last_poll_completed_at": "2026-06-25T08:00:00Z",
                "spot_last_valid_value_at": "2026-06-25T07:59:59Z",
                "spot_last_valid_value_monotonic": 99.0,
            }
        )
        service, row = self.build_v2_5_row(data)

        with tempfile.TemporaryDirectory() as tmp:
            v2_path = Path(tmp) / "Factory_Integrated_Log_v2_20260625_080000_2_5_0.csv"
            self.write_observation_fact(
                Path(tmp) / "spot_observation_fact.csv",
                [self.observation_fact_row()],
            )
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_5_CSV_COLUMNS)
                writer.writerow(row)
            with patch("backend.FacilityData.repository.config.SPOT_OBSERVATION_FACT_ENABLED", True):
                service._write_v2_sidecar(v2_path, service._get_active_v2_contract())
                service.refresh_spot_observation_fact_manifest_for_csv(v2_path)

            result = validate_csv_v2_shadow(None, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 0)

    def test_v2_4_to_v2_5_contract_change_rolls_over_with_separate_sidecar(self) -> None:
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
            handle, _ = service._open_v2_log_file("20260711_120000", "Factory_Integrated_Log_v2")
            service._close_v2_file(handle)

            service.apply_config(csv_v2_temperature_hardening_enabled=True)
            handle, _ = service._open_v2_log_file("20260711_120000", "Factory_Integrated_Log_v2")
            service._close_v2_file(handle)

            csv_files = sorted(log_dir.glob("Factory_Integrated_Log_v2_20260711_120000*.csv"))
            metadata_files = sorted(log_dir.glob("Factory_Integrated_Log_v2_20260711_120000*.metadata.json"))
            self.assertEqual(len(csv_files), 2)
            self.assertEqual(len(metadata_files), 2)
            headers = []
            for path in csv_files:
                with path.open("r", encoding="utf-8-sig", newline="") as csv_handle:
                    headers.append(next(csv.reader(csv_handle)))
            self.assertIn(V2_4_CSV_COLUMNS, headers)
            self.assertIn(V2_5_CSV_COLUMNS, headers)
            schemas = {
                json.loads(path.read_text(encoding="utf-8"))["schema_metadata"]["schema_version"]
                for path in metadata_files
            }
            self.assertEqual(schemas, {CSV_SCHEMA_VERSION_V2_4, CSV_SCHEMA_VERSION_V2_5})

    def test_temperature_hardening_runtime_flag_combination_is_fail_closed(self) -> None:
        service = CSVLoggerService()
        original_log_dir = service.active_log_dir

        with self.assertRaisesRegex(ValueError, "requires csv_v2_operational_fields_enabled=true"):
            service.apply_config(
                log_path=Path("must-not-apply"),
                csv_v2_temperature_hardening_enabled=True,
            )

        self.assertFalse(service.csv_v2_temperature_hardening_enabled)
        self.assertFalse(service.csv_v2_operational_fields_enabled)
        self.assertEqual(service.active_log_dir, original_log_dir)

    def test_v1_temperature_index_remains_stable(self) -> None:
        self.assertEqual(V1_CSV_COLUMNS.index("Temperature"), 2)


PROMOTION_FLAGS = (
    "CSV_V2_OPERATIONAL_FIELDS_ENABLED",
    "CSV_V2_TEMPERATURE_HARDENING_ENABLED",
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

    def test_v2_5_hardening_without_operational_fields_is_rejected_on_import(self) -> None:
        result = self.import_config(CSV_V2_TEMPERATURE_HARDENING_ENABLED="true")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "CSV v2 temperature hardening requires CSV_V2_OPERATIONAL_FIELDS_ENABLED=true",
            result.stderr + result.stdout,
        )

    def test_full_v2_5_flag_bundle_is_allowed_on_import(self) -> None:
        result = self.import_config(
            CSV_V2_OPERATIONAL_FIELDS_ENABLED="true",
            CSV_V2_TEMPERATURE_HARDENING_ENABLED="true",
            SPOT_OBSERVATION_FACT_ENABLED="true",
            PROCESS_PHASE_EVENT_FACT_ENABLED="true",
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("config-import-ok", result.stdout)

    def test_spot_config_operator_verified_env_flag_is_loaded(self) -> None:
        env = os.environ.copy()
        repo_root = Path(__file__).resolve().parents[2]
        env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")
        env["SPOT_CONFIG_OPERATOR_VERIFIED"] = "true"

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import backend.config as config; print(config.SPOT_CONFIG_OPERATOR_VERIFIED)",
            ],
            cwd=repo_root,
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "True")

    def test_spot_config_operator_verified_defaults_false_without_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env = os.environ.copy()
            repo_root = Path(__file__).resolve().parents[2]
            env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")
            env["SFL_CONFIG_PATH"] = str(Path(temp_dir) / "missing-config.ini")
            env.pop("SPOT_CONFIG_OPERATOR_VERIFIED", None)

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import backend.config as config; print(config.SPOT_CONFIG_OPERATOR_VERIFIED)",
                ],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
                timeout=20,
            )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "False")


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
            "unsupported_evidence_suppressed_count": 4,
            "process_phase_candidate_counts": {"setup_candidate": 3},
            "last_sample_seq": 3,
            "last_updated_at": "2026-06-25T00:00:00Z",
        }
        with (
            patch.object(facility_service.logger_service, "get_v2_4_operational_summary", return_value=dict(summary)),
            patch(
                "backend.FacilityData.drivers.spot_api.get_spot_diagnostics",
                return_value={
                    "build_git_commit": "b" * 40,
                    "spot_poll_status": "success",
                },
            ),
            patch(
                "backend.FacilityData.drivers.spot_api.get_spot_observation_fact_health",
                return_value={
                    "enabled": True,
                    "write_failure_count": 2,
                    "config_drift_detected_count": 1,
                },
            ),
        ):
            payload = facility_service.plc_service._spot_temperature_health()

        self.assertTrue(payload["diagnostics_available"])
        self.assertEqual(payload["build_git_commit"], "b" * 40)
        self.assertEqual(payload["v2_4_operational"]["rows_total"], 3)
        self.assertEqual(payload["v2_4_operational"]["observation_fact_write_failure_count"], 2)
        self.assertTrue(payload["v2_4_operational"]["observation_fact_enabled"])
        self.assertEqual(payload["v2_4_operational"]["config_drift_detected_count"], 1)
        self.assertEqual(payload["v2_4_operational"]["unsupported_evidence_suppressed_count"], 4)


if __name__ == "__main__":
    unittest.main()
