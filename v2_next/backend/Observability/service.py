from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import logging
import math
import threading
import time
from typing import Any, Deque, Dict, List, Optional, Tuple


RequestSample = Tuple[float, float, int, str, str]
PollingClientCounts = Dict[str, int]
PollingPathSummary = Dict[str, Any]
PollingBucket = Tuple[float, Dict[str, PollingPathSummary]]
_SPOT_PROXY_PATH = "/api/spot/proxy_image"
_SPOT_LIVE_PATH = "/api/spot/live_image"
_POLLING_PATHS = {
    _SPOT_PROXY_PATH,
    _SPOT_LIVE_PATH,
    "/api/data",
    "/health",
    "/stats",
    "/api/observability/export/latest",
    "/api/memory/state",
    "/api/memory/details",
    "/api/memory/export/latest",
    "/api/memory/profiler/start",
    "/api/memory/profiler/stop",
    "/api/config",
    "/api/config/central-status",
    "/api/config/verify-password",
    "/api/logs/comm-metrics",
    "/api/spot/config",
    "/api/control/path-health",
}
_QUIET_PATH_PREFIXES = (
    "/assets/",
)
_SUMMARY_ONLY_PATHS = {
    "/api/log/status",
}
_SUMMARY_ONLY_PATH_PREFIXES = (
    "/api/layouts/client/",
)


_PERFORMANCE_CONTRACT_VERSION = "1.0"
_ERROR_SUMMARY_LIMIT = 12


def _performance_thresholds() -> Dict[str, Any]:
    return {
        "operational": {
            "health_latency_ms": {"target": 50, "warning": 50, "failure": 200},
            "data_latency_ms": {"target": 100, "warning": 100, "failure": 500},
            "spot_live_image_latency_ms": {"target": 500, "warning": 500, "failure": None},
            "spot_proxy_image_latency_ms": {"target": 500, "warning": 500, "failure": None},
            "lcp_ms": {"target": 2500, "warning": 2500, "failure": 4000},
            "cls": {"target": 0.1, "warning": 0.1, "failure": 0.25},
        },
        "regression_budget": {
            "timing_warning_ratio": 1.2,
            "timing_regression_ratio": 1.5,
            "timing_regression_absolute_ms": 500,
            "bundle_warning_ratio": 1.1,
            "bundle_regression_ratio": 1.25,
            "request_count_warning_ratio": 1.3,
        },
        "resource_growth": {
            "warmup_sec": 120,
            "observation_window_sec": 300,
            "sampling_cadence_sec": 5,
            "preferred_sample_count": 60,
            "minimum_sample_count": 48,
            "minimum_window_sec": 240,
        },
    }


def _is_quiet_path(path: str) -> bool:
    if path in _POLLING_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _QUIET_PATH_PREFIXES)


def _is_summary_only_path(path: str) -> bool:
    if path in _SUMMARY_ONLY_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _SUMMARY_ONLY_PATH_PREFIXES)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def _p95(values: List[float]) -> Optional[float]:
    if not values:
        return None
    values_sorted = sorted(values)
    idx = int(math.ceil(0.95 * len(values_sorted))) - 1
    idx = max(0, min(idx, len(values_sorted) - 1))
    return float(values_sorted[idx])


def _coerce_status_code(value: Optional[int]) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        status_code = int(value)
    except (TypeError, ValueError):
        return None
    return status_code if status_code > 0 else None


def _summary_key(value: Any, fallback: str = "unknown") -> str:
    text = str(value if value is not None else fallback).strip()
    if not text:
        return fallback
    return text[:160]


def _increment_count(target: Dict[str, int], key: str, count: int = 1) -> None:
    target[key] = target.get(key, 0) + max(1, int(count))


def _top_counts(source: Dict[str, int], limit: int = _ERROR_SUMMARY_LIMIT) -> List[Dict[str, Any]]:
    return [
        {"key": key, "count": int(count)}
        for key, count in sorted(source.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


class ObservabilityService:
    def __init__(
        self,
        window_sec: float = 60.0,
        max_requests: int = 2400,
        max_errors: int = 200,
    ) -> None:
        self.window_sec = max(10.0, float(window_sec))
        self._requests: Deque[RequestSample] = deque(maxlen=max_requests)
        self._request_details: Deque[RequestSample] = deque(maxlen=max(400, max_requests // 2))
        self._polling_buckets: Deque[PollingBucket] = deque(maxlen=max(120, int(self.window_sec) + 30))
        self._errors: Deque[Dict[str, Any]] = deque(maxlen=max_errors)
        self._lock = threading.Lock()
        self._logger = logging.getLogger("SmartFactoryLoggerV2")
        self._total_requests = 0
        self._total_latency_ms = 0.0
        self._total_http_4xx_count = 0
        self._total_http_5xx_count = 0
        self._last_request: Dict[str, Any] = {
            "latency_ms": None,
            "path": None,
            "status": None,
            "timestamp": None,
        }

    def _trim_polling_buckets(self, now: float) -> None:
        window_start = now - self.window_sec
        while self._polling_buckets and self._polling_buckets[0][0] < window_start:
            self._polling_buckets.popleft()

    def _get_or_create_polling_bucket(self, now: float) -> Dict[str, PollingPathSummary]:
        bucket_ts = float(int(now))
        if self._polling_buckets and self._polling_buckets[-1][0] == bucket_ts:
            return self._polling_buckets[-1][1]
        next_bucket: Dict[str, PollingPathSummary] = {}
        self._polling_buckets.append((bucket_ts, next_bucket))
        return next_bucket

    def _get_or_create_polling_entry(
        self,
        bucket: Dict[str, PollingPathSummary],
        path: str,
    ) -> PollingPathSummary:
        entry = bucket.get(path)
        if entry is not None:
            return entry
        next_entry: PollingPathSummary = {
            "count": 0,
            "latency_total_ms": 0.0,
            "http_4xx_count": 0,
            "http_5xx_count": 0,
            "clients": {},
            "success_count": 0,
            "failure_count": 0,
            "stale_count": 0,
            "age_total_sec": 0.0,
            "age_count": 0,
        }
        bucket[path] = next_entry
        return next_entry

    def record_spot_proxy_result(self, status_code: int, age_sec: Optional[float], is_stale: bool) -> None:
        now = time.time()
        with self._lock:
            self._trim_polling_buckets(now)
            bucket = self._get_or_create_polling_bucket(now)
            entry = self._get_or_create_polling_entry(bucket, _SPOT_PROXY_PATH)
            if status_code >= 400:
                return
            entry["success_count"] += 1
            if is_stale:
                entry["stale_count"] += 1
            if age_sec is not None:
                entry["age_total_sec"] += float(age_sec)
                entry["age_count"] += 1

    def record_spot_live_image_result(self, status_code: int, age_sec: Optional[float], is_stale: bool) -> None:
        now = time.time()
        with self._lock:
            self._trim_polling_buckets(now)
            bucket = self._get_or_create_polling_bucket(now)
            entry = self._get_or_create_polling_entry(bucket, _SPOT_LIVE_PATH)
            if status_code >= 400:
                return
            entry["success_count"] += 1
            if is_stale:
                entry["stale_count"] += 1
            if age_sec is not None:
                entry["age_total_sec"] += float(age_sec)
                entry["age_count"] += 1

    def record_request(self, path: str, status_code: int, latency_ms: float, client_host: str) -> None:
        now = time.time()
        sample: RequestSample = (now, float(latency_ms), int(status_code), str(path), str(client_host))
        quiet_path = _is_quiet_path(path)
        summary_only_success = _is_summary_only_path(path) and status_code < 400
        with self._lock:
            self._total_requests += 1
            self._total_latency_ms += float(latency_ms)
            if 400 <= status_code < 500:
                self._total_http_4xx_count += 1
            elif status_code >= 500:
                self._total_http_5xx_count += 1
            self._last_request = {
                "latency_ms": int(latency_ms),
                "path": path,
                "status": status_code,
                "timestamp": now,
            }
            if quiet_path or summary_only_success:
                self._trim_polling_buckets(now)
                bucket = self._get_or_create_polling_bucket(now)
                entry = self._get_or_create_polling_entry(bucket, path)
                entry["count"] += 1
                entry["latency_total_ms"] += float(latency_ms)
                if 400 <= status_code < 500:
                    entry["http_4xx_count"] += 1
                elif status_code >= 500:
                    entry["http_5xx_count"] += 1
                clients: PollingClientCounts = entry["clients"]
                clients[client_host] = clients.get(client_host, 0) + 1
                if path in (_SPOT_PROXY_PATH, _SPOT_LIVE_PATH) and status_code >= 400:
                    entry["failure_count"] += 1
            else:
                self._requests.append(sample)
            if status_code >= 400 or (not quiet_path and not summary_only_success):
                self._request_details.append(sample)

    def get_request_storage_summary(self) -> Dict[str, int]:
        with self._lock:
            self._trim_polling_buckets(time.time())
            detail_request_count = len(self._requests)
            detail_count = len(self._request_details)
            polling_bucket_count = len(self._polling_buckets)
            polling_count = 0
            polling_client_count = 0
            for _, bucket in self._polling_buckets:
                for entry in bucket.values():
                    polling_count += int(entry["count"])
                    polling_client_count += len(entry["clients"])
            request_count = detail_request_count + polling_count
        estimated_bytes = (
            detail_request_count * 40
            + detail_count * 40
            + polling_count * 16
            + polling_bucket_count * 128
            + polling_client_count * 32
        )
        return {
            "request_count": request_count,
            "detail_count": detail_count,
            "polling_count": polling_count,
            "polling_window_count": polling_bucket_count,
            "estimated_bytes": estimated_bytes,
        }

    def _log_error_event(self, entry: Dict[str, Any]) -> None:
        log_method = self._logger.error
        level = str(entry.get("level") or "error").lower()
        if level == "warning":
            log_method = self._logger.warning
        elif level == "info":
            log_method = self._logger.info

        source = _summary_key(entry.get("source"))
        path = _summary_key(entry.get("path"), "none")
        status = _summary_key(entry.get("status_code"), "none")
        error_type = _summary_key(entry.get("error_type"), "none")
        log_method(
            "Observability error recorded source=%s status=%s type=%s path=%s",
            source,
            status,
            error_type,
            path,
            extra={
                "error_source": entry.get("source"),
                "error_message": entry.get("message"),
                "error_detail": entry.get("detail"),
                "error_path": entry.get("path"),
                "error_level": entry.get("level"),
                "error_status_code": entry.get("status_code"),
                "error_type": entry.get("error_type"),
                "error_repeat": entry.get("repeat"),
                "error_time": entry.get("time"),
            },
        )

    def record_error(
        self,
        source: str,
        message: str,
        *,
        detail: Optional[str] = None,
        path: Optional[str] = None,
        level: str = "error",
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
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
            "status_code": _coerce_status_code(status_code),
            "error_type": error_type,
            "repeat": 1,
        }
        log_entry = entry
        with self._lock:
            if self._errors:
                last = self._errors[-1]
                if (
                    last.get("source") == source
                    and last.get("message") == message
                    and last.get("path") == path
                    and last.get("status_code") == entry["status_code"]
                    and last.get("error_type") == error_type
                    and now - float(last.get("time", 0)) <= 5.0
                ):
                    last["time"] = now
                    last["time_iso"] = _iso(now)
                    last["repeat"] = int(last.get("repeat", 1)) + 1
                    if detail:
                        last["detail"] = detail
                    if path:
                        last["path"] = path
                    if entry["status_code"] is not None:
                        last["status_code"] = entry["status_code"]
                    if error_type:
                        last["error_type"] = error_type
                    log_entry = dict(last)
                    self._log_error_event(log_entry)
                    return
            self._errors.append(entry)
        self._log_error_event(log_entry)

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
            self._trim_polling_buckets(now)
            polling_buckets = list(self._polling_buckets)

        if not samples and not polling_buckets:
            return {
                "window_sec": int(self.window_sec),
                "request_count": 0,
                "error_count": 0,
                "http_error_count": 0,
                "http_4xx_count": 0,
                "http_5xx_count": 0,
                "error_rate": None,
                "avg_latency_ms": None,
                "p95_latency_ms": None,
                "requests_per_sec": 0.0,
                "top_paths": [],
            }

        request_count = 0
        latency_values: List[float] = []
        error_count = 0
        http_4xx_count = 0
        http_5xx_count = 0
        path_stats: Dict[str, Dict[str, Any]] = {}
        for _, latency_ms, status_code, path, _ in samples:
            request_count += 1
            latency_values.append(float(latency_ms))
            if 400 <= status_code < 500:
                error_count += 1
                http_4xx_count += 1
            elif status_code >= 500:
                error_count += 1
                http_5xx_count += 1
            bucket = path_stats.setdefault(path, {"count": 0, "error_count": 0, "lat_total": 0.0})
            bucket["count"] += 1
            bucket["lat_total"] += float(latency_ms)
            if status_code >= 400:
                bucket["error_count"] += 1

        for _, bucket in polling_buckets:
            for path, entry in bucket.items():
                count = int(entry["count"])
                if count <= 0:
                    continue
                request_count += count
                avg_latency_ms = float(entry["latency_total_ms"]) / count
                latency_values.extend([avg_latency_ms] * count)
                error_delta = int(entry["http_4xx_count"]) + int(entry["http_5xx_count"])
                error_count += error_delta
                http_4xx_count += int(entry["http_4xx_count"])
                http_5xx_count += int(entry["http_5xx_count"])
                path_bucket = path_stats.setdefault(path, {"count": 0, "error_count": 0, "lat_total": 0.0})
                path_bucket["count"] += count
                path_bucket["lat_total"] += float(entry["latency_total_ms"])
                path_bucket["error_count"] += error_delta

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
            "http_error_count": error_count,
            "http_4xx_count": http_4xx_count,
            "http_5xx_count": http_5xx_count,
            "error_rate": error_rate,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "requests_per_sec": round(req_per_sec, 3),
            "top_paths": top_paths_payload,
        }

    def _polling_metrics(self, now: float) -> Dict[str, Any]:
        with self._lock:
            self._trim_polling_buckets(now)
            polling_buckets = list(self._polling_buckets)

        path_stats: Dict[str, Dict[str, Any]] = {}
        for _, bucket in polling_buckets:
            for path, entry in bucket.items():
                path_entry = path_stats.setdefault(
                    path,
                    {
                        "count": 0,
                        "latency_total_ms": 0.0,
                        "http_4xx_count": 0,
                        "http_5xx_count": 0,
                        "clients": {},
                        "success_count": 0,
                        "failure_count": 0,
                        "stale_count": 0,
                        "age_total_sec": 0.0,
                        "age_count": 0,
                    },
                )
                path_entry["count"] += int(entry["count"])
                path_entry["latency_total_ms"] += float(entry["latency_total_ms"])
                path_entry["http_4xx_count"] += int(entry["http_4xx_count"])
                path_entry["http_5xx_count"] += int(entry["http_5xx_count"])
                path_entry["success_count"] += int(entry["success_count"])
                path_entry["failure_count"] += int(entry["failure_count"])
                path_entry["stale_count"] += int(entry["stale_count"])
                path_entry["age_total_sec"] += float(entry["age_total_sec"])
                path_entry["age_count"] += int(entry["age_count"])
                clients: PollingClientCounts = path_entry["clients"]
                for client_host, client_count in entry["clients"].items():
                    clients[client_host] = clients.get(client_host, 0) + int(client_count)

        payload: Dict[str, Any] = {}
        for path, entry in path_stats.items():
            count = int(entry["count"])
            if count <= 0:
                continue
            clients = entry["clients"]
            top_clients = sorted(clients.items(), key=lambda item: item[1], reverse=True)[:5]
            error_count = int(entry["http_4xx_count"]) + int(entry["http_5xx_count"])
            path_payload: Dict[str, Any] = {
                "count": count,
                "requests_per_sec": round(count / self.window_sec, 3) if self.window_sec else 0.0,
                "avg_latency_ms": round(float(entry["latency_total_ms"]) / count, 3),
                "error_rate": (error_count / count) if count else None,
                "http_4xx_count": int(entry["http_4xx_count"]),
                "http_5xx_count": int(entry["http_5xx_count"]),
                "unique_clients": len(clients),
                "top_clients": [
                    {
                        "client": client_host,
                        "count": int(client_count),
                    }
                    for client_host, client_count in top_clients
                ],
            }
            if path in (_SPOT_PROXY_PATH, _SPOT_LIVE_PATH):
                age_count = int(entry["age_count"])
                path_payload["success_count"] = int(entry["success_count"])
                path_payload["failure_count"] = int(entry["failure_count"])
                path_payload["stale_count"] = int(entry["stale_count"])
                path_payload["avg_age_sec"] = (
                    round(float(entry["age_total_sec"]) / age_count, 3) if age_count > 0 else None
                )
            payload[path] = path_payload

        return {
            "window_sec": int(self.window_sec),
            "paths": payload,
        }

    def _error_summary(self) -> Dict[str, Any]:
        with self._lock:
            last = self._errors[-1] if self._errors else None
            queue_size = len(self._errors)
            repeat_total = 0
            source_counts: Dict[str, int] = {}
            source_repeat_counts: Dict[str, int] = {}
            type_counts: Dict[str, int] = {}
            message_counts: Dict[str, int] = {}
            status_counts: Dict[str, int] = {}
            path_counts: Dict[str, int] = {}
            route_status_counts: Dict[str, int] = {}
            for item in self._errors:
                repeat = max(1, int(item.get("repeat") or 1))
                repeat_total += repeat
                source = str(item.get("source") or "unknown")
                source_counts[source] = source_counts.get(source, 0) + 1
                _increment_count(source_repeat_counts, _summary_key(source), repeat)
                _increment_count(type_counts, _summary_key(item.get("error_type")), repeat)
                _increment_count(message_counts, _summary_key(item.get("message")), repeat)
                status_key = _summary_key(item.get("status_code"), "none")
                _increment_count(status_counts, status_key, repeat)
                path_key = _summary_key(item.get("path"), "none")
                _increment_count(path_counts, path_key, repeat)
                _increment_count(route_status_counts, f"{path_key} {status_key}", repeat)
        return {
            "queue_size": queue_size,
            "repeat_total": repeat_total,
            "last_error_at": last.get("time") if last else None,
            "last_error_source": last.get("source") if last else None,
            "last_error_message": last.get("message") if last else None,
            "last_error_repeat": last.get("repeat") if last else None,
            "source_counts": source_counts,
            "source_repeat_counts": source_repeat_counts,
            "type_counts": type_counts,
            "status_counts": status_counts,
            "path_counts": path_counts,
            "route_status_counts": route_status_counts,
            "top_sources": _top_counts(source_repeat_counts),
            "top_types": _top_counts(type_counts),
            "top_messages": _top_counts(message_counts),
            "top_statuses": _top_counts(status_counts),
            "top_paths": _top_counts(path_counts),
            "top_route_statuses": _top_counts(route_status_counts),
        }

    def get_error_summary(self) -> Dict[str, Any]:
        return self._error_summary()

    def get_stats(self) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            total_requests = self._total_requests
            total_latency = self._total_latency_ms
            total_http_4xx_count = self._total_http_4xx_count
            total_http_5xx_count = self._total_http_5xx_count
            last = dict(self._last_request)
        avg_latency = (total_latency / total_requests) if total_requests else None
        total_http_error_count = total_http_4xx_count + total_http_5xx_count
        return {
            "performance_contract_version": _PERFORMANCE_CONTRACT_VERSION,
            "thresholds": _performance_thresholds(),
            "total_requests": total_requests,
            "avg_latency_ms": round(avg_latency, 2) if avg_latency is not None else None,
            "error_count": total_http_error_count,
            "total_http_error_count": total_http_error_count,
            "total_http_4xx_count": total_http_4xx_count,
            "total_http_5xx_count": total_http_5xx_count,
            "last": last,
            "window": self._window_metrics(now),
            "errors": self._error_summary(),
            "polling": self._polling_metrics(now),
        }


observability_service = ObservabilityService()
