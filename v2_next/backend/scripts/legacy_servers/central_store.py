from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import json
import os
import sqlite3
import threading


DEFAULT_POLICY = {
    "approval_required_for_operator": True,
    "auto_approve_admin": True,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).lower() in {"1", "true", "yes", "y", "on"}


class CentralStoreBase:
    def get_policy(self) -> dict[str, Any]:
        raise NotImplementedError

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def list_devices(self) -> list[str]:
        raise NotImplementedError

    def get_latest(self, device_id: str) -> Optional[dict[str, Any]]:
        raise NotImplementedError

    def list_history(self, device_id: str, limit: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    def find_config(self, device_id: str, version: str) -> Optional[dict[str, Any]]:
        raise NotImplementedError

    def save_update(
        self,
        device_id: str,
        *,
        author: str,
        force: bool,
        requires_restart: bool,
        config: dict[str, Any],
        source: str,
        request_id: Optional[str] = None,
        rolled_back_from: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def add_ack(self, device_id: str, ack: dict[str, Any]) -> None:
        raise NotImplementedError

    def create_request(
        self,
        device_id: str,
        *,
        author: str,
        reason: Optional[str],
        force: bool,
        requires_restart: bool,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def list_requests(
        self,
        *,
        device_id: Optional[str],
        status: Optional[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def approve_request(
        self,
        request_id: str,
        *,
        approver: str,
        comment: Optional[str],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def reject_request(
        self,
        request_id: str,
        *,
        rejector: str,
        comment: Optional[str],
    ) -> dict[str, Any]:
        raise NotImplementedError


class JsonCentralStore(CentralStoreBase):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {
                "meta": {"last_date": "", "seq": 0, "request_seq": 0},
                "policy": DEFAULT_POLICY.copy(),
                "devices": {},
            }
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        raw.setdefault("meta", {"last_date": "", "seq": 0, "request_seq": 0})
        raw.setdefault("policy", DEFAULT_POLICY.copy())
        raw.setdefault("devices", {})
        return raw

    def _write(self, store: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(store, ensure_ascii=True, indent=2), encoding="utf-8")

    def _next_version(self, store: dict[str, Any]) -> str:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y.%m.%d")
        meta = store.get("meta") or {}
        seq = int(meta.get("seq", 0))
        if meta.get("last_date") == date_str:
            seq += 1
        else:
            seq = 1
        meta["last_date"] = date_str
        meta["seq"] = seq
        store["meta"] = meta
        return f"{date_str}-{seq:04d}"

    def _next_request_id(self, store: dict[str, Any]) -> str:
        meta = store.get("meta") or {}
        seq = int(meta.get("request_seq", 0)) + 1
        meta["request_seq"] = seq
        store["meta"] = meta
        return f"REQ-{seq:05d}"

    def _ensure_device(self, store: dict[str, Any], device_id: str) -> dict[str, Any]:
        devices = store.setdefault("devices", {})
        device = devices.setdefault(device_id, {"history": [], "acks": [], "requests": []})
        device.setdefault("history", [])
        device.setdefault("acks", [])
        device.setdefault("requests", [])
        return device

    def get_policy(self) -> dict[str, Any]:
        with self._lock:
            store = self._read()
            policy = store.get("policy") or DEFAULT_POLICY.copy()
            store["policy"] = policy
            self._write(store)
            return dict(policy)

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            store = self._read()
            policy = store.get("policy") or DEFAULT_POLICY.copy()
            for key, value in updates.items():
                if value is None:
                    continue
                policy[key] = _bool(value, policy.get(key, False))
            store["policy"] = policy
            self._write(store)
            return dict(policy)

    def list_devices(self) -> list[str]:
        with self._lock:
            store = self._read()
            return sorted(store.get("devices", {}).keys())

    def get_latest(self, device_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            store = self._read()
            device = (store.get("devices") or {}).get(device_id)
            if not device:
                return None
            return device.get("latest")

    def list_history(self, device_id: str, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            store = self._read()
            device = (store.get("devices") or {}).get(device_id)
            if not device:
                return []
            history = device.get("history", [])
            items = list(reversed(history))[: max(limit, 1)]
            return items

    def find_config(self, device_id: str, version: str) -> Optional[dict[str, Any]]:
        with self._lock:
            store = self._read()
            device = (store.get("devices") or {}).get(device_id)
            if not device:
                return None
            for item in device.get("history", []):
                if item.get("version") == version:
                    return item
            return None

    def save_update(
        self,
        device_id: str,
        *,
        author: str,
        force: bool,
        requires_restart: bool,
        config: dict[str, Any],
        source: str,
        request_id: Optional[str] = None,
        rolled_back_from: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        with self._lock:
            store = self._read()
            device = self._ensure_device(store, device_id)
            version = self._next_version(store)
            updated_at = _utc_now()
            entry = {
                "version": version,
                "updated_at": updated_at,
                "author": author,
                "force": bool(force),
                "requires_restart": bool(requires_restart),
                "config": config,
                "source": source,
                "request_id": request_id,
                "rolled_back_from": rolled_back_from,
                "reason": reason,
            }
            device["latest"] = entry
            device.setdefault("history", []).append(entry)
            self._write(store)
            return entry

    def add_ack(self, device_id: str, ack: dict[str, Any]) -> None:
        with self._lock:
            store = self._read()
            device = self._ensure_device(store, device_id)
            device.setdefault("acks", []).append(ack)
            device["last_ack"] = ack
            self._write(store)

    def create_request(
        self,
        device_id: str,
        *,
        author: str,
        reason: Optional[str],
        force: bool,
        requires_restart: bool,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            store = self._read()
            device = self._ensure_device(store, device_id)
            request_id = self._next_request_id(store)
            entry = {
                "id": request_id,
                "device_id": device_id,
                "author": author,
                "created_at": _utc_now(),
                "status": "PENDING",
                "reason": reason,
                "force": bool(force),
                "requires_restart": bool(requires_restart),
                "config": config,
            }
            device.setdefault("requests", []).append(entry)
            self._write(store)
            return entry

    def list_requests(
        self,
        *,
        device_id: Optional[str],
        status: Optional[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        with self._lock:
            store = self._read()
            items: list[dict[str, Any]] = []
            for dev_id, device in (store.get("devices") or {}).items():
                if device_id and dev_id != device_id:
                    continue
                for entry in device.get("requests", []):
                    if status and entry.get("status") != status:
                        continue
                    items.append(entry)
            return list(reversed(items))[: max(limit, 1)]

    def approve_request(
        self,
        request_id: str,
        *,
        approver: str,
        comment: Optional[str],
    ) -> dict[str, Any]:
        with self._lock:
            store = self._read()
            target_device = None
            target_request = None
            for device_id, device in (store.get("devices") or {}).items():
                for entry in device.get("requests", []):
                    if entry.get("id") == request_id:
                        target_device = device_id
                        target_request = entry
                        break
                if target_request:
                    break
            if not target_device or not target_request:
                raise KeyError("request not found")
            if target_request.get("status") != "PENDING":
                raise ValueError("request not pending")

            device = self._ensure_device(store, target_device)
            version = self._next_version(store)
            updated_at = _utc_now()
            config_entry = {
                "version": version,
                "updated_at": updated_at,
                "author": target_request.get("author"),
                "force": bool(target_request.get("force", False)),
                "requires_restart": bool(target_request.get("requires_restart", False)),
                "config": target_request.get("config", {}),
                "source": "request",
                "request_id": target_request.get("id"),
            }
            device["latest"] = config_entry
            device.setdefault("history", []).append(config_entry)
            target_request["status"] = "APPROVED"
            target_request["approved_at"] = updated_at
            target_request["approved_by"] = approver
            target_request["comment"] = comment
            target_request["version"] = version
            self._write(store)
            return {"device_id": target_device, "version": version, "request": target_request}

    def reject_request(
        self,
        request_id: str,
        *,
        rejector: str,
        comment: Optional[str],
    ) -> dict[str, Any]:
        with self._lock:
            store = self._read()
            target_device = None
            target_request = None
            for device_id, device in (store.get("devices") or {}).items():
                for entry in device.get("requests", []):
                    if entry.get("id") == request_id:
                        target_device = device_id
                        target_request = entry
                        break
                if target_request:
                    break
            if not target_device or not target_request:
                raise KeyError("request not found")
            if target_request.get("status") != "PENDING":
                raise ValueError("request not pending")
            target_request["status"] = "REJECTED"
            target_request["rejected_at"] = _utc_now()
            target_request["rejected_by"] = rejector
            target_request["comment"] = comment
            self._write(store)
            return {"device_id": target_device, "request": target_request}


class SqliteCentralStore(CentralStoreBase):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE TABLE IF NOT EXISTS policy (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    approval_required_for_operator INTEGER NOT NULL,
                    auto_approve_admin INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    author TEXT,
                    force INTEGER NOT NULL,
                    requires_restart INTEGER NOT NULL,
                    config_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    request_id TEXT,
                    rolled_back_from TEXT,
                    reason TEXT
                );
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    author TEXT,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    force INTEGER NOT NULL,
                    requires_restart INTEGER NOT NULL,
                    config_json TEXT NOT NULL,
                    approved_at TEXT,
                    approved_by TEXT,
                    rejected_at TEXT,
                    rejected_by TEXT,
                    comment TEXT,
                    version TEXT
                );
                CREATE TABLE IF NOT EXISTS acks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    applied_at TEXT NOT NULL,
                    message TEXT,
                    received_at TEXT NOT NULL
                );
                """
            )

        with self._conn:
            row = self._conn.execute("SELECT 1 FROM policy WHERE id = 1").fetchone()
            if not row:
                self._conn.execute(
                    "INSERT INTO policy (id, approval_required_for_operator, auto_approve_admin) VALUES (1, ?, ?)",
                    (
                        1 if DEFAULT_POLICY["approval_required_for_operator"] else 0,
                        1 if DEFAULT_POLICY["auto_approve_admin"] else 0,
                    ),
                )

    def _get_meta(self, key: str, default: str) -> str:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        return str(row["value"])

    def _set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def _next_version(self) -> str:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y.%m.%d")
        last_date = self._get_meta("last_date", "")
        seq = int(self._get_meta("seq", "0"))
        if last_date == date_str:
            seq += 1
        else:
            seq = 1
        self._set_meta("last_date", date_str)
        self._set_meta("seq", str(seq))
        return f"{date_str}-{seq:04d}"

    def _next_request_id(self) -> str:
        seq = int(self._get_meta("request_seq", "0")) + 1
        self._set_meta("request_seq", str(seq))
        return f"REQ-{seq:05d}"

    def _row_to_entry(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "version": row["version"],
            "updated_at": row["updated_at"],
            "author": row["author"],
            "force": bool(row["force"]),
            "requires_restart": bool(row["requires_restart"]),
            "config": json.loads(row["config_json"]),
            "source": row["source"],
            "request_id": row["request_id"],
            "rolled_back_from": row["rolled_back_from"],
            "reason": row["reason"],
        }

    def _row_to_request(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "device_id": row["device_id"],
            "author": row["author"],
            "created_at": row["created_at"],
            "status": row["status"],
            "reason": row["reason"],
            "force": bool(row["force"]),
            "requires_restart": bool(row["requires_restart"]),
            "config": json.loads(row["config_json"]),
            "approved_at": row["approved_at"],
            "approved_by": row["approved_by"],
            "rejected_at": row["rejected_at"],
            "rejected_by": row["rejected_by"],
            "comment": row["comment"],
            "version": row["version"],
        }

    def get_policy(self) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT approval_required_for_operator, auto_approve_admin FROM policy WHERE id = 1"
            ).fetchone()
            if not row:
                return DEFAULT_POLICY.copy()
            return {
                "approval_required_for_operator": bool(row["approval_required_for_operator"]),
                "auto_approve_admin": bool(row["auto_approve_admin"]),
            }

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            policy = self.get_policy()
            if "approval_required_for_operator" in updates and updates["approval_required_for_operator"] is not None:
                policy["approval_required_for_operator"] = _bool(
                    updates["approval_required_for_operator"], policy["approval_required_for_operator"]
                )
            if "auto_approve_admin" in updates and updates["auto_approve_admin"] is not None:
                policy["auto_approve_admin"] = _bool(
                    updates["auto_approve_admin"], policy["auto_approve_admin"]
                )
            with self._conn:
                self._conn.execute(
                    "UPDATE policy SET approval_required_for_operator = ?, auto_approve_admin = ? WHERE id = 1",
                    (
                        1 if policy["approval_required_for_operator"] else 0,
                        1 if policy["auto_approve_admin"] else 0,
                    ),
                )
            return dict(policy)

    def list_devices(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT device_id FROM configs UNION SELECT DISTINCT device_id FROM requests"
            ).fetchall()
            return sorted({row["device_id"] for row in rows if row["device_id"]})

    def get_latest(self, device_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM configs WHERE device_id = ? ORDER BY id DESC LIMIT 1",
                (device_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_entry(row)

    def list_history(self, device_id: str, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM configs WHERE device_id = ? ORDER BY id DESC LIMIT ?",
                (device_id, max(limit, 1)),
            ).fetchall()
            return [self._row_to_entry(row) for row in rows]

    def find_config(self, device_id: str, version: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM configs WHERE device_id = ? AND version = ? LIMIT 1",
                (device_id, version),
            ).fetchone()
            if not row:
                return None
            return self._row_to_entry(row)

    def save_update(
        self,
        device_id: str,
        *,
        author: str,
        force: bool,
        requires_restart: bool,
        config: dict[str, Any],
        source: str,
        request_id: Optional[str] = None,
        rolled_back_from: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        with self._lock:
            version = self._next_version()
            updated_at = _utc_now()
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO configs (
                        device_id, version, updated_at, author, force, requires_restart,
                        config_json, source, request_id, rolled_back_from, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device_id,
                        version,
                        updated_at,
                        author,
                        1 if force else 0,
                        1 if requires_restart else 0,
                        json.dumps(config, ensure_ascii=True),
                        source,
                        request_id,
                        rolled_back_from,
                        reason,
                    ),
                )
            return {
                "version": version,
                "updated_at": updated_at,
                "author": author,
                "force": bool(force),
                "requires_restart": bool(requires_restart),
                "config": config,
                "source": source,
                "request_id": request_id,
                "rolled_back_from": rolled_back_from,
                "reason": reason,
            }

    def add_ack(self, device_id: str, ack: dict[str, Any]) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO acks (device_id, version, status, applied_at, message, received_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device_id,
                        ack.get("version"),
                        ack.get("status"),
                        ack.get("applied_at"),
                        ack.get("message"),
                        ack.get("received_at"),
                    ),
                )

    def create_request(
        self,
        device_id: str,
        *,
        author: str,
        reason: Optional[str],
        force: bool,
        requires_restart: bool,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            request_id = self._next_request_id()
            created_at = _utc_now()
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO requests (
                        id, device_id, author, created_at, status, reason, force,
                        requires_restart, config_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        device_id,
                        author,
                        created_at,
                        "PENDING",
                        reason,
                        1 if force else 0,
                        1 if requires_restart else 0,
                        json.dumps(config, ensure_ascii=True),
                    ),
                )
            return {
                "id": request_id,
                "device_id": device_id,
                "author": author,
                "created_at": created_at,
                "status": "PENDING",
                "reason": reason,
                "force": bool(force),
                "requires_restart": bool(requires_restart),
                "config": config,
            }

    def list_requests(
        self,
        *,
        device_id: Optional[str],
        status: Optional[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        with self._lock:
            query = "SELECT * FROM requests"
            params: list[Any] = []
            clauses = []
            if device_id:
                clauses.append("device_id = ?")
                params.append(device_id)
            if status:
                clauses.append("status = ?")
                params.append(status)
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY rowid DESC LIMIT ?"
            params.append(max(limit, 1))
            rows = self._conn.execute(query, params).fetchall()
            return [self._row_to_request(row) for row in rows]

    def approve_request(
        self,
        request_id: str,
        *,
        approver: str,
        comment: Optional[str],
    ) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
            if not row:
                raise KeyError("request not found")
            if row["status"] != "PENDING":
                raise ValueError("request not pending")
            request_entry = self._row_to_request(row)
            version = self._next_version()
            updated_at = _utc_now()
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO configs (
                        device_id, version, updated_at, author, force, requires_restart,
                        config_json, source, request_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_entry["device_id"],
                        version,
                        updated_at,
                        request_entry["author"],
                        1 if request_entry["force"] else 0,
                        1 if request_entry["requires_restart"] else 0,
                        json.dumps(request_entry["config"], ensure_ascii=True),
                        "request",
                        request_entry["id"],
                    ),
                )
                self._conn.execute(
                    """
                    UPDATE requests
                    SET status = ?, approved_at = ?, approved_by = ?, comment = ?, version = ?
                    WHERE id = ?
                    """,
                    ("APPROVED", updated_at, approver, comment, version, request_id),
                )
            request_entry["status"] = "APPROVED"
            request_entry["approved_at"] = updated_at
            request_entry["approved_by"] = approver
            request_entry["comment"] = comment
            request_entry["version"] = version
            return {"device_id": request_entry["device_id"], "version": version, "request": request_entry}

    def reject_request(
        self,
        request_id: str,
        *,
        rejector: str,
        comment: Optional[str],
    ) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
            if not row:
                raise KeyError("request not found")
            if row["status"] != "PENDING":
                raise ValueError("request not pending")
            updated_at = _utc_now()
            with self._conn:
                self._conn.execute(
                    """
                    UPDATE requests
                    SET status = ?, rejected_at = ?, rejected_by = ?, comment = ?
                    WHERE id = ?
                    """,
                    ("REJECTED", updated_at, rejector, comment, request_id),
                )
            request_entry = self._row_to_request(row)
            request_entry["status"] = "REJECTED"
            request_entry["rejected_at"] = updated_at
            request_entry["rejected_by"] = rejector
            request_entry["comment"] = comment
            return {"device_id": request_entry["device_id"], "request": request_entry}


_STORE_INSTANCE: Optional[CentralStoreBase] = None


def get_store() -> CentralStoreBase:
    global _STORE_INSTANCE
    if _STORE_INSTANCE:
        return _STORE_INSTANCE
    mode = (os.getenv("SFL_CENTRAL_STORE_MODE") or "json").lower().strip()
    store_dir = os.getenv("SFL_CENTRAL_STORE_DIR")
    if store_dir:
        base_dir = Path(store_dir)
    else:
        base_dir = Path(os.getenv("APPDATA") or ".") / "SmartFactoryLogger"
    if mode == "sqlite":
        path = Path(os.getenv("SFL_CENTRAL_DB_PATH") or (base_dir / "central_config_store.db"))
        _STORE_INSTANCE = SqliteCentralStore(path)
    else:
        path = Path(os.getenv("SFL_CENTRAL_STORE_PATH") or (base_dir / "central_config_store.json"))
        _STORE_INSTANCE = JsonCentralStore(path)
    return _STORE_INSTANCE
