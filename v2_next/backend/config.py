from __future__ import annotations

import configparser
from datetime import datetime
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import List, Tuple, Optional
from dotenv import load_dotenv

# Load .env file (if present)
load_dotenv()

# Default collection interval (can be changed via config.ini)
DEFAULT_INTERVAL_SEC = 0.2
MIN_INTERVAL_SEC = 0.1
MAX_INTERVAL_SEC = 2.0

# Versioning
try:
    from backend.version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.0.0-dev"

print(f"[Config] Loading SmartFactoryLogger v{APP_VERSION}")

# Defaults (used when config.ini is missing or invalid)
DEFAULT_EXTRUDER_IP = "192.168.10.10"
DEFAULT_EXTRUDER_PORT = 12289
DEFAULT_LS_IP = "192.168.10.220"
DEFAULT_LS_PORT = 2004
DEFAULT_SPOT_IP = "10.1.10.50"
DEFAULT_SPOT_REFRESH_INTERVAL = 3.0
DEFAULT_SPOT_IMAGE_URL = f"http://{DEFAULT_SPOT_IP}/image.jpg"
DEFAULT_SPOT_CROSSHAIR_X = 0.5
DEFAULT_SPOT_CROSSHAIR_Y = 0.5
DEFAULT_SPOT_CROSSHAIR_COLOR = "lime"
DEFAULT_SPOT_CROSSHAIR_THICKNESS = 2
DEFAULT_SPOT_CROSSHAIR_SIZE = 20
DEFAULT_SPOT_CROSSHAIR_GAP = 5
DEFAULT_SPOT_FOCUS_URL = f"http://{DEFAULT_SPOT_IP}/control?p=focus"
DEFAULT_SPOT_FOCUS_STEP = 50
DEFAULT_SPOT_ACTUATOR_STEP = 5
DEFAULT_SPOT_WIDGET_WIDTH = 512
DEFAULT_SPOT_WIDGET_HEIGHT = 288
DEFAULT_LOG_PATH = "logs/data"
DEFAULT_SNAPSHOT_PATH = "snapshots"
DEFAULT_AUTO_SAVE = True
DEFAULT_STATUS_WARN_MS = 10000
DEFAULT_STATUS_OFFLINE_MS = 20000
DEFAULT_ROTATION_ENABLED = True
DEFAULT_ROTATION_MODE = "BILLET"
DEFAULT_CYCLE_IDLE_TIME = 30
DEFAULT_CYCLE_THRESHOLD_PRESS = 20.0
DEFAULT_CUSTOM_NOTICE = "작업 상황 및 주의사항을 여기에 입력하세요.\n(마크다운 형식을 지원합니다)"
DEFAULT_CSV_HEADER = (
    "Date,Time,Temperature,MainPress,BilletLength,Temp_F,Temp_B,Count,Speed,EndPos,"
    "Mold1,Mold2,Mold3,Mold4,Mold5,Mold6,Billet_Temp,At_Pre,At_Temp,DIE_ID,Billet_CycleID"
)
DEFAULT_MES_USER_ID = ""
DEFAULT_MES_PASSWORD = ""
DEFAULT_MES_ENABLED = False
DEFAULT_MES_START_HOUR = 8   # 운영 시작 시간 (08:00)
DEFAULT_MES_END_HOUR = 19    # 운영 종료 시간 (19:00)
DEFAULT_LS_TARGETS: List[Tuple[str, str]] = [
    ("%DW250", "Mold1"),
    ("%DW256", "Mold2"),
    ("%DW262", "Mold3"),
    ("%DW288", "Mold4"),
    ("%DW276", "Mold5"),
    ("%DW282", "Mold6"),
    ("%DW268", "Billet_Temp"),
    ("%DW40", "At_Temp"),
    ("%DW50", "At_Pre"),
]


def _resolve_config_path() -> Optional[Path]:
    # Environment override (preferred for deployed machines)
    env_path = os.getenv("SFL_CONFIG_PATH") or os.getenv("SMARTFACTORY_CONFIG")
    if env_path:
        return Path(env_path)

    standard_dir = _get_user_data_dir()
    standard_path = standard_dir / "config.ini"
    if standard_path.is_file():
        return standard_path

    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "config.ini",
        Path.cwd() / "config" / "config.ini",
        here.parent / "config.ini",
        here.parents[1] / "config" / "config.ini",
        here.parents[2] / "config" / "config.ini",
    ]
    legacy_path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if legacy_path:
        try:
            standard_dir.mkdir(parents=True, exist_ok=True)
            if not standard_path.exists():
                shutil.copy2(legacy_path, standard_path)
                backup_path = standard_path.with_suffix(".bak")
                if not backup_path.exists():
                    shutil.copy2(standard_path, backup_path)
                _config_log("INFO", f"Config migrated: {legacy_path} -> {standard_path}")
            return standard_path
        except Exception as exc:
            _config_log("ERROR", f"Config migration failed: {exc}")
            return legacy_path
    return None


def _load_config(path: Optional[Path]) -> tuple[configparser.ConfigParser, Optional[str]]:
    parser = configparser.ConfigParser()
    parser.optionxform = str
    if not path or not path.is_file():
        return parser, None

    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
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


def _get_int(parser: configparser.ConfigParser, section: str, option: str, fallback: int) -> int:
    val = _get(parser, section, option, None)
    try:
        return int(val) if val is not None else fallback
    except ValueError:
        return fallback


def _save_config(path: Path, parser: configparser.ConfigParser, encoding: str) -> None:
    """Save the current config parser back to disk safely."""
    try:
        # Create a backup before writing
        backup_path = path.with_suffix(".bak")
        if path.exists() and not backup_path.exists():
            shutil.copy2(path, backup_path)
            
        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w", encoding=encoding) as handle:
            parser.write(handle)
        tmp_path.replace(path)
        _config_log("INFO", f"Config file auto-updated: {path}")
    except Exception as exc:
        _config_log("ERROR", f"Failed to auto-update config: {exc}")


def _get_float(parser: configparser.ConfigParser, section: str, option: str, fallback: float) -> float:
    val = _get(parser, section, option, None)
    try:
        return float(val) if val is not None else fallback
    except ValueError:
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


def _get_bool(parser: configparser.ConfigParser, section: str, option: str, fallback: bool) -> bool:
    val = _get(parser, section, option, None)
    if val is None:
        return fallback
    lowered = val.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    return fallback


def _get_user_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.getenv("APPDATA") or str(Path.home())
        return Path(base) / "SmartFactoryLogger"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SmartFactoryLogger"
    return Path.home() / ".config" / "SmartFactoryLogger"


def _ensure_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".perm_", dir=str(path))
        os.close(fd)
        Path(tmp_path).unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _config_log(level: str, message: str) -> None:
    try:
        base_dir = APP_DATA_DIR if "APP_DATA_DIR" in globals() else _get_user_data_dir()
        # Config logs go to 'system' subdirectory
        log_dir = base_dir / "logs" / "system"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "system.log"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{ts}] [{level}] [Config] {message}\n")
    except Exception:
        pass


def resolve_storage_path(path_value: Optional[str], default_subdir: str, label: str) -> Path:
    raw_value = path_value or default_subdir
    candidate = Path(raw_value)
    
    # If absolute, use as is
    if candidate.is_absolute():
        if _ensure_writable_dir(candidate):
            return candidate
        # Fallback if specific absolute path isn't writable (rare but possible)
        fallback = APP_DATA_DIR / default_subdir
        _ensure_writable_dir(fallback)
        _config_log("WARNING", f"{label} absolute path not writable: {candidate}. Fallback: {fallback}")
        return fallback

    # If relative, determine base directory
    # Portable Mode Check: If frozen (EXE), try to use the executable's directory first
    base_dir = APP_DATA_DIR
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        # Try to use a test path to check writability of the EXE dir
        test_path = exe_dir / raw_value
        if _ensure_writable_dir(test_path):
            base_dir = exe_dir
            _config_log("INFO", f"Portable mode detected. Using EXE dir for {label}: {base_dir}")
        else:
            _config_log("INFO", f"EXE dir not writable. Using AppData for {label}")

    candidate = base_dir / raw_value
    
    if _ensure_writable_dir(candidate):
        return candidate
        
    fallback = APP_DATA_DIR / default_subdir
    _ensure_writable_dir(fallback)
    _config_log(
        "WARNING",
        f"{label} path not usable: {candidate}. "
        f"Check permissions or run as administrator. Using fallback: {fallback}",
    )
    return fallback


CONFIG_PATH = _resolve_config_path()
CONFIG, CONFIG_ENCODING = _load_config(CONFIG_PATH)

# --- Auto-Update config.ini if missing new sections ---
if CONFIG_PATH and CONFIG_PATH.is_file():
    _updated = False
    
    # MES 섹션 및 개별 키 자동 추가 (기존 config.ini 호환)
    if not CONFIG.has_section("MES"):
        CONFIG.add_section("MES")
        _updated = True
    _mes_defaults = {
        "enabled": str(DEFAULT_MES_ENABLED),
        "userid": DEFAULT_MES_USER_ID,
        "password": DEFAULT_MES_PASSWORD,
        "starthour": str(DEFAULT_MES_START_HOUR),
        "endhour": str(DEFAULT_MES_END_HOUR),
    }
    for _key, _default_val in _mes_defaults.items():
        if not CONFIG.has_option("MES", _key):
            CONFIG.set("MES", _key, _default_val)
            _updated = True
            _config_log("INFO", f"Auto-added missing MES.{_key} = {_default_val}")
    
    # SYSTEM 섹션 및 개별 키 자동 추가
    if not CONFIG.has_section("SYSTEM"):
        CONFIG.add_section("SYSTEM")
        _updated = True
    _system_defaults = {
        "intervalsec": str(DEFAULT_INTERVAL_SEC),
        "statuswarnms": str(DEFAULT_STATUS_WARN_MS),
        "statusofflinems": str(DEFAULT_STATUS_OFFLINE_MS),
    }
    for _key, _default_val in _system_defaults.items():
        if not CONFIG.has_option("SYSTEM", _key):
            CONFIG.set("SYSTEM", _key, _default_val)
            _updated = True
            _config_log("INFO", f"Auto-added missing SYSTEM.{_key} = {_default_val}")

    if _updated:
        _save_config(CONFIG_PATH, CONFIG, CONFIG_ENCODING or "utf-8-sig")

APP_DATA_DIR = _get_user_data_dir()

# Distributed Settings (Environment & Ports)
BACKEND_PORT = _env_int("BACKEND_PORT", 8000)
CENTRAL_PORT = _env_int("CENTRAL_PORT", 9000)

# EXTRUDER
EXTRUDER_IP = os.getenv("EXTRUDER_IP", _get(CONFIG, "EXTRUDER", "ip", DEFAULT_EXTRUDER_IP) or DEFAULT_EXTRUDER_IP)
EXTRUDER_PORT = _get_int(CONFIG, "EXTRUDER", "port", DEFAULT_EXTRUDER_PORT)
EXTRUDER_PORT = _env_int("EXTRUDER_PORT", EXTRUDER_PORT)

# LS PLC
LS_IP = os.getenv("LS_IP", _get(CONFIG, "LS_PLC", "ip", DEFAULT_LS_IP) or DEFAULT_LS_IP)
LS_PORT = _get_int(CONFIG, "LS_PLC", "port", DEFAULT_LS_PORT)
LS_PORT = _env_int("LS_PORT", LS_PORT)


def _load_ls_targets() -> List[Tuple[str, str]]:
    if CONFIG.has_section("LS_PLC_TARGETS"):
        targets: List[Tuple[str, str]] = []
        for addr, key in CONFIG.items("LS_PLC_TARGETS"):
            addr_norm = addr.strip()
            if not addr_norm.startswith("%"):
                addr_norm = "%" + addr_norm
            addr_norm = addr_norm.upper()
            targets.append((addr_norm, key.strip()))
        if targets:
            return targets
    return DEFAULT_LS_TARGETS


LS_TARGETS = _load_ls_targets()

# SPOT
SPOT_IP = os.getenv("SPOT_IP", _get(CONFIG, "SPOT", "ip", DEFAULT_SPOT_IP) or DEFAULT_SPOT_IP)
SPOT_URL = os.getenv("SPOT_URL", f"http://{SPOT_IP}/output?p=temperature")
SPOT_IMAGE_URL = os.getenv(
    "SPOT_IMAGE_URL",
    _get(CONFIG, "SPOT", "imageurl", f"http://{SPOT_IP}/image.jpg") or f"http://{SPOT_IP}/image.jpg",
)
SPOT_REFRESH_INTERVAL = _get_float(CONFIG, "SPOT", "refreshinterval", DEFAULT_SPOT_REFRESH_INTERVAL)
SPOT_REFRESH_INTERVAL = _env_float("SPOT_REFRESH_INTERVAL", SPOT_REFRESH_INTERVAL)
if SPOT_REFRESH_INTERVAL <= 0:
    SPOT_REFRESH_INTERVAL = DEFAULT_SPOT_REFRESH_INTERVAL

SPOT_TIMEOUT = _get_float(CONFIG, "SPOT", "timeout", 0.3)
SPOT_TIMEOUT = _env_float("SPOT_TIMEOUT", SPOT_TIMEOUT)

SPOT_CROSSHAIR_X = _get_float(CONFIG, "SPOT", "crosshairx", DEFAULT_SPOT_CROSSHAIR_X)
SPOT_CROSSHAIR_X = _env_float("SPOT_CROSSHAIR_X", SPOT_CROSSHAIR_X)
SPOT_CROSSHAIR_Y = _get_float(CONFIG, "SPOT", "crosshairy", DEFAULT_SPOT_CROSSHAIR_Y)
SPOT_CROSSHAIR_Y = _env_float("SPOT_CROSSHAIR_Y", SPOT_CROSSHAIR_Y)
SPOT_CROSSHAIR_COLOR = os.getenv(
    "SPOT_CROSSHAIR_COLOR",
    _get(CONFIG, "SPOT", "crosshaircolor", DEFAULT_SPOT_CROSSHAIR_COLOR) or DEFAULT_SPOT_CROSSHAIR_COLOR,
)
SPOT_CROSSHAIR_THICKNESS = _get_int(CONFIG, "SPOT", "crosshairthickness", DEFAULT_SPOT_CROSSHAIR_THICKNESS)
SPOT_CROSSHAIR_THICKNESS = _env_int("SPOT_CROSSHAIR_THICKNESS", SPOT_CROSSHAIR_THICKNESS)
SPOT_CROSSHAIR_SIZE = _get_int(CONFIG, "SPOT", "crosshairsize", DEFAULT_SPOT_CROSSHAIR_SIZE)
SPOT_CROSSHAIR_SIZE = _env_int("SPOT_CROSSHAIR_SIZE", SPOT_CROSSHAIR_SIZE)
SPOT_CROSSHAIR_GAP = _get_int(CONFIG, "SPOT", "crosshairgap", DEFAULT_SPOT_CROSSHAIR_GAP)
SPOT_CROSSHAIR_GAP = _env_int("SPOT_CROSSHAIR_GAP", SPOT_CROSSHAIR_GAP)

SPOT_FOCUS_URL = os.getenv(
    "SPOT_FOCUS_URL",
    _get(CONFIG, "SPOT", "focusurl", DEFAULT_SPOT_FOCUS_URL) or DEFAULT_SPOT_FOCUS_URL,
)
SPOT_FOCUS_STEP = _get_int(CONFIG, "SPOT", "focusstep", DEFAULT_SPOT_FOCUS_STEP)
SPOT_FOCUS_STEP = _env_int("SPOT_FOCUS_STEP", SPOT_FOCUS_STEP)

SPOT_ACTUATOR_IP = os.getenv("SPOT_ACTUATOR_IP", _get(CONFIG, "SPOT", "actuatorip", "") or "")
if not SPOT_ACTUATOR_IP:
    SPOT_ACTUATOR_IP = SPOT_IP
SPOT_ACTUATOR_STEP = _get_int(CONFIG, "SPOT", "actuatorstep", DEFAULT_SPOT_ACTUATOR_STEP)
SPOT_ACTUATOR_STEP = _env_int("SPOT_ACTUATOR_STEP", SPOT_ACTUATOR_STEP)
SPOT_ACTUATOR_URL = os.getenv("SPOT_ACTUATOR_URL", f"http://{SPOT_ACTUATOR_IP}/scan.cgi")

SPOT_WIDGET_WIDTH = _get_int(CONFIG, "SPOT", "widgetwidth", DEFAULT_SPOT_WIDGET_WIDTH)
SPOT_WIDGET_WIDTH = _env_int("SPOT_WIDGET_WIDTH", SPOT_WIDGET_WIDTH)
SPOT_WIDGET_HEIGHT = _get_int(CONFIG, "SPOT", "widgetheight", DEFAULT_SPOT_WIDGET_HEIGHT)
SPOT_WIDGET_HEIGHT = _env_int("SPOT_WIDGET_HEIGHT", SPOT_WIDGET_HEIGHT)

# SETTINGS / LOGGING
LOG_PATH = resolve_storage_path(_get(CONFIG, "SETTINGS", "logpath", DEFAULT_LOG_PATH), "logs", "LogPath")
AUTO_SAVE = _get_bool(CONFIG, "SETTINGS", "autosave", DEFAULT_AUTO_SAVE)
CUSTOM_NOTICE = _get(CONFIG, "SETTINGS", "custom_notice", DEFAULT_CUSTOM_NOTICE) or DEFAULT_CUSTOM_NOTICE
ROTATION_ENABLED = _get_bool(CONFIG, "LOGGING", "rotationenabled", DEFAULT_ROTATION_ENABLED)
ROTATION_MODE = (_get(CONFIG, "LOGGING", "rotationmode", DEFAULT_ROTATION_MODE) or DEFAULT_ROTATION_MODE).upper()

# APP MODE (REAL vs MOCK)
# Priority: Env Var > Config.ini > Frozen State (Real) > Default (Mock)
_DEFAULT_MODE = "REAL" if getattr(sys, "frozen", False) else "MOCK"
MODE = os.getenv("V2_MODE", _get(CONFIG, "SETTINGS", "mode", _DEFAULT_MODE)).upper()
CYCLE_IDLE_TIME = _get_int(CONFIG, "LOGGING", "cycleidletime", DEFAULT_CYCLE_IDLE_TIME)
CYCLE_THRESHOLD_PRESS = _get_float(CONFIG, "LOGGING", "cyclethresholdpress", DEFAULT_CYCLE_THRESHOLD_PRESS)
CSV_HEADER = _get(CONFIG, "HEADERS", "csv", DEFAULT_CSV_HEADER) or DEFAULT_CSV_HEADER
SNAPSHOT_PATH = resolve_storage_path(
    _get(CONFIG, "SETTINGS", "snapshotpath", DEFAULT_SNAPSHOT_PATH),
    "snapshots",
    "SnapshotPath",
)

# SYSTEM / Polling Interval
_interval_raw = _get_float(CONFIG, "SYSTEM", "intervalsec", DEFAULT_INTERVAL_SEC)
_interval_raw = _env_float("INTERVAL_SEC", _interval_raw)
INTERVAL_SEC = max(MIN_INTERVAL_SEC, min(MAX_INTERVAL_SEC, _interval_raw))

# SYSTEM / Status Thresholds
STATUS_WARN_MS = _get_int(CONFIG, "SYSTEM", "statuswarnms", DEFAULT_STATUS_WARN_MS)
STATUS_OFFLINE_MS = _get_int(CONFIG, "SYSTEM", "statusofflinems", DEFAULT_STATUS_OFFLINE_MS)

# MES
MES_ENABLED = _get_bool(CONFIG, "MES", "enabled", DEFAULT_MES_ENABLED)
MES_USER_ID = os.getenv("MES_USER_ID", _get(CONFIG, "MES", "userid", DEFAULT_MES_USER_ID) or DEFAULT_MES_USER_ID)
MES_PASSWORD = os.getenv("MES_PASSWORD", _get(CONFIG, "MES", "password", DEFAULT_MES_PASSWORD) or DEFAULT_MES_PASSWORD)
MES_START_HOUR = _get_int(CONFIG, "MES", "starthour", DEFAULT_MES_START_HOUR)
MES_END_HOUR = _get_int(CONFIG, "MES", "endhour", DEFAULT_MES_END_HOUR)


# Validation Logic
def validate_config() -> List[str]:
    """
    Validates the current configuration and returns a list of warning/error messages.
    """
    issues = []
    
    def _is_valid_port(port: int) -> bool:
        return 1 <= port <= 65535

    def _is_valid_ip(ip: str) -> bool:
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit():
                return False
            if not 0 <= int(part) <= 255:
                return False
        return True

    # Validate Ports
    if not _is_valid_port(BACKEND_PORT):
        issues.append(f"Invalid BACKEND_PORT: {BACKEND_PORT}")
    if not _is_valid_port(CENTRAL_PORT):
        issues.append(f"Invalid CENTRAL_PORT: {CENTRAL_PORT}")
    if not _is_valid_port(EXTRUDER_PORT):
        issues.append(f"Invalid EXTRUDER_PORT: {EXTRUDER_PORT}")
    if not _is_valid_port(LS_PORT):
        issues.append(f"Invalid LS_PORT: {LS_PORT}")
        
    # Validate IPs (Basic check)
    if not _is_valid_ip(EXTRUDER_IP):
        issues.append(f"Invalid EXTRUDER_IP format: {EXTRUDER_IP}")
    if not _is_valid_ip(LS_IP):
        issues.append(f"Invalid LS_IP format: {LS_IP}")
    if not _is_valid_ip(SPOT_IP):
        issues.append(f"Invalid SPOT_IP format: {SPOT_IP}")
        
    # Validate Mode
    if MODE not in ("REAL", "MOCK", "CSV"):
         issues.append(f"Unknown MODE: {MODE}. Expected REAL, MOCK, or CSV.")

    # Log issues
    if issues:
        for issue in issues:
            _config_log("WARNING", f"Config Validation Issue: {issue}")
            print(f"[CONFIG WARNING] {issue}", file=sys.stderr)
    else:
        _config_log("INFO", "Configuration validation passed.")

    return issues

# Run validation on load
validate_config()
