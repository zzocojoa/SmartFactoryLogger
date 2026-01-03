from __future__ import annotations

import configparser
from copy import deepcopy
from datetime import datetime
import os
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional, Tuple

from .. import config
from .logger_service import logger_service

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


def _get(parser: configparser.ConfigParser, section: str, option: str, fallback: Optional[str]) -> Optional[str]:
    if parser.has_option(section, option):
        return parser.get(section, option)
    return fallback


def _get_text(parser: configparser.ConfigParser, section: str, option: str) -> str:
    if parser.has_option(section, option):
        return parser.get(section, option).strip()
    return ""


def _get_int(parser: configparser.ConfigParser, section: str, option: str, fallback: int) -> int:
    val = _get(parser, section, option, None)
    try:
        return int(val) if val is not None else fallback
    except Exception:
        return fallback


def _get_float(parser: configparser.ConfigParser, section: str, option: str, fallback: float) -> float:
    val = _get(parser, section, option, None)
    try:
        return float(val) if val is not None else fallback
    except Exception:
        return fallback


def _get_bool(parser: configparser.ConfigParser, section: str, option: str, fallback: bool) -> bool:
    raw = _get(parser, section, option, None)
    if raw is None:
        return fallback
    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    return fallback


def _env_int(name: str, fallback: int) -> int:
    val = os.getenv(name)
    if val is None:
        return fallback
    try:
        return int(val)
    except ValueError:
        return fallback


def _env_float(name: str, fallback: float) -> float:
    val = os.getenv(name)
    if val is None:
        return fallback
    try:
        return float(val)
    except ValueError:
        return fallback


def _load_ls_targets(parser: configparser.ConfigParser) -> list[tuple[str, str]]:
    if parser.has_section("LS_PLC_TARGETS"):
        targets: list[tuple[str, str]] = []
        for addr, key in parser.items("LS_PLC_TARGETS"):
            addr_norm = addr.strip()
            if not addr_norm.startswith("%"):
                addr_norm = "%" + addr_norm
            addr_norm = addr_norm.upper()
            targets.append((addr_norm, key.strip()))
        if targets:
            return targets
    return list(config.DEFAULT_LS_TARGETS)


def _flatten(values: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    flattened: Dict[str, Any] = {}
    for key, value in values.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flattened.update(_flatten(value, path))
        else:
            flattened[path] = value
    return flattened


def _diff_flat(prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    changes: Dict[str, Dict[str, Any]] = {}
    keys = set(prev.keys()) | set(curr.keys())
    for key in sorted(keys):
        old = prev.get(key)
        new = curr.get(key)
        if old != new:
            changes[key] = {"old": old, "new": new}
    return changes


class ConfigManager:
    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshot: Dict[str, Any] = {}
        self._flat: Dict[str, Any] = {}
        self._pending_keys: set[str] = set()
        self._last_apply: Dict[str, list[str]] = {"applied": [], "pending": []}
        self.reload()

    def _build_values(self, parser: configparser.ConfigParser) -> Dict[str, Any]:
        extruder_ip = os.getenv("EXTRUDER_IP", _get(parser, "EXTRUDER", "ip", config.DEFAULT_EXTRUDER_IP) or "")
        extruder_port = _get_int(parser, "EXTRUDER", "port", config.DEFAULT_EXTRUDER_PORT)
        extruder_port = _env_int("EXTRUDER_PORT", extruder_port)

        ls_ip = os.getenv("LS_IP", _get(parser, "LS_PLC", "ip", config.DEFAULT_LS_IP) or "")
        ls_port = _get_int(parser, "LS_PLC", "port", config.DEFAULT_LS_PORT)
        ls_port = _env_int("LS_PORT", ls_port)

        spot_ip = os.getenv("SPOT_IP", _get(parser, "SPOT", "ip", config.DEFAULT_SPOT_IP) or "")
        spot_refresh = _get_float(parser, "SPOT", "refreshinterval", config.DEFAULT_SPOT_REFRESH_INTERVAL)
        spot_refresh = _env_float("SPOT_REFRESH_INTERVAL", spot_refresh)
        if spot_refresh <= 0:
            spot_refresh = config.DEFAULT_SPOT_REFRESH_INTERVAL
        spot_image_url = os.getenv(
            "SPOT_IMAGE_URL",
            _get(parser, "SPOT", "imageurl", f"http://{spot_ip}/image.jpg") or f"http://{spot_ip}/image.jpg",
        )
        spot_focus_url = os.getenv(
            "SPOT_FOCUS_URL",
            _get(parser, "SPOT", "focusurl", f"http://{spot_ip}/control?p=focus")
            or f"http://{spot_ip}/control?p=focus",
        )
        spot_url = os.getenv("SPOT_URL", f"http://{spot_ip}/output?p=temperature")

        spot_crosshair_x = _env_float(
            "SPOT_CROSSHAIR_X",
            _get_float(parser, "SPOT", "crosshairx", config.DEFAULT_SPOT_CROSSHAIR_X),
        )
        spot_crosshair_y = _env_float(
            "SPOT_CROSSHAIR_Y",
            _get_float(parser, "SPOT", "crosshairy", config.DEFAULT_SPOT_CROSSHAIR_Y),
        )
        spot_crosshair_color = os.getenv(
            "SPOT_CROSSHAIR_COLOR",
            _get(parser, "SPOT", "crosshaircolor", config.DEFAULT_SPOT_CROSSHAIR_COLOR)
            or config.DEFAULT_SPOT_CROSSHAIR_COLOR,
        )
        spot_crosshair_thickness = _env_int(
            "SPOT_CROSSHAIR_THICKNESS",
            _get_int(parser, "SPOT", "crosshairthickness", config.DEFAULT_SPOT_CROSSHAIR_THICKNESS),
        )
        spot_crosshair_size = _env_int(
            "SPOT_CROSSHAIR_SIZE",
            _get_int(parser, "SPOT", "crosshairsize", config.DEFAULT_SPOT_CROSSHAIR_SIZE),
        )
        spot_crosshair_gap = _env_int(
            "SPOT_CROSSHAIR_GAP",
            _get_int(parser, "SPOT", "crosshairgap", config.DEFAULT_SPOT_CROSSHAIR_GAP),
        )
        spot_focus_step = _env_int(
            "SPOT_FOCUS_STEP",
            _get_int(parser, "SPOT", "focusstep", config.DEFAULT_SPOT_FOCUS_STEP),
        )
        spot_actuator_ip = os.getenv("SPOT_ACTUATOR_IP", _get(parser, "SPOT", "actuatorip", "") or "")
        if not spot_actuator_ip:
            spot_actuator_ip = spot_ip
        spot_actuator_step = _env_int(
            "SPOT_ACTUATOR_STEP",
            _get_int(parser, "SPOT", "actuatorstep", config.DEFAULT_SPOT_ACTUATOR_STEP),
        )
        spot_actuator_url = os.getenv("SPOT_ACTUATOR_URL", f"http://{spot_actuator_ip}/scan.cgi")
        spot_widget_width = _env_int(
            "SPOT_WIDGET_WIDTH",
            _get_int(parser, "SPOT", "widgetwidth", config.DEFAULT_SPOT_WIDGET_WIDTH),
        )
        spot_widget_height = _env_int(
            "SPOT_WIDGET_HEIGHT",
            _get_int(parser, "SPOT", "widgetheight", config.DEFAULT_SPOT_WIDGET_HEIGHT),
        )

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
            "csv_header": _get(parser, "HEADERS", "csv", config.DEFAULT_CSV_HEADER) or config.DEFAULT_CSV_HEADER,
        }
        thresholds_value = {key: _get_text(parser, "THRESHOLDS_VALUE", key) for key in _THRESHOLD_KEYS}
        thresholds_enable = {key: _get_bool(parser, "THRESHOLDS_ENABLE", key, False) for key in _THRESHOLD_KEYS}
        thresholds_enable["master_on"] = _get_bool(parser, "THRESHOLDS_ENABLE", "master_on", False)

        return {
            "system": {
                "intervalsec": float(config.INTERVAL_SEC),
            },
            "extruder": {"ip": extruder_ip, "port": extruder_port},
            "ls_plc": {"ip": ls_ip, "port": ls_port, "targets": _load_ls_targets(parser)},
            "spot": {
                "ip": spot_ip,
                "url": spot_url,
                "image_url": spot_image_url,
                "refresh_interval": spot_refresh,
                "crosshair_x": spot_crosshair_x,
                "crosshair_y": spot_crosshair_y,
                "crosshair_color": spot_crosshair_color,
                "crosshair_thickness": spot_crosshair_thickness,
                "crosshair_size": spot_crosshair_size,
                "crosshair_gap": spot_crosshair_gap,
                "focus_url": spot_focus_url,
                "focus_step": spot_focus_step,
                "actuator_ip": spot_actuator_ip,
                "actuator_step": spot_actuator_step,
                "actuator_url": spot_actuator_url,
                "widget_width": spot_widget_width,
                "widget_height": spot_widget_height,
            },
            "settings": settings,
            "logging": logging_cfg,
            "thresholds": {
                "values": thresholds_value,
                "enable": thresholds_enable,
            },
        }

    def reload(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            path = _config_path()
            parser, encoding = _load_parser(path)
            values = self._build_values(parser)
            snapshot = {
                "config_path": str(path),
                "encoding": encoding,
                "values": values,
                "loaded_at": datetime.now().isoformat(timespec="seconds"),
            }
            flat = _flatten(values)
            changes = _diff_flat(self._flat, flat)
            self._snapshot = snapshot
            self._flat = flat
            return changes

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._snapshot)

    def apply_changes(self, changes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        applied: list[str] = []
        pending: list[str] = []
        values = self._snapshot.get("values", {})
        settings = values.get("settings", {})
        logging_cfg = values.get("logging", {})
        system_cfg = values.get("system", {})

        log_keys = {
            "settings.logpath",
            "settings.autosave",
            "logging.rotation_enabled",
            "logging.rotation_mode",
            "logging.cycle_idle_time",
            "logging.cycle_threshold_press",
            "logging.csv_header",
        }
        security_keys = {"settings.password_set"}
        snapshot_keys = {"settings.snapshotpath"}
        system_keys = {"system.intervalsec"}
        spot_keys = {
            "spot.ip",
            "spot.url",
            "spot.image_url",
            "spot.refresh_interval",
            "spot.crosshair_x",
            "spot.crosshair_y",
            "spot.crosshair_color",
            "spot.crosshair_thickness",
            "spot.crosshair_size",
            "spot.crosshair_gap",
            "spot.focus_url",
            "spot.focus_step",
            "spot.actuator_ip",
            "spot.actuator_step",
            "spot.actuator_url",
            "spot.widget_width",
            "spot.widget_height",
        }
        plc_keys = {
            "extruder.ip",
            "extruder.port",
            "ls_plc.ip",
            "ls_plc.port",
            "ls_plc.targets",
        }
        threshold_keys = {"thresholds.enable.master_on"}
        for key in _THRESHOLD_KEYS:
            threshold_keys.add(f"thresholds.values.{key}")
            threshold_keys.add(f"thresholds.enable.{key}")

        log_changed = [key for key in changes if key in log_keys]
        security_changed = [key for key in changes if key in security_keys]
        snapshot_changed = [key for key in changes if key in snapshot_keys]
        system_changed = [key for key in changes if key in system_keys]
        spot_changed = [key for key in changes if key in spot_keys]
        plc_changed = [key for key in changes if key in plc_keys]
        threshold_changed = [key for key in changes if key in threshold_keys]

        if log_changed:
            log_path_value = settings.get("logpath")
            resolved_log_path = config.resolve_storage_path(log_path_value, "logs", "LogPath")
            config.LOG_PATH = resolved_log_path
            config.AUTO_SAVE = bool(settings.get("autosave", config.DEFAULT_AUTO_SAVE))
            config.ROTATION_ENABLED = bool(
                logging_cfg.get("rotation_enabled", config.DEFAULT_ROTATION_ENABLED)
            )
            rotation_mode = logging_cfg.get("rotation_mode") or config.DEFAULT_ROTATION_MODE
            config.ROTATION_MODE = str(rotation_mode).upper()
            try:
                config.CYCLE_IDLE_TIME = float(logging_cfg.get("cycle_idle_time", config.DEFAULT_CYCLE_IDLE_TIME))
            except Exception:
                config.CYCLE_IDLE_TIME = float(config.DEFAULT_CYCLE_IDLE_TIME)
            try:
                config.CYCLE_THRESHOLD_PRESS = float(
                    logging_cfg.get("cycle_threshold_press", config.DEFAULT_CYCLE_THRESHOLD_PRESS)
                )
            except Exception:
                config.CYCLE_THRESHOLD_PRESS = float(config.DEFAULT_CYCLE_THRESHOLD_PRESS)
            config.CSV_HEADER = logging_cfg.get("csv_header") or config.DEFAULT_CSV_HEADER
            try:
                logger_service.apply_config(
                    log_path=resolved_log_path,
                    auto_save=config.AUTO_SAVE,
                    rotation_enabled=config.ROTATION_ENABLED,
                    rotation_mode=config.ROTATION_MODE,
                    cycle_idle_time=config.CYCLE_IDLE_TIME,
                    cycle_threshold_press=config.CYCLE_THRESHOLD_PRESS,
                    csv_header=config.CSV_HEADER,
                )
                applied.extend(sorted(log_changed))
            except Exception:
                pending.extend(sorted(log_changed))

        if snapshot_changed:
            snapshot_path_value = settings.get("snapshotpath")
            config.SNAPSHOT_PATH = config.resolve_storage_path(snapshot_path_value, "snapshots", "SnapshotPath")
            applied.extend(sorted(snapshot_changed))

        if system_changed:
            interval_sec = system_cfg.get("intervalsec", config.INTERVAL_SEC)
            config.INTERVAL_SEC = float(config.INTERVAL_SEC)
            try:
                from .plc_service import plc_service

                plc_service.apply_interval(float(interval_sec))
                applied.extend(sorted(system_changed))
            except Exception:
                pending.extend(sorted(system_changed))

        if spot_changed:
            spot_cfg = values.get("spot", {})
            try:
                spot_ip = str(spot_cfg.get("ip") or config.DEFAULT_SPOT_IP)
                config.SPOT_IP = spot_ip
                config.SPOT_URL = spot_cfg.get("url") or f"http://{spot_ip}/output?p=temperature"
                config.SPOT_IMAGE_URL = spot_cfg.get("image_url") or f"http://{spot_ip}/image.jpg"
                refresh_value = spot_cfg.get("refresh_interval", config.DEFAULT_SPOT_REFRESH_INTERVAL)
                try:
                    refresh_float = float(refresh_value)
                except Exception:
                    refresh_float = float(config.DEFAULT_SPOT_REFRESH_INTERVAL)
                if refresh_float <= 0:
                    refresh_float = float(config.DEFAULT_SPOT_REFRESH_INTERVAL)
                config.SPOT_REFRESH_INTERVAL = refresh_float
                config.SPOT_CROSSHAIR_X = float(spot_cfg.get("crosshair_x", config.DEFAULT_SPOT_CROSSHAIR_X))
                config.SPOT_CROSSHAIR_Y = float(spot_cfg.get("crosshair_y", config.DEFAULT_SPOT_CROSSHAIR_Y))
                config.SPOT_CROSSHAIR_COLOR = str(
                    spot_cfg.get("crosshair_color", config.DEFAULT_SPOT_CROSSHAIR_COLOR)
                )
                config.SPOT_CROSSHAIR_THICKNESS = int(
                    spot_cfg.get("crosshair_thickness", config.DEFAULT_SPOT_CROSSHAIR_THICKNESS)
                )
                config.SPOT_CROSSHAIR_SIZE = int(
                    spot_cfg.get("crosshair_size", config.DEFAULT_SPOT_CROSSHAIR_SIZE)
                )
                config.SPOT_CROSSHAIR_GAP = int(
                    spot_cfg.get("crosshair_gap", config.DEFAULT_SPOT_CROSSHAIR_GAP)
                )
                config.SPOT_FOCUS_URL = str(spot_cfg.get("focus_url", config.SPOT_FOCUS_URL))
                config.SPOT_FOCUS_STEP = int(spot_cfg.get("focus_step", config.SPOT_FOCUS_STEP))
                config.SPOT_ACTUATOR_IP = str(spot_cfg.get("actuator_ip", spot_ip))
                config.SPOT_ACTUATOR_STEP = int(
                    spot_cfg.get("actuator_step", config.DEFAULT_SPOT_ACTUATOR_STEP)
                )
                config.SPOT_ACTUATOR_URL = str(
                    spot_cfg.get("actuator_url", f"http://{config.SPOT_ACTUATOR_IP}/scan.cgi")
                )
                config.SPOT_WIDGET_WIDTH = int(spot_cfg.get("widget_width", config.DEFAULT_SPOT_WIDGET_WIDTH))
                config.SPOT_WIDGET_HEIGHT = int(spot_cfg.get("widget_height", config.DEFAULT_SPOT_WIDGET_HEIGHT))
                applied.extend(sorted(spot_changed))
            except Exception:
                pending.extend(sorted(spot_changed))

        if plc_changed:
            extruder_cfg = values.get("extruder", {})
            ls_cfg = values.get("ls_plc", {})
            try:
                config.EXTRUDER_IP = str(extruder_cfg.get("ip") or config.DEFAULT_EXTRUDER_IP)
                config.EXTRUDER_PORT = int(extruder_cfg.get("port") or config.DEFAULT_EXTRUDER_PORT)
                config.LS_IP = str(ls_cfg.get("ip") or config.DEFAULT_LS_IP)
                config.LS_PORT = int(ls_cfg.get("port") or config.DEFAULT_LS_PORT)
                config.LS_TARGETS = list(ls_cfg.get("targets") or config.DEFAULT_LS_TARGETS)
                from .plc_service import plc_service

                if plc_service.apply_connection_config():
                    applied.extend(sorted(plc_changed))
                else:
                    pending.extend(sorted(plc_changed))
            except Exception:
                pending.extend(sorted(plc_changed))

        if threshold_changed:
            applied.extend(sorted(threshold_changed))
        if security_changed:
            applied.extend(sorted(security_changed))

        for key in changes:
            if key not in applied and key not in pending:
                pending.append(key)

        pending = sorted(set(pending))
        applied = sorted(set(applied))
        with self._lock:
            self._pending_keys = set(pending)
            self._last_apply = {"applied": applied, "pending": pending}
        try:
            if applied or pending:
                config._config_log(
                    "INFO",
                    f"Hot reload applied={len(applied)} pending={len(pending)}",
                )
            if pending:
                config._config_log("WARNING", f"Hot reload pending keys: {', '.join(pending)}")
        except Exception:
            pass
        return {
            "applied": applied,
            "pending": pending,
        }

    def get_restart_required(self) -> bool:
        with self._lock:
            return bool(self._pending_keys)

    def get_apply_result(self) -> Dict[str, list[str]]:
        with self._lock:
            return deepcopy(self._last_apply)


config_manager = ConfigManager()
