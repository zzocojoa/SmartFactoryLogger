from __future__ import annotations

import asyncio
import http.client
import logging
import socket
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Protocol
from urllib.parse import SplitResult, urlsplit

from backend.FacilityData.drivers.spot_port_quarantine import (
    ACQUIRE_TIMEOUT_SECONDS,
    POOL_CAPACITY,
    QUARANTINE_SECONDS,
    SourcePortLeasePool,
    SpotPortPoolError,
    SpotPortPoolInitError,
)

BIND_RETRY_LIMIT = 8
_ALLOWED_METHODS = frozenset({"GET", "PUT"})
_BIND_COLLISION_ERRNOS = frozenset({98, 10048})
_logger = logging.getLogger("spot_control")


class SpotRequestKind(str, Enum):
    IMAGE = "image"
    TEMPERATURE = "temperature"
    INTERNAL_TEMPERATURE = "internal_temperature"
    DIAGNOSTIC = "diagnostic"
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
        if bind_retry_limit <= 0:
            raise ValueError("bind_retry_limit must be positive")
        self._pool = pool or SourcePortLeasePool()
        self._connection_factory = connection_factory
        self._bind_retry_limit = int(bind_retry_limit)
        self._monotonic = monotonic
        self._executor: ThreadPoolExecutor | None = None
        self._state_lock = threading.RLock()
        self._request_lock = threading.Lock()
        self._pending: set[Future[SpotHttpResponse]] = set()
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
            if self._active:
                self._accepting = True
                return True
            if self._closed:
                raise SpotTransportClosedError("SPOT transport is closed")
            if not self.supported:
                if sys.platform == "win32":
                    raise SpotPortPoolInitError(
                        "exclusive source-port enforcement is unavailable on Windows"
                    )
                return False
            self._pool.initialize()
            self._executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="spot-http-transport",
            )
            self._active = True
            self._accepting = True
            return True

    async def request(self, request: SpotHttpRequest) -> SpotHttpResponse:
        self._validate_request(request)
        with self._state_lock:
            if not self._accepting or not self._active or self._executor is None:
                raise SpotTransportClosedError("SPOT transport is not accepting requests")
            future = self._executor.submit(self.request_sync, request)
            self._pending.add(future)
            future.add_done_callback(self._discard_pending)
        wrapped = asyncio.wrap_future(future)
        try:
            return await asyncio.shield(wrapped)
        except asyncio.CancelledError:
            future.add_done_callback(self._consume_cancelled_result)
            wrapped.add_done_callback(self._consume_cancelled_wrapped_result)
            raise

    def request_sync(self, request: SpotHttpRequest) -> SpotHttpResponse:
        self._validate_request(request)
        with self._state_lock:
            if not self._accepting or not self._active:
                raise SpotTransportClosedError("SPOT transport is not accepting requests")
        with self._request_lock:
            self._record_started(request.kind)
            try:
                response = self._request_with_bind_retries(request)
            except BaseException:
                self._record_failure(request.kind)
                raise
            self._record_success(request.kind)
            return response

    async def close(self, timeout_sec: float = 7.0) -> bool:
        with self._state_lock:
            if self._closed:
                return True
            self._accepting = False
            executor = self._executor
        if executor is None:
            with self._state_lock:
                self._active = False
                self._closed = True
            self._pool.close()
            return True

        shutdown_task = asyncio.create_task(
            asyncio.to_thread(executor.shutdown, wait=True, cancel_futures=True)
        )
        try:
            await asyncio.wait_for(
                asyncio.shield(shutdown_task),
                timeout=max(0.0, timeout_sec),
            )
        except asyncio.TimeoutError:
            return False

        self._pool.close()
        with self._state_lock:
            self._executor = None
            self._active = False
            self._closed = True
        return True

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
            lease = self._pool.acquire(ACQUIRE_TIMEOUT_SECONDS)
            connection: _Connection | None = None
            started_at = self._monotonic()
            try:
                self._pool.mark_connect_started(lease)
                connection = self._connection_factory(
                    parts.scheme,
                    host,
                    port,
                    request.connect_timeout_sec,
                    ("", lease.port),
                )
                connection.connect()
                if connection.sock is not None:
                    connection.sock.settimeout(request.read_timeout_sec)
                connection.request(
                    request.method.upper(),
                    origin_form,
                    body=request.body,
                    headers=dict(request.headers),
                )
                upstream = connection.getresponse()
                body = upstream.read()
                headers = {key.lower(): value for key, value in upstream.getheaders()}
                return SpotHttpResponse(
                    status_code=int(upstream.status),
                    headers=headers,
                    body=bytes(body),
                    elapsed_ms=max(0.0, (self._monotonic() - started_at) * 1000.0),
                )
            except (socket.timeout, TimeoutError) as exc:
                raise SpotTransportTimeout("SPOT transport timed out") from exc
            except OSError as exc:
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
                raise SpotTransportProtocolError(
                    f"SPOT HTTP protocol failed: {exc.__class__.__name__}"
                ) from exc
            except SpotPortPoolError:
                raise
            finally:
                if connection is not None:
                    try:
                        connection.close()
                    except OSError:
                        pass
                self._pool.release(lease)
        raise SpotPortBindError("SPOT source-port bind retry limit was exhausted")

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
        if request.connect_timeout_sec <= 0.0 or request.read_timeout_sec <= 0.0:
            raise SpotTransportProtocolError("SPOT HTTP timeouts must be positive")
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


__all__ = [
    "BIND_RETRY_LIMIT",
    "POOL_CAPACITY",
    "QUARANTINE_SECONDS",
    "SourcePortLeasePool",
    "SpotHttpRequest",
    "SpotHttpResponse",
    "SpotHttpTransport",
    "SpotPortBindError",
    "SpotRequestKind",
    "SpotTransportClosedError",
    "SpotTransportError",
    "SpotTransportProtocolError",
    "SpotTransportRequestError",
    "SpotTransportTimeout",
]
