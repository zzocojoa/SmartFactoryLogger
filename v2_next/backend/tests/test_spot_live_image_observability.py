import unittest

from backend.Observability.service import ObservabilityService


class SpotLiveImageObservabilityTests(unittest.TestCase):
    def test_snapshot_and_live_image_routes_keep_independent_counters(self) -> None:
        service = ObservabilityService(
            window_sec=60.0,
            max_requests=100,
            max_errors=20,
        )

        snapshot_path = "/api/spot/image.jpg"
        live_path = "/api/spot/live_image.jpg"

        service.record_request(snapshot_path, 200, 5.0, "127.0.0.1")
        service.record_spot_image_result(200, path=snapshot_path)
        service.record_request(live_path, 200, 6.0, "127.0.0.1")
        service.record_spot_image_result(200, path=live_path)
        service.record_request(live_path, 502, 8.0, "127.0.0.1")

        paths = service.get_stats()["polling"]["paths"]

        self.assertEqual(paths[snapshot_path]["count"], 1)
        self.assertEqual(paths[snapshot_path]["success_count"], 1)
        self.assertEqual(paths[snapshot_path]["failure_count"], 0)
        self.assertEqual(paths[live_path]["count"], 2)
        self.assertEqual(paths[live_path]["success_count"], 1)
        self.assertEqual(paths[live_path]["failure_count"], 1)

    def test_spot_image_result_rejects_unknown_route(self) -> None:
        service = ObservabilityService(
            window_sec=60.0,
            max_requests=100,
            max_errors=20,
        )

        with self.assertRaises(ValueError):
            service.record_spot_image_result(
                200,
                path="/api/spot/unknown",
            )


if __name__ == "__main__":
    unittest.main()
