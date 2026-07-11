import asyncio
import json
import logging
import math
import queue
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import httpx

from backend import config
from backend.FacilityData.spot_observation import (
    SPOT_INVALID_SENTINEL_VALUES,
    SpotPollStatus,
    SpotRawClassification,
    SpotRawValidity,
    SpotSourceFreshness,
    classify_spot_raw_response,
    derive_spot_target_observed_shadow,
)
from backend.FacilityData.spot_diagnostics import (
    DiagnosticSnapshot,
    SPOT_DIAGNOSTIC_OUTPUT_FIELDS,
    SpotPollContext,
    configured_diagnostics_max_age_ms,
)
from backend.FacilityData.spot_observation_fact import (
    SPOT_OBSERVATION_FACT_FILENAME,
    SpotObservationFactWriter,
    encode_spot_diagnostic_evidence_codes,
)
from backend.FacilityData.spot_config_provenance import build_spot_configuration_snapshot
from backend.FacilityData.spot_image_fact import SpotImageCaptureWriter
from backend.FacilityData.temperature_state import (
    TemperatureStateDecision,
    TemperatureStateInput,
    derive_temperature_state,
)
from backend.version import resolve_runtime_git_commit

_ACTUATOR_LOCK = threading.Lock()


class _TemperatureCache(TypedDict):
    temp: float
    temp_time: float

# Short-lived image proxy cache
_img_cache: Dict[str, Any] = {"data": None, "time": 0.0, "temp": 0.0, "temp_time": 0.0}
_internal_temp_cache: _TemperatureCache = {"temp": 0.0, "temp_time": 0.0}
_IMG_CACHE_TTL_SEC = 2.0
_IMG_BACKOFF_BASE_SEC = 0.5
_IMG_BACKOFF_MAX_SEC = 5.0
_LIVE_IMG_SHARED_FRAME_TTL_SEC = 0.05
_LIVE_IMG_BACKOFF_BASE_SEC = 0.25
_LIVE_IMG_BACKOFF_MAX_SEC = 2.0
_TEMP_CACHE_TTL_SEC = 15.0
_SPOT_VERIFIED_NO_TARGET_VALUES: tuple[str, ...] = ()
_SPOT_INVALID_SENTINEL_VALUES: tuple[str, ...] = SPOT_INVALID_SENTINEL_VALUES
_SPOT_FOCUS_MIN_MM = 300
_SPOT_FOCUS_MAX_MM = 10000
_SPOT_FOCUS_VERIFY_TIMEOUT_SEC = 4.0
_SPOT_FOCUS_VERIFY_INTERVAL_SEC = 0.25
_SPOT_ACTUATOR_VERIFY_TIMEOUT_SEC = 4.0
_SPOT_ACTUATOR_VERIFY_INTERVAL_SEC = 0.25
_SPOT_DIAGNOSTIC_OUTPUT_PARAMS = SPOT_DIAGNOSTIC_OUTPUT_FIELDS
_SPOT_DIAGNOSTIC_TEXT_MAX_CHARS = 256
_SPOT_DIAGNOSTICS_COLLECTION_MODE = str(
    getattr(config, "SPOT_DIAGNOSTICS_COLLECTION_MODE", "async_fact_only")
    or "async_fact_only"
)
_SPOT_RUNTIME_GIT_COMMIT = resolve_runtime_git_commit()
_ACTUATOR_POS_PATTERN = re.compile(rb"Pos-->\s*(\d+)")
_img_fetch_lock = asyncio.Lock()
_live_img_fetch_lock = asyncio.Lock()
_img_last_error = 0.0
_img_failure_count = 0
_img_cache_state = "empty"
_img_last_cache_log_at = 0.0
_img_last_error_code: Optional[str] = None
_img_last_error_message: Optional[str] = None
_img_next_retry_at: Optional[float] = None
_live_img_cache: Dict[str, Any] = {"data": None, "time": 0.0, "url": None}
_live_img_last_error = 0.0
_live_img_failure_count = 0
_live_img_last_error_code: Optional[str] = None
_live_img_last_error_message: Optional[str] = None
_live_img_last_url: Optional[str] = None
_live_img_next_retry_at: Optional[float] = None
_temp_last_error = 0.0
_temp_last_error_code: Optional[str] = None
_temp_last_error_message: Optional[str] = None
_temp_last_upstream_status: Optional[int] = None
_temp_last_url: Optional[str] = None
_temp_last_success_at = 0.0
_internal_temp_last_error = 0.0
_internal_temp_last_error_code: Optional[str] = None
_internal_temp_last_error_message: Optional[str] = None
_internal_temp_last_upstream_status: Optional[int] = None
_internal_temp_last_url: Optional[str] = None
_internal_temp_last_success_at = 0.0
_spot_diagnostics_lock = threading.Lock()
_spot_diagnostics_snapshot: Optional[Dict[str, Any]] = None
_spot_diagnostics_last_error_code: Optional[str] = None
_spot_diagnostics_last_error_message: Optional[str] = None
_spot_diagnostics_seq = 0
_spot_config_provenance_lock = threading.Lock()
_spot_config_drift_detected_count = 0
_spot_config_active_drift_signature: Optional[str] = None
_spot_last_configuration_snapshot: Optional[Dict[str, Any]] = None
_spot_temperature_snapshot_lock = threading.Lock()
_spot_service_instance_id = str(uuid4())
_spot_service_started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
_spot_poll_seq = 0
_spot_observation_seq = 0
_spot_temperature_snapshot: Optional[Dict[str, Any]] = None
_spot_observation_fact_writer: Optional[SpotObservationFactWriter] = None
_spot_diagnostics_prefetch_task: Optional[asyncio.Task[None]] = None
_spot_last_valid_value_at: Optional[float] = None
_spot_last_valid_value_monotonic: Optional[float] = None
_spot_temperature_cache_suppressed_until_valid = False
_INVALID_IMAGE_PAYLOAD_REJECTION_CODES = {"empty-body", "invalid-image-html", "invalid-image-payload"}

# Async HTTP client reused for connection pooling.
_http_client: Optional[httpx.AsyncClient] = None
_logger = logging.getLogger("spot_control")


@dataclass(frozen=True)
class _SpotImageCaptureEvent:
    image_bytes: bytes
    captured_at: float
    source_url: str
    source: str
    image_age_ms: Optional[float]
    link_checked_at: Optional[float]
    observation_snapshot: Optional[Dict[str, Any]]


_SPOT_IMAGE_CAPTURE_QUEUE_MAX = 128
_SPOT_IMAGE_CAPTURE_QUEUE: queue.Queue[_SpotImageCaptureEvent] = queue.Queue(maxsize=_SPOT_IMAGE_CAPTURE_QUEUE_MAX)
_SPOT_IMAGE_CAPTURE_STOP = threading.Event()
_SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED = threading.Event()
_spot_image_capture_lock = threading.Lock()
_spot_image_capture_thread: Optional[threading.Thread] = None
_spot_image_capture_writer: Optional[SpotImageCaptureWriter] = None
_spot_image_capture_writer_signature: Optional[tuple[Path, Path, int, float]] = None
_spot_image_capture_last_enqueue_at = 0.0
_spot_image_capture_last_write_at = 0.0
_spot_image_capture_last_error_at = 0.0
_spot_image_capture_last_error_code: Optional[str] = None
_spot_image_capture_last_error_message: Optional[str] = None
_spot_image_capture_enqueued_count = 0
_spot_image_capture_written_count = 0
_spot_image_capture_dropped_count = 0
_spot_image_capture_failure_count = 0
_spot_image_capture_last_fact: Optional[Dict[str, str]] = None


class SpotImageConfigError(ValueError):
    def __init__(self, image_url: str) -> None:
        super().__init__("SPOT_IMAGE_URL is not configured")
        self.image_url = image_url


class SpotImageFetchError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        image_url: str,
        upstream_status: Optional[int],
    ) -> None:
        super().__init__(message)
        self.code = code
        self.image_url = image_url
        self.upstream_status = upstream_status


class SpotImageBackoffError(RuntimeError):
    def __init__(self, image_url: str, retry_after_sec: float) -> None:
        super().__init__(f"SPOT image retry backoff is active; retry_after_sec={retry_after_sec:.3f}")
        self.code = "retry-backoff-active"
        self.image_url = image_url
        self.upstream_status: Optional[int] = None
        self.retry_after_sec = retry_after_sec


class SpotLiveImageConfigError(ValueError):
    def __init__(self, image_url: str) -> None:
        super().__init__("SPOT_LIVE_IMAGE_URL is not configured")
        self.image_url = image_url


class SpotLiveImageBackoffError(RuntimeError):
    def __init__(self, image_url: str, retry_after_sec: float) -> None:
        super().__init__(f"SPOT live image retry backoff is active; retry_after_sec={retry_after_sec:.3f}")
        self.code = "live-backoff-active"
        self.image_url = image_url
        self.upstream_status: Optional[int] = None
        self.retry_after_sec = retry_after_sec


class SpotTemperatureConfigError(ValueError):
    def __init__(self, temp_url: str) -> None:
        super().__init__("SPOT_URL is not configured")
        self.temp_url = temp_url


class SpotTemperatureFetchError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        temp_url: str,
        upstream_status: Optional[int],
        raw_body: Optional[bytes] = None,
        raw_classification: Optional[SpotRawClassification] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.temp_url = temp_url
        self.upstream_status = upstream_status
        self.raw_body = raw_body
        self.raw_classification = raw_classification


class SpotInternalTemperatureConfigError(ValueError):
    def __init__(self, temp_url: str) -> None:
        super().__init__("SPOT_INTERNAL_TEMPERATURE_URL is not configured")
        self.temp_url = temp_url


class SpotInternalTemperatureFetchError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        temp_url: str,
        upstream_status: Optional[int],
    ) -> None:
        super().__init__(message)
        self.code = code
        self.temp_url = temp_url
        self.upstream_status = upstream_status


class SpotFocusControlError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        focus_url: str,
        upstream_status: Optional[int],
    ) -> None:
        super().__init__(message)
        self.focus_url = focus_url
        self.upstream_status = upstream_status


class SpotActuatorControlError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        actuator_url: str,
        upstream_status: Optional[int],
    ) -> None:
        super().__init__(message)
        self.actuator_url = actuator_url
        self.upstream_status = upstream_status


def _spot_image_capture_mode() -> str:
    if not bool(getattr(config, "SPOT_IMAGE_CAPTURE_ENABLED", False)):
        return "off"
    mode = str(getattr(config, "SPOT_IMAGE_CAPTURE_MODE", "event") or "event").strip().lower()
    if mode not in {"off", "event", "interval", "all"}:
        return "event"
    return mode


def _spot_image_capture_log_path() -> Path:
    return Path(getattr(config, "LOG_PATH", Path("logs/data")))


def _spot_image_capture_root() -> Path:
    raw_path = str(getattr(config, "SPOT_IMAGE_CAPTURE_PATH", "spot_images") or "spot_images").strip()
    configured_path = Path(raw_path or "spot_images")
    if configured_path.is_absolute():
        return configured_path
    return _spot_image_capture_log_path() / configured_path


def _spot_image_capture_retention_days() -> int:
    return int(getattr(config, "SPOT_IMAGE_CAPTURE_RETENTION_DAYS", 7) or 0)


def _spot_image_capture_link_stale_threshold_ms() -> float:
    return float(getattr(config, "SPOT_REFRESH_INTERVAL", 3.0) or 3.0) * 3.0 * 1000.0


def _spot_image_capture_config_signature() -> tuple[Path, Path, int, float]:
    return (
        _spot_image_capture_log_path(),
        _spot_image_capture_root(),
        _spot_image_capture_retention_days(),
        _spot_image_capture_link_stale_threshold_ms(),
    )


def _get_spot_image_capture_writer() -> SpotImageCaptureWriter:
    global _spot_image_capture_writer, _spot_image_capture_writer_signature
    with _spot_image_capture_lock:
        signature = _spot_image_capture_config_signature()
        if _spot_image_capture_writer is None or _spot_image_capture_writer_signature != signature:
            _spot_image_capture_writer = SpotImageCaptureWriter(
                log_path=signature[0],
                capture_root=signature[1],
                retention_days=signature[2],
                link_stale_threshold_ms=signature[3],
            )
            _spot_image_capture_writer_signature = signature
        return _spot_image_capture_writer


def _start_spot_image_capture_worker(*, force: bool = False) -> None:
    global _spot_image_capture_thread
    if _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set() and not force:
        return
    with _spot_image_capture_lock:
        if _spot_image_capture_thread is not None and _spot_image_capture_thread.is_alive():
            return
        if _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set() and not force:
            return
        _SPOT_IMAGE_CAPTURE_STOP.clear()
        _spot_image_capture_thread = threading.Thread(
            target=_spot_image_capture_worker,
            name="spot-image-capture-writer",
            daemon=True,
        )
        _spot_image_capture_thread.start()


def _spot_image_capture_worker() -> None:
    global _spot_image_capture_failure_count, _spot_image_capture_last_fact
    global _spot_image_capture_last_error_at, _spot_image_capture_last_error_code, _spot_image_capture_last_error_message
    global _spot_image_capture_last_write_at, _spot_image_capture_written_count
    while not _SPOT_IMAGE_CAPTURE_STOP.is_set() or not _SPOT_IMAGE_CAPTURE_QUEUE.empty():
        try:
            event = _SPOT_IMAGE_CAPTURE_QUEUE.get(timeout=0.1)
        except queue.Empty:
            continue
        try:
            writer = _get_spot_image_capture_writer()
            fact = writer.write_capture(
                image_bytes=event.image_bytes,
                captured_at=event.captured_at,
                source_url=event.source_url,
                source=event.source,
                image_age_ms=event.image_age_ms,
                link_checked_at=event.link_checked_at,
                observation_snapshot=event.observation_snapshot,
            )
            with _spot_image_capture_lock:
                _spot_image_capture_written_count += 1
                _spot_image_capture_last_write_at = time.time()
                _spot_image_capture_last_fact = dict(fact)
                _spot_image_capture_last_error_code = None
                _spot_image_capture_last_error_message = None
        except Exception as exc:  # pragma: no cover - exercised through integration-style tests
            with _spot_image_capture_lock:
                _spot_image_capture_failure_count += 1
                _spot_image_capture_last_error_at = time.time()
                _spot_image_capture_last_error_code = exc.__class__.__name__
                _spot_image_capture_last_error_message = "capture writer failed"
            _logger.warning(
                "SPOT image capture writer failed",
                extra={
                    "error_type": exc.__class__.__name__,
                },
            )
        finally:
            _SPOT_IMAGE_CAPTURE_QUEUE.task_done()


def flush_spot_image_capture_queue(timeout_sec: float = 2.0) -> bool:
    deadline = time.time() + max(0.0, timeout_sec)
    while time.time() < deadline:
        if getattr(_SPOT_IMAGE_CAPTURE_QUEUE, "unfinished_tasks", 0) == 0:
            return True
        time.sleep(0.01)
    return getattr(_SPOT_IMAGE_CAPTURE_QUEUE, "unfinished_tasks", 0) == 0


def stop_spot_image_capture_writer(timeout_sec: float = 2.0) -> bool:
    _SPOT_IMAGE_CAPTURE_STOP.set()
    thread = _spot_image_capture_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=max(0.0, timeout_sec))
    return getattr(_SPOT_IMAGE_CAPTURE_QUEUE, "unfinished_tasks", 0) == 0 and not (
        thread is not None and thread.is_alive()
    )


def stop_spot_image_capture_for_shutdown(timeout_sec: float = 2.0) -> bool:
    global _prefetch_running
    _prefetch_running = False
    _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.set()
    thread = _spot_image_capture_thread
    if getattr(_SPOT_IMAGE_CAPTURE_QUEUE, "unfinished_tasks", 0) > 0 and (
        thread is None or not thread.is_alive()
    ):
        _start_spot_image_capture_worker(force=True)
    return stop_spot_image_capture_writer(timeout_sec=timeout_sec)


def _reset_spot_image_capture_state_for_tests() -> None:
    global _spot_image_capture_writer, _spot_image_capture_writer_signature, _spot_image_capture_thread
    global _spot_image_capture_enqueued_count, _spot_image_capture_written_count, _spot_image_capture_dropped_count
    global _spot_image_capture_failure_count, _spot_image_capture_last_enqueue_at, _spot_image_capture_last_write_at
    global _spot_image_capture_last_error_at, _spot_image_capture_last_error_code, _spot_image_capture_last_error_message
    global _spot_image_capture_last_fact
    stop_spot_image_capture_writer(timeout_sec=0.5)
    while True:
        try:
            _SPOT_IMAGE_CAPTURE_QUEUE.get_nowait()
            _SPOT_IMAGE_CAPTURE_QUEUE.task_done()
        except queue.Empty:
            break
    with _spot_image_capture_lock:
        _spot_image_capture_writer = None
        _spot_image_capture_writer_signature = None
        _spot_image_capture_thread = None
        _spot_image_capture_enqueued_count = 0
        _spot_image_capture_written_count = 0
        _spot_image_capture_dropped_count = 0
        _spot_image_capture_failure_count = 0
        _spot_image_capture_last_enqueue_at = 0.0
        _spot_image_capture_last_write_at = 0.0
        _spot_image_capture_last_error_at = 0.0
        _spot_image_capture_last_error_code = None
        _spot_image_capture_last_error_message = None
        _spot_image_capture_last_fact = None
    _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.clear()
    _SPOT_IMAGE_CAPTURE_STOP.clear()


def get_latest_spot_image_capture_fact() -> Dict[str, str]:
    with _spot_image_capture_lock:
        return dict(_spot_image_capture_last_fact or {})


def _spot_image_capture_fact_row_count() -> int:
    return _get_spot_image_capture_writer().fact_row_count


def get_spot_image_capture_health() -> Dict[str, Any]:
    fact_row_count = _spot_image_capture_fact_row_count()
    with _spot_image_capture_lock:
        last_fact = _spot_image_capture_last_fact or {}
        return {
            "enabled": _spot_image_capture_mode() != "off",
            "mode": _spot_image_capture_mode(),
            "queue_size": _SPOT_IMAGE_CAPTURE_QUEUE.qsize(),
            "queue_capacity": _SPOT_IMAGE_CAPTURE_QUEUE_MAX,
            "enqueued_count": _spot_image_capture_enqueued_count,
            "written_count": _spot_image_capture_written_count,
            "fact_row_count": fact_row_count,
            "dropped_count": _spot_image_capture_dropped_count,
            "failure_count": _spot_image_capture_failure_count,
            "last_enqueue_at": _spot_image_capture_last_enqueue_at or None,
            "last_write_at": _spot_image_capture_last_write_at or None,
            "last_error_at": _spot_image_capture_last_error_at or None,
            "last_error_code": _spot_image_capture_last_error_code,
            "last_error_message": _spot_image_capture_last_error_message,
            "last_capture_id": last_fact.get("spot_image_capture_id"),
            "last_capture_path": last_fact.get("spot_image_path"),
            "last_capture_link_status": last_fact.get("spot_image_link_status"),
            "last_capture_link_age_ms": last_fact.get("spot_image_link_age_ms"),
            "last_capture_linked_observation_key": last_fact.get("spot_image_linked_observation_key"),
        }


def _spot_image_capture_evidence_codes(snapshot: Dict[str, Any]) -> set[str]:
    value = snapshot.get("spot_diagnostic_evidence_codes")
    if value is None:
        return set()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return set()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = []
            if isinstance(parsed, list):
                return {str(item) for item in parsed}
        return {part.strip() for part in stripped.replace(";", ",").split(",") if part.strip()}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    return set()


def _spot_image_capture_output_status(snapshot: Dict[str, Any]) -> str:
    explicit = str(snapshot.get("temperature_output_status") or "").strip()
    if explicit:
        return explicit
    device_status = str(snapshot.get("spot_device_status_code") or "").strip()
    if device_status == "temperature_under_range":
        return "under_range"
    if device_status == "temperature_over_range":
        return "over_range"
    raw_validity = str(snapshot.get("spot_raw_validity") or "").strip()
    if raw_validity == SpotRawValidity.VALID_TEMPERATURE.value:
        return "valid"
    poll_status = str(snapshot.get("spot_poll_status") or "").strip()
    if poll_status in {"timeout", "connection_error", "http_error", "config_missing"}:
        return "source_error"
    return raw_validity


def _alarmstatus_bit4_active(value: Any) -> bool:
    if value is None:
        return False
    try:
        return bool(int(str(value).strip(), 0) & (1 << 4))
    except (TypeError, ValueError):
        return False


def _signal_below_capture_threshold(value: Any) -> bool:
    if value is None:
        return False
    try:
        signal_pc = float(value)
    except (TypeError, ValueError):
        return False
    threshold = float(getattr(config, "SPOT_LOW_SIGNAL_THRESHOLD_PC", 2.0) or 2.0)
    return signal_pc < threshold


def _spot_image_capture_event_matches(snapshot: Optional[Dict[str, Any]]) -> bool:
    if snapshot is None:
        return False
    output_status = _spot_image_capture_output_status(snapshot)
    if output_status in {"under_range", "over_range", "stale", "source_error"}:
        return True
    process_phase = str(snapshot.get("process_phase_candidate") or "").strip()
    if process_phase in {"setup_candidate", "setup_alignment_candidate", "die_change_candidate", "changeover_candidate"}:
        return True
    evidence = _spot_image_capture_evidence_codes(snapshot)
    if evidence.intersection(
        {
            "target_out_of_fov_evidence",
            "actuator_scanning",
            "actuator_position_changed",
            "signal_below_threshold",
            "alarm_low_signal",
            "detector_below_measurement_range",
        }
    ):
        return True
    if _alarmstatus_bit4_active(snapshot.get("alarmstatus")):
        return True
    return _signal_below_capture_threshold(snapshot.get("signalpc"))


def _should_enqueue_spot_image_capture(mode: str, snapshot: Optional[Dict[str, Any]]) -> bool:
    if mode == "off":
        return False
    if mode in {"all", "interval"}:
        return True
    return _spot_image_capture_event_matches(snapshot)


def _maybe_enqueue_spot_image_capture(
    *,
    image_bytes: bytes,
    captured_at: float,
    image_url: str,
    source: str,
    image_age_ms: Optional[float] = None,
) -> None:
    global _spot_image_capture_dropped_count, _spot_image_capture_enqueued_count, _spot_image_capture_last_enqueue_at
    if _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set():
        return
    mode = _spot_image_capture_mode()
    if mode == "off":
        return
    max_bytes = int(getattr(config, "SPOT_IMAGE_CAPTURE_MAX_BYTES", 2_000_000) or 1)
    if len(image_bytes) > max_bytes:
        with _spot_image_capture_lock:
            _spot_image_capture_dropped_count += 1
        return
    link_checked_at: Optional[float] = None
    snapshot = None
    if bool(getattr(config, "SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION", True)):
        link_checked_at = time.time()
        snapshot = get_spot_temperature_poll_snapshot()
    if not _should_enqueue_spot_image_capture(mode, snapshot):
        return
    min_interval_sec = max(0.0, float(getattr(config, "SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC", 1.0) or 0.0))
    now = time.time()
    with _spot_image_capture_lock:
        if _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set():
            return
        if min_interval_sec > 0.0 and now - _spot_image_capture_last_enqueue_at < min_interval_sec:
            return
        event = _SpotImageCaptureEvent(
            image_bytes=bytes(image_bytes),
            captured_at=captured_at,
            source_url=image_url,
            source=source,
            image_age_ms=image_age_ms,
            link_checked_at=link_checked_at,
            observation_snapshot=dict(snapshot) if snapshot is not None else None,
        )
        try:
            _SPOT_IMAGE_CAPTURE_QUEUE.put_nowait(event)
        except queue.Full:
            _spot_image_capture_dropped_count += 1
            return
        _spot_image_capture_enqueued_count += 1
        _spot_image_capture_last_enqueue_at = now
    _start_spot_image_capture_worker()


def _format_exception_message(exc: BaseException) -> str:
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


def _response_body_preview(response: httpx.Response, max_chars: int) -> str:
    body = response.text.strip()
    if len(body) <= max_chars:
        return body
    return body[:max_chars]


def _response_content_type(response: httpx.Response) -> str:
    return str(response.headers.get("content-type") or "").strip()


def _image_payload_type(data: bytes) -> Optional[str]:
    if data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"
    if data.startswith(b"BM"):
        return "bmp"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    return None


def _payload_looks_like_html(data: bytes) -> bool:
    sample = data.lstrip()[:256].lower()
    return (
        sample.startswith(b"<!doctype html")
        or sample.startswith(b"<html")
        or sample.startswith(b"<head")
        or sample.startswith(b"<body")
        or b"<html" in sample[:80]
    )


def _is_spot_image_payload_rejection_code(error_code: str | None) -> bool:
    if error_code is None:
        return False
    return error_code in _INVALID_IMAGE_PAYLOAD_REJECTION_CODES


def _validate_spot_image_response(response: httpx.Response, image_url: str, data: bytes) -> None:
    content_type = _response_content_type(response)
    if _payload_looks_like_html(data):
        raise SpotImageFetchError(
            "invalid-image-html",
            (
                "SPOT image upstream returned HTML instead of image bytes; "
                f"url={image_url}; status_code={response.status_code}; "
                f"content_type={content_type}; body={_response_body_preview(response, 200)}"
            ),
            image_url=image_url,
            upstream_status=response.status_code,
        )
    if _image_payload_type(data) is None:
        raise SpotImageFetchError(
            "invalid-image-payload",
            (
                "SPOT image upstream returned a non-image payload; "
                f"url={image_url}; status_code={response.status_code}; "
                f"content_type={content_type}; body={_response_body_preview(response, 200)}"
            ),
            image_url=image_url,
            upstream_status=response.status_code,
        )


def _resolve_spot_image_url() -> str:
    image_url = str(config.SPOT_IMAGE_URL or "").strip()
    if not image_url:
        raise SpotImageConfigError(image_url)
    return image_url


def _resolve_spot_live_image_url() -> str:
    fallback_url = str(config.SPOT_IMAGE_URL or "").strip() or f"http://{config.SPOT_IP}/image.jpg"
    image_url = str(getattr(config, "SPOT_LIVE_IMAGE_URL", "") or "").strip() or fallback_url
    if not image_url:
        raise SpotLiveImageConfigError(image_url)
    return image_url


def _resolve_spot_image_url_candidates(image_url: str) -> list[str]:
    stripped_url = image_url.rstrip("/")
    try:
        parsed = urlsplit(stripped_url)
    except Exception as exc:
        raise SpotImageFetchError(
            "upstream-request-error",
            (
                "SPOT image upstream URL is malformed; "
                f"url={image_url}; error={_format_exception_message(exc)}"
            ),
            image_url=image_url,
            upstream_status=None,
        ) from exc

    if not parsed.scheme or not parsed.netloc:
        return [image_url]

    normalized_path = (parsed.path or "").rstrip("/")
    if not normalized_path:
        return [image_url]

    normalized_lower = normalized_path.lower()
    variant_paths: list[str] = []
    if normalized_lower.endswith("/image"):
        variant_paths.append(normalized_path + ".jpg")
    elif normalized_lower.endswith("/image.jpg"):
        variant_paths.append(normalized_path[:-4])
    elif normalized_lower.endswith("/image.jpeg"):
        variant_paths.append(normalized_path[:-5])
    elif normalized_lower.endswith("/image.png"):
        variant_paths.append(normalized_path[:-4])

    candidates = [image_url]
    for variant_path in variant_paths:
        if variant_path == normalized_path:
            continue
        candidates.append(parsed._replace(path=variant_path).geturl())
    seen: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.append(candidate)
    return seen


def _is_retryable_spot_image_error(error: SpotImageFetchError, has_next_candidate: bool) -> bool:
    if not has_next_candidate:
        return False
    if error.code == "upstream-http-error":
        return error.upstream_status == 404
    if error.code in {"invalid-image-html", "invalid-image-payload"}:
        return True
    return False


def _resolve_spot_temperature_url() -> str:
    temp_url = str(config.SPOT_URL or "").strip()
    if not temp_url:
        raise SpotTemperatureConfigError(temp_url)
    return temp_url


def _resolve_spot_internal_temperature_url() -> str:
    temp_url = str(config.SPOT_INTERNAL_TEMPERATURE_URL or "").strip()
    if not temp_url:
        raise SpotInternalTemperatureConfigError(temp_url)
    return temp_url


def _resolve_spot_output_url(param: str) -> str:
    base_url = str(config.SPOT_URL or "").strip() or f"http://{config.SPOT_IP}/output?p=temperature"
    parts = urlsplit(base_url)
    if not parts.scheme or not parts.netloc:
        raise SpotTemperatureConfigError(base_url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key.lower() != "p"]
    query.append(("p", param))
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/output", urlencode(query), ""))


def _spot_diagnostics_max_age_sec() -> float:
    return configured_diagnostics_max_age_ms(config.SPOT_REFRESH_INTERVAL) / 1000.0


def _spot_configuration_snapshot() -> Dict[str, Any]:
    global _spot_config_active_drift_signature
    global _spot_config_drift_detected_count
    global _spot_last_configuration_snapshot

    snapshot = build_spot_configuration_snapshot(
        config,
        runtime_git_commit=_SPOT_RUNTIME_GIT_COMMIT,
        device_readback_status="not_supported",
    )
    with _spot_config_provenance_lock:
        if snapshot["config_drift_detected"]:
            signature = json.dumps(
                {
                    "fingerprint": snapshot["spot_config_fingerprint_sha256"],
                    "fields": snapshot["config_drift_fields"],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            if signature != _spot_config_active_drift_signature:
                _spot_config_drift_detected_count += 1
            _spot_config_active_drift_signature = signature
        else:
            _spot_config_active_drift_signature = None
        _spot_last_configuration_snapshot = dict(snapshot)
    return snapshot


async def _request_spot_diagnostic_output(client: httpx.AsyncClient, param: str) -> tuple[str, str]:
    url = _resolve_spot_output_url(param)
    response = await client.get(url)
    response.raise_for_status()
    return param, response.text.strip()[:_SPOT_DIAGNOSTIC_TEXT_MAX_CHARS]


def _diagnostic_exception_field_status(exc: BaseException) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPError):
        return "http_error"
    return "parse_error"


def _diagnostic_value_field_status(param: str, value: str) -> str:
    text = value.strip()
    if not text:
        return "missing"
    if param == "appnumber":
        return "success"
    if param == "alarmstatus":
        try:
            parsed = int(text, 0)
        except ValueError:
            normalized = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
            return "success" if normalized in {"low_signal", "lowsignal"} else "parse_error"
        return "success" if 0 <= parsed <= 255 else "parse_error"
    try:
        parsed_float = float(text.rstrip("%").strip())
    except ValueError:
        return "parse_error"
    if not math.isfinite(parsed_float):
        return "parse_error"
    if param == "signalpc" and not 0.0 <= parsed_float <= 100.0:
        return "parse_error"
    return "success"


def _next_spot_diagnostics_snapshot_id() -> str:
    global _spot_diagnostics_seq

    with _spot_diagnostics_lock:
        _spot_diagnostics_seq += 1
        return f"{_spot_service_instance_id}:diag:{_spot_diagnostics_seq}"


async def _refresh_spot_diagnostics(
    client: httpx.AsyncClient,
    poll_context: SpotPollContext | None = None,
    *,
    collection_mode: str = _SPOT_DIAGNOSTICS_COLLECTION_MODE,
) -> None:
    global _spot_diagnostics_last_error_code
    global _spot_diagnostics_last_error_message
    global _spot_diagnostics_snapshot

    results = await asyncio.gather(
        *(_request_spot_diagnostic_output(client, param) for param in _SPOT_DIAGNOSTIC_OUTPUT_PARAMS),
        return_exceptions=True,
    )
    payload: Dict[str, Any] = {}
    errors: list[str] = []
    field_status: dict[str, str] = {}
    for param, result in zip(_SPOT_DIAGNOSTIC_OUTPUT_PARAMS, results, strict=True):
        if isinstance(result, BaseException):
            field_status[param] = _diagnostic_exception_field_status(result)
            errors.append(f"{result.__class__.__name__}: {_format_exception_message(result)}")
            continue
        key, value = result
        status = _diagnostic_value_field_status(key, value)
        field_status[key] = status
        if status == "success":
            payload[key] = value
        else:
            errors.append(f"{key}:{status}")

    captured_at = time.time()
    captured_monotonic = time.monotonic()
    missing_fields = tuple(
        field for field in _SPOT_DIAGNOSTIC_OUTPUT_PARAMS if field_status.get(field) != "success"
    )
    if not payload:
        capture_status = "error"
    elif missing_fields:
        capture_status = "async_partial"
    else:
        capture_status = "async_complete"
    snapshot = DiagnosticSnapshot(
        snapshot_id=_next_spot_diagnostics_snapshot_id(),
        source_poll_seq=poll_context.poll_seq if poll_context is not None else None,
        captured_at=_epoch_to_utc_iso(captured_at) or "",
        captured_at_epoch=captured_at,
        captured_monotonic=captured_monotonic,
        capture_status=capture_status,
        collection_mode=collection_mode,
        source="spot_output_parameter_get",
        values=payload,
        field_status=field_status,
        missing_fields=missing_fields,
    ).as_payload(diagnostics_max_age_ms=_spot_diagnostics_max_age_sec() * 1000.0)
    with _spot_diagnostics_lock:
        _spot_diagnostics_snapshot = snapshot
        _spot_diagnostics_last_error_code = "spot-diagnostics-fetch-error" if errors else None
        _spot_diagnostics_last_error_message = "; ".join(errors)[:512] if errors else None


async def _refresh_spot_diagnostics_safely(
    client: httpx.AsyncClient,
    logger: Any,
    poll_context: SpotPollContext | None = None,
    *,
    collection_mode: str = _SPOT_DIAGNOSTICS_COLLECTION_MODE,
) -> None:
    try:
        await _refresh_spot_diagnostics(client, poll_context, collection_mode=collection_mode)
    except Exception as exc:
        global _spot_diagnostics_last_error_code
        global _spot_diagnostics_last_error_message
        global _spot_diagnostics_snapshot
        captured_at = time.time()
        captured_monotonic = time.monotonic()
        failed_status = _diagnostic_exception_field_status(exc)
        snapshot = DiagnosticSnapshot(
            snapshot_id=_next_spot_diagnostics_snapshot_id(),
            source_poll_seq=poll_context.poll_seq if poll_context is not None else None,
            captured_at=_epoch_to_utc_iso(captured_at) or "",
            captured_at_epoch=captured_at,
            captured_monotonic=captured_monotonic,
            capture_status="error",
            collection_mode=collection_mode,
            source="spot_output_parameter_get",
            values={},
            field_status={field: failed_status for field in _SPOT_DIAGNOSTIC_OUTPUT_PARAMS},
            missing_fields=tuple(_SPOT_DIAGNOSTIC_OUTPUT_PARAMS),
        ).as_payload(diagnostics_max_age_ms=_spot_diagnostics_max_age_sec() * 1000.0)
        with _spot_diagnostics_lock:
            _spot_diagnostics_snapshot = snapshot
            _spot_diagnostics_last_error_code = "spot-diagnostics-fetch-error"
            _spot_diagnostics_last_error_message = _format_exception_message(exc)[:512]
        logger.warning(
            "Spot diagnostics fetch failed",
            extra={"code": "spot-diagnostics-fetch-error", "error": _format_exception_message(exc)},
        )


async def _request_spot_image_from_url(client: httpx.AsyncClient, image_url: str) -> bytes:
    try:
        response = await client.get(image_url)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise SpotImageFetchError(
            "upstream-timeout",
            (
                "SPOT image upstream timed out; "
                f"url={image_url}; error_type={exc.__class__.__name__}; "
                f"error={_format_exception_message(exc)}"
            ),
            image_url=image_url,
            upstream_status=None,
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise SpotImageFetchError(
            "upstream-http-error",
            (
                f"SPOT image upstream returned HTTP {exc.response.status_code}; "
                f"url={image_url}; body={_response_body_preview(exc.response, 200)}"
            ),
            image_url=image_url,
            upstream_status=exc.response.status_code,
        ) from exc
    except httpx.RequestError as exc:
        raise SpotImageFetchError(
            "upstream-request-error",
            (
                "SPOT image upstream request failed; "
                f"url={image_url}; error_type={exc.__class__.__name__}; "
                f"error={_format_exception_message(exc)}"
            ),
            image_url=image_url,
            upstream_status=None,
        ) from exc

    data = response.content
    if not data:
        raise SpotImageFetchError(
            "empty-body",
            f"SPOT image upstream returned an empty body; url={image_url}",
            image_url=image_url,
            upstream_status=response.status_code,
        )
    _validate_spot_image_response(response, image_url, data)
    return data


async def _request_spot_image(client: httpx.AsyncClient, image_url: str) -> bytes:
    candidates = _resolve_spot_image_url_candidates(image_url)
    if len(candidates) == 1:
        return await _request_spot_image_from_url(client, candidates[0])

    last_error: Optional[SpotImageFetchError] = None
    for index, candidate in enumerate(candidates):
        try:
            payload = await _request_spot_image_from_url(client, candidate)
            if index > 0:
                _logger.warning(
                    "SPOT image endpoint fallback succeeded",
                    extra={
                        "configured_image_url": image_url,
                        "resolved_image_url": candidate,
                        "attempted_paths": candidates,
                    },
                )
            return payload
        except SpotImageFetchError as exc:
            last_error = exc
            if _is_retryable_spot_image_error(exc, index < len(candidates) - 1):
                _logger.warning(
                    "SPOT image endpoint candidate failed",
                    extra={
                        "configured_image_url": image_url,
                        "attempted_image_url": candidate,
                        "next_candidate": candidates[index + 1],
                        "attempt": index + 1,
                        "max_attempts": len(candidates),
                        "error_code": exc.code,
                        "upstream_status": exc.upstream_status,
                    },
                )
                continue
            break

    if last_error is None:
        last_error = SpotImageFetchError(
            "upstream-request-error",
            "SPOT image upstream failed for all configured endpoint candidates",
            image_url=image_url,
            upstream_status=None,
        )
    raise last_error


async def _request_spot_temperature_observation(
    client: httpx.AsyncClient,
    temp_url: str,
) -> tuple[float, SpotRawClassification]:
    try:
        response = await client.get(temp_url)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.TIMEOUT,
            body=None,
            error_code="temperature-upstream-timeout",
        )
        raise SpotTemperatureFetchError(
            "temperature-upstream-timeout",
            (
                "SPOT temperature upstream timed out; "
                f"url={temp_url}; error_type={exc.__class__.__name__}; "
                f"error={_format_exception_message(exc)}"
            ),
            temp_url=temp_url,
            upstream_status=None,
            raw_classification=classification,
        ) from exc
    except httpx.HTTPStatusError as exc:
        raw_body = exc.response.content
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.HTTP_ERROR,
            body=raw_body,
            http_status_code=exc.response.status_code,
            error_code="temperature-upstream-http-error",
        )
        raise SpotTemperatureFetchError(
            "temperature-upstream-http-error",
            (
                f"SPOT temperature upstream returned HTTP {exc.response.status_code}; "
                f"url={temp_url}; body={_response_body_preview(exc.response, 200)}"
            ),
            temp_url=temp_url,
            upstream_status=exc.response.status_code,
            raw_body=raw_body,
            raw_classification=classification,
        ) from exc
    except httpx.RequestError as exc:
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.CONNECTION_ERROR,
            body=None,
            error_code="temperature-upstream-request-error",
        )
        raise SpotTemperatureFetchError(
            "temperature-upstream-request-error",
            (
                "SPOT temperature upstream request failed; "
                f"url={temp_url}; error_type={exc.__class__.__name__}; "
                f"error={_format_exception_message(exc)}"
            ),
            temp_url=temp_url,
            upstream_status=None,
            raw_classification=classification,
        ) from exc

    classification = classify_spot_raw_response(
        poll_status=SpotPollStatus.SUCCESS,
        body=response.content,
        http_status_code=response.status_code,
        verified_no_target_values=_SPOT_VERIFIED_NO_TARGET_VALUES,
        invalid_sentinel_values=_SPOT_INVALID_SENTINEL_VALUES,
    )
    if classification.raw_validity == SpotRawValidity.VALID_TEMPERATURE:
        parsed_temperature_c = classification.parsed_temperature_c
        if parsed_temperature_c is None:
            raise SpotTemperatureFetchError(
                "temperature-parse-error",
                "SPOT temperature upstream produced a valid classification without a parsed temperature",
                temp_url=temp_url,
                upstream_status=response.status_code,
                raw_body=response.content,
                raw_classification=classification,
            )
        return float(parsed_temperature_c), classification

    raw_temp = classification.raw_value_text or ""
    if classification.raw_validity == SpotRawValidity.EMPTY_BODY:
        raise SpotTemperatureFetchError(
            "temperature-empty-body",
            f"SPOT temperature upstream returned an empty body; url={temp_url}",
            temp_url=temp_url,
            upstream_status=response.status_code,
            raw_body=response.content,
            raw_classification=classification,
        )
    if classification.raw_validity == SpotRawValidity.PARSE_ERROR:
        raise SpotTemperatureFetchError(
            "temperature-parse-error",
            (
                "SPOT temperature upstream returned a non-numeric body; "
                f"url={temp_url}; body={raw_temp[:200]}"
            ),
            temp_url=temp_url,
            upstream_status=response.status_code,
            raw_body=response.content,
            raw_classification=classification,
        )
    if classification.raw_validity == SpotRawValidity.OUT_OF_RANGE:
        raise SpotTemperatureFetchError(
            "temperature-out-of-range",
            (
                "SPOT temperature upstream returned an out-of-range value; "
                f"url={temp_url}; body={raw_temp[:200]}"
            ),
            temp_url=temp_url,
            upstream_status=response.status_code,
            raw_body=response.content,
            raw_classification=classification,
        )
    if classification.raw_validity == SpotRawValidity.INVALID_SENTINEL:
        raise SpotTemperatureFetchError(
            "temperature-invalid-sentinel",
            (
                "SPOT temperature upstream returned an invalid sentinel; "
                f"url={temp_url}; body={raw_temp[:200]}"
            ),
            temp_url=temp_url,
            upstream_status=response.status_code,
            raw_body=response.content,
            raw_classification=classification,
        )
    if classification.raw_validity == SpotRawValidity.VERIFIED_NO_TARGET:
        raise SpotTemperatureFetchError(
            "temperature-verified-no-target",
            (
                "SPOT temperature upstream returned a verified no-target value; "
                f"url={temp_url}; body={raw_temp[:200]}"
            ),
            temp_url=temp_url,
            upstream_status=response.status_code,
            raw_body=response.content,
            raw_classification=classification,
        )

    raise SpotTemperatureFetchError(
        "temperature-unknown-invalid-response",
        f"SPOT temperature upstream returned an unsupported response; url={temp_url}",
        temp_url=temp_url,
        upstream_status=response.status_code,
        raw_body=response.content,
        raw_classification=classification,
    )


async def _request_spot_temperature(client: httpx.AsyncClient, temp_url: str) -> float:
    temperature, _classification = await _request_spot_temperature_observation(client, temp_url)
    return temperature


async def _request_spot_internal_temperature(client: httpx.AsyncClient, temp_url: str) -> float:
    try:
        return await _request_spot_temperature(client, temp_url)
    except SpotTemperatureFetchError as exc:
        code = exc.code
        if code.startswith("temperature-"):
            code = f"internal-{code}"
        raise SpotInternalTemperatureFetchError(
            code,
            (
                "SPOT internal temperature upstream request failed; "
                f"url={temp_url}; upstream_status={exc.upstream_status}; error={str(exc)}"
            ),
            temp_url=exc.temp_url,
            upstream_status=exc.upstream_status,
        ) from exc


def _record_image_error(code: str, message: str) -> None:
    global _img_last_error
    global _img_last_error_code
    global _img_last_error_message

    _img_last_error = time.time()
    _img_last_error_code = code
    _img_last_error_message = message


def _record_image_success() -> None:
    global _img_failure_count
    global _img_last_error_code
    global _img_last_error_message
    global _img_next_retry_at

    _img_failure_count = 0
    _img_last_error_code = None
    _img_last_error_message = None
    _img_next_retry_at = None


def _record_image_backoff(backoff_sec: float) -> None:
    global _img_next_retry_at

    if backoff_sec <= 0.0:
        _img_next_retry_at = None
        return
    _img_next_retry_at = time.time() + backoff_sec


def _record_live_image_error(code: str, message: str, image_url: str) -> None:
    global _live_img_last_error
    global _live_img_last_error_code
    global _live_img_last_error_message
    global _live_img_last_url

    _live_img_last_error = time.time()
    _live_img_last_error_code = code
    _live_img_last_error_message = message
    _live_img_last_url = image_url


def _record_live_image_success(image_url: str) -> None:
    global _live_img_failure_count
    global _live_img_last_error_code
    global _live_img_last_error_message
    global _live_img_last_url
    global _live_img_next_retry_at

    _live_img_failure_count = 0
    _live_img_last_error_code = None
    _live_img_last_error_message = None
    _live_img_last_url = image_url
    _live_img_next_retry_at = None


def _record_live_image_backoff(backoff_sec: float) -> None:
    global _live_img_next_retry_at

    if backoff_sec <= 0.0:
        _live_img_next_retry_at = None
        return
    _live_img_next_retry_at = time.time() + backoff_sec


def _record_temperature_error(
    code: str,
    message: str,
    temp_url: str,
    upstream_status: Optional[int],
) -> None:
    global _temp_last_error
    global _temp_last_error_code
    global _temp_last_error_message
    global _temp_last_upstream_status
    global _temp_last_url

    _temp_last_error = time.time()
    _temp_last_error_code = code
    _temp_last_error_message = message
    _temp_last_upstream_status = upstream_status
    _temp_last_url = temp_url


def _record_temperature_success(temp_url: str) -> None:
    global _temp_last_error_code
    global _temp_last_error_message
    global _temp_last_upstream_status
    global _temp_last_url
    global _temp_last_success_at

    _temp_last_error_code = None
    _temp_last_error_message = None
    _temp_last_upstream_status = None
    _temp_last_url = temp_url
    _temp_last_success_at = time.time()


def _record_internal_temperature_error(
    code: str,
    message: str,
    temp_url: str,
    upstream_status: Optional[int],
) -> None:
    global _internal_temp_last_error
    global _internal_temp_last_error_code
    global _internal_temp_last_error_message
    global _internal_temp_last_upstream_status
    global _internal_temp_last_url

    _internal_temp_last_error = time.time()
    _internal_temp_last_error_code = code
    _internal_temp_last_error_message = message
    _internal_temp_last_upstream_status = upstream_status
    _internal_temp_last_url = temp_url


def _record_internal_temperature_success(temp_url: str) -> None:
    global _internal_temp_last_error_code
    global _internal_temp_last_error_message
    global _internal_temp_last_upstream_status
    global _internal_temp_last_url
    global _internal_temp_last_success_at

    _internal_temp_last_error_code = None
    _internal_temp_last_error_message = None
    _internal_temp_last_upstream_status = None
    _internal_temp_last_url = temp_url
    _internal_temp_last_success_at = time.time()


def _temperature_cache_age_sec(now: float) -> Optional[float]:
    temp_time = float(_img_cache.get("temp_time") or 0.0)
    if temp_time <= 0.0:
        return None
    return max(0.0, now - temp_time)


def _temperature_cache_status(now: float) -> str:
    age = _temperature_cache_age_sec(now)
    if age is None:
        if _temp_last_error_code:
            return "error"
        return "empty"
    if age > _TEMP_CACHE_TTL_SEC:
        return "stale"
    return "ok"


def _internal_temperature_cache_age_sec(now: float) -> Optional[float]:
    temp_time = float(_internal_temp_cache.get("temp_time") or 0.0)
    if temp_time <= 0.0:
        return None
    return max(0.0, now - temp_time)


def _internal_temperature_cache_status(now: float) -> str:
    age = _internal_temperature_cache_age_sec(now)
    if age is None:
        if _internal_temp_last_error_code:
            return "error"
        return "empty"
    if age > _TEMP_CACHE_TTL_SEC:
        return "stale"
    return "ok"


def _cached_internal_temperature(now: float) -> Optional[float]:
    age = _internal_temperature_cache_age_sec(now)
    if age is None or age > _TEMP_CACHE_TTL_SEC:
        return None
    temperature = _internal_temp_cache.get("temp")
    if isinstance(temperature, bool) or not isinstance(temperature, (float, int)):
        return None
    return float(temperature)


def _epoch_to_utc_iso(value: Optional[float]) -> Optional[str]:
    if not value:
        return None
    return datetime.fromtimestamp(float(value), timezone.utc).isoformat().replace("+00:00", "Z")


def _spot_poll_freshness_threshold_sec() -> float:
    try:
        refresh_interval = float(config.SPOT_REFRESH_INTERVAL or 1.0)
    except (TypeError, ValueError):
        refresh_interval = 1.0
    return max(1.0, refresh_interval * 3.0)


def _begin_spot_temperature_poll() -> SpotPollContext:
    global _spot_poll_seq

    started_at = time.time()
    started_monotonic = time.monotonic()
    with _spot_temperature_snapshot_lock:
        _spot_poll_seq += 1
        poll_seq = _spot_poll_seq
    return SpotPollContext(
        service_instance_id=_spot_service_instance_id,
        poll_seq=poll_seq,
        started_at_epoch=started_at,
        started_monotonic=started_monotonic,
    )


def _completed_poll_clocks() -> tuple[float, float]:
    return time.time(), time.monotonic()


def _poll_status_for_temperature_error_code(code: str) -> SpotPollStatus:
    if "config-missing" in code:
        return SpotPollStatus.CONFIG_MISSING
    if "timeout" in code:
        return SpotPollStatus.TIMEOUT
    if "http-error" in code:
        return SpotPollStatus.HTTP_ERROR
    return SpotPollStatus.CONNECTION_ERROR


def _classification_for_temperature_error(exc: SpotTemperatureFetchError) -> SpotRawClassification:
    if exc.raw_classification is not None:
        return exc.raw_classification
    return classify_spot_raw_response(
        poll_status=_poll_status_for_temperature_error_code(exc.code),
        body=exc.raw_body,
        http_status_code=exc.upstream_status,
        error_code=exc.code,
    )



def _spot_observation_fact_path() -> Path:
    return Path(config.LOG_PATH) / SPOT_OBSERVATION_FACT_FILENAME


def _get_spot_observation_fact_writer() -> SpotObservationFactWriter:
    global _spot_observation_fact_writer

    if _spot_observation_fact_writer is None:
        _spot_observation_fact_writer = SpotObservationFactWriter(_spot_observation_fact_path())
    return _spot_observation_fact_writer


def _write_spot_observation_fact_safely(snapshot: Dict[str, Any]) -> None:
    if not bool(getattr(config, "SPOT_OBSERVATION_FACT_ENABLED", False)):
        return
    try:
        _get_spot_observation_fact_writer().write_fact(snapshot)
    except Exception:
        writer = _get_spot_observation_fact_writer()
        writer.failure_count += 1


def get_spot_observation_fact_health() -> Dict[str, Any]:
    writer = _spot_observation_fact_writer
    with _spot_diagnostics_lock:
        diagnostics_status = (
            str(_spot_diagnostics_snapshot.get("diagnostics_capture_status"))
            if _spot_diagnostics_snapshot is not None
            else "missing"
        )
    with _spot_temperature_snapshot_lock:
        diagnostics_binding_status = (
            str(_spot_temperature_snapshot.get("diagnostics_binding_status"))
            if _spot_temperature_snapshot is not None
            else "missing"
        )
    with _spot_config_provenance_lock:
        config_snapshot = dict(_spot_last_configuration_snapshot or {})
        config_drift_detected_count = _spot_config_drift_detected_count
    return {
        "enabled": bool(getattr(config, "SPOT_OBSERVATION_FACT_ENABLED", False)),
        "write_failure_count": int(writer.failure_count) if writer is not None else 0,
        "spool_pending_count": int(writer.spool_pending_count()) if writer is not None else 0,
        "diagnostics_capture_status": diagnostics_status,
        "diagnostics_binding_status": diagnostics_binding_status,
        "diagnostics_last_error_code": _spot_diagnostics_last_error_code,
        "diagnostics_last_error_message": _spot_diagnostics_last_error_message,
        "config_drift_detected_count": config_drift_detected_count,
        "config_operator_verified": bool(config_snapshot.get("config_operator_verified", False)),
        "config_attestation_status": str(
            config_snapshot.get("config_attestation_status") or "not_observed"
        ),
        "device_config_readback_status": str(
            config_snapshot.get("device_config_readback_status") or "not_observed"
        ),
    }


def _missing_spot_diagnostics_payload() -> Dict[str, Any]:
    return {
        "diagnostics_capture_status": "missing",
        "diagnostics_collection_mode": _SPOT_DIAGNOSTICS_COLLECTION_MODE,
        "diagnostics_source": "spot_output_parameter_get",
        "diagnostics_binding_status": "missing",
        "diagnostics_age_ms": "",
        "diagnostics_max_age_ms": _spot_diagnostics_max_age_sec() * 1000.0,
        "diagnostics_field_status": {
            field: "not_requested" for field in _SPOT_DIAGNOSTIC_OUTPUT_PARAMS
        },
        "diagnostics_missing_fields": list(_SPOT_DIAGNOSTIC_OUTPUT_PARAMS),
    }


def _latest_spot_diagnostics_for_poll(
    *,
    poll_seq: int,
    poll_completed_at: float,
    poll_completed_monotonic: float,
) -> Dict[str, Any]:
    with _spot_diagnostics_lock:
        snapshot = dict(_spot_diagnostics_snapshot) if _spot_diagnostics_snapshot is not None else None
    if snapshot is None:
        return _missing_spot_diagnostics_payload()

    captured_epoch = snapshot.get("_diagnostics_captured_at_epoch")
    captured_monotonic = snapshot.get("_diagnostics_captured_monotonic")
    age_sec: float | None = None
    if isinstance(captured_monotonic, (float, int)):
        age_sec = poll_completed_monotonic - float(captured_monotonic)
    elif isinstance(captured_epoch, (float, int)) and captured_epoch > 0:
        age_sec = poll_completed_at - float(captured_epoch)

    source_poll_seq = snapshot.get("diagnostics_source_poll_seq")
    if not isinstance(source_poll_seq, int) or source_poll_seq <= 0:
        binding_status = "unbound"
    elif source_poll_seq < poll_seq:
        binding_status = "previous_poll"
    elif source_poll_seq > poll_seq:
        binding_status = "future_clock"
    else:
        binding_status = "same_poll"
    if age_sec is not None and age_sec < 0:
        binding_status = "future_clock"

    payload = {key: value for key, value in snapshot.items() if not key.startswith("_")}
    payload["_diagnostics_captured_at_epoch"] = captured_epoch
    payload["_diagnostics_captured_monotonic"] = captured_monotonic
    payload["diagnostics_binding_status"] = binding_status
    payload["diagnostics_age_ms"] = (
        f"{age_sec * 1000.0:.3f}" if age_sec is not None and age_sec >= 0 else ""
    )
    return payload


def _publish_spot_temperature_snapshot(
    *,
    poll_seq: int,
    poll_started_at: float,
    poll_completed_at: float,
    temp_url: str,
    classification: SpotRawClassification,
    poll_completed_monotonic: Optional[float] = None,
) -> None:
    global _spot_observation_seq
    global _spot_temperature_snapshot
    global _spot_last_valid_value_at
    global _spot_last_valid_value_monotonic
    global _spot_temperature_cache_suppressed_until_valid

    if classification.raw_validity == SpotRawValidity.VERIFIED_NO_TARGET:
        _img_cache["temp"] = 0.0
        _img_cache["temp_time"] = 0.0

    raw_value_text = classification.raw_value_text
    if classification.raw_validity == SpotRawValidity.NOT_EVALUATED:
        raw_value_text = None
    configuration_payload = _spot_configuration_snapshot()
    internal_temperature = _cached_internal_temperature(poll_completed_at)
    effective_completed_monotonic = poll_completed_monotonic
    if effective_completed_monotonic is None:
        effective_completed_monotonic = time.monotonic()
    diagnostics_payload = _latest_spot_diagnostics_for_poll(
        poll_seq=poll_seq,
        poll_completed_at=poll_completed_at,
        poll_completed_monotonic=effective_completed_monotonic,
    )

    with _spot_temperature_snapshot_lock:
        _spot_observation_seq += 1
        observation_seq = _spot_observation_seq
        if classification.raw_validity == SpotRawValidity.VALID_TEMPERATURE:
            _spot_last_valid_value_at = poll_completed_at
            _spot_last_valid_value_monotonic = effective_completed_monotonic
            _spot_temperature_cache_suppressed_until_valid = False
        elif classification.raw_validity == SpotRawValidity.INVALID_SENTINEL:
            _spot_temperature_cache_suppressed_until_valid = True
        elif classification.raw_validity == SpotRawValidity.VERIFIED_NO_TARGET:
            _spot_last_valid_value_at = None
            _spot_last_valid_value_monotonic = None
            _spot_temperature_cache_suppressed_until_valid = False

        cache_fallback_allowed = classification.cache_fallback_allowed
        if _spot_temperature_cache_suppressed_until_valid and classification.poll_status in {
            SpotPollStatus.TIMEOUT,
            SpotPollStatus.CONNECTION_ERROR,
            SpotPollStatus.HTTP_ERROR,
        }:
            cache_fallback_allowed = False

        _spot_temperature_snapshot = {
            "spot_service_instance_id": _spot_service_instance_id,
            "spot_service_started_at": _spot_service_started_at,
            "spot_poll_seq": poll_seq,
            "spot_observation_seq": observation_seq,
            "spot_poll_status": classification.poll_status.value,
            "spot_raw_validity": classification.raw_validity.value,
            "spot_raw_value_text": raw_value_text,
            "spot_temperature_observed_c": classification.parsed_temperature_c,
            "spot_last_poll_started_at": _epoch_to_utc_iso(poll_started_at),
            "spot_last_poll_completed_at": _epoch_to_utc_iso(poll_completed_at),
            "_spot_last_poll_completed_at_epoch": poll_completed_at,
            "_spot_last_poll_completed_monotonic": effective_completed_monotonic,
            "spot_poll_duration_ms": max(0.0, (poll_completed_at - poll_started_at) * 1000.0),
            "spot_http_status_code": classification.http_status_code,
            "spot_response_content_length": classification.response_content_length,
            "spot_raw_payload_hash": classification.raw_payload_hash,
            "spot_device_status_code": classification.device_status_code,
            "spot_error_code": classification.error_code,
            "cache_fallback_allowed": cache_fallback_allowed,
            "spot_temperature_url": temp_url,
        }
        _spot_temperature_snapshot.update(configuration_payload)
        if internal_temperature is not None:
            _spot_temperature_snapshot["itemperature"] = internal_temperature
        _spot_temperature_snapshot.update(diagnostics_payload)
        _spot_temperature_snapshot["spot_diagnostic_evidence_codes"] = encode_spot_diagnostic_evidence_codes(
            _spot_temperature_snapshot
        )
        snapshot_for_fact = dict(_spot_temperature_snapshot)
    _write_spot_observation_fact_safely(snapshot_for_fact)


def get_spot_temperature_poll_snapshot() -> Optional[Dict[str, Any]]:
    with _spot_temperature_snapshot_lock:
        if _spot_temperature_snapshot is None:
            return None
        return dict(_spot_temperature_snapshot)


def _spot_source_freshness_for_snapshot(
    snapshot: Optional[Dict[str, Any]],
    now: float,
    now_monotonic: Optional[float] = None,
) -> SpotSourceFreshness:
    if snapshot is None:
        return SpotSourceFreshness.UNKNOWN
    completed_monotonic = _positive_float_or_none(snapshot.get("_spot_last_poll_completed_monotonic"))
    if completed_monotonic is not None and now_monotonic is not None:
        age_sec = now_monotonic - completed_monotonic
        if age_sec < 0:
            return SpotSourceFreshness.UNKNOWN
        if age_sec > _spot_poll_freshness_threshold_sec():
            return SpotSourceFreshness.STALE
        return SpotSourceFreshness.FRESH
    completed_at = snapshot.get("_spot_last_poll_completed_at_epoch")
    if not isinstance(completed_at, (float, int)) or completed_at <= 0:
        return SpotSourceFreshness.UNKNOWN
    if now - float(completed_at) > _spot_poll_freshness_threshold_sec():
        return SpotSourceFreshness.STALE
    return SpotSourceFreshness.FRESH


def _positive_float_or_none(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _effective_spot_temperature_for_decision(decision: TemperatureStateDecision) -> Optional[float]:
    if decision.temperature_value_origin.value == "none":
        return None
    temperature = _img_cache.get("temp")
    if isinstance(temperature, bool) or not isinstance(temperature, (float, int)):
        return None
    return float(temperature)


def _build_spot_temperature_snapshot_diagnostics(now: float) -> Dict[str, Any]:
    now_monotonic = time.monotonic()
    with _spot_temperature_snapshot_lock:
        snapshot = dict(_spot_temperature_snapshot) if _spot_temperature_snapshot is not None else None
        poll_seq = _spot_poll_seq
        observation_seq = _spot_observation_seq
        last_valid_value_at = _spot_last_valid_value_at
        last_valid_value_monotonic = _spot_last_valid_value_monotonic

    if snapshot is None:
        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=SpotPollStatus.NOT_ATTEMPTED,
                raw_validity=SpotRawValidity.NOT_RECEIVED,
                source_freshness=SpotSourceFreshness.UNKNOWN,
                cache_fallback_allowed=False,
                first_poll_completed=False,
            )
        )
        target = derive_spot_target_observed_shadow(
            SpotRawValidity.NOT_RECEIVED,
            SpotSourceFreshness.UNKNOWN,
        )
        return {
            "spot_service_instance_id": _spot_service_instance_id,
            "spot_service_started_at": _spot_service_started_at,
            "spot_poll_seq": poll_seq,
            "spot_observation_seq": observation_seq,
            "spot_poll_status": SpotPollStatus.NOT_ATTEMPTED.value,
            "spot_raw_validity": SpotRawValidity.NOT_RECEIVED.value,
            "spot_source_freshness": SpotSourceFreshness.UNKNOWN.value,
            "spot_target_state_observed_shadow": target.state.value,
            "spot_target_state_observed_source": target.source.value,
            "temperature_status_shadow": decision.temperature_status_shadow.value,
            "spot_cache_status": decision.spot_cache_status.value,
            "temperature_value_origin": decision.temperature_value_origin.value,
            "spot_temperature_effective_c": None,
            "spot_temperature_observed_c": None,
            "spot_last_valid_value_at": None,
            "spot_last_valid_value_monotonic": None,
            "spot_value_age_ms": None,
            "spot_snapshot_age_ms": None,
            "spot_last_poll_started_at": None,
            "spot_last_poll_completed_at": None,
            "spot_last_poll_completed_monotonic": None,
            "spot_poll_freshness_threshold_sec": _spot_poll_freshness_threshold_sec(),
            "spot_cache_expiry_threshold_sec": _TEMP_CACHE_TTL_SEC,
            "cache_fallback_allowed": False,
            "spot_http_status_code": None,
            "spot_poll_duration_ms": None,
            "spot_response_content_length": None,
            "spot_raw_payload_hash": None,
            "spot_device_status_code": None,
            "spot_error_code": None,
        }

    source_freshness = _spot_source_freshness_for_snapshot(snapshot, now, now_monotonic)
    poll_status = SpotPollStatus(str(snapshot["spot_poll_status"]))
    raw_validity = SpotRawValidity(str(snapshot["spot_raw_validity"]))
    cache_age = _temperature_cache_age_sec(now)
    has_ttl_valid_cache = cache_age is not None and cache_age <= _TEMP_CACHE_TTL_SEC
    has_previous_valid_value = last_valid_value_at is not None
    decision = derive_temperature_state(
        TemperatureStateInput(
            poll_status=poll_status,
            raw_validity=raw_validity,
            source_freshness=source_freshness,
            cache_fallback_allowed=bool(snapshot.get("cache_fallback_allowed")),
            has_ttl_valid_cache=has_ttl_valid_cache,
            has_previous_valid_value=has_previous_valid_value,
            first_poll_completed=True,
        )
    )
    target = derive_spot_target_observed_shadow(raw_validity, source_freshness)
    completed_at = snapshot.get("_spot_last_poll_completed_at_epoch")
    completed_monotonic = _positive_float_or_none(snapshot.get("_spot_last_poll_completed_monotonic"))
    snapshot_age_ms = None
    if completed_monotonic is not None:
        snapshot_age_ms = max(0.0, (now_monotonic - completed_monotonic) * 1000.0)
    elif isinstance(completed_at, (float, int)) and completed_at > 0:
        snapshot_age_ms = max(0.0, (now - float(completed_at)) * 1000.0)
    value_age_ms = None
    if last_valid_value_at is not None:
        value_age_ms = max(0.0, (now - float(last_valid_value_at)) * 1000.0)

    payload = {k: v for k, v in snapshot.items() if not k.startswith("_")}
    diagnostics_captured_monotonic = _positive_float_or_none(
        snapshot.get("_diagnostics_captured_monotonic")
    )
    diagnostics_captured_epoch = _positive_float_or_none(
        snapshot.get("_diagnostics_captured_at_epoch")
    )
    diagnostics_age_sec: float | None = None
    if diagnostics_captured_monotonic is not None:
        diagnostics_age_sec = now_monotonic - diagnostics_captured_monotonic
    elif diagnostics_captured_epoch is not None:
        diagnostics_age_sec = now - diagnostics_captured_epoch
    if diagnostics_age_sec is not None:
        if diagnostics_age_sec < 0:
            payload["diagnostics_binding_status"] = "future_clock"
            payload["diagnostics_age_ms"] = ""
        else:
            payload["diagnostics_age_ms"] = f"{diagnostics_age_sec * 1000.0:.3f}"
    payload.update(
        {
            "spot_source_freshness": source_freshness.value,
            "spot_target_state_observed_shadow": target.state.value,
            "spot_target_state_observed_source": target.source.value,
            "temperature_status_shadow": decision.temperature_status_shadow.value,
            "spot_cache_status": decision.spot_cache_status.value,
            "temperature_value_origin": decision.temperature_value_origin.value,
            "spot_temperature_effective_c": _effective_spot_temperature_for_decision(decision),
            "spot_last_valid_value_at": _epoch_to_utc_iso(last_valid_value_at),
            "spot_last_valid_value_monotonic": last_valid_value_monotonic,
            "spot_value_age_ms": value_age_ms,
            "spot_snapshot_age_ms": snapshot_age_ms,
            "spot_last_poll_completed_monotonic": completed_monotonic,
            "spot_poll_freshness_threshold_sec": _spot_poll_freshness_threshold_sec(),
            "spot_cache_expiry_threshold_sec": _TEMP_CACHE_TTL_SEC,
        }
    )
    return payload

def _schedule_spot_diagnostics_for_poll(
    client: httpx.AsyncClient,
    poll_context: SpotPollContext,
) -> None:
    global _spot_diagnostics_prefetch_task

    if _spot_diagnostics_prefetch_task is not None and not _spot_diagnostics_prefetch_task.done():
        return
    _spot_diagnostics_prefetch_task = asyncio.create_task(
        _refresh_spot_diagnostics_safely(
            client,
            _logger,
            poll_context,
            collection_mode=_SPOT_DIAGNOSTICS_COLLECTION_MODE,
        )
    )


async def _refresh_spot_temperature(
    client: httpx.AsyncClient,
    *,
    schedule_diagnostics: bool = False,
) -> None:
    poll_context = _begin_spot_temperature_poll()
    poll_seq = poll_context.poll_seq
    poll_started_at = poll_context.started_at_epoch
    if schedule_diagnostics:
        _schedule_spot_diagnostics_for_poll(client, poll_context)
    try:
        temp_url = _resolve_spot_temperature_url()
    except SpotTemperatureConfigError as exc:
        poll_completed_at, poll_completed_monotonic = _completed_poll_clocks()
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.CONFIG_MISSING,
            body=None,
            error_code="temperature-config-missing",
        )
        _publish_spot_temperature_snapshot(
            poll_seq=poll_seq,
            poll_started_at=poll_started_at,
            poll_completed_at=poll_completed_at,
            poll_completed_monotonic=poll_completed_monotonic,
            temp_url=exc.temp_url,
            classification=classification,
        )
        raise

    try:
        temperature, classification = await _request_spot_temperature_observation(client, temp_url)
    except SpotTemperatureFetchError as exc:
        poll_completed_at, poll_completed_monotonic = _completed_poll_clocks()
        _publish_spot_temperature_snapshot(
            poll_seq=poll_seq,
            poll_started_at=poll_started_at,
            poll_completed_at=poll_completed_at,
            poll_completed_monotonic=poll_completed_monotonic,
            temp_url=exc.temp_url,
            classification=_classification_for_temperature_error(exc),
        )
        raise

    poll_completed_at, poll_completed_monotonic = _completed_poll_clocks()
    _img_cache["temp"] = temperature
    _img_cache["temp_time"] = poll_completed_at
    _record_temperature_success(temp_url)
    _publish_spot_temperature_snapshot(
        poll_seq=poll_seq,
        poll_started_at=poll_started_at,
        poll_completed_at=poll_completed_at,
        poll_completed_monotonic=poll_completed_monotonic,
        temp_url=temp_url,
        classification=classification,
    )


async def _refresh_spot_internal_temperature(client: httpx.AsyncClient) -> None:
    temp_url = _resolve_spot_internal_temperature_url()
    temperature = await _request_spot_internal_temperature(client, temp_url)
    _internal_temp_cache["temp"] = temperature
    _internal_temp_cache["temp_time"] = time.time()
    _record_internal_temperature_success(temp_url)


async def _refresh_spot_internal_temperature_safely(client: httpx.AsyncClient, logger: Any) -> None:
    try:
        await _refresh_spot_internal_temperature(client)
    except SpotInternalTemperatureConfigError as exc:
        _record_internal_temperature_error(
            "internal-temperature-config-missing",
            str(exc),
            exc.temp_url,
            None,
        )
        logger.warning(
            "Spot internal temperature fetch misconfigured",
            extra={
                "code": "internal-temperature-config-missing",
                "temp_url": exc.temp_url,
                "error": str(exc),
            },
        )
    except SpotInternalTemperatureFetchError as exc:
        _record_internal_temperature_error(exc.code, str(exc), exc.temp_url, exc.upstream_status)
        logger.warning(
            "Spot internal temperature fetch failed",
            extra={
                "code": exc.code,
                "temp_url": exc.temp_url,
                "upstream_status": exc.upstream_status,
                "error": str(exc),
            },
        )


def get_image_proxy_diagnostics() -> Dict[str, Any]:
    now = time.time()
    cached_image = _cached_image_data()
    cache_age = _cache_age_sec(now) if cached_image is not None else None
    cache_status = _cache_status(now)
    retry_after = _retry_after_sec(now)
    payload = {
        "cache_state": _cache_state_for_status(cache_status),
        "cache_status": cache_status,
        "image_status": _image_status_for_cache_status(cache_status),
        "proxy_state": _image_proxy_state(now),
        "last_cache_state": str(_img_cache_state),
        "failure_count": int(_img_failure_count),
        "last_error_at": float(_img_last_error) if _img_last_error else None,
        "last_error_code": _img_last_error_code,
        "last_error_message": _img_last_error_message,
        "image_url_configured": bool(str(config.SPOT_IMAGE_URL or "").strip()),
        "has_cached_image": cached_image is not None,
        "cache_captured_at": float(_img_cache.get("time") or 0.0) if cached_image is not None else None,
        "cache_age_sec": cache_age,
        "max_stale_age_sec": _max_stale_age_sec(),
        "current_backoff_sec": _current_backoff_sec(),
        "next_retry_at": _img_next_retry_at,
        "retry_after_sec": retry_after,
        "temperature_url_configured": bool(str(config.SPOT_URL or "").strip()),
        "temperature_cache_status": _temperature_cache_status(now),
        "temperature_cache_age_sec": _temperature_cache_age_sec(now),
        "temperature_last_success_at": float(_temp_last_success_at) if _temp_last_success_at else None,
        "temperature_last_error_at": float(_temp_last_error) if _temp_last_error else None,
        "temperature_last_error_code": _temp_last_error_code,
        "temperature_last_error_message": _temp_last_error_message,
        "temperature_last_upstream_status": _temp_last_upstream_status,
        "temperature_last_url": _temp_last_url,
    }
    payload.update(_build_spot_temperature_snapshot_diagnostics(now))
    payload.update(_build_internal_temperature_diagnostics(now, include_cached_at=False))
    return payload


def get_spot_internal_temperature_diagnostics() -> Dict[str, Any]:
    return _build_internal_temperature_diagnostics(time.time(), include_cached_at=True)


def get_live_image_diagnostics() -> Dict[str, Any]:
    now = time.time()
    cached_at = float(_live_img_cache.get("time") or 0.0)
    return {
        "live_image_url": _live_img_last_url or str(getattr(config, "SPOT_LIVE_IMAGE_URL", "") or ""),
        "live_cache_age_sec": max(0.0, now - cached_at) if cached_at else None,
        "live_failure_count": int(_live_img_failure_count),
        "live_last_error": float(_live_img_last_error) if _live_img_last_error else None,
        "live_last_error_code": _live_img_last_error_code,
        "live_last_error_message": _live_img_last_error_message,
        "live_next_retry_at": _live_img_next_retry_at,
        "live_retry_after_sec": _live_retry_after_sec(now),
        "live_current_backoff_sec": _current_live_backoff_sec(),
    }


def _cache_payload_bytes(value: Any) -> int:
    if isinstance(value, (bytes, bytearray)):
        return len(value)
    return 0


def _cache_age_for_payload(cached_at: Any, now: float, bytes_value: int) -> Optional[float]:
    if bytes_value <= 0:
        return None
    try:
        captured_at = float(cached_at or 0.0)
    except (TypeError, ValueError):
        return None
    if captured_at <= 0.0:
        return None
    return max(0.0, now - captured_at)


def _live_image_cache_state(now: float, live_image_bytes: int) -> str:
    if live_image_bytes <= 0:
        return "empty"
    cached_at = float(_live_img_cache.get("time") or 0.0)
    if cached_at <= 0.0:
        return "empty"
    if now - cached_at > _LIVE_IMG_SHARED_FRAME_TTL_SEC:
        return "stale"
    return "fresh"


def get_image_cache_memory_summary() -> Dict[str, Any]:
    now = time.time()
    image_bytes = _cache_payload_bytes(_img_cache.get("data"))
    live_image_bytes = _cache_payload_bytes(_live_img_cache.get("data"))
    image_cache_status = _cache_status(now)
    live_image_cache_state = _live_image_cache_state(now, live_image_bytes)
    live_image_url_present = any(
        str(value or "").strip()
        for value in (
            _live_img_cache.get("url"),
            _live_img_last_url,
            getattr(config, "SPOT_LIVE_IMAGE_URL", ""),
            getattr(config, "SPOT_IMAGE_URL", ""),
        )
    )
    return {
        "image_bytes": image_bytes,
        "image_age_sec": _cache_age_for_payload(_img_cache.get("time"), now, image_bytes),
        "image_cache_state": _cache_state_for_status(image_cache_status),
        "image_cache_status": image_cache_status,
        "image_failure_count": int(_img_failure_count),
        "image_next_retry_at": _img_next_retry_at,
        "image_retry_after_sec": _retry_after_sec(now),
        "image_current_backoff_sec": _current_backoff_sec(),
        "live_image_bytes": live_image_bytes,
        "live_image_age_sec": _cache_age_for_payload(_live_img_cache.get("time"), now, live_image_bytes),
        "live_image_cache_state": live_image_cache_state,
        "live_image_url_present": bool(live_image_url_present),
        "live_image_failure_count": int(_live_img_failure_count),
        "live_image_next_retry_at": _live_img_next_retry_at,
        "live_image_retry_after_sec": _live_retry_after_sec(now),
        "live_image_current_backoff_sec": _current_live_backoff_sec(),
        "total_bytes": image_bytes + live_image_bytes,
    }


def _build_internal_temperature_diagnostics(now: float, *, include_cached_at: bool) -> Dict[str, Any]:
    internal_temperature = _cached_internal_temperature(now)
    internal_temperature_at = float(_internal_temp_cache.get("temp_time") or 0.0)
    payload = {
        "internal_temperature_url_configured": bool(str(config.SPOT_INTERNAL_TEMPERATURE_URL or "").strip()),
        "internal_temperature": internal_temperature,
        "internal_temperature_at": internal_temperature_at if internal_temperature is not None else None,
        "internal_temperature_cache_status": _internal_temperature_cache_status(now),
        "internal_temperature_cache_age_sec": _internal_temperature_cache_age_sec(now),
        "internal_temperature_last_success_at": (
            float(_internal_temp_last_success_at) if _internal_temp_last_success_at else None
        ),
        "internal_temperature_last_error_at": (
            float(_internal_temp_last_error) if _internal_temp_last_error else None
        ),
        "internal_temperature_last_error_code": _internal_temp_last_error_code,
        "internal_temperature_last_error_message": _internal_temp_last_error_message,
        "internal_temperature_last_upstream_status": _internal_temp_last_upstream_status,
        "internal_temperature_last_url": _internal_temp_last_url,
    }
    if include_cached_at:
        payload["internal_temperature_cached_at"] = (
            float(_internal_temp_cache.get("temp_time") or 0.0)
            if _internal_temp_cache.get("temp_time")
            else None
        )
    return payload


def _get_http_client() -> httpx.AsyncClient:
    """?⑤벊? ??쑬猷욄묾?HTTP ?????곷섧?紐? 筌왖???λ뜃由?酉鍮?獄쏆꼹???뺣뼄."""
    global _http_client
    if _http_client is None:
        timeout = httpx.Timeout(
            connect=1.0,
            # ?臾먮뼗 ??疫???쀫립??5?λ뜄以??遺얜뼄.
            read=5.0,
            write=1.0,
            pool=5.0,
        )
        _http_client = httpx.AsyncClient(timeout=timeout)
    return _http_client


def _current_backoff_sec() -> float:
    if _img_failure_count <= 0:
        return 0.0
    return min(_IMG_BACKOFF_MAX_SEC, _IMG_BACKOFF_BASE_SEC * (2 ** (_img_failure_count - 1)))


def _current_live_backoff_sec() -> float:
    if _live_img_failure_count <= 0:
        return 0.0
    return min(_LIVE_IMG_BACKOFF_MAX_SEC, _LIVE_IMG_BACKOFF_BASE_SEC * (2 ** (_live_img_failure_count - 1)))


def _live_retry_after_sec(now: float) -> Optional[float]:
    if _live_img_next_retry_at is None:
        return None
    retry_after = float(_live_img_next_retry_at) - now
    if retry_after <= 0.0:
        return None
    return retry_after


def _max_stale_age_sec() -> float:
    refresh = float(config.SPOT_REFRESH_INTERVAL or 0)
    return max(5.0, refresh * 5.0)


def _cache_age_sec(now: float) -> float:
    return max(0.0, now - float(_img_cache.get("time") or 0.0))


def _cached_image_data() -> Optional[bytes]:
    data = _img_cache.get("data")
    if not isinstance(data, bytes) or not data:
        return None
    return data


def _cached_live_image_data(now: float, image_url: str, *, allow_stale: bool = False) -> Optional[bytes]:
    data = _live_img_cache.get("data")
    cached_url = str(_live_img_cache.get("url") or "")
    cached_at = float(_live_img_cache.get("time") or 0.0)
    if cached_url != image_url:
        return None
    cache_age_sec = max(0.0, now - cached_at)
    if allow_stale:
        if cache_age_sec > _max_stale_age_sec():
            return None
    elif cache_age_sec > _LIVE_IMG_SHARED_FRAME_TTL_SEC:
        return None
    if not isinstance(data, bytes) or not data:
        return None
    return data


def _build_live_image_meta(
    now: float,
    image_url: str,
    status: str,
    source: str,
    *,
    retry_after_sec: Optional[float] = None,
    fallback_error_code: Optional[str] = None,
    fallback_upstream_status: Optional[int] = None,
    fallback_reason: Optional[str] = None,
) -> Dict[str, Any]:
    captured_at = float(_live_img_cache.get("time") or now)
    meta: Dict[str, Any] = {
        "status": status,
        "source": source,
        "captured_at": captured_at,
        "age_sec": max(0.0, now - captured_at),
        "image_url": image_url,
        "max_stale_age_sec": _max_stale_age_sec(),
        "retry_after_sec": _live_retry_after_sec(now) if retry_after_sec is None else retry_after_sec,
    }
    if fallback_error_code:
        meta["fallback"] = True
        meta["fallback_reason"] = fallback_reason or "stale-cache"
        meta["fallback_error_code"] = fallback_error_code
        meta["fallback_upstream_status"] = fallback_upstream_status
    return meta


def _build_live_stale_cache_response(
    now: float,
    image_url: str,
    *,
    fallback_error_code: str,
    fallback_upstream_status: Optional[int],
    fallback_reason: str,
    retry_after_sec: Optional[float] = None,
) -> Optional[tuple[bytes, Dict[str, Any]]]:
    cached_image = _cached_live_image_data(now, image_url, allow_stale=True)
    if cached_image is None:
        return None
    return cached_image, _build_live_image_meta(
        now,
        image_url,
        "stale",
        "stale-cache",
        retry_after_sec=retry_after_sec,
        fallback_error_code=fallback_error_code,
        fallback_upstream_status=fallback_upstream_status,
        fallback_reason=fallback_reason,
    )


def _cache_status(now: float) -> str:
    if _cached_image_data() is None:
        return "empty"
    if _cache_age_sec(now) >= _max_stale_age_sec():
        return "stale"
    return "fresh"


def _cache_state_for_status(cache_status: str) -> str:
    if cache_status == "fresh":
        return "cache"
    return cache_status


def _image_status_for_cache_status(cache_status: str) -> str:
    if cache_status == "fresh":
        return "ok"
    return cache_status


def _retry_after_sec(now: float) -> Optional[float]:
    if _img_next_retry_at is None or _img_failure_count <= 0:
        return None
    return max(0.0, _img_next_retry_at - now)


def _image_proxy_state(now: float) -> str:
    retry_after = _retry_after_sec(now)
    if retry_after is not None and retry_after > 0.0:
        return "backoff"
    if _img_last_error_code:
        return "error"
    return "ok"


def _build_image_meta(
    now: float,
    status: str,
    source: str,
    *,
    cache_status: Optional[str] = None,
) -> Dict[str, Any]:
    captured_at = float(_img_cache.get("time") or 0.0)
    if cache_status is None:
        cache_status = _cache_status(now)
    return {
        "status": status,
        "source": source,
        "captured_at": captured_at,
        "age_sec": _cache_age_sec(now),
        "cache_status": cache_status,
        "proxy_state": _image_proxy_state(now),
        "failure_count": int(_img_failure_count),
        "last_error_code": _img_last_error_code,
        "max_stale_age_sec": _max_stale_age_sec(),
        "next_retry_at": _img_next_retry_at,
        "retry_after_sec": _retry_after_sec(now),
    }


def _should_log_cache_state(now: float) -> bool:
    global _img_last_cache_log_at
    if now - _img_last_cache_log_at < 10.0:
        return False
    _img_last_cache_log_at = now
    return True


def _build_cached_image_response(
    now: float,
    cached_image: bytes,
    *,
    cache_status: Optional[str] = None,
) -> tuple[bytes, Dict[str, Any]]:
    if cache_status is None:
        cache_status = _cache_status(now)
    status = _image_status_for_cache_status(cache_status)
    cache_state = _cache_state_for_status(cache_status)
    return cached_image, _build_image_meta(now, status, cache_state, cache_status=cache_status)


async def fetch_image_async() -> tuple[bytes, Dict[str, Any]]:
    """筌?Ŋ??癒?퐣 筌앸맩??獄쏆꼹??(獄쏄퉫???깆뒲???袁ⓥ봺??뤿Ф?????筌왖)."""
    global _img_failure_count
    global _img_cache_state
    now = time.time()

    # 筌?Ŋ??????筌왖揶쎛 ??됱몵筌?筌앸맩??獄쏆꼹??
    cached_image = _cached_image_data()
    if cached_image is not None:
        age = _cache_age_sec(now)
        cache_status = _cache_status(now)
        next_cache_state = _cache_state_for_status(cache_status)
        if _img_cache_state != next_cache_state and _should_log_cache_state(now):
            if next_cache_state == "cache":
                _logger.info("Spot cache serve: age_sec=%.3f", age)
            else:
                _logger.warning("Spot stale serve: age_sec=%.3f", age)
        _img_cache_state = next_cache_state
        return _build_cached_image_response(now, cached_image, cache_status=cache_status)

    # 筌?Ŋ?녶첎? ??쑴堉??됱몵筌??λ뜃由?嚥≪뮆諭띄몴??袁る퉸 ??甕?筌욊낯??揶쎛?紐꾩궔??
    try:
        image_url = _resolve_spot_image_url()
    except SpotImageConfigError as exc:
        _record_image_error("config-missing", str(exc))
        raise

    retry_after = _retry_after_sec(time.time())
    if retry_after is not None and retry_after > 0.0:
        cached_image = _cached_image_data()
        if cached_image is not None:
            backoff_cached_now = time.time()
            cache_status = _cache_status(backoff_cached_now)
            next_cache_state = _cache_state_for_status(cache_status)
            _img_cache_state = next_cache_state
            return _build_cached_image_response(backoff_cached_now, cached_image, cache_status=cache_status)
        raise SpotImageBackoffError(image_url, retry_after)

    async with _img_fetch_lock:
        # ?醫됲닊 ??얜굣 ??筌?Ŋ?녺몴???쇰뻻 ?類ㅼ뵥??뺣뼄.
        cached_image = _cached_image_data()
        if cached_image is not None:
            cached_now = time.time()
            cache_status = _cache_status(cached_now)
            next_cache_state = _cache_state_for_status(cache_status)
            _img_cache_state = next_cache_state
            return _build_cached_image_response(cached_now, cached_image, cache_status=cache_status)

        locked_retry_after = _retry_after_sec(time.time())
        if locked_retry_after is not None and locked_retry_after > 0.0:
            raise SpotImageBackoffError(image_url, locked_retry_after)

        client = _get_http_client()
        try:
            data = await _request_spot_image(client, image_url)
        except SpotImageFetchError as exc:
            if _is_spot_image_payload_rejection_code(exc.code):
                raise
            _record_image_error(exc.code, str(exc))
            _img_failure_count = min(_img_failure_count + 1, 10)
            _record_image_backoff(_current_backoff_sec())
            raise
        captured_at = time.time()
        _img_cache["data"] = data
        _img_cache["time"] = captured_at
        _img_cache_state = "upstream"
        _record_image_success()
        _maybe_enqueue_spot_image_capture(
            image_bytes=data,
            captured_at=captured_at,
            image_url=image_url,
            source="proxy_upstream",
            image_age_ms=0.0,
        )
        return data, _build_image_meta(time.time(), "ok", "upstream")


async def fetch_live_image_async() -> tuple[bytes, Dict[str, Any]]:
    global _live_img_failure_count

    try:
        image_url = _resolve_spot_live_image_url()
    except SpotLiveImageConfigError as exc:
        _record_live_image_error("live-config-missing", str(exc), exc.image_url)
        raise

    now = time.time()
    cached_image = _cached_live_image_data(now, image_url)
    if cached_image is not None:
        return cached_image, _build_live_image_meta(now, image_url, "ok", "shared-frame")

    retry_after = _live_retry_after_sec(now)
    if retry_after is not None and retry_after > 0.0:
        stale_response = _build_live_stale_cache_response(
            now,
            image_url,
            fallback_error_code="live-backoff-active",
            fallback_upstream_status=None,
            fallback_reason="backoff-active",
            retry_after_sec=retry_after,
        )
        if stale_response is not None:
            return stale_response
        raise SpotLiveImageBackoffError(image_url, retry_after)

    async with _live_img_fetch_lock:
        locked_now = time.time()
        cached_image = _cached_live_image_data(locked_now, image_url)
        if cached_image is not None:
            return cached_image, _build_live_image_meta(locked_now, image_url, "ok", "shared-frame")

        locked_retry_after = _live_retry_after_sec(locked_now)
        if locked_retry_after is not None and locked_retry_after > 0.0:
            stale_response = _build_live_stale_cache_response(
                locked_now,
                image_url,
                fallback_error_code="live-backoff-active",
                fallback_upstream_status=None,
                fallback_reason="backoff-active",
                retry_after_sec=locked_retry_after,
            )
            if stale_response is not None:
                return stale_response
            raise SpotLiveImageBackoffError(image_url, locked_retry_after)

        client = _get_http_client()
        try:
            data = await _request_spot_image(client, image_url)
        except SpotImageFetchError as exc:
            _record_live_image_error(exc.code, str(exc), exc.image_url)
            _live_img_failure_count = min(_live_img_failure_count + 1, 10)
            _record_live_image_backoff(_current_live_backoff_sec())
            stale_response = _build_live_stale_cache_response(
                time.time(),
                image_url,
                fallback_error_code=exc.code,
                fallback_upstream_status=exc.upstream_status,
                fallback_reason="upstream-failure",
            )
            if stale_response is not None:
                return stale_response
            raise

        captured_at = time.time()
        _live_img_cache["data"] = data
        _live_img_cache["time"] = captured_at
        _live_img_cache["url"] = image_url
        _record_live_image_success(image_url)
        _maybe_enqueue_spot_image_capture(
            image_bytes=data,
            captured_at=captured_at,
            image_url=image_url,
            source="live_upstream",
            image_age_ms=0.0,
        )
        return data, _build_live_image_meta(captured_at, image_url, "ok", "upstream", retry_after_sec=None)


# --- 獄쏄퉫???깆뒲???袁ⓥ봺??뤿Ф ---
_prefetch_task: Optional[asyncio.Task] = None
_internal_temp_prefetch_task: Optional[asyncio.Task] = None
_prefetch_running = False


async def _prefetch_loop():
    """獄쏄퉫???깆뒲??뽯퓠??筌왖??우읅??곗쨮 SPOT ???筌왖 ?袁ⓥ봺??뤿Ф (??뺚봺?袁る뱜 獄쎻뫗? 嚥≪뮇彛??怨몄뒠)."""
    global _img_cache_state, _img_failure_count, _img_last_error, _internal_temp_prefetch_task, _prefetch_running
    global _spot_diagnostics_prefetch_task
    _prefetch_running = True

    interval = max(0.5, float(config.SPOT_REFRESH_INTERVAL or 1.0))
    next_tick = time.time()

    while _prefetch_running:
        try:
            client = _get_http_client()
            if config.SPOT_IMAGE_URL:
                image_url = _resolve_spot_image_url()
                data = await _request_spot_image(client, image_url)

                if data:
                    captured_at = time.time()
                    _img_cache["data"] = data
                    _img_cache["time"] = captured_at
                    _img_cache_state = "upstream"
                    if _img_failure_count > 0:
                        _logger.info(
                            "Spot image fetch recovered",
                            extra={"failure_count": _img_failure_count},
                        )
                    _img_failure_count = 0
                    _record_image_success()
                    _maybe_enqueue_spot_image_capture(
                        image_bytes=data,
                        captured_at=captured_at,
                        image_url=image_url,
                        source="prefetch_upstream",
                        image_age_ms=0.0,
                    )

            if config.SPOT_URL:
                try:
                    await _refresh_spot_temperature(client, schedule_diagnostics=True)
                except SpotTemperatureConfigError as exc:
                    _record_temperature_error("temperature-config-missing", str(exc), exc.temp_url, None)
                    _logger.warning(
                        "Spot temperature fetch misconfigured",
                        extra={
                            "code": "temperature-config-missing",
                            "temp_url": exc.temp_url,
                            "error": str(exc),
                        },
                    )
                except SpotTemperatureFetchError as exc:
                    _record_temperature_error(exc.code, str(exc), exc.temp_url, exc.upstream_status)
                    _logger.warning(
                        "Spot temperature fetch failed",
                        extra={
                            "code": exc.code,
                            "temp_url": exc.temp_url,
                            "upstream_status": exc.upstream_status,
                            "error": str(exc),
                        },
                    )

            if config.SPOT_INTERNAL_TEMPERATURE_URL and (
                _internal_temp_prefetch_task is None or _internal_temp_prefetch_task.done()
            ):
                _internal_temp_prefetch_task = asyncio.create_task(
                    _refresh_spot_internal_temperature_safely(client, _logger)
                )

        except asyncio.CancelledError:
            break
        except SpotImageConfigError as exc:
            _record_image_error("config-missing", str(exc))
            _img_failure_count = min(_img_failure_count + 1, 10)
            config_backoff = max(interval, 1.0)
            _record_image_backoff(config_backoff)
            _logger.warning(
                "Spot image fetch misconfigured",
                extra={
                    "code": "config-missing",
                    "error": str(exc),
                    "failure_count": _img_failure_count,
                    "next_backoff_sec": config_backoff,
                    "next_retry_at": _img_next_retry_at,
                },
            )
            await asyncio.sleep(config_backoff)
            next_tick = time.time()
        except SpotImageFetchError as exc:
            if _is_spot_image_payload_rejection_code(exc.code):
                await asyncio.sleep(interval)
                next_tick = time.time()
                continue
            else:
                _record_image_error(exc.code, str(exc))
                _img_failure_count = min(_img_failure_count + 1, 10)
                backoff = _current_backoff_sec()
                _record_image_backoff(backoff)
                if _img_failure_count == 1 or _img_failure_count >= 6:
                    _logger.warning(
                        "Spot image fetch failed",
                        extra={
                            "code": exc.code,
                            "error": str(exc),
                            "failure_count": _img_failure_count,
                            "next_backoff_sec": backoff,
                            "next_retry_at": _img_next_retry_at,
                            "image_url": exc.image_url,
                            "upstream_status": exc.upstream_status,
                        },
                    )

                if backoff > 0:
                    await asyncio.sleep(backoff)
                    next_tick = time.time()
                    continue

        # ??뺚봺?袁る뱜 獄쎻뫗?: ??쇱벉 ??쎈뻬 ??볦퍢 ?④쑴沅?
        next_tick += interval
        now = time.time()
        sleep_time = next_tick - now

        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        else:
            # ?臾믩씜????댭???살삋 椰꾨챶????쇱벉 ??쎈뻬 ??뽰젎????? 筌왖??野껋럩??癰귣똻???뺣뼄.
            next_tick = now
            await asyncio.sleep(0.1)  # 筌ㅼ뮇??0.1????곷뻼??곗쨮 ?袁⑥쨮?紐꾧퐣 ?癒?? 獄쎻뫗?


async def start_prefetch_loop():
    """獄쏄퉫???깆뒲???袁ⓥ봺??뤿Ф ??뽰삂."""
    global _prefetch_task, _prefetch_running
    if _prefetch_task and not _prefetch_task.done():
        return  # ??? ??쎈뻬 餓?

    _prefetch_running = True
    _prefetch_task = asyncio.create_task(_prefetch_loop())


async def stop_prefetch_loop():
    """獄쏄퉫???깆뒲???袁ⓥ봺??뤿Ф 餓λ쵐?."""
    global _internal_temp_prefetch_task, _prefetch_task, _prefetch_running, _spot_diagnostics_prefetch_task
    _prefetch_running = False

    if _spot_diagnostics_prefetch_task:
        _spot_diagnostics_prefetch_task.cancel()
        try:
            await _spot_diagnostics_prefetch_task
        except asyncio.CancelledError:
            pass
        _spot_diagnostics_prefetch_task = None

    if _prefetch_task:
        _prefetch_task.cancel()
        try:
            await _prefetch_task
        except asyncio.CancelledError:
            pass
        _prefetch_task = None
    if _internal_temp_prefetch_task:
        _internal_temp_prefetch_task.cancel()
        try:
            await _internal_temp_prefetch_task
        except asyncio.CancelledError:
            pass
        _internal_temp_prefetch_task = None
    stop_spot_image_capture_writer()


def get_cached_spot_temp() -> float:
    """筌?Ŋ???SPOT ??ㅻ즲??獄쏆꼹??(PLC ??뺤뵬??苡??源녿퓠??????."""
    now = time.time()
    # ???筌왖揶쎛 ??댭???살삋??뤿?椰꾧퀡援?15??, ??ㅻ즲揶쎛 ??곸몵筌?0.0 獄쏆꼹??
    if not _img_cache["temp_time"] or (now - _img_cache["temp_time"] > _TEMP_CACHE_TTL_SEC):
        return 0.0
    return _img_cache["temp"]


def get_cached_spot_internal_temp() -> float:
    now = time.time()
    if not _internal_temp_cache["temp_time"] or (
        now - _internal_temp_cache["temp_time"] > _TEMP_CACHE_TTL_SEC
    ):
        return 0.0
    return _internal_temp_cache["temp"]


def _resolve_spot_focus_url() -> str:
    focus_url = str(config.SPOT_FOCUS_URL or "").strip()
    if not focus_url:
        raise RuntimeError("SPOT_FOCUS_URL is not configured")
    return focus_url


def _preview_spot_focus_body(content: bytes) -> str:
    return content.decode("utf-8", errors="replace").strip()[:200]


def _decode_spot_focus_body(content: bytes, focus_url: str, upstream_status: Optional[int]) -> str:
    try:
        return content.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise SpotFocusControlError(
            "SPOT focus response is not UTF-8; "
            f"url={focus_url}; status_code={upstream_status}; body={_preview_spot_focus_body(content)}",
            focus_url=focus_url,
            upstream_status=upstream_status,
        ) from exc


def _parse_spot_focus_position(
    raw_focus: str,
    focus_url: str,
    upstream_status: Optional[int],
) -> int:
    if not re.fullmatch(r"\d+", raw_focus):
        raise SpotFocusControlError(
            "SPOT focus response is not an integer; "
            f"url={focus_url}; status_code={upstream_status}; body={raw_focus[:200]}",
            focus_url=focus_url,
            upstream_status=upstream_status,
        )
    return int(raw_focus)


def _validate_spot_focus_write_ack(
    raw_focus: str,
    focus_url: str,
    upstream_status: Optional[int],
) -> None:
    if raw_focus.upper() == "OK":
        return
    _parse_spot_focus_position(raw_focus, focus_url, upstream_status)


def _raise_spot_focus_request_error(action: str, focus_url: str, exc: BaseException) -> None:
    raise SpotFocusControlError(
        "SPOT focus request failed; "
        f"action={action}; url={focus_url}; error_type={exc.__class__.__name__}; "
        f"error={_format_exception_message(exc)}",
        focus_url=focus_url,
        upstream_status=None,
    ) from exc


def _read_spot_focus_position(focus_url: str) -> int:
    try:
        with urlopen(focus_url, timeout=3) as resp:
            code = resp.getcode()
            content = resp.read()
    except HTTPError as exc:
        body = _preview_spot_focus_body(exc.read())
        raise SpotFocusControlError(
            f"SPOT focus read failed: HTTP {exc.code}; url={focus_url}; body={body[:200]}",
            focus_url=focus_url,
            upstream_status=exc.code,
        ) from exc
    except (TimeoutError, URLError, ValueError) as exc:
        _raise_spot_focus_request_error("read", focus_url, exc)

    if code != 200:
        raise SpotFocusControlError(
            f"SPOT focus read failed: HTTP {code}; url={focus_url}; body={_preview_spot_focus_body(content)}",
            focus_url=focus_url,
            upstream_status=code,
        )

    raw_focus = _decode_spot_focus_body(content, focus_url, code)
    return _parse_spot_focus_position(raw_focus, focus_url, code)


def _write_spot_focus_position(focus_url: str, new_val: int) -> None:
    request = Request(
        focus_url,
        data=str(new_val).encode("ascii"),
        headers={"Content-Type": "application/json;charset=utf-8"},
        method="PUT",
    )
    try:
        with urlopen(request, timeout=3) as resp:
            code = resp.getcode()
            content = resp.read()
    except HTTPError as exc:
        body = _preview_spot_focus_body(exc.read())
        raise SpotFocusControlError(
            "SPOT focus write failed: "
            f"HTTP {exc.code}; url={focus_url}; value={new_val}; body={body[:200]}",
            focus_url=focus_url,
            upstream_status=exc.code,
        ) from exc
    except (TimeoutError, URLError, ValueError) as exc:
        _raise_spot_focus_request_error("write", focus_url, exc)

    if code != 200:
        raise SpotFocusControlError(
            f"SPOT focus write failed: HTTP {code}; url={focus_url}; "
            f"value={new_val}; body={_preview_spot_focus_body(content)}",
            focus_url=focus_url,
            upstream_status=code,
        )
    raw_focus = _decode_spot_focus_body(content, focus_url, code)
    _validate_spot_focus_write_ack(raw_focus, focus_url, code)


def _wait_for_spot_focus_position(focus_url: str, expected_value: int, previous_value: int) -> int:
    deadline = time.monotonic() + _SPOT_FOCUS_VERIFY_TIMEOUT_SEC
    last_value = previous_value

    while time.monotonic() <= deadline:
        last_value = _read_spot_focus_position(focus_url)
        if last_value == expected_value:
            return last_value
        time.sleep(_SPOT_FOCUS_VERIFY_INTERVAL_SEC)

    raise SpotFocusControlError(
        "SPOT focus write did not reach requested position; "
        f"url={focus_url}; previous={previous_value}; expected={expected_value}; "
        f"last_read={last_value}; timeout_sec={_SPOT_FOCUS_VERIFY_TIMEOUT_SEC}",
        focus_url=focus_url,
        upstream_status=None,
    )


def move_focus(steps: int) -> Dict[str, Any]:
    if steps == 0:
        return {"status": "noop", "message": "steps=0"}

    focus_url = _resolve_spot_focus_url()

    with _ACTUATOR_LOCK:
        current = _read_spot_focus_position(focus_url)
        delta = steps * max(1, config.SPOT_FOCUS_STEP)
        new_val = current + delta

        # v1 ??덉삂??筌띿쉸??甕곕뗄?욅몴???쀫립??뺣뼄.
        new_val = max(_SPOT_FOCUS_MIN_MM, min(_SPOT_FOCUS_MAX_MM, new_val))
        if new_val == current:
            return {
                "status": "limit",
                "current": current,
                "new": new_val,
                "request_steps": steps,
                "focus_step": config.SPOT_FOCUS_STEP,
            }

        _write_spot_focus_position(focus_url, new_val)
        verified = _wait_for_spot_focus_position(focus_url, new_val, current)

        return {
            "status": "ok",
            "current": current,
            "new": new_val,
            "verified": verified,
            "request_steps": steps,
            "focus_step": config.SPOT_FOCUS_STEP,
        }


def _resolve_spot_actuator_url() -> str:
    actuator_url = str(config.SPOT_ACTUATOR_URL or "").strip()
    if not actuator_url:
        raise RuntimeError("SPOT_ACTUATOR_URL is not configured")
    return actuator_url


def _read_spot_actuator_position(actuator_url: str) -> int:
    read_url = f"{actuator_url}?scan=3"
    try:
        with urlopen(read_url, timeout=3) as resp:
            code = resp.getcode()
            content = resp.read()
    except HTTPError as exc:
        body = _preview_spot_focus_body(exc.read())
        raise SpotActuatorControlError(
            f"SPOT actuator read failed: HTTP {exc.code}; url={read_url}; body={body[:200]}",
            actuator_url=actuator_url,
            upstream_status=exc.code,
        ) from exc
    except (TimeoutError, URLError, ValueError) as exc:
        raise SpotActuatorControlError(
            "SPOT actuator request failed; "
            f"action=read; url={read_url}; error_type={exc.__class__.__name__}; "
            f"error={_format_exception_message(exc)}",
            actuator_url=actuator_url,
            upstream_status=None,
        ) from exc

    if code != 200:
        raise SpotActuatorControlError(
            f"SPOT actuator read failed: HTTP {code}; url={read_url}; body={_preview_spot_focus_body(content)}",
            actuator_url=actuator_url,
            upstream_status=code,
        )

    match = _ACTUATOR_POS_PATTERN.search(content)
    if not match:
        raise SpotActuatorControlError(
            f"SPOT actuator position not found in response; url={read_url}; body={_preview_spot_focus_body(content)}",
            actuator_url=actuator_url,
            upstream_status=code,
        )
    return int(match.group(1).decode("ascii"))


def _write_spot_actuator_position(actuator_url: str, new_val: int) -> None:
    write_url = f"{actuator_url}?scan=3&move={new_val}"
    try:
        with urlopen(write_url, timeout=3) as resp:
            code = resp.getcode()
            content = resp.read()
    except HTTPError as exc:
        body = _preview_spot_focus_body(exc.read())
        raise SpotActuatorControlError(
            f"SPOT actuator write failed: HTTP {exc.code}; url={write_url}; body={body[:200]}",
            actuator_url=actuator_url,
            upstream_status=exc.code,
        ) from exc
    except (TimeoutError, URLError, ValueError) as exc:
        raise SpotActuatorControlError(
            "SPOT actuator request failed; "
            f"action=write; url={write_url}; error_type={exc.__class__.__name__}; "
            f"error={_format_exception_message(exc)}",
            actuator_url=actuator_url,
            upstream_status=None,
        ) from exc

    if code != 200:
        raise SpotActuatorControlError(
            f"SPOT actuator write failed: HTTP {code}; url={write_url}; body={_preview_spot_focus_body(content)}",
            actuator_url=actuator_url,
            upstream_status=code,
        )


def _wait_for_spot_actuator_position(actuator_url: str, expected_value: int, previous_value: int) -> int:
    deadline = time.monotonic() + _SPOT_ACTUATOR_VERIFY_TIMEOUT_SEC
    last_value = previous_value

    while time.monotonic() <= deadline:
        last_value = _read_spot_actuator_position(actuator_url)
        if last_value == expected_value:
            return last_value
        time.sleep(_SPOT_ACTUATOR_VERIFY_INTERVAL_SEC)

    raise SpotActuatorControlError(
        "SPOT actuator write did not reach requested position; "
        f"url={actuator_url}; previous={previous_value}; expected={expected_value}; "
        f"last_read={last_value}; timeout_sec={_SPOT_ACTUATOR_VERIFY_TIMEOUT_SEC}",
        actuator_url=actuator_url,
        upstream_status=None,
    )


def move_actuator(steps: int) -> Dict[str, Any]:
    if steps == 0:
        return {"status": "noop", "message": "steps=0"}

    actuator_url = _resolve_spot_actuator_url()

    with _ACTUATOR_LOCK:
        current = _read_spot_actuator_position(actuator_url)
        delta = steps * max(1, config.SPOT_ACTUATOR_STEP)
        new_val = current + delta
        new_val = max(0, min(1000, new_val))
        if new_val == current:
            return {
                "status": "limit",
                "current": current,
                "new": new_val,
                "request_steps": steps,
                "actuator_step": config.SPOT_ACTUATOR_STEP,
            }

        _write_spot_actuator_position(actuator_url, new_val)
        verified = _wait_for_spot_actuator_position(actuator_url, new_val, current)

        return {
            "status": "ok",
            "current": current,
            "new": new_val,
            "verified": verified,
            "request_steps": steps,
            "actuator_step": config.SPOT_ACTUATOR_STEP,
        }
