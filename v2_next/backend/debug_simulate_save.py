import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.services.config_service import get_config_snapshot, update_config
from backend.services.config_manager import config_manager
from backend.models.config_model import ConfigUpdate

print(">>> Simulating Save without Changes...")

try:
    # 1. Get current snapshot
    snapshot = get_config_snapshot()
    values = snapshot['values']
    
    # 2. Construct payload (mimicking frontend behavior)
    # We need to map the flat structure back to ConfigUpdate model properly
    # Note: This is simplified.
    
    payload_dict = {
        "extruder": values.get("extruder"),
        "ls_plc": values.get("ls_plc"),
        "spot": values.get("spot"),
        "settings": values.get("settings"),
        "logging": values.get("logging"),
        "thresholds": values.get("thresholds"), # correct structure?
        "system": values.get("system")
    }
    
    # Fix thresholds structure if needed (frontend sends enable/values inside)
    # Backend snapshot has {values: ..., enable: ...} which matches ConfigUpdate
    
    # Fix spot.refresh_interval type (snapshot might have float, payload expects float)
    
    payload = ConfigUpdate(**payload_dict)
    
    # 3. Update Config
    print(">>> Calling update_config()...")
    result = update_config(payload, source="local")
    
    print(f">>> Result Changes: {result.get('changes')}")
    print(f">>> Result Restart Required: {result.get('restart_required')}")
    print(f">>> Result Pending: {result.get('apply', {}).get('pending')}")

except Exception as e:
    import traceback
    traceback.print_exc()
