import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .. import config


def _meta_path() -> Path:
    if config.CONFIG_PATH and config.CONFIG_PATH.parent:
        return config.CONFIG_PATH.parent / "config_meta.json"
    return Path(config.APP_DATA_DIR) / "config_meta.json"


def _default_meta() -> Dict[str, Any]:
    device_id = os.getenv("SFL_DEVICE_ID") or os.getenv("COMPUTERNAME") or "UNKNOWN"
    return {
        "device_id": device_id,
        "version": None,
        "last_sync": None,
        "source": "local",
        "override_enabled": False,
        "override_by": None,
        "override_at": None,
    }


def load_meta() -> Dict[str, Any]:
    path = _meta_path()
    defaults = _default_meta()
    if not path.exists():
        return defaults
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defaults
    for key, value in defaults.items():
        data.setdefault(key, value)
    return data


def save_meta(meta: Dict[str, Any]) -> None:
    path = _meta_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=True, indent=2), encoding="utf-8")


def record_local_update(meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    next_meta = meta if meta is not None else load_meta()
    now = datetime.now(timezone.utc)
    next_meta["version"] = now.strftime("%Y.%m.%d-%H%M%S")
    next_meta["last_sync"] = now.isoformat()
    next_meta["source"] = "local"
    save_meta(next_meta)
    return next_meta


def record_central_update(
    version: str,
    updated_at: str | None = None,
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    next_meta = meta if meta is not None else load_meta()
    next_meta["version"] = version
    next_meta["last_sync"] = updated_at or datetime.now(timezone.utc).isoformat()
    next_meta["source"] = "central"
    save_meta(next_meta)
    return next_meta


def set_override_enabled(enabled: bool, actor: str | None = None) -> Dict[str, Any]:
    meta = load_meta()
    meta["override_enabled"] = bool(enabled)
    meta["override_by"] = actor
    meta["override_at"] = datetime.now(timezone.utc).isoformat()
    save_meta(meta)
    return meta
