import time
import unittest
from typing import Any

import httpx

from backend.FacilityData.drivers import spot_api


class SpotApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_spot_url: str = str(spot_api.config.SPOT_URL)
        self.original_spot_image_url: str = str(spot_api.config.SPOT_IMAGE_URL)
        self.original_spot_refresh_interval: float = float(spot_api.config.SPOT_REFRESH_INTERVAL)
        self.reset_spot_state()

    def tearDown(self) -> None:
        spot_api.config.SPOT_URL = self.original_spot_url
        spot_api.config.SPOT_IMAGE_URL = self.original_spot_image_url
        spot_api.config.SPOT_REFRESH_INTERVAL = self.original_spot_refresh_interval
        self.reset_spot_state()

    def reset_spot_state(self) -> None:
        spot_api._img_cache = {"data": None, "time": 0.0, "temp": 0.0, "temp_time": 0.0}
        spot_api._img_last_error = 0.0
        spot_api._img_failure_count = 0
        spot_api._img_cache_state = "empty"
        spot_api._img_last_cache_log_at = 0.0
        spot_api._img_last_error_code = None
        spot_api._img_last_error_message = None
        spot_api._img_next_retry_at = None
        spot_api._temp_last_error = 0.0
        spot_api._temp_last_error_code = None
        spot_api._temp_last_error_message = None
        spot_api._temp_last_upstream_status = None
        spot_api._temp_last_url = None
        spot_api._temp_last_success_at = 0.0

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


if __name__ == "__main__":
    unittest.main()
