import unittest

from backend.Observability.service import ObservabilityService


class ObservabilityServiceTests(unittest.TestCase):
    def create_service(self) -> ObservabilityService:
        return ObservabilityService(window_sec=60.0, max_requests=100, max_errors=20)

    def test_request_stats_split_4xx_and_5xx(self) -> None:
        service = self.create_service()

        service.record_request("/ok", 200, 10.0, "127.0.0.1")
        service.record_request("/bad", 404, 20.0, "127.0.0.1")
        service.record_request("/boom", 500, 30.0, "127.0.0.1")

        stats = service.get_stats()

        self.assertEqual(stats["total_http_error_count"], 2)
        self.assertEqual(stats["total_http_4xx_count"], 1)
        self.assertEqual(stats["total_http_5xx_count"], 1)
        self.assertEqual(stats["window"]["http_error_count"], 2)
        self.assertEqual(stats["window"]["http_4xx_count"], 1)
        self.assertEqual(stats["window"]["http_5xx_count"], 1)

    def test_polling_stats_include_top_clients(self) -> None:
        service = self.create_service()

        service.record_request("/api/spot/image.jpg", 200, 5.0, "192.168.0.10")
        service.record_request("/api/spot/image.jpg", 200, 5.0, "192.168.0.10")
        service.record_request("/api/spot/image.jpg", 200, 5.0, "192.168.0.20")
        service.record_request("/health", 200, 2.0, "192.168.0.10")

        stats = service.get_stats()
        spot_stats = stats["polling"]["paths"]["/api/spot/image.jpg"]

        self.assertEqual(spot_stats["count"], 3)
        self.assertEqual(spot_stats["unique_clients"], 2)
        self.assertEqual(spot_stats["top_clients"][0]["client"], "192.168.0.10")
        self.assertEqual(spot_stats["top_clients"][0]["count"], 2)

    def test_spot_image_stats_include_success_and_failure_without_cache_fields(self) -> None:
        service = self.create_service()

        service.record_request("/api/spot/image.jpg", 200, 5.0, "192.168.0.10")
        service.record_spot_image_result(200)
        service.record_request("/api/spot/image.jpg", 200, 7.0, "192.168.0.20")
        service.record_spot_image_result(200)
        service.record_request("/api/spot/image.jpg", 502, 9.0, "192.168.0.20")

        stats = service.get_stats()
        spot_stats = stats["polling"]["paths"]["/api/spot/image.jpg"]

        self.assertEqual(spot_stats["count"], 3)
        self.assertEqual(spot_stats["success_count"], 2)
        self.assertEqual(spot_stats["failure_count"], 1)
        self.assertNotIn("stale_count", spot_stats)
        self.assertNotIn("avg_age_sec", spot_stats)

    def test_operator_live_image_has_independent_route_observability(self) -> None:
        service = self.create_service()
        path = "/api/spot/live_image.jpg"

        service.record_request(path, 200, 6.0, "192.168.0.10")
        service.record_spot_image_result(200, path=path)
        service.record_request(path, 502, 8.0, "192.168.0.10")

        live_stats = service.get_stats()["polling"]["paths"][path]

        self.assertEqual(live_stats["count"], 2)
        self.assertEqual(live_stats["success_count"], 1)
        self.assertEqual(live_stats["failure_count"], 1)

        with self.assertRaises(ValueError):
            service.record_spot_image_result(200, path="/api/spot/unknown")

    def test_export_latest_is_tracked_as_polling_path(self) -> None:
        service = self.create_service()

        service.record_request("/api/memory/export/latest", 200, 3.0, "192.168.0.10")

        stats = service.get_stats()

        self.assertIn("/api/memory/export/latest", stats["polling"]["paths"])

    def test_worker_asset_and_config_requests_do_not_fill_detail_queue(self) -> None:
        service = self.create_service()

        service.record_request("/assets/main-B3PXkacu.js", 200, 2.0, "192.168.0.10")
        service.record_request("/api/config", 200, 4.0, "192.168.0.10")
        service.record_request("/api/logs/comm-metrics", 200, 4.0, "192.168.0.10")
        service.record_request("/api/spot/config", 200, 4.0, "192.168.0.10")
        service.record_request("/api/memory/profiler/start", 200, 3.0, "192.168.0.10")
        service.record_request("/api/control/path-health", 200, 5.0, "192.168.0.10")
        service.record_request("/api/layouts/client/client-a/latest", 200, 5.0, "192.168.0.10")
        service.record_request("/api/log/status", 200, 6.0, "192.168.0.10")

        summary = service.get_request_storage_summary()

        self.assertEqual(summary["detail_count"], 0)
        self.assertEqual(summary["polling_count"], 8)

    def test_quiet_success_keeps_errors_in_detail_queue(self) -> None:
        service = self.create_service()

        service.record_request("/api/config/verify-password", 200, 4.0, "192.168.0.10")
        service.record_request("/api/config/verify-password", 500, 6.0, "192.168.0.10")

        summary = service.get_request_storage_summary()

        self.assertEqual(summary["detail_count"], 1)
        self.assertEqual(summary["polling_count"], 2)

    def test_summary_only_asset_failure_is_kept_in_detail_queue(self) -> None:
        service = self.create_service()

        service.record_request("/assets/index-oldhash.js", 404, 6.0, "192.168.0.10")

        summary = service.get_request_storage_summary()

        self.assertEqual(summary["detail_count"], 1)
        self.assertEqual(summary["polling_count"], 1)

    def test_request_storage_summary_keeps_detail_counts(self) -> None:
        service = self.create_service()

        service.record_request("/api/data", 200, 2.0, "192.168.0.10")
        service.record_request("/custom", 200, 4.0, "192.168.0.10")
        service.record_request("/api/data", 500, 6.0, "192.168.0.10")

        summary = service.get_request_storage_summary()

        self.assertEqual(summary["request_count"], 3)
        self.assertEqual(summary["detail_count"], 2)
        self.assertEqual(summary["polling_count"], 2)
        self.assertGreater(summary["estimated_bytes"], 0)

    def test_record_error_deduplicates_and_tracks_repeat(self) -> None:
        service = self.create_service()

        service.record_error("extruder", "timeout", detail="192.168.0.10:1234")
        service.record_error("extruder", "timeout", detail="192.168.0.10:1234")

        errors = service.get_errors(10)
        summary = service.get_error_summary()

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["repeat"], 2)
        self.assertEqual(summary["queue_size"], 1)
        self.assertEqual(summary["source_counts"], {"extruder": 1})

    def test_record_error_logs_structured_message(self) -> None:
        service = self.create_service()

        with self.assertLogs("SmartFactoryLoggerV2", level="ERROR") as logs:
            service.record_error("api", "HTTP 500", path="/api/data", detail="server failure")

        self.assertTrue(any("Observability error recorded" in line for line in logs.output))

    def test_error_summary_counts_multiple_sources(self) -> None:
        service = self.create_service()

        service.record_error("api", "HTTP 500")
        service.record_error("plc_loop", "read failed")
        service.record_error("api", "HTTP 404")

        summary = service.get_error_summary()

        self.assertEqual(summary["queue_size"], 3)
        self.assertEqual(summary["source_counts"], {"api": 2, "plc_loop": 1})


if __name__ == "__main__":
    unittest.main()
