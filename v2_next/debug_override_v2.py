
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend import config
from backend.services import config_service

print(f"Config Path: {config.CONFIG_PATH}")
print(f"AppData Dir: {config.APP_DATA_DIR}")

try:
    print("Attempting to enable override...")
    result = config_service.set_override_enabled(True, "", "debug_script")
    print("Success:", result)
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
