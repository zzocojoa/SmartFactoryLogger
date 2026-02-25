from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import math
import threading
import time
from typing import Any, Deque, Dict, List, Optional, Tuple


RequestSample = Tuple[float, float, int, str]


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def _p95(values: List[float]) -> Optional[float]:
    if not values:
        return None
    values_sorted = sorted(values)
    idx = int(math.ceil(0.95 * len(values_sorted))) - 1
    idx = max(0, min(idx, len(values_sorted) - 1))
    return float(values_sorted[idx])


class ObservabilityService:
    def __init__(
        self,
        window_sec: float = 60.0,
        max_requests: int = 6000,
        max_errors: int = 200,
    ) -> None:
        self.window_sec = max(10.0, float(window_sec))
        self._requests: Deque[RequestSample] = deque(maxlen=max_requests)
        self._errors: Deque[Dict[str, Any]] = deque(maxlen=max_errors)
        self._lock = threading.Lock()
        self._total_requests = 0
        self._total_latency_ms = 0.0
        self._error_count = 0
        self._last_request: Dict[str, Any] = {
            "latency_ms": None,
            "path": None,
            "status": None,
            "timestamp": None,
        }

    def record_request(self, path: str, status_code: int, latency_ms: float) -> None:
        now = time.time()
        sample: RequestSample = (now, float(latency_ms), int(status_code), str(path))
        with self._lock:
            self._total_requests += 1
            self._total_latency_ms += float(latency_ms)
            if status_code >= 400:
                self._error_count += 1
            self._last_request = {
                "latency_ms": int(latency_ms),
                "path": path,
                "status": status_code,
                "timestamp": now,
            }
            self._requests.append(sample)

    def record_error(
        self,
        source: str,
        message: str,
        *,
        detail: Optional[str] = None,
        path: Optional[str] = None,
        level: str = "error",
    ) -> None:
        now = time.time()
        entry = {
            "time": now,
            "time_iso": _iso(now),
            "source": source,
            "message": message,
            "detail": detail,
            "path": path,
            "level": level,
            "repeat": 1,
        }
        with self._lock:
            if self._errors:
                last = self._errors[-1]
                if (
                    last.get("source") == source
                    and last.get("message") == message
                    and now - float(last.get("time", 0)) <= 5.0
                ):
                    last["time"] = now
                    last["time_iso"] = _iso(now)
                    last["repeat"] = int(last.get("repeat", 1)) + 1
                    if detail:
                        last["detail"] = detail
                    if path:
                        last["path"] = path
                    return
            self._errors.append(entry)

    def clear_errors(self) -> None:
        with self._lock:
            self._errors.clear()

    def get_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            if limit <= 0:
                return []
            items = list(self._errors)[-limit:]
        items.reverse()
        return items

    def _window_metrics(self, now: float) -> Dict[str, Any]:
        window_start = now - self.window_sec
        with self._lock:
            samples = [sample for sample in self._requests if sample[0] >= window_start]

        request_count = len(samples)
        if request_count == 0:
            return {
                "window_sec": int(self.window_sec),
                "request_count": 0,
                "error_count": 0,
                "error_rate": None,
                "avg_latency_ms": None,
                "p95_latency_ms": None,
                "requests_per_sec": 0.0,
                "top_paths": [],
            }

        latency_values: List[float] = []
        error_count = 0
        path_stats: Dict[str, Dict[str, Any]] = {}
        for _, latency_ms, status_code, path in samples:
            latency_values.append(float(latency_ms))
            if status_code >= 400:
                error_count += 1
            bucket = path_stats.setdefault(path, {"count": 0, "error_count": 0, "lat_total": 0.0})
            bucket["count"] += 1
            bucket["lat_total"] += float(latency_ms)
            if status_code >= 400:
                bucket["error_count"] += 1

        avg_latency = sum(latency_values) / request_count
        p95_latency = _p95(latency_values)
        error_rate = error_count / request_count if request_count else None
        req_per_sec = request_count / self.window_sec if self.window_sec else 0.0

        top_paths = sorted(path_stats.items(), key=lambda item: item[1]["count"], reverse=True)[:3]
        top_paths_payload = []
        for path, bucket in top_paths:
            count = int(bucket["count"])
            avg = bucket["lat_total"] / count if count else None
            err_rate = bucket["error_count"] / count if count else None
            top_paths_payload.append(
                {
                    "path": path,
                    "count": count,
                    "error_rate": err_rate,
                    "avg_latency_ms": avg,
                }
            )

        return {
            "window_sec": int(self.window_sec),
            "request_count": request_count,
            "error_count": error_count,
            "error_rate": error_rate,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "requests_per_sec": round(req_per_sec, 3),
            "top_paths": top_paths_payload,
        }

    def _error_summary(self) -> Dict[str, Any]:
        with self._lock:
            last = self._errors[-1] if self._errors else None
            queue_size = len(self._errors)
        return {
            "queue_size": queue_size,
            "last_error_at": last.get("time") if last else None,
            "last_error_source": last.get("source") if last else None,
            "last_error_message": last.get("message") if last else None,
            "last_error_repeat": last.get("repeat") if last else None,
        }

    def get_error_summary(self) -> Dict[str, Any]:
        return self._error_summary()

    def get_stats(self) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            total_requests = self._total_requests
            total_latency = self._total_latency_ms
            error_count = self._error_count
            last = dict(self._last_request)
        avg_latency = (total_latency / total_requests) if total_requests else None
        return {
            "total_requests": total_requests,
            "avg_latency_ms": round(avg_latency, 2) if avg_latency is not None else None,
            "error_count": error_count,
            "last": last,
            "window": self._window_metrics(now),
            "errors": self._error_summary(),
        }


observability_service = ObservabilityService()
