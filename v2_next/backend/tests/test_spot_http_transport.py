import asyncio
import gc
import http.client
import http.server
import socket
import threading
import unittest
from collections.abc import Mapping
from typing import Any
from unittest.mock import patch

from backend.FacilityData.drivers import spot_http_transport as transport_module
from backend.FacilityData.drivers.spot_http_transport import (
    SpotHttpRequest,
    SpotHttpTransport,
    SpotPortBindError,
    SpotRequestKind,
    SpotTransportClosedError,
    SpotTransportProtocolError,
    SpotTransportTimeout,
)
from backend.FacilityData.drivers.spot_port_quarantine import (
    SourcePortLeasePool,
    SpotPortPoolInitError,
)


class _GuardSocketFactory:
    supported = True

    def __init__(self) -> None:
        self.created_ports: list[int] = []

    def create_guard(self, local_host: str, port: int = 0) -> tuple[socket.socket, int]:
        guard = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        guard.bind((local_host, port))
        actual_port = int(guard.getsockname()[1])
        if not port:
            self.created_ports.append(actual_port)
        return guard, actual_port


class _UnsupportedSocketFactory:
    supported = False

    def create_guard(self, _local_host: str, port: int = 0) -> tuple[socket.socket, int]:
        del port
        raise AssertionError("unsupported factory must not create guards")


class _LoopbackHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    peer_ports: list[int] = []

    def do_GET(self) -> None:
        type(self).peer_ports.append(int(self.client_address[1]))
        body = b"\xff\xd8guarded-image\xff\xd9"
        if self.path == "/chunked":
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            self.wfile.write(f"{len(body):X}\r\n".encode("ascii"))
            self.wfile.write(body + b"\r\n0\r\n\r\n")
            return
        self.protocol_version = "HTTP/1.0"
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *args: Any) -> None:
        del args


class _ContractHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requests: list[tuple[str, str, bytes, str | None]] = []

    def do_GET(self) -> None:
        responses = {
            "/temperature": b"451.25",
            "/diagnostic": b"7",
            "/actuator?scan=3&move=321": b"Pos--> 321",
        }
        body = responses[self.path]
        type(self).requests.append(
            ("GET", self.path, b"", self.headers.get("Content-Type"))
        )
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        type(self).requests.append(
            ("PUT", self.path, body, self.headers.get("Content-Type"))
        )
        response = b"OK"
        self.send_response(200)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, _format: str, *args: Any) -> None:
        del args


class _FakeSocket:
    def __init__(self) -> None:
        self.timeout: float | None = None

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        body: bytes = b"ok",
        headers: list[tuple[str, str]] | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self._headers = (
            headers
            if headers is not None
            else [("Content-Length", str(len(body)))]
        )

    def read(self) -> bytes:
        return self._body

    def getheaders(self) -> list[tuple[str, str]]:
        return list(self._headers)


class _FakeConnection:
    def __init__(
        self,
        *,
        response: _FakeResponse | None = None,
        connect_error: BaseException | None = None,
        response_error: BaseException | None = None,
        release_response: threading.Event | None = None,
    ) -> None:
        self.sock = _FakeSocket()
        self.response = response or _FakeResponse()
        self.connect_error = connect_error
        self.response_error = response_error
        self.release_response = release_response
        self.closed = False
        self.request_args: tuple[str, str, bytes | None, Mapping[str, str]] | None = None

    def connect(self) -> None:
        if self.connect_error is not None:
            raise self.connect_error

    def request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: Mapping[str, str] = {},
    ) -> None:
        self.request_args = (method, url, body, headers)

    def getresponse(self) -> _FakeResponse:
        if self.release_response is not None:
            if not self.release_response.wait(timeout=2.0):
                raise TimeoutError("test response was not released")
        if self.response_error is not None:
            raise self.response_error
        return self.response

    def close(self) -> None:
        self.closed = True


def _request(
    *,
    kind: SpotRequestKind = SpotRequestKind.IMAGE,
    method: str = "GET",
    url: str = "http://spot.local/image.jpg",
    headers: Mapping[str, str] | None = None,
    body: bytes | None = None,
    connect_timeout_sec: float = 1.0,
    read_timeout_sec: float = 2.0,
) -> SpotHttpRequest:
    return SpotHttpRequest(
        kind=kind,
        method=method,
        url=url,
        headers=headers or {},
        body=body,
        connect_timeout_sec=connect_timeout_sec,
        read_timeout_sec=read_timeout_sec,
    )


class SpotHttpTransportTests(unittest.IsolatedAsyncioTestCase):
    def make_pool(self, capacity: int = 8) -> SourcePortLeasePool:
        return SourcePortLeasePool(
            capacity=capacity,
            quarantine_seconds=75.0,
            acquire_timeout_seconds=0.1,
            socket_factory=_GuardSocketFactory(),
        )

    async def test_unsupported_enforcement_fails_closed_on_windows(self) -> None:
        transport = SpotHttpTransport(
            pool=SourcePortLeasePool(socket_factory=_UnsupportedSocketFactory())
        )

        with (
            patch.object(transport_module.sys, "platform", "win32"),
            self.assertRaises(SpotPortPoolInitError),
        ):
            transport.start()

        self.assertFalse(transport.active)
        self.assertTrue(await transport.close())

    async def test_unsupported_enforcement_remains_explicit_non_windows_fallback(self) -> None:
        transport = SpotHttpTransport(
            pool=SourcePortLeasePool(socket_factory=_UnsupportedSocketFactory())
        )

        with patch.object(transport_module.sys, "platform", "linux"):
            self.assertFalse(transport.start())

        self.assertFalse(transport.active)
        self.assertTrue(await transport.close())

    async def test_stdlib_http_10_request_uses_the_leased_source_port(self) -> None:
        _LoopbackHandler.peer_ports = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _LoopbackHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        socket_factory = _GuardSocketFactory()
        pool = SourcePortLeasePool(
            capacity=2,
            quarantine_seconds=75.0,
            acquire_timeout_seconds=0.1,
            socket_factory=socket_factory,
        )
        transport = SpotHttpTransport(pool=pool)
        transport.start()
        try:
            response = await transport.request(
                _request(url=f"http://127.0.0.1:{server.server_port}/http10")
            )
            chunked_response = await transport.request(
                _request(url=f"http://127.0.0.1:{server.server_port}/chunked")
            )
            diagnostics = transport.diagnostics()
        finally:
            self.assertTrue(await transport.close())
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=1.0)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b"\xff\xd8guarded-image\xff\xd9")
        self.assertEqual(chunked_response.body, response.body)
        self.assertEqual(len(_LoopbackHandler.peer_ports), 2)
        self.assertEqual(set(_LoopbackHandler.peer_ports), set(socket_factory.created_ports))
        self.assertEqual(diagnostics["source_port_transport_success_count"], 2)
        self.assertEqual(diagnostics["source_port_image_success_count"], 2)
        self.assertEqual(diagnostics["source_port_pool_quarantined_count"], 2)

    async def test_real_loopback_covers_temperature_diagnostic_put_and_actuator_query(
        self,
    ) -> None:
        _ContractHandler.requests = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _ContractHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        transport = SpotHttpTransport(pool=self.make_pool(capacity=4))
        transport.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            temperature = await transport.request(
                _request(
                    kind=SpotRequestKind.TEMPERATURE,
                    url=f"{base_url}/temperature",
                )
            )
            diagnostic = await transport.request(
                _request(
                    kind=SpotRequestKind.DIAGNOSTIC,
                    url=f"{base_url}/diagnostic",
                )
            )
            focus = await transport.request(
                _request(
                    kind=SpotRequestKind.FOCUS_WRITE,
                    method="PUT",
                    url=f"{base_url}/focus",
                    headers={"Content-Type": "application/json;charset=utf-8"},
                    body=b"620",
                )
            )
            actuator = await transport.request(
                _request(
                    kind=SpotRequestKind.ACTUATOR_WRITE,
                    url=f"{base_url}/actuator?scan=3&move=321",
                )
            )
        finally:
            self.assertTrue(await transport.close())
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=1.0)

        self.assertEqual(temperature.body, b"451.25")
        self.assertEqual(diagnostic.body, b"7")
        self.assertEqual(focus.body, b"OK")
        self.assertEqual(actuator.body, b"Pos--> 321")
        self.assertEqual(
            _ContractHandler.requests,
            [
                ("GET", "/temperature", b"", None),
                ("GET", "/diagnostic", b"", None),
                (
                    "PUT",
                    "/focus",
                    b"620",
                    "application/json;charset=utf-8",
                ),
                ("GET", "/actuator?scan=3&move=321", b"", None),
            ],
        )

    async def test_bind_collision_uses_a_different_guarded_lease(self) -> None:
        source_addresses: list[tuple[str, int]] = []
        connections: list[_FakeConnection] = []

        def connection_factory(
            _scheme: str,
            _host: str,
            _port: int,
            _timeout: float,
            source_address: tuple[str, int],
        ) -> _FakeConnection:
            source_addresses.append(source_address)
            connection = _FakeConnection(
                connect_error=(
                    OSError(10048, "address in use")
                    if len(source_addresses) == 1
                    else None
                )
            )
            connections.append(connection)
            return connection

        transport = SpotHttpTransport(
            pool=self.make_pool(capacity=2),
            connection_factory=connection_factory,
            bind_retry_limit=2,
        )
        transport.start()
        try:
            response = await transport.request(_request())
            diagnostics = transport.diagnostics()
        finally:
            self.assertTrue(await transport.close())

        self.assertEqual(response.body, b"ok")
        self.assertEqual(len(source_addresses), 2)
        self.assertNotEqual(source_addresses[0][1], source_addresses[1][1])
        self.assertTrue(all(connection.closed for connection in connections))
        self.assertEqual(diagnostics["source_port_bind_collision_count"], 1)

    async def test_bind_collision_exhaustion_never_falls_back_to_os_port(self) -> None:
        source_addresses: list[tuple[str, int]] = []

        def connection_factory(
            _scheme: str,
            _host: str,
            _port: int,
            _timeout: float,
            source_address: tuple[str, int],
        ) -> _FakeConnection:
            source_addresses.append(source_address)
            return _FakeConnection(connect_error=OSError(10048, "address in use"))

        transport = SpotHttpTransport(
            pool=self.make_pool(capacity=2),
            connection_factory=connection_factory,
            bind_retry_limit=2,
        )
        transport.start()
        try:
            with self.assertRaises(SpotPortBindError):
                await transport.request(_request())
            diagnostics = transport.diagnostics()
        finally:
            self.assertTrue(await transport.close())

        self.assertEqual(len(source_addresses), 2)
        self.assertTrue(all(address[1] > 0 for address in source_addresses))
        self.assertEqual(diagnostics["source_port_transport_failure_count"], 1)

    async def test_connect_and_read_timeouts_are_mapped_and_quarantined(self) -> None:
        cases = (
            {"connect_error": socket.timeout("connect timed out")},
            {"response_error": socket.timeout("read timed out")},
        )
        for connection_kwargs in cases:
            with self.subTest(connection_kwargs=tuple(connection_kwargs)):

                def connection_factory(
                    _scheme: str,
                    _host: str,
                    _port: int,
                    _timeout: float,
                    _source_address: tuple[str, int],
                ) -> _FakeConnection:
                    return _FakeConnection(**connection_kwargs)

                transport = SpotHttpTransport(
                    pool=self.make_pool(capacity=1),
                    connection_factory=connection_factory,
                )
                transport.start()
                try:
                    with self.assertRaises(SpotTransportTimeout):
                        await transport.request(_request())
                    diagnostics = transport.diagnostics()
                finally:
                    self.assertTrue(await transport.close())

                self.assertEqual(
                    diagnostics["source_port_transport_failure_count"],
                    1,
                )
                self.assertEqual(
                    diagnostics["source_port_pool_quarantined_count"],
                    1,
                )

    async def test_malformed_response_is_protocol_error_and_quarantined(self) -> None:
        def connection_factory(
            _scheme: str,
            _host: str,
            _port: int,
            _timeout: float,
            _source_address: tuple[str, int],
        ) -> _FakeConnection:
            return _FakeConnection(
                response_error=http.client.BadStatusLine("malformed-status")
            )

        transport = SpotHttpTransport(
            pool=self.make_pool(capacity=1),
            connection_factory=connection_factory,
        )
        transport.start()
        try:
            with self.assertRaises(SpotTransportProtocolError):
                await transport.request(_request())
            diagnostics = transport.diagnostics()
        finally:
            self.assertTrue(await transport.close())

        self.assertEqual(diagnostics["source_port_transport_failure_count"], 1)
        self.assertEqual(diagnostics["source_port_pool_quarantined_count"], 1)

    async def test_http_error_status_and_empty_body_are_preserved(self) -> None:
        responses = iter(
            (
                _FakeResponse(
                    status=503,
                    body=b"upstream-failure",
                    headers=[("Content-Type", "text/plain")],
                ),
                _FakeResponse(status=204, body=b"", headers=[]),
            )
        )

        def connection_factory(
            _scheme: str,
            _host: str,
            _port: int,
            _timeout: float,
            _source_address: tuple[str, int],
        ) -> _FakeConnection:
            return _FakeConnection(response=next(responses))

        transport = SpotHttpTransport(
            pool=self.make_pool(capacity=2),
            connection_factory=connection_factory,
        )
        transport.start()
        try:
            failure_response = await transport.request(_request())
            empty_response = await transport.request(
                _request(kind=SpotRequestKind.DIAGNOSTIC)
            )
            diagnostics = transport.diagnostics()
        finally:
            self.assertTrue(await transport.close())

        self.assertEqual(failure_response.status_code, 503)
        self.assertEqual(failure_response.body, b"upstream-failure")
        self.assertEqual(failure_response.headers["content-type"], "text/plain")
        self.assertEqual(empty_response.status_code, 204)
        self.assertEqual(empty_response.body, b"")
        self.assertEqual(diagnostics["source_port_transport_success_count"], 2)
        self.assertEqual(diagnostics["source_port_pool_quarantined_count"], 2)

    async def test_cancelled_waiter_does_not_release_worker_or_overlap_next_request(self) -> None:
        first_release = threading.Event()
        created_count = 0

        def connection_factory(
            _scheme: str,
            _host: str,
            _port: int,
            _timeout: float,
            _source_address: tuple[str, int],
        ) -> _FakeConnection:
            nonlocal created_count
            created_count += 1
            return _FakeConnection(
                release_response=first_release if created_count == 1 else None,
            )

        transport = SpotHttpTransport(
            pool=self.make_pool(capacity=2),
            connection_factory=connection_factory,
        )
        transport.start()
        first = asyncio.create_task(transport.request(_request()))
        await asyncio.sleep(0.02)
        first.cancel()
        second = asyncio.create_task(
            transport.request(_request(kind=SpotRequestKind.TEMPERATURE))
        )
        await asyncio.sleep(0.02)
        self.assertEqual(created_count, 1)

        first_release.set()
        with self.assertRaises(asyncio.CancelledError):
            await first
        second_response = await second
        diagnostics = transport.diagnostics()
        self.assertTrue(await transport.close())

        self.assertEqual(second_response.body, b"ok")
        self.assertEqual(created_count, 2)
        self.assertEqual(diagnostics["source_port_transport_success_count"], 2)
        self.assertEqual(diagnostics["source_port_pool_quarantined_count"], 2)

    async def test_cancelled_worker_failure_emits_privacy_safe_bounded_warning(
        self,
    ) -> None:
        release_response = threading.Event()

        def connection_factory(
            _scheme: str,
            _host: str,
            _port: int,
            _timeout: float,
            _source_address: tuple[str, int],
        ) -> _FakeConnection:
            return _FakeConnection(
                release_response=release_response,
                response_error=OSError(10054, "private endpoint detail"),
            )

        transport = SpotHttpTransport(
            pool=self.make_pool(capacity=1),
            connection_factory=connection_factory,
        )
        transport.start()
        loop = asyncio.get_running_loop()
        loop_failures: list[dict[str, object]] = []
        previous_handler = loop.get_exception_handler()
        loop.set_exception_handler(
            lambda _loop, context: loop_failures.append(dict(context))
        )
        try:
            with patch.object(transport_module._logger, "warning") as warning_mock:
                request_task = asyncio.create_task(
                    transport.request(
                        _request(url="http://secret.internal:8080/image.jpg")
                    )
                )
                await asyncio.sleep(0.02)
                request_task.cancel()
                release_response.set()
                with self.assertRaises(asyncio.CancelledError):
                    await request_task
                for _ in range(100):
                    if warning_mock.called:
                        break
                    await asyncio.sleep(0.01)
                diagnostics = transport.diagnostics()

            gc.collect()
            await asyncio.sleep(0)
        finally:
            loop.set_exception_handler(previous_handler)

        self.assertTrue(await transport.close())
        self.assertEqual(loop_failures, [])
        warning_mock.assert_called_once()
        warning_call = warning_mock.call_args
        self.assertEqual(
            warning_call.args,
            ("Cancelled SPOT HTTP worker failed",),
        )
        self.assertEqual(
            warning_call.kwargs["extra"],
            {
                "code": "spot-http-cancelled-worker-failure",
                "error_type": "SpotTransportRequestError",
            },
        )
        warning_payload = repr(warning_call)
        self.assertNotIn("secret.internal", warning_payload)
        self.assertNotIn("8080", warning_payload)
        self.assertNotIn("private endpoint detail", warning_payload)
        self.assertEqual(diagnostics["source_port_transport_failure_count"], 1)
        self.assertEqual(diagnostics["source_port_pool_quarantined_count"], 1)

    async def test_url_and_method_validation_reject_unsafe_requests(self) -> None:
        transport = SpotHttpTransport(pool=self.make_pool())
        transport.start()
        try:
            with self.assertRaises(SpotTransportProtocolError):
                await transport.request(_request(method="POST"))
            with self.assertRaises(SpotTransportProtocolError):
                await transport.request(_request(url="http://user:password@spot.local/image"))
            with self.assertRaises(SpotTransportProtocolError):
                await transport.request(_request(url="file:///tmp/image"))
        finally:
            self.assertTrue(await transport.close())

    async def test_shutdown_drain_timeout_is_bounded_and_recoverable(self) -> None:
        release_response = threading.Event()
        request_started = threading.Event()

        def connection_factory(
            _scheme: str,
            _host: str,
            _port: int,
            _timeout: float,
            _source_address: tuple[str, int],
        ) -> _FakeConnection:
            request_started.set()
            return _FakeConnection(release_response=release_response)

        transport = SpotHttpTransport(
            pool=self.make_pool(capacity=1),
            connection_factory=connection_factory,
        )
        transport.start()
        request_task = asyncio.create_task(transport.request(_request()))
        self.assertTrue(await asyncio.to_thread(request_started.wait, 1.0))

        self.assertFalse(await transport.close(timeout_sec=0.01))
        self.assertFalse(transport.active)
        with self.assertRaises(SpotTransportClosedError):
            await transport.request(_request())

        release_response.set()
        response = await request_task
        self.assertEqual(response.body, b"ok")
        self.assertTrue(await transport.close(timeout_sec=1.0))
        self.assertEqual(
            transport.diagnostics()["source_port_pool_quarantined_count"],
            0,
        )

    async def test_shutdown_rejects_new_requests(self) -> None:
        transport = SpotHttpTransport(pool=self.make_pool())
        transport.start()
        self.assertTrue(await transport.close())

        with self.assertRaises(SpotTransportClosedError):
            await transport.request(_request())


if __name__ == "__main__":
    unittest.main()
