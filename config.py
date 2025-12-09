# config.py
import configparser
import os
import sys
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
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. 실행 파일 옆에 config.ini가 있는지 확인 (Portable Mode 우선)
LOCAL_CONFIG = os.path.join(EXE_DIR, "config.ini")
if os.path.exists(LOCAL_CONFIG):
    APP_DATA_DIR = EXE_DIR
    print(f"[Config] Portable Mode Detected. Using: {APP_DATA_DIR}")
else:
    # 3. 없으면 AppData 사용 (Standard Install Mode)
    if sys.platform == "win32":
        APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), 'SmartFactoryLogger')
    elif sys.platform == "darwin":
        APP_DATA_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "SmartFactoryLogger")
    else:
        APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".config", "SmartFactoryLogger")
    print(f"[Config] Portable Config NOT found. Using AppData: {APP_DATA_DIR}")

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
        'CrosshairColor': 'lime',
        'CrosshairThickness': '2',
        'CrosshairSize': '20',
        'CrosshairGap': '5',
        'FocusURL': 'http://10.1.10.50/control?p=focus',
        'FocusStep': '200',
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

# Perform Sync
sync_config(config_parser, CONFIG_FILE, DEFAULT_CONFIG)

# [Debug] Popup Removed - Configuration Verified

# ---------------------------------------------------------------------------
# [Safe Loading] Pydantic Validation
# ---------------------------------------------------------------------------
try:
    # 1. Parser -> Dict 변환
    config_dict = {s: dict(config_parser.items(s)) for s in config_parser.sections()}
    
    # 2. Pydantic을 이용한 유효성 검사 및 타입 변환
    #    (검증 실패 시 except 블록으로 이동하여 기본값 사용)
    app_config = AppConfig(**config_dict)
    
    print("[Config] Configuration loaded and validated successfully.")

except Exception as e:
    print(f"[Config] Validation Failed: {e}")
    
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
            
        tkinter.messagebox.showwarning("Config Error", f"설정 파일(config.ini) 데이터 오류.\n\nError: {e}{debug_info}")
        _root.destroy()
    except: pass
    
    print("[Config] Falling back to DEFAULT configuration for safety.")
    # Fallback: Default 값을 사용하여 AppConfig 생성 (타입 변환 보장)
    # 주의: DEFAULT_CONFIG의 값들은 모두 string이므로, AppConfig가 이를 파싱해야 함.
    # Pydantic은 문자열 '0.2'를 float 0.2로 자동 변환해줌.
    app_config = AppConfig(**DEFAULT_CONFIG)

# ---------------------------------------------------------------------------
# [Export] 전역 변수 설정 (사용 편의성)
# ---------------------------------------------------------------------------

# [0] 환경 설정 (SETTINGS)
PASSWORD = app_config.SETTINGS.Password
LOG_PATH = app_config.SETTINGS.LogPath
SNAPSHOT_PATH = app_config.SETTINGS.SnapshotPath
AUTO_SAVE = app_config.SETTINGS.AutoSave

# 로그 폴더 절대 경로 변환
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

        # Combine
        # Keys are "Speed", "Press" etc.
        # We need to iterate all potential keys.
        # Let's union keys from both
        all_keys = set(enables.keys()) | set(values.keys())
        
        for k in all_keys:
            if k == 'MASTER_ON': continue
            
            # Value convert (None if empty/invalid)
            val = values.get(k)
            try:
                f_val = float(val) if val is not None and val != "" else None
            except:
                f_val = None
                
            is_enabled = enables.get(k, False)
            # Pydantic boolean might be True/False directly
            
            t_data[k] = {
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
