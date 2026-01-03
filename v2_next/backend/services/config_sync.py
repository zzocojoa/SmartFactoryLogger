from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .. import config
from ..models.config_model import ConfigUpdate
from . import config_meta
from .config_service import update_config


def _request(
    method: str,
    url: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 5.0,
) -> tuple[int, bytes]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, method=method.upper())
    for key, value in headers.items():
        request.add_header(key, value)
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()
    except URLError as exc:
        raise RuntimeError(str(exc)) from exc


def _cache_path() -> str:
    if config.CONFIG_PATH and config.CONFIG_PATH.parent:
        return str(config.CONFIG_PATH.parent / "config_cache.json")
    return str(config.APP_DATA_DIR / "config_cache.json")


class ConfigSyncAgent:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._backoff = 60
        self._max_backoff = 600
        self._sync_lock = threading.Lock()
        self._last_result: Dict[str, Any] = {
            "status": "IDLE",
            "message": "",
            "version": None,
            "at": None,
        }

    def start(self) -> None:
        if self._running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="ConfigSync", daemon=True)
        self._thread.start()
        self._running = True

    def stop(self) -> None:
        if not self._running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._running = False

    def _loop(self) -> None:
        base_interval = int(os.getenv("SFL_SYNC_INTERVAL", "60"))
        while not self._stop_event.is_set():
            try:
                with self._sync_lock:
                    result = self._sync_once()
                self._record_result(result)
                self._backoff = base_interval
            except Exception:
                self._record_result(
                    {"status": "FAILED", "message": "Central sync failed", "version": None}
                )
                self._backoff = min(self._max_backoff, max(self._backoff * 2, base_interval))
            self._stop_event.wait(self._backoff)

    def _record_result(self, result: Dict[str, Any]) -> None:
        self._last_result = {
            "status": result.get("status", "UNKNOWN"),
            "message": result.get("message", ""),
            "version": result.get("version"),
            "at": time.time(),
        }

    def get_status(self) -> Dict[str, Any]:
        base_url = os.getenv("SFL_CONFIG_SERVER")
        device_id = os.getenv("SFL_DEVICE_ID") or os.getenv("COMPUTERNAME")
        api_key = os.getenv("SFL_CONFIG_API_KEY")
        configured = bool(base_url and device_id and api_key)
        meta = config_meta.load_meta()
        return {
            "configured": configured,
            "running": self._running,
            "server": base_url,
            "device_id": device_id,
            "backoff_sec": self._backoff,
            "last_result": self._last_result,
            "meta": meta,
        }

    def sync_now(self) -> Dict[str, Any]:
        with self._sync_lock:
            try:
                result = self._sync_once()
                self._record_result(result)
                return self._last_result
            except Exception as exc:
                result = {"status": "FAILED", "message": str(exc), "version": None}
                self._record_result(result)
                return self._last_result

    def _sync_once(self) -> Dict[str, Any]:
        base_url = os.getenv("SFL_CONFIG_SERVER")
        device_id = os.getenv("SFL_DEVICE_ID") or os.getenv("COMPUTERNAME")
        api_key = os.getenv("SFL_CONFIG_API_KEY")
        if not base_url or not device_id or not api_key:
            return {"status": "DISABLED", "message": "Central config not configured", "version": None}

        meta = config_meta.load_meta()
        headers = {"Authorization": f"Bearer {api_key}"}
        if meta.get("version"):
            headers["If-None-Match"] = str(meta.get("version"))

        query = urlencode({"device_id": device_id})
        status, body = _request("GET", f"{base_url}/api/config/latest?{query}", headers)
        if status == 304:
            return {"status": "NO_CHANGE", "message": "No changes", "version": meta.get("version")}
        if status >= 400:
            raise RuntimeError(f"Config fetch failed: {status}")

        payload: Dict[str, Any] = json.loads(body.decode("utf-8"))
        new_version = payload.get("version")
        config_blob = payload.get("config")
        force = bool(payload.get("force", False))
        if not new_version or not config_blob:
            return {"status": "FAILED", "message": "Invalid payload", "version": None}

        # Cache latest payload for offline inspection
        cache_path = _cache_path()
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(config_blob, handle, ensure_ascii=True, indent=2)

        try:
            update_payload = ConfigUpdate(**config_blob)
        except Exception as exc:
            self._send_ack(
                base_url,
                headers,
                device_id,
                new_version,
                "FAILED",
                f"Invalid payload: {exc}",
            )
            return {"status": "FAILED", "message": f"Invalid payload: {exc}", "version": new_version}

        try:
            update_config(
                update_payload,
                source="central",
                override_allowed=force,
                meta_version=new_version,
                meta_updated_at=payload.get("updated_at"),
            )
        except PermissionError:
            self._send_ack(
                base_url,
                headers,
                device_id,
                new_version,
                "SKIPPED",
                "Local override enabled",
            )
            return {"status": "SKIPPED", "message": "Local override enabled", "version": new_version}
        except Exception as exc:
            self._send_ack(
                base_url,
                headers,
                device_id,
                new_version,
                "FAILED",
                str(exc),
            )
            return {"status": "FAILED", "message": str(exc), "version": new_version}

        self._send_ack(
            base_url,
            headers,
            device_id,
            new_version,
            "APPLIED",
            "Applied from central",
        )
        return {"status": "APPLIED", "message": "Applied from central", "version": new_version}

    def _send_ack(
        self,
        base_url: str,
        headers: Dict[str, str],
        device_id: str,
        version: str,
        status: str,
        message: str,
    ) -> None:
        ack_payload = {
            "device_id": device_id,
            "version": version,
            "status": status,
            "applied_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "message": message,
        }
        _request("POST", f"{base_url}/api/config/ack", headers, payload=ack_payload)


config_sync_agent = ConfigSyncAgent()
