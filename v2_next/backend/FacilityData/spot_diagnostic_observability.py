from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import Counter, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from backend.FacilityData.spot_diagnostics import SPOT_DIAGNOSTIC_OUTPUT_FIELDS


SPOT_DIAGNOSTIC_JOURNAL_SCHEMA_VERSION = "spot-diagnostic-request-journal-v1"
SPOT_DIAGNOSTIC_JOURNAL_FILENAME = "spot_diagnostic_request_events.jsonl"
SPOT_DIAGNOSTIC_FAILURE_JOURNAL_FILENAME = "spot_diagnostic_request_failures.jsonl"
DEFAULT_RECENT_EVENT_LIMIT = 512
DEFAULT_FAILURE_EVENT_LIMIT = 256
DEFAULT_API_RECENT_EVENT_LIMIT = 64
DEFAULT_API_FAILURE_EVENT_LIMIT = 128
DEFAULT_MAX_LOG_BYTES = 2 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 4
DEFAULT_PERSIST_QUEUE_LIMIT = 1024
MAX_RECOVERY_LINE_BYTES = 16 * 1024

_ALLOWED_ROUTES = frozenset({"/control", "/output"})
_ALLOWED_STATES = frozenset(
    {"queued", "running", "completed", "timed_out", "cancelled", "terminal_missing"}
)
_ALLOWED_OUTCOMES = frozenset(
    {
        "success",
        "missing",
        "http_error",
        "parse_error",
        "transport_error",
        "timeout",
        "cancelled",
        "terminal_missing_after_restart",
    }
)
_ALLOWED_TIMEOUT_PHASES = frozenset({"connect", "response", "write", "pool", "unknown"})
_TERMINAL_STATES = frozenset(
    {"completed", "timed_out", "cancelled", "terminal_missing"}
)
_SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
_REQUEST_ID_PATTERN = re.compile(r"^diagnostic:[0-9a-f]{32}$")
_JOURNAL_INSTANCE_ID_PATTERN = re.compile(r"^journal:[0-9a-f]{32}$")
_SNAPSHOT_CORRELATION_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}:diag:[0-9]+$"
)
_POLL_CORRELATION_ID_PATTERN = re.compile(
    r"^(?:poll:none|[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}:poll:[0-9]+)$"
)
_TRANSPORT_CORRELATION_ID_PATTERN = re.compile(r"^transport:[0-9a-f]{32}$")
_RECOVERED_BASE_KEYS = frozenset(
    {
        "schema_version",
        "event_sequence",
        "journal_instance_id",
        "event_at_utc",
        "state",
        "request_id",
        "snapshot_correlation_id",
        "poll_correlation_id",
        "transport_correlation_id",
        "diagnostic_field",
        "api_route",
    }
)
_RECOVERED_STATE_KEYS = {
    "queued": frozenset({"queued_at_utc"}),
    "running": frozenset({"started_at_utc", "queue_wait_ms"}),
    "completed": frozenset(
        {
            "started_at_utc",
            "ended_at_utc",
            "elapsed_ms",
            "queue_wait_ms",
            "outcome",
            "exception_class",
            "cause_exception_class",
        }
    ),
    "timed_out": frozenset(
        {
            "started_at_utc",
            "ended_at_utc",
            "elapsed_ms",
            "queue_wait_ms",
            "outcome",
            "exception_class",
            "cause_exception_class",
            "timeout_phase",
        }
    ),
    "cancelled": frozenset(
        {
            "started_at_utc",
            "ended_at_utc",
            "elapsed_ms",
            "queue_wait_ms",
            "outcome",
            "exception_class",
            "cause_exception_class",
        }
    ),
    "terminal_missing": frozenset(
        {
            "started_at_utc",
            "ended_at_utc",
            "elapsed_ms",
            "queue_wait_ms",
            "outcome",
            "recovered_from_state",
        }
    ),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc) if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return normalized.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _safe_identifier(value: object, *, fallback: str, max_chars: int = 160) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_chars or _SAFE_IDENTIFIER_PATTERN.fullmatch(text) is None:
        return fallback
    return text


def _safe_exception_class(value: type[BaseException] | None) -> str | None:
    if value is None:
        return None
    name = value.__name__
    if len(name) > 96 or _SAFE_IDENTIFIER_PATTERN.fullmatch(name) is None:
        return "Exception"
    return name


def _safe_api_route(value: object) -> str:
    try:
        path = urlsplit(str(value or "")).path
    except ValueError:
        return "/unknown"
    return path if path in _ALLOWED_ROUTES else "/unknown"


def _event_sequence(value: Mapping[str, object]) -> int:
    sequence = value.get("event_sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
        raise ValueError("diagnostic journal event sequence is invalid")
    return sequence


def _bounded_json_int(value: str) -> int:
    if len(value.lstrip("-")) > 20:
        raise ValueError("diagnostic journal integer is too large")
    return int(value)


def _decode_recovery_json(value: str | bytes) -> object | None:
    try:
        payload = value.encode("utf-8") if isinstance(value, str) else value
        if len(payload) > MAX_RECOVERY_LINE_BYTES:
            return None
        return json.loads(payload, parse_int=_bounded_json_int)
    except (
        json.JSONDecodeError,
        OverflowError,
        RecursionError,
        UnicodeError,
        ValueError,
    ):
        return None


@dataclass(frozen=True)
class SpotDiagnosticRequestContext:
    request_id: str
    snapshot_correlation_id: str
    poll_correlation_id: str
    transport_correlation_id: str
    diagnostic_field: str
    api_route: str
    queued_at_utc: str
    queued_at_monotonic: float


@dataclass
class _ActiveRequest:
    context: SpotDiagnosticRequestContext
    state: str
    running_at_utc: str | None = None
    running_at_monotonic: float | None = None


@dataclass(frozen=True)
class _PersistenceItem:
    event: dict[str, object]
    priority: bool


class _BoundedPersistenceQueue:
    """Bounded queue that preserves terminal failures ahead of routine events."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._condition = threading.Condition(threading.Lock())
        self._items: deque[_PersistenceItem] = deque()
        self._stopping = False

    def put(self, event: Mapping[str, object], *, priority: bool) -> tuple[bool, bool]:
        with self._condition:
            if self._stopping:
                return False, False
            evicted = False
            if len(self._items) >= self._limit:
                if not priority:
                    return False, False
                for index, item in enumerate(self._items):
                    if not item.priority:
                        del self._items[index]
                        evicted = True
                        break
                else:
                    return False, False
            new_item = _PersistenceItem(event=dict(event), priority=priority)
            self._items.append(new_item)
            self._condition.notify()
            return True, evicted

    def get(self, timeout_sec: float) -> tuple[bool, dict[str, object] | None]:
        deadline = time.monotonic() + max(0.0, timeout_sec)
        with self._condition:
            while not self._items and not self._stopping:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False, None
                self._condition.wait(timeout=remaining)
            if self._items:
                return True, self._items.popleft().event
            return True, None

    def stop(self) -> None:
        with self._condition:
            self._stopping = True
            self._condition.notify_all()


class SpotDiagnosticRequestJournal:
    """Bounded append-only diagnostic request lifecycle and failure journal."""

    def __init__(
        self,
        log_path: Path,
        *,
        recent_event_limit: int = DEFAULT_RECENT_EVENT_LIMIT,
        failure_event_limit: int = DEFAULT_FAILURE_EVENT_LIMIT,
        api_recent_event_limit: int = DEFAULT_API_RECENT_EVENT_LIMIT,
        api_failure_event_limit: int = DEFAULT_API_FAILURE_EVENT_LIMIT,
        max_log_bytes: int = DEFAULT_MAX_LOG_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
        persist_queue_limit: int = DEFAULT_PERSIST_QUEUE_LIMIT,
        utc_now: Callable[[], datetime] = _utc_now,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if recent_event_limit <= 0 or failure_event_limit <= 0:
            raise ValueError("journal retention limits must be positive")
        if api_recent_event_limit <= 0 or api_failure_event_limit <= 0:
            raise ValueError("journal API retention limits must be positive")
        if api_recent_event_limit > recent_event_limit or api_failure_event_limit > failure_event_limit:
            raise ValueError("journal API retention cannot exceed in-memory retention")
        if max_log_bytes < 512:
            raise ValueError("max_log_bytes must be at least 512")
        if backup_count <= 0:
            raise ValueError("backup_count must be positive")
        if persist_queue_limit <= 0:
            raise ValueError("persist_queue_limit must be positive")

        self._log_path = Path(log_path)
        self._failure_log_path = self._log_path.with_name(
            SPOT_DIAGNOSTIC_FAILURE_JOURNAL_FILENAME
        )
        self._recent_event_limit = int(recent_event_limit)
        self._failure_event_limit = int(failure_event_limit)
        self._api_recent_event_limit = int(api_recent_event_limit)
        self._api_failure_event_limit = int(api_failure_event_limit)
        self._max_log_bytes = int(max_log_bytes)
        self._backup_count = int(backup_count)
        self._persist_queue_limit = int(persist_queue_limit)
        self._utc_now = utc_now
        self._monotonic = monotonic
        self._lock = threading.RLock()
        self._close_lock = threading.Lock()
        self._pending_condition = threading.Condition(threading.Lock())
        self._persist_queue = _BoundedPersistenceQueue(self._persist_queue_limit)
        self._journal_instance_id = f"journal:{uuid4().hex}"
        self._recent_events: deque[dict[str, object]] = deque(maxlen=self._recent_event_limit)
        self._failure_events: deque[dict[str, object]] = deque(maxlen=self._failure_event_limit)
        self._active: dict[str, _ActiveRequest] = {}
        self._state_counts: Counter[str] = Counter()
        self._outcome_counts: Counter[str] = Counter()
        self._event_sequence = 0
        self._event_count_total = 0
        self._event_drop_count = 0
        self._failure_count_total = 0
        self._failure_drop_count = 0
        self._invalid_transition_count = 0
        self._write_failure_count = 0
        self._persist_queue_drop_count = 0
        self._pending_persist_count = 0
        self._last_write_error_class: str | None = None
        self._last_write_success_at_utc: str | None = None
        self._last_write_duration_ms: float | None = None
        self._rotation_count = 0
        self._recovered_event_count = 0
        self._recovered_failure_count = 0
        self._recovered_incomplete_request_count = 0
        self._recovered_incomplete_synthesized_count = 0
        self._recovery_invalid_line_count = 0
        self._recovery_truncated_byte_count = 0
        self._recovery_repaired_newline_count = 0
        self._recovery_skipped_byte_count = 0
        self._accepting_persistence = True
        self._recover_retained_events()
        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name="spot-diagnostic-journal-writer",
            daemon=True,
        )
        self._writer_thread.start()

    @property
    def log_path(self) -> Path:
        return self._log_path

    def queue_request(
        self,
        *,
        snapshot_correlation_id: str,
        poll_correlation_id: str,
        diagnostic_field: str,
        api_route: str,
    ) -> SpotDiagnosticRequestContext:
        now = self._utc_now()
        context = SpotDiagnosticRequestContext(
            request_id=f"diagnostic:{uuid4().hex}",
            snapshot_correlation_id=_safe_identifier(
                snapshot_correlation_id,
                fallback=f"snapshot:{uuid4().hex}",
            ),
            poll_correlation_id=_safe_identifier(
                poll_correlation_id,
                fallback="poll:none",
            ),
            transport_correlation_id=f"transport:{uuid4().hex}",
            diagnostic_field=(diagnostic_field if diagnostic_field in SPOT_DIAGNOSTIC_OUTPUT_FIELDS else "unknown"),
            api_route=_safe_api_route(api_route),
            queued_at_utc=_utc_iso(now),
            queued_at_monotonic=self._monotonic(),
        )
        with self._lock:
            self._active[context.request_id] = _ActiveRequest(context=context, state="queued")
            self._append_event_locked(
                context,
                state="queued",
                event_at_utc=context.queued_at_utc,
                details={"queued_at_utc": context.queued_at_utc},
            )
        return context

    def mark_running(self, context: SpotDiagnosticRequestContext) -> None:
        now = self._utc_now()
        monotonic_now = self._monotonic()
        with self._lock:
            active = self._active.get(context.request_id)
            if active is None or active.state != "queued":
                self._invalid_transition_count += 1
                return
            active.state = "running"
            active.running_at_utc = _utc_iso(now)
            active.running_at_monotonic = monotonic_now
            self._append_event_locked(
                context,
                state="running",
                event_at_utc=active.running_at_utc,
                details={
                    "started_at_utc": active.running_at_utc,
                    "queue_wait_ms": self._elapsed_ms(context.queued_at_monotonic, monotonic_now),
                },
            )

    def mark_completed(
        self,
        context: SpotDiagnosticRequestContext,
        *,
        outcome: str,
        exception: BaseException | None = None,
    ) -> None:
        normalized_outcome = outcome if outcome in _ALLOWED_OUTCOMES else "transport_error"
        if normalized_outcome in {
            "timeout",
            "cancelled",
            "terminal_missing_after_restart",
        }:
            normalized_outcome = "transport_error"
        self._mark_terminal(
            context,
            state="completed",
            outcome=normalized_outcome,
            exception=exception,
            timeout_phase=None,
        )

    def mark_timed_out(
        self,
        context: SpotDiagnosticRequestContext,
        *,
        exception: BaseException,
        timeout_phase: str,
    ) -> None:
        self._mark_terminal(
            context,
            state="timed_out",
            outcome="timeout",
            exception=exception,
            timeout_phase=(timeout_phase if timeout_phase in _ALLOWED_TIMEOUT_PHASES else "unknown"),
        )

    def mark_cancelled(
        self,
        context: SpotDiagnosticRequestContext,
        *,
        exception: BaseException | None = None,
    ) -> None:
        self._mark_terminal(
            context,
            state="cancelled",
            outcome="cancelled",
            exception=exception,
            timeout_phase=None,
        )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            with self._pending_condition:
                pending_persist_count = self._pending_persist_count
            return {
                "schema_version": SPOT_DIAGNOSTIC_JOURNAL_SCHEMA_VERSION,
                "retention_policy": {
                    "recent_event_limit": self._recent_event_limit,
                    "failure_event_limit": self._failure_event_limit,
                    "api_recent_event_limit": self._api_recent_event_limit,
                    "api_failure_event_limit": self._api_failure_event_limit,
                    "log_max_bytes": self._max_log_bytes,
                    "log_backup_count": self._backup_count,
                    "persist_queue_limit": self._persist_queue_limit,
                },
                "log_file": self._log_path.name,
                "failure_log_file": self._failure_log_path.name,
                "event_count_total": self._event_count_total,
                "event_count_retained": len(self._recent_events),
                "event_drop_count": self._event_drop_count,
                "failure_count_total": self._failure_count_total,
                "failure_count_retained": len(self._failure_events),
                "failure_drop_count": self._failure_drop_count,
                "active_request_count": len(self._active),
                "accepting_persistence": self._accepting_persistence,
                "invalid_transition_count": self._invalid_transition_count,
                "write_failure_count": self._write_failure_count,
                "persist_queue_drop_count": self._persist_queue_drop_count,
                "pending_persist_count": pending_persist_count,
                "last_write_error_class": self._last_write_error_class,
                "last_write_success_at_utc": self._last_write_success_at_utc,
                "last_write_duration_ms": self._last_write_duration_ms,
                "rotation_count": self._rotation_count,
                "journal_instance_id": self._journal_instance_id,
                "recovered_event_count": self._recovered_event_count,
                "recovered_failure_count": self._recovered_failure_count,
                "recovered_incomplete_request_count": self._recovered_incomplete_request_count,
                "recovered_incomplete_synthesized_count": self._recovered_incomplete_synthesized_count,
                "recovery_invalid_line_count": self._recovery_invalid_line_count,
                "recovery_truncated_byte_count": self._recovery_truncated_byte_count,
                "recovery_repaired_newline_count": self._recovery_repaired_newline_count,
                "recovery_skipped_byte_count": self._recovery_skipped_byte_count,
                "state_counts": {state: self._state_counts[state] for state in sorted(_ALLOWED_STATES)},
                "outcome_counts": {outcome: self._outcome_counts[outcome] for outcome in sorted(_ALLOWED_OUTCOMES)},
                "recent_events": [dict(event) for event in list(self._recent_events)[-self._api_recent_event_limit :]],
                "failure_events": [
                    dict(event) for event in list(self._failure_events)[-self._api_failure_event_limit :]
                ],
            }

    def _mark_terminal(
        self,
        context: SpotDiagnosticRequestContext,
        *,
        state: str,
        outcome: str,
        exception: BaseException | None,
        timeout_phase: str | None,
    ) -> None:
        now = self._utc_now()
        monotonic_now = self._monotonic()
        with self._lock:
            active = self._active.get(context.request_id)
            if active is None or active.state not in {"queued", "running"} or state not in _TERMINAL_STATES:
                self._invalid_transition_count += 1
                return
            started_at_utc = active.running_at_utc or context.queued_at_utc
            started_at_monotonic = active.running_at_monotonic or context.queued_at_monotonic
            details: dict[str, object] = {
                "started_at_utc": started_at_utc,
                "ended_at_utc": _utc_iso(now),
                "elapsed_ms": self._elapsed_ms(started_at_monotonic, monotonic_now),
                "queue_wait_ms": self._elapsed_ms(
                    context.queued_at_monotonic,
                    active.running_at_monotonic or monotonic_now,
                ),
                "outcome": outcome,
            }
            if exception is not None:
                details["exception_class"] = _safe_exception_class(exception.__class__)
                details["cause_exception_class"] = _safe_exception_class(
                    exception.__cause__.__class__ if exception.__cause__ is not None else None
                )
            if timeout_phase is not None:
                details["timeout_phase"] = timeout_phase
            event = self._append_event_locked(
                context,
                state=state,
                event_at_utc=str(details["ended_at_utc"]),
                details=details,
            )
            self._outcome_counts[outcome] += 1
            if state != "completed" or outcome != "success":
                self._failure_count_total += 1
                if len(self._failure_events) == self._failure_event_limit:
                    self._failure_drop_count += 1
                self._failure_events.append(dict(event))
            self._active.pop(context.request_id, None)

    def _append_event_locked(
        self,
        context: SpotDiagnosticRequestContext,
        *,
        state: str,
        event_at_utc: str,
        details: Mapping[str, object],
    ) -> dict[str, object]:
        self._event_sequence += 1
        event: dict[str, object] = {
            "schema_version": SPOT_DIAGNOSTIC_JOURNAL_SCHEMA_VERSION,
            "event_sequence": self._event_sequence,
            "journal_instance_id": self._journal_instance_id,
            "event_at_utc": event_at_utc,
            "state": state,
            "request_id": context.request_id,
            "snapshot_correlation_id": context.snapshot_correlation_id,
            "poll_correlation_id": context.poll_correlation_id,
            "transport_correlation_id": context.transport_correlation_id,
            "diagnostic_field": context.diagnostic_field,
            "api_route": context.api_route,
            **dict(details),
        }
        self._event_count_total += 1
        self._state_counts[state] += 1
        if len(self._recent_events) == self._recent_event_limit:
            self._event_drop_count += 1
        self._recent_events.append(dict(event))
        self._enqueue_event_locked(event)
        return event

    def flush(self, timeout_sec: float = 2.0) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout_sec))
        with self._pending_condition:
            while self._pending_persist_count > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._pending_condition.wait(timeout=remaining)
            return True

    def close(self, timeout_sec: float = 2.0) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout_sec))
        with self._close_lock:
            with self._lock:
                self._accepting_persistence = False
            drained = self.flush(max(0.0, deadline - time.monotonic()))
            if not drained:
                return False
            if not self._writer_thread.is_alive():
                return True
            self._persist_queue.stop()
            self._writer_thread.join(timeout=max(0.0, deadline - time.monotonic()))
            return not self._writer_thread.is_alive()

    def _enqueue_event_locked(self, event: Mapping[str, object]) -> None:
        if not self._accepting_persistence:
            self._persist_queue_drop_count += 1
            return
        with self._pending_condition:
            self._pending_persist_count += 1
        priority = event.get("state") in _TERMINAL_STATES
        accepted, evicted = self._persist_queue.put(event, priority=priority)
        if not accepted or evicted:
            with self._pending_condition:
                self._pending_persist_count -= 1
                self._pending_condition.notify_all()
            self._persist_queue_drop_count += 1
        if not accepted:
            return

    def _writer_loop(self) -> None:
        while True:
            ready, event = self._persist_queue.get(timeout_sec=0.5)
            if not ready:
                continue
            if event is None:
                return
            started = time.monotonic()
            failure: Exception | None = None
            try:
                self._write_event_locked(event)
            except Exception as exc:
                failure = exc
            duration_ms = self._elapsed_ms(started, time.monotonic())
            with self._lock:
                self._last_write_duration_ms = duration_ms
                if failure is None:
                    self._last_write_success_at_utc = _utc_iso(self._utc_now())
                else:
                    self._write_failure_count += 1
                    self._last_write_error_class = _safe_exception_class(failure.__class__)
            with self._pending_condition:
                self._pending_persist_count -= 1
                self._pending_condition.notify_all()

    def _write_event_locked(self, event: Mapping[str, object]) -> None:
        line = (json.dumps(event, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
        write_errors: list[Exception] = []
        if self._is_failure_event(event):
            try:
                self._write_line_to_retained_log(self._failure_log_path, line)
            except Exception as exc:
                write_errors.append(exc)
        try:
            self._write_line_to_retained_log(self._log_path, line)
        except Exception as exc:
            write_errors.append(exc)
        if write_errors:
            raise write_errors[0]

    @staticmethod
    def _is_failure_event(event: Mapping[str, object]) -> bool:
        return event.get("state") in {"timed_out", "cancelled", "terminal_missing"} or (
            event.get("state") == "completed" and event.get("outcome") != "success"
        )

    def _write_line_to_retained_log(self, path: Path, line: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        current_size = path.stat().st_size if path.exists() else 0
        if current_size > 0 and current_size + len(line) > self._max_log_bytes:
            self._rotate_locked(path)
        with path.open("ab") as handle:
            handle.write(line)

    def _rotate_locked(self, path: Path) -> None:
        for index in range(self._backup_count, 0, -1):
            source = path if index == 1 else Path(f"{path}.{index - 1}")
            target = Path(f"{path}.{index}")
            if target.exists():
                target.unlink()
            if source.exists():
                os.replace(source, target)
        self._rotation_count += 1

    def _recover_retained_events(self) -> None:
        self._repair_partial_current_tail_locked(self._log_path)
        self._repair_partial_current_tail_locked(self._failure_log_path)
        recovered_by_sequence: dict[int, dict[str, object]] = {}
        for journal_path in (self._log_path, self._failure_log_path):
            for path in self._retained_log_paths_oldest_first(journal_path):
                for line in self._bounded_recovery_lines(path):
                    value = _decode_recovery_json(line)
                    if value is None:
                        self._recovery_invalid_line_count += 1
                        continue
                    event = self._canonical_recovered_event(value)
                    if event is None:
                        self._recovery_invalid_line_count += 1
                        continue
                    sequence = _event_sequence(event)
                    existing = recovered_by_sequence.get(sequence)
                    if existing is not None:
                        if existing != event:
                            self._recovery_invalid_line_count += 1
                        continue
                    recovered_by_sequence[sequence] = event

        incomplete_requests: dict[tuple[str, str], dict[str, object]] = {}
        for sequence in sorted(recovered_by_sequence):
            event = recovered_by_sequence[sequence]
            self._restore_event_locked(event)
            request_key = (
                str(event["journal_instance_id"]),
                str(event["request_id"]),
            )
            if event["state"] in {"queued", "running"}:
                incomplete_requests[request_key] = event
            else:
                incomplete_requests.pop(request_key, None)
            self._recovered_event_count += 1
        ordered_incomplete = sorted(
            incomplete_requests.values(),
            key=_event_sequence,
        )
        self._recovered_incomplete_request_count = len(ordered_incomplete)
        for event in ordered_incomplete[-self._failure_event_limit :]:
            self._append_recovered_interruption_locked(event)
            self._recovered_incomplete_synthesized_count += 1
        self._recovered_failure_count = len(self._failure_events)

    def _append_recovered_interruption_locked(
        self,
        prior_event: Mapping[str, object],
    ) -> None:
        ended_at_utc = _utc_iso(self._utc_now())
        recovered_from_state = str(prior_event["state"])
        started_at_utc = str(
            prior_event.get("started_at_utc")
            or prior_event.get("queued_at_utc")
            or prior_event["event_at_utc"]
        )
        elapsed_ms = 0.0
        try:
            started_at = datetime.fromisoformat(
                started_at_utc.removesuffix("Z") + "+00:00"
            )
            ended_at = datetime.fromisoformat(
                ended_at_utc.removesuffix("Z") + "+00:00"
            )
            elapsed_ms = round(
                max(0.0, (ended_at - started_at).total_seconds() * 1000.0),
                3,
            )
        except ValueError:
            elapsed_ms = 0.0
        queue_wait_value = prior_event.get("queue_wait_ms", 0.0)
        queue_wait_ms = (
            float(queue_wait_value)
            if not isinstance(queue_wait_value, bool)
            and isinstance(queue_wait_value, (int, float))
            else 0.0
        )

        self._event_sequence += 1
        event: dict[str, object] = {
            "schema_version": SPOT_DIAGNOSTIC_JOURNAL_SCHEMA_VERSION,
            "event_sequence": self._event_sequence,
            "journal_instance_id": prior_event["journal_instance_id"],
            "event_at_utc": ended_at_utc,
            "state": "terminal_missing",
            "request_id": prior_event["request_id"],
            "snapshot_correlation_id": prior_event["snapshot_correlation_id"],
            "poll_correlation_id": prior_event["poll_correlation_id"],
            "transport_correlation_id": prior_event["transport_correlation_id"],
            "diagnostic_field": prior_event["diagnostic_field"],
            "api_route": prior_event["api_route"],
            "started_at_utc": started_at_utc,
            "ended_at_utc": ended_at_utc,
            "elapsed_ms": elapsed_ms,
            "queue_wait_ms": queue_wait_ms,
            "outcome": "terminal_missing_after_restart",
            "recovered_from_state": recovered_from_state,
        }
        self._event_count_total += 1
        self._state_counts["terminal_missing"] += 1
        self._outcome_counts["terminal_missing_after_restart"] += 1
        if len(self._recent_events) == self._recent_event_limit:
            self._event_drop_count += 1
        self._recent_events.append(dict(event))
        self._failure_count_total += 1
        if len(self._failure_events) == self._failure_event_limit:
            self._failure_drop_count += 1
        self._failure_events.append(dict(event))
        self._enqueue_event_locked(event)

    def _repair_partial_current_tail_locked(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            size = path.stat().st_size
            if size <= 0:
                return
            with path.open("rb+") as handle:
                handle.seek(-1, os.SEEK_END)
                if handle.read(1) == b"\n":
                    return
                tail_start = max(0, size - self._max_log_bytes)
                handle.seek(tail_start)
                tail = handle.read(self._max_log_bytes)
                final_newline = tail.rfind(b"\n")
                fragment = tail[final_newline + 1 :]
                value = _decode_recovery_json(fragment)
                if self._canonical_recovered_event(value) is not None:
                    handle.seek(0, os.SEEK_END)
                    handle.write(b"\n")
                    self._recovery_repaired_newline_count += 1
                    return
                retained_size = tail_start + final_newline + 1 if final_newline >= 0 else 0
                handle.truncate(retained_size)
                self._recovery_truncated_byte_count += size - retained_size
        except OSError as exc:
            self._write_failure_count += 1
            self._last_write_error_class = _safe_exception_class(exc.__class__)

    def _retained_log_paths_oldest_first(self, path: Path) -> list[Path]:
        backups = [Path(f"{path}.{index}") for index in range(self._backup_count, 0, -1)]
        return [*backups, path]

    def _bounded_recovery_lines(self, path: Path) -> list[str]:
        if not path.exists():
            return []
        try:
            size = path.stat().st_size
            start = max(0, size - self._max_log_bytes)
            with path.open("rb") as handle:
                handle.seek(start)
                payload = handle.read(self._max_log_bytes)
        except OSError:
            self._recovery_invalid_line_count += 1
            return []
        if start > 0:
            first_newline = payload.find(b"\n")
            skipped_in_payload = len(payload) if first_newline < 0 else first_newline + 1
            self._recovery_skipped_byte_count += start + skipped_in_payload
            payload = b"" if first_newline < 0 else payload[first_newline + 1 :]
        try:
            return payload.decode("utf-8").splitlines()
        except UnicodeError:
            self._recovery_invalid_line_count += 1
            return []

    @staticmethod
    def _canonical_recovered_event(value: object) -> dict[str, object] | None:
        if not isinstance(value, dict):
            return None
        sequence = value.get("event_sequence")
        state = value.get("state")
        if (
            value.get("schema_version") != SPOT_DIAGNOSTIC_JOURNAL_SCHEMA_VERSION
            or isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence <= 0
            or not isinstance(state, str)
            or state not in _ALLOWED_STATES
        ):
            return None
        allowed_keys = _RECOVERED_BASE_KEYS | _RECOVERED_STATE_KEYS[state]
        if not set(value).issubset(allowed_keys):
            return None
        required_keys = _RECOVERED_BASE_KEYS | {
            key
            for key in _RECOVERED_STATE_KEYS[state]
            if key not in {"exception_class", "cause_exception_class"}
        }
        if not required_keys.issubset(value):
            return None
        if (
            _JOURNAL_INSTANCE_ID_PATTERN.fullmatch(str(value.get("journal_instance_id", ""))) is None
            or _REQUEST_ID_PATTERN.fullmatch(str(value.get("request_id", ""))) is None
            or _SNAPSHOT_CORRELATION_ID_PATTERN.fullmatch(str(value.get("snapshot_correlation_id", ""))) is None
            or _POLL_CORRELATION_ID_PATTERN.fullmatch(str(value.get("poll_correlation_id", ""))) is None
            or _TRANSPORT_CORRELATION_ID_PATTERN.fullmatch(str(value.get("transport_correlation_id", ""))) is None
            or value.get("diagnostic_field") not in {*SPOT_DIAGNOSTIC_OUTPUT_FIELDS, "unknown"}
            or value.get("api_route") not in {*_ALLOWED_ROUTES, "/unknown"}
        ):
            return None
        timestamp_keys = {"event_at_utc", "queued_at_utc", "started_at_utc", "ended_at_utc"} & set(value)
        if any(not SpotDiagnosticRequestJournal._valid_utc_timestamp(value[key]) for key in timestamp_keys):
            return None
        numeric_keys = {"elapsed_ms", "queue_wait_ms"} & set(value)
        if any(not SpotDiagnosticRequestJournal._valid_nonnegative_number(value[key]) for key in numeric_keys):
            return None
        for key in ("exception_class", "cause_exception_class"):
            exception_class = value.get(key)
            if exception_class is not None and (
                not isinstance(exception_class, str)
                or len(exception_class) > 96
                or _SAFE_IDENTIFIER_PATTERN.fullmatch(exception_class) is None
            ):
                return None
        outcome = value.get("outcome")
        if state == "completed" and outcome not in _ALLOWED_OUTCOMES - {
            "timeout",
            "cancelled",
            "terminal_missing_after_restart",
        }:
            return None
        if state == "timed_out" and (
            outcome != "timeout" or value.get("timeout_phase") not in _ALLOWED_TIMEOUT_PHASES
        ):
            return None
        if state == "cancelled" and outcome != "cancelled":
            return None
        if state == "terminal_missing" and (
            outcome != "terminal_missing_after_restart"
            or value.get("recovered_from_state") not in {"queued", "running"}
        ):
            return None
        return {key: value[key] for key in allowed_keys if key in value}

    @staticmethod
    def _valid_utc_timestamp(value: object) -> bool:
        if not isinstance(value, str) or not value.endswith("Z"):
            return False
        try:
            parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        except ValueError:
            return False
        return parsed.tzinfo is not None

    @staticmethod
    def _valid_nonnegative_number(value: object) -> bool:
        return (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and float(value) >= 0.0
            and float(value) != float("inf")
        )

    def _restore_event_locked(self, event: dict[str, object]) -> None:
        sequence = _event_sequence(event)
        state = str(event["state"])
        self._event_sequence = max(self._event_sequence, sequence)
        self._event_count_total += 1
        self._state_counts[state] += 1
        if len(self._recent_events) == self._recent_event_limit:
            self._event_drop_count += 1
        self._recent_events.append(dict(event))
        outcome = event.get("outcome")
        if isinstance(outcome, str) and outcome in _ALLOWED_OUTCOMES:
            self._outcome_counts[outcome] += 1
            if state != "completed" or outcome != "success":
                self._failure_count_total += 1
                if len(self._failure_events) == self._failure_event_limit:
                    self._failure_drop_count += 1
                self._failure_events.append(dict(event))

    @staticmethod
    def _elapsed_ms(started_at: float, ended_at: float) -> float:
        return round(max(0.0, (ended_at - started_at) * 1000.0), 3)
