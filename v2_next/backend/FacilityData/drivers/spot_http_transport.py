from __future__ import annotations

import asyncio
import http.client
import logging
import math
import socket
import sys
import threading
import time
from concurrent.futures import Future, InvalidStateError
from dataclasses import dataclass, replace
from enum import Enum
from queue import Empty, Queue
from typing import Callable, Mapping, Protocol
from urllib.parse import SplitResult, urljoin, urlsplit

from backend.FacilityData.drivers.spot_port_quarantine import (
    POOL_CAPACITY,
    QUARANTINE_SECONDS,
    SourcePortLease,
    SourcePortLeasePool,
    SpotPortPoolError,
    SpotPortPoolInitError,
)

BIND_RETRY_LIMIT = 8
DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024
HARD_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_REDIRECT_HOPS = 5
_RESPONSE_READ_CHUNK_BYTES = 64 * 1024
_ALLOWED_METHODS = frozenset({"GET", "HEAD", "PUT"})
_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
_BIND_COLLISION_ERRNOS = frozenset({98, 10048})
_logger = logging.getLogger("spot_control")


class SpotRequestKind(str, Enum):
    IMAGE = "image"
    TEMPERATURE = "temperature"
    INTERNAL_TEMPERATURE = "internal_temperature"
    DIAGNOSTIC = "diagnostic"
    CONNECTION_TEST = "connection_test"
    FOCUS_READ = "focus_read"
    FOCUS_WRITE = "focus_write"
    ACTUATOR_READ = "actuator_read"
    ACTUATOR_WRITE = "actuator_write"


@dataclass(frozen=True)
class SpotHttpRequest:
    kind: SpotRequestKind
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None
    connect_timeout_sec: float
    read_timeout_sec: float
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    read_response_body: bool = True


@dataclass(frozen=True)
class SpotHttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes
    elapsed_ms: float


class SpotTransportError(RuntimeError):
    """Base error for the guarded stdlib SPOT HTTP transport."""


class SpotPortBindError(SpotTransportError):
    """Raised after bounded source-port bind collision retries."""


class SpotTransportTimeout(SpotTransportError):
    """Raised for connect or response timeout."""


class SpotTransportConnectTimeout(SpotTransportTimeout):
    """Raised when the guarded socket cannot connect before its timeout."""


class SpotTransportReadTimeout(SpotTransportTimeout):
    """Raised when an established guarded request exceeds its response timeout."""


class SpotTransportRequestError(SpotTransportError):
    """Raised for DNS, connect, send, or receive failures."""


class SpotTransportProtocolError(SpotTransportError):
    """Raised for invalid URLs or malformed HTTP responses."""


class SpotTransportClosedError(SpotTransportError):
    """Raised after transport intake has been closed."""


class _Connection(Protocol):
    sock: socket.socket | None

    def connect(self) -> None: ...

    def request(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
    ) -> None: ...

    def getresponse(self) -> http.client.HTTPResponse: ...

    def close(self) -> None: ...


ConnectionFactory = Callable[
    [str, str, int, float, tuple[str, int]],
    _Connection,
]


@dataclass(frozen=True)
class _WorkItem:
    future: Future[SpotHttpResponse]
    request: SpotHttpRequest


@dataclass(frozen=True)
class _ConnectionInterruptTarget:
    connection: _Connection
    response_socket: object | None = None


class _DaemonSingleWorker:
    """One daemon worker with cancellable queued futures and no exit-time join."""

    def __init__(
        self,
        handler: Callable[[SpotHttpRequest], SpotHttpResponse],
    ) -> None:
        self._handler = handler
        self._queue: Queue[_WorkItem | None] = Queue()
        self._state_lock = threading.Lock()
        self._accepting = True
        self._current_future: Future[SpotHttpResponse] | None = None
        self._thread = threading.Thread(
            target=self._run,
            name="spot-http-transport",
            daemon=True,
        )
        self._thread.start()

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def submit(self, request: SpotHttpRequest) -> Future[SpotHttpResponse]:
        future: Future[SpotHttpResponse] = Future()
        with self._state_lock:
            if not self._accepting:
                raise RuntimeError("SPOT HTTP worker is closed")
            self._queue.put(_WorkItem(future=future, request=request))
        return future

    def shutdown(self, *, cancel_futures: bool) -> None:
        with self._state_lock:
            if not self._accepting:
                return
            self._accepting = False
            if cancel_futures:
                self._fail_queued_locked()
            self._queue.put(None)

    def abandon_current(self, failure: BaseException) -> None:
        with self._state_lock:
            future = self._current_future
        if future is None or future.done():
            return
        try:
            future.set_exception(failure)
        except InvalidStateError:
            pass

    def _fail_queued_locked(self) -> None:
        retained_sentinel = False
        while True:
            try:
                item = self._queue.get_nowait()
            except Empty:
                break
            if item is None:
                retained_sentinel = True
                continue
            try:
                item.future.set_exception(
                    SpotTransportClosedError(
                        "SPOT transport is not accepting requests"
                    )
                )
            except InvalidStateError:
                pass
        if retained_sentinel:
            self._queue.put(None)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            future = item.future
            if future.cancelled():
                continue
            with self._state_lock:
                self._current_future = future
            try:
                result = self._handler(item.request)
            except BaseException as exc:
                try:
                    future.set_exception(exc)
                except InvalidStateError:
                    pass
            else:
                try:
                    future.set_result(result)
                except InvalidStateError:
                    pass
            finally:
                with self._state_lock:
                    if self._current_future is future:
                        self._current_future = None


def _default_connection_factory(
    scheme: str,
    host: str,
    port: int,
    timeout: float,
    source_address: tuple[str, int],
) -> _Connection:
    connection_type: type[http.client.HTTPConnection]
    connection_type = (
        http.client.HTTPSConnection
        if scheme == "https"
        else http.client.HTTPConnection
    )
    return connection_type(
        host,
        port=port,
        timeout=timeout,
        source_address=source_address,
    )


class SpotHttpTransport:
    def __init__(
        self,
        *,
        pool: SourcePortLeasePool | None = None,
        connection_factory: ConnectionFactory = _default_connection_factory,
        bind_retry_limit: int = BIND_RETRY_LIMIT,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        normalized_bind_retry_limit = int(bind_retry_limit)
        if (
            isinstance(bind_retry_limit, bool)
            or normalized_bind_retry_limit != bind_retry_limit
            or normalized_bind_retry_limit <= 0
        ):
            raise ValueError("bind_retry_limit must be positive")
        self._pool = pool or SourcePortLeasePool()
        self._connection_factory = connection_factory
        self._bind_retry_limit = normalized_bind_retry_limit
        self._monotonic = monotonic
        self._executor: _DaemonSingleWorker | None = None
        self._state_lock = threading.RLock()
        self._response_deadline_condition = threading.Condition(self._state_lock)
        self._response_deadline_thread: threading.Thread | None = None
        self._response_deadline_stop = False
        self._response_deadline_target: _ConnectionInterruptTarget | None = None
        self._response_deadline_expired: threading.Event | None = None
        self._response_deadline_at: float | None = None
        self._response_deadline_token = 0
        self._request_lock = threading.Lock()
        self._pending: set[Future[SpotHttpResponse]] = set()
        self._active_connections: dict[int, _ConnectionInterruptTarget] = {}
        self._shutdown_task: asyncio.Task[bool] | None = None
        self._shutdown_result: bool | None = None
        self._active = False
        self._accepting = False
        self._closed = False
        self._started_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._bind_collision_count = 0
        self._kind_started_count = {kind.value: 0 for kind in SpotRequestKind}
        self._kind_success_count = {kind.value: 0 for kind in SpotRequestKind}
        self._kind_failure_count = {kind.value: 0 for kind in SpotRequestKind}

    @property
    def supported(self) -> bool:
        return self._pool.supported

    @property
    def active(self) -> bool:
        with self._state_lock:
            return self._active and self._accepting and not self._closed

    def start(self) -> bool:
        with self._state_lock:
            if self._shutdown_task is not None or self._closed:
                raise SpotTransportClosedError("SPOT transport is closed")
            if self._active:
                if not self._accepting:
                    raise SpotTransportClosedError("SPOT transport is closing")
                return True
            if not self.supported:
                if sys.platform == "win32":
                    raise SpotPortPoolInitError(
                        "exclusive source-port enforcement is unavailable on Windows"
                    )
                return False
            self._pool.initialize()
            self._start_response_deadline_watchdog_locked()
            self._executor = _DaemonSingleWorker(self._execute_request_sync)
            self._active = True
            self._accepting = True
            return True

    async def request(self, request: SpotHttpRequest) -> SpotHttpResponse:
        future = self._submit_request(request)
        wrapped = asyncio.wrap_future(future)
        try:
            return await asyncio.shield(wrapped)
        except asyncio.CancelledError:
            future.add_done_callback(self._consume_cancelled_result)
            wrapped.add_done_callback(self._consume_cancelled_wrapped_result)
            raise

    def request_sync(self, request: SpotHttpRequest) -> SpotHttpResponse:
        future = self._submit_request(request)
        return future.result()

    def _submit_request(self, request: SpotHttpRequest) -> Future[SpotHttpResponse]:
        self._validate_request(request)
        with self._state_lock:
            executor = self._executor
            if not self._accepting or not self._active or executor is None:
                raise SpotTransportClosedError("SPOT transport is not accepting requests")
            try:
                future = executor.submit(request)
            except RuntimeError as exc:
                raise SpotTransportClosedError(
                    "SPOT transport is not accepting requests"
                ) from exc
            self._pending.add(future)
            future.add_done_callback(self._discard_pending)
            return future

    def _execute_request_sync(self, request: SpotHttpRequest) -> SpotHttpResponse:
        with self._request_lock:
            with self._state_lock:
                if not self._accepting or not self._active:
                    raise SpotTransportClosedError(
                        "SPOT transport is not accepting requests"
                    )
            self._record_started(request.kind)
            try:
                response = self._request_with_redirects(request)
            except BaseException:
                self._record_failure(request.kind)
                raise
            self._record_success(request.kind)
            return response

    def _request_with_redirects(
        self,
        request: SpotHttpRequest,
    ) -> SpotHttpResponse:
        current_request = request
        for hop in range(MAX_REDIRECT_HOPS + 1):
            response = self._request_with_bind_retries(current_request)
            location = response.headers.get("location")
            if (
                current_request.method.upper() not in {"GET", "HEAD"}
                or response.status_code not in _REDIRECT_STATUS_CODES
                or not location
            ):
                return response
            if hop >= MAX_REDIRECT_HOPS:
                raise SpotTransportProtocolError(
                    "SPOT HTTP redirect limit was exceeded"
                )
            current_request = replace(
                current_request,
                url=resolve_spot_redirect_url(
                    current_request.url,
                    location,
                ),
            )
        raise SpotTransportProtocolError("SPOT HTTP redirect limit was exceeded")

    async def close(self, timeout_sec: float = 7.0) -> bool:
        with self._state_lock:
            if self._closed:
                executor = self._executor
                if self._shutdown_result is not False:
                    return True
                if executor is not None and not executor.is_alive:
                    self._executor = None
                    self._shutdown_result = True
                    return True
                return False
            self._accepting = False
            shutdown_task = self._shutdown_task
            if shutdown_task is None:
                shutdown_task = asyncio.create_task(
                    self._run_shutdown(max(0.0, timeout_sec))
                )
                self._shutdown_task = shutdown_task
        return await asyncio.shield(shutdown_task)

    async def _run_shutdown(self, timeout_sec: float) -> bool:
        with self._state_lock:
            executor = self._executor
        if executor is None:
            drained = True
        else:
            executor.shutdown(cancel_futures=True)
            self._interrupt_active_connections()
            deadline = asyncio.get_running_loop().time() + timeout_sec
            while executor.is_alive and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(
                    min(
                        0.01,
                        max(0.0, deadline - asyncio.get_running_loop().time()),
                    )
                )
            drained = not executor.is_alive
            if not drained:
                failure = SpotTransportClosedError(
                    "SPOT transport shutdown timed out"
                )
                executor.abandon_current(failure)
                self._interrupt_active_connections()

        pool_error: Exception | None = None
        try:
            self._pool.close()
        except Exception as exc:
            pool_error = exc
        finally:
            self._stop_response_deadline_watchdog()
            with self._state_lock:
                self._active = False
                self._closed = pool_error is None
                self._shutdown_result = drained and pool_error is None
                if drained:
                    self._executor = None
                if pool_error is not None:
                    self._shutdown_task = None
        if pool_error is not None:
            raise pool_error
        return drained

    def _interrupt_active_connections(self) -> None:
        with self._state_lock:
            targets = list(self._active_connections.values())
        for target in targets:
            self._interrupt_target(target)

    @classmethod
    def _interrupt_target(cls, target: _ConnectionInterruptTarget) -> None:
        if target.response_socket is not None:
            cls._interrupt_socket(target.response_socket)
            return
        cls._interrupt_connection(target.connection)

    @staticmethod
    def _interrupt_connection(connection: _Connection) -> None:
        sock = getattr(connection, "sock", None)
        if sock is not None:
            if SpotHttpTransport._interrupt_socket(sock):
                # HTTPConnection.close() also closes its HTTPResponse. Calling it
                # here can block on the buffered reader lock held by the worker.
                # The interrupted worker owns final connection cleanup.
                return
        try:
            connection.close()
        except OSError:
            pass

    @staticmethod
    def _interrupt_socket(sock: object) -> bool:
        socket_interrupt_attempted = False
        shutdown = getattr(sock, "shutdown", None)
        if callable(shutdown):
            socket_interrupt_attempted = True
            try:
                shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        close_socket = getattr(sock, "close", None)
        if callable(close_socket):
            socket_interrupt_attempted = True
            try:
                close_socket()
            except OSError:
                pass
        return socket_interrupt_attempted

    def _retarget_response_deadline(
        self,
        token: int,
        target: _ConnectionInterruptTarget,
        expired: threading.Event,
    ) -> bool:
        with self._response_deadline_condition:
            still_armed = (
                token == self._response_deadline_token
                and self._response_deadline_target is not None
                and self._response_deadline_expired is expired
                and not expired.is_set()
            )
            if still_armed:
                self._response_deadline_target = target
                self._active_connections[id(target.connection)] = target
                self._response_deadline_condition.notify_all()
                return True

        self._interrupt_target(target)
        return False

    @staticmethod
    def _close_response(upstream: http.client.HTTPResponse) -> None:
        close = getattr(upstream, "close", None)
        if not callable(close):
            return
        try:
            close()
        except OSError:
            pass

    def _register_connection(self, connection: _Connection) -> None:
        with self._state_lock:
            if not self._accepting or not self._active:
                try:
                    connection.close()
                except OSError:
                    pass
                raise SpotTransportClosedError(
                    "SPOT transport is not accepting requests"
                )
            self._active_connections[id(connection)] = _ConnectionInterruptTarget(
                connection=connection
            )

    def _discard_connection(self, connection: _Connection) -> None:
        with self._state_lock:
            self._active_connections.pop(id(connection), None)

    def _start_response_deadline_watchdog_locked(self) -> None:
        thread = self._response_deadline_thread
        if thread is not None and thread.is_alive():
            return
        self._response_deadline_stop = False
        thread = threading.Thread(
            target=self._run_response_deadline_watchdog,
            name=f"spot-http-deadline-{id(self):x}",
            daemon=True,
        )
        self._response_deadline_thread = thread
        thread.start()

    def _run_response_deadline_watchdog(self) -> None:
        while True:
            with self._response_deadline_condition:
                while (
                    not self._response_deadline_stop
                    and self._response_deadline_target is None
                ):
                    self._response_deadline_condition.wait()
                if self._response_deadline_stop:
                    return

                deadline_at = self._response_deadline_at
                if deadline_at is None:
                    continue
                remaining = deadline_at - time.monotonic()
                if remaining > 0.0:
                    self._response_deadline_condition.wait(timeout=remaining)
                    continue

                target = self._response_deadline_target
                expired = self._response_deadline_expired
                if expired is not None:
                    expired.set()
                self._response_deadline_target = None
                self._response_deadline_expired = None
                self._response_deadline_at = None

            if target is not None and expired is not None:
                self._interrupt_target(target)

    def _arm_response_deadline(
        self,
        connection: _Connection,
        *,
        deadline_at: float,
        expired: threading.Event,
    ) -> int:
        with self._response_deadline_condition:
            if self._response_deadline_stop:
                raise SpotTransportClosedError(
                    "SPOT response deadline watchdog is closed"
                )
            self._response_deadline_token += 1
            token = self._response_deadline_token
            self._response_deadline_target = _ConnectionInterruptTarget(
                connection=connection
            )
            self._response_deadline_expired = expired
            self._response_deadline_at = deadline_at
            self._response_deadline_condition.notify_all()
            return token

    def _disarm_response_deadline(self, token: int) -> None:
        with self._response_deadline_condition:
            if token != self._response_deadline_token:
                return
            self._response_deadline_target = None
            self._response_deadline_expired = None
            self._response_deadline_at = None
            self._response_deadline_condition.notify_all()

    def _stop_response_deadline_watchdog(self) -> None:
        with self._response_deadline_condition:
            self._response_deadline_stop = True
            self._response_deadline_target = None
            self._response_deadline_expired = None
            self._response_deadline_at = None
            thread = self._response_deadline_thread
            self._response_deadline_condition.notify_all()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=0.1)
        with self._response_deadline_condition:
            if thread is None or not thread.is_alive():
                self._response_deadline_thread = None

    def _release_lease(self, lease: SourcePortLease) -> None:
        try:
            self._pool.release(lease)
        except SpotPortPoolError:
            with self._state_lock:
                shutting_down = not self._accepting
            if not shutting_down:
                raise

    def diagnostics(self) -> dict[str, object]:
        pool_diagnostics = self._pool.diagnostics()
        with self._state_lock:
            payload: dict[str, object] = {
                **pool_diagnostics,
                "source_port_transport_started_count": self._started_count,
                "source_port_transport_success_count": self._success_count,
                "source_port_transport_failure_count": self._failure_count,
                "source_port_bind_collision_count": self._bind_collision_count,
                "source_port_transport_pending_count": len(self._pending),
            }
            for kind in SpotRequestKind:
                key = kind.value
                payload[f"source_port_{key}_started_count"] = self._kind_started_count[key]
                payload[f"source_port_{key}_success_count"] = self._kind_success_count[key]
                payload[f"source_port_{key}_failure_count"] = self._kind_failure_count[key]
            return payload

    def _request_with_bind_retries(self, request: SpotHttpRequest) -> SpotHttpResponse:
        parts, host, port, origin_form = self._parse_url(request.url)
        for attempt in range(self._bind_retry_limit):
            lease = self._pool.acquire()
            connection: _Connection | None = None
            upstream: http.client.HTTPResponse | None = None
            response_deadline_token: int | None = None
            response_deadline_expired = threading.Event()
            response_deadline_at: float | None = None
            started_at = self._monotonic()
            request_phase = "connect"
            try:
                self._pool.mark_connect_started(lease)
                connection = self._connection_factory(
                    parts.scheme,
                    host,
                    port,
                    request.connect_timeout_sec,
                    ("", lease.port),
                )
                self._register_connection(connection)
                connection.connect()
                request_phase = "response"
                if connection.sock is not None:
                    connection.sock.settimeout(request.read_timeout_sec)
                response_deadline_at = time.monotonic() + request.read_timeout_sec
                response_deadline_token = self._arm_response_deadline(
                    connection,
                    deadline_at=response_deadline_at,
                    expired=response_deadline_expired,
                )
                connection.request(
                    request.method.upper(),
                    origin_form,
                    body=request.body,
                    headers=dict(request.headers),
                )
                # HTTPConnection.getresponse() clears connection.sock for
                # connection-close responses. Retain the public socket before
                # that ownership transfer so the watchdog never depends on
                # HTTPResponse's private fp/raw implementation layout.
                response_socket = connection.sock
                upstream = connection.getresponse()
                response_target = _ConnectionInterruptTarget(
                    connection=connection,
                    response_socket=response_socket,
                )
                if not self._retarget_response_deadline(
                    response_deadline_token,
                    response_target,
                    response_deadline_expired,
                ):
                    raise SpotTransportReadTimeout(
                        "SPOT transport response deadline expired"
                    )
                raw_headers = list(upstream.getheaders())
                body = (
                    self._read_bounded_response(
                        upstream,
                        raw_headers=raw_headers,
                        max_response_bytes=request.max_response_bytes,
                    )
                    if request.read_response_body
                    else b""
                )
                if (
                    response_deadline_expired.is_set()
                    or (
                        response_deadline_at is not None
                        and time.monotonic() >= response_deadline_at
                    )
                ):
                    raise SpotTransportReadTimeout(
                        "SPOT transport response deadline expired"
                    )
                headers = {key.lower(): value for key, value in raw_headers}
                return SpotHttpResponse(
                    status_code=int(upstream.status),
                    headers=headers,
                    body=bytes(body),
                    elapsed_ms=max(0.0, (self._monotonic() - started_at) * 1000.0),
                )
            except (socket.timeout, TimeoutError) as exc:
                if request_phase == "connect" and not response_deadline_expired.is_set():
                    raise SpotTransportConnectTimeout(
                        "SPOT transport connect timed out"
                    ) from exc
                raise SpotTransportReadTimeout(
                    "SPOT transport response timed out"
                ) from exc
            except OSError as exc:
                if response_deadline_expired.is_set():
                    raise SpotTransportReadTimeout(
                        "SPOT transport response deadline expired"
                    ) from exc
                if self._is_bind_collision(exc):
                    with self._state_lock:
                        self._bind_collision_count += 1
                    if attempt + 1 >= self._bind_retry_limit:
                        raise SpotPortBindError(
                            "SPOT source-port bind retry limit was exhausted"
                        ) from exc
                    continue
                raise SpotTransportRequestError(self._safe_os_error(exc)) from exc
            except http.client.HTTPException as exc:
                if response_deadline_expired.is_set():
                    raise SpotTransportReadTimeout(
                        "SPOT transport response deadline expired"
                    ) from exc
                raise SpotTransportProtocolError(
                    f"SPOT HTTP protocol failed: {exc.__class__.__name__}"
                ) from exc
            except SpotPortPoolError:
                raise
            finally:
                if response_deadline_token is not None:
                    self._disarm_response_deadline(response_deadline_token)
                if upstream is not None:
                    self._close_response(upstream)
                if connection is not None:
                    self._discard_connection(connection)
                    try:
                        connection.close()
                    except OSError:
                        pass
                self._release_lease(lease)
        raise SpotPortBindError("SPOT source-port bind retry limit was exhausted")

    @staticmethod
    def _read_bounded_response(
        upstream: http.client.HTTPResponse,
        *,
        raw_headers: list[tuple[str, str]],
        max_response_bytes: int,
    ) -> bytes:
        content_length: int | None = None
        content_lengths = {
            value.strip()
            for key, value in raw_headers
            if key.lower() == "content-length"
        }
        if len(content_lengths) > 1:
            raise SpotTransportProtocolError(
                "SPOT response has conflicting Content-Length headers"
            )
        if content_lengths:
            content_length_text = next(iter(content_lengths))
            try:
                content_length = int(content_length_text, 10)
            except ValueError as exc:
                raise SpotTransportProtocolError(
                    "SPOT response Content-Length is invalid"
                ) from exc
            if content_length < 0:
                raise SpotTransportProtocolError(
                    "SPOT response Content-Length is invalid"
                )
            if content_length > max_response_bytes:
                raise SpotTransportProtocolError(
                    "SPOT response exceeds the configured byte limit"
                )

        chunks: list[bytes] = []
        total_bytes = 0
        while True:
            remaining_with_sentinel = max_response_bytes - total_bytes + 1
            chunk = upstream.read(
                min(_RESPONSE_READ_CHUNK_BYTES, remaining_with_sentinel)
            )
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_response_bytes:
                raise SpotTransportProtocolError(
                    "SPOT response exceeds the configured byte limit"
                )
            chunks.append(bytes(chunk))
        if content_length is not None and total_bytes != content_length:
            raise SpotTransportProtocolError(
                "SPOT response body length does not match Content-Length"
            )
        return b"".join(chunks)

    def _record_started(self, kind: SpotRequestKind) -> None:
        with self._state_lock:
            self._started_count += 1
            self._kind_started_count[kind.value] += 1

    def _record_success(self, kind: SpotRequestKind) -> None:
        with self._state_lock:
            self._success_count += 1
            self._kind_success_count[kind.value] += 1

    def _record_failure(self, kind: SpotRequestKind) -> None:
        with self._state_lock:
            self._failure_count += 1
            self._kind_failure_count[kind.value] += 1

    @staticmethod
    def _validate_request(request: SpotHttpRequest) -> None:
        if request.method.upper() not in _ALLOWED_METHODS:
            raise SpotTransportProtocolError("SPOT HTTP method is not allowed")
        if (
            not math.isfinite(request.connect_timeout_sec)
            or not math.isfinite(request.read_timeout_sec)
            or request.connect_timeout_sec <= 0.0
            or request.read_timeout_sec <= 0.0
        ):
            raise SpotTransportProtocolError(
                "SPOT HTTP timeouts must be finite and positive"
            )
        if (
            isinstance(request.max_response_bytes, bool)
            or not isinstance(request.max_response_bytes, int)
            or not 1 <= request.max_response_bytes <= HARD_MAX_RESPONSE_BYTES
        ):
            raise SpotTransportProtocolError(
                "SPOT HTTP response byte limit is invalid"
            )
        SpotHttpTransport._parse_url(request.url)

    @staticmethod
    def _parse_url(url: str) -> tuple[SplitResult, str, int, str]:
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError as exc:
            raise SpotTransportProtocolError("SPOT URL is invalid") from exc
        if parts.scheme not in {"http", "https"}:
            raise SpotTransportProtocolError("SPOT URL scheme is not allowed")
        if not parts.hostname or parts.username is not None or parts.password is not None:
            raise SpotTransportProtocolError("SPOT URL authority is invalid")
        if parts.fragment:
            raise SpotTransportProtocolError("SPOT URL fragments are not allowed")
        origin_form = parts.path or "/"
        if parts.query:
            origin_form = f"{origin_form}?{parts.query}"
        return (
            parts,
            parts.hostname,
            int(port or (443 if parts.scheme == "https" else 80)),
            origin_form,
        )

    @staticmethod
    def _is_bind_collision(exc: OSError) -> bool:
        codes = {
            int(value)
            for value in (getattr(exc, "errno", None), getattr(exc, "winerror", None))
            if value is not None
        }
        return bool(codes & _BIND_COLLISION_ERRNOS)

    @staticmethod
    def _safe_os_error(exc: OSError) -> str:
        code = getattr(exc, "winerror", None)
        if code is None:
            code = getattr(exc, "errno", None)
        code_text = "unknown" if code is None else str(code)
        return f"SPOT transport request failed: {exc.__class__.__name__}; code={code_text}"

    @staticmethod
    def _consume_cancelled_result(future: Future[SpotHttpResponse]) -> None:
        try:
            failure = future.exception()
        except BaseException:
            return
        if failure is None:
            return
        _logger.warning(
            "Cancelled SPOT HTTP worker failed",
            extra={
                "code": "spot-http-cancelled-worker-failure",
                "error_type": failure.__class__.__name__,
            },
        )

    @staticmethod
    def _consume_cancelled_wrapped_result(
        future: asyncio.Future[SpotHttpResponse],
    ) -> None:
        if future.cancelled():
            return
        try:
            future.exception()
        except BaseException:
            return

    def _discard_pending(self, future: Future[SpotHttpResponse]) -> None:
        with self._state_lock:
            self._pending.discard(future)


def resolve_spot_redirect_url(current_url: str, location: str) -> str:
    normalized_location = location.strip()
    if not normalized_location:
        raise SpotTransportProtocolError("SPOT HTTP redirect location is empty")
    target_url = urljoin(current_url, normalized_location)
    current_parts, current_host, current_port, _ = SpotHttpTransport._parse_url(
        current_url
    )
    target_parts, target_host, target_port, _ = SpotHttpTransport._parse_url(
        target_url
    )
    current_origin = (
        current_parts.scheme,
        current_host.lower(),
        current_port,
    )
    target_origin = (
        target_parts.scheme,
        target_host.lower(),
        target_port,
    )
    if target_origin != current_origin:
        raise SpotTransportProtocolError(
            "SPOT HTTP redirect target is outside the configured device origin"
        )
    return target_url


__all__ = [
    "BIND_RETRY_LIMIT",
    "HARD_MAX_RESPONSE_BYTES",
    "MAX_REDIRECT_HOPS",
    "POOL_CAPACITY",
    "QUARANTINE_SECONDS",
    "SourcePortLeasePool",
    "SpotHttpRequest",
    "SpotHttpResponse",
    "SpotHttpTransport",
    "SpotPortBindError",
    "SpotRequestKind",
    "SpotTransportConnectTimeout",
    "SpotTransportClosedError",
    "SpotTransportError",
    "SpotTransportProtocolError",
    "SpotTransportReadTimeout",
    "SpotTransportRequestError",
    "SpotTransportTimeout",
    "resolve_spot_redirect_url",
]
