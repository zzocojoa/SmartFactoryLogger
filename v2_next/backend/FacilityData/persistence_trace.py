"""Bounded persistence-result segments, owned by a data-path writer."""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Mapping
from uuid import uuid4
from backend.FacilityData.persistence_payload import PayloadBudgetExceeded, encode_json_payload, prepare_json_payload

TRACE_SEGMENT_RECORD_LIMIT = 1000
TRACE_PENDING_SEGMENT_LIMIT = 2
TRACE_SEGMENT_BYTE_LIMIT = 1024**2
TRACE_PENDING_BYTE_LIMIT = 2 * TRACE_SEGMENT_BYTE_LIMIT
TRACE_READBACK_BYTES = 4096
TRACE_FLUSH_INTERVAL_SEC = 1.0
ADMISSION_REJECTION_RANGE_LIMIT = 4096


@dataclass(frozen=True)
class AdmissionRejectionRange:
    first_sequence: int
    last_sequence: int
    status: str
    reason: str | None
    config_generation: int


class AdmissionRejectionLedger:
    """Admission accounting owned by one serialized producer generation."""

    def __init__(self, *, after_sequence: int = 0) -> None:
        self._after_sequence = after_sequence
        self._counts: Counter[str] = Counter()
        self._ranges: deque[AdmissionRejectionRange] = deque()
        self._claimed: AdmissionRejectionRange | None = None
        self._pending_rejections = 0
        self._committed_rejections = 0
        self._committed_ranges = 0
        self._omitted = 0
        self._first_omitted: int | None = None
        self._last_omitted: int | None = None
        self._last_sequence = after_sequence

    def record(self, sequence: int, status: str, reason: str | None, generation: int) -> None:
        self._last_sequence = sequence
        self._counts[status] += 1
        if status in ("ACCEPTED", "DISABLED"):
            return
        if self._ranges:
            previous = self._ranges[-1]
            if (previous.last_sequence + 1 == sequence and previous.status == status
                    and previous.reason == reason and previous.config_generation == generation):
                self._ranges[-1] = AdmissionRejectionRange(previous.first_sequence, sequence, status, reason, generation)
                self._pending_rejections += 1
                return
        if len(self._ranges) + int(self._claimed is not None) < ADMISSION_REJECTION_RANGE_LIMIT:
            self._ranges.append(AdmissionRejectionRange(sequence, sequence, status, reason, generation))
            self._pending_rejections += 1
            return
        self._omitted += 1
        if self._first_omitted is None:
            self._first_omitted = sequence
        self._last_omitted = sequence

    def snapshot(self) -> dict[str, Any]:
        accounted = sum(self._counts.values())
        produced = self._last_sequence - self._after_sequence
        unaccounted = produced - accounted
        accepted, excluded = self._counts["ACCEPTED"], self._counts["DISABLED"]
        return {"produced_count": produced, "last_producer_seq": self._last_sequence,
                "accounted_count": accounted, "unaccounted_count": unaccounted,
                "accepted_count": accepted, "excluded_count": excluded,
                "rejected_count": accounted - accepted - excluded, "outcome_counts": dict(self._counts),
                "rejection_range_count": len(self._ranges) + int(self._claimed is not None),
                "rejection_range_limit": ADMISSION_REJECTION_RANGE_LIMIT,
                "pending_rejection_count": self._pending_rejections,
                "committed_rejection_count": self._committed_rejections,
                "committed_rejection_range_count": self._committed_ranges,
                "details_incomplete": self._omitted > 0 or unaccounted != 0, "omitted_rejection_count": self._omitted,
                "first_omitted_producer_seq": self._first_omitted, "last_omitted_producer_seq": self._last_omitted}

    def rejection_ranges(self) -> tuple[AdmissionRejectionRange, ...]:
        return (() if self._claimed is None else (self._claimed,)) + tuple(self._ranges)

    def close(self, final_sequence: int) -> None:
        self._last_sequence = final_sequence

    def claim_range(self) -> AdmissionRejectionRange | None:
        if self._claimed is None and self._ranges:
            self._claimed = self._ranges.popleft()
        return self._claimed

    def acknowledge_range(self, claimed: AdmissionRejectionRange) -> None:
        if claimed is None or claimed is not self._claimed:
            raise ValueError("Only the currently claimed rejection range may be acknowledged")
        count = claimed.last_sequence - claimed.first_sequence + 1
        self._pending_rejections -= count
        self._committed_rejections += count
        self._committed_ranges += 1
        self._claimed = None


class _TraceContentUncertain(OSError):
    """Keep existing bytes and prevent a false complete evidence result."""


@dataclass
class _TraceSegment:
    sequence: int
    header: bytes
    flush_due_monotonic: float
    records: list[bytes] = field(default_factory=list)
    sealed: bool = False

    @property
    def size(self) -> int:
        return len(self.header) + sum(map(len, self.records))


class PersistenceTraceWriter:
    def __init__(self, root: Path, producer_id: str, *, clock: Callable[[], float] = time.monotonic):
        self.root = root
        self.producer_id = producer_id
        self.clock = clock
        self._instance_id = uuid4().hex
        self._next_sequence = 1
        self._committed_sequence = 0
        self._segments: deque[_TraceSegment] = deque()
        self._lock = threading.Lock()
        self._writer_lock = threading.Lock()
        self._failure_count = 0
        self._refused_count = 0
        self._incomplete = False
        self._processing_bytes = 0
        self._blocked_workspace_bytes = 0
        self._last_error: str | None = None

    def append(self, record: Mapping[str, Any]) -> int | None:
        with self._lock:
            try:
                prepared, byte_bound, workspace = self._prepare(record)
            except (PayloadBudgetExceeded, TypeError, ValueError, OverflowError, RecursionError):
                self._refuse("invalid_or_oversized_record", incomplete=True)
                return None
            if byte_bound > TRACE_SEGMENT_BYTE_LIMIT:
                self._refuse("record_too_large", incomplete=True)
                return None
            if workspace > TRACE_PENDING_BYTE_LIMIT - TRACE_READBACK_BYTES:
                self._refuse("record_workspace_too_large", incomplete=True)
                return None
            pending_bytes = sum(segment.size for segment in self._segments)
            # Keep readback possible even when the producer fills both slots.
            available = TRACE_PENDING_BYTE_LIMIT - pending_bytes - max(self._processing_bytes, TRACE_READBACK_BYTES)
            if workspace > available:
                self._blocked_workspace_bytes = max(self._blocked_workspace_bytes, workspace)
                self._refuse("trace_workspace_full")
                return None
            if self._segments and len(self._segments[-1].records) >= TRACE_SEGMENT_RECORD_LIMIT:
                self._segments[-1].sealed = True
            segment = self._segments[-1] if self._segments and not self._segments[-1].sealed else None
            if segment is not None and segment.size + byte_bound > TRACE_SEGMENT_BYTE_LIMIT:
                segment.sealed = True
                segment = None
            header = b""
            if segment is None:
                if len(self._segments) >= TRACE_PENDING_SEGMENT_LIMIT:
                    self._refuse("trace_segments_full")
                    return None
                try:
                    header_source, header_bound, header_workspace = self._prepare({
                        "schema_version": 1, "producer_instance_id": self.producer_id,
                        "writer_instance_id": self._instance_id, "segment_id": self._next_sequence,
                    })
                except (PayloadBudgetExceeded, TypeError, ValueError, OverflowError, RecursionError):
                    self._refuse("invalid_or_oversized_header", incomplete=True)
                    return None
                if header_bound + byte_bound > TRACE_SEGMENT_BYTE_LIMIT:
                    self._refuse("record_too_large", incomplete=True)
                    return None
                if max(header_workspace, header_bound + workspace) > TRACE_PENDING_BYTE_LIMIT - TRACE_READBACK_BYTES:
                    self._refuse("header_workspace_too_large", incomplete=True)
                    return None
                if max(header_workspace, header_bound + workspace) > available:
                    self._blocked_workspace_bytes = max(
                        self._blocked_workspace_bytes, header_workspace, header_bound + workspace)
                    self._refuse("trace_workspace_full")
                    return None
                header = encode_json_payload(header_source, sort_keys=True, compact=True, newline=True)
            payload = encode_json_payload(prepared, sort_keys=True, compact=True, newline=True)
            if segment is None:
                segment = _TraceSegment(self._next_sequence, header, self.clock() + TRACE_FLUSH_INTERVAL_SEC)
                self._next_sequence += 1
                self._segments.append(segment)
            segment.records.append(payload)
            return segment.sequence

    def _refuse(self, reason: str, *, incomplete: bool = False) -> None:
        self._refused_count += 1
        self._incomplete |= incomplete
        self._last_error = reason

    @staticmethod
    def _prepare(record: Mapping[str, Any]) -> tuple[Any, int, int]:
        source, byte_bound, characters, width = prepare_json_payload(dict(record), TRACE_PENDING_BYTE_LIMIT)
        text_bytes = (characters + 1) * width
        return source, byte_bound + 1, max(2 * text_bytes, byte_bound + 1 + text_bytes)

    @staticmethod
    def _matches(path: Path, segment: _TraceSegment) -> bool:
        buffer = bytearray(TRACE_READBACK_BYTES)
        view = memoryview(buffer)
        with path.open("rb", buffering=0) as handle:
            for chunk in (segment.header, *segment.records):
                expected = memoryview(chunk)
                offset = 0
                while offset < len(chunk):
                    count = handle.readinto(view[:min(TRACE_READBACK_BYTES, len(chunk) - offset)])
                    if not count or view[:count] != expected[offset:offset + count]:
                        return False
                    offset += count
            return handle.readinto(view[:1]) == 0

    def _publish(self, segment: _TraceSegment) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        stem = f"{self._instance_id}-{segment.sequence:08d}"
        final = self.root / f"{stem}.trace.jsonl"
        pending = self.root / f".{stem}.pending"
        if final.exists():
            if not self._matches(final, segment):
                raise _TraceContentUncertain("trace_final_content_conflict")
            return  # Publication succeeded before an earlier error was observed.
        if pending.exists():
            if not self._matches(pending, segment):
                raise _TraceContentUncertain("trace_pending_content_uncertain")
        else:
            with pending.open("xb", buffering=0) as handle:
                if handle.write(segment.header) != len(segment.header):
                    raise _TraceContentUncertain("trace_short_write")
                for record in segment.records:
                    if handle.write(record) != len(record):
                        raise _TraceContentUncertain("trace_short_write")
                handle.flush()
                os.fsync(handle.fileno())
            if not self._matches(pending, segment):
                raise _TraceContentUncertain("trace_pending_content_uncertain")
        pending.replace(final)
        if not self._matches(final, segment):
            raise _TraceContentUncertain("trace_published_content_mismatch")

    def flush(self, *, force: bool = False) -> bool:
        with self._writer_lock:
            with self._lock:
                if not self._segments:
                    return True
                segment = self._segments[0]
                if (not force and not segment.sealed and len(segment.records) < TRACE_SEGMENT_RECORD_LIMIT
                        and segment.size < TRACE_SEGMENT_BYTE_LIMIT and self.clock() < segment.flush_due_monotonic):
                    return True
                segment.sealed = True
                self._processing_bytes = TRACE_READBACK_BYTES
            try:
                self._publish(segment)
            except OSError as exc:
                with self._lock:
                    self._failure_count += 1
                    uncertain = isinstance(exc, _TraceContentUncertain)
                    self._incomplete |= uncertain
                    self._last_error = str(exc) if uncertain else "trace_io_failed"
                return False
            finally:
                with self._lock:
                    self._processing_bytes = 0
            with self._lock:
                self._committed_sequence = segment.sequence
                self._segments.popleft()
                del segment  # Drop encoded bytes before another producer reuses their budget.
                available = TRACE_PENDING_BYTE_LIMIT - sum(item.size for item in self._segments) - TRACE_READBACK_BYTES
                if self._blocked_workspace_bytes <= available:
                    self._blocked_workspace_bytes = 0
                return True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            admission_blocked_reason = None
            available = (TRACE_PENDING_BYTE_LIMIT - sum(segment.size for segment in self._segments)
                         - max(self._processing_bytes, TRACE_READBACK_BYTES))
            if self._blocked_workspace_bytes > available:
                admission_blocked_reason = "trace_workspace_full"
            if len(self._segments) >= TRACE_PENDING_SEGMENT_LIMIT:
                tail = self._segments[-1]
                if (tail.sealed or len(tail.records) >= TRACE_SEGMENT_RECORD_LIMIT
                        or tail.size >= TRACE_SEGMENT_BYTE_LIMIT):
                    admission_blocked_reason = "trace_segments_full"
            return {"pending_records": sum(len(segment.records) for segment in self._segments),
                    "pending_bytes": sum(segment.size for segment in self._segments) + self._processing_bytes,
                    "processing_bytes": self._processing_bytes,
                    "pending_segments": len(self._segments),
                    "admission_blocked_reason": admission_blocked_reason,
                    "committed_segment_seq": self._committed_sequence,
                    "failure_count": self._failure_count,
                    "refused_count": self._refused_count, "incomplete": self._incomplete,
                    "last_error": self._last_error,
                    "next_flush_monotonic": self._segments[0].flush_due_monotonic if self._segments else None}
