# config.py
import configparser
import datetime
import os
import shutil
import sys
import tempfile
from config_schema import AppConfig

# 색상 상수
COLOR_BG = "#1e1e1e"       # VS Code style dark bg
COLOR_PANEL = "#252526"    # Slightly lighter panel
COLOR_CARD = "#333333"     # Card bg
COLOR_TEXT = "#ffffff"
COLOR_TEXT_DIM = "#aaaaaa"
COLOR_ACCENT = "#007acc"   # VS Code Blue
COLOR_WARNING = "#e0a800"
COLOR_DANGER = "#f14c4c"
COLOR_SUCCESS = "#4ec9b0"
COLOR_COLD = "#569cd6"
COLOR_HOT = "#ce9178"

# 설정 파일 경로 (AppData/Roaming 사용)
# 설정 파일 경로 (Portable vs AppData)
# 1. 실행 파일 위치 확인
if getattr(sys, 'frozen', False):
    EXE_DIR = os.path.dirname(sys.executable)
else:
    # src/config.py -> parent is src -> parent is root
    EXE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_user_data_dir():
    if sys.platform == "win32":
        base = os.getenv('APPDATA') or os.path.expanduser("~")
        return os.path.join(base, 'SmartFactoryLogger')
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "SmartFactoryLogger")
    return os.path.join(os.path.expanduser("~"), ".config", "SmartFactoryLogger")

APP_DATA_DIR = get_user_data_dir()
LOCAL_CONFIG = os.path.join(EXE_DIR, "config.ini")
DEV_CONFIG = os.path.join(EXE_DIR, "config", "config.ini")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.ini")
CONFIG_BACKUP_VERSIONS = 3

def _config_log(level, message):
    try:
        logs_dir = os.path.join(APP_DATA_DIR, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        log_path = os.path.join(logs_dir, "system.log")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] [Config] {message}\n")
    except Exception:
        pass

def _ensure_writable_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        return False
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".perm_", dir=path)
        os.close(fd)
        os.remove(tmp_path)
        return True
    except Exception:
        return False

def resolve_storage_path(path_value, default_subdir, label):
    raw_value = path_value if path_value else default_subdir
    if not os.path.isabs(raw_value):
        candidate = os.path.join(APP_DATA_DIR, raw_value)
    else:
        candidate = raw_value
    if _ensure_writable_dir(candidate):
        return candidate
    fallback = os.path.join(APP_DATA_DIR, default_subdir)
    _ensure_writable_dir(fallback)
    _config_log("WARNING", f"{label} path not usable: {candidate}. Using fallback: {fallback}")
    return fallback

# Ensure AppData dir exists
if not os.path.exists(APP_DATA_DIR):
    try:
        os.makedirs(APP_DATA_DIR)
        print(f"[Config] Created AppData directory: {APP_DATA_DIR}")
    except Exception as e:
        print(f"[Config] Failed to create AppData directory: {e}")

# Seed AppData config from local or dev config if missing
if not os.path.exists(CONFIG_FILE):
    if os.path.exists(LOCAL_CONFIG):
        try:
            import shutil
            shutil.copy2(LOCAL_CONFIG, CONFIG_FILE)
            print(f"[Config] Copied local config to AppData: {CONFIG_FILE}")
        except Exception as e:
            print(f"[Config] Copy local config failed: {e}")
    elif os.path.exists(DEV_CONFIG):
        try:
            import shutil
            shutil.copy2(DEV_CONFIG, CONFIG_FILE)
            print(f"[Config] Copied dev config to AppData: {CONFIG_FILE}")
        except Exception as e:
            print(f"[Config] Copy dev config failed: {e}")

BASE_DIR = APP_DATA_DIR

# ---------------------------------------------------------------------------
# [0] Default Configuration (Source of Truth)
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    'SYSTEM': {
        'DeviceName': '창녕 2호기',
        'IntervalSec': '0.2'
    },
    'EXTRUDER': {
        'IP': '192.168.10.10',
        'Port': '12289'
    },
    'SPOT': {
        'IP': '10.1.10.50',
        'RefreshInterval': '3.0',
        'ImageURL': 'http://10.1.10.50/image.jpg',
        'CrosshairX': '0.5',
        'CrosshairY': '0.5',
        'CrosshairColor': 'lime',
        'CrosshairThickness': '2',
        'CrosshairSize': '20',
        'CrosshairGap': '5',
        'FocusURL': 'http://10.1.10.50/control?p=focus',
        'FocusStep': '200',
        'WidgetWidth': '512',
        'WidgetHeight': '288',
        'RefreshInterval': '0.5',
        'ActuatorIP': '10.1.10.60' # Dedicated Controller IP
    },
    'ACTUATOR': {
        'CmdLeft': 'http://10.1.10.60/scan.cgi?scan=3',
        'CmdRight': 'http://10.1.10.60/scan.cgi?scan=2'
    },
    'LS_PLC': {
        'IP': '192.168.10.220',
        'Port': '2004'
    },
    'LS_PLC_TARGETS': {
        '%DW250': 'Mold1',
        '%DW256': 'Mold2',
        '%DW262': 'Mold3',
        '%DW288': 'Mold4',
        '%DW276': 'Mold5',
        '%DW282': 'Mold6',
        '%DW268': 'Billet_Temp',
        '%DW40': 'At_Temp',
        '%DW50': 'At_Pre'
    },
    'SETTINGS': {
        'Password': '1234',
        'LogPath': 'logs', # Relative to APP_DATA_DIR
        'SnapshotPath': 'snapshots',
        'AutoSave': 'True'
    },
    'LOGGING': {
        'RotationMode': 'BILLET', # BILLET, DAILY
        'CycleIdleTime': '30',    # Seconds (Wait for new billet)
        'CycleThresholdPress': '20' # Bar (Start trigger)
    },
    'HEADERS': {
        'CSV': "Date,Time,Temperature,메인압력,빌렛길이,콘테이너온도 앞쪽,콘테이너온도 뒷쪽,생산카운터,현재속도,압출종료 위치,Mold1,Mold2,Mold3,Mold4,Mold5,Mold6,Billet_Temp,At_Pre,At_Temp,DIE_ID,Billet_CycleID",
        'CONSOLE': "| Temp  | 압력  | 빌렛L | 콘(앞)| 콘(뒤)| 카운트| 속도 | 종료 | Mold1 | Mold2 | Mold3 | Mold4 | Mold5 | Mold6 | BillT | AtPre | AtTmp"
    },
    'THRESHOLDS_VALUE': {
        'Speed': '', 'Press': '', 'Spot': '', 'Temp_F': '', 'Temp_B': '',
        'Billet': '', 'Billet_Temp': '', 'At_Temp': '', 'At_Pre': '',
        'Count': '', 'EndPos': ''
    },
    'THRESHOLDS_ENABLE': {
        'Speed': 'False', 'Press': 'False', 'Spot': 'False', 'Temp_F': 'False', 'Temp_B': 'False',
        'Billet': 'False', 'Billet_Temp': 'False', 'At_Temp': 'False', 'At_Pre': 'False',
        'Count': 'False', 'EndPos': 'False',
        'MASTER_ON': 'False'
    }
}

# ConfigParser Init
config_parser = configparser.ConfigParser()

def read_config_with_fallback(config_obj, file_path):
    encodings = ["utf-8-sig", "utf-8", "cp949"]
    last_err = None
    for enc in encodings:
        try:
            config_obj.read(file_path, encoding=enc)
            return enc
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    return None


def rotate_backups(file_path, max_versions=CONFIG_BACKUP_VERSIONS):
    if max_versions < 1:
        return None
    bak_base = file_path + ".bak"
    if max_versions > 1:
        oldest = f"{bak_base}.{max_versions - 1}"
        if os.path.exists(oldest):
            try:
                os.remove(oldest)
            except Exception:
                pass
        for i in range(max_versions - 2, 0, -1):
            src = f"{bak_base}.{i}"
            dst = f"{bak_base}.{i + 1}"
            if os.path.exists(src):
                try:
                    os.replace(src, dst)
                except Exception:
                    pass
        if os.path.exists(bak_base):
            try:
                os.replace(bak_base, f"{bak_base}.1")
            except Exception:
                pass
    if not os.path.exists(file_path):
        return None
    try:
        shutil.copy2(file_path, bak_base)
        print(f"[Config] Backup created: {bak_base}")
        return bak_base
    except Exception as e:
        print(f"[Config] Backup failed: {e}")
        _config_log("ERROR", f"Backup failed for {file_path}: {e}")
        return None


def backup_config(file_path, max_versions=CONFIG_BACKUP_VERSIONS):
    return rotate_backups(file_path, max_versions=max_versions)


def _write_pending_file(file_path, write_func):
    candidates = [file_path + ".pending"]
    base_name = os.path.basename(file_path)
    candidates.append(os.path.join(APP_DATA_DIR, base_name + ".pending"))
    candidates.append(os.path.join(tempfile.gettempdir(), base_name + ".pending"))
    for pending_path in candidates:
        try:
            os.makedirs(os.path.dirname(pending_path), exist_ok=True)
            with open(pending_path, "w", encoding="utf-8-sig") as f:
                write_func(f)
            return pending_path
        except Exception:
            continue
    return None


def _write_temp_file(file_path, write_func, encoding="utf-8-sig"):
    dir_path = os.path.dirname(file_path)
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=dir_path)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            write_func(f)
        return tmp_path
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise


def safe_write_file(file_path, write_func, backup_versions=CONFIG_BACKUP_VERSIONS, encoding="utf-8-sig"):
    tmp_path = None
    try:
        tmp_path = _write_temp_file(file_path, write_func, encoding=encoding)
        if os.path.exists(file_path):
            backup_config(file_path, max_versions=backup_versions)
        os.replace(tmp_path, file_path)
        return True, None, None
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        is_perm = isinstance(e, PermissionError) or getattr(e, "winerror", None) in (5, 32)
        pending_path = None
        if is_perm:
            pending_path = _write_pending_file(file_path, write_func)
        _config_log("ERROR", f"Safe write failed for {file_path}: {e}")
        return False, e, pending_path


def safe_write_config_parser(config_obj, file_path, backup_versions=CONFIG_BACKUP_VERSIONS):
    def _write(f):
        config_obj.write(f)
    return safe_write_file(file_path, _write, backup_versions=backup_versions)


def build_defaults_index(defaults):
    index = {}
    for sec, keys in defaults.items():
        key_index = {k.lower(): k for k in keys.keys()}
        index[sec.lower()] = (sec, key_index)
    return index


def merge_with_defaults(config_dict, defaults):
    merged = {}
    defaults_index = build_defaults_index(defaults)
    for sec, keys in defaults.items():
        merged[sec] = {k: str(v) for k, v in keys.items()}
    for sec, keys in config_dict.items():
        sec_lower = sec.lower()
        if sec_lower in defaults_index:
            sec_name, key_index = defaults_index[sec_lower]
        else:
            sec_name, key_index = sec, {}
        if sec_name not in merged:
            merged[sec_name] = {}
        for key, value in keys.items():
            key_name = key_index.get(key.lower(), key)
            merged[sec_name][key_name] = value
    return merged


def apply_validation_defaults(config_dict, defaults, errors):
    if not errors:
        return config_dict
    defaults_index = build_defaults_index(defaults)
    for err in errors:
        loc = err.get("loc") if isinstance(err, dict) else None
        if not loc:
            continue
        if len(loc) >= 2:
            sec = str(loc[0])
            key = str(loc[1])
            sec_lower = sec.lower()
            if sec_lower in defaults_index:
                sec_name, key_index = defaults_index[sec_lower]
                key_name = key_index.get(key.lower(), key)
                if sec_name not in config_dict:
                    config_dict[sec_name] = {}
                if sec_name in defaults and key_name in defaults[sec_name]:
                    config_dict[sec_name][key_name] = str(defaults[sec_name][key_name])
    return config_dict


def write_config_dict(file_path, data):
    parser = configparser.ConfigParser()
    for sec, keys in data.items():
        if not parser.has_section(sec):
            parser.add_section(sec)
        for k, v in keys.items():
            parser.set(sec, k, str(v))
    ok, err, pending = safe_write_config_parser(parser, file_path)
    if not ok:
        print(f"[Config] Failed to save config: {err}")
        if pending:
            print(f"[Config] Pending config saved: {pending}")


def sync_config(config_obj, file_path, defaults):
    # Synchronizes the config object with default values.
    # - Creates file if not likely exists.
    # - Adds missing sections/keys (Merge).
    # - Preserves existing user values.
    # - Creates a backup (.bak) before modifying if file exists.
    is_modified = False

    # 1. Load existing
    if os.path.exists(file_path):
        try:
            read_config_with_fallback(config_obj, file_path)
        except Exception as e:
            print(f"[Config] Error reading config: {e}. Using defaults.")

    # 2. Merge Defaults
    for section, keys in defaults.items():
        if not config_obj.has_section(section):
            config_obj.add_section(section)
            is_modified = True

        for key, value in keys.items():
            if not config_obj.has_option(section, key):
                config_obj.set(section, key, str(value))
                is_modified = True

    # 3. Save if needed
    if is_modified:
        ok, err, pending = safe_write_config_parser(config_obj, file_path)
        if ok:
            print(f"[Config] Updated configuration at {file_path} (Merged new defaults)")
        else:
            print(f"[Config] Failed to save config: {err}")
            if pending:
                print(f"[Config] Pending config saved: {pending}")

# Perform Sync
sync_config(config_parser, CONFIG_FILE, DEFAULT_CONFIG)

# [Debug] Popup Removed - Configuration Verified

# ---------------------------------------------------------------------------
# [Safe Loading] Pydantic Validation
# ---------------------------------------------------------------------------
try:
    # 1. Parser -> Dict
    config_dict = {s: dict(config_parser.items(s)) for s in config_parser.sections()}

    # 2. Pydantic Validation
    app_config = AppConfig(**config_dict)

    print("[Config] Configuration loaded and validated successfully.")

except Exception as e:
    print(f"[Config] Validation Failed: {e}")

    repaired = False
    if 'config_dict' not in locals():
        config_dict = {}

    # [Auto-Repair] Check for bracket corruption "['value']"
    try:
        if 'config_dict' in locals():
            fixed_count = 0
            for section, params in config_dict.items():
                for key, val in params.items():
                    if isinstance(val, str) and val.startswith("['") and val.endswith("']"):
                        # remove brackets and quotes
                        clean_val = val[2:-2]
                        config_parser.set(section, key, clean_val)
                        config_dict[section][key] = clean_val
                        fixed_count += 1

            if fixed_count > 0:
                print(f"[Config] Detected {fixed_count} corrupted values. Attempting repair...")
                # Re-validate
                app_config = AppConfig(**config_dict)
                print("[Config] Repair successful! Saving fixed config.")

                ok, err, pending = safe_write_config_parser(config_parser, CONFIG_FILE)
                if not ok:
                    print(f"[Config] Failed to save repaired config: {err}")
                    if pending:
                        print(f"[Config] Pending config saved: {pending}")

                repaired = True

    except Exception as repair_err:
        print(f"[Config] Auto-repair failed: {repair_err}")

    if not repaired:
        try:
            merged = merge_with_defaults(config_dict, DEFAULT_CONFIG)
            try:
                app_config = AppConfig(**merged)
                print("[Config] Validation recovered by defaults merge.")
                backup_config(CONFIG_FILE)
                write_config_dict(CONFIG_FILE, merged)
                config_parser.read_dict(merged)
                repaired = True
            except Exception as merge_err:
                errors = merge_err.errors() if hasattr(merge_err, 'errors') else []
                merged = apply_validation_defaults(merged, DEFAULT_CONFIG, errors)
                app_config = AppConfig(**merged)
                print("[Config] Validation recovered by targeted defaults.")
                backup_config(CONFIG_FILE)
                write_config_dict(CONFIG_FILE, merged)
                config_parser.read_dict(merged)
                repaired = True
        except Exception as merge_err2:
            print(f"[Config] Validation recovery failed: {merge_err2}")

    if not repaired:
        # [Debug] Alert User on Startup
        try:
            import tkinter.messagebox
            import tkinter as tk
            _root = tk.Tk()
            _root.withdraw() # Hide main

            # Capture problematic data
            debug_info = ""
            if 'config_dict' in locals():
                sys_val = config_dict.get('SYSTEM', {})
                debug_info = f"\n[Debug Data]\nSYSTEM Section: {sys_val}"

            tkinter.messagebox.showwarning("Config Error", f"설정 파일(config.ini) 데이터 오류.\n초기 설정으로 복구합니다.\n\nError: {e}{debug_info}")
            _root.destroy()
        except: pass

        print("[Config] Falling back to DEFAULT configuration for safety.")
        # Fallback: Default values in memory only
        app_config = AppConfig(**DEFAULT_CONFIG)
        try:
            config_parser.read_dict(DEFAULT_CONFIG)
        except Exception:
            pass
# ---------------------------------------------------------------------------
# [Export] 전역 변수 설정 (사용 편의성)
# ---------------------------------------------------------------------------

# [0] 환경 설정 (SETTINGS)
PASSWORD = app_config.SETTINGS.Password
LOG_PATH = app_config.SETTINGS.LogPath
SNAPSHOT_PATH = app_config.SETTINGS.SnapshotPath
AUTO_SAVE = app_config.SETTINGS.AutoSave

# Resolve and validate log/snapshot paths with fallback
LOG_PATH = resolve_storage_path(LOG_PATH, "logs", "LogPath")
SNAPSHOT_PATH = resolve_storage_path(SNAPSHOT_PATH, "snapshots", "SnapshotPath")

# [0-1] 로깅 설정 (LOGGING)
ROTATION_MODE = getattr(app_config.LOGGING, 'RotationMode', 'DAILY')
CYCLE_IDLE_TIME = int(getattr(app_config.LOGGING, 'CycleIdleTime', 10))
CYCLE_THRESHOLD_PRESS = float(getattr(app_config.LOGGING, 'CycleThresholdPress', 20.0))

# [1] 기본 설정
DEVICE_NAME = app_config.SYSTEM.DeviceName
INTERVAL_SEC = app_config.SYSTEM.IntervalSec

# [2] 장비 IP 및 포트 설정
# [압출기]
IP_EXT = app_config.EXTRUDER.IP
PORT_EXT = app_config.EXTRUDER.Port

# [적외선 온도기 & 카메라]
IP_SPOT = app_config.SPOT.IP
# Dual IP Support: If ActuatorIP is defined, use it. Else fall back to Main IP.
IP_SPOT_ACTUATOR = app_config.SPOT.ActuatorIP if app_config.SPOT.ActuatorIP else IP_SPOT

URL_SPOT = f"http://{IP_SPOT}/output?p=temperature"
URL_SPOT_IMAGE = app_config.SPOT.ImageURL # Usually contains main IP
SPOT_REFRESH_INTERVAL = app_config.SPOT.RefreshInterval

SPOT_CROSSHAIR_X = app_config.SPOT.CrosshairX
SPOT_CROSSHAIR_Y = app_config.SPOT.CrosshairY

URL_SPOT_FOCUS = app_config.SPOT.FocusURL
# [Actuator] Override Focus with Scan/Move API (Targeting Actuator IP)
URL_SPOT_ACTUATOR = f"http://{IP_SPOT_ACTUATOR}/scan.cgi"
SPOT_ACTUATOR_STEP = app_config.SPOT.ActuatorStep # Configurable step size

SPOT_CROSSHAIR_COLOR = app_config.SPOT.CrosshairColor
SPOT_CROSSHAIR_THICK = app_config.SPOT.CrosshairThickness
SPOT_CROSSHAIR_SIZE = app_config.SPOT.CrosshairSize
SPOT_CROSSHAIR_GAP = app_config.SPOT.CrosshairGap

# [Thresholds] Construction
def get_thresholds():
    t_data = {"MASTER_ON": False}
    if hasattr(app_config, 'THRESHOLDS_ENABLE') and app_config.THRESHOLDS_ENABLE:
        # Pydantic model to dict
        enables = app_config.THRESHOLDS_ENABLE.dict()
        t_data["MASTER_ON"] = enables.pop('MASTER_ON', False)
        
        values = {}
        if hasattr(app_config, 'THRESHOLDS_VALUE') and app_config.THRESHOLDS_VALUE:
             values = app_config.THRESHOLDS_VALUE.dict()

        # [Fix] Normalize keys to match DEFAULT_CONFIG (e.g. 'press' -> 'Press')
        # ConfigParser validation forces lowercase, but UI expects Capitalized keys.
        canonical_map = {}
        # Union keys from DEFAULT_CONFIG sections
        for k in DEFAULT_CONFIG.get('THRESHOLDS_VALUE', {}).keys():
            canonical_map[k.lower()] = k
        for k in DEFAULT_CONFIG.get('THRESHOLDS_ENABLE', {}).keys():
            canonical_map[k.lower()] = k
            
        # Combine keys from loaded config
        all_loaded_keys = set(enables.keys()) | set(values.keys())
        
        for k in all_loaded_keys:
            if k.lower() == 'master_on': continue
            
            # Map lowercase key back to Canonical Key (e.g. 'press' -> 'Press')
            # If not in map, keep original (e.g. custom keys)
            norm_k = canonical_map.get(k.lower(), k)
            
            # Value convert (None if empty/invalid)
            val = values.get(k)
            try:
                f_val = float(val) if val is not None and val != "" else None
            except:
                f_val = None
                
            is_enabled = enables.get(k, False)
            # Pydantic boolean might be True/False directly
            
            t_data[norm_k] = {
                "value": f_val,
                "enabled": bool(is_enabled)
            }
            
    return t_data

THRESHOLDS_CONFIG = get_thresholds()
SPOT_FOCUS_STEP = app_config.SPOT.FocusStep
SPOT_WIDGET_WIDTH = app_config.SPOT.WidgetWidth
SPOT_WIDGET_HEIGHT = app_config.SPOT.WidgetHeight

# [LS PLC (XGT)]
IP_LS = app_config.LS_PLC.IP
PORT_LS = app_config.LS_PLC.Port

# [3] LS PLC 타겟 및 컬럼 매핑 (Legacy Dict handling)
LS_TARGETS = []
if config_parser.has_section("LS_PLC_TARGETS"):
    for key, value in config_parser.items("LS_PLC_TARGETS"):
        addr = key.upper() 
        LS_TARGETS.append((addr, value))

# [4] CSV 및 출력 헤더 설정
csv_str = config_parser.get("HEADERS", "CSV", fallback="")
CSV_HEADER = [x.strip() for x in csv_str.split(",") if x.strip()]
CONSOLE_HEADER = config_parser.get("HEADERS", "CONSOLE", fallback="Header Error").strip('"')

# [Migration] Auto-add missing columns to existing config.ini
def ensure_config_migration():
    """
    Check if config.ini exists and has the old CSV header.
    If 'DIE_ID' is missing, append the new columns and save.
    """
    if not os.path.exists(CONFIG_FILE):
        return

    parser = configparser.ConfigParser()
    try:
        read_config_with_fallback(parser, CONFIG_FILE)
        if 'HEADERS' in parser and 'CSV' in parser['HEADERS']:
            current_header = parser['HEADERS']['CSV']
            if "DIE_ID" not in current_header:
                print("[Config] Old CSV header detected. Migrating...")
                new_header = current_header + ",DIE_ID,Billet_CycleID"
                parser['HEADERS']['CSV'] = new_header
                
                ok, err, pending = safe_write_config_parser(parser, CONFIG_FILE)
                if not ok:
                    print(f"[Config] Migration save failed: {err}")
                    if pending:
                        print(f"[Config] Pending config saved: {pending}")
                print("[Config] Migration Complete: Added DIE_ID, Billet_CycleID.")
            else:
                 # Ensure internal config also reflects it if parser read old file before update?
                 # Actually config_parser is already loaded. This is for persistent file update.
                 pass

    except Exception as e:
        print(f"[Config] Migration Failed: {e}")

# Run migration on import
ensure_config_migration()
