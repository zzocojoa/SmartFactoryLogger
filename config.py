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
# C:\Users\<User>\AppData\Roaming\SmartFactoryLogger
APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), 'SmartFactoryLogger')

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

# ConfigParser 초기화
config = configparser.ConfigParser()

# 파일 존재 여부 확인 및 읽기
if not os.path.exists(CONFIG_FILE):
    print(f"[Warning] {CONFIG_FILE} not found. Creating default configuration...")
    try:
        # Create default config
        config['SYSTEM'] = {
            'DeviceName': '창녕 2호기',
            'IntervalSec': '0.2'
        }
        config['EXTRUDER'] = {
            'IP': '192.168.10.10',
            'Port': '12289'
        }
        config['SPOT'] = {
            'IP': '10.1.10.50'
        }
        config['LS_PLC'] = {
            'IP': '192.168.10.220',
            'Port': '2004'
        }
        config['SETTINGS'] = {
            'Password': '1234',
            # 로그와 스냅샷도 AppData 내부에 저장하거나 사용자가 변경 가능
            'LogPath': os.path.join(APP_DATA_DIR, 'logs'),
            'SnapshotPath': os.path.join(APP_DATA_DIR, 'snapshots'),
            'AutoSave': 'True'
        }
        config['HEADERS'] = {
            'CSV': "Date,Time,Temperature,메인압력,빌렛길이,콘테이너온도 앞쪽,콘테이너온도 뒷쪽,생산카운터,현재속도,압출종료 위치,Mold1,Mold2,Mold3,Mold4,Mold5,Mold6,Billet_Temp,At_Pre,At_Temp",
            'CONSOLE': "| Temp  | 압력  | 빌렛L | 콘(앞)| 콘(뒤)| 카운트| 속도 | 종료 | Mold1 | Mold2 | Mold3 | Mold4 | Mold5 | Mold6 | BillT | AtPre | AtTmp"
        }
        # LS_PLC_TARGETS (Default)
        config['LS_PLC_TARGETS'] = {
            '%DW250': 'Mold1',
            '%DW256': 'Mold2',
            '%DW262': 'Mold3',
            '%DW288': 'Mold4',
            '%DW276': 'Mold5',
            '%DW282': 'Mold6',
            '%DW268': 'Billet_Temp',
            '%DW40': 'At_Temp',
            '%DW50': 'At_Pre'
        }

        with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        
        print(f"[Info] Default config created at {CONFIG_FILE}")
    except Exception as e:
        print(f"[Critical] Failed to create default config: {e}")
        sys.exit(1)

try:
    config.read(CONFIG_FILE, encoding='utf-8')

    # ---------------------------------------------------------------------------
    # [0] 환경 설정 (SETTINGS)
    # ---------------------------------------------------------------------------
    PASSWORD = config.get("SETTINGS", "Password", fallback="1234")
    LOG_PATH = config.get("SETTINGS", "LogPath", fallback="./logs")
    SNAPSHOT_PATH = config.get("SETTINGS", "SnapshotPath", fallback="./snapshots")
    AUTO_SAVE = config.getboolean("SETTINGS", "AutoSave", fallback=True)
    
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
    DEVICE_NAME = config.get("SYSTEM", "DeviceName", fallback="창녕 2호기")
    INTERVAL_SEC = config.getfloat("SYSTEM", "IntervalSec", fallback=0.2)

    # ---------------------------------------------------------------------------
    # [2] 장비 IP 및 포트 설정
    # ---------------------------------------------------------------------------
    # [압출기]
    IP_EXT = config.get("EXTRUDER", "IP", fallback="192.168.10.10")
    PORT_EXT = config.getint("EXTRUDER", "Port", fallback=12289)

    # [적외선 온도기]
    IP_SPOT = config.get("SPOT", "IP", fallback="10.1.10.50")
    URL_SPOT = f"http://{IP_SPOT}/output?p=temperature"

    # [LS PLC (XGT)]
    IP_LS = config.get("LS_PLC", "IP", fallback="192.168.10.220")
    PORT_LS = config.getint("LS_PLC", "Port", fallback=2004)

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
