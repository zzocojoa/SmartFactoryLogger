from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .. import config

_LAYOUT_FILE = "layout.json"
_LAYOUT_BACKUP_FILE = "layout.backup.json"
_LAYOUT_TMP_FILE = "layout.tmp"
_LAYOUT_ENCODINGS = ("utf-8-sig", "utf-8")
_MAX_SLOTS = 3


def _base_dir() -> Path:
    if config.CONFIG_PATH:
        return config.CONFIG_PATH.parent
    return config.APP_DATA_DIR


def _layout_path() -> Path:
    return _base_dir() / _LAYOUT_FILE


def _backup_path() -> Path:
    return _base_dir() / _LAYOUT_BACKUP_FILE


def _tmp_path() -> Path:
    return _base_dir() / _LAYOUT_TMP_FILE


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_text(path: Path) -> str:
    last_error: Optional[Exception] = None
    for enc in _LAYOUT_ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return path.read_text(encoding="utf-8")


def _default_data() -> dict[str, Any]:
    return {
        "version": "v2",
        "updated_at": _iso_now(),
        "active_id": None,
        "slots": [],
    }


def _normalize_slot(slot: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "id": str(slot.get("id") or ""),
        "name": str(slot.get("name") or "").strip() or "레이아웃",
        "layout": slot.get("layout") if isinstance(slot.get("layout"), dict) else {},
        "cols": slot.get("cols"),
        "updated_at": slot.get("updated_at") or _iso_now(),
    }
    return normalized


def _normalize_data(data: dict[str, Any]) -> dict[str, Any]:
    if "slots" in data and isinstance(data.get("slots"), list):
        slots = [_normalize_slot(item) for item in data.get("slots", [])]
        active_id = data.get("active_id") or (slots[0]["id"] if slots else None)
        return {
            "version": data.get("version") or "v2",
            "updated_at": data.get("updated_at") or _iso_now(),
            "active_id": active_id,
            "slots": slots[:_MAX_SLOTS],
        }
    if "layout" in data and isinstance(data.get("layout"), dict):
        slot = _normalize_slot(
            {
                "id": "slot1",
                "name": "기본 레이아웃",
                "layout": data.get("layout"),
                "cols": data.get("cols"),
                "updated_at": data.get("updated_at") or _iso_now(),
            }
        )
        return {
            "version": data.get("version") or "v2",
            "updated_at": data.get("updated_at") or _iso_now(),
            "active_id": slot["id"],
            "slots": [slot],
        }
    return _default_data()


def _load_data() -> dict[str, Any]:
    path = _layout_path()
    if not path.exists():
        return _default_data()
    raw = _read_text(path)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Layout file is not an object")
    return _normalize_data(data)


def _write_data(data: dict[str, Any]) -> None:
    base_dir = _base_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    path = _layout_path()
    backup = _backup_path()
    if path.exists():
        try:
            shutil.copy2(path, backup)
        except Exception:
            pass
    payload = {
        "version": data.get("version") or "v2",
        "updated_at": _iso_now(),
        "active_id": data.get("active_id"),
        "slots": data.get("slots", [])[:_MAX_SLOTS],
    }
    tmp_path = _tmp_path()
    tmp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def list_layouts() -> dict[str, Any]:
    data = _load_data()
    slots = [
        {
            "id": slot.get("id"),
            "name": slot.get("name"),
            "updated_at": slot.get("updated_at"),
            "cols": slot.get("cols"),
        }
        for slot in data.get("slots", [])
    ]
    return {
        "active_id": data.get("active_id"),
        "slots": slots,
    }


def get_active_layout() -> Optional[dict[str, Any]]:
    data = _load_data()
    active_id = data.get("active_id")
    slots = data.get("slots", [])
    if not slots:
        return None
    active_slot = None
    if active_id:
        active_slot = next((slot for slot in slots if slot.get("id") == active_id), None)
    if active_slot is None:
        active_slot = slots[0]
    return {
        "version": data.get("version") or "v2",
        "updated_at": active_slot.get("updated_at") or data.get("updated_at"),
        "layout": active_slot.get("layout", {}),
        "cols": active_slot.get("cols"),
    }


def save_layout_slot(
    name: str,
    layout: dict[str, Any],
    cols: str | int | None,
    version: Optional[str],
    slot_id: Optional[str] = None,
) -> dict[str, Any]:
    if not isinstance(layout, dict):
        raise ValueError("layout must be an object")
    name = (name or "").strip()
    if not name:
        raise ValueError("name is required")
    data = _load_data()
    slots = data.get("slots", [])
    target = None
    if slot_id:
        target = next((slot for slot in slots if slot.get("id") == slot_id), None)
    if target is None:
        target = next((slot for slot in slots if slot.get("name") == name), None)
    if target is None:
        if len(slots) >= _MAX_SLOTS:
            raise ValueError("Max layout slots reached")
        slot_id = slot_id or f"slot{len(slots) + 1}"
        target = {
            "id": slot_id,
            "name": name,
            "layout": layout,
            "cols": str(cols) if cols is not None else None,
            "updated_at": _iso_now(),
        }
        slots.append(target)
    else:
        target["name"] = name
        target["layout"] = layout
        target["cols"] = str(cols) if cols is not None else target.get("cols")
        target["updated_at"] = _iso_now()
    data["version"] = version or data.get("version") or "v2"
    data["active_id"] = target.get("id")
    data["slots"] = slots
    _write_data(data)
    return {
        "ok": True,
        "active_id": data.get("active_id"),
        "slot": {
            "id": target.get("id"),
            "name": target.get("name"),
            "updated_at": target.get("updated_at"),
            "cols": target.get("cols"),
        },
    }


def restore_layout_slot(slot_id: str) -> dict[str, Any]:
    if not slot_id:
        raise ValueError("slot_id is required")
    data = _load_data()
    slots = data.get("slots", [])
    if not any(slot for slot in slots if slot.get("id") == slot_id):
        raise FileNotFoundError("Layout slot not found")
    data["active_id"] = slot_id
    _write_data(data)
    return {"ok": True, "active_id": slot_id}


def restore_layout_backup() -> dict[str, Any]:
    path = _layout_path()
    backup = _backup_path()
    if not backup.exists():
        raise FileNotFoundError("Layout backup not found")
    shutil.copy2(backup, path)
    return {
        "ok": True,
        "path": str(path),
        "backup_path": str(backup),
    }


def delete_layout_slot(slot_id: str) -> dict[str, Any]:
    if not slot_id:
        raise ValueError("slot_id is required")
    data = _load_data()
    slots = data.get("slots", [])
    remaining = [slot for slot in slots if slot.get("id") != slot_id]
    if len(remaining) == len(slots):
        raise FileNotFoundError("Layout slot not found")
    data["slots"] = remaining
    if data.get("active_id") == slot_id:
        data["active_id"] = remaining[0].get("id") if remaining else None
    _write_data(data)
    return {
        "ok": True,
        "active_id": data.get("active_id"),
        "slot_count": len(remaining),
    }


def get_layout_meta() -> dict[str, Any]:
    path = _layout_path()
    backup = _backup_path()
    meta: dict[str, Any] = {
        "path": str(path),
        "backup_path": str(backup),
        "exists": path.exists(),
        "backup_exists": backup.exists(),
    }
    if path.exists():
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            meta["updated_at"] = mtime.astimezone().isoformat(timespec="seconds")
        except Exception:
            pass
        try:
            data = _load_data()
            meta["version"] = data.get("version")
            meta["active_id"] = data.get("active_id")
            slots = data.get("slots", [])
            meta["slot_count"] = len(slots)
            active_slot = None
            if data.get("active_id"):
                active_slot = next((slot for slot in slots if slot.get("id") == data.get("active_id")), None)
            if active_slot is None and slots:
                active_slot = slots[0]
            if active_slot is not None:
                meta["cols"] = active_slot.get("cols")
        except Exception:
            pass
    return meta
