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

from backend import app as backend_app
from backend.FacilityData.drivers import spot_api
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData.spot_image_fact import (
    SpotImageCaptureWriter,
    _under_range_cause_candidate,
)

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


class FakeSpotHttpTransport:
    supported = True
    active = True

    def __init__(self) -> None:
        self.requests: list[spot_api.SpotHttpRequest] = []

    async def request(self, request: spot_api.SpotHttpRequest) -> spot_api.SpotHttpResponse:
        return self.request_sync(request)

    async def close(self, timeout_sec: float = 7.0) -> bool:
        del timeout_sec
        self.active = False
        return True

    def request_sync(self, request: spot_api.SpotHttpRequest) -> spot_api.SpotHttpResponse:
        self.requests.append(request)
        if request.kind == spot_api.SpotRequestKind.IMAGE:
            body = b"\xff\xd8guarded-image\xff\xd9"
            headers = {"content-type": "image/jpeg"}
        elif request.kind in {
            spot_api.SpotRequestKind.TEMPERATURE,
            spot_api.SpotRequestKind.INTERNAL_TEMPERATURE,
        }:
            body = b"451.25"
            headers = {"content-type": "text/plain"}
        elif request.kind == spot_api.SpotRequestKind.DIAGNOSTIC:
            body = b"7"
            headers = {"content-type": "text/plain"}
        elif request.kind in {
            spot_api.SpotRequestKind.FOCUS_READ,
            spot_api.SpotRequestKind.FOCUS_WRITE,
        }:
            body = b"600" if request.kind == spot_api.SpotRequestKind.FOCUS_READ else b"OK"
            headers = {"content-type": "text/plain"}
        else:
            body = b"Pos--> 321"
            headers = {"content-type": "text/plain"}
        return spot_api.SpotHttpResponse(
            status_code=200,
            headers=headers,
            body=body,
            elapsed_ms=1.0,
        )

    def diagnostics(self) -> dict[str, object]:
        return {
            "source_port_policy_version": "spot-source-port-quarantine-v2",
            "source_port_enforcement_supported": True,
            "source_port_enforcement_active": True,
            "source_port_quarantine_seconds": 75.0,
            "source_port_pool_capacity": 768,
            "source_port_pool_guarded_count": 767,
            "source_port_pool_leased_count": 0,
            "source_port_pool_quarantined_count": 1,
            "source_port_pool_rebind_pending_count": 0,
            "source_port_pool_acquire_wait_count": 0,
            "source_port_pool_exhaustion_count": 0,
            "source_port_bind_collision_count": 0,
            "source_port_rebind_retry_count": 0,
            "source_port_reuse_violation_count": 0,
            "source_port_minimum_reuse_interval_seconds": None,
            "source_port_transport_started_count": len(self.requests),
            "source_port_transport_success_count": len(self.requests),
            "source_port_transport_failure_count": 0,
        }


class SpotApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_spot_url: str = str(spot_api.config.SPOT_URL)
        self.original_spot_ip: str = str(spot_api.config.SPOT_IP)
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

    async def asyncSetUp(self) -> None:
        await spot_api._reset_spot_http_transport_state_for_tests()

    async def asyncTearDown(self) -> None:
        await spot_api._reset_spot_http_transport_state_for_tests()

    def tearDown(self) -> None:
        spot_api.config.SPOT_URL = self.original_spot_url
        spot_api.config.SPOT_IP = self.original_spot_ip
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
        spot_api._reset_spot_image_request_state_for_tests()
        spot_api._reset_spot_diagnostics_request_state_for_tests()
        spot_api._spot_device_request_lock = asyncio.Lock()
        spot_api._temperature_cache = {"temp": 0.0, "temp_time": 0.0}
        spot_api._internal_temp_cache = {"temp": 0.0, "temp_time": 0.0}
        spot_api._img_last_error = 0.0
        spot_api._img_failure_count = 0
        spot_api._img_last_error_code = None
        spot_api._img_last_error_message = None
        spot_api._img_last_success_at = 0.0
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
            spot_api._spot_diagnostics_seq = 0
        with spot_api._spot_temperature_snapshot_lock:
            spot_api._spot_service_instance_id = "test-spot-service-instance"
            spot_api._spot_service_started_at = "2026-06-22T00:00:00Z"
            spot_api._spot_poll_seq = 0
            spot_api._spot_observation_seq = 0
            spot_api._spot_temperature_snapshot = None
            spot_api._spot_last_valid_value_at = None
            spot_api._spot_last_valid_value_monotonic = None
            spot_api._spot_temperature_cache_suppressed_until_valid = False
        with spot_api._spot_config_provenance_lock:
            spot_api._spot_config_drift_detected_count = 0
            spot_api._spot_config_active_drift_signature = None
            spot_api._spot_last_configuration_snapshot = None
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

    def test_image_fact_cause_requires_explicit_operational_gate_result(self) -> None:
        raw_low_signal = {
            "spot_raw_validity": "invalid_sentinel",
            "spot_device_status_code": "temperature_under_range",
            "spot_diagnostic_evidence_codes": '["alarm_low_signal"]',
        }

        self.assertEqual(_under_range_cause_candidate(raw_low_signal), "unknown")
        self.assertEqual(
            _under_range_cause_candidate(
                {
                    **raw_low_signal,
                    "temperature_under_range_cause_candidate": "low_signal_candidate",
                }
            ),
            "low_signal_candidate",
        )
        self.assertEqual(
            _under_range_cause_candidate(
                {
                    **raw_low_signal,
                    "temperature_under_range_cause_candidate": "target_out_of_fov_candidate",
                }
            ),
            "unknown",
        )

    def test_config_drift_health_counts_transitions_not_poll_repetitions(self) -> None:
        with patch.object(spot_api.config, "SPOT_CONFIG_OPERATOR_VERIFIED", True):
            spot_api._spot_configuration_snapshot()
            spot_api._spot_configuration_snapshot()
            self.assertEqual(
                spot_api.get_spot_observation_fact_health()["config_drift_detected_count"],
                1,
            )

        with patch.object(spot_api.config, "SPOT_CONFIG_OPERATOR_VERIFIED", False):
            spot_api._spot_configuration_snapshot()
        with patch.object(spot_api.config, "SPOT_CONFIG_OPERATOR_VERIFIED", True):
            spot_api._spot_configuration_snapshot()

        self.assertEqual(
            spot_api.get_spot_observation_fact_health()["config_drift_detected_count"],
            2,
        )

    def test_spot_temperature_diagnostics_before_first_poll_are_startup_pending(self) -> None:
        diagnostics: dict[str, Any] = spot_api.get_spot_diagnostics()

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
            diagnostics: dict[str, Any] = spot_api.get_spot_diagnostics()
            snapshot = spot_api.get_spot_temperature_poll_snapshot()

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["_spot_last_poll_completed_monotonic"], 12345.5)
        self.assertEqual(diagnostics["spot_last_poll_completed_monotonic"], 12345.5)
        self.assertEqual(diagnostics["spot_snapshot_age_ms"], 0.0)
        self.assertEqual(diagnostics["spot_last_valid_value_monotonic"], 12345.5)
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

    async def test_slow_observation_fact_write_does_not_block_health_or_data(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"
        writer_started = threading.Event()
        release_writer = threading.Event()
        writer_timed_out = threading.Event()
        writer_thread_ids: list[int] = []
        event_loop_thread_id = threading.get_ident()

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="448.5", request=request)

        def blocking_fact_write(snapshot: dict[str, Any]) -> None:
            self.assertEqual(snapshot["spot_temperature_observed_c"], 448.5)
            writer_thread_ids.append(threading.get_ident())
            writer_started.set()
            if not release_writer.wait(timeout=1.0):
                writer_timed_out.set()

        with (
            patch.object(
                spot_api,
                "_write_spot_observation_fact_safely",
                side_effect=blocking_fact_write,
            ),
            patch.object(backend_app, "build_health_payload", return_value={"running": True}),
        ):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                refresh_task = asyncio.create_task(spot_api._refresh_spot_temperature(client))
                try:
                    started = await asyncio.wait_for(
                        asyncio.to_thread(writer_started.wait, 0.5),
                        timeout=1.0,
                    )
                    self.assertTrue(started)

                    health_payload, data_payload = await asyncio.wait_for(
                        asyncio.gather(backend_app.health(), backend_app.get_data()),
                        timeout=0.5,
                    )
                    self.assertTrue(health_payload["running"])
                    self.assertIsNotNone(data_payload)
                    self.assertFalse(refresh_task.done())
                finally:
                    release_writer.set()

                await asyncio.wait_for(refresh_task, timeout=1.0)

        self.assertFalse(writer_timed_out.is_set())
        self.assertEqual(len(writer_thread_ids), 1)
        self.assertNotEqual(writer_thread_ids[0], event_loop_thread_id)

    async def test_cancelled_refresh_waits_for_observation_fact_write(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"
        writer_started = threading.Event()
        release_writer = threading.Event()

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="448.5", request=request)

        def blocking_fact_write(_snapshot: dict[str, Any]) -> None:
            writer_started.set()
            release_writer.wait(timeout=1.0)

        with patch.object(
            spot_api,
            "_write_spot_observation_fact_safely",
            side_effect=blocking_fact_write,
        ):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                refresh_task = asyncio.create_task(spot_api._refresh_spot_temperature(client))
                started = await asyncio.wait_for(
                    asyncio.to_thread(writer_started.wait, 0.5),
                    timeout=1.0,
                )
                self.assertTrue(started)

                refresh_task.cancel()
                await asyncio.sleep(0)
                self.assertFalse(refresh_task.done())

                release_writer.set()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(refresh_task, timeout=1.0)

    async def test_temperature_cache_and_observation_snapshot_publish_atomically(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"

        async def first_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="448.5", request=request)

        async def second_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="449.5", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(first_handler)) as client:
            await spot_api._refresh_spot_temperature(client)

        original_publish = spot_api._publish_spot_temperature_snapshot
        interleaved_diagnostics: list[dict[str, Any]] = []

        def observe_before_publish(**kwargs: Any) -> dict[str, Any]:
            interleaved_diagnostics.append(spot_api.get_spot_diagnostics())
            return original_publish(**kwargs)

        with patch.object(spot_api, "_publish_spot_temperature_snapshot", side_effect=observe_before_publish):
            async with httpx.AsyncClient(transport=httpx.MockTransport(second_handler)) as client:
                await spot_api._refresh_spot_temperature(client)

        self.assertEqual(len(interleaved_diagnostics), 1)
        interleaved = interleaved_diagnostics[0]
        self.assertEqual(interleaved["temperature_value_origin"], "current_observation")
        self.assertEqual(interleaved["spot_temperature_observed_c"], 448.5)
        self.assertEqual(interleaved["spot_temperature_effective_c"], 448.5)

        final_diagnostics = spot_api.get_spot_diagnostics()
        self.assertEqual(final_diagnostics["spot_temperature_observed_c"], 449.5)
        self.assertEqual(final_diagnostics["spot_temperature_effective_c"], 449.5)

    async def test_temperature_diagnostics_read_one_cache_snapshot_generation(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"

        async def first_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="448.5", request=request)

        async def second_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="449.5", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(first_handler)) as client:
            await spot_api._refresh_spot_temperature(client)

        derive_entered = threading.Event()
        allow_derive = threading.Event()
        original_derive = spot_api.derive_temperature_state
        captured: list[dict[str, Any]] = []
        reader_errors: list[BaseException] = []

        def blocking_derive(input_state: Any) -> Any:
            result = original_derive(input_state)
            derive_entered.set()
            if not allow_derive.wait(timeout=2.0):
                raise TimeoutError("diagnostics read was not released")
            return result

        def read_diagnostics() -> None:
            try:
                captured.append(spot_api.get_spot_diagnostics())
            except BaseException as exc:  # pragma: no cover - asserted below
                reader_errors.append(exc)

        with patch.object(spot_api, "derive_temperature_state", side_effect=blocking_derive):
            reader = threading.Thread(target=read_diagnostics)
            reader.start()
            try:
                self.assertTrue(derive_entered.wait(timeout=1.0))
                async with httpx.AsyncClient(transport=httpx.MockTransport(second_handler)) as client:
                    await spot_api._refresh_spot_temperature(client)
            finally:
                allow_derive.set()
                reader.join(timeout=2.0)

        self.assertFalse(reader.is_alive())
        self.assertEqual(reader_errors, [])
        self.assertEqual(len(captured), 1)
        diagnostics = captured[0]
        self.assertEqual(diagnostics["spot_temperature_observed_c"], 448.5)
        self.assertEqual(diagnostics["spot_temperature_effective_c"], 448.5)

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

        diagnostics: dict[str, Any] = spot_api.get_spot_diagnostics()

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
        self.assertIsNone(diagnostics["spot_last_valid_value_monotonic"])
        self.assertEqual(spot_api._temperature_cache["temp_time"], 0.0)


    async def test_ametek_under_range_sentinel_publishes_invalid_value_snapshot(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/temp"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="6553.4\r\n", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(spot_api.SpotTemperatureFetchError) as raised:
                await spot_api._refresh_spot_temperature(client)

        error = raised.exception
        diagnostics: dict[str, Any] = spot_api.get_spot_diagnostics()

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
            if url == "http://spot.local/control?p=appnumber":
                return httpx.Response(200, text="7", request=request)
            if url == "http://spot.local/output?p=temperature":
                return httpx.Response(200, text="6553.4", request=request)
            return httpx.Response(404, text="not found", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await spot_api._refresh_spot_diagnostics_safely(client, spot_api._logger)
            with self.assertRaises(spot_api.SpotTemperatureFetchError):
                await spot_api._refresh_spot_temperature(client)

        diagnostics: dict[str, Any] = spot_api.get_spot_diagnostics()
        fact = spot_api.get_spot_temperature_poll_snapshot()

        self.assertEqual(diagnostics["diagnostics_capture_status"], "async_complete")
        self.assertEqual(diagnostics["diagnostics_upstream_request_count"], 8)
        self.assertEqual(diagnostics["diagnostics_binding_status"], "unbound")
        self.assertEqual(diagnostics["diagnostics_collection_mode"], "async_fact_only")
        self.assertIsNone(diagnostics["diagnostics_source_poll_seq"])
        self.assertEqual(diagnostics["alarmstatus"], "LOW SIGNAL")
        self.assertEqual(diagnostics["signalpc"], "3.2")
        self.assertEqual(
            diagnostics["spot_diagnostic_evidence_codes"],
            '["alarm_low_signal","signalpc_present_comparator_unverified"]',
        )
        self.assertEqual(diagnostics["d1temperature"], "345.7")
        self.assertEqual(diagnostics["d2temperature"], "319.1")
        self.assertEqual(diagnostics["e1out"], "57")
        self.assertEqual(diagnostics["e2out"], "53")
        self.assertEqual(diagnostics["itemperature"], "41.2")
        self.assertEqual(diagnostics["appnumber"], "7")
        self.assertEqual(diagnostics["low_signal_alarm_enabled"], False)
        self.assertEqual(diagnostics["low_signal_threshold_pc"], 2.0)
        self.assertEqual(diagnostics["low_signal_comparator"], "lt")
        self.assertEqual(diagnostics["low_signal_comparator_verified"], False)
        self.assertEqual(diagnostics["spot_app_mode"], "App1: AL E")
        self.assertFalse(diagnostics["config_operator_verified"])
        self.assertEqual(len(diagnostics["spot_config_fingerprint_sha256"]), 64)
        self.assertEqual(diagnostics["device_config_readback_status"], "not_supported")
        self.assertIsNotNone(fact)
        assert fact is not None
        self.assertEqual(fact["diagnostics_capture_status"], "async_complete")
        self.assertEqual(fact["diagnostics_binding_status"], "unbound")
        self.assertEqual(fact["itemperature"], "41.2")
        self.assertIn("http://spot.local/output?p=alarmstatus", requests)
        self.assertIn("http://spot.local/output?p=signalpc", requests)
        self.assertIn("http://spot.local/output?p=d1temperature", requests)
        self.assertIn("http://spot.local/output?p=d2temperature", requests)
        self.assertIn("http://spot.local/output?p=e1out", requests)
        self.assertIn("http://spot.local/output?p=e2out", requests)
        self.assertIn("http://spot.local/output?p=itemperature", requests)
        self.assertIn("http://spot.local/control?p=appnumber", requests)
        self.assertNotIn("http://spot.local/output?p=appnumber", requests)

    async def test_serialized_scheduled_diagnostics_bind_to_next_poll(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/output?p=temperature"

        async def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url).endswith("p=temperature"):
                return httpx.Response(200, text="450.0", request=request)
            return httpx.Response(200, text="0", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await spot_api._refresh_spot_temperature(client, schedule_diagnostics=True)
            first_snapshot = spot_api.get_spot_temperature_poll_snapshot()
            task = spot_api._spot_diagnostics_task
            if task is not None:
                await task
            await spot_api._refresh_spot_temperature(client)

        snapshot = spot_api.get_spot_temperature_poll_snapshot()
        self.assertIsNotNone(first_snapshot)
        assert first_snapshot is not None
        self.assertEqual(first_snapshot["diagnostics_capture_status"], "missing")
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot["diagnostics_capture_status"], "async_complete")
        self.assertEqual(snapshot["diagnostics_binding_status"], "previous_poll")
        self.assertEqual(snapshot["diagnostics_source_poll_seq"], 1)
        self.assertEqual(snapshot["spot_poll_seq"], 2)
        self.assertRegex(snapshot["diagnostics_snapshot_id"], r":diag:[1-9][0-9]*$")
        self.assertGreaterEqual(float(snapshot["diagnostics_age_ms"]), 0.0)
        captured_monotonic = float(snapshot["_diagnostics_captured_monotonic"])
        with patch.object(spot_api.time, "monotonic", return_value=captured_monotonic + 7.0):
            refreshed = spot_api._build_spot_temperature_snapshot_diagnostics(time.time())
        self.assertEqual(refreshed["diagnostics_age_ms"], "7000.000")

    async def test_diagnostics_scheduler_enforces_the_device_request_budget(self) -> None:
        spot_api.config.SPOT_REFRESH_INTERVAL = 1.0
        context = spot_api.SpotPollContext(
            service_instance_id="test-spot-service-instance",
            poll_seq=1,
            started_at_epoch=time.time(),
            started_monotonic=100.0,
        )
        client = AsyncMock(spec=httpx.AsyncClient)

        with patch.object(
            spot_api,
            "_refresh_spot_diagnostics_safely",
            AsyncMock(),
        ) as refresh_mock:
            with patch.object(spot_api.time, "monotonic", return_value=100.0):
                self.assertTrue(
                    spot_api._schedule_spot_diagnostics_for_poll(client, context)
                )
            first_task = spot_api._spot_diagnostics_task
            assert first_task is not None
            await first_task

            with patch.object(spot_api.time, "monotonic", return_value=109.999):
                self.assertFalse(
                    spot_api._schedule_spot_diagnostics_for_poll(client, context)
                )
            with patch.object(spot_api.time, "monotonic", return_value=110.0):
                self.assertTrue(
                    spot_api._schedule_spot_diagnostics_for_poll(client, context)
                )
            second_task = spot_api._spot_diagnostics_task
            assert second_task is not None
            await second_task

        self.assertEqual(refresh_mock.await_count, 2)
        diagnostics = spot_api.get_spot_diagnostics()
        self.assertEqual(diagnostics["diagnostics_refresh_interval_sec_effective"], 10.0)
        self.assertEqual(diagnostics["diagnostics_sweep_started_count"], 2)
        self.assertEqual(diagnostics["diagnostics_suppressed_poll_count"], 1)
        self.assertEqual(diagnostics["diagnostics_inflight_suppressed_count"], 0)

    async def test_diagnostics_scheduler_does_not_overlap_a_slow_sweep(self) -> None:
        spot_api.config.SPOT_REFRESH_INTERVAL = 1.0
        context = spot_api.SpotPollContext(
            service_instance_id="test-spot-service-instance",
            poll_seq=1,
            started_at_epoch=time.time(),
            started_monotonic=100.0,
        )
        client = AsyncMock(spec=httpx.AsyncClient)
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_refresh(*_args: object, **_kwargs: object) -> None:
            started.set()
            await release.wait()

        with patch.object(
            spot_api,
            "_refresh_spot_diagnostics_safely",
            side_effect=slow_refresh,
        ) as refresh_mock:
            with patch.object(spot_api.time, "monotonic", return_value=100.0):
                self.assertTrue(
                    spot_api._schedule_spot_diagnostics_for_poll(client, context)
                )
            await started.wait()
            with patch.object(spot_api.time, "monotonic", return_value=120.0):
                self.assertFalse(
                    spot_api._schedule_spot_diagnostics_for_poll(client, context)
                )
            release.set()
            task = spot_api._spot_diagnostics_task
            assert task is not None
            await task

        self.assertEqual(refresh_mock.await_count, 1)
        diagnostics = spot_api.get_spot_diagnostics()
        self.assertEqual(diagnostics["diagnostics_sweep_started_count"], 1)
        self.assertEqual(diagnostics["diagnostics_inflight_suppressed_count"], 1)

    async def test_late_diagnostics_do_not_block_temperature_or_bind_to_next_poll(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/output?p=temperature"
        diagnostics_started = asyncio.Event()
        diagnostics_release = asyncio.Event()

        async def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url).endswith("p=temperature"):
                return httpx.Response(200, text="450.0", request=request)
            diagnostics_started.set()
            await diagnostics_release.wait()
            return httpx.Response(200, text="0", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            started = time.perf_counter()
            await spot_api._refresh_spot_temperature(client, schedule_diagnostics=True)
            elapsed = time.perf_counter() - started
            first_snapshot = spot_api.get_spot_temperature_poll_snapshot()
            await asyncio.wait_for(diagnostics_started.wait(), timeout=1.0)
            diagnostics_release.set()
            task = spot_api._spot_diagnostics_task
            assert task is not None
            await task
            await spot_api._refresh_spot_temperature(client)

        self.assertLess(elapsed, 0.1)
        self.assertIsNotNone(first_snapshot)
        assert first_snapshot is not None
        self.assertEqual(first_snapshot["diagnostics_capture_status"], "missing")
        second_snapshot = spot_api.get_spot_temperature_poll_snapshot()
        self.assertIsNotNone(second_snapshot)
        assert second_snapshot is not None
        self.assertEqual(second_snapshot["diagnostics_binding_status"], "previous_poll")
        self.assertEqual(second_snapshot["diagnostics_source_poll_seq"], 1)
        self.assertEqual(second_snapshot["spot_poll_seq"], 2)

    async def test_partial_diagnostics_record_per_field_status(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/output?p=temperature"

        async def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url).endswith("p=d1temperature"):
                return httpx.Response(503, text="busy", request=request)
            return httpx.Response(200, text="0", request=request)

        context = spot_api.SpotPollContext(
            service_instance_id="test-spot-service-instance",
            poll_seq=4,
            started_at_epoch=time.time(),
            started_monotonic=time.monotonic(),
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await spot_api._refresh_spot_diagnostics(
                client,
                context,
                collection_mode="async_same_poll",
            )

        with spot_api._spot_diagnostics_lock:
            snapshot = dict(spot_api._spot_diagnostics_snapshot or {})
        self.assertEqual(snapshot["diagnostics_capture_status"], "async_partial")
        self.assertEqual(snapshot["diagnostics_source_poll_seq"], 4)
        self.assertEqual(snapshot["diagnostics_field_status"]["d1temperature"], "http_error")
        self.assertIn("d1temperature", snapshot["diagnostics_missing_fields"])

    async def test_parse_failure_preserves_bounded_raw_value_outside_operational_payload(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/output?p=temperature"

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.params.get("p") == "signalpc":
                return httpx.Response(200, text="6553.4", request=request)
            if request.url.params.get("p") == "appnumber":
                self.assertEqual(request.url.path, "/control")
                return httpx.Response(200, text="7", request=request)
            return httpx.Response(200, text="0", request=request)

        context = spot_api.SpotPollContext(
            service_instance_id="test-spot-service-instance",
            poll_seq=5,
            started_at_epoch=time.time(),
            started_monotonic=time.monotonic(),
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await spot_api._refresh_spot_diagnostics(client, context)

        with spot_api._spot_diagnostics_lock:
            snapshot = dict(spot_api._spot_diagnostics_snapshot or {})
        self.assertEqual(snapshot["diagnostics_capture_status"], "async_partial")
        self.assertEqual(snapshot["diagnostics_field_status"]["signalpc"], "parse_error")
        self.assertIn("signalpc", snapshot["diagnostics_missing_fields"])
        self.assertNotIn("signalpc", snapshot)
        self.assertEqual(snapshot["diagnostics_raw_values"]["signalpc"], "6553.4")
        self.assertEqual(snapshot["appnumber"], "7")

    async def test_serialized_diagnostics_failure_does_not_change_temperature_poll_status(self) -> None:
        spot_api.config.SPOT_URL = "http://spot.local/output?p=temperature"

        async def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url).endswith("p=temperature"):
                await asyncio.sleep(0.02)
                return httpx.Response(200, text="450.0", request=request)
            raise httpx.ConnectError("diagnostics unavailable", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await spot_api._refresh_spot_temperature(client, schedule_diagnostics=True)
            task = spot_api._spot_diagnostics_task
            if task is not None:
                await task

        snapshot = spot_api.get_spot_temperature_poll_snapshot()
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot["spot_poll_status"], "success")
        self.assertEqual(snapshot["spot_raw_validity"], "valid_temperature")
        self.assertEqual(snapshot["diagnostics_capture_status"], "missing")
        self.assertEqual(snapshot["diagnostics_binding_status"], "missing")
        with spot_api._spot_diagnostics_lock:
            diagnostics = dict(spot_api._spot_diagnostics_snapshot or {})
        self.assertEqual(diagnostics["diagnostics_capture_status"], "error")
        self.assertEqual(diagnostics["diagnostics_source_poll_seq"], snapshot["spot_poll_seq"])
        self.assertTrue(
            all(
                status == "http_error"
                for status in diagnostics["diagnostics_field_status"].values()
            )
        )

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

        diagnostics: dict[str, Any] = spot_api.get_spot_diagnostics()

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
        spot_api._temperature_cache["temp_time"] = stale_epoch
        with spot_api._spot_temperature_snapshot_lock:
            assert spot_api._spot_temperature_snapshot is not None
            spot_api._spot_temperature_snapshot["_spot_last_poll_completed_at_epoch"] = stale_epoch
            spot_api._spot_temperature_snapshot["_spot_last_poll_completed_monotonic"] = stale_monotonic
            spot_api._spot_last_valid_value_at = stale_epoch

        diagnostics: dict[str, Any] = spot_api.get_spot_diagnostics()

        self.assertEqual(diagnostics["spot_source_freshness"], "stale")
        self.assertEqual(diagnostics["temperature_status_shadow"], "unknown_missing")
        self.assertEqual(diagnostics["temperature_value_origin"], "none")
        self.assertEqual(diagnostics["spot_cache_status"], "available_not_used")
        self.assertIsNone(diagnostics["spot_temperature_effective_c"])
        self.assertIsNotNone(diagnostics["spot_last_valid_value_monotonic"])
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
        spot_api._temperature_cache["temp_time"] = stale_epoch
        with spot_api._spot_temperature_snapshot_lock:
            assert spot_api._spot_temperature_snapshot is not None
            spot_api._spot_temperature_snapshot["_spot_last_poll_completed_at_epoch"] = stale_epoch
            spot_api._spot_temperature_snapshot["_spot_last_poll_completed_monotonic"] = stale_monotonic

        diagnostics: dict[str, Any] = spot_api.get_spot_diagnostics()

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

        diagnostics: dict[str, Any] = spot_api.get_spot_diagnostics()

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

        diagnostics = spot_api.get_spot_diagnostics()

        self.assertEqual(diagnostics["spot_poll_status"], "timeout")
        self.assertTrue(diagnostics["cache_fallback_allowed"])
        self.assertEqual(diagnostics["temperature_value_origin"], "cached_observation")
        self.assertEqual(diagnostics["spot_cache_status"], "reused")
        self.assertEqual(diagnostics["spot_temperature_effective_c"], 510.0)
        self.assertIsNotNone(diagnostics["spot_last_valid_value_monotonic"])

    async def test_temperature_timeout_diagnostics_have_non_empty_message_and_status(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaises(spot_api.SpotTemperatureFetchError) as raised:
                await spot_api._request_spot_temperature(client, "http://spot.local/temp")

        error = raised.exception
        spot_api._record_temperature_error(error.code, str(error), error.temp_url, error.upstream_status)

        diagnostics: dict[str, Any] = spot_api.get_spot_diagnostics()

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
        self.assertEqual(error.transport_error_type, "ReadTimeout")
        self.assertIsNotNone(error.request_elapsed_ms)
        self.assertGreaterEqual(float(error.request_elapsed_ms), 0.0)

    async def test_image_request_uses_image_specific_connect_timeout(self) -> None:
        image_bytes = b"\xff\xd8image-data\xff\xd9"
        request_timeouts: list[dict[str, float]] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            request_timeouts.append(dict(request.extensions["timeout"]))
            return httpx.Response(200, content=image_bytes, request=request)

        transport = httpx.MockTransport(handler)
        client_timeout = httpx.Timeout(connect=0.1, read=0.1, write=0.1, pool=0.1)
        async with httpx.AsyncClient(transport=transport, timeout=client_timeout) as client:
            data = await spot_api._request_spot_image(client, "http://spot.local/image.jpg")

        self.assertEqual(data, image_bytes)
        self.assertEqual(len(request_timeouts), 1)
        self.assertEqual(request_timeouts[0]["connect"], 2.0)
        self.assertEqual(request_timeouts[0]["read"], 5.0)
        self.assertEqual(request_timeouts[0]["write"], 1.0)
        self.assertEqual(request_timeouts[0]["pool"], 5.0)

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

    def test_error_summary_groups_source_type_status_path_and_repeat(self) -> None:
        from backend.Observability.service import ObservabilityService

        service = ObservabilityService(window_sec=60.0, max_requests=100, max_errors=20)

        service.record_error(
            "spot_image",
            "SPOT image upstream failure",
            path="/api/spot/image.jpg",
            status_code=502,
            error_type="upstream-timeout",
        )
        service.record_error(
            "spot_image",
            "SPOT image upstream failure",
            path="/api/spot/image.jpg",
            status_code=502,
            error_type="upstream-timeout",
        )

        summary = service.get_error_summary()

        self.assertEqual(summary["queue_size"], 1)
        self.assertEqual(summary["repeat_total"], 2)
        self.assertEqual(summary["source_repeat_counts"]["spot_image"], 2)
        self.assertEqual(summary["type_counts"]["upstream-timeout"], 2)
        self.assertEqual(summary["status_counts"]["502"], 2)
        self.assertEqual(summary["path_counts"]["/api/spot/image.jpg"], 2)
        self.assertEqual(summary["route_status_counts"]["/api/spot/image.jpg 502"], 2)

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

    async def test_control_shutdown_drains_image_writer_before_final_manifest(self) -> None:
        from backend import app as backend_app

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="all")
            spot_api.config.SPOT_IP = "spot.local"
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
                await spot_api.fetch_image_async()
                self.assertTrue(write_started.wait(timeout=1.0))

                release_thread = threading.Thread(target=lambda: (time.sleep(0.05), release_write.set()))
                release_thread.start()
                with (
                    patch.object(backend_app, "logger_service", final_manifest_logger),
                    patch.object(backend_app.plc_service, "stop", Mock(return_value=True)),
                    patch.object(backend_app.comm_metrics_logger_service, "stop", Mock(return_value=True)),
                    patch.object(backend_app.memory_service, "stop", Mock(return_value=True)),
                    patch.object(backend_app.config_sync_agent, "stop", Mock(return_value=True)),
                    patch.object(backend_app.config_watch_service, "stop", Mock(return_value=True)),
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

    async def test_shutdown_helper_fails_when_queued_capture_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="all")
            event = spot_api._SpotImageCaptureEvent(
                image_bytes=b"\xff\xd8failed-shutdown-write\xff\xd9",
                captured_at=time.time(),
                source_url="http://spot.local/live.jpg",
                source="test_shutdown_failure",
                image_age_ms=0.0,
                link_checked_at=None,
                observation_snapshot=None,
            )
            spot_api._SPOT_IMAGE_CAPTURE_QUEUE.put_nowait(event)
            with spot_api._spot_image_capture_lock:
                spot_api._spot_image_capture_enqueued_count += 1

            original_task_done = spot_api._SPOT_IMAGE_CAPTURE_QUEUE.task_done
            outcome_and_task_done_are_atomic = False

            def assert_atomic_task_done() -> None:
                nonlocal outcome_and_task_done_are_atomic
                acquired = spot_api._spot_image_capture_lock.acquire(blocking=False)
                if acquired:
                    spot_api._spot_image_capture_lock.release()
                outcome_and_task_done_are_atomic = (
                    not acquired and spot_api._spot_image_capture_failure_count == 1
                )
                original_task_done()

            with patch.object(
                SpotImageCaptureWriter,
                "write_capture",
                side_effect=RuntimeError("simulated capture write failure"),
            ), patch.object(
                spot_api._SPOT_IMAGE_CAPTURE_QUEUE,
                "task_done",
                side_effect=assert_atomic_task_done,
            ):
                drained = spot_api.stop_spot_image_capture_for_shutdown(timeout_sec=2.0)
            health = spot_api.get_spot_image_capture_health()

        self.assertFalse(drained)
        self.assertEqual(health["failure_count"], 1)
        self.assertTrue(outcome_and_task_done_are_atomic)

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
                    source="official_image_jpg",
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

    def test_image_capture_writer_does_not_scan_history_for_new_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            capture_root = log_path / "spot_images"
            historical_captured_at = time.time()
            historical_image_bytes = b"\xff\xd8historical-capture\xff\xd9"
            first_writer = SpotImageCaptureWriter(log_path=log_path, capture_root=capture_root)
            first_writer.write_capture(
                image_bytes=historical_image_bytes,
                captured_at=historical_captured_at,
                source_url="http://spot.local/image.jpg",
                source="test",
                image_age_ms=0.0,
                link_checked_at=None,
                observation_snapshot=None,
            )
            historical_fact_mtime = time.time() - 10.0
            os.utime(
                first_writer.fact_path,
                (historical_fact_mtime, historical_fact_mtime),
            )

            restarted_writer = SpotImageCaptureWriter(log_path=log_path, capture_root=capture_root)
            with patch.object(
                restarted_writer,
                "_load_known_facts_by_capture_id",
                side_effect=AssertionError("new capture must not scan historical facts"),
            ):
                first_current_fact = restarted_writer.write_capture(
                    image_bytes=b"\xff\xd8new-capture\xff\xd9",
                    captured_at=historical_fact_mtime + 1.0,
                    source_url="http://spot.local/image.jpg",
                    source="test",
                    image_age_ms=0.0,
                    link_checked_at=None,
                    observation_snapshot=None,
                )
                (log_path / first_current_fact["spot_image_path"]).unlink()
                duplicate_current_fact = restarted_writer.write_capture(
                    image_bytes=b"\xff\xd8new-capture\xff\xd9",
                    captured_at=historical_fact_mtime + 1.0,
                    source_url="http://spot.local/image.jpg",
                    source="test",
                    image_age_ms=0.0,
                    link_checked_at=None,
                    observation_snapshot=None,
                )
                restarted_writer.write_capture(
                    image_bytes=b"\xff\xd8queued-new-capture\xff\xd9",
                    captured_at=historical_fact_mtime + 2.0,
                    source_url="http://spot.local/image.jpg",
                    source="test",
                    image_age_ms=0.0,
                    link_checked_at=None,
                    observation_snapshot=None,
                )
            restarted_writer.write_capture(
                image_bytes=historical_image_bytes,
                captured_at=historical_captured_at,
                source_url="http://spot.local/image.jpg",
                source="test",
                image_age_ms=0.0,
                link_checked_at=None,
                observation_snapshot=None,
            )

            rows = self.read_spot_image_fact_rows(log_path)

        self.assertEqual(len(rows), 3)
        self.assertEqual(duplicate_current_fact, first_current_fact)

    def test_event_mode_captures_under_range_snapshot_and_skips_valid_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            self.configure_image_capture(log_path, mode="event")
            spot_api.config.SPOT_IP = "spot.local"
            image_bytes = b"\xff\xd8event-capture\xff\xd9"

            self.set_spot_temperature_snapshot(spot_poll_seq=1, spot_raw_validity="valid_temperature")
            spot_api._maybe_enqueue_spot_image_capture(
                image_bytes=image_bytes,
                captured_at=time.time(),
                image_url="http://spot.local/image.jpg",
                source="official_image_jpg",
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
                source="official_image_jpg",
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
                source="official_image_jpg",
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
                source="official_image_jpg",
                image_age_ms=0.0,
            )
            self.assertTrue(spot_api.flush_spot_image_capture_queue(timeout_sec=2.0))

            spot_api.config.SPOT_IMAGE_CAPTURE_PATH = "spot_images_b"
            spot_api._maybe_enqueue_spot_image_capture(
                image_bytes=image_bytes,
                captured_at=time.time(),
                image_url="http://spot.local/image.jpg",
                source="official_image_jpg",
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

    async def test_official_image_resource_is_cached_for_the_configured_interval(self) -> None:
        spot_api.config.SPOT_IP = "spot.local"
        spot_api.config.SPOT_REFRESH_INTERVAL = 3.0
        image_bytes = b"\xff\xd8official-image\xff\xd9"
        request_mock = AsyncMock(return_value=image_bytes)

        with patch.object(spot_api, "_request_spot_image", request_mock):
            first_data, first_meta = await spot_api.fetch_image_async()
            cached_results = await asyncio.gather(
                *(spot_api.fetch_image_async() for _ in range(20))
            )

        self.assertEqual(first_data, image_bytes)
        self.assertTrue(all(data == image_bytes for data, _meta in cached_results))
        self.assertEqual(request_mock.await_count, 1)
        self.assertEqual(request_mock.await_args_list[0].args[1], "http://spot.local/image.jpg")
        self.assertEqual(first_meta["image_path"], "/image.jpg")
        self.assertEqual(first_meta["source"], "upstream")
        self.assertTrue(all(meta["source"] == "cache" for _data, meta in cached_results))
        self.assertTrue(
            all(meta["captured_at"] == first_meta["captured_at"] for _data, meta in cached_results)
        )
        self.assertTrue(all(meta["age_ms"] >= 0.0 for _data, meta in cached_results))
        diagnostics = spot_api.get_spot_diagnostics()
        self.assertEqual(diagnostics["image_cache_hit_count"], 20)
        self.assertEqual(diagnostics["image_downstream_request_count"], 21)

    async def test_image_cache_is_not_reused_after_spot_ip_changes(self) -> None:
        spot_api.config.SPOT_IP = "spot-a.local"
        spot_api.config.SPOT_REFRESH_INTERVAL = 10.0

        async def request_image(_client: httpx.AsyncClient, image_url: str) -> bytes:
            if image_url == "http://spot-a.local/image.jpg":
                return b"\xff\xd8spot-a\xff\xd9"
            if image_url == "http://spot-b.local/image.jpg":
                return b"\xff\xd8spot-b\xff\xd9"
            self.fail(f"unexpected image URL: {image_url}")

        with patch.object(
            spot_api,
            "_request_spot_image",
            side_effect=request_image,
        ) as request_mock:
            first_data, _first_meta = await spot_api.fetch_image_async()
            spot_api.config.SPOT_IP = "spot-b.local"
            second_data, second_meta = await spot_api.fetch_image_async()

        self.assertEqual(first_data, b"\xff\xd8spot-a\xff\xd9")
        self.assertEqual(second_data, b"\xff\xd8spot-b\xff\xd9")
        self.assertEqual(second_meta["source"], "upstream")
        self.assertEqual(
            [call.args[1] for call in request_mock.await_args_list],
            [
                "http://spot-a.local/image.jpg",
                "http://spot-b.local/image.jpg",
            ],
        )
        self.assertIsNotNone(spot_api._img_cache_entry)
        assert spot_api._img_cache_entry is not None
        self.assertEqual(
            spot_api._img_cache_entry.image_url,
            "http://spot-b.local/image.jpg",
        )

    async def test_inflight_image_refresh_does_not_cross_spot_ip_changes(self) -> None:
        spot_api.config.SPOT_IP = "spot-a.local"
        first_refresh_started = asyncio.Event()
        release_first_refresh = asyncio.Event()

        async def request_image(_client: httpx.AsyncClient, image_url: str) -> bytes:
            if image_url == "http://spot-a.local/image.jpg":
                first_refresh_started.set()
                await release_first_refresh.wait()
                return b"\xff\xd8spot-a\xff\xd9"
            if image_url == "http://spot-b.local/image.jpg":
                return b"\xff\xd8spot-b\xff\xd9"
            self.fail(f"unexpected image URL: {image_url}")

        with patch.object(
            spot_api,
            "_request_spot_image",
            side_effect=request_image,
        ) as request_mock:
            first_caller = asyncio.create_task(spot_api.fetch_image_async())
            await first_refresh_started.wait()
            spot_api.config.SPOT_IP = "spot-b.local"
            second_caller = asyncio.create_task(spot_api.fetch_image_async())
            await asyncio.sleep(0)
            release_first_refresh.set()
            results = await asyncio.gather(first_caller, second_caller)

        self.assertEqual(
            [data for data, _meta in results],
            [b"\xff\xd8spot-b\xff\xd9", b"\xff\xd8spot-b\xff\xd9"],
        )
        self.assertEqual(
            [call.args[1] for call in request_mock.await_args_list],
            [
                "http://spot-a.local/image.jpg",
                "http://spot-b.local/image.jpg",
            ],
        )
        self.assertEqual(
            {meta["source"] for _data, meta in results},
            {"upstream", "coalesced"},
        )

    def test_image_cache_freshness_uses_normalized_interval_and_strict_boundary(self) -> None:
        entry = spot_api._SpotImageCacheEntry(
            image_bytes=b"\xff\xd8boundary\xff\xd9",
            captured_at_epoch=100.0,
            captured_at_monotonic=10.0,
            upstream_latency_ms=5.0,
        )

        spot_api.config.SPOT_REFRESH_INTERVAL = 0.25
        self.assertEqual(spot_api._spot_image_refresh_interval_sec(), 3.0)
        self.assertTrue(spot_api._is_spot_image_cache_fresh(entry, now_monotonic=12.999))
        self.assertFalse(spot_api._is_spot_image_cache_fresh(entry, now_monotonic=13.0))

        spot_api.config.SPOT_REFRESH_INTERVAL = 30.0
        self.assertEqual(spot_api._spot_image_refresh_interval_sec(), 10.0)

        spot_api.config.SPOT_REFRESH_INTERVAL = float("nan")
        self.assertEqual(spot_api._spot_image_refresh_interval_sec(), 3.0)
        self.assertFalse(
            spot_api._is_spot_image_cache_fresh(
                entry,
                now_monotonic=9.0,
                record_clock_anomaly=True,
            )
        )
        self.assertEqual(spot_api.get_spot_diagnostics()["image_cache_clock_anomaly_count"], 1)

    def test_background_request_budget_stays_below_field_gate_at_fastest_poll(self) -> None:
        spot_api.config.SPOT_IP = "spot.local"
        spot_api.config.SPOT_URL = "http://spot.local/output?p=temperature"
        spot_api.config.SPOT_INTERNAL_TEMPERATURE_URL = (
            "http://spot.local/output?p=itemperature"
        )
        spot_api.config.SPOT_REFRESH_INTERVAL = 0.25

        diagnostics = spot_api.get_spot_diagnostics()

        self.assertEqual(
            diagnostics["request_budget_policy_version"],
            "spot-background-request-budget-v2",
        )
        self.assertEqual(
            diagnostics["image_request_policy_version"],
            "spot-image-demand-shaping-v2",
        )
        self.assertEqual(diagnostics["image_refresh_interval_sec_effective"], 3.0)
        self.assertEqual(diagnostics["diagnostics_refresh_interval_sec_effective"], 10.0)
        self.assertEqual(spot_api._spot_diagnostics_max_age_sec(), 20.0)
        self.assertEqual(diagnostics["request_budget_image_max_per_sec"], 0.333333)
        self.assertEqual(diagnostics["request_budget_temperature_max_per_sec"], 2.0)
        self.assertEqual(
            diagnostics["request_budget_internal_temperature_max_per_sec"],
            2.0,
        )
        self.assertEqual(diagnostics["request_budget_diagnostics_max_per_sec"], 0.8)
        self.assertEqual(
            diagnostics["request_budget_total_background_max_per_sec"],
            5.133333,
        )
        self.assertTrue(diagnostics["request_budget_within_target"])

    async def test_official_image_requests_are_single_flight(self) -> None:
        spot_api.config.SPOT_IP = "spot.local"
        spot_api.config.SPOT_REFRESH_INTERVAL = 3.0
        image_bytes = b"\xff\xd8single-flight\xff\xd9"
        active_requests = 0
        maximum_active_requests = 0

        async def request_image(client: httpx.AsyncClient, image_url: str) -> bytes:
            nonlocal active_requests, maximum_active_requests
            self.assertEqual(image_url, "http://spot.local/image.jpg")
            active_requests += 1
            maximum_active_requests = max(maximum_active_requests, active_requests)
            await asyncio.sleep(0.01)
            active_requests -= 1
            return image_bytes

        with (
            patch.object(spot_api, "_request_spot_image", side_effect=request_image) as request_mock,
            patch.object(spot_api, "_maybe_enqueue_spot_image_capture") as enqueue_mock,
        ):
            results = await asyncio.gather(
                *(spot_api.fetch_image_async() for _ in range(20))
            )

        self.assertTrue(all(data == image_bytes for data, _meta in results))
        self.assertEqual(request_mock.await_count, 1)
        self.assertEqual(maximum_active_requests, 1)
        sources = [meta["source"] for _data, meta in results]
        self.assertEqual(sources.count("upstream"), 1)
        self.assertEqual(sources.count("coalesced"), 19)
        enqueue_mock.assert_called_once()
        diagnostics = spot_api.get_spot_diagnostics()
        self.assertEqual(diagnostics["image_singleflight_leader_count"], 1)
        self.assertEqual(diagnostics["image_coalesced_waiter_count"], 19)
        self.assertEqual(diagnostics["image_upstream_request_count"], 1)
        self.assertEqual(diagnostics["image_downstream_request_count"], 20)

    async def test_expired_image_cache_refreshes_without_serving_stale_on_error(self) -> None:
        spot_api.config.SPOT_IP = "spot.local"
        spot_api.config.SPOT_REFRESH_INTERVAL = 1.0
        image_bytes = b"\xff\xd8first-image\xff\xd9"
        upstream_error = spot_api.SpotImageFetchError(
            "upstream-timeout",
            "timed out",
            image_url="http://spot.local/image.jpg",
            upstream_status=None,
        )
        request_mock = AsyncMock(side_effect=[image_bytes, upstream_error])

        with patch.object(spot_api, "_request_spot_image", request_mock):
            first_data, _first_meta = await spot_api.fetch_image_async()
            cached = spot_api._img_cache_entry
            self.assertIsNotNone(cached)
            assert cached is not None
            spot_api._img_cache_entry = spot_api._SpotImageCacheEntry(
                image_bytes=cached.image_bytes,
                captured_at_epoch=cached.captured_at_epoch,
                captured_at_monotonic=cached.captured_at_monotonic - 4.0,
                upstream_latency_ms=cached.upstream_latency_ms,
            )
            with self.assertRaises(spot_api.SpotImageFetchError):
                await spot_api.fetch_image_async()

        self.assertEqual(first_data, image_bytes)
        self.assertEqual(request_mock.await_count, 2)
        diagnostics = spot_api.get_spot_diagnostics()
        self.assertFalse(diagnostics["image_cache_fresh"])
        self.assertEqual(diagnostics["image_refresh_success_count"], 1)
        self.assertEqual(diagnostics["image_refresh_failure_count"], 1)
        self.assertEqual(diagnostics["failure_count"], 1)

    async def test_failed_image_refresh_recovers_with_the_next_shared_refresh(self) -> None:
        spot_api.config.SPOT_IP = "spot.local"
        spot_api.config.SPOT_REFRESH_INTERVAL = 1.0
        first_image = b"\xff\xd8first-image\xff\xd9"
        recovered_image = b"\xff\xd8recovered-image\xff\xd9"
        recovery_started = asyncio.Event()
        release_recovery = asyncio.Event()
        upstream_error = spot_api.SpotImageFetchError(
            "upstream-timeout",
            "timed out",
            image_url="http://spot.local/image.jpg",
            upstream_status=None,
        )

        async def request_image(client: httpx.AsyncClient, image_url: str) -> bytes:
            call_number = request_mock.await_count
            if call_number == 1:
                return first_image
            if call_number == 2:
                raise upstream_error
            recovery_started.set()
            await release_recovery.wait()
            return recovered_image

        request_mock = AsyncMock(side_effect=request_image)

        with patch.object(spot_api, "_request_spot_image", request_mock):
            await spot_api.fetch_image_async()
            cached = spot_api._img_cache_entry
            self.assertIsNotNone(cached)
            assert cached is not None
            spot_api._img_cache_entry = spot_api._SpotImageCacheEntry(
                image_bytes=cached.image_bytes,
                captured_at_epoch=cached.captured_at_epoch,
                captured_at_monotonic=cached.captured_at_monotonic - 4.0,
                upstream_latency_ms=cached.upstream_latency_ms,
            )

            with self.assertRaises(spot_api.SpotImageFetchError):
                await spot_api.fetch_image_async()
            recovery_leader = asyncio.create_task(spot_api.fetch_image_async())
            await recovery_started.wait()
            recovery_waiter = asyncio.create_task(spot_api.fetch_image_async())
            await asyncio.sleep(0)
            release_recovery.set()
            recovered_results = await asyncio.gather(recovery_leader, recovery_waiter)

        self.assertEqual([result[0] for result in recovered_results], [recovered_image] * 2)
        self.assertEqual(
            {result[1]["source"] for result in recovered_results},
            {"upstream", "coalesced"},
        )
        self.assertEqual(request_mock.await_count, 3)
        self.assertIsNotNone(spot_api._img_cache_entry)
        assert spot_api._img_cache_entry is not None
        self.assertEqual(spot_api._img_cache_entry.image_bytes, recovered_image)
        diagnostics = spot_api.get_spot_diagnostics()
        self.assertEqual(diagnostics["image_refresh_success_count"], 2)
        self.assertEqual(diagnostics["image_refresh_failure_count"], 1)
        self.assertEqual(diagnostics["image_coalesced_waiter_count"], 1)
        self.assertEqual(diagnostics["failure_count"], 0)

    async def test_second_cache_check_is_not_counted_as_a_coalesced_waiter(self) -> None:
        spot_api.config.SPOT_IP = "spot.local"
        cached_entry = spot_api._SpotImageCacheEntry(
            image_bytes=b"\xff\xd8racing-cache-hit\xff\xd9",
            captured_at_epoch=time.time(),
            captured_at_monotonic=time.monotonic(),
            upstream_latency_ms=4.0,
        )
        spot_api._img_cache_entry = cached_entry

        with (
            patch.object(
                spot_api,
                "_is_spot_image_cache_fresh",
                side_effect=[False, True],
            ) as freshness_mock,
            patch.object(spot_api, "_request_spot_image", AsyncMock()) as request_mock,
        ):
            image_data, metadata = await spot_api.fetch_image_async()

        self.assertEqual(image_data, cached_entry.image_bytes)
        self.assertEqual(metadata["source"], "cache")
        self.assertEqual(freshness_mock.call_count, 2)
        request_mock.assert_not_awaited()
        diagnostics = spot_api.get_spot_diagnostics()
        self.assertEqual(diagnostics["image_cache_hit_count"], 1)
        self.assertEqual(diagnostics["image_coalesced_waiter_count"], 0)
        self.assertEqual(diagnostics["image_upstream_request_count"], 0)

    async def test_shared_image_refresh_failure_is_recorded_once_for_all_waiters(self) -> None:
        spot_api.config.SPOT_IP = "spot.local"
        refresh_started = asyncio.Event()
        release_refresh = asyncio.Event()

        async def fail_refresh(client: httpx.AsyncClient, image_url: str) -> bytes:
            refresh_started.set()
            await release_refresh.wait()
            raise spot_api.SpotImageFetchError(
                "upstream-timeout",
                "timed out",
                image_url=image_url,
                upstream_status=None,
            )

        with patch.object(spot_api, "_request_spot_image", side_effect=fail_refresh) as request_mock:
            first_task = asyncio.create_task(spot_api.fetch_image_async())
            await refresh_started.wait()
            waiter_tasks = [
                asyncio.create_task(spot_api.fetch_image_async())
                for _ in range(19)
            ]
            await asyncio.sleep(0)
            release_refresh.set()
            results = await asyncio.gather(first_task, *waiter_tasks, return_exceptions=True)

        self.assertTrue(all(isinstance(result, spot_api.SpotImageFetchError) for result in results))
        self.assertEqual(request_mock.await_count, 1)
        diagnostics = spot_api.get_spot_diagnostics()
        self.assertEqual(diagnostics["image_refresh_failure_count"], 1)
        self.assertEqual(diagnostics["failure_count"], 1)
        self.assertEqual(diagnostics["image_coalesced_waiter_count"], 19)

    async def test_cancelling_one_image_waiter_does_not_cancel_shared_refresh(self) -> None:
        spot_api.config.SPOT_IP = "spot.local"
        image_bytes = b"\xff\xd8shielded-image\xff\xd9"
        refresh_started = asyncio.Event()
        release_refresh = asyncio.Event()

        async def request_image(client: httpx.AsyncClient, image_url: str) -> bytes:
            refresh_started.set()
            await release_refresh.wait()
            return image_bytes

        with patch.object(spot_api, "_request_spot_image", side_effect=request_image) as request_mock:
            cancelled_waiter = asyncio.create_task(spot_api.fetch_image_async())
            await refresh_started.wait()
            surviving_waiter = asyncio.create_task(spot_api.fetch_image_async())
            await asyncio.sleep(0)
            cancelled_waiter.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await cancelled_waiter
            release_refresh.set()
            surviving_result = await surviving_waiter

        self.assertEqual(surviving_result[0], image_bytes)
        self.assertEqual(surviving_result[1]["source"], "coalesced")
        self.assertEqual(request_mock.await_count, 1)
        self.assertEqual(spot_api.get_spot_diagnostics()["image_refresh_success_count"], 1)

    async def test_cancelling_all_image_waiters_still_publishes_the_shared_result(self) -> None:
        spot_api.config.SPOT_IP = "spot.local"
        image_bytes = b"\xff\xd8background-result\xff\xd9"
        refresh_started = asyncio.Event()
        release_refresh = asyncio.Event()

        async def request_image(client: httpx.AsyncClient, image_url: str) -> bytes:
            refresh_started.set()
            await release_refresh.wait()
            return image_bytes

        with patch.object(spot_api, "_request_spot_image", side_effect=request_image) as request_mock:
            leader = asyncio.create_task(spot_api.fetch_image_async())
            await refresh_started.wait()
            waiters = [
                asyncio.create_task(spot_api.fetch_image_async())
                for _ in range(4)
            ]
            await asyncio.sleep(0)
            for task in (leader, *waiters):
                task.cancel()
            cancelled_results = await asyncio.gather(leader, *waiters, return_exceptions=True)
            self.assertTrue(all(isinstance(result, asyncio.CancelledError) for result in cancelled_results))

            refresh_task = spot_api._img_refresh_task
            self.assertIsNotNone(refresh_task)
            release_refresh.set()
            assert refresh_task is not None
            published_entry = await refresh_task
            cached_data, cached_meta = await spot_api.fetch_image_async()

        self.assertEqual(published_entry.image_bytes, image_bytes)
        self.assertEqual(cached_data, image_bytes)
        self.assertEqual(cached_meta["source"], "cache")
        self.assertEqual(request_mock.await_count, 1)
        self.assertEqual(spot_api.get_spot_diagnostics()["image_refresh_success_count"], 1)

    async def test_completed_refresh_cleanup_preserves_a_replacement_task(self) -> None:
        spot_api.config.SPOT_IP = "spot.local"
        image_bytes = b"\xff\xd8completed-refresh\xff\xd9"
        refresh_started = asyncio.Event()
        release_refresh = asyncio.Event()
        release_replacement = asyncio.Event()

        async def request_image(client: httpx.AsyncClient, image_url: str) -> bytes:
            refresh_started.set()
            await release_refresh.wait()
            return image_bytes

        async def replacement_refresh() -> spot_api._SpotImageCacheEntry:
            await release_replacement.wait()
            return spot_api._SpotImageCacheEntry(
                image_bytes=b"\xff\xd8replacement\xff\xd9",
                captured_at_epoch=time.time(),
                captured_at_monotonic=time.monotonic(),
                upstream_latency_ms=1.0,
            )

        with patch.object(spot_api, "_request_spot_image", side_effect=request_image):
            first_caller = asyncio.create_task(spot_api.fetch_image_async())
            await refresh_started.wait()
            first_refresh = spot_api._img_refresh_task
            self.assertIsNotNone(first_refresh)

            await spot_api._img_fetch_lock.acquire()
            try:
                release_refresh.set()
                assert first_refresh is not None
                await asyncio.wait_for(asyncio.shield(first_refresh), timeout=1.0)
                replacement_task = asyncio.create_task(replacement_refresh())
                spot_api._img_refresh_task = replacement_task
            finally:
                spot_api._img_fetch_lock.release()

            first_result = await first_caller
            self.assertEqual(first_result[0], image_bytes)
            self.assertIs(spot_api._img_refresh_task, replacement_task)
            release_replacement.set()
            await replacement_task

    async def test_image_refresh_shutdown_is_bounded_and_rejects_new_work(self) -> None:
        spot_api.config.SPOT_IP = "spot.local"
        refresh_started = asyncio.Event()

        async def never_complete(client: httpx.AsyncClient, image_url: str) -> bytes:
            refresh_started.set()
            await asyncio.Event().wait()
            return b"unreachable"

        with patch.object(spot_api, "_request_spot_image", side_effect=never_complete) as request_mock:
            caller_task = asyncio.create_task(spot_api.fetch_image_async())
            await refresh_started.wait()
            drained = await spot_api._stop_spot_image_refresh_for_shutdown(timeout_sec=0.01)
            with self.assertRaises(asyncio.CancelledError):
                await caller_task
            with self.assertRaises(spot_api.SpotImageFetchError) as stopped_context:
                await spot_api.fetch_image_async()

        self.assertTrue(drained)
        self.assertEqual(stopped_context.exception.code, "shutdown")
        self.assertEqual(request_mock.await_count, 1)
        self.assertFalse(spot_api.get_spot_diagnostics()["image_accepting_requests"])

    async def test_guarded_transport_routes_background_requests_by_kind(self) -> None:
        transport = FakeSpotHttpTransport()
        spot_api._spot_http_transport = transport
        client = AsyncMock(spec=httpx.AsyncClient)

        image = await spot_api._request_spot_image(
            client,
            "http://spot.local/image.jpg",
        )
        temperature = await spot_api._request_spot_temperature(
            client,
            "http://spot.local/output?p=temperature",
        )
        internal_temperature = await spot_api._request_spot_internal_temperature(
            client,
            "http://spot.local/output?p=internal",
        )
        param, diagnostic = await spot_api._request_spot_diagnostic_output(
            client,
            "alarmstatus",
        )

        self.assertEqual(image, b"\xff\xd8guarded-image\xff\xd9")
        self.assertEqual(temperature, 451.25)
        self.assertEqual(internal_temperature, 451.25)
        self.assertEqual((param, diagnostic), ("alarmstatus", "7"))
        self.assertEqual(
            [request.kind for request in transport.requests],
            [
                spot_api.SpotRequestKind.IMAGE,
                spot_api.SpotRequestKind.TEMPERATURE,
                spot_api.SpotRequestKind.INTERNAL_TEMPERATURE,
                spot_api.SpotRequestKind.DIAGNOSTIC,
            ],
        )
        client.request.assert_not_awaited()

    async def test_guarded_transport_preserves_connect_and_read_timeout_types(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        cases = (
            (
                spot_api.SpotTransportConnectTimeout("connect timed out"),
                httpx.ConnectTimeout,
            ),
            (
                spot_api.SpotTransportReadTimeout("response timed out"),
                httpx.ReadTimeout,
            ),
        )

        try:
            for transport_error, expected_httpx_error in cases:
                with self.subTest(expected_httpx_error=expected_httpx_error.__name__):
                    transport = Mock(supported=True, active=True)
                    transport.request = AsyncMock(side_effect=transport_error)
                    spot_api._spot_http_transport = transport

                    with self.assertRaises(expected_httpx_error):
                        await spot_api._request_spot_http_response(
                            client,
                            kind=spot_api.SpotRequestKind.IMAGE,
                            method="GET",
                            url="http://spot.local/image.jpg",
                        )
        finally:
            spot_api._spot_http_transport = None

        client.request.assert_not_awaited()

    async def test_transport_test_reset_closes_and_clears_module_state(self) -> None:
        transport = FakeSpotHttpTransport()
        spot_api._spot_http_transport = transport

        await spot_api._reset_spot_http_transport_state_for_tests()

        self.assertIsNone(spot_api._spot_http_transport)
        self.assertFalse(transport.active)

    def test_guarded_transport_routes_focus_and_actuator_operations(self) -> None:
        transport = FakeSpotHttpTransport()
        spot_api._spot_http_transport = transport

        focus = spot_api._read_spot_focus_position("http://spot.local/focus")
        spot_api._write_spot_focus_position("http://spot.local/focus", 620)
        actuator = spot_api._read_spot_actuator_position("http://spot.local/actuator")
        spot_api._write_spot_actuator_position("http://spot.local/actuator", 400)

        self.assertEqual(focus, 600)
        self.assertEqual(actuator, 321)
        self.assertEqual(
            [request.kind for request in transport.requests],
            [
                spot_api.SpotRequestKind.FOCUS_READ,
                spot_api.SpotRequestKind.FOCUS_WRITE,
                spot_api.SpotRequestKind.ACTUATOR_READ,
                spot_api.SpotRequestKind.ACTUATOR_WRITE,
            ],
        )

    def test_spot_diagnostics_include_aggregate_source_port_policy(self) -> None:
        transport = FakeSpotHttpTransport()
        spot_api._spot_http_transport = transport
        diagnostics = spot_api.get_spot_diagnostics()

        self.assertEqual(
            diagnostics["source_port_policy_version"],
            "spot-source-port-quarantine-v2",
        )
        self.assertTrue(diagnostics["source_port_enforcement_supported"])
        self.assertTrue(diagnostics["source_port_enforcement_active"])
        self.assertEqual(diagnostics["source_port_quarantine_seconds"], 75.0)
        self.assertEqual(diagnostics["source_port_pool_capacity"], 768)
        self.assertNotIn("source_port_values", diagnostics)

    async def test_supported_but_inactive_transport_fails_closed(self) -> None:
        transport = FakeSpotHttpTransport()
        transport.active = False
        spot_api._spot_http_transport = transport
        client = AsyncMock(spec=httpx.AsyncClient)

        with self.assertRaises(spot_api.SpotImageFetchError) as raised:
            await spot_api._request_spot_image(
                client,
                "http://spot.local/image.jpg",
            )

        self.assertEqual(raised.exception.code, "upstream-request-error")
        client.request.assert_not_awaited()

    async def test_all_spot_device_http_requests_are_serialized(self) -> None:
        active_requests = 0
        maximum_active_requests = 0
        image_bytes = b"\xff\xd8serialized-device-image\xff\xd9"

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal active_requests, maximum_active_requests
            active_requests += 1
            maximum_active_requests = max(maximum_active_requests, active_requests)
            try:
                await asyncio.sleep(0.005)
                if request.url.path == "/image.jpg":
                    return httpx.Response(
                        200,
                        content=image_bytes,
                        headers={"Content-Type": "image/jpeg"},
                        request=request,
                    )
                if request.url.params.get("p") == "temperature":
                    return httpx.Response(200, text="450.0", request=request)
                return httpx.Response(200, text="0", request=request)
            finally:
                active_requests -= 1

        context = spot_api.SpotPollContext(
            service_instance_id="test-spot-service-instance",
            poll_seq=9,
            started_at_epoch=time.time(),
            started_monotonic=time.monotonic(),
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            image, temperature, _diagnostics = await asyncio.gather(
                spot_api._request_spot_image(client, "http://spot.local/image.jpg"),
                spot_api._request_spot_temperature(client, "http://spot.local/output?p=temperature"),
                spot_api._refresh_spot_diagnostics(client, context),
            )

        self.assertEqual(image, image_bytes)
        self.assertEqual(temperature, 450.0)
        self.assertEqual(maximum_active_requests, 1)
        with spot_api._spot_diagnostics_lock:
            diagnostics = dict(spot_api._spot_diagnostics_snapshot or {})
        self.assertEqual(diagnostics["diagnostics_capture_status"], "async_complete")
        self.assertEqual(diagnostics["diagnostics_source_poll_seq"], 9)

    async def test_cancelled_focus_keeps_device_gate_until_worker_finishes(self) -> None:
        focus_started = threading.Event()
        release_focus = threading.Event()
        image_started = asyncio.Event()
        image_bytes = b"\xff\xd8post-focus-image\xff\xd9"

        def slow_focus(steps: int) -> dict[str, Any]:
            self.assertEqual(steps, 1)
            focus_started.set()
            if not release_focus.wait(timeout=1.0):
                self.fail("Timed out waiting to release focus operation")
            return {"status": "ok"}

        async def handler(request: httpx.Request) -> httpx.Response:
            image_started.set()
            return httpx.Response(
                200,
                content=image_bytes,
                headers={"Content-Type": "image/jpeg"},
                request=request,
            )

        with patch.object(spot_api, "move_focus", side_effect=slow_focus):
            focus_task = asyncio.create_task(spot_api.move_focus_serialized(1))
            self.assertTrue(await asyncio.to_thread(focus_started.wait, 1.0))
            focus_task.cancel()

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                image_task = asyncio.create_task(
                    spot_api._request_spot_image(client, "http://spot.local/image.jpg")
                )
                await asyncio.sleep(0.01)
                self.assertFalse(image_started.is_set())
                release_focus.set()
                with self.assertRaises(asyncio.CancelledError):
                    await focus_task
                self.assertEqual(await image_task, image_bytes)

    def test_only_official_image_bridge_route_is_registered(self) -> None:
        from backend import app as backend_app

        image_bytes = b"\xff\xd8bridge-image\xff\xd9"
        meta = {
            "status": "ok",
            "source": "upstream",
            "captured_at": time.time(),
            "latency_ms": 12.5,
            "age_ms": 4.5,
            "image_path": "/image.jpg",
        }
        internal_temperature_at = time.time()
        with (
            patch.object(backend_app.spot_control, "fetch_image_async", AsyncMock(return_value=(image_bytes, meta))),
            patch.object(
                backend_app.spot_control,
                "get_spot_internal_temperature_diagnostics",
                return_value={
                    "internal_temperature": 41.25,
                    "internal_temperature_at": internal_temperature_at,
                    "internal_temperature_cache_status": "ok",
                },
            ),
            patch.object(backend_app.observability_service, "record_spot_image_result"),
            TestClient(backend_app.app) as client,
        ):
            response = client.get(
                "/api/spot/image.jpg",
                headers={"Origin": "file://"},
            )
            config_response = client.get("/api/spot/config")
            removed_live = client.get("/api/spot/live_image")
            removed_proxy = client.get("/api/spot/proxy_image")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, image_bytes)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertEqual(response.headers["cache-control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(response.headers["x-spot-image-age-ms"], "4.5")
        self.assertEqual(response.headers["x-spot-internal-temperature"], "41.250")
        self.assertEqual(
            response.headers["x-spot-internal-temperature-at"],
            str(int(internal_temperature_at * 1000)),
        )
        self.assertEqual(response.headers["x-spot-internal-temperature-status"], "ok")
        exposed_headers = {
            value.strip().lower()
            for value in response.headers["access-control-expose-headers"].split(",")
        }
        self.assertTrue(
            {
                "x-spot-internal-temperature",
                "x-spot-internal-temperature-at",
                "x-spot-internal-temperature-status",
                "x-spot-image-at",
                "x-spot-image-source",
                "x-spot-image-latency-ms",
                "x-spot-image-age-ms",
            }.issubset(exposed_headers)
        )
        self.assertEqual(config_response.status_code, 200)
        self.assertEqual(config_response.json()["image_url"], "/api/spot/image.jpg")
        self.assertNotIn("live_image_url", config_response.json())
        self.assertNotIn("proxy", config_response.json())
        self.assertNotIn("live", config_response.json())
        self.assertEqual(removed_live.status_code, 404)
        self.assertEqual(removed_proxy.status_code, 404)

    def test_official_image_bridge_does_not_expose_stale_internal_temperature(self) -> None:
        from backend import app as backend_app

        image_bytes = b"\xff\xd8bridge-image\xff\xd9"
        meta = {
            "status": "ok",
            "source": "upstream",
            "captured_at": time.time(),
            "latency_ms": 12.5,
            "image_path": "/image.jpg",
        }
        with (
            patch.object(backend_app.spot_control, "fetch_image_async", AsyncMock(return_value=(image_bytes, meta))),
            patch.object(
                backend_app.spot_control,
                "get_spot_internal_temperature_diagnostics",
                return_value={
                    "internal_temperature": None,
                    "internal_temperature_at": None,
                    "internal_temperature_cache_status": "stale",
                },
            ),
            patch.object(backend_app.observability_service, "record_spot_image_result"),
            TestClient(backend_app.app) as client,
        ):
            response = client.get("/api/spot/image.jpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-spot-internal-temperature-status"], "stale")
        self.assertNotIn("x-spot-internal-temperature", response.headers)
        self.assertNotIn("x-spot-internal-temperature-at", response.headers)

    def test_official_image_bridge_survives_internal_temperature_metadata_failure(self) -> None:
        from backend import app as backend_app

        image_bytes = b"\xff\xd8bridge-image\xff\xd9"
        meta = {
            "status": "ok",
            "source": "upstream",
            "captured_at": time.time(),
            "latency_ms": 12.5,
            "image_path": "/image.jpg",
        }
        with (
            patch.object(backend_app.spot_control, "fetch_image_async", AsyncMock(return_value=(image_bytes, meta))),
            patch.object(
                backend_app.spot_control,
                "get_spot_internal_temperature_diagnostics",
                side_effect=RuntimeError("simulated metadata failure"),
            ),
            patch.object(backend_app.observability_service, "record_spot_image_result"),
            patch.object(backend_app._logger, "warning") as warning,
            TestClient(backend_app.app) as client,
        ):
            response = client.get("/api/spot/image.jpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, image_bytes)
        self.assertEqual(response.headers["x-spot-internal-temperature-status"], "error")
        self.assertNotIn("x-spot-internal-temperature", response.headers)
        warning.assert_called_once()

    def test_official_image_bridge_reports_missing_configuration(self) -> None:
        from backend import app as backend_app

        with (
            patch.object(
                backend_app.spot_control,
                "fetch_image_async",
                AsyncMock(side_effect=spot_api.SpotImageConfigError("")),
            ),
            patch.object(backend_app.spot_control, "get_spot_diagnostics", return_value={"image_status": "idle"}),
            patch.object(backend_app.observability_service, "record_spot_image_result") as result_mock,
            TestClient(backend_app.app) as client,
        ):
            response = client.get("/api/spot/image.jpg")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["code"], "config-missing")
        self.assertEqual(response.json()["detail"]["diagnostics"], {"image_status": "idle"})
        result_mock.assert_called_once_with(404)

    def test_official_image_bridge_marks_payload_rejection(self) -> None:
        from backend import app as backend_app

        error = spot_api.SpotImageFetchError(
            "invalid-image-html",
            "SPOT image upstream returned HTML",
            image_url="http://spot.local/image.jpg",
            upstream_status=200,
        )
        with (
            patch.object(backend_app.spot_control, "fetch_image_async", AsyncMock(side_effect=error)),
            patch.object(backend_app.spot_control, "get_spot_diagnostics", return_value={"image_status": "error"}),
            patch.object(backend_app.observability_service, "record_error") as error_mock,
            patch.object(backend_app.observability_service, "record_spot_image_result") as result_mock,
            TestClient(backend_app.app) as client,
        ):
            response = client.get("/api/spot/image.jpg")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.headers["x-spot-payload-rejection"], "1")
        self.assertEqual(response.json()["detail"]["code"], "invalid-image-html")
        self.assertEqual(response.json()["detail"]["upstream_status"], 200)
        error_mock.assert_called_once()
        self.assertEqual(error_mock.call_args.kwargs["error_type"], "invalid-image-html")
        self.assertEqual(error_mock.call_args.kwargs["level"], "warning")
        result_mock.assert_called_once_with(502)

    def test_official_image_bridge_reports_upstream_failure_without_rejection_header(self) -> None:
        from backend import app as backend_app

        error = spot_api.SpotImageFetchError(
            "upstream-timeout",
            "SPOT image upstream timed out",
            image_url="http://spot.local/image.jpg",
            upstream_status=None,
            transport_error_type="ConnectTimeout",
            request_elapsed_ms=1004.2,
        )
        with (
            patch.object(backend_app.spot_control, "fetch_image_async", AsyncMock(side_effect=error)),
            patch.object(backend_app.spot_control, "get_spot_diagnostics", return_value={"image_status": "error"}),
            patch.object(backend_app.observability_service, "record_error") as error_mock,
            patch.object(backend_app.observability_service, "record_spot_image_result") as result_mock,
            TestClient(backend_app.app) as client,
        ):
            response = client.get("/api/spot/image.jpg")

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("x-spot-payload-rejection", response.headers)
        self.assertEqual(response.json()["detail"]["code"], "upstream-timeout")
        self.assertIsNone(response.json()["detail"]["upstream_status"])
        self.assertEqual(response.json()["detail"]["transport_error_type"], "ConnectTimeout")
        self.assertEqual(response.json()["detail"]["request_elapsed_ms"], 1004.2)
        error_mock.assert_called_once()
        self.assertEqual(error_mock.call_args.kwargs["error_type"], "ConnectTimeout")
        self.assertIn("'code': 'upstream-timeout'", error_mock.call_args.kwargs["detail"])
        self.assertIn("'transport_error_type': 'ConnectTimeout'", error_mock.call_args.kwargs["detail"])
        self.assertIn("'request_elapsed_ms': 1004.2", error_mock.call_args.kwargs["detail"])
        self.assertEqual(error_mock.call_args.kwargs["level"], "error")
        result_mock.assert_called_once_with(502)

    def test_official_image_bridge_reports_unexpected_failure(self) -> None:
        from backend import app as backend_app

        with (
            patch.object(
                backend_app.spot_control,
                "fetch_image_async",
                AsyncMock(side_effect=RuntimeError("simulated bridge failure")),
            ),
            patch.object(backend_app.spot_control, "get_spot_diagnostics", return_value={"image_status": "error"}),
            patch.object(backend_app.observability_service, "record_error") as error_mock,
            patch.object(backend_app.observability_service, "record_spot_image_result") as result_mock,
            TestClient(backend_app.app) as client,
        ):
            response = client.get("/api/spot/image.jpg")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["code"], "unknown")
        self.assertEqual(response.json()["detail"]["message"], "Unexpected SPOT image bridge error.")
        error_mock.assert_called_once()
        self.assertEqual(error_mock.call_args.kwargs["error_type"], "RuntimeError")
        result_mock.assert_called_once_with(502)

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
            patch.object(
                backend_app.spot_control,
                "move_focus_serialized",
                AsyncMock(side_effect=focus_error),
            ),
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
                "move_focus_serialized",
                AsyncMock(side_effect=RuntimeError("SPOT_FOCUS_URL is not configured")),
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
            patch.object(
                backend_app.spot_control,
                "move_focus_serialized",
                AsyncMock(side_effect=focus_error),
            ),
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.post("/api/spot/focus?steps=1")
            finally:
                client.close()

        self.assertEqual(response.status_code, 403)
        self.assertIn("HTTP 403", response.json()["detail"])

    def test_spot_actuator_route_uses_serialized_operation(self) -> None:
        from backend import app as backend_app

        result = {
            "status": "ok",
            "current": 500,
            "new": 550,
            "verified": 550,
            "request_steps": 1,
            "actuator_step": 50,
        }
        actuator_mock = AsyncMock(return_value=result)
        with patch.object(
            backend_app.spot_control,
            "move_actuator_serialized",
            actuator_mock,
        ):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.post("/api/spot/actuator", json={"step": 1})
            finally:
                client.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)
        actuator_mock.assert_awaited_once_with(1)


if __name__ == "__main__":
    unittest.main()
