from pathlib import Path
import sys

# Base URLs
MES_BASE_URL = "https://dmc.mescloud.net"
LOGIN_URL = f"{MES_BASE_URL}/Default.aspx"

# Selectors
LOGIN_SELECTOR_ID = "#txt_userId"
LOGIN_SELECTOR_PW = "#txt_userPw"
LOGIN_SELECTOR_BTN = "#btnLogin"

# Timeouts (ms)
DEFAULT_TIMEOUT = 30000
LONG_TIMEOUT = 60000

# Paths
# Now integrated with SmartFactoryLogger v2_next
from .. import config

PROJECT_ROOT = Path(config.__file__).resolve().parent
# Reuse the main log architecture (either AppData or Portable folder)
DATA_DIR = config.APP_DATA_DIR / "logs" / "mes_data"
CONFIG_FILE = config.CONFIG_PATH or (PROJECT_ROOT / "config.ini")

# For EXE environments, we need to handle inner resource paths carefully
if getattr(sys, "frozen", False):
    # PyInstaller stores data in _MEIPASS
    base_resource_path = Path(sys._MEIPASS) / "backend"
else:
    base_resource_path = PROJECT_ROOT

STRUCTURES_FILE = base_resource_path / "mes_bridge" / "data" / "page_structures.json"
# Note: Ensure the structures file exists in its new location

# Business Constants
DATA_START_YEAR = 2016
IGNORE_PAGES = {"app_line", "trace_lot"}
