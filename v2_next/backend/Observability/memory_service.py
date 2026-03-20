from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import gc
import logging
import sys
import threading
import time
import tracemalloc
from typing import Any, Callable, Deque, Dict, Iterable, Mapping, Optional

import psutil


MemoryCollectorResult = Dict[str, Any]
MemoryCollector = Callable[[], MemoryCollectorResult]

_IGNORED_TYPES = (type, type(sys))


def _utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def _coerce_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return 0


def _coerce_items(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def estimate_size_bytes(value: Any) -> int:
    seen: set[int] = set()
    return _estimate_size_bytes(value, seen)


def _estimate_size_bytes(value: Any, seen: set[int]) -> int:
    obj_id = id(value)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    try:
        size = sys.getsizeof(value)
    except Exception:
        size = 0

    if value is None or isinstance(value, (bool, int, float, complex, bytes, bytearray, str)):
        return size

    if isinstance(value, Mapping):
        total = size
        for key, item in value.items():
            total += _estimate_size_bytes(key, seen)
            total += _estimate_size_bytes(item, seen)
        return total

    if isinstance(value, (list, tuple, set, frozenset, deque)):
        total = size
        for item in value:
            total += _estimate_size_bytes(item, seen)
        return total

    if isinstance(value, _IGNORED_TYPES):
        return size

    if hasattr(value, "__dict__"):
        return size + _estimate_size_bytes(vars(value), seen)

    if hasattr(value, "__slots__"):
        total = size
        for slot in value.__slots__:
            if hasattr(value, slot):
                total += _estimate_size_bytes(getattr(value, slot), seen)
        return total

    try:
        referents = gc.get_referents(value)
    except Exception:
        return size

    total = size
    for item in referents:
        if isinstance(item, _IGNORED_TYPES):
            continue
        total += _estimate_size_bytes(item, seen)
    return total


def _normalize_collector_result(name: str, raw: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "name": str(raw.get("name") or name),
        "kind": str(raw.get("kind") or "unknown"),
        "exactness": str(raw.get("exactness") or "estimated"),
        "bytes": _coerce_int(raw.get("bytes")),
        "items": _coerce_items(raw.get("items")),
        "note": raw.get("note"),
    }


def _build_growth_payload(
    current_collectors: Iterable[Mapping[str, Any]],
    previous_collectors: Iterable[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    current_map = {str(item.get("name") or ""): dict(item) for item in current_collectors}
    previous_map = {str(item.get("name") or ""): dict(item) for item in previous_collectors}
    total_current_bytes = sum(_coerce_int(item.get("bytes")) for item in current_map.values())
    names = [name for name in current_map.keys() | previous_map.keys() if name]

    payload: list[Dict[str, Any]] = []
    for name in names:
        current_item = current_map.get(name)
        previous_item = previous_map.get(name)
        current_bytes = _coerce_int(current_item.get("bytes")) if current_item else 0
        previous_bytes = _coerce_int(previous_item.get("bytes")) if previous_item else 0
        source_item = current_item or previous_item or {}
        payload.append(
            {
                "name": name,
                "kind": str(source_item.get("kind") or "unknown"),
                "exactness": str(source_item.get("exactness") or "estimated"),
                "bytes": current_bytes,
                "delta_bytes": current_bytes - previous_bytes,
                "share_ratio": (current_bytes / total_current_bytes) if total_current_bytes else 0.0,
                "items": source_item.get("items"),
                "note": source_item.get("note"),
            }
        )

    return sorted(
        payload,
        key=lambda item: (int(item.get("delta_bytes") or 0), int(item.get("bytes") or 0)),
        reverse=True,
    )


class MemoryService:
    def __init__(
        self,
        sample_interval_sec: float,
        profiler_interval_sec: float,
        history_limit: int,
        diff_limit: int,
        collector_history_limit: int,
    ) -> None:
        self._sample_interval_sec = max(1.0, float(sample_interval_sec))
        self._profiler_interval_sec = max(1.0, float(profiler_interval_sec))
        self._history_limit = max(10, int(history_limit))
        self._collector_history_limit = max(2, int(collector_history_limit))
        self._history: Deque[Dict[str, Any]] = deque(maxlen=self._history_limit)
        self._collector_history: Deque[Dict[str, Any]] = deque(maxlen=self._collector_history_limit)
        self._collector_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._collectors: dict[str, MemoryCollector] = {}
        self._collector_cache: list[Dict[str, Any]] = []
        self._collector_cache_at: Optional[float] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._process = psutil.Process()
        self._logger = logging.getLogger("SmartFactoryLoggerV2")
        self._diff_limit = max(1, int(diff_limit))
        self._latest_top_consumers: list[Dict[str, Any]] = []
        self._latest_backend_growth: list[Dict[str, Any]] = []
        self._latest_summary: dict[str, Any] = {}
        self._latest_summary_state: dict[str, Any] = {}
        self._latest_details_state: dict[str, Any] = {}
        self._latest_tracemalloc_diff: list[Dict[str, Any]] = []
        self._profiler_enabled = False
        self._profiler_collector_interval_sec = max(self._sample_interval_sec * 3.0, self._profiler_interval_sec)
        self._profiler_max_runtime_sec = 600.0
        self._profiler_started_at: Optional[str] = None
        self._profiler_started_at_ts: Optional[float] = None
        self._profiler_last_snapshot: Optional[tracemalloc.Snapshot] = None
        self._profiler_last_snapshot_at: Optional[float] = None
        self._profiler_last_diff_at: Optional[float] = None

    def register_collector(self, name: str, collector: MemoryCollector) -> None:
        with self._collector_lock:
            self._collectors[name] = collector

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="MemorySampler", daemon=True)
        self._thread.start()
        self.capture_snapshot()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.stop_profiler()

    def start_profiler(self) -> Dict[str, Any]:
        with self._state_lock:
            now = time.time()
            if not tracemalloc.is_tracing():
                tracemalloc.start(25)
            self._profiler_enabled = True
            self._profiler_started_at = _utc_iso(now)
            self._profiler_started_at_ts = now
            self._profiler_last_snapshot = None
            self._profiler_last_snapshot_at = None
            self._profiler_last_diff_at = None
            self._latest_tracemalloc_diff = []
            self._latest_summary_state = self._build_summary_state_locked()
            self._latest_details_state = self._build_details_state_locked()
        return self.get_profiler_state()

    def stop_profiler(self) -> Dict[str, Any]:
        with self._state_lock:
            self._profiler_enabled = False
            self._profiler_started_at = None
            self._profiler_started_at_ts = None
            self._profiler_last_snapshot = None
            self._profiler_last_snapshot_at = None
            self._profiler_last_diff_at = None
            self._latest_tracemalloc_diff = []
            if tracemalloc.is_tracing():
                tracemalloc.stop()
            self._latest_summary_state = self._build_summary_state_locked()
            self._latest_details_state = self._build_details_state_locked()
        return self.get_profiler_state()

    def get_profiler_state(self) -> Dict[str, Any]:
        with self._state_lock:
            return {
                "enabled": self._profiler_enabled,
                "started_at": self._profiler_started_at,
                "last_snapshot_at": _utc_iso(self._profiler_last_snapshot_at)
                if self._profiler_last_snapshot_at
                else None,
                "last_diff_at": _utc_iso(self._profiler_last_diff_at) if self._profiler_last_diff_at else None,
            }

    def capture_snapshot(self) -> Dict[str, Any]:
        self._expire_profiler_if_needed()
        sample = self._build_process_sample()
        collectors = self._run_collectors(force=True)
        self._apply_snapshot(sample, collectors)
        self._capture_profiler_diff(force=True)
        return self.get_state()

    def get_summary_state(self) -> Dict[str, Any]:
        with self._state_lock:
            return dict(self._latest_summary_state)

    def get_details_state(self) -> Dict[str, Any]:
        with self._state_lock:
            return dict(self._latest_details_state)

    def get_state(self) -> Dict[str, Any]:
        summary_state = self.get_summary_state()
        details_state = self.get_details_state()
        return {
            **summary_state,
            **details_state,
        }

    def build_export_payload(self, frontend_snapshot: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        summary_state = self.get_summary_state()
        details_state = self.get_details_state()
        payload = {
            "summary_state": summary_state,
            "details_state": details_state,
            **summary_state,
            **details_state,
        }
        payload["generated_at"] = _utc_iso(time.time())
        payload["frontend"] = dict(frontend_snapshot or {})
        return payload

    def _loop(self) -> None:
        while not self._stop_event.wait(self._sample_interval_sec):
            try:
                self._expire_profiler_if_needed()
                sample = self._build_process_sample()
                collectors = self._run_collectors(force=False)
                self._apply_snapshot(sample, collectors)
                self._capture_profiler_diff(force=False)
            except Exception as exc:
                self._logger.error(
                    "Memory sampler failed",
                    extra={"memory_error": str(exc)},
                )

    def _apply_snapshot(self, sample: Mapping[str, Any], collectors: list[Dict[str, Any]]) -> None:
        top_consumers = sorted(collectors, key=lambda item: int(item.get("bytes") or 0), reverse=True)
        collector_snapshot = {
            "captured_at": float(sample.get("captured_at") or time.time()),
            "items": [dict(item) for item in collectors],
        }

        with self._state_lock:
            previous_collectors = self._collector_history[-1]["items"] if self._collector_history else []
            backend_growth = _build_growth_payload(collectors, previous_collectors)
            self._history.append(dict(sample))
            self._collector_history.append(collector_snapshot)
            self._latest_summary = dict(sample)
            self._latest_top_consumers = top_consumers[:20]
            self._latest_backend_growth = backend_growth[:20]
            self._latest_summary_state = self._build_summary_state_locked()
            self._latest_details_state = self._build_details_state_locked()

    def _build_process_sample(self) -> Dict[str, Any]:
        now = time.time()
        memory_info = self._process.memory_info()
        rss_bytes = int(memory_info.rss)
        vms_bytes = int(memory_info.vms)
        uss_bytes: Optional[int] = None
        private_bytes: Optional[int] = None
        try:
            full_info = self._process.memory_full_info()
            if hasattr(full_info, "uss"):
                uss_bytes = int(full_info.uss)
            if hasattr(full_info, "private"):
                private_bytes = int(full_info.private)
        except Exception:
            uss_bytes = None
            private_bytes = None

        open_files_count: Optional[int] = None
        handle_count: Optional[int] = None
        try:
            open_files_count = len(self._process.open_files())
        except Exception:
            open_files_count = None
        try:
            handle_count = int(self._process.num_handles())
        except Exception:
            handle_count = None

        gc_counts = gc.get_count()
        return {
            "captured_at": now,
            "captured_at_iso": _utc_iso(now),
            "rss_bytes": rss_bytes,
            "vms_bytes": vms_bytes,
            "uss_bytes": uss_bytes,
            "private_bytes": private_bytes,
            "thread_count": self._process.num_threads(),
            "open_files_count": open_files_count,
            "handle_count": handle_count,
            "gc_gen0": gc_counts[0],
            "gc_gen1": gc_counts[1],
            "gc_gen2": gc_counts[2],
        }

    def _run_collectors(self, force: bool) -> list[Dict[str, Any]]:
        with self._state_lock:
            profiler_enabled = self._profiler_enabled
            collector_cache = [dict(item) for item in self._collector_cache]
            collector_cache_at = self._collector_cache_at

        now = time.time()
        if (
            not force
            and profiler_enabled
            and collector_cache
            and collector_cache_at is not None
            and (now - collector_cache_at) < self._profiler_collector_interval_sec
        ):
            return collector_cache

        with self._collector_lock:
            collectors = list(self._collectors.items())
        results: list[Dict[str, Any]] = []
        for name, collector in collectors:
            try:
                raw = collector()
            except Exception as exc:
                results.append(
                    {
                        "name": name,
                        "kind": "error",
                        "exactness": "estimated",
                        "bytes": 0,
                        "items": None,
                        "note": str(exc),
                    }
                )
                continue
            results.append(_normalize_collector_result(name, raw))
        with self._state_lock:
            self._collector_cache = [dict(item) for item in results]
            self._collector_cache_at = now
        return results

    def _capture_profiler_diff(self, force: bool) -> None:
        with self._state_lock:
            enabled = self._profiler_enabled
            last_snapshot_at = self._profiler_last_snapshot_at
        if not enabled or not tracemalloc.is_tracing():
            return

        now = time.time()
        if not force and last_snapshot_at is not None and (now - last_snapshot_at) < self._profiler_interval_sec:
            return

        current = tracemalloc.take_snapshot()
        with self._state_lock:
            previous = self._profiler_last_snapshot
            self._profiler_last_snapshot = current
            self._profiler_last_snapshot_at = now
        if previous is None:
            return

        diffs = current.compare_to(previous, "lineno")
        payload: list[Dict[str, Any]] = []
        for stat in diffs[: self._diff_limit]:
            frame = stat.traceback[0] if stat.traceback else None
            payload.append(
                {
                    "trace": str(frame) if frame else "unknown",
                    "size_diff_bytes": int(stat.size_diff),
                    "size_bytes": int(stat.size),
                    "count_diff": int(stat.count_diff),
                    "count": int(stat.count),
                }
            )
        with self._state_lock:
            self._latest_tracemalloc_diff = payload
            self._profiler_last_diff_at = now
            self._latest_summary_state = self._build_summary_state_locked()
            self._latest_details_state = self._build_details_state_locked()

    def _build_profiler_state_locked(self) -> Dict[str, Any]:
        return {
            "enabled": self._profiler_enabled,
            "started_at": self._profiler_started_at,
            "last_snapshot_at": _utc_iso(self._profiler_last_snapshot_at)
            if self._profiler_last_snapshot_at
            else None,
            "last_diff_at": _utc_iso(self._profiler_last_diff_at) if self._profiler_last_diff_at else None,
        }

    def _expire_profiler_if_needed(self) -> None:
        with self._state_lock:
            if not self._profiler_enabled or self._profiler_started_at_ts is None:
                return
            runtime_sec = time.time() - self._profiler_started_at_ts
        if runtime_sec < self._profiler_max_runtime_sec:
            return
        self._logger.warning(
            "Memory profiler auto-stopped",
            extra={
                "memory_profiler_runtime_sec": round(runtime_sec, 3),
                "memory_profiler_max_runtime_sec": self._profiler_max_runtime_sec,
            },
        )
        self.stop_profiler()

    def _build_sampling_state_locked(self) -> Dict[str, Any]:
        return {
            "sample_interval_sec": self._sample_interval_sec,
            "history_limit": self._history_limit,
            "collector_history_limit": self._collector_history_limit,
            "detail_refresh_interval_sec": self._profiler_collector_interval_sec,
        }

    def _build_summary_state_locked(self) -> Dict[str, Any]:
        return {
            "summary": dict(self._latest_summary),
            "history": list(self._history),
            "profiler": self._build_profiler_state_locked(),
            "sampling": self._build_sampling_state_locked(),
        }

    def _build_details_state_locked(self) -> Dict[str, Any]:
        return {
            "backend_top_consumers": list(self._latest_top_consumers),
            "backend_growth": list(self._latest_backend_growth),
            "collector_history": list(self._collector_history),
            "latest_tracemalloc_diff": list(self._latest_tracemalloc_diff),
        }


memory_service = MemoryService(
    sample_interval_sec=5.0,
    profiler_interval_sec=10.0,
    history_limit=360,
    diff_limit=10,
    collector_history_limit=12,
)
