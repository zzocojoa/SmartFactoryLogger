from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import gc
import logging
import platform
import sys
import threading
import time
import tracemalloc
from typing import Any, Callable, Deque, Dict, Iterable, Mapping, Optional

import psutil


MemoryCollectorResult = Dict[str, Any]
MemoryCollector = Callable[[], MemoryCollectorResult]

_IGNORED_TYPES = (type, type(sys))
_SEVERITY_RANK = {"ok": 0, "warn": 1, "critical": 2}
DEFAULT_MEMORY_BUDGETS: dict[str, dict[str, float]] = {
    "process.rss_bytes": {
        "warn_growth_per_min": 32 * 1024 * 1024,
    },
    "process.uss_bytes": {
        "warn_growth_per_min": 32 * 1024 * 1024,
    },
    "process.private_bytes": {
        "warn_growth_per_min": 32 * 1024 * 1024,
    },
    "facility.plc_history": {
        "warn_bytes": 150 * 1024 * 1024,
        "critical_bytes": 300 * 1024 * 1024,
        "warn_growth_per_min": 32 * 1024 * 1024,
    },
    "facility.csv_logger": {
        "warn_items_ratio": 0.70,
        "critical_items_ratio": 0.90,
        "warn_growth_per_min": 16 * 1024 * 1024,
    },
    "spot.live_cache": {
        "warn_bytes": 10 * 1024 * 1024,
        "critical_bytes": 50 * 1024 * 1024,
    },
}
_LEAK_SUSPECT_MIN_POINTS = 4
_LEAK_SUSPECT_MIN_MONOTONIC_RATIO = 0.75
_LEAK_SUSPECT_MIN_BASELINE_RATIO = 1.20
_MEMORY_EXPORT_SCHEMA_VERSION = "memory-export-v2"
_REDACTED_VALUE = "[REDACTED]"
_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "authorization",
    "api_key",
    "private_key",
)
_SENSITIVE_NORMALIZED_KEY_FRAGMENTS = tuple(
    fragment.replace("_", "").replace("-", "") for fragment in _SENSITIVE_KEY_FRAGMENTS
) + ("liveimageurl",)


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


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _optional_delta(after: Any, before: Any) -> int | None:
    if after is None or before is None:
        return None
    try:
        return int(after) - int(before)
    except Exception:
        return None


def _is_sensitive_key(key: Any) -> bool:
    lowered = str(key).lower()
    normalized = lowered.replace("_", "").replace("-", "")
    return any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS) or any(
        fragment in normalized for fragment in _SENSITIVE_NORMALIZED_KEY_FRAGMENTS
    )


def _redact_sensitive(value: Any) -> tuple[Any, int]:
    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        redacted_count = 0
        for key, item in value.items():
            if _is_sensitive_key(key):
                redacted[key] = _REDACTED_VALUE
                redacted_count += 1
                continue
            redacted_item, item_count = _redact_sensitive(item)
            redacted[key] = redacted_item
            redacted_count += item_count
        return redacted, redacted_count

    if isinstance(value, list):
        redacted_items = []
        redacted_count = 0
        for item in value:
            redacted_item, item_count = _redact_sensitive(item)
            redacted_items.append(redacted_item)
            redacted_count += item_count
        return redacted_items, redacted_count

    if isinstance(value, tuple):
        redacted_items = []
        redacted_count = 0
        for item in value:
            redacted_item, item_count = _redact_sensitive(item)
            redacted_items.append(redacted_item)
            redacted_count += item_count
        return tuple(redacted_items), redacted_count

    if isinstance(value, (set, frozenset)):
        redacted_items = []
        redacted_count = 0
        for item in value:
            redacted_item, item_count = _redact_sensitive(item)
            redacted_items.append(redacted_item)
            redacted_count += item_count
        return redacted_items, redacted_count

    return value, 0


def _redact_argv(argv: Iterable[str]) -> list[str]:
    redacted: list[str] = []
    redact_next = False
    for raw_arg in argv:
        arg = str(raw_arg)
        if redact_next:
            redacted.append(_REDACTED_VALUE)
            redact_next = False
            continue

        key_part = arg.split("=", 1)[0].split(":", 1)[0]
        if not _is_sensitive_key(key_part):
            redacted.append(arg)
            continue

        if "=" in arg:
            key, _value = arg.split("=", 1)
            redacted.append(f"{key}={_REDACTED_VALUE}")
        elif ":" in arg:
            key, _value = arg.split(":", 1)
            redacted.append(f"{key}:{_REDACTED_VALUE}")
        else:
            redacted.append(arg)
            redact_next = True
    return redacted


def _append_note(note: Any, extra: str) -> str:
    if note:
        return f"{note}; {extra}"
    return extra


def _promote_severity(current: str, candidate: str) -> str:
    if _SEVERITY_RANK.get(candidate, 0) > _SEVERITY_RANK.get(current, 0):
        return candidate
    return current


def _collector_error_note(exc: Exception) -> str:
    return f"collector failed ({type(exc).__name__})"


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
    return _apply_budget(
        {
            "name": str(raw.get("name") or name),
            "kind": str(raw.get("kind") or "unknown"),
            "exactness": str(raw.get("exactness") or "estimated"),
            "bytes": _coerce_int(raw.get("bytes")),
            "items": _coerce_items(raw.get("items")),
            "items_ratio": _coerce_optional_float(raw.get("items_ratio")),
            "items_capacity": _coerce_items(raw.get("items_capacity")),
            "note": raw.get("note"),
        }
    )


def _resolve_items_ratio(item: Mapping[str, Any]) -> float | None:
    ratio = _coerce_optional_float(item.get("items_ratio"))
    if ratio is not None:
        return ratio
    items = _coerce_optional_float(item.get("items"))
    capacity = _coerce_optional_float(item.get("items_capacity"))
    if items is None or capacity is None or capacity <= 0:
        return None
    return items / capacity


def _apply_budget(
    item: Dict[str, Any],
    previous: Mapping[str, Any] | None = None,
    *,
    growth_bytes_per_min: float | None = None,
) -> Dict[str, Any]:
    name = str(item.get("name") or "")
    budget = DEFAULT_MEMORY_BUDGETS.get(name)
    severity = "ok"
    reasons: list[str] = []

    if budget:
        bytes_value = _coerce_int(item.get("bytes"))
        critical_bytes = _coerce_optional_float(budget.get("critical_bytes"))
        warn_bytes = _coerce_optional_float(budget.get("warn_bytes"))
        if critical_bytes is not None and bytes_value >= critical_bytes:
            severity = _promote_severity(severity, "critical")
            reasons.append(f"bytes>={int(critical_bytes)}")
        elif warn_bytes is not None and bytes_value >= warn_bytes:
            severity = _promote_severity(severity, "warn")
            reasons.append(f"bytes>={int(warn_bytes)}")

        items_ratio = _resolve_items_ratio(item)
        critical_items_ratio = _coerce_optional_float(budget.get("critical_items_ratio"))
        warn_items_ratio = _coerce_optional_float(budget.get("warn_items_ratio"))
        if items_ratio is not None:
            if critical_items_ratio is not None and items_ratio >= critical_items_ratio:
                severity = _promote_severity(severity, "critical")
                reasons.append(f"items_ratio>={critical_items_ratio:.2f}")
            elif warn_items_ratio is not None and items_ratio >= warn_items_ratio:
                severity = _promote_severity(severity, "warn")
                reasons.append(f"items_ratio>={warn_items_ratio:.2f}")

        if growth_bytes_per_min is None and previous is not None:
            growth_bytes_per_min = _coerce_optional_float(item.get("growth_bytes_per_min"))
        warn_growth_per_min = _coerce_optional_float(budget.get("warn_growth_per_min"))
        if (
            growth_bytes_per_min is not None
            and warn_growth_per_min is not None
            and growth_bytes_per_min >= warn_growth_per_min
        ):
            severity = _promote_severity(severity, "warn")
            reasons.append(f"growth_bytes_per_min>={int(warn_growth_per_min)}")

    item["severity"] = severity
    item["severity_reasons"] = reasons
    item["budget"] = dict(budget) if budget else None
    return item


def _collector_severity_rank(item: Mapping[str, Any]) -> int:
    return _SEVERITY_RANK.get(str(item.get("severity") or "ok"), 0)


def _build_growth_item(
    name: str,
    source_item: Mapping[str, Any],
    current_bytes: int,
    previous_bytes: int,
    total_current_bytes: int,
    *,
    growth_bytes_per_min: float | None,
) -> Dict[str, Any]:
    item = {
        "name": name,
        "kind": str(source_item.get("kind") or "unknown"),
        "exactness": str(source_item.get("exactness") or "estimated"),
        "bytes": current_bytes,
        "delta_bytes": current_bytes - previous_bytes,
        "share_ratio": (current_bytes / total_current_bytes) if total_current_bytes else 0.0,
        "items": source_item.get("items"),
        "items_ratio": source_item.get("items_ratio"),
        "items_capacity": source_item.get("items_capacity"),
        "growth_bytes_per_min": growth_bytes_per_min,
        "note": source_item.get("note"),
        "latency_ms": source_item.get("latency_ms"),
        "status": source_item.get("status"),
        "last_ok_at": source_item.get("last_ok_at"),
        "last_error_at": source_item.get("last_error_at"),
        "error_count": source_item.get("error_count"),
        "stale": source_item.get("stale"),
        "source": source_item.get("source"),
    }
    return _apply_budget(item, growth_bytes_per_min=growth_bytes_per_min)


def _build_growth_payload(
    current_collectors: Iterable[Mapping[str, Any]],
    previous_collectors: Iterable[Mapping[str, Any]],
    *,
    current_captured_at: float | None = None,
    previous_captured_at: float | None = None,
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
        elapsed_sec = (
            max(0.001, current_captured_at - previous_captured_at)
            if current_captured_at is not None and previous_captured_at is not None
            else None
        )
        delta_bytes = current_bytes - previous_bytes
        growth_bytes_per_min = (
            (delta_bytes / elapsed_sec) * 60.0 if elapsed_sec is not None and delta_bytes > 0 else None
        )
        payload.append(
            _build_growth_item(
                name,
                source_item,
                current_bytes,
                previous_bytes,
                total_current_bytes,
                growth_bytes_per_min=growth_bytes_per_min,
            )
        )

    return sorted(
        payload,
        key=lambda item: (
            _collector_severity_rank(item),
            int(item.get("delta_bytes") or 0),
            int(item.get("bytes") or 0),
        ),
        reverse=True,
    )


def _calc_slope_bytes_per_min(points: list[tuple[float, int]]) -> float:
    if len(points) < _LEAK_SUSPECT_MIN_POINTS:
        return 0.0
    ordered_points = sorted(points, key=lambda point: point[0])
    first_ts = ordered_points[0][0]
    xs = [(timestamp - first_ts) / 60.0 for timestamp, _ in ordered_points]
    ys = [float(value) for _, value in ordered_points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator <= 0.0:
        return 0.0
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    return numerator / denominator


def _calc_monotonic_ratio(points: list[tuple[float, int]]) -> float:
    if len(points) < 2:
        return 0.0
    ordered_values = [value for _, value in sorted(points, key=lambda point: point[0])]
    comparisons = len(ordered_values) - 1
    increases = sum(1 for previous, current in zip(ordered_values, ordered_values[1:]) if current > previous)
    return increases / comparisons if comparisons else 0.0


def _build_leak_suspect(
    *,
    name: str,
    source: str,
    points: list[tuple[float, int]],
    budget: Mapping[str, Any] | None,
) -> Dict[str, Any] | None:
    if len(points) < _LEAK_SUSPECT_MIN_POINTS or not budget:
        return None
    ordered_points = sorted(points, key=lambda point: point[0])
    baseline_bytes = max(0, int(ordered_points[0][1]))
    latest_bytes = max(0, int(ordered_points[-1][1]))
    if baseline_bytes <= 0:
        return None
    warn_growth_per_min = _coerce_optional_float(budget.get("warn_growth_per_min"))
    if warn_growth_per_min is None or warn_growth_per_min <= 0.0:
        return None
    slope = _calc_slope_bytes_per_min(ordered_points)
    monotonic_ratio = _calc_monotonic_ratio(ordered_points)
    increase_ratio = latest_bytes / baseline_bytes
    if (
        slope < warn_growth_per_min
        or monotonic_ratio < _LEAK_SUSPECT_MIN_MONOTONIC_RATIO
        or increase_ratio < _LEAK_SUSPECT_MIN_BASELINE_RATIO
    ):
        return None
    return {
        "name": name,
        "source": source,
        "classification": "leak_suspect",
        "slope_bytes_per_min": slope,
        "monotonic_ratio": monotonic_ratio,
        "baseline_bytes": baseline_bytes,
        "latest_bytes": latest_bytes,
        "increase_ratio": increase_ratio,
        "sample_count": len(ordered_points),
        "budget": dict(budget),
    }


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
        self._collector_runtime_state: dict[str, Dict[str, Any]] = {}
        self._collector_latency_warn_ms = 250.0
        self._collector_stale_after_sec = 60.0
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
        self._latest_leak_suspects: list[Dict[str, Any]] = []
        self._last_gc_snapshot: dict[str, Any] | None = None
        self._latest_tracemalloc_diff: list[Dict[str, Any]] = []
        self._latest_capture_latency: Dict[str, Any] = {}
        self._profiler_enabled = False
        self._profiler_collector_interval_sec = max(self._sample_interval_sec * 3.0, self._profiler_interval_sec)
        self._profiler_max_runtime_sec = 600.0
        self._profiler_started_at: Optional[str] = None
        self._profiler_started_at_ts: Optional[float] = None
        self._profiler_last_snapshot: Optional[tracemalloc.Snapshot] = None
        self._profiler_last_snapshot_at: Optional[float] = None
        self._profiler_last_diff_at: Optional[float] = None
        self._profiler_last_stop_reason: Optional[str] = None
        self._profiler_last_stop_at: Optional[str] = None
        self._profiler_last_stop_expected = False

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

    def stop(self) -> bool:
        if not self._running:
            return self._thread is None or not self._thread.is_alive()
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.stop_profiler()
        return self._thread is None or not self._thread.is_alive()

    def start_profiler(self) -> Dict[str, Any]:
        self._expire_profiler_if_needed()
        with self._state_lock:
            now = time.time()
            if self._profiler_enabled:
                state = self._build_profiler_state_locked(now)
                state["already_running"] = True
                return state
            if not tracemalloc.is_tracing():
                tracemalloc.start(25)
            self._profiler_enabled = True
            self._profiler_started_at = _utc_iso(now)
            self._profiler_started_at_ts = now
            self._profiler_last_snapshot = None
            self._profiler_last_snapshot_at = None
            self._profiler_last_diff_at = None
            self._profiler_last_stop_reason = None
            self._profiler_last_stop_at = None
            self._profiler_last_stop_expected = False
            self._latest_tracemalloc_diff = []
            self._latest_summary_state = self._build_summary_state_locked()
            self._latest_details_state = self._build_details_state_locked()
            state = self._build_profiler_state_locked(now)
        state["already_running"] = False
        return state

    def stop_profiler(self) -> Dict[str, Any]:
        return self._stop_profiler("manual", False)

    def _stop_profiler(self, stop_reason: str, expected_stop: bool) -> Dict[str, Any]:
        with self._state_lock:
            stopped_at = time.time()
            if not self._profiler_enabled and not tracemalloc.is_tracing():
                return self._build_profiler_state_locked(stopped_at)
            self._profiler_enabled = False
            self._profiler_started_at = None
            self._profiler_started_at_ts = None
            self._profiler_last_snapshot = None
            self._profiler_last_snapshot_at = None
            self._profiler_last_diff_at = None
            self._profiler_last_stop_reason = stop_reason
            self._profiler_last_stop_at = _utc_iso(stopped_at)
            self._profiler_last_stop_expected = expected_stop
            self._latest_tracemalloc_diff = []
            if tracemalloc.is_tracing():
                tracemalloc.stop()
            self._latest_summary_state = self._build_summary_state_locked()
            self._latest_details_state = self._build_details_state_locked()
        return self.get_profiler_state()

    def get_profiler_state(self) -> Dict[str, Any]:
        with self._state_lock:
            return self._build_profiler_state_locked(time.time())

    def capture_snapshot(self) -> Dict[str, Any]:
        started_perf = time.perf_counter()
        steps: list[Dict[str, Any]] = []

        step_started_perf = time.perf_counter()
        self._expire_profiler_if_needed()
        steps.append(self._build_latency_step("expire_profiler", step_started_perf, time.perf_counter()))

        step_started_perf = time.perf_counter()
        sample = self._build_process_sample()
        steps.append(self._build_latency_step("build_process_sample", step_started_perf, time.perf_counter()))

        step_started_perf = time.perf_counter()
        collectors = self._run_collectors(force=True)
        steps.append(self._build_latency_step("run_collectors", step_started_perf, time.perf_counter()))

        step_started_perf = time.perf_counter()
        self._apply_snapshot(sample, collectors)
        steps.append(self._build_latency_step("apply_snapshot", step_started_perf, time.perf_counter()))

        step_started_perf = time.perf_counter()
        self._capture_profiler_diff(force=True)
        steps.append(self._build_latency_step("capture_profiler_diff", step_started_perf, time.perf_counter()))

        step_started_perf = time.perf_counter()
        state = self.get_state()
        steps.append(self._build_latency_step("build_state", step_started_perf, time.perf_counter()))

        latency = {
            "captured_at": sample.get("captured_at_iso"),
            "total_ms": round((time.perf_counter() - started_perf) * 1000.0, 3),
            "steps": steps,
        }
        with self._state_lock:
            self._latest_capture_latency = latency
            self._latest_details_state = self._build_details_state_locked()
        state["capture_latency"] = latency
        return state

    def capture_gc_snapshot(self) -> Dict[str, Any]:
        started_perf = time.perf_counter()
        before = self._build_process_sample()
        collected = {
            "gen0": int(gc.collect(0)),
            "gen1": int(gc.collect(1)),
            "gen2": int(gc.collect(2)),
        }
        collected["total"] = collected["gen0"] + collected["gen1"] + collected["gen2"]
        after = self._build_process_sample()
        latency_ms = round((time.perf_counter() - started_perf) * 1000.0, 3)
        captured_at = _coerce_optional_float(after.get("captured_at")) or time.time()
        snapshot = {
            "captured_at": after.get("captured_at_iso") or _utc_iso(captured_at),
            "latency_ms": latency_ms,
            "collected": collected,
            "before": dict(before),
            "after": dict(after),
            "delta": {
                "rss_bytes": _optional_delta(after.get("rss_bytes"), before.get("rss_bytes")),
                "uss_bytes": _optional_delta(after.get("uss_bytes"), before.get("uss_bytes")),
                "private_bytes": _optional_delta(after.get("private_bytes"), before.get("private_bytes")),
            },
        }
        with self._state_lock:
            self._last_gc_snapshot = snapshot
            self._latest_details_state = self._build_details_state_locked()
        return snapshot

    def get_summary_state(self) -> Dict[str, Any]:
        with self._state_lock:
            return dict(self._latest_summary_state)

    def get_details_state(self) -> Dict[str, Any]:
        with self._state_lock:
            return dict(self._latest_details_state)

    def get_budget_results(self) -> Dict[str, Any]:
        with self._state_lock:
            items = list(self._latest_top_consumers) + list(self._latest_backend_growth)

        results: dict[str, Any] = {}
        for item in items:
            name = str(item.get("name") or "")
            if not name or name in results:
                continue
            budget = item.get("budget")
            results[name] = {
                "severity": item.get("severity"),
                "severity_reasons": list(item.get("severity_reasons") or []),
                "budget": dict(budget) if isinstance(budget, Mapping) else budget,
                "bytes": item.get("bytes"),
                "items": item.get("items"),
                "items_capacity": item.get("items_capacity"),
                "items_ratio": item.get("items_ratio"),
                "delta_bytes": item.get("delta_bytes"),
                "growth_bytes_per_min": item.get("growth_bytes_per_min"),
                "source": item.get("source"),
                "status": item.get("status"),
            }
        return results

    def get_leak_suspects(self) -> list[Dict[str, Any]]:
        with self._state_lock:
            return [dict(item) for item in self._latest_leak_suspects]

    def get_collector_runtime_state(self) -> Dict[str, Any]:
        with self._state_lock:
            return {name: dict(state) for name, state in self._collector_runtime_state.items()}

    def get_last_gc_snapshot(self) -> Dict[str, Any] | None:
        with self._state_lock:
            return dict(self._last_gc_snapshot) if self._last_gc_snapshot else None

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
        frontend_state = dict(frontend_snapshot or {}) if isinstance(frontend_snapshot, Mapping) else {}
        payload = {
            "schema_version": _MEMORY_EXPORT_SCHEMA_VERSION,
            "generated_at": _utc_iso(time.time()),
            "runtime": self._build_export_runtime_payload(),
            "summary_state": summary_state,
            "details_state": details_state,
            "frontend": frontend_state,
            "analysis": self._build_export_analysis_payload(summary_state, details_state),
            **summary_state,
            **details_state,
        }
        redacted_payload, redacted_count = _redact_sensitive(payload)
        if not isinstance(redacted_payload, dict):
            redacted_payload = {}
        redacted_payload["redaction"] = {
            "applied": True,
            "redacted_value": _REDACTED_VALUE,
            "redacted_fields": redacted_count,
            "key_fragments": list(_SENSITIVE_KEY_FRAGMENTS),
            "normalized_key_fragments": list(_SENSITIVE_NORMALIZED_KEY_FRAGMENTS),
        }
        return redacted_payload

    def _build_export_runtime_payload(self) -> Dict[str, Any]:
        return {
            "pid": int(self._process.pid),
            "python_version": sys.version,
            "platform": platform.platform(),
            "argv": _redact_argv(sys.argv),
        }

    def _build_export_analysis_payload(
        self,
        summary_state: Mapping[str, Any],
        details_state: Mapping[str, Any],
    ) -> Dict[str, Any]:
        return {
            "budget_results": self.get_budget_results(),
            "leak_suspects": self.get_leak_suspects(),
            "collector_runtime_state": self.get_collector_runtime_state(),
            "last_gc_snapshot": self.get_last_gc_snapshot(),
            "profiler": dict(summary_state.get("profiler") or {}),
            "latest_tracemalloc_diff": list(details_state.get("latest_tracemalloc_diff") or []),
        }

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._expire_profiler_if_needed()
                # Keep the periodic sampler lightweight. On Windows,
                # memory_full_info() and open_files() may scan process handles
                # for several seconds. Explicit diagnostic snapshots still
                # include those expensive process details.
                sample = self._build_process_sample(include_expensive_details=False)
                collectors = self._run_collectors(force=False)
                self._apply_snapshot(sample, collectors)
                self._capture_profiler_diff(force=False)
            except Exception as exc:
                self._logger.error(
                    "Memory sampler failed",
                    extra={"memory_error": str(exc)},
                )
            if self._stop_event.wait(self._sample_interval_sec):
                break

    def _apply_snapshot(self, sample: Mapping[str, Any], collectors: list[Dict[str, Any]]) -> None:
        top_consumers = sorted(collectors, key=lambda item: int(item.get("bytes") or 0), reverse=True)
        captured_at = float(sample.get("captured_at") or time.time())
        collector_snapshot = {
            "captured_at": captured_at,
            "items": [dict(item) for item in collectors],
        }

        with self._state_lock:
            previous_snapshot = self._collector_history[-1] if self._collector_history else None
            previous_collectors = previous_snapshot["items"] if previous_snapshot else []
            previous_captured_at = (
                _coerce_optional_float(previous_snapshot.get("captured_at")) if previous_snapshot else None
            )
            backend_growth = _build_growth_payload(
                collectors,
                previous_collectors,
                current_captured_at=captured_at,
                previous_captured_at=previous_captured_at,
            )
            self._history.append(dict(sample))
            self._collector_history.append(collector_snapshot)
            self._latest_summary = dict(sample)
            self._latest_top_consumers = top_consumers[:20]
            self._latest_backend_growth = backend_growth[:20]
            self._latest_leak_suspects = self._build_leak_suspects_locked()
            self._latest_summary_state = self._build_summary_state_locked()
            self._latest_details_state = self._build_details_state_locked()

    def _build_process_sample(self, *, include_expensive_details: bool = True) -> Dict[str, Any]:
        now = time.time()
        memory_info = self._process.memory_info()
        rss_bytes = int(memory_info.rss)
        vms_bytes = int(memory_info.vms)
        uss_bytes: Optional[int] = None
        private_bytes: Optional[int] = (
            int(memory_info.private) if hasattr(memory_info, "private") else None
        )
        if include_expensive_details:
            try:
                full_info = self._process.memory_full_info()
                if hasattr(full_info, "uss"):
                    uss_bytes = int(full_info.uss)
                if hasattr(full_info, "private"):
                    private_bytes = int(full_info.private)
            except Exception:
                uss_bytes = None

        open_files_count: Optional[int] = None
        handle_count: Optional[int] = None
        if include_expensive_details:
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
            return [self._refresh_collector_runtime_fields(item, now) for item in collector_cache]

        with self._collector_lock:
            collectors = list(self._collectors.items())
        results: list[Dict[str, Any]] = []
        for name, collector in collectors:
            if not force:
                cached_item = self._build_cached_collector_reuse(name, now)
                if cached_item is not None:
                    results.append(cached_item)
                    continue

            started_perf = time.perf_counter()
            try:
                raw = collector()
            except Exception as exc:
                latency_ms = round((time.perf_counter() - started_perf) * 1000.0, 3)
                results.append(self._record_collector_error(name, exc, latency_ms, now))
                continue
            latency_ms = round((time.perf_counter() - started_perf) * 1000.0, 3)
            normalized = _normalize_collector_result(name, raw)
            results.append(self._record_collector_success(name, normalized, latency_ms, now))
        with self._state_lock:
            self._collector_cache = [dict(item) for item in results]
            self._collector_cache_at = now
        return results

    def _record_collector_success(
        self,
        name: str,
        item: Dict[str, Any],
        latency_ms: float,
        now: float,
    ) -> Dict[str, Any]:
        status = "slow" if latency_ms >= self._collector_latency_warn_ms else "ok"
        with self._state_lock:
            state = dict(self._collector_runtime_state.get(name, {}))
            state["last_ok_at"] = now
            state["last_latency_ms"] = latency_ms
            state["last_status"] = status
            state["last_value_at"] = now
            item.update(self._build_collector_contract_fields(state, latency_ms, status, now, stale=False))
            state["last_value"] = dict(item)
            self._collector_runtime_state[name] = state
        return item

    def _record_collector_error(
        self,
        name: str,
        exc: Exception,
        latency_ms: float,
        now: float,
    ) -> Dict[str, Any]:
        with self._state_lock:
            state = dict(self._collector_runtime_state.get(name, {}))
            state["last_error_at"] = now
            state["error_count"] = int(state.get("error_count") or 0) + 1
            state["last_latency_ms"] = latency_ms
            state["last_status"] = "error"
            stale = self._is_collector_state_stale(state, now)
            self._collector_runtime_state[name] = state
            return _apply_budget({
                "name": name,
                "kind": "error",
                "exactness": "estimated",
                "bytes": 0,
                "items": None,
                "note": _collector_error_note(exc),
                **self._build_collector_contract_fields(state, latency_ms, "error", now, stale=stale),
            })

    def _build_cached_collector_reuse(self, name: str, now: float) -> Dict[str, Any] | None:
        with self._state_lock:
            state = dict(self._collector_runtime_state.get(name, {}))
            if state.get("last_status") != "slow":
                return None
            last_value_at = _coerce_optional_float(state.get("last_value_at"))
            last_value = state.get("last_value")
            if last_value_at is None or not isinstance(last_value, Mapping):
                return None
            if (now - last_value_at) >= self._collector_stale_after_sec:
                return None
            item = dict(last_value)
            latency_ms = _coerce_optional_float(state.get("last_latency_ms"))
            stale = self._is_collector_state_stale(state, now)
            item.update(self._build_collector_contract_fields(state, latency_ms, "stale", now, stale=stale))
            item["note"] = _append_note(item.get("note"), "cached previous collector result")
            return item

    def _refresh_collector_runtime_fields(self, item: Mapping[str, Any], now: float) -> Dict[str, Any]:
        name = str(item.get("name") or "")
        refreshed = dict(item)
        with self._state_lock:
            state = dict(self._collector_runtime_state.get(name, {}))
        if not state:
            return refreshed
        stale = self._is_collector_state_stale(state, now)
        current_status = str(refreshed.get("status") or state.get("last_status") or "ok")
        status = "stale" if stale and current_status in {"ok", "slow"} else current_status
        latency_ms = _coerce_optional_float(refreshed.get("latency_ms"))
        if latency_ms is None:
            latency_ms = _coerce_optional_float(state.get("last_latency_ms"))
        refreshed.update(self._build_collector_contract_fields(state, latency_ms, status, now, stale=stale))
        return refreshed

    def _build_collector_contract_fields(
        self,
        state: Mapping[str, Any],
        latency_ms: float | None,
        status: str,
        now: float,
        *,
        stale: bool | None = None,
    ) -> Dict[str, Any]:
        stale_value = self._is_collector_state_stale(state, now) if stale is None else stale
        last_ok_at = _coerce_optional_float(state.get("last_ok_at"))
        last_error_at = _coerce_optional_float(state.get("last_error_at"))
        return {
            "latency_ms": round(latency_ms, 3) if latency_ms is not None else None,
            "status": status,
            "last_ok_at": _utc_iso(last_ok_at) if last_ok_at is not None else None,
            "last_error_at": _utc_iso(last_error_at) if last_error_at is not None else None,
            "error_count": int(state.get("error_count") or 0),
            "stale": bool(stale_value),
            "source": "backend",
        }

    def _is_collector_state_stale(self, state: Mapping[str, Any], now: float) -> bool:
        last_ok_at = _coerce_optional_float(state.get("last_ok_at"))
        if last_ok_at is None:
            return False
        return (now - last_ok_at) >= self._collector_stale_after_sec

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

    def _build_latency_step(self, name: str, started_perf: float, ended_perf: float) -> Dict[str, Any]:
        return {
            "name": name,
            "latency_ms": round((ended_perf - started_perf) * 1000.0, 3),
        }

    def _build_profiler_state_locked(self, now: Optional[float] = None) -> Dict[str, Any]:
        current_time = time.time() if now is None else now
        remaining_ttl_sec: Optional[float] = None
        expires_at: Optional[str] = None
        if self._profiler_enabled and self._profiler_started_at_ts is not None:
            expires_at_ts = self._profiler_started_at_ts + self._profiler_max_runtime_sec
            remaining_ttl_sec = max(0.0, round(expires_at_ts - current_time, 3))
            expires_at = _utc_iso(expires_at_ts)
        return {
            "enabled": self._profiler_enabled,
            "started_at": self._profiler_started_at,
            "last_snapshot_at": _utc_iso(self._profiler_last_snapshot_at)
            if self._profiler_last_snapshot_at
            else None,
            "last_diff_at": _utc_iso(self._profiler_last_diff_at) if self._profiler_last_diff_at else None,
            "expires_at": expires_at,
            "remaining_ttl_sec": remaining_ttl_sec,
            "max_runtime_sec": round(self._profiler_max_runtime_sec, 3),
            "last_stop_reason": self._profiler_last_stop_reason,
            "last_stop_at": self._profiler_last_stop_at,
            "last_stop_expected": self._profiler_last_stop_expected,
        }

    def _expire_profiler_if_needed(self) -> None:
        with self._state_lock:
            if not self._profiler_enabled or self._profiler_started_at_ts is None:
                return
            runtime_sec = time.time() - self._profiler_started_at_ts
        if runtime_sec < self._profiler_max_runtime_sec:
            return
        self._logger.info(
            "Memory profiler auto-stopped",
            extra={
                "memory_profiler_runtime_sec": round(runtime_sec, 3),
                "memory_profiler_max_runtime_sec": self._profiler_max_runtime_sec,
                "memory_profiler_stop_reason": "ttl_expired",
                "memory_profiler_stop_expected": True,
            },
        )
        self._stop_profiler("ttl_expired", True)

    def _build_sampling_state_locked(self) -> Dict[str, Any]:
        return {
            "sample_interval_sec": self._sample_interval_sec,
            "history_limit": self._history_limit,
            "collector_history_limit": self._collector_history_limit,
            "detail_refresh_interval_sec": self._profiler_collector_interval_sec,
        }

    def _build_leak_suspects_locked(self) -> list[Dict[str, Any]]:
        suspects: list[Dict[str, Any]] = []
        for field in ("rss_bytes", "uss_bytes", "private_bytes"):
            points = [
                (float(sample.get("captured_at") or 0.0), _coerce_int(sample.get(field)))
                for sample in self._history
                if sample.get(field) is not None
            ]
            suspect = _build_leak_suspect(
                name=f"process.{field}",
                source="process",
                points=points,
                budget=DEFAULT_MEMORY_BUDGETS.get(f"process.{field}"),
            )
            if suspect is not None:
                suspects.append(suspect)

        collector_points: dict[str, list[tuple[float, int]]] = {}
        for snapshot in self._collector_history:
            captured_at = _coerce_optional_float(snapshot.get("captured_at"))
            if captured_at is None:
                continue
            for item in snapshot.get("items") or []:
                if not isinstance(item, Mapping):
                    continue
                name = str(item.get("name") or "")
                if not name:
                    continue
                collector_points.setdefault(name, []).append((captured_at, _coerce_int(item.get("bytes"))))

        for name, points in collector_points.items():
            suspect = _build_leak_suspect(
                name=name,
                source="collector",
                points=points,
                budget=DEFAULT_MEMORY_BUDGETS.get(name),
            )
            if suspect is not None:
                suspects.append(suspect)

        return sorted(
            suspects,
            key=lambda item: (float(item.get("slope_bytes_per_min") or 0.0), int(item.get("latest_bytes") or 0)),
            reverse=True,
        )

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
            "leak_suspects": list(self._latest_leak_suspects),
            "latest_gc_snapshot": dict(self._last_gc_snapshot) if self._last_gc_snapshot else None,
            "latest_tracemalloc_diff": list(self._latest_tracemalloc_diff),
            "capture_latency": dict(self._latest_capture_latency),
        }


memory_service = MemoryService(
    sample_interval_sec=5.0,
    profiler_interval_sec=10.0,
    history_limit=360,
    diff_limit=10,
    collector_history_limit=12,
)
