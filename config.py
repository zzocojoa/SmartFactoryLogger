# config.py
import configparser
import os
import sys

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
# 플랫폼별 앱 데이터 경로 설정
if sys.platform == "win32":
    APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), 'SmartFactoryLogger')
elif sys.platform == "darwin":
    APP_DATA_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "SmartFactoryLogger")
else:
    # Linux/Unix
    APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".config", "SmartFactoryLogger")

if not os.path.exists(APP_DATA_DIR):
    try:
        os.makedirs(APP_DATA_DIR)
        print(f"[Info] Created AppData directory: {APP_DATA_DIR}")
    except Exception as e:
        print(f"[Critical] Failed to create AppData directory: {e}")

# 설정 파일 위치
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.ini")

# 기본 경로 설정을 위한 Base Dir (옵션)
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
        'FocusURL': 'http://10.1.10.50/control?p=focus',
        'FocusStep': '50',
        'WidgetWidth': '512',
        'WidgetHeight': '288'
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
    'HEADERS': {
        'CSV': "Date,Time,Temperature,메인압력,빌렛길이,콘테이너온도 앞쪽,콘테이너온도 뒷쪽,생산카운터,현재속도,압출종료 위치,Mold1,Mold2,Mold3,Mold4,Mold5,Mold6,Billet_Temp,At_Pre,At_Temp",
        'CONSOLE': "| Temp  | 압력  | 빌렛L | 콘(앞)| 콘(뒤)| 카운트| 속도 | 종료 | Mold1 | Mold2 | Mold3 | Mold4 | Mold5 | Mold6 | BillT | AtPre | AtTmp"
    }
}

# ConfigParser Init
config = configparser.ConfigParser()

def sync_config(config_obj, file_path, defaults):
    """
    Synchronizes the config object with default values.
    - Creates file if not likely exists.
    - Adds missing sections/keys.
    - Preserves existing user values.
    """
    is_modified = False
    
    # 1. Load existing
    if os.path.exists(file_path):
        try:
            config_obj.read(file_path, encoding='utf-8')
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
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                config_obj.write(f)
            print(f"[Config] Updated configuration at {file_path}")
        except Exception as e:
            print(f"[Config] Failed to save config: {e}")

def safe_get_int(section, key, fallback):
    try:
        return config.getint(section, key, fallback=fallback)
    except Exception:
        print(f"[Config] Invalid integer for [{section}] {key}. Using default: {fallback}")
        return fallback

def safe_get_float(section, key, fallback):
    try:
        return config.getfloat(section, key, fallback=fallback)
    except Exception:
        print(f"[Config] Invalid float for [{section}] {key}. Using default: {fallback}")
        return fallback

# Perform Sync
sync_config(config, CONFIG_FILE, DEFAULT_CONFIG)

try:
    # ---------------------------------------------------------------------------
    # [0] 환경 설정 (SETTINGS)
    # ---------------------------------------------------------------------------
    PASSWORD = config.get("SETTINGS", "Password", fallback=DEFAULT_CONFIG['SETTINGS']['Password'])
    LOG_PATH = config.get("SETTINGS", "LogPath", fallback=DEFAULT_CONFIG['SETTINGS']['LogPath'])
    SNAPSHOT_PATH = config.get("SETTINGS", "SnapshotPath", fallback=DEFAULT_CONFIG['SETTINGS']['SnapshotPath'])
    AUTO_SAVE = config.getboolean("SETTINGS", "AutoSave", fallback=DEFAULT_CONFIG['SETTINGS']['AutoSave'] == 'True')
    
    # 로그 폴더 절대 경로 변환 (상대 경로일 경우 BASE_DIR 기준)
    if not os.path.isabs(LOG_PATH):
        LOG_PATH = os.path.join(BASE_DIR, LOG_PATH)
        
    if not os.path.exists(LOG_PATH):
        try: os.makedirs(LOG_PATH)
        except: pass

    # 스냅샷 폴더 절대 경로 변환
    if not os.path.isabs(SNAPSHOT_PATH):
        SNAPSHOT_PATH = os.path.join(BASE_DIR, SNAPSHOT_PATH)

    if not os.path.exists(SNAPSHOT_PATH):
        try: os.makedirs(SNAPSHOT_PATH)
        except: pass

    # ---------------------------------------------------------------------------
    # [1] 기본 설정
    # ---------------------------------------------------------------------------
    DEVICE_NAME = config.get("SYSTEM", "DeviceName", fallback=DEFAULT_CONFIG['SYSTEM']['DeviceName'])
    INTERVAL_SEC = safe_get_float("SYSTEM", "IntervalSec", float(DEFAULT_CONFIG['SYSTEM']['IntervalSec']))

    # ---------------------------------------------------------------------------
    # [2] 장비 IP 및 포트 설정
    # ---------------------------------------------------------------------------
    # [압출기]
    IP_EXT = config.get("EXTRUDER", "IP", fallback=DEFAULT_CONFIG['EXTRUDER']['IP'])
    PORT_EXT = safe_get_int("EXTRUDER", "Port", int(DEFAULT_CONFIG['EXTRUDER']['Port']))

    # [적외선 온도기]
    IP_SPOT = config.get("SPOT", "IP", fallback=DEFAULT_CONFIG['SPOT']['IP'])
    URL_SPOT = f"http://{IP_SPOT}/output?p=temperature"
    # Default to /image.jpg (Confirmed working)
    URL_SPOT_IMAGE = config.get("SPOT", "ImageURL", fallback=DEFAULT_CONFIG['SPOT']['ImageURL'])
    SPOT_REFRESH_INTERVAL = safe_get_float("SPOT", "RefreshInterval", float(DEFAULT_CONFIG['SPOT']['RefreshInterval']))
    SPOT_CROSSHAIR_X = safe_get_float("SPOT", "CrosshairX", float(DEFAULT_CONFIG['SPOT']['CrosshairX']))
    SPOT_CROSSHAIR_Y = safe_get_float("SPOT", "CrosshairY", float(DEFAULT_CONFIG['SPOT']['CrosshairY']))
    
    # [SPOT Actuator Control]
    # Actuator Manual Move is NOT supported by standard API.
    # We use Focus Control instead.
    URL_SPOT_FOCUS = config.get("SPOT", "FocusURL", fallback=DEFAULT_CONFIG['SPOT']['FocusURL'])
    SPOT_FOCUS_STEP = safe_get_int("SPOT", "FocusStep", int(DEFAULT_CONFIG['SPOT']['FocusStep'])) # mm step

    # [SPOT Widget Size]
    SPOT_WIDGET_WIDTH = safe_get_int("SPOT", "WidgetWidth", int(DEFAULT_CONFIG['SPOT']['WidgetWidth']))
    SPOT_WIDGET_HEIGHT = safe_get_int("SPOT", "WidgetHeight", int(DEFAULT_CONFIG['SPOT']['WidgetHeight']))

    # [LS PLC (XGT)]
    IP_LS = config.get("LS_PLC", "IP", fallback=DEFAULT_CONFIG['LS_PLC']['IP'])
    PORT_LS = safe_get_int("LS_PLC", "Port", int(DEFAULT_CONFIG['LS_PLC']['Port']))

    # ---------------------------------------------------------------------------
    # [3] LS PLC 타겟 및 컬럼 매핑
    # ---------------------------------------------------------------------------
    # INI 파일의 [LS_PLC_TARGETS] 섹션을 읽어서 리스트로 변환
    # (Key, Value) -> ("%DW250", "Mold1")
    LS_TARGETS = []
    if config.has_section("LS_PLC_TARGETS"):
        for key, value in config.items("LS_PLC_TARGETS"):
            # configparser는 키를 소문자로 변환하므로, 대문자 유지가 필요하면 주의
            # 여기서는 주소(%DW...)가 대소문자 구분 없거나, 원본 키를 가져오는 로직 필요시 optionxform 사용
            # 하지만 %DW는 대소문자 상관없으므로 그대로 사용. 단, % 기호 처리에 주의.
            # configparser에서 %는 interpolation으로 쓰일 수 있음. -> RawConfigParser 사용 권장 혹은 % escaping.
            # 여기서는 SafeConfigParser(기본) 사용 시 %를 %%로 써야 할 수도 있음.
            # 간단하게는 키를 대문자로 변환하여 저장.
            addr = key.upper() 
            LS_TARGETS.append((addr, value))
    
    # ---------------------------------------------------------------------------
    # [4] CSV 및 출력 헤더 설정
    # ---------------------------------------------------------------------------
    csv_str = config.get("HEADERS", "CSV", fallback="")
    CSV_HEADER = [x.strip() for x in csv_str.split(",") if x.strip()]

    CONSOLE_HEADER = config.get("HEADERS", "CONSOLE", fallback="Header Error").strip('"')

except Exception as e:
    print(f"[Critical] Error parsing config.ini: {e}")
    sys.exit(1)
