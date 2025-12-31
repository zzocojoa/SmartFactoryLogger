from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import List, Tuple, Optional

# Fixed collection interval (policy: must stay at 0.2s)
INTERVAL_SEC = 0.2

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

    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "config.ini",
        Path.cwd() / "config" / "config.ini",
        here.parent / "config.ini",
        here.parents[1] / "config" / "config.ini",
        here.parents[2] / "config" / "config.ini",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
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
    try:
        return float(val)
    except ValueError:
        return fallback


CONFIG_PATH = _resolve_config_path()
CONFIG, CONFIG_ENCODING = _load_config(CONFIG_PATH)

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
