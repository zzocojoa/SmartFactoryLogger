import configparser
import json
from datetime import datetime, timezone
import os
import shutil
from pathlib import Path
from typing import Optional

from .. import config
from ..models.config_model import ConfigUpdate
from .config_manager import config_manager
from . import config_meta


def _config_path() -> Path:
    if config.CONFIG_PATH:
        return config.CONFIG_PATH
    return Path(config.APP_DATA_DIR) / "config.ini"


def _load_parser(path: Path) -> tuple[configparser.ConfigParser, Optional[str]]:
    parser = configparser.ConfigParser()
    parser.optionxform = str
    if not path.exists():
        return parser, None
    enc_candidates = [
        "utf-8-sig",
        "utf-8",
        config.CONFIG_ENCODING,
        "cp949",
        "euc-kr",
    ]
    for enc in enc_candidates:
        if not enc:
            continue
        try:
            text = path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
        parser.read_string(text)
        return parser, enc
    return parser, None


def _get(parser: configparser.ConfigParser, section: str, option: str, fallback: str) -> str:
    if parser.has_option(section, option):
        return parser.get(section, option)
    return fallback


def _get_text(parser: configparser.ConfigParser, section: str, option: str) -> str:
    if parser.has_option(section, option):
        return parser.get(section, option).strip()
    return ""


def _get_int(parser: configparser.ConfigParser, section: str, option: str, fallback: int) -> int:
    raw = _get(parser, section, option, "")
    try:
        return int(raw)
    except Exception:
        return fallback


def _get_float(parser: configparser.ConfigParser, section: str, option: str, fallback: float) -> float:
    raw = _get(parser, section, option, "")
    try:
        return float(raw)
    except Exception:
        return fallback


def _get_bool(parser: configparser.ConfigParser, section: str, option: str, fallback: bool) -> bool:
    raw = _get(parser, section, option, "")
    if raw == "":
        return fallback
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


_THRESHOLD_KEYS = [
    "speed",
    "press",
    "spot",
    "temp_f",
    "temp_b",
    "billet",
    "billet_temp",
    "at_temp",
    "at_pre",
    "count",
    "endpos",
]


def get_config_snapshot() -> dict:
    path = _config_path()
    parser, encoding = _load_parser(path)
    meta = config_meta.load_meta()
    try:
        if path.exists():
            config_writable = os.access(path, os.W_OK)
        else:
            config_writable = os.access(path.parent, os.W_OK)
    except Exception:
        config_writable = False

    extruder = {
        "ip": _get(parser, "EXTRUDER", "ip", config.DEFAULT_EXTRUDER_IP),
        "port": _get_int(parser, "EXTRUDER", "port", config.DEFAULT_EXTRUDER_PORT),
    }
    ls_plc = {
        "ip": _get(parser, "LS_PLC", "ip", config.DEFAULT_LS_IP),
        "port": _get_int(parser, "LS_PLC", "port", config.DEFAULT_LS_PORT),
    }
    spot_ip = _get(parser, "SPOT", "ip", config.DEFAULT_SPOT_IP)
    spot = {
        "ip": spot_ip,
        "refresh_interval": _get_float(parser, "SPOT", "refreshinterval", config.DEFAULT_SPOT_REFRESH_INTERVAL),
    }
    settings = {
        "logpath": _get(parser, "SETTINGS", "logpath", config.DEFAULT_LOG_PATH),
        "snapshotpath": _get(parser, "SETTINGS", "snapshotpath", config.DEFAULT_SNAPSHOT_PATH),
        "autosave": _get_bool(parser, "SETTINGS", "autosave", config.DEFAULT_AUTO_SAVE),
        "password_set": bool(_get(parser, "SETTINGS", "password", "")),
    }
    logging_cfg = {
        "rotation_enabled": _get_bool(parser, "LOGGING", "rotationenabled", config.DEFAULT_ROTATION_ENABLED),
        "rotation_mode": _get(parser, "LOGGING", "rotationmode", config.DEFAULT_ROTATION_MODE),
        "cycle_idle_time": _get_int(parser, "LOGGING", "cycleidletime", config.DEFAULT_CYCLE_IDLE_TIME),
        "cycle_threshold_press": _get_float(
            parser, "LOGGING", "cyclethresholdpress", config.DEFAULT_CYCLE_THRESHOLD_PRESS
        ),
    }
    thresholds_value = {key: _get_text(parser, "THRESHOLDS_VALUE", key) for key in _THRESHOLD_KEYS}
    thresholds_enable = {key: _get_bool(parser, "THRESHOLDS_ENABLE", key, False) for key in _THRESHOLD_KEYS}
    thresholds_enable["master_on"] = _get_bool(parser, "THRESHOLDS_ENABLE", "master_on", False)

    pending_info = None
    pending_path = _pending_path(path)
    if pending_path.exists():
        try:
            pending_raw = json.loads(pending_path.read_text(encoding="utf-8"))
            pending_info = {
                "path": str(pending_path),
                "created_at": pending_raw.get("created_at"),
                "source": pending_raw.get("source"),
                "reason": pending_raw.get("reason"),
            }
        except Exception:
            pending_info = {"path": str(pending_path)}

    return {
        "config_path": str(path),
        "encoding": encoding,
        "meta": meta,
        "config_writable": config_writable,
        "apply": config_manager.get_apply_result(),
        "pending": pending_info,
        "values": {
            "extruder": extruder,
            "ls_plc": ls_plc,
            "spot": spot,
            "settings": settings,
            "logging": logging_cfg,
            "thresholds": {
                "values": thresholds_value,
                "enable": thresholds_enable,
            },
        },
        "restart_required": config_manager.get_restart_required(),
    }


def _require_local_override() -> None:
    if os.getenv("SFL_ALLOW_LOCAL_CONFIG") == "1":
        return
    meta = config_meta.load_meta()
    if meta.get("override_enabled"):
        return
    raise PermissionError("Local override is disabled")


def set_override_enabled(enabled: bool, password: Optional[str], actor: Optional[str]) -> dict:
    path = _config_path()
    parser, _ = _load_parser(path)
    stored_password = _get(parser, "SETTINGS", "password", "")
    if stored_password and stored_password != (password or ""):
        raise PermissionError("Invalid password")
    meta = config_meta.set_override_enabled(enabled, actor)
    return {
        "ok": True,
        "meta": meta,
    }


def _ensure_section(parser: configparser.ConfigParser, section: str) -> None:
    if not parser.has_section(section):
        parser.add_section(section)


def _is_writable(path: Path) -> bool:
    try:
        if path.exists():
            return os.access(path, os.W_OK)
        return os.access(path.parent, os.W_OK)
    except Exception:
        return False


def _pending_path(path: Path) -> Path:
    candidate = path.with_suffix(".pending.json")
    try:
        if os.access(candidate.parent, os.W_OK):
            return candidate
    except Exception:
        pass
    return Path(config.APP_DATA_DIR) / "config.pending.json"


def _build_pending_payload(
    payload: ConfigUpdate,
    source: str,
    reason: str,
    encoding: Optional[str],
    path: Path,
) -> dict:
    data = payload.dict(exclude_none=True)
    settings = data.get("settings")
    if isinstance(settings, dict) and "password" in settings:
        settings["password"] = "***"
    return {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "reason": reason,
        "config_path": str(path),
        "encoding": encoding,
        "payload": data,
    }


def _write_pending(path: Path, payload: ConfigUpdate, source: str, reason: str, encoding: Optional[str]) -> Path:
    pending_path = _pending_path(path)
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_payload = _build_pending_payload(payload, source, reason, encoding, path)
    pending_path.write_text(json.dumps(pending_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return pending_path


def _clear_pending(path: Path) -> None:
    pending_path = _pending_path(path)
    try:
        if pending_path.exists():
            pending_path.unlink()
    except Exception:
        pass


def _load_pending(path: Path) -> Optional[dict]:
    pending_path = _pending_path(path)
    if not pending_path.exists():
        return None
    try:
        return json.loads(pending_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def apply_pending_config() -> dict:
    path = _config_path()
    pending = _load_pending(path)
    if not pending:
        raise FileNotFoundError("Pending config not found")
    payload_data = pending.get("payload") or {}
    settings = payload_data.get("settings")
    if isinstance(settings, dict) and settings.get("password") == "***":
        settings.pop("password", None)
    payload = ConfigUpdate(**payload_data)
    source = pending.get("source") or "local"
    return update_config(payload, source=source, override_allowed=source != "local")


def clear_pending_config() -> dict:
    path = _config_path()
    pending_path = _pending_path(path)
    if not pending_path.exists():
        raise FileNotFoundError("Pending config not found")
    _clear_pending(path)
    return {"ok": True, "path": str(pending_path)}


def restore_defaults() -> dict:
    _require_local_override()
    path = _config_path()
    if not _is_writable(path):
        raise PermissionError("Config file is read-only")
    threshold_values = {key: "" for key in _THRESHOLD_KEYS}
    threshold_enable = {key: False for key in _THRESHOLD_KEYS}
    threshold_enable["master_on"] = False
    payload = ConfigUpdate(
        extruder={"ip": config.DEFAULT_EXTRUDER_IP, "port": config.DEFAULT_EXTRUDER_PORT},
        ls_plc={"ip": config.DEFAULT_LS_IP, "port": config.DEFAULT_LS_PORT},
        spot={"ip": config.DEFAULT_SPOT_IP, "refresh_interval": config.DEFAULT_SPOT_REFRESH_INTERVAL},
        settings={
            "logpath": config.DEFAULT_LOG_PATH,
            "snapshotpath": config.DEFAULT_SNAPSHOT_PATH,
            "autosave": config.DEFAULT_AUTO_SAVE,
        },
        logging={
            "rotation_enabled": config.DEFAULT_ROTATION_ENABLED,
            "rotation_mode": config.DEFAULT_ROTATION_MODE,
            "cycle_idle_time": config.DEFAULT_CYCLE_IDLE_TIME,
            "cycle_threshold_press": config.DEFAULT_CYCLE_THRESHOLD_PRESS,
        },
        thresholds={
            "values": threshold_values,
            "enable": threshold_enable,
        },
    )
    return update_config(payload, source="local")


def restore_backup() -> dict:
    _require_local_override()
    path = _config_path()
    if not _is_writable(path):
        raise PermissionError("Config file is read-only")
    backup_path = path.with_suffix(".bak")
    if not backup_path.exists():
        raise FileNotFoundError("Config backup not found")
    shutil.copy2(backup_path, path)
    _clear_pending(path)
    _, encoding = _load_parser(path)
    meta = config_meta.record_local_update()
    changes = config_manager.reload()
    apply_result = config_manager.apply_changes(changes)
    return {
        "ok": True,
        "config_path": str(path),
        "encoding": encoding,
        "restart_required": bool(apply_result.get("pending")),
        "meta": meta,
        "changes": changes,
        "apply": apply_result,
    }


def update_config(
    payload: ConfigUpdate,
    source: str = "local",
    override_allowed: bool = False,
    meta_version: Optional[str] = None,
    meta_updated_at: Optional[str] = None,
) -> dict:
    if source == "local":
        _require_local_override()
    elif source == "central":
        meta = config_meta.load_meta()
        if meta.get("override_enabled") and not override_allowed:
            raise PermissionError("Local override is enabled")
    path = _config_path()
    if not _is_writable(path):
        reason = "Config file is read-only"
        try:
            pending_path = _write_pending(path, payload, source, reason, config.CONFIG_ENCODING)
            config._config_log("WARNING", f"Config save blocked: {reason}. Pending={pending_path}")
        except Exception:
            config._config_log("ERROR", f"Config save blocked and pending write failed: {reason}")
        raise PermissionError("Config file is read-only")
    parser, encoding = _load_parser(path)
    _ensure_section(parser, "EXTRUDER")
    _ensure_section(parser, "LS_PLC")
    _ensure_section(parser, "SPOT")
    _ensure_section(parser, "SETTINGS")
    _ensure_section(parser, "LOGGING")
    _ensure_section(parser, "THRESHOLDS_VALUE")
    _ensure_section(parser, "THRESHOLDS_ENABLE")

    old_spot_ip = _get(parser, "SPOT", "ip", config.DEFAULT_SPOT_IP)
    old_image_url = _get(parser, "SPOT", "imageurl", "")
    old_focus_url = _get(parser, "SPOT", "focusurl", "")

    if payload.extruder:
        if payload.extruder.ip:
            parser.set("EXTRUDER", "ip", payload.extruder.ip)
        if payload.extruder.port is not None:
            parser.set("EXTRUDER", "port", str(payload.extruder.port))

    if payload.ls_plc:
        if payload.ls_plc.ip:
            parser.set("LS_PLC", "ip", payload.ls_plc.ip)
        if payload.ls_plc.port is not None:
            parser.set("LS_PLC", "port", str(payload.ls_plc.port))

    if payload.spot:
        if payload.spot.ip:
            parser.set("SPOT", "ip", payload.spot.ip)
            if not old_image_url or old_spot_ip in old_image_url:
                parser.set("SPOT", "imageurl", f"http://{payload.spot.ip}/image.jpg")
            if not old_focus_url or old_spot_ip in old_focus_url:
                parser.set("SPOT", "focusurl", f"http://{payload.spot.ip}/control?p=focus")
        if payload.spot.refresh_interval is not None:
            parser.set("SPOT", "refreshinterval", str(payload.spot.refresh_interval))

    if payload.settings:
        if payload.settings.logpath is not None:
            parser.set("SETTINGS", "logpath", payload.settings.logpath)
        if payload.settings.snapshotpath is not None:
            parser.set("SETTINGS", "snapshotpath", payload.settings.snapshotpath)
        if payload.settings.autosave is not None:
            parser.set("SETTINGS", "autosave", str(payload.settings.autosave))
        if payload.settings.password:
            parser.set("SETTINGS", "password", payload.settings.password)

    if payload.logging:
        if payload.logging.rotation_enabled is not None:
            parser.set("LOGGING", "rotationenabled", str(payload.logging.rotation_enabled))
        if payload.logging.rotation_mode:
            parser.set("LOGGING", "rotationmode", payload.logging.rotation_mode.upper())
        if payload.logging.cycle_idle_time is not None:
            parser.set("LOGGING", "cycleidletime", str(payload.logging.cycle_idle_time))
        if payload.logging.cycle_threshold_press is not None:
            parser.set("LOGGING", "cyclethresholdpress", str(payload.logging.cycle_threshold_press))

    if payload.thresholds:
        if payload.thresholds.values:
            for key in _THRESHOLD_KEYS:
                value = getattr(payload.thresholds.values, key, None)
                if value is not None:
                    parser.set("THRESHOLDS_VALUE", key, str(value))
        if payload.thresholds.enable:
            master_on = payload.thresholds.enable.master_on
            if master_on is not None:
                parser.set("THRESHOLDS_ENABLE", "master_on", str(master_on))
            for key in _THRESHOLD_KEYS:
                enabled = getattr(payload.thresholds.enable, key, None)
                if enabled is not None:
                    parser.set("THRESHOLDS_ENABLE", key, str(enabled))

    path.parent.mkdir(parents=True, exist_ok=True)
    write_encoding = "utf-8-sig"
    try:
        if path.exists():
            backup_path = path.with_suffix(".bak")
            try:
                shutil.copy2(path, backup_path)
            except Exception:
                pass
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text("", encoding=write_encoding)
        with tmp_path.open("w", encoding=write_encoding) as handle:
            parser.write(handle)
        tmp_path.replace(path)
        _clear_pending(path)
    except Exception as exc:
        reason = str(exc)
        try:
            pending_path = _write_pending(path, payload, source, reason, write_encoding)
            config._config_log("ERROR", f"Config save failed, pending stored at {pending_path}")
        except Exception:
            config._config_log("ERROR", "Config save failed and pending write failed")
        raise

    if source == "central":
        existing = config_meta.load_meta()
        version = meta_version or existing.get("version") or datetime.now().strftime("%Y.%m.%d-%H%M%S")
        meta = config_meta.record_central_update(version, meta_updated_at, existing)
    else:
        meta = config_meta.record_local_update()
    changes = config_manager.reload()
    apply_result = config_manager.apply_changes(changes)
    return {
        "ok": True,
        "config_path": str(path),
        "encoding": write_encoding,
        "restart_required": bool(apply_result.get("pending")),
        "meta": meta,
        "changes": changes,
        "apply": apply_result,
    }
