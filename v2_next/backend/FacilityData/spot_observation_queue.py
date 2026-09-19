"""Bounded persistence owner. Producers only serialize and enqueue immutable events.

Saturation rejects the newest event and latches an observable failure. This is not
a promise of lossless operation through an unbounded storage outage.
"""
from __future__ import annotations

import copy
import json
import queue
import threading
import time
from typing import Any, Callable, Mapping

from backend.FacilityData.spot_observation_fact import SpotObservationFactWriter


class FactPersistencePending(RuntimeError):
    """Normal asynchronous work remains; it is not a disk failure."""


class SpotObservationQueue:
    def __init__(self, factory: Callable[[], SpotObservationFactWriter], capacity: int = 256):
        if isinstance(capacity, bool) or capacity <= 0:
            raise ValueError("capacity must be positive")
        self._factory = factory
        self._queue: queue.Queue[tuple[bytes, float]] = queue.Queue(maxsize=capacity)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._writer: SpotObservationFactWriter | None = None
        self._summary: dict[str, Any] | None = None
        self._file_stamp: tuple[int, int] | None = None
        self._state: dict[str, Any] = {
            "queue_capacity": capacity, "accepted_count": 0, "completed_count": 0,
            "rejected_count": 0, "write_failure_count": 0, "spool_failure_count": 0,
            "spool_pending_count": 0, "inflight": False, "initialization_state": "pending",
            "initialization_duration_ms": None, "last_write_duration_ms": None,
            "last_error_code": None, "last_success_at": None, "accepting": True,
            "last_queue_residence_ms": None, "existing_fact_hash_ms": None, "existing_fact_index_ms": None,
        }
        self._thread = threading.Thread(target=self._run, name="SPOT-ObservationFact", daemon=True)
        self._thread.start()

    def enqueue(self, snapshot: Mapping[str, Any]) -> bool:
        try:
            # Bytes own all nested data. No caller can mutate a queued observation.
            payload = json.dumps(dict(snapshot), ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return self._reject("snapshot_serialization_failed")
        with self._lock:
            if not self._state["accepting"]:
                return self._reject_locked("persistence_closed")
            try:
                self._queue.put_nowait((payload, time.monotonic()))
            except queue.Full:
                return self._reject_locked("queue_full")
            self._state["accepted_count"] += 1
        return True

    def _reject(self, code: str) -> bool:
        with self._lock:
            return self._reject_locked(code)

    def _reject_locked(self, code: str) -> bool:
        self._state["rejected_count"] += 1
        self._state["last_error_code"] = code
        return False

    def snapshot(self) -> dict[str, Any]:
        # Never wait on a writer/file/spool lock, scan, or filesystem call.
        with self._lock:
            state = dict(self._state)
        state["pending_write_count"] = state["accepted_count"] - state["completed_count"]
        state["queue_depth"] = self._queue.qsize()
        state["writer_alive"] = self._thread.is_alive()
        state["writes_drained"] = (
            state["initialization_state"] == "ready" and state["pending_write_count"] == 0
            and state["write_failure_count"] == 0 and state["rejected_count"] == 0
            and state["spool_pending_count"] == 0 and state["spool_failure_count"] == 0
        )
        return state

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
            self._state["write_failure_count"] = max(self._state["write_failure_count"], writer.failure_count)
            self._state["spool_failure_count"] = writer.spool_failure_count
            self._state["spool_pending_count"] = pending
            self._state["existing_fact_hash_ms"] = writer.existing_fact_hash_ms
            self._state["existing_fact_index_ms"] = writer.existing_fact_index_ms

    def _run(self) -> None:
        started = time.monotonic()
        try:
            writer = self._factory()
            self._writer = writer
            if not writer.ensure_initialized():
                raise RuntimeError("fact_header_initialization_failed")
            writer._flush_spool()
            self._refresh_state(writer)
            with self._lock:
                self._state["initialization_state"] = "ready"
                self._state["initialization_duration_ms"] = (time.monotonic()-started)*1000
        except Exception:
            with self._lock:
                self._state["initialization_state"] = "failed"
                self._state["accepting"] = False
                self._state["write_failure_count"] += 1
                self._state["last_error_code"] = "initialization_failed"
            return  # Accepted-but-unwritten items remain visible; never claim clean.
        while not self._stop.is_set() or not self._queue.empty():
            try:
                payload, enqueued_at = self._queue.get(timeout=.05)
            except queue.Empty:
                continue
            started = time.monotonic()
            with self._lock:
                self._state["inflight"] = True
                self._state["last_queue_residence_ms"] = (started-enqueued_at)*1000
            try:
                writer.write_fact(json.loads(payload))
                self._refresh_state(writer)
                with self._lock:
                    if writer.failure_count:
                        self._state["last_error_code"] = "fact_or_spool_write_failed"
                    else:
                        self._state["last_success_at"] = time.time()
            except Exception:
                with self._lock:
                    self._state["write_failure_count"] += 1
                    self._state["last_error_code"] = "writer_state_unavailable"
            finally:
                with self._lock:
                    self._state["inflight"] = False
                    self._state["completed_count"] += 1
                    self._state["last_write_duration_ms"] = (time.monotonic()-started)*1000
                self._queue.task_done()
