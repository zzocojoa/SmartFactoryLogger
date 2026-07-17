import threading
import time
import unittest
from unittest.mock import Mock, patch

from backend.FacilityData.service import plc_service
from backend.Observability.metrics_logger import CommMetricsLoggerService


class CommMetricsLoggerServiceTests(unittest.TestCase):
    def test_stop_interrupts_full_interval_wait(self) -> None:
        health_called = threading.Event()

        def get_health() -> dict[str, object]:
            health_called.set()
            return {"mode": "REAL", "comm": {}}

        logger = Mock()
        with patch.object(CommMetricsLoggerService, "_build_logger", return_value=logger):
            service = CommMetricsLoggerService(interval_sec=60.0)

        # A restarted service must not inherit a previously signalled stop event.
        service._stop_event.set()

        with patch.object(plc_service, "get_health", side_effect=get_health):
            service.start()
            self.assertTrue(health_called.wait(timeout=1.0))

            started = time.monotonic()
            stopped = service.stop()
            elapsed = time.monotonic() - started

        self.assertTrue(stopped)
        self.assertLess(elapsed, 0.5)
        self.assertIsNone(service.thread)


if __name__ == "__main__":
    unittest.main()
