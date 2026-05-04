import time
import unittest
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

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
            TestClient(backend_app.app, raise_server_exceptions=False) as client,
        ):
            response = client.get("/api/spot/proxy_image")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.headers.get("X-Spot-Payload-Rejection"), "1")
        self.assertEqual(backend_app._stats_total_requests, original_total_requests + 1)
        self.assertEqual(backend_app._stats_error_count, original_error_count)
        self.assertEqual(backend_app._stats_last_status, 502)

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
                    TestClient(backend_app.app, raise_server_exceptions=False) as client,
                ):
                    response = client.get("/api/spot/proxy_image")

                self.assertEqual(response.status_code, 502)
                detail: dict[str, Any] = response.json()["detail"]
                self.assertEqual(detail["code"], "upstream-http-error")
                self.assertEqual(detail["upstream_status"], status)
                self.assertIsNone(response.headers.get("X-Spot-Payload-Rejection"))
                self.assertEqual(backend_app._stats_total_requests, original_total_requests + 1)
                self.assertEqual(backend_app._stats_error_count, original_error_count + 1)
                self.assertEqual(backend_app._stats_last_status, 502)


if __name__ == "__main__":
    unittest.main()
