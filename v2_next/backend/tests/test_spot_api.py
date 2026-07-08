import asyncio
import csv
import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.request import Request as UrlRequest
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.FacilityData.drivers import spot_api
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData.spot_image_fact import SpotImageCaptureWriter

FocusUrlopenTarget = str | UrlRequest


class UrlopenResponse:
    def __init__(self, body: bytes, status_code: int) -> None:
        self.body = body
        self.status_code = status_code

    def __enter__(self) -> "UrlopenResponse":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body

    def getcode(self) -> int:
        return self.status_code


class SpotApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_spot_url: str = str(spot_api.config.SPOT_URL)
        self.original_spot_image_url: str = str(spot_api.config.SPOT_IMAGE_URL)
        self.original_spot_live_image_url: str = str(spot_api.config.SPOT_LIVE_IMAGE_URL)
        self.original_spot_refresh_interval: float = float(spot_api.config.SPOT_REFRESH_INTERVAL)
        self.original_spot_internal_temperature_url: str = str(spot_api.config.SPOT_INTERNAL_TEMPERATURE_URL)
        self.original_spot_focus_url: str = str(spot_api.config.SPOT_FOCUS_URL)
        self.original_spot_focus_step: int = int(spot_api.config.SPOT_FOCUS_STEP)
        self.original_spot_actuator_url: str = str(spot_api.config.SPOT_ACTUATOR_URL)
        self.original_spot_actuator_step: int = int(spot_api.config.SPOT_ACTUATOR_STEP)
        self.original_log_path: Path = Path(spot_api.config.LOG_PATH)
        self.original_spot_image_capture_enabled: bool = bool(spot_api.config.SPOT_IMAGE_CAPTURE_ENABLED)
        self.original_spot_image_capture_mode: str = str(spot_api.config.SPOT_IMAGE_CAPTURE_MODE)
        self.original_spot_image_capture_path: str = str(spot_api.config.SPOT_IMAGE_CAPTURE_PATH)
        self.original_spot_image_capture_min_interval_sec: float = float(
            spot_api.config.SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC
        )
        self.original_spot_image_capture_retention_days: int = int(
            spot_api.config.SPOT_IMAGE_CAPTURE_RETENTION_DAYS
        )
        self.original_spot_image_capture_max_bytes: int = int(spot_api.config.SPOT_IMAGE_CAPTURE_MAX_BYTES)
        self.original_spot_image_capture_link_to_observation: bool = bool(
            spot_api.config.SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION
        )
        self.reset_spot_state()

    def tearDown(self) -> None:
        spot_api.config.SPOT_URL = self.original_spot_url
        spot_api.config.SPOT_IMAGE_URL = self.original_spot_image_url
        spot_api.config.SPOT_LIVE_IMAGE_URL = self.original_spot_live_image_url
        spot_api.config.SPOT_REFRESH_INTERVAL = self.original_spot_refresh_interval
        spot_api.config.SPOT_INTERNAL_TEMPERATURE_URL = self.original_spot_internal_temperature_url
        spot_api.config.SPOT_FOCUS_URL = self.original_spot_focus_url
        spot_api.config.SPOT_FOCUS_STEP = self.original_spot_focus_step
        spot_api.config.SPOT_ACTUATOR_URL = self.original_spot_actuator_url
        spot_api.config.SPOT_ACTUATOR_STEP = self.original_spot_actuator_step
        spot_api.config.LOG_PATH = self.original_log_path
        spot_api.config.SPOT_IMAGE_CAPTURE_ENABLED = self.original_spot_image_capture_enabled
        spot_api.config.SPOT_IMAGE_CAPTURE_MODE = self.original_spot_image_capture_mode
        spot_api.config.SPOT_IMAGE_CAPTURE_PATH = self.original_spot_image_capture_path
        spot_api.config.SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC = self.original_spot_image_capture_min_interval_sec
        spot_api.config.SPOT_IMAGE_CAPTURE_RETENTION_DAYS = self.original_spot_image_capture_retention_days
        spot_api.config.SPOT_IMAGE_CAPTURE_MAX_BYTES = self.original_spot_image_capture_max_bytes
        spot_api.config.SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION = self.original_spot_image_capture_link_to_observation
        self.reset_spot_state()

    def reset_spot_state(self) -> None:
        spot_api._img_cache = {"data": None, "time": 0.0, "temp": 0.0, "temp_time": 0.0}
        spot_api._internal_temp_cache = {"temp": 0.0, "temp_time": 0.0}
        spot_api._img_last_error = 0.0
        spot_api._img_failure_count = 0
        spot_api._img_cache_state = "empty"
        spot_api._img_last_cache_log_at = 0.0
        spot_api._img_last_error_code = None
        spot_api._img_last_error_message = None
        spot_api._img_next_retry_at = None
        spot_api._live_img_cache = {"data": None, "time": 0.0, "url": None}
        spot_api._live_img_last_error = 0.0
        spot_api._live_img_failure_count = 0
        spot_api._live_img_last_error_code = None
        spot_api._live_img_last_error_message = None
        spot_api._live_img_last_url = None
        spot_api._live_img_next_retry_at = None
        spot_api._temp_last_error = 0.0
        spot_api._temp_last_error_code = None
        spot_api._temp_last_error_message = None
        spot_api._temp_last_upstream_status = None
        spot_api._temp_last_url = None
        spot_api._temp_last_success_at = 0.0
        spot_api._internal_temp_last_error = 0.0
        spot_api._internal_temp_last_error_code = None
        spot_api._internal_temp_last_error_message = None
        spot_api._internal_temp_last_upstream_status = None
        spot_api._internal_temp_last_url = None
        spot_api._internal_temp_last_success_at = 0.0
        with spot_api._spot_diagnostics_lock:
            spot_api._spot_diagnostics_snapshot = None
            spot_api._spot_diagnostics_last_error_code = None
            spot_api._spot_diagnostics_last_error_message = None
        spot_api._spot_diagnostics_prefetch_task = None
        with spot_api._spot_temperature_snapshot_lock:
            spot_api._spot_service_instance_id = "test-spot-service-instance"
            spot_api._spot_service_started_at = "2026-06-22T00:00:00Z"
            spot_api._spot_poll_seq = 0
            spot_api._spot_observation_seq = 0
            spot_api._spot_temperature_snapshot = None
            spot_api._spot_last_valid_value_at = None
            spot_api._spot_temperature_cache_suppressed_until_valid = False
        spot_api._reset_spot_image_capture_state_for_tests()

    def configure_image_capture(self, log_path: Path, *, mode: str = "all", max_bytes: int = 2_000_000) -> None:
        spot_api.config.LOG_PATH = log_path
        spot_api.config.SPOT_IMAGE_CAPTURE_ENABLED = True
        spot_api.config.SPOT_IMAGE_CAPTURE_MODE = mode
        spot_api.config.SPOT_IMAGE_CAPTURE_PATH = "spot_images"
        spot_api.config.SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC = 0.0
        spot_api.config.SPOT_IMAGE_CAPTURE_RETENTION_DAYS = 7
        spot_api.config.SPOT_IMAGE_CAPTURE_MAX_BYTES = max_bytes
        spot_api.config.SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION = True

    def read_spot_image_fact_rows(self, log_path: Path) -> list[dict[str, str]]:
        fact_path = log_path / "spot_image_fact.csv"
        if not fact_path.exists():
            return []
        with fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def set_spot_temperature_snapshot(self, **overrides: Any) -> None:
        snapshot: dict[str, Any] = {
            "spot_service_instance_id": "test-spot-service-instance",
            "spot_poll_seq": 7,
            "sample_seq": 70,
            "spot_last_poll_completed_at": "2026-06-29T06:00:00Z",
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_device_status_code": None,
            "spot_diagnostic_evidence_codes": "[]",
            "signalpc": "55.0",
            "alarmstatus": "0",
            "process_phase_candidate": "production_stable",
            "focus_mm": "6071",
            "low_signal_threshold_pc": "2.0",
            "peak_picker_enabled": "False",
        }
        snapshot.update(overrides)
        with spot_api._spot_temperature_snapshot_lock:
            spot_api._spot_temperature_snapshot = snapshot

    def test_spot_temperature_diagnostics_before_first_poll_are_startup_pending(self) -> None:
        diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()

        self.assertEqual(diagnostics["spot_service_instance_id"], "test-spot-service-instance")
        self.assertEqual(diagnostics["spot_poll_seq"], 0)
        self.assertEqual(diagnostics["spot_observation_seq"], 0)
        self.assertEqual(diagnostics["spot_poll_status"], "not_attempted")
        self.assertEqual(diagnostics["spot_raw_validity"], "not_received")
        self.assertEqual(diagnostics["spot_source_freshness"], "unknown")
        self.assertEqual(diagnostics["temperature_status_shadow"], "startup_pending")
        self.assertEqual(diagnostics["temperature_value_origin"], "none")
        self.assertIsNone(diagnostics["spot_snapshot_age_ms"])

    async def test_spot_temperature_refresh_success_publishes_shadow_snapshot(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="448.5", request=request)

        transport = httpx.MockTransport(handler)
        with patch.object(spot_api.time, "monotonic", return_value=12345.5):
            async with httpx.AsyncClient(transport=transport) as client:
                await spot_api._refresh_spot_temperature(client)
            diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()
        snapshot = spot_api.get_spot_temperature_poll_snapshot()

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["_spot_last_poll_completed_monotonic"], 12345.5)
        self.assertEqual(diagnostics["spot_last_poll_completed_monotonic"], 12345.5)
        self.assertEqual(diagnostics["spot_snapshot_age_ms"], 0.0)
        self.assertEqual(diagnostics["spot_poll_seq"], 1)
        self.assertEqual(diagnostics["spot_observation_seq"], 1)
        self.assertEqual(diagnostics["spot_poll_status"], "success")
        self.assertEqual(diagnostics["spot_raw_validity"], "valid_temperature")
        self.assertEqual(diagnostics["spot_source_freshness"], "fresh")
        self.assertEqual(diagnostics["temperature_status_shadow"], "ok")
        self.assertEqual(diagnostics["temperature_value_origin"], "current_observation")
        self.assertEqual(diagnostics["spot_cache_status"], "fresh")
        self.assertEqual(diagnostics["spot_target_state_observed_shadow"], "present")
        self.assertEqual(diagnostics["spot_target_state_observed_source"], "valid_temperature")
        self.assertEqual(diagnostics["spot_temperature_observed_c"], 448.5)
        self.assertEqual(diagnostics["spot_temperature_effective_c"], 448.5)
        self.assertIsNotNone(diagnostics["spot_last_valid_value_at"])
        self.assertIsNotNone(diagnostics["spot_raw_payload_hash"])

    async def test_verified_no_target_invalidates_previous_temperature_cache(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"

        async def success_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="448.5", request=request)

        async def no_target_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="NO_TARGET", request=request)

        with patch.object(spot_api, "_SPOT_VERIFIED_NO_TARGET_VALUES", ("NO_TARGET",)):
            async with httpx.AsyncClient(transport=httpx.MockTransport(success_handler)) as client:
                await spot_api._refresh_spot_temperature(client)
            async with httpx.AsyncClient(transport=httpx.MockTransport(no_target_handler)) as client:
                with self.assertRaises(spot_api.SpotTemperatureFetchError):
                    await spot_api._refresh_spot_temperature(client)

        diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()

        self.assertEqual(diagnostics["spot_poll_seq"], 2)
        self.assertEqual(diagnostics["spot_observation_seq"], 2)
        self.assertEqual(diagnostics["spot_poll_status"], "success")
        self.assertEqual(diagnostics["spot_raw_validity"], "verified_no_target")
        self.assertEqual(diagnostics["temperature_status_shadow"], "no_target")
        self.assertEqual(diagnostics["spot_cache_status"], "invalidated")
        self.assertEqual(diagnostics["temperature_value_origin"], "none")
        self.assertEqual(diagnostics["spot_target_state_observed_shadow"], "absent")
        self.assertEqual(diagnostics["spot_target_state_observed_source"], "verified_device_code")
        self.assertIsNone(diagnostics["spot_temperature_effective_c"])
        self.assertIsNone(diagnostics["spot_last_valid_value_at"])
        self.assertEqual(spot_api._img_cache["temp_time"], 0.0)


    async def test_ametek_under_range_sentinel_publishes_invalid_value_snapshot(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="6553.4\r\n", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(spot_api.SpotTemperatureFetchError) as raised:
                await spot_api._refresh_spot_temperature(client)

        error = raised.exception
        diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()

        self.assertEqual(error.code, "temperature-invalid-sentinel")
        self.assertEqual(error.upstream_status, 200)
        self.assertEqual(diagnostics["spot_poll_status"], "success")
        self.assertEqual(diagnostics["spot_raw_validity"], "invalid_sentinel")
        self.assertEqual(diagnostics["spot_raw_value_text"], "6553.4\r\n")
        self.assertEqual(diagnostics["spot_device_status_code"], "temperature_under_range")
        self.assertIsNone(diagnostics["spot_error_code"])
        self.assertFalse(diagnostics["cache_fallback_allowed"])
        self.assertEqual(diagnostics["temperature_status_shadow"], "invalid_value")
        self.assertEqual(diagnostics["spot_cache_status"], "empty")
        self.assertEqual(diagnostics["temperature_value_origin"], "none")
        self.assertEqual(diagnostics["spot_target_state_observed_shadow"], "unknown")
        self.assertEqual(diagnostics["spot_target_state_observed_source"], "unknown")
        self.assertIsNone(diagnostics["spot_temperature_observed_c"])
        self.assertIsNone(diagnostics["spot_temperature_effective_c"])

    async def test_spot_diagnostics_enrich_under_range_evidence_without_blocking_poll(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/output?p=temperature"
        requests: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            requests.append(url)
            if url == "http://spot.local/output?p=alarmstatus":
                return httpx.Response(200, text="LOW SIGNAL", request=request)
            if url == "http://spot.local/output?p=signalpc":
                return httpx.Response(200, text="3.2", request=request)
            if url == "http://spot.local/output?p=d1temperature":
                return httpx.Response(200, text="345.7", request=request)
            if url == "http://spot.local/output?p=d2temperature":
                return httpx.Response(200, text="319.1", request=request)
            if url == "http://spot.local/output?p=e1out":
                return httpx.Response(200, text="57", request=request)
            if url == "http://spot.local/output?p=e2out":
                return httpx.Response(200, text="53", request=request)
            if url == "http://spot.local/output?p=itemperature":
                return httpx.Response(200, text="41.2", request=request)
            if url == "http://spot.local/output?p=appnumber":
                return httpx.Response(200, text="App1", request=request)
            if url == "http://spot.local/output?p=temperature":
                return httpx.Response(200, text="6553.4", request=request)
            return httpx.Response(404, text="not found", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await spot_api._refresh_spot_diagnostics_safely(client, spot_api._logger)
            with self.assertRaises(spot_api.SpotTemperatureFetchError):
                await spot_api._refresh_spot_temperature(client)

        diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()
        fact = spot_api.get_spot_temperature_poll_snapshot()

        self.assertEqual(diagnostics["diagnostics_capture_status"], "async_enriched")
        self.assertEqual(diagnostics["alarmstatus"], "LOW SIGNAL")
        self.assertEqual(diagnostics["signalpc"], "3.2")
        self.assertEqual(
            diagnostics["spot_diagnostic_evidence_codes"],
            '["alarm_low_signal","signal_at_or_above_configured_threshold"]',
        )
        self.assertEqual(diagnostics["d1temperature"], "345.7")
        self.assertEqual(diagnostics["d2temperature"], "319.1")
        self.assertEqual(diagnostics["e1out"], "57")
        self.assertEqual(diagnostics["e2out"], "53")
        self.assertEqual(diagnostics["itemperature"], "41.2")
        self.assertEqual(diagnostics["appnumber"], "App1")
        self.assertEqual(diagnostics["low_signal_alarm_enabled"], False)
        self.assertEqual(diagnostics["low_signal_threshold_pc"], 2.0)
        self.assertEqual(diagnostics["low_signal_comparator"], "lt")
        self.assertEqual(diagnostics["spot_app_mode"], "App1: AL E")
        self.assertIsNotNone(fact)
        assert fact is not None
        self.assertEqual(fact["diagnostics_capture_status"], "async_enriched")
        self.assertEqual(fact["itemperature"], "41.2")
        self.assertIn("http://spot.local/output?p=alarmstatus", requests)
        self.assertIn("http://spot.local/output?p=signalpc", requests)
        self.assertIn("http://spot.local/output?p=d1temperature", requests)
        self.assertIn("http://spot.local/output?p=d2temperature", requests)
        self.assertIn("http://spot.local/output?p=e1out", requests)
        self.assertIn("http://spot.local/output?p=e2out", requests)
        self.assertIn("http://spot.local/output?p=itemperature", requests)
        self.assertIn("http://spot.local/output?p=appnumber", requests)

    async def test_ametek_over_range_sentinel_uses_invalid_sentinel_error(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="6553.50", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(spot_api.SpotTemperatureFetchError) as raised:
                await spot_api._request_spot_temperature(client, "http://spot.local/temp")

        self.assertEqual(raised.exception.code, "temperature-invalid-sentinel")
        self.assertEqual(raised.exception.upstream_status, 200)
        self.assertIsNotNone(raised.exception.raw_classification)
        assert raised.exception.raw_classification is not None
        self.assertEqual(raised.exception.raw_classification.raw_validity.value, "invalid_sentinel")
        self.assertEqual(raised.exception.raw_classification.device_status_code, "temperature_over_range")

    async def test_spot_temperature_http_error_with_body_publishes_not_evaluated_snapshot(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="busy", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaises(spot_api.SpotTemperatureFetchError):
                await spot_api._refresh_spot_temperature(client)

        diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()

        self.assertEqual(diagnostics["spot_poll_seq"], 1)
        self.assertEqual(diagnostics["spot_observation_seq"], 1)
        self.assertEqual(diagnostics["spot_poll_status"], "http_error")
        self.assertEqual(diagnostics["spot_raw_validity"], "not_evaluated")
        self.assertTrue(diagnostics["cache_fallback_allowed"])
        self.assertEqual(diagnostics["spot_http_status_code"], 503)
        self.assertEqual(diagnostics["spot_response_content_length"], 4)
        self.assertIsNotNone(diagnostics["spot_raw_payload_hash"])
        self.assertEqual(diagnostics["temperature_status_shadow"], "source_error")
        self.assertEqual(diagnostics["spot_cache_status"], "empty")
        self.assertEqual(diagnostics["temperature_value_origin"], "none")
        self.assertIsNone(diagnostics["spot_temperature_observed_c"])
        self.assertIsNone(diagnostics["spot_temperature_effective_c"])

    async def test_stale_success_snapshot_suppresses_ttl_cache(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"
        spot_api.config.SPOT_REFRESH_INTERVAL = 0.5

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="450.0", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await spot_api._refresh_spot_temperature(client)

        stale_epoch = time.time() - 2.0
        stale_monotonic = time.monotonic() - 2.0
        spot_api._img_cache["temp_time"] = stale_epoch
        with spot_api._spot_temperature_snapshot_lock:
            assert spot_api._spot_temperature_snapshot is not None
            spot_api._spot_temperature_snapshot["_spot_last_poll_completed_at_epoch"] = stale_epoch
            spot_api._spot_temperature_snapshot["_spot_last_poll_completed_monotonic"] = stale_monotonic
            spot_api._spot_last_valid_value_at = stale_epoch

        diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()

        self.assertEqual(diagnostics["spot_source_freshness"], "stale")
        self.assertEqual(diagnostics["temperature_status_shadow"], "unknown_missing")
        self.assertEqual(diagnostics["temperature_value_origin"], "none")
        self.assertEqual(diagnostics["spot_cache_status"], "available_not_used")
        self.assertIsNone(diagnostics["spot_temperature_effective_c"])
        self.assertEqual(diagnostics["spot_target_state_observed_shadow"], "unknown")
        self.assertGreater(float(diagnostics["spot_snapshot_age_ms"]), 1500.0)

    async def test_stale_transport_failure_snapshot_reuses_ttl_cache(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"
        spot_api.config.SPOT_REFRESH_INTERVAL = 0.5

        async def success_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="450.0", request=request)

        async def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(success_handler)) as client:
            await spot_api._refresh_spot_temperature(client)
        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
            with self.assertRaises(spot_api.SpotTemperatureFetchError):
                await spot_api._refresh_spot_temperature(client)

        stale_epoch = time.time() - 2.0
        stale_monotonic = time.monotonic() - 2.0
        spot_api._img_cache["temp_time"] = stale_epoch
        with spot_api._spot_temperature_snapshot_lock:
            assert spot_api._spot_temperature_snapshot is not None
            spot_api._spot_temperature_snapshot["_spot_last_poll_completed_at_epoch"] = stale_epoch
            spot_api._spot_temperature_snapshot["_spot_last_poll_completed_monotonic"] = stale_monotonic

        diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()

        self.assertEqual(diagnostics["spot_source_freshness"], "stale")
        self.assertEqual(diagnostics["spot_poll_status"], "timeout")
        self.assertTrue(diagnostics["cache_fallback_allowed"])
        self.assertEqual(diagnostics["temperature_status_shadow"], "ok")
        self.assertEqual(diagnostics["temperature_value_origin"], "cached_observation")
        self.assertEqual(diagnostics["spot_cache_status"], "reused")
        self.assertEqual(diagnostics["spot_temperature_effective_c"], 450.0)
        self.assertEqual(diagnostics["spot_target_state_observed_shadow"], "unknown")

    async def test_invalid_sentinel_suppresses_pre_sentinel_cache_until_next_valid_temperature(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"

        async def valid_500_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="500.0", request=request)

        async def sentinel_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="6553.4", request=request)

        async def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        async def valid_510_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="510.0", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(valid_500_handler)) as client:
            await spot_api._refresh_spot_temperature(client)
        async with httpx.AsyncClient(transport=httpx.MockTransport(sentinel_handler)) as client:
            with self.assertRaises(spot_api.SpotTemperatureFetchError):
                await spot_api._refresh_spot_temperature(client)
        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
            with self.assertRaises(spot_api.SpotTemperatureFetchError):
                await spot_api._refresh_spot_temperature(client)

        diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()

        self.assertEqual(diagnostics["spot_poll_status"], "timeout")
        self.assertEqual(diagnostics["spot_raw_validity"], "not_received")
        self.assertFalse(diagnostics["cache_fallback_allowed"])
        self.assertEqual(diagnostics["temperature_status_shadow"], "source_error")
        self.assertEqual(diagnostics["temperature_value_origin"], "none")
        self.assertEqual(diagnostics["spot_cache_status"], "available_not_used")
        self.assertIsNone(diagnostics["spot_temperature_effective_c"])

        async with httpx.AsyncClient(transport=httpx.MockTransport(valid_510_handler)) as client:
            await spot_api._refresh_spot_temperature(client)
        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
            with self.assertRaises(spot_api.SpotTemperatureFetchError):
                await spot_api._refresh_spot_temperature(client)

        diagnostics = spot_api.get_image_proxy_diagnostics()

        self.assertEqual(diagnostics["spot_poll_status"], "timeout")
        self.assertTrue(diagnostics["cache_fallback_allowed"])
        self.assertEqual(diagnostics["temperature_value_origin"], "cached_observation")
        self.assertEqual(diagnostics["spot_cache_status"], "reused")
        self.assertEqual(diagnostics["spot_temperature_effective_c"], 510.0)

    async def test_temperature_timeout_diagnostics_have_non_empty_message_and_status(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaises(spot_api.SpotTemperatureFetchError) as raised:
                await spot_api._request_spot_temperature(client, "http://spot.local/temp")

        error = raised.exception
        spot_api._record_temperature_error(error.code, str(error), error.temp_url, error.upstream_status)

        diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()

        self.assertEqual(error.code, "temperature-upstream-timeout")
        self.assertIn("ReadTimeout", str(error))
        self.assertEqual(diagnostics["temperature_cache_status"], "error")
        self.assertEqual(diagnostics["temperature_last_error_code"], "temperature-upstream-timeout")
        self.assertTrue(diagnostics["temperature_last_error_message"])
        self.assertEqual(diagnostics["temperature_last_url"], "http://spot.local/temp")

    async def test_temperature_parse_error_includes_body_and_status(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not-a-number", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaises(spot_api.SpotTemperatureFetchError) as raised:
                await spot_api._request_spot_temperature(client, "http://spot.local/temp")

        error = raised.exception

        self.assertEqual(error.code, "temperature-parse-error")
        self.assertEqual(error.upstream_status, 200)
        self.assertIn("not-a-number", str(error))
        self.assertIn("http://spot.local/temp", str(error))

    async def test_internal_temperature_refresh_parses_and_caches_itemperature(self) -> None:
        spot_api.config.SPOT_INTERNAL_TEMPERATURE_URL = "http://spot.local/output?p=itemperature"
        requests: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(str(request.url))
            return httpx.Response(200, text="41.25", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await spot_api._refresh_spot_internal_temperature(client)

        diagnostics: dict[str, Any] = spot_api.get_spot_internal_temperature_diagnostics()

        self.assertEqual(requests, ["http://spot.local/output?p=itemperature"])
        self.assertEqual(spot_api._internal_temp_cache["temp"], 41.25)
        self.assertGreater(float(spot_api._internal_temp_cache["temp_time"]), 0.0)
        self.assertEqual(diagnostics["internal_temperature"], 41.25)
        self.assertEqual(diagnostics["internal_temperature_cache_status"], "ok")
        self.assertEqual(diagnostics["internal_temperature_last_url"], "http://spot.local/output?p=itemperature")

    async def test_image_timeout_diagnostics_include_url_and_error_type(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaises(spot_api.SpotImageFetchError) as raised:
                await spot_api._request_spot_image(client, "http://spot.local/image.jpg")

        error = raised.exception

        self.assertEqual(error.code, "upstream-timeout")
        self.assertIn("http://spot.local/image.jpg", str(error))
        self.assertIn("ReadTimeout", str(error))

    async def test_image_empty_body_diagnostics_include_url_and_status(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaises(spot_api.SpotImageFetchError) as raised:
                await spot_api._request_spot_image(client, "http://spot.local/image.jpg")

        error = raised.exception

        self.assertEqual(error.code, "empty-body")
        self.assertEqual(error.upstream_status, 200)
        self.assertIn("http://spot.local/image.jpg", str(error))

    async def test_image_text_html_response_with_body_is_accepted(self) -> None:
        image_bytes = b"\xff\xd8image-data\xff\xd9"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=image_bytes,
                headers={"Content-Type": "text/html"},
                request=request,
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            data = await spot_api._request_spot_image(client, "http://spot.local/image.jpg")

        self.assertEqual(data, image_bytes)

    async def test_image_html_payload_is_rejected(self) -> None:
        html_body = b"<!doctype html><html><body>not an image</body></html>"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=html_body,
                headers={"Content-Type": "text/html"},
                request=request,
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaises(spot_api.SpotImageFetchError) as raised:
                await spot_api._request_spot_image(client, "http://spot.local/image.ssi")

        error = raised.exception

        self.assertEqual(error.code, "invalid-image-html")
        self.assertEqual(error.upstream_status, 200)
        self.assertIn("content_type=text/html", str(error))
        self.assertIn("not an image", str(error))

    def test_live_image_url_falls_back_to_spot_image_url(self) -> None:
        spot_api.config.SPOT_LIVE_IMAGE_URL = ""
        spot_api.config.SPOT_IMAGE_URL = "http://spot.local/image.jpg"

        self.assertEqual(spot_api._resolve_spot_live_image_url(), "http://spot.local/image.jpg")

    async def test_live_image_fetch_does_not_update_snapshot_cache(self) -> None:
        spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/newjpeg.jpg"
        image_bytes = b"\xff\xd8live-image\xff\xd9"
        request_mock: AsyncMock = AsyncMock(return_value=image_bytes)

        with patch.object(spot_api, "_request_spot_image", request_mock):
            data, meta = await spot_api.fetch_live_image_async()

        self.assertEqual(data, image_bytes)
        self.assertEqual(meta["source"], "upstream")
        self.assertEqual(meta["image_url"], "http://spot.local/newjpeg.jpg")
        self.assertIsNone(spot_api._img_cache["data"])
        self.assertEqual(spot_api._live_img_cache["data"], image_bytes)
        request_mock.assert_awaited_once()

    async def test_live_image_html_payload_is_rejected_and_backed_off(self) -> None:
        spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/image.ssi"
        html_body = b"<!doctype html><html><body><img src='/newjpeg.jpg'></body></html>"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=html_body,
                headers={"Content-Type": "text/html"},
                request=request,
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch.object(spot_api, "_get_http_client", Mock(return_value=client)):
                with self.assertRaises(spot_api.SpotImageFetchError) as raised:
                    await spot_api.fetch_live_image_async()

        error = raised.exception
        diagnostics = spot_api.get_live_image_diagnostics()

        self.assertEqual(error.code, "invalid-image-html")
        self.assertEqual(error.upstream_status, 200)
        self.assertIsNone(spot_api._img_cache["data"])
        self.assertEqual(diagnostics["live_failure_count"], 1)
        self.assertEqual(diagnostics["live_last_error_code"], "invalid-image-html")
        self.assertGreater(float(diagnostics["live_retry_after_sec"]), 0.0)

    async def test_image_missing_extension_fallbacks_to_jpg(self) -> None:
        image_bytes = b"\xff\xd8image-data\xff\xd9"
        requests: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(str(request.url))
            if str(request.url).endswith("/image.jpg"):
                return httpx.Response(
                    200,
                    content=image_bytes,
                    headers={"Content-Type": "image/jpeg"},
                    request=request,
                )
            return httpx.Response(404, text="not found", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            data = await spot_api._request_spot_image(client, "http://spot.local/image")

        self.assertEqual(data, image_bytes)
        self.assertEqual(requests, ["http://spot.local/image", "http://spot.local/image.jpg"])

    async def test_image_jpg_path_fallbacks_to_image(self) -> None:
        image_bytes = b"\xff\xd8alt-image\xff\xd9"
        requests: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(str(request.url))
            if str(request.url).endswith("/image"):
                return httpx.Response(
                    200,
                    content=image_bytes,
                    headers={"Content-Type": "image/jpeg"},
                    request=request,
                )
            return httpx.Response(404, text="not found", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            data = await spot_api._request_spot_image(client, "http://spot.local/image.jpg")

        self.assertEqual(data, image_bytes)
        self.assertEqual(requests, ["http://spot.local/image.jpg", "http://spot.local/image"])

    async def test_image_http_401_is_rejected_with_http_error(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="auth required", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaises(spot_api.SpotImageFetchError) as raised:
                await spot_api._request_spot_image(client, "http://spot.local/image.jpg")

        error = raised.exception

        self.assertEqual(error.code, "upstream-http-error")
        self.assertEqual(error.upstream_status, 401)
        self.assertIn("HTTP 401", str(error))

    async def test_image_http_403_is_rejected_with_http_error(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, text="forbidden", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaises(spot_api.SpotImageFetchError) as raised:
                await spot_api._request_spot_image(client, "http://spot.local/image.jpg")

        error = raised.exception

        self.assertEqual(error.code, "upstream-http-error")
        self.assertEqual(error.upstream_status, 403)
        self.assertIn("HTTP 403", str(error))

    async def test_image_query_string_is_preserved_in_fallback(self) -> None:
        image_bytes = b"\xff\xd8query-image\xff\xd9"
        requests: list[str] = []
        query = "stream=1&quality=high"

        async def handler(request: httpx.Request) -> httpx.Response:
            request_url = str(request.url)
            requests.append(request_url)
            if request_url == f"http://spot.local/image?{query}":
                return httpx.Response(404, text="not found", request=request)
            if request_url == f"http://spot.local/image.jpg?{query}":
                return httpx.Response(
                    200,
                    content=image_bytes,
                    headers={"Content-Type": "image/jpeg"},
                    request=request,
                )
            return httpx.Response(
                500,
                text=f"unexpected path: {request_url}",
                request=request,
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            data = await spot_api._request_spot_image(client, f"http://spot.local/image?{query}")

        self.assertEqual(data, image_bytes)
        self.assertEqual(
            requests,
            [f"http://spot.local/image?{query}", f"http://spot.local/image.jpg?{query}"],
        )

    def test_image_backoff_diagnostics_include_retry_timing(self) -> None:
        spot_api._img_failure_count = 3
        spot_api._record_image_error("upstream-timeout", "timeout")
        spot_api._record_image_backoff(2.0)

        diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()

        self.assertEqual(diagnostics["failure_count"], 3)
        self.assertEqual(diagnostics["current_backoff_sec"], 2.0)
        self.assertIsNotNone(diagnostics["next_retry_at"])
        self.assertIsNotNone(diagnostics["retry_after_sec"])
        self.assertGreater(float(diagnostics["retry_after_sec"]), 0.0)
        self.assertLessEqual(float(diagnostics["retry_after_sec"]), 2.0)

    def test_image_cache_memory_summary_splits_static_and_live_bytes_without_url(self) -> None:
        now = 1_777_660_900.0
        raw_live_url = "http://spot.local/live.jpg?token=secret-token"
        spot_api._img_cache["data"] = b"static-cache"
        spot_api._img_cache["time"] = now - 3.0
        spot_api._img_failure_count = 2
        spot_api._img_next_retry_at = now + 2.0
        spot_api._live_img_cache = {"data": b"live-frame", "time": now - 0.02, "url": raw_live_url}
        spot_api._live_img_last_url = raw_live_url
        spot_api._live_img_failure_count = 1
        spot_api._live_img_next_retry_at = now + 1.0

        with patch.object(spot_api.time, "time", return_value=now):
            summary: dict[str, Any] = spot_api.get_image_cache_memory_summary()

        self.assertEqual(summary["image_bytes"], len(b"static-cache"))
        self.assertEqual(summary["live_image_bytes"], len(b"live-frame"))
        self.assertEqual(summary["total_bytes"], len(b"static-cache") + len(b"live-frame"))
        self.assertEqual(summary["image_age_sec"], 3.0)
        self.assertAlmostEqual(float(summary["live_image_age_sec"]), 0.02)
        self.assertEqual(summary["image_cache_state"], "cache")
        self.assertEqual(summary["live_image_cache_state"], "fresh")
        self.assertEqual(summary["image_failure_count"], 2)
        self.assertEqual(summary["live_image_failure_count"], 1)
        self.assertEqual(summary["image_next_retry_at"], now + 2.0)
        self.assertEqual(summary["live_image_next_retry_at"], now + 1.0)
        self.assertTrue(summary["live_image_url_present"])
        self.assertNotIn(raw_live_url, str(summary))
        self.assertNotIn("secret-token", str(summary))

    def test_spot_live_cache_collector_reports_live_bytes(self) -> None:
        from backend import app as backend_app

        raw_live_url = "http://spot.local/live.jpg?token=secret-token"
        summary: dict[str, Any] = {
            "image_bytes": 12,
            "image_age_sec": 3.0,
            "image_cache_state": "cache",
            "image_failure_count": 2,
            "image_next_retry_at": 1_777_660_902.0,
            "live_image_bytes": 9,
            "live_image_age_sec": 0.02,
            "live_image_cache_state": "fresh",
            "live_image_url_present": True,
            "live_image_failure_count": 1,
            "live_image_next_retry_at": 1_777_660_901.0,
            "total_bytes": 21,
        }

        with patch.object(
            backend_app.spot_control,
            "get_image_cache_memory_summary",
            Mock(return_value=summary),
        ):
            image_cache = backend_app._collect_spot_image_cache()
            live_cache = backend_app._collect_spot_live_cache()
            compatibility_alias = backend_app._collect_spot_cache()

        self.assertIn("spot.image_cache", backend_app.memory_service._collectors)
        self.assertIn("spot.live_cache", backend_app.memory_service._collectors)
        self.assertIn("spot.cache", backend_app.memory_service._collectors)
        self.assertEqual(image_cache["name"], "spot.image_cache")
        self.assertEqual(image_cache["bytes"], 12)
        self.assertEqual(image_cache["exactness"], "exact")
        self.assertIn("fail=2", str(image_cache["note"]))
        self.assertEqual(live_cache["name"], "spot.live_cache")
        self.assertEqual(live_cache["bytes"], 9)
        self.assertEqual(live_cache["exactness"], "exact")
        self.assertIn("url_present=True", str(live_cache["note"]))
        self.assertEqual(compatibility_alias["name"], "spot.cache")
        self.assertEqual(compatibility_alias["bytes"], 21)
        self.assertEqual(compatibility_alias["exactness"], "exact")
        self.assertIn("split=spot.image_cache,spot.live_cache", str(compatibility_alias["note"]))
        self.assertNotIn(raw_live_url, str([image_cache, live_cache, compatibility_alias]))
        self.assertNotIn("secret-token", str([image_cache, live_cache, compatibility_alias]))

    async def test_cold_cache_backoff_fast_fails_without_upstream_call(self) -> None:
        spot_api.config.SPOT_IMAGE_URL = "http://spot.local/image.jpg"
        spot_api._img_failure_count = 1
        spot_api._record_image_error("upstream-timeout", "timeout")
        spot_api._record_image_backoff(2.0)
        request_mock: AsyncMock = AsyncMock(return_value=b"unexpected")

        with patch.object(spot_api, "_request_spot_image", request_mock):
            with self.assertRaises(spot_api.SpotImageBackoffError) as raised:
                await spot_api.fetch_image_async()

        error = raised.exception

        self.assertEqual(error.code, "retry-backoff-active")
        self.assertEqual(error.image_url, "http://spot.local/image.jpg")
        self.assertIsNone(error.upstream_status)
        self.assertGreater(error.retry_after_sec, 0.0)
        request_mock.assert_not_awaited()

    async def test_cold_cache_fetch_failure_sets_backoff_for_next_request(self) -> None:
        spot_api.config.SPOT_IMAGE_URL = "http://spot.local/image.jpg"
        image_error = spot_api.SpotImageFetchError(
            "upstream-timeout",
            "SPOT image upstream timed out; url=http://spot.local/image.jpg",
            image_url="http://spot.local/image.jpg",
            upstream_status=None,
        )
        request_mock: AsyncMock = AsyncMock(side_effect=[image_error, b"unexpected"])

        with patch.object(spot_api, "_request_spot_image", request_mock):
            with self.assertRaises(spot_api.SpotImageFetchError):
                await spot_api.fetch_image_async()

            diagnostics = spot_api.get_image_proxy_diagnostics()

            with self.assertRaises(spot_api.SpotImageBackoffError):
                await spot_api.fetch_image_async()

        self.assertEqual(diagnostics["failure_count"], 1)
        self.assertEqual(diagnostics["cache_status"], "empty")
        self.assertEqual(diagnostics["proxy_state"], "backoff")
        self.assertGreater(float(diagnostics["retry_after_sec"]), 0.0)
        self.assertEqual(request_mock.await_count, 1)

    async def test_cached_image_backoff_still_returns_cache_without_upstream_call(self) -> None:
        spot_api.config.SPOT_IMAGE_URL = "http://spot.local/image.jpg"
        spot_api._img_cache["data"] = b"cached-image"
        spot_api._img_cache["time"] = time.time()
        spot_api._img_failure_count = 2
        spot_api._record_image_error("upstream-timeout", "timeout")
        spot_api._record_image_backoff(2.0)
        request_mock: AsyncMock = AsyncMock(return_value=b"unexpected")

        with patch.object(spot_api, "_request_spot_image", request_mock):
            data, meta = await spot_api.fetch_image_async()

        self.assertEqual(data, b"cached-image")
        self.assertEqual(meta["status"], "ok")
        self.assertEqual(meta["source"], "cache")
        self.assertEqual(meta["cache_status"], "fresh")
        self.assertEqual(meta["proxy_state"], "backoff")
        self.assertGreater(float(meta["retry_after_sec"]), 0.0)
        request_mock.assert_not_awaited()

    async def test_stale_cached_image_backoff_still_returns_cache_without_upstream_call(self) -> None:
        spot_api.config.SPOT_IMAGE_URL = "http://spot.local/image.jpg"
        spot_api.config.SPOT_REFRESH_INTERVAL = 1.0
        spot_api._img_cache["data"] = b"stale-image"
        spot_api._img_cache["time"] = time.time() - 20.0
        spot_api._img_failure_count = 2
        spot_api._record_image_error("upstream-timeout", "timeout")
        spot_api._record_image_backoff(2.0)
        request_mock: AsyncMock = AsyncMock(return_value=b"unexpected")

        with patch.object(spot_api, "_request_spot_image", request_mock):
            data, meta = await spot_api.fetch_image_async()

        self.assertEqual(data, b"stale-image")
        self.assertEqual(meta["status"], "stale")
        self.assertEqual(meta["source"], "stale")
        self.assertEqual(meta["cache_status"], "stale")
        self.assertEqual(meta["proxy_state"], "backoff")
        self.assertGreater(float(meta["retry_after_sec"]), 0.0)
        request_mock.assert_not_awaited()

    async def test_cold_cache_backoff_rechecked_after_lock_wait(self) -> None:
        spot_api.config.SPOT_IMAGE_URL = "http://spot.local/image.jpg"
        lock_entered = asyncio.Event()
        release_lock = asyncio.Event()
        request_mock: AsyncMock = AsyncMock(return_value=b"unexpected")

        @asynccontextmanager
        async def delayed_fetch_lock() -> AsyncIterator[None]:
            lock_entered.set()
            await release_lock.wait()
            yield

        with (
            patch.object(spot_api, "_img_fetch_lock", delayed_fetch_lock()),
            patch.object(spot_api, "_request_spot_image", request_mock),
        ):
            fetch_task = asyncio.create_task(spot_api.fetch_image_async())
            await lock_entered.wait()
            spot_api._img_failure_count = 1
            spot_api._record_image_error("upstream-timeout", "timeout")
            spot_api._record_image_backoff(2.0)
            release_lock.set()

            with self.assertRaises(spot_api.SpotImageBackoffError):
                await fetch_task

        request_mock.assert_not_awaited()

    async def test_prefetch_payload_rejection_uses_loop_pacing_without_backoff(self) -> None:
        spot_api.config.SPOT_IMAGE_URL = "http://spot.local/image.jpg"
        spot_api.config.SPOT_URL = ""
        spot_api.config.SPOT_INTERNAL_TEMPERATURE_URL = ""
        spot_api.config.SPOT_REFRESH_INTERVAL = 1.25
        image_error = spot_api.SpotImageFetchError(
            "invalid-image-html",
            "SPOT image upstream returned HTML instead of image bytes; url=http://spot.local/image.jpg",
            image_url="http://spot.local/image.jpg",
            upstream_status=200,
        )
        request_mock: AsyncMock = AsyncMock(side_effect=image_error)
        sleep_delays: list[float] = []

        async def sleep_once(delay: float) -> None:
            sleep_delays.append(delay)
            spot_api._prefetch_running = False

        with (
            patch.object(spot_api, "_get_http_client", Mock(return_value=object())),
            patch.object(spot_api, "_request_spot_image", request_mock),
            patch.object(spot_api.asyncio, "sleep", AsyncMock(side_effect=sleep_once)),
        ):
            await spot_api._prefetch_loop()

        self.assertEqual(request_mock.await_count, 1)
        self.assertEqual(sleep_delays, [1.25])
        self.assertEqual(spot_api._img_failure_count, 0)
        self.assertIsNone(spot_api._img_last_error_code)
        self.assertIsNone(spot_api._img_next_retry_at)

    async def test_prefetch_fetch_error_sleeps_backoff_without_extra_interval(self) -> None:
        spot_api.config.SPOT_IMAGE_URL = "http://spot.local/image.jpg"
        spot_api.config.SPOT_URL = ""
        spot_api.config.SPOT_INTERNAL_TEMPERATURE_URL = ""
        spot_api.config.SPOT_REFRESH_INTERVAL = 1.25
        image_error = spot_api.SpotImageFetchError(
            "upstream-timeout",
            "SPOT image upstream timed out; url=http://spot.local/image.jpg",
            image_url="http://spot.local/image.jpg",
            upstream_status=None,
        )
        request_mock: AsyncMock = AsyncMock(side_effect=image_error)
        sleep_delays: list[float] = []

        async def sleep_once(delay: float) -> None:
            sleep_delays.append(delay)
            spot_api._prefetch_running = False

        with (
            patch.object(spot_api, "_get_http_client", Mock(return_value=object())),
            patch.object(spot_api, "_request_spot_image", request_mock),
            patch.object(spot_api.asyncio, "sleep", AsyncMock(side_effect=sleep_once)),
        ):
            await spot_api._prefetch_loop()

        self.assertEqual(request_mock.await_count, 1)
        self.assertEqual(spot_api._img_failure_count, 1)
        self.assertEqual(sleep_delays, [spot_api._current_backoff_sec()])
        self.assertEqual(spot_api._img_last_error_code, "upstream-timeout")
        self.assertIsNotNone(spot_api._img_next_retry_at)

    async def test_stale_cache_diagnostics_include_policy_threshold(self) -> None:
        spot_api.config.SPOT_REFRESH_INTERVAL = 3.0
        spot_api._img_cache["data"] = b"image-data"
        spot_api._img_cache["time"] = time.time() - 20.0

        data, meta = await spot_api.fetch_image_async()
        diagnostics: dict[str, Any] = spot_api.get_image_proxy_diagnostics()

        self.assertEqual(data, b"image-data")
        self.assertEqual(meta["status"], "stale")
        self.assertEqual(meta["source"], "stale")
        self.assertTrue(diagnostics["has_cached_image"])
        self.assertGreaterEqual(float(diagnostics["cache_age_sec"]), float(diagnostics["max_stale_age_sec"]))
        self.assertEqual(diagnostics["max_stale_age_sec"], 15.0)

    async def test_proxy_image_response_includes_cache_metadata_headers(self) -> None:
        from backend import app as backend_app

        fetch_mock: AsyncMock = AsyncMock(
            return_value=(
                b"image-data",
                {
                    "status": "ok",
                    "source": "cache",
                    "captured_at": 1_714_567_890.123,
                    "age_sec": 0.333,
                    "cache_status": "fresh",
                    "proxy_state": "backoff",
                    "failure_count": 2,
                    "last_error_code": "upstream-timeout",
                    "max_stale_age_sec": 15.0,
                    "retry_after_sec": 1.2345,
                },
            )
        )
        record_mock: Mock = Mock()

        with (
            patch.object(backend_app.spot_control, "fetch_image_async", fetch_mock),
            patch.object(backend_app.observability_service, "record_spot_proxy_result", record_mock),
        ):
            response = await backend_app.proxy_spot_image()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b"image-data")
        self.assertEqual(response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(response.headers["X-Spot-Image-At"], "1714567890123")
        self.assertEqual(response.headers["X-Spot-Image-Age"], "0.333")
        self.assertEqual(response.headers["X-Spot-Image-Status"], "ok")
        self.assertEqual(response.headers["X-Spot-Cache-Status"], "fresh")
        self.assertEqual(response.headers["X-Spot-Proxy-State"], "backoff")
        self.assertEqual(response.headers["X-Spot-Image-Source"], "cache")
        self.assertEqual(response.headers["X-Spot-Failure-Count"], "2")
        self.assertEqual(response.headers["X-Spot-Last-Error-Code"], "upstream-timeout")
        self.assertEqual(response.headers["X-Spot-Max-Stale-Age"], "15.000")
        self.assertEqual(response.headers["Retry-After"], "2")
        self.assertEqual(response.headers["X-Spot-Retry-After-Ms"], "1235")
        record_mock.assert_called_once_with(200, 0.333, False)

    async def test_proxy_image_response_includes_internal_temperature_headers_from_cache(self) -> None:
        from backend import app as backend_app

        measured_at = time.time()
        spot_api._internal_temp_cache = {"temp": 41.25, "temp_time": measured_at}
        fetch_mock: AsyncMock = AsyncMock(
            return_value=(
                b"image-data",
                {
                    "status": "ok",
                    "source": "cache",
                    "captured_at": measured_at,
                    "age_sec": 0.333,
                    "cache_status": "fresh",
                    "proxy_state": "ok",
                    "failure_count": 0,
                    "last_error_code": None,
                    "max_stale_age_sec": 15.0,
                    "retry_after_sec": None,
                },
            )
        )
        record_mock: Mock = Mock()

        with (
            patch.object(backend_app.spot_control, "fetch_image_async", fetch_mock),
            patch.object(backend_app.observability_service, "record_spot_proxy_result", record_mock),
        ):
            response = await backend_app.proxy_spot_image()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Spot-Internal-Temperature"], "41.250")
        self.assertEqual(response.headers["X-Spot-Internal-Temperature-At"], str(int(measured_at * 1000)))
        self.assertEqual(response.headers["X-Spot-Internal-Temperature-Status"], "ok")

    async def test_proxy_image_response_records_stale_metadata(self) -> None:
        from backend import app as backend_app

        fetch_mock: AsyncMock = AsyncMock(
            return_value=(
                b"stale-image-data",
                {
                    "status": "stale",
                    "source": "stale",
                    "captured_at": 1_714_567_000.0,
                    "age_sec": 15.5,
                    "cache_status": "stale",
                    "proxy_state": "ok",
                    "failure_count": 0,
                    "last_error_code": None,
                    "max_stale_age_sec": 15.0,
                    "retry_after_sec": None,
                },
            )
        )
        record_mock: Mock = Mock()

        with (
            patch.object(backend_app.spot_control, "fetch_image_async", fetch_mock),
            patch.object(backend_app.observability_service, "record_spot_proxy_result", record_mock),
        ):
            response = await backend_app.proxy_spot_image()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Spot-Image-Age"], "15.500")
        self.assertEqual(response.headers["X-Spot-Image-Status"], "stale")
        self.assertEqual(response.headers["X-Spot-Cache-Status"], "stale")
        self.assertEqual(response.headers["X-Spot-Proxy-State"], "ok")
        self.assertEqual(response.headers["X-Spot-Image-Source"], "stale")
        self.assertEqual(response.headers["X-Spot-Failure-Count"], "0")
        self.assertEqual(response.headers["X-Spot-Max-Stale-Age"], "15.000")
        self.assertNotIn("X-Spot-Retry-After-Ms", response.headers)
        record_mock.assert_called_once_with(200, 15.5, True)

    async def test_proxy_image_response_ignores_boolean_retry_after_metadata(self) -> None:
        from backend import app as backend_app

        fetch_mock: AsyncMock = AsyncMock(
            return_value=(
                b"image-data",
                {
                    "status": "ok",
                    "source": "cache",
                    "captured_at": 1_714_567_890.123,
                    "age_sec": 0.333,
                    "cache_status": "fresh",
                    "proxy_state": "ok",
                    "failure_count": 0,
                    "last_error_code": None,
                    "max_stale_age_sec": 15.0,
                    "retry_after_sec": True,
                },
            )
        )

        with patch.object(backend_app.spot_control, "fetch_image_async", fetch_mock):
            response = await backend_app.proxy_spot_image()

        self.assertNotIn("Retry-After", response.headers)
        self.assertNotIn("X-Spot-Retry-After-Ms", response.headers)

    async def test_proxy_image_response_ignores_non_finite_retry_after_metadata(self) -> None:
        from backend import app as backend_app

        for retry_after_sec in [float("nan"), float("inf")]:
            fetch_mock: AsyncMock = AsyncMock(
                return_value=(
                    b"image-data",
                    {
                        "status": "ok",
                        "source": "cache",
                        "captured_at": 1_714_567_890.123,
                        "age_sec": 0.333,
                        "cache_status": "fresh",
                        "proxy_state": "ok",
                        "failure_count": 0,
                        "last_error_code": None,
                        "max_stale_age_sec": 15.0,
                        "retry_after_sec": retry_after_sec,
                    },
                )
            )

            with self.subTest(retry_after_sec=retry_after_sec):
                with patch.object(backend_app.spot_control, "fetch_image_async", fetch_mock):
                    response = await backend_app.proxy_spot_image()

                self.assertNotIn("Retry-After", response.headers)
                self.assertNotIn("X-Spot-Retry-After-Ms", response.headers)

    async def test_proxy_image_fetch_error_includes_diagnostics_payload(self) -> None:
        from backend import app as backend_app

        image_error = spot_api.SpotImageFetchError(
            "upstream-timeout",
            "SPOT image upstream timed out; url=http://spot.local/image.jpg; error_type=ReadTimeout; error=ReadTimeout",
            image_url="http://spot.local/image.jpg",
            upstream_status=None,
        )
        diagnostics: dict[str, Any] = {
            "cache_state": "empty",
            "cache_status": "empty",
            "proxy_state": "backoff",
            "failure_count": 1,
            "last_error_code": "upstream-timeout",
            "retry_after_sec": 2.001,
        }
        fetch_mock: AsyncMock = AsyncMock(side_effect=image_error)
        diagnostics_mock: Mock = Mock(return_value=diagnostics)
        record_mock: Mock = Mock()

        with (
            patch.object(backend_app.spot_control, "fetch_image_async", fetch_mock),
            patch.object(backend_app.spot_control, "get_image_proxy_diagnostics", diagnostics_mock),
            patch.object(backend_app.observability_service, "record_error", record_mock),
        ):
            with self.assertRaises(HTTPException) as raised:
                await backend_app.proxy_spot_image()

        exception = raised.exception
        detail: dict[str, Any] = exception.detail

        self.assertEqual(exception.status_code, 502)
        self.assertEqual(detail["code"], "upstream-timeout")
        self.assertEqual(detail["upstream_status"], None)
        self.assertEqual(detail["image_url"], "http://spot.local/image.jpg")
        self.assertEqual(detail["diagnostics"], diagnostics)
        self.assertEqual(exception.headers, {"Retry-After": "3", "X-Spot-Retry-After-Ms": "2001"})
        record_mock.assert_called_once()
        _, record_kwargs = record_mock.call_args
        self.assertEqual(record_kwargs["path"], "/api/spot/proxy_image")
        self.assertEqual(record_kwargs["status_code"], 502)
        self.assertEqual(record_kwargs["error_type"], "upstream-timeout")
        self.assertNotIn("spot.local", record_kwargs["detail"])
        self.assertNotIn("diagnostics", record_kwargs["detail"])

    async def test_proxy_image_backoff_error_returns_503_with_retry_headers(self) -> None:
        from backend import app as backend_app

        image_error = spot_api.SpotImageBackoffError("http://spot.local/image.jpg", 2.001)
        diagnostics: dict[str, Any] = {
            "cache_state": "empty",
            "cache_status": "empty",
            "proxy_state": "backoff",
            "failure_count": 1,
            "last_error_code": "upstream-timeout",
            "retry_after_sec": 1.0,
        }
        fetch_mock: AsyncMock = AsyncMock(side_effect=image_error)
        diagnostics_mock: Mock = Mock(return_value=diagnostics)

        with (
            patch.object(backend_app.spot_control, "fetch_image_async", fetch_mock),
            patch.object(backend_app.spot_control, "get_image_proxy_diagnostics", diagnostics_mock),
            patch.object(backend_app.observability_service, "record_error", Mock()) as record_mock,
        ):
            with self.assertRaises(HTTPException) as raised:
                await backend_app.proxy_spot_image()

        exception = raised.exception
        detail: dict[str, Any] = exception.detail

        self.assertEqual(exception.status_code, 503)
        self.assertEqual(detail["code"], "retry-backoff-active")
        self.assertIsNone(detail["upstream_status"])
        self.assertEqual(detail["image_url"], "http://spot.local/image.jpg")
        self.assertEqual(detail["diagnostics"]["cache_status"], "empty")
        self.assertEqual(detail["diagnostics"]["proxy_state"], "backoff")
        self.assertEqual(detail["diagnostics"]["retry_after_sec"], 2.001)
        self.assertEqual(exception.headers, {"Retry-After": "3", "X-Spot-Retry-After-Ms": "2001"})
        record_mock.assert_called_once()
        _, record_kwargs = record_mock.call_args
        self.assertEqual(record_kwargs["path"], "/api/spot/proxy_image")
        self.assertEqual(record_kwargs["status_code"], 503)
        self.assertEqual(record_kwargs["error_type"], "retry-backoff-active")
        self.assertNotIn("spot.local", record_kwargs["detail"])
        self.assertNotIn("diagnostics", record_kwargs["detail"])

    async def test_proxy_image_payload_rejection_response_includes_payload_rejection_header(self) -> None:
        from backend import app as backend_app

        image_error = spot_api.SpotImageFetchError(
            "invalid-image-html",
            "SPOT image upstream returned HTML instead of image bytes; url=http://spot.local/image.jpg; status_code=200; content_type=text/html; body=<!doctype html><html><body>not an image</body></html>",
            image_url="http://spot.local/image.jpg",
            upstream_status=200,
        )
        diagnostics: dict[str, Any] = {
            "cache_state": "empty",
            "cache_status": "empty",
            "proxy_state": "error",
            "failure_count": 1,
            "last_error_code": "invalid-image-html",
            "retry_after_sec": 2.001,
        }
        fetch_mock: AsyncMock = AsyncMock(side_effect=image_error)
        diagnostics_mock: Mock = Mock(return_value=diagnostics)
        record_mock: Mock = Mock()

        with (
            patch.object(backend_app.spot_control, "fetch_image_async", fetch_mock),
            patch.object(backend_app.spot_control, "get_image_proxy_diagnostics", diagnostics_mock),
            patch.object(backend_app.observability_service, "record_error", record_mock),
        ):
            with self.assertRaises(HTTPException) as raised:
                await backend_app.proxy_spot_image()

        exception = raised.exception
        detail: dict[str, Any] = exception.detail

        self.assertEqual(exception.status_code, 502)
        self.assertEqual(detail["code"], "invalid-image-html")
        self.assertEqual(exception.headers.get("X-Spot-Payload-Rejection"), "1")
        self.assertEqual(exception.headers.get("Retry-After"), "3")
        self.assertEqual(exception.headers.get("X-Spot-Retry-After-Ms"), "2001")
        record_mock.assert_not_called()

    def test_proxy_image_payload_rejection_not_counted_as_request_error(self) -> None:
        from backend import app as backend_app

        image_error = spot_api.SpotImageFetchError(
            "invalid-image-payload",
            "SPOT image upstream returned invalid payload; url=http://spot.local/image.jpg; status_code=200; content_type=application/octet-stream",
            image_url="http://spot.local/image.jpg",
            upstream_status=200,
        )
        diagnostics: dict[str, Any] = {
            "cache_state": "empty",
            "cache_status": "empty",
            "proxy_state": "error",
            "failure_count": 1,
            "last_error_code": "invalid-image-payload",
            "retry_after_sec": 2.001,
        }

        original_total_requests = backend_app._stats_total_requests
        original_error_count = backend_app._stats_error_count

        with (
            patch.object(backend_app.spot_control, "fetch_image_async", AsyncMock(side_effect=image_error)),
            patch.object(backend_app.spot_control, "get_image_proxy_diagnostics", Mock(return_value=diagnostics)),
            patch.object(backend_app.observability_service, "record_error", Mock()),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.get("/api/spot/proxy_image")
            finally:
                client.close()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.headers.get("X-Spot-Payload-Rejection"), "1")
        self.assertEqual(backend_app._stats_total_requests, original_total_requests + 1)
        self.assertEqual(backend_app._stats_error_count, original_error_count)
        self.assertEqual(backend_app._stats_last_status, 502)

    async def test_request_stats_call_next_exception_keeps_original_error_and_counts_500(self) -> None:
        from backend import app as backend_app
        from starlette.requests import Request as StarletteRequest

        request = StarletteRequest(
            {
                "type": "http",
                "method": "GET",
                "path": "/boom",
                "headers": [],
                "client": ("testclient", 50000),
                "scheme": "http",
                "server": ("testserver", 80),
                "query_string": b"",
            }
        )
        original_total_requests = backend_app._stats_total_requests
        original_error_count = backend_app._stats_error_count

        async def raise_runtime_error(_: object) -> None:
            raise RuntimeError("boom")

        with self.assertRaisesRegex(RuntimeError, "boom"):
            await backend_app.record_request_stats(request, raise_runtime_error)

        self.assertEqual(backend_app._stats_total_requests, original_total_requests + 1)
        self.assertEqual(backend_app._stats_error_count, original_error_count + 1)
        self.assertEqual(backend_app._stats_last_status, 500)

    async def test_request_stats_records_generic_api_5xx_route_status_and_type(self) -> None:
        from backend import app as backend_app
        from starlette.requests import Request as StarletteRequest
        from starlette.responses import Response as StarletteResponse

        request = StarletteRequest(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/memory/export/open-file",
                "headers": [],
                "client": ("testclient", 50000),
                "scheme": "http",
                "server": ("testserver", 80),
                "query_string": b"",
            }
        )
        record_mock: Mock = Mock()

        async def return_service_unavailable(_: object) -> StarletteResponse:
            return StarletteResponse(status_code=503)

        with patch.object(backend_app.observability_service, "record_error", record_mock):
            response = await backend_app.record_request_stats(request, return_service_unavailable)

        self.assertEqual(response.status_code, 503)
        record_mock.assert_called_once_with(
            "api",
            "HTTP 503",
            path="/api/memory/export/open-file",
            status_code=503,
            error_type="http_5xx",
        )

    async def test_proxy_image_forbidden_and_unauthorized_are_counted_as_request_errors(self) -> None:
        from backend import app as backend_app

        for status in [401, 403]:
            with self.subTest(status=status):
                image_error = spot_api.SpotImageFetchError(
                    "upstream-http-error",
                    f"SPOT image upstream returned HTTP {status}; url=http://spot.local/image.jpg; body=denied",
                    image_url="http://spot.local/image.jpg",
                    upstream_status=status,
                )
                diagnostics: dict[str, Any] = {
                    "cache_state": "error",
                    "cache_status": "empty",
                    "proxy_state": "error",
                    "failure_count": 1,
                    "last_error_code": "upstream-http-error",
                    "retry_after_sec": 1.001,
                }

                original_total_requests = backend_app._stats_total_requests
                original_error_count = backend_app._stats_error_count

                with (
                    patch.object(
                        backend_app.spot_control,
                        "fetch_image_async",
                        AsyncMock(side_effect=image_error),
                    ),
                    patch.object(
                        backend_app.spot_control,
                        "get_image_proxy_diagnostics",
                        Mock(return_value=diagnostics),
                    ),
                    patch.object(backend_app.observability_service, "record_error", Mock()),
                ):
                    client = TestClient(backend_app.app, raise_server_exceptions=False)
                    try:
                        response = client.get("/api/spot/proxy_image")
                    finally:
                        client.close()

                self.assertEqual(response.status_code, 502)
                detail: dict[str, Any] = response.json()["detail"]
                self.assertEqual(detail["code"], "upstream-http-error")
                self.assertEqual(detail["upstream_status"], status)
                self.assertIsNone(response.headers.get("X-Spot-Payload-Rejection"))
                self.assertEqual(backend_app._stats_total_requests, original_total_requests + 1)
                self.assertEqual(backend_app._stats_error_count, original_error_count + 1)
                self.assertEqual(backend_app._stats_last_status, 502)

    def test_stats_response_includes_performance_contract_version_and_thresholds(self) -> None:
        from backend import app as backend_app

        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.get("/stats")
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["performance_contract_version"], "1.0")
        self.assertEqual(payload["thresholds"]["operational"]["health_latency_ms"]["target"], 50)
        self.assertEqual(payload["thresholds"]["regression_budget"]["timing_warning_ratio"], 1.2)
        self.assertEqual(payload["thresholds"]["resource_growth"]["minimum_sample_count"], 48)
        self.assertIn("total_requests", payload)
        self.assertIn("avg_latency_ms", payload)
        self.assertIn("error_count", payload)
        self.assertIn("polling", payload)

    def test_spot_live_image_stats_include_success_failure_stale_and_age(self) -> None:
        from backend.Observability.service import ObservabilityService

        service = ObservabilityService(window_sec=60.0, max_requests=100, max_errors=20)

        service.record_request("/api/spot/live_image", 200, 5.0, "client-a")
        service.record_spot_live_image_result(200, 0.25, False)
        service.record_request("/api/spot/live_image", 200, 7.0, "client-b")
        service.record_spot_live_image_result(200, 0.75, True)
        service.record_request("/api/spot/live_image", 503, 9.0, "client-b")

        live_stats = service.get_stats()["polling"]["paths"]["/api/spot/live_image"]

        self.assertEqual(live_stats["count"], 3)
        self.assertEqual(live_stats["success_count"], 2)
        self.assertEqual(live_stats["failure_count"], 1)
        self.assertEqual(live_stats["http_5xx_count"], 1)
        self.assertEqual(live_stats["stale_count"], 1)
        self.assertEqual(live_stats["avg_age_sec"], 0.5)

    def test_error_summary_groups_source_type_status_path_and_repeat(self) -> None:
        from backend.Observability.service import ObservabilityService

        service = ObservabilityService(window_sec=60.0, max_requests=100, max_errors=20)

        service.record_error(
            "spot_live_image",
            "SPOT live image retry backoff active",
            path="/api/spot/live_image",
            status_code=503,
            error_type="live-backoff-active",
        )
        service.record_error(
            "spot_live_image",
            "SPOT live image retry backoff active",
            path="/api/spot/live_image",
            status_code=503,
            error_type="live-backoff-active",
        )

        summary = service.get_error_summary()

        self.assertEqual(summary["queue_size"], 1)
        self.assertEqual(summary["repeat_total"], 2)
        self.assertEqual(summary["source_repeat_counts"]["spot_live_image"], 2)
        self.assertEqual(summary["type_counts"]["live-backoff-active"], 2)
        self.assertEqual(summary["status_counts"]["503"], 2)
        self.assertEqual(summary["path_counts"]["/api/spot/live_image"], 2)
        self.assertEqual(summary["route_status_counts"]["/api/spot/live_image 503"], 2)

    def test_error_log_message_includes_sanitized_route_status_and_type(self) -> None:
        from backend.Observability.service import ObservabilityService

        service = ObservabilityService(window_sec=60.0, max_requests=100, max_errors=20)

        with self.assertLogs("SmartFactoryLoggerV2", level="ERROR") as captured:
            service.record_error(
                "api",
                "HTTP 503",
                path="/api/memory/export/open-file",
                status_code=503,
                error_type="http_5xx",
            )

        self.assertIn(
            "Observability error recorded source=api status=503 type=http_5xx path=/api/memory/export/open-file",
            "\n".join(captured.output),
        )

    async def test_live_image_endpoint_returns_jpeg_with_no_store_headers(self) -> None:
        from backend import app as backend_app

        image_bytes = b"\xff\xd8live-endpoint\xff\xd9"
        meta: dict[str, Any] = {
            "status": "ok",
            "source": "upstream",
            "captured_at": 1_777_660_800.123,
            "age_sec": 0.0,
            "image_url": "http://spot.local/image.jpg",
            "retry_after_sec": None,
        }

        record_mock: Mock = Mock()

        with (
            patch.object(
                backend_app.spot_control,
                "fetch_live_image_async",
                AsyncMock(return_value=(image_bytes, meta)),
            ),
            patch.object(backend_app.observability_service, "record_spot_live_image_result", record_mock),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.get("/api/spot/live_image?t=123")
            finally:
                client.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, image_bytes)
        self.assertIn("image/jpeg", response.headers.get("content-type", ""))
        self.assertIn("no-store", response.headers.get("cache-control", ""))
        self.assertEqual(response.headers.get("X-Spot-Live-Image-Source"), "upstream")
        self.assertEqual(response.headers.get("X-Spot-Live-Image-Age"), "0.000")
        record_mock.assert_called_once_with(200, 0.0, False)

    def test_live_image_backoff_with_stale_cache_returns_200_stale_response(self) -> None:
        from backend import app as backend_app

        spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/live.jpg"
        spot_api.config.SPOT_REFRESH_INTERVAL = 1.0
        stale_bytes = b"\xff\xd8stale-live-frame\xff\xd9"
        spot_api._live_img_cache = {
            "data": stale_bytes,
            "time": time.time() - 2.0,
            "url": "http://spot.local/live.jpg",
        }
        spot_api._live_img_failure_count = 1
        spot_api._record_live_image_error("upstream-timeout", "timeout", "http://spot.local/live.jpg")
        spot_api._record_live_image_backoff(1.25)
        request_mock: AsyncMock = AsyncMock(return_value=b"unexpected")
        record_error_mock: Mock = Mock()
        record_result_mock: Mock = Mock()

        with (
            patch.object(spot_api, "_request_spot_image", request_mock),
            patch.object(backend_app.observability_service, "record_error", record_error_mock),
            patch.object(backend_app.observability_service, "record_spot_live_image_result", record_result_mock),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.get("/api/spot/live_image")
            finally:
                client.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, stale_bytes)
        self.assertEqual(response.headers.get("X-Spot-Live-Image-Source"), "stale-cache")
        self.assertEqual(response.headers.get("X-SFL-Image-Source"), "stale-cache")
        self.assertEqual(response.headers.get("X-SFL-Image-Stale"), "true")
        self.assertEqual(response.headers.get("X-SFL-Image-Fallback-Code"), "live-backoff-active")
        request_mock.assert_not_awaited()
        record_error_mock.assert_called_once()
        _, record_kwargs = record_error_mock.call_args
        self.assertEqual(record_kwargs["path"], "/api/spot/live_image")
        self.assertEqual(record_kwargs["status_code"], 200)
        self.assertEqual(record_kwargs["error_type"], "live-backoff-active")
        self.assertEqual(record_kwargs["level"], "warning")
        record_result_mock.assert_called_once()
        _, _, is_stale = record_result_mock.call_args.args
        self.assertTrue(is_stale)

    def test_live_image_upstream_timeout_with_stale_cache_returns_200_stale_response(self) -> None:
        from backend import app as backend_app

        spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/live.jpg"
        spot_api.config.SPOT_REFRESH_INTERVAL = 1.0
        stale_bytes = b"\xff\xd8stale-live-frame\xff\xd9"
        spot_api._live_img_cache = {
            "data": stale_bytes,
            "time": time.time() - 2.0,
            "url": "http://spot.local/live.jpg",
        }
        image_error = spot_api.SpotImageFetchError(
            "upstream-timeout",
            "SPOT image upstream timed out",
            image_url="http://spot.local/live.jpg",
            upstream_status=None,
        )
        request_mock: AsyncMock = AsyncMock(side_effect=image_error)
        record_error_mock: Mock = Mock()
        record_result_mock: Mock = Mock()

        with (
            patch.object(spot_api, "_request_spot_image", request_mock),
            patch.object(backend_app.observability_service, "record_error", record_error_mock),
            patch.object(backend_app.observability_service, "record_spot_live_image_result", record_result_mock),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.get("/api/spot/live_image")
            finally:
                client.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, stale_bytes)
        self.assertEqual(response.headers.get("X-Spot-Live-Image-Source"), "stale-cache")
        self.assertEqual(response.headers.get("X-SFL-Image-Source"), "stale-cache")
        self.assertEqual(response.headers.get("X-SFL-Image-Stale"), "true")
        self.assertEqual(response.headers.get("X-SFL-Image-Fallback-Code"), "upstream-timeout")
        request_mock.assert_awaited_once()
        record_error_mock.assert_called_once()
        _, record_kwargs = record_error_mock.call_args
        self.assertEqual(record_kwargs["path"], "/api/spot/live_image")
        self.assertEqual(record_kwargs["status_code"], 200)
        self.assertEqual(record_kwargs["error_type"], "upstream-timeout")
        self.assertEqual(record_kwargs["level"], "warning")
        record_result_mock.assert_called_once()
        _, _, is_stale = record_result_mock.call_args.args
        self.assertTrue(is_stale)

    def test_live_image_upstream_timeout_without_cache_keeps_502_response(self) -> None:
        from backend import app as backend_app

        spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/live.jpg"
        image_error = spot_api.SpotImageFetchError(
            "upstream-timeout",
            "SPOT image upstream timed out",
            image_url="http://spot.local/live.jpg",
            upstream_status=None,
        )
        record_error_mock: Mock = Mock()

        with (
            patch.object(spot_api, "_request_spot_image", AsyncMock(side_effect=image_error)),
            patch.object(backend_app.observability_service, "record_error", record_error_mock),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.get("/api/spot/live_image")
            finally:
                client.close()

        self.assertEqual(response.status_code, 502)
        self.assertNotEqual(response.headers.get("X-SFL-Image-Stale"), "true")
        record_error_mock.assert_called_once()
        _, record_kwargs = record_error_mock.call_args
        self.assertEqual(record_kwargs["path"], "/api/spot/live_image")
        self.assertEqual(record_kwargs["status_code"], 502)
        self.assertEqual(record_kwargs["error_type"], "upstream-timeout")

    def test_live_image_backoff_with_over_age_stale_cache_keeps_503_response(self) -> None:
        from backend import app as backend_app

        spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/live.jpg"
        spot_api.config.SPOT_REFRESH_INTERVAL = 1.0
        spot_api._live_img_cache = {
            "data": b"\xff\xd8too-old-live-frame\xff\xd9",
            "time": time.time() - 10.0,
            "url": "http://spot.local/live.jpg",
        }
        spot_api._live_img_failure_count = 1
        spot_api._record_live_image_error("upstream-timeout", "timeout", "http://spot.local/live.jpg")
        spot_api._record_live_image_backoff(1.25)
        request_mock: AsyncMock = AsyncMock(return_value=b"unexpected")
        record_error_mock: Mock = Mock()

        with (
            patch.object(spot_api, "_request_spot_image", request_mock),
            patch.object(backend_app.observability_service, "record_error", record_error_mock),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.get("/api/spot/live_image")
            finally:
                client.close()

        self.assertEqual(response.status_code, 503)
        self.assertNotEqual(response.headers.get("X-SFL-Image-Stale"), "true")
        request_mock.assert_not_awaited()
        record_error_mock.assert_called_once()
        _, record_kwargs = record_error_mock.call_args
        self.assertEqual(record_kwargs["path"], "/api/spot/live_image")
        self.assertEqual(record_kwargs["status_code"], 503)
        self.assertEqual(record_kwargs["error_type"], "live-backoff-active")

    def test_live_image_upstream_timeout_with_over_age_stale_cache_keeps_502_response(self) -> None:
        from backend import app as backend_app

        spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/live.jpg"
        spot_api.config.SPOT_REFRESH_INTERVAL = 1.0
        spot_api._live_img_cache = {
            "data": b"\xff\xd8too-old-live-frame\xff\xd9",
            "time": time.time() - 10.0,
            "url": "http://spot.local/live.jpg",
        }
        image_error = spot_api.SpotImageFetchError(
            "upstream-timeout",
            "SPOT image upstream timed out",
            image_url="http://spot.local/live.jpg",
            upstream_status=None,
        )
        record_error_mock: Mock = Mock()

        with (
            patch.object(spot_api, "_request_spot_image", AsyncMock(side_effect=image_error)),
            patch.object(backend_app.observability_service, "record_error", record_error_mock),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.get("/api/spot/live_image")
            finally:
                client.close()

        self.assertEqual(response.status_code, 502)
        self.assertNotEqual(response.headers.get("X-SFL-Image-Stale"), "true")
        record_error_mock.assert_called_once()
        _, record_kwargs = record_error_mock.call_args
        self.assertEqual(record_kwargs["path"], "/api/spot/live_image")
        self.assertEqual(record_kwargs["status_code"], 502)
        self.assertEqual(record_kwargs["error_type"], "upstream-timeout")

    def test_live_image_fresh_shared_frame_cache_still_returns_200_response(self) -> None:
        from backend import app as backend_app

        spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/live.jpg"
        image_bytes = b"\xff\xd8fresh-live-frame\xff\xd9"
        spot_api._live_img_cache = {
            "data": image_bytes,
            "time": time.time(),
            "url": "http://spot.local/live.jpg",
        }
        request_mock: AsyncMock = AsyncMock(return_value=b"unexpected")
        record_result_mock: Mock = Mock()

        with (
            patch.object(spot_api, "_request_spot_image", request_mock),
            patch.object(backend_app.observability_service, "record_spot_live_image_result", record_result_mock),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.get("/api/spot/live_image")
            finally:
                client.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, image_bytes)
        self.assertEqual(response.headers.get("X-Spot-Live-Image-Source"), "shared-frame")
        self.assertNotEqual(response.headers.get("X-SFL-Image-Stale"), "true")
        request_mock.assert_not_awaited()
        record_result_mock.assert_called_once()
        _, _, is_stale = record_result_mock.call_args.args
        self.assertFalse(is_stale)

    async def test_live_image_upstream_capture_writes_image_fact_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="all")
            spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/live.jpg"
            self.set_spot_temperature_snapshot(
                spot_poll_seq=42,
                spot_raw_validity="invalid_sentinel",
                spot_device_status_code="temperature_under_range",
                spot_diagnostic_evidence_codes='["target_out_of_fov_evidence"]',
                signalpc="1.5",
                _spot_last_poll_completed_at_epoch=time.time(),
            )
            image_bytes = b"\xff\xd8live-capture\xff\xd9"

            with patch.object(spot_api, "_request_spot_image", AsyncMock(return_value=image_bytes)):
                data, meta = await spot_api.fetch_live_image_async()

            self.assertEqual(data, image_bytes)
            self.assertEqual(meta["source"], "upstream")
            self.assertTrue(spot_api.flush_spot_image_capture_queue(timeout_sec=2.0))
            rows = self.read_spot_image_fact_rows(log_path)

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["spot_image_size_bytes"], str(len(image_bytes)))
            self.assertEqual(row["spot_image_mime"], "image/jpeg")
            self.assertEqual(row["spot_image_source"], "live_upstream")
            self.assertEqual(row["spot_image_linked_observation_key"], "test-spot-service-instance:42")
            self.assertEqual(row["spot_image_link_status"], "fresh")
            self.assertGreaterEqual(float(row["spot_image_link_age_ms"]), 0.0)
            self.assertEqual(row["temperature_output_status_nearest"], "under_range")
            self.assertEqual(row["temperature_under_range_cause_candidate_nearest"], "target_out_of_fov_candidate")
            self.assertEqual(len(row["spot_image_source_url_hash"]), 64)
            self.assertTrue((log_path / row["spot_image_path"]).exists())
            self.assertNotIn("http://spot.local", ",".join(row.values()))
            latest = spot_api.get_latest_spot_image_capture_fact()
            health = spot_api.get_spot_image_capture_health()
            self.assertEqual(latest["spot_image_capture_id"], row["spot_image_capture_id"])
            self.assertEqual(latest["spot_image_path"], row["spot_image_path"])
            self.assertEqual(latest["spot_image_link_status"], "fresh")
            self.assertEqual(health["last_capture_id"], row["spot_image_capture_id"])
            self.assertEqual(health["last_capture_path"], row["spot_image_path"])
            self.assertEqual(health["last_capture_link_status"], "fresh")

    async def test_control_shutdown_drains_image_writer_before_final_manifest(self) -> None:
        from backend import app as backend_app

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="all")
            spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/live.jpg"
            self.set_spot_temperature_snapshot(
                spot_poll_seq=43,
                _spot_last_poll_completed_at_epoch=time.time(),
            )
            image_bytes = b"\xff\xd8control-shutdown-drain\xff\xd9"
            write_started = threading.Event()
            release_write = threading.Event()
            original_write_capture = SpotImageCaptureWriter.write_capture

            def delayed_write_capture(writer: SpotImageCaptureWriter, *args: Any, **kwargs: Any) -> dict[str, str]:
                write_started.set()
                release_write.wait(timeout=1.0)
                return original_write_capture(writer, *args, **kwargs)

            class FinalManifestLogger:
                final_manifest: dict[str, Any] | None = None

                def stop(self, *, timeout_sec: float | None = None) -> bool:
                    service = CSVLoggerService()
                    service.fallback_log_dir = log_path
                    service.apply_config(log_path=log_path, auto_save=True, csv_v2_enabled=True)
                    final_path = service.write_spot_image_fact_final_manifest(log_path)
                    self.final_manifest = json.loads(final_path.read_text(encoding="utf-8"))
                    return True

            final_manifest_logger = FinalManifestLogger()

            with (
                patch.object(SpotImageCaptureWriter, "write_capture", delayed_write_capture),
                patch.object(spot_api, "_request_spot_image", AsyncMock(return_value=image_bytes)),
            ):
                await spot_api.fetch_live_image_async()
                self.assertTrue(write_started.wait(timeout=1.0))

                release_thread = threading.Thread(target=lambda: (time.sleep(0.05), release_write.set()))
                release_thread.start()
                with (
                    patch.object(backend_app, "logger_service", final_manifest_logger),
                    patch.object(backend_app.plc_service, "stop", Mock()),
                    patch.object(backend_app.comm_metrics_logger_service, "stop", Mock()),
                    patch.object(backend_app.config_sync_agent, "stop", Mock()),
                    patch.object(backend_app.config_watch_service, "stop", Mock()),
                ):
                    shutdown_status = backend_app._stop_services_for_control_shutdown()
                release_thread.join(timeout=1.0)

            rows = self.read_spot_image_fact_rows(log_path)
            fact_path = log_path / "spot_image_fact.csv"
            fact_sha = hashlib.sha256(fact_path.read_bytes()).hexdigest()

        self.assertTrue(shutdown_status["spot_image_capture_drained"])
        self.assertEqual(len(rows), 1)
        self.assertIsNotNone(final_manifest_logger.final_manifest)
        self.assertEqual(final_manifest_logger.final_manifest["row_count"], 1)
        self.assertEqual(final_manifest_logger.final_manifest["sha256"], fact_sha)

    async def test_shutdown_helper_drains_capture_event_queued_before_worker_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="all")
            event = spot_api._SpotImageCaptureEvent(
                image_bytes=b"\xff\xd8queued-before-worker\xff\xd9",
                captured_at=time.time(),
                source_url="http://spot.local/live.jpg",
                source="test_shutdown_pending",
                image_age_ms=0.0,
                link_checked_at=None,
                observation_snapshot=None,
            )
            spot_api._SPOT_IMAGE_CAPTURE_QUEUE.put_nowait(event)
            with spot_api._spot_image_capture_lock:
                spot_api._spot_image_capture_enqueued_count += 1

            drained = spot_api.stop_spot_image_capture_for_shutdown(timeout_sec=2.0)
            rows = self.read_spot_image_fact_rows(log_path)
            health = spot_api.get_spot_image_capture_health()
            spot_api._maybe_enqueue_spot_image_capture(
                image_bytes=b"\xff\xd8after-shutdown\xff\xd9",
                captured_at=time.time(),
                image_url="http://spot.local/live.jpg",
                source="after_shutdown",
                image_age_ms=0.0,
            )
            health_after_enqueue_attempt = spot_api.get_spot_image_capture_health()

        self.assertTrue(drained)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["spot_image_source"], "test_shutdown_pending")
        self.assertEqual(health["written_count"], 1)
        self.assertEqual(health_after_enqueue_attempt["enqueued_count"], 1)

    async def test_live_image_shared_frame_cache_does_not_duplicate_image_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="all")
            spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/live.jpg"
            image_bytes = b"\xff\xd8shared-frame-capture\xff\xd9"
            request_mock = AsyncMock(return_value=image_bytes)

            with patch.object(spot_api, "_request_spot_image", request_mock):
                first_data, first_meta = await spot_api.fetch_live_image_async()
                second_data, second_meta = await spot_api.fetch_live_image_async()

            self.assertEqual(first_data, image_bytes)
            self.assertEqual(second_data, image_bytes)
            self.assertEqual(first_meta["source"], "upstream")
            self.assertEqual(second_meta["source"], "shared-frame")
            self.assertEqual(request_mock.await_count, 1)
            self.assertTrue(spot_api.flush_spot_image_capture_queue(timeout_sec=2.0))
            self.assertEqual(len(self.read_spot_image_fact_rows(log_path)), 1)

    def test_image_capture_health_separates_worker_writes_from_fact_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="all")
            captured_at = 1782910800.123456
            image_bytes = b"\xff\xd8health-row-count-dedupe\xff\xd9"

            for _ in range(2):
                spot_api._maybe_enqueue_spot_image_capture(
                    image_bytes=image_bytes,
                    captured_at=captured_at,
                    image_url="http://spot.local/image.jpg",
                    source="prefetch_upstream",
                    image_age_ms=0.0,
                )
                self.assertTrue(spot_api.flush_spot_image_capture_queue(timeout_sec=2.0))

            rows = self.read_spot_image_fact_rows(log_path)
            health = spot_api.get_spot_image_capture_health()

            self.assertEqual(len(rows), 1)
            self.assertEqual(health["written_count"], 2)
            self.assertEqual(health["fact_row_count"], 1)

    def test_image_capture_writer_dedupes_same_capture_id_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            capture_root = log_path / "spot_images"
            captured_at = 1782910800.123456
            link_checked_at = captured_at + 0.1
            image_bytes = b"\xff\xd8dedupe-capture\xff\xd9"
            snapshot = {
                "spot_service_instance_id": "test-spot-service-instance",
                "spot_poll_seq": 101,
                "spot_last_poll_completed_at": "2026-07-01T01:00:00Z",
                "_spot_last_poll_completed_at_epoch": captured_at,
                "spot_poll_status": "success",
                "temperature_output_status": "under_range",
            }

            first_writer = SpotImageCaptureWriter(log_path=log_path, capture_root=capture_root)
            first_fact = first_writer.write_capture(
                image_bytes=image_bytes,
                captured_at=captured_at,
                source_url="http://spot.local/image.jpg",
                source="test",
                image_age_ms=0.0,
                link_checked_at=link_checked_at,
                observation_snapshot=snapshot,
            )
            restarted_writer = SpotImageCaptureWriter(log_path=log_path, capture_root=capture_root)
            second_fact = restarted_writer.write_capture(
                image_bytes=image_bytes,
                captured_at=captured_at,
                source_url="http://spot.local/image.jpg",
                source="test",
                image_age_ms=0.0,
                link_checked_at=link_checked_at,
                observation_snapshot=snapshot,
            )

            rows = self.read_spot_image_fact_rows(log_path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(second_fact, first_fact)
            self.assertEqual(rows[0]["spot_image_capture_id"], first_fact["spot_image_capture_id"])
            self.assertTrue((log_path / first_fact["spot_image_path"]).exists())

    def test_event_mode_captures_under_range_snapshot_and_skips_valid_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="event")
            spot_api.config.SPOT_IMAGE_URL = "http://spot.local/image.jpg"
            image_bytes = b"\xff\xd8event-capture\xff\xd9"

            self.set_spot_temperature_snapshot(spot_poll_seq=1, spot_raw_validity="valid_temperature")
            spot_api._maybe_enqueue_spot_image_capture(
                image_bytes=image_bytes,
                captured_at=time.time(),
                image_url="http://spot.local/image.jpg",
                source="prefetch_upstream",
                image_age_ms=0.0,
            )
            self.assertTrue(spot_api.flush_spot_image_capture_queue(timeout_sec=1.0))
            self.assertEqual(self.read_spot_image_fact_rows(log_path), [])

            self.set_spot_temperature_snapshot(
                spot_poll_seq=2,
                spot_raw_validity="invalid_sentinel",
                spot_device_status_code="temperature_under_range",
                spot_diagnostic_evidence_codes='["target_out_of_fov_evidence"]',
            )
            spot_api._maybe_enqueue_spot_image_capture(
                image_bytes=image_bytes,
                captured_at=time.time(),
                image_url="http://spot.local/image.jpg",
                source="prefetch_upstream",
                image_age_ms=0.0,
            )
            self.assertTrue(spot_api.flush_spot_image_capture_queue(timeout_sec=2.0))
            rows = self.read_spot_image_fact_rows(log_path)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["spot_image_linked_observation_key"], "test-spot-service-instance:2")
            self.assertEqual(rows[0]["temperature_output_status_nearest"], "under_range")

    def test_image_capture_drops_oversized_payload_before_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="all", max_bytes=4)

            spot_api._maybe_enqueue_spot_image_capture(
                image_bytes=b"12345",
                captured_at=time.time(),
                image_url="http://spot.local/image.jpg",
                source="prefetch_upstream",
                image_age_ms=0.0,
            )

            self.assertTrue(spot_api.flush_spot_image_capture_queue(timeout_sec=1.0))
            self.assertEqual(self.read_spot_image_fact_rows(log_path), [])
            self.assertEqual(spot_api.get_spot_image_capture_health()["dropped_count"], 1)

    def test_image_capture_writer_rebuilds_when_capture_path_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="all")
            image_bytes = b"\xff\xd8writer-reload\xff\xd9"

            spot_api.config.SPOT_IMAGE_CAPTURE_PATH = "spot_images_a"
            spot_api._maybe_enqueue_spot_image_capture(
                image_bytes=image_bytes,
                captured_at=time.time(),
                image_url="http://spot.local/image.jpg",
                source="prefetch_upstream",
                image_age_ms=0.0,
            )
            self.assertTrue(spot_api.flush_spot_image_capture_queue(timeout_sec=2.0))

            spot_api.config.SPOT_IMAGE_CAPTURE_PATH = "spot_images_b"
            spot_api._maybe_enqueue_spot_image_capture(
                image_bytes=image_bytes,
                captured_at=time.time(),
                image_url="http://spot.local/image.jpg",
                source="prefetch_upstream",
                image_age_ms=0.0,
            )
            self.assertTrue(spot_api.flush_spot_image_capture_queue(timeout_sec=2.0))

            rows = self.read_spot_image_fact_rows(log_path)
            self.assertEqual(len(rows), 2)
            self.assertTrue(rows[0]["spot_image_path"].startswith("spot_images_a/"))
            self.assertTrue(rows[1]["spot_image_path"].startswith("spot_images_b/"))
            self.assertTrue((log_path / rows[0]["spot_image_path"]).exists())
            self.assertTrue((log_path / rows[1]["spot_image_path"]).exists())

    def test_image_capture_retention_cleanup_deletes_only_managed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            capture_root = log_path / "absolute_capture_root"
            old_day_dir = capture_root / "2026" / "06" / "28"
            new_day_dir = capture_root / "2026" / "06" / "29"
            manual_dir = capture_root / "manual"
            old_day_dir.mkdir(parents=True)
            new_day_dir.mkdir(parents=True)
            manual_dir.mkdir(parents=True)
            stale_managed = old_day_dir / "spotimg_20260628T000000000000Z_deadbeef1234.jpg"
            stale_general = old_day_dir / "operator-note.txt"
            stale_lookalike_in_date_tree = old_day_dir / "spotimg_manual.jpg"
            stale_lookalike_outside_date_tree = manual_dir / "spotimg_20260628T000000000000Z_deadbeef1234.jpg"
            fresh_managed = new_day_dir / "spotimg_20260629T000000000000Z_deadbeef1234.jpg"

            now = time.time()
            old_mtime = now - (3 * 86400.0)
            for path in (stale_managed, stale_general, stale_lookalike_in_date_tree, stale_lookalike_outside_date_tree):
                path.write_bytes(b"old")
                os.utime(path, (old_mtime, old_mtime))
            fresh_managed.write_bytes(b"new")

            writer = SpotImageCaptureWriter(
                log_path=log_path,
                capture_root=capture_root,
                retention_days=1,
                last_cleanup_at=0.0,
            )
            writer._cleanup_retention(now)

            self.assertFalse(stale_managed.exists())
            self.assertTrue(stale_general.exists())
            self.assertTrue(stale_lookalike_in_date_tree.exists())
            self.assertTrue(stale_lookalike_outside_date_tree.exists())
            self.assertTrue(fresh_managed.exists())

    async def test_image_capture_writer_failure_does_not_break_live_image_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="all")
            blocker = log_path / "capture-blocker"
            blocker.write_text("not a directory", encoding="utf-8")
            spot_api.config.SPOT_IMAGE_CAPTURE_PATH = "capture-blocker"
            spot_api.config.SPOT_LIVE_IMAGE_URL = "http://spot.local/live.jpg"
            image_bytes = b"\xff\xd8writer-failure-isolated\xff\xd9"

            with patch.object(spot_api, "_request_spot_image", AsyncMock(return_value=image_bytes)):
                data, meta = await spot_api.fetch_live_image_async()

            self.assertEqual(data, image_bytes)
            self.assertEqual(meta["source"], "upstream")
            self.assertTrue(spot_api.flush_spot_image_capture_queue(timeout_sec=2.0))
            health = spot_api.get_spot_image_capture_health()
            self.assertEqual(health["enqueued_count"], 1)
            self.assertEqual(health["failure_count"], 1)
            self.assertEqual(self.read_spot_image_fact_rows(log_path), [])

    async def test_live_image_backoff_records_route_status_and_error_type(self) -> None:
        from backend import app as backend_app

        image_error = spot_api.SpotLiveImageBackoffError("http://spot.local/live.jpg", 1.25)
        record_mock: Mock = Mock()

        with (
            patch.object(
                backend_app.spot_control,
                "fetch_live_image_async",
                AsyncMock(side_effect=image_error),
            ),
            patch.object(backend_app.spot_control, "get_live_image_diagnostics", Mock(return_value={})),
            patch.object(backend_app.observability_service, "record_error", record_mock),
        ):
            with self.assertRaises(HTTPException) as raised:
                await backend_app.live_spot_image()

        exception = raised.exception

        self.assertEqual(exception.status_code, 503)
        self.assertEqual(exception.headers.get("Retry-After"), "2")
        self.assertEqual(exception.headers.get("X-Spot-Retry-After-Ms"), "1250")
        self.assertIn("no-store", exception.headers.get("Cache-Control", ""))
        record_mock.assert_called_once()
        record_args, record_kwargs = record_mock.call_args
        self.assertEqual(record_args[:2], ("spot_live_image", "SPOT live image retry backoff active"))
        self.assertEqual(record_kwargs["path"], "/api/spot/live_image")
        self.assertEqual(record_kwargs["status_code"], 503)
        self.assertEqual(record_kwargs["error_type"], "live-backoff-active")

    def test_live_image_backoff_records_single_handler_error_via_middleware(self) -> None:
        from backend import app as backend_app

        image_error = spot_api.SpotLiveImageBackoffError("http://spot.local/live.jpg", 1.25)
        record_mock: Mock = Mock()

        with (
            patch.object(
                backend_app.spot_control,
                "fetch_live_image_async",
                AsyncMock(side_effect=image_error),
            ),
            patch.object(backend_app.spot_control, "get_live_image_diagnostics", Mock(return_value={})),
            patch.object(backend_app.observability_service, "record_error", record_mock),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.get("/api/spot/live_image")
            finally:
                client.close()

        self.assertEqual(response.status_code, 503)
        record_mock.assert_called_once()
        record_args, record_kwargs = record_mock.call_args
        self.assertEqual(record_args[:2], ("spot_live_image", "SPOT live image retry backoff active"))
        self.assertEqual(record_kwargs["status_code"], 503)

    def test_move_focus_uses_ametek_focus_control_endpoint(self) -> None:
        spot_api.config.SPOT_FOCUS_URL = "http://spot.local/control?p=focus"
        spot_api.config.SPOT_FOCUS_STEP = 50
        calls: list[FocusUrlopenTarget] = []

        def fake_urlopen(target: FocusUrlopenTarget, timeout: int) -> UrlopenResponse:
            calls.append(target)
            if len(calls) == 1:
                return UrlopenResponse(b"700", 200)
            return UrlopenResponse(b"750", 200)

        with patch.object(spot_api, "urlopen", side_effect=fake_urlopen):
            result = spot_api.move_focus(1)

        self.assertEqual(
            result,
            {
                "status": "ok",
                "current": 700,
                "new": 750,
                "verified": 750,
                "request_steps": 1,
                "focus_step": 50,
            },
        )
        self.assertEqual(calls[0], "http://spot.local/control?p=focus")
        request = calls[1]
        if not isinstance(request, UrlRequest):
            self.fail("Expected focus write to use urllib.request.Request")
        self.assertEqual(request.full_url, "http://spot.local/control?p=focus")
        self.assertEqual(request.data, b"750")
        self.assertEqual(request.get_method(), "PUT")
        self.assertEqual(calls[2], "http://spot.local/control?p=focus")

    def test_move_actuator_uses_scan_cgi_move_endpoint(self) -> None:
        spot_api.config.SPOT_ACTUATOR_URL = "http://actuator.local/scan.cgi"
        spot_api.config.SPOT_ACTUATOR_STEP = 5
        calls: list[FocusUrlopenTarget] = []

        def fake_urlopen(target: FocusUrlopenTarget, timeout: int) -> UrlopenResponse:
            calls.append(target)
            if len(calls) == 1:
                return UrlopenResponse(b"<html>Pos--> 100</html>", 200)
            if len(calls) == 2:
                return UrlopenResponse(b"OK", 200)
            return UrlopenResponse(b"<html>Pos--> 95</html>", 200)

        with patch("backend.FacilityData.drivers.spot_api.urlopen", fake_urlopen):
            result = spot_api.move_actuator(-1)

        self.assertEqual(
            {
                "status": "ok",
                "current": 100,
                "new": 95,
                "verified": 95,
                "request_steps": -1,
                "actuator_step": 5,
            },
            result,
        )
        self.assertEqual(
            calls,
            [
                "http://actuator.local/scan.cgi?scan=3",
                "http://actuator.local/scan.cgi?scan=3&move=95",
                "http://actuator.local/scan.cgi?scan=3",
            ],
        )

    def test_move_actuator_rejects_unchanged_readback_after_successful_move(self) -> None:
        spot_api.config.SPOT_ACTUATOR_URL = "http://actuator.local/scan.cgi"
        spot_api.config.SPOT_ACTUATOR_STEP = 5
        calls: list[FocusUrlopenTarget] = []

        def fake_urlopen(target: FocusUrlopenTarget, timeout: int) -> UrlopenResponse:
            calls.append(target)
            if len(calls) == 1:
                return UrlopenResponse(b"<html>Pos--> 100</html>", 200)
            if len(calls) == 2:
                return UrlopenResponse(b"OK", 200)
            return UrlopenResponse(b"<html>Pos--> 100</html>", 200)

        with (
            patch("backend.FacilityData.drivers.spot_api.urlopen", fake_urlopen),
            patch.object(spot_api, "_SPOT_ACTUATOR_VERIFY_TIMEOUT_SEC", 0.001),
            patch.object(spot_api, "_SPOT_ACTUATOR_VERIFY_INTERVAL_SEC", 0.001),
        ):
            with self.assertRaises(spot_api.SpotActuatorControlError) as raised:
                spot_api.move_actuator(-1)

        self.assertIn("SPOT actuator write did not reach requested position", str(raised.exception))
        self.assertIn("http://actuator.local/scan.cgi", str(raised.exception))
        self.assertEqual(calls[0], "http://actuator.local/scan.cgi?scan=3")
        self.assertEqual(calls[1], "http://actuator.local/scan.cgi?scan=3&move=95")

    def test_move_focus_accepts_previous_value_write_ack_when_readback_matches(self) -> None:
        spot_api.config.SPOT_FOCUS_URL = "http://spot.local/control?p=focus"
        spot_api.config.SPOT_FOCUS_STEP = 200
        calls: list[FocusUrlopenTarget] = []

        def fake_urlopen(target: FocusUrlopenTarget, timeout: int) -> UrlopenResponse:
            calls.append(target)
            if len(calls) == 1:
                return UrlopenResponse(b"6071", 200)
            if len(calls) == 2:
                return UrlopenResponse(b"6071", 200)
            return UrlopenResponse(b"5871", 200)

        with patch("backend.FacilityData.drivers.spot_api.urlopen", fake_urlopen):
            result = spot_api.move_focus(-1)

        self.assertEqual(
            {
                "status": "ok",
                "current": 6071,
                "new": 5871,
                "verified": 5871,
                "request_steps": -1,
                "focus_step": 200,
            },
            result,
        )
        self.assertEqual(len(calls), 3)

    def test_move_focus_rejects_unchanged_readback_after_successful_put(self) -> None:
        spot_api.config.SPOT_FOCUS_URL = "http://spot.local/control?p=focus"
        spot_api.config.SPOT_FOCUS_STEP = 50
        calls: list[FocusUrlopenTarget] = []

        def fake_urlopen(target: FocusUrlopenTarget, timeout: int) -> UrlopenResponse:
            calls.append(target)
            if len(calls) == 1:
                return UrlopenResponse(b"700", 200)
            if len(calls) == 2:
                return UrlopenResponse(b"750", 200)
            return UrlopenResponse(b"700", 200)

        with patch.object(spot_api, "urlopen", side_effect=fake_urlopen):
            with self.assertRaises(spot_api.SpotFocusControlError) as raised:
                spot_api.move_focus(1)

        self.assertIn("SPOT focus write did not reach requested position", str(raised.exception))
        self.assertEqual(calls[0], "http://spot.local/control?p=focus")
        write_request = calls[1]
        if not isinstance(write_request, UrlRequest):
            self.fail("Expected focus write to use urllib.request.Request")
        self.assertEqual(write_request.data, b"750")
        self.assertEqual(calls[2], "http://spot.local/control?p=focus")

    def test_move_focus_zero_steps_is_noop_without_put(self) -> None:
        spot_api.config.SPOT_FOCUS_URL = "http://spot.local/control?p=focus"
        spot_api.config.SPOT_FOCUS_STEP = 50
        calls: list[FocusUrlopenTarget] = []

        def fake_urlopen(target: FocusUrlopenTarget, timeout: int) -> UrlopenResponse:
            calls.append(target)
            return UrlopenResponse(b"700", 200)

        with patch.object(spot_api, "urlopen", side_effect=fake_urlopen):
            result = spot_api.move_focus(0)

        self.assertEqual(
            result,
            {
                "status": "noop",
                "message": "steps=0",
            },
        )
        self.assertEqual(calls, [])

    def test_move_focus_clamps_ametek_focus_value_to_document_range(self) -> None:
        spot_api.config.SPOT_FOCUS_URL = "http://spot.local/control?p=focus"
        spot_api.config.SPOT_FOCUS_STEP = 50
        calls: list[FocusUrlopenTarget] = []

        def fake_urlopen(target: FocusUrlopenTarget, timeout: int) -> UrlopenResponse:
            calls.append(target)
            if len(calls) == 1:
                return UrlopenResponse(b"9980", 200)
            return UrlopenResponse(b"10000", 200)

        with patch.object(spot_api, "urlopen", side_effect=fake_urlopen):
            result = spot_api.move_focus(1)

        request = calls[1]
        if not isinstance(request, UrlRequest):
            self.fail("Expected focus write to use urllib.request.Request")

        self.assertEqual(result["new"], 10000)
        self.assertEqual(request.data, b"10000")

    def test_move_focus_clamps_lower_ametek_focus_value_to_document_range(self) -> None:
        spot_api.config.SPOT_FOCUS_URL = "http://spot.local/control?p=focus"
        spot_api.config.SPOT_FOCUS_STEP = 50
        calls: list[FocusUrlopenTarget] = []

        def fake_urlopen(target: FocusUrlopenTarget, timeout: int) -> UrlopenResponse:
            calls.append(target)
            if len(calls) == 1:
                return UrlopenResponse(b"320", 200)
            return UrlopenResponse(b"300", 200)

        with patch.object(spot_api, "urlopen", side_effect=fake_urlopen):
            result = spot_api.move_focus(-1)

        request = calls[1]
        if not isinstance(request, UrlRequest):
            self.fail("Expected focus write to use urllib.request.Request")

        self.assertEqual(result["current"], 320)
        self.assertEqual(result["new"], 300)
        self.assertEqual(request.data, b"300")
        self.assertEqual(request.get_method(), "PUT")

    def test_move_focus_does_not_put_when_ametek_focus_is_already_at_limit(self) -> None:
        spot_api.config.SPOT_FOCUS_URL = "http://spot.local/control?p=focus"
        spot_api.config.SPOT_FOCUS_STEP = 50
        calls: list[FocusUrlopenTarget] = []

        def fake_urlopen(target: FocusUrlopenTarget, timeout: int) -> UrlopenResponse:
            calls.append(target)
            return UrlopenResponse(b"300", 200)

        with patch.object(spot_api, "urlopen", side_effect=fake_urlopen):
            result = spot_api.move_focus(-1)

        self.assertEqual(
            result,
            {
                "status": "limit",
                "current": 300,
                "new": 300,
                "request_steps": -1,
                "focus_step": 50,
            },
        )
        self.assertEqual(calls, ["http://spot.local/control?p=focus"])

    def test_move_focus_does_not_put_when_ametek_focus_is_already_at_upper_limit(self) -> None:
        spot_api.config.SPOT_FOCUS_URL = "http://spot.local/control?p=focus"
        spot_api.config.SPOT_FOCUS_STEP = 50
        calls: list[FocusUrlopenTarget] = []

        def fake_urlopen(target: FocusUrlopenTarget, timeout: int) -> UrlopenResponse:
            calls.append(target)
            return UrlopenResponse(b"10000", 200)

        with patch.object(spot_api, "urlopen", side_effect=fake_urlopen):
            result = spot_api.move_focus(1)

        self.assertEqual(
            result,
            {
                "status": "limit",
                "current": 10000,
                "new": 10000,
                "request_steps": 1,
                "focus_step": 50,
            },
        )
        self.assertEqual(calls, ["http://spot.local/control?p=focus"])

    def test_move_focus_rejects_non_numeric_focus_response(self) -> None:
        spot_api.config.SPOT_FOCUS_URL = "http://spot.local/control?p=focus"

        with patch.object(spot_api, "urlopen", return_value=UrlopenResponse(b"not-a-focus-value", 200)):
            with self.assertRaises(spot_api.SpotFocusControlError) as raised:
                spot_api.move_focus(1)

        self.assertIn("SPOT focus response is not an integer", str(raised.exception))

    def test_move_focus_secure_mode_read_status_is_preserved(self) -> None:
        spot_api.config.SPOT_FOCUS_URL = "http://spot.local/control?p=focus"

        with patch.object(spot_api, "urlopen", return_value=UrlopenResponse(b"secure mode", 403)):
            with self.assertRaises(spot_api.SpotFocusControlError) as raised:
                spot_api.move_focus(1)

        self.assertEqual(raised.exception.upstream_status, 403)
        self.assertIn("HTTP 403", str(raised.exception))
        self.assertIn("secure mode", str(raised.exception))

    def test_move_focus_secure_mode_write_status_is_preserved(self) -> None:
        spot_api.config.SPOT_FOCUS_URL = "http://spot.local/control?p=focus"
        spot_api.config.SPOT_FOCUS_STEP = 50
        calls: list[FocusUrlopenTarget] = []

        def fake_urlopen(target: FocusUrlopenTarget, timeout: int) -> UrlopenResponse:
            calls.append(target)
            if len(calls) == 1:
                return UrlopenResponse(b"700", 200)
            return UrlopenResponse(b"secure mode", 403)

        with patch.object(spot_api, "urlopen", side_effect=fake_urlopen):
            with self.assertRaises(spot_api.SpotFocusControlError) as raised:
                spot_api.move_focus(1)

        self.assertEqual(raised.exception.upstream_status, 403)
        self.assertIn("HTTP 403", str(raised.exception))
        self.assertIn("secure mode", str(raised.exception))

    def test_spot_focus_bad_upstream_body_maps_to_bad_gateway(self) -> None:
        from backend import app as backend_app

        focus_error = spot_api.SpotFocusControlError(
            "SPOT focus response is not an integer; url=http://spot.local/control?p=focus; status_code=200; body=bad",
            focus_url="http://spot.local/control?p=focus",
            upstream_status=200,
        )

        with (
            patch.object(backend_app.spot_control, "move_focus", Mock(side_effect=focus_error)),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.post("/api/spot/focus?steps=1")
            finally:
                client.close()

        self.assertEqual(response.status_code, 502)
        self.assertIn("not an integer", response.json()["detail"])

    def test_spot_focus_missing_focus_url_maps_to_not_found(self) -> None:
        from backend import app as backend_app

        with (
            patch.object(
                backend_app.spot_control,
                "move_focus",
                Mock(side_effect=RuntimeError("SPOT_FOCUS_URL is not configured")),
            ),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.post("/api/spot/focus?steps=1")
            finally:
                client.close()

        self.assertEqual(response.status_code, 404)
        self.assertIn("SPOT_FOCUS_URL is not configured", response.json()["detail"])

    def test_spot_focus_preserves_upstream_auth_status(self) -> None:
        from backend import app as backend_app

        focus_error = spot_api.SpotFocusControlError(
            "SPOT focus write failed: HTTP 403; url=http://spot.local/control?p=focus; value=750; body=locked",
            focus_url="http://spot.local/control?p=focus",
            upstream_status=403,
        )

        with (
            patch.object(backend_app.spot_control, "move_focus", Mock(side_effect=focus_error)),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.post("/api/spot/focus?steps=1")
            finally:
                client.close()

        self.assertEqual(response.status_code, 403)
        self.assertIn("HTTP 403", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
