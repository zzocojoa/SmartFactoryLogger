import sys
import os
from pathlib import Path

# Important: Add the directory containing the 'backend' folder to sys.path
# This ensures that 'from backend.services...' works in all environments.
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from contextlib import asynccontextmanager
import atexit
from datetime import datetime, timezone
import base64
import json
import logging
from logging.handlers import RotatingFileHandler
import socket
import subprocess
import tempfile
import threading
import traceback
import time
import uvicorn
from urllib.request import Request, urlopen
from typing import Any

# Import Service Layer using absolute imports
from backend.services.plc_service import plc_service
from backend.services.logger_service import logger_service
from backend.services.comm_metrics_logger import comm_metrics_logger_service
from backend.services.observability_service import observability_service
from backend.services.layout_service import (
    delete_layout_slot,
    get_active_layout,
    get_layout_meta,
    list_layouts,
    restore_layout_backup,
    restore_layout_slot,
    save_layout_slot
)
from backend.services.config_service import (
    apply_pending_config,
    clear_pending_config,
    get_config_snapshot,
    set_override_enabled,
    update_config,
    restore_defaults,
    restore_backup,
)
from backend.services.config_sync import config_sync_agent
from backend.services.config_watch import config_watch_service
from backend.models.config_model import ConfigUpdate, OverrideToggle, SettingsConfig
from backend.services import spot_control
from backend.models.data_model import FactoryData
from backend.services.verification_service import compare_with_reference
from backend import config

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
_stats_lock = threading.Lock()
_stats_total_requests = 0
_stats_total_latency_ms = 0.0
_stats_last_latency_ms: int | None = None
_stats_last_path: str | None = None
_stats_last_status: int | None = None
_stats_last_time: float | None = None
_stats_error_count = 0
_last_observability_export_path: Path | None = None

_INVALID_PATH_CHARS = set('<>:"|?*')
_NETWORK_WARN_MS = 200


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
    global _log_dir
    if _log_dir:
        return _log_dir
    base_dir = config.APP_DATA_DIR
    candidates = [
        base_dir / "logs",
        Path(tempfile.gettempdir()) / "SmartFactoryLogger" / "logs",
        Path.cwd() / "logs",
    ]
    for candidate in candidates:
        if _ensure_dir(candidate):
            _log_dir = candidate
            return candidate
    _log_dir = Path.cwd()
    return _log_dir


def _observability_state_path() -> Path:
    return _resolve_log_dir() / "observability_last_export.json"


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


def _setup_logging() -> tuple[logging.Logger, logging.Logger]:
    log_dir = _resolve_log_dir()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    logger = logging.getLogger("SmartFactoryLoggerV2")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        system_log = log_dir / "system.log"
        file_handler = RotatingFileHandler(
            system_log,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    crash_logger = logging.getLogger("SmartFactoryLoggerV2.Crash")
    if not crash_logger.handlers:
        crash_logger.setLevel(logging.ERROR)
        crash_log = log_dir / "crash.log"
        crash_handler = RotatingFileHandler(
            crash_log,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        crash_handler.setFormatter(formatter)
        crash_logger.addHandler(crash_handler)

    return logger, crash_logger


_logger, _crash_logger = _setup_logging()


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

# Lifecycle Manager (Startup/Shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not acquire_single_instance_lock():
        raise RuntimeError("Instance already running")
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
    
    # Log local IPs for debugging remote connectivity
    try:
        hostname = socket.gethostname()
        local_ips = socket.gethostbyname_ex(hostname)[2]
        _logger.info(f"[Main] Backend started. Accessible at: {', '.join([f'http://{ip}:{config.BACKEND_PORT}' for ip in local_ips])}")
    except Exception as exc:
        _logger.warning(f"[Main] Failed to log local IPs: {exc}")

    try:
        yield
    finally:
        # Shutdown
        print("[Main] Stopping Comm Metrics Logger...")
        comm_metrics_logger_service.stop()
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
    version="2.1.0",
    lifespan=lifespan
)

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
    try:
        # Log incoming request for external visibility
        _logger.info(f"[Access] INCOMING: {client_host} -> {request.method} {request.url.path}")
        
        response = await call_next(request)
        status_code = response.status_code
        if status_code >= 500:
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
        # Log completion
        _logger.info(f"[Access] DONE: {client_host} -> {request.url.path} (Status: {status_code}, {elapsed_ms:.1f}ms)")
        
        try:
            observability_service.record_request(request.url.path, status_code, elapsed_ms)
        except Exception:
            pass
        with _stats_lock:
            _stats_total_requests += 1
            _stats_total_latency_ms += elapsed_ms
            _stats_last_latency_ms = int(elapsed_ms)
            _stats_last_path = request.url.path
            _stats_last_status = status_code
            _stats_last_time = time.time()
            if status_code >= 400:
                _stats_error_count += 1

@app.get("/")
def read_root():
    # UX Improvement: Serve Dashboard directly at root
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        return FileResponse(frontend_dist / "index.html")
    return {
        "system": "Smart Factory Logger V2",
        "status": "Online",
        "backend": "FastAPI with Service Layer (Frontend missing)"
    }

@app.get("/api/data", response_model=FactoryData)
def get_data():
    """Get latest snapshot from PLC Service (Memory)"""
    return plc_service.get_latest_data()

@app.get("/health")
def health():
    return plc_service.get_health()

@app.get("/stats")
def stats():
    data = observability_service.get_stats()
    data["uptime_sec"] = int(time.time() - _app_start_time)
    return data

@app.get("/api/observability/errors")
def list_observability_errors(limit: int = 50):
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
def export_observability(payload: ObservabilityExportRequest):
    global _last_observability_export_path
    try:
        health_snapshot = plc_service.get_health()
        stats_snapshot = observability_service.get_stats()
        errors_snapshot = observability_service.get_errors(200) if payload.include_errors else []
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
        path = log_dir / filename
        path.write_text(json.dumps(snapshot, ensure_ascii=True, indent=2), encoding="utf-8")
        _last_observability_export_path = path
        _persist_observability_export_state(path)
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
def get_config():
    try:
        return get_config_snapshot()
    except Exception as exc:
        _logger.error("Config load failed: %s", exc)
        raise HTTPException(status_code=500, detail="Config load failed") from exc

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

@app.get("/api/config/central-status")
def central_status():
    try:
        return config_sync_agent.get_status()
    except Exception as exc:
        _logger.error("Central status failed: %s", exc)
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
        "focus_step": config.SPOT_ACTUATOR_STEP,
        "focus_enabled": bool(config.SPOT_ACTUATOR_URL),
    }

@app.post("/api/spot/focus")
def spot_focus(steps: int = 0):
    try:
        return spot_control.move_focus(steps)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/spot/proxy_image")
def proxy_spot_image():
    """Proxy the SPOT camera image for remote clients."""
    try:
        if not config.SPOT_IMAGE_URL:
            raise HTTPException(status_code=404, detail="SPOT URL not configured")
            
        with urlopen(config.SPOT_IMAGE_URL, timeout=config.SPOT_TIMEOUT or 2.0) as conn:
            data = conn.read()
            return Response(content=data, media_type="image/jpeg")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch upstream image: {exc}")

@app.post("/api/control/shutdown")
def shutdown(payload: ShutdownRequest):
    def _shutdown() -> None:
        try:
            _logger.info("Shutdown requested: %s", payload.reason)
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

# --- Static File Serving (Frontend) ---
# Check common locations for frontend dist
if getattr(sys, 'frozen', False):
    # If running from backend_server.exe in resources/backend/
    # resources/backend/backend_server.exe -> parent is backend/ -> parent is resources/
    base_dir = Path(sys.executable).parent.parent
else:
    # Development mode
    base_dir = Path(__file__).parent.parent

frontend_dist = base_dir / "frontend" / "dist"

if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")


if __name__ == "backend.app" or __name__ == "app":
    # Ensure app is defined if imported
    pass

