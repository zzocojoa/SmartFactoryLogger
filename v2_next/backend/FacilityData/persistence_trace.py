"""Bounded persistence-result segments, owned by a data-path writer."""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
import os
from pathlib import Path
import stat
import threading
import time
from typing import Any, Callable, Mapping
from uuid import uuid4
from backend.FacilityData.persistence_payload import PayloadBudgetExceeded, encode_json_payload, prepare_json_payload
from backend.FacilityData.freshness import clock_domain_id
from backend.FacilityData.spot_image_fact import _probe_storage_directory

TRACE_SEGMENT_RECORD_LIMIT = 1000
TRACE_PENDING_SEGMENT_LIMIT = 2
TRACE_SEGMENT_BYTE_LIMIT = 1024**2
TRACE_PENDING_BYTE_LIMIT = 2 * TRACE_SEGMENT_BYTE_LIMIT
TRACE_READBACK_BYTES = 4096
TRACE_FLUSH_INTERVAL_SEC = 1.0
TRACE_PROBE_WORKSPACE_BYTES = 128
ADMISSION_REJECTION_RANGE_LIMIT = 4096


@dataclass(frozen=True)
class AdmissionRejectionRange:
    first_sequence: int
    last_sequence: int
    status: str
    reason: str | None
    config_generation: int


class AdmissionRejectionLedger:
    """Admission accounting and bounded non-accepted ranges for one producer."""

    def __init__(self, *, after_sequence: int = 0) -> None:
        self._after_sequence = after_sequence
        self._counts: Counter[str] = Counter()
        self._ranges: deque[AdmissionRejectionRange] = deque()
        self._claimed: AdmissionRejectionRange | None = None
        self._staged: deque[tuple[AdmissionRejectionRange, int]] = deque()
        self._pending: Counter[str] = Counter()
        self._committed: Counter[str] = Counter()
        self._range_counts: Counter[str] = Counter()
        self._committed_ranges: Counter[str] = Counter()
        self._omitted: Counter[str] = Counter()
        self._first_omitted: dict[str, int] = {}
        self._last_omitted: dict[str, int] = {}
        self._last_sequence = after_sequence

    def record(self, sequence: int, status: str, reason: str | None, generation: int) -> None:
        self._last_sequence = sequence
        self._counts[status] += 1
        if status == "ACCEPTED":
            return
        kind = "exclusion" if status == "DISABLED" else "rejection"
        if self._ranges:
            previous = self._ranges[-1]
            if (previous.last_sequence + 1 == sequence and previous.status == status
                    and previous.reason == reason and previous.config_generation == generation):
                self._ranges[-1] = AdmissionRejectionRange(previous.first_sequence, sequence, status, reason, generation)
                self._pending[kind] += 1
                return
        if len(self._ranges) + len(self._staged) + int(self._claimed is not None) < ADMISSION_REJECTION_RANGE_LIMIT:
            self._ranges.append(AdmissionRejectionRange(sequence, sequence, status, reason, generation))
            self._pending[kind] += 1
            self._range_counts[kind] += 1
            return
        self._omitted[kind] += 1
        self._first_omitted.setdefault(kind, sequence)
        self._last_omitted[kind] = sequence

    def snapshot(self) -> dict[str, Any]:
        accounted = sum(self._counts.values())
        produced = self._last_sequence - self._after_sequence
        unaccounted = produced - accounted
        accepted, excluded = self._counts["ACCEPTED"], self._counts["DISABLED"]
        result = {"produced_count": produced, "last_producer_seq": self._last_sequence,
                  "accounted_count": accounted, "unaccounted_count": unaccounted,
                  "accepted_count": accepted, "excluded_count": excluded,
                  "rejected_count": accounted - accepted - excluded, "outcome_counts": dict(self._counts),
                  "outcome_range_count": sum(self._range_counts.values()),
                  "outcome_range_limit": ADMISSION_REJECTION_RANGE_LIMIT,
                  "rejection_range_limit": ADMISSION_REJECTION_RANGE_LIMIT,
                  "range_budget_scope": "REJECTIONS_AND_POLICY_EXCLUSIONS",
                  "pending_outcome_count": sum(self._pending.values()),
                  "committed_outcome_count": sum(self._committed.values()),
                  "omitted_outcome_count": sum(self._omitted.values()),
                  "details_incomplete": bool(self._omitted) or unaccounted != 0,
                  "first_omitted_producer_seq": self._first_omitted.get("rejection"),
                  "last_omitted_producer_seq": self._last_omitted.get("rejection"),
                  "first_omitted_exclusion_seq": self._first_omitted.get("exclusion"),
                  "last_omitted_exclusion_seq": self._last_omitted.get("exclusion")}
        for kind in ("rejection", "exclusion"):
            result.update({f"{kind}_range_count": self._range_counts[kind],
                           f"pending_{kind}_count": self._pending[kind],
                           f"committed_{kind}_count": self._committed[kind],
                           f"committed_{kind}_range_count": self._committed_ranges[kind],
                           f"omitted_{kind}_count": self._omitted[kind]})
        return result

    def rejection_ranges(self) -> tuple[AdmissionRejectionRange, ...]:
        ranges = (tuple(item for item, _ in self._staged)
                  + (() if self._claimed is None else (self._claimed,)) + tuple(self._ranges))
        return tuple(item for item in ranges if item.status != "DISABLED")

    def close(self, final_sequence: int) -> None:
        self._last_sequence = final_sequence

    def claim_range(self) -> AdmissionRejectionRange | None:
        if self._claimed is None and self._ranges:
            self._claimed = self._ranges.popleft()
        return self._claimed

    def acknowledge_range(self, claimed: AdmissionRejectionRange) -> None:
        if claimed is None or claimed is not self._claimed:
            raise ValueError("Only the currently claimed rejection range may be acknowledged")
        self._acknowledge(claimed)
        self._claimed = None

    def _acknowledge(self, claimed: AdmissionRejectionRange) -> None:
        kind = "exclusion" if claimed.status == "DISABLED" else "rejection"
        count = claimed.last_sequence - claimed.first_sequence + 1
        self._pending[kind] -= count
        self._committed[kind] += count
        self._range_counts[kind] -= 1
        self._committed_ranges[kind] += 1

    def stage_range(self, claimed: AdmissionRejectionRange, segment_sequence: int) -> None:
        if claimed is None or claimed is not self._claimed:
            raise ValueError("Only the currently claimed rejection range may be staged")
        self._staged.append((claimed, segment_sequence))
        self._claimed = None

    def acknowledge_committed(self, segment_sequence: int) -> None:
        while self._staged and self._staged[0][1] <= segment_sequence:
            claimed, _ = self._staged.popleft()
            self._acknowledge(claimed)


class _TraceContentUncertain(OSError):
    """Keep existing bytes and prevent a false complete evidence result."""


@dataclass
class _TraceSegment:
    sequence: int
    header: bytes
    created_monotonic: float
    flush_due_monotonic: float
    records: list[bytes] = field(default_factory=list)
    sealed: bool = False
    recovery_required: bool = False

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
        self._manual_recovery_required = False
        self._next_retry_monotonic: float | None = None
        self._retry_delay_seconds = 1.0
        self._current_storage_availability = "unknown"
        self._availability_scope = "last_trace_publication"
        self._availability_checked_monotonic: float | None = None
        self._last_success_monotonic: float | None = None
        self._next_probe_monotonic = 0.0
        self._probe_failure_count = 0
        self._probe_failed = False
        self._probe_retry_delay_seconds = 1.0
        self._last_probe_success_monotonic: float | None = None
        self._last_probe_error: str | None = None
        self._latest_publication: tuple[Path, tuple[int, int, int, int]] | None = None
        self._processing_bytes = 0
        self._blocked_workspace_bytes = 0
        self._last_error: str | None = None

    def append(self, record: Mapping[str, Any]) -> int | None:
        with self._lock:
            if self._manual_recovery_required:
                self._refuse("trace_manual_recovery")
                return None
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
                created = self.clock()
                segment = _TraceSegment(self._next_sequence, header, created, created + TRACE_FLUSH_INTERVAL_SEC)
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

    @staticmethod
    def _file_identity(path: Path) -> tuple[int, int, int, int]:
        try:
            info = path.lstat()
        except FileNotFoundError as exc:
            raise _TraceContentUncertain("trace_publication_missing") from exc
        if not stat.S_ISREG(info.st_mode) or not info.st_ino:
            raise _TraceContentUncertain("trace_publication_identity_unavailable")
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns

    def _verified_publication(self, path: Path, segment: _TraceSegment) -> tuple[Path, tuple[int, int, int, int]]:
        before = self._file_identity(path)
        if not self._matches(path, segment) or self._file_identity(path) != before:
            raise _TraceContentUncertain("trace_published_content_mismatch")
        return path, before

    def _check_latest_publication(self) -> None:
        if self._latest_publication is None:
            return
        path, expected = self._latest_publication
        if self._file_identity(path) != expected:
            raise _TraceContentUncertain("trace_publication_changed")
        with path.open("rb", buffering=0) as handle:
            info = os.fstat(handle.fileno())
            if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != expected:
                raise _TraceContentUncertain("trace_publication_handle_changed")
        if self._file_identity(path) != expected:
            raise _TraceContentUncertain("trace_publication_changed_after_access")

    def _publish(self, segment: _TraceSegment) -> tuple[Path, tuple[int, int, int, int]]:
        self._check_latest_publication()
        self.root.mkdir(parents=True, exist_ok=True)
        stem = f"{self._instance_id}-{segment.sequence:08d}"
        final = self.root / f"{stem}.trace.jsonl"
        pending = self.root / f".{stem}.pending"
        if final.exists():
            # Publication may have succeeded before an earlier error was observed.
            return self._verified_publication(final, segment)
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
        return self._verified_publication(final, segment)

    def probe_storage(self) -> None:
        """Owner-only idle destination check; pending publications take priority."""
        with self._writer_lock:
            with self._lock:
                if (self._manual_recovery_required or self._segments
                        or self.clock() < self._next_probe_monotonic):
                    return
                self._processing_bytes = TRACE_PROBE_WORKSPACE_BYTES
            error: OSError | RuntimeError | None = None
            try:
                # Check the existing file before a directory probe can recreate
                # a deleted parent. Directory success cannot repair old evidence.
                self._check_latest_publication()
                _probe_storage_directory(self.root)
                self._check_latest_publication()
            except (OSError, RuntimeError) as exc:
                error = exc
            finally:
                with self._lock:
                    self._processing_bytes = 0
            with self._lock:
                checked = self.clock()
                self._availability_scope = "directory_probe"
                self._availability_checked_monotonic = checked
                self._current_storage_availability = "blocked" if error else "available"
                if error is not None:
                    self._probe_failure_count += 1
                    self._last_probe_error = type(error).__name__
                    self._probe_retry_delay_seconds = (min(30.0, self._probe_retry_delay_seconds * 2)
                                                       if self._probe_failed else 1.0)
                    self._probe_failed = True
                    # Uncertain cleanup must not accumulate more probe files.
                    if isinstance(error, (RuntimeError, _TraceContentUncertain)):
                        self._manual_recovery_required = True
                        self._incomplete = True
                        self._last_error = "trace_probe_manual_recovery"
                else:
                    if self._latest_publication is not None:
                        self._availability_scope = "directory_and_latest_publication_access"
                    self._probe_failed = False
                    self._probe_retry_delay_seconds = 1.0
                    self._last_probe_success_monotonic = checked
                self._next_probe_monotonic = checked + self._probe_retry_delay_seconds

    def flush(self, *, force: bool = False) -> bool:
        with self._writer_lock:
            with self._lock:
                if self._manual_recovery_required:
                    return False
                if not self._segments:
                    return True
                segment = self._segments[0]
                now = self.clock()
                if self._next_retry_monotonic is not None and now < self._next_retry_monotonic:
                    return False  # Producer/closeout force cannot bypass an owned retry schedule.
                if self._probe_failed and now < self._next_probe_monotonic:
                    return False  # New evidence cannot bypass failed required-file access.
                if (not force and not segment.sealed and len(segment.records) < TRACE_SEGMENT_RECORD_LIMIT
                        and segment.size < TRACE_SEGMENT_BYTE_LIMIT and now < segment.flush_due_monotonic):
                    return True
                segment.sealed = True
                # Early publication may advance the deadline. Retries may
                # never postpone that first scheduled/attempted completion.
                segment.flush_due_monotonic = min(segment.flush_due_monotonic, now)
                self._processing_bytes = TRACE_READBACK_BYTES
            try:
                publication = self._publish(segment)
            except OSError as exc:
                with self._lock:
                    self._failure_count += 1
                    segment.recovery_required = True
                    uncertain = isinstance(exc, _TraceContentUncertain)
                    self._incomplete |= uncertain
                    self._manual_recovery_required |= uncertain
                    self._last_error = str(exc) if uncertain else "trace_io_failed"
                    self._current_storage_availability = "blocked"
                    self._availability_scope = "last_trace_publication"
                    self._availability_checked_monotonic = self.clock()
                    if uncertain:
                        self._next_retry_monotonic = None
                    else:
                        self._retry_delay_seconds = (1.0 if self._next_retry_monotonic is None
                                                     else min(30.0, 2 * self._retry_delay_seconds))
                        self._next_retry_monotonic = self._availability_checked_monotonic + self._retry_delay_seconds
                return False
            finally:
                with self._lock:
                    self._processing_bytes = 0
            with self._lock:
                self._latest_publication = publication
                self._current_storage_availability = "available"
                self._availability_scope = "last_trace_publication"
                self._availability_checked_monotonic = self.clock()
                self._last_success_monotonic = self._availability_checked_monotonic
                self._next_retry_monotonic = None
                self._retry_delay_seconds = 1.0
                # Actual publication also proves current destination access.
                self._probe_failed = False
                self._probe_retry_delay_seconds = 1.0
                self._next_probe_monotonic = self._availability_checked_monotonic + 1.0
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
            if self._manual_recovery_required:
                admission_blocked_reason = "trace_manual_recovery"
            return {"pending_records": sum(len(segment.records) for segment in self._segments),
                    "oldest_pending_monotonic": self._segments[0].created_monotonic if self._segments else None,
                    "stage_due_monotonic": min((segment.flush_due_monotonic for segment in self._segments), default=None),
                    "clock_domain": clock_domain_id(),
                    "pending_recovery": sum(len(segment.records) for segment in self._segments
                                            if segment.recovery_required),
                    "pending_bytes": sum(segment.size for segment in self._segments) + self._processing_bytes,
                    "processing_bytes": self._processing_bytes,
                    "pending_segments": len(self._segments),
                    "admission_blocked_reason": admission_blocked_reason,
                    "manual_recovery_required": self._manual_recovery_required,
                    "current_storage_availability": self._current_storage_availability,
                    "availability_scope": self._availability_scope,
                    "availability_checked_monotonic": self._availability_checked_monotonic,
                    "next_probe_monotonic": (None if self._manual_recovery_required else self._next_probe_monotonic),
                    "probe_failure_count": self._probe_failure_count,
                    "probe_retry_delay_seconds": self._probe_retry_delay_seconds,
                    "last_probe_success_monotonic": self._last_probe_success_monotonic,
                    "last_probe_error": self._last_probe_error,
                    "last_success_monotonic": self._last_success_monotonic,
                    "next_retry_monotonic": self._next_retry_monotonic,
                    "retry_delay_seconds": self._retry_delay_seconds,
                    "committed_segment_seq": self._committed_sequence,
                    "failure_count": self._failure_count,
                    "refused_count": self._refused_count, "incomplete": self._incomplete,
                    "last_error": self._last_error,
                    "next_flush_monotonic": self._segments[0].flush_due_monotonic if self._segments else None}
