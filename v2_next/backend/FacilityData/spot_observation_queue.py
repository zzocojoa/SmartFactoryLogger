"""Bounded persistence owner. Producers only serialize and enqueue immutable events.

Saturation rejects the newest event and latches an observable failure. This is not
a promise of lossless operation through an unbounded storage outage.
"""
from __future__ import annotations

import copy
import hashlib
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import queue
import stat
import threading
import time
from typing import Any, Callable, Iterator, Literal, Mapping

from backend.FacilityData.persistence_payload import (
    PayloadBudgetExceeded as _PayloadBudgetExceeded, prepare_json_payload as _prepare_json_payload,
    decoded_string_bytes as _decoded_string_bytes,
    encode_json_payload as _encode_json_payload,
)
from backend.FacilityData.spot_observation_fact import (
    FACT_SPOOL_PENDING_BYTE_LIMIT, FactPayloadBudgetExceeded, SpotObservationFactWriter, build_spot_observation_key,
)
from backend.FacilityData.freshness import clock_domain_id
from backend.FacilityData.spot_image_fact import _probe_storage_directory
from backend.FacilityData.persistence_pressure import StoragePressureSample


FACT_PENDING_PAYLOAD_BYTE_LIMIT = 16 * 1024**2
_logger = logging.getLogger(__name__)
FactAdmissionStatus = Literal[
    "ACCEPTED", "REJECTED_FULL", "REJECTED_LIMIT", "REJECTED_UNAVAILABLE",
    "REJECTED_CLOSED", "DISABLED", "INVALID",
]


def _required_file_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    if not stat.S_ISREG(info.st_mode) or not info.st_ino:
        raise RuntimeError("observation fact file identity is unavailable")
    # Windows path stat and handle fstat may expose different creation-time
    # values. Compare the same identity fields used by image fact ownership.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


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
    clock_domain: str


class SpotObservationQueue:
    def __init__(self, factory: Callable[[], SpotObservationFactWriter], capacity: int = 256,
                 *, config_generation: int | None = None):
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
        self._required_file_identity: tuple[int, int, int, int] | None = None
        self._required_file_probe_at: float | None = 0.0
        self._required_file_probe_delay = 1.0
        self._spool_recovery_at: float | None = None
        self._spool_recovery_delay = 1.0
        self._storage_directories: dict[str, Path] = {}
        self._storage_probes: dict[str, dict[str, Any]] = {}
        self._state: dict[str, Any] = {
            "config_generation": config_generation,
            "queue_capacity": capacity, "accepted_count": 0, "completed_count": 0,
            "rejected_count": 0, "write_failure_count": 0, "spool_failure_count": 0,
            "spool_last_error_code": None,
            "spool_pending_count": 0, "inflight": False, "initialization_state": "pending",
            "spool_pending_bytes": None, "spool_retained_bytes": None,
            "spool_pending_byte_limit": FACT_SPOOL_PENDING_BYTE_LIMIT,
            "spool_usage_status": "unknown", "spool_usage_error_type": None,
            "spool_usage_failure_count": 0, "spool_usage_checked_monotonic": None,
            "spool_timing_status": "unknown", "spool_oldest_pending_monotonic": None,
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
            "required_file_manual_recovery": False,
            "spool_next_recovery_monotonic": None, "spool_recovery_failure_count": 0,
            "spool_recovered_count": 0, "spool_recovery_error_type": None,
            "spool_manual_recovery": False,
            "initialization_next_retry_monotonic": None,
            "initialization_retry_delay_sec": 1.0,
            "initialization_failure_count": 0,
            "initialization_manual_recovery": False,
            "storage_probe_manual_recovery": False,
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
            if (self._state["required_file_manual_recovery"] or self._state["spool_manual_recovery"]
                    or self._state["storage_probe_manual_recovery"]):
                return self._reject_locked("REJECTED_UNAVAILABLE", "file_manual_recovery", observation_key)
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
                event = _FactEvent(payload, text_characters * text_width, observation_key,
                                   time.monotonic(), clock_domain_id())
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
            state["storage_destinations"] = [dict(probe) for probe in self._storage_probes.values()]
            oldest = self._pending_enqueued_at[0] if self._pending_enqueued_at else None
            state["memory_oldest_pending_monotonic"] = oldest
            if state['spool_pending_count'] or state['spool_pending_bytes']:
                spool_oldest = state['spool_oldest_pending_monotonic']
                oldest = (None if state['spool_timing_status'] != 'known'
                          else spool_oldest if oldest is None else min(oldest, spool_oldest))
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
            and not state["required_file_manual_recovery"]
            and not state["spool_manual_recovery"]
            and not state["storage_probe_manual_recovery"]
        )
        return state

    def storage_pressure_samples(self, *, enabled: bool = True) -> list[StoragePressureSample]:
        state = self.snapshot()
        destinations = {item["sink_id"]: item for item in state["storage_destinations"]}
        samples = []
        for sink_id in ("temperature_fact", "temperature_spool"):
            probe = destinations.get(sink_id, {})
            fact = sink_id == "temperature_fact"
            manual = (state["initialization_manual_recovery"] or probe.get("manual_recovery_required", False)
                      or (state["required_file_manual_recovery"] if fact else state["spool_manual_recovery"]))
            statuses = [probe.get("probe_status", "unknown")]
            if state["initialization_state"] != "ready":
                statuses.append("blocked" if state["initialization_state"] == "failed" else "unknown")
            if fact:
                statuses.append(state["required_file_availability"])
            elif state["spool_usage_status"] != "measured":
                statuses.append("unknown")
            availability = ("blocked" if manual or "blocked" in statuses else
                            "available" if all(value == "available" for value in statuses) else "unknown")
            oldest = (state["memory_oldest_pending_monotonic"] if fact else
                      state["spool_oldest_pending_monotonic"] if state["spool_timing_status"] == "known" else None)
            samples.append(StoragePressureSample(
                sink_id=sink_id, config_generation=state["config_generation"],
                destination_key=probe.get("destination_key", ""), enabled=enabled, availability=availability,
                pending_count=state["pending_write_count"] if fact else 0,
                pending_bytes=state["pending_payload_bytes"] if fact else 0,
                count_limit=state["queue_capacity"], byte_limit=state["pending_payload_byte_limit"],
                spool_bytes=0 if fact else (state["spool_retained_bytes"] or 0),
                spool_limit=state["spool_pending_byte_limit"],
                pending_recovery=0 if fact else state["spool_pending_count"],
                oldest_pending_monotonic=oldest, stage_due_monotonic=oldest,
                writer_alive=state["writer_alive"], manual_recovery_required=bool(manual),
                budget_pending_count=state["pending_write_count"],
                budget_pending_bytes=state["pending_payload_bytes"],
            ))
        return samples

    def _record_failure(self, code: str, observation_key: str, *, worker_failure: bool) -> None:
        with self._lock:
            if worker_failure:
                self._worker_failure_count += 1
            self._state["write_failure_count"] = self._worker_failure_count + (
                self._writer.failure_count if self._writer is not None else 0
            )
            self._state["last_error_code"] = code
            self._state["last_failed_observation_key"] = observation_key
            if code in ("fact_or_spool_write_failed", "writer_state_unavailable"):
                self._invalidate_required_file_locked()
        _logger.error("SPOT fact processing failed", extra={
            "observation_key": observation_key, "reason": code,
        })

    def _invalidate_required_file_locked(self) -> None:
        if self._state["required_file_manual_recovery"]:
            return
        if self._state["required_file_availability"] == "available":
            self._state["required_file_availability"] = "unknown"
        # New arrivals or repeated failures cannot postpone an owned retry.
        if self._required_file_probe_at is None:
            self._required_file_probe_at = time.monotonic() + self._required_file_probe_delay
        self._state["required_file_next_probe_monotonic"] = self._required_file_probe_at

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
        try:
            pending_bytes, retained_bytes = writer.spool_storage_usage()
            pending = writer.spool_pending_count()
            spool_oldest = writer.spool_oldest_pending_monotonic()
        except Exception as exc:
            with self._lock:
                self._state["spool_usage_status"] = "unknown"
                self._state["spool_usage_error_type"] = type(exc).__name__
                self._state["spool_usage_failure_count"] += 1
                self._state["spool_timing_status"] = "unknown"
            raise
        with self._lock:
            self._state.update(spool_pending_bytes=pending_bytes, spool_retained_bytes=retained_bytes,
                               spool_usage_status="measured", spool_usage_error_type=None,
                               spool_usage_checked_monotonic=time.monotonic(),
                               spool_oldest_pending_monotonic=spool_oldest,
                               spool_timing_status=('empty' if pending == 0 and pending_bytes == 0
                                                    else 'known' if spool_oldest is not None else 'unknown'))
        summary = writer.manifest_summary()
        stat = writer.output_path.stat()
        with self._lock:
            self._summary = summary
            self._file_stamp = (stat.st_size, stat.st_mtime_ns)
            self._required_file_identity = _required_file_identity(stat)
            self._state["write_failure_count"] = self._worker_failure_count + writer.failure_count
            self._state["spool_failure_count"] = writer.spool_failure_count
            self._state["spool_last_error_code"] = writer.spool_last_error_code
            self._state["spool_pending_count"] = pending
            if pending == 0:
                self._spool_recovery_at = None
                self._spool_recovery_delay = 1.0
            elif self._spool_recovery_at is None:
                self._spool_recovery_at = time.monotonic() + self._spool_recovery_delay
            self._state["spool_next_recovery_monotonic"] = self._spool_recovery_at
            self._state["existing_fact_hash_ms"] = writer.existing_fact_hash_ms
            self._state["existing_fact_index_ms"] = writer.existing_fact_index_ms

    def _probe_required_file_access(self, writer: SpotObservationFactWriter) -> None:
        # The owner alone opens the existing file. This does not append, create,
        # repair history, or claim that other required destinations are ready.
        if (self._stop.is_set() or self._required_file_probe_at is None
                or time.monotonic() < self._required_file_probe_at):
            return
        error_type = None
        manual_recovery = opened = False
        try:
            expected = self._required_file_identity
            if expected is None or _required_file_identity(writer.output_path.lstat()) != expected:
                raise RuntimeError("observation fact changed before access verification")
            with writer.output_path.open("r+b") as handle:
                opened = True
                if _required_file_identity(os.fstat(handle.fileno())) != expected:
                    raise RuntimeError("observation fact handle changed during access verification")
            if _required_file_identity(writer.output_path.lstat()) != expected:
                raise RuntimeError("observation fact changed after access verification")
        except (FileNotFoundError, RuntimeError) as exc:
            error_type, manual_recovery = type(exc).__name__, True
        except OSError as exc:
            error_type = type(exc).__name__
            # A close failure leaves resource ownership unresolved.
            manual_recovery = opened
        checked = time.monotonic()
        with self._lock:
            self._state["required_file_availability"] = "blocked" if error_type else "available"
            self._state["required_file_error_type"] = error_type
            self._state["required_file_checked_monotonic"] = checked
            self._state["required_file_manual_recovery"] = manual_recovery
            if error_type:
                self._state["required_file_failure_count"] += 1
                self._required_file_probe_at = None if manual_recovery else checked + self._required_file_probe_delay
                self._required_file_probe_delay = min(30.0, 2 * self._required_file_probe_delay)
                if manual_recovery:
                    self._state["accepting"] = False
            else:
                self._state["required_file_last_success_monotonic"] = checked
                self._required_file_probe_at = None
                self._required_file_probe_delay = 1.0
            self._state["required_file_next_probe_monotonic"] = self._required_file_probe_at

    def _register_storage_directories(self, writer: SpotObservationFactWriter) -> None:
        # These are the writer's actual fixed destinations, not a UI-selected
        # fallback. Do not publish raw filesystem paths in status snapshots.
        self._storage_directories = {
            "temperature_fact": writer.output_path.parent,
            "temperature_spool": writer.spool_write_directory,
        }
        with self._lock:
            for sink_id, directory in self._storage_directories.items():
                key = hashlib.sha256(os.fsencode(os.path.normcase(os.path.abspath(directory)))).hexdigest()
                self._storage_probes[sink_id] = {
                    "sink_id": sink_id, "destination_key": key, "probe_scope": "directory_only",
                    "probe_status": "unknown", "probe_error_type": None,
                    "probe_failure_count": 0, "last_probe_monotonic": None,
                    "last_probe_success_monotonic": None, "next_probe_monotonic": 0.0,
                    "retry_delay_sec": 1.0, "manual_recovery_required": False,
                }

    def _probe_storage_destinations(self) -> None:
        # The existing owner performs I/O even with no arrivals or UI requests.
        # Each destination keeps its own failure history and retry schedule.
        for sink_id, directory in self._storage_directories.items():
            if self._stop.is_set():
                return
            with self._lock:
                probe = self._storage_probes[sink_id]
                due = probe["next_probe_monotonic"]
            if due is None or time.monotonic() < due:
                continue
            error_type = None
            manual = False
            try:
                with self._reserve_writer_payload(128, "storage_probe_byte_limit"):
                    _probe_storage_directory(directory)
            except (OSError, FactPayloadBudgetExceeded) as exc:
                error_type = type(exc).__name__
            except RuntimeError as exc:
                error_type, manual = type(exc).__name__, True
            checked = time.monotonic()
            with self._lock:
                probe.update(probe_status="blocked" if error_type else "available",
                             probe_error_type=error_type, last_probe_monotonic=checked,
                             manual_recovery_required=manual)
                if error_type:
                    probe["probe_failure_count"] += 1
                    probe["next_probe_monotonic"] = None if manual else checked + probe["retry_delay_sec"]
                    probe["retry_delay_sec"] = min(30.0, 2 * probe["retry_delay_sec"])
                    if manual:
                        self._state["storage_probe_manual_recovery"] = True
                        self._state["accepting"] = False
                else:
                    probe.update(last_probe_success_monotonic=checked,
                                 next_probe_monotonic=checked + 1.0, retry_delay_sec=1.0)

    def _recover_spool_if_due(self, writer: SpotObservationFactWriter) -> None:
        if (self._stop.is_set() or self._spool_recovery_at is None
                or time.monotonic() < self._spool_recovery_at
                or self._state["required_file_manual_recovery"] or self._state["spool_manual_recovery"]):
            return
        # Check the original file identity before any retry writes. A scheduled
        # access retry keeps its own backoff; recovery cannot bypass it.
        if self._required_file_probe_at is None:
            self._required_file_probe_at = time.monotonic()
        self._probe_required_file_access(writer)
        if self._required_file_probe_at is not None or self._state["required_file_availability"] != "available":
            return
        before = self._state["spool_pending_count"]
        error: Exception | None = None
        try:
            writer._flush_spool()  # Existing owner-bounded 20-row/1 MiB batch.
        except Exception as exc:
            error = exc
        try:
            self._refresh_state(writer)
        except Exception as exc:
            error = exc
        with self._lock:
            recovered = max(0, before - self._state["spool_pending_count"])
            self._state["spool_recovered_count"] += recovered
            if error is not None:
                self._state["spool_recovery_failure_count"] += 1
                self._state["spool_recovery_error_type"] = type(error).__name__
                if isinstance(error, (OSError, FactPayloadBudgetExceeded)):
                    self._spool_recovery_delay = 1.0 if recovered else min(30.0, 2 * self._spool_recovery_delay)
                    self._spool_recovery_at = time.monotonic() + self._spool_recovery_delay
                    if isinstance(error, OSError):
                        self._invalidate_required_file_locked()
                else:
                    self._state["spool_manual_recovery"] = True
                    self._state["accepting"] = False
                    self._spool_recovery_at = None
            else:
                self._state["spool_recovery_error_type"] = None
                self._spool_recovery_delay = 1.0
                self._spool_recovery_at = (time.monotonic() + 1.0 if self._state["spool_pending_count"] else None)
                if recovered:
                    self._state["last_success_at"] = time.time()
            self._state["spool_next_recovery_monotonic"] = self._spool_recovery_at

    def _initialize_writer(self, writer: SpotObservationFactWriter) -> bool:
        if not writer.initialization_retryable:
            return writer.ensure_initialized()
        # Only confirmed, closed read failures are retried here. Creation,
        # header writes and spool mutations retain their separate failure path.
        delay = 1.0
        try:
            while writer.initialization_retryable and not self._stop.is_set():
                due = time.monotonic() + delay
                with self._lock:
                    self._state["initialization_state"] = "failed"
                    self._state["accepting"] = False
                    self._state["initialization_failure_count"] += 1
                    self._state["write_failure_count"] = self._worker_failure_count + writer.failure_count
                    self._state["last_error_code"] = "initialization_failed"
                    self._state["required_file_availability"] = "blocked"
                    self._state["initialization_next_retry_monotonic"] = due
                    self._state["initialization_retry_delay_sec"] = delay
                while time.monotonic() < due:
                    if self._stop.wait(min(.05, max(0.0, due - time.monotonic()))):
                        return False
                if self._stop.is_set():
                    return False
                if writer.ensure_initialized():
                    return True
                delay = min(30.0, 2 * delay)
            return False
        finally:
            with self._lock:
                self._state["initialization_next_retry_monotonic"] = None
                self._state["initialization_manual_recovery"] = writer.initialization_manual_recovery

    def _run(self) -> None:
        started = time.monotonic()
        try:
            writer = self._factory()
            self._writer = writer
            writer.payload_reservation = self._reserve_writer_payload
            self._register_storage_directories(writer)
            if not self._initialize_writer(writer):
                raise RuntimeError("fact_header_initialization_failed")
            writer._flush_spool()
            self._refresh_state(writer)
            self._probe_storage_destinations()
            with self._lock:
                self._state["initialization_state"] = "ready"
                self._state["accepting"] = not (self._stop.is_set() or self._state["storage_probe_manual_recovery"])
                self._state["initialization_duration_ms"] = (time.monotonic()-started)*1000
            self._probe_required_file_access(writer)
            if self._state["required_file_manual_recovery"] or self._state["storage_probe_manual_recovery"]:
                return
        except Exception:
            with self._lock:
                self._state["initialization_state"] = "failed"
                self._state["accepting"] = False
                self._worker_failure_count += 1
                self._state["write_failure_count"] = self._worker_failure_count + (
                    self._writer.failure_count if self._writer is not None else 0)
                self._state["initialization_manual_recovery"] = bool(
                    self._writer is not None and self._writer.initialization_manual_recovery)
                self._state["last_error_code"] = "initialization_failed"
            return  # Accepted-but-unwritten items remain visible; never claim clean.
        while not self._stop.is_set() or not self._queue.empty():
            self._probe_storage_destinations()
            if self._state["storage_probe_manual_recovery"]:
                break
            self._recover_spool_if_due(writer)
            if self._state["required_file_manual_recovery"] or self._state["spool_manual_recovery"]:
                break
            self._probe_required_file_access(writer)
            if self._state["required_file_manual_recovery"]:
                break
            try:
                event = self._queue.get(timeout=.05)
            except queue.Empty:
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
                spool_failures_before = writer.spool_failure_count
                # During normal collection, new arrivals do not override the
                # recovery owner's backoff. Keep existing terminal queue-drain
                # behavior for already admitted events after close is requested.
                deferred = self._state["spool_pending_count"] > 0 and not self._stop.is_set()
                stored = writer.write_fact(decoded, defer_to_spool=deferred,
                                           admission=(event.enqueued_at, event.clock_domain))
                if writer.failure_count > failures_before or writer.spool_failure_count > spool_failures_before:
                    self._record_failure("fact_or_spool_write_failed", event.observation_key,
                                         worker_failure=writer.failure_count == failures_before)
                self._refresh_state(writer)
                with self._lock:
                    if stored is not None and writer.failure_count == failures_before:
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
