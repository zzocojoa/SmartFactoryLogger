import asyncio
import sys
import os
from pathlib import Path
from typing import Optional

# Important: Add the directory containing the 'backend' folder to sys.path
# This ensures that 'from backend.Observability...' works in all environments.
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from contextlib import asynccontextmanager
import atexit
from datetime import datetime, timezone
import base64
import json
import logging
import math
import re
from logging.handlers import RotatingFileHandler
import time
from backend.MESSync import sync_router as mes_sync

import contextvars
import queue
from logging.handlers import QueueHandler, QueueListener
from pythonjsonlogger import jsonlogger
import uuid

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        if hasattr(record, "trace_id"):
            log_record["trace_id"] = record.trace_id

class TraceIDFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_var.get()
        return True

class SafeRotatingFileHandler(RotatingFileHandler):
    """
    RotatingFileHandler that catches PermissionError/OSError during rollover (common on Windows)
    and continues logging to the same file instead of crashing.
    """
    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError) as e:
            # If rotation fails (file locked), reopen the current file and continue
            # The file will grow larger than maxBytes, but we avoid a crash.
            # We can log a localized error to stderr or just ignore it.
            try:
                if self.stream is None:
                    self.stream = self._open()
            except Exception:
                pass
import socket
import subprocess
import tempfile
import threading
import traceback
import time
import uvicorn
from urllib.request import Request, urlopen
from typing import Any, NamedTuple, TypedDict

# Import Service Layer using absolute imports
from backend.FacilityData.service import plc_service
from backend.FacilityData.repository import logger_service
from backend.Observability.metrics_logger import comm_metrics_logger_service
from backend.Observability.memory_service import estimate_size_bytes, memory_service
from backend.Observability.service import observability_service
from backend.Configuration.Configuration_DB_Manager import config_manager
from backend.Configuration.Configuration_Logic_Layout import (
    delete_layout_slot,
    get_active_layout,
    get_layout_meta,
    list_layouts,
    restore_layout_backup,
    restore_layout_slot,
    save_layout_slot
)
from backend.Configuration.service import (
    apply_pending_config,
    clear_pending_config,
    get_config_snapshot,
    set_override_enabled,
    update_config,
    restore_defaults,
    restore_backup,
)
from backend.Configuration.Configuration_Logic_Sync import config_sync_agent
from backend.Configuration.Configuration_Logic_Watch import config_watch_service
from backend.Configuration.Configuration_Structure import ConfigUpdate, OverrideToggle, SettingsConfig
from backend.FacilityData.drivers import spot_api as spot_control
from backend.FacilityData.schemas import FactoryData
from backend.Observability.Observability_Logic_Verification import compare_with_reference
from backend import config
from backend.MESSync import MESSync_Logic_Scheduler as mes_scheduler
from backend.MESSync import repository as mes_db
from backend.MESSync.MESSync_Structure import MES_PAGES
from backend.MESSync import router as mes_router
from backend.core import ai_tools_dispatcher
from backend.version import get_runtime_info

class ConnectionTarget(BaseModel):
    ip: str | None = None
    port: int | None = None
    url: str | None = None


class ConnectionTestPayload(BaseModel):
    extruder: ConnectionTarget | None = None
    ls_plc: ConnectionTarget | None = None
    spot: ConnectionTarget | None = None


class PathCheckItem(BaseModel):
    key: str
    path: str


class PathHealthRequest(BaseModel):
    paths: list[PathCheckItem]


class PathCreateRequest(BaseModel):
    path: str


class FolderBrowseRequest(BaseModel):
    initial_dir: str | None = None
    title: str | None = None


class VerificationCompareRequest(BaseModel):
    reference_csv_path: str
    sample_count: int = 50
    interval_sec: float | None = None


class ShutdownRequest(BaseModel):
    reason: str | None = None


class FrontendErrorPayload(BaseModel):
    time: float
    type: str
    message: str
    detail: str | None = None
    stack: str | None = None


class ObservabilityExportRequest(BaseModel):
    include_errors: bool = True
    front_errors: list[FrontendErrorPayload] | None = None
    tolerance_abs: dict[str, float] | None = None
    tolerance_pct: dict[str, float] | None = None


class MemoryExportRequest(BaseModel):
    frontend: dict[str, Any] | None = None


class SnapshotRequest(BaseModel):
    image_base64: str
    name: str | None = None
    format: str | None = None


class LayoutSaveRequest(BaseModel):
    layout: dict[str, dict[str, Any]]
    cols: str | int | None = None
    version: str | None = None


class LayoutSlotSaveRequest(BaseModel):
    name: str
    layout: dict[str, dict[str, Any]]
    cols: str | int | None = None
    version: str | None = None
    slot_id: str | None = None


class LayoutSlotRestoreRequest(BaseModel):
    slot_id: str



class LayoutSlotDeleteRequest(BaseModel):
    slot_id: str



_lock_fd = None
_lock_path: Path | None = None
_log_dir: Path | None = None
_app_start_time = time.time()
_app_started_at_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
_app_session_id = uuid.uuid4().hex[:12]
_stats_lock = threading.Lock()
_stats_total_requests = 0
_stats_total_latency_ms = 0.0
_stats_last_latency_ms: int | None = None
_stats_last_path: str | None = None
_stats_last_status: int | None = None
_stats_last_time: float | None = None
_stats_error_count = 0
_last_observability_export_path: Path | None = None
_last_memory_export_path: Path | None = None
_access_log_lock = threading.Lock()
_quiet_access_state: dict[tuple[str, str, int], dict[str, float | int]] = {}
_QUIET_ACCESS_PATHS = {
    "/api/spot/proxy_image",
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
_QUIET_ACCESS_PREFIXES = (
    "/assets/",
    "/api/layouts/client/",
)
_ACCESS_LOG_SAMPLE_SEC = 5.0

_INVALID_PATH_CHARS = set('<>:"|?*')
_NETWORK_WARN_MS = 200
_SPOT_PROXY_IMAGE_PATH = "/api/spot/proxy_image"
_SPOT_PAYLOAD_REJECTION_CODES = {"invalid-image-html", "invalid-image-payload", "empty-body"}
_SPOT_FOCUS_CONFIG_ERROR = "SPOT_FOCUS_URL is not configured"


def _lifecycle_log_fields() -> str:
    return f"session={_app_session_id} pid={os.getpid()} started_at={_app_started_at_iso}"


def _is_quiet_access_path(path: str) -> bool:
    if path in _QUIET_ACCESS_PATHS:
        return True
    if path == "/api/log/status":
        return True
    return any(path.startswith(prefix) for prefix in _QUIET_ACCESS_PREFIXES)


def _should_log_access_start(path: str) -> bool:
    return not _is_quiet_access_path(path)


def _consume_quiet_access_sample(path: str, client_host: str, status_code: int, now: float) -> tuple[bool, int]:
    key = (path, client_host, status_code)
    with _access_log_lock:
        state = _quiet_access_state.get(key)
        if state is None:
            _quiet_access_state[key] = {
                "last_logged_at": now,
                "suppressed_count": 0,
            }
            return True, 0

        last_logged_at = float(state.get("last_logged_at") or 0.0)
        suppressed_count = int(state.get("suppressed_count") or 0)
        if now - last_logged_at >= _ACCESS_LOG_SAMPLE_SEC:
            state["last_logged_at"] = now
            state["suppressed_count"] = 0
            return True, suppressed_count

        state["suppressed_count"] = suppressed_count + 1
        return False, suppressed_count + 1


def _log_access_completion(path: str, client_host: str, status_code: int, elapsed_ms: float) -> None:
    if _is_quiet_access_path(path) and status_code < 400:
        return

    _logger.info(f"[Access] DONE: {client_host} -> {path} (Status: {status_code}, {elapsed_ms:.1f}ms)")


def _is_valid_segment(segment: str) -> bool:
    if not segment:
        return False
    return not any(ch in _INVALID_PATH_CHARS for ch in segment)


def _is_valid_path(path_str: str) -> bool:
    if not path_str:
        return False
    # Absolute UNC path
    if path_str.startswith("\\\\"):
        parts = [part for part in path_str.split("\\") if part]
        if len(parts) < 2:
            return False
        return all(_is_valid_segment(part) for part in parts)
    # Absolute Windows path
    if len(path_str) >= 3 and path_str[1] == ":" and (path_str[2] == "\\" or path_str[2] == "/") and path_str[0].isalpha():
        tail = path_str[3:]
        if not tail:
            return True
        # Handle both separators
        segments = [s for s in tail.replace("/", "\\").split("\\") if s]
        return all(_is_valid_segment(part) for part in segments)
    # Relative path (e.g. "logs", "./data")
    if not path_str.startswith("/") and not path_str.startswith("\\"):
        segments = [s for s in path_str.replace("/", "\\").split("\\") if s]
        return all(_is_valid_segment(part) for part in segments)
    
    return False


def _is_nas_drive(path_str: str) -> bool:
    return len(path_str) >= 2 and path_str[1] == ":" and path_str[0].upper() == "Z"


def _is_network_path(path_str: str) -> bool:
    return path_str.startswith("\\\\") or _is_nas_drive(path_str)


def _ensure_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def _resolve_log_dir() -> Path:
    """Resolve log directory for system logs (server.log, crash.log)."""
    global _log_dir
    if _log_dir:
        return _log_dir
    base_dir = config.APP_DATA_DIR
    # System logs go to 'system' subdirectory
    candidates = [
        base_dir / "logs" / "system",
        Path(tempfile.gettempdir()) / "SmartFactoryLogger" / "logs" / "system",
        Path.cwd() / "logs" / "system",
    ]
    for candidate in candidates:
        if _ensure_dir(candidate):
            _log_dir = candidate
            return candidate
    _log_dir = Path.cwd()
    return _log_dir


def _observability_state_path() -> Path:
    return _resolve_log_dir() / "observability_last_export.json"


def _memory_state_path() -> Path:
    return _resolve_log_dir() / "memory_last_export.json"


def _persist_observability_export_state(path: Path) -> None:
    try:
        payload = {
            "path": str(path),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _observability_state_path().write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _persist_memory_export_state(path: Path) -> None:
    try:
        payload = {
            "path": str(path),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _memory_state_path().write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _load_observability_export_state() -> tuple[Path | None, str | None]:
    state_path = _observability_state_path()
    if not state_path.exists():
        return None, None
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    path_str = raw.get("path")
    if not path_str:
        return None, raw.get("updated_at")
    return Path(path_str), raw.get("updated_at")


def _load_memory_export_state() -> tuple[Path | None, str | None]:
    state_path = _memory_state_path()
    if not state_path.exists():
        return None, None
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    path_str = raw.get("path")
    if not path_str:
        return None, raw.get("updated_at")
    return Path(path_str), raw.get("updated_at")


def _latest_observability_snapshot(log_dir: Path) -> Path | None:
    try:
        candidates = sorted(
            log_dir.glob("observability_snapshot_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None
    except Exception:
        return None


def _latest_memory_snapshot(log_dir: Path) -> Path | None:
    try:
        candidates = sorted(
            log_dir.glob("memory_snapshot_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None
    except Exception:
        return None


def _resolve_last_observability_export() -> tuple[Path | None, str | None]:
    global _last_observability_export_path
    if _last_observability_export_path and _last_observability_export_path.exists():
        return _last_observability_export_path, None
    state_path, updated_at = _load_observability_export_state()
    if state_path and state_path.exists():
        _last_observability_export_path = state_path
        return state_path, updated_at
    latest = _latest_observability_snapshot(_resolve_log_dir())
    if latest:
        _last_observability_export_path = latest
        return latest, None
    return None, updated_at


def _resolve_last_memory_export() -> tuple[Path | None, str | None]:
    global _last_memory_export_path
    if _last_memory_export_path and _last_memory_export_path.exists():
        return _last_memory_export_path, None
    state_path, updated_at = _load_memory_export_state()
    if state_path and state_path.exists():
        _last_memory_export_path = state_path
        return state_path, updated_at
    return None, updated_at


def _test_tcp(ip: str | None, port: int | None, timeout: float = 1.5) -> dict:
    if not ip or not port:
        return {"ok": False, "latency_ms": None, "message": "IP/Port missing"}
    start = time.perf_counter()
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            pass
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {"ok": True, "latency_ms": latency_ms, "message": "connected"}
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {"ok": False, "latency_ms": latency_ms, "message": str(exc)}


def _test_http(url: str | None, timeout: float = 1.5) -> dict:
    if not url:
        return {"ok": False, "latency_ms": None, "message": "URL missing"}
    start = time.perf_counter()
    try:
        request = Request(url, method="HEAD")
        with urlopen(request, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
        latency_ms = int((time.perf_counter() - start) * 1000)
        if status >= 400:
            return {"ok": False, "latency_ms": latency_ms, "message": f"HTTP {status}"}
        return {"ok": True, "latency_ms": latency_ms, "message": f"HTTP {status}"}
    except Exception:
        try:
            with urlopen(url, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
            latency_ms = int((time.perf_counter() - start) * 1000)
            if status >= 400:
                return {"ok": False, "latency_ms": latency_ms, "message": f"HTTP {status}"}
            return {"ok": True, "latency_ms": latency_ms, "message": f"HTTP {status}"}
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return {"ok": False, "latency_ms": latency_ms, "message": str(exc)}


def _check_path(path_str: str) -> dict:
    start = time.perf_counter()
    try:
        normalized = path_str.strip()
        is_network = _is_network_path(normalized)
        
        # Validation of format
        if not _is_valid_path(normalized):
            latency_ms = int((time.perf_counter() - start) * 1000)
            return {
                "status": "ERROR",
                "exists": False,
                "writable": False,
                "is_dir": False,
                "is_network": is_network,
                "latency_ms": latency_ms,
                "message": "Invalid path format",
            }
            
        # Resolve path - if relative, use APP_DATA_DIR
        path = Path(normalized)
        if not path.is_absolute():
            path = config.APP_DATA_DIR / normalized
            
        if _is_nas_drive(normalized) and not Path("Z:\\").exists():
            latency_ms = int((time.perf_counter() - start) * 1000)
            return {
                "status": "ERROR",
                "exists": False,
                "writable": False,
                "is_dir": False,
                "is_network": True,
                "latency_ms": latency_ms,
                "message": "Network drive unavailable",
            }

        exists = path.exists()
        is_dir = path.is_dir() if exists else False
        if not exists:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return {
                "status": "WARN",
                "exists": False,
                "writable": False,
                "is_dir": False,
                "is_network": is_network,
                "latency_ms": latency_ms,
                "message": "Path not found (creatable)",
            }
        if not is_dir:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return {
                "status": "ERROR",
                "exists": True,
                "writable": False,
                "is_dir": False,
                "is_network": is_network,
                "latency_ms": latency_ms,
                "message": "Not a directory",
            }
        writable = False
        test_file = path / f".sfl_write_test_{os.getpid()}"
        try:
            test_file.write_text("", encoding="utf-8")
            writable = True
        except Exception:
            writable = False
        finally:
            try:
                if test_file.exists():
                    test_file.unlink()
            except Exception:
                pass
        latency_ms = int((time.perf_counter() - start) * 1000)
        if writable:
            if is_network and latency_ms >= _NETWORK_WARN_MS:
                return {
                    "status": "WARN",
                    "exists": True,
                    "writable": True,
                    "is_dir": True,
                    "is_network": is_network,
                    "latency_ms": latency_ms,
                    "message": "Network path latency",
                }
            return {
                "status": "OK",
                "exists": True,
                "writable": True,
                "is_dir": True,
                "is_network": is_network,
                "latency_ms": latency_ms,
                "message": "OK",
            }
        return {
            "status": "ERROR",
            "exists": True,
            "writable": False,
            "is_dir": True,
            "is_network": is_network,
            "latency_ms": latency_ms,
            "message": "Write permission denied",
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "status": "ERROR",
            "exists": False,
            "writable": False,
            "is_dir": False,
            "is_network": _is_network_path(path_str.strip()),
            "latency_ms": latency_ms,
            "message": str(exc),
        }


def _decode_snapshot_payload(payload: str) -> tuple[bytes, str]:
    raw = payload.strip()
    if raw.startswith("data:"):
        header, encoded = raw.split(",", 1)
        content_type = header.split(";")[0]
        ext = content_type.split("/")[-1] if "/" in content_type else "png"
        data = base64.b64decode(encoded)
        return data, ext
    data = base64.b64decode(raw)
    return data, "png"


def _open_path(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
        return
    subprocess.run(["xdg-open", str(path)], check=False)


def _memory_result(
    name: str,
    kind: str,
    bytes_value: int,
    *,
    items: int | None = None,
    note: str | None = None,
    exactness: str = "estimated",
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": kind,
        "exactness": exactness,
        "bytes": max(0, int(bytes_value)),
        "items": items,
        "note": note,
    }


def _estimate_text_bytes(value: Any) -> int:
    if value is None:
        return 0
    return len(str(value)) * 2


def _estimate_mapping_bytes(value: dict[str, Any]) -> int:
    total = 0
    for key, item in value.items():
        total += _estimate_text_bytes(key)
        if isinstance(item, bool):
            total += 8
        elif isinstance(item, int):
            total += 8
        elif isinstance(item, float):
            total += 8
        elif item is None:
            total += 0
        else:
            total += _estimate_text_bytes(item)
    return total


def _collect_observability_requests() -> dict[str, Any]:
    storage_summary = observability_service.get_request_storage_summary()
    return _memory_result(
        "observability.requests",
        "summary",
        int(storage_summary["estimated_bytes"]),
        items=int(storage_summary["detail_count"]),
        note=(
            f"window={storage_summary['request_count']} "
            f"detail={storage_summary['detail_count']} "
            f"polling={storage_summary['polling_count']}"
        ),
    )


def _collect_observability_errors() -> dict[str, Any]:
    error_items = list(observability_service._errors)
    return _memory_result(
        "observability.errors",
        "deque",
        estimate_size_bytes(error_items),
        items=len(error_items),
        note="recent runtime errors",
    )


def _collect_plc_state() -> dict[str, Any]:
    with plc_service.lock:
        current_data = plc_service.current_data
        last_update = plc_service.last_update
    payload = {
        "Time": getattr(current_data, "Time", None),
        "Status": getattr(current_data, "Status", None),
        "Speed": getattr(current_data, "Speed", None),
        "Press": getattr(current_data, "Press", None),
        "Spot": getattr(current_data, "Spot", None),
        "Count": getattr(current_data, "Count", None),
        "Computed": getattr(current_data, "Computed", None),
        "last_update": last_update,
        "mode": plc_service.mode,
    }
    return _memory_result(
        "facility.plc_state",
        "snapshot",
        _estimate_mapping_bytes(payload),
        items=len(payload),
        note="latest plc scalar summary",
    )


def _collect_csv_logger() -> dict[str, Any]:
    runtime_state = logger_service.get_runtime_state()
    payload = {
        "queue_size": int(runtime_state.get("queue_size") or 0),
        "buffer_size": int(runtime_state.get("buffer_size") or 0),
        "rotation_mode": runtime_state.get("rotation_mode"),
        "rotation_enabled": runtime_state.get("rotation_enabled"),
        "auto_save": runtime_state.get("auto_save"),
        "log_path": runtime_state.get("log_path"),
    }
    return _memory_result(
        "facility.csv_logger",
        "queue",
        _estimate_mapping_bytes(payload),
        items=int(runtime_state.get("queue_size") or 0) + int(runtime_state.get("buffer_size") or 0),
        note=f"queue={runtime_state.get('queue_size')} buffer={runtime_state.get('buffer_size')}",
    )


def _collect_config_manager() -> dict[str, Any]:
    snapshot = config_manager.get_snapshot()
    flat_items = dict(config_manager._flat)
    pending_keys = list(config_manager._pending_keys)
    last_apply = dict(config_manager._last_apply)
    payload = {
        "config_path": snapshot.get("config_path"),
        "encoding": snapshot.get("encoding"),
        "restart_required": snapshot.get("restart_required"),
        "flat_count": len(flat_items),
        "pending_count": len(pending_keys),
        "applied_count": len(last_apply.get("applied") or []),
        "pending_apply_count": len(last_apply.get("pending") or []),
    }
    return _memory_result(
        "configuration.snapshot",
        "snapshot",
        _estimate_mapping_bytes(payload),
        items=len(flat_items),
        note="config summary and pending counters",
    )


def _collect_spot_cache() -> dict[str, Any]:
    image_bytes = 0
    image_data = spot_control._img_cache.get("data")
    if isinstance(image_data, (bytes, bytearray)):
        image_bytes = len(image_data)
    payload = {
        "image_bytes": image_bytes,
        "temperature": spot_control._img_cache.get("temp"),
        "fetched_at": spot_control._img_cache.get("time"),
        "temperature_at": spot_control._img_cache.get("temp_time"),
    }
    note = "cached image metadata and byte length"
    return _memory_result(
        "spot.cache",
        "cache",
        image_bytes + _estimate_mapping_bytes(payload),
        items=1,
        note=note,
    )


def _collect_mes_sync_state() -> dict[str, Any]:
    payload = dict(mes_sync.sync_state)
    return _memory_result(
        "mes.sync_state",
        "state",
        estimate_size_bytes(payload),
        items=1,
        note="manual sync state",
    )


def _register_memory_collectors() -> None:
    memory_service.register_collector("observability.requests", _collect_observability_requests)
    memory_service.register_collector("observability.errors", _collect_observability_errors)
    memory_service.register_collector("facility.plc_state", _collect_plc_state)
    memory_service.register_collector("facility.csv_logger", _collect_csv_logger)
    memory_service.register_collector("configuration.snapshot", _collect_config_manager)
    memory_service.register_collector("spot.cache", _collect_spot_cache)
    memory_service.register_collector("mes.sync_state", _collect_mes_sync_state)


_log_queue_listeners = []

def _setup_logging() -> tuple[logging.Logger, logging.Logger]:
    log_dir = _resolve_log_dir()
    
    # JSON Formatter for Files (Agent Parsing)
    json_formatter = CustomJsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(trace_id)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console Formatter (Human Readable)
    console_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(trace_id)s] %(message)s", 
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    logger = logging.getLogger("SmartFactoryLoggerV2")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Async Queue Handler
        log_queue = queue.Queue(-1)
        queue_handler = QueueHandler(log_queue)
        queue_handler.addFilter(TraceIDFilter())
        logger.addHandler(queue_handler)

        system_log = log_dir / "system.log"
        file_handler = SafeRotatingFileHandler(
            system_log,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(json_formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(console_formatter)

        listener = QueueListener(log_queue, file_handler, console_handler, respect_handler_level=True)
        listener.start()
        _log_queue_listeners.append(listener)

    crash_logger = logging.getLogger("SmartFactoryLoggerV2.Crash")
    if not crash_logger.handlers:
        crash_logger.setLevel(logging.ERROR)
        
        crash_queue = queue.Queue(-1)
        crash_queue_handler = QueueHandler(crash_queue)
        crash_queue_handler.addFilter(TraceIDFilter())
        crash_logger.addHandler(crash_queue_handler)
        
        crash_log = log_dir / "crash.log"
        crash_handler = SafeRotatingFileHandler(
            crash_log,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        crash_handler.setFormatter(json_formatter)
        
        crash_listener = QueueListener(crash_queue, crash_handler, respect_handler_level=True)
        crash_listener.start()
        _log_queue_listeners.append(crash_listener)

    return logger, crash_logger

_logger, _crash_logger = _setup_logging()
_register_memory_collectors()


class FrontendResolutionCandidateSpec(NamedTuple):
    source: str
    origin: str
    path: Path


class FrontendResolutionCandidate(TypedDict):
    priority: int
    source: str
    origin: str
    path: str
    exists: bool
    missing_assets: list[str]
    is_ready: bool


def build_frontend_resolution_candidate(
    priority: int,
    spec: FrontendResolutionCandidateSpec,
) -> FrontendResolutionCandidate:
    resolved_path = spec.path.resolve(strict=False)
    exists = resolved_path.is_dir()
    missing_assets = get_frontend_missing_assets(resolved_path) if exists else []
    return {
        "priority": priority,
        "source": spec.source,
        "origin": spec.origin,
        "path": str(resolved_path),
        "exists": exists,
        "missing_assets": missing_assets,
        "is_ready": exists and not missing_assets,
    }


def get_frontend_resolution_candidates(
    candidate_specs: list[FrontendResolutionCandidateSpec],
) -> list[FrontendResolutionCandidate]:
    return [
        build_frontend_resolution_candidate(
            priority=index,
            spec=spec,
        )
        for index, spec in enumerate(candidate_specs, start=1)
    ]


def get_frozen_frontend_candidate_specs() -> list[FrontendResolutionCandidateSpec]:
    executable_dir = Path(sys.executable).resolve().parent
    candidate_specs: list[FrontendResolutionCandidateSpec] = [
        FrontendResolutionCandidateSpec("sidecar", "executable_dir", executable_dir / "frontend" / "dist"),
        FrontendResolutionCandidateSpec("resources", "executable_parent", executable_dir.parent / "frontend" / "dist"),
        FrontendResolutionCandidateSpec("resources", "executable_grandparent", executable_dir.parent.parent / "frontend" / "dist"),
    ]

    if hasattr(sys, "_MEIPASS"):
        candidate_specs.append(
            FrontendResolutionCandidateSpec("meipass", "pyinstaller_temp", Path(sys._MEIPASS) / "frontend" / "dist")
        )

    unique_specs: list[FrontendResolutionCandidateSpec] = []
    seen_paths: set[str] = set()
    for spec in candidate_specs:
        normalized_path = str(spec.path.resolve(strict=False))
        if normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        unique_specs.append(spec)

    return unique_specs


def resolve_frontend_dist() -> tuple[Path, str, str, str, str, list[FrontendResolutionCandidateSpec]]:
    if getattr(sys, "frozen", False):
        candidate_specs = get_frozen_frontend_candidate_specs()
        candidates = get_frontend_resolution_candidates(candidate_specs)
        for candidate in candidates:
            if candidate["is_ready"]:
                resolution_reason = f"selected_ready_{candidate['source']}_{candidate['origin']}"
                return (
                    Path(candidate["path"]),
                    "frozen",
                    candidate["source"],
                    candidate["origin"],
                    resolution_reason,
                    candidate_specs,
                )

        for candidate in candidates:
            if candidate["exists"]:
                return (
                    Path(candidate["path"]),
                    "frozen",
                    candidate["source"],
                    candidate["origin"],
                    f"selected_existing_incomplete_{candidate['source']}_{candidate['origin']}",
                    candidate_specs,
                )

        fallback_path = candidate_specs[0].path.resolve(strict=False)
        return (
            fallback_path,
            "frozen",
            candidate_specs[0].source,
            candidate_specs[0].origin,
            "no_frontend_dist_candidate_exists",
            candidate_specs,
        )

    development_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    development_candidate_specs = [
        FrontendResolutionCandidateSpec(
            "project",
            "project_root",
            development_dist,
        )
    ]
    return (
        development_dist,
        "development",
        "project",
        "project_root",
        "selected_ready_project_project_root",
        development_candidate_specs,
    )


_FRONTEND_REQUIRED_EXACT_PATHS: tuple[str, ...] = (
    "index.html",
    "manifest.json",
    "favicon.ico",
    "logo192.png",
    "logo512.png",
    "assets/logo_white.png",
    "assets/logo_color.png",
)
_FRONTEND_REQUIRED_GLOB_PATTERNS: tuple[str, ...] = (
    "assets/index-*.js",
    "assets/index-*.css",
)
_FRONTEND_PUBLIC_FILENAMES: tuple[str, ...] = (
    "manifest.json",
    "favicon.ico",
    "logo192.png",
    "logo512.png",
)
_FRONTEND_ENTRY_ASSET_PATTERN = re.compile(r'(?:src|href)="\./(assets/[^"]+\.(?:js|css))"')


def get_frontend_runtime_class(frontend_mode: str, frontend_source: str) -> str:
    if frontend_mode == "development":
        return "development"
    if frontend_source == "sidecar":
        return "portable-sidecar"
    if frontend_source == "resources":
        return "packaged-resources"
    if frontend_source == "meipass":
        return "legacy-one-file"
    return "unknown"


def get_frontend_runtime_warning(frontend_source: str, frontend_missing_assets: list[str]) -> str:
    if frontend_missing_assets:
        if "index.html" in frontend_missing_assets:
            return "missing_index"
        return "missing_assets"
    if frontend_source == "meipass":
        return "legacy_meipass"
    return "none"


def get_frontend_required_entry_assets(frontend_dist_path: Path) -> list[str]:
    index_path = frontend_dist_path / "index.html"
    if not index_path.is_file():
        return []

    try:
        index_html = index_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        index_html = index_path.read_text(encoding="utf-8", errors="ignore")

    return sorted(set(_FRONTEND_ENTRY_ASSET_PATTERN.findall(index_html)))


def get_frontend_missing_assets(frontend_dist_path: Path) -> list[str]:
    missing_assets: list[str] = []
    for relative_path in _FRONTEND_REQUIRED_EXACT_PATHS:
        if not (frontend_dist_path / relative_path).is_file():
            missing_assets.append(relative_path)

    required_entry_assets = get_frontend_required_entry_assets(frontend_dist_path)
    if required_entry_assets:
        for relative_path in required_entry_assets:
            if not (frontend_dist_path / relative_path).is_file():
                missing_assets.append(relative_path)
    else:
        for relative_pattern in _FRONTEND_REQUIRED_GLOB_PATTERNS:
            if not any(candidate.is_file() for candidate in frontend_dist_path.glob(relative_pattern)):
                missing_assets.append(relative_pattern)

    return sorted(missing_assets)


def get_frontend_static_status(
    frontend_dist_path: Path,
    frontend_mode: str,
    frontend_source: str,
    frontend_source_origin: str,
    selected_resolution_reason: str,
    candidate_specs: list[FrontendResolutionCandidateSpec],
) -> dict[str, Any]:
    index_path = frontend_dist_path / "index.html"
    assets_path = frontend_dist_path / "assets"
    frontend_dist_exists = frontend_dist_path.exists()
    frontend_index_exists = index_path.exists()
    frontend_assets_exists = assets_path.exists()
    frontend_missing_assets = get_frontend_missing_assets(frontend_dist_path)
    frontend_resolution_candidates = get_frontend_resolution_candidates(candidate_specs)

    return {
        "frontend_mode": frontend_mode,
        "frontend_source": frontend_source,
        "frontend_source_origin": frontend_source_origin,
        "frontend_runtime_class": get_frontend_runtime_class(frontend_mode, frontend_source),
        "frontend_runtime_warning": get_frontend_runtime_warning(frontend_source, frontend_missing_assets),
        "frontend_dist_path": str(frontend_dist_path),
        "frontend_resolution_reason": selected_resolution_reason,
        "frontend_resolution_candidates": frontend_resolution_candidates,
        "frontend_dist_exists": frontend_dist_exists,
        "frontend_index_exists": frontend_index_exists,
        "frontend_assets_exists": frontend_assets_exists,
        "frontend_missing_assets": frontend_missing_assets,
        "frontend_static_ready": frontend_dist_exists and not frontend_missing_assets,
    }


def resolve_frontend_file(base_dir: Path, relative_path: str) -> Path | None:
    try:
        resolved_base_dir = base_dir.resolve(strict=False)
        resolved_target = (base_dir / relative_path).resolve(strict=False)
    except OSError:
        return None

    try:
        resolved_target.relative_to(resolved_base_dir)
    except ValueError:
        return None

    return resolved_target


def resolve_nested_frontend_file(frontend_dist_path: Path, full_path: str) -> Path | None:
    normalized_path = full_path.lstrip("/")
    if "/assets/" in normalized_path:
        asset_suffix = normalized_path.rsplit("/assets/", 1)[1]
        if asset_suffix:
            asset_path = resolve_frontend_file(frontend_dist_path / "assets", asset_suffix)
            if asset_path is not None:
                return asset_path

    for public_filename in _FRONTEND_PUBLIC_FILENAMES:
        if normalized_path == public_filename or normalized_path.endswith(f"/{public_filename}"):
            public_path = resolve_frontend_file(frontend_dist_path, public_filename)
            if public_path is not None:
                return public_path

    return None


def is_frontend_file_request(full_path: str) -> bool:
    normalized_path = full_path.lstrip("/")
    if "/assets/" in normalized_path:
        return True
    last_segment = normalized_path.rsplit("/", 1)[-1]
    if last_segment in _FRONTEND_PUBLIC_FILENAMES:
        return True
    return "." in last_segment


def get_frontend_file_request_status(frontend_status: dict[str, Any], full_path: str) -> int:
    normalized_path = full_path.lstrip("/")
    if "/assets/" in normalized_path and not frontend_status["frontend_assets_exists"]:
        return 503
    if not frontend_status["frontend_dist_exists"]:
        return 503
    return 404


def build_frontend_error_response(status_code: int, detail: str) -> JSONResponse:
    frontend_status = get_frontend_static_status(
        frontend_dist,
        frontend_mode,
        frontend_source,
        frontend_source_origin,
        frontend_resolution_reason,
        frontend_resolution_candidate_specs,
    )
    payload: dict[str, Any] = {
        "detail": detail,
        "status_code": status_code,
        **frontend_status,
    }
    return JSONResponse(status_code=status_code, content=payload)


frontend_dist, frontend_mode, frontend_source, frontend_source_origin, frontend_resolution_reason, frontend_resolution_candidate_specs = resolve_frontend_dist()
frontend_status_snapshot = get_frontend_static_status(
    frontend_dist,
    frontend_mode,
    frontend_source,
    frontend_source_origin,
    frontend_resolution_reason,
    frontend_resolution_candidate_specs,
)
_logger.info(
    "Frontend static root resolved",
    extra={
        **frontend_status_snapshot,
        "frontend_sys_executable": sys.executable,
        "frontend_sys_meipass": getattr(sys, "_MEIPASS", None),
        "frontend_app_project_root": str(project_root),
    },
)
if frontend_status_snapshot["frontend_runtime_warning"] != "none":
    _logger.warning(
        "Frontend runtime warning",
        extra={
            **frontend_status_snapshot,
            "frontend_sys_executable": sys.executable,
            "frontend_sys_meipass": getattr(sys, "_MEIPASS", None),
            "frontend_app_project_root": str(project_root),
        },
    )


def get_frontend_log_context() -> dict[str, Any]:
    return {
        "frontend_mode": frontend_mode,
        "frontend_source": frontend_source,
        "frontend_source_origin": frontend_source_origin,
        "frontend_dist_path": str(frontend_dist),
        "frontend_resolution_reason": frontend_resolution_reason,
    }



def _write_crash_log(title: str, exc_type, exc_value, tb) -> None:
    if _crash_logger:
        _crash_logger.error(title, exc_info=(exc_type, exc_value, tb))
        return
    log_dir = _resolve_log_dir()
    crash_log = log_dir / "crash.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with crash_log.open("a", encoding="utf-8") as handle:
            handle.write(f"\n{'=' * 40}\n[{timestamp}] {title}\n{'=' * 40}\n")
            handle.write("".join(traceback.format_exception(exc_type, exc_value, tb)))
            handle.write("-" * 80 + "\n")
    except Exception as exc:
        print(f"[Main] Failed to write crash log: {exc}", file=sys.stderr)


def _exception_hook(exc_type, exc_value, tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, tb)
        return
    _write_crash_log("UNHANDLED EXCEPTION", exc_type, exc_value, tb)
    sys.__excepthook__(exc_type, exc_value, tb)


def _thread_exception_hook(args: threading.ExceptHookArgs) -> None:
    _write_crash_log(
        f"UNHANDLED THREAD EXCEPTION: {getattr(args.thread, 'name', 'unknown')}",
        args.exc_type,
        args.exc_value,
        args.exc_traceback,
    )
    if hasattr(threading, "__excepthook__"):
        threading.__excepthook__(args)
    else:
        sys.__excepthook__(args.exc_type, args.exc_value, args.exc_traceback)


sys.excepthook = _exception_hook
threading.excepthook = _thread_exception_hook


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    return True


def _get_lock_path() -> Path:
    global _lock_path
    if _lock_path:
        return _lock_path
    base_dir = None
    if config.CONFIG_PATH and config.CONFIG_PATH.parent:
        base_dir = config.CONFIG_PATH.parent
    if base_dir is None:
        appdata = os.getenv("APPDATA")
        base_dir = Path(appdata) / "SmartFactoryLogger" if appdata else Path.cwd()
    _lock_path = base_dir / "sfl_v2.lock"
    return _lock_path


def release_single_instance_lock() -> None:
    global _lock_fd
    lock_path = _get_lock_path()
    try:
        if _lock_fd is not None:
            os.close(_lock_fd)
            _lock_fd = None
    except Exception:
        pass
    try:
        if lock_path.exists():
            lock_path.unlink()
    except Exception:
        pass


def acquire_single_instance_lock() -> bool:
    global _lock_fd
    lock_path = _get_lock_path()
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        _lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(_lock_fd, str(os.getpid()).encode("ascii", errors="ignore"))
        atexit.register(release_single_instance_lock)
        return True
    except FileExistsError:
        existing_pid = 0
        try:
            raw = lock_path.read_text(encoding="ascii", errors="ignore").strip()
            if raw.isdigit():
                existing_pid = int(raw)
        except Exception:
            existing_pid = 0

        if existing_pid and _pid_is_alive(existing_pid):
            print(f"[Main] Another instance is already running (pid={existing_pid}).")
            return False

        try:
            lock_path.unlink()
        except Exception:
            print("[Main] Stale lock detected but could not remove it.")
            return False
        return acquire_single_instance_lock()
    except Exception as exc:
        print(f"[Main] Failed to acquire single instance lock: {exc}")
        return True

# MES Bridge 제어는 mes_scheduler.start() / stop()을 통해 수행됩니다.

# Lifecycle Manager (Startup/Shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not acquire_single_instance_lock():
        raise RuntimeError("Instance already running")
    _logger.info("[Main] Lifespan startup begin %s", _lifecycle_log_fields())
    print("[Main] Starting CSV Logger...")
    logger_service.start()
    print("[Main] Starting Config Sync Agent...")
    config_sync_agent.start()
    print("[Main] Starting Config Watcher...")
    config_watch_service.start()
    print("[Main] Starting PLC Service...")
    plc_service.start()
    print("[Main] Starting Comm Metrics Logger...")
    comm_metrics_logger_service.start()
    print("[Main] Starting Memory Service...")
    memory_service.start()

    # Start MES Bridge if enabled
    if config.MES_ENABLED:
        await mes_scheduler.start()
    
    # Start SPOT image background prefetching
    print("[Main] Starting SPOT Image Prefetch...")
    await spot_control.start_prefetch_loop()
    
    # Log local IPs for debugging remote connectivity
    try:
        hostname = socket.gethostname()
        local_ips = socket.gethostbyname_ex(hostname)[2]
        _logger.info(
            "[Main] Backend started. Accessible at: %s %s",
            ", ".join([f"http://{ip}:{config.BACKEND_PORT}" for ip in local_ips]),
            _lifecycle_log_fields(),
        )
    except Exception as exc:
        _logger.warning(f"[Main] Failed to log local IPs: {exc}")

    try:
        yield
    finally:
        # Shutdown
        _logger.info("[Main] Lifespan shutdown begin %s", _lifecycle_log_fields())
        print("[Main] Stopping SPOT Image Prefetch...")
        await spot_control.stop_prefetch_loop()
        print("[Main] Stopping Comm Metrics Logger...")
        comm_metrics_logger_service.stop()
        print("[Main] Stopping Memory Service...")
        memory_service.stop()
        print("[Main] Stopping PLC Service...")
        plc_service.stop()
        print("[Main] Stopping Config Sync Agent...")
        config_sync_agent.stop()
        print("[Main] Stopping Config Watcher...")
        config_watch_service.stop()
        print("[Main] Stopping CSV Logger...")
        logger_service.stop()
        release_single_instance_lock()

# --- App Definition ---
app = FastAPI(
    title="Smart Factory Logger V2 API",
    description="Backend API for Smart Factory Logger V2 (Web Tech)",
    version=config.APP_VERSION,
    lifespan=lifespan
)

# Register Routers
app.include_router(mes_router.router, prefix="/api/mes", tags=["MES"])
app.include_router(mes_sync.router, prefix="/api/mes/sync", tags=["MES Sync"])
app.include_router(ai_tools_dispatcher.router, prefix="/api", tags=["AI Tool Calling"])

# CORS (Allow Frontend Access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def record_request_stats(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    token = trace_id_var.set(trace_id)
    
    global _stats_total_requests
    global _stats_total_latency_ms
    global _stats_last_latency_ms
    global _stats_last_path
    global _stats_last_status
    global _stats_last_time
    global _stats_error_count
    start = time.perf_counter()
    status_code = 500
    client_host = request.client.host if request.client else "unknown"
    response = None
    try:
        if _should_log_access_start(request.url.path):
            _logger.info(f"[Access] INCOMING: {client_host} -> {request.method} {request.url.path}")
        
        response = await call_next(request)
        status_code = response.status_code
        
        is_spot_payload_rejection = _is_spot_proxy_payload_rejection_response(
            request.url.path,
            status_code,
            dict(response.headers),
        )

        if status_code >= 500 and not is_spot_payload_rejection:
            try:
                observability_service.record_error(
                    "api",
                    f"HTTP {status_code}",
                    path=request.url.path,
                )
            except Exception:
                pass
        return response
    except Exception as exc:
        try:
            observability_service.record_error(
                "api",
                str(exc),
                path=request.url.path,
            )
        except Exception:
            pass
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        _log_access_completion(request.url.path, client_host, status_code, elapsed_ms)
        
        if response is not None:
            response.headers["X-Trace-ID"] = trace_id
            
        try:
            observability_service.record_request(request.url.path, status_code, elapsed_ms, client_host)
        except Exception:
            pass
        with _stats_lock:
            _stats_total_requests += 1
            _stats_total_latency_ms += elapsed_ms
            _stats_last_latency_ms = int(elapsed_ms)
            _stats_last_path = request.url.path
            _stats_last_status = status_code
            _stats_last_time = time.time()
            if status_code >= 400 and not is_spot_payload_rejection:
                _stats_error_count += 1
        trace_id_var.reset(token)

@app.get("/")
def read_root():
    frontend_status = get_frontend_static_status(
        frontend_dist,
        frontend_mode,
        frontend_source,
        frontend_source_origin,
        frontend_resolution_reason,
        frontend_resolution_candidate_specs,
    )
    if frontend_status["frontend_static_ready"]:
        index_path = frontend_dist / "index.html"
        if frontend_status["frontend_index_exists"]:
            return FileResponse(index_path)

    _logger.error(
        "Frontend index unavailable for root request",
        extra={
            **get_frontend_log_context(),
            "frontend_missing_assets": frontend_status["frontend_missing_assets"],
        },
    )
    return build_frontend_error_response(503, "Frontend bundle is incomplete.")

@app.get("/api/data", response_model=FactoryData)
async def get_data():
    """Get latest snapshot from PLC Service (Memory)"""
    return plc_service.get_latest_data()

@app.get("/health")
async def health():
    return {
        **plc_service.get_health(),
        **get_runtime_info(),
        **get_frontend_static_status(
            frontend_dist,
            frontend_mode,
            frontend_source,
            frontend_source_origin,
            frontend_resolution_reason,
            frontend_resolution_candidate_specs,
        ),
    }

@app.get("/stats")
async def stats():
    data = observability_service.get_stats()
    data["uptime_sec"] = int(time.time() - _app_start_time)
    return data

@app.get("/api/observability/errors")
async def list_observability_errors(limit: int = 50):
    try:
        items = observability_service.get_errors(limit)
        summary = observability_service.get_error_summary()
        return {"items": items, "summary": summary}
    except Exception as exc:
        _logger.error("Observability errors fetch failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/observability/errors/clear")
def clear_observability_errors():
    try:
        observability_service.clear_errors()
        return {"ok": True}
    except Exception as exc:
        _logger.error("Observability errors clear failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/observability/export")
async def export_observability(payload: ObservabilityExportRequest):
    global _last_observability_export_path
    try:
        # Vercel Guidelines: Run independent tasks concurrently
        health_task = asyncio.to_thread(plc_service.get_health)
        stats_task = asyncio.to_thread(observability_service.get_stats)
        errors_task = asyncio.to_thread(observability_service.get_errors, 200) if payload.include_errors else asyncio.to_thread(lambda: [])
        
        health_snapshot, stats_snapshot, errors_snapshot = await asyncio.gather(
            health_task, stats_task, errors_task
        )

        front_errors_payload: list[dict[str, Any]] = []
        if payload.front_errors:
            for item in payload.front_errors:
                data = item.dict()
                ts_value = data.get("time")
                ts_sec: float | None = None
                ts_ms: int | None = None
                if isinstance(ts_value, (int, float)):
                    ts_sec = float(ts_value)
                    if ts_sec > 1_000_000_000_000:
                        ts_ms = int(ts_sec)
                        ts_sec = ts_sec / 1000.0
                    else:
                        ts_ms = int(ts_sec * 1000)
                    data["time"] = ts_sec
                    data["time_ms"] = ts_ms
                    data["time_iso"] = datetime.fromtimestamp(ts_sec, tz=timezone.utc).isoformat(
                        timespec="seconds"
                    )
                front_errors_payload.append(data)
        snapshot = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "health": health_snapshot,
            "stats": stats_snapshot,
            "errors": errors_snapshot,
            "front_errors": front_errors_payload,
            "front_error_count": len(front_errors_payload),
        }
        log_dir = _resolve_log_dir()
        filename = f"observability_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Vercel Guidelines: Use non-blocking disk I/O when possible or offload
        def _write_and_persist():
            path = log_dir / filename
            path.write_text(json.dumps(snapshot, ensure_ascii=True, indent=2), encoding="utf-8")
            _persist_observability_export_state(path)
            return path
            
        path = await asyncio.to_thread(_write_and_persist)
        _last_observability_export_path = path
        return {"ok": True, "path": str(path), "size": path.stat().st_size}
    except Exception as exc:
        _logger.error("Observability export failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/observability/export/open-file")
def open_observability_export_file():
    try:
        path, _ = _resolve_last_observability_export()
        if not path or not path.exists():
            raise HTTPException(status_code=404, detail="Export file missing")
        _open_path(path)
        return {"ok": True, "path": str(path)}
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Open export file failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/observability/export/open-folder")
def open_observability_export_folder():
    try:
        path, _ = _resolve_last_observability_export()
        if not path or not path.exists():
            raise HTTPException(status_code=404, detail="Export file missing")
        _open_path(path.parent)
        return {"ok": True, "path": str(path.parent)}
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Open export folder failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/api/observability/export/latest")
def get_observability_export_latest():
    path, updated_at = _resolve_last_observability_export()
    return {
        "path": str(path) if path else None,
        "updated_at": updated_at,
    }


@app.get("/api/memory/state")
def get_memory_state():
    try:
        return memory_service.get_summary_state()
    except Exception as exc:
        _logger.error("Memory state fetch failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/memory/details")
def get_memory_details():
    try:
        return memory_service.get_details_state()
    except Exception as exc:
        _logger.error("Memory details fetch failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/memory/profiler/start")
def start_memory_profiler():
    try:
        return memory_service.start_profiler()
    except Exception as exc:
        _logger.error("Memory profiler start failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/memory/profiler/stop")
def stop_memory_profiler():
    try:
        return memory_service.stop_profiler()
    except Exception as exc:
        _logger.error("Memory profiler stop failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/memory/snapshot")
def capture_memory_snapshot():
    try:
        return memory_service.capture_snapshot()
    except Exception as exc:
        _logger.error("Memory snapshot failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/memory/export")
async def export_memory_snapshot(payload: MemoryExportRequest):
    global _last_memory_export_path
    try:
        snapshot = await asyncio.to_thread(memory_service.build_export_payload, payload.frontend or {})
        log_dir = _resolve_log_dir()
        filename = f"memory_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        def _write_and_persist() -> Path:
            path = log_dir / filename
            path.write_text(json.dumps(snapshot, ensure_ascii=True, indent=2), encoding="utf-8")
            _persist_memory_export_state(path)
            return path

        path = await asyncio.to_thread(_write_and_persist)
        _last_memory_export_path = path
        return {"ok": True, "path": str(path), "size": path.stat().st_size}
    except Exception as exc:
        _logger.error("Memory export failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/memory/export/latest")
def get_memory_export_latest():
    path, updated_at = _resolve_last_memory_export()
    return {
        "path": str(path) if path else None,
        "updated_at": updated_at,
    }


@app.post("/api/memory/export/open-file")
def open_memory_export_file():
    try:
        path, _ = _resolve_last_memory_export()
        if not path or not path.exists():
            raise HTTPException(status_code=404, detail="Export file missing")
        _open_path(path)
        return {"ok": True, "path": str(path)}
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Open memory export file failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/memory/export/open-folder")
def open_memory_export_folder():
    try:
        path, _ = _resolve_last_memory_export()
        if not path or not path.exists():
            raise HTTPException(status_code=404, detail="Export file missing")
        _open_path(path.parent)
        return {"ok": True, "path": str(path.parent)}
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Open memory export folder failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/api/logs/comm-metrics")
def comm_metrics_log_info():
    try:
        return {"path": comm_metrics_logger_service.get_log_path()}
    except Exception as exc:
        _logger.error("Comm metrics log path failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/logs/comm-metrics/open")
def open_comm_metrics_log():
    try:
        log_path = comm_metrics_logger_service.get_log_path()
        if not log_path:
            raise HTTPException(status_code=404, detail="Comm metrics log not available")
        target = Path(log_path).parent
        _open_path(target)
        return {"ok": True, "path": str(target)}
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Open comm metrics log failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/logs/comm-metrics/open-file")
def open_comm_metrics_log_file():
    try:
        log_path = comm_metrics_logger_service.get_log_path()
        if not log_path:
            raise HTTPException(status_code=404, detail="Comm metrics log not available")
        target = Path(log_path)
        _open_path(target)
        return {"ok": True, "path": str(target)}
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Open comm metrics log file failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/api/config")
async def get_config():
    try:
        return get_config_snapshot()
    except Exception as exc:
        _logger.error("Config load failed: %s", exc)
        raise HTTPException(status_code=500, detail="Config load failed") from exc


@app.post("/api/config")
def save_config(payload: ConfigUpdate):
    """Save configuration settings. Requires override enabled for local changes."""
    try:
        return update_config(payload, source="local")
    except PermissionError as exc:
        _logger.warning("Config save permission error: %s", exc)
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Config save failed: %s", exc)
        raise HTTPException(status_code=500, detail="Config save failed") from exc

class NoticeUpdateRequest(BaseModel):
    content: str


@app.get("/api/config/notice")
async def get_notice():
    return {"content": config.CUSTOM_NOTICE}


@app.post("/api/config/notice")
async def save_notice(payload: NoticeUpdateRequest):
    try:
        config.CUSTOM_NOTICE = payload.content
        update_payload = ConfigUpdate(settings=SettingsConfig(custom_notice=payload.content))
        update_config(update_payload, source="notice_widget")
        return {"status": "ok"}
    except Exception as exc:
        _logger.error("Notice save failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/config/override")
def update_override(payload: OverrideToggle):
    try:
        return set_override_enabled(payload.enabled, payload.password, payload.actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Override update failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class PasswordVerifyRequest(BaseModel):
    password: str


@app.post("/api/config/verify-password")
def verify_password(payload: PasswordVerifyRequest):
    """Verify the settings access password."""
    import configparser

    try:
        # Check if password is set using the already-imported get_config_snapshot
        snapshot = get_config_snapshot()
        password_set = snapshot.get("values", {}).get("settings", {}).get("password_set", False)
        
        if not password_set:
            # No password set, allow access
            return {"ok": True, "message": "비밀번호가 설정되지 않았습니다."}
        
        # Read actual password from config file
        config_path_str = snapshot.get("config_path", "")
        config_path = Path(config_path_str) if config_path_str else None
        
        if not config_path or not config_path.exists():
            return {"ok": True, "message": "설정 파일이 없습니다."}
        
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read(str(config_path), encoding="utf-8-sig")
        
        stored_password = ""
        if parser.has_option("SETTINGS", "password"):
            stored_password = parser.get("SETTINGS", "password").strip()
        
        if not stored_password:
            return {"ok": True, "message": "비밀번호가 설정되지 않았습니다."}
        
        if payload.password == stored_password:
            return {"ok": True, "message": "인증 성공"}
        else:
            raise HTTPException(status_code=403, detail="비밀번호가 일치하지 않습니다.")
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Password verification failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/config/restore-defaults")
def restore_config_defaults():
    try:
        return restore_defaults()
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Restore defaults failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/config/restore-backup")
def restore_config_backup():
    try:
        return restore_backup()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Restore backup failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/config/pending/apply")
def apply_pending():
    try:
        return apply_pending_config()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Pending config apply failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/config/pending/clear")
def clear_pending():
    try:
        return clear_pending_config()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Pending config clear failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/api/layout")
def get_layout():
    try:
        data = get_active_layout()
        if not data:
            raise HTTPException(status_code=404, detail="Layout not found")
        return data
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Layout load failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/layout/meta")
def layout_meta():
    try:
        return get_layout_meta()
    except Exception as exc:
        _logger.error("Layout meta failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/layouts")
def get_layouts():
    try:
        return list_layouts()
    except Exception as exc:
        _logger.error("Layout list failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/layouts")
def save_layout_slot_api(payload: LayoutSlotSaveRequest):
    try:
        return save_layout_slot(payload.name, payload.layout, payload.cols, payload.version, payload.slot_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Layout slot save failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/layouts/restore")
def restore_layout_slot_api(payload: LayoutSlotRestoreRequest):
    try:
        return restore_layout_slot(payload.slot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Layout slot restore failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/layouts/delete")
def delete_layout_slot_api(payload: LayoutSlotDeleteRequest):
    try:
        return delete_layout_slot(payload.slot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Layout slot delete failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/layout")
def save_layout_api(payload: LayoutSaveRequest):
    try:
        return save_layout_slot("레이아웃", payload.layout, payload.cols, payload.version, None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Layout save failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/layout/restore")
def restore_layout_api():
    try:
        return restore_layout_backup()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Layout restore failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# --- Client-Specific Layout Storage ---
# Each client has a unique UUID; layouts are stored in AppData/Roaming/SmartFactoryLogger/layouts/

_CLIENT_LAYOUTS_DIR: Path | None = None


def _get_client_layouts_dir() -> Path:
    """Get the directory for storing client-specific layouts."""
    global _CLIENT_LAYOUTS_DIR
    if _CLIENT_LAYOUTS_DIR is not None:
        return _CLIENT_LAYOUTS_DIR
    
    # Use APPDATA on Windows, or a fallback for other systems
    appdata = os.environ.get("APPDATA")
    if appdata:
        base_dir = Path(appdata) / "SmartFactoryLogger"
    else:
        # Fallback for non-Windows systems
        base_dir = Path.home() / ".smartfactorylogger"
    
    layouts_dir = base_dir / "layouts"
    layouts_dir.mkdir(parents=True, exist_ok=True)
    _CLIENT_LAYOUTS_DIR = layouts_dir
    _logger.info(f"[ClientLayout] Storage directory: {layouts_dir}")
    return layouts_dir


def _validate_client_id(client_id: str) -> bool:
    """Validate that client_id is a safe UUID-like string."""
    import re
    # Accept UUID format or simple alphanumeric with dashes
    pattern = r'^[a-zA-Z0-9\-]{8,64}$'
    return bool(re.match(pattern, client_id))


class ClientLayoutSaveRequest(BaseModel):
    layout: dict[str, dict[str, Any]]
    cols: str | int | None = None
    version: str | None = None
    name: str | None = None


def _get_client_dir(client_id: str) -> Path:
    """Get (and create if needed) the directory for a specific client layout slots."""
    if not _validate_client_id(client_id):
        raise ValueError("Invalid client ID")
    
    # layouts/{client_id}/
    root = _get_client_layouts_dir()
    client_dir = root / client_id
    client_dir.mkdir(parents=True, exist_ok=True)
    return client_dir

def _make_safe_filename(name: str) -> str:
    """Convert a layout name to a safe filename."""
    # Replace invalid chars with underscore
    safe = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in name)
    return safe.strip('_') or "layout"

@app.get("/api/layouts/client/{client_id}/list")
def list_client_layouts(client_id: str):
    """List all layout slots for a specific client."""
    try:
        client_dir = _get_client_dir(client_id)
        files = list(client_dir.glob("*.json"))
        results = []
        
        for f in files:
            # Skip special file
            if f.name == "last_active.json":
                continue
                
            try:
                content = json.loads(f.read_text(encoding="utf-8"))
                results.append({
                    "id": f.stem, # safe filename as ID
                    "name": content.get("name", f.stem),
                    "updated_at": content.get("updated_at", ""),
                })
            except Exception:
                continue
                
        # Sort by updated_at desc
        results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return results

    except Exception as exc:
        _logger.error("Client layout list failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/layouts/client/{client_id}/latest")
def get_client_latest_layout(client_id: str) -> dict[str, Any] | None:
    """Get the 'last active' layout for automatic restoration."""
    try:
        client_dir = _get_client_dir(client_id)
        active_path = client_dir / "last_active.json"
        
        if not active_path.exists():
            # 저장된 레이아웃이 없는 새 클라이언트는 정상 빈 상태로 응답한다.
            legacy_path = _get_client_layouts_dir() / f"{client_id}.json"
            if legacy_path.exists():
                return json.loads(legacy_path.read_text(encoding="utf-8"))
            return None
            
        data = json.loads(active_path.read_text(encoding="utf-8"))
        return data
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Client latest layout load failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/layouts/client/{client_id}/{slot_id}")
def get_client_layout_slot(client_id: str, slot_id: str):
    """Get a specific layout slot."""
    try:
        client_dir = _get_client_dir(client_id)
        # Security check: ensure slot_id is safe path component
        if not all(c.isalnum() or c in ('-', '_') for c in slot_id):
             raise HTTPException(status_code=400, detail="Invalid slot ID")
             
        file_path = client_dir / f"{slot_id}.json"
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Layout slot not found")
        
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return data
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Client layout slot load failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/layouts/client/{client_id}")
def save_client_layout(client_id: str, payload: ClientLayoutSaveRequest):
    """
    Save layout for a specific client.
    Updates 'last_active.json' AND creates a named slot if 'name' is provided.
    """
    try:
        client_dir = _get_client_dir(client_id)
        
        data = {
            "layout": payload.layout,
            "cols": str(payload.cols) if payload.cols else "60",
            "version": payload.version or "v2",
            "name": payload.name or "Client Layout",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "client_id": client_id,
        }
        
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        
        # 1. Always update last_active
        (client_dir / "last_active.json").write_text(json_data, encoding="utf-8")
        
        # 2. Save as named slot
        safe_name = _make_safe_filename(payload.name or "unnamed")
        slot_path = client_dir / f"{safe_name}.json"
        
        # Avoid overwriting if name collision? No, overwrite is expected for same name.
        slot_path.write_text(json_data, encoding="utf-8")
        
        _logger.info(f"[ClientLayout] Saved layout '{payload.name}' for client: {client_id}")
        
        return {"ok": True, "path": str(slot_path), "slot_id": safe_name}
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Client layout save failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/layouts/client/{client_id}/{slot_id}")
def delete_client_layout(client_id: str, slot_id: str):
    """Delete a specific layout slot."""
    try:
        client_dir = _get_client_dir(client_id)
        # Security check
        if not all(c.isalnum() or c in ('-', '_') for c in slot_id):
             raise HTTPException(status_code=400, detail="Invalid slot ID")
             
        file_path = client_dir / f"{slot_id}.json"
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Layout slot not found")
        
        file_path.unlink()
        _logger.info(f"[ClientLayout] Deleted slot '{slot_id}' for client: {client_id}")
        
        return {"ok": True, "slot_id": slot_id}
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Client layout delete failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/api/config/central-status")
def central_status():
    try:
        return config_sync_agent.get_status()
    except Exception as exc:
        _logger.error("Central status failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/config")
async def save_config(payload: ConfigUpdate):
    try:
        # 1. Update config object in memory and config.ini
        # PLC/SPOT/Logging
        if payload.extruder:
            if payload.extruder.ip: config.EXTRUDER_IP = payload.extruder.ip
            if payload.extruder.port: config.EXTRUDER_PORT = payload.extruder.port
        if payload.ls_plc:
            if payload.ls_plc.ip: config.LS_IP = payload.ls_plc.ip
            if payload.ls_plc.port: config.LS_PORT = payload.ls_plc.port
        if payload.spot:
            if payload.spot.ip: config.SPOT_IP = payload.spot.ip
            if payload.spot.refresh_interval: config.SPOT_REFRESH_INTERVAL = payload.spot.refresh_interval
            
        if payload.thresholds:
             # This part might involve more complex logic in update_config, 
             # but we follow the existing pattern if applicable.
             pass
             
        if payload.settings:
            if payload.settings.logpath: config.LOG_PATH = Path(payload.settings.logpath)
            if payload.settings.snapshotpath: config.SNAPSHOT_PATH = Path(payload.settings.snapshotpath)
            if payload.settings.autosave is not None: config.AUTO_SAVE = payload.settings.autosave
            
        if payload.logging:
            if payload.logging.rotation_enabled is not None: config.ROTATION_ENABLED = payload.logging.rotation_enabled
            if payload.logging.rotation_mode: config.ROTATION_MODE = payload.logging.rotation_mode
            if payload.logging.cycle_idle_time: config.CYCLE_IDLE_TIME = int(payload.logging.cycle_idle_time)
            
        if payload.system:
            if payload.system.interval_sec: config.INTERVAL_SEC = payload.system.interval_sec
            if payload.system.status_warn_ms: config.STATUS_WARN_MS = payload.system.status_warn_ms
            if payload.system.status_offline_ms: config.STATUS_OFFLINE_MS = payload.system.status_offline_ms
            
        mes_changed = False
        if payload.mes:
            if payload.mes.enabled is not None: 
                if config.MES_ENABLED != payload.mes.enabled:
                    config.MES_ENABLED = payload.mes.enabled
                    mes_changed = True
            if payload.mes.userid: 
                if config.MES_USER_ID != payload.mes.userid:
                    config.MES_USER_ID = payload.mes.userid
                    mes_changed = True
            if payload.mes.password: 
                if config.MES_PASSWORD != payload.mes.password:
                    config.MES_PASSWORD = payload.mes.password
                    mes_changed = True
            if payload.mes.starthour is not None:
                config.MES_START_HOUR = payload.mes.starthour
            if payload.mes.endhour is not None:
                config.MES_END_HOUR = payload.mes.endhour
            
        # 2. Persist to config.ini
        results = update_config(payload)
        
        # 3. Apply MES changes: restart or start/stop
        if mes_changed:
            if config.MES_ENABLED:
                await mes_scheduler.restart()
            else:
                await mes_scheduler.stop()
        
        return results
    except PermissionError as exc:
        _logger.warning("Config save permission error: %s", exc)
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Config save failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/config/sync")
def sync_central_config():
    try:
        return config_sync_agent.sync_now()
    except Exception as exc:
        _logger.error("Central sync failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/control/reconnect")
def reconnect():
    try:
        plc_service.stop()
        plc_service.start()
        return {"ok": True, "running": plc_service.running}
    except Exception as exc:
        _logger.error("Reconnect failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/control/test-connection")
def test_connection(payload: ConnectionTestPayload):
    try:
        results: dict[str, dict] = {}
        if payload.extruder is not None:
            results["extruder"] = _test_tcp(payload.extruder.ip, payload.extruder.port)
        if payload.ls_plc is not None:
            results["ls_plc"] = _test_tcp(payload.ls_plc.ip, payload.ls_plc.port)
        if payload.spot is not None:
            results["spot"] = _test_http(payload.spot.url)
        if not results:
            raise HTTPException(status_code=400, detail="No targets provided")
        return {"results": results}
    except HTTPException:
        raise
    except Exception as exc:
        _logger.error("Connection test failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/control/path-health")
def path_health(payload: PathHealthRequest):
    try:
        results: dict[str, dict] = {}
        for item in payload.paths:
            results[item.key] = _check_path(item.path)
        return {"results": results}
    except Exception as exc:
        _logger.error("Path health failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/control/path-create")
def path_create(payload: PathCreateRequest):
    try:
        path = Path(payload.path)
        path.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "message": "created"}
    except Exception as exc:
        _logger.error("Path create failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/control/folder-browse")
def folder_browse(payload: FolderBrowseRequest):
    """Open Windows folder browser dialog and return selected path."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Bring to front
        
        initial = payload.initial_dir if payload.initial_dir and Path(payload.initial_dir).exists() else None
        title = payload.title or "폴더 선택"
        
        selected = filedialog.askdirectory(
            parent=root,
            initialdir=initial,
            title=title
        )
        
        root.destroy()
        
        if selected:
            return {"ok": True, "path": selected}
        else:
            return {"ok": False, "path": None, "message": "cancelled"}
    except Exception as exc:
        _logger.error("Folder browse failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/control/snapshot")
def save_snapshot(payload: SnapshotRequest):
    try:
        snapshot_dir = Path(config.SNAPSHOT_PATH)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        data, ext = _decode_snapshot_payload(payload.image_base64)
        ext_value = (payload.format or ext or "png").lower().strip(".")
        if ext_value not in {"png", "jpg", "jpeg"}:
            ext_value = "png"
        base_name = (payload.name or "snapshot").strip()
        safe_name = "".join(ch for ch in base_name if ch.isalnum() or ch in {"-", "_"}).strip("_-")
        if not safe_name:
            safe_name = "snapshot"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{ts}.{ext_value}"
        file_path = snapshot_dir / filename
        file_path.write_bytes(data)
        return {"ok": True, "path": str(file_path), "filename": filename}
    except Exception as exc:
        _logger.error("Snapshot save failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/verify/compare")
def verify_compare(payload: VerificationCompareRequest):
    try:
        sample_count = max(int(payload.sample_count), 1)
        interval_sec = payload.interval_sec
        if interval_sec is None or interval_sec <= 0:
            interval_sec = config.INTERVAL_SEC
        return compare_with_reference(
            payload.reference_csv_path,
            sample_count,
            float(interval_sec),
            payload.tolerance_abs,
            payload.tolerance_pct,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        _logger.error("Verify compare failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/api/spot/config")
def spot_config():
    return {
        "image_url": config.SPOT_IMAGE_URL,
        "refresh_interval": config.SPOT_REFRESH_INTERVAL,
        "crosshair_x": config.SPOT_CROSSHAIR_X,
        "crosshair_y": config.SPOT_CROSSHAIR_Y,
        "crosshair_color": config.SPOT_CROSSHAIR_COLOR,
        "crosshair_thickness": config.SPOT_CROSSHAIR_THICKNESS,
        "crosshair_size": config.SPOT_CROSSHAIR_SIZE,
        "crosshair_gap": config.SPOT_CROSSHAIR_GAP,
        "widget_width": config.SPOT_WIDGET_WIDTH,
        "widget_height": config.SPOT_WIDGET_HEIGHT,
        "focus_step": config.SPOT_FOCUS_STEP,
        "focus_enabled": bool(config.SPOT_FOCUS_URL),
        "proxy": spot_control.get_image_proxy_diagnostics(),
    }

@app.post("/api/spot/focus")
def spot_focus(steps: int = 0):
    try:
        return spot_control.move_focus(steps)
    except spot_control.SpotFocusControlError as exc:
        if exc.upstream_status in {401, 403}:
            raise HTTPException(status_code=exc.upstream_status, detail=str(exc)) from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        if str(exc).strip() == _SPOT_FOCUS_CONFIG_ERROR:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _ceil_positive_seconds(value: float) -> int:
    seconds = int(value)
    if value > float(seconds):
        seconds += 1
    return max(1, seconds)


def _ceil_positive_milliseconds(value: float) -> int:
    milliseconds = int(value * 1000.0)
    if value * 1000.0 > float(milliseconds):
        milliseconds += 1
    return max(1, milliseconds)


def _spot_retry_headers_from_value(retry_after_sec: float | None) -> dict[str, str]:
    if (
        retry_after_sec is None
        or isinstance(retry_after_sec, bool)
        or not math.isfinite(retry_after_sec)
        or retry_after_sec <= 0.0
    ):
        return {}
    return {
        "Retry-After": str(_ceil_positive_seconds(retry_after_sec)),
        "X-Spot-Retry-After-Ms": str(_ceil_positive_milliseconds(retry_after_sec)),
    }


def _spot_retry_headers_from_diagnostics(diagnostics: dict[str, Any]) -> dict[str, str]:
    retry_after_sec = diagnostics.get("retry_after_sec")
    if isinstance(retry_after_sec, bool) or not isinstance(retry_after_sec, (float, int)):
        return {}
    return _spot_retry_headers_from_value(float(retry_after_sec))


def _is_spot_payload_rejection_headers(headers: dict[str, str] | None) -> bool:
    if headers is None:
        return False
    for header_name, header_value in headers.items():
        if header_name.lower() != "x-spot-payload-rejection":
            continue
        return str(header_value).strip() == "1"
    return False


def _is_spot_proxy_payload_rejection_response(
    path: str,
    status_code: int,
    headers: dict[str, str] | None,
) -> bool:
    if path != _SPOT_PROXY_IMAGE_PATH:
        return False
    if status_code != 502:
        return False
    return _is_spot_payload_rejection_headers(headers)


@app.get("/api/spot/proxy_image")
async def proxy_spot_image():
    """Proxy the SPOT camera image for remote clients (Async + Cached)."""
    try:
        data, meta = await spot_control.fetch_image_async()
        headers: dict[str, str] = {
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        captured_at = meta.get("captured_at") or 0.0
        age_sec = meta.get("age_sec")
        is_stale = str(meta.get("status") or "") == "stale"
        retry_after_sec = meta.get("retry_after_sec")
        if captured_at:
            headers["X-Spot-Image-At"] = str(int(captured_at * 1000))
        if age_sec is not None:
            headers["X-Spot-Image-Age"] = f"{age_sec:.3f}"
        if meta.get("max_stale_age_sec") is not None:
            headers["X-Spot-Max-Stale-Age"] = f"{float(meta['max_stale_age_sec']):.3f}"
        if meta.get("status"):
            headers["X-Spot-Image-Status"] = str(meta["status"])
        if meta.get("cache_status"):
            headers["X-Spot-Cache-Status"] = str(meta["cache_status"])
        if meta.get("proxy_state"):
            headers["X-Spot-Proxy-State"] = str(meta["proxy_state"])
        if meta.get("source"):
            headers["X-Spot-Image-Source"] = str(meta["source"])
        if meta.get("failure_count") is not None:
            headers["X-Spot-Failure-Count"] = str(int(meta["failure_count"]))
        if meta.get("last_error_code"):
            headers["X-Spot-Last-Error-Code"] = str(meta["last_error_code"])
        if not isinstance(retry_after_sec, bool) and isinstance(retry_after_sec, (float, int)):
            headers.update(_spot_retry_headers_from_value(float(retry_after_sec)))
        observability_service.record_spot_proxy_result(200, float(age_sec) if age_sec is not None else None, is_stale)
        return Response(content=data, media_type="image/jpeg", headers=headers)
    except spot_control.SpotImageConfigError as exc:
        diagnostics = spot_control.get_image_proxy_diagnostics()
        observability_service.record_error(
            "spot_proxy",
            "SPOT image proxy misconfigured",
            detail=str({
                "code": "config-missing",
                "message": str(exc),
                "diagnostics": diagnostics,
            }),
            path="/api/spot/proxy_image",
            level="warning",
        )
        raise HTTPException(
            status_code=404,
            detail={
                "code": "config-missing",
                "message": "SPOT 이미지 URL이 설정되지 않았습니다.",
                "diagnostics": diagnostics,
            },
            headers=_spot_retry_headers_from_diagnostics(diagnostics),
        ) from exc
    except spot_control.SpotImageFetchError as exc:
        diagnostics = spot_control.get_image_proxy_diagnostics()
        error_headers = _spot_retry_headers_from_diagnostics(diagnostics)
        if exc.code in _SPOT_PAYLOAD_REJECTION_CODES:
            error_headers["X-Spot-Payload-Rejection"] = "1"
        if exc.code not in _SPOT_PAYLOAD_REJECTION_CODES:
            observability_service.record_error(
                "spot_proxy",
                "SPOT image proxy upstream failure",
                detail=str({
                    "code": exc.code,
                    "message": str(exc),
                    "upstream_status": exc.upstream_status,
                    "image_url": exc.image_url,
                    "diagnostics": diagnostics,
                }),
                path="/api/spot/proxy_image",
            )
        raise HTTPException(
            status_code=502,
            detail={
                "code": exc.code,
                "message": "SPOT 이미지 상위 서버 요청에 실패했습니다.",
                "upstream_status": exc.upstream_status,
                "image_url": exc.image_url,
                "diagnostics": diagnostics,
            },
            headers=error_headers,
        ) from exc
    except Exception as exc:
        diagnostics = spot_control.get_image_proxy_diagnostics()
        observability_service.record_error(
            "spot_proxy",
            "SPOT image proxy unexpected failure",
            detail=str({
                "code": "unknown",
                "message": str(exc),
                "diagnostics": diagnostics,
            }),
            path="/api/spot/proxy_image",
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": "unknown",
                "message": "SPOT 이미지 프록시 처리 중 알 수 없는 오류가 발생했습니다.",
                "diagnostics": diagnostics,
            },
            headers=_spot_retry_headers_from_diagnostics(diagnostics),
        ) from exc


# --- Frontend Status Logging ---
class StatusLogRequest(BaseModel):
    previous: str
    current: str
    reason: Optional[str] = None


_status_log_lock = threading.Lock()


def _get_status_log_path() -> Path:
    """Get the path for status log file."""
    log_dir = _resolve_log_dir()
    return log_dir / "status.log"


@app.post("/api/log/status")
async def log_status_change(payload: StatusLogRequest):
    """Log frontend status badge changes (Running/Warning/Offline)."""
    try:
        log_path = _get_status_log_path()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        reason_str = f" reason='{payload.reason}'" if payload.reason else ""
        log_line = (
            f"[{timestamp}] STATUS_CHANGE {payload.previous} -> {payload.current}"
            f" session='{_app_session_id}' pid={os.getpid()} started_at='{_app_started_at_iso}'"
            f"{reason_str}\n"
        )
        
        with _status_log_lock:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(log_line)
        
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/control/shutdown")
def shutdown(payload: ShutdownRequest):
    def _shutdown() -> None:
        try:
            _logger.info("Shutdown requested: reason=%s %s", payload.reason, _lifecycle_log_fields())
        except Exception:
            pass
        try:
            plc_service.stop()
        except Exception:
            pass
        try:
            logger_service.stop()
        except Exception:
            pass
        try:
            comm_metrics_logger_service.stop()
        except Exception:
            pass
        try:
            config_sync_agent.stop()
        except Exception:
            pass
        try:
            config_watch_service.stop()
        except Exception:
            pass
        time.sleep(0.2)
        os._exit(0)

    threading.Thread(target=_shutdown, daemon=True).start()
    return {"ok": True}

# --- MES Data APIs ---
# (Moved to Api_MESSync.py)

# --- Static File Serving (Frontend) ---
@app.get("/assets/{asset_path:path}")
async def serve_frontend_asset(asset_path: str):
    frontend_status = get_frontend_static_status(
        frontend_dist,
        frontend_mode,
        frontend_source,
        frontend_source_origin,
        frontend_resolution_reason,
        frontend_resolution_candidate_specs,
    )
    assets_dir = frontend_dist / "assets"
    if not frontend_status["frontend_assets_exists"]:
        _logger.error(
            "Frontend assets directory unavailable",
            extra={
                **get_frontend_log_context(),
                "asset_path": asset_path,
            },
        )
        return build_frontend_error_response(503, "Frontend assets directory is unavailable.")

    asset_file = resolve_frontend_file(assets_dir, asset_path)
    if asset_file is None or not asset_file.exists() or not asset_file.is_file():
        _logger.warning(
            "Frontend asset not found",
            extra={
                **get_frontend_log_context(),
                "asset_path": asset_path,
            },
        )
        return build_frontend_error_response(404, "Frontend asset was not found.")

    return FileResponse(asset_file)


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    frontend_status = get_frontend_static_status(
        frontend_dist,
        frontend_mode,
        frontend_source,
        frontend_source_origin,
        frontend_resolution_reason,
        frontend_resolution_candidate_specs,
    )
    requested_file = resolve_frontend_file(frontend_dist, full_path)
    if requested_file is not None and requested_file.exists() and requested_file.is_file():
        return FileResponse(requested_file)

    nested_file = resolve_nested_frontend_file(frontend_dist, full_path)
    if nested_file is not None and nested_file.exists() and nested_file.is_file():
        return FileResponse(nested_file)

    if is_frontend_file_request(full_path):
        error_status = get_frontend_file_request_status(frontend_status, full_path)
        _logger.warning(
            "Frontend file request not found",
            extra={
                **get_frontend_log_context(),
                "request_path": full_path,
                "frontend_missing_assets": frontend_status["frontend_missing_assets"],
            },
        )
        return build_frontend_error_response(error_status, "Requested frontend file was not found.")

    if not frontend_status["frontend_static_ready"]:
        _logger.error(
            "Frontend bundle incomplete for SPA request",
            extra={
                **get_frontend_log_context(),
                "request_path": full_path,
                "frontend_missing_assets": frontend_status["frontend_missing_assets"],
            },
        )
        return build_frontend_error_response(503, "Frontend bundle is incomplete.")

    index_path = frontend_dist / "index.html"
    if frontend_status["frontend_index_exists"]:
        return FileResponse(index_path)

    _logger.error(
        "Frontend index unavailable for SPA request",
        extra={
            **get_frontend_log_context(),
            "request_path": full_path,
        },
    )
    return build_frontend_error_response(503, "Frontend index is unavailable.")


if __name__ == "backend.app" or __name__ == "app":
    # Ensure app is defined if imported
    pass

