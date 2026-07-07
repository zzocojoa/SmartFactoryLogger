import csv
import hashlib
import io
import json
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import app as backend_app
from backend.FacilityData import repository as repository_module
from backend.FacilityData.changeover_candidate_resolution_fact import (
    CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS,
    PROCESS_PHASE_EVENT_FACT_COLUMNS,
)
from backend.FacilityData.drivers import real_plc
from backend.FacilityData.drivers.real_plc import MelsecResponseError, RealPLCDriver, _parse_melsec_values
from backend.FacilityData.process_state import PROCESS_SEGMENT_FACT_COLUMNS, infer_process_segment_facts
from backend.FacilityData.repository import (
    CSVLoggerService,
    CSV_SCHEMA_VERSION_V2_3,
    CSV_SCHEMA_VERSION_V2_4,
    SPOT_TEMPERATURE_SHADOW_COLUMNS,
    V1_CSV_COLUMNS,
    V2_CSV_COLUMNS,
)
from backend.FacilityData.schemas import FactoryData, OperatorMetadata, OperatorMetadataUpdate
from backend.FacilityData.spot_image_fact import SPOT_IMAGE_FACT_FINAL_MANIFEST_FILENAME
from scripts.validate_csv_v2_shadow import validate as validate_csv_v2_shadow
from scripts.validate_csv_v2_shadow import validate_many as validate_csv_v2_shadow_many
from scripts.validate_csv_v2_shadow import SPOT_IMAGE_FACT_REQUIRED_COLUMNS
from scripts.infer_process_segments_for_csv import infer_process_segments_from_csv


class MelsecParseTests(unittest.TestCase):
    def test_parse_melsec_values_returns_hex_words(self) -> None:
        values = _parse_melsec_values("D0020", 2, b"01OK000A0014\r\n", "01OK000A0014")

        self.assertEqual(values, [10, 20])

    def test_parse_melsec_values_raises_with_context_for_invalid_hex(self) -> None:
        raw = b"01OK000G0014\r\n"

        with self.assertRaises(MelsecResponseError) as context:
            _parse_melsec_values("D0020", 2, raw, "01OK000G0014")

        message = str(context.exception)
        self.assertIn("addr=D0020", message)
        self.assertIn("count=2", message)
        self.assertIn("raw=b'01OK000G0014\\r\\n'", message)
        self.assertIn("chunk='000G'", message)
        self.assertIn("offset=0", message)

    def test_parse_melsec_values_raises_with_context_for_short_chunk(self) -> None:
        raw = b"01OK000A1\r\n"

        with self.assertRaises(MelsecResponseError) as context:
            _parse_melsec_values("D0020", 2, raw, "01OK000A1")

        message = str(context.exception)
        self.assertIn("addr=D0020", message)
        self.assertIn("count=2", message)
        self.assertIn("raw=b'01OK000A1\\r\\n'", message)
        self.assertIn("chunk='1'", message)
        self.assertIn("offset=4", message)


class SpotSnapshotTests(unittest.TestCase):
    def test_zero_cached_spot_temperature_replaces_previous_positive_snapshot(self) -> None:
        driver = RealPLCDriver()
        driver.last_spot = 45.5
        driver._update_spot_snapshot(45.5, 100.0)

        _, _, previous_spot = driver._read_cached_snapshot()
        self.assertEqual(previous_spot, 45.5)

        diagnostics = {
            "temperature_status_shadow": "no_target",
            "temperature_value_origin": "none",
            "spot_temperature_effective_c": None,
            "spot_poll_status": "success",
            "spot_raw_validity": "verified_no_target",
            "spot_cache_status": "invalidated",
            "spot_source_freshness": "fresh",
        }
        with patch("backend.FacilityData.drivers.real_plc.get_image_proxy_diagnostics", return_value=diagnostics):
            with patch("backend.FacilityData.drivers.real_plc.get_cached_spot_temp", return_value=0.0):
                spot_value = driver._read_spot()

        _, _, cached_spot = driver._read_cached_snapshot()

        self.assertEqual(spot_value, 0.0)
        self.assertEqual(driver.last_spot, 45.5)
        self.assertIsNone(cached_spot)

    def test_cached_observation_uses_effective_temperature_value(self) -> None:
        driver = RealPLCDriver()
        diagnostics = {
            "temperature_status_shadow": "ok",
            "temperature_value_origin": "cached_observation",
            "spot_temperature_effective_c": 450.0,
            "spot_poll_status": "timeout",
            "spot_raw_validity": "not_received",
            "spot_cache_status": "reused",
            "spot_source_freshness": "stale",
        }

        with patch("backend.FacilityData.drivers.real_plc.get_image_proxy_diagnostics", return_value=diagnostics):
            with patch("backend.FacilityData.drivers.real_plc.get_cached_spot_temp", return_value=999.0):
                spot_value = driver._read_spot()

        _, _, cached_spot = driver._read_cached_snapshot()
        self.assertEqual(spot_value, 450.0)
        self.assertEqual(cached_spot, 450.0)
        self.assertEqual(driver.last_spot, 450.0)
        self.assertIsNone(driver.spot_last_success_time)

    def test_read_data_includes_spot_shadow_metadata(self) -> None:
        driver = RealPLCDriver()
        now = time.time()
        driver._update_ext_snapshot({"Speed": 1.0, "Press": 10.0}, now)
        driver._process_high_speed_since = now - 1.0
        driver._update_ls_snapshot({}, now)
        driver._update_spot_snapshot(
            448.5,
            now,
            {
                "spot_target_state_observed_shadow": "present",
                "spot_target_state_observed_source": "valid_temperature",
                "temperature_status_shadow": "ok",
                "spot_poll_status": "success",
                "spot_raw_validity": "valid_temperature",
                "spot_cache_status": "fresh",
                "spot_source_freshness": "fresh",
                "temperature_value_origin": "current_observation",
                "cache_fallback_allowed": False,
                "spot_service_instance_id": "spot-service-1",
                "spot_service_started_at": "2026-03-09T07:20:00Z",
                "spot_poll_seq": 3,
                "spot_observation_seq": 3,
                "spot_temperature_observed_c": 448.5,
                "spot_raw_value_text": "448.5",
                "spot_raw_payload_hash": "hash-1",
                "spot_http_status_code": 200,
                "spot_poll_duration_ms": 12.5,
                "spot_response_content_length": 5,
                "spot_last_poll_started_at": "2026-03-09T07:20:24.000Z",
                "spot_last_poll_completed_at": "2026-03-09T07:20:24.012Z",
                "spot_last_poll_completed_monotonic": 12345.5,
                "spot_last_valid_value_at": "2026-03-09T07:20:24.012Z",
                "spot_snapshot_age_ms": 188.0,
                "spot_value_age_ms": 188.0,
            },
        )

        data = driver.read_data()

        self.assertEqual(data.Spot, 448.5)
        self.assertEqual(data.extruder_process_state_online, "extruding")
        self.assertEqual(data.process_state_online_rule_version, "process-state-online-v1")
        self.assertEqual(data.label_validation_state, "shadow")
        self.assertEqual(data.temperature_status_shadow, "ok")
        self.assertEqual(data.temperature_status_rule_version, "temperature-status-shadow-v1")
        self.assertEqual(data.spot_poll_status, "success")
        self.assertEqual(data.spot_raw_validity, "valid_temperature")
        self.assertEqual(data.spot_source_freshness, "fresh")
        self.assertEqual(data.temperature_value_origin, "current_observation")
        self.assertEqual(data.spot_service_instance_id, "spot-service-1")
        self.assertEqual(data.spot_poll_seq, 3)
        self.assertEqual(data.spot_observation_seq, 3)
        self.assertEqual(data.spot_temperature_observed_c, 448.5)
        self.assertEqual(data.spot_temperature_raw, "448.5")
        self.assertFalse(data.spot_temperature_raw_truncated)
        self.assertEqual(data.spot_raw_payload_encoding, "utf-8-replace")
        self.assertEqual(data.spot_last_response_at, "2026-03-09T07:20:24.012Z")
        self.assertEqual(data.spot_last_poll_completed_monotonic, 12345.5)
        self.assertNotIn("spot_last_poll_completed_monotonic", data.model_dump())




    def test_read_data_preserves_invalid_sentinel_device_status_without_snapshot_error(self) -> None:
        driver = RealPLCDriver()
        now = time.time()
        driver._update_ext_snapshot({"Speed": 1.0, "Press": 10.0}, now)
        driver._process_high_speed_since = now - 1.0
        driver._update_ls_snapshot({}, now)
        driver._update_spot_snapshot(
            None,
            now,
            {
                "spot_target_state_observed_shadow": "unknown",
                "spot_target_state_observed_source": "unknown",
                "temperature_status_shadow": "invalid_value",
                "spot_poll_status": "success",
                "spot_raw_validity": "invalid_sentinel",
                "spot_cache_status": "available_not_used",
                "spot_source_freshness": "fresh",
                "temperature_value_origin": "none",
                "cache_fallback_allowed": False,
                "spot_temperature_observed_c": None,
                "spot_raw_value_text": "6553.4",
                "spot_http_status_code": 200,
                "spot_device_status_code": "temperature_under_range",
                "spot_error_code": None,
                "spot_diagnostic_evidence_codes": '["alarm_low_signal"]',
            },
        )

        data = driver.read_data()

        self.assertIsNone(data.Spot)
        self.assertIsNone(data.spot_snapshot_error)
        self.assertEqual(data.spot_poll_status, "success")
        self.assertEqual(data.spot_raw_validity, "invalid_sentinel")
        self.assertEqual(data.spot_device_status_code, "temperature_under_range")
        self.assertIsNone(data.spot_error_code)
        self.assertEqual(data.temperature_status_shadow, "invalid_value")
        self.assertEqual(data.temperature_value_origin, "none")
        self.assertFalse(data.cache_fallback_allowed)
        self.assertEqual(data.spot_diagnostic_evidence_codes, '["alarm_low_signal"]')

class OnlineProcessStateTests(unittest.TestCase):
    def test_ext_snapshot_stale_missing_or_error_forces_unknown(self) -> None:
        driver = RealPLCDriver()
        now = 1_773_040_825.0

        self.assertEqual(
            driver._derive_extruder_process_state_online({"Speed": 1.0, "Press": 10.0}, None, None, now),
            "unknown",
        )
        self.assertEqual(
            driver._derive_extruder_process_state_online(
                {"Speed": 1.0, "Press": 10.0}, now, "plc-timeout", now
            ),
            "unknown",
        )
        self.assertEqual(
            driver._derive_extruder_process_state_online(
                {"Speed": 1.0, "Press": 10.0}, now - driver._ext_snapshot_grace_sec() - 0.1, None, now
            ),
            "unknown",
        )

    def test_high_speed_requires_enter_dwell_before_extruding(self) -> None:
        driver = RealPLCDriver()
        now = 1_773_040_825.0

        first = driver._derive_extruder_process_state_online({"Speed": 1.0, "Press": 10.0}, now, None, now)
        second = driver._derive_extruder_process_state_online(
            {"Speed": 1.0, "Press": 10.0},
            now + real_plc.PROCESS_STATE_ENTER_DWELL_SEC + 0.1,
            None,
            now + real_plc.PROCESS_STATE_ENTER_DWELL_SEC + 0.1,
        )

        self.assertEqual(first, "unknown")
        self.assertEqual(second, "extruding")

    def test_restart_low_speed_without_recent_context_stays_unknown_until_idle_dwell(self) -> None:
        driver = RealPLCDriver()
        now = 1_773_040_825.0

        first = driver._derive_extruder_process_state_online({"Speed": 0.0, "Press": 0.0}, now, None, now)
        idle = driver._derive_extruder_process_state_online(
            {"Speed": 0.0, "Press": 0.0},
            now + real_plc.IDLE_CANDIDATE_MIN_SEC + 0.1,
            None,
            now + real_plc.IDLE_CANDIDATE_MIN_SEC + 0.1,
        )

        self.assertEqual(first, "unknown")
        self.assertEqual(idle, "idle_candidate")

    def test_recent_extrusion_low_speed_becomes_stopped_after_exit_dwell(self) -> None:
        driver = RealPLCDriver()
        now = 1_773_040_825.0
        driver._process_state_online = "extruding"
        driver._process_last_extruding_at = now - 1.0
        driver._process_low_speed_since = now - real_plc.PROCESS_STATE_EXIT_DWELL_SEC - 0.1

        state = driver._derive_extruder_process_state_online({"Speed": 0.0, "Press": 10.0}, now, None, now)

        self.assertEqual(state, "stopped")
class PLCServiceHealthTests(unittest.TestCase):
    def test_get_health_exposes_shadow_spot_temperature_source_health_without_urls(self) -> None:
        service = backend_app.PLCService(use_mock=True)
        diagnostics = {
            "spot_service_instance_id": "spot-service-1",
            "spot_poll_seq": 7,
            "spot_observation_seq": 7,
            "spot_poll_status": "timeout",
            "spot_raw_validity": "not_received",
            "spot_source_freshness": "stale",
            "spot_device_status_code": "temperature_under_range",
            "temperature_status_shadow": "ok",
            "spot_cache_status": "reused",
            "temperature_value_origin": "cached_observation",
            "cache_fallback_allowed": True,
            "spot_snapshot_age_ms": 2400.0,
            "spot_value_age_ms": 1400.0,
            "spot_poll_freshness_threshold_sec": 1.5,
            "spot_cache_expiry_threshold_sec": 15.0,
            "temperature_cache_status": "ok",
            "temperature_last_success_at": 1770000000.0,
            "temperature_last_error_at": 1770000001.0,
            "temperature_last_error_code": "temperature-upstream-timeout",
            "temperature_last_url": "http://spot.local/temp",
        }

        with patch(
            "backend.FacilityData.drivers.spot_api.get_image_proxy_diagnostics",
            return_value=diagnostics,
        ):
            health = service.get_health()

        spot_health = health["spot_temperature"]
        self.assertTrue(spot_health["diagnostics_available"])
        self.assertFalse(spot_health["operational_truth"])
        self.assertEqual(spot_health["validation_state"], "shadow")
        self.assertEqual(spot_health["spot_poll_status"], "timeout")
        self.assertEqual(spot_health["spot_source_freshness"], "stale")
        self.assertEqual(spot_health["spot_device_status_code"], "temperature_under_range")
        self.assertEqual(spot_health["temperature_status_shadow"], "ok")
        self.assertEqual(spot_health["temperature_value_origin"], "cached_observation")
        self.assertTrue(spot_health["cache_fallback_allowed"])
        self.assertNotIn("temperature_last_url", spot_health)


class RealPLCPositionReadFlagTests(unittest.TestCase):
    def _merged_read_fixture(self, calls: list[str]):
        def fake_read(addr: str, count: int, deadline: float) -> list[int]:
            calls.append(addr)
            if addr == "D0020":
                values = [0] * 16
                values[3] = 300
                values[11] = 410
                values[12] = 420
                return values
            if addr == "D0420":
                values = [0] * 6
                values[1] = 10150
                return values
            if addr == "D1500":
                values = [0] * 16
                values[10] = 7
                return values
            if addr == "D1900":
                values = [0] * 16
                values[11] = 650
                return values
            if addr == "B1502":
                return [45]
            if addr == "D0010":
                return [4970, 0, 116]
            return []

        return fake_read

    def test_position_read_disabled_does_not_read_d0010(self) -> None:
        driver = RealPLCDriver()
        calls: list[str] = []

        with patch("backend.FacilityData.drivers.real_plc.config.POSITION_READ_ENABLED", False):
            with patch.object(driver, "_melsec_read", side_effect=self._merged_read_fixture(calls)):
                data = driver._read_extruder_merged(9999999999.0)

        self.assertIsNotNone(data)
        assert data is not None
        self.assertNotIn("D0010", calls)
        self.assertNotIn("MainRamPosition_D0010", data)
        self.assertNotIn("ContainerPosition_D0012", data)

    def test_position_read_enabled_reads_d0010_and_maps_positions(self) -> None:
        driver = RealPLCDriver()
        calls: list[str] = []

        with patch("backend.FacilityData.drivers.real_plc.config.POSITION_READ_ENABLED", True):
            with patch.object(driver, "_melsec_read", side_effect=self._merged_read_fixture(calls)):
                data = driver._read_extruder_merged(9999999999.0)

        self.assertIsNotNone(data)
        assert data is not None
        self.assertIn("D0010", calls)
        self.assertEqual(data["MainRamPosition_D0010"], 497.0)
        self.assertEqual(data["ContainerPosition_D0012"], 11.6)


class OperatorMetadataApiTests(unittest.TestCase):
    TRUSTED_WRITE_HEADERS = {"origin": "http://localhost:3000", "host": "localhost:8000"}

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = backend_app.operator_metadata_store._path
        self.original_metadata = backend_app.operator_metadata_store.get()
        self.original_runtime_state_path = backend_app.plc_service.operator_metadata_runtime_state_path
        self.original_previous_count = backend_app.plc_service.operator_metadata_previous_count
        self.original_last_normal_sample_at = backend_app.plc_service.operator_metadata_last_normal_sample_at
        self.original_last_state_write_at = backend_app.plc_service.operator_metadata_last_state_write_at
        self.original_process_operator_context = backend_app.plc_service._process_operator_context
        self.original_reset_hours = backend_app.config.OPERATOR_METADATA_DOWNTIME_RESET_HOURS
        with backend_app.operator_metadata_store._lock:
            backend_app.operator_metadata_store._path = Path(self.temp_dir.name) / "operator_metadata.json"
            backend_app.operator_metadata_store._metadata = OperatorMetadata()
        backend_app.plc_service.operator_metadata_runtime_state_path = (
            Path(self.temp_dir.name) / "operator_metadata_runtime_state.json"
        )
        backend_app.plc_service.operator_metadata_previous_count = None
        backend_app.plc_service.operator_metadata_last_normal_sample_at = None
        backend_app.plc_service.operator_metadata_last_state_write_at = None
        backend_app.plc_service._process_operator_context = None
        backend_app.config.OPERATOR_METADATA_DOWNTIME_RESET_HOURS = 8

    def tearDown(self) -> None:
        with backend_app.operator_metadata_store._lock:
            backend_app.operator_metadata_store._path = self.original_path
            backend_app.operator_metadata_store._metadata = self.original_metadata
        backend_app.plc_service.operator_metadata_runtime_state_path = self.original_runtime_state_path
        backend_app.plc_service.operator_metadata_previous_count = self.original_previous_count
        backend_app.plc_service.operator_metadata_last_normal_sample_at = self.original_last_normal_sample_at
        backend_app.plc_service.operator_metadata_last_state_write_at = self.original_last_state_write_at
        backend_app.plc_service._process_operator_context = self.original_process_operator_context
        backend_app.config.OPERATOR_METADATA_DOWNTIME_RESET_HOURS = self.original_reset_hours
        self.temp_dir.cleanup()

    def _factory_data(self, count: int | None = 3) -> FactoryData:
        return FactoryData(
            Time="2026-03-09T07:20:25.123",
            Status="Running",
            Speed=1.0,
            Press=2.0,
            Count=count,
            EndPos=4.0,
            Billet_Length=5.0,
            Spot=6.0,
            Temp_F=7.0,
            Temp_B=8.0,
            Billet_Temp=9.0,
            Mold1=10.0,
            Mold2=11.0,
            Mold3=12.0,
            Mold4=13.0,
            Mold5=14.0,
            Mold6=15.0,
            At_Temp=16.0,
            At_Pre=17.0,
        )

    def _set_operator_metadata_runtime_state(self, last_sample_at: float, count: int = 3) -> None:
        payload = {
            "operator_metadata_runtime_state_version": "1.0.0",
            "last_normal_sample_at": last_sample_at,
            "last_count": count,
        }
        backend_app.plc_service.operator_metadata_runtime_state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        backend_app.plc_service.operator_metadata_previous_count = None
        backend_app.plc_service.operator_metadata_last_normal_sample_at = last_sample_at
        backend_app.plc_service.operator_metadata_last_state_write_at = last_sample_at

    def test_get_returns_default_invalid_state(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.get("/api/facility/operator-metadata")
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["missing_fields"], ["product_no", "operator_mold_no"])
        self.assertEqual(payload["history"], [])

    def test_put_persists_valid_operator_metadata(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "12345", "operator_mold_no": "123"},
                headers=self.TRUSTED_WRITE_HEADERS,
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["product_no"], "12345")
        self.assertEqual(payload["operator_mold_no"], "123")
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["missing_fields"], [])
        self.assertEqual(payload["history"], [])
        self.assertTrue(backend_app.operator_metadata_store._path.exists())

    def test_put_returns_previous_three_operator_metadata_entries(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            for product_no, mold_no in [
                ("11111", "111"),
                ("22222", "222"),
                ("33333", "333"),
                ("44444", "444"),
            ]:
                response = client.put(
                    "/api/facility/operator-metadata",
                    json={"product_no": product_no, "operator_mold_no": mold_no},
                    headers=self.TRUSTED_WRITE_HEADERS,
                )
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["product_no"], "44444")
        self.assertEqual(payload["operator_mold_no"], "444")
        self.assertEqual(
            [(item["product_no"], item["operator_mold_no"]) for item in payload["history"]],
            [("33333", "333"), ("22222", "222"), ("11111", "111")],
        )

        persisted = json.loads(backend_app.operator_metadata_store._path.read_text(encoding="utf-8"))
        self.assertEqual(
            [(item["product_no"], item["operator_mold_no"]) for item in persisted["metadata"]["history"]],
            [("33333", "333"), ("22222", "222"), ("11111", "111")],
        )

    def test_put_records_history_when_only_product_no_changes(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "11111", "operator_mold_no": "123"},
                headers=self.TRUSTED_WRITE_HEADERS,
            )
            response = client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "22222", "operator_mold_no": "123"},
                headers=self.TRUSTED_WRITE_HEADERS,
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [(item["product_no"], item["operator_mold_no"]) for item in payload["history"]],
            [("11111", "123")],
        )

    def test_put_records_history_when_only_operator_mold_no_changes(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "11111", "operator_mold_no": "123"},
                headers=self.TRUSTED_WRITE_HEADERS,
            )
            response = client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "11111", "operator_mold_no": "456"},
                headers=self.TRUSTED_WRITE_HEADERS,
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [(item["product_no"], item["operator_mold_no"]) for item in payload["history"]],
            [("11111", "123")],
        )

    def test_put_same_values_reapply_does_not_duplicate_history(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "11111", "operator_mold_no": "111"},
                headers=self.TRUSTED_WRITE_HEADERS,
            )
            client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "22222", "operator_mold_no": "222"},
                headers=self.TRUSTED_WRITE_HEADERS,
            )
            response = client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "22222", "operator_mold_no": "222"},
                headers=self.TRUSTED_WRITE_HEADERS,
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [(item["product_no"], item["operator_mold_no"]) for item in payload["history"]],
            [("11111", "111")],
        )

    def test_put_rejects_untrusted_origin(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "12345", "operator_mold_no": "123"},
                headers={"origin": "https://example.invalid", "host": "localhost:8000"},
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(backend_app.operator_metadata_store.get().product_no, "")

    def test_put_rejects_csv_formula_prefix(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "12345", "operator_mold_no": "=cmd"},
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 422)
        self.assertEqual(backend_app.operator_metadata_store.get().operator_mold_no, "")

    def test_put_rejects_non_numeric_operator_metadata(self) -> None:
        invalid_payloads = [
            {"product_no": "DW-12345", "operator_mold_no": "123"},
            {"product_no": "ABC", "operator_mold_no": "123"},
            {"product_no": "123-1", "operator_mold_no": "123"},
            {"product_no": "123\n", "operator_mold_no": "123"},
            {"product_no": "12345", "operator_mold_no": "ABC"},
            {"product_no": "12345", "operator_mold_no": "123-1"},
            {"product_no": "12345", "operator_mold_no": "123\r\n"},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                client = TestClient(backend_app.app, raise_server_exceptions=False)
                try:
                    response = client.put("/api/facility/operator-metadata", json=payload)
                finally:
                    client.close()

                self.assertEqual(response.status_code, 422)
                self.assertEqual(backend_app.operator_metadata_store.get().product_no, "")
                self.assertEqual(backend_app.operator_metadata_store.get().operator_mold_no, "")

    def test_put_rejects_missing_required_fields(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "12345", "operator_mold_no": ""},
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 422)
        self.assertFalse(backend_app.operator_metadata_store.get().valid)

    def test_delete_resets_operator_metadata_to_persisted_invalid_state(self) -> None:
        backend_app.operator_metadata_store.update(
            OperatorMetadataUpdate(product_no="12345", operator_mold_no="123")
        )
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.delete(
                "/api/facility/operator-metadata",
                headers=self.TRUSTED_WRITE_HEADERS,
            )
            get_response = client.get("/api/facility/operator-metadata")
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["product_no"], "")
        self.assertEqual(payload["operator_mold_no"], "")
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["missing_fields"], ["product_no", "operator_mold_no"])
        self.assertIsNotNone(payload["updated_at"])
        self.assertEqual(get_response.json(), payload)

        persisted = json.loads(backend_app.operator_metadata_store._path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["operator_metadata_version"], "1.0.0")
        self.assertEqual(persisted["metadata"]["product_no"], "")
        self.assertEqual(persisted["metadata"]["operator_mold_no"], "")
        self.assertFalse(persisted["metadata"]["valid"])
        self.assertEqual(persisted["metadata"]["missing_fields"], ["product_no", "operator_mold_no"])

        composed = backend_app.plc_service._compose_data(
            FactoryData(
                Time="2026-03-09T07:20:25.123",
                Status="Running",
                Speed=1.0,
                Press=2.0,
                Count=3,
                EndPos=4.0,
                Billet_Length=5.0,
                Spot=6.0,
                Temp_F=7.0,
                Temp_B=8.0,
                Billet_Temp=9.0,
                Mold1=10.0,
                Mold2=11.0,
                Mold3=12.0,
                Mold4=13.0,
                Mold5=14.0,
                Mold6=15.0,
                At_Temp=16.0,
                At_Pre=17.0,
            )
        )
        self.assertEqual(composed.Product_No_operator, "")
        self.assertEqual(composed.Mold_No_operator, "")
        self.assertFalse(composed.operator_metadata_valid)
        self.assertEqual(composed.operator_metadata_missing_fields, ["product_no", "operator_mold_no"])
        self.assertEqual(composed.operator_metadata_updated_at, payload["updated_at"])

    def test_delete_rejects_untrusted_origin(self) -> None:
        backend_app.operator_metadata_store.update(
            OperatorMetadataUpdate(product_no="12345", operator_mold_no="123")
        )
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.delete(
                "/api/facility/operator-metadata",
                headers={"origin": "https://example.invalid", "host": "localhost:8000"},
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(backend_app.operator_metadata_store.get().product_no, "12345")
        self.assertEqual(backend_app.operator_metadata_store.get().operator_mold_no, "123")

    def test_store_keeps_existing_memory_state_when_persist_fails(self) -> None:
        existing_metadata = OperatorMetadata(
            product_no="11111",
            operator_mold_no="111",
            updated_at="2026-03-09T07:20:20Z",
        )
        with backend_app.operator_metadata_store._lock:
            backend_app.operator_metadata_store._metadata = existing_metadata

        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                backend_app.operator_metadata_store.update(
                    OperatorMetadataUpdate(product_no="22222", operator_mold_no="222")
                )

        current_metadata = backend_app.operator_metadata_store.get()
        self.assertEqual(current_metadata.product_no, "11111")
        self.assertEqual(current_metadata.operator_mold_no, "111")

    def test_compose_data_attaches_current_operator_metadata(self) -> None:
        backend_app.operator_metadata_store.update(
            OperatorMetadataUpdate(product_no="12345", operator_mold_no="123")
        )
        raw_data = FactoryData(
            Time="2026-03-09T07:20:25.123",
            Status="Running",
            Speed=1.0,
            Press=2.0,
            Count=3,
            EndPos=4.0,
            Billet_Length=5.0,
            Spot=6.0,
            Temp_F=7.0,
            Temp_B=8.0,
            Billet_Temp=9.0,
            Mold1=10.0,
            Mold2=11.0,
            Mold3=12.0,
            Mold4=13.0,
            Mold5=14.0,
            Mold6=15.0,
            At_Temp=16.0,
            At_Pre=17.0,
        )

        composed = backend_app.plc_service._compose_data(raw_data)

        self.assertEqual(composed.Product_No_operator, "12345")
        self.assertEqual(composed.Mold_No_operator, "123")
        self.assertTrue(composed.operator_metadata_valid)
        self.assertEqual(composed.operator_metadata_missing_fields, [])
        self.assertIsNotNone(composed.operator_metadata_updated_at)


    def test_compose_data_marks_changeover_candidate_only_for_valid_metadata_change_while_stopped(self) -> None:
        backend_app.plc_service._process_operator_context = ("11111", "111")
        backend_app.operator_metadata_store.update(
            OperatorMetadataUpdate(product_no="22222", operator_mold_no="222")
        )
        raw_data = self._factory_data(count=0).model_copy(
            update={"Speed": 0.0, "Press": 0.0, "extruder_process_state_online": "stopped"}
        )

        composed = backend_app.plc_service._compose_data(raw_data)

        self.assertEqual(composed.extruder_process_state_online, "changeover_candidate")

    def test_compose_data_does_not_mark_changeover_candidate_while_extruding(self) -> None:
        backend_app.plc_service._process_operator_context = ("11111", "111")
        backend_app.operator_metadata_store.update(
            OperatorMetadataUpdate(product_no="22222", operator_mold_no="222")
        )
        raw_data = self._factory_data(count=3).model_copy(
            update={"Speed": 1.0, "Press": 2.0, "extruder_process_state_online": "extruding"}
        )

        composed = backend_app.plc_service._compose_data(raw_data)

        self.assertEqual(composed.extruder_process_state_online, "extruding")

    def test_downtime_reset_after_threshold_with_zero_count(self) -> None:
        backend_app.operator_metadata_store.update(
            OperatorMetadataUpdate(product_no="12345", operator_mold_no="123")
        )
        now = 1_773_040_825.0
        self._set_operator_metadata_runtime_state(now - (8 * 60 * 60) - 1, count=9)

        composed = backend_app.plc_service._compose_data(self._factory_data(count=0), captured_at_sec=now)

        self.assertEqual(composed.Product_No_operator, "")
        self.assertEqual(composed.Mold_No_operator, "")
        self.assertFalse(composed.operator_metadata_valid)
        current = backend_app.operator_metadata_store.get()
        self.assertFalse(current.valid)
        self.assertEqual(current.source, "auto_downtime_threshold")

    def test_downtime_reset_after_threshold_with_positive_count(self) -> None:
        backend_app.operator_metadata_store.update(
            OperatorMetadataUpdate(product_no="12345", operator_mold_no="123")
        )
        now = 1_773_040_825.0
        self._set_operator_metadata_runtime_state(now - (8 * 60 * 60) - 1, count=9)

        composed = backend_app.plc_service._compose_data(self._factory_data(count=2), captured_at_sec=now)

        self.assertEqual(composed.Product_No_operator, "")
        self.assertEqual(composed.Mold_No_operator, "")
        self.assertFalse(composed.operator_metadata_valid)
        self.assertEqual(backend_app.operator_metadata_store.get().source, "auto_downtime_threshold")

    def test_downtime_under_threshold_does_not_reset(self) -> None:
        backend_app.operator_metadata_store.update(
            OperatorMetadataUpdate(product_no="12345", operator_mold_no="123")
        )
        now = 1_773_040_825.0
        self._set_operator_metadata_runtime_state(now - (7 * 60 * 60), count=9)

        composed = backend_app.plc_service._compose_data(self._factory_data(count=2), captured_at_sec=now)

        self.assertEqual(composed.Product_No_operator, "12345")
        self.assertEqual(composed.Mold_No_operator, "123")
        self.assertTrue(composed.operator_metadata_valid)
        self.assertEqual(backend_app.operator_metadata_store.get().product_no, "12345")

    def test_running_positive_count_to_zero_resets(self) -> None:
        backend_app.operator_metadata_store.update(
            OperatorMetadataUpdate(product_no="12345", operator_mold_no="123")
        )
        now = 1_773_040_825.0

        first = backend_app.plc_service._compose_data(self._factory_data(count=3), captured_at_sec=now)
        second = backend_app.plc_service._compose_data(self._factory_data(count=0), captured_at_sec=now + 1)

        self.assertTrue(first.operator_metadata_valid)
        self.assertEqual(second.Product_No_operator, "")
        self.assertEqual(second.Mold_No_operator, "")
        self.assertFalse(second.operator_metadata_valid)
        self.assertEqual(backend_app.operator_metadata_store.get().source, "auto_count_transition_to_zero")

    def test_auto_reset_skips_duplicate_when_metadata_already_invalid(self) -> None:
        now = 1_773_040_825.0
        self._set_operator_metadata_runtime_state(now - (8 * 60 * 60) - 1, count=9)

        composed = backend_app.plc_service._compose_data(self._factory_data(count=0), captured_at_sec=now)

        current = backend_app.operator_metadata_store.get()
        self.assertFalse(composed.operator_metadata_valid)
        self.assertIsNone(current.updated_at)
        self.assertFalse(backend_app.operator_metadata_store._path.exists())
        self.assertTrue(backend_app.plc_service.operator_metadata_runtime_state_path.exists())

    def test_auto_reset_sample_records_blank_operator_metadata_in_v2_csv_without_changing_v1(self) -> None:
        backend_app.operator_metadata_store.update(
            OperatorMetadataUpdate(product_no="12345", operator_mold_no="123")
        )
        now = 1_773_040_825.0
        self._set_operator_metadata_runtime_state(now - (8 * 60 * 60) - 1, count=9)
        composed = backend_app.plc_service._compose_data(self._factory_data(count=2), captured_at_sec=now)
        service = CSVLoggerService()
        timestamp = service._parse_timestamp(composed)
        v1_row = service._build_row(composed, timestamp)

        v2_row = service._build_v2_row(composed, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertNotIn("Product_No_operator", V1_CSV_COLUMNS)
        self.assertNotIn("Mold_No_operator", V1_CSV_COLUMNS)
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Product_No_operator")], "")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Mold_No_operator")], "")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("operator_metadata_valid")], "false")

class CSVLoggerV2ContractTests(unittest.TestCase):
    def create_data(self, press_value: float | None = 30.0) -> FactoryData:
        return FactoryData(
            Time="2026-03-09T07:20:25.123",
            Status="Running",
            Press=press_value,
            Spot=100.0,
            Billet_Length=1.0,
            Temp_F=2.0,
            Temp_B=3.0,
            Count=1,
            Speed=4.0,
            EndPos=5.0,
            MainRamPosition_D0010=15.0,
            ContainerPosition_D0012=16.0,
            Mold1=6.0,
            Mold2=7.0,
            Mold3=8.0,
            Mold4=9.0,
            Mold5=10.0,
            Mold6=11.0,
            Billet_Temp=12.0,
            At_Pre=13.0,
            At_Temp=14.0,
            Die_ID="D1",
            Billet_Cycle_ID="C1",
            Product_No_operator="12345",
            Mold_No_operator="123",
            operator_metadata_valid=True,
            operator_metadata_missing_fields=[],
            operator_metadata_updated_at="2026-03-09T07:20:20Z",
            captured_at_extruder=1773040825.0,
            captured_at_ls=1773040825.0,
            captured_at_spot=1773040825.0,
        )

    def _read_csv_rows(self, path: Path) -> list[list[str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.reader(handle))

    def _write_spot_image_fact_fixture(self, path: Path, rows: int) -> tuple[int, str]:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(SPOT_IMAGE_FACT_REQUIRED_COLUMNS)
            for seq in range(1, rows + 1):
                writer.writerow(
                    [
                        f"capture-{seq}",
                        f"spot_images/20260702/capture-{seq}.jpg",
                        f"{seq:064x}",
                        "123",
                        "image/jpeg",
                        "100",
                        "fresh",
                        f"spot-service:{seq}",
                    ]
                )
        return rows, hashlib.sha256(path.read_bytes()).hexdigest()

    def _list_v1_files(self, log_dir: Path) -> list[Path]:
        return sorted(
            path for path in log_dir.glob("Factory_Integrated_Log_*.csv") if "_v2_" not in path.name
        )

    def _list_v2_files(self, log_dir: Path) -> list[Path]:
        return sorted(log_dir.glob("Factory_Integrated_Log_v2_*.csv"))

    def _run_logger_once(
        self,
        log_dir: Path,
        *,
        csv_v1_enabled: bool,
        csv_v2_enabled: bool,
    ) -> CSVLoggerService:
        service = CSVLoggerService()
        service.fallback_log_dir = log_dir
        service.apply_config(
            log_path=log_dir,
            auto_save=True,
            csv_v1_enabled=csv_v1_enabled,
            csv_v2_enabled=csv_v2_enabled,
        )
        service.start()
        try:
            service.enqueue(self.create_data())
            service.stop()
        finally:
            if service.running:
                service.stop()
        return service

    def test_v1_golden_row_contract_is_stable(self) -> None:
        service = CSVLoggerService()
        data = self.create_data()

        row = service._build_row(data, service._parse_timestamp(data))

        self.assertEqual(
            row,
            [
                "2026-03-09",
                "07:20:25.123",
                "100.0",
                "30.0",
                "1.0",
                "2.0",
                "3.0",
                "1",
                "4.0",
                "5.0",
                "6.0",
                "7.0",
                "8.0",
                "9.0",
                "10.0",
                "11.0",
                "12.0",
                "13.0",
                "14.0",
                "D1",
                "C1",
            ],
        )

    def test_header_mismatch_falls_back_to_v1_contract(self) -> None:
        service = CSVLoggerService()

        with self.assertLogs("SmartFactoryLoggerV2", level="WARNING") as logs:
            service.apply_config(csv_header="Date,Time,Temperature")

        self.assertEqual(service.csv_header, V1_CSV_COLUMNS)
        self.assertTrue(any("CSV header ignored" in message for message in logs.output))

    def test_header_position_mismatch_falls_back_to_v1_contract(self) -> None:
        service = CSVLoggerService()
        swapped_header = ",".join(
            [
                "Date",
                "Time",
                "Temperature",
                "MainPress",
                "BilletLength",
                "Temp_F",
                "Temp_B",
                "Count",
                "EndPos",
                "Speed",
                "Mold1",
                "Mold2",
                "Mold3",
                "Mold4",
                "Mold5",
                "Mold6",
                "Billet_Temp",
                "At_Pre",
                "At_Temp",
                "DIE_ID",
                "Billet_CycleID",
            ]
        )

        with self.assertLogs("SmartFactoryLoggerV2", level="WARNING") as logs:
            service.apply_config(csv_header=swapped_header)

        self.assertEqual(service.csv_header, V1_CSV_COLUMNS)
        self.assertTrue(any("label does not match v1 position contract" in message for message in logs.output))

    def test_known_legacy_header_aliases_are_accepted_by_position(self) -> None:
        service = CSVLoggerService()
        legacy_header = ",".join(
            [
                "Date",
                "Time",
                "Temperature",
                "메인압력",
                "빌렛길이",
                "콘테이너온도 앞쪽",
                "콘테이너온도 뒷쪽",
                "생산카운터",
                "현재속도",
                "압출종료 위치",
                "Mold1",
                "Mold2",
                "Mold3",
                "Mold4",
                "Mold5",
                "Mold6",
                "Billet_Temp",
                "At_Pre",
                "At_Temp",
                "DIE_ID",
                "Billet_CycleID",
            ]
        )

        service.apply_config(csv_header=legacy_header)

        self.assertEqual(service.csv_header, legacy_header.split(","))

    def test_v2_row_marks_mainpress_missing_without_changing_v1_zero(self) -> None:
        service = CSVLoggerService()
        data = self.create_data(press_value=None)
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertEqual(v1_row[3], "0.0")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("MainPress_quality")], "missing")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("MainPress_missing_reason")], "source_missing")

    def test_v2_row_keeps_temperature_empty_when_value_origin_none(self) -> None:
        service = CSVLoggerService()
        data = self.create_data().model_copy(
            update={
                "Spot": None,
                "temperature_status_shadow": "no_target",
                "temperature_value_origin": "none",
                "spot_cache_status": "invalidated",
                "spot_source_freshness": "fresh",
                "spot_raw_validity": "verified_no_target",
            }
        )
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertEqual(v1_row[V1_CSV_COLUMNS.index("Temperature")], "")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Temperature")], "")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Temperature_quality")], "missing")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Temperature_missing_reason")], "source_missing")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("temperature_value_origin")], "none")

    def test_v2_row_sets_origin_none_when_current_observation_is_row_stale(self) -> None:
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True)
        data = self.create_data().model_copy(
            update={
                "Spot": 557.9,
                "Time": "2026-03-09T07:20:25.123+00:00",
                "temperature_status_shadow": "ok",
                "temperature_value_origin": "current_observation",
                "spot_poll_status": "success",
                "spot_raw_validity": "valid_temperature",
                "spot_cache_status": "fresh",
                "spot_source_freshness": "fresh",
                "spot_temperature_observed_c": 557.9,
                "spot_last_poll_completed_at": "2026-03-09T07:20:15.123Z",
                "spot_last_valid_value_at": "2026-03-09T07:20:24.012Z",
                "spot_effective_age_ms_at_row": 10_000.0,
            }
        )
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)
        contract = service._get_active_v2_contract()
        columns = list(contract.columns)

        self.assertEqual(contract.schema_version, CSV_SCHEMA_VERSION_V2_4)
        self.assertEqual(v2_row[columns.index("Temperature")], "")
        self.assertEqual(v2_row[columns.index("temperature_value_origin")], "none")
        self.assertEqual(v2_row[columns.index("temperature_output_status")], "stale")
        self.assertEqual(v2_row[columns.index("spot_effective_freshness_at_row")], "stale")

        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path, service._get_active_v2_contract())

            result = validate_csv_v2_shadow(None, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 0)

    def test_v2_row_records_reset_operator_metadata_as_invalid(self) -> None:
        service = CSVLoggerService()
        data = self.create_data()
        data.Product_No_operator = ""
        data.Mold_No_operator = ""
        data.operator_metadata_valid = False
        data.operator_metadata_missing_fields = ["product_no", "operator_mold_no"]
        data.operator_metadata_updated_at = "2026-03-09T07:21:00Z"
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Product_No_operator")], "")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Mold_No_operator")], "")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("operator_metadata_valid")], "false")
        self.assertEqual(
            v2_row[V2_CSV_COLUMNS.index("operator_metadata_missing_fields")],
            "product_no,operator_mold_no",
        )
        self.assertEqual(
            v2_row[V2_CSV_COLUMNS.index("operator_metadata_updated_at")],
            "2026-03-09T07:21:00Z",
        )

    def test_v2_row_marks_billet_length_zero_as_idle_not_missing(self) -> None:
        service = CSVLoggerService()
        data = self.create_data().model_copy(update={"Billet_Length": 0.0})
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertEqual(v1_row[V1_CSV_COLUMNS.index("BilletLength")], "0.0")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("BilletLength_quality")], "idle")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("BilletLength_missing_reason")], "not_missing")

    def test_v2_row_marks_positive_billet_length_as_ok(self) -> None:
        service = CSVLoggerService()
        data = self.create_data().model_copy(update={"Billet_Length": 650.0})
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertEqual(v1_row[V1_CSV_COLUMNS.index("BilletLength")], "650.0")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("BilletLength_quality")], "ok")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("BilletLength_missing_reason")], "not_missing")

    def test_v2_row_includes_actual_position_fields_without_changing_v1(self) -> None:
        service = CSVLoggerService()
        data = self.create_data()
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertNotIn("MainRamPosition_D0010", V1_CSV_COLUMNS)
        self.assertNotIn("ContainerPosition_D0012", V1_CSV_COLUMNS)
        self.assertEqual(len(v1_row), 21)
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("MainRamPosition_D0010")], "15.0")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("ContainerPosition_D0012")], "16.0")

    def test_v2_row_includes_v2_3_shadow_fields_without_duplicate_sample_seq(self) -> None:
        service = CSVLoggerService()
        data = self.create_data()
        data.extruder_process_state_online = "extruding"
        data.process_state_online_rule_version = "process-state-online-v1"
        data.spot_target_state_observed_shadow = "present"
        data.spot_target_state_observed_source = "valid_temperature"
        data.label_validation_state = "shadow"
        data.temperature_status_shadow = "ok"
        data.temperature_status_rule_version = "temperature-status-shadow-v1"
        data.spot_poll_status = "success"
        data.spot_raw_validity = "valid_temperature"
        data.spot_cache_status = "fresh"
        data.spot_source_freshness = "fresh"
        data.temperature_value_origin = "current_observation"
        data.cache_fallback_allowed = False
        data.spot_service_instance_id = "spot-service-1"
        data.spot_service_started_at = "2026-03-09T07:20:00Z"
        data.spot_poll_seq = 10
        data.spot_observation_seq = 10
        data.spot_temperature_observed_c = 448.5
        data.spot_temperature_raw = "=448.5"
        data.spot_raw_payload_hash = "abc123"
        data.spot_raw_payload_encoding = "utf-8-replace"
        data.spot_http_status_code = 200
        data.spot_device_status_code = "temperature_under_range"
        data.spot_poll_duration_ms = 12.5
        data.spot_response_content_length = 5
        data.spot_last_poll_started_at = "2026-03-09T07:20:24.000Z"
        data.spot_last_poll_completed_at = "2026-03-09T07:20:24.012Z"
        data.spot_last_response_at = "2026-03-09T07:20:24.012Z"
        data.spot_last_valid_value_at = "2026-03-09T07:20:24.012Z"
        data.spot_snapshot_age_ms = 188.0
        data.spot_value_age_ms = 188.0
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        contract = service._get_active_v2_contract()
        self.assertFalse(hasattr(repository_module, "CSV_SCHEMA_VERSION"))
        self.assertEqual(contract.schema_version, CSV_SCHEMA_VERSION_V2_3)
        self.assertEqual(tuple(V2_CSV_COLUMNS), contract.columns)
        self.assertEqual(V2_CSV_COLUMNS.count("sample_seq"), 1)
        for column in SPOT_TEMPERATURE_SHADOW_COLUMNS:
            self.assertIn(column, V2_CSV_COLUMNS)
        self.assertEqual(len(v2_row), len(V2_CSV_COLUMNS))
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("schema_version")], CSV_SCHEMA_VERSION_V2_3)
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("logger_service_instance_id")], service.logger_service_instance_id)
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("logger_service_started_at")], service.logger_service_started_at)
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("extruder_process_state_online")], "extruding")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("temperature_status_shadow")], "ok")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("spot_poll_status")], "success")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("spot_temperature_observed_c")], "448.5")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("spot_temperature_raw")], "'=448.5")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("spot_temperature_raw_truncated")], "false")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("spot_device_status_code")], "temperature_under_range")

    def test_v2_row_includes_operator_metadata_without_changing_v1(self) -> None:
        service = CSVLoggerService()
        data = self.create_data()
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertNotIn("Product_No_operator", V1_CSV_COLUMNS)
        self.assertNotIn("Mold_No_operator", V1_CSV_COLUMNS)
        self.assertEqual(len(v1_row), 21)
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Product_No_operator")], "12345")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Mold_No_operator")], "123")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("operator_metadata_valid")], "true")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("operator_metadata_missing_fields")], "")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("operator_metadata_updated_at")], "2026-03-09T07:20:20Z")

    def test_v2_row_records_missing_operator_metadata_as_invalid(self) -> None:
        service = CSVLoggerService()
        data = self.create_data().model_copy(update={
            "Product_No_operator": "",
            "Mold_No_operator": "",
            "operator_metadata_valid": False,
            "operator_metadata_missing_fields": ["product_no", "operator_mold_no"],
            "operator_metadata_updated_at": None,
        })
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("operator_metadata_valid")], "false")
        self.assertEqual(
            v2_row[V2_CSV_COLUMNS.index("operator_metadata_missing_fields")],
            "product_no,operator_mold_no",
        )

    def test_csv_injection_escapes_string_fields(self) -> None:
        service = CSVLoggerService()
        data = self.create_data().model_copy(update={
            "Die_ID": "=cmd",
            "Billet_Cycle_ID": "+cycle",
            "Product_No_operator": "@product",
            "Mold_No_operator": "-mold",
        })
        timestamp = service._parse_timestamp(data)

        row = service._build_row(data, timestamp)
        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, row)

        self.assertEqual(row[19], "'=cmd")
        self.assertEqual(row[20], "'+cycle")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Product_No_operator")], "'@product")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Mold_No_operator")], "'-mold")

    def test_csv_writer_mode_v1_enabled_v2_disabled_creates_v1_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            self._run_logger_once(log_dir, csv_v1_enabled=True, csv_v2_enabled=False)

            self.assertEqual(len(self._list_v1_files(log_dir)), 1)
            self.assertEqual(self._list_v2_files(log_dir), [])

    def test_csv_writer_mode_v1_enabled_v2_enabled_creates_both_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            self._run_logger_once(log_dir, csv_v1_enabled=True, csv_v2_enabled=True)

            self.assertEqual(len(self._list_v1_files(log_dir)), 1)
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(len(v2_files), 1)
            metadata = json.loads(v2_files[0].with_suffix(".metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(metadata["schema_metadata"]["v1_csv_enabled"])

    def test_csv_writer_mode_v1_disabled_v2_enabled_creates_v2_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            self._run_logger_once(log_dir, csv_v1_enabled=False, csv_v2_enabled=True)

            self.assertEqual(self._list_v1_files(log_dir), [])
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(len(v2_files), 1)
            rows = self._read_csv_rows(v2_files[0])
            self.assertEqual(rows[0], V2_CSV_COLUMNS)
            self.assertEqual(len(rows), 2)
            metadata = json.loads(v2_files[0].with_suffix(".metadata.json").read_text(encoding="utf-8"))
            self.assertFalse(metadata["schema_metadata"]["v1_csv_enabled"])

    def test_csv_writer_mode_v1_disabled_v2_disabled_falls_back_to_v1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            with self.assertLogs("SmartFactoryLoggerV2", level="WARNING") as logs:
                service = self._run_logger_once(log_dir, csv_v1_enabled=False, csv_v2_enabled=False)

            self.assertTrue(service.csv_v1_enabled)
            self.assertTrue(any("cannot disable both v1 and v2 writers" in message for message in logs.output))
            self.assertEqual(len(self._list_v1_files(log_dir)), 1)
            self.assertEqual(self._list_v2_files(log_dir), [])

    def test_hot_reload_to_v2_only_flushes_pending_v1_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v1_enabled=True,
                csv_v2_enabled=False,
            )
            service.start()
            try:
                service.enqueue(self.create_data())
                deadline = time.time() + 2.0
                while service._buffer_size < 1 and time.time() < deadline:
                    time.sleep(0.01)
                self.assertEqual(service._buffer_size, 1)

                service.apply_config(csv_v1_enabled=False, csv_v2_enabled=True)

                deadline = time.time() + 2.0
                while service._buffer_size != 0 and time.time() < deadline:
                    time.sleep(0.01)
            finally:
                service.stop()

            v1_files = self._list_v1_files(log_dir)
            self.assertEqual(len(v1_files), 1)
            rows = self._read_csv_rows(v1_files[0])
            self.assertEqual(rows[0], V1_CSV_COLUMNS)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1][V1_CSV_COLUMNS.index("Time")], "07:20:25.123")

    def test_csv_writer_rolls_over_v1_v2_and_sidecar_at_midnight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v1_enabled=True,
                csv_v2_enabled=True,
            )
            service.start()
            try:
                service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-09T23:59:59.900"}))
                service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-10T00:00:00.100"}))
                time.sleep(1.2)
            finally:
                service.stop()

            v1_files = self._list_v1_files(log_dir)
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(
                [path.name for path in v1_files],
                [
                    "Factory_Integrated_Log_20260309_235959.csv",
                    "Factory_Integrated_Log_20260310_000000.csv",
                ],
            )
            self.assertEqual(
                [path.name for path in v2_files],
                [
                    "Factory_Integrated_Log_v2_20260309_235959.csv",
                    "Factory_Integrated_Log_v2_20260310_000000.csv",
                ],
            )
            self.assertTrue(v2_files[0].with_suffix(".metadata.json").exists())
            self.assertTrue(v2_files[1].with_suffix(".metadata.json").exists())

            first_v2_rows = self._read_csv_rows(v2_files[0])
            second_v2_rows = self._read_csv_rows(v2_files[1])
            sample_seq_index = V2_CSV_COLUMNS.index("sample_seq")
            date_index = V2_CSV_COLUMNS.index("Date")
            self.assertEqual(first_v2_rows[1][sample_seq_index], "1")
            self.assertEqual(second_v2_rows[1][sample_seq_index], "2")
            self.assertEqual(first_v2_rows[1][date_index], "2026-03-09")
            self.assertEqual(second_v2_rows[1][date_index], "2026-03-10")

    def test_csv_rollover_defers_new_day_row_until_previous_day_flush_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v1_enabled=True,
                csv_v2_enabled=True,
            )
            original_flush = service._flush_buffer
            injected_failure = {"remaining": 1}

            def fail_previous_day_flush_once(writer, handle, buffer):
                rows = list(buffer)
                if injected_failure["remaining"] and rows and rows[0][1].date().isoformat() == "2026-03-09":
                    injected_failure["remaining"] = 0
                    return False
                return original_flush(writer, handle, rows)

            with patch.object(service, "_flush_buffer", side_effect=fail_previous_day_flush_once):
                service.start()
                try:
                    service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-09T23:59:59.900"}))
                    deadline = time.time() + 2.0
                    while service._buffer_size < 1 and time.time() < deadline:
                        time.sleep(0.01)

                    service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-10T00:00:00.100"}))
                    deadline = time.time() + 3.0
                    while len(self._list_v1_files(log_dir)) < 2 and time.time() < deadline:
                        time.sleep(0.01)
                finally:
                    service.stop()

            self.assertEqual(injected_failure["remaining"], 0)
            v1_files = self._list_v1_files(log_dir)
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(
                [path.name for path in v1_files],
                [
                    "Factory_Integrated_Log_20260309_235959.csv",
                    "Factory_Integrated_Log_20260310_000000.csv",
                ],
            )
            self.assertEqual(
                [path.name for path in v2_files],
                [
                    "Factory_Integrated_Log_v2_20260309_235959.csv",
                    "Factory_Integrated_Log_v2_20260310_000000.csv",
                ],
            )
            self.assertEqual([self._read_csv_rows(path)[1][0] for path in v1_files], ["2026-03-09", "2026-03-10"])
            self.assertEqual([self._read_csv_rows(path)[1][V1_CSV_COLUMNS.index("Time")] for path in v1_files], [
                "23:59:59.900",
                "00:00:00.100",
            ])
            self.assertTrue(v2_files[0].with_suffix(".metadata.json").exists())
            self.assertTrue(v2_files[1].with_suffix(".metadata.json").exists())

    def test_csv_rollover_defers_new_day_row_when_previous_day_flush_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v1_enabled=True,
                csv_v2_enabled=True,
            )
            original_flush = service._flush_buffer
            injected_failure = {"remaining": 1}

            def raise_previous_day_flush_once(writer, handle, buffer):
                rows = list(buffer)
                if injected_failure["remaining"] and rows and rows[0][1].date().isoformat() == "2026-03-09":
                    injected_failure["remaining"] = 0
                    raise OSError("simulated flush failure")
                return original_flush(writer, handle, rows)

            with patch.object(service, "_flush_buffer", side_effect=raise_previous_day_flush_once):
                service.start()
                try:
                    service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-09T23:59:59.900"}))
                    deadline = time.time() + 2.0
                    while service._buffer_size < 1 and time.time() < deadline:
                        time.sleep(0.01)

                    service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-10T00:00:00.100"}))
                    deadline = time.time() + 4.0
                    while len(self._list_v1_files(log_dir)) < 2 and time.time() < deadline:
                        time.sleep(0.01)
                finally:
                    service.stop()

            self.assertEqual(injected_failure["remaining"], 0)
            v1_files = self._list_v1_files(log_dir)
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(
                [path.name for path in v1_files],
                [
                    "Factory_Integrated_Log_20260309_235959.csv",
                    "Factory_Integrated_Log_20260310_000000.csv",
                ],
            )
            self.assertEqual(
                [path.name for path in v2_files],
                [
                    "Factory_Integrated_Log_v2_20260309_235959.csv",
                    "Factory_Integrated_Log_v2_20260310_000000.csv",
                ],
            )
            self.assertEqual([self._read_csv_rows(path)[1][0] for path in v1_files], ["2026-03-09", "2026-03-10"])
            self.assertEqual([self._read_csv_rows(path)[1][V1_CSV_COLUMNS.index("Time")] for path in v1_files], [
                "23:59:59.900",
                "00:00:00.100",
            ])
            self.assertTrue(v2_files[0].with_suffix(".metadata.json").exists())
            self.assertTrue(v2_files[1].with_suffix(".metadata.json").exists())

    def test_csv_shutdown_writes_deferred_new_day_row_after_final_flush_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v1_enabled=True,
                csv_v2_enabled=True,
            )
            original_flush = service._flush_buffer
            injected_failure = {"remaining": 1}

            def fail_previous_day_flush_and_stop_once(writer, handle, buffer):
                rows = list(buffer)
                if injected_failure["remaining"] and rows and rows[0][1].date().isoformat() == "2026-03-09":
                    injected_failure["remaining"] = 0
                    service.running = False
                    return False
                return original_flush(writer, handle, rows)

            with patch.object(service, "_flush_buffer", side_effect=fail_previous_day_flush_and_stop_once):
                service.start()
                service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-09T23:59:59.900"}))
                deadline = time.time() + 2.0
                while service._buffer_size < 1 and time.time() < deadline:
                    time.sleep(0.01)

                service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-10T00:00:00.100"}))
                if service.thread:
                    service.thread.join(timeout=3.0)
                if service.running:
                    service.stop()

            self.assertEqual(injected_failure["remaining"], 0)
            self.assertFalse(service.thread and service.thread.is_alive())
            v1_files = self._list_v1_files(log_dir)
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(
                [path.name for path in v1_files],
                [
                    "Factory_Integrated_Log_20260309_235959.csv",
                    "Factory_Integrated_Log_20260310_000000.csv",
                ],
            )
            self.assertEqual(
                [path.name for path in v2_files],
                [
                    "Factory_Integrated_Log_v2_20260309_235959.csv",
                    "Factory_Integrated_Log_v2_20260310_000000.csv",
                ],
            )
            self.assertEqual([self._read_csv_rows(path)[1][0] for path in v1_files], ["2026-03-09", "2026-03-10"])
            self.assertEqual([self._read_csv_rows(path)[1][V1_CSV_COLUMNS.index("Time")] for path in v1_files], [
                "23:59:59.900",
                "00:00:00.100",
            ])
            self.assertTrue(v2_files[0].with_suffix(".metadata.json").exists())
            self.assertTrue(v2_files[1].with_suffix(".metadata.json").exists())

    def test_v2_sidecar_records_config_operator_verified_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            timestamp = service._parse_timestamp(self.create_data())

            handle, _ = service._open_v2_log_file(
                timestamp.strftime("%Y%m%d_%H%M%S"),
                "Factory_Integrated_Log_v2",
            )
            service._close_file(handle)
            v2_file = next(log_dir.glob("Factory_Integrated_Log_v2_*.csv"))
            metadata = json.loads(v2_file.with_suffix(".metadata.json").read_text(encoding="utf-8"))

        self.assertTrue(metadata["spot_configuration_snapshot"]["config_operator_verified"])

    def test_v2_writer_creates_separate_file_and_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            timestamp = service._parse_timestamp(self.create_data())

            handle, writer = service._open_v2_log_file(timestamp.strftime("%Y%m%d_%H%M%S"), "Factory_Integrated_Log_v2")
            try:
                self.assertIsNotNone(handle)
                self.assertIsNotNone(writer)
            finally:
                service._close_file(handle)

            v2_files = sorted(log_dir.glob("Factory_Integrated_Log_v2_*.csv"))
            self.assertEqual(len(v2_files), 1)
            with v2_files[0].open("r", encoding="utf-8-sig", newline="") as csv_handle:
                rows = list(csv.reader(csv_handle))
            self.assertEqual(rows[0], V2_CSV_COLUMNS)
            self.assertNotIn("ButtLength_HMI_B1880", V2_CSV_COLUMNS)

            metadata = json.loads(v2_files[0].with_suffix(".metadata.json").read_text(encoding="utf-8"))
            self.assertIn("position-specific label", metadata["schema_metadata"]["header_policy"])
            self.assertEqual(metadata["schema_metadata"]["schema_version"], "2.3.0")
            self.assertEqual(metadata["schema_metadata"]["operator_metadata_version"], "1.0.0")
            spot_image_linkage_policy = metadata["schema_metadata"]["spot_image_linkage_policy"]
            self.assertEqual(
                spot_image_linkage_policy["realtime_columns"],
                [
                    "spot_image_capture_id_nearest",
                    "spot_image_path_nearest",
                    "spot_image_link_status_nearest",
                    "spot_image_link_age_ms_nearest",
                ],
            )
            self.assertEqual(
                spot_image_linkage_policy["realtime_semantics"],
                "spot_image_*_nearest columns are best-effort live hints.",
            )
            self.assertEqual(
                spot_image_linkage_policy["authoritative_linkage"],
                "Authoritative linkage is post-hoc join via spot_image_fact.csv and spot_observation_key.",
            )
            self.assertEqual(spot_image_linkage_policy["authoritative_fact_file"], "spot_image_fact.csv")
            self.assertEqual(spot_image_linkage_policy["authoritative_join_key"], "spot_observation_key")
            self.assertEqual(
                spot_image_linkage_policy["realtime_csv_completeness"],
                "best_effort_not_guaranteed",
            )
            spot_config = metadata["spot_configuration_snapshot"]
            self.assertEqual(spot_config["spot_ip"], "10.1.10.50")
            self.assertEqual(spot_config["spot_model_info"], "SPOT+ AL")
            self.assertEqual(spot_config["spot_app_mode"], "App1: AL E")
            self.assertEqual(spot_config["low_signal_threshold_pc"], 2.0)
            self.assertEqual(spot_config["low_signal_comparator"], "lt")
            self.assertFalse(spot_config["low_signal_alarm_enabled"])
            self.assertFalse(spot_config["low_signal_comparator_verified"])
            self.assertFalse(spot_config["peak_picker_enabled"])
            self.assertEqual(spot_config["window_obscuration_pc"], 12.0)
            self.assertEqual(spot_config["focus_mm"], 6071)
            self.assertEqual(spot_config["config_source"], "spot_web_server_screenshot")
            self.assertTrue(spot_config["config_operator_verified"])
            self.assertTrue(spot_config["config_captured_at"].endswith("Z"))
            image_fact_manifest = metadata["spot_image_fact_manifest"]
            self.assertFalse(image_fact_manifest["enabled"])
            self.assertEqual(image_fact_manifest["mode"], "off")
            self.assertEqual(image_fact_manifest["fact_path"], str(log_dir / "spot_image_fact.csv"))
            self.assertEqual(image_fact_manifest["capture_root"], str(log_dir / "spot_images"))
            self.assertEqual(image_fact_manifest["row_count"], 0)
            self.assertIsNone(image_fact_manifest["sha256"])
            self.assertEqual(image_fact_manifest["written"], 0)
            self.assertEqual(image_fact_manifest["dropped"], 0)
            self.assertEqual(image_fact_manifest["failure"], 0)
            self.assertIsNone(image_fact_manifest["last_write_at"])
            self.assertEqual(
                metadata["schema_metadata"]["posthoc_fact_manifests"],
                [
                    "changeover_candidate_resolution_fact_manifest",
                    "process_phase_event_fact_manifest",
                ],
            )
            resolution_fact_manifest = metadata["changeover_candidate_resolution_fact_manifest"]
            self.assertEqual(resolution_fact_manifest["fact_kind"], "changeover_candidate_resolution_fact")
            self.assertEqual(
                resolution_fact_manifest["fact_path"],
                str(log_dir / "changeover_candidate_resolution_fact.csv"),
            )
            self.assertEqual(
                resolution_fact_manifest["required_columns"],
                CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS,
            )
            self.assertEqual(resolution_fact_manifest["row_count"], 0)
            self.assertIsNone(resolution_fact_manifest["sha256"])
            self.assertIsNone(resolution_fact_manifest["source_csv_sha256"])
            self.assertIsNone(resolution_fact_manifest["source_file_id"])
            event_fact_manifest = metadata["process_phase_event_fact_manifest"]
            self.assertEqual(event_fact_manifest["fact_kind"], "process_phase_event_fact")
            self.assertEqual(event_fact_manifest["fact_path"], str(log_dir / "process_phase_event_fact.csv"))
            self.assertEqual(event_fact_manifest["required_columns"], PROCESS_PHASE_EVENT_FACT_COLUMNS)
            self.assertEqual(event_fact_manifest["row_count"], 0)
            self.assertIsNone(event_fact_manifest["sha256"])
            self.assertIsNone(event_fact_manifest["source_csv_sha256"])
            self.assertIsNone(event_fact_manifest["source_file_id"])
            self.assertEqual(
                metadata["schema_metadata"]["position_read_feature_flag"],
                "EXTRUDER.position_read_enabled or POSITION_READ_ENABLED",
            )
            self.assertIn("메인압력", metadata["schema_metadata"]["v1_header_aliases"]["MainPress"])
            self.assertIn("압출종료 위치", metadata["schema_metadata"]["v1_header_aliases"]["EndPos"])

            billet_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "BilletLength"
            ][0]
            self.assertEqual(billet_meta["field_name"], "BilletLength")
            self.assertEqual(billet_meta["source_address"], "D1911")
            self.assertEqual(billet_meta["mapping_status"], "hmi_confirmed")
            self.assertIn("B1880 Float32 LH matches the separate HMI Butt Length", billet_meta["note"])

            butt_meta = [
                item for item in metadata["sensor_metadata"] if item["field_name"] == "ButtLength_HMI_B1880"
            ][0]
            self.assertEqual(butt_meta["physical_meaning"], "HMI 버트 길이")
            self.assertEqual(butt_meta["source_address"], "B1880")
            self.assertEqual(butt_meta["data_type"], "Float32")
            self.assertEqual(butt_meta["word_order"], "LH")
            self.assertEqual(butt_meta["mapping_status"], "hmi_confirmed_separate_field")
            self.assertEqual(butt_meta["semantic_group"], "butt_length")
            self.assertEqual(butt_meta["not_replacement_for"], "BilletLength")
            self.assertEqual(butt_meta["related_v1_field"], "BilletLength")
            self.assertEqual(butt_meta["quality_rule"]["range_10_to_200"], "ok")
            self.assertEqual(butt_meta["quality_rule"]["less_than_or_equal_zero"], "invalid_candidate")
            self.assertIn("must not be treated as v1 BilletLength replacement", butt_meta["notes"])

            endpos_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "EndPos"
            ][0]
            self.assertEqual(endpos_meta["mapping_status"], "hmi_confirmed_setting_value")
            self.assertIn("D0010 / 10.0 is the real-time main ram position", endpos_meta["note"])
            self.assertIn("not the moving actual position", endpos_meta["note"])

            main_ram_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "MainRamPosition_D0010"
            ][0]
            self.assertEqual(main_ram_meta["source_address"], "D0010")
            self.assertEqual(main_ram_meta["plc_address"], "D0010 / 10.0")
            self.assertEqual(main_ram_meta["unit"], "mm")
            self.assertEqual(main_ram_meta["mapping_status"], "hmi_confirmed_actual_position")
            self.assertEqual(main_ram_meta["semantic_group"], "position")
            self.assertEqual(main_ram_meta["read_feature_flag"], "POSITION_READ_ENABLED")

            container_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "ContainerPosition_D0012"
            ][0]
            self.assertEqual(container_meta["source_address"], "D0012")
            self.assertEqual(container_meta["plc_address"], "D0012 / 10.0")
            self.assertEqual(container_meta["unit"], "mm")
            self.assertEqual(container_meta["mapping_status"], "hmi_confirmed_actual_position")
            self.assertEqual(container_meta["semantic_group"], "position")
            self.assertEqual(container_meta["read_feature_flag"], "POSITION_READ_ENABLED")

            product_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "Product_No_operator"
            ][0]
            self.assertEqual(product_meta["field_name"], "product_no")
            self.assertEqual(product_meta["physical_meaning"], "Operator-entered numeric product number")
            self.assertEqual(product_meta["source_system"], "Operator input")
            self.assertEqual(product_meta["mapping_status"], "operator_entered_required")
            self.assertEqual(product_meta["validation_rule"], "1-40 digits only")
            self.assertEqual(product_meta["not_replacement_for"], "%DW PLC address")

            mold_no_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "Mold_No_operator"
            ][0]
            self.assertEqual(mold_no_meta["field_name"], "operator_mold_no")
            self.assertEqual(mold_no_meta["mapping_status"], "operator_entered_required")
            self.assertEqual(mold_no_meta["validation_rule"], "1-32 digits only")
            self.assertEqual(mold_no_meta["not_replacement_for"], "DIE_ID")

            self.assertIn(
                "hmi_confirmed_actual_position",
                metadata["quality_rule_metadata"]["mapping_status_values"],
            )
            self.assertIn(
                "hmi_confirmed_separate_field",
                metadata["quality_rule_metadata"]["mapping_status_values"],
            )
            self.assertIn(
                "operator_entered_required",
                metadata["quality_rule_metadata"]["mapping_status_values"],
            )
            self.assertEqual(
                metadata["operator_metadata"]["required_fields"],
                ["product_no", "operator_mold_no"],
            )

    def test_spot_image_fact_final_manifest_records_closeout_stats_without_mutating_sidecar(self) -> None:
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
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)
            contract = service._get_active_v2_contract()

            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(contract.columns)
                writer.writerow(v2_row)

            service._write_v2_sidecar(v2_path, contract)
            metadata_path = v2_path.with_suffix(".metadata.json")
            initial_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(initial_metadata["spot_image_fact_manifest"]["row_count"], 0)
            self.assertIsNone(initial_metadata["spot_image_fact_manifest"]["sha256"])

            fact_rows, fact_sha = self._write_spot_image_fact_fixture(log_dir / "spot_image_fact.csv", 2)
            final_manifest_path = service.write_spot_image_fact_final_manifest(log_dir)
            final_manifest = json.loads(final_manifest_path.read_text(encoding="utf-8"))
            sidecar_after_closeout = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(final_manifest_path.name, SPOT_IMAGE_FACT_FINAL_MANIFEST_FILENAME)
        self.assertEqual(final_manifest["fact_path"], str(log_dir / "spot_image_fact.csv"))
        self.assertEqual(final_manifest["row_count"], fact_rows)
        self.assertEqual(final_manifest["sha256"], fact_sha)
        self.assertEqual(sidecar_after_closeout["spot_image_fact_manifest"]["row_count"], 0)
        self.assertIsNone(sidecar_after_closeout["spot_image_fact_manifest"]["sha256"])

    def test_shadow_validation_script_accepts_v1_v2_sidecar_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

            v1_path = log_dir / "Factory_Integrated_Log_20260309_072025.csv"
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"

            with v1_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V1_CSV_COLUMNS)
                writer.writerow(v1_row)
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path)

            result = validate_csv_v2_shadow(v1_path, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 0)

    def test_shadow_validation_script_accepts_legacy_2_1_v2_sidecar_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)
            operator_columns = {
                "Product_No_operator",
                "Mold_No_operator",
                "operator_metadata_valid",
                "operator_metadata_missing_fields",
                "operator_metadata_updated_at",
            }
            legacy_columns = [column for column in V2_CSV_COLUMNS if column not in operator_columns]
            legacy_row = [
                value for column, value in zip(V2_CSV_COLUMNS, v2_row) if column not in operator_columns
            ]
            legacy_row[legacy_columns.index("schema_version")] = "2.1.0"
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            metadata_path = v2_path.with_suffix(".metadata.json")

            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(legacy_columns)
                writer.writerow(legacy_row)
            metadata_path.write_text(
                json.dumps(
                    {
                        "schema_metadata": {"schema_version": "2.1.0"},
                        "sensor_metadata": [
                            {
                                "field_name": "EndPos",
                                "mapping_status": "hmi_confirmed_setting_value",
                            },
                            {
                                "field_name": "MainRamPosition_D0010",
                                "mapping_status": "hmi_confirmed_actual_position",
                            },
                            {
                                "field_name": "ContainerPosition_D0012",
                                "mapping_status": "hmi_confirmed_actual_position",
                            },
                            {
                                "field_name": "ButtLength_HMI_B1880",
                                "mapping_status": "hmi_confirmed_separate_field",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = validate_csv_v2_shadow(None, v2_path, metadata_path)

        self.assertEqual(result, 0)

    def test_shadow_validation_script_rejects_invalid_v2_3_shadow_enum_and_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)
            v2_row[V2_CSV_COLUMNS.index("spot_poll_status")] = "parse_error"
            v2_row[V2_CSV_COLUMNS.index("spot_poll_seq")] = "1"
            v2_row[V2_CSV_COLUMNS.index("spot_observation_seq")] = "2"

            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path)

            result = validate_csv_v2_shadow(None, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 1)

    def test_shadow_validation_script_accepts_temperature_origin_current_invariant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            data = self.create_data()
            data.Spot = 448.5
            data.temperature_value_origin = "current_observation"
            data.temperature_status_shadow = "ok"
            data.spot_poll_status = "success"
            data.spot_raw_validity = "valid_temperature"
            data.spot_cache_status = "fresh"
            data.spot_source_freshness = "fresh"
            data.spot_temperature_observed_c = 448.5
            data.spot_last_valid_value_at = "2026-03-09T07:20:24.012Z"
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path)

            result = validate_csv_v2_shadow(None, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 0)

    def test_shadow_validation_script_accepts_portable_spot_image_fact_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "source"
            bundle_dir = Path(tmp) / "bundle"
            log_dir.mkdir()
            bundle_dir.mkdir()

            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v2_enabled=True,
                csv_v2_operational_fields_enabled=True,
            )
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)
            contract = service._get_active_v2_contract()
            columns = list(contract.columns)

            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                writer.writerow(v2_row)

            stale_count, stale_sha = self._write_spot_image_fact_fixture(log_dir / "spot_image_fact.csv", 1)
            service._write_v2_sidecar(v2_path, contract)

            metadata_path = v2_path.with_suffix(".metadata.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            manifest = metadata["spot_image_fact_manifest"]
            manifest["fact_path"] = str(log_dir / "missing_spot_image_fact.csv")
            manifest["row_count"] = stale_count
            manifest["sha256"] = stale_sha
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

            override_fact_path = bundle_dir / "spot_image_fact.csv"
            self._write_spot_image_fact_fixture(override_fact_path, 2)

            strict_result = validate_csv_v2_shadow(None, v2_path, metadata_path)
            output = io.StringIO()
            with redirect_stdout(output):
                override_result = validate_csv_v2_shadow(
                    None,
                    v2_path,
                    metadata_path,
                    spot_image_fact_path=override_fact_path,
                )

        self.assertEqual(strict_result, 1)
        self.assertEqual(override_result, 0)
        output_text = output.getvalue()
        spot_image_summary_lines = [line for line in output_text.splitlines() if line.startswith("spot_image_fact_")]
        self.assertIn("spot_image_fact_validation_source=override", spot_image_summary_lines)
        self.assertIn("spot_image_fact_override_file=spot_image_fact.csv", spot_image_summary_lines)
        self.assertIn("spot_image_fact_row_count_match=false", spot_image_summary_lines)
        self.assertIn("spot_image_fact_sha256_match=false", spot_image_summary_lines)
        self.assertNotIn(str(v2_path), output_text)
        self.assertNotIn(str(metadata_path), output_text)
        self.assertNotIn(str(override_fact_path), output_text)

    def test_shadow_validation_script_accepts_final_spot_image_manifest_with_portable_fact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            bundle_dir = log_dir / "bundle"
            bundle_dir.mkdir()
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v2_enabled=True,
                csv_v2_operational_fields_enabled=True,
            )
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)
            contract = service._get_active_v2_contract()

            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(contract.columns)
                writer.writerow(v2_row)

            service._write_v2_sidecar(v2_path, contract)
            metadata_path = v2_path.with_suffix(".metadata.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            manifest = metadata["spot_image_fact_manifest"]
            manifest["fact_path"] = str(log_dir / "missing_spot_image_fact.csv")
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

            override_fact_path = bundle_dir / "spot_image_fact.csv"
            final_rows, final_sha = self._write_spot_image_fact_fixture(override_fact_path, 2)
            final_manifest = dict(manifest)
            final_manifest["fact_path"] = str(log_dir / "live_spot_image_fact.csv")
            final_manifest["row_count"] = final_rows
            final_manifest["sha256"] = final_sha
            final_manifest_path = bundle_dir / SPOT_IMAGE_FACT_FINAL_MANIFEST_FILENAME
            final_manifest_path.write_text(json.dumps(final_manifest, ensure_ascii=False), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                result = validate_csv_v2_shadow(
                    None,
                    v2_path,
                    metadata_path,
                    spot_image_fact_path=override_fact_path,
                    spot_image_fact_final_manifest_path=final_manifest_path,
                )

        self.assertEqual(result, 0)
        output_text = output.getvalue()
        spot_image_summary_lines = [line for line in output_text.splitlines() if line.startswith("spot_image_fact_")]
        self.assertIn("spot_image_fact_validation_source=final_manifest", spot_image_summary_lines)
        self.assertIn("spot_image_fact_final_manifest_file=spot_image_fact_manifest.final.json", spot_image_summary_lines)
        self.assertIn("spot_image_fact_row_count_match=true", spot_image_summary_lines)
        self.assertIn("spot_image_fact_sha256_match=true", spot_image_summary_lines)
        self.assertNotIn(str(v2_path), output_text)
        self.assertNotIn(str(metadata_path), output_text)
        self.assertNotIn(str(override_fact_path), output_text)
        self.assertNotIn(str(final_manifest_path), output_text)

    def test_shadow_validation_script_rejects_malformed_spot_image_fact_without_crashing(self) -> None:
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
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)
            contract = service._get_active_v2_contract()

            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(contract.columns)
                writer.writerow(v2_row)

            fact_path = log_dir / "spot_image_fact.csv"
            malformed_header = [
                column for column in SPOT_IMAGE_FACT_REQUIRED_COLUMNS if column != "spot_image_link_status"
            ]
            with fact_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(malformed_header)
                writer.writerow(
                    [
                        "capture-1",
                        "spot_images/20260702/capture-1.jpg",
                        "1".zfill(64),
                        "123",
                        "image/jpeg",
                        "100",
                        "spot-service:1",
                    ]
                )
            service._write_v2_sidecar(v2_path, contract)

            output = io.StringIO()
            with redirect_stdout(output):
                result = validate_csv_v2_shadow(None, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 1)
        self.assertIn("spot_image_fact header missing columns: spot_image_link_status", output.getvalue())

    def test_shadow_validation_script_rejects_origin_none_with_legacy_temperature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            data = self.create_data()
            data.temperature_value_origin = "none"
            data.temperature_status_shadow = "no_target"
            data.spot_poll_status = "success"
            data.spot_raw_validity = "verified_no_target"
            data.spot_cache_status = "invalidated"
            data.spot_source_freshness = "fresh"
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path)

            result = validate_csv_v2_shadow(None, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 1)

    def test_shadow_validation_script_rejects_current_origin_temperature_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            data = self.create_data()
            data.temperature_value_origin = "current_observation"
            data.temperature_status_shadow = "ok"
            data.spot_poll_status = "success"
            data.spot_raw_validity = "valid_temperature"
            data.spot_cache_status = "fresh"
            data.spot_source_freshness = "fresh"
            data.spot_temperature_observed_c = 448.5
            data.spot_last_valid_value_at = "2026-03-09T07:20:24.012Z"
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path)

            result = validate_csv_v2_shadow(None, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 1)

    def test_shadow_validation_script_rejects_wrong_v2_3_row_unique_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path)
            metadata_path = v2_path.with_suffix(".metadata.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["schema_metadata"]["row_unique_key"] = ["spot_service_instance_id", "spot_poll_seq"]
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

            result = validate_csv_v2_shadow(None, v2_path, metadata_path)

        self.assertEqual(result, 1)

    def test_shadow_validation_script_accepts_v2_only_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v1_enabled=False, csv_v2_enabled=True)
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"

            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path)

            result = validate_csv_v2_shadow(None, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 0)

    def test_shadow_validation_script_accepts_daily_rollover_file_sets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)

            file_specs = [
                ("20260309_235959", "2026-03-09T23:59:59.900", 1),
                ("20260310_000000", "2026-03-10T00:00:00.100", 2),
            ]
            v1_paths = []
            v2_paths = []
            metadata_paths = []
            for suffix, timestamp_s, sample_seq in file_specs:
                data = self.create_data().model_copy(update={"Time": timestamp_s})
                timestamp = service._parse_timestamp(data)
                v1_row = service._build_row(data, timestamp)
                v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), sample_seq, v1_row)
                v1_path = log_dir / f"Factory_Integrated_Log_{suffix}.csv"
                v2_path = log_dir / f"Factory_Integrated_Log_v2_{suffix}.csv"

                with v1_path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(V1_CSV_COLUMNS)
                    writer.writerow(v1_row)
                with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(V2_CSV_COLUMNS)
                    writer.writerow(v2_row)
                service._write_v2_sidecar(v2_path)
                v1_paths.append(v1_path)
                v2_paths.append(v2_path)
                metadata_paths.append(v2_path.with_suffix(".metadata.json"))

            result = validate_csv_v2_shadow_many(
                list(reversed(v1_paths)),
                list(reversed(v2_paths)),
                list(reversed(metadata_paths)),
            )

        self.assertEqual(result, 0)

    def test_shadow_validation_script_fails_when_required_v1_glob_has_no_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"

            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path)

            result = validate_csv_v2_shadow_many(
                [],
                [v2_path],
                [v2_path.with_suffix(".metadata.json")],
                require_v1=True,
            )

        self.assertEqual(result, 1)



class ProcessSegmentFactInferenceTests(unittest.TestCase):
    def _process_row(
        self,
        sample_seq: int,
        online_state: str,
        *,
        product_no: str = "12345",
        mold_no: str = "123",
        logger_id: str = "logger-1",
        valid_metadata: bool = True,
    ) -> dict[str, str]:
        return {
            "schema_version": "2.3.0",
            "sample_seq": str(sample_seq),
            "timestamp_utc": f"2026-03-09T07:20:{sample_seq:02d}.000Z",
            "logger_service_instance_id": logger_id,
            "Product_No_operator": product_no,
            "Mold_No_operator": mold_no,
            "operator_metadata_valid": "true" if valid_metadata else "false",
            "extruder_process_state_online": online_state,
        }

    def test_infers_billet_change_pause_only_as_separate_posthoc_fact(self) -> None:
        rows = [
            self._process_row(1, "extruding"),
            self._process_row(2, "stopped"),
            self._process_row(3, "extruding"),
        ]

        facts = infer_process_segment_facts(rows, source_file_id="sha256:test")

        self.assertEqual(
            [fact["extruder_process_state_inferred"] for fact in facts],
            ["extruding", "billet_change_pause", "extruding"],
        )
        stopped = facts[1]
        self.assertEqual(stopped["sample_seq_start"], "2")
        self.assertEqual(stopped["sample_seq_end"], "2")
        self.assertEqual(stopped["logger_service_instance_id"], "logger-1")
        self.assertEqual(stopped["inference_rule_version"], "process-segment-inference-v1")
        self.assertEqual(stopped["run_segmentation_rule_version"], "run-segmentation-inferred-v1")
        self.assertTrue(stopped["process_segment_id"].startswith("ps_"))
        self.assertTrue(stopped["run_segment_id_inferred"].startswith("run_"))

    def test_does_not_label_stopped_between_different_contexts_as_billet_change_pause(self) -> None:
        rows = [
            self._process_row(1, "extruding", product_no="11111", mold_no="111"),
            self._process_row(2, "stopped", product_no="11111", mold_no="111"),
            self._process_row(3, "extruding", product_no="22222", mold_no="111"),
        ]

        facts = infer_process_segment_facts(rows, source_file_id="sha256:test")

        self.assertEqual(facts[1]["extruder_process_state_inferred"], "unknown")
        self.assertEqual(facts[1]["inference_reason"], "stopped_without_same_run_future_context")

    def test_promotes_only_candidate_states_in_posthoc_output(self) -> None:
        rows = [
            self._process_row(1, "idle_candidate"),
            self._process_row(2, "changeover_candidate", product_no="54321", mold_no="321"),
        ]

        facts = infer_process_segment_facts(rows, source_file_id="sha256:test")

        self.assertEqual(facts[0]["extruder_process_state_inferred"], "idle")
        self.assertEqual(facts[1]["extruder_process_state_inferred"], "changeover")
        self.assertEqual(facts[0]["inference_confidence"], "0.650")
        self.assertEqual(facts[1]["inference_confidence"], "0.650")

    def test_realtime_v2_columns_do_not_contain_posthoc_segment_fields(self) -> None:
        excluded = {
            "process_segment_id",
            "extruder_process_state_inferred",
            "extruder_process_state_inferred_confidence",
            "process_state_inference_rule_version",
            "run_segment_id_inferred",
            "run_segmentation_confidence",
            "run_segmentation_rule_version",
        }

        for column in excluded:
            self.assertNotIn(column, V2_CSV_COLUMNS)

    def test_script_writes_process_segment_fact_csv_without_mutating_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            input_path = temp_dir / "Factory_Integrated_Log_v2_20260309_072000.csv"
            output_path = temp_dir / "Factory_Integrated_Log_v2_20260309_072000.process_segment_fact.csv"
            rows = [
                self._process_row(1, "extruding"),
                self._process_row(2, "stopped"),
                self._process_row(3, "extruding"),
            ]
            with input_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            original_text = input_path.read_text(encoding="utf-8-sig")

            facts = infer_process_segments_from_csv(input_path, output_path)

            self.assertEqual(input_path.read_text(encoding="utf-8-sig"), original_text)
            self.assertTrue(output_path.exists())
            with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                output_rows = list(csv.DictReader(handle))
            self.assertEqual(output_rows, facts)
            self.assertEqual(list(output_rows[0]), PROCESS_SEGMENT_FACT_COLUMNS)
            self.assertEqual(output_rows[1]["extruder_process_state_inferred"], "billet_change_pause")
            self.assertTrue(output_rows[1]["source_file_id"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
