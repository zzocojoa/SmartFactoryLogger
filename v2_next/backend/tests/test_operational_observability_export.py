import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from backend.FacilityData.changeover_candidate_resolution_fact import (
    CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS,
    PROCESS_PHASE_EVENT_FACT_COLUMNS,
    build_changeover_candidate_resolution_fact_manifest,
    build_process_phase_event_fact_manifest,
)
from backend.FacilityData.repository import CSVLoggerService, V2_4_CSV_COLUMNS
from backend.FacilityData.schemas import FactoryData
from scripts.validate_csv_v2_shadow import SPOT_IMAGE_FACT_REQUIRED_COLUMNS


class _OperationalObservabilityHandler(BaseHTTPRequestHandler):
    fact_path = r"C:\Users\operator\AppData\Roaming\SmartFactoryLogger\logs\test_data\spot_image_fact.csv"
    capture_root = (
        r"C:\Users\operator\AppData\Roaming\SmartFactoryLogger\logs\test_data"
        r"\spot_images\server_smoke_20260701-100445"
    )

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        payload = self._payload_for(path)
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return

    @classmethod
    def _payload_for(cls, path: str) -> dict:
        if path == "/stats":
            return {
                "total_http_5xx_count": 0,
                "total_http_4xx_count": 0,
                "error_count": 0,
                "window": {"seconds": 60},
                "polling": {"paths": {}},
            }
        if path == "/api/observability/errors":
            return {"summary": {"queue_size": 0}, "items": []}
        if path == "/api/spot/config":
            return {
                "image_capture": {
                    "enabled": True,
                    "mode": "all",
                    "queue_size": 0,
                    "queue_capacity": 128,
                    "enqueued_count": 3,
                    "written_count": 3,
                    "dropped_count": 0,
                    "failure_count": 0,
                    "last_write_at": 1782867948.0793145,
                },
                "spot_image_fact_manifest": {
                    "enabled": True,
                    "mode": "all",
                    "fact_path": cls.fact_path,
                    "capture_root": cls.capture_root,
                    "row_count": 19883,
                    "sha256": "bcb96397fbb97df8d6595fa8e71d03d0e60f4c2a6e7daaef0a54797d802f15d5",
                    "written": 3,
                    "dropped": 0,
                    "failure": 0,
                    "last_write_at": 1782867948.0793145,
                },
            }
        return {"status": "ok"}


class OperationalObservabilityExportTests(unittest.TestCase):
    def test_sanitized_summary_scrubs_spot_image_fact_manifest_paths(self) -> None:
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell is None:
            self.skipTest("PowerShell is required for collect_operational_observability.ps1")

        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "scripts" / "collect_operational_observability.ps1"

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "evidence"
            server = HTTPServer(("127.0.0.1", 0), _OperationalObservabilityHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    [
                        powershell,
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(script),
                        "-ApiBase",
                        f"http://127.0.0.1:{server.server_port}",
                        "-Samples",
                        "1",
                        "-IntervalSec",
                        "0",
                        "-OutputRoot",
                        str(output_root),
                    ],
                    cwd=repo_root,
                    text=True,
                    capture_output=True,
                    timeout=30,
                )
            finally:
                server.shutdown()
                server.server_close()

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            raw_files = list(output_root.glob("*/raw/sample_001_spot_config.json"))
            self.assertEqual(len(raw_files), 1)
            raw_text = raw_files[0].read_text(encoding="utf-8-sig")
            raw_envelope = json.loads(raw_text)
            raw_body = json.loads(raw_envelope["body"])
            raw_manifest = raw_body["spot_image_fact_manifest"]
            self.assertEqual(raw_manifest["fact_path"], _OperationalObservabilityHandler.fact_path)
            self.assertEqual(raw_manifest["capture_root"], _OperationalObservabilityHandler.capture_root)

            summaries = list(output_root.glob("*/sanitized/operational_observability_summary.json"))
            self.assertEqual(len(summaries), 1)
            summary_text = summaries[0].read_text(encoding="utf-8-sig")
            self.assertNotIn(_OperationalObservabilityHandler.fact_path, summary_text)
            self.assertNotIn(_OperationalObservabilityHandler.capture_root, summary_text)

            summary = json.loads(summary_text)
            manifest = summary["spot_config_samples"][0]["spot_image_fact_manifest"]
            self.assertEqual(manifest["fact_basename"], "spot_image_fact.csv")
            self.assertEqual(manifest["capture_root_basename"], "server_smoke_20260701-100445")
            self.assertRegex(manifest["fact_path_sha256"], r"^[a-f0-9]{64}$")
            self.assertRegex(manifest["capture_root_sha256"], r"^[a-f0-9]{64}$")
            self.assertNotIn("fact_path", manifest)
            self.assertNotIn("capture_root", manifest)
            self.assertTrue(manifest["path_values_redacted"])


class ServerSmokeCloseoutHelperTests(unittest.TestCase):
    def _factory_data(self) -> FactoryData:
        return FactoryData(
            Time="2026-07-02T23:30:25.000",
            Status="Running",
            Speed=4.0,
            Press=30.0,
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
            temperature_status_shadow="invalid_value",
            cache_fallback_allowed=False,
            spot_device_status_code="temperature_under_range",
            spot_target_state_observed_shadow="unknown",
            spot_service_instance_id="spot-service-1",
            spot_poll_seq=14,
            spot_observation_seq=14,
            spot_snapshot_age_ms=10.0,
            spot_value_age_ms=10.0,
            spot_temperature_raw="6553.4",
        )

    def _write_csv(self, path: Path, header: list[str], rows: list[list[str]]) -> str:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_bundle_fixture(self, bundle: Path) -> Path:
        bundle.mkdir(parents=True)
        service = CSVLoggerService()
        service.fallback_log_dir = bundle
        service.apply_config(
            log_path=bundle,
            auto_save=True,
            csv_v2_enabled=True,
            csv_v2_operational_fields_enabled=True,
        )
        rows = []
        row_inputs = [
            self._factory_data().model_copy(
                update={
                    "spot_effective_age_ms_at_row": 100.0,
                    "spot_snapshot_age_ms": 10.0,
                    "spot_value_age_ms": 10.0,
                }
            ),
            self._factory_data().model_copy(
                update={
                    "Time": "2026-07-02T23:30:26.000",
                    "spot_effective_age_ms_at_row": 10_000.0,
                    "spot_snapshot_age_ms": 20.0,
                    "spot_value_age_ms": 20.0,
                }
            ),
            self._factory_data().model_copy(
                update={
                    "Time": "2026-07-02T23:30:27.000",
                    "spot_poll_status": "not_attempted",
                    "spot_raw_validity": "not_received",
                    "spot_source_freshness": "unknown",
                    "spot_cache_status": "empty",
                    "temperature_status_shadow": "startup_pending",
                    "spot_device_status_code": "",
                    "spot_poll_seq": 0,
                    "spot_observation_seq": 0,
                    "spot_snapshot_age_ms": None,
                    "spot_value_age_ms": None,
                    "spot_temperature_raw": "",
                }
            ),
        ]
        for sample_seq, data in enumerate(row_inputs, start=1):
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            rows.append(
                service._build_v2_row(
                    data,
                    timestamp,
                    timestamp.astimezone(),
                    sample_seq,
                    v1_row,
                )
            )
        edge_row = list(rows[0])
        edge_row[V2_4_CSV_COLUMNS.index("timestamp_utc")] = "2026-07-02T23:30:25.000Z"
        edge_row[V2_4_CSV_COLUMNS.index("ingest_timestamp")] = "2026-07-02T23:30:26.000+00:00"
        edge_row[V2_4_CSV_COLUMNS.index("spot_last_poll_completed_at")] = "2026-07-02T23:30:25.500Z"
        rows[0] = edge_row
        v2_path = bundle / "Factory_Integrated_Log_v2_20260702_233025.csv"
        self._write_csv(v2_path, V2_4_CSV_COLUMNS, rows)

        image_fact = bundle / "spot_image_fact.csv"
        image_sha = self._write_csv(
            image_fact,
            SPOT_IMAGE_FACT_REQUIRED_COLUMNS,
            [
                [
                    "capture-1",
                    "spot_images/20260702/capture-1.jpg",
                    "1".zfill(64),
                    "123",
                    "image/jpeg",
                    "100",
                    "fresh",
                    "spot-service-1:14",
                ]
            ],
        )
        resolution_fact = bundle / "changeover_candidate_resolution_fact.csv"
        event_fact = bundle / "process_phase_event_fact.csv"
        self._write_csv(resolution_fact, CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS, [])
        self._write_csv(event_fact, PROCESS_PHASE_EVENT_FACT_COLUMNS, [])

        service._write_v2_sidecar(v2_path, service._get_active_v2_contract())
        metadata_path = v2_path.with_suffix(".metadata.json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["spot_image_fact_manifest"].update(
            {
                "enabled": True,
                "mode": "all",
                "fact_path": str(image_fact),
                "capture_root": str(bundle / "spot_images"),
                "row_count": 1,
                "sha256": image_sha,
                "written": 1,
                "dropped": 0,
                "failure": 0,
            }
        )
        metadata["schema_metadata"]["posthoc_fact_manifests"] = [
            "changeover_candidate_resolution_fact_manifest",
            "process_phase_event_fact_manifest",
        ]
        metadata["changeover_candidate_resolution_fact_manifest"] = (
            build_changeover_candidate_resolution_fact_manifest(
                fact_path=resolution_fact,
                source_csv_path=v2_path,
            )
        )
        metadata["process_phase_event_fact_manifest"] = build_process_phase_event_fact_manifest(
            fact_path=event_fact,
            source_csv_path=v2_path,
        )
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

        (bundle / "spot_config_off.json").write_text(
            json.dumps({"image_capture": {"enabled": False, "mode": "off", "failure_count": 0}}),
            encoding="utf-8",
        )
        return bundle / "spot_config_off.json"

    def _write_spot_config(self, path: Path, image_capture: dict[str, object]) -> Path:
        path.write_text(json.dumps({"image_capture": image_capture}), encoding="utf-8")
        return path

    def _run_closeout_helper(self, bundle: Path, mode: str, spot_config: Path) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[2]
        return subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "write_server_smoke_closeout.py"),
                "--bundle",
                str(bundle),
                "--mode",
                mode,
                "--spot-config-json",
                str(spot_config),
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            timeout=30,
        )

    def test_server_smoke_closeout_records_copied_override_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "server_csv_linkage_bundle_20260702-233303"
            spot_config = self._write_bundle_fixture(bundle)

            result = self._run_closeout_helper(bundle, "copied", spot_config)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            closeout = json.loads((bundle / "server_smoke_closeout_sanitized.json").read_text(encoding="utf-8"))

        self.assertEqual(closeout["validation_source"], "override")
        self.assertEqual(closeout["validator_verdict"], "PASS")
        self.assertEqual(closeout["validator_exit_code"], 0)
        self.assertFalse(closeout["capture_enabled"])
        self.assertEqual(closeout["capture_mode"], "off")
        self.assertEqual(closeout["capture_failure_count"], 0)
        self.assertEqual(closeout["process_facts"]["changeover_candidate_resolution_fact"]["presence"], "present")
        self.assertEqual(closeout["process_facts"]["changeover_candidate_resolution_fact"]["validation_source"], "override")
        self.assertEqual(closeout["process_facts"]["process_phase_event_fact"]["presence"], "present")
        self.assertEqual(closeout["process_facts"]["process_phase_event_fact"]["validation_source"], "override")
        self.assertTrue(closeout["row_time_required_columns_present"])
        self.assertEqual(closeout["effective_age_differs_from_snapshot_age_rows"], 2)
        self.assertEqual(closeout["threshold_mismatch_count"], 0)
        self.assertEqual(closeout["startup_observation_key_nonblank_count"], 0)
        self.assertEqual(closeout["timestamp_direction_mismatch_count"], 0)
        self.assertEqual(closeout["row_time_validation_errors"], [])
        self.assertFalse(any(closeout["redaction"].values()))
        closeout_text = json.dumps(closeout, ensure_ascii=False)
        self.assertNotIn(str(bundle), closeout_text)
        self.assertNotIn("://", closeout_text)

    def test_server_smoke_closeout_records_freeze_metadata_manifest_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "server_csv_linkage_bundle_20260702-233303"
            spot_config = self._write_bundle_fixture(bundle)

            result = self._run_closeout_helper(bundle, "freeze", spot_config)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            closeout = json.loads((bundle / "server_smoke_closeout_sanitized.json").read_text(encoding="utf-8"))

        self.assertEqual(closeout["validation_source"], "metadata_manifest")
        self.assertEqual(closeout["validator_verdict"], "PASS")
        self.assertTrue(closeout["spot_image_fact_row_count_match"])
        self.assertTrue(closeout["spot_image_fact_sha256_match"])
        self.assertEqual(closeout["process_facts"]["changeover_candidate_resolution_fact"]["validation_source"], "metadata_manifest")
        self.assertEqual(closeout["process_facts"]["process_phase_event_fact"]["validation_source"], "metadata_manifest")
        self.assertTrue(closeout["process_facts"]["changeover_candidate_resolution_fact"]["row_count_match"])
        self.assertTrue(closeout["process_facts"]["process_phase_event_fact"]["row_count_match"])
        self.assertTrue(closeout["row_time_required_columns_present"])
        self.assertEqual(closeout["effective_age_differs_from_snapshot_age_rows"], 2)
        self.assertEqual(closeout["threshold_mismatch_count"], 0)
        self.assertEqual(closeout["startup_observation_key_nonblank_count"], 0)
        self.assertEqual(closeout["timestamp_direction_mismatch_count"], 0)
        self.assertEqual(closeout["row_time_validation_errors"], [])
        self.assertFalse(any(closeout["redaction"].values()))

    def test_server_smoke_closeout_rejects_missing_capture_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "server_csv_linkage_bundle_20260702-233303"
            self._write_bundle_fixture(bundle)
            spot_config = self._write_spot_config(
                bundle / "spot_config_missing_enabled.json",
                {"mode": "off", "failure_count": 0},
            )

            result = self._run_closeout_helper(bundle, "copied", spot_config)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            closeout = json.loads((bundle / "server_smoke_closeout_sanitized.json").read_text(encoding="utf-8"))

        self.assertEqual(closeout["validator_verdict"], "FAIL")
        self.assertIsNone(closeout["capture_enabled"])
        self.assertEqual(closeout["capture_mode"], "off")
        self.assertEqual(closeout["capture_failure_count"], 0)
        self.assertIn("image_capture.enabled_missing_or_not_boolean", closeout["capture_validation_errors"])

    def test_server_smoke_closeout_rejects_missing_capture_failure_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "server_csv_linkage_bundle_20260702-233303"
            self._write_bundle_fixture(bundle)
            spot_config = self._write_spot_config(
                bundle / "spot_config_missing_failure_count.json",
                {"enabled": False, "mode": "off"},
            )

            result = self._run_closeout_helper(bundle, "copied", spot_config)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            closeout = json.loads((bundle / "server_smoke_closeout_sanitized.json").read_text(encoding="utf-8"))

        self.assertEqual(closeout["validator_verdict"], "FAIL")
        self.assertFalse(closeout["capture_enabled"])
        self.assertEqual(closeout["capture_mode"], "off")
        self.assertIsNone(closeout["capture_failure_count"])
        self.assertIn("image_capture.failure_count_missing_or_not_integer", closeout["capture_validation_errors"])

    def test_server_smoke_closeout_rejects_invalid_capture_failure_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "server_csv_linkage_bundle_20260702-233303"
            self._write_bundle_fixture(bundle)
            spot_config = self._write_spot_config(
                bundle / "spot_config_invalid_failure_count.json",
                {"enabled": False, "mode": "off", "failure_count": "0"},
            )

            result = self._run_closeout_helper(bundle, "copied", spot_config)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            closeout = json.loads((bundle / "server_smoke_closeout_sanitized.json").read_text(encoding="utf-8"))

        self.assertEqual(closeout["validator_verdict"], "FAIL")
        self.assertFalse(closeout["capture_enabled"])
        self.assertEqual(closeout["capture_mode"], "off")
        self.assertIsNone(closeout["capture_failure_count"])
        self.assertIn("image_capture.failure_count_missing_or_not_integer", closeout["capture_validation_errors"])


if __name__ == "__main__":
    unittest.main()
