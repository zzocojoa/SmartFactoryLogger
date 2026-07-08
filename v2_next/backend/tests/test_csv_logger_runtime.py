import csv
from datetime import datetime
import io
import queue
import threading
import time
import unittest
from unittest.mock import Mock, patch

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

    def test_control_shutdown_waits_for_csv_logger_stop_timeout(self) -> None:
        class LoggerStub:
            timeout_sec: float | None = None

            def stop(self, *, timeout_sec: float | None = None) -> bool:
                self.timeout_sec = timeout_sec
                return True

        logger_stub = LoggerStub()

        with (
            patch.object(backend_app, "logger_service", logger_stub),
            patch.object(backend_app.config, "CSV_LOGGER_CONTROL_SHUTDOWN_TIMEOUT_SEC", 123.0),
            patch.object(backend_app.spot_control, "stop_spot_image_capture_for_shutdown", Mock(return_value=True)),
            patch.object(backend_app.plc_service, "stop", Mock()),
            patch.object(backend_app.comm_metrics_logger_service, "stop", Mock()),
            patch.object(backend_app.config_sync_agent, "stop", Mock()),
            patch.object(backend_app.config_watch_service, "stop", Mock()),
        ):
            status = backend_app._stop_services_for_control_shutdown()

        self.assertTrue(status["logger_service_stopped"])
        self.assertEqual(logger_stub.timeout_sec, 123.0)


if __name__ == "__main__":
    unittest.main()
