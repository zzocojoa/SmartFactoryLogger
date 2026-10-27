import asyncio
import copy
import hashlib
import io
import json
import logging
import math
import os
import queue
import re
import threading
import time
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Literal, Optional, TypeAlias, TypeVar, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import httpx
from PIL import Image, UnidentifiedImageError

from backend import config
from backend.FacilityData.drivers.spot_http_transport import (
    DEFAULT_MAX_RESPONSE_BYTES,
    HARD_MAX_RESPONSE_BYTES,
    MAX_REDIRECT_HOPS,
    SpotHttpRequest,
    SpotHttpResponse,
    SpotHttpTransport,
    SpotRequestKind,
    SpotTransportConnectTimeout,
    SpotTransportClosedError,
    SpotTransportError,
    SpotTransportReadTimeout,
    SpotTransportTimeout,
    empty_spot_http_transport_diagnostics,
    resolve_spot_redirect_url,
)
from backend.FacilityData.drivers.spot_port_quarantine import (
    SpotPortPoolError,
)
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
from backend.FacilityData.spot_diagnostic_observability import (
    SPOT_DIAGNOSTIC_JOURNAL_FILENAME,
    SpotDiagnosticRequestContext,
    SpotDiagnosticRequestJournal,
)
from backend.FacilityData.spot_observation_fact import (
    SPOT_OBSERVATION_FACT_FILENAME,
    SpotObservationFactWriter,
    encode_spot_diagnostic_evidence_codes,
)
from backend.FacilityData.spot_config_provenance import build_spot_configuration_snapshot
from backend.FacilityData.spot_image_fact import SPOT_IMAGE_FACT_FILENAME, SpotImageCaptureWriter
from backend.FacilityData.persistence_payload import (
    PayloadBudgetExceeded, decoded_string_bytes, encode_json_payload, prepare_json_payload,
)
from backend.FacilityData.persistence_pressure import StoragePressureMonitor, StoragePressureSample
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

_temperature_cache: _TemperatureCache = {"temp": 0.0, "temp_time": 0.0}
_internal_temp_cache: _TemperatureCache = {"temp": 0.0, "temp_time": 0.0}
from backend.FacilityData.freshness import (
    SPOT_CACHE_EXPIRY_THRESHOLD_SEC, cache_rejection_reason, clock_domain_id, monotonic_age_ms,
    finite_number,
)

_TEMP_CACHE_TTL_SEC = SPOT_CACHE_EXPIRY_THRESHOLD_SEC
_SPOT_VERIFIED_NO_TARGET_VALUES: tuple[str, ...] = ()
_SPOT_INVALID_SENTINEL_VALUES: tuple[str, ...] = SPOT_INVALID_SENTINEL_VALUES
_SPOT_FOCUS_MIN_MM = 300
_SPOT_FOCUS_MAX_MM = 10000
_SPOT_FOCUS_VERIFY_TIMEOUT_SEC = 4.0
_SPOT_FOCUS_VERIFY_INTERVAL_SEC = 0.25
_SPOT_ACTUATOR_VERIFY_TIMEOUT_SEC = 4.0
_SPOT_ACTUATOR_VERIFY_INTERVAL_SEC = 0.25
_SPOT_BACKGROUND_SHUTDOWN_TIMEOUT_SEC = 15.0
_SPOT_OBSERVATION_FACT_DRAIN_TIMEOUT_SEC = 5.0
_SPOT_DIAGNOSTIC_OUTPUT_PARAMS = SPOT_DIAGNOSTIC_OUTPUT_FIELDS
_SPOT_DIAGNOSTIC_TEXT_MAX_CHARS = 256
_SPOT_DIAGNOSTICS_COLLECTION_MODE = str(
    getattr(config, "SPOT_DIAGNOSTICS_COLLECTION_MODE", "async_fact_only")
    or "async_fact_only"
)
_SPOT_RUNTIME_GIT_COMMIT = resolve_runtime_git_commit()
_ACTUATOR_POS_PATTERN = re.compile(rb"Pos-->\s*(\d+)")


@dataclass(frozen=True)
class _SpotImageCacheEntry:
    image_bytes: bytes
    captured_at_epoch: float
    captured_at_monotonic: float
    upstream_latency_ms: float
    image_url: str = ""
    capture_id: Optional[str] = None


_img_fetch_lock = asyncio.Lock()
_spot_device_request_lock = asyncio.Lock()
SpotImageProfile: TypeAlias = Literal["snapshot", "operator_live"]
_SPOT_IMAGE_PROFILE_SNAPSHOT: SpotImageProfile = "snapshot"
_SPOT_IMAGE_PROFILE_OPERATOR_LIVE: SpotImageProfile = "operator_live"
_SPOT_IMAGE_PROFILES = {
    _SPOT_IMAGE_PROFILE_SNAPSHOT,
    _SPOT_IMAGE_PROFILE_OPERATOR_LIVE,
}
_SPOT_REQUEST_BUDGET_POLICY_VERSION = "spot-background-request-budget-v3"
_SPOT_BACKGROUND_REQUEST_BUDGET_TARGET_PER_SEC = 6.0
_SPOT_IMAGE_POLICY_VERSION = "spot-realtime-image-budget-v1"
_SPOT_IMAGE_REFRESH_INTERVAL_DEFAULT_SEC = 3.0
_SPOT_IMAGE_REFRESH_INTERVAL_MIN_SEC = 3.0
_SPOT_IMAGE_REFRESH_INTERVAL_MAX_SEC = 10.0
_SPOT_LIVE_IMAGE_DESIRED_MAX_PER_SEC = 4.0
_SPOT_LIVE_IMAGE_MIN_PER_SEC = 1.0 / _SPOT_IMAGE_REFRESH_INTERVAL_MIN_SEC
_SPOT_IMAGE_REFRESH_SHUTDOWN_TIMEOUT_SEC = 7.0
_SPOT_HTTP_TRANSPORT_SHUTDOWN_TIMEOUT_SEC = 7.0
_SPOT_DIAGNOSTICS_REFRESH_INTERVAL_MIN_SEC = 10.0
_img_cache_entry: Optional[_SpotImageCacheEntry] = None
_img_refresh_task: Optional[asyncio.Task[_SpotImageCacheEntry]] = None
_img_accepting_requests = True
_img_last_source: Optional[str] = None
_img_downstream_request_count = 0
_img_snapshot_downstream_request_count = 0
_img_live_downstream_request_count = 0
_img_upstream_request_count = 0
_img_http_dispatch_count = 0
_img_storage_suppressed_task_count = 0
_img_cache_hit_count = 0
_img_singleflight_leader_count = 0
_img_coalesced_waiter_count = 0
_img_refresh_success_count = 0
_img_refresh_failure_count = 0
_img_cache_clock_anomaly_count = 0
_img_last_upstream_started_at = 0.0
_img_last_upstream_completed_at = 0.0
_img_last_error = 0.0
_img_failure_count = 0
_img_last_error_code: Optional[str] = None
_img_last_error_message: Optional[str] = None
_img_last_success_at = 0.0
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
_spot_diagnostics_last_started_at = 0.0
_spot_diagnostics_last_started_monotonic: Optional[float] = None
_spot_diagnostics_last_completed_at = 0.0
_spot_diagnostics_sweep_started_count = 0
_spot_diagnostics_upstream_request_count = 0
_spot_diagnostics_storage_suppressed_request_count = 0
_spot_diagnostics_storage_suppressed_poll_count = 0
_spot_diagnostics_suppressed_poll_count = 0
_spot_diagnostics_inflight_suppressed_count = 0
_spot_diagnostic_journal_lock = threading.RLock()
_spot_diagnostic_journal: SpotDiagnosticRequestJournal | None = None
_spot_diagnostic_journal_path: Path | None = None
_spot_diagnostic_journal_lease_count = 0
_spot_diagnostic_journal_shutdown_started = False
_spot_diagnostic_journal_closed_snapshot: dict[str, object] | None = None
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
_spot_observation_fact_writer_lock = threading.Lock()
_spot_observation_fact_writer: Optional[SpotObservationFactWriter] = None
from backend.FacilityData.spot_observation_queue import SpotObservationQueue, FactPersistencePending

_spot_observation_queue: Optional[SpotObservationQueue] = None
_spot_observation_queue_path: Optional[Path] = None
_spot_observation_queue_lock = threading.Lock()
_spot_observation_storage_generation = 0


def _observation_fact_path_matches(expected: Path | None, actual: Path) -> bool:
    if expected is None:
        return False
    left, right = expected.resolve(), actual.resolve()
    if left == right:
        return True
    # Windows resolve may retain the extended-length prefix during creation.
    # Compare directory identity and matching remaining names, not just file
    # identity (which could accept a hard link in a different destination).
    while left.name and Path(left.name) == Path(right.name):
        try:
            return left.parent.samefile(right.parent)
        except FileNotFoundError:
            left, right = left.parent, right.parent
        except OSError:
            return False
    return False


def _get_spot_observation_queue() -> SpotObservationQueue:
    global _spot_observation_queue, _spot_observation_queue_path
    global _spot_observation_storage_generation
    with _spot_observation_queue_lock:
        if _spot_observation_queue is None:
            expected_path = _spot_observation_fact_path().resolve()
            _spot_observation_queue_path = expected_path
            def create_writer():
                global _spot_observation_fact_writer
                with _spot_observation_fact_writer_lock:
                    if _spot_observation_fact_writer is None:
                        _spot_observation_fact_writer = SpotObservationFactWriter(expected_path)
                    if not _observation_fact_path_matches(_spot_observation_fact_writer.output_path, expected_path):
                        raise RuntimeError("observation writer belongs to a different path")
                    return _spot_observation_fact_writer
            # Bind the actual owner at creation; later settings cannot relabel
            # pending work or give a replacement owner the previous generation.
            _spot_observation_storage_generation += 1
            _spot_observation_queue = SpotObservationQueue(
                create_writer, config_generation=_spot_observation_storage_generation)
        return _spot_observation_queue


_spot_observation_fact_write_tasks: set[asyncio.Task[None]] = set()
_spot_diagnostics_task: Optional[asyncio.Task[None]] = None
_spot_last_valid_value_at: Optional[float] = None
_spot_last_valid_value_monotonic: Optional[float] = None
_spot_temperature_cache_suppressed_until_valid = False
_INVALID_IMAGE_PAYLOAD_REJECTION_CODES = {"empty-body", "invalid-image-html", "invalid-image-payload"}
# Async HTTP client reused for connection pooling.
_http_client: Optional[httpx.AsyncClient] = None
_spot_http_transport: Optional[SpotHttpTransport] = None
_spot_http_transport_enforcement_required = False
_spot_http_transport_shutdown_started = False
_storage_pressure_monitor: Optional[StoragePressureMonitor] = None
_logger = logging.getLogger("spot_control")


@dataclass(frozen=True)
class ImageCaptureAdmissionResult:
    status: Literal[
        "ACCEPTED", "REJECTED_FULL", "REJECTED_LIMIT", "REJECTED_UNAVAILABLE",
        "REJECTED_CLOSED", "DISABLED", "INVALID",
    ]
    reason: Optional[str]
    capture_id: Optional[str]

    @property
    def accepted(self) -> bool:
        return self.status == "ACCEPTED"


@dataclass(frozen=True)
class _SpotImageCaptureEvent:
    image_bytes: bytes
    captured_at: float
    source_url: str
    source: str
    image_age_ms: Optional[float]
    link_checked_at: Optional[float]
    observation_snapshot: Optional[Dict[str, Any] | bytes]
    reserved_payload_bytes: int = 0
    writer_signature: Optional[tuple[Path, Path, int, float]] = None
    capture_id: Optional[str] = None
    snapshot_text_storage_bytes: int = 0


@dataclass(frozen=True)
class _ImageCapturePendingStage:
    admitted_monotonic: float
    clock_domain: str
    config_generation: int
    destinations: tuple[tuple[str, str], ...]
    payload_bytes: int


_SPOT_IMAGE_CAPTURE_QUEUE_MAX = 128
_SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT = 128 * 1024**2
_SPOT_IMAGE_CAPTURE_QUEUE: queue.Queue[_SpotImageCaptureEvent] = queue.Queue(maxsize=_SPOT_IMAGE_CAPTURE_QUEUE_MAX)
_SPOT_IMAGE_CAPTURE_STOP = threading.Event()
_SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED = threading.Event()
_SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED = threading.Event()
_SPOT_IMAGE_MANIFEST_INITIALIZATION_FAILED = threading.Event()
_SPOT_IMAGE_CAPTURE_OWNER_RELEASE_FAILED = threading.Event()
_spot_image_capture_lock = threading.Lock()
# Historical fact hashing/row scans must not block producer accounting or
# memory-only shutdown snapshots. Writer construction has its own lock.
_spot_image_capture_writer_lock = threading.Lock()
_spot_image_capture_thread: Optional[threading.Thread] = None
_spot_image_capture_writer: Optional[SpotImageCaptureWriter] = None
_spot_image_capture_writer_signature: Optional[tuple[Path, Path, int, float]] = None
_spot_image_storage_activation: Optional[tuple[str, tuple[Path, Path, int, float]]] = None
_spot_image_storage_generation = 0
_spot_image_initialization_retry_at: Optional[float] = None
_spot_image_initialization_retry_delay = 1.0
_spot_image_capture_last_enqueue_at = 0.0
_spot_image_capture_last_enqueue_monotonic: Optional[float] = None
_spot_image_capture_last_write_at = 0.0
_spot_image_capture_last_error_at = 0.0
_spot_image_capture_last_error_code: Optional[str] = None
_spot_image_capture_last_error_message: Optional[str] = None
_spot_image_capture_enqueued_count = 0
_spot_image_capture_written_count = 0
_spot_image_capture_dropped_count = 0
_spot_image_capture_dropped_oversize_count = 0
_spot_image_capture_dropped_queue_full_count = 0
_spot_image_capture_dropped_pending_limit_count = 0
_spot_image_capture_dropped_payload_limit_count = 0
_spot_image_capture_dropped_invalid_count = 0
_spot_image_capture_pending_payload_bytes = 0
_spot_image_capture_pending_stages: Dict[int, _ImageCapturePendingStage] = {}
_spot_image_workspace_stages: Dict[object, _ImageCapturePendingStage] = {}
_spot_image_capture_failure_count = 0
_spot_image_capture_recovery: Optional[_SpotImageCaptureEvent] = None
_spot_image_capture_retry_at: Optional[float] = None
_spot_image_capture_retry_delay = 1.0
_spot_image_capture_retry_error_count = 0
_spot_image_capture_recovered_count = 0
_spot_image_capture_last_fact: Optional[Dict[str, str]] = None
_spot_image_shutdown_baseline: Optional[Dict[str, Any]] = None


class SpotStoragePressureError(RuntimeError):
    """A local storage gate, not a sensor or transport failure."""

    def __init__(self, retry_after_sec: int = 1) -> None:
        super().__init__("Acquisition is suppressed by storage pressure")
        self.retry_after_sec = retry_after_sec


class SpotImageConfigError(ValueError):
    def __init__(self, image_url: str) -> None:
        super().__init__("SPOT_IP is not configured")
        self.image_url = image_url


class SpotImageFetchError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        image_url: str,
        upstream_status: Optional[int],
        transport_error_type: Optional[str] = None,
        transport_os_error_code: Optional[int] = None,
        transport_correlation_id: Optional[str] = None,
        request_elapsed_ms: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.image_url = image_url
        self.upstream_status = upstream_status
        self.transport_error_type = transport_error_type
        self.transport_os_error_code = transport_os_error_code
        self.transport_correlation_id = transport_correlation_id
        self.request_elapsed_ms = request_elapsed_ms


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


def _get_spot_diagnostic_request_journal() -> SpotDiagnosticRequestJournal:
    global _spot_diagnostic_journal
    global _spot_diagnostic_journal_path

    journal_path = Path(getattr(config, "LOG_PATH", Path("logs/data"))) / SPOT_DIAGNOSTIC_JOURNAL_FILENAME
    with _spot_diagnostic_journal_lock:
        if _spot_diagnostic_journal_shutdown_started:
            if _spot_diagnostic_journal is not None:
                return _spot_diagnostic_journal
            raise RuntimeError("SPOT diagnostic request journal is closed")
        if _spot_diagnostic_journal is None:
            _spot_diagnostic_journal = SpotDiagnosticRequestJournal(journal_path)
            _spot_diagnostic_journal_path = journal_path
        elif (
            _spot_diagnostic_journal_path == journal_path
            and not _spot_diagnostic_journal.snapshot()["accepting_persistence"]
        ):
            if (
                _spot_diagnostic_journal_lease_count != 0
                or _spot_diagnostic_journal.snapshot()["active_request_count"] != 0
            ):
                raise RuntimeError(
                    "SPOT diagnostic request journal recovery has active requests"
                )
            if not _spot_diagnostic_journal.close(timeout_sec=0.5):
                raise RuntimeError(
                    "SPOT diagnostic request journal recovery drain timed out"
                )
            _spot_diagnostic_journal = None
            _spot_diagnostic_journal_path = None
            _spot_diagnostic_journal = SpotDiagnosticRequestJournal(journal_path)
            _spot_diagnostic_journal_path = journal_path
        elif _spot_diagnostic_journal_path != journal_path:
            if (
                _spot_diagnostic_journal_lease_count != 0
                or _spot_diagnostic_journal.snapshot()["active_request_count"] != 0
            ):
                raise RuntimeError(
                    "SPOT diagnostic request journal path change has active requests"
                )
            if not _spot_diagnostic_journal.close(timeout_sec=0.5):
                raise RuntimeError(
                    "SPOT diagnostic request journal path change drain timed out"
                )
            _spot_diagnostic_journal = None
            _spot_diagnostic_journal_path = None
            _spot_diagnostic_journal = SpotDiagnosticRequestJournal(journal_path)
            _spot_diagnostic_journal_path = journal_path
        journal = _spot_diagnostic_journal
    return journal


def _acquire_spot_diagnostic_request_journal() -> SpotDiagnosticRequestJournal:
    global _spot_diagnostic_journal_lease_count

    with _spot_diagnostic_journal_lock:
        if _spot_diagnostic_journal_shutdown_started:
            raise RuntimeError("SPOT diagnostic request journal is shutting down")
        journal = _get_spot_diagnostic_request_journal()
        _spot_diagnostic_journal_lease_count += 1
        return journal


def _release_spot_diagnostic_request_journal(
    journal: SpotDiagnosticRequestJournal,
) -> None:
    global _spot_diagnostic_journal_lease_count

    with _spot_diagnostic_journal_lock:
        if _spot_diagnostic_journal is not journal:
            raise RuntimeError("SPOT diagnostic request journal lease identity changed")
        if _spot_diagnostic_journal_lease_count <= 0:
            raise RuntimeError("SPOT diagnostic request journal lease underflow")
        _spot_diagnostic_journal_lease_count -= 1


async def _acquire_spot_diagnostic_request_journal_for_sweep(
) -> SpotDiagnosticRequestJournal:
    acquire_task = asyncio.create_task(
        asyncio.to_thread(_acquire_spot_diagnostic_request_journal)
    )
    cancellation_requested = False
    while not acquire_task.done():
        try:
            await asyncio.shield(acquire_task)
        except asyncio.CancelledError:
            cancellation_requested = True
        except Exception:
            if cancellation_requested:
                raise asyncio.CancelledError from None
            raise

    try:
        journal = acquire_task.result()
    except Exception:
        if cancellation_requested:
            raise asyncio.CancelledError from None
        raise
    if cancellation_requested:
        _release_spot_diagnostic_request_journal(journal)
        raise asyncio.CancelledError
    return journal


def _close_spot_diagnostic_request_journal(
    timeout_sec: float = 2.0,
    *,
    final_shutdown: bool = False,
) -> bool:
    global _spot_diagnostic_journal
    global _spot_diagnostic_journal_path
    global _spot_diagnostic_journal_shutdown_started
    global _spot_diagnostic_journal_closed_snapshot

    with _spot_diagnostic_journal_lock:
        if final_shutdown:
            _spot_diagnostic_journal_shutdown_started = True
        journal = _spot_diagnostic_journal
        if _spot_diagnostic_journal_lease_count != 0:
            if final_shutdown and journal is not None:
                _spot_diagnostic_journal_closed_snapshot = journal.snapshot()
            return False
    if journal is None:
        return True
    if final_shutdown:
        _spot_diagnostic_journal_closed_snapshot = journal.snapshot()
    stopped = journal.close(timeout_sec=timeout_sec)
    snapshot = journal.snapshot()
    with _spot_diagnostic_journal_lock:
        if final_shutdown:
            _spot_diagnostic_journal_closed_snapshot = snapshot
        if stopped and _spot_diagnostic_journal is journal:
            _spot_diagnostic_journal = None
            _spot_diagnostic_journal_path = None
    return stopped


def _spot_diagnostic_request_journal_snapshot() -> dict[str, object]:
    with _spot_diagnostic_journal_lock:
        journal = _spot_diagnostic_journal
        shutdown_started = _spot_diagnostic_journal_shutdown_started
        closed_snapshot = copy.deepcopy(_spot_diagnostic_journal_closed_snapshot)
    if journal is not None:
        return journal.snapshot()
    if shutdown_started and closed_snapshot is not None:
        return closed_snapshot
    return _get_spot_diagnostic_request_journal().snapshot()


def stop_spot_diagnostic_request_journal(timeout_sec: float = 2.0) -> bool:
    """Drain the append-only journal after all SPOT diagnostic consumers stop."""

    return _close_spot_diagnostic_request_journal(
        timeout_sec=timeout_sec,
        final_shutdown=True,
    )


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
    with config.PERSISTENCE_CONFIG_LOCK:
        return (
            _spot_image_capture_log_path().absolute(),
            _spot_image_capture_root().absolute(),
            _spot_image_capture_retention_days(),
            _spot_image_capture_link_stale_threshold_ms(),
        )


@contextmanager
def _reserve_image_writer_payload(
    size: int, reason: str, sink_id: str, destination: Path, generation: int,
) -> Iterator[None]:
    global _spot_image_capture_pending_payload_bytes
    destination_key = _image_destination_key(destination)
    token = object()
    with _spot_image_capture_lock:
        if _spot_image_capture_pending_payload_bytes + size > _SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT:
            raise PayloadBudgetExceeded(reason)
        _spot_image_capture_pending_payload_bytes += size
        _spot_image_workspace_stages[token] = _ImageCapturePendingStage(
            time.monotonic(), clock_domain_id(), generation, ((sink_id, destination_key),), size)
    try:
        yield
    finally:
        with _spot_image_capture_lock:
            _spot_image_workspace_stages.pop(token)
            _spot_image_capture_pending_payload_bytes -= size


def _image_probe_manual_recovery_required() -> bool:
    """Memory-only; keep the existing owner as the unresolved resource holder."""
    writer = _spot_image_capture_writer
    return writer is not None and writer.probe_manual_recovery_required()


def _get_spot_image_capture_writer(
    signature: Optional[tuple[Path, Path, int, float]] = None,
) -> SpotImageCaptureWriter:
    global _spot_image_capture_writer, _spot_image_capture_writer_signature
    with _spot_image_capture_writer_lock:
        if _image_probe_manual_recovery_required():
            raise RuntimeError("SPOT image probe requires manual recovery before owner replacement")
        if _SPOT_IMAGE_CAPTURE_OWNER_RELEASE_FAILED.is_set():
            raise RuntimeError("SPOT image owner resource release is unconfirmed")
        if signature is None:
            signature = _spot_image_capture_config_signature()
        if _spot_image_capture_writer is None or _spot_image_capture_writer_signature != signature:
            _spot_image_capture_writer = SpotImageCaptureWriter(
                log_path=signature[0],
                capture_root=signature[1],
                retention_days=signature[2],
                link_stale_threshold_ms=signature[3],
                payload_reservation=_reserve_image_writer_payload,
            )
            _spot_image_capture_writer_signature = signature
        return _spot_image_capture_writer


def _start_spot_image_capture_worker(*, force: bool = False) -> None:
    global _spot_image_capture_thread
    if _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set() and not force:
        return
    with _spot_image_capture_lock:
        if _SPOT_IMAGE_CAPTURE_OWNER_RELEASE_FAILED.is_set() or _image_probe_manual_recovery_required():
            return
        if _spot_image_capture_thread is not None and _spot_image_capture_thread.is_alive():
            return
        if _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set() and not force:
            return
        retry_deadlines = [deadline for deadline in (
            _spot_image_initialization_retry_at,
            _spot_image_capture_retry_at if _spot_image_capture_recovery is not None else None,
        ) if deadline is not None]
        if retry_deadlines and (
            _SPOT_IMAGE_CAPTURE_STOP.is_set() or force
            or time.monotonic() < max(retry_deadlines)
        ):
            return
        _SPOT_IMAGE_CAPTURE_STOP.clear()
        _spot_image_capture_thread = threading.Thread(
            target=_spot_image_capture_worker,
            name="spot-image-capture-writer",
            daemon=True,
        )
        _spot_image_capture_thread.start()


def _request_spot_image_manifest_initialization() -> None:
    # Reuse the owned, joined image worker even when no images are captured.
    # Otherwise a cold startup would merely move the historical scan to exit.
    with _spot_image_capture_lock:
        if (_SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set() or _SPOT_IMAGE_CAPTURE_STOP.is_set()
                or _image_probe_manual_recovery_required()):
            return
        _SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.set()
    _start_spot_image_capture_worker()


def _bind_spot_image_activation_locked(
    activation: Optional[tuple[str, tuple[Path, Path, int, float]]],
) -> bool:
    """Caller holds configuration then image accounting locks; no file I/O."""
    global _spot_image_storage_activation, _spot_image_storage_generation
    global _spot_image_initialization_retry_at, _spot_image_initialization_retry_delay
    changed = activation != _spot_image_storage_activation
    if changed:
        _spot_image_storage_activation = activation
        _spot_image_storage_generation += 1
        _spot_image_initialization_retry_at = None
        _spot_image_initialization_retry_delay = 1.0
        if activation is None:
            _SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.clear()
    return changed


def _activate_spot_image_storage() -> None:
    """Schedule configuration changes; all destination I/O stays in the owner."""
    with config.PERSISTENCE_CONFIG_LOCK:
        mode = _spot_image_capture_mode()
        activation = None if mode == "off" else (mode, _spot_image_capture_config_signature())
        with _spot_image_capture_lock:
            if (_SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set() or _SPOT_IMAGE_CAPTURE_STOP.is_set()
                    or _image_probe_manual_recovery_required()):
                return
            changed = _bind_spot_image_activation_locked(activation)
            initialize = activation is not None and (
                changed or _SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.is_set())
            pending = _SPOT_IMAGE_CAPTURE_QUEUE.unfinished_tasks > 0
    if initialize:
        _request_spot_image_manifest_initialization()
    elif pending:
        # Disabling future captures must not abandon an admitted old-generation
        # event when its initializer owner exited. Its own deadline still applies.
        _start_spot_image_capture_worker()


def _spot_image_capture_failure_evidence(
    event: _SpotImageCaptureEvent, error: Exception, *, stage: str, error_at: float, failure_count: int,
) -> Dict[str, Any]:
    sha256 = hashlib.sha256(event.image_bytes).hexdigest()
    try:
        captured_dt = datetime.fromtimestamp(event.captured_at, timezone.utc)
    except (ValueError, OverflowError, OSError):
        # A bad capture timestamp must not prevent the next queued write.
        captured_dt = None
    return {
        "schema_version": 1,
        "event": "spot_image_capture_failure",
        "error_at": error_at,
        "captured_at": captured_dt.isoformat().replace("+00:00", "Z") if captured_dt is not None else None,
        "capture_id": event.capture_id or (
            f"spotimg_{captured_dt.strftime('%Y%m%dT%H%M%S%fZ')}_{sha256[:12]}"
            if captured_dt is not None else None),
        "image_sha256": sha256,
        "image_bytes": len(event.image_bytes),
        "spot_service_instance_id": _spot_service_instance_id,
        "failure_count": failure_count,
        "stage": stage,
        "error_type": error.__class__.__name__,
        "reason": "snapshot_decode_byte_limit" if stage == "snapshot_decode" and isinstance(error, PayloadBudgetExceeded) else None,
        "errno": getattr(error, "errno", None) if isinstance(getattr(error, "errno", None), int) else None,
        "winerror": getattr(error, "winerror", None) if isinstance(getattr(error, "winerror", None), int) else None,
    }


def _probe_spot_image_storage_if_due(writer: SpotImageCaptureWriter) -> None:
    captured_at = time.time()
    with config.PERSISTENCE_CONFIG_LOCK:
        mode = _spot_image_capture_mode()
        signature = _spot_image_capture_config_signature()
    with _spot_image_capture_lock:
        activation = _spot_image_storage_activation
        generation = _spot_image_storage_generation
    if (mode == "off" or not _SPOT_IMAGE_CAPTURE_QUEUE.empty()
            or _SPOT_IMAGE_CAPTURE_STOP.is_set() or _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set()
            or writer is not _spot_image_capture_writer or signature != _spot_image_capture_writer_signature
            or (generation > 0 and activation != (mode, signature))):
        return
    writer.bind_destination_probe_generation(generation)
    if writer.destination_probe_due(captured_at=captured_at, now_monotonic=time.monotonic()):
        writer.probe_storage_destinations(captured_at=captured_at)


def _spot_image_capture_worker() -> None:
    global _spot_image_capture_failure_count, _spot_image_capture_last_fact
    global _spot_image_capture_last_error_at, _spot_image_capture_last_error_code, _spot_image_capture_last_error_message
    global _spot_image_capture_last_write_at, _spot_image_capture_written_count
    global _spot_image_capture_pending_payload_bytes
    global _spot_image_capture_recovery, _spot_image_capture_retry_at, _spot_image_capture_retry_delay
    global _spot_image_capture_retry_error_count, _spot_image_capture_recovered_count
    global _spot_image_initialization_retry_at, _spot_image_initialization_retry_delay
    writer: Optional[SpotImageCaptureWriter] = None
    try:
        while (not _SPOT_IMAGE_CAPTURE_STOP.is_set() or not _SPOT_IMAGE_CAPTURE_QUEUE.empty()
               or _SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.is_set()
               or _spot_image_capture_recovery is not None):
            if _image_probe_manual_recovery_required():
                if _SPOT_IMAGE_CAPTURE_STOP.wait(.1):
                    break
                continue  # Preserve admitted work and the old owner; no file I/O.
            if _spot_image_capture_recovery is not None:
                # The same single owner retains the original queue task and
                # payload reservation. Shutdown must not schedule another try.
                if _SPOT_IMAGE_CAPTURE_STOP.is_set() or _spot_image_shutdown_baseline is not None:
                    break
                remaining = max(0.0, (_spot_image_capture_retry_at or 0.0) - time.monotonic())
                if remaining:
                    _SPOT_IMAGE_CAPTURE_STOP.wait(min(remaining, 0.1))
                    continue
                event = _spot_image_capture_recovery
            elif (_SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.is_set()
                  and _SPOT_IMAGE_CAPTURE_QUEUE.empty()):
                with _spot_image_capture_lock:
                    initialization_generation = _spot_image_storage_generation
                    _SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.clear()
                try:
                    current_writer = _get_spot_image_capture_writer()
                    if writer is not None and writer is not current_writer:
                        writer.close_retention_scan()
                    writer = current_writer
                    _probe_spot_image_storage_if_due(writer)
                    with _spot_image_capture_lock:
                        if initialization_generation == _spot_image_storage_generation:
                            _spot_image_initialization_retry_at = None
                            _spot_image_initialization_retry_delay = 1.0
                except Exception:
                    # Initialization is not an image capture. Keep its failure
                    # separate from the capture enqueue/write/failure equation.
                    _SPOT_IMAGE_MANIFEST_INITIALIZATION_FAILED.set()
                    with _spot_image_capture_lock:
                        if (initialization_generation == _spot_image_storage_generation
                                and not _SPOT_IMAGE_CAPTURE_STOP.is_set()
                                and not _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set()):
                            _spot_image_initialization_retry_at = time.monotonic() + _spot_image_initialization_retry_delay
                            _spot_image_initialization_retry_delay = min(30.0, _spot_image_initialization_retry_delay * 2.0)
                            _SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.set()
                    _logger.exception("SPOT image manifest initialization failed")
                    # The service tick may restart only after this owner's
                    # finally has completed and Thread.is_alive() is false.
                    break
                continue
            else:
                try:
                    event = _SPOT_IMAGE_CAPTURE_QUEUE.get(timeout=0.1)
                except queue.Empty:
                    if writer is not None and not _SPOT_IMAGE_CAPTURE_STOP.is_set():
                        if (writer is not _spot_image_capture_writer
                                or _spot_image_capture_writer_signature != _spot_image_capture_config_signature()):
                            writer.close_retention_scan()
                            writer = None
                        else:
                            writer._cleanup_retention(time.time(), allow_start=False)
                            _probe_spot_image_storage_if_due(writer)
                    continue
            fact: Optional[Dict[str, str]] = None
            capture_error: Optional[Exception] = None
            failure_stage = "writer_initialization"
            failure_evidence = None
            decoded_snapshot = None
            processing_bytes = 0
            try:
                current_writer = _get_spot_image_capture_writer(event.writer_signature)
                if writer is not None and writer is not current_writer:
                    writer.close_retention_scan()
                writer = current_writer
                failure_stage = "snapshot_decode"
                if isinstance(event.observation_snapshot, bytes):
                    # JSON decoding owns both its text and parsed strings. Old
                    # direct events without a bound use a conservative UCS4
                    # bound; production events carry the admission preflight.
                    text_bytes = event.snapshot_text_storage_bytes or 4 * len(event.observation_snapshot)
                    required = 2 * text_bytes
                    with _spot_image_capture_lock:
                        if _spot_image_capture_pending_payload_bytes + required > _SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT:
                            raise PayloadBudgetExceeded
                        _spot_image_capture_pending_payload_bytes += required
                        processing_bytes = required
                        admitted_stage = _spot_image_capture_pending_stages.get(id(event))
                        if admitted_stage is not None:
                            _spot_image_workspace_stages[id(event)] = replace(admitted_stage, payload_bytes=required)
                    decoded_snapshot = json.loads(event.observation_snapshot)
                    retained = decoded_string_bytes(decoded_snapshot)
                    if retained > required:
                        raise RuntimeError("Image snapshot exceeded its decode bound")
                    with _spot_image_capture_lock:
                        _spot_image_capture_pending_payload_bytes -= processing_bytes - retained
                        processing_bytes = retained
                        if admitted_stage is not None:
                            _spot_image_workspace_stages[id(event)] = replace(admitted_stage, payload_bytes=retained)
                else:
                    decoded_snapshot = event.observation_snapshot
                failure_stage = "write_capture"
                fact = writer.write_capture(
                    capture_id=event.capture_id,
                    image_bytes=event.image_bytes,
                    captured_at=event.captured_at,
                    source_url=event.source_url,
                    source=event.source,
                    image_age_ms=event.image_age_ms,
                    link_checked_at=event.link_checked_at,
                    observation_snapshot=decoded_snapshot,
                )
            except Exception as exc:  # pragma: no cover - exercised through integration-style tests
                capture_error = exc
            finally:
                if capture_error is None and fact is None:
                    capture_error = RuntimeError("capture writer returned no fact")
                if capture_error is not None:
                    failure_evidence = _spot_image_capture_failure_evidence(
                        event, capture_error, stage=failure_stage, error_at=time.time(),
                        failure_count=_spot_image_capture_failure_count + 1,
                    )
                retain_for_retry = (
                    isinstance(capture_error, OSError)
                    and not (writer is not None and writer._fact_append_uncertain)
                    and not _SPOT_IMAGE_CAPTURE_STOP.is_set()
                    and _spot_image_shutdown_baseline is None
                )
                reserved_bytes = event.reserved_payload_bytes
                event_token = id(event)
                if retain_for_retry:
                    with _spot_image_capture_lock:
                        _spot_image_capture_recovery = event
                # Drop temporary decoded copies before returning reservations.
                capture_error = None
                decoded_snapshot = None
                # Outcome accounting and Queue.task_done() are one atomic state
                # transition. Shutdown can therefore never observe a recorded
                # failure while the same capture still appears unfinished.
                with _spot_image_capture_lock:
                    _spot_image_workspace_stages.pop(event_token, None)
                    if not retain_for_retry:
                        _spot_image_capture_pending_stages.pop(event_token, None)
                    # Remove the stage before this object's id can be reused
                    # by a producer, and release payload before its budget.
                    del event
                    if retain_for_retry:
                        _spot_image_capture_retry_error_count += 1
                        _spot_image_capture_retry_at = time.monotonic() + _spot_image_capture_retry_delay
                        _spot_image_capture_retry_delay = min(30.0, _spot_image_capture_retry_delay * 2.0)
                        _spot_image_capture_pending_payload_bytes -= processing_bytes
                        assert failure_evidence is not None
                        failure_evidence["event"] = "spot_image_capture_retry_pending"
                        failure_evidence["failure_count"] = _spot_image_capture_failure_count
                        failure_evidence["retry_error_count"] = _spot_image_capture_retry_error_count
                        failure_evidence["next_retry_at_monotonic"] = _spot_image_capture_retry_at
                    elif failure_evidence is None and fact is not None:
                        _spot_image_capture_written_count += 1
                        _spot_image_capture_last_write_at = time.time()
                        _spot_image_capture_last_fact = dict(fact)
                        _spot_image_capture_last_error_code = None
                        _spot_image_capture_last_error_message = None
                    else:
                        assert failure_evidence is not None
                        _spot_image_capture_failure_count += 1
                    if failure_evidence is not None:
                        _spot_image_capture_last_error_at = failure_evidence["error_at"]
                        _spot_image_capture_last_error_code = failure_evidence["error_type"]
                        _spot_image_capture_last_error_message = "capture writer failed"
                    if not retain_for_retry:
                        if _spot_image_capture_recovery is not None and fact is not None:
                            _spot_image_capture_recovered_count += 1
                        _spot_image_capture_recovery = None
                        _spot_image_capture_retry_at = None
                        _spot_image_capture_retry_delay = 1.0
                        _spot_image_capture_pending_payload_bytes -= reserved_bytes + processing_bytes
                        _SPOT_IMAGE_CAPTURE_QUEUE.task_done()
            if failure_evidence is not None:
                # Default stderr formatting drops LogRecord.extra. Keep the safe
                # capture identity in the message even after later writes recover.
                _logger.warning(
                    "SPOT image capture writer failed %s",
                    json.dumps(failure_evidence, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                    extra={
                        "error_type": failure_evidence["error_type"],
                    },
                )
            if retain_for_retry and failure_stage == "writer_initialization":
                _SPOT_IMAGE_MANIFEST_INITIALIZATION_FAILED.set()
                # Keep the same event, queue task and payload reservation for
                # the replacement owner; the service tick cannot overlap us.
                break

    finally:
        if writer is not None:
            try:
                writer.close_retention_scan()
            except Exception:
                _SPOT_IMAGE_CAPTURE_OWNER_RELEASE_FAILED.set()
                _logger.exception("SPOT image owner resource release is unconfirmed")


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
    return (not _SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.is_set()
            and not _SPOT_IMAGE_MANIFEST_INITIALIZATION_FAILED.is_set()
            and not _SPOT_IMAGE_CAPTURE_OWNER_RELEASE_FAILED.is_set()
            and not _image_probe_manual_recovery_required()
            and getattr(_SPOT_IMAGE_CAPTURE_QUEUE, "unfinished_tasks", 0) == 0) and not (
        thread is not None and thread.is_alive()
    )


def _image_destination_key(path: Path) -> str:
    return hashlib.sha256(os.fsencode(os.path.normcase(os.path.abspath(path)))).hexdigest()


def _image_pending_destinations_locked() -> list[Dict[str, Any]]:
    destinations: Dict[tuple[int, str, str], Dict[str, Any]] = {}
    stages: list[tuple[object, _ImageCapturePendingStage, bool]] = [
        (token, stage, True) for token, stage in _spot_image_capture_pending_stages.items()]
    stages.extend((token, stage, False) for token, stage in _spot_image_workspace_stages.items())
    for token, stage, is_capture in stages:
        for sink, key in stage.destinations:
            item = destinations.setdefault((stage.config_generation, sink, key), {
                "sink_id": sink, "config_generation": stage.config_generation, "destination_key": key,
                "pending_count": 0, "pending_bytes": 0, "pending_recovery": 0,
                "clock_domain": stage.clock_domain,
                "oldest_pending_monotonic": stage.admitted_monotonic,
                "stage_due_monotonic": stage.admitted_monotonic,
            })
            item["pending_count"] += int(is_capture)
            item["pending_bytes"] += stage.payload_bytes
            item["pending_recovery"] += int(is_capture and token == id(_spot_image_capture_recovery))
            item["oldest_pending_monotonic"] = min(item["oldest_pending_monotonic"], stage.admitted_monotonic)
            item["stage_due_monotonic"] = item["oldest_pending_monotonic"]
    return list(destinations.values())


def _image_shutdown_status_locked() -> Dict[str, Any]:
    # Outcome counters and task_done use this same lock order. No file I/O,
    # writer initialization or thread join is permitted in this snapshot.
    with _SPOT_IMAGE_CAPTURE_QUEUE.mutex:
        queued = len(_SPOT_IMAGE_CAPTURE_QUEUE.queue)
        unfinished = _SPOT_IMAGE_CAPTURE_QUEUE.unfinished_tasks
    baseline = _spot_image_shutdown_baseline or {}
    historical = baseline.get("historical_failures")
    failures = _spot_image_capture_failure_count
    delta = failures - historical if isinstance(historical, int) and failures >= historical else None
    alive = _spot_image_capture_thread is not None and _spot_image_capture_thread.is_alive()
    accounting = (
        0 <= queued <= unfinished
        and _spot_image_capture_enqueued_count
        == _spot_image_capture_written_count + failures + unfinished
    )
    blocked = _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set()
    stopping = _SPOT_IMAGE_CAPTURE_STOP.is_set()
    initialization_pending = _SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.is_set()
    initialization_failed = _SPOT_IMAGE_MANIFEST_INITIALIZATION_FAILED.is_set()
    owner_release_failed = _SPOT_IMAGE_CAPTURE_OWNER_RELEASE_FAILED.is_set()
    probe_manual_recovery = _image_probe_manual_recovery_required()
    stages = tuple(_spot_image_capture_pending_stages.values())
    timing_known = (len(stages) == unfinished
                    and all(stage.clock_domain == clock_domain_id() for stage in stages))
    oldest = min((stage.admitted_monotonic for stage in stages), default=None) if timing_known else None
    writes_drained = (bool(baseline) and blocked and stopping and not alive and queued == 0
                      and unfinished == 0 and accounting and not initialization_pending
                      and not owner_release_failed and not probe_manual_recovery)
    return {
        "shutdown_id": baseline.get("shutdown_id"),
        "requested_at": baseline.get("requested_at"),
        "historical_failures": historical,
        "historical_dropped_count": baseline.get("historical_dropped_count"),
        "historical_last_error_at": baseline.get("historical_last_error_at"),
        "new_failures_during_drain": delta,
        "worker_started": _spot_image_capture_thread is not None,
        "worker_alive": alive,
        "worker_stopped": not alive,
        "queue_size": queued,
        "unfinished_tasks": unfinished,
        "inflight_count": unfinished - queued,
        "enqueue_disabled": blocked,
        "stop_requested": stopping,
        "enqueued_count": _spot_image_capture_enqueued_count,
        "written_count": _spot_image_capture_written_count,
        "failure_count": failures,
        "pending_recovery": int(_spot_image_capture_recovery is not None),
        "retry_error_count": _spot_image_capture_retry_error_count,
        "recovered_count": _spot_image_capture_recovered_count,
        "next_retry_at_monotonic": _spot_image_capture_retry_at,
        "historical_retry_errors": baseline.get("historical_retry_errors"),
        "dropped_count": _spot_image_capture_dropped_count,
        "dropped_oversize_count": _spot_image_capture_dropped_oversize_count,
        "dropped_queue_full_count": _spot_image_capture_dropped_queue_full_count,
        "dropped_pending_limit_count": _spot_image_capture_dropped_pending_limit_count,
        "dropped_payload_limit_count": _spot_image_capture_dropped_payload_limit_count,
        "dropped_invalid_count": _spot_image_capture_dropped_invalid_count,
        "pending_payload_bytes": _spot_image_capture_pending_payload_bytes,
        "oldest_pending_monotonic": oldest,
        "stage_due_monotonic": oldest,
        "clock_domain": clock_domain_id() if timing_known else None,
        "pending_clock_unknown": not timing_known,
        "pending_destinations": _image_pending_destinations_locked(),
        "pending_stage_count": len(stages),
        "pending_capture_payload_bytes": sum(stage.payload_bytes for stage in stages),
        "pending_workspace_payload_bytes": sum(stage.payload_bytes for stage in _spot_image_workspace_stages.values()),
        "pending_payload_byte_limit": _SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT,
        "last_error_at": _spot_image_capture_last_error_at or None,
        "accounting_consistent": accounting,
        "manifest_initialization_requested": initialization_pending,
        "manifest_initialization_failed": initialization_failed,
        "owner_release_failed": owner_release_failed,
        "probe_manual_recovery_required": probe_manual_recovery,
        "writes_drained": writes_drained,
        # This is evidence of unresolved writes, not an image-loss estimate.
        "integrity_unresolved": failures > 0 or _spot_image_capture_retry_error_count > 0
        or _spot_image_capture_dropped_count > 0
        or not writes_drained or delta is None or initialization_failed,
    }


def begin_spot_image_capture_shutdown() -> Dict[str, Any]:
    """Freeze the first failure baseline before any asynchronous shutdown work.

    Observing a late completion or repeating stop must never rebase failures.
    Producer admission continues to follow the existing stop ordering.
    """
    global _spot_image_shutdown_baseline
    with _spot_image_capture_lock:
        if _spot_image_shutdown_baseline is None:
            _spot_image_shutdown_baseline = {
                "shutdown_id": uuid4().hex,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "historical_failures": _spot_image_capture_failure_count,
                "historical_retry_errors": _spot_image_capture_retry_error_count,
                "historical_dropped_count": _spot_image_capture_dropped_count,
                "historical_last_error_at": _spot_image_capture_last_error_at or None,
            }
        return _image_shutdown_status_locked()


def get_spot_image_capture_shutdown_status() -> Dict[str, Any]:
    """Return a fresh, memory-only snapshot; this does not request shutdown."""
    with _spot_image_capture_lock:
        return _image_shutdown_status_locked()


def get_spot_image_storage_pressure_samples() -> tuple[StoragePressureSample, ...]:
    """Memory-only actual destinations; unmatched or unfinished state stays unknown."""
    with config.PERSISTENCE_CONFIG_LOCK:
        mode = _spot_image_capture_mode()
        signature = _spot_image_capture_config_signature()
        with _spot_image_capture_lock:
            state = _image_shutdown_status_locked()
            generation = (_spot_image_storage_generation
                          if (_spot_image_storage_activation == (mode, signature)
                              or _spot_image_storage_generation == 0) else None)
            writer = _spot_image_capture_writer
    day = datetime.fromtimestamp(time.time(), timezone.utc)
    current = {
        (generation, "image_fact", _image_destination_key(signature[0] / SPOT_IMAGE_FACT_FILENAME)),
        (generation, "image_jpeg", _image_destination_key(signature[1] / day.strftime('%Y/%m/%d'))),
    } if mode != "off" else set()
    probes = {}
    if writer is not None:
        for probe in writer.destination_probe_snapshot():
            path = Path(probe["destination_path"])
            if probe["sink_id"] == "image_fact":
                path /= SPOT_IMAGE_FACT_FILENAME
            probes[(probe["config_generation"], probe["sink_id"], _image_destination_key(path))] = probe
    samples = []
    pending = {(stage["config_generation"], stage["sink_id"], stage["destination_key"]): stage
               for stage in state["pending_destinations"]}
    for binding in current | probes.keys() | pending.keys():
        probe = probes.get(binding, {})
        stage = pending.get(binding, {})
        manual = (state["owner_release_failed"] or state["probe_manual_recovery_required"]
                  or probe.get("manual_recovery_required", False)
                  or (writer is not None and writer._fact_append_uncertain))
        availability = ("blocked" if manual or state["manifest_initialization_failed"] else
                        "unknown" if state["manifest_initialization_requested"] else
                        probe.get("current_storage_availability", "unknown"))
        samples.append(StoragePressureSample(
            sink_id=binding[1], config_generation=binding[0], destination_key=binding[2],
            enabled=binding in current, availability=availability,
            pending_count=stage.get("pending_count", 0), pending_bytes=stage.get("pending_bytes", 0),
            pending_recovery=stage.get("pending_recovery", 0),
            oldest_pending_monotonic=stage.get("oldest_pending_monotonic"),
            stage_due_monotonic=stage.get("stage_due_monotonic"),
            clock_domain=stage.get("clock_domain", clock_domain_id()),
            count_limit=_SPOT_IMAGE_CAPTURE_QUEUE_MAX, byte_limit=_SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT,
            writer_alive=state["worker_alive"], manual_recovery_required=bool(manual),
            budget_pending_count=state["unfinished_tasks"], budget_pending_bytes=state["pending_payload_bytes"],
        ))
    unbound_count = state["unfinished_tasks"] - state["pending_stage_count"]
    unbound_bytes = (state["pending_payload_bytes"] - state["pending_capture_payload_bytes"]
                     - state["pending_workspace_payload_bytes"])
    if unbound_count or unbound_bytes or state["pending_clock_unknown"]:
        # Legacy direct events and unbound processing reservations must not
        # borrow the latest capture's clock or a different destination's probe.
        samples.append(StoragePressureSample(
            sink_id="image_pending_unbound", config_generation=None, destination_key="", enabled=True,
            availability="unknown", pending_count=max(0, unbound_count),
            pending_bytes=max(0, unbound_bytes), count_limit=_SPOT_IMAGE_CAPTURE_QUEUE_MAX,
            byte_limit=_SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT, pending_recovery=state["pending_recovery"],
            writer_alive=state["worker_alive"],
        ))
    return tuple(samples)


def stop_spot_image_capture_for_shutdown(timeout_sec: float = 2.0) -> bool:
    global _spot_poll_running
    begin_spot_image_capture_shutdown()
    with _spot_image_capture_lock:
        _spot_poll_running = False
        _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.set()
    thread = _spot_image_capture_thread
    if (getattr(_SPOT_IMAGE_CAPTURE_QUEUE, "unfinished_tasks", 0) > 0
            or _SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.is_set()) and (
        thread is None or not thread.is_alive()
    ):
        _start_spot_image_capture_worker(force=True)
    stopped = stop_spot_image_capture_writer(timeout_sec=timeout_sec)
    with _spot_image_capture_lock:
        failure_count_after = _spot_image_capture_failure_count
        retry_errors = _spot_image_capture_retry_error_count
    return stopped and failure_count_after == 0 and retry_errors == 0


def _reset_spot_image_capture_state_for_tests() -> None:
    global _spot_image_capture_writer, _spot_image_capture_writer_signature, _spot_image_capture_thread
    global _spot_image_capture_enqueued_count, _spot_image_capture_written_count, _spot_image_capture_dropped_count
    global _spot_image_capture_dropped_oversize_count, _spot_image_capture_dropped_queue_full_count
    global _spot_image_capture_dropped_pending_limit_count
    global _spot_image_capture_dropped_payload_limit_count, _spot_image_capture_pending_payload_bytes
    global _spot_image_capture_dropped_invalid_count
    global _spot_image_capture_failure_count, _spot_image_capture_last_enqueue_at, _spot_image_capture_last_write_at
    global _spot_image_capture_last_error_at, _spot_image_capture_last_error_code, _spot_image_capture_last_error_message
    global _spot_image_capture_last_fact, _spot_image_shutdown_baseline
    global _spot_image_capture_last_enqueue_monotonic
    global _spot_image_capture_recovery, _spot_image_capture_retry_at, _spot_image_capture_retry_delay
    global _spot_image_capture_retry_error_count, _spot_image_capture_recovered_count
    global _spot_image_storage_activation, _spot_image_storage_generation
    global _spot_image_initialization_retry_at, _spot_image_initialization_retry_delay
    stop_spot_image_capture_writer(timeout_sec=0.5)
    if _spot_image_capture_recovery is not None:
        _spot_image_capture_recovery = None
        _SPOT_IMAGE_CAPTURE_QUEUE.task_done()
    while True:
        try:
            _SPOT_IMAGE_CAPTURE_QUEUE.get_nowait()
            _SPOT_IMAGE_CAPTURE_QUEUE.task_done()
        except queue.Empty:
            break
    with _spot_image_capture_writer_lock:
        _spot_image_capture_writer = None
        _spot_image_capture_writer_signature = None
    with _spot_image_capture_lock:
        _spot_image_capture_thread = None
        _spot_image_capture_enqueued_count = 0
        _spot_image_capture_written_count = 0
        _spot_image_capture_dropped_count = 0
        _spot_image_capture_dropped_oversize_count = 0
        _spot_image_capture_dropped_queue_full_count = 0
        _spot_image_capture_dropped_pending_limit_count = 0
        _spot_image_capture_dropped_payload_limit_count = 0
        _spot_image_capture_dropped_invalid_count = 0
        _spot_image_capture_pending_payload_bytes = 0
        _spot_image_capture_pending_stages.clear()
        _spot_image_workspace_stages.clear()
        _spot_image_capture_failure_count = 0
        _spot_image_capture_retry_at = None
        _spot_image_capture_retry_delay = 1.0
        _spot_image_capture_retry_error_count = 0
        _spot_image_capture_recovered_count = 0
        _spot_image_capture_last_enqueue_at = 0.0
        _spot_image_capture_last_enqueue_monotonic = None
        _spot_image_capture_last_write_at = 0.0
        _spot_image_capture_last_error_at = 0.0
        _spot_image_capture_last_error_code = None
        _spot_image_capture_last_error_message = None
        _spot_image_capture_last_fact = None
        _spot_image_shutdown_baseline = None
        _spot_image_storage_activation = None
        _spot_image_storage_generation = 0
        _spot_image_initialization_retry_at = None
        _spot_image_initialization_retry_delay = 1.0
    _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.clear()
    _SPOT_IMAGE_CAPTURE_STOP.clear()
    _SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.clear()
    _SPOT_IMAGE_MANIFEST_INITIALIZATION_FAILED.clear()
    _SPOT_IMAGE_CAPTURE_OWNER_RELEASE_FAILED.clear()


def _reset_spot_image_request_state_for_tests() -> None:
    global _img_fetch_lock, _img_cache_entry, _img_refresh_task, _img_accepting_requests, _img_last_source
    global _img_downstream_request_count, _img_upstream_request_count, _img_cache_hit_count
    global _img_http_dispatch_count, _img_storage_suppressed_task_count
    global _img_snapshot_downstream_request_count, _img_live_downstream_request_count
    global _img_singleflight_leader_count, _img_coalesced_waiter_count
    global _img_refresh_success_count, _img_refresh_failure_count
    global _img_cache_clock_anomaly_count
    global _img_last_upstream_started_at, _img_last_upstream_completed_at
    global _img_last_error, _img_failure_count, _img_last_error_code, _img_last_error_message
    global _img_last_success_at

    refresh_task = _img_refresh_task
    if refresh_task is not None and not refresh_task.done():
        refresh_task.cancel()
    _img_fetch_lock = asyncio.Lock()
    _img_cache_entry = None
    _img_refresh_task = None
    _img_accepting_requests = True
    _img_last_source = None
    _img_downstream_request_count = 0
    _img_snapshot_downstream_request_count = 0
    _img_live_downstream_request_count = 0
    _img_upstream_request_count = 0
    _img_http_dispatch_count = 0
    _img_storage_suppressed_task_count = 0
    _img_cache_hit_count = 0
    _img_singleflight_leader_count = 0
    _img_coalesced_waiter_count = 0
    _img_refresh_success_count = 0
    _img_refresh_failure_count = 0
    _img_cache_clock_anomaly_count = 0
    _img_last_upstream_started_at = 0.0
    _img_last_upstream_completed_at = 0.0
    _img_last_error = 0.0
    _img_failure_count = 0
    _img_last_error_code = None
    _img_last_error_message = None
    _img_last_success_at = 0.0


def _reset_spot_diagnostics_request_state_for_tests() -> None:
    global _spot_diagnostics_task
    global _spot_diagnostics_last_started_at, _spot_diagnostics_last_started_monotonic
    global _spot_diagnostics_last_completed_at, _spot_diagnostics_sweep_started_count
    global _spot_diagnostics_upstream_request_count, _spot_diagnostics_suppressed_poll_count
    global _spot_diagnostics_storage_suppressed_request_count
    global _spot_diagnostics_storage_suppressed_poll_count
    global _spot_diagnostics_inflight_suppressed_count
    global _spot_diagnostic_journal_shutdown_started
    global _spot_diagnostic_journal_closed_snapshot
    global _spot_diagnostic_journal_lease_count

    diagnostics_task = _spot_diagnostics_task
    if diagnostics_task is not None and not diagnostics_task.done():
        diagnostics_task.cancel()
    _spot_diagnostics_task = None
    _spot_diagnostics_last_started_at = 0.0
    _spot_diagnostics_last_started_monotonic = None
    _spot_diagnostics_last_completed_at = 0.0
    _spot_diagnostics_sweep_started_count = 0
    _spot_diagnostics_upstream_request_count = 0
    _spot_diagnostics_storage_suppressed_request_count = 0
    _spot_diagnostics_storage_suppressed_poll_count = 0
    _spot_diagnostics_suppressed_poll_count = 0
    _spot_diagnostics_inflight_suppressed_count = 0
    _close_spot_diagnostic_request_journal(timeout_sec=0.5)
    with _spot_diagnostic_journal_lock:
        _spot_diagnostic_journal_lease_count = 0
        _spot_diagnostic_journal_shutdown_started = False
        _spot_diagnostic_journal_closed_snapshot = None


def get_latest_spot_image_capture_fact() -> Dict[str, str]:
    with _spot_image_capture_lock:
        return dict(_spot_image_capture_last_fact or {})


def _spot_image_capture_fact_stats() -> tuple[int, Optional[str], bool]:
    writer = _get_spot_image_capture_writer()
    try:
        return writer.fact_row_count, writer.fact_sha256, True
    except RuntimeError:
        return writer.fact_row_count, None, False


def _spot_image_capture_fact_stats_if_available() -> tuple[Optional[int], Optional[str], bool]:
    if not _spot_image_capture_writer_lock.acquire(blocking=False):
        return None, None, False
    try:
        writer = _spot_image_capture_writer
        if writer is None or _spot_image_capture_writer_signature != _spot_image_capture_config_signature():
            return None, None, False
        snapshot = writer.try_manifest_stats()
        return snapshot if snapshot is not None else (None, None, False)
    finally:
        _spot_image_capture_writer_lock.release()


def get_spot_image_capture_health(*, wait_for_manifest: bool = True) -> Dict[str, Any]:
    fact_row_count, fact_sha256, fact_manifest_state_ready = (
        _spot_image_capture_fact_stats() if wait_for_manifest
        else _spot_image_capture_fact_stats_if_available()
    )
    with _spot_image_capture_lock:
        last_fact = _spot_image_capture_last_fact or {}
        return {
            "enabled": _spot_image_capture_mode() != "off",
            "mode": _spot_image_capture_mode(),
            "queue_size": _SPOT_IMAGE_CAPTURE_QUEUE.qsize(),
            "queue_capacity": _SPOT_IMAGE_CAPTURE_QUEUE_MAX,
            "pending_capture_count": (_spot_image_capture_enqueued_count
                                      - _spot_image_capture_written_count - _spot_image_capture_failure_count),
            "enqueued_count": _spot_image_capture_enqueued_count,
            "written_count": _spot_image_capture_written_count,
            "fact_row_count": fact_row_count,
            "fact_sha256": fact_sha256,
            "fact_manifest_state_ready": fact_manifest_state_ready,
            "manifest_initialization_requested": _SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.is_set(),
            "manifest_initialization_failed": _SPOT_IMAGE_MANIFEST_INITIALIZATION_FAILED.is_set(),
            "owner_release_failed": _SPOT_IMAGE_CAPTURE_OWNER_RELEASE_FAILED.is_set(),
            "dropped_count": _spot_image_capture_dropped_count,
            "dropped_oversize_count": _spot_image_capture_dropped_oversize_count,
            "dropped_queue_full_count": _spot_image_capture_dropped_queue_full_count,
            "dropped_pending_limit_count": _spot_image_capture_dropped_pending_limit_count,
            "dropped_payload_limit_count": _spot_image_capture_dropped_payload_limit_count,
            "dropped_invalid_count": _spot_image_capture_dropped_invalid_count,
            "pending_payload_bytes": _spot_image_capture_pending_payload_bytes,
            "pending_payload_byte_limit": _SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT,
            "failure_count": _spot_image_capture_failure_count,
            "pending_recovery": int(_spot_image_capture_recovery is not None),
            "retry_error_count": _spot_image_capture_retry_error_count,
            "recovered_count": _spot_image_capture_recovered_count,
            "next_retry_at_monotonic": _spot_image_capture_retry_at,
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


def get_spot_image_capture_manifest_stats(
    *,
    fact_path: Path,
    wait_for_manifest: bool = True,
) -> Dict[str, Any] | None:
    if _SPOT_IMAGE_CAPTURE_OWNER_RELEASE_FAILED.is_set():
        raise RuntimeError("SPOT image owner resource release is unconfirmed")
    if _SPOT_IMAGE_MANIFEST_INITIALIZATION_FAILED.is_set():
        raise RuntimeError("SPOT image manifest initialization failed")
    if not wait_for_manifest:
        # CSV startup may precede the image worker or its historical scan. It
        # must neither start that scan nor wait for its lock. Closeout keeps
        # the default blocking, path-bound validation below.
        configured_fact_path = _spot_image_capture_log_path() / SPOT_IMAGE_FACT_FILENAME
        if configured_fact_path.resolve() != fact_path.resolve():
            return None
        if not _spot_image_capture_writer_lock.acquire(blocking=False):
            raise FactPersistencePending("image writer is initializing")
        request_initialization = False
        try:
            writer = _spot_image_capture_writer
            if writer is None or _spot_image_capture_writer_signature != _spot_image_capture_config_signature():
                request_initialization = True
                raise FactPersistencePending("image writer is not ready")
            if writer.fact_path.resolve() != fact_path.resolve():
                return None
            snapshot = writer.try_manifest_stats()
            if snapshot is None:
                raise FactPersistencePending("image manifest is busy")
            fact_row_count, fact_sha256, state_ready = snapshot
            return {
                "fact_row_count": fact_row_count,
                "fact_sha256": fact_sha256,
                "fact_manifest_state_ready": state_ready,
            }
        finally:
            _spot_image_capture_writer_lock.release()
            if request_initialization:
                _request_spot_image_manifest_initialization()
    writer = _get_spot_image_capture_writer()
    if writer.fact_path.resolve() != fact_path.resolve():
        return None
    fact_row_count, fact_sha256, state_ready = _spot_image_capture_fact_stats()
    return {
        "fact_row_count": fact_row_count,
        "fact_sha256": fact_sha256,
        "fact_manifest_state_ready": state_ready,
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
    capture_id: Optional[str] = None,
) -> ImageCaptureAdmissionResult:
    # The publisher holds the same lock only while swapping prepared values.
    # Capture policy, limits, and writer settings therefore belong to one state.
    with config.PERSISTENCE_CONFIG_LOCK:
        return _enqueue_spot_image_capture_locked(
            image_bytes=image_bytes, captured_at=captured_at, image_url=image_url,
            source=source, image_age_ms=image_age_ms,
            capture_id=capture_id,
        )


def _enqueue_spot_image_capture_locked(
    *,
    image_bytes: bytes,
    captured_at: float,
    image_url: str,
    source: str,
    image_age_ms: Optional[float],
    capture_id: Optional[str],
) -> ImageCaptureAdmissionResult:
    global _spot_image_capture_dropped_count, _spot_image_capture_enqueued_count, _spot_image_capture_last_enqueue_at
    global _spot_image_capture_dropped_oversize_count, _spot_image_capture_dropped_queue_full_count
    global _spot_image_capture_dropped_pending_limit_count
    global _spot_image_capture_dropped_payload_limit_count, _spot_image_capture_pending_payload_bytes
    global _spot_image_capture_dropped_invalid_count
    global _spot_image_capture_last_error_at, _spot_image_capture_last_error_code, _spot_image_capture_last_error_message
    global _spot_image_capture_last_enqueue_monotonic
    if _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set():
        return ImageCaptureAdmissionResult("REJECTED_CLOSED", "persistence_closed", capture_id)
    mode = _spot_image_capture_mode()
    if mode == "off":
        return ImageCaptureAdmissionResult("DISABLED", "capture_disabled", capture_id)
    max_bytes = int(getattr(config, "SPOT_IMAGE_CAPTURE_MAX_BYTES", 2_000_000) or 1)
    if len(image_bytes) > max_bytes:
        with _spot_image_capture_lock:
            _spot_image_capture_dropped_count += 1
            _spot_image_capture_dropped_oversize_count += 1
        return ImageCaptureAdmissionResult("REJECTED_LIMIT", "image_too_large", capture_id)
    link_checked_at: Optional[float] = None
    snapshot = None
    if bool(getattr(config, "SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION", True)):
        link_checked_at = time.time()
        snapshot = get_spot_temperature_poll_snapshot()
    if not _should_enqueue_spot_image_capture(mode, snapshot):
        return ImageCaptureAdmissionResult("DISABLED", "policy_skipped_mode", capture_id)
    min_interval_sec = max(0.0, float(getattr(config, "SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC", 1.0) or 0.0))
    monotonic_now = time.monotonic()
    with _spot_image_capture_lock:
        if _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set():
            return ImageCaptureAdmissionResult("REJECTED_CLOSED", "persistence_closed", capture_id)
        if _image_probe_manual_recovery_required():
            _spot_image_capture_dropped_count += 1
            return ImageCaptureAdmissionResult("REJECTED_UNAVAILABLE", "image_probe_manual_recovery", capture_id)
        if (min_interval_sec > 0.0 and _spot_image_capture_last_enqueue_monotonic is not None
                and monotonic_now - _spot_image_capture_last_enqueue_monotonic < min_interval_sec):
            return ImageCaptureAdmissionResult("DISABLED", "policy_skipped_interval", capture_id)
        # The single writer owns a dequeued capture until task_done. Include it
        # in admission rather than freeing its reservation at queue.get().
        with _SPOT_IMAGE_CAPTURE_QUEUE.mutex:
            pending = _SPOT_IMAGE_CAPTURE_QUEUE.unfinished_tasks
            queued = len(_SPOT_IMAGE_CAPTURE_QUEUE.queue)
        if pending >= _SPOT_IMAGE_CAPTURE_QUEUE_MAX:
            _spot_image_capture_dropped_count += 1
            if queued >= _SPOT_IMAGE_CAPTURE_QUEUE.maxsize:
                _spot_image_capture_dropped_queue_full_count += 1
                return ImageCaptureAdmissionResult("REJECTED_FULL", "queue_full", capture_id)
            _spot_image_capture_dropped_pending_limit_count += 1
            return ImageCaptureAdmissionResult("REJECTED_LIMIT", "pending_item_limit", capture_id)
        available = _SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT - _spot_image_capture_pending_payload_bytes
    reserved_bytes = transferred_bytes = 0
    prepared_snapshot = snapshot_payload = event = None
    try:
        workspace = text_bytes = 0
        if snapshot is not None:
            prepared_snapshot, payload_bound, characters, width = prepare_json_payload(
                snapshot, available - len(image_bytes),
            )
            text_bytes = characters * width
            # Preflight uses spaced JSON, an upper bound for the existing
            # compact/sorted wire bytes. Joining chunks owns two text copies.
            workspace = max(2 * text_bytes, text_bytes + payload_bound)
        required = len(image_bytes) + workspace
        with _spot_image_capture_lock:
            if _spot_image_capture_pending_payload_bytes + required > _SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT:
                raise PayloadBudgetExceeded
            _spot_image_capture_pending_payload_bytes += required
            reserved_bytes = required
        # No image-accounting lock is held during JSON traversal or encoding.
        if prepared_snapshot is not None:
            snapshot_payload = encode_json_payload(prepared_snapshot, sort_keys=True, compact=True)
            if len(snapshot_payload) > payload_bound:
                raise ValueError("Image snapshot exceeded its preflight bound")
        payload_size = len(image_bytes) + (len(snapshot_payload) if snapshot_payload is not None else 0)
        signature = _spot_image_capture_config_signature()
        fact_key = _image_destination_key(signature[0] / SPOT_IMAGE_FACT_FILENAME)
        try:
            day = datetime.fromtimestamp(captured_at, timezone.utc)
            jpeg_key = _image_destination_key(signature[1] / day.strftime('%Y/%m/%d'))
        except (ValueError, OverflowError, OSError):
            jpeg_key = ""  # Invalid legacy timestamp remains unknown until the writer rejects it.
        event = _SpotImageCaptureEvent(
            image_bytes=bytes(image_bytes), captured_at=captured_at, source_url=image_url,
            source=source, image_age_ms=image_age_ms, link_checked_at=link_checked_at,
            observation_snapshot=snapshot_payload, reserved_payload_bytes=payload_size,
            writer_signature=signature, capture_id=capture_id,
            snapshot_text_storage_bytes=text_bytes,
        )
        with _spot_image_capture_lock:
            if _SPOT_IMAGE_CAPTURE_ENQUEUE_DISABLED.is_set():
                return ImageCaptureAdmissionResult("REJECTED_CLOSED", "persistence_closed", capture_id)
            if _image_probe_manual_recovery_required():
                _spot_image_capture_dropped_count += 1
                return ImageCaptureAdmissionResult("REJECTED_UNAVAILABLE", "image_probe_manual_recovery", capture_id)
            try:
                _SPOT_IMAGE_CAPTURE_QUEUE.put_nowait(event)
            except queue.Full:
                _spot_image_capture_dropped_count += 1
                _spot_image_capture_dropped_queue_full_count += 1
                return ImageCaptureAdmissionResult("REJECTED_FULL", "queue_full", capture_id)
            transferred_bytes = payload_size
            admitted_monotonic = time.monotonic()
            _bind_spot_image_activation_locked((mode, signature))
            _spot_image_capture_pending_stages[id(event)] = _ImageCapturePendingStage(
                admitted_monotonic, clock_domain_id(), _spot_image_storage_generation,
                (("image_fact", fact_key), ("image_jpeg", jpeg_key)), payload_size)
            _spot_image_capture_enqueued_count += 1
            _spot_image_capture_last_enqueue_at = time.time()
            _spot_image_capture_last_enqueue_monotonic = admitted_monotonic
    except PayloadBudgetExceeded:
        with _spot_image_capture_lock:
            _spot_image_capture_dropped_count += 1
            _spot_image_capture_dropped_payload_limit_count += 1
        return ImageCaptureAdmissionResult("REJECTED_LIMIT", "pending_byte_limit", capture_id)
    except (TypeError, ValueError, OverflowError, RecursionError):
        # Persistence cannot serialize this link; it must not fail live viewing.
        with _spot_image_capture_lock:
            _spot_image_capture_dropped_count += 1
            _spot_image_capture_dropped_invalid_count += 1
            _spot_image_capture_last_error_at = time.time()
            _spot_image_capture_last_error_code = "snapshot_serialization_failed"
            _spot_image_capture_last_error_message = "capture observation snapshot is not serializable"
        return ImageCaptureAdmissionResult("INVALID", "snapshot_serialization_failed", capture_id)
    finally:
        # Only the queued event may retain the snapshot when returning the
        # serialization workspace; failed admission retains no new bytes.
        prepared_snapshot = snapshot_payload = event = None
        if reserved_bytes:
            with _spot_image_capture_lock:
                _spot_image_capture_pending_payload_bytes -= reserved_bytes - transferred_bytes
    _start_spot_image_capture_worker()
    return ImageCaptureAdmissionResult("ACCEPTED", None, capture_id)


def _format_exception_message(exc: BaseException) -> str:
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


def _exception_chain(exc: BaseException) -> Iterable[BaseException]:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        if current.__cause__ is not None:
            current = current.__cause__
        elif not current.__suppress_context__:
            current = current.__context__
        else:
            current = None


def _transport_error_details(exc: BaseException) -> tuple[str, Optional[int]]:
    chain = tuple(_exception_chain(exc))
    transport_error_type = exc.__class__.__name__
    for candidate in chain:
        if isinstance(candidate, (SpotTransportError, SpotPortPoolError)):
            transport_error_type = candidate.__class__.__name__
            break

    for candidate in chain:
        if not isinstance(candidate, OSError):
            continue
        for attribute in ("winerror", "errno"):
            value = getattr(candidate, attribute, None)
            if isinstance(value, int) and not isinstance(value, bool):
                return transport_error_type, value
    return transport_error_type, None


def _response_body_preview(response: httpx.Response, max_chars: int) -> str:
    body = response.text.strip()
    if len(body) <= max_chars:
        return body
    return body[:max_chars]


def _response_content_type(response: httpx.Response) -> str:
    return str(response.headers.get("content-type") or "").strip()


def _is_jpeg_payload(data: bytes) -> bool:
    if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        return False
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "JPEG":
                return False
            image.verify()
    except (OSError, UnidentifiedImageError, ValueError):
        return False
    return True


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


def _validate_spot_image_response(
    response: httpx.Response,
    image_url: str,
    data: bytes,
    *,
    transport_correlation_id: Optional[str] = None,
) -> None:
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
            transport_correlation_id=transport_correlation_id,
        )
    if not _is_jpeg_payload(data):
        raise SpotImageFetchError(
            "invalid-image-payload",
            (
                "SPOT image upstream returned a non-image payload; "
                f"url={image_url}; status_code={response.status_code}; "
                f"content_type={content_type}; body={_response_body_preview(response, 200)}"
            ),
            image_url=image_url,
            upstream_status=response.status_code,
            transport_correlation_id=transport_correlation_id,
        )


def _resolve_spot_image_url() -> str:
    spot_host = str(config.SPOT_IP or "").strip()
    if not spot_host or any(character.isspace() for character in spot_host):
        raise SpotImageConfigError("")

    parsed = urlsplit(f"http://{spot_host}")
    if (
        parsed.scheme != "http"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise SpotImageConfigError("")
    hostname = parsed.hostname or ""
    host_labels = hostname.split(".")
    if not host_labels or any(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) is None
        for label in host_labels
    ):
        raise SpotImageConfigError("")
    try:
        port = parsed.port
    except ValueError as exc:
        raise SpotImageConfigError("") from exc
    authority = hostname if port is None else f"{hostname}:{port}"
    return f"http://{authority}/image.jpg"


def _spot_image_refresh_interval_sec() -> float:
    try:
        configured_interval = float(config.SPOT_REFRESH_INTERVAL)
    except (TypeError, ValueError):
        return _SPOT_IMAGE_REFRESH_INTERVAL_DEFAULT_SEC
    if not math.isfinite(configured_interval) or configured_interval <= 0.0:
        return _SPOT_IMAGE_REFRESH_INTERVAL_DEFAULT_SEC
    return min(
        _SPOT_IMAGE_REFRESH_INTERVAL_MAX_SEC,
        max(_SPOT_IMAGE_REFRESH_INTERVAL_MIN_SEC, configured_interval),
    )


def _normalize_spot_image_profile(profile: str) -> SpotImageProfile:
    if profile == _SPOT_IMAGE_PROFILE_SNAPSHOT:
        return _SPOT_IMAGE_PROFILE_SNAPSHOT
    if profile == _SPOT_IMAGE_PROFILE_OPERATOR_LIVE:
        return _SPOT_IMAGE_PROFILE_OPERATOR_LIVE
    raise ValueError(f"unsupported SPOT image profile: {profile}")


def _spot_poll_interval_sec() -> float:
    try:
        configured_interval = float(config.SPOT_REFRESH_INTERVAL)
    except (TypeError, ValueError):
        configured_interval = 1.0
    if not math.isfinite(configured_interval) or configured_interval <= 0.0:
        configured_interval = 1.0
    return max(0.5, configured_interval)


def _spot_diagnostics_refresh_interval_sec() -> float:
    return max(
        _SPOT_DIAGNOSTICS_REFRESH_INTERVAL_MIN_SEC,
        _spot_poll_interval_sec(),
    )


def _spot_non_image_background_request_rates() -> Dict[str, float]:
    poll_interval = _spot_poll_interval_sec()
    temperature_rate = 1.0 / poll_interval if str(config.SPOT_URL or "").strip() else 0.0
    internal_temperature_rate = (
        1.0 / poll_interval
        if str(config.SPOT_INTERNAL_TEMPERATURE_URL or "").strip()
        else 0.0
    )
    diagnostics_rate = (
        len(_SPOT_DIAGNOSTIC_OUTPUT_PARAMS) / _spot_diagnostics_refresh_interval_sec()
        if str(config.SPOT_URL or "").strip()
        else 0.0
    )
    return {
        "temperature": temperature_rate,
        "internal_temperature": internal_temperature_rate,
        "diagnostics": diagnostics_rate,
    }


def _spot_live_image_max_per_sec() -> float:
    non_image_rate = sum(_spot_non_image_background_request_rates().values())
    remaining_rate = _SPOT_BACKGROUND_REQUEST_BUDGET_TARGET_PER_SEC - non_image_rate
    return max(
        _SPOT_LIVE_IMAGE_MIN_PER_SEC,
        min(_SPOT_LIVE_IMAGE_DESIRED_MAX_PER_SEC, remaining_rate),
    )


def _spot_live_image_refresh_interval_sec() -> float:
    return 1.0 / _spot_live_image_max_per_sec()


def get_spot_live_image_refresh_interval_sec() -> float:
    """Return the server-owned operator image cadence in seconds."""
    return _spot_live_image_refresh_interval_sec()


def _spot_image_cache_ttl_sec(profile: SpotImageProfile) -> float:
    if profile == _SPOT_IMAGE_PROFILE_OPERATOR_LIVE:
        return _spot_live_image_refresh_interval_sec()
    return _spot_image_refresh_interval_sec()


def _spot_background_request_budget() -> Dict[str, float | bool | str]:
    non_image_rates = _spot_non_image_background_request_rates()
    image_rate = _spot_live_image_max_per_sec() if str(config.SPOT_IP or "").strip() else 0.0
    temperature_rate = non_image_rates["temperature"]
    internal_temperature_rate = non_image_rates["internal_temperature"]
    diagnostics_rate = non_image_rates["diagnostics"]
    total_rate = image_rate + temperature_rate + internal_temperature_rate + diagnostics_rate
    return {
        "request_budget_policy_version": _SPOT_REQUEST_BUDGET_POLICY_VERSION,
        "request_budget_target_max_per_sec": _SPOT_BACKGROUND_REQUEST_BUDGET_TARGET_PER_SEC,
        "request_budget_image_max_per_sec": round(image_rate, 6),
        "request_budget_temperature_max_per_sec": round(temperature_rate, 6),
        "request_budget_internal_temperature_max_per_sec": round(
            internal_temperature_rate,
            6,
        ),
        "request_budget_diagnostics_max_per_sec": round(diagnostics_rate, 6),
        "request_budget_total_background_max_per_sec": round(total_rate, 6),
        "request_budget_within_target": total_rate
        <= _SPOT_BACKGROUND_REQUEST_BUDGET_TARGET_PER_SEC,
    }


def _spot_image_cache_age_ms(
    entry: _SpotImageCacheEntry,
    *,
    now_monotonic: Optional[float] = None,
) -> float:
    now_value = time.monotonic() if now_monotonic is None else now_monotonic
    return max(0.0, (now_value - entry.captured_at_monotonic) * 1000.0)


def _is_spot_image_cache_fresh(
    entry: Optional[_SpotImageCacheEntry],
    *,
    profile: SpotImageProfile = _SPOT_IMAGE_PROFILE_SNAPSHOT,
    now_monotonic: Optional[float] = None,
    record_clock_anomaly: bool = False,
    expected_image_url: Optional[str] = None,
) -> bool:
    global _img_cache_clock_anomaly_count
    if entry is None:
        return False
    if expected_image_url is not None and entry.image_url != expected_image_url:
        return False
    now_value = time.monotonic() if now_monotonic is None else now_monotonic
    age_seconds = now_value - entry.captured_at_monotonic
    if age_seconds < 0.0:
        if record_clock_anomaly:
            _img_cache_clock_anomaly_count += 1
            _logger.warning(
                "SPOT image cache monotonic clock moved backwards",
                extra={"code": "spot-image-cache-clock-anomaly"},
            )
        return False
    return age_seconds < _spot_image_cache_ttl_sec(profile)


def _spot_image_response(
    entry: _SpotImageCacheEntry,
    *,
    profile: SpotImageProfile,
    source: str,
    upstream_suppressed: bool = False,
) -> tuple[bytes, Dict[str, Any]]:
    global _img_last_source
    _img_last_source = source
    return entry.image_bytes, {
        "status": "ok",
        "source": source,
        "captured_at": entry.captured_at_epoch,
        "latency_ms": entry.upstream_latency_ms,
        "age_ms": _spot_image_cache_age_ms(entry),
        "image_path": "/image.jpg",
        "profile": profile,
        "image_upstream_suppressed": upstream_suppressed,
        "suppression_reason": "storage_pressure" if upstream_suppressed else None,
        "retry_after_sec": math.ceil(max(1.0, _spot_image_cache_ttl_sec(profile))) if upstream_suppressed else None,
    }


def _spot_auxiliary_dispatch_storage_blocked() -> bool:
    return (_storage_pressure_monitor is not None
            and _storage_pressure_monitor.snapshot().state == "PERSISTENCE_BLOCKED")


def _spot_image_pressure_response(profile: SpotImageProfile) -> tuple[bytes, Dict[str, Any]]:
    global _img_cache_hit_count
    image_url = _resolve_spot_image_url()
    entry = _img_cache_entry
    if entry is not None and entry.image_url == image_url:
        _img_cache_hit_count += 1
        return _spot_image_response(entry, profile=profile, source="cache", upstream_suppressed=True)
    raise SpotStoragePressureError(math.ceil(max(1.0, _spot_image_cache_ttl_sec(profile))))


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


def _resolve_spot_diagnostic_url(param: str) -> str:
    if param != "appnumber":
        return _resolve_spot_output_url(param)

    base_url = str(config.SPOT_URL or "").strip() or f"http://{config.SPOT_IP}/output?p=temperature"
    parts = urlsplit(base_url)
    if not parts.scheme or not parts.netloc:
        raise SpotTemperatureConfigError(base_url)
    return urlunsplit((parts.scheme, parts.netloc, "/control", urlencode({"p": param}), ""))


def _spot_diagnostics_max_age_sec() -> float:
    configured_max_age_sec = (
        configured_diagnostics_max_age_ms(config.SPOT_REFRESH_INTERVAL) / 1000.0
    )
    return max(
        configured_max_age_sec,
        _spot_diagnostics_refresh_interval_sec() * 2.0,
    )


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


async def _request_spot_diagnostic_output(
    client: httpx.AsyncClient,
    param: str,
    *,
    journal: SpotDiagnosticRequestJournal | None = None,
    request_context: SpotDiagnosticRequestContext | None = None,
) -> tuple[str, str]:
    global _spot_diagnostics_upstream_request_count
    global _spot_diagnostics_storage_suppressed_request_count

    url = _resolve_spot_diagnostic_url(param)
    async with _spot_device_request_lock:
        if _spot_auxiliary_dispatch_storage_blocked():
            _spot_diagnostics_storage_suppressed_request_count += 1
            raise SpotStoragePressureError()
        if journal is not None and request_context is not None:
            journal.mark_running(request_context)
        _spot_diagnostics_upstream_request_count += 1
        response = await _request_spot_http_response(
            client,
            kind=SpotRequestKind.DIAGNOSTIC,
            method="GET",
            url=url,
            correlation_id=(
                request_context.transport_correlation_id if request_context is not None else None
            ),
        )
        response.raise_for_status()
    return param, response.text.strip()[:_SPOT_DIAGNOSTIC_TEXT_MAX_CHARS]


def _diagnostic_exception_field_status(exc: BaseException) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPError):
        return "http_error"
    return "parse_error"


def _diagnostic_timeout_phase(exc: BaseException) -> str:
    if isinstance(exc, httpx.ConnectTimeout) or isinstance(exc.__cause__, SpotTransportConnectTimeout):
        return "connect"
    if isinstance(exc, httpx.ReadTimeout) or isinstance(exc.__cause__, SpotTransportReadTimeout):
        return "response"
    if isinstance(exc, httpx.WriteTimeout):
        return "write"
    if isinstance(exc, httpx.PoolTimeout):
        return "pool"
    return "unknown"


def _diagnostic_journal_error_outcome(exc: BaseException) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return "http_error"
    if isinstance(exc, httpx.RequestError):
        return "transport_error"
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

    snapshot_id = _next_spot_diagnostics_snapshot_id()
    poll_correlation_id = (
        f"{poll_context.service_instance_id}:poll:{poll_context.poll_seq}"
        if poll_context is not None
        else "poll:none"
    )
    journal = await _acquire_spot_diagnostic_request_journal_for_sweep()
    results: dict[str, tuple[str, str] | BaseException] = {}
    try:
        for param in _SPOT_DIAGNOSTIC_OUTPUT_PARAMS:
            api_route = "/control" if param == "appnumber" else "/output"
            request_context = journal.queue_request(
                snapshot_correlation_id=snapshot_id,
                poll_correlation_id=poll_correlation_id,
                diagnostic_field=param,
                api_route=api_route,
            )
            try:
                request_result = await _request_spot_diagnostic_output(
                    client,
                    param,
                    journal=journal,
                    request_context=request_context,
                )
            except asyncio.CancelledError as exc:
                journal.mark_cancelled(request_context, exception=exc)
                raise
            except SpotStoragePressureError as exc:
                journal.mark_completed(request_context, outcome="storage_pressure")
                results[param] = exc
                break
            except httpx.TimeoutException as exc:
                journal.mark_timed_out(
                    request_context,
                    exception=exc,
                    timeout_phase=_diagnostic_timeout_phase(exc),
                )
                results[param] = exc
            except Exception as exc:
                journal.mark_completed(
                    request_context,
                    outcome=_diagnostic_journal_error_outcome(exc),
                    exception=exc,
                )
                results[param] = exc
            else:
                _key, value = request_result
                journal.mark_completed(
                    request_context,
                    outcome=_diagnostic_value_field_status(param, value),
                )
                results[param] = request_result
    finally:
        _release_spot_diagnostic_request_journal(journal)
    payload: Dict[str, Any] = {}
    raw_values: dict[str, str] = {}
    errors: list[str] = []
    field_status: dict[str, str] = {}
    for param in _SPOT_DIAGNOSTIC_OUTPUT_PARAMS:
        result = results.get(param)
        if result is None:
            field_status[param] = "not_requested"
            continue
        if isinstance(result, SpotStoragePressureError):
            field_status[param] = "storage_pressure"
            continue
        if isinstance(result, BaseException):
            field_status[param] = _diagnostic_exception_field_status(result)
            errors.append(f"{result.__class__.__name__}: {_format_exception_message(result)}")
            continue
        key, value = result
        raw_values[key] = value
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
        capture_status = "error" if errors else "missing"
    elif missing_fields:
        capture_status = "async_partial"
    else:
        capture_status = "async_complete"
    snapshot = DiagnosticSnapshot(
        snapshot_id=snapshot_id,
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
    # Preserve the already bounded HTTP-200 body for audit only. Invalid raw
    # values remain absent from the operational payload and cannot affect cause
    # classification.
    snapshot["diagnostics_raw_values"] = raw_values
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
    global _spot_diagnostics_last_completed_at

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
    finally:
        _spot_diagnostics_last_completed_at = time.time()


async def _request_spot_image(client: httpx.AsyncClient, image_url: str) -> bytes:
    global _img_http_dispatch_count, _img_storage_suppressed_task_count
    request_started_at: Optional[float] = None
    transport_correlation_id = f"transport:{uuid4().hex}"
    try:
        async with _spot_device_request_lock:
            if _spot_auxiliary_dispatch_storage_blocked():
                _img_storage_suppressed_task_count += 1
                raise SpotStoragePressureError
            request_started_at = time.monotonic()
            _img_http_dispatch_count += 1
            response = await _request_spot_http_response(
                client,
                kind=SpotRequestKind.IMAGE,
                method="GET",
                url=image_url,
                connect_timeout_sec=2.0,
                read_timeout_sec=5.0,
                max_response_bytes=HARD_MAX_RESPONSE_BYTES,
                correlation_id=transport_correlation_id,
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        transport_error_type, transport_os_error_code = _transport_error_details(exc)
        request_elapsed_ms = (
            max(0.0, (time.monotonic() - request_started_at) * 1000.0)
            if request_started_at is not None
            else None
        )
        elapsed_text = "unknown" if request_elapsed_ms is None else f"{request_elapsed_ms:.1f}"
        raise SpotImageFetchError(
            "upstream-timeout",
            (
                "SPOT image upstream timed out; "
                f"url={image_url}; error_type={transport_error_type}; "
                f"request_elapsed_ms={elapsed_text}; error={_format_exception_message(exc)}"
            ),
            image_url=image_url,
            upstream_status=None,
            transport_error_type=transport_error_type,
            transport_os_error_code=transport_os_error_code,
            transport_correlation_id=transport_correlation_id,
            request_elapsed_ms=request_elapsed_ms,
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
            transport_correlation_id=transport_correlation_id,
        ) from exc
    except httpx.RequestError as exc:
        transport_error_type, transport_os_error_code = _transport_error_details(exc)
        request_elapsed_ms = (
            max(0.0, (time.monotonic() - request_started_at) * 1000.0)
            if request_started_at is not None
            else None
        )
        elapsed_text = "unknown" if request_elapsed_ms is None else f"{request_elapsed_ms:.1f}"
        raise SpotImageFetchError(
            "upstream-request-error",
            (
                "SPOT image upstream request failed; "
                f"url={image_url}; error_type={transport_error_type}; "
                f"request_elapsed_ms={elapsed_text}; error={_format_exception_message(exc)}"
            ),
            image_url=image_url,
            upstream_status=None,
            transport_error_type=transport_error_type,
            transport_os_error_code=transport_os_error_code,
            transport_correlation_id=transport_correlation_id,
            request_elapsed_ms=request_elapsed_ms,
        ) from exc

    data = response.content
    if not data:
        raise SpotImageFetchError(
            "empty-body",
            f"SPOT image upstream returned an empty body; url={image_url}",
            image_url=image_url,
            upstream_status=response.status_code,
            transport_correlation_id=transport_correlation_id,
        )
    _validate_spot_image_response(
        response,
        image_url,
        data,
        transport_correlation_id=transport_correlation_id,
    )
    return data


async def _request_spot_temperature_observation(
    client: httpx.AsyncClient,
    temp_url: str,
    *,
    request_kind: SpotRequestKind = SpotRequestKind.TEMPERATURE,
) -> tuple[float, SpotRawClassification]:
    try:
        async with _spot_device_request_lock:
            response = await _request_spot_http_response(
                client,
                kind=request_kind,
                method="GET",
                url=temp_url,
            )
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
        temperature, _classification = await _request_spot_temperature_observation(
            client,
            temp_url,
            request_kind=SpotRequestKind.INTERNAL_TEMPERATURE,
        )
        return temperature
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
    global _img_last_success_at

    _img_failure_count = 0
    _img_last_error_code = None
    _img_last_error_message = None
    _img_last_success_at = time.time()


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
    temp_time = float(_temperature_cache.get("temp_time") or 0.0)
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


def _spot_poll_freshness_threshold_sec() -> Optional[float]:
    refresh_interval = finite_number(getattr(config, "SPOT_REFRESH_INTERVAL", 1.0))
    if refresh_interval is None or refresh_interval <= 0:
        return None
    return refresh_interval * 3.0


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
        clock_domain=clock_domain_id(),
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

    with _spot_observation_fact_writer_lock:
        if _spot_observation_fact_writer is None:
            _spot_observation_fact_writer = SpotObservationFactWriter(
                _spot_observation_fact_path()
            )
        return _spot_observation_fact_writer


def _write_spot_observation_fact_safely(snapshot: Dict[str, Any]) -> None:
    if not bool(getattr(config, "SPOT_OBSERVATION_FACT_ENABLED", False)):
        return
    try:
        _get_spot_observation_fact_writer().write_fact(snapshot)
    except Exception:
        writer = _get_spot_observation_fact_writer()
        writer.failure_count += 1


async def _write_spot_observation_fact_async(snapshot: Dict[str, Any]) -> None:
    if not bool(getattr(config, "SPOT_OBSERVATION_FACT_ENABLED", False)):
        return
    admission = _get_spot_observation_queue().enqueue_detailed(snapshot)
    if not admission.accepted:
        _logger.error("SPOT observation persistence rejected an event", extra={
            "code": "spot-fact-enqueue-rejected",
            "admission_status": admission.status,
            "admission_reason": admission.reason,
            "observation_key": admission.observation_key,
        })


def spot_observation_fact_writes_drained() -> bool:
    if _spot_observation_queue is not None:
        return bool(_spot_observation_queue.snapshot()["writes_drained"])
    if any(not task.done() for task in _spot_observation_fact_write_tasks):
        return False
    writer = _spot_observation_fact_writer
    if writer is None:
        return True
    try:
        return writer.failure_count == 0 and writer.spool_pending_count() == 0
    except Exception:
        return False


def spot_observation_fact_closeout_deferred(fact_path: Path) -> bool:
    """Only a healthy active owner at this path may defer a runtime rollover."""
    if not config.SPOT_OBSERVATION_FACT_ENABLED or _spot_observation_queue is None:
        return False
    if _spot_observation_queue_path != fact_path.resolve():
        return False
    state = _spot_observation_queue.snapshot()
    return bool(state["accepting"] and state["initialization_state"] != "failed"
                and not state["write_failure_count"] and not state["rejected_count"]
                and not state["spool_failure_count"] and not state["spool_pending_count"])


async def wait_for_spot_observation_fact_writes_drain(
    timeout_sec: Optional[float] = None,
) -> bool:
    if timeout_sec is None:
        timeout_sec = _SPOT_OBSERVATION_FACT_DRAIN_TIMEOUT_SEC
    if _spot_observation_queue is not None:
        return await asyncio.to_thread(_spot_observation_queue.close, timeout_sec)
    pending_tasks = tuple(
        task for task in _spot_observation_fact_write_tasks if not task.done()
    )
    if pending_tasks:
        _done, pending = await asyncio.wait(
            pending_tasks,
            timeout=max(0.0, timeout_sec),
        )
        if pending:
            _logger.warning(
                "SPOT observation fact writes exceeded the final drain timeout",
                extra={
                    "code": "spot-observation-fact-final-drain-timeout",
                    "pending_write_count": len(pending),
                    "timeout_sec": timeout_sec,
                },
            )
    return spot_observation_fact_writes_drained()


def get_spot_observation_fact_health() -> Dict[str, Any]:
    writer = _spot_observation_fact_writer
    queue_health = _spot_observation_queue.snapshot() if _spot_observation_queue is not None else None
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
        "write_failure_count": (queue_health["write_failure_count"] + queue_health["rejected_count"]
                                if queue_health is not None else int(writer.failure_count) if writer is not None else 0),
        "spool_pending_count": (queue_health["spool_pending_count"] if queue_health is not None
                                else int(writer.spool_pending_count()) if writer is not None else 0),
        "persistence": queue_health,
        "pending_write_count": queue_health["pending_write_count"] if queue_health is not None else sum(
            not task.done()
            for task in _spot_observation_fact_write_tasks
        ),
        "writes_drained": spot_observation_fact_writes_drained(),
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
        "diagnostics_age_ms": None,
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
    if captured_monotonic is not None:
        # Invalid completion proof must not crash publication or use an epoch fallback.
        endpoints = (poll_completed_monotonic, captured_monotonic)
        if all(isinstance(value, (float, int)) and not isinstance(value, bool) for value in endpoints):
            age_ms, status = monotonic_age_ms(*endpoints)
            if status == "ok" and age_ms is not None:
                age_sec = age_ms / 1000.0
            elif status == "clock_anomaly":
                age_sec = -1.0  # Preserve the existing future-clock binding suppression.
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
        f"{age_sec * 1000.0:.3f}" if age_sec is not None and age_sec >= 0 else None
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
    poll_started_monotonic: Optional[float] = None,
    poll_clock_domain: Optional[str] = None,
) -> Dict[str, Any]:
    global _spot_observation_seq
    global _spot_temperature_snapshot
    global _spot_last_valid_value_at
    global _spot_last_valid_value_monotonic
    global _spot_temperature_cache_suppressed_until_valid

    from backend.FacilityData.freshness import spot_poll_duration
    duration_ms, duration_status = spot_poll_duration(
        poll_started_monotonic, poll_completed_monotonic, poll_clock_domain)
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
            observed_temperature = classification.parsed_temperature_c
            if (
                observed_temperature is not None
                and not isinstance(observed_temperature, bool)
                and math.isfinite(float(observed_temperature))
            ):
                _temperature_cache["temp"] = float(observed_temperature)
                _temperature_cache["temp_time"] = poll_completed_at
            _spot_last_valid_value_at = poll_completed_at
            _spot_last_valid_value_monotonic = effective_completed_monotonic
            _spot_temperature_cache_suppressed_until_valid = False
        elif classification.raw_validity == SpotRawValidity.INVALID_SENTINEL:
            _spot_temperature_cache_suppressed_until_valid = True
        elif classification.raw_validity == SpotRawValidity.VERIFIED_NO_TARGET:
            _temperature_cache["temp"] = 0.0
            _temperature_cache["temp_time"] = 0.0
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
            "spot_poll_duration_ms": duration_ms,
            "spot_poll_duration_status": duration_status,
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
    return snapshot_for_fact


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
    if snapshot.get("_spot_last_poll_completed_monotonic") is not None:
        age_ms, clock_status = monotonic_age_ms(now_monotonic, snapshot.get("_spot_last_poll_completed_monotonic"))
        if clock_status != "ok" or age_ms is None:
            return SpotSourceFreshness.UNKNOWN
        threshold = finite_number(_spot_poll_freshness_threshold_sec())
        if threshold is None or threshold <= 0:
            return SpotSourceFreshness.UNKNOWN
        if age_ms > threshold * 1000.0:
            return SpotSourceFreshness.STALE
        return SpotSourceFreshness.FRESH
    completed_at = snapshot.get("_spot_last_poll_completed_at_epoch")
    if not isinstance(completed_at, (float, int)) or completed_at <= 0:
        return SpotSourceFreshness.UNKNOWN
    age = finite_number(now - float(completed_at))
    if age is None or age < 0:
        return SpotSourceFreshness.UNKNOWN
    threshold = _spot_poll_freshness_threshold_sec()
    if threshold is None:
        return SpotSourceFreshness.UNKNOWN
    if age > threshold:
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


def _effective_spot_temperature_for_decision(
    decision: TemperatureStateDecision,
    cached_temperature: Any,
) -> Optional[float]:
    if decision.temperature_value_origin.value == "none":
        return None
    if isinstance(cached_temperature, bool) or not isinstance(cached_temperature, (float, int)):
        return None
    return float(cached_temperature)


def _build_spot_temperature_snapshot_diagnostics(now: float) -> Dict[str, Any]:
    now_monotonic = time.monotonic()
    with _spot_temperature_snapshot_lock:
        snapshot = dict(_spot_temperature_snapshot) if _spot_temperature_snapshot is not None else None
        poll_seq = _spot_poll_seq
        observation_seq = _spot_observation_seq
        last_valid_value_at = _spot_last_valid_value_at
        last_valid_value_monotonic = _spot_last_valid_value_monotonic
        cached_temperature = _temperature_cache.get("temp")

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
            "spot_poll_duration_status": "not_attempted",
            "spot_response_content_length": None,
            "spot_raw_payload_hash": None,
            "spot_device_status_code": None,
            "spot_error_code": None,
        }

    source_freshness = _spot_source_freshness_for_snapshot(snapshot, now, now_monotonic)
    poll_status = SpotPollStatus(str(snapshot["spot_poll_status"]))
    raw_validity = SpotRawValidity(str(snapshot["spot_raw_validity"]))
    value_age_ms, value_clock_status = monotonic_age_ms(now_monotonic, last_valid_value_monotonic)
    has_ttl_valid_cache = not cache_rejection_reason(
        value_age_ms, value_clock_status, _TEMP_CACHE_TTL_SEC * 1000.0,
    )
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
        snapshot_age_ms = (now_monotonic - completed_monotonic) * 1000.0
    elif isinstance(completed_at, (float, int)) and completed_at > 0:
        snapshot_age_ms = (now - float(completed_at)) * 1000.0

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
            payload["diagnostics_age_ms"] = None
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
            "spot_temperature_effective_c": _effective_spot_temperature_for_decision(
                decision,
                cached_temperature,
            ),
            "spot_last_valid_value_at": _epoch_to_utc_iso(last_valid_value_at),
            "spot_last_valid_value_monotonic": last_valid_value_monotonic,
            "spot_clock_domain_id": clock_domain_id(),
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
) -> bool:
    global _spot_diagnostics_task
    global _spot_diagnostics_last_started_at, _spot_diagnostics_last_started_monotonic
    global _spot_diagnostics_sweep_started_count, _spot_diagnostics_suppressed_poll_count
    global _spot_diagnostics_inflight_suppressed_count
    global _spot_diagnostics_storage_suppressed_poll_count

    if _spot_diagnostics_task is not None and not _spot_diagnostics_task.done():
        _spot_diagnostics_inflight_suppressed_count += 1
        return False

    if _spot_auxiliary_dispatch_storage_blocked():
        _spot_diagnostics_storage_suppressed_poll_count += 1
        return False

    now_monotonic = time.monotonic()
    if (
        _spot_diagnostics_last_started_monotonic is not None
        and now_monotonic - _spot_diagnostics_last_started_monotonic
        < _spot_diagnostics_refresh_interval_sec()
    ):
        _spot_diagnostics_suppressed_poll_count += 1
        return False

    _spot_diagnostics_last_started_at = time.time()
    _spot_diagnostics_last_started_monotonic = now_monotonic
    _spot_diagnostics_sweep_started_count += 1
    _spot_diagnostics_task = asyncio.create_task(
        _refresh_spot_diagnostics_safely(
            client,
            _logger,
            poll_context,
            collection_mode=_SPOT_DIAGNOSTICS_COLLECTION_MODE,
        )
    )
    return True


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
        snapshot_for_fact = _publish_spot_temperature_snapshot(
            poll_seq=poll_seq,
            poll_started_at=poll_started_at,
            poll_started_monotonic=poll_context.started_monotonic,
            poll_clock_domain=poll_context.clock_domain,
            poll_completed_at=poll_completed_at,
            poll_completed_monotonic=poll_completed_monotonic,
            temp_url=exc.temp_url,
            classification=classification,
        )
        await _write_spot_observation_fact_async(snapshot_for_fact)
        raise

    try:
        _temperature, classification = await _request_spot_temperature_observation(client, temp_url)
    except SpotTemperatureFetchError as exc:
        poll_completed_at, poll_completed_monotonic = _completed_poll_clocks()
        snapshot_for_fact = _publish_spot_temperature_snapshot(
            poll_seq=poll_seq,
            poll_started_at=poll_started_at,
            poll_started_monotonic=poll_context.started_monotonic,
            poll_clock_domain=poll_context.clock_domain,
            poll_completed_at=poll_completed_at,
            poll_completed_monotonic=poll_completed_monotonic,
            temp_url=exc.temp_url,
            classification=_classification_for_temperature_error(exc),
        )
        await _write_spot_observation_fact_async(snapshot_for_fact)
        raise

    poll_completed_at, poll_completed_monotonic = _completed_poll_clocks()
    _record_temperature_success(temp_url)
    snapshot_for_fact = _publish_spot_temperature_snapshot(
        poll_seq=poll_seq,
        poll_started_at=poll_started_at,
        poll_started_monotonic=poll_context.started_monotonic,
        poll_clock_domain=poll_context.clock_domain,
        poll_completed_at=poll_completed_at,
        poll_completed_monotonic=poll_completed_monotonic,
        temp_url=temp_url,
        classification=classification,
    )
    await _write_spot_observation_fact_async(snapshot_for_fact)


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


def get_spot_diagnostics() -> Dict[str, Any]:
    now = time.time()
    cache_entry = _img_cache_entry
    cache_age_ms = _spot_image_cache_age_ms(cache_entry) if cache_entry is not None else None
    refresh_task = _img_refresh_task
    try:
        configured_image_url: Optional[str] = _resolve_spot_image_url()
    except SpotImageConfigError:
        configured_image_url = None
    payload: Dict[str, Any] = {
        "image_status": "error" if _img_last_error_code else ("ok" if _img_last_success_at else "idle"),
        "image_source": _img_last_source,
        "failure_count": int(_img_failure_count),
        "last_error_at": float(_img_last_error) if _img_last_error else None,
        "last_error_code": _img_last_error_code,
        "last_error_message": _img_last_error_message,
        "last_success_at": float(_img_last_success_at) if _img_last_success_at else None,
        "image_request_policy_version": _SPOT_IMAGE_POLICY_VERSION,
        "image_refresh_interval_sec_effective": _spot_image_refresh_interval_sec(),
        "snapshot_image_refresh_interval_sec_effective": _spot_image_refresh_interval_sec(),
        "live_image_refresh_interval_sec_effective": _spot_live_image_refresh_interval_sec(),
        "live_image_max_fps_effective": _spot_live_image_max_per_sec(),
        "image_cache_present": cache_entry is not None,
        "image_cache_fresh": (
            _is_spot_image_cache_fresh(
                cache_entry,
                expected_image_url=configured_image_url,
            )
            if configured_image_url is not None
            else False
        ),
        "live_image_cache_fresh": (
            _is_spot_image_cache_fresh(
                cache_entry,
                profile=_SPOT_IMAGE_PROFILE_OPERATOR_LIVE,
                expected_image_url=configured_image_url,
            )
            if configured_image_url is not None
            else False
        ),
        "image_cache_age_ms": cache_age_ms,
        "image_refresh_in_flight": bool(refresh_task is not None and not refresh_task.done()),
        "image_accepting_requests": bool(_img_accepting_requests),
        "image_downstream_request_count": int(_img_downstream_request_count),
        "image_snapshot_downstream_request_count": int(
            _img_snapshot_downstream_request_count
        ),
        "image_live_downstream_request_count": int(_img_live_downstream_request_count),
        "image_upstream_request_count": int(_img_upstream_request_count),
        "image_http_dispatch_count": int(_img_http_dispatch_count),
        "image_storage_suppressed_task_count": int(_img_storage_suppressed_task_count),
        "image_cache_hit_count": int(_img_cache_hit_count),
        "image_singleflight_leader_count": int(_img_singleflight_leader_count),
        "image_coalesced_waiter_count": int(_img_coalesced_waiter_count),
        "image_refresh_success_count": int(_img_refresh_success_count),
        "image_refresh_failure_count": int(_img_refresh_failure_count),
        "image_cache_clock_anomaly_count": int(_img_cache_clock_anomaly_count),
        "image_last_upstream_started_at": (
            float(_img_last_upstream_started_at) if _img_last_upstream_started_at else None
        ),
        "image_last_upstream_completed_at": (
            float(_img_last_upstream_completed_at) if _img_last_upstream_completed_at else None
        ),
        "image_url_configured": bool(str(config.SPOT_IP or "").strip()),
        "image_path": "/image.jpg",
        "diagnostics_refresh_interval_sec_effective": _spot_diagnostics_refresh_interval_sec(),
        "diagnostics_refresh_in_flight": bool(
            _spot_diagnostics_task is not None and not _spot_diagnostics_task.done()
        ),
        "diagnostics_sweep_started_count": int(_spot_diagnostics_sweep_started_count),
        "diagnostics_upstream_request_count": int(_spot_diagnostics_upstream_request_count),
        "diagnostics_http_dispatch_count": int(_spot_diagnostics_upstream_request_count),
        "diagnostic_dispatch_attempt_count": int(_spot_diagnostics_upstream_request_count),
        "image_dispatch_attempt_count": int(_img_http_dispatch_count),
        # Current-process requests stopped at the dispatch gate, not polls,
        # coalesced waiters or downstream responses served without a task.
        "pre_dispatch_suppressed_count": int(
            _img_storage_suppressed_task_count + _spot_diagnostics_storage_suppressed_request_count
        ),
        "diagnostics_storage_suppressed_request_count": int(
            _spot_diagnostics_storage_suppressed_request_count
        ),
        "diagnostics_storage_suppressed_poll_count": int(
            _spot_diagnostics_storage_suppressed_poll_count
        ),
        "diagnostics_suppressed_poll_count": int(_spot_diagnostics_suppressed_poll_count),
        "diagnostics_inflight_suppressed_count": int(
            _spot_diagnostics_inflight_suppressed_count
        ),
        "diagnostics_last_started_at": (
            float(_spot_diagnostics_last_started_at)
            if _spot_diagnostics_last_started_at
            else None
        ),
        "diagnostics_last_completed_at": (
            float(_spot_diagnostics_last_completed_at)
            if _spot_diagnostics_last_completed_at
            else None
        ),
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
    payload.update(_spot_background_request_budget())
    payload.update(_spot_source_port_diagnostics())
    payload.update(_build_spot_temperature_snapshot_diagnostics(now))
    payload.update(_build_internal_temperature_diagnostics(now, include_cached_at=False))
    payload["diagnostic_request_journal"] = _spot_diagnostic_request_journal_snapshot()
    return payload


def get_spot_observation_fact_manifest_summary(
    *,
    fact_path: Path | None = None,
    realtime_rows: Iterable[Mapping[str, Any]] | None = None,
    allow_offline_rebuild: bool = True,
) -> Dict[str, Any]:
    if _spot_observation_queue is not None:
        if fact_path is not None and not _observation_fact_path_matches(_spot_observation_queue_path, fact_path):
            raise RuntimeError("observation queue path does not match manifest path")
        return _spot_observation_queue.manifest_summary(realtime_rows=realtime_rows)
    writer = _get_spot_observation_fact_writer()
    if fact_path is not None and not _observation_fact_path_matches(writer.output_path, fact_path):
        if not allow_offline_rebuild:
            raise RuntimeError(
                "SPOT observation fact runtime manifest path does not match closeout path"
            )
        writer = SpotObservationFactWriter(fact_path)
    return writer.manifest_summary(
        realtime_rows=realtime_rows,
    )


def ensure_spot_observation_fact_initialized(
    *,
    fact_path: Path,
    allow_offline_rebuild: bool = True,
) -> bool:
    if _spot_observation_queue is None and _spot_observation_fact_writer is None and not allow_offline_rebuild:
        _get_spot_observation_queue()
    if _spot_observation_queue is not None:
        if not _observation_fact_path_matches(_spot_observation_queue_path, fact_path):
            raise RuntimeError("observation queue belongs to a different initialization path")
        state = _spot_observation_queue.snapshot()["initialization_state"]
        if state == "pending":
            raise FactPersistencePending("observation writer is initializing")
        return state == "ready"
    writer = _get_spot_observation_fact_writer()
    if not _observation_fact_path_matches(writer.output_path, fact_path):
        if not allow_offline_rebuild:
            raise RuntimeError(
                "SPOT observation fact runtime manifest path does not match initialization path"
            )
        writer = SpotObservationFactWriter(fact_path)
    return writer.ensure_initialized()


def get_spot_internal_temperature_diagnostics() -> Dict[str, Any]:
    return _build_internal_temperature_diagnostics(time.time(), include_cached_at=True)


def get_image_state_summary() -> Dict[str, Any]:
    cache_entry = _img_cache_entry
    return {
        "image_bytes": len(cache_entry.image_bytes) if cache_entry is not None else 0,
        "image_failure_count": int(_img_failure_count),
        "image_last_success_at": float(_img_last_success_at) if _img_last_success_at else None,
        "image_cache_age_ms": (
            _spot_image_cache_age_ms(cache_entry) if cache_entry is not None else None
        ),
        "image_cache_fresh": _is_spot_image_cache_fresh(cache_entry),
        "image_refresh_in_flight": bool(_img_refresh_task is not None and not _img_refresh_task.done()),
        "image_upstream_request_count": int(_img_upstream_request_count),
        "image_http_dispatch_count": int(_img_http_dispatch_count),
        "image_storage_suppressed_task_count": int(_img_storage_suppressed_task_count),
        "image_downstream_request_count": int(_img_downstream_request_count),
        "image_url_present": bool(str(config.SPOT_IP or "").strip()),
        "total_bytes": len(cache_entry.image_bytes) if cache_entry is not None else 0,
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


def _start_spot_http_transport() -> bool:
    global _spot_http_transport
    global _spot_http_transport_enforcement_required
    global _spot_http_transport_shutdown_started

    if _spot_http_transport is None:
        _spot_http_transport = SpotHttpTransport()
    started = _spot_http_transport.start()
    _spot_http_transport_enforcement_required = bool(
        _spot_http_transport.supported
    )
    _spot_http_transport_shutdown_started = False
    return started


async def _stop_spot_http_transport(
    timeout_sec: float = _SPOT_HTTP_TRANSPORT_SHUTDOWN_TIMEOUT_SEC,
) -> bool:
    global _http_client
    global _spot_http_transport
    global _spot_http_transport_shutdown_started

    _spot_http_transport_shutdown_started = True
    transport = _spot_http_transport
    drained = True
    transport_error: BaseException | None = None
    if transport is not None:
        try:
            drained = await transport.close(timeout_sec=timeout_sec)
        except BaseException as exc:
            transport_error = exc
        else:
            if drained:
                _spot_http_transport = None

    client = _http_client
    client_error: BaseException | None = None
    if client is not None:
        try:
            await client.aclose()
        except BaseException as exc:
            client_error = exc
        finally:
            _http_client = None
    if transport_error is not None:
        raise transport_error
    if client_error is not None:
        raise client_error
    return drained


async def _reset_spot_http_transport_state_for_tests(
    timeout_sec: float = 2.0,
) -> None:
    global _spot_http_transport
    global _spot_http_transport_enforcement_required
    global _spot_http_transport_shutdown_started

    if not await _stop_spot_http_transport(timeout_sec=timeout_sec):
        raise RuntimeError("SPOT HTTP transport test reset timed out")
    _spot_http_transport = None
    _spot_http_transport_enforcement_required = False
    _spot_http_transport_shutdown_started = False


def _spot_source_port_diagnostics() -> Dict[str, Any]:
    transport = _spot_http_transport
    if transport is not None:
        return dict(transport.diagnostics())
    return dict(empty_spot_http_transport_diagnostics())


def _active_spot_http_transport() -> SpotHttpTransport | None:
    transport = _spot_http_transport
    if _spot_http_transport_shutdown_started:
        raise SpotTransportClosedError("SPOT transport shutdown has started")
    if transport is None:
        if _spot_http_transport_enforcement_required:
            raise SpotTransportClosedError(
                "SPOT source-port enforcement transport is unavailable"
            )
        return None
    if not transport.supported:
        if _spot_http_transport_enforcement_required:
            raise SpotTransportClosedError(
                "SPOT source-port enforcement is unavailable"
            )
        return None
    if not transport.active:
        raise SpotTransportClosedError("SPOT source-port enforcement is inactive")
    return transport


def _transport_response_as_httpx(
    response: SpotHttpResponse,
    *,
    method: str,
    url: str,
) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(
        response.status_code,
        headers=dict(response.headers),
        content=response.body,
        request=request,
    )


async def _request_spot_http_response(
    client: httpx.AsyncClient,
    *,
    kind: SpotRequestKind,
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    body: bytes | None = None,
    connect_timeout_sec: float = 1.0,
    read_timeout_sec: float = 5.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    read_response_body: bool = True,
    correlation_id: str | None = None,
) -> httpx.Response:
    request = httpx.Request(method, url)
    try:
        transport = _active_spot_http_transport()
    except (SpotTransportError, SpotPortPoolError) as exc:
        raise httpx.RequestError(str(exc), request=request) from exc
    if transport is None:
        timeout = httpx.Timeout(
            connect=connect_timeout_sec,
            read=read_timeout_sec,
            write=1.0,
            pool=5.0,
        )
        if read_response_body:
            response = await client.request(
                method,
                url,
                headers=headers,
                content=body,
                timeout=timeout,
            )
            if len(response.content) > max_response_bytes:
                raise httpx.RequestError(
                    "SPOT response exceeds the configured byte limit",
                    request=request,
                )
            return response
        async with client.stream(
            method,
            url,
            headers=headers,
            content=body,
            timeout=timeout,
        ) as response:
            return httpx.Response(
                response.status_code,
                headers=dict(response.headers),
                content=b"",
                request=request,
            )

    try:
        guarded_response = await transport.request(
            SpotHttpRequest(
                kind=kind,
                method=method,
                url=url,
                headers=headers or {},
                body=body,
                connect_timeout_sec=connect_timeout_sec,
                read_timeout_sec=read_timeout_sec,
                max_response_bytes=max_response_bytes,
                read_response_body=read_response_body,
                correlation_id=correlation_id,
            )
        )
    except SpotTransportConnectTimeout as exc:
        raise httpx.ConnectTimeout(str(exc), request=request) from exc
    except SpotTransportReadTimeout as exc:
        raise httpx.ReadTimeout(str(exc), request=request) from exc
    except SpotTransportTimeout as exc:
        raise httpx.TimeoutException(str(exc), request=request) from exc
    except (SpotTransportError, SpotPortPoolError) as exc:
        raise httpx.RequestError(str(exc), request=request) from exc
    return _transport_response_as_httpx(
        guarded_response,
        method=method,
        url=url,
    )


async def test_spot_http_connection(
    url: str | None,
    timeout_sec: float = 1.5,
) -> dict[str, object]:
    if not url:
        return {"ok": False, "latency_ms": None, "message": "URL missing"}
    started_at = time.perf_counter()
    try:
        async with _spot_device_request_lock:
            client = _get_http_client()
            response = await _request_spot_connection_probe(
                client,
                url=url,
                method="HEAD",
                timeout_sec=timeout_sec,
            )
            if response.status_code in {405, 501}:
                response = await _request_spot_connection_probe(
                    client,
                    url=url,
                    method="GET",
                    timeout_sec=timeout_sec,
                )
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        if not 200 <= response.status_code < 300:
            return {
                "ok": False,
                "latency_ms": latency_ms,
                "message": f"HTTP {response.status_code}",
            }
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "message": f"HTTP {response.status_code}",
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "message": _format_exception_message(exc),
        }


async def _request_spot_connection_probe(
    client: httpx.AsyncClient,
    *,
    url: str,
    method: str,
    timeout_sec: float,
) -> httpx.Response:
    current_url = url
    for hop in range(MAX_REDIRECT_HOPS + 1):
        response = await _request_spot_http_response(
            client,
            kind=SpotRequestKind.CONNECTION_TEST,
            method=method,
            url=current_url,
            connect_timeout_sec=timeout_sec,
            read_timeout_sec=timeout_sec,
            read_response_body=False,
        )
        location = response.headers.get("location")
        if response.status_code not in {301, 302, 303, 307, 308} or not location:
            return response
        if hop >= MAX_REDIRECT_HOPS:
            raise httpx.RequestError(
                "SPOT HTTP redirect limit was exceeded",
                request=httpx.Request(method, current_url),
            )
        try:
            current_url = resolve_spot_redirect_url(current_url, location)
        except SpotTransportError as exc:
            raise httpx.RequestError(
                str(exc),
                request=httpx.Request(method, current_url),
            ) from exc
    raise httpx.RequestError(
        "SPOT HTTP redirect limit was exceeded",
        request=httpx.Request(method, current_url),
    )


def _request_spot_http_response_sync(
    *,
    kind: SpotRequestKind,
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    body: bytes | None = None,
    timeout_sec: float = 3.0,
) -> SpotHttpResponse | None:
    transport = _active_spot_http_transport()
    if transport is None:
        return None
    return transport.request_sync(
        SpotHttpRequest(
            kind=kind,
            method=method,
            url=url,
            headers=headers or {},
            body=body,
            connect_timeout_sec=timeout_sec,
            read_timeout_sec=timeout_sec,
            max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
        )
    )


def _consume_spot_image_refresh_result(task: asyncio.Task[_SpotImageCacheEntry]) -> None:
    if task.cancelled():
        return
    try:
        task.exception()
    except asyncio.CancelledError:
        return


async def _refresh_spot_image_cache(image_url: str) -> _SpotImageCacheEntry:
    global _img_cache_entry, _img_failure_count
    global _img_upstream_request_count, _img_refresh_success_count, _img_refresh_failure_count
    global _img_last_upstream_started_at, _img_last_upstream_completed_at

    client = _get_http_client()
    started_at_epoch = time.time()
    started_at_monotonic = time.monotonic()
    _img_upstream_request_count += 1
    _img_last_upstream_started_at = started_at_epoch
    try:
        data = await _request_spot_image(client, image_url)
    except SpotImageFetchError as exc:
        _record_image_error(exc.code, str(exc))
        _img_failure_count = min(_img_failure_count + 1, 10)
        _img_refresh_failure_count += 1
        _img_last_upstream_completed_at = time.time()
        raise

    captured_at_epoch = time.time()
    captured_at_monotonic = time.monotonic()
    entry = _SpotImageCacheEntry(
        image_bytes=bytes(data),
        captured_at_epoch=captured_at_epoch,
        captured_at_monotonic=captured_at_monotonic,
        upstream_latency_ms=max(0.0, (captured_at_monotonic - started_at_monotonic) * 1000.0),
        image_url=image_url,
        # One identity per successful upstream acquisition, including equal
        # bytes and equal wall-clock timestamps. Cache readers reuse this ID.
        capture_id=(f"spotimg_{datetime.fromtimestamp(captured_at_epoch, timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_"
                    f"{uuid4().hex}"),
    )
    _img_cache_entry = entry
    _img_refresh_success_count += 1
    _img_last_upstream_completed_at = captured_at_epoch
    _record_image_success()
    admission = _maybe_enqueue_spot_image_capture(
        image_bytes=entry.image_bytes,
        captured_at=entry.captured_at_epoch,
        image_url=image_url,
        source="official_image_jpg",
        image_age_ms=0.0,
        capture_id=entry.capture_id,
    )
    if not admission.accepted and admission.status != "DISABLED":
        _logger.warning(
            "SPOT image capture admission rejected %s",
            json.dumps({
                "status": admission.status,
                "reason": admission.reason,
                "capture_id": admission.capture_id,
            }, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
        )
    return entry


async def fetch_image_async(
    profile: str = _SPOT_IMAGE_PROFILE_SNAPSHOT,
) -> tuple[bytes, Dict[str, Any]]:
    """Return a fresh process-local JPEG, coalescing concurrent upstream refreshes."""
    global _img_downstream_request_count, _img_cache_hit_count
    global _img_snapshot_downstream_request_count, _img_live_downstream_request_count
    global _img_singleflight_leader_count, _img_coalesced_waiter_count
    global _img_refresh_task, _img_failure_count

    normalized_profile = _normalize_spot_image_profile(profile)
    _img_downstream_request_count += 1
    if normalized_profile == _SPOT_IMAGE_PROFILE_OPERATOR_LIVE:
        _img_live_downstream_request_count += 1
    else:
        _img_snapshot_downstream_request_count += 1
    if not _img_accepting_requests:
        raise SpotImageFetchError(
            "shutdown",
            "SPOT image service is stopping",
            image_url="",
            upstream_status=None,
        )

    while True:
        try:
            image_url = _resolve_spot_image_url()
        except SpotImageConfigError as exc:
            _record_image_error("config-missing", str(exc))
            _img_failure_count = min(_img_failure_count + 1, 10)
            raise

        if _spot_auxiliary_dispatch_storage_blocked():
            return _spot_image_pressure_response(normalized_profile)
        cache_entry = _img_cache_entry
        if _is_spot_image_cache_fresh(
            cache_entry,
            profile=normalized_profile,
            record_clock_anomaly=True,
            expected_image_url=image_url,
        ):
            assert cache_entry is not None
            _img_cache_hit_count += 1
            return _spot_image_response(
                cache_entry,
                profile=normalized_profile,
                source="cache",
            )

        is_leader = False
        async with _img_fetch_lock:
            if not _img_accepting_requests:
                raise SpotImageFetchError(
                    "shutdown",
                    "SPOT image service is stopping",
                    image_url=image_url,
                    upstream_status=None,
                )
            if _spot_auxiliary_dispatch_storage_blocked():
                return _spot_image_pressure_response(normalized_profile)
            cache_entry = _img_cache_entry
            if _is_spot_image_cache_fresh(
                cache_entry,
                profile=normalized_profile,
                expected_image_url=image_url,
            ):
                assert cache_entry is not None
                _img_cache_hit_count += 1
                return _spot_image_response(
                    cache_entry,
                    profile=normalized_profile,
                    source="cache",
                )

            refresh_task = _img_refresh_task
            if refresh_task is None or refresh_task.done():
                refresh_task = asyncio.create_task(_refresh_spot_image_cache(image_url))
                refresh_task.add_done_callback(_consume_spot_image_refresh_result)
                _img_refresh_task = refresh_task
                _img_singleflight_leader_count += 1
                is_leader = True
            else:
                _img_coalesced_waiter_count += 1

        try:
            refreshed_entry = await asyncio.shield(refresh_task)
        except (SpotImageFetchError, SpotStoragePressureError) as exc:
            try:
                current_image_url = _resolve_spot_image_url()
            except SpotImageConfigError:
                continue
            if current_image_url != image_url:
                continue
            if isinstance(exc, SpotStoragePressureError):
                return _spot_image_pressure_response(normalized_profile)
            raise
        finally:
            async with _img_fetch_lock:
                if _img_refresh_task is refresh_task and refresh_task.done():
                    _img_refresh_task = None

        try:
            current_image_url = _resolve_spot_image_url()
        except SpotImageConfigError:
            continue
        if refreshed_entry.image_url != current_image_url:
            continue

        return _spot_image_response(
            refreshed_entry,
            profile=normalized_profile,
            source="upstream" if is_leader else "coalesced",
        )


async def _stop_spot_image_refresh_for_shutdown(
    timeout_sec: float = _SPOT_IMAGE_REFRESH_SHUTDOWN_TIMEOUT_SEC,
) -> bool:
    global _img_accepting_requests, _img_refresh_task

    _img_accepting_requests = False
    refresh_task = _img_refresh_task
    if refresh_task is None:
        return True
    if not refresh_task.done():
        try:
            await asyncio.wait_for(asyncio.shield(refresh_task), timeout=max(0.0, timeout_sec))
        except asyncio.TimeoutError:
            _logger.warning(
                "SPOT image refresh exceeded the shutdown timeout and will be cancelled",
                extra={"code": "spot-image-refresh-shutdown-timeout"},
            )
            refresh_task.cancel()
            await asyncio.gather(refresh_task, return_exceptions=True)
        except SpotImageFetchError:
            pass
        except asyncio.CancelledError:
            refresh_task.cancel()
            await asyncio.gather(refresh_task, return_exceptions=True)
            raise
    _img_refresh_task = None
    return refresh_task.done()

# --- Temperature and diagnostics polling ---
_spot_poll_task: Optional[asyncio.Task] = None
_internal_temperature_task: Optional[asyncio.Task] = None
_spot_poll_running = False
_spot_shutdown_state_lock = threading.Lock()
_spot_shutdown_task_states: dict[str, str] = {
    "diagnostics": "not_started",
    "poll": "not_started",
    "internal_temperature": "not_started",
}
_spot_shutdown_image_refresh_stopped = False
_spot_shutdown_transport_stopped = False
_spot_shutdown_started_monotonic: float | None = None


async def _spot_poll_loop():
    """獄쏄퉫???깆뒲??뽯퓠??筌왖??우읅??곗쨮 SPOT ???筌왖 ?袁ⓥ봺??뤿Ф (??뺚봺?袁る뱜 獄쎻뫗? 嚥≪뮇彛??怨몄뒠)."""
    global _internal_temperature_task, _spot_poll_running
    global _spot_diagnostics_task
    _spot_poll_running = True

    interval = _spot_poll_interval_sec()
    next_tick = time.monotonic()

    while _spot_poll_running:
        try:
            _activate_spot_image_storage()
            client = _get_http_client()
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
                _internal_temperature_task is None or _internal_temperature_task.done()
            ):
                _internal_temperature_task = asyncio.create_task(
                    _refresh_spot_internal_temperature_safely(client, _logger)
                )

        except asyncio.CancelledError:
            break
        # ??뺚봺?袁る뱜 獄쎻뫗?: ??쇱벉 ??쎈뻬 ??볦퍢 ?④쑴沅?
        next_tick += interval
        now_monotonic = time.monotonic()
        if next_tick <= now_monotonic:
            # Skip missed ticks. After an overrun, wait a full configured interval
            # rather than issuing catch-up requests; I/O concurrency is unchanged.
            next_tick = now_monotonic + interval
        try:
            await asyncio.sleep(next_tick - now_monotonic)
        except asyncio.CancelledError:
            break
    _spot_poll_running = False


async def start_spot_poll_loop():
    """獄쏄퉫???깆뒲???袁ⓥ봺??뤿Ф ??뽰삂."""
    global _img_accepting_requests, _spot_poll_task, _spot_poll_running
    global _spot_shutdown_image_refresh_stopped, _spot_shutdown_started_monotonic
    global _spot_shutdown_transport_stopped
    global _spot_diagnostic_journal_shutdown_started
    global _spot_diagnostic_journal_closed_snapshot
    global _spot_observation_queue
    if _spot_poll_task and not _spot_poll_task.done():
        return  # ??? ??쎈뻬 餓?

    if bool(getattr(config, "SPOT_OBSERVATION_FACT_ENABLED", False)):
        if _spot_observation_queue is not None and not _spot_observation_queue.snapshot()["accepting"]:
            if _spot_observation_queue.snapshot()["writer_alive"] or not spot_observation_fact_writes_drained():
                raise RuntimeError("SPOT observation persistence shutdown is incomplete")
            _spot_observation_queue = None
        _get_spot_observation_queue()

    with _spot_diagnostic_journal_lock:
        if (
            _spot_diagnostic_journal_shutdown_started
            and _spot_diagnostic_journal is not None
        ):
            raise RuntimeError("SPOT diagnostic request journal shutdown is incomplete")
        _spot_diagnostic_journal_shutdown_started = False
        _spot_diagnostic_journal_closed_snapshot = None

    with _spot_shutdown_state_lock:
        _spot_shutdown_task_states.update(
            diagnostics="running",
            poll="running",
            internal_temperature="running",
        )
        _spot_shutdown_image_refresh_stopped = False
        _spot_shutdown_transport_stopped = False
        _spot_shutdown_started_monotonic = None
    await asyncio.to_thread(_get_spot_diagnostic_request_journal)
    _activate_spot_image_storage()
    _start_spot_http_transport()
    _img_accepting_requests = True
    _spot_poll_running = True
    _spot_poll_task = asyncio.create_task(_spot_poll_loop())


async def stop_spot_poll_loop() -> bool:
    """獄쏄퉫???깆뒲???袁ⓥ봺??뤿Ф 餓λ쵐?."""
    global _internal_temperature_task, _spot_poll_task, _spot_poll_running, _spot_diagnostics_task
    global _spot_shutdown_image_refresh_stopped, _spot_shutdown_started_monotonic
    global _spot_shutdown_transport_stopped
    _spot_poll_running = False
    shutdown_started_monotonic = time.monotonic()
    with _spot_shutdown_state_lock:
        _spot_shutdown_started_monotonic = shutdown_started_monotonic

    task_entries = (
        ("diagnostics", _spot_diagnostics_task),
        ("poll", _spot_poll_task),
        ("internal_temperature", _internal_temperature_task),
    )
    for _, task in task_entries:
        if task is not None and not task.done():
            task.cancel()

    active_tasks = {
        task: task_name
        for task_name, task in task_entries
        if task is not None
    }
    task_shutdown_succeeded = True
    done: set[asyncio.Task[None]] = set()
    pending: set[asyncio.Task[None]] = set()
    if active_tasks:
        done, pending = await asyncio.wait(
            active_tasks,
            timeout=_SPOT_BACKGROUND_SHUTDOWN_TIMEOUT_SEC,
        )
    for task_name, task in task_entries:
        if task is None:
            _record_spot_background_shutdown_state(
                task_name,
                "not_started",
                shutdown_started_monotonic,
            )
    for task in done:
        task_name = active_tasks[task]
        task_state, result = _spot_background_task_result(task, late=False)
        _record_spot_background_shutdown_state(
            task_name,
            task_state,
            shutdown_started_monotonic,
        )
        if result is not None:
            task_shutdown_succeeded = False
            _logger.warning(
                "SPOT background task shutdown failed task=%s state=%s "
                "error_type=%s timeout_sec=%.1f",
                task_name,
                task_state,
                type(result).__name__,
                _SPOT_BACKGROUND_SHUTDOWN_TIMEOUT_SEC,
                extra={
                    "code": "spot-background-task-shutdown-failed",
                    "task": task_name,
                    "error_type": type(result).__name__,
                },
            )
    for task in pending:
        task_shutdown_succeeded = False
        task_name = active_tasks[task]
        _record_spot_background_shutdown_state(
            task_name,
            "timeout_pending",
            shutdown_started_monotonic,
        )
        task.add_done_callback(
            partial(_record_late_spot_background_shutdown_result, task_name)
        )
        _logger.warning(
            "SPOT background task shutdown task=%s state=timeout_pending "
            "timeout_sec=%.1f elapsed_ms=%.1f",
            task_name,
            _SPOT_BACKGROUND_SHUTDOWN_TIMEOUT_SEC,
            (time.monotonic() - shutdown_started_monotonic) * 1000.0,
            extra={
                "code": "spot-background-task-shutdown-timeout",
                "task": task_name,
                "timeout_sec": _SPOT_BACKGROUND_SHUTDOWN_TIMEOUT_SEC,
            },
        )

    if _spot_diagnostics_task is None or _spot_diagnostics_task.done():
        _spot_diagnostics_task = None
    if _spot_poll_task is None or _spot_poll_task.done():
        _spot_poll_task = None
    if _internal_temperature_task is None or _internal_temperature_task.done():
        _internal_temperature_task = None

    try:
        image_refresh_stopped = await _stop_spot_image_refresh_for_shutdown()
    except Exception as exc:
        image_refresh_stopped = False
        _logger.warning(
            "SPOT image refresh shutdown failed",
            extra={
                "code": "spot-image-refresh-shutdown-failed",
                "error_type": type(exc).__name__,
            },
        )
    try:
        transport_stopped = await _stop_spot_http_transport()
    except Exception as exc:
        transport_stopped = False
        _logger.warning(
            "SPOT HTTP transport shutdown failed",
            extra={
                "code": "spot-http-transport-shutdown-failed",
                "error_type": type(exc).__name__,
            },
        )
    if not transport_stopped:
        _logger.warning(
            "SPOT HTTP transport did not drain before shutdown timeout",
            extra={"code": "spot-http-transport-shutdown-timeout"},
        )
    with _spot_shutdown_state_lock:
        _spot_shutdown_image_refresh_stopped = image_refresh_stopped
        _spot_shutdown_transport_stopped = transport_stopped
    observation_fact_drained = await wait_for_spot_observation_fact_writes_drain()
    if not observation_fact_drained:
        _logger.warning(
            "SPOT observation fact writes did not drain before shutdown timeout",
            extra={
                "code": "spot-observation-fact-shutdown-timeout",
                "pending_write_count": sum(
                    not task.done()
                    for task in _spot_observation_fact_write_tasks
                ),
            },
        )
    return (
        task_shutdown_succeeded
        and observation_fact_drained
        and image_refresh_stopped
        and transport_stopped
    )


def _spot_background_task_result(
    task: asyncio.Task[None],
    *,
    late: bool,
) -> tuple[str, BaseException | None]:
    suffix = "_late" if late else ""
    if task.cancelled():
        return f"cancelled{suffix}", None
    try:
        error = task.exception()
    except BaseException as exc:
        return f"failed{suffix}", exc
    if error is not None:
        return f"failed{suffix}", error
    return f"completed{suffix}", None


def _record_spot_background_shutdown_state(
    task_name: str,
    state: str,
    shutdown_started_monotonic: float,
) -> None:
    with _spot_shutdown_state_lock:
        _spot_shutdown_task_states[task_name] = state
    _logger.info(
        "SPOT background task shutdown task=%s state=%s timeout_sec=%.1f elapsed_ms=%.1f",
        task_name,
        state,
        _SPOT_BACKGROUND_SHUTDOWN_TIMEOUT_SEC,
        (time.monotonic() - shutdown_started_monotonic) * 1000.0,
    )


def _record_late_spot_background_shutdown_result(
    task_name: str,
    task: asyncio.Task[None],
) -> None:
    state, error = _spot_background_task_result(task, late=True)
    with _spot_shutdown_state_lock:
        _spot_shutdown_task_states[task_name] = state
        started_monotonic = _spot_shutdown_started_monotonic
    elapsed_ms = (
        (time.monotonic() - started_monotonic) * 1000.0
        if started_monotonic is not None
        else 0.0
    )
    _logger.info(
        "SPOT background task shutdown task=%s state=%s timeout_sec=%.1f elapsed_ms=%.1f",
        task_name,
        state,
        _SPOT_BACKGROUND_SHUTDOWN_TIMEOUT_SEC,
        elapsed_ms,
    )
    if error is not None:
        _logger.warning(
            "SPOT background task late shutdown failed task=%s error_type=%s",
            task_name,
            type(error).__name__,
        )


def get_spot_poll_shutdown_status() -> Dict[str, Any]:
    with _spot_shutdown_state_lock:
        task_states = dict(_spot_shutdown_task_states)
        image_refresh_stopped = _spot_shutdown_image_refresh_stopped
        transport_stopped = _spot_shutdown_transport_stopped
    drained_states = {
        "not_started",
        "cancelled",
        "completed",
        "cancelled_late",
        "completed_late",
    }
    settled_states = drained_states | {"failed", "failed_late"}
    tasks_drained = all(state in drained_states for state in task_states.values())
    tasks_settled = all(state in settled_states for state in task_states.values())
    observation_fact_drained = spot_observation_fact_writes_drained()
    return {
        "tasks": task_states,
        "tasks_drained": tasks_drained,
        "tasks_settled": tasks_settled,
        "observation_fact_drained": observation_fact_drained,
        "image_refresh_stopped": image_refresh_stopped,
        "transport_stopped": transport_stopped,
        "complete": (
            tasks_drained
            and observation_fact_drained
            and image_refresh_stopped
            and transport_stopped
        ),
    }


def get_cached_spot_temp() -> float:
    """筌?Ŋ???SPOT ??ㅻ즲??獄쏆꼹??(PLC ??뺤뵬??苡??源녿퓠??????."""
    now = time.time()
    # ???筌왖揶쎛 ??댭???살삋??뤿?椰꾧퀡援?15??, ??ㅻ즲揶쎛 ??곸몵筌?0.0 獄쏆꼹??
    if not _temperature_cache["temp_time"] or (
        now - _temperature_cache["temp_time"] > _TEMP_CACHE_TTL_SEC
    ):
        return 0.0
    return _temperature_cache["temp"]


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
        guarded_response = _request_spot_http_response_sync(
            kind=SpotRequestKind.FOCUS_READ,
            method="GET",
            url=focus_url,
        )
        if guarded_response is None:
            with urlopen(focus_url, timeout=3) as resp:
                code = resp.getcode()
                content = resp.read()
        else:
            code = guarded_response.status_code
            content = guarded_response.body
    except HTTPError as exc:
        body = _preview_spot_focus_body(exc.read())
        raise SpotFocusControlError(
            f"SPOT focus read failed: HTTP {exc.code}; url={focus_url}; body={body[:200]}",
            focus_url=focus_url,
            upstream_status=exc.code,
        ) from exc
    except (TimeoutError, URLError, ValueError, SpotTransportError, SpotPortPoolError) as exc:
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
        guarded_response = _request_spot_http_response_sync(
            kind=SpotRequestKind.FOCUS_WRITE,
            method="PUT",
            url=focus_url,
            headers={"Content-Type": "application/json;charset=utf-8"},
            body=str(new_val).encode("ascii"),
        )
        if guarded_response is None:
            with urlopen(request, timeout=3) as resp:
                code = resp.getcode()
                content = resp.read()
        else:
            code = guarded_response.status_code
            content = guarded_response.body
    except HTTPError as exc:
        body = _preview_spot_focus_body(exc.read())
        raise SpotFocusControlError(
            "SPOT focus write failed: "
            f"HTTP {exc.code}; url={focus_url}; value={new_val}; body={body[:200]}",
            focus_url=focus_url,
            upstream_status=exc.code,
        ) from exc
    except (TimeoutError, URLError, ValueError, SpotTransportError, SpotPortPoolError) as exc:
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


_SerializedResult = TypeVar("_SerializedResult")


async def _run_spot_device_sync_operation(
    operation: Callable[[int], _SerializedResult],
    value: int,
) -> _SerializedResult:
    async with _spot_device_request_lock:
        operation_task = asyncio.create_task(asyncio.to_thread(operation, value))
        try:
            return await asyncio.shield(operation_task)
        except asyncio.CancelledError:
            try:
                await operation_task
            except Exception as exc:
                _logger.warning(
                    "SPOT control operation failed after caller cancellation",
                    extra={
                        "operation": getattr(operation, "__name__", operation.__class__.__name__),
                        "error": _format_exception_message(exc),
                    },
                )
            raise


async def move_focus_serialized(steps: int) -> Dict[str, Any]:
    return await _run_spot_device_sync_operation(move_focus, steps)


def _resolve_spot_actuator_url() -> str:
    actuator_url = str(config.SPOT_ACTUATOR_URL or "").strip()
    if not actuator_url:
        raise RuntimeError("SPOT_ACTUATOR_URL is not configured")
    return actuator_url


def _read_spot_actuator_position(actuator_url: str) -> int:
    read_url = f"{actuator_url}?scan=3"
    try:
        guarded_response = _request_spot_http_response_sync(
            kind=SpotRequestKind.ACTUATOR_READ,
            method="GET",
            url=read_url,
        )
        if guarded_response is None:
            with urlopen(read_url, timeout=3) as resp:
                code = resp.getcode()
                content = resp.read()
        else:
            code = guarded_response.status_code
            content = guarded_response.body
    except HTTPError as exc:
        body = _preview_spot_focus_body(exc.read())
        raise SpotActuatorControlError(
            f"SPOT actuator read failed: HTTP {exc.code}; url={read_url}; body={body[:200]}",
            actuator_url=actuator_url,
            upstream_status=exc.code,
        ) from exc
    except (TimeoutError, URLError, ValueError, SpotTransportError, SpotPortPoolError) as exc:
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
        guarded_response = _request_spot_http_response_sync(
            kind=SpotRequestKind.ACTUATOR_WRITE,
            method="GET",
            url=write_url,
        )
        if guarded_response is None:
            with urlopen(write_url, timeout=3) as resp:
                code = resp.getcode()
                content = resp.read()
        else:
            code = guarded_response.status_code
            content = guarded_response.body
    except HTTPError as exc:
        body = _preview_spot_focus_body(exc.read())
        raise SpotActuatorControlError(
            f"SPOT actuator write failed: HTTP {exc.code}; url={write_url}; body={body[:200]}",
            actuator_url=actuator_url,
            upstream_status=exc.code,
        ) from exc
    except (TimeoutError, URLError, ValueError, SpotTransportError, SpotPortPoolError) as exc:
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


async def move_actuator_serialized(steps: int) -> Dict[str, Any]:
    return await _run_spot_device_sync_operation(move_actuator, steps)
