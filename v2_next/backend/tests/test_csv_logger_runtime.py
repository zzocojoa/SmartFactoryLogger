import csv
from datetime import datetime
import io
import json
import queue
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from backend import app as backend_app
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData.schemas import FactoryData


def create_factory_data() -> FactoryData:
    return FactoryData(
        Time="2026-03-09T07:20:25.123",
        Status="Running",
        Press=30.0,
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


class CSVLoggerRuntimeTests(unittest.TestCase):
    def test_closeout_recovers_manifest_when_observation_writes_drain_late(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CSVLoggerService()
            csv_path = Path(temp_dir) / "Factory_Integrated_Log_v2_late.csv"
            metadata_path = csv_path.with_suffix(".metadata.json")
            csv_path.write_text("sample_seq\n1\n", encoding="utf-8")
            metadata_path.write_text("{}", encoding="utf-8")
            service._current_v2_csv_path = csv_path
            service._finalize_spot_observation_manifest_on_stop = False
            service._allow_spot_observation_late_drain_on_stop = True

            with (
                patch(
                    "backend.FacilityData.drivers.spot_api.spot_observation_fact_writes_drained",
                    return_value=True,
                ),
                patch.object(
                    service,
                    "refresh_spot_observation_fact_manifest_for_csv",
                    return_value=metadata_path,
                ) as refresh_manifest,
                patch.object(
                    service,
                    "_suppress_spot_observation_fact_manifest_for_csv",
                ) as suppress_manifest,
            ):
                self.assertTrue(service._close_v2_file(None))

            refresh_manifest.assert_called_once_with(
                csv_path,
                closeout_reason="runtime-close",
            )
            suppress_manifest.assert_not_called()

    def test_closeout_fails_closed_when_observation_manifest_cannot_be_finalized(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CSVLoggerService()
            csv_path = Path(temp_dir) / "Factory_Integrated_Log_v2_pending.csv"
            metadata_path = csv_path.with_suffix(".metadata.json")
            csv_path.write_text("sample_seq\n1\n", encoding="utf-8")
            metadata_path.write_text("{}", encoding="utf-8")
            service._current_v2_csv_path = csv_path
            service._finalize_spot_observation_manifest_on_stop = False
            service._allow_spot_observation_late_drain_on_stop = True

            with (
                patch(
                    "backend.FacilityData.drivers.spot_api.spot_observation_fact_writes_drained",
                    return_value=False,
                ),
                patch.object(
                    service,
                    "_suppress_spot_observation_fact_manifest_for_csv",
                    return_value=metadata_path,
                ) as suppress_manifest,
            ):
                self.assertFalse(service._close_v2_file(None))

            suppress_manifest.assert_called_once_with(
                csv_path,
                writes_drained=False,
                reason="shutdown-write-drain-timeout",
            )
            self.assertTrue(service._runtime_write_failure_observed)

    def test_stop_suppresses_image_manifest_when_capture_did_not_drain(self) -> None:
        service = CSVLoggerService()
        service.csv_v2_enabled = True
        service.csv_v2_sidecar_enabled = True

        with patch.object(
            service,
            "_write_spot_image_fact_final_manifest_safely",
        ) as write_manifest:
            service.start()
            stopped = service.stop(
                timeout_sec=2.0,
                finalize_spot_image_manifest=False,
            )

        self.assertTrue(stopped)
        write_manifest.assert_not_called()

    def test_start_fails_explicitly_while_a_logger_generation_is_stopping(self) -> None:
        service = CSVLoggerService()
        loop_started = threading.Event()
        release_loop = threading.Event()
        observed_finalize_values: list[bool] = []

        def controlled_loop() -> None:
            loop_started.set()
            release_loop.wait(timeout=2.0)
            observed_finalize_values.append(
                service._finalize_spot_image_manifest_on_stop
            )
            service._shutdown_flush_succeeded = True

        service._loop = controlled_loop  # type: ignore[method-assign]
        service.start()
        self.assertTrue(loop_started.wait(timeout=1.0))
        retiring_thread = service.thread
        stop_result: list[bool] = []
        stop_thread = threading.Thread(
            target=lambda: stop_result.append(
                service.stop(
                    timeout_sec=2.0,
                    finalize_spot_image_manifest=False,
                )
            )
        )
        stop_thread.start()

        deadline = time.time() + 1.0
        while service.running and time.time() < deadline:
            time.sleep(0.01)
        with self.assertRaisesRegex(
            RuntimeError,
            "previous worker generation",
        ):
            service.start()

        self.assertIs(service.thread, retiring_thread)
        self.assertFalse(service._finalize_spot_image_manifest_on_stop)
        release_loop.set()
        stop_thread.join(timeout=2.0)

        self.assertEqual(stop_result, [True])
        self.assertEqual(observed_finalize_values, [False])
        self.assertIsNone(service.thread)

        service.start()
        self.assertTrue(service.running)
        self.assertTrue(service.stop(timeout_sec=2.0))

    def test_start_rejects_running_state_without_a_live_worker(self) -> None:
        dead_thread = threading.Thread(target=lambda: None)
        dead_thread.start()
        dead_thread.join(timeout=1.0)
        self.assertFalse(dead_thread.is_alive())

        for worker in (None, dead_thread):
            with self.subTest(worker=worker):
                service = CSVLoggerService()
                service.running = True
                service.thread = worker

                with self.assertRaisesRegex(
                    RuntimeError,
                    "marked running without a live worker thread",
                ):
                    service.start()

    def test_repeated_stop_can_disable_manifest_after_an_earlier_timeout(self) -> None:
        service = CSVLoggerService()
        loop_started = threading.Event()
        release_loop = threading.Event()
        observed_finalize_values: list[bool] = []

        def controlled_loop() -> None:
            loop_started.set()
            release_loop.wait(timeout=2.0)
            observed_finalize_values.append(
                service._finalize_spot_image_manifest_on_stop
            )
            service._shutdown_flush_succeeded = True

        service._loop = controlled_loop  # type: ignore[method-assign]
        service.start()
        self.assertTrue(loop_started.wait(timeout=1.0))
        self.assertFalse(service.stop(timeout_sec=0.0))

        release_loop.set()
        self.assertTrue(
            service.stop(
                timeout_sec=2.0,
                finalize_spot_image_manifest=False,
            )
        )
        self.assertEqual(observed_finalize_values, [False])

    def test_stop_sentinel_is_ordered_after_an_accepted_concurrent_enqueue(self) -> None:
        enqueue_entered = threading.Event()
        release_enqueue = threading.Event()

        class BlockingQueue(queue.Queue[FactoryData | None]):
            def put_nowait(self, item: FactoryData | None) -> None:
                if item is not None:
                    enqueue_entered.set()
                    release_enqueue.wait(timeout=1.0)
                super().put_nowait(item)

        service = CSVLoggerService()
        service.queue = BlockingQueue(maxsize=10)
        service.running = True
        data = create_factory_data()
        stop_result: list[bool] = []

        enqueue_thread = threading.Thread(target=service.enqueue, args=(data,))
        stop_thread = threading.Thread(target=lambda: stop_result.append(service.stop()))
        enqueue_thread.start()
        self.assertTrue(enqueue_entered.wait(timeout=1.0))
        stop_thread.start()
        time.sleep(0.01)
        self.assertTrue(stop_thread.is_alive())

        release_enqueue.set()
        enqueue_thread.join(timeout=1.0)
        stop_thread.join(timeout=1.0)

        self.assertEqual(stop_result, [True])
        self.assertIs(service.queue.get_nowait(), data)
        self.assertIsNone(service.queue.get_nowait())

    def test_csv_logger_drop_count_increments_on_full_queue(self) -> None:
        service = CSVLoggerService()
        service.queue = queue.Queue(maxsize=1)
        service.running = True

        service.enqueue(create_factory_data())
        service.enqueue(create_factory_data())

        state = service.get_runtime_state()
        self.assertEqual(state["queue_size"], 1)
        self.assertEqual(state["queue_maxsize"], 1)
        self.assertEqual(state["queue_ratio"], 1.0)
        self.assertEqual(state["drop_count"], 1)
        self.assertIsNotNone(state["last_drop_at"])
        self.assertIsNotNone(state["last_enqueue_at"])

    def test_payload_bytes_ema_updates_on_enqueue(self) -> None:
        service = CSVLoggerService()
        data = create_factory_data()
        service.running = True

        service.enqueue(data)

        expected_bytes = len(data.model_dump_json()) * 2
        state = service.get_runtime_state()
        self.assertEqual(state["queue_size"], 1)
        self.assertEqual(state["payload_bytes_ema"], expected_bytes)
        self.assertEqual(state["estimated_queue_bytes"], expected_bytes)

    def test_writer_lag_is_null_before_first_write(self) -> None:
        service = CSVLoggerService()

        state = service.get_runtime_state()

        self.assertIsNone(state["last_write_at"])
        self.assertIsNone(state["writer_lag_sec"])

    def test_writer_lag_is_positive_after_flush(self) -> None:
        service = CSVLoggerService()
        handle = io.StringIO()
        writer = csv.writer(handle)

        flushed = service._flush_buffer(writer, handle, [(["value"], datetime.now())])
        time.sleep(0.01)
        state = service.get_runtime_state()

        self.assertTrue(flushed)
        self.assertIsNotNone(state["last_write_at"])
        self.assertIsNotNone(state["writer_lag_sec"])
        self.assertGreaterEqual(state["writer_lag_sec"], 0.0)

    def test_estimated_queue_bytes_scales_with_queue_size(self) -> None:
        service = CSVLoggerService()
        service.queue = queue.Queue(maxsize=10)
        service.running = True
        data = create_factory_data()

        service.enqueue(data)
        service.enqueue(data)

        expected_payload_bytes = len(data.model_dump_json()) * 2
        state = service.get_runtime_state()
        self.assertEqual(state["queue_size"], 2)
        self.assertEqual(state["payload_bytes_ema"], expected_payload_bytes)
        self.assertEqual(state["estimated_queue_bytes"], expected_payload_bytes * 2)

    def test_memory_collector_uses_estimated_queue_bytes_and_runtime_note(self) -> None:
        service = CSVLoggerService()
        service.queue = queue.Queue(maxsize=10)
        service.running = True
        service.enqueue(create_factory_data())
        original_logger_service = backend_app.logger_service
        backend_app.logger_service = service
        try:
            item = backend_app._collect_csv_logger()
        finally:
            backend_app.logger_service = original_logger_service

        state = service.get_runtime_state()
        self.assertEqual(item["name"], "facility.csv_logger")
        self.assertEqual(item["kind"], "queue")
        self.assertEqual(item["items"], 1)
        self.assertGreaterEqual(item["bytes"], state["estimated_queue_bytes"])
        self.assertIn("queue=1/10", item["note"])
        self.assertIn("drop=0", item["note"])
        self.assertIn("lag=n/a", item["note"])

    def test_stop_reports_timeout_when_logger_thread_is_still_alive(self) -> None:
        service = CSVLoggerService()
        release = threading.Event()

        def wait_until_released() -> None:
            release.wait(timeout=1.0)

        service.running = True
        service.thread = threading.Thread(target=wait_until_released)
        service.thread.start()
        try:
            self.assertFalse(service.stop(timeout_sec=0.01))
        finally:
            release.set()
            service.thread.join(timeout=1.0)

    def test_stop_reports_final_flush_failure_after_thread_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CSVLoggerService()
            log_path = Path(temp_dir)
            service.fallback_log_dir = log_path
            service.apply_config(
                log_path=log_path,
                auto_save=True,
                csv_v1_enabled=True,
                csv_v2_enabled=False,
            )
            with patch.object(service, "_flush_buffer", return_value=False):
                service.start()
                service.enqueue(create_factory_data())
                self.assertFalse(service.stop(timeout_sec=2.0))
                self.assertFalse(service.stop(timeout_sec=2.0))

        self.assertFalse(service._shutdown_flush_succeeded)

    def test_runtime_v2_flush_failure_cannot_be_reported_as_clean_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CSVLoggerService()
            log_path = Path(temp_dir)
            service.fallback_log_dir = log_path
            service.apply_config(
                log_path=log_path,
                auto_save=True,
                csv_v1_enabled=False,
                csv_v2_enabled=True,
            )
            with patch.object(service, "_flush_v2_buffer", return_value=False) as flush_v2:
                service.start()
                for _ in range(20):
                    service.enqueue(create_factory_data())
                deadline = time.time() + 2.0
                while flush_v2.call_count == 0 and time.time() < deadline:
                    time.sleep(0.01)
                self.assertGreaterEqual(flush_v2.call_count, 1)
                self.assertFalse(service.stop(timeout_sec=2.0))
            metadata_paths = list(
                log_path.glob("Factory_Integrated_Log_v2_*.metadata.json")
            )
            self.assertEqual(len(metadata_paths), 1)
            closeout_payload = json.loads(
                metadata_paths[0].read_text(encoding="utf-8-sig")
            )

        self.assertFalse(service._shutdown_flush_succeeded)
        self.assertNotIn("csv_closeout", closeout_payload)
        self.assertEqual(
            closeout_payload["spot_observation_fact_closeout"],
            {
                "finalized": False,
                "writes_drained": True,
                "reason": "closeout-not-finalized",
            },
        )

    def test_observation_manifest_is_suppressed_when_writes_do_not_drain(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "Factory_Integrated_Log_v2_test.csv"
            metadata_path = csv_path.with_suffix(".metadata.json")
            csv_path.write_text("sample_seq\n1\n", encoding="utf-8")
            metadata_path.write_text(
                json.dumps(
                    {
                        "spot_observation_fact_manifest": {
                            "row_count": 1,
                            "sha256": "unsafe-stale-hash",
                        }
                    }
                ),
                encoding="utf-8",
            )
            service = CSVLoggerService()

            result = service._suppress_spot_observation_fact_manifest_for_csv(
                csv_path
            )
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(result, metadata_path)
        self.assertNotIn("spot_observation_fact_manifest", payload)
        self.assertEqual(
            payload["spot_observation_fact_closeout"],
            {
                "finalized": False,
                "writes_drained": False,
                "reason": "shutdown-write-drain-timeout",
            },
        )

    def test_stop_rejects_clean_shutdown_when_observation_manifest_refresh_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CSVLoggerService()
            log_path = Path(temp_dir)
            service.fallback_log_dir = log_path
            service.apply_config(
                log_path=log_path,
                auto_save=True,
                csv_v1_enabled=False,
                csv_v2_enabled=True,
            )
            service.start()
            service.enqueue(create_factory_data())
            deadline = time.time() + 2.0
            while service._current_v2_csv_path is None and time.time() < deadline:
                time.sleep(0.01)
            csv_path = service._current_v2_csv_path
            self.assertIsNotNone(csv_path)
            assert csv_path is not None
            metadata_path = csv_path.with_suffix(".metadata.json")
            payload = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
            payload["spot_observation_fact_manifest"] = {
                "row_count": 1,
                "sha256": "unsafe-stale-hash",
            }
            metadata_path.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(
                service,
                "refresh_spot_observation_fact_manifest_for_csv",
                return_value=None,
            ):
                self.assertFalse(service.stop(timeout_sec=2.0))

            closeout_payload = json.loads(
                metadata_path.read_text(encoding="utf-8")
            )

        self.assertFalse(service._shutdown_flush_succeeded)
        self.assertNotIn(
            "spot_observation_fact_manifest",
            closeout_payload,
        )
        self.assertEqual(
            closeout_payload["spot_observation_fact_closeout"],
            {
                "finalized": False,
                "writes_drained": True,
                "reason": "manifest-refresh-failed",
            },
        )

    def test_control_shutdown_waits_for_csv_logger_stop_timeout(self) -> None:
        class LoggerStub:
            timeout_sec: float | None = None
            finalize_spot_image_manifest: bool | None = None
            finalize_spot_observation_manifest: bool | None = None

            def stop(
                self,
                *,
                timeout_sec: float | None = None,
                finalize_spot_image_manifest: bool = True,
                finalize_spot_observation_manifest: bool = True,
            ) -> bool:
                self.timeout_sec = timeout_sec
                self.finalize_spot_image_manifest = finalize_spot_image_manifest
                self.finalize_spot_observation_manifest = (
                    finalize_spot_observation_manifest
                )
                return True

        logger_stub = LoggerStub()

        with (
            patch.object(backend_app, "logger_service", logger_stub),
            patch.object(backend_app.config, "CSV_LOGGER_CONTROL_SHUTDOWN_TIMEOUT_SEC", 123.0),
            patch.object(backend_app.config, "SPOT_IMAGE_CAPTURE_SHUTDOWN_TIMEOUT_SEC", 30.0),
            patch.object(
                backend_app.spot_control,
                "stop_spot_image_capture_for_shutdown",
                Mock(return_value=True),
            ) as stop_image_capture,
            patch.object(backend_app.plc_service, "stop", Mock(return_value=True)),
            patch.object(backend_app.comm_metrics_logger_service, "stop", Mock(return_value=True)),
            patch.object(backend_app.memory_service, "stop", Mock(return_value=True)),
            patch.object(backend_app.config_sync_agent, "stop", Mock(return_value=True)),
            patch.object(backend_app.config_watch_service, "stop", Mock(return_value=True)),
        ):
            status = backend_app._stop_services_for_control_shutdown(
                observation_fact_drained=True
            )

        status["spot_poll_loop_stopped"] = True
        status["spot_diagnostic_journal_stopped"] = True
        self.assertTrue(status["logger_service_stopped"])
        stop_image_capture.assert_called_once_with(timeout_sec=30.0)
        self.assertTrue(logger_stub.finalize_spot_image_manifest)
        self.assertTrue(logger_stub.finalize_spot_observation_manifest)
        self.assertEqual(logger_stub.timeout_sec, 123.0)
        self.assertIn("logger_service_elapsed_ms", status)
        self.assertIn("total_elapsed_ms", status)
        self.assertEqual(backend_app._control_shutdown_exit_code(status), 0)

        status["logger_service_stopped"] = False
        self.assertEqual(backend_app._control_shutdown_exit_code(status), 2)

    def test_control_shutdown_suppresses_observation_manifest_after_drain_timeout(
        self,
    ) -> None:
        logger_stop = Mock(return_value=True)
        with (
            patch.object(
                backend_app.spot_control,
                "stop_spot_image_capture_for_shutdown",
                Mock(return_value=True),
            ),
            patch.object(backend_app.plc_service, "stop", Mock(return_value=True)),
            patch.object(backend_app.logger_service, "stop", logger_stop),
            patch.object(
                backend_app.comm_metrics_logger_service,
                "stop",
                Mock(return_value=True),
            ),
            patch.object(backend_app.memory_service, "stop", Mock(return_value=True)),
            patch.object(backend_app.config_sync_agent, "stop", Mock(return_value=True)),
            patch.object(
                backend_app.config_watch_service,
                "stop",
                Mock(return_value=True),
            ),
            patch.object(
                backend_app.spot_control,
                "spot_observation_fact_writes_drained",
                Mock(return_value=False),
            ),
        ):
            status = backend_app._stop_services_for_control_shutdown(
                observation_fact_drained=False
            )

        status["spot_poll_loop_stopped"] = False
        logger_stop.assert_called_once_with(
            timeout_sec=backend_app.config.CSV_LOGGER_CONTROL_SHUTDOWN_TIMEOUT_SEC,
            finalize_spot_image_manifest=True,
            finalize_spot_observation_manifest=False,
        )
        self.assertFalse(status["spot_observation_fact_drained"])
        self.assertEqual(backend_app._control_shutdown_exit_code(status), 2)

    def test_control_shutdown_recovers_observation_drain_after_initial_timeout(
        self,
    ) -> None:
        logger_stop = Mock(return_value=True)
        with (
            patch.object(
                backend_app.spot_control,
                "stop_spot_image_capture_for_shutdown",
                Mock(return_value=True),
            ),
            patch.object(backend_app.plc_service, "stop", Mock(return_value=True)),
            patch.object(backend_app.logger_service, "stop", logger_stop),
            patch.object(
                backend_app.comm_metrics_logger_service,
                "stop",
                Mock(return_value=True),
            ),
            patch.object(backend_app.memory_service, "stop", Mock(return_value=True)),
            patch.object(backend_app.config_sync_agent, "stop", Mock(return_value=True)),
            patch.object(
                backend_app.config_watch_service,
                "stop",
                Mock(return_value=True),
            ),
            patch.object(
                backend_app.spot_control,
                "spot_observation_fact_writes_drained",
                Mock(return_value=True),
            ),
        ):
            status = backend_app._stop_services_for_control_shutdown(
                observation_fact_drained=False
            )

        logger_stop.assert_called_once_with(
            timeout_sec=backend_app.config.CSV_LOGGER_CONTROL_SHUTDOWN_TIMEOUT_SEC,
            finalize_spot_image_manifest=True,
            finalize_spot_observation_manifest=False,
        )
        self.assertTrue(status["spot_observation_fact_drained"])

    def test_control_shutdown_records_failed_stage_and_continues(self) -> None:
        later_stop = Mock(return_value=True)
        logger_stop = Mock(return_value=True)

        with (
            patch.object(
                backend_app.spot_control,
                "stop_spot_image_capture_for_shutdown",
                Mock(return_value=False),
            ),
            patch.object(backend_app.plc_service, "stop", later_stop),
            patch.object(backend_app.logger_service, "stop", logger_stop),
            patch.object(backend_app.comm_metrics_logger_service, "stop", Mock(return_value=True)),
            patch.object(backend_app.memory_service, "stop", Mock(return_value=True)),
            patch.object(backend_app.config_sync_agent, "stop", Mock(return_value=True)),
            patch.object(backend_app.config_watch_service, "stop", Mock(return_value=True)),
        ):
            status = backend_app._stop_services_for_control_shutdown(
                observation_fact_drained=True
            )

        status["spot_poll_loop_stopped"] = True
        self.assertFalse(status["spot_image_capture_drained"])
        self.assertTrue(status["plc_service_stopped"])
        later_stop.assert_called_once_with()
        logger_stop.assert_called_once_with(
            timeout_sec=backend_app.config.CSV_LOGGER_CONTROL_SHUTDOWN_TIMEOUT_SEC,
            finalize_spot_image_manifest=False,
            finalize_spot_observation_manifest=True,
        )
        self.assertEqual(backend_app._control_shutdown_exit_code(status), 2)

    def test_control_shutdown_stage_records_exceptions(self) -> None:
        status: dict[str, object] = {}

        def raise_stop_error() -> None:
            raise RuntimeError("stop failed")

        succeeded = backend_app._run_control_shutdown_stage(
            stage="test_service",
            status_key="test_service_stopped",
            stopper=raise_stop_error,
            status=status,
        )

        self.assertFalse(succeeded)
        self.assertFalse(status["test_service_stopped"])
        self.assertIn("test_service_elapsed_ms", status)

    def test_control_shutdown_stage_rejects_ambiguous_none_result(self) -> None:
        status: dict[str, object] = {}

        succeeded = backend_app._run_control_shutdown_stage(
            stage="test_service",
            status_key="test_service_stopped",
            stopper=lambda: None,
            status=status,
        )

        self.assertFalse(succeeded)
        self.assertFalse(status["test_service_stopped"])


if __name__ == "__main__":
    unittest.main()
