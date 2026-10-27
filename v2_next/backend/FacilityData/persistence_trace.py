"""Bounded persistence-result segments, owned by a data-path writer."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Mapping
from uuid import uuid4


@dataclass
class _TraceSegment:
    sequence: int
    header: bytes
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

    def append(self, record: Mapping[str, Any]) -> int | None:
        payload = self._encode(record)
        with self._lock:
            if not self._segments or self._segments[-1].sealed:
                sequence = self._next_sequence
                self._next_sequence += 1
                header = self._encode({"schema_version": 1, "producer_instance_id": self.producer_id,
                                       "writer_instance_id": self._instance_id, "segment_id": sequence})
                self._segments.append(_TraceSegment(sequence, header))
            segment = self._segments[-1]
            segment.records.append(payload)
            return segment.sequence

    @staticmethod
    def _encode(record: Mapping[str, Any]) -> bytes:
        return (json.dumps(dict(record), ensure_ascii=False, allow_nan=False,
                           sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

    @staticmethod
    def _matches(path: Path, segment: _TraceSegment) -> bool:
        with path.open("rb") as handle:
            for chunk in (segment.header, *segment.records):
                if handle.read(len(chunk)) != chunk:
                    return False
            return handle.read(1) == b""

    def _publish(self, segment: _TraceSegment) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        stem = f"{self._instance_id}-{segment.sequence:08d}"
        final = self.root / f"{stem}.trace.jsonl"
        pending = self.root / f".{stem}.pending"
        if final.exists():
            if not self._matches(final, segment):
                raise OSError("trace_final_content_conflict")
            return  # Publication succeeded before an earlier error was observed.
        if pending.exists():
            if not self._matches(pending, segment):
                raise OSError("trace_pending_content_uncertain")
        else:
            with pending.open("xb") as handle:
                handle.write(segment.header)
                for record in segment.records:
                    handle.write(record)
                handle.flush()
                os.fsync(handle.fileno())
        pending.replace(final)
        if not self._matches(final, segment):
            raise OSError("trace_published_content_mismatch")

    def flush(self, *, force: bool = False) -> bool:
        with self._writer_lock:
            with self._lock:
                if not self._segments:
                    return True
                segment = self._segments[0]
                segment.sealed = True
            try:
                self._publish(segment)
            except OSError:
                with self._lock:
                    self._failure_count += 1
                return False
            with self._lock:
                self._committed_sequence = segment.sequence
                self._segments.popleft()
                return True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"pending_records": sum(len(segment.records) for segment in self._segments),
                    "pending_bytes": sum(segment.size for segment in self._segments),
                    "pending_segments": len(self._segments),
                    "committed_segment_seq": self._committed_sequence,
                    "failure_count": self._failure_count}
