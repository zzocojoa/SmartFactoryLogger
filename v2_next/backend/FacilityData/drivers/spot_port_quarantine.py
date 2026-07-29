from __future__ import annotations

import math
import socket
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

POLICY_VERSION = "spot-source-port-quarantine-v2"
POOL_CAPACITY = 768
QUARANTINE_SECONDS = 75.0
ACQUIRE_TIMEOUT_SECONDS = 5.0
REBIND_RETRY_INTERVAL_SECONDS = 1.0


class SpotPortPoolError(RuntimeError):
    """Base error for deterministic SPOT source-port allocation."""


class SpotPortPoolInitError(SpotPortPoolError):
    """Raised when the complete exclusive guard pool cannot be created."""


class SpotPortPoolExhausted(SpotPortPoolError):
    """Raised when no guarded source port becomes available before timeout."""


class SpotPortReuseViolation(SpotPortPoolError):
    """Raised when the quarantine invariant is violated."""


class _GuardSocket(Protocol):
    def close(self) -> None: ...


class GuardSocketFactory(Protocol):
    @property
    def supported(self) -> bool: ...

    def create_guard(self, local_host: str, port: int = 0) -> tuple[_GuardSocket, int]: ...


class SystemGuardSocketFactory:
    @property
    def supported(self) -> bool:
        return sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE")

    def create_guard(self, local_host: str, port: int = 0) -> tuple[socket.socket, int]:
        if not self.supported:
            raise SpotPortPoolInitError("exclusive source-port guards are unsupported")
        guard = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        try:
            guard.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            guard.bind((local_host, port))
            actual_port = int(guard.getsockname()[1])
            if actual_port <= 0:
                raise OSError("operating system returned an invalid source port")
            return guard, actual_port
        except BaseException:
            guard.close()
            raise


@dataclass(frozen=True)
class SourcePortLease:
    port: int
    _record_id: int


@dataclass
class _PortRecord:
    record_id: int
    port: int
    guard: _GuardSocket | None
    state: str = "guarded"
    quarantine_until: float | None = None
    retry_at: float | None = None
    last_connect_started: float | None = None


class SourcePortLeasePool:
    def __init__(
        self,
        *,
        capacity: int = POOL_CAPACITY,
        quarantine_seconds: float = QUARANTINE_SECONDS,
        acquire_timeout_seconds: float = ACQUIRE_TIMEOUT_SECONDS,
        rebind_retry_interval_seconds: float = REBIND_RETRY_INTERVAL_SECONDS,
        local_host: str = "",
        socket_factory: GuardSocketFactory | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        normalized_capacity = int(capacity)
        normalized_quarantine_seconds = float(quarantine_seconds)
        normalized_acquire_timeout_seconds = float(acquire_timeout_seconds)
        normalized_rebind_retry_interval_seconds = float(
            rebind_retry_interval_seconds
        )
        if (
            isinstance(capacity, bool)
            or normalized_capacity != capacity
            or normalized_capacity <= 0
        ):
            raise ValueError("capacity must be positive")
        if (
            not math.isfinite(normalized_quarantine_seconds)
            or normalized_quarantine_seconds <= 0.0
        ):
            raise ValueError("quarantine_seconds must be positive")
        if (
            not math.isfinite(normalized_acquire_timeout_seconds)
            or normalized_acquire_timeout_seconds < 0.0
        ):
            raise ValueError("acquire_timeout_seconds must not be negative")
        if (
            not math.isfinite(normalized_rebind_retry_interval_seconds)
            or normalized_rebind_retry_interval_seconds <= 0.0
        ):
            raise ValueError("rebind_retry_interval_seconds must be positive")

        self._capacity = normalized_capacity
        self._quarantine_seconds = normalized_quarantine_seconds
        self._acquire_timeout_seconds = normalized_acquire_timeout_seconds
        self._rebind_retry_interval_seconds = normalized_rebind_retry_interval_seconds
        self._local_host = local_host
        self._socket_factory = socket_factory or SystemGuardSocketFactory()
        self._monotonic = monotonic
        self._condition = threading.Condition(threading.RLock())
        self._records: list[_PortRecord] = []
        self._active = False
        self._closed = False
        self._fatal = False
        self._acquire_wait_count = 0
        self._exhaustion_count = 0
        self._rebind_retry_count = 0
        self._reuse_violation_count = 0
        self._minimum_reuse_interval_seconds: float | None = None

    @property
    def supported(self) -> bool:
        return bool(self._socket_factory.supported)

    @property
    def active(self) -> bool:
        with self._condition:
            return self._active and not self._closed and not self._fatal

    def initialize(self) -> None:
        with self._condition:
            if self._active:
                return
            if self._closed:
                raise SpotPortPoolInitError("source-port pool is closed")
            if not self.supported:
                raise SpotPortPoolInitError("exclusive source-port guards are unsupported")

            created: list[_PortRecord] = []
            seen_ports: set[int] = set()
            try:
                for record_id in range(self._capacity):
                    guard, port = self._socket_factory.create_guard(self._local_host)
                    if port in seen_ports:
                        guard.close()
                        raise SpotPortPoolInitError("guard pool contains a duplicate source port")
                    seen_ports.add(port)
                    created.append(
                        _PortRecord(
                            record_id=record_id,
                            port=port,
                            guard=guard,
                        )
                    )
            except BaseException as exc:
                for record in created:
                    if record.guard is not None:
                        record.guard.close()
                if isinstance(exc, SpotPortPoolInitError):
                    raise
                raise SpotPortPoolInitError(
                    f"failed to initialize complete source-port guard pool: {exc.__class__.__name__}"
                ) from exc

            self._records = created
            self._active = True
            self._condition.notify_all()

    def acquire(self, timeout_seconds: float | None = None) -> SourcePortLease:
        timeout = self._acquire_timeout_seconds
        if timeout_seconds is not None:
            timeout = float(timeout_seconds)
            if not math.isfinite(timeout) or timeout < 0.0:
                raise ValueError(
                    "timeout_seconds must be finite and non-negative"
                )
        deadline = self._monotonic() + timeout
        counted_wait = False

        with self._condition:
            while True:
                self._ensure_usable_locked()
                now = self._monotonic()
                self._refresh_rebinds_locked(now)
                record = next((item for item in self._records if item.state == "guarded"), None)
                if record is not None:
                    guard = record.guard
                    if guard is None:
                        self._fatal = True
                        raise SpotPortPoolError("guarded source-port record has no guard socket")
                    try:
                        guard.close()
                    except Exception as exc:
                        self._fatal = True
                        self._condition.notify_all()
                        raise SpotPortPoolError(
                            "failed to release source-port guard socket"
                        ) from exc
                    record.guard = None
                    record.state = "leased"
                    record.quarantine_until = None
                    record.retry_at = None
                    return SourcePortLease(port=record.port, _record_id=record.record_id)

                if not counted_wait:
                    self._acquire_wait_count += 1
                    counted_wait = True
                remaining = deadline - now
                if remaining <= 0.0:
                    self._exhaustion_count += 1
                    raise SpotPortPoolExhausted("source-port pool acquire timed out")
                next_ready = self._next_ready_locked(now)
                self._condition.wait(
                    timeout=min(remaining, max(0.001, next_ready - now))
                    if next_ready is not None
                    else remaining
                )

    def mark_connect_started(self, lease: SourcePortLease) -> None:
        with self._condition:
            self._ensure_usable_locked()
            record = self._record_for_lease_locked(lease)
            now = self._monotonic()
            previous = record.last_connect_started
            if previous is not None:
                interval = now - previous
                if (
                    self._minimum_reuse_interval_seconds is None
                    or interval < self._minimum_reuse_interval_seconds
                ):
                    self._minimum_reuse_interval_seconds = interval
                if interval < self._quarantine_seconds:
                    self._reuse_violation_count += 1
                    self._fatal = True
                    self._condition.notify_all()
                    raise SpotPortReuseViolation("source-port quarantine invariant violated")
            record.last_connect_started = now

    def release(self, lease: SourcePortLease) -> None:
        with self._condition:
            record = self._record_for_lease_locked(lease)
            now = self._monotonic()
            record.state = "quarantined"
            record.quarantine_until = now + self._quarantine_seconds
            record.retry_at = None
            self._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            self._active = False
            for record in self._records:
                if record.guard is not None:
                    record.guard.close()
                    record.guard = None
                record.state = "closed"
            self._condition.notify_all()

    def diagnostics(self) -> dict[str, object]:
        with self._condition:
            counts = {
                state: sum(1 for record in self._records if record.state == state)
                for state in ("guarded", "leased", "quarantined", "rebind_pending")
            }
            return {
                "source_port_policy_version": POLICY_VERSION,
                "source_port_enforcement_supported": self.supported,
                "source_port_enforcement_active": self.active,
                "source_port_quarantine_seconds": self._quarantine_seconds,
                "source_port_pool_capacity": self._capacity,
                "source_port_pool_guarded_count": counts["guarded"],
                "source_port_pool_leased_count": counts["leased"],
                "source_port_pool_quarantined_count": counts["quarantined"],
                "source_port_pool_rebind_pending_count": counts["rebind_pending"],
                "source_port_pool_acquire_wait_count": self._acquire_wait_count,
                "source_port_pool_exhaustion_count": self._exhaustion_count,
                "source_port_rebind_retry_count": self._rebind_retry_count,
                "source_port_reuse_violation_count": self._reuse_violation_count,
                "source_port_minimum_reuse_interval_seconds": (
                    round(self._minimum_reuse_interval_seconds, 6)
                    if self._minimum_reuse_interval_seconds is not None
                    else None
                ),
            }

    def _ensure_usable_locked(self) -> None:
        if self._closed:
            raise SpotPortPoolError("source-port pool is closed")
        if self._fatal:
            raise SpotPortReuseViolation("source-port pool is blocked by a policy violation")
        if not self._active:
            raise SpotPortPoolError("source-port pool is not active")

    def _record_for_lease_locked(self, lease: SourcePortLease) -> _PortRecord:
        if lease._record_id < 0 or lease._record_id >= len(self._records):
            raise SpotPortPoolError("invalid source-port lease")
        record = self._records[lease._record_id]
        if record.port != lease.port or record.state != "leased":
            raise SpotPortPoolError("source-port lease is not active")
        return record

    def _refresh_rebinds_locked(self, now: float) -> None:
        for record in self._records:
            ready_at = (
                record.retry_at
                if record.state == "rebind_pending"
                else record.quarantine_until
                if record.state == "quarantined"
                else None
            )
            if ready_at is None or now < ready_at:
                continue
            try:
                guard, rebound_port = self._socket_factory.create_guard(
                    self._local_host,
                    record.port,
                )
                if rebound_port != record.port:
                    guard.close()
                    raise OSError("guard rebind returned a different source port")
            except BaseException:
                record.state = "rebind_pending"
                record.retry_at = now + self._rebind_retry_interval_seconds
                self._rebind_retry_count += 1
                continue
            record.guard = guard
            record.state = "guarded"
            record.quarantine_until = None
            record.retry_at = None

    def _next_ready_locked(self, now: float) -> float | None:
        candidates = [
            ready_at
            for record in self._records
            for ready_at in (
                record.retry_at
                if record.state == "rebind_pending"
                else record.quarantine_until
                if record.state == "quarantined"
                else None,
            )
            if ready_at is not None and ready_at >= now
        ]
        return min(candidates) if candidates else None
