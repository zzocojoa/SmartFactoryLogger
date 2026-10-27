"""Bounded persistence owner. Producers only serialize and enqueue immutable events.

Saturation rejects the newest event and latches an observable failure. This is not
a promise of lossless operation through an unbounded storage outage.
"""
from __future__ import annotations

import copy
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
import json
import logging
import queue
import threading
import time
from typing import Any, Callable, Iterator, Literal, Mapping

from backend.FacilityData.persistence_payload import (
    PayloadBudgetExceeded as _PayloadBudgetExceeded, prepare_json_payload as _prepare_json_payload,
    decoded_string_bytes as _decoded_string_bytes,
    encode_json_payload as _encode_json_payload,
)
from backend.FacilityData.spot_observation_fact import (
    FactPayloadBudgetExceeded, SpotObservationFactWriter, build_spot_observation_key,
)
from backend.FacilityData.freshness import clock_domain_id


FACT_PENDING_PAYLOAD_BYTE_LIMIT = 16 * 1024**2
_logger = logging.getLogger(__name__)
FactAdmissionStatus = Literal[
    "ACCEPTED", "REJECTED_FULL", "REJECTED_LIMIT", "REJECTED_UNAVAILABLE",
    "REJECTED_CLOSED", "DISABLED", "INVALID",
]


@dataclass(frozen=True)
class FactAdmissionResult:
    status: FactAdmissionStatus
    reason: str | None
    observation_key: str

    @property
    def accepted(self) -> bool:
        return self.status == "ACCEPTED"


class FactPersistencePending(RuntimeError):
    """Normal asynchronous work remains; it is not a disk failure."""


@dataclass(frozen=True)
class _FactEvent:
    payload: bytes
    text_storage_bytes: int
    observation_key: str
    enqueued_at: float


class SpotObservationQueue:
    def __init__(self, factory: Callable[[], SpotObservationFactWriter], capacity: int = 256):
        if isinstance(capacity, bool) or capacity <= 0:
            raise ValueError("capacity must be positive")
        self._factory = factory
        self._queue: queue.Queue[_FactEvent] = queue.Queue(maxsize=capacity)
        # FIFO timestamps remain owned through the in-flight write, bounded by
        # the same admitted-item limit as the payload queue.
        self._pending_enqueued_at: deque[float] = deque()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._writer: SpotObservationFactWriter | None = None
        self._worker_failure_count = 0
        self._summary: dict[str, Any] | None = None
        self._file_stamp: tuple[int, int] | None = None
        self._required_file_probe_at: float | None = 0.0
        self._required_file_probe_delay = 1.0
        self._state: dict[str, Any] = {
            "queue_capacity": capacity, "accepted_count": 0, "completed_count": 0,
            "rejected_count": 0, "write_failure_count": 0, "spool_failure_count": 0,
            "spool_last_error_code": None,
            "spool_pending_count": 0, "inflight": False, "initialization_state": "pending",
            "initialization_duration_ms": None, "last_write_duration_ms": None,
            "last_error_code": None, "last_success_at": None, "accepting": True,
            "last_queue_residence_ms": None, "existing_fact_hash_ms": None, "existing_fact_index_ms": None,
            "pending_payload_bytes": 0, "pending_source_payload_bytes": 0,
            "processing_payload_bytes": 0, "last_failed_observation_key": None,
            "pending_payload_byte_limit": FACT_PENDING_PAYLOAD_BYTE_LIMIT,
            "required_file_availability": "unknown", "required_file_scope": "read_write_open",
            "required_file_error_type": None, "required_file_failure_count": 0,
            "required_file_checked_monotonic": None, "required_file_last_success_monotonic": None,
            "required_file_next_probe_monotonic": None,
        }
        self._thread = threading.Thread(target=self._run, name="SPOT-ObservationFact", daemon=True)
        self._thread.start()

    def enqueue(self, snapshot: Mapping[str, Any]) -> bool:
        """Compatibility wrapper; callers needing provenance use enqueue_detailed."""
        return self.enqueue_detailed(snapshot).accepted

    def enqueue_detailed(self, snapshot: Mapping[str, Any]) -> FactAdmissionResult:
        observation_key = ""
        try:
            source = dict(snapshot)
            observation_key = build_spot_observation_key(source)
        except (TypeError, ValueError, OverflowError):
            return self._reject("INVALID", "snapshot_serialization_failed", observation_key)
        with self._lock:
            if self._state["initialization_state"] == "failed" and not self._stop.is_set():
                return self._reject_locked("REJECTED_UNAVAILABLE", "initialization_failed", observation_key)
            if not self._state["accepting"]:
                return self._reject_locked("REJECTED_CLOSED", "persistence_closed", observation_key)
            if self._queue.full():
                return self._reject_locked("REJECTED_FULL", "queue_full", observation_key)
            # Dequeue transfers ownership to the writer, not out of the budget.
            pending = self._state["accepted_count"] - self._state["completed_count"]
            if pending >= self._queue.maxsize:
                return self._reject_locked("REJECTED_LIMIT", "pending_item_limit", observation_key)
            available = FACT_PENDING_PAYLOAD_BYTE_LIMIT - self._state["pending_payload_bytes"]
            try:
                source, payload_size, text_characters, text_width = _prepare_json_payload(source, available)
            except _PayloadBudgetExceeded:
                return self._reject_locked("REJECTED_LIMIT", "pending_byte_limit", observation_key)
            except (TypeError, ValueError, OverflowError):
                return self._reject_locked("INVALID", "snapshot_serialization_failed", observation_key)
            # Joining encoded chunks owns two text copies; UTF-8 allocation
            # owns text and bytes. Detached containers share immutable leaves.
            text_bytes = text_characters * text_width
            reservation = max(2 * text_bytes, payload_size + text_bytes)
            if reservation > available:
                return self._reject_locked("REJECTED_LIMIT", "pending_byte_limit", observation_key)
            self._state["pending_payload_bytes"] += reservation
            accepted = False
            payload = b""
            try:
                payload = _encode_json_payload(source)
                if len(payload) != payload_size:
                    raise ValueError("JSON payload size changed after reservation")
                event = _FactEvent(payload, text_characters * text_width, observation_key, time.monotonic())
                self._queue.put_nowait(event)
                self._pending_enqueued_at.append(event.enqueued_at)
                self._state["accepted_count"] += 1
                self._state["pending_source_payload_bytes"] += payload_size
                accepted = True
            except queue.Full:
                return self._reject_locked("REJECTED_FULL", "queue_full", observation_key)
            except (TypeError, ValueError, OverflowError):
                return self._reject_locked("INVALID", "snapshot_serialization_failed", observation_key)
            finally:
                if not accepted:
                    payload = b""
                self._state["pending_payload_bytes"] -= reservation - (payload_size if accepted else 0)
        return FactAdmissionResult("ACCEPTED", None, observation_key)

    def _reject(self, status: FactAdmissionStatus, code: str, observation_key: str) -> FactAdmissionResult:
        with self._lock:
            return self._reject_locked(status, code, observation_key)

    def _reject_locked(self, status: FactAdmissionStatus, code: str, observation_key: str) -> FactAdmissionResult:
        self._state["rejected_count"] += 1
        self._state["last_error_code"] = code
        return FactAdmissionResult(status, code, observation_key)

    def snapshot(self) -> dict[str, Any]:
        # Never wait on a writer/file/spool lock, scan, or filesystem call.
        with self._lock:
            state = dict(self._state)
            oldest = self._pending_enqueued_at[0] if self._pending_enqueued_at else None
            state["oldest_pending_monotonic"] = oldest
            # Fact data has no scheduled flush delay. Retries or newer arrivals
            # must not postpone the immediate stage deadline fixed at admission.
            state["stage_due_monotonic"] = oldest
            state["clock_domain"] = clock_domain_id()
        state["pending_write_count"] = state["accepted_count"] - state["completed_count"]
        state["queue_depth"] = self._queue.qsize()
        state["writer_alive"] = self._thread.is_alive()
        state["writes_drained"] = (
            state["initialization_state"] == "ready" and state["pending_write_count"] == 0
            and state["write_failure_count"] == 0 and state["rejected_count"] == 0
            and state["spool_pending_count"] == 0 and state["spool_failure_count"] == 0
        )
        return state

    def _record_failure(self, code: str, observation_key: str, *, worker_failure: bool) -> None:
        with self._lock:
            if worker_failure:
                self._worker_failure_count += 1
            self._state["write_failure_count"] = self._worker_failure_count + (
                self._writer.failure_count if self._writer is not None else 0
            )
            self._state["last_error_code"] = code
            self._state["last_failed_observation_key"] = observation_key
        _logger.error("SPOT fact processing failed", extra={
            "observation_key": observation_key, "reason": code,
        })

    @contextmanager
    def _reserve_writer_payload(self, size: int, reason: str) -> Iterator[None]:
        with self._lock:
            if self._state["pending_payload_bytes"] + size > FACT_PENDING_PAYLOAD_BYTE_LIMIT:
                raise FactPayloadBudgetExceeded(reason)
            self._state["pending_payload_bytes"] += size
            self._state["processing_payload_bytes"] += size
        try:
            yield
        finally:
            with self._lock:
                self._state["pending_payload_bytes"] -= size
                self._state["processing_payload_bytes"] -= size

    def manifest_summary(self, *, realtime_rows=None) -> dict[str, Any]:
        before = self.snapshot()
        if not before["writes_drained"]:
            raise FactPersistencePending("observation persistence is not drained")
        with self._lock:
            summary = copy.deepcopy(self._summary)
            writer = self._writer
            stamp = self._file_stamp
        if summary is None or writer is None:
            raise FactPersistencePending("observation writer is initializing")
        # The worker owns insertions; membership checks perform no file I/O.
        total = linked = 0
        for row in realtime_rows or ():
            key = str(row.get("spot_observation_key") or "").strip()
            if key:
                total += 1
                linked += int(key in writer._seen_keys)
        summary["link_coverage"] = {
            "realtime_rows_with_observation_key": total, "linked_rows": linked,
            "missing_fact_key_rows": total-linked, "coverage_pct": round(linked / total * 100, 6) if total else 0.0,
        }
        after = self.snapshot()
        if not after["writes_drained"] or before["accepted_count"] != after["accepted_count"]:
            raise FactPersistencePending("observation manifest generation changed during closeout")
        stat = writer.output_path.stat()  # Closeout only; never on poll/health path.
        if stamp != (stat.st_size, stat.st_mtime_ns):
            raise RuntimeError("observation fact changed outside the captured manifest generation")
        summary["_persistence_generation"] = after["accepted_count"]
        return summary

    def close(self, timeout_sec: float) -> bool:
        with self._lock:
            self._state["accepting"] = False
        self._stop.set()
        self._thread.join(max(0, timeout_sec))
        return not self._thread.is_alive() and bool(self.snapshot()["writes_drained"])

    def _refresh_state(self, writer: SpotObservationFactWriter) -> None:
        # All stat/read/manifest work is performed by the single owner thread.
        pending = writer.spool_pending_count()
        summary = writer.manifest_summary()
        stat = writer.output_path.stat()
        with self._lock:
            self._summary = summary
            self._file_stamp = (stat.st_size, stat.st_mtime_ns)
            self._state["write_failure_count"] = self._worker_failure_count + writer.failure_count
            self._state["spool_failure_count"] = writer.spool_failure_count
            self._state["spool_last_error_code"] = writer.spool_last_error_code
            self._state["spool_pending_count"] = pending
            self._state["existing_fact_hash_ms"] = writer.existing_fact_hash_ms
            self._state["existing_fact_index_ms"] = writer.existing_fact_index_ms

    def _probe_required_file_access(self, writer: SpotObservationFactWriter) -> None:
        # The owner alone opens the existing file. This does not append, create,
        # repair history, or claim that other required destinations are ready.
        if (self._stop.is_set() or self._required_file_probe_at is None
                or time.monotonic() < self._required_file_probe_at):
            return
        error_type = None
        try:
            with writer.output_path.open("r+b"):
                pass
        except OSError as exc:
            error_type = type(exc).__name__
        checked = time.monotonic()
        with self._lock:
            self._state["required_file_availability"] = "blocked" if error_type else "available"
            self._state["required_file_error_type"] = error_type
            self._state["required_file_checked_monotonic"] = checked
            if error_type:
                self._state["required_file_failure_count"] += 1
                self._required_file_probe_at = checked + self._required_file_probe_delay
                self._required_file_probe_delay = min(30.0, 2 * self._required_file_probe_delay)
            else:
                self._state["required_file_last_success_monotonic"] = checked
                self._required_file_probe_at = None
                self._required_file_probe_delay = 1.0
            self._state["required_file_next_probe_monotonic"] = self._required_file_probe_at

    def _run(self) -> None:
        started = time.monotonic()
        try:
            writer = self._factory()
            self._writer = writer
            writer.payload_reservation = self._reserve_writer_payload
            if not writer.ensure_initialized():
                raise RuntimeError("fact_header_initialization_failed")
            writer._flush_spool()
            self._refresh_state(writer)
            with self._lock:
                self._state["initialization_state"] = "ready"
                self._state["initialization_duration_ms"] = (time.monotonic()-started)*1000
            self._probe_required_file_access(writer)
        except Exception:
            with self._lock:
                self._state["initialization_state"] = "failed"
                self._state["accepting"] = False
                self._state["write_failure_count"] += 1
                self._state["last_error_code"] = "initialization_failed"
            return  # Accepted-but-unwritten items remain visible; never claim clean.
        while not self._stop.is_set() or not self._queue.empty():
            try:
                event = self._queue.get(timeout=.05)
            except queue.Empty:
                self._probe_required_file_access(writer)
                continue
            started = time.monotonic()
            decoded = None
            processing_bytes = 0
            with self._lock:
                self._state["inflight"] = True
                self._state["last_queue_residence_ms"] = (started-event.enqueued_at)*1000
            try:
                # bytes decoding temporarily owns the whole JSON text while
                # building strings in the result. Both fit within twice the
                # text bound computed at admission; queued bytes remain owned.
                decode_reservation = 2 * event.text_storage_bytes
                with self._lock:
                    if self._state["pending_payload_bytes"] + decode_reservation > FACT_PENDING_PAYLOAD_BYTE_LIMIT:
                        raise _PayloadBudgetExceeded
                    self._state["pending_payload_bytes"] += decode_reservation
                    self._state["processing_payload_bytes"] += decode_reservation
                    processing_bytes = decode_reservation
                decoded = json.loads(event.payload)
                decoded_bytes = _decoded_string_bytes(decoded)
                with self._lock:
                    self._state["pending_payload_bytes"] -= processing_bytes - decoded_bytes
                    self._state["processing_payload_bytes"] -= processing_bytes - decoded_bytes
                    processing_bytes = decoded_bytes
                failures_before = writer.failure_count
                writer.write_fact(decoded)
                if writer.failure_count > failures_before:
                    self._record_failure("fact_or_spool_write_failed", event.observation_key, worker_failure=False)
                self._refresh_state(writer)
                with self._lock:
                    if writer.failure_count == failures_before:
                        self._state["last_success_at"] = time.time()
            except _PayloadBudgetExceeded:
                self._record_failure("decode_byte_limit", event.observation_key, worker_failure=True)
            except FactPayloadBudgetExceeded as exc:
                self._record_failure(exc.reason, event.observation_key, worker_failure=True)
            except Exception:
                self._record_failure("writer_state_unavailable", event.observation_key, worker_failure=True)
            finally:
                payload_size = len(event.payload)
                # Release the actual references before returning their budget.
                decoded = None
                del event
                with self._lock:
                    self._state["inflight"] = False
                    self._pending_enqueued_at.popleft()
                    self._state["completed_count"] += 1
                    self._state["pending_payload_bytes"] -= payload_size + processing_bytes
                    self._state["pending_source_payload_bytes"] -= payload_size
                    self._state["processing_payload_bytes"] -= processing_bytes
                    self._state["last_write_duration_ms"] = (time.monotonic()-started)*1000
                self._queue.task_done()
